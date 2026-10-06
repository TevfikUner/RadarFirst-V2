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
  - Büyük daire rotası etrafında, rotaya dik yönde kaydırılmış aday
    konumlardan oluşan bir IZGARA (graf) kurulur (bkz. _YanalIzgara). Sınırlar
    mesafe ve açıyla tanımlıdır: her bacağın büyük daire yönüne göre açısı en
    fazla config.ROTA_MAKS_SAPMA_ACISI_DERECE, toplam sapma en fazla
    config.ROTA_MAKS_YANAL_SAPMA_KM.
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
from dataclasses import dataclass

import numpy as np
import pandas as pd
import shapely
import xarray as xr

from turbulans_radar import config
from turbulans_radar.fizik.birim_donusumleri import (
    en_yakin_basinc_seviyesi,
    irtifa_metre_to_basinc_hpa,
)
from turbulans_radar.fizik.eslestirme import kapsam_disi_maskesi
from turbulans_radar.fizik.iz_bulutu import duyarli_nokta_sayisi
from turbulans_radar.fizik.turbulans_indeksleri import TI1_GUVENILIRLIK_NOTU
from turbulans_radar.loglama import logger_al
from turbulans_radar.rota import hava_yolu_agi, ucus_seviyeleri
from turbulans_radar.rota.risk_katmanlari import (
    KisitliSahaKatmani,
    SigmetKisitKatmani,
    Ti1CezaKatmani,
    degerlendirmeleri_birlestir,
    rota_eslesmesi,
)
from turbulans_radar.veri.kisitli_saha_saglayici import ORNEK_KAYNAK, gecerli_kisitli_sahalari_getir
from turbulans_radar.veri.sigmet_saglayici import (
    gecerli_sigmetleri_getir,
    kacinilacak_tehlikeler,
    son_guncelleme_zamani,
    sorunlu_kaynaklar,
)
from turbulans_radar.veri.veri_saglayicilari import veri_kupu_kaynagi, veri_kupunu_sec
from turbulans_radar.veri.veri_yukleme import hava_durumu_onbellekli_yukle, veri_kupu_adi

DUNYA_YARICAPI_M = 6_371_000.0

# Yaklaşık, halka açık tipik seyir performansı değerleri (bkz. modül dosya
# başlığı) -- resmi üretici verisi değildir, sadece büyüklük mertebesi
# doğru, karşılaştırma amaçlı kaba tahminlerdir.
# azami_fl: halka açık azami işletme irtifası (A320 39.800 ft, 737-800 41.000 ft,
# 777-300ER ve A350-900 43.100 ft); kütleye bağlı fiili tavan modellenmez.
UCAK_PROFILLERI = {
    "A320": {
        "etiket": "Airbus A320 (dar gövde, kısa/orta menzil)",
        "tas_ms": 230.0,
        "yakit_akisi_kg_saat": 2400.0,
        "azami_fl": 398,
    },
    "B738": {
        "etiket": "Boeing 737-800 (dar gövde, kısa/orta menzil)",
        "tas_ms": 227.0,
        "yakit_akisi_kg_saat": 2500.0,
        "azami_fl": 410,
    },
    "B77W": {
        "etiket": "Boeing 777-300ER (geniş gövde, uzun menzil)",
        "tas_ms": 250.0,
        "yakit_akisi_kg_saat": 6800.0,
        "azami_fl": 431,
    },
    "A359": {
        "etiket": "Airbus A350-900 (geniş gövde, uzun menzil)",
        "tas_ms": 252.0,
        "yakit_akisi_kg_saat": 5800.0,
        "azami_fl": 431,
    },
}

# Jet yakıtının (Jet A-1) yanma başına CO2 emisyon katsayısı -- ICAO/IPCC'nin
# standart, halka açık "emission factor" değeridir (kaynak: ICAO Carbon
# Emissions Calculator Methodology / IPCC Guidelines for National Greenhouse
# Gas Inventories, karbon içeriğinden hesaplanan yakma katsayısı). Yakıt
# TÜRÜNE göre neredeyse sabittir (kerosen bazlı jet yakıtları için ~3.15-3.16
# kg CO2 / kg yakıt) -- uçak modeline göre DEĞİŞMEZ, uydurma bir katsayı DEĞİLDİR.
CO2_KG_PER_KG_YAKIT = 3.16

# İrtifa değişimi (tırmanma/alçalma) maliyet modeli: aynı yönün bir üst/alt yasal
# FL'sine geçmek irtifaya bağlı bir CAT katmanını atlatabilir. Seyir başı ve
# sonu planlanan seviyede olduğu için (ToC/ToD, bkz. kapsam) geçici seviyeye
# gidiş ve planlanan seviyeye dönüş BİRLİKTE maliyetlenir: tırmanma ve alçalma
# simetriktir, hiçbiri yakıt "tasarrufu" göstermez. Katsayılar YAKLAŞIKTIR
# (halka açık tipik jet mertebeleri, resmi performans verisi DEĞİL); seviyeye
# bağlı seyir yakıt akışı ve TAS modellenmez.
#   - Tırmanmada yakıt akışı seyrin ~%50 üstü; alçalmaya kredi verilmez (seyirle aynı).
#   - Dikey hız ~1500 ft/dk; uçak bu sürede ilerlediği için ek süre sayılmaz.
TIRMANMA_EK_YAKIT_ORANI = 0.5
DIKEY_HIZ_FT_DK = 1500.0

# Veritabanından SIGMET/kısıtlı saha çekerken rota kutusuna eklenen pay
# (derece): A*'ın yanal ızgarası büyük daireden ROTA_MAKS_YANAL_SAPMA_KM
# (varsayılan 400 km) kadar sapabilir.
_SIGMET_ARAMA_PAYI_DERECE = 5.0

_logger = logger_al(__name__)

CANLI_VERI_HAZIRLANIYOR = (
    "Canlı NOAA GFS verisi arka planda indiriliyor (sağlayıcı yavaş yanıt veriyor); bu ön sonuç onu beklemeden "
    "hesaplandı, birkaç saniye sonra yeniden hesaplayın."
)


def veri_kupune_eris(
    enlemler=None, boylamlar=None, zaman=None, irtifa_m=None, zamanlar=None, durum=None, canli_bekleme_saniye=None
):
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
    return veri_kupunu_sec(
        enlemler,
        boylamlar,
        zamanlar or [zaman] * len(enlemler),
        basinc_hpa,
        pay_derece=_a_yildiz_pay_derecesi(enlemler),
        durum=durum,
        canli_bekleme_saniye=canli_bekleme_saniye,
    )


_KM_PER_DERECE_ENLEM = 111.2


def _km_boylam_derecesine_cevir(km, enlemler):
    """km cinsinden bir yatay mesafeyi dereceye çevirir; 1° boylam =
    111.2*cos(enlem) km olduğu için (enlem arttıkça küçülür) enlemler
    dizisindeki EN KÖTÜ (en yüksek mutlak enlem, 75°'ye kadar kelepçeli)
    değer kullanılır -- rotanın herhangi bir noktasında en az `km` kadar
    kapsama garanti edilir (düz bir derece değeri kullanmak yüksek enlemde
    gerçek km'yi olduğundan dar gösterirdi, bkz. konuşma geçmişi)."""
    enlem = min(float(np.max(np.abs(enlemler))), 75.0)
    return km / (_KM_PER_DERECE_ENLEM * math.cos(math.radians(enlem)))


def _a_yildiz_pay_derecesi(enlemler):
    """A* ızgarası büyük daireden ROTA_MAKS_YANAL_SAPMA_KM kadar sapabilir;
    büyük küplerden okunan pencere bu koridoru da kapsasın (boylamda enleme
    göre genişletilmiş, +1° eşleştirme toleransı)."""
    return _km_boylam_derecesine_cevir(config.ROTA_MAKS_YANAL_SAPMA_KM, enlemler) + 1.0


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


@dataclass(frozen=True)
class _YanalIzgara:
    """A* aramasının yanal ızgarası. Düğüm (i, k): i. büyük daire noktasından
    rotaya dik yönde k x aralik_km kaydırılmış konum (k=0 büyük dairenin
    kendisi, uydurma bir "iyileşme" gösterilmesin diye her zaman aday).

    Sınırlar ADIM SAYISIYLA değil MESAFE ve AÇIYLA tanımlanır. Eskiden sabit
    20 km/adım vardı: 480 km'lik İstanbul-Antalya'da 12 km'lik bacakta 59°'lik
    (uçağın izlemeyeceği) sapmalar; 8000 km'lik İstanbul-New York'ta ise 200
    km'lik bacakta sadece 5.7°, kalkıştan 600 km sonra bile 60 km'lik gereksiz
    dar bir koridor (SIGMET'lerden kaçılabilecekken "öneri yok") çıkıyordu.
      - Her bacağın büyük daire yönüne göre açısı en fazla
        ROTA_MAKS_SAPMA_ACISI_DERECE: bir adımda en fazla
        adim_km x tan(açı) kadar yanal kayma (adim_basina_seviye seviye).
      - Izgara aralığı en fazla ROTA_YANAL_IZGARA_KM; kısa rotalarda bir
        adımda izin verilen kaymaya eşitlenir.
      - Toplam sapma en fazla ROTA_MAKS_YANAL_SAPMA_KM (maks_seviye).
    Başlangıç ve bitiş sabit olduğu için sapma uçlarda kendiliğinden kademeli
    sınırlanır: i. noktada en fazla min(i, n-1-i) x adim_basina_seviye."""

    nokta_sayisi: int
    aralik_km: float
    adim_basina_seviye: int
    maks_seviye: int

    def zarf(self, i: int) -> int:
        return min(min(i, self.nokta_sayisi - 1 - i) * self.adim_basina_seviye, self.maks_seviye)


def _yanal_izgara_olustur(enlemler_gc, boylamlar_gc) -> _YanalIzgara:
    n = len(enlemler_gc)
    adim_km = buyuk_daire_mesafesi_km(enlemler_gc[0], boylamlar_gc[0], enlemler_gc[-1], boylamlar_gc[-1]) / (n - 1)
    adim_basina_km = adim_km * math.tan(math.radians(config.ROTA_MAKS_SAPMA_ACISI_DERECE))
    aralik_km = min(config.ROTA_YANAL_IZGARA_KM, adim_basina_km)
    return _YanalIzgara(
        nokta_sayisi=n,
        aralik_km=aralik_km,
        adim_basina_seviye=max(1, int(adim_basina_km / aralik_km + 1e-9)),
        maks_seviye=int(config.ROTA_MAKS_YANAL_SAPMA_KM / aralik_km + 1e-9),
    )


