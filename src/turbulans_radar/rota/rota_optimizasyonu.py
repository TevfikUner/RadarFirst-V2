"""
rota_optimizasyonu.py
------------------------
3D uçuş simülasyonu (web/ucus_simulasyonu.html) için iki rota üretir:
  1. "Normal rota"    -> iki nokta arasındaki büyük daire (great circle) rotası.
  2. "Optimize rota"  -> ÖNCELİK SIRASI: ÖNCE TÜRBÜLANSTAN KAÇIN, SONRA EN
     UCUZ (yakıt/süre) YOLU BUL.

NEDEN BU SIRAYLA (proje sahibiyle netleştirildi -- ilk sürüm SADECE rüzgara
göre en hızlı/ucuz rotayı arıyordu, bu da türbülans hiç yokken bile rotaların
gereksiz yere görsel olarak ayrışmasına yol açıyordu):
  - Türbülansın kendisi uçuş sırasında DOĞRUDAN çok fazla ekstra yakıt
    yaktırmaz; asıl yakıt belirleyicisi rüzgardır (kuyruk/burun rüzgarı).
  - Türbülansın yakıtla bağlantısı DOLAYLIDIR: ondan kaçmak için rotadan
    sapmak yol/süre uzatır (yakıt kaybı); asıl değeri YOLCU GÜVENLİĞİ/
    KONFORUdur (bu da projenin geri kalanının -- Ellrod TI1, Richardson
    sayısı -- asıl konusu).
  - Bu yüzden: rota üzerinde riskli türbülans (TI1 >= config.TI1_ESIK_ORTA_
    SIDDETLI) YOKSA, optimize rota normal rotayla BİREBİR AYNIDIR (uydurma
    bir sapma gösterilmez). Riskli türbülans VARSA, o bölgeyi TAMAMEN
    atlatan adaylar arasından en az yakıt harcayanı seçilir (rüzgar da bu
    adaylar arasında zaten hesaba katılmış olur -- bazen kaçış aynı zamanda
    daha iyi rüzgar da yakalar). Hiçbir aday riski tamamen ortadan
    kaldıramazsa (deneme aralığı türbülans alanından dar kalmışsa), riski en
    aza indiren aday dürüstçe seçilir -- "tamamen güvenli" diye yalan
    söylenmez.

YÖNTEM (GERÇEK ERA5 rüzgar VE gerçek Ellrod TI1 türbülans hesabına dayanan
bir A* (A-star) graf araması -- literatürdeki "lateral rota kayması"
fikrine yakın, tam bir 4D optimal-kontrol/dinamik programlama çözücüsü
DEĞİL, ama "birkaç sabit aday dene" gibi açgözlü/kaba bir arama da DEĞİL):
  - Büyük daire rotası etrafında, her ara noktada +/- 500 km'ye kadar 11
    yanal seviyeden oluşan bir IZGARA (graf) kurulur (bkz.
    _yanal_izgara_dugum_konumlari).
  - Her ızgara düğümünün TI1 türbülans indeksi, projenin ANA analiz koduyla
    (bkz. eslestirme.rotayi_hava_durumuyla_eslestir -- turbulans_
    indeksleri.py'deki Ellrod TI1 hesabı) TEK bir vektörel çağrıyla
    hesaplanır; her kenarın (iki düğüm arası bacak) maliyeti gerçek ERA5
    rüzgarına göre uçuş süresi + (riskli türbülans içeriyorsa) büyük bir
    ceza olarak tanımlanır.
  - A*, kalan büyük daire mesafesi/(TAS x 1.8) admissible (asla aşırı tahmin
    etmeyen) sezgiseliyle, başlangıçtan bitişe TOPLAM MALİYETİ EN AZA
    indiren yolu GARANTİLİ OPTİMAL şekilde bulur (bkz. _a_yildiz_ile_rota_ara)
    -- bu, yukarıdaki öncelik sırasını (güvenlik > maliyet) TEK bir arama
    içinde birleştirir.

DÜRÜSTLÜK SINIRLAMASI (projenin geri kalanıyla aynı ilkeyle):
Gerçek ERA5 verisi bu depoda SADECE `config.HAVA_DURUMU_DOSYASI` küpünün
(varsayılan: Türkiye/Doğu Akdeniz, Ocak 2019) ve `config.EK_HAVA_DURUMU_
KLASORU`'ndaki küplerin (varsayılan: Kuzeydoğu ABD, 2018-2020 seçili günler)
kapsadığı bölge/tarih/irtifa için var; rotayı en iyi kapsayan küp otomatik
seçilir. Kullanıcının seçtiği başlangıç/bitiş/tarih/irtifa bu kapsamın dışındaysa,
kod SESSİZCE uydurma bir rüzgar/türbülans üretmez -- `ruzgar_verisi_kaynagi`
alanı "era5_kapsam_disi" döner, iki rota da (rüzgarsız, sadece TAS ile)
büyük daire olarak hesaplanır ve `aciklama` alanında bu açıkça belirtilir.
Bu, sigmet_dogrulama.py'deki "ABD dışı kapsam yok" dürüstlük deseninin
aynısıdır.

Uçak "modelleri": gerçek performans farkını göstermek için birkaç bilinen
uçak tipinin YAKLAŞIK (halka açık, tipik) seyir hızı/yakıt akış hızı değerleri
kullanılır -- üreticinin resmi performans verisi DEĞİLDİR, sadece büyüklük
mertebesi doğru kaba bir tahmindir. 3D görselleştirmede hepsi AYNI jenerik
uçak modelini (web/models/ucak.glb, resmi CesiumJS örnek verisi) kullanır.
"""

from __future__ import annotations

import heapq
import math

import numpy as np
import pandas as pd
import xarray as xr

from turbulans_radar import config
from turbulans_radar.fizik.birim_donusumleri import (
    basinc_hpa_to_irtifa_metre,
    en_yakin_basinc_seviyesi,
    irtifa_metre_to_basinc_hpa,
)
from turbulans_radar.fizik.eslestirme import kapsam_disi_maskesi
from turbulans_radar.loglama import logger_al
from turbulans_radar.rota.risk_katmanlari import (
    SigmetKisitKatmani,
    Ti1CezaKatmani,
    degerlendirmeleri_birlestir,
    rota_ti1_degerleri,
)
from turbulans_radar.veri.sigmet_saglayici import gecerli_sigmetleri_getir, son_guncelleme_zamani
from turbulans_radar.veri.veri_saglayicilari import veri_kupu_kaynagi, veri_kupunu_sec
from turbulans_radar.veri.veri_yukleme import hava_durumu_onbellekli_yukle, veri_kupu_adi

DUNYA_YARICAPI_M = 6_371_000.0

# Yaklaşık, halka açık tipik seyir performansı değerleri (bkz. modül dosya
# başlığı) -- resmi üretici verisi değildir, sadece büyüklük mertebesi
# doğru, karşılaştırma amaçlı kaba tahminlerdir.
UCAK_PROFILLERI = {
    "A320": {"etiket": "Airbus A320 (dar gövde, kısa/orta menzil)", "tas_ms": 230.0, "yakit_akisi_kg_saat": 2400.0},
    "B738": {"etiket": "Boeing 737-800 (dar gövde, kısa/orta menzil)", "tas_ms": 227.0, "yakit_akisi_kg_saat": 2500.0},
    "B77W": {"etiket": "Boeing 777-300ER (geniş gövde, uzun menzil)", "tas_ms": 250.0, "yakit_akisi_kg_saat": 6800.0},
    "A359": {"etiket": "Airbus A350-900 (geniş gövde, uzun menzil)", "tas_ms": 252.0, "yakit_akisi_kg_saat": 5800.0},
}

