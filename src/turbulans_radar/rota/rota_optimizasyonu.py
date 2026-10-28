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

Uçak "modelleri": seyir hızı tip başına YAKLAŞIK (halka açık, tipik) bir
değerdir. Yakıt ve NOx OpenAP ile kütleye/irtifaya bağlı hesaplanır
(rota/performans_modeli.py); UCAK_PROFILLERI'ndeki sabit yakıt akışı yalnız
OpenAP kullanılamazsa yedektir -- üreticinin resmi performans verisi DEĞİLDİR. 3D görselleştirmede hepsi AYNI jenerik
uçak modelini (web/models/ucak.glb, resmi CesiumJS örnek verisi) kullanır.

Bu modül akışı yönetir; A* a_yildiz.py, geometri geometri.py, rüzgâr ruzgar.py, riskli
bölüm/brifing brifing.py, dispeç bulguları bulgular.py, CZML czml.py'dedir.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import shapely

from turbulans_radar import config
from turbulans_radar.fizik.birim_donusumleri import (
    irtifa_metre_to_basinc_hpa,
)
from turbulans_radar.fizik.cografya import mesafe_km as buyuk_daire_mesafesi_km
from turbulans_radar.fizik.eslestirme import kapsam_disi_maskesi
from turbulans_radar.fizik.iz_bulutu import duyarli_nokta_sayisi
from turbulans_radar.fizik.ti1_esigi import ayri_esik_baglaminda, etkin_ti1_esigi, kaynaga_gore_ayarla
from turbulans_radar.fizik.turbulans_indeksleri import TI1_GUVENILIRLIK_NOTU
from turbulans_radar.loglama import logger_al
from turbulans_radar.rota import fpl, hava_yolu_agi, performans_modeli, ucus_seviyeleri
from turbulans_radar.rota.a_yildiz import (
    _a_yildiz_ile_rota_ara,
    _ats_dugum_zamani,
    _ats_ile_rota_ara,
    _zaman_belirsizligi,
)
from turbulans_radar.rota.brifing import (
    _nokta_hucre_uzunluklari_km,
    _noktalari_paketle,
    _ucus_seviyesi,
    brifing_karti,
    iz_bulutu_seviye_bilgisi,
    kabin_onerisi,
    riskli_bolumler,
)
from turbulans_radar.rota.bulgular import (
    _bulgu,
    _bulgulari_olustur,
    _temel_strateji,
)
from turbulans_radar.rota.dikey_kesit import dikey_kesit
from turbulans_radar.rota.geometri import (
    NM_KM,
    _ilk_yon_derece,
    _km_boylam_derecesine_cevir,
    antimeridyeni_kesiyor_mu,
    buyuk_daire_rotasi_olustur,
    yanal_sapma_yonu,
)
from turbulans_radar.rota.risk_katmanlari import (
    TURBULANS_CEZASI_SANIYE,
    KisitliSahaKatmani,
    SigmetKisitKatmani,
    Ti1CezaKatmani,
    rota_eslesmesi,
)
from turbulans_radar.rota.ruzgar import (
    _bacak_ruzgar_okuyucu,
    _yer_hizi_ms,
    ruzgar_bilesenlerini_al,
)
from turbulans_radar.uretim_bilgisi import uretim_bilgisi
from turbulans_radar.veri.kisitli_saha_saglayici import ORNEK_KAYNAK, gecerli_kisitli_sahalari_getir
from turbulans_radar.veri.sigmet_saglayici import (
    gecerli_sigmetleri_getir,
    kacinilacak_tehlikeler,
    son_guncelleme_zamani,
    sorunlu_kaynaklar,
)
from turbulans_radar.veri.veri_saglayicilari import veri_kupu_kaynagi, veri_kupunu_sec
from turbulans_radar.veri.veri_yukleme import hava_durumu_onbellekli_yukle, veri_kupu_adi

