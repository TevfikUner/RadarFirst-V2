import numpy as np

from turbulans_radar.ml import sonuc_paketi as sp
from turbulans_radar.ml.degerlendirme import guvenilirlik_tablosu


def test_guvenilirlik_svg_her_seri_icin_nokta_ve_kosegen_cizer():
    rng = np.random.default_rng(0)
    p = rng.uniform(0, 1, 500)
    y = (rng.uniform(0, 1, 500) < p).astype(int)
    svg = sp.guvenilirlik_svg({"A": guvenilirlik_tablosu(y, p), "B": guvenilirlik_tablosu(y, p * 0.5)}, "Başlık")
    assert svg.startswith("<svg") and svg.rstrip().endswith("</svg>")
    assert svg.count("<circle") == len(guvenilirlik_tablosu(y, p)) + len(guvenilirlik_tablosu(y, p * 0.5))
    assert "stroke-dasharray" in svg and "A (n=500)" in svg


def test_skor_karsilastirmasi_az_gunde_ga_vermez_cok_gunde_verir():
    rng = np.random.default_rng(1)
    y = rng.integers(0, 2, 300)
    skorlar = {"TI1": y + rng.normal(0, 1, 300), "Model": y + rng.normal(0, 0.5, 300)}
    az, *_ = sp._skor_karsilastirmasi(y, skorlar, np.repeat(["a", "b", "c"], 100), tekrar=20)
    assert "not" in az and "alt" not in az["skorlar"]["Model"]
    cok, *_ = sp._skor_karsilastirmasi(y, skorlar, np.repeat([f"g{i}" for i in range(10)], 30), tekrar=20)
    assert (
        "ti1_farki" in cok["skorlar"]["Model"] and cok["skorlar"]["Model"]["roc_auc"] > cok["skorlar"]["TI1"]["roc_auc"]
    )


def test_gecersiz_skorlu_satirlar_atilir():
    y = np.array([0, 1, 0, 1, 1, 0])
    skorlar = {"TI1": np.array([0.1, 0.9, np.nan, 0.8, 0.7, 0.2]), "Model": np.arange(6.0)}
    sonuc, yy, *_ = sp._skor_karsilastirmasi(y, skorlar, np.array(list("aabbcc")))
    assert sonuc["ornek"] == 5 and len(yy) == 5