def _yanal_izgara_dugum_konumlari(enlemler_gc, boylamlar_gc, izgara):
    """Izgaranın tüm düğümleri: {(i, k): (enlem, boylam)}. Uçlarda (i=0 ve
    i=n-1) sadece k=0 vardır, çünkü başlangıç/bitiş sabittir."""
    n = izgara.nokta_sayisi
    konumlar = {(0, 0): (enlemler_gc[0], boylamlar_gc[0])}
    for i in range(1, n - 1):
        yon = _ilk_yon_derece(enlemler_gc[i - 1], boylamlar_gc[i - 1], enlemler_gc[i + 1], boylamlar_gc[i + 1])
        dikey_yon = (yon + 90.0) % 360.0
        for k in range(-izgara.zarf(i), izgara.zarf(i) + 1):
            konumlar[(i, k)] = (
                (enlemler_gc[i], boylamlar_gc[i])
                if k == 0
                else _hedef_nokta(enlemler_gc[i], boylamlar_gc[i], dikey_yon, k * izgara.aralik_km)
            )
    konumlar[(n - 1, 0)] = (enlemler_gc[n - 1], boylamlar_gc[n - 1])
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

    izgara = _yanal_izgara_olustur(enlemler_gc, boylamlar_gc)
    konumlar = _yanal_izgara_dugum_konumlari(enlemler_gc, boylamlar_gc, izgara)

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
        dugumler = [d for d, disi in zip(dugumler, kapsam_disi, strict=True) if not disi]
    konum_kumesi = set(dugumler)
    kenarlar = [(d, k) for d in dugumler for k in _komsu_dugumler(d, izgara) if k in konum_kumesi]

    # Sert kısıtların geçerliliği için: A* rüzgarsız nominal zamanlarla arar,
    # oysa aday rotanın son kontrolü rüzgarlı zamanlarla yapılır. Aradaki
    # fark yüzünden A*'ın "güvenli" bulduğu rota son kontrolde SIGMET'e girip
    # gereksiz "öneri yok"a düşebiliyordu; bu yüzden her düğümün zamanı,
    # kalkıştan geçen sürenin ROTA_ZAMAN_BELIRSIZLIK_ORANI'sı + sabit pay kadar
    # belirsiz sayılır.
    belirsizlik = {
        d: (nominal_zamanlar[d[0]] - nominal_zamanlar[0]) * config.ROTA_ZAMAN_BELIRSIZLIK_ORANI
        + pd.Timedelta(minutes=config.ROTA_ZAMAN_BELIRSIZLIK_PAYI_DAKIKA)
        for d in dugumler
    }
    risk = degerlendirmeleri_birlestir(
        katman.degerlendir(
            {d: konumlar[d] for d in dugumler},
            {d: nominal_zamanlar[d[0]] for d in dugumler},
            kenarlar,
            irtifa_m,
            zaman_belirsizligi=belirsizlik,
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
        ruzgar_sozluk = dict(zip(dugumler, zip(u_tum.tolist(), v_tum.tolist(), strict=True), strict=True))
    else:
        ruzgar_sozluk = dict.fromkeys(dugumler, (0.0, 0.0))

    def _kenar_maliyeti_saniye(dugum_a, dugum_b):
        ea, ba = konumlar[dugum_a]
        eb, bb = konumlar[dugum_b]
        mesafe_km = buyuk_daire_mesafesi_km(ea, ba, eb, bb)
        yon = _ilk_yon_derece(ea, ba, eb, bb)
        u, v = ruzgar_sozluk[dugum_b]
        return (mesafe_km * 1000.0) / _yer_hizi_ms(tas_ms, u, v, yon) + risk.dugum_cezasi.get(dugum_b, 0.0)

    def _sezgisel_saniye(dugum):
        e, b = konumlar[dugum]
        kalan_km = buyuk_daire_mesafesi_km(e, b, enlemler_gc[-1], boylamlar_gc[-1])
        return (kalan_km * 1000.0) / (tas_ms * 1.8)

    baslangic_dugumu = (0, 0)
    hedef_dugumu = (n - 1, 0)
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
        for komsu in _komsu_dugumler(dugum, izgara):
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
    maks_sapma_km = max(abs(k) for _, k in yol) * izgara.aralik_km
    return yol_enlem, yol_boylam, maks_sapma_km


class AtsAgiKullanilamazHatasi(ValueError):
    """ATS modu istendi ama ağ yok ya da ToC/ToD ağa bağlanamıyor."""


class AntimeridyenHatasi(ValueError):
    """Rota 180° boylamını kesiyor (desteklenmez, bkz. SISTEM_KARTI)."""


def antimeridyeni_kesiyor_mu(boylamlar) -> bool:
    return bool(np.any(np.abs(np.diff(np.asarray(boylamlar, dtype=float))) > 180.0))


def _ats_ile_rota_ara(ag, bas, bit, irtifa_m, baslangic_zamani, tas_ms, veri_kupu, risk_katmanlari=()):
    """hava_yolu_agi grafında, ızgara aramasıyla AYNI maliyet (rüzgarlı süre +
    TI1 cezası) ve AYNI risk katmanlarıyla A*. Düğüm zamanı: ToC'den büyük daire
    uzaklığı / TAS (nominal); belirsizlik payı ızgarayla aynı. Hava küpünün
    kapsamadığı düğümler elenir. Dönüş: (enlemler, boylamlar, düğümler, yollar)
    ya da yol yoksa None."""
    kalkis = pd.Timestamp(baslangic_zamani)
    kalkis = kalkis.tz_localize("UTC") if kalkis.tzinfo is None else kalkis
    konumlar, komsular, kenarlar = hava_yolu_agi.arama_grafi(ag, bas, bit, irtifa_m / 0.3048, kalkis.tz_convert("UTC"))
    dugumler = list(konumlar)
    zamanlar = {
        d: kalkis + pd.Timedelta(seconds=buyuk_daire_mesafesi_km(*bas, *konumlar[d]) * 1000.0 / tas_ms)
        for d in dugumler
    }
    if veri_kupu is not None:
        disi = kapsam_disi_maskesi(
            veri_kupu,
            [konumlar[d][0] for d in dugumler],
            [konumlar[d][1] for d in dugumler],
            [zamanlar[d] for d in dugumler],
        )
        dugumler = [d for d, x in zip(dugumler, disi, strict=True) if not x]
    gecerli = set(dugumler)
    kenarlar = [(a, b) for a, b in kenarlar if a in gecerli and b in gecerli]
    belirsizlik = {
        d: (zamanlar[d] - kalkis) * config.ROTA_ZAMAN_BELIRSIZLIK_ORANI
        + pd.Timedelta(minutes=config.ROTA_ZAMAN_BELIRSIZLIK_PAYI_DAKIKA)
        for d in dugumler
    }
    risk = degerlendirmeleri_birlestir(
        katman.degerlendir(
            {d: konumlar[d] for d in dugumler},
            {d: zamanlar[d] for d in dugumler},
            kenarlar,
            irtifa_m,
            zaman_belirsizligi=belirsizlik,
        )
        for katman in risk_katmanlari
    )
    if veri_kupu is not None:
        u, v = ruzgar_bilesenlerini_toplu_al(
            veri_kupu,
            np.array([konumlar[d][0] for d in dugumler]),
            np.array([konumlar[d][1] for d in dugumler]),
            irtifa_metre_to_basinc_hpa(irtifa_m),
            [zamanlar[d] for d in dugumler],
        )
        ruzgar = dict(zip(dugumler, zip(u.tolist(), v.tolist(), strict=True), strict=True))
    else:
        ruzgar = dict.fromkeys(dugumler, (0.0, 0.0))

    def kenar_maliyeti(a, b):
        (ea, ba), (eb, bb) = konumlar[a], konumlar[b]
        yon = _ilk_yon_derece(ea, ba, eb, bb)
        u, v = ruzgar[b]
        yer_hizi = _yer_hizi_ms(tas_ms, u, v, yon)
        return buyuk_daire_mesafesi_km(ea, ba, eb, bb) * 1000.0 / yer_hizi + risk.dugum_cezasi.get(b, 0.0)

    def sezgisel(d):
        return buyuk_daire_mesafesi_km(*konumlar[d], *bit) * 1000.0 / (tas_ms * 1.8)

    yasak = set(konumlar) - gecerli | risk.yasak_dugumler
    sonuc = hava_yolu_agi.a_yildiz(
        komsular, hava_yolu_agi.BASLANGIC, hava_yolu_agi.BITIS, kenar_maliyeti, sezgisel, yasak, risk.yasak_kenarlar
    )
    if sonuc is None:
        return None
    yol_dugumleri, yol_adlari = sonuc
    return (
        np.array([konumlar[d][0] for d in yol_dugumleri]),
        np.array([konumlar[d][1] for d in yol_dugumleri]),
        yol_dugumleri,
        yol_adlari,
    )


def _komsu_dugumler(dugum, izgara):
    """Bir sonraki ara noktada ulaşılabilen ızgara düğümleri: seviye değişimi
    en fazla adim_basina_seviye (bkz. _YanalIzgara -- bacak açısı sınırı);
    yoksa A*, uçağın izlemeyeceği ani yanal sıçramalar içeren bir "kısayol"
    bulabiliyor (gerçek veriyle doğrulandı). Son noktaya sadece k=0'dan
    değil, açı sınırı içinde kalan her düğümden girilir."""
    i, seviye = dugum
    n = izgara.nokta_sayisi
    if i >= n - 1:
        return []
    if i + 1 == n - 1:
        return [(n - 1, 0)]
    sinir, adim = izgara.zarf(i + 1), izgara.adim_basina_seviye
    return [(i + 1, k) for k in range(max(seviye - adim, -sinir), min(seviye + adim, sinir) + 1)]


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


def _yer_hizi_ms(tas_ms, u, v, iz_derece):
    """Rüzgâr üçgeni: GS = √(TAS² − Xw²) + Hw. Hw izdeki bileşen (kuyruk +),
    Xw yan bileşen; u doğu, v kuzey. Alt sınır TAS'ın %20'si (bacak süresi şişmesin)."""
    iz = _bd(iz_derece)
    kuyruk = u * math.sin(iz) + v * math.cos(iz)
    yan = u * math.cos(iz) - v * math.sin(iz)
    return max(math.sqrt(max(tas_ms * tas_ms - yan * yan, 0.0)) + kuyruk, tas_ms * 0.2)


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
            yer_hizi_ms = _yer_hizi_ms(tas_ms, u, v, yon_derece)

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


NM_KM = 1.852


def _ucus_seviyesi(irtifa_m) -> int:
    return int(round(float(irtifa_m) / 0.3048 / 100.0))


def _riskli_maskesi(ti1):
    """Nokta başına True/False; TI1 hesaplanamayan (kapsam dışı) nokta None."""
    if ti1 is None:
        return None
    ti1 = np.asarray(ti1, dtype=float)
    with np.errstate(invalid="ignore"):
        return [None if np.isnan(t) else bool(t >= config.TI1_ESIK_ORTA_SIDDETLI) for t in ti1]


def _sonlu(deger):
    return None if deger is None or not np.isfinite(deger) else float(deger)


def _noktalari_paketle(enlemler, boylamlar, irtifa_m, zamanlar, ti1=None, birlesik_edr=None):
    riskli = _riskli_maskesi(ti1) or [None] * len(enlemler)
    ti1 = [None] * len(enlemler) if ti1 is None else ti1
    birlesik_edr = [None] * len(enlemler) if birlesik_edr is None else birlesik_edr
    fl = _ucus_seviyesi(irtifa_m)
    return [
        {
            "enlem": float(e),
            "boylam": float(b),
            "irtifa_m": float(irtifa_m),
            "fl": fl,
            "zaman": z.isoformat(),
            "ti1": _sonlu(t),
            "birlesik_edr": _sonlu(d),
            "riskli": r,
        }
        for e, b, z, t, d, r in zip(enlemler, boylamlar, zamanlar, ti1, birlesik_edr, riskli, strict=True)
    ]


def _nokta_hucre_uzunluklari_km(enlemler, boylamlar):
    """Her noktanın temsil ettiği rota uzunluğu: komşu bacakların yarıları."""
    bacak = np.array(
        [
            buyuk_daire_mesafesi_km(enlemler[i], boylamlar[i], enlemler[i + 1], boylamlar[i + 1])
            for i in range(len(enlemler) - 1)
        ]
    )
    hucre = np.zeros(len(enlemler))
    hucre[:-1] += bacak / 2
    hucre[1:] += bacak / 2
    return hucre


def _edr_siddeti(edr):
    if edr is None or not np.isfinite(edr):
        return None
    if edr >= config.EDR_ESIK_SIDDETLI:
        return "şiddetli"
    if edr >= config.EDR_ESIK_ORTA:
        return "orta"
    if edr >= config.EDR_ESIK_HAFIF:
        return "hafif"
    return "hafif altı"


def riskli_bolumler(aday) -> list[dict] | None:
    """Ardışık riskli noktalar tek bölüm: başlangıç/bitiş UTC, FL, NM, dakika,
    en yüksek TI1 ve birleşik EDR. RISKLI_BOLUM_MIN_NM'den kısa bölümler
    atılır (varsayılan 0: kalibre edilmedi, mevcut davranış). Risk hesaplanmadıysa None."""
    maske = _riskli_maskesi(aday.get("ti1"))
    if maske is None or all(m is None for m in maske):
        return None
    hucre_km = _nokta_hucre_uzunluklari_km(aday["enlem"], aday["boylam"])
    zamanlar = list(aday["zamanlar"])
    ti1 = np.asarray(aday["ti1"], dtype=float)
    birlesik = np.asarray(
        aday.get("birlesik_edr") if aday.get("birlesik_edr") is not None else np.full(len(ti1), np.nan)
    )
    bolumler, i = [], 0
    while i < len(maske):
        if not maske[i]:
            i += 1
            continue
        j = i
        while j + 1 < len(maske) and maske[j + 1]:
            j += 1
        uzunluk_nm = float(hucre_km[i : j + 1].sum()) / NM_KM
        if uzunluk_nm >= config.RISKLI_BOLUM_MIN_NM:
            baslangic = zamanlar[max(i - 1, 0)] + (zamanlar[i] - zamanlar[max(i - 1, 0)]) / 2
            bitis = zamanlar[j] + (zamanlar[min(j + 1, len(zamanlar) - 1)] - zamanlar[j]) / 2
            maks_edr = float(np.nanmax(birlesik[i : j + 1])) if np.isfinite(birlesik[i : j + 1]).any() else None
            bolumler.append(
                {
                    "baslangic_utc": pd.Timestamp(baslangic).isoformat(),
                    "bitis_utc": pd.Timestamp(bitis).isoformat(),
                    "fl": _ucus_seviyesi(aday["irtifa_m"]),
                    "uzunluk_nm": uzunluk_nm,
                    "sure_dk": (pd.Timestamp(bitis) - pd.Timestamp(baslangic)).total_seconds() / 60.0,
                    "baslangic_enlem": float(aday["enlem"][i]),
                    "baslangic_boylam": float(aday["boylam"][i]),
                    "bitis_enlem": float(aday["enlem"][j]),
                    "bitis_boylam": float(aday["boylam"][j]),
                    "maks_ti1": float(np.nanmax(ti1[i : j + 1])),
                    "maks_birlesik_edr": maks_edr,
                    "beklenen_siddet": _edr_siddeti(maks_edr),
                }
            )
        i = j + 1
    return bolumler


def kabin_onerisi(bolumler) -> dict | None:
    """Yalnızca önerilen rotada kalan risk varsa: ilk bölüm için dispeçer/kabin
    dilinde öneri. Karar kaptanındır; sertifikalı EDR değildir."""
    if not bolumler:
        return None
    ilk = bolumler[0]
    toplam_dk = sum(b["sure_dk"] for b in bolumler)
    baslangic = pd.Timestamp(ilk["baslangic_utc"])
    metin = (
        f"Öneri (karar kaptanındır): ~{baslangic:%H:%M}Z'den itibaren ~{ilk['sure_dk']:.0f} dk, "
        f"FL{ilk['fl']:03d}'te olası türbülans. Kabin servisini bu saatten önce durdurun, emniyet kemeri "
        "işaretini açın."
    )
    if len(bolumler) > 1:
        metin += f" Rotada toplam {len(bolumler)} bölüm, ~{toplam_dk:.0f} dk."
    return {
        "metin": metin,
        "servis_durdur": True,
        "ilk_bolum_baslangic_utc": ilk["baslangic_utc"],
        "bolum_sayisi": len(bolumler),
        "toplam_sure_dk": toplam_dk,
    }


def _irtifa_degisimi_maliyeti(eski_irtifa_m, yeni_irtifa_m, yakit_akisi_kg_saat):
    """Geçici seviyeye gidiş + planlanan seviyeye dönüşün seyre göre ek
    maliyeti: (ekstra_saniye, ekstra_yakit_kg). Bir tırmanma ve bir alçalma
    içerdiği için yön fark etmez (bkz. modül başındaki not)."""
    fark_ft = abs(yeni_irtifa_m - eski_irtifa_m) / 0.3048
    if fark_ft == 0:
        return 0.0, 0.0
    tek_yon_saat = fark_ft / DIKEY_HIZ_FT_DK / 60.0
    ekstra_yakit_kg = yakit_akisi_kg_saat * tek_yon_saat * TIRMANMA_EK_YAKIT_ORANI
    return 0.0, ekstra_yakit_kg


def _komsu_yasal_seviyeler(seviye, veri_kupu, enlemler, boylamlar, zaman_iso):
    """Aynı yönün bir üst/alt yasal FL'si (irtifa, m); veri küpünün dikeyde
    kapsamadığı seviye aday yapılmaz (TI1 hesaplanamaz, 'risk yok' sanılmasın)."""
    sonuc = {}
    for strateji, fl in (("irtifa_yukari", seviye["yukari_fl"]), ("irtifa_asagi", seviye["asagi_fl"])):
        if fl is not None and _era5_tamamen_kapsiyor_mu(
            veri_kupu, enlemler, boylamlar, zaman_iso, ucus_seviyeleri.fl_metre(fl)
        ):
            sonuc[strateji] = ucus_seviyeleri.fl_metre(fl)
    return sonuc


# ---------------------------------------------------------------------------
# Üst düzey giriş noktası
# ---------------------------------------------------------------------------


def _rota_zaman_araligi(enlemler_gc, boylamlar_gc, zaman_iso, tas_ms):
    """Kısıt sorgusu için muhafazakâr uçuş penceresi: kalkış -> TAS'ın %60'ıyla
    varış + 1 saat (rüzgarlı ve sapmalı rotanın varışı da kapsansın)."""
    baslangic = pd.Timestamp(zaman_iso)
    baslangic = baslangic.tz_localize("UTC") if baslangic.tzinfo is None else baslangic.tz_convert("UTC")
    toplam_km = sum(
        buyuk_daire_mesafesi_km(enlemler_gc[i], boylamlar_gc[i], enlemler_gc[i + 1], boylamlar_gc[i + 1])
        for i in range(len(enlemler_gc) - 1)
    )
    bitis = (baslangic + pd.Timedelta(seconds=toplam_km * 1000.0 / (tas_ms * 0.6)) + pd.Timedelta(hours=1)).ceil("s")
    return baslangic, bitis


def _arama_kutusu(enlemler_gc, boylamlar_gc):
    return (
        float(np.min(enlemler_gc)) - _SIGMET_ARAMA_PAYI_DERECE,
        float(np.max(enlemler_gc)) + _SIGMET_ARAMA_PAYI_DERECE,
        float(np.min(boylamlar_gc)) - _SIGMET_ARAMA_PAYI_DERECE,
        float(np.max(boylamlar_gc)) + _SIGMET_ARAMA_PAYI_DERECE,
    )


def _sigmet_katmanini_hazirla(sigmetler, enlemler_gc, boylamlar_gc, zaman_iso, tas_ms):
    """Rota bölgesi/zamanı için aktif SIGMET'leri (verilmediyse veritabanından)
    yükleyip sert kısıt katmanını kurar. Dönüş: (katman ya da None, özet)."""
    baslangic, bitis = _rota_zaman_araligi(enlemler_gc, boylamlar_gc, zaman_iso, tas_ms)
    ozet = {
        "durum": "aktif_sigmet_yok",
        "aktif_sigmet_sayisi": 0,
        "son_guncelleme": None,
        "bayat_mi": False,
        "sorunlu_kaynaklar": [],
    }

    if sigmetler is None:
        try:
            sigmetler = gecerli_sigmetleri_getir(
                baslangic.to_pydatetime(),
                bitis.to_pydatetime(),
                *_arama_kutusu(enlemler_gc, boylamlar_gc),
                tehlikeler=kacinilacak_tehlikeler(),
            )
            ozet["son_guncelleme"] = son_guncelleme_zamani()
            ozet["sorunlu_kaynaklar"] = sorunlu_kaynaklar()
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
            "hareket_yonu_derece": sg.get("hareket_yonu_derece"),
            "hareket_hizi_kt": sg.get("hareket_hizi_kt"),
        }
        for sg in katman.sigmetler
    ]
    ozet["aktif_sigmet_sayisi"] = len(katman.sigmetler)
    ozet.update(sigmet_ufku(baslangic, bitis))
    if not katman.sigmetler:
        return None, ozet
    return katman, {**ozet, "durum": "uygulandi"}