# Yaklaşık, halka açık tipik seyir performansı değerleri (bkz. modül dosya
# başlığı) -- resmi üretici verisi değildir, sadece büyüklük mertebesi
# doğru, karşılaştırma amaçlı kaba tahminlerdir.
# azami_fl: halka açık azami işletme irtifası (A320 39.800 ft, 737-800 41.000 ft,
# 777-300ER ve A350-900 43.100 ft); kütleye bağlı fiili tavan modellenmez.
UCAK_PROFILLERI: dict[str, dict[str, Any]] = {
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
# Hatalar (geometri: rota/geometri.py, A*: rota/a_yildiz.py, rüzgâr: rota/ruzgar.py)
# ---------------------------------------------------------------------------


class AtsAgiKullanilamazHatasi(ValueError):
    """ATS modu istendi ama ağ yok ya da ToC/ToD ağa bağlanamıyor."""


class AntimeridyenHatasi(ValueError):
    """Rota 180° boylamını kesiyor (desteklenmez, bkz. SISTEM_KARTI)."""


# ---------------------------------------------------------------------------
# ERA5 kapsama alanı kontrolü
# ---------------------------------------------------------------------------


def _era5_tamamen_kapsiyor_mu(veri_kupu, enlemler, boylamlar, zaman, irtifa_m=None):
    if veri_kupu is None:
        return False
    enlemler = np.atleast_1d(np.asarray(enlemler, dtype=float))
    basinc_hpa = None if irtifa_m is None else np.full(len(enlemler), irtifa_metre_to_basinc_hpa(irtifa_m))
    return not kapsam_disi_maskesi(veri_kupu, enlemler, boylamlar, [zaman] * len(enlemler), basinc_hpa).any()


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
    okuyucu = None
    if ruzgarli_mi and len(enlemler) > 1:
        orta_enlemler = [(enlemler[i] + enlemler[i + 1]) / 2 for i in range(len(enlemler) - 1)]
        orta_boylamlar = [(boylamlar[i] + boylamlar[i + 1]) / 2 for i in range(len(boylamlar) - 1)]
        okuyucu = _bacak_ruzgar_okuyucu(veri_kupu, orta_enlemler, orta_boylamlar, basinc_hpa)

    for i in range(len(enlemler) - 1):
        mesafe_km = buyuk_daire_mesafesi_km(enlemler[i], boylamlar[i], enlemler[i + 1], boylamlar[i + 1])
        yer_hizi_ms = tas_ms

        if ruzgarli_mi:
            yon_derece = _ilk_yon_derece(enlemler[i], boylamlar[i], enlemler[i + 1], boylamlar[i + 1])
            orta_enlem = (enlemler[i] + enlemler[i + 1]) / 2
            orta_boylam = (boylamlar[i] + boylamlar[i + 1]) / 2
            if okuyucu is not None:
                u, v = okuyucu(i, zaman)
            else:
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
    riskli_sayisi = int(np.nansum(ti1_degerleri >= etkin_ti1_esigi()))
    return maks_ti1, riskli_sayisi


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
            "yanal_tampon_nm": katman.yanal_tampon_nm(sg),
        }
        for sg in katman.sigmetler
    ]
    ozet["aktif_sigmet_sayisi"] = len(katman.sigmetler)
    ozet["tampon"] = katman.tampon_ozeti()
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


