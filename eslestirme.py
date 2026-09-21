"""
eslestirme.py
--------------
Gerçek uçuş rotasındaki (OpenSky) her noktayı, Copernicus veri küpündeki
en yakın (zaman, enlem, boylam, basınç seviyesi) hücresiyle eşleştirir ve
o hücre için Ellrod TI1 tabanlı türbülans proxy'sini hesaplar.

Eski koddaki `kucuk_simulasyon.py` / `interaktif_harita.py` SİMÜLE EDİLMİŞ
bir rota (np.linspace ile üretilmiş düz bir çizgi) kullanıyordu. Bu modül
gerçek uçuş verisiyle çalışacak şekilde tasarlandı.
"""

import numpy as np
import pandas as pd

import config
from birim_donusumleri import irtifa_metre_to_basinc_hpa, en_yakin_basinc_seviyesi
from turbulans_indeksleri import (
    yatay_deformasyon_hesapla,
    dusey_ruzgar_kaymasi_hesapla,
    ti1_indeksi_hesapla,
    ti1_den_edr_proxy_olcegine_cevir,
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

    sonuclar = []
    for _, satir in rota_df.iterrows():
        try:
            edr_bilgisi = _tek_nokta_icin_edr_hesapla(
                veri_kupu, satir, basinc_seviyeleri_sirali
            )
        except Exception as hata:
            # Bir noktada veri eksikse/aralık dışıysa tüm rotayı çökertme,
            # o noktayı NaN bırakıp devam et.
            edr_bilgisi = {"basinc_hpa": np.nan, "ti1_indeksi": np.nan, "edr_proxy": np.nan}
            print(f"[Uyarı] Nokta eşleştirilemedi ({satir.get('zaman')}): {hata}")
        sonuclar.append(edr_bilgisi)

    eslesme_df = pd.DataFrame(sonuclar, index=rota_df.index)
    return pd.concat([rota_df, eslesme_df], axis=1)


def _tek_nokta_icin_edr_hesapla(veri_kupu, satir, basinc_seviyeleri_sirali):
    basinc_hpa = irtifa_metre_to_basinc_hpa(satir["geo_irtifa_m"])
    en_yakin_seviye = en_yakin_basinc_seviyesi(basinc_hpa, basinc_seviyeleri_sirali)

    # Düşey kayma için bir üst ve bir alt seviyeyi bul (varsa)
    seviye_indeksi = int(np.where(basinc_seviyeleri_sirali == en_yakin_seviye)[0][0])
    alt_seviye = basinc_seviyeleri_sirali[max(seviye_indeksi - 1, 0)]
    ust_seviye = basinc_seviyeleri_sirali[min(seviye_indeksi + 1, len(basinc_seviyeleri_sirali) - 1)]

    ortak_secim = dict(
        valid_time=satir["zaman"],
        latitude=satir["enlem"],
        longitude=satir["boylam"],
        method="nearest",
    )

    dilim_orta = veri_kupu.sel(pressure_level=en_yakin_seviye, **ortak_secim)
    dilim_alt = veri_kupu.sel(pressure_level=alt_seviye, **ortak_secim)
    dilim_ust = veri_kupu.sel(pressure_level=ust_seviye, **ortak_secim)

    # Yatay deformasyon: komşu grid hücreleriyle türev alabilmek için
    # tek noktadan biraz daha geniş bir pencere (nokta çevresindeki grid)
    # üzerinden hesaplanması gerekir; burada basitleştirilmiş nokta-bazlı
    # yaklaşım için tüm zaman diliminin 2D kesitini kullanıyoruz.
    tam_dilim = veri_kupu.sel(pressure_level=en_yakin_seviye, valid_time=satir["zaman"], method="nearest")
    deformasyon_alani = yatay_deformasyon_hesapla(tam_dilim["u"], tam_dilim["v"])
    deformasyon = float(
        deformasyon_alani.sel(latitude=satir["enlem"], longitude=satir["boylam"], method="nearest").values
    )

    from birim_donusumleri import basinc_hpa_to_irtifa_metre
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
