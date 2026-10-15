import numpy as np
import pandas as pd
import xarray as xr

from turbulans_radar.ml import rf_deneyi


def test_altin_gunler_okumada_atilir():
    df = pd.DataFrame({"gun": ["2019-01-01", "2019-01-02", "2019-01-03"], "y": [0, 1, 0]})
    kalan = rf_deneyi.altin_gunlerini_at(df, ["2019-01-02"])
    assert kalan["gun"].tolist() == ["2019-01-01", "2019-01-03"]


def test_komsu_seviyeler_kenarda_kirpilir():
    seviyeler = [350.0, 300.0, 250.0, 200.0, 150.0]
    assert rf_deneyi._komsu_seviyeler(245.0, seviyeler) == [300.0, 250.0, 200.0]
    assert rf_deneyi._komsu_seviyeler(360.0, seviyeler) == [350.0, 300.0]


def test_en_sik_parametreler():
    secilen = [{"max_depth": 10, "n_estimators": 300}, {"n_estimators": 300, "max_depth": 10}, {"max_depth": None}]
    assert rf_deneyi.en_sik_parametreler(secilen) == {"max_depth": 10, "n_estimators": 300}


def test_ic_ice_cv_kat_disi_olasilik_ve_onem_uretir(monkeypatch):
    monkeypatch.setattr(rf_deneyi, "ARAMA_UZAYI", {"max_depth": [3, None], "n_estimators": [20]})
    rng = np.random.default_rng(0)
    gunler = np.repeat([f"g{i}" for i in range(12)], 25)
    X = pd.DataFrame({"ti1_indeksi": rng.random(300), "a": rng.random(300), "b": rng.random(300)})
    y = (X["ti1_indeksi"] + 0.3 * rng.random(300) > 0.65).astype(int).to_numpy()
    sonuc = rf_deneyi.ic_ice_cv(X, y, gunler, dis_kat=3, ic_kat=2, deneme=2, onem=True)
    for olasilik in sonuc["kat_disi"].values():
        assert np.isfinite(olasilik).all()
    assert len(sonuc["secilen_parametreler"]) == 3
    assert {o["ozellik"] for o in sonuc["onem"]} == {"ti1_indeksi", "a", "b"}


def test_baglam_ozellikleri_demo_kupunde_sonlu():
    with xr.open_dataset("demo/era5/era5_THY322_2019-01-15.nc") as kup:
        kup = kup.load()
    oz = rf_deneyi.baglam_ozellikleri(kup, pd.Timestamp("2019-01-15T20:00"), 41.0, 35.0, 10668.0)
    assert set(oz) == set(rf_deneyi.BAGLAM_SUTUNLARI)
    assert oz["ti1_komsu_maks"] >= oz["ti1_komsu_ort"] > 0
    assert 0 < oz["jet_orani"] <= 1 + 1e-9
    assert np.isfinite(oz["ri_kolon_min"]) and np.isfinite(oz["sicaklik_azalma_k_km"])
