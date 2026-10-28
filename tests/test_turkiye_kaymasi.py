import numpy as np
import pandas as pd
import pytest

from turbulans_radar.ml import turkiye_kaymasi as tk
from turbulans_radar.ml.turbulans_ml_modeli import MODEL_OZELLIK_SUTUNLARI

pytestmark = pytest.mark.birim


def _ozellikler(n, kaydirma=0.0, tohum=0, gunler=("2019-01-05", "2019-07-05")):
    rng = np.random.default_rng(tohum)
    df = pd.DataFrame({s: rng.normal(kaydirma, 1.0, n) for s in MODEL_OZELLIK_SUTUNLARI})
    df["gun"] = np.resize(np.array(gunler), n)
    return df


def test_destek_disi_orani_yuzdelik_araligina_gore():
    referans = pd.DataFrame({"a": np.arange(1000.0)})
    guncel = pd.DataFrame({"a": [-5.0, 10.0, 500.0, 2000.0]})
    sonuc = tk.destek_disi_oranlari(referans, guncel, ["a"], yuzdelikler=(1, 99))
    assert sonuc["ozellikler"]["a"]["disarida_orani"] == pytest.approx(0.5)
    assert sonuc["herhangi_disarida_orani"] == pytest.approx(0.5)


def test_kaymis_turkiye_kontrolden_belirgin_ayrilir():
    abd = _ozellikler(4000, tohum=1, gunler=("2019-01-05", "2019-07-05", "2019-12-20", "2018-03-25"))
    turkiye = _ozellikler(2000, kaydirma=1.5, tohum=2)
    sonuc = tk.karsilastir(abd, turkiye, altin_gunleri={"2018-03-25"})
    assert sonuc["ornek"] == {"abd": 4000, "abd_kis": 2000, "turkiye": 2000}
    kontrol, kayma = sonuc["kontrol_abd_altin_egitim"], sonuc["turkiye_abd"]
    assert kontrol["durum"] == "kararli" and kayma["durum"] == "belirgin"
    assert kayma["destek"]["herhangi_disarida_orani"] > 5 * kontrol["destek"]["herhangi_disarida_orani"]
    metin = tk.markdown_ozeti({"meta": {"uretim_zamani": "t", "commit": None}, "veri": {"kup": "k.nc"}, "sonuc": sonuc})
    assert "Kontrol: ABD altın − eğitim günleri" in metin and "beceri ölçümü değildir" in metin


def test_turkiye_noktalari_ic_bolgede_ve_fl_bandinda():
    xr = pytest.importorskip("xarray")
    kup = xr.Dataset(
        coords={
            "valid_time": pd.date_range("2019-01-01", periods=48, freq="h"),
            "latitude": np.arange(42.0, 35.75, -0.25),
            "longitude": np.arange(26.0, 45.25, 0.25),
        }
    )
    noktalar = tk.turkiye_noktalari(kup, 500)
    assert noktalar["enlem"].between(36.5, 41.5).all() and noktalar["boylam"].between(26.5, 44.5).all()
    fl = noktalar["irtifa_m"] / 0.3048 / 100
    assert fl.between(*tk.FL_ARALIGI).all()
