import numpy as np
import pandas as pd
import pytest

from turbulans_radar.ml import duyarlilik_analizi as da
from turbulans_radar.ml import ml_otomatik_egitim as me
from turbulans_radar.ml.ml_veri_hatti import pirep_anahtari
from turbulans_radar.ml.turbulans_ml_modeli import EK_OZELLIK_SUTUNLARI, MODEL_OZELLIK_SUTUNLARI


@pytest.mark.parametrize(
    "metin,beklenen",
    [
        ("NEG", 0),
        ("SMOOTH", 0),
        ("NEG CHOP", 0),
        ("LGT CHOP", None),
        ("CONT LT CHOP", None),
        ("MTW +", None),
        ("MOD", 1),
        ("OCNL MOD CHOP", 1),
        ("SEV", 1),
        ("LGT-MOD CHOP", None),
        ("CONT LGT OCNL MOD", None),
        ("NONE", None),
        (None, None),
    ],
)
def test_net_etiket_yalniz_net_metinleri_etiketler(metin, beklenen):
    assert da.net_etiket(metin) == beklenen


def test_iso_hafta_ve_ay_gruplari():
    gunler = pd.Series(["2018-12-31", "2019-01-06", "2019-01-07", "2019-02-01"])
    assert da.iso_hafta(gunler).tolist() == ["2019-W01", "2019-W01", "2019-W02", "2019-W05"]
    assert da.ay(gunler).tolist() == ["2018-12", "2019-01", "2019-01", "2019-02"]


def test_arsiv_net_etiketleri_anahtarla_eslesir_celiskiyi_eler(tmp_path):
    pd.DataFrame(
        {
            "VALID": ["201901010000", "201901010010", "201901010010", "201901010020", "201901010030"],
            "TURBULENCE": ["MOD", "NEG", "MOD", "LGT", "SMOOTH"],
            "FL": ["35000", "35000", "35000", "35000", "1000"],
            "LAT": ["40.0", "41.0", "41.0", "42.0", "43.0"],
            "LON": ["-100.0", "-101.0", "-101.0", "-102.0", "-103.0"],
        }
    ).to_csv(tmp_path / "a.csv", index=False)
    net = da.arsiv_net_etiketleri(str(tmp_path))
    pozitif = pirep_anahtari(pd.Timestamp("2019-01-01T00:00Z"), 40.0, -100.0, 35000)
    hafif = pirep_anahtari(pd.Timestamp("2019-01-01T00:20Z"), 42.0, -102.0, 35000)
    assert net[pozitif] == 1
    assert hafif in net.index and pd.isna(net[hafif])
    assert len(net) == 2


def _ornekler(gun_sayisi=40, gunluk=10, tohum=0):
    rng = np.random.default_rng(tohum)
    n = gun_sayisi * gunluk
    y = rng.integers(0, 2, n)
    X = pd.DataFrame(
        {
            "ti1_indeksi": (rng.normal(0, 1, n) + 0.6 * y) * 1e-7 + 5e-7,
            "richardson_sayisi": rng.normal(2, 1, n) - 2 * y,
            "ruzgar_hizi_ms": rng.normal(30, 5, n),
            "basinc_hpa": rng.choice([200.0, 250.0, 300.0], n),
            **{s: rng.normal(0, 1, n) for s in EK_OZELLIK_SUTUNLARI},
        }
    )[MODEL_OZELLIK_SUTUNLARI]
    bilgi = pd.DataFrame(
        {
            "anahtar": [f"k{i}" for i in range(n)],
            "ikili_etiket": y,
            "gun": np.repeat(pd.date_range("2019-01-01", periods=gun_sayisi).strftime("%Y-%m-%d"), gunluk),
        }
    )
    return X, bilgi


def test_gruplu_cv_duyarliligi_uc_gruplama_raporlar():
    X, bilgi = _ornekler(gun_sayisi=100, gunluk=4)
    sonuc = da.gruplu_cv_duyarliligi(X, pd.Series(bilgi["ikili_etiket"]), bilgi["gun"], kat_sayisi=3, tekrar_sayisi=1)
    gruplar = sonuc["gruplamalar"]
    assert list(gruplar) == ["gun", "iso_hafta", "ay"]
    assert gruplar["gun"]["grup_sayisi"] > gruplar["iso_hafta"]["grup_sayisi"] > gruplar["ay"]["grup_sayisi"]
    for g in gruplar.values():
        assert set(g["modeller"]) == {"Lojistik Regresyon", "Random Forest", "Gradient Boosting"}
        assert 0.5 < g["modeller"]["Lojistik Regresyon"]["roc_auc"] <= 1


def test_net_ornek_deneyi_altin_gunleri_egitime_sokmaz(monkeypatch):
    X, bilgi = _ornekler()
    altin = sorted(bilgi["gun"].unique())[::5]
    monkeypatch.setattr(me, "altin_test_gunleri", lambda yol=None: altin)
    net = bilgi.set_index("anahtar")["ikili_etiket"].astype(float)
    net[::3] = np.nan
    net = net.iloc[: len(net) // 2]
    sonuc = da.net_ornek_deneyi(X, bilgi, net)
    holdout = bilgi["gun"].isin(altin)
    assert sonuc["holdout"]["ornek"] == int(holdout.sum())
    varyant = sonuc["varyantlar"]
    assert varyant["tum"]["egitim_ornek"] == int((~holdout).sum())
    assert varyant["metinli"]["egitim_ornek"] == int((~holdout & bilgi["anahtar"].isin(net.index)).sum())
    assert varyant["net"]["egitim_ornek"] == int((~holdout & bilgi["anahtar"].map(net).notna()).sum())
    lr = varyant["net"]["modeller"]["Lojistik Regresyon"]
    assert {"roc_auc", "eksi_ti1", "eksi_tum", "eksi_metinli"} <= set(lr)
