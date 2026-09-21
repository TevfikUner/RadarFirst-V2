"""
veri_yukleme.py
-----------------
İki veri kaynağını yüklemek için gereken fonksiyonlar:
  1. Copernicus/ERA5 hava durumu veri küpü (NetCDF -> xarray.Dataset)
  2. OpenSky (Trino) üzerinden GERÇEK uçuş verisi, artık UÇUŞ NUMARASINA
     (callsign) göre sorgulanabiliyor.

Eski `trino_baglanti.py`'de sadece sabit bir enlem/boylam/zaman kutusu
sorgulanıyordu ve tek bir uçuşu hedeflemek mümkün değildi. Burada
`flights_data4` tablosu üzerinden callsign -> icao24 eşlemesi yapılıyor,
sonra o icao24 için state_vectors_data4'ten rota çekiliyor.
"""

import xarray as xr
import pandas as pd
import trino
from trino.auth import BasicAuthentication
import config
from kimlik_dogrulama import kimlik_bilgilerini_al


# ---------------------------------------------------------------------------
# 1) Copernicus / ERA5 veri küpü
# ---------------------------------------------------------------------------

def hava_durumu_yukle(dosya_yolu=config.HAVA_DURUMU_DOSYASI):
    """NetCDF veri küpünü açar. Dosya bulunamazsa açıklayıcı hata verir."""
    try:
        return xr.open_dataset(dosya_yolu)
    except FileNotFoundError as e:
        raise FileNotFoundError(
            f"'{dosya_yolu}' bulunamadı. Copernicus veri küpünü indirip proje "
            f"klasörüne koyduğundan emin ol."
        ) from e


# ---------------------------------------------------------------------------
# 2) OpenSky / Trino bağlantısı
# ---------------------------------------------------------------------------

def trino_baglantisi_olustur():
    kullanici_adi, sifre = kimlik_bilgilerini_al()
    
    baglanti = trino.dbapi.connect(
        host=config.TRINO_HOST,
        port=config.TRINO_PORT,
        user=kullanici_adi,
        auth=BasicAuthentication(kullanici_adi, sifre),
        http_scheme='https',
        catalog=config.TRINO_CATALOG
    )
    return baglanti

def _sorgu_calistir(baglanti, sorgu, sutunlar):
    imlec = baglanti.cursor()
    imlec.execute(sorgu)
    sonuc = imlec.fetchall()
    return pd.DataFrame(sonuc, columns=sutunlar)


def ucus_numarasindan_icao24_bul(baglanti, ucus_numarasi, tarih_str):
    """
    Uçuş numarasından (callsign, örn. 'THY1234') icao24 adresini bulur.

    NOT: OpenSky'da callsign alanı sabit 8 karakter uzunluğunda, boşlukla
    doldurulmuş (padded) olarak saklanır — bu yüzden tam eşleşme için
    `ljust(8)` uyguluyoruz. `day` sütunu, günün başlangıcına denk gelen
    UNIX zaman damgasıdır (Trino tarafında `date_trunc('day', ...)` ile
    de filtrelenebilir).

    tarih_str: 'YYYY-MM-DD' formatında, aranacak gün.
    Dönüş: eşleşen uçuşları içeren DataFrame (birden fazla olabilir,
    çünkü aynı uçuş numarası farklı günlerde/rotalarda tekrar edebilir).
    """
    gun_baslangic_ts = int(pd.Timestamp(tarih_str, tz="UTC").timestamp())
    gun_bitis_ts = gun_baslangic_ts + 86400

    sorgu = f"""
    SELECT icao24, callsign, firstseen, lastseen, estdepartureairport, estarrivalairport
    FROM flights_data4
    WHERE callsign = '{ucus_numarasi.ljust(8)}'
    AND day >= {gun_baslangic_ts} AND day < {gun_bitis_ts}
    ORDER BY firstseen
    """
    sutunlar = ["icao24", "callsign", "ilk_gorulme", "son_gorulme", "kalkis_havaalani", "varis_havaalani"]
    df = _sorgu_calistir(baglanti, sorgu, sutunlar)

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
    """
    sorgu = f"""
    SELECT time, icao24, lat, lon, velocity, heading, vertrate, geoaltitude, baroaltitude
    FROM state_vectors_data4
    WHERE icao24 = '{icao24}'
    AND time >= {baslangic_ts} AND time <= {bitis_ts}
    AND lat IS NOT NULL AND lon IS NOT NULL
    ORDER BY time
    LIMIT {config.MAKS_STATE_VECTOR_SATIRI}
    """
    sutunlar = ["zaman_unix", "icao24", "enlem", "boylam", "hiz", "yon",
                "dikey_hiz", "geo_irtifa_m", "baro_irtifa_m"]
    df = _sorgu_calistir(baglanti, sorgu, sutunlar)
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
