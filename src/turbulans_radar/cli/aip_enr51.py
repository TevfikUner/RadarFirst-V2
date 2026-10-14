"""
aip_enr51.py
---------------
AIP Türkiye ENR 5.1 (yasak P, tahditli R, tehlikeli D sahalar) PDF'inden
kisitli_saha_saglayici GeoJSON'u (hoca önerisi 2). Veri uydurulmaz: yalnızca
biçimi kesin olan sahalar alınır, belirsizler gerekçesiyle "atlandi" listesine
yazılır ve elle girilmelidir (docs/veri_hazirlama/ATS_AGI_HAZIRLAMA.md §2).

Kesin sayılan biçimler:
  - çokgen: yalnızca koordinat listesi (en az 3 köşe; kapanış köşesinin tekrarı
    ve Türkçe/İngilizce aynı listenin iki kez yazılması tek listeye indirilir)
  - daire  : "Centered on <koordinat>" + "Radius <x> NM|M" -> 32 köşeli çokgen
  - tek üst sınır (FL / FT AMSL|MSL / UNL), alt sınır SFC|MSL|GND; zaman
    ifadesinden sonraki açıklamalardaki seviyeler sınır sayılmaz
  - IFR/VFR için ayrı sınır ("*For IFR Traffic" dipnotlu): IFR sınırı alınır
    (sistem IFR seyir trafiğini modeller); dipnot yoksa atlanır
  - zaman: H24 (her zaman), "Daily HHMM-HHMM [UTC]" (haftalık takvim; AIP
    saatleri UTC'dir), "Daily SR/SS" ve "Activated by NOTAM" (gün doğumu/batımı
    ve NOTAM verisi yokken muhafazakâr: sürekli aktif)
  - "FIR hududunu takiben" kenarı: AIP Ege'deki İstanbul FIR hattını kesin
    koordinatsız "teorik hat" olarak tanımlar (ENR 2.1); bu kenar
    veri/fir_sinirlari'nin YAKLAŞIK FIR sınırıyla kapatılır ve açıklamaya
    yazılır. FIR verisi yoksa atlanır.
Atlananlar: AGL sınırlar, birden çok alt bölge ya da tanınmayan zaman ifadesi.

    turbulans-aip-sahalar --indir
    turbulans-aip-sahalar --enr51 ats_verisi/kaynak/LT_ENR_5_1_en.pdf
    turbulans-kisitli-saha ice-aktar ats_verisi/aip_enr51.geojson --kaynak aip_enr51
"""

import argparse
import json
import math
import os
import re
from pathlib import Path

from turbulans_radar.cli.aip_ats_agi import _AIRAC, airac_alanlari, koordinat_cevir, pdf_metni

ENR51_URL = "https://www.dhmi.gov.tr/AIPDocuments/LT_ENR_5_1_en.pdf"
VARSAYILAN_PDF = os.path.join("ats_verisi", "kaynak", "LT_ENR_5_1_en.pdf")
VARSAYILAN_CIKTI = os.path.join("ats_verisi", "aip_enr51.geojson")

_SAHA = re.compile(r"(?m)^(LT([PRD])\s?(\d+[A-Z]?))\s+(.+)$")
_KOOR = re.compile(r"(\d{6}(?:\.\d+)?)([NS])\s*-?\s*(\d{7}(?:\.\d+)?)([EW])")
_LIMIT = re.compile(r"\b(FL\s?(\d{3})|(\d{3,6})\s?FT\s?(AMSL|MSL|AGL)|UNL)\b")
_YARICAP = re.compile(r"(?i)radius\s+(?:of\s+)?(\d+(?:\.\d+)?)\s*(NM|M)\b")
_GUNLUK = re.compile(r"(?i)daily\s+(\d{4})\s*-\s*(\d{4})(?:\s*UTC)?")
_GUNES = re.compile(r"(?i)\bSR\s*[/-]\s*SS\b")
_ZAMAN = re.compile(r"(?i)\bH24\b|\bdaily\b|\bnotam\b")
_DIPNOT = re.compile(r"(?im)^\s*(\*{1,2})\s*for\s+(IFR|VFR)\b")
_FIR_KODU = {"istanbul": "LTBB", "ankara": "LTAA"}
_TUR = {"P": "YASAK", "R": "KISITLI", "D": "TEHLIKELI"}
_DAIRE_KOSE = 32