def sigmet_ufku(baslangic, bitis, simdi=None) -> dict:
    """Uçuş penceresinin SIGMET yayın ufkunun (şimdi + SIGMET_YAYIN_UFKU_SAAT)
    ötesine düşen kısmı: 'yok' | 'kismi' | 'tam'. O kısım için 'aktif SIGMET
    yok' sonucu güvence değildir; henüz yayımlanmamış olabilir."""
    simdi = pd.Timestamp.now(tz="UTC") if simdi is None else pd.Timestamp(simdi)
    ufuk = simdi + pd.Timedelta(hours=config.SIGMET_YAYIN_UFKU_SAAT)
    baslangic, bitis = pd.Timestamp(baslangic), pd.Timestamp(bitis)
    kisim = "tam" if baslangic > ufuk else "kismi" if bitis > ufuk else "yok"
    return {"yayin_ufku_disi": kisim, "yayin_ufku_saat": config.SIGMET_YAYIN_UFKU_SAAT}


def planlama_ufku(zaman_iso, simdi=None) -> dict:
    """Uçuşun şimdiye göre konumu ve kullanılabilecek veri: geçmiş tarihli
    uçuş (analiz/backtest) ya da uçuş öncesi planlama (kalkışa kalan saat)."""
    simdi = pd.Timestamp.now(tz="UTC") if simdi is None else pd.Timestamp(simdi)
    kalkis = pd.Timestamp(zaman_iso)
    kalkis = kalkis.tz_localize("UTC") if kalkis.tzinfo is None else kalkis.tz_convert("UTC")
    kalan_saat = (kalkis - simdi).total_seconds() / 3600.0
    return {
        "kullanim": "gecmis_analiz" if kalan_saat < 0 else "ucus_oncesi_planlama",
        "kalkisa_kalan_saat": round(kalan_saat, 2),
        "tahmin_ufku_saat": config.CANLI_TAHMIN_UFKU_SAAT,
        "sigmet_yayin_ufku_saat": config.SIGMET_YAYIN_UFKU_SAAT,
        "tahmin_ufku_disi": kalan_saat > config.CANLI_TAHMIN_UFKU_SAAT,
    }


