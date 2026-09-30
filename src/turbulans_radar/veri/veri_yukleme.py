"""
veri_yukleme.py
-----------------
İki veri kaynağını yüklemek için gereken fonksiyonlar:
  1. Copernicus/ERA5 hava durumu veri küpü (NetCDF -> xarray.Dataset)
  2. OpenSky (Trino) üzerinden GERÇEK uçuş verisi, callsign'a göre sorgulanır.

ÖNEMLİ GÜNCELLEME (bkz. https://openskynetwork.github.io/opensky-api/trino.html):
  - OpenSky 2024'te yeni backend'e geçti. Trino artık kullanıcı adı/şifre
    (BasicAuthentication) KABUL ETMİYOR; tarayıcı üzerinden giriş yaptıran
    OAuth2/"external authentication" akışı kullanıyor. Eski koddaki
    BasicAuthentication bu yüzden her zaman "401 Access Denied" veriyordu --
    bu, kimlik bilgilerinin yanlış olmasıyla ilgili değildi.
  - Catalog "opensky" değil "minio"; schema "osky" olmalı.
  - state_vectors_data4 gibi tablolarda artık 'hour' partition sütununda
    filtre ZORUNLU (filtresiz sorgular Trino tarafından otomatik reddediliyor
    ve tekrarlanan ihlaller hesap askıya alınmasına yol açabiliyor).
"""

import glob
import math
import os
import threading
from collections import OrderedDict

import numpy as np
import pandas as pd
import trino
import xarray as xr
from trino.auth import OAuth2Authentication
from trino.exceptions import (
    Http502Error,
    Http503Error,
    Http504Error,
    TrinoConnectionError,
    TrinoExternalError,
    TrinoInternalError,
)

from turbulans_radar import config
from turbulans_radar.veri.kimlik_dogrulama import kimlik_bilgilerini_al
from turbulans_radar.yeniden_deneme import gecici_hatada_yeniden_dene

# OpenSky'yi rate-limit/ban riskine sokmamak için SADECE geçici (transient)
# ağ/sunucu hatalarında (bağlantı kopması, 502/503/504, dahili Trino hatası)
# yeniden deniyoruz -- kimlik hatası veya hatalı sorgu gibi kalıcı hatalarda
# retry YAPILMAZ. Deneme sayısı bilerek düşük (3) ve aralar üstel artan
# (2s, 4s, 8s...) tutuluyor; sunucuyu art arda isteklerle yormamak için.
_GECICI_HATALAR = (
    TrinoConnectionError,
    TrinoExternalError,
    TrinoInternalError,
    Http502Error,
    Http503Error,
    Http504Error,
    ConnectionError,
    TimeoutError,
)

_yeniden_dene = gecici_hatada_yeniden_dene(_GECICI_HATALAR, azami_bekleme_saniye=30)


# ---------------------------------------------------------------------------
# 1) Copernicus / ERA5 veri küpü
# ---------------------------------------------------------------------------


def hava_durumu_yukle(dosya_yolu=config.HAVA_DURUMU_DOSYASI):
    """NetCDF veri küpünü açar. Dosya bulunamazsa açıklayıcı hata verir."""
    try:
        return xr.open_dataset(dosya_yolu)
    except FileNotFoundError as e:
        raise FileNotFoundError(
            f"'{dosya_yolu}' bulunamadı. Copernicus veri küpünü indirip proje klasörüne koyduğundan emin ol."
        ) from e


# NetCDF/HDF5 thread-safe değil: API'nin iş parçacıkları aynı .nc dosyasını
# paralel okuduğunda 'access violation' ile çökebiliyordu. Tüm dosya erişimi
# (açma, koordinat okuma, yükleme) bu kilitle tek sıraya alınır; bellekteki
# küplere erişim ayrı kilitle korunur, önbellek isabetleri yükleme beklemez.
hdf5_kilidi = threading.Lock()
_onbellek_kilidi = threading.Lock()
_onbellek: "OrderedDict[tuple, xr.Dataset]" = OrderedDict()
_meta_onbellegi: dict = {}
_ZAMAN_PAYI = pd.Timedelta(hours=3)