def katman_cevrelenmiyor_bulgusu(veri_kupu, irtifalar_m) -> dict | None:
    """Rota seviyesi küpün basınç seviyelerinin dışındaysa (ör. 3 seviyeli GFS/Türkiye küpünde FL280–290 ya
    da FL390+), düşey kayma çevreleyen katmandan değil en yakın iki seviyeden dışdeğerlenir (bkz.
    eslestirme.cevreleyen_katman_seviyeleri)."""
    seviyeler = np.sort(np.asarray(veri_kupu[config.BASINC_BOYUTU].values, dtype=float))
    disarida = sorted(
        {
            int(round(float(irtifa_m) / 0.3048 / 100))
            for irtifa_m in irtifalar_m
            if not seviyeler[0] <= float(irtifa_metre_to_basinc_hpa(irtifa_m)) <= seviyeler[-1]
        }
    )
    if not disarida:
        return None
    return _bulgu(
        "katman_cevrelenmiyor",
        "uyari",
        f"FL{', FL'.join(f'{fl:03d}' for fl in disarida)} hava küpünün basınç seviyelerinin "
        f"({seviyeler[0]:.0f}–{seviyeler[-1]:.0f} hPa, {len(seviyeler)} seviye) dışında; düşey kayma ve TI1 bu "
        "seviyede çevreleyen katmandan değil en yakın iki seviyeden dışdeğerlenir, güvenilirliği daha düşüktür.",
        seviyeler_hpa=[float(s) for s in seviyeler],
        fl=disarida,
    )


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
        "guvenilir_ongoru_saat": config.GUVENILIR_ONGORU_SAAT,
        "ongoru_belirsiz": kalan_saat > config.GUVENILIR_ONGORU_SAAT,
    }


_KAPSAM_ORTAK = (
    "Rota yalnızca seyir (en-route) safhası içindir: başlangıç ve bitiş seyre giriş (ToC) ve seyirden "
    "çıkış (ToD) noktası, irtifa seyir irtifası kabul edilir. Kalkış, tırmanış, alçalış, SID/STAR ve "
    "yaklaşma kapsam dışıdır. "
)


def kapsam(arama_uzayi="koridor", ats_kaynagi=None, ats_etiketi=None) -> dict:
    if arama_uzayi == "ats":
        arama = (
            f"Rota, yüklü ağda ({ats_etiketi or 'ATS/FRA'}; {ats_kaynagi}) aranır; ToC/ToD ağa doğrudan (DCT) "
            "bağlanır. "
        )
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