# A* aramasının her bir ara noktada deneyebileceği yanal kaydırma SEVİYELERİ
# (km) -- büyük daire etrafında bir "ızgara" oluşturur. 0.0 dahildir -- hiçbir
# kaydırma gerekmiyorsa A* zaten en ucuz yol olarak düz çizgiyi (0 seviyesini)
# bulur (uydurma bir "iyileşme" gösterilmez). 20 km ADIMLARLA (100 km değil)
# İNCE TUTULUR -- kaba bir ızgarada (100 km/adım) A*'ın, bir defada büyük bir
# seviye sıçraması yapıp onu KORUMASININ (uçağın fiziksel olarak
# yapamayacağı ani bir dönüş, üstelik gerçek veriyle ölçüldüğünde eski
# sinüs-şekilli tek-adaylık yaklaşımdan bile daha UZUN bir rota) ucuza
# geldiği görüldü -- ince ızgara, kademeli/gerçekçi bir sapmayı ucuzlatır.
_YANAL_SEVIYE_KM = tuple(float(k) for k in range(-400, 401, 20))
_ORTA_SEVIYE_INDEKSI = _YANAL_SEVIYE_KM.index(0.0)

# Jet yakıtının (Jet A-1) yanma başına CO2 emisyon katsayısı -- ICAO/IPCC'nin
# standart, halka açık "emission factor" değeridir (kaynak: ICAO Carbon
# Emissions Calculator Methodology / IPCC Guidelines for National Greenhouse
# Gas Inventories, karbon içeriğinden hesaplanan yakma katsayısı). Yakıt
# TÜRÜNE göre neredeyse sabittir (kerosen bazlı jet yakıtları için ~3.15-3.16
# kg CO2 / kg yakıt) -- uçak modeline göre DEĞİŞMEZ, uydurma bir katsayı DEĞİLDİR.
CO2_KG_PER_KG_YAKIT = 3.16

# İrtifa değişimi (tırmanma/alçalma) maliyet modeli -- türbülanstan kaçınmanın
# YANAL sapma dışında ikinci bir GERÇEK stratejisi: bazı CAT katmanları
# irtifaya bağlıdır, bir üst/alt basınç seviyesine geçmek türbülansı
# tamamen atlatabilir. Tırmanma/alçalma KENDİ İÇİNDE de bir yakıt/süre
# maliyeti taşır -- bu yüzden "çok faktörlü" bir karşılaştırma: yanal A*
# yolu ile irtifa değişimi arasından TOPLAM maliyeti (temel seyir yakıtı +
# tırmanma/alçalma bedeli) en düşük, güvenliği sağlayan seçenek seçilir.
# Katsayılar YAKLAŞIKTIR (halka açık, tipik jet performansı mertebeleri) --
# resmi uçak performans verisi DEĞİLDİR:
#   - Tırmanma sırasında motor gücü seyirden yüksektir -> yakıt akışı seyrin
#     ÜZERİNDE (+%50 tipik mertebe).
#   - Alçalma genelde ridle-yakın güçle yapılır -> yakıt akışı seyrin
#     ALTINDA (-%30 tipik mertebe) -- yani alçalarak kaçınma bazen hem
#     güvenli HEM ucuz olabilir.
#   - Dikey hız ~1500 ft/dk -- yüksek irtifada tipik tırmanma/alçalma hızı.
TIRMANMA_EK_YAKIT_ORANI = 0.5
ALCALMA_YAKIT_TASARRUFU_ORANI = 0.3
DIKEY_HIZ_FT_DK = 1500.0

# Veritabanından SIGMET çekerken rota kutusuna eklenen pay (derece): A*'ın
# yanal ızgarası büyük daireden 400 km'ye kadar sapabilir.
_SIGMET_ARAMA_PAYI_DERECE = 5.0

_logger = logger_al(__name__)


def veri_kupune_eris(enlemler=None, boylamlar=None, zaman=None, irtifa_m=None, zamanlar=None):
    """Argümansız: ana küp (yoksa None). Noktalar verilirse: onları en iyi
    kapsayan yerel küp, yoksa (zaman canlı penceredeyse) canlı GFS küpü (bkz.
    veri_saglayicilari.veri_kupunu_sec), hiçbiri yoksa None. zamanlar
    verilmezse tüm noktalar için `zaman` kullanılır."""
    if enlemler is None:
        try:
            return hava_durumu_onbellekli_yukle()
        except FileNotFoundError:
            return None
    enlemler = np.atleast_1d(np.asarray(enlemler, dtype=float))
    basinc_hpa = None if irtifa_m is None else np.full(len(enlemler), irtifa_metre_to_basinc_hpa(irtifa_m))
    return veri_kupunu_sec(enlemler, boylamlar, zamanlar or [zaman] * len(enlemler), basinc_hpa)


def _tahmini_varis_zamanlari(enlemler, boylamlar, zaman_iso, tas_ms):
    """Rota noktalarına yaklaşık (rüzgarsız, TAS'ın %80'i) varış zamanları --
    uzun bir rotada küp seçiminin/canlı indirmenin tüm uçuş süresini kapsaması için."""
    zaman = pd.Timestamp(zaman_iso)
    zaman = zaman.tz_localize("UTC") if zaman.tzinfo is None else zaman
    zamanlar = [zaman]
    for i in range(len(enlemler) - 1):
        mesafe_m = buyuk_daire_mesafesi_km(enlemler[i], boylamlar[i], enlemler[i + 1], boylamlar[i + 1]) * 1000.0
        zamanlar.append(zamanlar[-1] + pd.Timedelta(seconds=mesafe_m / (tas_ms * 0.8)))
    return zamanlar


# ---------------------------------------------------------------------------
# Küresel geometri (büyük daire) yardımcıları
# ---------------------------------------------------------------------------


def _bd(deger):
    return math.radians(deger)