def _onbellekten_al(anahtar, yukleyici):
    """Bellek bütçeli (config.KUP_ONBELLEK_MAKS_MB) LRU önbellek: en uzun süre
    kullanılmayan küp/pencere bütçe aşılınca atılır. Anahtar: (dosya_yolu,
    pencere) -- pencere None ise tüm küp."""
    with _onbellek_kilidi:
        if anahtar in _onbellek:
            _onbellek.move_to_end(anahtar)
            return _onbellek[anahtar]
    with hdf5_kilidi:
        with _onbellek_kilidi:
            if anahtar in _onbellek:
                _onbellek.move_to_end(anahtar)
                return _onbellek[anahtar]
        kup = yukleyici()
    with _onbellek_kilidi:
        _onbellek[anahtar] = kup
        butce = config.KUP_ONBELLEK_MAKS_MB * 1024 * 1024
        while len(_onbellek) > 1 and sum(k.nbytes for k in _onbellek.values()) > butce:
            _onbellek.popitem(last=False)
    return kup


def onbellek_durumu() -> dict:
    with _onbellek_kilidi:
        return {
            "kup_sayisi": len(_onbellek),
            "bayt": int(sum(k.nbytes for k in _onbellek.values())),
            "butce_bayt": int(config.KUP_ONBELLEK_MAKS_MB * 1024 * 1024),
        }


def hava_durumu_onbellekli_yukle(dosya_yolu=config.HAVA_DURUMU_DOSYASI):
    """Küpü TAMAMEN belleğe yükleyip dosyayı hemen kapatır (bkz. hdf5_kilidi)."""

    def _yukle():
        with hava_durumu_yukle(dosya_yolu) as veri_kupu:
            return veri_kupu.load()

    return _onbellekten_al((dosya_yolu, None), _yukle)


def _utc_tz_siz(zaman) -> pd.Timestamp:
    """Küplerin valid_time koordinatı saat dilimsiz UTC'dir."""
    ts = pd.Timestamp(zaman)
    return ts if ts.tzinfo is None else ts.tz_convert("UTC").tz_localize(None)


def _pencere(enlem_araligi, boylam_araligi, zaman_araligi):
    """İstenen bölge/zamanı 1° ve 6 saatlik sınırlara DIŞA doğru hizalar --
    yakın istekler aynı pencereyi (önbellek isabetini) paylaşsın diye."""
    return (
        math.floor(enlem_araligi[0]),
        math.ceil(enlem_araligi[1]),
        math.floor(boylam_araligi[0]),
        math.ceil(boylam_araligi[1]),
        (_utc_tz_siz(zaman_araligi[0]) - _ZAMAN_PAYI).floor("6h"),
        (_utc_tz_siz(zaman_araligi[1]) + _ZAMAN_PAYI).ceil("6h"),
    )


def _dilim(koordinat, alt, ust):
    return slice(ust, alt) if koordinat.size > 1 and koordinat[0] > koordinat[-1] else slice(alt, ust)


def hava_durumu_penceresi_yukle(dosya_yolu, enlem_araligi, boylam_araligi, zaman_araligi):
    """Büyük bir küpün sadece istenen bölge/zaman penceresini belleğe okur
    (tüm küp değil) -- GB boyutlu arşivlerde bellek, rotanın kapladığı alanla
    sınırlı kalır. Tüm basınç seviyeleri korunur."""
    pencere = _pencere(enlem_araligi, boylam_araligi, zaman_araligi)

    def _yukle():
        enlem_min, enlem_maks, boylam_min, boylam_maks, zaman_min, zaman_maks = pencere
        with hava_durumu_yukle(dosya_yolu) as veri_kupu:
            alt = veri_kupu.sel(
                latitude=_dilim(veri_kupu["latitude"].values, enlem_min, enlem_maks),
                longitude=_dilim(veri_kupu["longitude"].values, boylam_min, boylam_maks),
                valid_time=slice(zaman_min, zaman_maks),
            ).load()
        alt.encoding["source"] = veri_kupu.encoding.get("source", dosya_yolu)
        return alt

    return _onbellekten_al((dosya_yolu, pencere), _yukle)


