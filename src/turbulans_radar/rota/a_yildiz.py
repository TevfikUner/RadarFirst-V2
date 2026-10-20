"""Yanal ızgara ve ATS ağı üzerinde A* araması (rota_optimizasyonu'ndan ayrıldı)."""

from __future__ import annotations

import heapq
import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

from turbulans_radar import config
from turbulans_radar.fizik.birim_donusumleri import irtifa_metre_to_basinc_hpa
from turbulans_radar.fizik.cografya import mesafe_km as buyuk_daire_mesafesi_km
from turbulans_radar.fizik.eslestirme import kapsam_disi_maskesi
from turbulans_radar.rota import hava_yolu_agi
from turbulans_radar.rota.geometri import _hedef_nokta, _ilk_yon_derece
from turbulans_radar.rota.risk_katmanlari import degerlendirmeleri_birlestir
from turbulans_radar.rota.ruzgar import _yer_hizi_ms, ruzgar_bilesenlerini_toplu_al


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
    belirsizlik = {d: _zaman_belirsizligi(nominal_zamanlar[d[0]] - nominal_zamanlar[0]) for d in dugumler}
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


def _ats_dugum_zamani(kalkis, bas, konum, tas_ms) -> pd.Timestamp:
    return kalkis + pd.Timedelta(seconds=buyuk_daire_mesafesi_km(*bas, *konum) * 1000.0 / tas_ms)


def _zaman_belirsizligi(gecen: pd.Timedelta) -> pd.Timedelta:
    return gecen * config.ROTA_ZAMAN_BELIRSIZLIK_ORANI + pd.Timedelta(minutes=config.ROTA_ZAMAN_BELIRSIZLIK_PAYI_DAKIKA)


def _ats_ile_rota_ara(
    ag, bas, bit, irtifa_m, baslangic_zamani, tas_ms, veri_kupu, risk_katmanlari=(), meydanlar=(None, None)
):
    """hava_yolu_agi grafında, ızgara aramasıyla AYNI maliyet (rüzgarlı süre +
    TI1 cezası) ve AYNI risk katmanlarıyla A*. Düğüm zamanı: ToC'den büyük daire
    uzaklığı / TAS (nominal); belirsizlik payı ızgarayla aynı. Hava küpünün
    kapsamadığı düğümler elenir. Dönüş: (enlemler, boylamlar, düğümler, yollar)
    ya da yol yoksa None."""
    kalkis = pd.Timestamp(baslangic_zamani)
    kalkis = kalkis.tz_localize("UTC") if kalkis.tzinfo is None else kalkis.tz_convert("UTC")
    tum_konumlar = {**ag.noktalar, hava_yolu_agi.BASLANGIC: bas, hava_yolu_agi.BITIS: bit}
    zamanlar = {d: _ats_dugum_zamani(kalkis, bas, k, tas_ms) for d, k in tum_konumlar.items()}
    belirsizlik = {d: _zaman_belirsizligi(t - kalkis) for d, t in zamanlar.items()}
    konumlar, komsular, kenarlar = hava_yolu_agi.arama_grafi(
        ag, bas, bit, irtifa_m / 0.3048, kalkis, {d: (t, t + belirsizlik[d]) for d, t in zamanlar.items()}, *meydanlar
    )
    for d in konumlar.keys() - zamanlar.keys():
        zamanlar[d] = _ats_dugum_zamani(kalkis, bas, konumlar[d], tas_ms)
        belirsizlik[d] = _zaman_belirsizligi(zamanlar[d] - kalkis)
    dugumler = list(konumlar)
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
