"""
turbulans_indeksleri.py
------------------------
Eski koddaki EDR hesabı ( edr = cbrt(|w|) * 0.15  veya  cbrt(|w * rüzgar|) * 0.1 )
keyfi seçilmiş katsayılara dayanıyordu ve iki dosyada birbirinden farklı sonuç
veriyordu. Bu modül, havacılık meteorolojisinde CAT (Clear Air Turbulence)
tahmini için gerçekten kullanılan **Ellrod TI1 indeksini** (Ellrod & Knapp, 1992)
hesaplar. GTG (Graphical Turbulence Guidance) gibi operasyonel sistemler de
benzer shear x deformation yaklaşımını temel alır.

    TI1 = |Düşey Rüzgar Kayması (VWS)| x |Yatay Deformasyon (DEF)|

ÖNEMLİ SINIRLAMA:
Bu, uçağın kendi ivme ölçerlerinden türetilen SERTİFİKALI/GERÇEK EDR
DEĞİLDİR. ERA5 gibi ~25-30 km çözünürlüklü reanaliz verisinden hesaplanan
bir türbülans OLASILIK PROXY'sidir; gerçek uçuş operasyonu kararları için
kullanılmamalıdır — sadece araştırma/görselleştirme amaçlıdır.
"""

import numpy as np

# Enlem/boylam derecesini yaklaşık metreye çeviren sabitler
METRE_PER_DERECE_ENLEM = 110_540.0


def _metre_per_derece_boylam(enlem_derece):
    return 111_320.0 * np.cos(np.deg2rad(enlem_derece))


def yatay_deformasyon_hesapla(u, v, enlem_boyutu="latitude", boylam_boyutu="longitude"):
    """
    Tek bir basınç seviyesindeki u, v rüzgar bileşenlerinden (xarray.DataArray,
    2 boyutlu: enlem x boylam) yatay deformasyonu hesaplar.

    DEF = sqrt(gerilme_terimi^2 + kayma_terimi^2)
      gerilme_terimi (stretching) = du/dx - dv/dy
      kayma_terimi   (shearing)   = dv/dx + du/dy
    """
    dx = _metre_per_derece_boylam(u[enlem_boyutu])
    dy = METRE_PER_DERECE_ENLEM

    dudx = u.differentiate(boylam_boyutu) / dx
    dudy = u.differentiate(enlem_boyutu) / dy
    dvdx = v.differentiate(boylam_boyutu) / dx
    dvdy = v.differentiate(enlem_boyutu) / dy

    gerilme = dudx - dvdy
    kayma = dvdx + dudy
    return np.sqrt(gerilme ** 2 + kayma ** 2)


def dusey_ruzgar_kaymasi_hesapla(u_ust, v_ust, u_alt, v_alt, yukseklik_farki_m):
    """
    İki komşu basınç seviyesi arasındaki rüzgar farkından düşey kaymayı (VWS)
    hesaplar. yukseklik_farki_m, iki seviye arasındaki yaklaşık düşey mesafedir
    (bkz. birim_donusumleri.basinc_hpa_to_irtifa_metre ile hesaplanabilir).
    """
    if yukseklik_farki_m == 0:
        raise ValueError("İki basınç seviyesi aynı irtifaya denk geliyor, kayma hesaplanamaz.")

    du = u_ust - u_alt
    dv = v_ust - v_alt
    return np.sqrt(du ** 2 + dv ** 2) / abs(yukseklik_farki_m)


def ti1_indeksi_hesapla(vws, deformasyon):
    """TI1 = VWS x DEF (Ellrod & Knapp, 1992)."""
    return np.abs(vws) * deformasyon


def ti1_den_edr_proxy_olcegine_cevir(ti1_degeri, olceklendirme_katsayisi=1.5):
    """
    TI1'in tipik değer aralığı (~1e-7 - 1e-6 s^-2) EDR'nin alışılan 0-1
    aralığıyla doğrudan karşılaştırılabilir değil. Burada TI1'i, eski
    kodunla aynı yerlerde kullanılabilecek 0'a yakın-1'e yakın bir "proxy"
    ölçeğine sıkıştırıyoruz (tanh ile doygunlaştırma). Bu, keyfi bir
    kalibrasyondur — gerçek EDR karşılığı için gözlemsel veriyle (PIREP,
    AMDAR) kalibre edilmesi gerekir.
    """
    return float(np.tanh(ti1_degeri * olceklendirme_katsayisi * 1e6))