def onbellekten_cikar(dosya_yolu):
    with _onbellek_kilidi:
        for anahtar in [a for a in _onbellek if a[0] == dosya_yolu]:
            del _onbellek[anahtar]
    _meta_onbellegi.pop(dosya_yolu, None)


def hava_durumu_dosyalari():
    """Ana küp (config.HAVA_DURUMU_DOSYASI) + config.EK_HAVA_DURUMU_KLASORU'ndaki
    tüm .nc küpleri (örn. ml_veri_indir.py'nin indirdiği ABD küpleri) --
    sadece diskte gerçekten var olanlar."""
    dosyalar = [config.HAVA_DURUMU_DOSYASI]
    for klasor in (config.EK_HAVA_DURUMU_KLASORU, config.ERA5_UCUS_KLASORU):
        if klasor:
            dosyalar += sorted(glob.glob(os.path.join(klasor, "*.nc")))
    return [d for d in dosyalar if os.path.isfile(d)]


def dosya_meta_verisi(dosya_yolu) -> dict:
    """Küpün kapsamı (enlem/boylam/zaman aralığı) -- veri yüklenmeden, sadece
    koordinatlar okunarak; dosya değişmedikçe süreç içinde önbellekte."""
    durum = os.stat(dosya_yolu)
    imza = (durum.st_mtime_ns, durum.st_size)
    kayit = _meta_onbellegi.get(dosya_yolu)
    if kayit is None or kayit["imza"] != imza:
        with hdf5_kilidi, hava_durumu_yukle(dosya_yolu) as veri_kupu:
            zamanlar = veri_kupu["valid_time"].values
            kayit = {
                "imza": imza,
                "enlem": (float(veri_kupu["latitude"].min()), float(veri_kupu["latitude"].max())),
                "boylam": (float(veri_kupu["longitude"].min()), float(veri_kupu["longitude"].max())),
                "zaman": (pd.Timestamp(zamanlar.min()), pd.Timestamp(zamanlar.max())),
            }
        _meta_onbellegi[dosya_yolu] = kayit
    return kayit


def _meta_kesisiyor(meta, enlem_araligi, boylam_araligi, zaman_araligi):
    zaman_min, zaman_maks = map(_utc_tz_siz, zaman_araligi)
    return (
        meta["enlem"][0] <= enlem_araligi[1]
        and meta["enlem"][1] >= enlem_araligi[0]
        and meta["boylam"][0] <= boylam_araligi[1]
        and meta["boylam"][1] >= boylam_araligi[0]
        and meta["zaman"][0] - _ZAMAN_PAYI <= zaman_maks
        and meta["zaman"][1] + _ZAMAN_PAYI >= zaman_min
    )


def _aday_dosyalar(enlem_araligi, boylam_araligi, zaman_araligi):
    """Noktaların bölge/zamanıyla kesişen yerel küpler. Önce hava_durumu_
    kupleri KATALOĞU (dosya açılmadan); katalogda olmayan ya da veritabanı
    erişilemezken dosyanın kendi koordinat meta verisi kullanılır."""
    yerel = hava_durumu_dosyalari()
    try:
        from turbulans_radar.depo.kup_katalogu import kesisen_kup_yollari

        kesisen, kayitli = kesisen_kup_yollari("era5", *enlem_araligi, *boylam_araligi, *zaman_araligi)
    except Exception:
        kesisen, kayitli = set(), set()
    return [
        d
        for d in yerel
        if d in kesisen
        or (d not in kayitli and _meta_kesisiyor(dosya_meta_verisi(d), enlem_araligi, boylam_araligi, zaman_araligi))
    ]


