"""İz bulutu duyarlılığı. Nem alanı SENTETİKTİR; sıcaklık ve rüzgar gerçek demo küpünden."""

import os

import numpy as np
import pytest

from turbulans_radar.fizik.eslestirme import rotayi_hava_durumuyla_eslestir
from turbulans_radar.fizik.iz_bulutu import duyarli_nokta_sayisi, iz_bulutu_duyarli


def test_olcut_soguk_ve_buza_gore_doymus_havayi_isaretler():
    sonuc = iz_bulutu_duyarli([220.0, 220.0, 240.0, 233.15, np.nan], [105.0, 95.0, 120.0, 100.0, 110.0])
    assert list(sonuc) == [True, False, False, True, None]
    assert duyarli_nokta_sayisi(sonuc) == 2
    assert duyarli_nokta_sayisi([None, None]) is None


@pytest.fixture(scope="module")
def veri_kupu():
    xr = pytest.importorskip("xarray")
    from test_eslestirme import DEMO_NC_YOLU, NC_YOLU

    with xr.open_dataset(NC_YOLU if os.path.isfile(NC_YOLU) else DEMO_NC_YOLU) as kup:
        return kup.load()


def test_eslestirme_nem_varsa_iz_bulutu_sutunlarini_doldurur_yoksa_bos_birakir(veri_kupu):
    from test_eslestirme import _sentetik_rota_uret

    rota = _sentetik_rota_uret(veri_kupu, n=30)
    nemsiz = rotayi_hava_durumuyla_eslestir(rota, veri_kupu)
    assert nemsiz["buz_bagil_nem_yuzde"].isna().all() and nemsiz["iz_bulutu_duyarli"].isna().all()

    nemli_kup = veri_kupu.assign(r=veri_kupu["t"] * 0 + 110.0)
    nemli = rotayi_hava_durumuyla_eslestir(rota, nemli_kup)
    kapsamda = nemli["ti1_indeksi"].notna() | nemli["basinc_hpa"].notna()
    assert (nemli.loc[kapsamda, "buz_bagil_nem_yuzde"] == 110.0).all()
    soguk = nemli.loc[kapsamda, "iz_bulutu_duyarli"].astype(bool)
    assert soguk.any()


def test_murphy_koop_egrileri_uclu_noktada_kesisir():
    from turbulans_radar.fizik.iz_bulutu import _e_buz_pa, _e_sivi_pa

    assert float(_e_buz_pa(273.16)) == pytest.approx(611.657, rel=1e-4)
    assert float(_e_sivi_pa(273.16)) == pytest.approx(611.657, rel=1e-4)
    assert float(_e_sivi_pa(233.15)) > float(_e_buz_pa(233.15))


def test_sac_esigi_basincla_artar_ve_karisim_dogrusu_buz_egrisini_keser():
    from turbulans_radar.fizik.iz_bulutu import _e_buz_pa, _e_sivi_pa, karisim_egimi_pa_k, sac_esik_sicakligi_k

    esikler = sac_esik_sicakligi_k([200.0, 250.0, 300.0, np.nan])
    assert esikler[0] < esikler[1] < esikler[2] < 233.15
    assert np.isnan(esikler[3])
    g = float(karisim_egimi_pa_k(250.0))
    t_lm = 273.15 - 46.46 + 9.43 * np.log(g - 0.053) + 0.720 * np.log(g - 0.053) ** 2
    t_lc = float(esikler[1])
    assert t_lc < t_lm
    assert float(_e_sivi_pa(t_lm)) + g * (t_lc - t_lm) == pytest.approx(float(_e_buz_pa(t_lc)), rel=1e-6)


def test_basinc_verilince_sac_esigi_sabit_olcutte_eski_davranis(monkeypatch):
    from turbulans_radar import config
    from turbulans_radar.fizik.iz_bulutu import sac_esik_sicakligi_k

    t_lc = float(sac_esik_sicakligi_k(250.0)[0])
    sicaklik = [t_lc - 0.5, t_lc + 0.5, 230.0]
    monkeypatch.setattr(config, "IZ_BULUTU_OLCUTU", "sac")
    assert list(iz_bulutu_duyarli(sicaklik, [105.0, 105.0, 105.0], [250.0, 250.0, 250.0])) == [True, False, False]
    monkeypatch.setattr(config, "IZ_BULUTU_OLCUTU", "sabit")
    assert list(iz_bulutu_duyarli(sicaklik, [105.0, 105.0, 105.0], [250.0, 250.0, 250.0])) == [True, True, True]


def test_iz_bulutu_seviye_bilgisi_yalniz_iz_bulutu_varsa_ve_iki_komsu_seviye():
    import pandas as pd
    import xarray as xr

    from turbulans_radar.rota.rota_optimizasyonu import iz_bulutu_seviye_bilgisi

    lat = np.arange(42.0, 37.75, -0.25)
    lon = np.arange(27.0, 33.25, 0.25)
    zaman = pd.to_datetime(["2026-10-17T00:00", "2026-10-17T03:00"])
    seviyeler = [300.0, 250.0, 200.0]
    sekil = (len(zaman), len(seviyeler), len(lat), len(lon))
    boyutlar = ["valid_time", "pressure_level", "latitude", "longitude"]
    kup = xr.Dataset(
        {
            "u": (boyutlar, np.full(sekil, 20.0)),
            "v": (boyutlar, np.zeros(sekil)),
            "t": (boyutlar, np.full(sekil, 212.0)),
            "r": (boyutlar, np.full(sekil, 110.0)),
        },
        coords={"valid_time": zaman, "pressure_level": seviyeler, "latitude": lat, "longitude": lon},
    )
    aday = {
        "enlem": np.array([40.0, 40.0, 40.0]),
        "boylam": np.array([29.0, 30.0, 31.0]),
        "irtifa_m": 35000 * 0.3048,
        "zamanlar": list(pd.date_range("2026-10-17T01:00Z", periods=3, freq="10min")),
        "iz_bulutu_sayisi": 3,
    }
    bilgi = iz_bulutu_seviye_bilgisi(aday, kup)
    assert bilgi["fl"] == 350 and [s["fl"] for s in bilgi["secenekler"]] == [330, 370]
    assert all(s["duyarli_nokta_sayisi"] == 3 for s in bilgi["secenekler"])
    assert "rota kararına girmez" in bilgi["aciklama"]
    assert iz_bulutu_seviye_bilgisi({**aday, "iz_bulutu_sayisi": 0}, kup) is None
