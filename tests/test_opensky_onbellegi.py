import os

import pandas as pd
import pytest

from turbulans_radar import config
from turbulans_radar.veri import opensky_onbellegi as oo


@pytest.fixture(autouse=True)
def gecici_klasor(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "OPENSKY_ONBELLEK_KLASORU", str(tmp_path))
    return tmp_path


def _rota(zamanlar=("2019-01-15T19:39:36Z", "2019-01-15T19:39:46Z")):
    return pd.DataFrame(
        {
            "zaman_unix": [int(pd.Timestamp(z).timestamp()) for z in zamanlar],
            "icao24": ["4bb1d6"] * len(zamanlar),
            "enlem": [40.37, 40.38],
            "boylam": [28.89, 28.90],
            "geo_irtifa_m": [None, 9500.0],
            "baro_irtifa_m": [9400.0, 9450.0],
            "zaman": pd.to_datetime(list(zamanlar), utc=True),
            "ucus_numarasi": ["THY322"] * len(zamanlar),
        }
    )


@pytest.mark.parametrize("ucus", ["../etc", "THY 322", "THY322;DROP", "", "A" * 9])
def test_guvensiz_ucus_numarasi_icin_yol_uretilmez(ucus):
    assert oo.rota_onbellek_yolu(ucus, "2019-01-15") is None


def test_gecersiz_tarih_icin_yol_uretilmez():
    assert oo.rota_onbellek_yolu("THY322", "dun") is None


def test_yol_ucus_numarasini_buyuk_harfe_ve_tarihi_iso_bicime_cevirir(gecici_klasor):
    assert oo.rota_onbellek_yolu("thy322", "2019-01-15T00:00") == os.path.join(
        str(gecici_klasor), "THY322_2019-01-15.parquet"
    )


def test_yazilan_rota_ayni_tip_ve_degerlerle_okunur():
    rota = _rota()
    assert oo.rota_onbellege_yaz(rota, "THY322", "2019-01-15") is not None
    okunan = oo.rota_onbellekten_oku("THY322", "2019-01-15")
    pd.testing.assert_frame_equal(okunan, rota)
    assert str(okunan["zaman"].dt.tz) == "UTC"


def test_onbellekte_olmayan_rota_none_doner():
    assert oo.rota_onbellekten_oku("THY322", "2019-01-15") is None


def test_henuz_bitmemis_ucus_onbellege_yazilmaz():
    simdi = pd.Timestamp.now(tz="UTC")
    rota = _rota((str(simdi - pd.Timedelta(hours=2)), str(simdi - pd.Timedelta(hours=1))))
    assert oo.rota_onbellege_yaz(rota, "THY322", f"{simdi:%Y-%m-%d}") is None
    assert oo.rota_onbellekten_oku("THY322", f"{simdi:%Y-%m-%d}") is None


def test_bos_rota_onbellege_yazilmaz(gecici_klasor):
    assert oo.rota_onbellege_yaz(_rota().iloc[0:0], "THY322", "2019-01-15") is None
    assert not os.listdir(gecici_klasor)


def test_bozuk_onbellek_dosyasi_none_doner_ve_hata_firlatmaz(gecici_klasor):
    (gecici_klasor / "THY322_2019-01-15.parquet").write_bytes(b"parquet degil")
    assert oo.rota_onbellekten_oku("THY322", "2019-01-15") is None