def _daire(enlem, boylam, yaricap_km):
    kos = math.cos(math.radians(enlem))
    halka = [
        [
            round(boylam + yaricap_km / (111.32 * kos) * math.sin(2 * math.pi * i / _DAIRE_KOSE), 6),
            round(enlem + yaricap_km / 110.57 * math.cos(2 * math.pi * i / _DAIRE_KOSE), 6),
        ]
        for i in range(_DAIRE_KOSE)
    ]
    return halka + [halka[0]]


def _limit_ft(m) -> int | None:
    if m.group(0) == "UNL":
        return None
    if m.group(2):
        return int(m.group(2)) * 100
    return int(m.group(3))


def _tekil_koseler(koordinatlar: list) -> list:
    if len(koordinatlar) > 3 and koordinatlar[0] == koordinatlar[-1]:
        koordinatlar = koordinatlar[:-1]
    yari = len(koordinatlar) // 2
    if len(koordinatlar) % 2 == 0 and yari >= 2 and koordinatlar[:yari] == koordinatlar[yari:]:
        koordinatlar = koordinatlar[:yari]
    return koordinatlar


def _ifr_siniri(govde: str):
    """(IFR üst sınır eşleşmesi, VFR sınır metni) ya da None."""
    dipnotlar = {isaret: tur.upper() for isaret, tur in _DIPNOT.findall(govde)}
    ifr = next((isaret for isaret, tur in dipnotlar.items() if tur == "IFR"), None)
    if ifr is None or len(dipnotlar) != 2:
        return None
    siniri = {}
    for isaret_m in re.finditer(r"(?mi)^\s*(\*{1,2})\s*(?!for\b)", govde):
        limit = _LIMIT.match(govde, isaret_m.end())
        if limit:
            siniri[isaret_m.group(1)] = limit
    if set(siniri) != set(dipnotlar):
        return None
    vfr = next(i for i in dipnotlar if i != ifr)
    return siniri[ifr], siniri[vfr].group(0)


def _fir_kenari(govde: str, koseler: list, fir_getirici):
    """Son köşeden ilk köşeye FIR sınırı boyunca giden kenarla kapatılmış köşe listesi.
    İki yönden geçerli çokgen veren ve alanı küçük olanı seçilir (öbür yön FIR'ın
    tamamını dolaşır). FIR verisi yoksa ya da geçerli çokgen çıkmazsa None."""
    from shapely.geometry import Polygon

    sade = govde.replace("İ", "i").replace("ı", "i").lower()
    kod = next((k for ad, k in _FIR_KODU.items() if ad in sade), None)
    geometri = fir_getirici(kod) if kod else None
    if geometri is None:
        return None
    halka = max(getattr(geometri, "geoms", [geometri]), key=lambda p: p.area).exterior.coords[:-1]

    def _en_yakin(nokta):
        return min(range(len(halka)), key=lambda i: (halka[i][1] - nokta[0]) ** 2 + (halka[i][0] - nokta[1]) ** 2)

    bas, bit = _en_yakin(koseler[-1]), _en_yakin(koseler[0])
    ileri = [halka[(bas + i) % len(halka)] for i in range((bit - bas) % len(halka) + 1)]
    geri = [halka[(bas - i) % len(halka)] for i in range((bas - bit) % len(halka) + 1)]
    adaylar = []
    for yol in (ileri, geri):
        ekler = [(round(y, 6), round(x, 6)) for x, y in yol[1:-1]]
        tum = koseler + [k for k in ekler if k not in koseler]
        cokgen = Polygon([(b, e) for e, b in tum])
        if cokgen.is_valid:
            adaylar.append((cokgen.area, tum))
    return min(adaylar)[1] if adaylar else None


