"""
eslestirme.py
--------------
Gerçek uçuş rotasındaki (OpenSky) her noktayı, Copernicus veri küpündeki
en yakın (zaman, enlem, boylam, basınç seviyesi) hücresiyle eşleştirir ve
o hücre için Ellrod TI1 tabanlı türbülans proxy'sini hesaplar.

DÜZELTMELER:
  1. OpenSky'den gelen 'zaman' sütunu saat-dilimli (UTC, datetime64[s, UTC])
     iken ERA5 NetCDF'lerindeki 'valid_time' boyutu genelde saat-dilimsiz
     (datetime64[ns]) oluyor -- xarray bu iki tipi karşılaştıramadığı için
     "Cannot compare dtypes" hatası veriyordu. Zamanı seçim yapmadan önce
     saat-dilimsiz hale çeviriyoruz.
  2. Yatay deformasyon (tüm grid üzerinde .differentiate() gerektiriyor,
     pahalı bir işlem) eskiden HER TEK ROTA NOKTASI için yeniden
     hesaplanıyordu -- binlerce nokta için bu son derece yavaştı. Şimdi
     aynı (zaman, basınç seviyesi) kombinasyonu için deformasyon sadece
     BİR KEZ hesaplanıp önbelleğe alınıyor.
  3. ÖNEMLİ -- KAPSAMA ALANI KONTROLÜ: xarray'in .sel(method="nearest")
     fonksiyonu, "en yakın" nokta ne kadar UZAKTA olursa olsun bir sonuç
     döndürür -- mesafe sınırı yoktur. Bu yüzden veri küpü sadece Türkiye'yi
     kapsıyorsa ve rota Teksas'tan geçiyorsa, kod SESSİZCE Türkiye'nin en
     kenar hücresini "en yakın" diye kullanıp yanlış (ve rota boyunca hep
     benzer) sonuçlar üretiyordu -- hata vermiyordu. Şimdi her noktanın
     enlem/boylamının veri küpünün gerçekten kapsadığı aralıkta olup
     olmadığı ÖNCEDEN kontrol ediliyor; değilse açık bir hata fırlatılıyor
     (rotayi_hava_durumuyla_eslestir zaten bunu yakalayıp o noktayı NaN
     bırakıyor, ama artık SESSİZCE yanlış değer üretmek yerine gerçek
     sebebi console'a yazdırıyor).
"""

import numpy as np
import pandas as pd

import config
from birim_donusumleri import (
    irtifa_metre_to_basinc_hpa,
    en_yakin_basinc_seviyesi,
    basinc_hpa_to_irtifa_metre,
)
from turbulans_indeksleri import (
    yatay_deformasyon_hesapla,
    dusey_ruzgar_kaymasi_hesapla,
    ti1_indeksi_hesapla,
    ti1_den_edr_proxy_olcegine_cevir,
)


def _zamani_veri_kupune_uydur(zaman_degeri):
    """
    OpenSky'nin saat-dilimli (tz-aware, UTC) zaman damgasını, ERA5 veri
    küpünün genelde saat-dilimsiz (tz-naive) olan 'valid_time' boyutuyla
    karşılaştırılabilir hale getirir. İkisi de zaten UTC olduğu için
    sadece tz bilgisini kaldırmak (değeri KAYDIRMADAN) yeterli.
    """
    zaman_ts = pd.Timestamp(zaman_degeri)
    if zaman_ts.tzinfo is not None:
        zaman_ts = zaman_ts.tz_convert("UTC").tz_localize(None)
    return zaman_ts


def _kapsama_alanini_kontrol_et(veri_kupu, enlem, boylam, zaman_uyumlu, tolerans_derece=1.0):
    """
    Noktanın veri küpünün GERÇEKTEN kapsadığı enlem/boylam/zaman aralığında
    olup olmadığını kontrol eder. xarray'in .sel(method="nearest") fonksiyonu
    mesafe sınırı olmadan her zaman bir sonuç döndürdüğü için, bu kontrol
    olmadan "Teksas rotası - Türkiye verisi" gibi tamamen alakasız
    eşleşmeler SESSİZCE oluyor ve fark edilmiyor.
    """
    lat_min, lat_maks = float(veri_kupu["latitude"].min()), float(veri_kupu["latitude"].max())
    lon_min, lon_maks = float(veri_kupu["longitude"].min()), float(veri_kupu["longitude"].max())

    if not (lat_min - tolerans_derece <= enlem <= lat_maks + tolerans_derece):
        raise ValueError(
            f"Nokta enlemi ({enlem:.2f}) veri küpünün kapsadığı aralığın "
            f"({lat_min:.2f} - {lat_maks:.2f}) çok dışında. Bu rota, indirdiğin "
            f"hava durumu verisinin coğrafi alanını kapsamıyor."
        )
    if not (lon_min - tolerans_derece <= boylam <= lon_maks + tolerans_derece):
        raise ValueError(
            f"Nokta boylamı ({boylam:.2f}) veri küpünün kapsadığı aralığın "
            f"({lon_min:.2f} - {lon_maks:.2f}) çok dışında. Bu rota, indirdiğin "
            f"hava durumu verisinin coğrafi alanını kapsamıyor."
        )

    if "valid_time" in veri_kupu.dims:
        zaman_min = pd.Timestamp(veri_kupu["valid_time"].min().values)
        zaman_maks = pd.Timestamp(veri_kupu["valid_time"].max().values)
        tolerans_zaman = pd.Timedelta(hours=3)
        if not (zaman_min - tolerans_zaman <= zaman_uyumlu <= zaman_maks + tolerans_zaman):
            raise ValueError(
                f"Nokta zamanı ({zaman_uyumlu}) veri küpünün kapsadığı aralığın "
                f"({zaman_min} - {zaman_maks}) dışında."
            )


