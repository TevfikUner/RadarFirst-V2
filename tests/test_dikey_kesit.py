import numpy as np
import pandas as pd
import pytest
import xarray as xr

from turbulans_radar.rota.dikey_kesit import dikey_kesit

pytestmark = pytest.mark.birim


def _kup(seviyeler):
    lat = np.arange(42.0, 37.75, -0.25)
    lon = np.arange(27.0, 33.25, 0.25)
    zaman = pd.to_datetime(["2026-10-17T00:00", "2026-10-17T06:00"])
    sekil = (len(zaman), len(seviyeler), len(lat), len(lon))
    u = (
        30.0
        + np.linspace(0, 20, len(seviyeler))[None, :, None, None] * np.sin(np.radians(lon) * 30)[None, None, None, :]
    )
    u = np.broadcast_to(u, sekil).copy()
    t = np.broadcast_to(np.linspace(229.0, 216.0, len(seviyeler))[None, :, None, None], sekil).copy()
    boyutlar = ["valid_time", "pressure_level", "latitude", "longitude"]
    return xr.Dataset(
        {"u": (boyutlar, u), "v": (boyutlar, np.zeros(sekil)), "t": (boyutlar, t)},
        coords={"valid_time": zaman, "pressure_level": seviyeler, "latitude": lat, "longitude": lon},
    )


def test_kesit_seviye_ve_mesafe_boyutlari_kapsam_disi_seviye_bos():
    enlemler = np.linspace(40.0, 40.0, 6)
    boylamlar = np.linspace(28.0, 32.0, 6)
    zamanlar = list(pd.date_range("2026-10-17T01:00Z", periods=6, freq="10min"))
    kesit = dikey_kesit(
        enlemler, boylamlar, zamanlar, _kup([300.0, 250.0, 200.0]), 7e-7, fl_listesi=(150, 340, 400, 450)
    )
    assert kesit["fl"] == [150, 340, 400, 450]
    assert len(kesit["mesafe_nm"]) == 6 and kesit["mesafe_nm"][0] == 0.0 and kesit["mesafe_nm"][-1] > 100
    assert kesit["ti1"][0] is None and kesit["ti1"][3] is None
    assert len(kesit["ti1"][1]) == 6 and all(v is not None for v in kesit["ti1"][1])
    assert kesit["basinc_seviyeleri_hpa"] == [200.0, 250.0, 300.0]
    assert "3 basınç seviyesinden" in kesit["aciklama"]
    assert dikey_kesit(enlemler[:1], boylamlar[:1], zamanlar[:1], _kup([300.0, 250.0]), 7e-7) is None