def _kupu_yukle(dosya, enlem_araligi, boylam_araligi, zaman_araligi):
    if os.path.getsize(dosya) <= config.KUP_TAM_YUKLEME_ESIGI_MB * 1024 * 1024:
        return hava_durumu_onbellekli_yukle(dosya)
    return hava_durumu_penceresi_yukle(dosya, enlem_araligi, boylam_araligi, zaman_araligi)


def kapsayan_veri_kupunu_bul(enlemler, boylamlar, zamanlar, basinc_hpa=None, pay_derece=1.0):
    """Yerel küpler arasından verilen noktaların EN ÇOĞUNU kapsayanı döndürür
    (bkz. eslestirme.kapsam_disi_maskesi). Hiçbiri tek bir noktayı bile
    kapsamıyorsa None -- uydurma bir eşleşme yapılmaz. Sadece bölge/zamanı
    kesişen aday küpler yüklenir; config.KUP_TAM_YUKLEME_ESIGI_MB'den büyük
    küplerden noktaların pay_derece genişletilmiş penceresi okunur (A*
    ızgarası gibi noktaların çevresini de kullanacaklar için geniş pay verilir)."""
    from turbulans_radar.fizik.eslestirme import kapsam_disi_maskesi

    enlem_dizisi = np.asarray(enlemler, dtype=float)
    boylam_dizisi = np.asarray(boylamlar, dtype=float)
    if enlem_dizisi.size == 0:
        return None
    zaman_dizisi = pd.DatetimeIndex(pd.to_datetime(list(zamanlar), utc=True))
    enlem_araligi = (float(np.nanmin(enlem_dizisi)) - pay_derece, float(np.nanmax(enlem_dizisi)) + pay_derece)
    boylam_araligi = (float(np.nanmin(boylam_dizisi)) - pay_derece, float(np.nanmax(boylam_dizisi)) + pay_derece)
    zaman_araligi = (zaman_dizisi.min(), zaman_dizisi.max())

    en_iyi_kup, en_iyi_sayi = None, 0
    for dosya in _aday_dosyalar(enlem_araligi, boylam_araligi, zaman_araligi):
        veri_kupu = _kupu_yukle(dosya, enlem_araligi, boylam_araligi, zaman_araligi)
        if any(veri_kupu.sizes[b] == 0 for b in ("latitude", "longitude", "valid_time") if b in veri_kupu.sizes):
            continue
        kapsanan = int((~kapsam_disi_maskesi(veri_kupu, enlemler, boylamlar, zamanlar, basinc_hpa)).sum())
        if kapsanan > en_iyi_sayi:
            en_iyi_kup, en_iyi_sayi = veri_kupu, kapsanan
    return en_iyi_kup


def veri_kupu_adi(veri_kupu):
    kaynak = veri_kupu.encoding.get("source") if veri_kupu is not None else None
    return os.path.basename(kaynak) if kaynak else config.HAVA_DURUMU_DOSYASI


# ---------------------------------------------------------------------------
# 2) OpenSky / Trino bağlantısı
# ---------------------------------------------------------------------------

# OAuth2Authentication kendi token önbelleğini (keyring yoksa bellek-içi) bu
# nesneye bağlı tutuyor. Her trino_baglantisi_olustur() çağrısında YENİ bir
# OAuth2Authentication() oluşturmak (eski davranış) önbelleği sıfırlıyor ve
# AYNI süreç içinde bile (örn. toplu_analiz.py'nin ardışık uçuşları veya
# api_servisi.py'nin arka arkaya gelen /analiz/ucus istekleri) her seferinde
# yeniden tarayıcı girişi istenmesine yol açıyordu. Tekil (singleton) tutarak
# tek bir girişin süreç ömrü boyunca yeterli olmasını sağlıyoruz -- ayrıca
# OpenSky'ye gereksiz OAuth isteği gitmesini önlüyor.
_oauth2_kimlik_dogrulama = None


