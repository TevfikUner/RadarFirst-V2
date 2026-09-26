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

import threading

import pandas as pd
import trino
import xarray as xr
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential
from trino.auth import OAuth2Authentication
from trino.exceptions import (
    Http502Error,
    Http503Error,
    Http504Error,
    TrinoConnectionError,
    TrinoExternalError,
    TrinoInternalError,
)

import config
from kimlik_dogrulama import kimlik_bilgilerini_al

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

_yeniden_dene = retry(
    retry=retry_if_exception_type(_GECICI_HATALAR),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    reraise=True,
)


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


_veri_kupu_onbellegi = {}
_veri_kupu_kilidi = threading.Lock()


def hava_durumu_onbellekli_yukle(dosya_yolu=config.HAVA_DURUMU_DOSYASI):
    """Küpü bir kez BELLEĞE yükleyip dosyayı hemen kapatır: API'nin iş
    parçacıkları aynı .nc dosyasını paralel açık tuttuğunda HDF5 (thread-safe
    değil) 'access violation' ile çökebiliyordu."""
    with _veri_kupu_kilidi:
        if dosya_yolu not in _veri_kupu_onbellegi:
            with hava_durumu_yukle(dosya_yolu) as veri_kupu:
                _veri_kupu_onbellegi[dosya_yolu] = veri_kupu.load()
        return _veri_kupu_onbellegi[dosya_yolu]


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