_KAPSAM_ORTAK = (
    "Rota yalnızca seyir (en-route) safhası içindir: başlangıç ve bitiş seyre giriş (ToC) ve seyirden "
    "çıkış (ToD) noktası, irtifa seyir irtifası kabul edilir. Kalkış, tırmanış, alçalış, SID/STAR ve "
    "yaklaşma kapsam dışıdır. "
)


def kapsam(arama_uzayi="koridor", ats_kaynagi=None) -> dict:
    if arama_uzayi == "ats":
        arama = f"Rota, yüklü ATS yolu/FRA ağı ({ats_kaynagi}) üzerinde aranır; ToC/ToD ağa doğrudan (DCT) bağlanır. "
    else:
        arama = "Rota, ATS yolları yerine büyük daire etrafındaki bir koridorda aranır. "
    return {
        "safha": "seyir",
        "arama_uzayi": arama_uzayi,
        "aciklama": _KAPSAM_ORTAK + arama + "Diğer trafikle ayırma dikkate alınmaz; ATC talimatlarının yerini tutmaz.",
    }


KAPSAM = kapsam()


_SAHA_OZET_ALANLARI = (
    "id",
    "dis_kimlik",
    "ad",
    "tur",
    "kaynak",
    "taban_ft",
    "tavan_ft",
    "gecerlilik_baslangic",
    "gecerlilik_bitis",
    "poligon",
    "aktivasyon",
)


def _cizim_kayitlari(saha):
    """Yanıt/CZML için saha özeti; koridoru çıkarılmış sahada (bkz.
    _kisitli_saha_katmanini_hazirla) her parçanın dış halkası ayrı çizilir."""
    ozet = {alan: saha.get(alan) for alan in _SAHA_OZET_ALANLARI}
    geometri = saha.get("_geometri")
    if geometri is None:
        return [ozet]
    parcalar = [g for g in shapely.get_parts(geometri) if g.geom_type == "Polygon" and not g.is_empty]
    return [
        {**ozet, "ad": f"{saha['ad']} (planlı rota koridoru hariç)", "poligon": [list(k) for k in p.exterior.coords]}
        for p in parcalar
    ]


def _kisitli_saha_katmanini_hazirla(kisitli_sahalar, enlemler_gc, boylamlar_gc, zaman_iso, tas_ms):
    """Kısıtlı hava sahalarını (verilmediyse veritabanından) yükleyip sert kısıt
    katmanını kurar. Kalkış ya da varış noktasını İÇEREN sahada (örn. varış
    ülkesi) uçuşun planlı rotasına yetkili olduğu varsayılır: sadece büyük
    dairenin ±KISITLI_SAHA_UC_KORIDORU_KM çevresi serbest bırakılır, sahanın
    geri kalanı kısıt olarak kalır (eskiden sahanın TAMAMI muaftı, A* varış
    ülkesinde istediği yere sapabiliyordu). Bu sahalar özette
    'muaf_tutulanlar' olarak raporlanır. Dönüş: (katman ya da None, özet)."""
    ozet = {"durum": "kisitli_saha_yok", "uygulanan_saha_sayisi": 0, "muaf_tutulanlar": [], "ornek_veri_mi": False}
    if kisitli_sahalar is None:
        baslangic, bitis = _rota_zaman_araligi(enlemler_gc, boylamlar_gc, zaman_iso, tas_ms)
        try:
            kisitli_sahalar = gecerli_kisitli_sahalari_getir(
                baslangic.to_pydatetime(), bitis.to_pydatetime(), *_arama_kutusu(enlemler_gc, boylamlar_gc)
            )
        except Exception as hata:
            _logger.warning("Kısıtlı sahalar okunamadı, rota bu kontrol olmadan hesaplanıyor: %s", hata)
            return None, {**ozet, "durum": "erisilemedi", "sahalar": []}

    tum = KisitliSahaKatmani(kisitli_sahalar)
    muaf = {
        id(saha)
        for enlem, boylam in ((enlemler_gc[0], boylamlar_gc[0]), (enlemler_gc[-1], boylamlar_gc[-1]))
        for saha in tum.noktayi_iceren_kayitlar(enlem, boylam)
    }
    # Düz bir derece tamponu yüksek enlemde gerçek km'yi olduğundan dar
    # gösterirdi (60°K'de "100 km" tamponu doğu-batı yönünde gerçekte sadece
    # ~50 km'ye karşılık gelir, cos(enlem) küçüldüğü için) -- bu yüzden
    # _km_boylam_derecesine_cevir ile rotanın en yüksek enlemine göre
    # (muhafazakâr) ölçeklenir.
    koridor = shapely.buffer(
        shapely.linestrings(np.column_stack([boylamlar_gc, enlemler_gc])),
        _km_boylam_derecesine_cevir(config.KISITLI_SAHA_UC_KORIDORU_KM, enlemler_gc),
    )
    uygulanacak = []
    for saha in tum.kayitlar:
        if id(saha) not in muaf:
            uygulanacak.append(saha)
            continue
        kalan = shapely.difference(tum.geometri(saha), koridor)
        if not shapely.is_empty(kalan):
            uygulanacak.append({**saha, "_geometri": kalan})
    katman = KisitliSahaKatmani(uygulanacak)
    ozet["muaf_tutulanlar"] = [s["ad"] for s in tum.kayitlar if id(s) in muaf]
    ozet["sahalar"] = [ciz for s in katman.kayitlar for ciz in _cizim_kayitlari(s)]
    ozet["uygulanan_saha_sayisi"] = len(katman.kayitlar)
    ozet["ornek_veri_mi"] = any(s.get("kaynak") == ORNEK_KAYNAK for s in tum.kayitlar)
    if not katman.kayitlar:
        return None, ozet
    return katman, {**ozet, "durum": "uygulandi"}


def _temel_strateji(strateji: str) -> str:
    """Pareto adayları ("yanal_ceza_60", "ats_ceza_0") temel stratejiye indirgenir."""
    if "_ceza_" not in strateji:
        return strateji
    return "yanal" if strateji.startswith("yanal") else "ats_alternatif"