def _oauth2_kimlik_dogrulamasini_al():
    global _oauth2_kimlik_dogrulama
    if _oauth2_kimlik_dogrulama is None:
        _oauth2_kimlik_dogrulama = OAuth2Authentication()
    return _oauth2_kimlik_dogrulama


@_yeniden_dene
def trino_baglantisi_olustur():
    """
    OpenSky'nin Trino kümesine OAuth2 (external authentication) ile bağlanır.

    NOT: Bu artık kullanıcı adı/şifre ile DOĞRUDAN kimlik doğrulaması yapmaz.
    İlk sorgu çalıştırıldığında bir tarayıcı penceresi açılır (veya konsola
    bir URL basılır) ve OpenSky hesabınla web üzerinden giriş yapman istenir.
    Bu, senin CLI'da denediğin '--external-authentication' bayrağının Python
    karşılığıdır.
    """
    kullanici_adi, _ = kimlik_bilgilerini_al()
    # OpenSky kullanıcı adları küçük harfle saklanıyor; bağlanırken büyük/
    # küçük harf uyuşmazlığı sorun çıkarabiliyor.
    kullanici_adi = kullanici_adi.lower()

    print(
        "[Bilgi] Trino'ya OAuth2 ile bağlanılıyor. Bir tarayıcı penceresi "
        "açılabilir veya konsolda bir giriş linki görebilirsin -- OpenSky "
        "hesabınla (web arayüzündeki ile AYNI hesap) giriş yap."
    )

    baglanti = trino.dbapi.connect(
        host=config.TRINO_HOST,
        port=config.TRINO_PORT,
        user=kullanici_adi,
        auth=_oauth2_kimlik_dogrulamasini_al(),
        http_scheme="https",
        catalog=config.TRINO_CATALOG,
        schema=config.TRINO_SCHEMA,
    )
    return baglanti


@_yeniden_dene
def _sorgu_calistir(baglanti, sorgu, sutunlar, parametreler=None):
    """
    parametreler verilirse, sorgu metnindeki '?' yer tutucuları trino
    kütüphanesi tarafından GÜVENLİ şekilde (tip kontrolü + tırnak kaçışı ile)
    değerlerle değiştirilir -- callsign/icao24 gibi dışarıdan gelen (artık
    API üzerinden de tetiklenebilen) değerleri asla f-string ile doğrudan SQL
    içine gömmemek için (SQL enjeksiyonuna karşı).
    """
    imlec = baglanti.cursor()
    imlec.execute(sorgu, parametreler)
    sonuc = imlec.fetchall()
    return pd.DataFrame(sonuc, columns=sutunlar)


def ucus_numarasindan_icao24_bul(baglanti, ucus_numarasi, tarih_str):
    """
    Uçuş numarasından (callsign, örn. 'THY1234') icao24 adresini bulur.

    NOT: OpenSky'da callsign alanı sabit 8 karakter uzunluğunda, boşlukla
    doldurulmuş (padded) olarak saklanır — bu yüzden tam eşleşme için
    `ljust(8)` uyguluyoruz. `day` sütunu flights_data4'ün ZORUNLU partition
    sütunudur.

    tarih_str: 'YYYY-MM-DD' formatında, aranacak gün.
    Dönüş: eşleşen uçuşları içeren DataFrame (birden fazla olabilir,
    çünkü aynı uçuş numarası farklı günlerde/rotalarda tekrar edebilir).
    """
    gun_baslangic_ts = int(pd.Timestamp(tarih_str, tz="UTC").timestamp())
    gun_bitis_ts = gun_baslangic_ts + 86400

    sorgu = """
    SELECT icao24, callsign, firstseen, lastseen, estdepartureairport, estarrivalairport
    FROM flights_data4
    WHERE callsign = ?
    AND day >= ? AND day < ?
    ORDER BY firstseen
    """
    sutunlar = ["icao24", "callsign", "ilk_gorulme", "son_gorulme", "kalkis_havaalani", "varis_havaalani"]
    df = _sorgu_calistir(baglanti, sorgu, sutunlar, [ucus_numarasi.ljust(8), gun_baslangic_ts, gun_bitis_ts])

    if df.empty:
        print(
            f"[Uyarı] '{ucus_numarasi}' için {tarih_str} tarihinde flights_data4 "
            f"tablosunda eşleşme bulunamadı. Uçuş numarasını, tarihi veya "
            f"padding'i kontrol et."
        )
        return None
    return df


