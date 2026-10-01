"""
hava_yolu_agi.py
-------------------
ATS yolları / Serbest Rota Sahası (FRA) üzerinde graf tabanlı A* (hoca önerisi 1,
Doç. Dr. Fulya Aybek Çetek). Önemli noktalar düğüm, hava yolu segmentleri kenar;
FRA noktaları arasında belirli bir mesafeye kadar doğrudan (DCT) kenarlar.

Veri: config.ATS_AGI_DOSYASI (JSON; AIP Türkiye ENR 3 ve ENR 4.4'ten elle
hazırlanır, bkz. docs/veri_hazirlama/ATS_AGI_HAZIRLAMA.md). Depoya konmaz; bu
modül uydurma bir ağ içermez.

    {
      "kaynak": "AIP Türkiye, AIRAC 2610",
      "noktalar": [{"ad": "ABCDE", "enlem": 40.1, "boylam": 30.2}, ...],
      "yollar": [{"ad": "UL123", "noktalar": ["ABCDE", "FGHIJ", ...],
                  "alt_fl": 245, "ust_fl": 460, "yon": "cift"}],
      "fra": {"noktalar": ["ABCDE", ...], "dct_maks_km": 400, "alt_fl": 245, "ust_fl": 660}
    }

yon: "cift" (iki yön), "ileri" (listedeki sıra), "geri". alt_fl/ust_fl boşsa
sınır yok. Kalkış ve varış (ToC/ToD) ağa en yakın noktalara doğrudan bağlanır
(ATS_AGI_BAGLANTI_KM içinde en fazla ATS_AGI_BAGLANTI_SAYISI nokta).

Segmentler ATS_AGI_ARA_NOKTA_KM'den uzunsa ara noktalarla bölünür: TI1 ve
SIGMET/kısıtlı saha katmanları düğümlerde değerlendirildiği için uzun bir
segmentin ortasındaki risk atlanmasın diye.
"""

from __future__ import annotations

import heapq
import json
import math
from dataclasses import dataclass, field
from pathlib import Path

from turbulans_radar import config

_YONLER = ("cift", "ileri", "geri")


class AtsAgiHatasi(ValueError):
    pass


@dataclass
class Kenar:
    hedef: str
    yol: str
    alt_fl: float | None
    ust_fl: float | None


@dataclass
class HavaYoluAgi:
    kaynak: str
    noktalar: dict[str, tuple[float, float]]
    komsular: dict[str, list[Kenar]] = field(default_factory=dict)

    def kenar_ekle(self, a: str, b: str, yol: str, alt_fl=None, ust_fl=None):
        self.komsular.setdefault(a, []).append(Kenar(b, yol, alt_fl, ust_fl))


def mesafe_km(enlem1, boylam1, enlem2, boylam2) -> float:
    p1, p2 = math.radians(enlem1), math.radians(enlem2)
    dp, dl = p2 - p1, math.radians(boylam2 - boylam1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(min(1.0, a)))


def _ara_nokta(e1, b1, e2, b2, oran):
    p1, l1, p2, l2 = map(math.radians, (e1, b1, e2, b2))
    d = 2 * math.asin(
        math.sqrt(math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin((l2 - l1) / 2) ** 2)
    )
    if d == 0:
        return e1, b1
    a, b = math.sin((1 - oran) * d) / math.sin(d), math.sin(oran * d) / math.sin(d)
    x = a * math.cos(p1) * math.cos(l1) + b * math.cos(p2) * math.cos(l2)
    y = a * math.cos(p1) * math.sin(l1) + b * math.cos(p2) * math.sin(l2)
    z = a * math.sin(p1) + b * math.sin(p2)
    return math.degrees(math.atan2(z, math.hypot(x, y))), math.degrees(math.atan2(y, x))


def _fl(deger, alan, konum):
    if deger is None:
        return None
    if isinstance(deger, bool) or not isinstance(deger, int | float) or not 0 <= deger <= 700:
        raise AtsAgiHatasi(f"{konum}: '{alan}' 0-700 arası uçuş seviyesi (FL) ya da null olmalı")
    return float(deger)


