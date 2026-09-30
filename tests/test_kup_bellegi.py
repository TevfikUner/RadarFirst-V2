import numpy as np
import pandas as pd
import pytest
import xarray as xr

from turbulans_radar import config
from turbulans_radar.fizik.eslestirme import rotayi_hava_durumuyla_eslestir
from turbulans_radar.veri import veri_yukleme as vy


@pytest.fixture
def sentetik_kup(tmp_path, monkeypatch):
    """ERA5 düzeninde (enlem azalan) 30-50°K, 20-50°D, 48 saatlik bir küp."""
    enlemler = np.arange(50.0, 29.9, -0.25)
    boylamlar = np.arange(20.0, 50.01, 0.25)
    zamanlar = pd.date_range("2020-01-01T00:00", periods=48, freq="1h")
    seviyeler = np.array([200.0, 250.0, 300.0])
    rng = np.random.default_rng(7)
    sekil = (len(zamanlar), len(seviyeler), len(enlemler), len(boylamlar))
    boyutlar = ("valid_time", "pressure_level", "latitude", "longitude")
    kup = xr.Dataset(
        {
            "u": (boyutlar, rng.normal(20, 10, sekil).astype("float32")),
            "v": (boyutlar, rng.normal(0, 10, sekil).astype("float32")),
            "t": (boyutlar, rng.normal(220, 5, sekil).astype("float32")),
        },
        coords={"valid_time": zamanlar, "pressure_level": seviyeler, "latitude": enlemler, "longitude": boylamlar},
    )
    yol = tmp_path / "buyuk_kup.nc"
    kup.to_netcdf(yol)
    monkeypatch.setattr(config, "HAVA_DURUMU_DOSYASI", str(yol))
    monkeypatch.setattr(config, "EK_HAVA_DURUMU_KLASORU", "")
    monkeypatch.setattr(config, "ERA5_UCUS_KLASORU", "")
    yield str(yol)
    vy.onbellekten_cikar(str(yol))


def _rota():
    return pd.DataFrame(
        {
            "zaman": pd.date_range("2020-01-01T10:00", periods=20, freq="5min", tz="UTC"),
            "enlem": np.linspace(40.0, 41.0, 20),
            "boylam": np.linspace(30.0, 33.0, 20),
            "geo_irtifa_m": 10500.0,
        }
    )


def test_buyuk_kupten_sadece_rota_penceresi_okunur_ve_sonuc_degismez(sentetik_kup, monkeypatch):
    rota = _rota()
    tam = vy.kapsayan_veri_kupunu_bul(rota["enlem"], rota["boylam"], rota["zaman"])
    monkeypatch.setattr(config, "KUP_TAM_YUKLEME_ESIGI_MB", 0.0)
    pencere = vy.kapsayan_veri_kupunu_bul(rota["enlem"], rota["boylam"], rota["zaman"])

    assert pencere.nbytes < tam.nbytes / 10
    assert (float(pencere.latitude.min()), float(pencere.latitude.max())) == (39.0, 42.0)
    assert (float(pencere.longitude.min()), float(pencere.longitude.max())) == (29.0, 34.0)
    assert vy.veri_kupu_adi(pencere) == "buyuk_kup.nc"
    np.testing.assert_allclose(
        rotayi_hava_durumuyla_eslestir(rota, pencere)["ti1_indeksi"],
        rotayi_hava_durumuyla_eslestir(rota, tam)["ti1_indeksi"],
        rtol=1e-6,
    )


def test_kucuk_kup_bugunku_gibi_tamamen_yuklenir(sentetik_kup):
    kup = vy.kapsayan_veri_kupunu_bul([40.0], [30.0], ["2020-01-01T10:00"])
    assert kup.sizes["latitude"] == 81 and kup.sizes["valid_time"] == 48


def test_onbellek_butceyi_asinca_en_eski_kupu_atar(sentetik_kup, monkeypatch):
    monkeypatch.setattr(config, "KUP_TAM_YUKLEME_ESIGI_MB", 0.0)
    monkeypatch.setattr(config, "KUP_ONBELLEK_MAKS_MB", 0.015)
    ilk = vy.hava_durumu_penceresi_yukle(sentetik_kup, (40, 41), (30, 31), ("2020-01-01T10:00", "2020-01-01T11:00"))
    ikinci = vy.hava_durumu_penceresi_yukle(sentetik_kup, (44, 45), (40, 41), ("2020-01-02T10:00", "2020-01-02T11:00"))
    assert max(ilk.nbytes, ikinci.nbytes) <= 0.015 * 1024 * 1024 < ilk.nbytes + ikinci.nbytes
    anahtarlar = [a for a in vy._onbellek if a[0] == sentetik_kup]
    assert len(anahtarlar) == 1 and anahtarlar[0][1][0] == 44

    vy.onbellekten_cikar(sentetik_kup)
    assert not [a for a in vy._onbellek if a[0] == sentetik_kup]


def test_bolge_ya_da_zaman_kesismeyen_kup_hic_yuklenmez(sentetik_kup, monkeypatch):
    def yuklenmemeli(*args, **kwargs):
        raise AssertionError("Kesişmeyen küp yüklenmemeli")

    monkeypatch.setattr(vy, "hava_durumu_onbellekli_yukle", yuklenmemeli)
    assert vy.kapsayan_veri_kupunu_bul([10.0], [30.0], ["2020-01-01T10:00"]) is None
    assert vy.kapsayan_veri_kupunu_bul([40.0], [30.0], ["2021-06-01T10:00"]) is None


def test_katalog_varsa_secim_dosya_acmadan_katalogdan_yapilir(sentetik_kup, monkeypatch):
    from turbulans_radar.depo import kup_katalogu

    monkeypatch.setattr(kup_katalogu, "kesisen_kup_yollari", lambda *a, **k: (set(), {sentetik_kup}))
    monkeypatch.setattr(vy, "dosya_meta_verisi", lambda yol: pytest.fail("Katalogdaki küp için dosya açılmamalı"))
    assert vy.kapsayan_veri_kupunu_bul([40.0], [30.0], ["2020-01-01T10:00"]) is None

    monkeypatch.setattr(kup_katalogu, "kesisen_kup_yollari", lambda *a, **k: ({sentetik_kup}, {sentetik_kup}))
    assert vy.kapsayan_veri_kupunu_bul([40.0], [30.0], ["2020-01-01T10:00"]) is not None


def test_katalog_erisilemezse_dosya_meta_verisine_dusulur(sentetik_kup, monkeypatch):
    from turbulans_radar.depo import kup_katalogu

    def erisilemez(*args, **kwargs):
        raise ConnectionError("veritabanı yok")

    monkeypatch.setattr(kup_katalogu, "kesisen_kup_yollari", erisilemez)
    assert vy.kapsayan_veri_kupunu_bul([40.0], [30.0], ["2020-01-01T10:00"]) is not None
