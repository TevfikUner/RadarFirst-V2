import json
import re
from pathlib import Path

import pytest

from turbulans_radar.fizik.turbulans_indeksleri import TI1_GUVENILIRLIK_NOTU

KOK = Path(__file__).resolve().parents[1]
NIHAI = KOK / "docs/sonuclar/2026-10-18"
ON_PAKET = KOK / "docs/sonuclar/2026-10-07"
TARIHCE = re.compile(r"tarihçe|ön paket|[57] Eki|2026-10-0[57]|80 gün", re.IGNORECASE)
GA_DEGERI = re.compile(r"[+-]?\d,\d{3} \[[^\]]+\]")
BINLIK = re.compile(r"\b\d{1,3}\.\d{3}\b")


def guncel_belgeler() -> list[Path]:
    return sorted(
        {
            KOK / "README.md",
            KOK / "docs/KILAVUZ.md",
            KOK / "docs/SISTEM_KARTI.md",
            KOK / "docs/sonuclar/README.md",
            *(KOK / "docs/rapor").glob("*.md"),
            *(KOK / "docs/sunum").glob("*.md"),
            *(KOK / "docs/sunum").glob("*.html"),
        }
    )


def paket_degerleri(sayilar_md: Path) -> set[str]:
    degerler = set()
    for satir in sayilar_md.read_text(encoding="utf-8").splitlines():
        hucreler = [h.strip() for h in satir.split("|")]
        if len(hucreler) >= 5 and hucreler[-2].startswith("`"):
            degerler |= set(GA_DEGERI.findall(hucreler[2])) | set(BINLIK.findall(hucreler[2]))
    return degerler


def tarihce_baglaminda_mi(satirlar: list[str], sira: int) -> bool:
    if TARIHCE.search(satirlar[sira]):
        return True
    for i in range(sira, -1, -1):
        if satirlar[i].lstrip().startswith("#"):
            return any(TARIHCE.search(s) for s in satirlar[i : min(i + 4, sira + 1)])
    return False


def eski_sayi_bulgulari(belgeler, eski: set[str]) -> list[str]:
    bulgular = []
    for belge in belgeler:
        satirlar = belge.read_text(encoding="utf-8").splitlines()
        for sira, satir in enumerate(satirlar):
            for deger in sorted(d for d in eski if d in satir):
                if not tarihce_baglaminda_mi(satirlar, sira):
                    bulgular.append(f"{belge.relative_to(KOK)}:{sira + 1}: {deger}")
    return bulgular


def test_tarihce_baglami_baslik_ve_satirdan_okunur():
    satirlar = ["## 2. Model — tarihçe, 5 Ekim", "", "AUC 0,681 [0,646–0,716]", "## 3. Güncel", "0,681 [0,646–0,716]"]
    assert tarihce_baglaminda_mi(satirlar, 2)
    assert not tarihce_baglaminda_mi(satirlar, 4)
    assert tarihce_baglaminda_mi(["7 Eki ön paketi 0,681 [0,646–0,716]"], 0)


def test_paket_degerleri_yalniz_tablo_degerlerini_alir(tmp_path):
    md = tmp_path / "SAYILAR.md"
    md.write_text(
        "Kesme 1.234\n| Sayı | Değer | JSON |\n|---|---|---|\n"
        "| ROC | 0,708 [0,677–0,738] | `a` |\n| Örnek | 15.940 | `b` |\n",
        encoding="utf-8",
    )
    assert paket_degerleri(md) == {"0,708 [0,677–0,738]", "15.940"}


def test_guncel_belgelerde_on_paket_sayisi_yalniz_tarihce_baglaminda():
    yeni = paket_degerleri(NIHAI / "SAYILAR.md")
    eski = paket_degerleri(ON_PAKET / "SAYILAR.md") - yeni
    assert yeni and eski
    bulgular = eski_sayi_bulgulari(guncel_belgeler(), eski)
    assert not bulgular, "7 Ekim ön paketinin sayısı tarihçe bağlamı dışında:\n" + "\n".join(bulgular)


def test_ti1_guvenilirlik_notu_nihai_paketle_ayni():
    veri = json.loads((NIHAI / "sonuc_paketi.json").read_text(encoding="utf-8"))["veri"]
    assert f"{veri['ornek']} PIREP" in TI1_GUVENILIRLIK_NOTU
    assert f"[{veri['gun']} gün]" in TI1_GUVENILIRLIK_NOTU


@pytest.mark.parametrize("belge", ["docs/sonuclar/README.md", "docs/rapor/SONUCLAR.md"])
def test_nihai_paket_commiti_belgelerde(belge):
    commit = json.loads((NIHAI / "sonuc_paketi.json").read_text(encoding="utf-8"))["meta"]["commit"]
    assert commit[:7] in (KOK / belge).read_text(encoding="utf-8")