def _varsayilan_fir(kod):
    from turbulans_radar.veri.fir_sinirlari import fir_geometrisi

    return fir_geometrisi(kod)


def saha_ayristir(
    kimlik: str, tur_harfi: str, ad: str, govde: str, fir_getirici=_varsayilan_fir
) -> tuple[dict | None, str | None]:
    """(GeoJSON Feature, None) ya da (None, atlanma gerekçesi)."""
    notlar = []
    if "*" in govde:
        ifr = _ifr_siniri(govde)
        if ifr is None:
            return None, "IFR/VFR için ayrı sınırlar"
        ust, vfr_metni = ifr
        sinir_oncesi = govde[: govde.index("*")]
        notlar.append(f"IFR sınırı (VFR: {vfr_metni})")
    else:
        ilk_limit = _LIMIT.search(govde)
        zaman = _ZAMAN.search(govde, ilk_limit.end()) if ilk_limit else None
        limitler = list(_LIMIT.finditer(govde, 0, zaman.start() if zaman else len(govde)))
        if len({m.group(0).replace("\n", " ") for m in limitler}) != 1:
            return None, f"üst sınır belirsiz ({len(limitler)} sınır ifadesi)"
        ust = limitler[0]
        sinir_oncesi = govde[: ust.start()]
    if ust.group(4) == "AGL":
        return None, "AGL referanslı sınır"
    if not re.search(r"\b(SFC|MSL|GND)\b", govde[ust.end() :][:40]):
        return None, "alt sınır SFC/MSL/GND değil"
    koordinatlar = _tekil_koseler(
        [(koordinat_cevir(a, b, 2), koordinat_cevir(c, d, 3)) for a, b, c, d in _KOOR.findall(sinir_oncesi)]
    )
    if re.search(r"(?i)FIR\s*(hudud|bound)", govde):
        kapali = _fir_kenari(govde, koordinatlar, fir_getirici) if len(koordinatlar) >= 2 else None
        if kapali is None:
            return None, "FIR sınırını izleyen sınır (FIR verisi yok ya da birleştirilemedi)"
        koordinatlar = kapali
        notlar.append(
            "FIR kenarı YAKLAŞIK (VATSIM FIR sınırı; AIP ENR 2.1 bu hattı kesin koordinatsız teorik hat olarak tanımlar)"
        )
    yaricap = _YARICAP.search(govde)
    if re.search(r"(?i)cent(?:er|re)d?\s+on|merkez", sinir_oncesi):
        if not yaricap or len(set(koordinatlar)) != 1:
            return None, "daire tanımı belirsiz"
        km = float(yaricap.group(1)) * (1.852 if yaricap.group(2).upper() == "NM" else 0.001)
        halka = _daire(*koordinatlar[0], km)
        sekil = f"daire r={yaricap.group(1)} {yaricap.group(2)}"
    else:
        if len(koordinatlar) < 3 or len(set(koordinatlar)) != len(koordinatlar):
            return None, f"çokgen belirsiz ({len(koordinatlar)} köşe)"
        halka = [[b, e] for e, b in koordinatlar] + [[koordinatlar[0][1], koordinatlar[0][0]]]
        sekil = f"çokgen {len(koordinatlar)} köşe"
    zaman_kismi = govde[ust.end() :]
    ozellikler = {
        "kimlik": kimlik,
        "ad": f"{kimlik} {ad.strip()}",
        "tur": _TUR[tur_harfi],
        "taban_ft": None,
        "tavan_ft": _limit_ft(ust),
    }
    if re.search(r"\bH24\b", zaman_kismi):
        notu = "H24"
    elif gunluk := _GUNLUK.search(zaman_kismi):
        bas, bit = gunluk.groups()
        ozellikler["haftalik_takvim"] = [
            {"gunler": [1, 2, 3, 4, 5, 6, 7], "baslangic": f"{bas[:2]}:{bas[2:]}", "bitis": f"{bit[:2]}:{bit[2:]}"}
        ]
        notu = f"günlük {bas}-{bit} UTC"
    elif _GUNES.search(zaman_kismi):
        notu = "günlük gün doğumu-batımı (SR/SS); tarihe göre değiştiği için sürekli aktif sayıldı (muhafazakâr)"
    elif re.search(r"(?i)notam", zaman_kismi):
        notu = "NOTAM ile aktiflenir; NOTAM verisi yokken sürekli aktif sayıldı (muhafazakâr)"
    else:
        return None, "aktif zaman ifadesi tanınmadı"
    ozellikler["aciklama"] = "; ".join([f"AIP Türkiye ENR 5.1; {sekil}; {notu}", *notlar])
    return {"type": "Feature", "properties": ozellikler, "geometry": {"type": "Polygon", "coordinates": [halka]}}, None


