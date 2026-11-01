import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.birim

KAYNAK = Path(__file__).resolve().parents[1] / "docs" / "sunum" / "kaynak" / "komite_sunumu.html"
METIN = KAYNAK.read_text(encoding="utf-8")


def test_gorseller_goreli_ve_depoda_var():
    yollar = re.findall(r'src="([^"]+)"', METIN)
    assert yollar and not any(y.startswith("file:") for y in yollar)
    for yol in yollar:
        assert (KAYNAK.parent / yol).resolve().is_file(), yol


def test_bolum_ve_sayfa_numaralari_sirali():
    bolumler = [int(n) for n in re.findall(r'<div class="ust">(\d+) ·', METIN)]
    sayfalar = [int(n) for n in re.findall(r"Optimizasyonu</span><span>(\d+)</span>", METIN)]
    assert bolumler == list(range(1, len(bolumler) + 1))
    assert sayfalar == list(range(2, len(sayfalar) + 2))


def test_karar_destek_ve_edr_uyarisi_korunur():
    assert "karar destek aracıdır" in METIN and "sertifikalı EDR değildir" in METIN.replace(
        "Sertifikalı", "sertifikalı"
    )
