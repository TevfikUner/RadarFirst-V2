import math

import numpy as np
import xarray as xr
import pytest

from turbulans_indeksleri import (
    yatay_deformasyon_hesapla,
    dusey_ruzgar_kaymasi_hesapla,
    ti1_indeksi_hesapla,
    ti1_den_edr_proxy_olcegine_cevir,
)


def _dogrusal_ruzgar_alani():
    """du/dx, du/dy, dv/dx, dv/dy sabit olacak şekilde dogrusal bir alan
    üretir; böylece differentiate() sonucunu elle hesaplayıp doğrulayabiliriz."""
    lat = np.linspace(38.0, 42.0, 5)
    lon = np.linspace(28.0, 32.0, 5)
    lon_grid, lat_grid = np.meshgrid(lon, lat)

    u = xr.DataArray(2.0 * lon_grid, coords={"latitude": lat, "longitude": lon}, dims=["latitude", "longitude"])
    v = xr.DataArray(3.0 * lat_grid, coords={"latitude": lat, "longitude": lon}, dims=["latitude", "longitude"])
    return u, v


def test_yatay_deformasyon_dogrusal_alan_icin_sabittir():
    u, v = _dogrusal_ruzgar_alani()
    deformasyon = yatay_deformasyon_hesapla(u, v)

    # Kenar noktaları haric (merkezi fark), degerler grid boyunca hemen hemen sabit olmali.
    ic_bolge = deformasyon.isel(latitude=slice(1, -1), longitude=slice(1, -1))
    assert float(ic_bolge.std()) < 1e-6
    assert float(ic_bolge.mean()) > 0


def test_dusey_ruzgar_kaymasi_sifir_farkta_sifirdir():
    vws = dusey_ruzgar_kaymasi_hesapla(u_ust=10, v_ust=5, u_alt=10, v_alt=5, yukseklik_farki_m=500)
    assert vws == 0


def test_dusey_ruzgar_kaymasi_beklenen_deger():
    # du=3, dv=4 -> |dV|=5; 500 m fark -> 5/500 = 0.01 s^-1
    vws = dusey_ruzgar_kaymasi_hesapla(u_ust=3, v_ust=4, u_alt=0, v_alt=0, yukseklik_farki_m=500)
    assert math.isclose(vws, 0.01, rel_tol=1e-9)


def test_dusey_ruzgar_kaymasi_sifir_yukseklik_farkinda_hata_verir():
    with pytest.raises(ValueError):
        dusey_ruzgar_kaymasi_hesapla(u_ust=1, v_ust=1, u_alt=0, v_alt=0, yukseklik_farki_m=0)


def test_ti1_indeksi_carpimdir():
    assert math.isclose(ti1_indeksi_hesapla(vws=2.0, deformasyon=3.0), 6.0)
    # VWS negatif olsa bile TI1 negatif olamaz (mutlak deger).
    assert ti1_indeksi_hesapla(vws=-2.0, deformasyon=3.0) == 6.0


def test_edr_proxy_sifirda_sifir_ve_0_1_araliginda_kalir():
    assert ti1_den_edr_proxy_olcegine_cevir(0.0) == 0.0
    for ti1 in [1e-8, 1e-7, 1e-6, 1e-5]:
        proxy = ti1_den_edr_proxy_olcegine_cevir(ti1)
        assert 0.0 <= proxy < 1.0


def test_edr_proxy_artan_ti1_ile_artar():
    onceki = 0.0
    for ti1 in [1e-8, 5e-8, 1e-7, 5e-7, 1e-6]:
        proxy = ti1_den_edr_proxy_olcegine_cevir(ti1)
        assert proxy > onceki
        onceki = proxy
