import numpy as np
import pandas as pd
import pytest

from turbulans_radar.analiz import zaman_ornekleme as zo

xr = pytest.importorskip("xarray")
pytestmark = pytest.mark.birim


def _kup(saat=13, tohum=0):
    rng = np.random.default_rng(tohum)
    zaman = pd.date_range("2019-01-01", periods=saat, freq="h")
    enlem, boylam, seviye = np.arange(42.0, 35.75, -0.25), np.arange(26.0, 32.25, 0.25), [300.0, 250.0, 200.0]
    sekil = (len(zaman), len(seviye), len(enlem), len(boylam))
    egilim = np.linspace(0, 1, len(zaman))[:, None, None, None]
    return xr.Dataset(
        {
            "u": (("valid_time", "pressure_level", "latitude", "longitude"), 30 * egilim + rng.normal(20, 8, sekil)),
            "v": (("valid_time", "pressure_level", "latitude", "longitude"), rng.normal(0, 8, sekil)),
            "t": (("valid_time", "pressure_level", "latitude", "longitude"), rng.normal(220, 2, sekil)),
        },
        coords={"valid_time": zaman, "pressure_level": seviye, "latitude": enlem, "longitude": boylam},
    )


def test_bir_saatlik_adim_saatlikle_ozdes_uc_saatlik_farkli():
    kup = _kup()
    noktalar = zo.rastgele_noktalar(kup, 400, tohum=1)
    assert noktalar["enlem"].between(36.5, 41.5).all() and noktalar["boylam"].between(26.5, 31.5).all()
    rapor = zo.olcum_yap(kup, noktalar, adimlar=(1, 3), esik=1e-7)
    bir, uc = rapor["adimlar"]["1_saat"], rapor["adimlar"]["3_saat"]
    assert bir["spearman"] == pytest.approx(1.0) and bir["ayni_karar_orani"] == 1.0
    assert bir["medyan_mutlak_log10_fark"] == pytest.approx(0.0)
    assert uc["spearman"] < 1.0 and uc["nokta"] > 300
    metin = zo.markdown_ozeti(
        {"kup": "k.nc", "nokta_sayisi": 400, "fl": [310, 380], "commit": None, "uretim_zamani": "t", **rapor}
    )
    assert "| 3 sa |" in metin and "sertifikalı EDR değildir" in metin
