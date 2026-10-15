import numpy as np
import pandas as pd
import pytest

from turbulans_radar.ml import tip_analizi


def test_rapordan_tip_ayrisir():
    assert tip_analizi.rapordan_tip("DEN UA /OV DEN /TM 1200 /FL350 /TP B738 /TB MOD") == "B738"
    assert tip_analizi.rapordan_tip("/TP A320/TB LGT") == "A320"
    assert tip_analizi.rapordan_tip("/OV ABC /TB NEG") is None


def test_kanat_yuku_openap_mtow_bolu_alan_ve_bilinmeyen_none():
    assert tip_analizi.kanat_yuku_kg_m2("A320") == pytest.approx(78000 / 124)
    assert tip_analizi.kanat_yuku_kg_m2("B757") is None


def test_analiz_katmanli_farki_ti1_dilimleri_icinde_olcer():
    rng = np.random.default_rng(0)
    n = 3000
    ti1 = rng.random(n)
    tip = rng.choice(["H", "O", "A"], n)
    kanat_yuku = pd.Series(tip).map({"H": 450.0, "O": 600.0, "A": 750.0}).to_numpy()
    y = (rng.random(n) < 0.2 + 0.5 * ti1 + 0.15 * (kanat_yuku == 750.0)).astype(int)
    df = pd.DataFrame(
        {"y": y, "ti1": ti1, "kanat_yuku": kanat_yuku, "gun": rng.choice([f"g{i}" for i in range(30)], n), "tip": tip}
    )
    sonuc = tip_analizi.analiz(df, tekrar=50)
    fark = sonuc["agir_eksi_hafif_katmanli_pozitif_orani"]
    assert fark["fark"] == pytest.approx(0.15, abs=0.06) and fark["anlamli"]
    assert set(sonuc["gruplar"]) == {"hafif", "orta", "agir"}
    assert sonuc["gruplar"]["agir"]["en_sik_tipler"] == {"A": int((tip == "A").sum())}
