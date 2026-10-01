"""
aip_ats_agi.py
-----------------
AIP Türkiye ENR 4.4 (önemli noktalar: ad, koordinat, bağlı ATS yolları, FRA
rolü) PDF'inden hava_yolu_agi.py biçiminde bir FRA ağı üretir (hoca önerisi 1).
Veri uydurulmaz: her nokta doğrudan resmi tablodan gelir; çıktı ve indirilen
PDF depoya konmaz (ats_verisi/ .gitignore'da; yeniden dağıtım izni doğrulanmadı).

FRA rolleri (ENR 4.4 açıklaması): E yatay giriş, X yatay çıkış, I ara nokta,
A varış bağlantısı, D kalkış bağlantısı (EX, AD birleşik).

Kurulan ağ: FRA rolü olan tüm noktalar arasında dct_maks_km'ye kadar doğrudan
(DCT) kenarlar, FRA alt sınırından itibaren (varsayılan FL305; DHMİ duyurusu,
AIP FRA kurallarından doğrulanmalı). ENR 4.4 hava yollarının nokta SIRASINI
vermediği için klasik/RNAV yolları (ENR 3.1/3.2) bu araçla kurulmaz; FRA alt
sınırının altındaki seviyelerde ATS modu rota bulamaz (dürüstçe hata verir).

    turbulans-aip-ats --indir                       (ENR 4.4'ü DHMİ'den tek istekle indirir)
    turbulans-aip-ats --enr44 ats_verisi/kaynak/LT_ENR_4_4_en.pdf
"""

import argparse
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path

ENR44_URL = "https://www.dhmi.gov.tr/AIPDocuments/LT_ENR_4_4_en.pdf"
VARSAYILAN_PDF = os.path.join("ats_verisi", "kaynak", "LT_ENR_4_4_en.pdf")
VARSAYILAN_CIKTI = os.path.join("ats_verisi", "ats_agi.json")

_KAYIT = re.compile(r"(?m)^([A-Z]{5})\s+(\d{6}(?:\.\d+)?)([NS])\s*-\s*(\d{7}(?:\.\d+)?)([EW])")
_FRA = re.compile(r"FRA \(([A-Z]+)\)")
_AIRAC = re.compile(r"AIRAC AMDT (\d{2})/(\d{2})")
_YOL = re.compile(r"\b(?:[A-Z]/)?U?[A-Z]{1,2}\d{1,4}\b")
_ROLLER = {"E", "X", "I", "A", "D"}


def koordinat_cevir(deger: str, yon: str, derece_basamak: int) -> float:
    """DDMMSS(.ss) / DDDMMSS(.ss) -> ondalık derece; S ve W negatif."""
    tam, _, kesir = deger.partition(".")
    derece = int(tam[:derece_basamak])
    dakika = int(tam[derece_basamak : derece_basamak + 2])
    saniye = float(tam[derece_basamak + 2 :] + ("." + kesir if kesir else ""))
    if dakika >= 60 or saniye >= 60:
        raise ValueError(f"Geçersiz koordinat: {deger}")
    sonuc = derece + dakika / 60 + saniye / 3600
    return -sonuc if yon in "SW" else sonuc


def metni_ayristir(metin: str) -> tuple[list[dict], str | None]:
    """ENR 4.4 metninden kayıtlar ve en yeni AIRAC değişikliği ('MM/YY')."""
    eslesmeler = list(_KAYIT.finditer(metin))
    kayitlar = []
    for sira, m in enumerate(eslesmeler):
        govde = metin[m.end() : eslesmeler[sira + 1].start() if sira + 1 < len(eslesmeler) else len(metin)]
        govde = _AIRAC.split(govde)[0]
        roller = set()
        for etiket in _FRA.findall(govde):
            roller |= set(etiket) & _ROLLER
        yol_kismi = _FRA.split(govde)[0]
        kayitlar.append(
            {
                "ad": m.group(1),
                "enlem": round(koordinat_cevir(m.group(2), m.group(3), 2), 6),
                "boylam": round(koordinat_cevir(m.group(4), m.group(5), 3), 6),
                "yollar": sorted(set(_YOL.findall(yol_kismi))),
                "fir_siniri": "FIR BDRY" in yol_kismi,
                "fra_rolleri": sorted(roller),
            }
        )
    surumler = [(int(yy), int(mm)) for mm, yy in _AIRAC.findall(metin)]
    en_yeni = max(surumler) if surumler else None
    return kayitlar, (f"{en_yeni[1]:02d}/{en_yeni[0]:02d}" if en_yeni else None)


