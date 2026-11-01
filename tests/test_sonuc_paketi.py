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


def _sahte_veri(monkeypatch, madis_var=True):
    import pandas as pd
    from sklearn.linear_model import LogisticRegression

    import turbulans_radar.ml.madis_hatti as mh
    import turbulans_radar.ml.ml_otomatik_egitim as moe
    import turbulans_radar.ml.turbulans_ml_modeli as tmm

    rng = np.random.default_rng(0)
    n = 300
    ti1 = rng.lognormal(np.log(3e-7), 1.0, n)
    X = pd.DataFrame(
        {
            "ti1_indeksi": ti1,
            "ti2_indeksi": ti1 * 0.9,
            "dusey_ruzgar_kaymasi": rng.lognormal(np.log(6e-3), 0.7, n),
            "yatay_deformasyon": rng.lognormal(np.log(5e-5), 0.7, n),
            "richardson_sayisi": rng.lognormal(np.log(5.0), 1.0, n),
        }
    )
    y = pd.Series((ti1 * rng.lognormal(0, 0.5, n) > 3e-7).astype(int))
    gunler = pd.Series(np.repeat([f"2026-01-{g:02d}" for g in range(1, 16)], n // 15))
    monkeypatch.setattr(moe, "veritabanindan_veri_hazirla", lambda motor: (X, y, gunler))
    monkeypatch.setattr(moe, "degerlendirme_gunleri_maskesi", lambda g: (g >= "2026-01-09", "test"))
    monkeypatch.setattr(tmm, "model_bilgisini_yukle", lambda: {"secilen_model": "Lojistik"})
    monkeypatch.setattr(
        sp,
        "_egitim_gunlerinde_model",
        lambda X_, y_, g_, egitim, isim: LogisticRegression().fit(np.log(X_[egitim]), y_[egitim]),
    )
    madis = X.iloc[:150].assign(
        max_edr=np.linspace(0.0, 0.4, 150),
        edr_sinifi=(np.arange(150) % 3 == 0).astype(int),
        gun=gunler.iloc[:150].to_numpy(),
    )
    monkeypatch.setattr(mh, "degerlendirme_verisi", lambda motor: madis if madis_var else pd.DataFrame())
    monkeypatch.setattr("turbulans_radar.depo.veritabani.motor_al", lambda: object())


class _LogOlasilik:
    def __init__(self, model):
        self.model = model

    def predict_proba(self, X):
        return self.model.predict_proba(np.log(X))


def test_calistir_pirep_holdout_ve_madis_bolumlerini_uretir(monkeypatch):
    _sahte_veri(monkeypatch)
    asil = sp._egitim_gunlerinde_model
    monkeypatch.setattr(sp, "_egitim_gunlerinde_model", lambda *a: _LogOlasilik(asil(*a)))
    rapor = sp.calistir(tekrar=10)
    assert rapor["model_turu"] == "Lojistik" and rapor["egitim"] == {"ornek": 160, "gun": 8}
    pirep = rapor["pirep_holdout_orta_ve_ustu"]
    assert pirep["holdout_yontemi"] == "test" and len(pirep["holdout_gunleri"]) == 7
    assert {"metrikler", "guvenilirlik", "brier_ga"} <= set(pirep["model"])
    assert rapor["madis_hafif_ve_ustu"]["egitim_gunleriyle_cakisan_gun"]


def test_cli_json_ve_svg_yazar_madis_yoksa_tek_seri(monkeypatch, tmp_path):
    import json

    _sahte_veri(monkeypatch, madis_var=False)
    asil = sp._egitim_gunlerinde_model
    monkeypatch.setattr(sp, "_egitim_gunlerinde_model", lambda *a: _LogOlasilik(asil(*a)))
    sp.ana(["--klasor", str(tmp_path), "--tekrar", "10", "--model-turu", "RF"])
    rapor = json.loads((tmp_path / "sonuc_paketi.json").read_text(encoding="utf-8"))
    assert rapor["model_turu"] == "RF" and "madis_hafif_ve_ustu" not in rapor
    svg = (tmp_path / "guvenilirlik_diyagrami.svg").read_text(encoding="utf-8")
    assert "PIREP holdout" in svg and "MADIS" not in svg