def agi_kur(veri: dict, ara_nokta_km: float | None = None) -> HavaYoluAgi:
    """JSON sözlüğünden ağ; hatalı veride nerede olduğunu söyleyen AtsAgiHatasi."""
    ara_nokta_km = config.ATS_AGI_ARA_NOKTA_KM if ara_nokta_km is None else ara_nokta_km
    if not isinstance(veri, dict) or not isinstance(veri.get("noktalar"), list) or not veri["noktalar"]:
        raise AtsAgiHatasi("'noktalar' boş olmayan bir liste olmalı")
    noktalar = {}
    for sira, nokta in enumerate(veri["noktalar"]):
        try:
            ad, enlem, boylam = str(nokta["ad"]).strip().upper(), float(nokta["enlem"]), float(nokta["boylam"])
        except (KeyError, TypeError, ValueError):
            raise AtsAgiHatasi(f"noktalar[{sira}]: 'ad', 'enlem', 'boylam' gerekli") from None
        if not ad or not (-90 <= enlem <= 90 and -180 <= boylam <= 180):
            raise AtsAgiHatasi(f"noktalar[{sira}]: geçersiz ad ya da koordinat")
        if ad in noktalar:
            raise AtsAgiHatasi(f"noktalar[{sira}]: '{ad}' iki kez tanımlı")
        noktalar[ad] = (enlem, boylam)
    ag = HavaYoluAgi(kaynak=str(veri.get("kaynak") or "belirtilmedi"), noktalar=dict(noktalar))

    def segment_ekle(a, b, yol, alt_fl, ust_fl, yonler):
        (e1, b1), (e2, b2) = noktalar[a], noktalar[b]
        parca = max(1, math.ceil(mesafe_km(e1, b1, e2, b2) / ara_nokta_km)) if ara_nokta_km > 0 else 1
        zincir = [a]
        for i in range(1, parca):
            ara = f"{a}>{b}#{i}"
            ag.noktalar[ara] = _ara_nokta(e1, b1, e2, b2, i / parca)
            zincir.append(ara)
        zincir.append(b)
        for x, y in zip(zincir, zincir[1:]):
            if "ileri" in yonler:
                ag.kenar_ekle(x, y, yol, alt_fl, ust_fl)
            if "geri" in yonler:
                ag.kenar_ekle(y, x, yol, alt_fl, ust_fl)

    for sira, yol in enumerate(veri.get("yollar") or []):
        konum = f"yollar[{sira}]"
        if not isinstance(yol, dict) or not isinstance(yol.get("noktalar"), list) or len(yol["noktalar"]) < 2:
            raise AtsAgiHatasi(f"{konum}: 'noktalar' en az 2 nokta adı içermeli")
        ad = str(yol.get("ad") or f"YOL{sira}")
        yon = str(yol.get("yon") or "cift")
        if yon not in _YONLER:
            raise AtsAgiHatasi(f"{konum}: 'yon' şunlardan biri olmalı: {', '.join(_YONLER)}")
        alt_fl, ust_fl = _fl(yol.get("alt_fl"), "alt_fl", konum), _fl(yol.get("ust_fl"), "ust_fl", konum)
        if alt_fl is not None and ust_fl is not None and alt_fl > ust_fl:
            raise AtsAgiHatasi(f"{konum}: alt_fl ust_fl'den büyük olamaz")
        sirali = [str(n).strip().upper() for n in yol["noktalar"]]
        bilinmeyen = [n for n in sirali if n not in noktalar]
        if bilinmeyen:
            raise AtsAgiHatasi(f"{konum} ({ad}): tanımsız nokta(lar): {', '.join(bilinmeyen)}")
        yonler = {"cift": ("ileri", "geri"), "ileri": ("ileri",), "geri": ("geri",)}[yon]
        for a, b in zip(sirali, sirali[1:]):
            segment_ekle(a, b, ad, alt_fl, ust_fl, yonler)

    fra = veri.get("fra")
    if fra:
        fra_noktalari = [str(n).strip().upper() for n in fra.get("noktalar") or []]
        bilinmeyen = [n for n in fra_noktalari if n not in noktalar]
        if bilinmeyen:
            raise AtsAgiHatasi(f"fra: tanımsız nokta(lar): {', '.join(bilinmeyen)}")
        dct_km = float(fra.get("dct_maks_km") or 0)
        alt_fl, ust_fl = _fl(fra.get("alt_fl"), "alt_fl", "fra"), _fl(fra.get("ust_fl"), "ust_fl", "fra")
        for i, a in enumerate(fra_noktalari):
            for b in fra_noktalari[i + 1 :]:
                if mesafe_km(*noktalar[a], *noktalar[b]) <= dct_km:
                    segment_ekle(a, b, "DCT", alt_fl, ust_fl, ("ileri", "geri"))
    if not ag.komsular:
        raise AtsAgiHatasi("Ağda hiç segment yok ('yollar' ya da 'fra' gerekli)")
    return ag