def rota_simulasyonu_olustur(
    baslangic_enlem,
    baslangic_boylam,
    bitis_enlem,
    bitis_boylam,
    irtifa_ft,
    zaman_iso,
    ucak_modeli_kodu,
    sigmetler=None,
    kisitli_sahalar=None,
    canli_bekleme_saniye=None,
    arama_uzayi="koridor",
    ats_agi=None,
):
    """
    arama_uzayi: "koridor" (büyük daire etrafında yanal ızgara) ya da "ats"
    (ATS yolu/FRA ağı, bkz. hava_yolu_agi.py; ats_agi verilmezse
    config.ATS_AGI_DOSYASI). ATS modunda normal rota ağdaki en hızlı yol,
    optimize rota aynı risk katmanlarıyla ağda aranan yoldur.
    İki gerçek rota üretir: büyük daire ("normal") ve "optimize" rota.
    Öncelik sırası: (1) aktif SIGMET'lere ve kısıtlı hava sahalarına GİRMEMEK
    (sert kısıtlar, bkz. risk_katmanlari.SigmetKisitKatmani/KisitliSahaKatmani),
    (2) riskli TI1 türbülansından kaçınmak, (3) en ucuz (yakıt/süre) yol. Sert
    kısıtları sağlayan hiçbir aday bulunamazsa rota ÖNERİLMEZ
    (guvenli_rota_bulundu_mu=False).
    sigmetler / kisitli_sahalar: None ise veritabanındaki aktif kayıtlar
    (sigmet_saglayici.py / kisitli_saha_saglayici.py) kullanılır;
    test/backtest için açıkça bir liste verilebilir.
    canli_bekleme_saniye: etkileşimli çağrıda canlı hava verisi için azami
    bekleme (bkz. veri_saglayicilari.veri_kupunu_sec); None ise indirme beklenir.
    Dönüş, api_servisi.py'nin doğrudan JSON'a çevirebileceği bir dict'tir.
    """
    if ucak_modeli_kodu not in UCAK_PROFILLERI:
        raise ValueError(f"Bilinmeyen uçak modeli: '{ucak_modeli_kodu}'. Geçerli seçenekler: {list(UCAK_PROFILLERI)}")

    profil = UCAK_PROFILLERI[ucak_modeli_kodu]
    tas_ms = profil["tas_ms"]
    seviye = ucus_seviyeleri.seviye_plani(
        irtifa_ft,
        ucus_seviyeleri.manyetik_iz(_ilk_yon_derece(baslangic_enlem, baslangic_boylam, bitis_enlem, bitis_boylam)),
        profil["azami_fl"],
    )
    irtifa_m = ucus_seviyeleri.fl_metre(seviye["fl"])
    enlemler_gc, boylamlar_gc = buyuk_daire_rotasi_olustur(
        baslangic_enlem, baslangic_boylam, bitis_enlem, bitis_boylam, config.ROTA_SIMULASYONU_NOKTA_SAYISI
    )
    if antimeridyeni_kesiyor_mu(boylamlar_gc):
        raise AntimeridyenHatasi(
            "Büyük daire rotası 180° boylamını kesiyor (ör. Pasifik geçişi); bu rotalar desteklenmez. "
            "Kısıt ve risk geometrisi -180..180 düzleminde hesaplandığı için sonuç güvence sayılamazdı."
        )

    veri_durumu = {}
    veri_kupu = veri_kupune_eris(
        enlemler_gc,
        boylamlar_gc,
        zaman_iso,
        irtifa_m,
        zamanlar=_tahmini_varis_zamanlari(enlemler_gc, boylamlar_gc, zaman_iso, tas_ms),
        durum=veri_durumu,
        canli_bekleme_saniye=canli_bekleme_saniye,
    )
    ruzgarli_mi = _era5_tamamen_kapsiyor_mu(veri_kupu, enlemler_gc, boylamlar_gc, zaman_iso, irtifa_m)
    kup_adi = veri_kupu_adi(veri_kupu)
    sigmet_katmani, sigmet_kontrolu = _sigmet_katmanini_hazirla(sigmetler, enlemler_gc, boylamlar_gc, zaman_iso, tas_ms)
    saha_katmani, kisitli_saha_kontrolu = _kisitli_saha_katmanini_hazirla(
        kisitli_sahalar, enlemler_gc, boylamlar_gc, zaman_iso, tas_ms
    )

    def _aday(strateji, enlemler, boylamlar, aday_irtifa_m, yanal_sapma_km=0.0, ekstra=(0.0, 0.0)):
        saniye, zamanlar = _rotayi_zamanla(
            enlemler, boylamlar, aday_irtifa_m, zaman_iso, tas_ms, veri_kupu, ruzgarli_mi
        )
        if ruzgarli_mi:
            eslesme = rota_eslesmesi(enlemler, boylamlar, aday_irtifa_m, zamanlar, veri_kupu)
            ti1 = eslesme["ti1_indeksi"].to_numpy(dtype=float)
            birlesik = (
                eslesme["birlesik_edr"].to_numpy(dtype=float)
                if "birlesik_edr" in eslesme
                else np.full(len(ti1), np.nan)
            )
            maks_ti1, riskli_sayisi = _ti1_ozeti_cikar(ti1)
            iz_bulutu_sayisi = duyarli_nokta_sayisi(eslesme["iz_bulutu_duyarli"])
        else:
            ti1 = birlesik = None
            maks_ti1, riskli_sayisi, iz_bulutu_sayisi = None, 0, None
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
            "ti1": ti1,
            "birlesik_edr": birlesik,
            "iz_bulutu_sayisi": iz_bulutu_sayisi,
            "sigmet_ihlali": (
                sigmet_katmani.rota_ihlal_sayisi(enlemler, boylamlar, zamanlar, aday_irtifa_m) if sigmet_katmani else 0
            ),
            "kisitli_saha_ihlali": (
                saha_katmani.rota_ihlal_sayisi(enlemler, boylamlar, zamanlar, aday_irtifa_m) if saha_katmani else 0
            ),
            "yanal_sapma_km": yanal_sapma_km,
        }

    def _aday_toplam_yakit_kg(aday):
        return profil["yakit_akisi_kg_saat"] * (aday["saniye"] / 3600.0) + aday["ekstra_yakit_kg"]

    ats_yollari = {}
    if arama_uzayi == "ats":
        ag = ats_agi or hava_yolu_agi.agi_yukle()
        if ag is None:
            raise AtsAgiKullanilamazHatasi(
                f"ATS ağı yüklü değil ({config.ATS_AGI_DOSYASI}); bkz. docs/veri_hazirlama/ATS_AGI_HAZIRLAMA.md."
            )
        uclar = ((baslangic_enlem, baslangic_boylam), (bitis_enlem, bitis_boylam))

        def _ats_yolu(aday_irtifa_m, katmanlar):
            return _ats_ile_rota_ara(
                ag, *uclar, aday_irtifa_m, zaman_iso, tas_ms, veri_kupu if ruzgarli_mi else None, katmanlar
            )

        planli = _ats_yolu(irtifa_m, [])
        kalkis_utc = pd.Timestamp(zaman_iso)
        kalkis_utc = kalkis_utc.tz_localize("UTC") if kalkis_utc.tzinfo is None else kalkis_utc.tz_convert("UTC")
        if planli is None and not ag.fra_acik_mi(kalkis_utc):
            raise AtsAgiKullanilamazHatasi(
                f"Serbest Rota Sahası (FRA) {kalkis_utc:%H:%M} UTC'de uygulanmıyor (yalnızca "
                f"{ag.fra_saatleri_metni()}, AIP ENR 1.3); bu saatte ATS yolları (ENR 3.1) gerekir ve ağda yok. "
                "Koridor modunu kullanın ya da FRA saatinde planlayın."
            )
        if planli is None:
            raise AtsAgiKullanilamazHatasi(
                f"ToC/ToD ATS ağına bağlanamadı (en yakın nokta {config.ATS_AGI_BAGLANTI_KM:.0f} km'den uzak) ya da "
                f"FL{seviye['fl']}'de bu iki nokta arasında ATS rotası yok."
            )
        ats_yollari["yok"] = planli
        normal = _aday("yok", planli[0], planli[1], irtifa_m)
    elif arama_uzayi == "koridor":
        ag = None
        normal = _aday("yok", enlemler_gc, boylamlar_gc, irtifa_m)
    else:
        raise ValueError(f"Bilinmeyen arama_uzayi: {arama_uzayi!r} (koridor | ats)")
    guvenli_rota_bulundu_mu = True

    if normal["riskli_sayisi"] == 0 and normal["sigmet_ihlali"] == 0 and normal["kisitli_saha_ihlali"] == 0:
        # Kaçınılacak risk YOK -- kullanıcıyla netleştirilen ilkeyle, uydurma
        # bir sapma göstermek yerine optimize rota normal rotayla BİREBİR AYNI.
        en_iyi = normal
    else:
        # ÇOK FAKTÖRLÜ karşılaştırma: (1) YANAL -- A* ile büyük daire
        # etrafındaki ızgarada, risk katmanlarına (TI1 cezası + SIGMET yasağı)
        # göre en ucuz yol; (2/3) İRTİFA -- aynı yatay rotada aynı yönün bir üst/alt
        # yasal FL (gerçek tırmanma/alçalma bedeliyle, bkz.
        # _irtifa_degisimi_maliyeti). Bazı CAT katmanları ve SIGMET'ler
        # irtifaya bağlıdır; seviye değiştirmek bazen en ucuz güvenli seçenektir.
        sert_katmanlar = [k for k in (sigmet_katmani, saha_katmani) if k is not None]
        risk_katmanlari = ([Ti1CezaKatmani(veri_kupu)] if ruzgarli_mi else []) + sert_katmanlar
        pareto_cezalari = config.ROTA_PARETO_CEZALARI_SANIYE if ruzgarli_mi else []
        adaylar = []
        irtifa_secenekleri = (
            _komsu_yasal_seviyeler(seviye, veri_kupu, enlemler_gc, boylamlar_gc, zaman_iso) if ruzgarli_mi else {}
        )
        if ag is None:
            for strateji_adi, katmanlar in [
                ("yanal", risk_katmanlari),
                *(
                    (f"yanal_ceza_{c:g}", [Ti1CezaKatmani(veri_kupu, ceza_saniye=c), *sert_katmanlar])
                    for c in pareto_cezalari
                ),
            ]:
                yanal = _a_yildiz_ile_rota_ara(
                    enlemler_gc,
                    boylamlar_gc,
                    irtifa_m,
                    zaman_iso,
                    tas_ms,
                    veri_kupu if ruzgarli_mi else None,
                    katmanlar,
                )
                if yanal is not None:
                    adaylar.append(_aday(strateji_adi, yanal[0], yanal[1], irtifa_m, yanal_sapma_km=yanal[2]))
            for strateji_adi, yeni_irtifa_m in irtifa_secenekleri.items():
                ekstra = _irtifa_degisimi_maliyeti(irtifa_m, yeni_irtifa_m, profil["yakit_akisi_kg_saat"])
                adaylar.append(_aday(strateji_adi, enlemler_gc, boylamlar_gc, yeni_irtifa_m, ekstra=ekstra))
        else:
            for strateji_adi, aday_irtifa_m in {"ats_alternatif": irtifa_m, **irtifa_secenekleri}.items():
                yol = _ats_yolu(aday_irtifa_m, risk_katmanlari)
                if yol is None:
                    continue
                ats_yollari[strateji_adi] = yol
                ekstra = _irtifa_degisimi_maliyeti(irtifa_m, aday_irtifa_m, profil["yakit_akisi_kg_saat"])
                adaylar.append(_aday(strateji_adi, yol[0], yol[1], aday_irtifa_m, ekstra=ekstra))
            for ceza in pareto_cezalari:
                strateji_adi = f"ats_ceza_{ceza:g}"
                yol = _ats_yolu(irtifa_m, [Ti1CezaKatmani(veri_kupu, ceza_saniye=ceza), *sert_katmanlar])
                if yol is not None:
                    ats_yollari[strateji_adi] = yol
                    adaylar.append(_aday(strateji_adi, yol[0], yol[1], irtifa_m))

        sert_kisita_uyan = [a for a in adaylar if a["sigmet_ihlali"] == 0 and a["kisitli_saha_ihlali"] == 0]
        tam_guvenli = [a for a in sert_kisita_uyan if a["riskli_sayisi"] == 0]
        if tam_guvenli or sert_kisita_uyan:
            en_iyi = min(tam_guvenli or sert_kisita_uyan, key=lambda a: (a["riskli_sayisi"], _aday_toplam_yakit_kg(a)))
        else:
            # SERT kısıt sağlanamadı: kısıtı ihlal eden bir rota "optimize"
            # diye önerilmez -- normal rota gösterilir ve açıkça işaretlenir.
            en_iyi, guvenli_rota_bulundu_mu = normal, False

    normal_yakit_kg = _aday_toplam_yakit_kg(normal)
    # Yakıt = seyir süresi x yakıt akışı + seviye geçişlerinin ek yakıtı (bkz. _irtifa_degisimi_maliyeti).
    optimize_yakit_kg = _aday_toplam_yakit_kg(en_iyi)
    optimize_saniye = en_iyi["saniye"] + en_iyi["ekstra_saniye"]
    secenekler = pareto_secenekleri(
        [normal, *(adaylar if en_iyi is not normal else [])], en_iyi, normal, _aday_toplam_yakit_kg
    )
    bulgular = _bulgulari_olustur(
        ruzgarli_mi,
        veri_kupu,
        kup_adi,
        normal,
        en_iyi,
        irtifa_m,
        sigmet_kontrolu,
        guvenli_rota_bulundu_mu,
        kisitli_saha_kontrolu,
        veri_durumu.get("canli_hata") or (CANLI_VERI_HAZIRLANIYOR if veri_durumu.get("canli_hazirlaniyor") else None),
        seviye,
    )

    return {
        "ruzgar_verisi_kaynagi": (
            ("gfs_tahmin" if veri_kupu_kaynagi(veri_kupu) == "gfs" else "era5_gercek")
            if ruzgarli_mi
            else (
                "canli_veri_hazirlaniyor"
                if veri_durumu.get("canli_hazirlaniyor")
                else "canli_veri_alinamadi"
                if veri_durumu.get("canli_hata")
                else "era5_kapsam_disi"
            )
        ),
        "aciklama": " ".join(b["metin"] for b in bulgular),
        "bulgular": [{k: b[k] for k in ("kod", "seviye", "parametreler")} for b in bulgular],
        "ucak_modeli": ucak_modeli_kodu,
        "ucak_etiketi": profil["etiket"],
        "seviye_plani": seviye,
        "turbulanstan_kacinildi_mi": en_iyi["riskli_sayisi"] < normal["riskli_sayisi"],
        "sigmetten_kacinildi_mi": normal["sigmet_ihlali"] > 0 and en_iyi["sigmet_ihlali"] == 0,
        "kisitli_sahadan_kacinildi_mi": normal["kisitli_saha_ihlali"] > 0 and en_iyi["kisitli_saha_ihlali"] == 0,
        "guvenli_rota_bulundu_mu": guvenli_rota_bulundu_mu,
        "kacinma_stratejisi": _temel_strateji(en_iyi["strateji"]),
        "sigmet_kontrolu": sigmet_kontrolu,
        "kisitli_saha_kontrolu": kisitli_saha_kontrolu,
        "normal_rota": {
            **_rota_ozeti(normal, normal_yakit_kg, normal["saniye"]),
            "ortalama_ruzgar_bileseni_kt": _ortalama_ruzgar_bileseni_kt(normal, tas_ms),
        },
        "optimize_rota": (
            optimize_ozeti := {
                **_rota_ozeti(en_iyi, optimize_yakit_kg, optimize_saniye),
                "maks_yanal_sapma_km": en_iyi["yanal_sapma_km"],
                "ortalama_ruzgar_bileseni_kt": _ortalama_ruzgar_bileseni_kt(en_iyi, tas_ms),
            }
        ),
        "kabin_onerisi": kabin_onerisi(optimize_ozeti["riskli_bolumler"]),
        "sure_tasarrufu_dk": (normal["saniye"] - optimize_saniye) / 60.0,
        "yakit_tasarrufu_yuzde": (
            100.0 * (normal_yakit_kg - optimize_yakit_kg) / normal_yakit_kg if normal_yakit_kg > 0 else 0.0
        ),
        "co2_farki_kg": normal_yakit_kg * CO2_KG_PER_KG_YAKIT - optimize_yakit_kg * CO2_KG_PER_KG_YAKIT,
        "ti1_guvenilirlik_notu": TI1_GUVENILIRLIK_NOTU,
        "secenekler": secenekler,
        "kapsam": kapsam(arama_uzayi, ag.kaynak if ag is not None else None),
        "planlama_ufku": planlama_ufku(zaman_iso),
        "ats": (
            None
            if ag is None
            else {
                "kaynak": ag.kaynak,
                "normal_rota": hava_yolu_agi.rota_ozeti(*ats_yollari["yok"][2:]),
                "optimize_rota": hava_yolu_agi.rota_ozeti(*ats_yollari.get(en_iyi["strateji"], ats_yollari["yok"])[2:]),
                "buyuk_daire_km": sum(
                    buyuk_daire_mesafesi_km(enlemler_gc[i], boylamlar_gc[i], enlemler_gc[i + 1], boylamlar_gc[i + 1])
                    for i in range(len(enlemler_gc) - 1)
                ),
            }
        ),
    }


