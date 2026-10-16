import numpy as np
import pandas as pd
import pytest
import xarray as xr

from turbulans_radar import config
from turbulans_radar.analiz import esik_esleme
from turbulans_radar.fizik import ti1_esigi
from turbulans_radar.uretim_bilgisi import uretim_bilgisi
from turbulans_radar.veri.veri_saglayicilari import gfs_kosu_url

pytestmark = pytest.mark.birim


def _kup(seviyeler, kaynak="gfs"):
    lat = np.arange(42.0, 37.75, -0.25)
    lon = np.arange(28.0, 32.25, 0.25)
    zaman = pd.to_datetime(["2026-10-10T00:00"])
    sekil = (1, len(seviyeler), len(lat), len(lon))
    uretec = np.random.default_rng(1)
    u = 30.0 + 0.2 * np.asarray(seviyeler)[None, :, None, None] / 10 + uretec.normal(0, 3, sekil)
    v = uretec.normal(0, 3, sekil)
    t = np.broadcast_to(np.linspace(225.0, 215.0, len(seviyeler))[None, :, None, None], sekil).copy()
    boyutlar = ["valid_time", "pressure_level", "latitude", "longitude"]
    return xr.Dataset(
        {"u": (boyutlar, u), "v": (boyutlar, v), "t": (boyutlar, t)},
        coords={"valid_time": zaman, "pressure_level": np.asarray(seviyeler, float), "latitude": lat, "longitude": lon},
        attrs={"kaynak": kaynak},
    )


def test_yuzdelik_esleme_olcekli_dagilimda_esik_olcekle_tasinir():
    uretec = np.random.default_rng(0)
    era5 = uretec.lognormal(np.log(3e-7), 0.8, 20000)
    gfs = 0.5 * era5
    sonuc = esik_esleme.yuzdelik_esleme(era5, gfs, 7e-7)
    assert sonuc["gfs_esdeger_esik"] == pytest.approx(3.5e-7, rel=0.02)
    assert sonuc["era5_riskli_orani"] == pytest.approx(1 - sonuc["yuzdelik"])
    assert sonuc["gfs_riskli_orani_ayni_esikte"] < sonuc["era5_riskli_orani"]
    assert sonuc["spearman"] == pytest.approx(1.0)


def test_yuzdelik_esleme_nan_atar_ve_bos_veride_none_doner():
    sonuc = esik_esleme.yuzdelik_esleme([1e-7, np.nan, 9e-7, 8e-7], [1e-7, 5e-7, np.nan, 4e-7], 7e-7)
    assert sonuc["n"] == 2
    assert esik_esleme.yuzdelik_esleme([np.nan], [np.nan], 7e-7)["gfs_esdeger_esik"] is None


def test_zaman_bootstrap_araligi_nokta_tahminini_icerir_tek_zamanda_none():
    uretec = np.random.default_rng(2)
    era5 = uretec.lognormal(np.log(3e-7), 0.8, 4000)
    gfs = 0.6 * era5 * uretec.lognormal(0, 0.1, 4000)
    zamanlar = np.repeat(np.arange(8), 500)
    nokta = esik_esleme.yuzdelik_esleme(era5, gfs, 7e-7)["gfs_esdeger_esik"]
    alt, ust = esik_esleme.zaman_bootstrap(era5, gfs, zamanlar, 7e-7, tekrar=200)
    assert alt <= nokta <= ust
    assert esik_esleme.zaman_bootstrap(era5, gfs, np.zeros(4000), 7e-7) is None


def test_izgara_noktalari_her_zaman_ve_seviye_icin_tum_hucreler():
    noktalar = esik_esleme.izgara_noktalari(
        (38.5, 39.5, 29.0, 30.0), 0.5, [pd.Timestamp("2026-10-10T00:00", tz="UTC")], (300, 340)
    )
    assert len(noktalar) == 2 * 3 * 3
    assert set(noktalar["fl"]) == {300, 340}
    assert noktalar["baro_irtifa_m"].max() == pytest.approx(34000 * 0.3048)


def test_ayni_noktalarda_iki_kup_icin_ti1_rota_eslestirmesiyle_hesaplanir():
    noktalar = esik_esleme.izgara_noktalari(
        (39.0, 41.0, 29.0, 31.0), 0.5, [pd.Timestamp("2026-10-10T00:00", tz="UTC")], (300, 340, 380)
    )
    era5 = esik_esleme.ti1_orneklemi(_kup([350.0, 300.0, 250.0, 225.0, 200.0, 175.0, 150.0], "era5_cds"), noktalar)
    gfs = esik_esleme.ti1_orneklemi(_kup([300.0, 250.0, 200.0]), noktalar)
    assert len(era5) == len(gfs) == len(noktalar)
    assert np.isfinite(era5).all() and np.isfinite(gfs).all()
    rapor = esik_esleme.esleme_raporu(noktalar, era5, gfs, float(np.median(era5)), tekrar=10)
    assert set(rapor["seviyeler"]) == {"FL300", "FL340", "FL380"}
    assert "GFS eşdeğer eşik" in esik_esleme.markdown_ozeti(
        {
            **rapor,
            "ayarlar": {
                "uretim_zamani": "t",
                "kutu": [],
                "adim_derece": 0.5,
                "fl": [],
                "era5_seviyeleri_hpa": [],
                "gfs_seviyeleri_hpa": [],
            },
        }
    )


def test_gfs_kosu_url_best_yerine_kosu_dosyasi_ve_gecersiz_saat_hatasi():
    url = gfs_kosu_url(
        "2026-10-09T06:00Z", "https://thredds.ucar.edu/thredds/ncss/grid/grib/NCEP/GFS/Global_0p25deg/Best"
    )
    assert url.endswith("/Global_0p25deg/GFS_Global_0p25deg_20261009_0600.grib2")
    with pytest.raises(ValueError):
        gfs_kosu_url("2026-10-09T05:00Z")


def test_gfs_esigi_bosken_her_kaynakta_ortak_esik(monkeypatch):
    monkeypatch.setattr(config, "TI1_ESIK_ORTA_SIDDETLI_GFS", None)
    assert ti1_esigi.kaynak_ti1_esigi("gfs") == config.TI1_ESIK_ORTA_SIDDETLI
    assert ti1_esigi.kaynak_ti1_esigi("era5_cds") == config.TI1_ESIK_ORTA_SIDDETLI


def test_gfs_esigi_yalniz_gfs_kupunde_ve_yalniz_kendi_baglaminda_uygulanir(monkeypatch):
    monkeypatch.setattr(config, "TI1_ESIK_ORTA_SIDDETLI_GFS", 3e-7)
    assert ti1_esigi.kaynak_ti1_esigi("gfs") == 3e-7
    assert ti1_esigi.kaynak_ti1_esigi("era5_cds") == config.TI1_ESIK_ORTA_SIDDETLI

    @ti1_esigi.ayri_esik_baglaminda
    def islem():
        ti1_esigi.kaynaga_gore_ayarla("gfs")
        return ti1_esigi.etkin_ti1_esigi()

    assert islem() == 3e-7
    assert ti1_esigi.etkin_ti1_esigi() == config.TI1_ESIK_ORTA_SIDDETLI
    assert uretim_bilgisi(_kup([300.0, 250.0, 200.0]))["esikler"]["ti1_orta_siddetli_uygulanan"] == 3e-7
    assert uretim_bilgisi(_kup([300.0, 250.0], "era5_cds"))["esikler"]["ti1_orta_siddetli_uygulanan"] == (
        config.TI1_ESIK_ORTA_SIDDETLI
    )
