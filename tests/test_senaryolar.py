import json
import re
from pathlib import Path

import pytest

KOK = Path(__file__).resolve().parents[1]
SENARYOLAR = json.loads((KOK / "web/veri/senaryolar.json").read_text(encoding="utf-8"))
SAYFA = (KOK / "web/ucus_simulasyonu.html").read_text(encoding="utf-8")

pytestmark = pytest.mark.birim


def test_senaryo_kimlikleri_benzersiz():
    kimlikler = [s["kimlik"] for s in SENARYOLAR]
    assert len(kimlikler) == len(set(kimlikler))


@pytest.mark.parametrize("senaryo", SENARYOLAR, ids=lambda s: s["kimlik"])
def test_senaryo_alanlari_sayfada_var_ve_gecerli(senaryo):
    alanlar = senaryo["alanlar"]
    for kimlik in alanlar:
        assert f'id="{kimlik}"' in SAYFA
    assert -90 <= float(alanlar["baslangic-enlem"]) <= 90 and -90 <= float(alanlar["bitis-enlem"]) <= 90
    assert -180 <= float(alanlar["baslangic-boylam"]) <= 180 and -180 <= float(alanlar["bitis-boylam"]) <= 180
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", alanlar["zaman"])
    assert senaryo["ad"] and senaryo["aciklama"]
