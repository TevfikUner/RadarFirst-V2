from pathlib import Path

import numpy as np
import pytest
import xarray as xr

from turbulans_radar.fizik.turbulans_indeksleri import (
    DUNYA_YARICAPI_M,
    frontogenez_hesapla,
    potansiyel_sicaklik_hesapla,
    yatay_deformasyon_hesapla,
    yatay_diverjans_hesapla,
    yatay_vortisite_hesapla,
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


def test_vortisite_metpy_ile_ayni(seviyeler):
    for seviye in seviyeler:
        beklenen = mpcalc.vorticity(_metpy_alani(seviye.u), _metpy_alani(seviye.v)).metpy.dequantify().values[IC]
        hesaplanan = yatay_vortisite_hesapla(seviye.u, seviye.v).values[IC]
        np.testing.assert_allclose(hesaplanan, beklenen, rtol=0, atol=1e-5 * np.abs(beklenen).max())


def test_frontogenez_metpy_ile_ayni(seviyeler):
    for seviye in seviyeler:
        theta = potansiyel_sicaklik_hesapla(seviye.t, float(seviye.pressure_level))
        theta_mp = xr.DataArray(theta, coords=seviye.t.coords, dims=seviye.t.dims).assign_attrs(units="K")
        theta_mp = theta_mp.metpy.assign_crs(grid_mapping_name="latitude_longitude", earth_radius=DUNYA_YARICAPI_M)
        beklenen = mpcalc.frontogenesis(theta_mp, _metpy_alani(seviye.u), _metpy_alani(seviye.v))
        beklenen = beklenen.metpy.dequantify().values[IC]
        hesaplanan = frontogenez_hesapla(theta_mp.metpy.dequantify(), seviye.u, seviye.v).values[IC]
        np.testing.assert_allclose(hesaplanan, beklenen, rtol=0, atol=1e-4 * np.abs(beklenen).max())