def pareto_secenekleri(adaylar, onerilen, normal, yakit_fonksiyonu) -> list[dict]:
    """Sert kısıtlara (SIGMET, kısıtlı saha) uyan adaylardan, (toplam süre,
    yakıt, riskli nokta) üçlüsünde başka bir aday tarafından baskılanmayanlar;
    aynı rotayı (aynı süre, yakıt ve risk) bir kez listeler. Riskli nokta
    sayısına göre sıralı. Seçenekler karar desteğidir: hangi bedelin kabul
    edileceğine dispeçer karar verir; risk sayısı TI1 eşiğine dayanır,
    sertifikalı EDR değildir."""
    uygun = [a for a in adaylar if a["sigmet_ihlali"] == 0 and a["kisitli_saha_ihlali"] == 0]

    def _olcut(a):
        return (round(a["saniye"] + a["ekstra_saniye"], 1), round(yakit_fonksiyonu(a), 1), int(a["riskli_sayisi"]))

    olcutler = {id(a): _olcut(a) for a in uygun}
    tekil, gorulen = [], set()
    for a in sorted(uygun, key=lambda a: (a is not onerilen, olcutler[id(a)])):
        if olcutler[id(a)] not in gorulen:
            gorulen.add(olcutler[id(a)])
            tekil.append(a)

    def _baskilanir(a, b):
        oa, ob = olcutler[id(a)], olcutler[id(b)]
        return all(y <= x for x, y in zip(oa, ob, strict=True)) and ob != oa

    cephe = [a for a in tekil if not any(_baskilanir(a, b) for b in tekil if b is not a)]
    normal_saniye, normal_yakit = normal["saniye"] + normal["ekstra_saniye"], yakit_fonksiyonu(normal)
    return [
        {
            "strateji": a["strateji"],
            "onerilen": a is onerilen,
            "toplam_sure_dk": (a["saniye"] + a["ekstra_saniye"]) / 60.0,
            "ek_sure_dk": (a["saniye"] + a["ekstra_saniye"] - normal_saniye) / 60.0,
            "tahmini_yakit_kg": yakit_fonksiyonu(a),
            "ek_yakit_yuzde": 100.0 * (yakit_fonksiyonu(a) - normal_yakit) / normal_yakit if normal_yakit else 0.0,
            "riskli_nokta_sayisi": _riskli_nokta_sayisi(a),
            "iz_bulutu_nokta_sayisi": a.get("iz_bulutu_sayisi"),
            "maks_ti1": a["maks_ti1"],
            "irtifa_ft": _ucus_seviyesi(a["irtifa_m"]) * 100,
            "maks_yanal_sapma_km": a["yanal_sapma_km"],
            "noktalar": _noktalari_paketle(
                a["enlem"], a["boylam"], a["irtifa_m"], a["zamanlar"], a.get("ti1"), a.get("birlesik_edr")
            ),
        }
        for a in sorted(cephe, key=lambda a: (a["riskli_sayisi"], olcutler[id(a)][0]))
    ]


def _ortalama_ruzgar_bileseni_kt(aday, tas_ms):
    """Yer hızı − TAS (kt): + kuyruk (P), − baş rüzgârı (M). Seviye geçiş süresi hariç."""
    if not aday["saniye"]:
        return None
    mesafe_nm = _nokta_hucre_uzunluklari_km(aday["enlem"], aday["boylam"]).sum() / NM_KM
    return float(mesafe_nm / (aday["saniye"] / 3600.0) - tas_ms * 3600.0 / (NM_KM * 1000.0))


