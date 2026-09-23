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

Ayrıca, TI1'e EK ve ONDAN BAĞIMSIZ bir kararlılık göstergesi olarak **bulk
Richardson sayısı** (richardson_sayisi_hesapla) hesaplanır. Ri < 0.25
(Miles-Howard kriteri) dinamik kararsızlığın klasik bir işaretidir. Bilerek
TI1 ile tek bir sayıya karıştırılmaz -- iki farklı fiziksel mekanizmayı
(shear x deformation vs. düşey kararlılık) keyfi bir katsayıyla birleştirmek,
bu projenin başında eleştirilen "uydurma katsayı" hatasını tekrarlamak
olurdu. İkisi ayrı sütunlar olarak raporlanır, yorum kullanıcıya bırakılır.
"""

import numpy as np

# Enlem/boylam derecesini yaklaşık metreye çeviren sabitler
METRE_PER_DERECE_ENLEM = 110_540.0

# Potansiyel sıcaklık formülü için kuru hava sabiti (R/cp, Poisson bağıntısı).
R_CP_KURU_HAVA = 0.286

# Yerçekimi ivmesi (m/s^2).
YERCEKIMI_IVMESI = 9.80665

# Bulk Richardson sayısı bu eşiğin altına düştüğünde (Ri < 0.25) Kelvin-Helmholtz
# tipi dinamik kararsızlık (ve dolayısıyla CAT olasılığı) literatürde klasik bir
# gösterge olarak kabul edilir (bkz. Miles-Howard kararsızlık kriteri).
DINAMIK_KARARSIZLIK_ESIGI = 0.25


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
    yukseklik_farki_m = np.asarray(yukseklik_farki_m, dtype=float)
    if np.any(yukseklik_farki_m == 0):
        raise ValueError("İki basınç seviyesi aynı irtifaya denk geliyor, kayma hesaplanamaz.")

    du = np.asarray(u_ust, dtype=float) - np.asarray(u_alt, dtype=float)
    dv = np.asarray(v_ust, dtype=float) - np.asarray(v_alt, dtype=float)
    sonuc = np.sqrt(du ** 2 + dv ** 2) / np.abs(yukseklik_farki_m)
    return float(sonuc) if sonuc.ndim == 0 else sonuc


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
    sonuc = np.tanh(np.asarray(ti1_degeri, dtype=float) * olceklendirme_katsayisi * 1e6)
    return float(sonuc) if sonuc.ndim == 0 else sonuc


def potansiyel_sicaklik_hesapla(sicaklik_kelvin, basinc_hpa, referans_basinc_hpa=1000.0):
    """
    Poisson bağıntısıyla potansiyel sıcaklığı (theta) hesaplar: bir hava
    parselini kuru-adyabatik olarak referans basınca (1000 hPa) getirseydik
    alacağı sıcaklık. Farklı basınç seviyelerindeki sıcaklıkları doğrudan
    kıyaslayabilmek (ve Richardson sayısını hesaplayabilmek) için gereklidir.
    """
    return np.asarray(sicaklik_kelvin, dtype=float) * (
        referans_basinc_hpa / np.asarray(basinc_hpa, dtype=float)
    ) ** R_CP_KURU_HAVA


def richardson_sayisi_hesapla(theta_ust, theta_alt, u_ust, v_ust, u_alt, v_alt, yukseklik_farki_m):
    """
    Bulk (toplu) Richardson sayısını hesaplar:

        Ri = (g * Δtheta * Δz) / (theta_ortalama * (Δu^2 + Δv^2))

    Düşey kararlılığı (Δtheta, payda) düşey rüzgar kaymasına (Δu, Δv) oranlar.
    Ri < 0.25 (DINAMIK_KARARSIZLIK_ESIGI), Miles-Howard kriterine göre
    Kelvin-Helmholtz tipi dinamik kararsızlığın (dolayısıyla CAT olasılığının)
    klasik göstergesidir. TI1'den BAĞIMSIZ, tamamlayıcı bir tanı büyüklüğüdür;
    keyfi bir katsayıyla TI1 ile birleştirilmez -- ayrı bir sütun olarak
    raporlanır.

    NOT: Rüzgar kayması sıfıra çok yakınsa (Δu, Δv ~ 0) sonuç aşırı büyük/
    sonsuz çıkabilir; bu düşey kayma neredeyse yokken beklenen (kararlı)
    bir durumdur, hata değildir.
    """
    theta_ust = np.asarray(theta_ust, dtype=float)
    theta_alt = np.asarray(theta_alt, dtype=float)
    yukseklik_farki_m = np.asarray(yukseklik_farki_m, dtype=float)

    theta_ortalama = (theta_ust + theta_alt) / 2
    d_theta = theta_ust - theta_alt
    du = np.asarray(u_ust, dtype=float) - np.asarray(u_alt, dtype=float)
    dv = np.asarray(v_ust, dtype=float) - np.asarray(v_alt, dtype=float)

    with np.errstate(divide="ignore", invalid="ignore"):
        sonuc = (YERCEKIMI_IVMESI * d_theta * yukseklik_farki_m) / (theta_ortalama * (du ** 2 + dv ** 2))

    return float(sonuc) if sonuc.ndim == 0 else sonuc
