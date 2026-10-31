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
bir türbülans OLASILIK PROXY'sidir; çıktılar sertifikalı EDR değildir, sistem
operasyonel karar aracı değil, karar destek aracıdır.

Ayrıca, TI1'e EK ve ONDAN BAĞIMSIZ bir kararlılık göstergesi olarak **bulk
Richardson sayısı** (richardson_sayisi_hesapla) hesaplanır. Ri < 0.25
(Miles-Howard kriteri) dinamik kararsızlığın klasik bir işaretidir. Bilerek
TI1 ile tek bir sayıya karıştırılmaz -- iki farklı fiziksel mekanizmayı
(shear x deformation vs. düşey kararlılık) keyfi bir katsayıyla birleştirmek,
bu projenin başında eleştirilen "uydurma katsayı" hatasını tekrarlamak
olurdu. İkisi ayrı sütunlar olarak raporlanır, yorum kullanıcıya bırakılır.
"""

import numpy as np

DUNYA_YARICAPI_M = 6_371_000.0
METRE_PER_DERECE_ENLEM = DUNYA_YARICAPI_M * np.pi / 180.0

# Potansiyel sıcaklık formülü için kuru hava sabiti (R/cp, Poisson bağıntısı).
R_CP_KURU_HAVA = 0.286

# Kuru havanın gaz sabiti (J kg^-1 K^-1).
R_KURU_HAVA = 287.05

# Yerçekimi ivmesi (m/s^2).
YERCEKIMI_IVMESI = 9.80665

# Bulk Richardson sayısı bu eşiğin altına düştüğünde (Ri < 0.25) Kelvin-Helmholtz
# tipi dinamik kararsızlık (ve dolayısıyla CAT olasılığı) literatürde klasik bir
# gösterge olarak kabul edilir (bkz. Miles-Howard kararsızlık kriteri).
DINAMIK_KARARSIZLIK_ESIGI = 0.25

RI_ESIGI_NOTU = (
    "Ri < 0,25 (Miles-Howard) sınırı ~25-30 km çözünürlüklü ERA5/GFS'te nadiren aşılır; bu sayının 0 olması "
    "kararsızlık olmadığı anlamına gelmez. Veriden seçilen ayırma eşiği Ri < 2,27'dir (SONUCLAR §0.2); "
    "Richardson değerinin kendisine bakın."
)


def _metre_per_derece_boylam(enlem_derece):
    return METRE_PER_DERECE_ENLEM * np.cos(np.deg2rad(enlem_derece))


def _kuresel_turevler(u, v, enlem_boyutu, boylam_boyutu):
    enlem = u[enlem_boyutu]
    dx = _metre_per_derece_boylam(enlem)
    metrik = np.tan(np.deg2rad(enlem)) / DUNYA_YARICAPI_M
    return (
        u.differentiate(boylam_boyutu) / dx,
        u.differentiate(enlem_boyutu) / METRE_PER_DERECE_ENLEM,
        v.differentiate(boylam_boyutu) / dx,
        v.differentiate(enlem_boyutu) / METRE_PER_DERECE_ENLEM,
        metrik,
    )


def yatay_deformasyon_hesapla(u, v, enlem_boyutu="latitude", boylam_boyutu="longitude"):
    """
    Tek bir basınç seviyesindeki u, v rüzgar bileşenlerinden (xarray.DataArray,
    2 boyutlu: enlem x boylam) küresel metrik terimleriyle yatay deformasyonu hesaplar.

    DEF = sqrt(gerilme^2 + kayma^2)
      gerilme (stretching) = du/dx - dv/dy - v·tanφ/a
      kayma   (shearing)   = dv/dx + du/dy + u·tanφ/a
    Katı cisim dönmesinde DEF = 0 olur.
    """
    dudx, dudy, dvdx, dvdy, metrik = _kuresel_turevler(u, v, enlem_boyutu, boylam_boyutu)
    gerilme = dudx - dvdy - v * metrik
    kayma = dvdx + dudy + u * metrik
    return np.sqrt(gerilme**2 + kayma**2)


def yatay_diverjans_hesapla(u, v, enlem_boyutu="latitude", boylam_boyutu="longitude"):
    """DIV = du/dx + dv/dy - v·tanφ/a (küresel)."""
    dudx, _, _, dvdy, metrik = _kuresel_turevler(u, v, enlem_boyutu, boylam_boyutu)
    return dudx + dvdy - v * metrik


DUNYA_ACISAL_HIZI = 7.292e-5


def yatay_vortisite_hesapla(u, v, enlem_boyutu="latitude", boylam_boyutu="longitude"):
    """ζ = dv/dx - du/dy + u·tanφ/a (küresel)."""
    _, dudy, dvdx, _, metrik = _kuresel_turevler(u, v, enlem_boyutu, boylam_boyutu)
    return dvdx - dudy + u * metrik


def yatay_gradyan_buyuklugu_hesapla(alan, enlem_boyutu="latitude", boylam_boyutu="longitude"):
    """|∇alan| (ör. TEMPG = |∇T|, Sharman vd. 2006)."""
    dx = _metre_per_derece_boylam(alan[enlem_boyutu])
    return np.hypot(alan.differentiate(boylam_boyutu) / dx, alan.differentiate(enlem_boyutu) / METRE_PER_DERECE_ENLEM)


def frontogenez_hesapla(theta, u, v, enlem_boyutu="latitude", boylam_boyutu="longitude"):
    """2B kinematik frontogenez F = ½|∇θ|(DEF·cos2β − DIV) (Bluestein 1993; MetPy ile aynı biçim).
    β: genişleme ekseni ile izentroplar arasındaki açı. Pozitif F cephe güçlenmesidir."""
    dudx, dudy, dvdx, dvdy, metrik = _kuresel_turevler(u, v, enlem_boyutu, boylam_boyutu)
    gerilme = dudx - dvdy - v * metrik
    kayma = dvdx + dudy + u * metrik
    deformasyon = np.sqrt(gerilme**2 + kayma**2)
    diverjans = dudx + dvdy - v * metrik
    dx = _metre_per_derece_boylam(theta[enlem_boyutu])
    theta_x = theta.differentiate(boylam_boyutu) / dx
    theta_y = theta.differentiate(enlem_boyutu) / METRE_PER_DERECE_ENLEM
    buyukluk = np.hypot(theta_x, theta_y)
    psi = 0.5 * np.arctan2(kayma, gerilme)
    with np.errstate(divide="ignore", invalid="ignore"):
        beta = np.arcsin(np.clip((-theta_x * np.cos(psi) - theta_y * np.sin(psi)) / buyukluk, -1.0, 1.0))
    return 0.5 * buyukluk * (deformasyon * np.cos(2 * beta) - diverjans)


def potansiyel_vortisite_hesapla(vortisite, enlem_derece, theta_ust, theta_alt, basinc_ust_hpa, basinc_alt_hpa):
    """Hidrostatik izobarik yaklaşım PV = −g(ζ + f)∂θ/∂p, PVU (1e-6 K m² kg⁻¹ s⁻¹); yatay terimler ihmal."""
    f = 2 * DUNYA_ACISAL_HIZI * np.sin(np.deg2rad(np.asarray(enlem_derece, dtype=float)))
    dp_pa = (np.asarray(basinc_ust_hpa, dtype=float) - np.asarray(basinc_alt_hpa, dtype=float)) * 100.0
    with np.errstate(divide="ignore", invalid="ignore"):
        dtheta_dp = (np.asarray(theta_ust, dtype=float) - np.asarray(theta_alt, dtype=float)) / dp_pa
    return -YERCEKIMI_IVMESI * (np.asarray(vortisite, dtype=float) + f) * dtheta_dp * 1e6


def ti3_indeksi_hesapla(ti1, diverjans_simdi, diverjans_6sa_once, katsayi=0.01):
    """TI3 = TI1 + C·|DIV(t) − DIV(t−6 sa)| (Ellrod ve Knox 2010; C = 0,01, Kim ve Kim 2026)."""
    return np.asarray(ti1, dtype=float) + katsayi * np.abs(
        np.asarray(diverjans_simdi, dtype=float) - np.asarray(diverjans_6sa_once, dtype=float)
    )


def hipsometrik_kalinlik_m(basinc_ust_hpa, basinc_alt_hpa, sicaklik_ust_k, sicaklik_alt_k):
    """Δz = R_d·T̄/g·ln(p_alt/p_ust); T̄ iki seviyenin ortalama sıcaklığı."""
    ortalama_t = (np.asarray(sicaklik_ust_k, dtype=float) + np.asarray(sicaklik_alt_k, dtype=float)) / 2
    with np.errstate(divide="ignore", invalid="ignore"):
        return (
            R_KURU_HAVA
            * ortalama_t
            / YERCEKIMI_IVMESI
            * np.log(np.asarray(basinc_alt_hpa, dtype=float) / np.asarray(basinc_ust_hpa, dtype=float))
        )


def ti2_indeksi_hesapla(vws, deformasyon, diverjans):
    return np.abs(vws) * (np.asarray(deformasyon, dtype=float) - np.asarray(diverjans, dtype=float))


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
    sonuc = np.sqrt(du**2 + dv**2) / np.abs(yukseklik_farki_m)
    return float(sonuc) if sonuc.ndim == 0 else sonuc


def ti1_indeksi_hesapla(vws, deformasyon):
    """TI1 = VWS x DEF (Ellrod & Knapp, 1992)."""
    return np.abs(vws) * deformasyon


# DÜRÜSTLÜK NOTU (madde 6, bkz. konuşma geçmişi): TI1'in TEK BAŞINA gerçek
# türbülans olaylarını ayırt ettiği BAĞIMSIZ olarak kanıtlanmamıştır. Seyir
# irtifasındaki 15940 PIREP'te (163 gün, çevreleyen katman fiziği) TI1'in tek başına
# ayırt ediciliği orta düzeydedir (ROC-AUC 0.67; altın test günlerinde 0.67; sayılar
# docs/sonuclar/2026-10-18/SAYILAR.md'den).
# Bağımsız kanıt modülüyle (dogrulama/bagimsiz_kanit.py)
# yapılan canlı bir sınamada (PUE502, 26 Eylül 2026) aktif TURB SIGMET'lerin
# işaret ettiği bir bölgede TI1 HİÇ risk görmedi -- yani bugün rota
# güvenliğini fiilen SIGMET sert kısıtı sağlıyor, TI1 değil. Bu yüzden bu not
# API yanıtlarında (bkz. rota_optimizasyonu.rota_simulasyonu_olustur,
# api_servisi.turbulans_tahmini) ayrı bir alan olarak taşınır -- rota
# açıklamasına gömülmez ki her yanıtta baskın bir uyarı gibi görünmesin, ama
# istemci (EFB arayüzü) TI1'e "kanıtlanmış" güvenmesin diye elinin altında olsun.
TI1_GUVENILIRLIK_NOTU = (
    "TI1 fiziksel göstergesi, gerçek türbülans olaylarını TEK BAŞINA güvenilir şekilde ayırt ettiği bağımsız "
    "olarak KANITLANMAMIŞTIR (seyir irtifasındaki 15940 PIREP'te [163 gün] ROC-AUC 0.67, altın test "
    "günlerinde 0.67 [%95 GA 0.64-0.71]; risk eşiğinde altın günlerde yakalama 0.50, yanlış alarm 0.25; "
    "gerçek bir uçuşta [PUE502] aktif SIGMET'in işaret ettiği türbülansı TI1 hiç "
    "yakalamadı). Bugün güvenlik garantisi TI1'den değil SIGMET sert kısıtından "
    "gelir; TI1 yalnızca ek/yumuşak bir gösterge olarak değerlendirilmelidir. Kapsam yalnızca açık hava "
    "türbülansıdır (CAT); konvektif, bulut içi, dağ dalgası ve iz türbülansı kapsam dışıdır."
)


def ti1_den_edr_proxy_olcegine_cevir(ti1_degeri, olceklendirme_katsayisi=0.27):
    """
    TI1'in tipik değer aralığı (~1e-7 - 1e-6 s^-2) EDR'nin alışılan 0-1
    aralığıyla doğrudan karşılaştırılabilir değil. Burada TI1'i, eski
    kodunla aynı yerlerde kullanılabilecek 0'a yakın-1'e yakın bir "proxy"
    ölçeğine sıkıştırıyoruz (tanh ile doygunlaştırma). Varsayılan katsayı
    (0.27), config.EDR_OLCEKLENDIRME_KATSAYISI ile AYNIDIR -- EDR ölçümüne
    değil, seyir irtifasındaki IEM PIREP sınıf koduna uyduruldu (bkz.
    ml/edr_kalibrasyonu.py); sabit ortalama tahmininden daha iyi tahmin etmez
    (SISTEM_KARTI §5). Görselleştirme ölçeğidir, sertifikalı EDR değildir.
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
    return (
        np.asarray(sicaklik_kelvin, dtype=float)
        * (referans_basinc_hpa / np.asarray(basinc_hpa, dtype=float)) ** R_CP_KURU_HAVA
    )


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
        sonuc = (YERCEKIMI_IVMESI * d_theta * yukseklik_farki_m) / (theta_ortalama * (du**2 + dv**2))

    return float(sonuc) if sonuc.ndim == 0 else sonuc