def _risk_hesaplandi_mi(aday) -> bool:
    return aday.get("ti1") is not None and not np.all(np.isnan(np.asarray(aday["ti1"], dtype=float)))


def _riskli_nokta_sayisi(aday):
    """Risk hesaplanamadıysa (kapsam dışı / veri yok) None: 'hesaplanmadı' 0 risk değildir."""
    return int(aday["riskli_sayisi"]) if _risk_hesaplandi_mi(aday) else None


def _rota_ozeti(aday, yakit_kg, toplam_saniye):
    enlemler, boylamlar = aday["enlem"], aday["boylam"]
    bolumler = riskli_bolumler(aday)
    ti1 = aday.get("ti1")
    return {
        "noktalar": _noktalari_paketle(
            enlemler, boylamlar, aday["irtifa_m"], aday["zamanlar"], ti1, aday.get("birlesik_edr")
        ),
        "fl": _ucus_seviyesi(aday["irtifa_m"]),
        "riskli_bolumler": bolumler,
        "riskli_mesafe_nm": None if bolumler is None else sum(b["uzunluk_nm"] for b in bolumler),
        "riskli_sure_dk": None if bolumler is None else sum(b["sure_dk"] for b in bolumler),
        "kapsam_disi_nokta_sayisi": (
            len(enlemler) if ti1 is None else int(np.isnan(np.asarray(ti1, dtype=float)).sum())
        ),
        "toplam_sure_dk": toplam_saniye / 60.0,
        "mesafe_km": sum(
            buyuk_daire_mesafesi_km(enlemler[i], boylamlar[i], enlemler[i + 1], boylamlar[i + 1])
            for i in range(len(enlemler) - 1)
        ),
        "tahmini_yakit_kg": yakit_kg,
        "tahmini_co2_kg": yakit_kg * CO2_KG_PER_KG_YAKIT,
        "irtifa_ft": _ucus_seviyesi(aday["irtifa_m"]) * 100,
        "maks_ti1": aday["maks_ti1"],
        "riskli_nokta_sayisi": _riskli_nokta_sayisi(aday),
        "iz_bulutu_nokta_sayisi": aday["iz_bulutu_sayisi"],
        "sigmet_ihlali_sayisi": aday["sigmet_ihlali"],
        "kisitli_saha_ihlali_sayisi": aday["kisitli_saha_ihlali"],
    }


_SEVIYE_MALIYET_NOTU = (
    " Yakıt farkı yalnızca geçici seviyeye gidip planlanan seviyeye dönmenin yaklaşık bedelidir; seviyeye bağlı "
    "seyir yakıt akışı modellenmez."
)


def _bulgu(kod, seviye, metin, **parametreler):
    """Yanıttaki makine-okunur bulgu (kod + seviye + parametreler) ve onun
    Türkçe cümlesi TEK yerde üretilir: 'aciklama' metni bulgulardan türetilir,
    ikisi birbirinden kopamaz. Seviye: bilgi | uyari | kritik."""
    return {"kod": kod, "seviye": seviye, "parametreler": parametreler, "metin": metin}


def _seviye_bulgulari(seviye):
    if not seviye or not seviye["duzeltildi"]:
        return []
    yon = "doğu (000-179°): tek" if seviye["yon"] == "dogu" else "batı (180-359°): çift"
    if seviye["tavan_asildi"]:
        neden = f"uçak tipinin azami seviyesinin (FL{seviye['azami_fl']}) üstünde"
    else:
        neden = f"yarım daire kuralına aykırı (manyetik iz {seviye['manyetik_iz']:03.0f}°, {yon} FL)"
    return [
        _bulgu(
            "ucus_seviyesi_duzeltildi",
            "uyari",
            f"İstenen FL{seviye['istenen_fl']:.0f} {neden}; hesap en yakın yasal seviye FL{seviye['fl']} ile "
            f"yapıldı. Manyetik sapma sabit {config.MANYETIK_SAPMA_DERECE:+.0f}° varsayıldı.",
            istenen_fl=seviye["istenen_fl"],
            fl=seviye["fl"],
            manyetik_iz=seviye["manyetik_iz"],
            yon=seviye["yon"],
            tavan_asildi=seviye["tavan_asildi"],
        )
    ]


def _bulgulari_olustur(
    ruzgarli_mi,
    veri_kupu,
    kup_adi,
    normal,
    en_iyi,
    irtifa_m,
    sigmet_kontrolu,
    guvenli_rota_bulundu_mu,
    kisitli_saha_kontrolu=None,
    canli_hata=None,
    seviye=None,
):
    bulgular = _seviye_bulgulari(seviye)
    if ruzgarli_mi and veri_kupu_kaynagi(veri_kupu) == "gfs":
        calisma = veri_kupu.attrs.get("model_calisma_zamani", "bilinmiyor")
        bulgular.append(
            _bulgu(
                "veri_gfs_tahmin",
                "bilgi",
                f"Canlı NOAA GFS tahmin verisiyle hesaplandı (model çalıştırması {calisma} UTC).",
                model_calisma_zamani=str(calisma),
            )
        )
    elif ruzgarli_mi:
        bulgular.append(_bulgu("veri_era5", "bilgi", f"Gerçek ERA5 verisiyle hesaplandı ('{kup_adi}').", kup=kup_adi))
    if ruzgarli_mi:
        normal_bolumler = riskli_bolumler(normal)
        if normal_bolumler is None:
            bulgular.append(
                _bulgu(
                    "ti1_hesaplanmadi",
                    "uyari",
                    "Normal rota için TI1 hesaplanamadı (rota veri küpünün kapsamı dışında); bu, risk OLMADIĞI "
                    "anlamına gelmez.",
                )
            )
        elif normal["riskli_sayisi"] == 0:
            bulgular.append(
                _bulgu(
                    "ti1_risk_yok",
                    "bilgi",
                    f"Normal rota üzerinde riskli türbülans (TI1 >= {config.TI1_ESIK_ORTA_SIDDETLI:.1e} s^-2) "
                    "TESPİT EDİLMEDİ.",
                    esik=config.TI1_ESIK_ORTA_SIDDETLI,
                )
            )
        else:
            bulgular.append(
                _bulgu(
                    "ti1_risk_var",
                    "uyari",
                    f"Normal rota üzerinde {normal['riskli_sayisi']} noktada (~"
                    f"{sum(b['uzunluk_nm'] for b in normal_bolumler):.0f} NM, ~"
                    f"{sum(b['sure_dk'] for b in normal_bolumler):.0f} dk) riskli türbülans tespit edildi.",
                    riskli_nokta_sayisi=normal["riskli_sayisi"],
                    esik=config.TI1_ESIK_ORTA_SIDDETLI,
                )
            )
    elif canli_hata:
        bulgular.append(
            _bulgu(
                "ruzgar_hesaba_katilamadi",
                "uyari",
                f"UYARI: {canli_hata} Rüzgar ve türbülans (TI1) hesaba katılamadı, rotalar sadece uçağın hava "
                "hızıyla (TAS) zamanlandı (bkz. GET /saglik?derin=true); SIGMET ve kısıtlı saha kısıtları yine "
                "uygulandı.",
                neden="canli_veri",
            )
        )
    else:
        bulgular.append(
            _bulgu(
                "ruzgar_hesaba_katilamadi",
                "uyari",
                "Seçilen bölge/tarih/irtifa için ne sunucudaki ERA5 arşiv küpleri ne de canlı GFS "
                f"verisi (şimdi -{config.CANLI_GECMIS_SAAT} sa / +{config.CANLI_TAHMIN_UFKU_SAAT} sa aralığı için) "
                "rotanın TAMAMINI kapsıyor -- rüzgar ve türbülans (TI1) hesaba katılamadı, rotalar sadece uçağın "
                "hava hızıyla (TAS) zamanlandı; gerçek bir yakıt tasarrufu/türbülans kaçınması iddia edilmiyor.",
                neden="kapsam_disi",
            )
        )

    durum = sigmet_kontrolu["durum"]
    if durum == "erisilemedi":
        bulgular.append(
            _bulgu(
                "sigmet_erisilemedi",
                "kritik",
                "UYARI: SIGMET veritabanına erişilemedi -- aktif SIGMET kontrolü YAPILAMADI.",
            )
        )
    elif durum == "uygulandi":
        ihlal = normal["sigmet_ihlali"]
        bulgular.append(
            _bulgu(
                "sigmet_uygulandi",
                "bilgi",
                f"{sigmet_kontrolu['aktif_sigmet_sayisi']} aktif SIGMET sert kısıt olarak uygulandı; normal rota "
                + (f"{ihlal} nokta/bacakta bunlara giriyor." if ihlal else "bunlara girmiyor."),
                aktif_sigmet_sayisi=sigmet_kontrolu["aktif_sigmet_sayisi"],
                normal_rota_ihlali=ihlal,
            )
        )
    ufuk_disi = sigmet_kontrolu.get("yayin_ufku_disi", "yok")
    if durum != "erisilemedi" and ufuk_disi != "yok":
        bulgular.append(
            _bulgu(
                "sigmet_ufuk_disi",
                "uyari",
                ("Uçuşun tamamı" if ufuk_disi == "tam" else "Uçuşun bir kısmı")
                + f" şu andan {config.SIGMET_YAYIN_UFKU_SAAT:g} saatten daha sonra; o zaman dilimi için SIGMET henüz "
                "yayımlanmamış olabilir. SIGMET kontrolü bu kısım için güvence vermez -- kalkıştan önceki son "
                "saatlerde yeniden hesaplayın.",
                kisim=ufuk_disi,
                yayin_ufku_saat=config.SIGMET_YAYIN_UFKU_SAAT,
            )
        )
    if sigmet_kontrolu.get("bayat_mi"):
        sorunlu = sigmet_kontrolu.get("sorunlu_kaynaklar") or []
        bulgular.append(
            _bulgu(
                "sigmet_bayat",
                "kritik",
                f"UYARI: son başarılı SIGMET güncellemesi {config.SIGMET_BAYATLIK_DAKIKA} dakikadan eski ya da hiç "
                "yapılmamış (bkz. POST /api/v1/sigmet/guncelle)"
                + (f"; hata veren kaynak: {', '.join(sorunlu)}" if sorunlu else "")
                + " -- aktif uyarılar eksik olabilir.",
                bayatlik_esigi_dakika=config.SIGMET_BAYATLIK_DAKIKA,
                sorunlu_kaynaklar=list(sorunlu),
            )
        )

    bulgular += _kisitli_saha_bulgulari(kisitli_saha_kontrolu or {}, normal)

    if not guvenli_rota_bulundu_mu:
        bulgular.append(
            _bulgu(
                "guvenli_rota_yok",
                "kritik",
                "ÖNERİ YOK: aktif SIGMET'lere ve kısıtlı hava sahalarına girmeyen geçerli bir rota bulunamadı "
                "(başlangıç/bitiş SIGMET içinde olabilir ya da alan arama ızgarasından geniş) -- gösterilen rota "
                "normal rotadır ve ÖNERİLMEZ.",
            )
        )
    elif en_iyi["strateji"] == "yok":
        bulgular.append(
            _bulgu(
                "sapma_gereksiz",
                "bilgi",
                "Kaçınılacak bir risk olmadığı için optimize rota normal rotayla birebir aynıdır "
                "(uydurma bir sapma gösterilmiyor).",
            )
        )
    else:
        strateji = _temel_strateji(en_iyi["strateji"])
        irtifa_farki_ft = (en_iyi["irtifa_m"] - irtifa_m) / 0.3048
        strateji_aciklamasi = {
            "yanal": (
                f"A* araması ile yanal sapma (en fazla {en_iyi['yanal_sapma_km'] / NM_KM:.0f} NM, "
                f"{en_iyi['yanal_sapma_km']:.0f} km)"
            ),
            "ats_alternatif": "ATS ağı üzerinde alternatif rota (A*)",
            "irtifa_yukari": f"irtifayı {irtifa_farki_ft:.0f} ft artırarak (tırmanma)",
            "irtifa_asagi": f"irtifayı {-irtifa_farki_ft:.0f} ft azaltarak (alçalma)",
        }[strateji]
        kacinma = {"strateji": strateji, "yanal_sapma_km": en_iyi["yanal_sapma_km"], "irtifa_farki_ft": irtifa_farki_ft}
        if not ruzgarli_mi:
            bulgular.append(
                _bulgu(
                    "kacinma_sert_kisit",
                    "bilgi",
                    f"Aktif SIGMET'lere ve kısıtlı sahalara girmeyen en kısa rota olarak {strateji_aciklamasi} "
                    "bulundu.",
                    **kacinma,
                )
            )
        elif en_iyi["riskli_sayisi"] == 0:
            bulgular.append(
                _bulgu(
                    "kacinma_tam_guvenli",
                    "bilgi",
                    "ÇOK FAKTÖRLÜ karşılaştırmada (yanal A* araması vs aynı yönün bir üst/alt yasal FL'sine geçiş, her "
                    "biri yaklaşık yakıt/süre maliyetiyle) en ucuz TAM güvenli seçenek olarak "
                    f"{strateji_aciklamasi} bulundu." + (_SEVIYE_MALIYET_NOTU if strateji.startswith("irtifa") else ""),
                    **kacinma,
                )
            )
        else:
            bulgular.append(
                _bulgu(
                    "ti1_riski_kismen_kaldi",
                    "uyari",
                    "Denenen adaylar TI1 riskini TAMAMEN ortadan kaldıramadı (türbülans alanı geniş olabilir) -- "
                    f"sert kısıtlara uyan seçenekler arasından {strateji_aciklamasi} seçildi "
                    f"({en_iyi['riskli_sayisi']} riskli nokta, normal rotadaki {normal['riskli_sayisi']}'e karşı)."
                    + (_SEVIYE_MALIYET_NOTU if strateji.startswith("irtifa") else ""),
                    riskli_nokta_sayisi=en_iyi["riskli_sayisi"],
                    normal_riskli_nokta_sayisi=normal["riskli_sayisi"],
                    **kacinma,
                )
            )
    return bulgular


