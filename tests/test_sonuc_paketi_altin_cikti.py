"""Depodaki sonuç paketlerinin metin çıktıları, kendi JSON'larından bayt bayt yeniden üretilir.
Biçimlendirme kodu (sayilar_tablosu, guvenilirlik_svg) değişip yayımlanmış sayıları sessizce
değiştirirse bu test kırılır."""

import json
from pathlib import Path

import pytest

from turbulans_radar.ml.sonuc_disa_aktarimi import sayilar_tablosu
from turbulans_radar.ml.sonuc_paketi import guvenilirlik_svg

pytestmark = pytest.mark.birim

KOK = Path(__file__).resolve().parents[1]
PAKETLER = ["2026-10-18", "2026-10-18/ilk_uretim_sirasiz", "2026-10-07"]


@pytest.mark.parametrize("paket", PAKETLER)
def test_sayilar_md_jsondan_birebir_uretilir(paket):
    klasor = KOK / "docs" / "sonuclar" / paket
    veri = json.loads((klasor / "sonuc_paketi.json").read_text(encoding="utf-8"))
    assert sayilar_tablosu(veri) == (klasor / "SAYILAR.md").read_text(encoding="utf-8")


def test_rapor_guvenilirlik_diyagrami_jsondan_birebir_uretilir():
    klasor = KOK / "docs" / "rapor" / "veri"
    rapor = json.loads((klasor / "sonuc_paketi.json").read_text(encoding="utf-8"))
    seriler = {"PIREP holdout": rapor["pirep_holdout_orta_ve_ustu"]["model"]["guvenilirlik"]}
    if "madis_hafif_ve_ustu" in rapor:
        seriler["MADIS EDR ≥ 0,1"] = rapor["madis_hafif_ve_ustu"]["model"]["guvenilirlik"]
    beklenen = (klasor / "guvenilirlik_diyagrami.svg").read_text(encoding="utf-8")
    assert guvenilirlik_svg(seriler, "Güvenilirlik diyagramı (model olasılığı)") == beklenen
