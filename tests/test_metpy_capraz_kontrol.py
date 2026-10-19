from pathlib import Path

import numpy as np
import pytest
import xarray as xr

from turbulans_radar.fizik.turbulans_indeksleri import (
    DUNYA_YARICAPI_M,
    yatay_deformasyon_hesapla,
    yatay_diverjans_hesapla,
)

mpcalc = pytest.importorskip("metpy.calc")

DEMO_KUPU = Path(__file__).resolve().parents[1] / "demo/era5/era5_THY322_2019-01-15.nc"
IC = (slice(1, -1), slice(1, -1))


def _metpy_alani(alan: xr.DataArray) -> xr.DataArray:
    return alan.assign_attrs(units="m/s").metpy.assign_crs(
        grid_mapping_name="latitude_longitude", earth_radius=DUNYA_YARICAPI_M
    )


@pytest.fixture(scope="module")
def seviyeler():
    kup = xr.load_dataset(DEMO_KUPU)
    return [
        kup.isel(valid_time=z).sel(pressure_level=p) for z in (0, kup.sizes["valid_time"] - 1) for p in (300.0, 200.0)
    ]


@pytest.mark.parametrize(
    ("bizim", "metpy_adi"),
    [(yatay_deformasyon_hesapla, "total_deformation"), (yatay_diverjans_hesapla, "divergence")],
)
def test_gercek_era5_alaninda_metpy_ile_ayni(seviyeler, bizim, metpy_adi):
    for seviye in seviyeler:
        beklenen = getattr(mpcalc, metpy_adi)(_metpy_alani(seviye.u), _metpy_alani(seviye.v))
        beklenen = beklenen.metpy.dequantify().values[IC]
        hesaplanan = bizim(seviye.u, seviye.v).values[IC]
        np.testing.assert_allclose(hesaplanan, beklenen, rtol=0, atol=1e-5 * np.abs(beklenen).max())