def buyuk_daire_mesafesi_km(enlem1, boylam1, enlem2, boylam2):
    """Haversine formülüyle iki nokta arasındaki büyük daire mesafesi (km)."""
    phi1, phi2 = _bd(enlem1), _bd(enlem2)
    d_phi = _bd(enlem2 - enlem1)
    d_lambda = _bd(boylam2 - boylam1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * DUNYA_YARICAPI_M * math.asin(math.sqrt(a)) / 1000.0


def _ilk_yon_derece(enlem1, boylam1, enlem2, boylam2):
    """Nokta 1'den nokta 2'ye ilk pusula yönü (derece, 0=kuzey, 90=doğu)."""
    phi1, phi2 = _bd(enlem1), _bd(enlem2)
    d_lambda = _bd(boylam2 - boylam1)
    y = math.sin(d_lambda) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(d_lambda)
    return math.degrees(math.atan2(y, x)) % 360.0


def _hedef_nokta(enlem, boylam, yon_derece, mesafe_km):
    """Bir noktadan, verilen pusula yönünde ve mesafede (km) hedef noktayı
    küresel trigonometriyle hesaplar (great-circle destination formülü)."""
    delta = (mesafe_km * 1000.0) / DUNYA_YARICAPI_M
    theta = _bd(yon_derece)
    phi1, lambda1 = _bd(enlem), _bd(boylam)

    phi2 = math.asin(math.sin(phi1) * math.cos(delta) + math.cos(phi1) * math.sin(delta) * math.cos(theta))
    lambda2 = lambda1 + math.atan2(
        math.sin(theta) * math.sin(delta) * math.cos(phi1),
        math.cos(delta) - math.sin(phi1) * math.sin(phi2),
    )
    return math.degrees(phi2), (math.degrees(lambda2) + 540.0) % 360.0 - 180.0


def buyuk_daire_rotasi_olustur(baslangic_enlem, baslangic_boylam, bitis_enlem, bitis_boylam, nokta_sayisi):
    """Slerp (küresel doğrusal ara değerleme) ile iki nokta arasında eşit
    açısal aralıklı `nokta_sayisi` adet ara nokta üretir. Dönüş: (enlemler,
    boylamlar) -- numpy dizileri, ikisi de uzunluk `nokta_sayisi`."""
    phi1, lambda1 = _bd(baslangic_enlem), _bd(baslangic_boylam)
    phi2, lambda2 = _bd(bitis_enlem), _bd(bitis_boylam)

    d = 2 * math.asin(
        math.sqrt(
            math.sin((phi2 - phi1) / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin((lambda2 - lambda1) / 2) ** 2
        )
    )
    if d < 1e-9:
        raise ValueError("Başlangıç ve bitiş noktası birbirine çok yakın/aynı -- rota oluşturulamaz.")

    enlemler, boylamlar = [], []
    for f in np.linspace(0.0, 1.0, nokta_sayisi):
        a = math.sin((1 - f) * d) / math.sin(d)
        b = math.sin(f * d) / math.sin(d)
        x = a * math.cos(phi1) * math.cos(lambda1) + b * math.cos(phi2) * math.cos(lambda2)
        y = a * math.cos(phi1) * math.sin(lambda1) + b * math.cos(phi2) * math.sin(lambda2)
        z = a * math.sin(phi1) + b * math.sin(phi2)
        enlemler.append(math.degrees(math.atan2(z, math.sqrt(x * x + y * y))))
        boylamlar.append(math.degrees(math.atan2(y, x)))
    return np.array(enlemler), np.array(boylamlar)


# Bir ara noktada ulaşılabilir azami yanal sapma, o noktanın başlangıca/bitişe
# olan UZAKLIĞIYLA (adım sayısı) orantılı bir "zarf" (envelope) ile sınırlanır
# -- yoksa A*, uçağın fiziksel olarak yapamayacağı ani/sert bir dönüşle rotanın
# HEMEN başında/sonunda tam kaydırmaya sıçrayıp sonra onu KORUYABİLİYOR (gerçek
# veriyle doğrulandı: bu, eski sinüs-şekilli tek-adaylık yaklaşımdan daha KÖTÜ,
# daha uzun bir rota buluyordu). Bu zarf, ucuz uçlarda düşük, ortada yüksek --
# tıpkı önceki sinüs şeklinin sağladığı kademeli giriş/çıkışı garanti eder, ama
# A*'ın zirvenin NEREDE ve NE KADAR geniş olacağını -- gerçek türbülansın
# konumuna göre -- serbestçe seçmesine izin verir.
_ZARF_KM_PER_ADIM = 20.0


def _yanal_izgara_dugum_konumlari(enlemler_gc, boylamlar_gc):
    """Büyük daire rotasının her ara noktasında (uçlar hariç), rotaya dik
    yönde `_YANAL_SEVIYE_KM` kadar kaydırılmış (ve başlangıca/bitişe yakın
    noktalarda zarfla sınırlanmış) aday konumlardan oluşan bir IZGARA üretir
    -- A* aramasının üzerinde gezineceği graf budur. Dönüş: {(i,
    seviye_indeksi): (enlem, boylam)} sözlüğü (uçlarda i=0 ve i=n-1 için
    SADECE orta seviye/0 km vardır, çünkü başlangıç/bitiş sabittir)."""
    n = len(enlemler_gc)
    konumlar = {(0, _ORTA_SEVIYE_INDEKSI): (enlemler_gc[0], boylamlar_gc[0])}
    for i in range(1, n - 1):
        yon = _ilk_yon_derece(enlemler_gc[i - 1], boylamlar_gc[i - 1], enlemler_gc[i + 1], boylamlar_gc[i + 1])
        dikey_yon = (yon + 90.0) % 360.0
        zarf_km = min(i, n - 1 - i) * _ZARF_KM_PER_ADIM
        for j, kaydirma_km in enumerate(_YANAL_SEVIYE_KM):
            if abs(kaydirma_km) > zarf_km:
                continue  # bu erken/geç noktada bu kadar sapmak fiziksel olarak gerçekci degil
            if kaydirma_km == 0.0:
                konumlar[(i, j)] = (enlemler_gc[i], boylamlar_gc[i])
            else:
                konumlar[(i, j)] = _hedef_nokta(enlemler_gc[i], boylamlar_gc[i], dikey_yon, kaydirma_km)
    konumlar[(n - 1, _ORTA_SEVIYE_INDEKSI)] = (enlemler_gc[n - 1], boylamlar_gc[n - 1])
    return konumlar


def _a_yildiz_ile_rota_ara(
    enlemler_gc, boylamlar_gc, irtifa_m, baslangic_zamani, tas_ms, veri_kupu, risk_katmanlari=()
):
    """
    A* (A-star) graf araması: büyük daire etrafındaki yanal ızgarada,
    başlangıçtan bitişe TOPLAM MALİYETİ (uçuş süresi + riskli türbülans
    cezası) EN AZA indiren yolu bulur. Ceza yeterince büyük olduğu için A*,
    mümkünse riskli türbülans içeren HİÇBİR kenardan geçmeyen bir yol bulur;
    böyle bir yol yoksa (türbülans alanı ızgaradan genişse), en az cezalı
    (en az riskli) yolu bulur -- açgözlü (greedy) bir "birkaç sabit aday
    dene" yaklaşımından farklı olarak, TÜM ızgarayı sistematik ve OPTİMAL
    şekilde arar.

    Sezgisel (heuristic) fonksiyon: kalan büyük daire mesafesi / (TAS x 1.8)
    -- gerçekte mümkün olabilecek en iyimser rüzgar hızlanmasını bile asla
    aşmayacak (admissible) bir alt sınır, bu yüzden A*'ın bulduğu yolun
    GERÇEKTEN optimal olduğu garantilidir.

    risk_katmanlari (bkz. risk_katmanlari.py): her katmanın yasak düğüm/
    kenarları grafdan çıkarılır (SERT kısıt), cezaları düğüme giriş
    maliyetine eklenir. veri_kupu None ise (hava verisi yok) rüzgarsız,
    sadece TAS ile aranır -- SIGMET kısıtı hava verisinden bağımsızdır.
    Hiçbir geçerli yol yoksa None döner (sessizce kısıt ihlal edilmez).
    """
    n = len(enlemler_gc)

    # Hava durumu örnekleme zamanı için nominal (sadece TAS ile) zaman
    # çizelgesi -- gerçek (rüzgarlı) süre yol seçildikten SONRA hesaplanır.
    nominal_zaman = pd.Timestamp(baslangic_zamani)
    if nominal_zaman.tzinfo is None:
        nominal_zaman = nominal_zaman.tz_localize("UTC")
    nominal_zamanlar = [nominal_zaman]
    for i in range(n - 1):
        mesafe_km = buyuk_daire_mesafesi_km(enlemler_gc[i], boylamlar_gc[i], enlemler_gc[i + 1], boylamlar_gc[i + 1])
        nominal_zamanlar.append(nominal_zamanlar[-1] + pd.Timedelta(seconds=mesafe_km * 1000.0 / tas_ms))

    konumlar = _yanal_izgara_dugum_konumlari(enlemler_gc, boylamlar_gc)

    # Hava verisi kapsamı dışına taşan ızgara düğümleri dürüstçe ELENİR (A*
    # onlardan asla geçemez) -- kapsam dışı bir noktada "türbülans yok" diye
    # YANLIŞ bir varsayımda bulunmamak için.
    dugumler = list(konumlar)
    if veri_kupu is not None:
        kapsam_disi = kapsam_disi_maskesi(
            veri_kupu,
            [konumlar[d][0] for d in dugumler],
            [konumlar[d][1] for d in dugumler],
            [nominal_zamanlar[d[0]] for d in dugumler],
        )
        dugumler = [d for d, disi in zip(dugumler, kapsam_disi) if not disi]
    konum_kumesi = set(dugumler)
    kenarlar = [(d, k) for d in dugumler for k in _komsu_dugumler(d, n) if k in konum_kumesi]

    risk = degerlendirmeleri_birlestir(
        katman.degerlendir(
            {d: konumlar[d] for d in dugumler}, {d: nominal_zamanlar[d[0]] for d in dugumler}, kenarlar, irtifa_m
        )
        for katman in risk_katmanlari
    )
    konum_kumesi -= risk.yasak_dugumler

    tum_enlem = np.array([konumlar[d][0] for d in dugumler])
    tum_boylam = np.array([konumlar[d][1] for d in dugumler])
    if veri_kupu is not None:
        u_tum, v_tum = ruzgar_bilesenlerini_toplu_al(
            veri_kupu,
            tum_enlem,
            tum_boylam,
            irtifa_metre_to_basinc_hpa(irtifa_m),
            [nominal_zamanlar[d[0]] for d in dugumler],
        )
        ruzgar_sozluk = dict(zip(dugumler, zip(u_tum.tolist(), v_tum.tolist())))
    else:
        ruzgar_sozluk = dict.fromkeys(dugumler, (0.0, 0.0))

    def _kenar_maliyeti_saniye(dugum_a, dugum_b):
        ea, ba = konumlar[dugum_a]
        eb, bb = konumlar[dugum_b]
        mesafe_km = buyuk_daire_mesafesi_km(ea, ba, eb, bb)
        yon = _ilk_yon_derece(ea, ba, eb, bb)
        u, v = ruzgar_sozluk[dugum_b]
        kuyruk_ruzgari_ms = u * math.sin(_bd(yon)) + v * math.cos(_bd(yon))
        yer_hizi_ms = max(tas_ms + kuyruk_ruzgari_ms, tas_ms * 0.2)
        return (mesafe_km * 1000.0) / yer_hizi_ms + risk.dugum_cezasi.get(dugum_b, 0.0)

    def _sezgisel_saniye(dugum):
        e, b = konumlar[dugum]
        kalan_km = buyuk_daire_mesafesi_km(e, b, enlemler_gc[-1], boylamlar_gc[-1])
        return (kalan_km * 1000.0) / (tas_ms * 1.8)

    baslangic_dugumu = (0, _ORTA_SEVIYE_INDEKSI)
    hedef_dugumu = (n - 1, _ORTA_SEVIYE_INDEKSI)
    if baslangic_dugumu not in konum_kumesi or hedef_dugumu not in konum_kumesi:
        return None

    acik_kume = [(_sezgisel_saniye(baslangic_dugumu), 0.0, baslangic_dugumu)]
    gercek_maliyet = {baslangic_dugumu: 0.0}
    ebeveyn = {}
    ziyaret_edildi = set()

    while acik_kume:
        _, mevcut_maliyet, dugum = heapq.heappop(acik_kume)
        if dugum in ziyaret_edildi:
            continue
        ziyaret_edildi.add(dugum)
        if dugum == hedef_dugumu:
            break
        for komsu in _komsu_dugumler(dugum, n):
            if komsu not in konum_kumesi or (dugum, komsu) in risk.yasak_kenarlar:
                continue
            yeni_maliyet = mevcut_maliyet + _kenar_maliyeti_saniye(dugum, komsu)
            if komsu not in gercek_maliyet or yeni_maliyet < gercek_maliyet[komsu]:
                gercek_maliyet[komsu] = yeni_maliyet
                ebeveyn[komsu] = dugum
                heapq.heappush(acik_kume, (yeni_maliyet + _sezgisel_saniye(komsu), yeni_maliyet, komsu))

    if hedef_dugumu not in ebeveyn:
        return None

    yol = [hedef_dugumu]
    while yol[-1] != baslangic_dugumu:
        yol.append(ebeveyn[yol[-1]])
    yol.reverse()

    yol_enlem = np.array([konumlar[d][0] for d in yol])
    yol_boylam = np.array([konumlar[d][1] for d in yol])
    maks_sapma_km = max((abs(_YANAL_SEVIYE_KM[j]) for _, j in yol), default=0.0)
    return yol_enlem, yol_boylam, maks_sapma_km


def _komsu_dugumler(dugum, n):
    """Bir sonraki ara noktada ulaşılabilen ızgara düğümleri. Seviye değişimi
    SINIRLI (±1) -- yoksa A*, uçağın fiziksel olarak yapamayacağı ani/sert
    yanal sıçramalar içeren, TOPLAM MESAFESİ aslında daha uzun olan bir
    "kısayol" bulabiliyor (gerçek veriyle doğrulandı). Son noktaya sadece orta
    seviyeden (bitiş sabit) girilir."""
    i, seviye = dugum
    if i >= n - 1:
        return []
    if i + 1 == n - 1:
        return [(n - 1, _ORTA_SEVIYE_INDEKSI)]
    return [(i + 1, j) for j in range(max(seviye - 1, 0), min(seviye + 1, len(_YANAL_SEVIYE_KM) - 1) + 1)]


# ---------------------------------------------------------------------------
# ERA5 kapsama alanı kontrolü ve rüzgar okuma
# ---------------------------------------------------------------------------


def _era5_tamamen_kapsiyor_mu(veri_kupu, enlemler, boylamlar, zaman, irtifa_m=None):
    if veri_kupu is None:
        return False
    enlemler = np.atleast_1d(np.asarray(enlemler, dtype=float))
    basinc_hpa = None if irtifa_m is None else np.full(len(enlemler), irtifa_metre_to_basinc_hpa(irtifa_m))
    return not kapsam_disi_maskesi(veri_kupu, enlemler, boylamlar, [zaman] * len(enlemler), basinc_hpa).any()


def _tz_sizlestir(zaman):
    ts = pd.Timestamp(zaman)
    if ts.tzinfo is not None:
        ts = ts.tz_convert("UTC").tz_localize(None)
    return ts


def ruzgar_bilesenlerini_al(veri_kupu, enlem, boylam, basinc_hpa, zaman):
    basinc_seviyeleri = np.sort(veri_kupu[config.BASINC_BOYUTU].values)
    en_yakin_seviye = en_yakin_basinc_seviyesi(basinc_hpa, basinc_seviyeleri)
    dilim = veri_kupu.sel(
        **{config.BASINC_BOYUTU: en_yakin_seviye},
        latitude=enlem,
        longitude=boylam,
        valid_time=_tz_sizlestir(zaman),
        method="nearest",
    )
    return float(dilim["u"].values), float(dilim["v"].values)


def ruzgar_bilesenlerini_toplu_al(veri_kupu, enlemler, boylamlar, basinc_hpa, zamanlar):
    """ruzgar_bilesenlerini_al'ın çok noktalı karşılığı -- tüm noktalar tek bir
    vektörel .sel() ile okunur. Dönüş: (u_dizisi, v_dizisi)."""
    enlemler = np.asarray(enlemler, dtype=float)
    if len(enlemler) == 0:
        return np.array([]), np.array([])
    basinc_seviyeleri = np.sort(veri_kupu[config.BASINC_BOYUTU].values)
    basinc_hpa = np.broadcast_to(np.asarray(basinc_hpa, dtype=float), enlemler.shape)
    seviyeler = basinc_seviyeleri[np.abs(basinc_seviyeleri[None, :] - basinc_hpa[:, None]).argmin(axis=1)]
    boyut = "nokta"
    dilim = veri_kupu.sel(
        **{config.BASINC_BOYUTU: xr.DataArray(seviyeler, dims=boyut)},
        latitude=xr.DataArray(enlemler, dims=boyut),
        longitude=xr.DataArray(np.asarray(boylamlar, dtype=float), dims=boyut),
        valid_time=xr.DataArray(pd.DatetimeIndex([_tz_sizlestir(z) for z in zamanlar]).to_numpy(), dims=boyut),
        method="nearest",
    )
    return dilim["u"].to_numpy(), dilim["v"].to_numpy()


# ---------------------------------------------------------------------------
# Bir rotanın uçuş süresini/yakıtını hesaplama
# ---------------------------------------------------------------------------


def _rotayi_zamanla(enlemler, boylamlar, irtifa_m, baslangic_zamani, tas_ms, veri_kupu, ruzgarli_mi):
    """Rota boyunca her bacağı (leg) sırayla zamanlar; dönüş:
    (toplam_saniye, her_noktadaki_zaman_listesi)."""
    basinc_hpa = irtifa_metre_to_basinc_hpa(irtifa_m)
    zaman = pd.Timestamp(baslangic_zamani)
    if zaman.tzinfo is None:
        zaman = zaman.tz_localize("UTC")
    zamanlar = [zaman]
    toplam_saniye = 0.0

    for i in range(len(enlemler) - 1):
        mesafe_km = buyuk_daire_mesafesi_km(enlemler[i], boylamlar[i], enlemler[i + 1], boylamlar[i + 1])
        yer_hizi_ms = tas_ms

        if ruzgarli_mi:
            yon_derece = _ilk_yon_derece(enlemler[i], boylamlar[i], enlemler[i + 1], boylamlar[i + 1])
            orta_enlem = (enlemler[i] + enlemler[i + 1]) / 2
            orta_boylam = (boylamlar[i] + boylamlar[i + 1]) / 2
            u, v = ruzgar_bilesenlerini_al(veri_kupu, orta_enlem, orta_boylam, basinc_hpa, zaman)
            # Rüzgarın rota yönündeki izdüşümü (kuyruk rüzgarı pozitif, burun
            # rüzgarı negatif): u=doğu bileşeni, v=kuzey bileşeni.
            kuyruk_ruzgari_ms = u * math.sin(_bd(yon_derece)) + v * math.cos(_bd(yon_derece))
            # Yer hızının aşırı düşüp bacak süresini gerçekçi olmayan
            # biçimde şişirmesini önlemek için alt sınır (TAS'ın %20'si).
            yer_hizi_ms = max(tas_ms + kuyruk_ruzgari_ms, tas_ms * 0.2)

        bacak_saniye = (mesafe_km * 1000.0) / yer_hizi_ms
        toplam_saniye += bacak_saniye
        zaman = zaman + pd.Timedelta(seconds=bacak_saniye)
        zamanlar.append(zaman)

    return toplam_saniye, zamanlar


def _ti1_ozeti_cikar(ti1_degerleri):
    """Dönüş: (maks_ti1 ya da hepsi NaN ise None, riskli_nokta_sayisi)."""
    if ti1_degerleri is None or np.all(np.isnan(ti1_degerleri)):
        return None, 0
    maks_ti1 = float(np.nanmax(ti1_degerleri))
    riskli_sayisi = int(np.nansum(ti1_degerleri >= config.TI1_ESIK_ORTA_SIDDETLI))
    return maks_ti1, riskli_sayisi


def _noktalari_paketle(enlemler, boylamlar, irtifa_m, zamanlar):
    return [
        {"enlem": float(e), "boylam": float(b), "irtifa_m": float(irtifa_m), "zaman": z.isoformat()}
        for e, b, z in zip(enlemler, boylamlar, zamanlar)
    ]


def _irtifa_degisimi_maliyeti(eski_irtifa_m, yeni_irtifa_m, yakit_akisi_kg_saat):
    """İki irtifa arasında geçişin EKSTRA maliyetini hesaplar (normal
    seyire göre FARK olarak): (ekstra_saniye, ekstra_yakit_kg). Tırmanma
    pozitif, alçalma NEGATİF (yakıt tasarrufu) ekstra_yakit_kg döndürebilir
    -- bkz. modül başındaki TIRMANMA_EK_YAKIT_ORANI/ALCALMA_YAKIT_TASARRUFU_
    ORANI notu."""
    fark_ft = (yeni_irtifa_m - eski_irtifa_m) / 0.3048
    if fark_ft == 0:
        return 0.0, 0.0
    sure_saat = abs(fark_ft) / DIKEY_HIZ_FT_DK / 60.0
    oran = TIRMANMA_EK_YAKIT_ORANI if fark_ft > 0 else -ALCALMA_YAKIT_TASARRUFU_ORANI
    ekstra_yakit_kg = yakit_akisi_kg_saat * sure_saat * oran
    return sure_saat * 3600.0, ekstra_yakit_kg


def _en_yakin_komsu_basinc_seviyeleri(veri_kupu, irtifa_m):
    """Veri küpündeki basınç seviyeleri arasından, mevcut irtifaya en yakın
    olanın BİR ÜST ve BİR ALT komşusunu (varsa) irtifa (m) olarak döner --
    'irtifa değiştirerek kaçınma' adaylarını üretmek için."""
    basinc_seviyeleri = np.sort(veri_kupu[config.BASINC_BOYUTU].values)  # artan basınç = azalan irtifa
    mevcut_basinc = irtifa_metre_to_basinc_hpa(irtifa_m)
    en_yakin_indeks = int(np.argmin(np.abs(basinc_seviyeleri - mevcut_basinc)))
    sonuc = {}
    if en_yakin_indeks - 1 >= 0:
        sonuc["irtifa_yukari"] = basinc_hpa_to_irtifa_metre(basinc_seviyeleri[en_yakin_indeks - 1])
    if en_yakin_indeks + 1 < len(basinc_seviyeleri):
        sonuc["irtifa_asagi"] = basinc_hpa_to_irtifa_metre(basinc_seviyeleri[en_yakin_indeks + 1])
    return sonuc


# ---------------------------------------------------------------------------
# Üst düzey giriş noktası
# ---------------------------------------------------------------------------


def _sigmet_katmanini_hazirla(sigmetler, enlemler_gc, boylamlar_gc, zaman_iso, tas_ms):
    """Rota bölgesi/zamanı için aktif SIGMET'leri (verilmediyse veritabanından)
    yükleyip sert kısıt katmanını kurar. Dönüş: (katman ya da None, özet)."""
    baslangic = pd.Timestamp(zaman_iso)
    baslangic = baslangic.tz_localize("UTC") if baslangic.tzinfo is None else baslangic.tz_convert("UTC")
    toplam_km = sum(
        buyuk_daire_mesafesi_km(enlemler_gc[i], boylamlar_gc[i], enlemler_gc[i + 1], boylamlar_gc[i + 1])
        for i in range(len(enlemler_gc) - 1)
    )
    bitis = (baslangic + pd.Timedelta(seconds=toplam_km * 1000.0 / (tas_ms * 0.6)) + pd.Timedelta(hours=1)).ceil("s")
    ozet = {"durum": "aktif_sigmet_yok", "aktif_sigmet_sayisi": 0, "son_guncelleme": None, "bayat_mi": False}

    if sigmetler is None:
        try:
            sigmetler = gecerli_sigmetleri_getir(
                baslangic.to_pydatetime(),
                bitis.to_pydatetime(),
                float(np.min(enlemler_gc)) - _SIGMET_ARAMA_PAYI_DERECE,
                float(np.max(enlemler_gc)) + _SIGMET_ARAMA_PAYI_DERECE,
                float(np.min(boylamlar_gc)) - _SIGMET_ARAMA_PAYI_DERECE,
                float(np.max(boylamlar_gc)) + _SIGMET_ARAMA_PAYI_DERECE,
                tehlikeler=config.SIGMET_KACINILACAK_TEHLIKELER,
            )
            ozet["son_guncelleme"] = son_guncelleme_zamani()
        except Exception as hata:
            _logger.warning("SIGMET'ler okunamadı, rota SIGMET kontrolü olmadan hesaplanıyor: %s", hata)
            return None, {**ozet, "durum": "erisilemedi", "sigmetler": []}
        simdi = pd.Timestamp.now(tz="UTC")
        canli_mi = abs(simdi - baslangic) <= pd.Timedelta(hours=24)
        esik = pd.Timedelta(minutes=config.SIGMET_BAYATLIK_DAKIKA)
        ozet["bayat_mi"] = bool(
            canli_mi and (ozet["son_guncelleme"] is None or simdi - pd.Timestamp(ozet["son_guncelleme"]) > esik)
        )

    katman = SigmetKisitKatmani(sigmetler)
    ozet["sigmetler"] = [
        {
            "id": sg.get("id"),
            "fir_kodu": sg.get("fir_kodu"),
            "tehlike": sg["tehlike"],
            "taban_ft": sg["taban_ft"],
            "tavan_ft": sg["tavan_ft"],
            "gecerlilik_baslangic": sg["gecerlilik_baslangic"],
            "gecerlilik_bitis": sg["gecerlilik_bitis"],
            "poligon": sg["poligon"],
        }
        for sg in katman.sigmetler
    ]
    ozet["aktif_sigmet_sayisi"] = len(katman.sigmetler)
    if not katman.sigmetler:
        return None, ozet
    return katman, {**ozet, "durum": "uygulandi"}


def rota_simulasyonu_olustur(
    baslangic_enlem,
    baslangic_boylam,
    bitis_enlem,
    bitis_boylam,
    irtifa_ft,
    zaman_iso,
    ucak_modeli_kodu,
    sigmetler=None,
):
    """
    İki gerçek rota üretir: büyük daire ("normal") ve "optimize" rota.
    Öncelik sırası: (1) aktif SIGMET'lere GİRMEMEK (sert kısıt, bkz.
    risk_katmanlari.SigmetKisitKatmani), (2) riskli TI1 türbülansından
    kaçınmak, (3) en ucuz (yakıt/süre) yol. SIGMET'e girmeyen hiçbir aday
    bulunamazsa rota ÖNERİLMEZ (guvenli_rota_bulundu_mu=False).
    sigmetler: None ise veritabanındaki (sigmet_saglayici.py) aktif SIGMET'ler
    kullanılır; test/backtest için açıkça bir liste verilebilir.
    Dönüş, api_servisi.py'nin doğrudan JSON'a çevirebileceği bir dict'tir.
    """
    if ucak_modeli_kodu not in UCAK_PROFILLERI:
        raise ValueError(f"Bilinmeyen uçak modeli: '{ucak_modeli_kodu}'. Geçerli seçenekler: {list(UCAK_PROFILLERI)}")

    profil = UCAK_PROFILLERI[ucak_modeli_kodu]
    tas_ms = profil["tas_ms"]
    irtifa_m = irtifa_ft * 0.3048
    enlemler_gc, boylamlar_gc = buyuk_daire_rotasi_olustur(
        baslangic_enlem, baslangic_boylam, bitis_enlem, bitis_boylam, config.ROTA_SIMULASYONU_NOKTA_SAYISI
    )

    veri_kupu = veri_kupune_eris(
        enlemler_gc,
        boylamlar_gc,
        zaman_iso,
        irtifa_m,
        zamanlar=_tahmini_varis_zamanlari(enlemler_gc, boylamlar_gc, zaman_iso, tas_ms),
    )
    ruzgarli_mi = _era5_tamamen_kapsiyor_mu(veri_kupu, enlemler_gc, boylamlar_gc, zaman_iso, irtifa_m)
    kup_adi = veri_kupu_adi(veri_kupu)
    sigmet_katmani, sigmet_kontrolu = _sigmet_katmanini_hazirla(sigmetler, enlemler_gc, boylamlar_gc, zaman_iso, tas_ms)

    def _aday(strateji, enlemler, boylamlar, aday_irtifa_m, yanal_sapma_km=0.0, ekstra=(0.0, 0.0)):
        saniye, zamanlar = _rotayi_zamanla(
            enlemler, boylamlar, aday_irtifa_m, zaman_iso, tas_ms, veri_kupu, ruzgarli_mi
        )
        if ruzgarli_mi:
            maks_ti1, riskli_sayisi = _ti1_ozeti_cikar(
                rota_ti1_degerleri(enlemler, boylamlar, aday_irtifa_m, zamanlar, veri_kupu)
            )
        else:
            maks_ti1, riskli_sayisi = None, 0
        return {
            "strateji": strateji,
            "enlem": enlemler,
            "boylam": boylamlar,
            "irtifa_m": aday_irtifa_m,
            "zamanlar": zamanlar,
            "saniye": saniye,
            "ekstra_saniye": ekstra[0],
            "ekstra_yakit_kg": ekstra[1],
            "maks_ti1": maks_ti1,
            "riskli_sayisi": riskli_sayisi,
            "sigmet_ihlali": (
                sigmet_katmani.rota_ihlal_sayisi(enlemler, boylamlar, zamanlar, aday_irtifa_m) if sigmet_katmani else 0
            ),
            "yanal_sapma_km": yanal_sapma_km,
        }

    def _aday_toplam_yakit_kg(aday):
        return profil["yakit_akisi_kg_saat"] * (aday["saniye"] / 3600.0) + aday["ekstra_yakit_kg"]

    normal = _aday("yok", enlemler_gc, boylamlar_gc, irtifa_m)
    guvenli_rota_bulundu_mu = True

    if normal["riskli_sayisi"] == 0 and normal["sigmet_ihlali"] == 0:
        # Kaçınılacak risk YOK -- kullanıcıyla netleştirilen ilkeyle, uydurma
        # bir sapma göstermek yerine optimize rota normal rotayla BİREBİR AYNI.
        en_iyi = normal
    else:
        # ÇOK FAKTÖRLÜ karşılaştırma: (1) YANAL -- A* ile büyük daire
        # etrafındaki ızgarada, risk katmanlarına (TI1 cezası + SIGMET yasağı)
        # göre en ucuz yol; (2/3) İRTİFA -- aynı yatay rotada bir üst/alt
        # basınç seviyesi (gerçek tırmanma/alçalma bedeliyle, bkz.
        # _irtifa_degisimi_maliyeti). Bazı CAT katmanları ve SIGMET'ler
        # irtifaya bağlıdır; seviye değiştirmek bazen en ucuz güvenli seçenektir.
        risk_katmanlari = [Ti1CezaKatmani(veri_kupu)] if ruzgarli_mi else []
        if sigmet_katmani is not None:
            risk_katmanlari.append(sigmet_katmani)
        adaylar = []
        yanal = _a_yildiz_ile_rota_ara(
            enlemler_gc, boylamlar_gc, irtifa_m, zaman_iso, tas_ms, veri_kupu if ruzgarli_mi else None, risk_katmanlari
        )
        if yanal is not None:
            adaylar.append(_aday("yanal", yanal[0], yanal[1], irtifa_m, yanal_sapma_km=yanal[2]))
        irtifa_secenekleri = _en_yakin_komsu_basinc_seviyeleri(veri_kupu, irtifa_m) if ruzgarli_mi else {}
        for strateji_adi, yeni_irtifa_m in irtifa_secenekleri.items():
            ekstra = _irtifa_degisimi_maliyeti(irtifa_m, yeni_irtifa_m, profil["yakit_akisi_kg_saat"])
            adaylar.append(_aday(strateji_adi, enlemler_gc, boylamlar_gc, yeni_irtifa_m, ekstra=ekstra))

        sigmete_uyan = [a for a in adaylar if a["sigmet_ihlali"] == 0]
        tam_guvenli = [a for a in sigmete_uyan if a["riskli_sayisi"] == 0]
        if tam_guvenli or sigmete_uyan:
            en_iyi = min(tam_guvenli or sigmete_uyan, key=_aday_toplam_yakit_kg)
        else:
            # SERT kısıt sağlanamadı: kısıtı ihlal eden bir rota "optimize"
            # diye önerilmez -- normal rota gösterilir ve açıkça işaretlenir.
            en_iyi, guvenli_rota_bulundu_mu = normal, False

    normal_yakit_kg = _aday_toplam_yakit_kg(normal)
    # İrtifa değişiminde toplam süre tırmanma/alçalmayı da içerir, ama o süre
    # boyunca yakıt akışı SEYİR hızında DEĞİLDİR -- yakıt, seyir süresinden +
    # ayrıca hesaplanan ek yakıttan hesaplanır (bkz. _irtifa_degisimi_maliyeti).
    optimize_yakit_kg = _aday_toplam_yakit_kg(en_iyi)
    optimize_saniye = en_iyi["saniye"] + en_iyi["ekstra_saniye"]

    return {
        "ruzgar_verisi_kaynagi": (
            ("gfs_tahmin" if veri_kupu_kaynagi(veri_kupu) == "gfs" else "era5_gercek")
            if ruzgarli_mi
            else "era5_kapsam_disi"
        ),
        "aciklama": _aciklama_olustur(
            ruzgarli_mi, veri_kupu, kup_adi, normal, en_iyi, irtifa_m, sigmet_kontrolu, guvenli_rota_bulundu_mu
        ),
        "ucak_modeli": ucak_modeli_kodu,
        "ucak_etiketi": profil["etiket"],
        "turbulanstan_kacinildi_mi": en_iyi["riskli_sayisi"] < normal["riskli_sayisi"],
        "sigmetten_kacinildi_mi": normal["sigmet_ihlali"] > 0 and en_iyi["sigmet_ihlali"] == 0,
        "guvenli_rota_bulundu_mu": guvenli_rota_bulundu_mu,
        "kacinma_stratejisi": en_iyi["strateji"],
        "sigmet_kontrolu": sigmet_kontrolu,
        "normal_rota": _rota_ozeti(normal, normal_yakit_kg, normal["saniye"]),
        "optimize_rota": {
            **_rota_ozeti(en_iyi, optimize_yakit_kg, optimize_saniye),
            "maks_yanal_sapma_km": en_iyi["yanal_sapma_km"],
        },
        "sure_tasarrufu_dk": (normal["saniye"] - optimize_saniye) / 60.0,
        "yakit_tasarrufu_yuzde": (
            100.0 * (normal_yakit_kg - optimize_yakit_kg) / normal_yakit_kg if normal_yakit_kg > 0 else 0.0
        ),
        "co2_farki_kg": normal_yakit_kg * CO2_KG_PER_KG_YAKIT - optimize_yakit_kg * CO2_KG_PER_KG_YAKIT,
    }


def _rota_ozeti(aday, yakit_kg, toplam_saniye):
    enlemler, boylamlar = aday["enlem"], aday["boylam"]
    return {
        "noktalar": _noktalari_paketle(enlemler, boylamlar, aday["irtifa_m"], aday["zamanlar"]),
        "toplam_sure_dk": toplam_saniye / 60.0,
        "mesafe_km": sum(
            buyuk_daire_mesafesi_km(enlemler[i], boylamlar[i], enlemler[i + 1], boylamlar[i + 1])
            for i in range(len(enlemler) - 1)
        ),
        "tahmini_yakit_kg": yakit_kg,
        "tahmini_co2_kg": yakit_kg * CO2_KG_PER_KG_YAKIT,
        "irtifa_ft": aday["irtifa_m"] / 0.3048,
        "maks_ti1": aday["maks_ti1"],
        "riskli_nokta_sayisi": aday["riskli_sayisi"],
        "sigmet_ihlali_sayisi": aday["sigmet_ihlali"],
    }


def _aciklama_olustur(
    ruzgarli_mi, veri_kupu, kup_adi, normal, en_iyi, irtifa_m, sigmet_kontrolu, guvenli_rota_bulundu_mu
):
    cumleler = []
    if ruzgarli_mi and veri_kupu_kaynagi(veri_kupu) == "gfs":
        calisma = veri_kupu.attrs.get("model_calisma_zamani", "bilinmiyor")
        cumleler.append(f"Canlı NOAA GFS tahmin verisiyle hesaplandı (model çalıştırması {calisma} UTC).")
    elif ruzgarli_mi:
        cumleler.append(f"Gerçek ERA5 verisiyle hesaplandı ('{kup_adi}').")
    if ruzgarli_mi:
        if normal["riskli_sayisi"] == 0:
            cumleler.append(
                f"Normal rota üzerinde riskli türbülans (TI1 >= {config.TI1_ESIK_ORTA_SIDDETLI:.1e} s^-2) TESPİT EDİLMEDİ."
            )
        else:
            cumleler.append(f"Normal rota üzerinde {normal['riskli_sayisi']} noktada riskli türbülans tespit edildi.")
    else:
        cumleler.append(
            "Seçilen bölge/tarih/irtifa için ne projenin ERA5 veri küpleri (ana küp: "
            f"'{config.HAVA_DURUMU_DOSYASI}', ek küpler: '{config.EK_HAVA_DURUMU_KLASORU}/') ne de canlı GFS "
            f"verisi (şimdi -{config.CANLI_GECMIS_SAAT} sa / +{config.CANLI_TAHMIN_UFKU_SAAT} sa aralığı için) "
            "rotanın TAMAMINI kapsıyor -- rüzgar ve türbülans (TI1) hesaba katılamadı, rotalar sadece uçağın hava "
            "hızıyla (TAS) zamanlandı; gerçek bir yakıt tasarrufu/türbülans kaçınması iddia edilmiyor."
        )

    durum = sigmet_kontrolu["durum"]
    if durum == "erisilemedi":
        cumleler.append("UYARI: SIGMET veritabanına erişilemedi -- aktif SIGMET kontrolü YAPILAMADI.")
    elif durum == "uygulandi":
        ihlal = normal["sigmet_ihlali"]
        cumleler.append(
            f"{sigmet_kontrolu['aktif_sigmet_sayisi']} aktif SIGMET sert kısıt olarak uygulandı; normal rota "
            + (f"{ihlal} nokta/bacakta bunlara giriyor." if ihlal else "bunlara girmiyor.")
        )
    if sigmet_kontrolu.get("bayat_mi"):
        cumleler.append(
            f"UYARI: son SIGMET güncellemesi {config.SIGMET_BAYATLIK_DAKIKA} dakikadan eski ya da hiç yapılmamış "
            "(bkz. POST /api/v1/sigmet/guncelle) -- aktif uyarılar eksik olabilir."
        )

    if not guvenli_rota_bulundu_mu:
        cumleler.append(
            "ÖNERİ YOK: aktif SIGMET'lere girmeyen geçerli bir rota bulunamadı (başlangıç/bitiş SIGMET içinde "
            "olabilir ya da alan arama ızgarasından geniş) -- gösterilen rota normal rotadır ve ÖNERİLMEZ."
        )
    elif en_iyi["strateji"] == "yok":
        cumleler.append(
            "Kaçınılacak bir risk olmadığı için optimize rota normal rotayla birebir aynıdır "
            "(uydurma bir sapma gösterilmiyor)."
        )
    else:
        strateji_aciklamasi = {
            "yanal": f"A* araması ile yanal sapma (en fazla {en_iyi['yanal_sapma_km']:.0f} km)",
            "irtifa_yukari": f"irtifayı {(en_iyi['irtifa_m'] - irtifa_m) / 0.3048:.0f} ft artırarak (tırmanma)",
            "irtifa_asagi": f"irtifayı {(irtifa_m - en_iyi['irtifa_m']) / 0.3048:.0f} ft azaltarak (alçalma)",
        }[en_iyi["strateji"]]
        if not ruzgarli_mi:
            cumleler.append(f"Aktif SIGMET'lere girmeyen en kısa rota olarak {strateji_aciklamasi} bulundu.")
        elif en_iyi["riskli_sayisi"] == 0:
            cumleler.append(
                "ÇOK FAKTÖRLÜ karşılaştırmada (yanal A* araması vs bir üst/alt basınç seviyesine geçiş, her biri "
                f"gerçek yakıt/süre maliyetiyle) en ucuz TAM güvenli seçenek olarak {strateji_aciklamasi} bulundu."
            )
        else:
            cumleler.append(
                "Denenen adaylar TI1 riskini TAMAMEN ortadan kaldıramadı (türbülans alanı geniş olabilir) -- "
                f"SIGMET kısıtına uyan seçenekler arasından {strateji_aciklamasi} seçildi "
                f"({en_iyi['riskli_sayisi']} riskli nokta, normal rotadaki {normal['riskli_sayisi']}'e karşı)."
            )
    return " ".join(cumleler)


# ---------------------------------------------------------------------------
# CZML üretimi (web/ucus_simulasyonu.html CesiumJS'in doğrudan yükleyebildiği format)
# ---------------------------------------------------------------------------

_UCAK_MODEL_URL = "/harita/models/ucak.glb"


def _rotayi_czml_varligina_cevir(rota, id_, isim, rgba):
    noktalar = rota["noktalar"]
    epoch = noktalar[0]["zaman"]
    cartographic = []
    duz_koordinatlar = []  # [boylam, enlem, irtifa, boylam, enlem, irtifa, ...] -- zamana bağlı değil
    for n in noktalar:
        saniye_farki = (pd.Timestamp(n["zaman"]) - pd.Timestamp(epoch)).total_seconds()
        cartographic.extend([saniye_farki, n["boylam"], n["enlem"], n["irtifa_m"]])
        duz_koordinatlar.extend([n["boylam"], n["enlem"], n["irtifa_m"]])

    ucak_varligi = {
        "id": id_,
        "name": isim,
        "availability": f"{epoch}/{noktalar[-1]['zaman']}",
        "position": {"epoch": epoch, "cartographicDegrees": cartographic, "interpolationAlgorithm": "LAGRANGE"},
        "orientation": {"velocityReference": f"{id_}#position"},
        "model": {"gltf": _UCAK_MODEL_URL, "scale": 1.0, "minimumPixelSize": 48, "maximumScale": 20000},
        "path": {
            "material": {"solidColor": {"color": {"rgba": rgba}}},
            "width": 3,
            "leadTime": 0,
            "trailTime": 999999,
            "resolution": 60,
        },
        "label": {
            "text": isim,
            "font": "13px sans-serif",
            "pixelOffset": {"cartesian2": [0, -22]},
            "fillColor": {"rgba": rgba},
            "showBackground": True,
        },
    }

    # CZML 'path' SADECE o ana kadar UÇULMUŞ izi çizer (trailTime ne kadar
    # büyük olursa olsun, gelecek kısmı göstermez) -- kullanıcı simülasyonu
    # başlatır başlatmaz rotanın TAMAMINI görebilsin diye, zamana bağlı
    # olmayan ayrı bir statik çizgi (ince, yarı saydam) ayrıca ekleniyor.
    on_izleme_cizgisi = {
        "id": f"{id_}-on-izleme",
        "name": f"{isim} (tüm rota)",
        "polyline": {
            "positions": {"cartographicDegrees": duz_koordinatlar},
            "material": {"solidColor": {"color": {"rgba": [rgba[0], rgba[1], rgba[2], 90]}}},
            "width": 2,
            "clampToGround": False,
        },
    }
    return ucak_varligi, on_izleme_cizgisi


def simulasyonu_czml_e_cevir(sonuc):
    """rota_simulasyonu_olustur(...) çıktısını, CesiumJS CzmlDataSource'un
    doğrudan yükleyebileceği bir CZML paket listesine çevirir."""
    normal_bitis = sonuc["normal_rota"]["noktalar"][-1]["zaman"]
    optimize_bitis = sonuc["optimize_rota"]["noktalar"][-1]["zaman"]
    baslangic = sonuc["normal_rota"]["noktalar"][0]["zaman"]
    genel_bitis = max(normal_bitis, optimize_bitis)

    belge_paketi = {
        "id": "document",
        "name": "Ucus Simulasyonu",
        "version": "1.0",
        "clock": {
            "interval": f"{baslangic}/{genel_bitis}",
            "currentTime": baslangic,
            "multiplier": 60,
            "range": "CLAMPED",
        },
    }
    normal_ucak, normal_on_izleme = _rotayi_czml_varligina_cevir(
        sonuc["normal_rota"], "normal-rota", "Normal Rota (buyuk daire)", [51, 136, 255, 255]
    )
    optimize_ucak, optimize_on_izleme = _rotayi_czml_varligina_cevir(
        sonuc["optimize_rota"], "optimize-rota", "Optimize Rota (turbulanstan kacinma)", [46, 204, 113, 255]
    )
    sigmet_varliklari = [
        _sigmeti_czml_varligina_cevir(sigmet, i)
        for i, sigmet in enumerate((sonuc.get("sigmet_kontrolu") or {}).get("sigmetler", []))
    ]
    # Statik ön izleme çizgileri ve SIGMET hacimleri ÖNCE eklenir ki uçak
    # modelleri/etiketleri onların üzerinde (z-sırasında sonda) görünsün.
    return [belge_paketi, *sigmet_varliklari, normal_on_izleme, optimize_on_izleme, normal_ucak, optimize_ucak]


_SIGMET_VARSAYILAN_TAVAN_FT = 45000


def _sigmeti_czml_varligina_cevir(sigmet, sira):
    """Aktif SIGMET'i, taban-tavan irtifaları arasında yükseltilmiş
    (extruded) yarı saydam kırmızı bir hacim olarak çizer -- A*'ın kaçındığı
    'yasak bölge' 3D sahnede görünür olsun diye."""
    taban_m = (sigmet.get("taban_ft") or 0) * 0.3048
    tavan_m = (sigmet.get("tavan_ft") or _SIGMET_VARSAYILAN_TAVAN_FT) * 0.3048
    koseler = [deger for boylam, enlem in sigmet["poligon"] for deger in (boylam, enlem, taban_m)]
    baslangic = pd.Timestamp(sigmet["gecerlilik_baslangic"]).isoformat()
    bitis = pd.Timestamp(sigmet["gecerlilik_bitis"]).isoformat()
    return {
        "id": f"sigmet-{sigmet.get('id') or sira}",
        "name": f"SIGMET {sigmet.get('fir_kodu') or ''} {sigmet['tehlike']}".strip(),
        "availability": f"{baslangic}/{bitis}",
        "polygon": {
            "positions": {"cartographicDegrees": koseler},
            "height": taban_m,
            "extrudedHeight": tavan_m,
            "material": {"solidColor": {"color": {"rgba": [231, 76, 60, 70]}}},
            "outline": True,
            "outlineColor": {"rgba": [231, 76, 60, 200]},
        },
    }