def agi_yukle(yol: str | None = None) -> HavaYoluAgi | None:
    """Dosya yoksa None (ATS modu kullanılamaz); hatalıysa AtsAgiHatasi."""
    yol = Path(yol or config.ATS_AGI_DOSYASI)
    if not yol.is_file():
        return None
    try:
        veri = json.loads(yol.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as hata:
        raise AtsAgiHatasi(f"{yol} okunamadı: {hata}") from None
    return agi_kur(veri)


def _seviyede_mi(kenar: Kenar, fl: float) -> bool:
    return (kenar.alt_fl is None or kenar.alt_fl <= fl) and (kenar.ust_fl is None or fl <= kenar.ust_fl)


BASLANGIC, BITIS = "<ToC>", "<ToD>"


def uc_baglantilari(ag: HavaYoluAgi, enlem, boylam, maks_km=None, sayi=None) -> list[tuple[str, float]]:
    """(nokta, km) -- ToC/ToD'ye en yakın gerçek ağ noktaları (ara noktalar hariç)."""
    maks_km = config.ATS_AGI_BAGLANTI_KM if maks_km is None else maks_km
    sayi = config.ATS_AGI_BAGLANTI_SAYISI if sayi is None else sayi
    adaylar = sorted(
        (mesafe_km(enlem, boylam, e, b), ad)
        for ad, (e, b) in ag.noktalar.items()
        if "#" not in ad and ad in ag.komsular
    )
    return [(ad, km) for km, ad in adaylar if km <= maks_km][:sayi]


def arama_grafi(ag: HavaYoluAgi, bas, bit, irtifa_ft) -> tuple[dict, dict, list]:
    """A* için (konumlar, komsular, kenarlar): seviyeye uymayan segmentler
    çıkarılmış, ToC/ToD bağlantıları eklenmiş graf."""
    fl = irtifa_ft / 100.0
    konumlar = dict(ag.noktalar)
    konumlar[BASLANGIC], konumlar[BITIS] = bas, bit
    komsular = {a: [(k.hedef, k.yol) for k in kenarlar if _seviyede_mi(k, fl)] for a, kenarlar in ag.komsular.items()}
    komsular[BASLANGIC] = [(ad, "DCT") for ad, _ in uc_baglantilari(ag, *bas)]
    for ad, _ in uc_baglantilari(ag, *bit):
        komsular.setdefault(ad, []).append((BITIS, "DCT"))
    kenarlar = [(a, b) for a, hedefler in komsular.items() for b, _ in hedefler]
    return konumlar, komsular, kenarlar


def a_yildiz(komsular: dict, bas: str, bit: str, kenar_maliyeti, sezgisel, yasak_dugumler=(), yasak_kenarlar=()):
    """Genel A*: kenar_maliyeti(a, b) ve sezgisel(d) saniye. Dönüş: düğüm
    yolu ve yol üzerindeki kenarların adları; yol yoksa None."""
    if bas in yasak_dugumler or bit in yasak_dugumler:
        return None
    acik = [(sezgisel(bas), 0.0, bas)]
    maliyet = {bas: 0.0}
    ebeveyn: dict[str, tuple[str, str]] = {}
    kapali = set()
    while acik:
        _, g, dugum = heapq.heappop(acik)
        if dugum in kapali:
            continue
        kapali.add(dugum)
        if dugum == bit:
            break
        for komsu, yol in komsular.get(dugum, []):
            if komsu in yasak_dugumler or (dugum, komsu) in yasak_kenarlar or komsu in kapali:
                continue
            yeni = g + kenar_maliyeti(dugum, komsu)
            if yeni < maliyet.get(komsu, math.inf):
                maliyet[komsu] = yeni
                ebeveyn[komsu] = (dugum, yol)
                heapq.heappush(acik, (yeni + sezgisel(komsu), yeni, komsu))
    if bit not in ebeveyn and bit != bas:
        return None
    dugumler, yollar = [bit], []
    while dugumler[-1] != bas:
        onceki, yol = ebeveyn[dugumler[-1]]
        yollar.append(yol)
        dugumler.append(onceki)
    return dugumler[::-1], yollar[::-1]


def rota_ozeti(dugumler: list[str], yollar: list[str]) -> list[dict]:
    """Uçuş planı biçimine yakın özet: ara noktalar atılır, aynı yoldaki ardışık
    segmentler birleştirilir. [{"nokta": "ABCDE", "yol": "UL123" | "DCT" | None}]"""
    ozet = []
    for i, dugum in enumerate(dugumler):
        if "#" in dugum:
            continue
        gelen = yollar[i - 1] if i > 0 else None
        if ozet and gelen not in (None, "DCT") and gelen == ozet[-1]["yol"] and i < len(dugumler) - 1:
            ozet[-1]["nokta"] = dugum
            continue
        ozet.append({"nokta": dugum, "yol": gelen})
    return ozet