@ayri_esik_baglaminda
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
    kalkis_meydani=None,
    varis_meydani=None,
    veri_kupu=None,
):
    """
    veri_kupu: verilirse küp seçimi/canlı indirme atlanır, bu küp kullanılır
    (deney için belirli bir GFS koşusu, bkz. analiz/kacinma_baslangici.py).
    arama_uzayi: "koridor" (büyük daire etrafında yanal ızgara) ya da "ats"
    (ATS yolu/FRA ağı, bkz. hava_yolu_agi.py; ats_agi verilmezse
    config.ATS_AGI_DOSYASI). ATS modunda normal rota ağdaki en hızlı yol,
    optimize rota aynı risk katmanlarıyla ağda aranan yoldur. kalkis_meydani/
    varis_meydani (ICAO, isteğe bağlı): ToC/ToD o meydanın AIP FRA bağlantı
    noktalarına bağlanır.
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
    yakit_modeli = "openap" if performans_modeli.kullanilabilir_mi(ucak_modeli_kodu) else "sabit"

    def _seviye_ekstrasi(eski_irtifa_m, yeni_irtifa_m):
        ek = performans_modeli.seviye_degisimi_ek_yakiti(
            ucak_modeli_kodu, eski_irtifa_m, yeni_irtifa_m, tas_ms, DIKEY_HIZ_FT_DK
        )
        if ek is None:
            return _irtifa_degisimi_maliyeti(eski_irtifa_m, yeni_irtifa_m, profil["yakit_akisi_kg_saat"])
        return 0.0, ek

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
    if veri_kupu is None:
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
    kaynaga_gore_ayarla(veri_kupu_kaynagi(veri_kupu) if ruzgarli_mi else None)
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
            "yakit_modeli": yakit_modeli,
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

    yakit_ozetleri = {}
    seyir_onbellegi = {}

    def _seyir_yakiti(aday, oran=None):
        oran = config.ROTA_SEYIR_KUTLE_ORANI if oran is None else oran
        anahtar = (aday["saniye"], aday["irtifa_m"], oran)
        if anahtar not in seyir_onbellegi:
            seyir_onbellegi[anahtar] = performans_modeli.seyir_yakiti(
                ucak_modeli_kodu, aday["saniye"], tas_ms, aday["irtifa_m"], kutle_orani=oran
            )
        return seyir_onbellegi[anahtar]

    def _aday_yakit_ozeti(aday):
        anahtar = id(aday)
        if anahtar not in yakit_ozetleri:
            seyir = _seyir_yakiti(aday)
            if seyir is None:
                seyir = {"yakit_kg": profil["yakit_akisi_kg_saat"] * (aday["saniye"] / 3600.0), "nox_kg": None}
            yakit_ozetleri[anahtar] = (aday, seyir["yakit_kg"] + aday["ekstra_yakit_kg"], seyir["nox_kg"])
        return yakit_ozetleri[anahtar]

    def _aday_toplam_yakit_kg(aday):
        return _aday_yakit_ozeti(aday)[1]

    def _aday_nox_kg(aday):
        return _aday_yakit_ozeti(aday)[2]

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
                ag,
                *uclar,
                aday_irtifa_m,
                zaman_iso,
                tas_ms,
                veri_kupu if ruzgarli_mi else None,
                katmanlar,
                (kalkis_meydani, varis_meydani),
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
        tod = _ats_dugum_zamani(kalkis_utc, uclar[0], uclar[1], tas_ms)
        tod_gec = tod + _zaman_belirsizligi(tod - kalkis_utc)
        if planli is None and not ag.fra_penceresinde_mi(kalkis_utc, tod_gec):
            raise AtsAgiKullanilamazHatasi(
                f"FRA uçuşu FRA kapanmadan önce FRATURK'tan çıkmalı ({ag.fra_saatleri_metni()}, AIP ENR 1.3 "
                f"§5.5.2.1); {kalkis_utc:%H:%M} UTC kalkışla tahmini ToD {tod:%H:%M} UTC (belirsizlik payıyla "
                f"{tod_gec:%H:%M}). Daha erken planlayın ya da koridor modunu kullanın."
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
        ti1_onbellegi = {}
        risk_katmanlari = ([Ti1CezaKatmani(veri_kupu, onbellek=ti1_onbellegi)] if ruzgarli_mi else []) + sert_katmanlar
        pareto_cezalari = config.ROTA_PARETO_CEZALARI_SANIYE if ruzgarli_mi else []
        adaylar = []
        irtifa_secenekleri = (
            _komsu_yasal_seviyeler(seviye, veri_kupu, enlemler_gc, boylamlar_gc, zaman_iso) if ruzgarli_mi else {}
        )
        if ag is None:
            for strateji_adi, katmanlar in [
                ("yanal", risk_katmanlari),
                *(
                    (
                        f"yanal_ceza_{c:g}",
                        [Ti1CezaKatmani(veri_kupu, ceza_saniye=c, onbellek=ti1_onbellegi), *sert_katmanlar],
                    )
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
                ekstra = _seviye_ekstrasi(irtifa_m, yeni_irtifa_m)
                adaylar.append(_aday(strateji_adi, enlemler_gc, boylamlar_gc, yeni_irtifa_m, ekstra=ekstra))
        else:
            for strateji_adi, aday_irtifa_m in {"ats_alternatif": irtifa_m, **irtifa_secenekleri}.items():
                yol = _ats_yolu(aday_irtifa_m, risk_katmanlari)
                if yol is None:
                    continue
                ats_yollari[strateji_adi] = yol
                ekstra = _seviye_ekstrasi(irtifa_m, aday_irtifa_m)
                adaylar.append(_aday(strateji_adi, yol[0], yol[1], aday_irtifa_m, ekstra=ekstra))
            for ceza in pareto_cezalari:
                strateji_adi = f"ats_ceza_{ceza:g}"
                yol = _ats_yolu(
                    irtifa_m, [Ti1CezaKatmani(veri_kupu, ceza_saniye=ceza, onbellek=ti1_onbellegi), *sert_katmanlar]
                )
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

    ruzgar_optimum = normal
    if arama_uzayi == "koridor" and ruzgarli_mi:
        yol = _a_yildiz_ile_rota_ara(enlemler_gc, boylamlar_gc, irtifa_m, zaman_iso, tas_ms, veri_kupu, [])
        if yol is not None:
            ruzgar_optimum = _aday("ruzgar_optimum", yol[0], yol[1], irtifa_m, yanal_sapma_km=yol[2])
    for a in (normal, ruzgar_optimum, en_iyi, *(adaylar if en_iyi is not normal else [])):
        a["tahmini_nox_kg"] = _aday_nox_kg(a)
    referans_karsilastirmasi = (
        _referans_karsilastirmasi(normal, ruzgar_optimum, en_iyi, _aday_toplam_yakit_kg, tas_ms, arama_uzayi)
        if ruzgarli_mi
        else None
    )

    normal_yakit_kg = _aday_toplam_yakit_kg(normal)
    # Yakıt = seyir yakıtı (OpenAP ya da sabit tablo) + seviye geçişlerinin ek yakıtı (bkz. _seviye_ekstrasi).
    optimize_yakit_kg = _aday_toplam_yakit_kg(en_iyi)
    optimize_saniye = en_iyi["saniye"] + en_iyi["ekstra_saniye"]

    def _kutleli_yakit_kg(aday, oran):
        seyir = _seyir_yakiti(aday, oran)
        if seyir is None:
            return None
        ek = 0.0
        if aday["irtifa_m"] != irtifa_m:
            ek = performans_modeli.seviye_degisimi_ek_yakiti(
                ucak_modeli_kodu, irtifa_m, aday["irtifa_m"], tas_ms, DIKEY_HIZ_FT_DK, kutle_orani=oran
            )
        return seyir["yakit_kg"] + ek

    yakit_bandi = None
    if yakit_modeli == "openap" and config.ROTA_KUTLE_BANDI:
        oranlar = sorted({*config.ROTA_KUTLE_BANDI, config.ROTA_SEYIR_KUTLE_ORANI})
        yuzdeler = []
        for oran in oranlar:
            n_kg, o_kg = _kutleli_yakit_kg(normal, oran), _kutleli_yakit_kg(en_iyi, oran)
            yuzdeler.append(100.0 * (n_kg - o_kg) / n_kg if n_kg else None)
        gecerli = [y for y in yuzdeler if y is not None]
        yakit_bandi = {
            "kutle_oranlari": oranlar,
            "yakit_tasarrufu_yuzde": yuzdeler,
            "en_dusuk": min(gecerli) if gecerli else None,
            "en_yuksek": max(gecerli) if gecerli else None,
            "aciklama": "Aynı iki rota için seyir başı kütlesi MTOW'un bu oranlarıyla yeniden hesaplandı; rota seçimi "
            "ROTA_SEYIR_KUTLE_ORANI ile yapıldı. Kütle bilinmediği için tek bir değer yerine bu aralık okunmalıdır.",
        }
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
    if ruzgarli_mi:
        katman_bulgusu = katman_cevrelenmiyor_bulgusu(veri_kupu, {normal["irtifa_m"], en_iyi["irtifa_m"]})
        if katman_bulgusu is not None:
            bulgular.append(katman_bulgusu)
    ufuk = planlama_ufku(zaman_iso)
    if ruzgarli_mi and veri_kupu_kaynagi(veri_kupu) == "gfs" and ufuk["ongoru_belirsiz"]:
        bulgular.append(
            _bulgu(
                "ongoru_belirsiz",
                "uyari",
                f"Kalkışa ~{ufuk['kalkisa_kalan_saat']:.0f} saat var. CAT'in yeri topluluk tahminleriyle ancak "
                f"~24–48 saat önceden tutarlı öngörülebildi (Lee, 2025); bu ufkun ötesinde riskli alanların yeri "
                f"belirsizdir. Kalkıştan önceki {config.GUVENILIR_ONGORU_SAAT} saat içinde yeniden hesaplayın. "
                "Sınır literatürden alındı, kalibre edilmedi.",
                kalkisa_kalan_saat=ufuk["kalkisa_kalan_saat"],
                guvenilir_ongoru_saat=config.GUVENILIR_ONGORU_SAAT,
            )
        )

    sonuc = {
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
                "maks_yanal_sapma_yonu": yanal_sapma_yonu(en_iyi["enlem"], en_iyi["boylam"]),
                "ortalama_ruzgar_bileseni_kt": _ortalama_ruzgar_bileseni_kt(en_iyi, tas_ms),
            }
        ),
        "referans_karsilastirmasi": referans_karsilastirmasi,
        "kabin_onerisi": kabin_onerisi(optimize_ozeti["riskli_bolumler"]),
        "iz_bulutu_seviye_bilgisi": iz_bulutu_seviye_bilgisi(en_iyi, veri_kupu) if ruzgarli_mi else None,
        "dikey_kesit": (
            dikey_kesit(en_iyi["enlem"], en_iyi["boylam"], en_iyi["zamanlar"], veri_kupu, etkin_ti1_esigi())
            if ruzgarli_mi
            else None
        ),
        "fpl_madde15": (
            fpl.madde15(optimize_ozeti["noktalar"], tas_ms, optimize_ozeti["fl"]) if guvenli_rota_bulundu_mu else None
        ),
        "sure_tasarrufu_dk": (normal["saniye"] - optimize_saniye) / 60.0,
        "yakit_tasarrufu_yuzde": (
            100.0 * (normal_yakit_kg - optimize_yakit_kg) / normal_yakit_kg if normal_yakit_kg > 0 else 0.0
        ),
        "co2_farki_kg": normal_yakit_kg * CO2_KG_PER_KG_YAKIT - optimize_yakit_kg * CO2_KG_PER_KG_YAKIT,
        "yakit_tasarrufu_yuzde_araligi": yakit_bandi,
        "ti1_guvenilirlik_notu": TI1_GUVENILIRLIK_NOTU,
        "yakit_modeli": {
            "kaynak": yakit_modeli,
            "baslangic_kutle_kg": performans_modeli.baslangic_kutlesi_kg(ucak_modeli_kodu),
            "kutle_orani_notu": "Seyir başı kütlesi MTOW x ROTA_SEYIR_KUTLE_ORANI; parametrik varsayım, kalibre edilmedi.",
            "aciklama": (
                performans_modeli.KAYNAK_NOTU
                if yakit_modeli == "openap"
                else "Sabit tipik yakıt akışı; irtifa ve kütleye bağlı değil."
            )
            + " Mutlak yakıt değil, aynı tipteki rotalar arası karşılaştırmadır.",
            "openap_surumu": performans_modeli.openap_surumu() if yakit_modeli == "openap" else None,
        },
        "uretim_bilgisi": uretim_bilgisi(
            veri_kupu if ruzgarli_mi else None,
            parametreler={
                "arama_uzayi": arama_uzayi,
                "maks_yanal_sapma_km": config.ROTA_MAKS_YANAL_SAPMA_KM,
                "maks_sapma_acisi_derece": config.ROTA_MAKS_SAPMA_ACISI_DERECE,
                "ti1_ceza_saniye": TURBULANS_CEZASI_SANIYE,
            },
        ),
        "secenekler": secenekler,
        "kapsam": kapsam(arama_uzayi, *((ag.kaynak, ag.etiket()) if ag is not None else ())),
        "planlama_ufku": ufuk,
        "ats": (
            None
            if ag is None
            else {
                "kaynak": ag.kaynak,
                "etiket": ag.etiket(),
                "normal_rota": hava_yolu_agi.rota_ozeti(*ats_yollari["yok"][2:]),
                "optimize_rota": hava_yolu_agi.rota_ozeti(*ats_yollari.get(en_iyi["strateji"], ats_yollari["yok"])[2:]),
                "uyarilar": list(
                    dict.fromkeys(
                        u
                        for yol in (ats_yollari["yok"], ats_yollari.get(en_iyi["strateji"], ats_yollari["yok"]))
                        for u in ag.rol_uyarilari(yol[2], *uclar, kalkis_meydani, varis_meydani)
                    )
                    | dict.fromkeys(filter(None, [ag.airac_uyarisi()]))
                ),
                "buyuk_daire_km": sum(
                    buyuk_daire_mesafesi_km(enlemler_gc[i], boylamlar_gc[i], enlemler_gc[i + 1], boylamlar_gc[i + 1])
                    for i in range(len(enlemler_gc) - 1)
                ),
            }
        ),
    }
    sonuc["brifing_karti"] = brifing_karti(sonuc)
    return sonuc


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
            "tahmini_nox_kg": a.get("tahmini_nox_kg"),
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


def _referans_karsilastirmasi(normal, ruzgar_optimum, en_iyi, yakit_fonksiyonu, tas_ms, arama_uzayi):
    """Kazancı ikiye ayırır: büyük daire -> rüzgâr-optimum (yalnız rüzgâr; risk
    yok sayılır) ve rüzgâr-optimum -> optimize rota (türbülanstan/kısıttan
    kaçınmanın bedeli). Yakıt/süre tasarrufu büyük daireye göre tek başına
    okunursa rüzgâr kazancını da içerir. ATS modunda 'normal' rota zaten rüzgâr
    optimum ATS yoludur, ayrı rüzgâr kazancı yoktur. Kaçınma yapılmadıysa (optimize
    = normal) bedel None: orada rota büyük dairede bırakılmıştır, rüzgâr-optimum
    değildir."""

    def _sure(a):
        return a["saniye"] + a["ekstra_saniye"]

    def _yuzde(a, b):
        return 100.0 * (yakit_fonksiyonu(a) - yakit_fonksiyonu(b)) / yakit_fonksiyonu(b) if yakit_fonksiyonu(b) else 0.0

    ayri = ruzgar_optimum is not normal
    kacinildi = en_iyi is not normal
    return {
        "referans": "ruzgar_optimum_koridor" if ayri else ("ats_planli" if arama_uzayi == "ats" else "buyuk_daire"),
        "ruzgar_optimum_rota": (
            {
                **_rota_ozeti(ruzgar_optimum, yakit_fonksiyonu(ruzgar_optimum), _sure(ruzgar_optimum)),
                "maks_yanal_sapma_km": ruzgar_optimum["yanal_sapma_km"],
                "maks_yanal_sapma_yonu": yanal_sapma_yonu(ruzgar_optimum["enlem"], ruzgar_optimum["boylam"]),
                "ortalama_ruzgar_bileseni_kt": _ortalama_ruzgar_bileseni_kt(ruzgar_optimum, tas_ms),
            }
            if ayri
            else None
        ),
        "ruzgar_kazanci": (
            {
                "sure_dk": (_sure(normal) - _sure(ruzgar_optimum)) / 60.0,
                "yakit_yuzde": -_yuzde(ruzgar_optimum, normal),
            }
            if ayri
            else None
        ),
        "kacinma_bedeli": (
            {
                "ek_sure_dk": (_sure(en_iyi) - _sure(ruzgar_optimum)) / 60.0,
                "ek_yakit_yuzde": _yuzde(en_iyi, ruzgar_optimum),
            }
            if kacinildi
            else None
        ),
    }


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
        "tahmini_nox_kg": aday.get("tahmini_nox_kg"),
        "irtifa_ft": _ucus_seviyesi(aday["irtifa_m"]) * 100,
        "maks_ti1": aday["maks_ti1"],
        "riskli_nokta_sayisi": _riskli_nokta_sayisi(aday),
        "iz_bulutu_nokta_sayisi": aday["iz_bulutu_sayisi"],
        "sigmet_ihlali_sayisi": aday["sigmet_ihlali"],
        "kisitli_saha_ihlali_sayisi": aday["kisitli_saha_ihlali"],
    }
