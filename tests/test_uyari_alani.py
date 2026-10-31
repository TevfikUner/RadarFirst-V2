import numpy as np
import pandas as pd
import pytest
import xarray as xr

from turbulans_radar.analiz import uyari_alani as ua


def _kup(zamanlar):
    rng = np.random.default_rng(0)
    enlem = np.arange(50.0, 39.75, -0.25)
    boylam = np.arange(-80.0, -69.75, 0.25)
    seviye = np.array([300.0, 250.0, 200.0])
    sekil = (len(zamanlar), len(seviye), len(enlem), len(boylam))
    temel_u = np.array([20.0, 35.0, 30.0])[None, :, None, None]
    koordinatlar = {"valid_time": zamanlar, "pressure_level": seviye, "latitude": enlem, "longitude": boylam}
    boyutlar = list(koordinatlar)
    return xr.Dataset(
        {
            "u": (boyutlar, temel_u + rng.normal(0, 3, sekil)),
            "v": (boyutlar, rng.normal(0, 3, sekil)),
            "t": (boyutlar, np.array([229.0, 222.0, 218.0])[None, :, None, None] + rng.normal(0, 0.5, sekil)),
        },
        coords=koordinatlar,
    )


@pytest.fixture(scope="module")
def kup():
    zamanlar = pd.date_range("2019-01-01", periods=16, freq="3h")
    return _kup(zamanlar)


def test_ti3_blok_basinda_tanimsiz_sonra_ti1den_buyuk(kup):
    noktalar = pd.DataFrame(
        {
            "zaman": pd.to_datetime(
                ["2019-01-01T00:00Z", "2019-01-01T03:00Z", "2019-01-01T06:00Z", "2019-01-01T07:10Z"]
            ),
            "enlem": [45.0] * 4,
            "boylam": [-75.0] * 4,
            "baro_irtifa_m": [10363.2] * 4,
        }
    )
    skor = ua.skorlari_hesapla(noktalar, kup, ua.diverjans_kupu(kup))
    assert skor["TI3"].isna().tolist() == [True, True, False, False]
    assert (skor["TI3"].iloc[2:] >= skor["TI1"].iloc[2:]).all()
    assert skor["kup_zaman_farki_dk"].tolist() == pytest.approx([0, 0, 0, 70])
    assert skor["gun"].unique().tolist() == ["2019-01-01"]


def test_izgara_noktalari_ic_hucreler(kup):
    noktalar = ua.izgara_noktalari(kup, "2019-01-01")
    assert len(noktalar) == 8 * len(ua.FL_LISTESI) * 39 * 39
    assert noktalar["enlem"].max() == pytest.approx(49.75) and noktalar["boylam"].min() == pytest.approx(-79.75)


def test_egri_ozeti_rastgele_ve_mukemmel():
    alan = np.linspace(0.05, 0.5, 10)
    assert ua.egri_ozeti(alan, alan)["auc_alan"] == pytest.approx(0.5)
    mukemmel = ua.egri_ozeti(alan, np.ones_like(alan))
    assert mukemmel["auc_alan"] > 0.97 and mukemmel["pod_alan_10"] == pytest.approx(1.0)


def test_gunluk_sayimlar_ve_egri_raporu():
    rng = np.random.default_rng(3)
    gunler = [f"2019-01-{i:02d}" for i in range(1, 7)]
    izgara = pd.DataFrame({"gun": np.repeat(gunler, 200)})
    pirep = pd.DataFrame({"gun": np.repeat(gunler, 20), "sinif": np.tile([0, 1], 60)})
    for ad in ua.SKORLAR:
        izgara[ad] = rng.random(len(izgara))
        pirep[ad] = rng.random(len(pirep)) + 0.5 * pirep["sinif"]
    esikler = ua.esikleri_belirle(izgara)
    sayimlar = {ad: ua.gunluk_sayimlar(izgara, pirep, ad, esikler[ad], gunler) for ad in ua.SKORLAR}
    s = sayimlar["TI1"]
    assert s["izgara_n"].sum() == 1200 and s["m_n"].sum() == 60 and s["n_n"].sum() == 60
    alan, _, _ = ua._oranlar(s)
    assert alan[0] == pytest.approx(0.5, abs=0.01) and alan[-1] == pytest.approx(0.005, abs=0.005)
    rapor = ua.egri_raporu(sayimlar, esikler, tekrar=50)
    assert rapor["skorlar"]["TI1"]["auc_alan"] > 0.5
    assert set(rapor["farklar"]) == {"birlesik_edr - TI1", "TI3 - TI1"}
    assert len(rapor["skorlar"]["TI3"]["auc_alan_ga"]) == 2


def test_pirep_noktalari_kutu_ve_fl_suzgeci(monkeypatch):
    ham = pd.DataFrame(
        {
            "zaman": pd.to_datetime(["2019-01-01T01:00Z"] * 4),
            "enlem": [45.0, 45.0, 51.0, 45.0],
            "boylam": [-75.0, -75.0, -75.0, -75.0],
            "irtifa_ft": [35000.0, 29000.0, 35000.0, 39000.0],
            "sinif": [1, 0, 1, 0],
            "net": [1, 0, 1, 0],
        }
    )
    monkeypatch.setattr(ua, "arsiv_pireplerini_oku", lambda gunler, klasor=None: ham)
    sonuc = ua.pirep_noktalari(["2019-01-01"])
    assert sonuc["irtifa_ft"].tolist() == [35000.0, 39000.0]
    assert sonuc["baro_irtifa_m"].tolist() == pytest.approx([10668.0, 11887.2])