def rotayi_hava_durumuyla_eslestir(rota_df, veri_kupu):
    """
    rota_df: veri_yukleme.ucus_numarasi_ile_rota_cek(...) çıktısı
             (sütunlar: zaman, enlem, boylam, geo_irtifa_m, ...)
    veri_kupu: xarray.Dataset (u, v, w rüzgar bileşenleri; boyutlar
               config.py'de tanımlı ZAMAN_BOYUTU/BASINC_BOYUTU/ENLEM_BOYUTU/BOYLAM_BOYUTU)

    Dönüş: rota_df'e 'basinc_hpa', 'ti1_indeksi', 'edr_proxy' sütunları eklenmiş hali.
    """
    basinc_seviyeleri = veri_kupu[config.BASINC_BOYUTU].values
    basinc_seviyeleri_sirali = np.sort(basinc_seviyeleri)

    # (basinc_seviyesi, zaman) -> deformasyon_alani (2D DataArray) önbelleği.
    deformasyon_onbellegi = {}

    sonuclar = []
    toplam = len(rota_df)
    kapsam_disi_sayaci = 0
    for i, (_, satir) in enumerate(rota_df.iterrows()):
        if i % 200 == 0:
            print(f"   ... {i}/{toplam} nokta işlendi")
        try:
            edr_bilgisi = _tek_nokta_icin_edr_hesapla(
                veri_kupu, satir, basinc_seviyeleri_sirali, deformasyon_onbellegi
            )
        except Exception as hata:
            edr_bilgisi = {"basinc_hpa": np.nan, "ti1_indeksi": np.nan, "edr_proxy": np.nan}
            kapsam_disi_sayaci += 1
            if kapsam_disi_sayaci <= 5:
                print(f"[Uyarı] Nokta eşleştirilemedi ({satir.get('zaman')}): {hata}")
        sonuclar.append(edr_bilgisi)

    if kapsam_disi_sayaci > 5:
        print(f"[Uyarı] ... ve {kapsam_disi_sayaci - 5} nokta daha eşleştirilemedi (tekrarları gizledim).")
    if kapsam_disi_sayaci == toplam:
        print(
            "\n[ÖNEMLİ] Rotadaki HİÇBİR nokta hava durumu veri küpünün kapsama "
            "alanına girmiyor. Muhtemelen indirdiğin ERA5 verisi ile seçtiğin "
            "uçuşun coğrafi bölgesi/tarihi uyuşmuyor.\n"
        )

    eslesme_df = pd.DataFrame(sonuclar, index=rota_df.index)
    return pd.concat([rota_df, eslesme_df], axis=1)


def _tek_nokta_icin_edr_hesapla(veri_kupu, satir, basinc_seviyeleri_sirali, deformasyon_onbellegi):
    basinc_hpa = irtifa_metre_to_basinc_hpa(satir["geo_irtifa_m"])
    en_yakin_seviye = en_yakin_basinc_seviyesi(basinc_hpa, basinc_seviyeleri_sirali)

    seviye_indeksi = int(np.where(basinc_seviyeleri_sirali == en_yakin_seviye)[0][0])
    alt_seviye = basinc_seviyeleri_sirali[max(seviye_indeksi - 1, 0)]
    ust_seviye = basinc_seviyeleri_sirali[min(seviye_indeksi + 1, len(basinc_seviyeleri_sirali) - 1)]

    zaman_uyumlu = _zamani_veri_kupune_uydur(satir["zaman"])

    # Kapsama alanı kontrolü -- "Teksas rotası, Türkiye verisi" gibi
    # tamamen alakasız sessiz eşleşmeleri engeller.
    _kapsama_alanini_kontrol_et(veri_kupu, satir["enlem"], satir["boylam"], zaman_uyumlu)

    ortak_secim = dict(
        valid_time=zaman_uyumlu,
        latitude=satir["enlem"],
        longitude=satir["boylam"],
        method="nearest",
    )

    dilim_orta = veri_kupu.sel(pressure_level=en_yakin_seviye, **ortak_secim)
    dilim_alt = veri_kupu.sel(pressure_level=alt_seviye, **ortak_secim)
    dilim_ust = veri_kupu.sel(pressure_level=ust_seviye, **ortak_secim)

    onbellek_anahtari = (float(en_yakin_seviye), zaman_uyumlu)
    if onbellek_anahtari in deformasyon_onbellegi:
        deformasyon_alani = deformasyon_onbellegi[onbellek_anahtari]
    else:
        tam_dilim = veri_kupu.sel(pressure_level=en_yakin_seviye, valid_time=zaman_uyumlu, method="nearest")
        deformasyon_alani = yatay_deformasyon_hesapla(tam_dilim["u"], tam_dilim["v"])
        deformasyon_onbellegi[onbellek_anahtari] = deformasyon_alani

    deformasyon = float(
        deformasyon_alani.sel(latitude=satir["enlem"], longitude=satir["boylam"], method="nearest").values
    )

    yukseklik_farki_m = float(
        basinc_hpa_to_irtifa_metre(ust_seviye) - basinc_hpa_to_irtifa_metre(alt_seviye)
    )

    vws = dusey_ruzgar_kaymasi_hesapla(
        u_ust=float(dilim_ust["u"].values), v_ust=float(dilim_ust["v"].values),
        u_alt=float(dilim_alt["u"].values), v_alt=float(dilim_alt["v"].values),
        yukseklik_farki_m=yukseklik_farki_m,
    )

    ti1 = ti1_indeksi_hesapla(vws, deformasyon)
    edr_proxy = ti1_den_edr_proxy_olcegine_cevir(ti1)

    return {"basinc_hpa": en_yakin_seviye, "ti1_indeksi": ti1, "edr_proxy": edr_proxy}
