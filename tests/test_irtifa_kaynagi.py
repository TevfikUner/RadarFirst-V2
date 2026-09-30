import numpy as np
import pandas as pd
import xarray as xr

from turbulans_radar.fizik.eslestirme import rota_irtifalari_ve_kaynagi, rotayi_hava_durumuyla_eslestir


def _kup():
    zamanlar = pd.date_range("2019-01-15T19:00", periods=3, freq="h")
    enlemler, boylamlar = np.arange(43.0, 37.75, -0.25), np.arange(27.0, 33.25, 0.25)
    seviyeler = np.array([300.0, 250.0, 200.0])
    sekil = (3, 3, len(enlemler), len(boylamlar))
    rng = np.random.default_rng(1)
    return xr.Dataset(
        {
            ad: (
                ("valid_time", "pressure_level", "latitude", "longitude"),
                (t + rng.normal(0, 4, sekil)).astype("float32"),
            )
            for ad, t in (("u", 20.0), ("v", 5.0), ("t", 220.0))
        },
        coords={"valid_time": zamanlar, "pressure_level": seviyeler, "latitude": enlemler, "longitude": boylamlar},
    )


def _rota(geo, baro):
    n = len(geo)
    return pd.DataFrame(
        {
            "zaman": pd.to_datetime(["2019-01-15T20:00Z"] * n),
            "enlem": [40.0] * n,
            "boylam": [30.0] * n,
            "geo_irtifa_m": geo,
            "baro_irtifa_m": baro,
        }
    )


def test_baro_irtifa_oncelikli_yoksa_geoya_duser_ve_isaretlenir():
    irtifa, kaynak = rota_irtifalari_ve_kaynagi(_rota([11000.0, 10500.0, np.nan], [10400.0, np.nan, np.nan]))
    np.testing.assert_array_equal(irtifa, [10400.0, 10500.0, np.nan])
    assert list(kaynak) == ["baro", "geo", None]


def test_baro_sutunu_olmayan_rota_geo_kullanir():
    irtifa, kaynak = rota_irtifalari_ve_kaynagi(pd.DataFrame({"geo_irtifa_m": [9000.0]}))
    assert irtifa.tolist() == [9000.0] and list(kaynak) == ["geo"]


def test_seviye_secimi_baro_irtifaya_gore_yapilir_ve_ek_ozellikler_uretilir():
    sonuc = rotayi_hava_durumuyla_eslestir(_rota([9200.0], [10400.0]), _kup())
    assert sonuc.loc[0, "basinc_hpa"] == 250.0
    assert sonuc.loc[0, "irtifa_kaynagi"] == "baro"
    for sutun in ("dusey_ruzgar_kaymasi", "yatay_deformasyon", "yatay_diverjans", "ti2_indeksi"):
        assert np.isfinite(sonuc.loc[0, sutun])
    np.testing.assert_allclose(
        sonuc.loc[0, "ti1_indeksi"], sonuc.loc[0, "dusey_ruzgar_kaymasi"] * sonuc.loc[0, "yatay_deformasyon"], rtol=1e-6
    )


def test_kapsam_disi_noktada_ek_ozellikler_nan():
    rota = _rota([10400.0], [10400.0]).assign(enlem=[10.0])
    sonuc = rotayi_hava_durumuyla_eslestir(rota, _kup())
    assert np.isnan(sonuc.loc[0, "ti2_indeksi"]) and np.isnan(sonuc.loc[0, "dusey_ruzgar_kaymasi"])