def pdf_metni(yol: str) -> str:
    try:
        import pypdf
    except ImportError:
        raise SystemExit("Bu araç pypdf ister: pip install -r requirements-dev.txt") from None

    return "\n".join(sayfa.extract_text() or "" for sayfa in pypdf.PdfReader(yol).pages)


def dogrula(kayitlar: list[dict]) -> list[str]:
    """Bariz hatalar (Türkiye çevresi dışı koordinat, tekrar eden ad)."""
    sorunlar = []
    gorulen = set()
    for k in kayitlar:
        if k["ad"] in gorulen:
            sorunlar.append(f"{k['ad']}: iki kez")
        gorulen.add(k["ad"])
        if not (33.0 <= k["enlem"] <= 44.5 and 24.0 <= k["boylam"] <= 46.0):
            sorunlar.append(f"{k['ad']}: Türkiye FIR'ları dışında görünen koordinat ({k['enlem']}, {k['boylam']})")
    return sorunlar


def fra_agi(kayitlar: list[dict], airac: str | None, dct_maks_km: float, alt_fl: float, ust_fl=None) -> dict:
    fra_noktalari = [k["ad"] for k in kayitlar if k["fra_rolleri"]]
    return {
        "kaynak": f"AIP Türkiye ENR 4.4, AIRAC AMDT {airac or '?'} (DHMİ), {datetime.now(UTC):%Y-%m-%d} ayrıştırıldı",
        "noktalar": [
            {"ad": k["ad"], "enlem": k["enlem"], "boylam": k["boylam"], "fra_rolleri": k["fra_rolleri"]}
            for k in kayitlar
        ],
        "yollar": [],
        "fra": {"noktalar": fra_noktalari, "dct_maks_km": dct_maks_km, "alt_fl": alt_fl, "ust_fl": ust_fl},
    }


def indir(hedef: str = VARSAYILAN_PDF, url: str = ENR44_URL) -> str:
    """Tek HTTP isteği (AIRAC döngüsünde, 28 günde bir yeterli)."""
    import httpx

    Path(hedef).parent.mkdir(parents=True, exist_ok=True)
    yanit = httpx.get(url, timeout=120, follow_redirects=True)
    yanit.raise_for_status()
    if not yanit.content.startswith(b"%PDF"):
        raise ValueError("İndirilen dosya PDF değil.")
    Path(hedef).write_bytes(yanit.content)
    return hedef


def ana(argv=None):
    ayristirici = argparse.ArgumentParser(description="AIP Türkiye ENR 4.4'ten FRA ağı (ats_verisi/ats_agi.json).")
    ayristirici.add_argument("--enr44", default=VARSAYILAN_PDF)
    ayristirici.add_argument("--indir", action="store_true", help="ENR 4.4'ü DHMİ'den indir (tek istek).")
    ayristirici.add_argument("--cikti", default=VARSAYILAN_CIKTI)
    ayristirici.add_argument("--dct-km", type=float, default=200.0, help="FRA noktaları arası en uzun DCT kenarı (km).")
    ayristirici.add_argument("--alt-fl", type=float, default=305.0, help="FRA alt sınırı (FL; doğrulanmalı).")
    argumanlar = ayristirici.parse_args(argv)
    if argumanlar.indir:
        print("İndirildi:", indir(argumanlar.enr44))
    kayitlar, airac = metni_ayristir(pdf_metni(argumanlar.enr44))
    sorunlar = dogrula(kayitlar)
    for sorun in sorunlar:
        print("[Uyarı]", sorun)
    ag = fra_agi(kayitlar, airac, argumanlar.dct_km, argumanlar.alt_fl)
    Path(argumanlar.cikti).parent.mkdir(parents=True, exist_ok=True)
    Path(argumanlar.cikti).write_text(json.dumps(ag, ensure_ascii=False, indent=1), encoding="utf-8")
    print(
        f"{len(kayitlar)} nokta ({len(ag['fra']['noktalar'])} FRA), AIRAC {airac}, {len(sorunlar)} uyarı -> "
        f"{argumanlar.cikti}"
    )


if __name__ == "__main__":
    ana()