def ucus_rotasini_cek(baglanti, icao24, baslangic_ts, bitis_ts):
    """
    Belirli bir icao24 adresi ve zaman aralığı için ham state vector
    (konum, hız, irtifa) verisini çeker.

    ÖNEMLİ: state_vectors_data4'ün partition sütunu 'hour' -- saatin
    başlangıcına denk gelen unix timestamp. Bu filtre artık ZORUNLU,
    yoksa Trino sorguyu reddediyor. `time` filtresi tek başına yeterli
    DEĞİL, `hour` filtresi de eklenmeli.
    """
    baslangic_saat = (baslangic_ts // 3600) * 3600
    bitis_saat = (bitis_ts // 3600) * 3600

    # NOT: LIMIT değeri config.MAKS_STATE_VECTOR_SATIRI'den (sabit, kullanıcı
    # girdisi DEĞİL) geliyor -- bu yüzden parametre yerine doğrudan yazılıyor;
    # Trino'nun EXECUTE IMMEDIATE...USING'i her SQL konumunda (örn. LIMIT)
    # yer tutucuyu desteklemeyebiliyor. Kullanıcıdan gelen icao24/zaman
    # değerleri ise parametre olarak geçiliyor.
    sorgu = f"""
    SELECT time, icao24, lat, lon, velocity, heading, vertrate, geoaltitude, baroaltitude
    FROM state_vectors_data4
    WHERE icao24 = ?
    AND hour >= ? AND hour <= ?
    AND time >= ? AND time <= ?
    AND lat IS NOT NULL AND lon IS NOT NULL
    ORDER BY time
    LIMIT {config.MAKS_STATE_VECTOR_SATIRI}
    """
    sutunlar = ["zaman_unix", "icao24", "enlem", "boylam", "hiz", "yon", "dikey_hiz", "geo_irtifa_m", "baro_irtifa_m"]
    df = _sorgu_calistir(
        baglanti,
        sorgu,
        sutunlar,
        [icao24, baslangic_saat, bitis_saat, baslangic_ts, bitis_ts],
    )
    if not df.empty:
        df["zaman"] = pd.to_datetime(df["zaman_unix"], unit="s", utc=True)
    return df


def ucus_numarasi_ile_rota_cek(baglanti, ucus_numarasi, tarih_str):
    """
    Uçtan uca kolaylık fonksiyonu: uçuş numarasından başlayıp gerçek
    state-vector rotasını döndürür. Eşleşme yoksa None döner ("yapamıyorsan
    bırak" prensibiyle — hata fırlatıp pipeline'ı durdurmak yerine).
    """
    ucus_bilgisi = ucus_numarasindan_icao24_bul(baglanti, ucus_numarasi, tarih_str)
    if ucus_bilgisi is None or ucus_bilgisi.empty:
        return None

    ilk_kayit = ucus_bilgisi.iloc[0]
    rota = ucus_rotasini_cek(
        baglanti,
        icao24=ilk_kayit["icao24"],
        baslangic_ts=int(ilk_kayit["ilk_gorulme"]),
        bitis_ts=int(ilk_kayit["son_gorulme"]),
    )
    if rota.empty:
        print(f"[Uyarı] icao24={ilk_kayit['icao24']} için state_vectors_data4'te veri bulunamadı.")
        return None

    rota["ucus_numarasi"] = ucus_numarasi
    rota["kalkis_havaalani"] = ilk_kayit["kalkis_havaalani"]
    rota["varis_havaalani"] = ilk_kayit["varis_havaalani"]
    return rota