def _kisitli_saha_bulgulari(kontrol, normal):
    bulgular = []
    if kontrol.get("durum") == "erisilemedi":
        bulgular.append(
            _bulgu(
                "kisitli_saha_erisilemedi",
                "kritik",
                "UYARI: kısıtlı hava sahası veritabanına erişilemedi -- saha kontrolü YAPILAMADI.",
            )
        )
    elif kontrol.get("durum") == "uygulandi":
        ihlal = normal["kisitli_saha_ihlali"]
        bulgular.append(
            _bulgu(
                "kisitli_saha_uygulandi",
                "bilgi",
                f"{kontrol['uygulanan_saha_sayisi']} kısıtlı hava sahası sert kısıt olarak uygulandı; normal rota "
                + (f"{ihlal} nokta/bacakta bunlara giriyor." if ihlal else "bunlara girmiyor."),
                uygulanan_saha_sayisi=kontrol["uygulanan_saha_sayisi"],
                normal_rota_ihlali=ihlal,
            )
        )
    if kontrol.get("muaf_tutulanlar"):
        bulgular.append(
            _bulgu(
                "kisitli_saha_uc_koridoru",
                "bilgi",
                "Kalkış/varış noktasını içeren saha(lar)da sadece planlı rotanın "
                f"±{config.KISITLI_SAHA_UC_KORIDORU_KM:.0f} km koridoru serbest bırakıldı: "
                + ", ".join(kontrol["muaf_tutulanlar"])
                + ".",
                koridor_km=config.KISITLI_SAHA_UC_KORIDORU_KM,
                sahalar=list(kontrol["muaf_tutulanlar"]),
            )
        )
    if kontrol.get("ornek_veri_mi"):
        bulgular.append(
            _bulgu(
                "kisitli_saha_ornek_veri",
                "uyari",
                "NOT: kısıtlı sahaların bir kısmı paketle gelen ÖRNEK veridir (ülke sınırından türetilmiş) -- resmi "
                "AIP/CZIB/NOTAM verisi değildir.",
            )
        )
    return bulgular


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


def _riskli_bolum_czml_varliklari(rota, id_on_eki):
    """Riskli bölümler rota üzerinde kırmızı kalın çizgi (nokta 'riskli' alanından)."""
    noktalar = rota["noktalar"]
    varliklar, bolum = [], []
    for n in [*noktalar, None]:
        if n is not None and n.get("riskli"):
            bolum.append(n)
            continue
        if bolum:
            koordinatlar = [
                d for p in (bolum if len(bolum) > 1 else bolum * 2) for d in (p["boylam"], p["enlem"], p["irtifa_m"])
            ]
            varliklar.append(
                {
                    "id": f"{id_on_eki}-riskli-{len(varliklar)}",
                    "name": f"Riskli bölüm FL{bolum[0]['fl']:03d} {bolum[0]['zaman'][11:16]}Z",
                    "polyline": {
                        "positions": {"cartographicDegrees": koordinatlar},
                        "material": {"solidColor": {"color": {"rgba": [231, 76, 60, 255]}}},
                        "width": 6,
                        "clampToGround": False,
                    },
                }
            )
            bolum = []
    return varliklar


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
    saha_varliklari = [
        _kisitli_sahayi_czml_varligina_cevir(saha, i)
        for i, saha in enumerate((sonuc.get("kisitli_saha_kontrolu") or {}).get("sahalar", []))
    ]
    # Statik ön izleme çizgileri ve kısıt hacimleri ÖNCE eklenir ki uçak
    # modelleri/etiketleri onların üzerinde (z-sırasında sonda) görünsün.
    return [
        belge_paketi,
        *saha_varliklari,
        *sigmet_varliklari,
        normal_on_izleme,
        optimize_on_izleme,
        *_riskli_bolum_czml_varliklari(sonuc["normal_rota"], "normal-rota"),
        *_riskli_bolum_czml_varliklari(sonuc["optimize_rota"], "optimize-rota"),
        normal_ucak,
        optimize_ucak,
    ]


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
        "name": (
            f"SIGMET {sigmet.get('fir_kodu') or ''} {sigmet['tehlike']}".strip()
            + (
                f" (hareket {sigmet['hareket_yonu_derece']:.0f}° "
                + (f"{sigmet['hareket_hizi_kt']:.0f} kt" if sigmet.get("hareket_hizi_kt") else "hız bilinmiyor")
                + "; çizim yayın anındaki konum)"
                if sigmet.get("hareket_yonu_derece") is not None
                else ""
            )
        ),
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


def _kisitli_sahayi_czml_varligina_cevir(saha, sira):
    """Kısıtlı hava sahasını mor, yarı saydam bir hacim olarak çizer; süresiz
    sahalar (boş geçerlilik) tüm simülasyon boyunca görünür."""
    taban_m = (saha.get("taban_ft") or 0) * 0.3048
    tavan_m = (saha.get("tavan_ft") or _SIGMET_VARSAYILAN_TAVAN_FT) * 0.3048
    koseler = [deger for boylam, enlem in saha["poligon"] for deger in (boylam, enlem, taban_m)]
    varlik = {
        "id": f"kisitli-saha-{saha.get('id') or sira}",
        "name": f"Kısıtlı saha ({saha.get('tur') or ''}): {saha.get('ad') or ''}".strip(),
        "polygon": {
            "positions": {"cartographicDegrees": koseler},
            "height": taban_m,
            "extrudedHeight": tavan_m,
            "material": {"solidColor": {"color": {"rgba": [142, 68, 173, 60]}}},
            "outline": True,
            "outlineColor": {"rgba": [142, 68, 173, 200]},
        },
    }
    baslangic, bitis = saha.get("gecerlilik_baslangic"), saha.get("gecerlilik_bitis")
    if baslangic is not None or bitis is not None:
        bas = pd.Timestamp(baslangic).isoformat() if baslangic is not None else "0000-01-01T00:00:00Z"
        son = pd.Timestamp(bitis).isoformat() if bitis is not None else "9999-12-31T23:59:59Z"
        varlik["availability"] = f"{bas}/{son}"
    return varlik
