import math

import numpy as np
import pytest
import xarray as xr

from turbulans_radar.fizik.turbulans_indeksleri import (
    dusey_ruzgar_kaymasi_hesapla,
    ti1_den_edr_proxy_olcegine_cevir,
    ti1_indeksi_hesapla,
    yatay_deformasyon_hesapla,
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


def test_diverjans_ve_deformasyon_dogrusal_alanda_analitik_degere_esittir():
    from turbulans_radar.fizik.turbulans_indeksleri import (
        DUNYA_YARICAPI_M,
        METRE_PER_DERECE_ENLEM,
        _metre_per_derece_boylam,
        yatay_diverjans_hesapla,
    )

    u, v = _dogrusal_ruzgar_alani()
    dudx = 2.0 / _metre_per_derece_boylam(u["latitude"])
    dvdy = 3.0 / METRE_PER_DERECE_ENLEM
    metrik = np.tan(np.deg2rad(u["latitude"])) / DUNYA_YARICAPI_M
    gerilme = dudx - dvdy - v * metrik
    kayma = u * metrik
    np.testing.assert_allclose(
        yatay_diverjans_hesapla(u, v).values, (dudx + dvdy - v * metrik).broadcast_like(u).values, rtol=1e-9
    )
    np.testing.assert_allclose(
        yatay_deformasyon_hesapla(u, v).values, np.sqrt(gerilme**2 + kayma**2).broadcast_like(u).values, rtol=1e-9
    )


def test_ti2_diverjans_sifirken_ti1e_esit_yakinsamada_buyuk_olur():
    from turbulans_radar.fizik.turbulans_indeksleri import ti2_indeksi_hesapla

    vws, deformasyon = np.array([0.01, 0.01]), np.array([2e-5, 2e-5])
    ti2 = ti2_indeksi_hesapla(vws, deformasyon, np.array([0.0, -1e-5]))
    np.testing.assert_allclose(ti2, [ti1_indeksi_hesapla(0.01, 2e-5), 0.01 * 3e-5])


def _kuresel_alan(enlem_min, enlem_maks, boylam_min, boylam_maks, u_fonk, v_fonk):
    lat = np.arange(enlem_maks, enlem_min - 1e-9, -0.25)
    lon = np.arange(boylam_min, boylam_maks + 1e-9, 0.25)
    lam, phi = np.meshgrid(np.deg2rad(lon), np.deg2rad(lat))
    koordinat = {"latitude": lat, "longitude": lon}
    boyut = ["latitude", "longitude"]
    return (
        xr.DataArray(u_fonk(phi, lam), coords=koordinat, dims=boyut),
        xr.DataArray(v_fonk(phi, lam), coords=koordinat, dims=boyut),
    )


def _ic(alan):
    return alan.isel(latitude=slice(1, -1), longitude=slice(1, -1))


def test_kati_cisim_donmesinde_deformasyon_ve_diverjans_sifirdir():
    from turbulans_radar.fizik.turbulans_indeksleri import DUNYA_YARICAPI_M, yatay_diverjans_hesapla

    omega = 50.0 / DUNYA_YARICAPI_M
    for u_fonk, v_fonk in [
        (lambda phi, lam: omega * DUNYA_YARICAPI_M * np.cos(phi), lambda phi, lam: 0.0 * phi),
        (
            lambda phi, lam: -omega * DUNYA_YARICAPI_M * np.sin(phi) * np.cos(lam),
            lambda phi, lam: omega * DUNYA_YARICAPI_M * np.sin(lam),
        ),
    ]:
        u, v = _kuresel_alan(30.0, 55.0, -10.0, 30.0, u_fonk, v_fonk)
        assert float(np.abs(_ic(yatay_deformasyon_hesapla(u, v))).max()) < 0.01 * omega
        assert float(np.abs(_ic(yatay_diverjans_hesapla(u, v))).max()) < 0.01 * omega


def test_saf_gerilmede_deformasyon_2k_dir():
    from turbulans_radar.fizik.turbulans_indeksleri import DUNYA_YARICAPI_M

    k = 2e-5
    u, v = _kuresel_alan(
        -2.0,
        2.0,
        28.0,
        32.0,
        lambda phi, lam: k * DUNYA_YARICAPI_M * np.cos(phi) * (lam - np.deg2rad(30.0)),
        lambda phi, lam: -k * DUNYA_YARICAPI_M * phi,
    )
    np.testing.assert_allclose(_ic(yatay_deformasyon_hesapla(u, v)).values, 2 * k, rtol=0.01)


def test_dogrusal_kaymada_deformasyon_kayma_katsayisina_esittir():
    from turbulans_radar.fizik.turbulans_indeksleri import DUNYA_YARICAPI_M

    a = 3e-5
    u, v = _kuresel_alan(-2.0, 2.0, 28.0, 32.0, lambda phi, lam: a * DUNYA_YARICAPI_M * phi, lambda phi, lam: 0.0 * phi)
    np.testing.assert_allclose(_ic(yatay_deformasyon_hesapla(u, v)).values, a, rtol=0.01)


def test_hipsometrik_kalinlik_isa_yakininda_ve_sicaklikla_artar():
    from turbulans_radar.fizik.birim_donusumleri import basinc_hpa_to_irtifa_metre
    from turbulans_radar.fizik.turbulans_indeksleri import hipsometrik_kalinlik_m

    isa = float(basinc_hpa_to_irtifa_metre(225.0) - basinc_hpa_to_irtifa_metre(250.0))
    assert float(hipsometrik_kalinlik_m(225.0, 250.0, 216.65, 216.65)) == pytest.approx(isa, rel=0.01)
    assert hipsometrik_kalinlik_m(225.0, 250.0, 230.0, 230.0) > hipsometrik_kalinlik_m(225.0, 250.0, 210.0, 210.0)