def metni_ayristir(metin: str, fir_getirici=_varsayilan_fir) -> tuple[list[dict], list[dict], str | None]:
    bloklar = [m for m in _SAHA.finditer(metin) if not m.group(4).startswith(",")]
    ozellikler, atlananlar = [], []
    for sira, m in enumerate(bloklar):
        govde = metin[m.end() : bloklar[sira + 1].start() if sira + 1 < len(bloklar) else len(metin)]
        govde = _AIRAC.split(govde)[0]
        kimlik = f"LT{m.group(2)}{m.group(3)}"
        ozellik, neden = saha_ayristir(kimlik, m.group(2), m.group(4), govde, fir_getirici)
        if ozellik:
            ozellikler.append(ozellik)
        else:
            atlananlar.append({"kimlik": kimlik, "ad": m.group(4).strip(), "neden": neden})
    surumler = [(int(yy), int(mm)) for mm, yy in _AIRAC.findall(metin)]
    en_yeni = max(surumler) if surumler else None
    return ozellikler, atlananlar, (f"{en_yeni[1]:02d}/{en_yeni[0]:02d}" if en_yeni else None)


def ana(argv=None):
    ayristirici = argparse.ArgumentParser(description="AIP Türkiye ENR 5.1'den kısıtlı saha GeoJSON'u.")
    ayristirici.add_argument("--enr51", default=VARSAYILAN_PDF)
    ayristirici.add_argument("--indir", action="store_true", help="ENR 5.1'i DHMİ'den indir (tek istek).")
    ayristirici.add_argument("--cikti", default=VARSAYILAN_CIKTI)
    argumanlar = ayristirici.parse_args(argv)
    if argumanlar.indir:
        from turbulans_radar.cli.aip_ats_agi import indir

        print("İndirildi:", indir(argumanlar.enr51, ENR51_URL))
    metin = pdf_metni(argumanlar.enr51)
    ozellikler, atlananlar, airac = metni_ayristir(metin)
    tarihler = airac_alanlari([metin])
    Path(argumanlar.cikti).parent.mkdir(parents=True, exist_ok=True)
    Path(argumanlar.cikti).write_text(
        json.dumps(
            {"type": "FeatureCollection", "airac": airac, **tarihler, "features": ozellikler},
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    print(
        f"{len(ozellikler)} saha alındı, {len(atlananlar)} atlandı (AIRAC {airac}, yürürlük "
        f"{tarihler['airac_yururluk']}, bitiş {tarihler['airac_bitis']}) -> {argumanlar.cikti}"
    )
    for a in atlananlar:
        print(f"  ATLANDI {a['kimlik']} {a['ad']}: {a['neden']} -- elle girin")


if __name__ == "__main__":
    ana()
