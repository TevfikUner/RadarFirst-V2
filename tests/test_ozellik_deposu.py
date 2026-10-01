import numpy as np
import pandas as pd
import pytest
import xarray as xr

from turbulans_radar import config
from turbulans_radar.cli import demo
from turbulans_radar.ml import ozellik_deposu as od
from turbulans_radar.ml.turbulans_ml_modeli import EK_OZELLIK_SUTUNLARI, OZELLIK_SUTUNLARI, ozellikleri_cikar
from turbulans_radar.veri import era5_saglayici as es
from turbulans_radar.veri.veri_saglayicilari import Kutu


@pytest.fixture(autouse=True)
def gecici_depo(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "ML_DEPO_KLASORU", str(tmp_path / "depo"))
    return tmp_path / "depo"


def _kup(seviyeler=(300.0, 250.0, 200.0), degiskenler=("u", "v", "t")):
    zamanlar = pd.date_range("2019-01-15T10:00", "2019-01-15T14:00", freq="h")
    enlemler = np.arange(44.0, 37.9, -0.25)
    boylamlar = np.arange(26.0, 32.1, 0.25)
    sekil = (len(zamanlar), len(seviyeler), len(enlemler), len(boylamlar))
    deger = np.arange(np.prod(sekil), dtype="float32").reshape(sekil)
    return xr.Dataset(
        {d: (("valid_time", "pressure_level", "latitude", "longitude"), deger + i) for i, d in enumerate(degiskenler)},
        coords={
            "valid_time": zamanlar,
            "pressure_level": list(seviyeler),
            "latitude": enlemler,
            "longitude": boylamlar,
        },
        attrs={"kaynak": "era5"},
    )


def test_pencere_merkez_hucre_ve_saat_etrafinda_sabit_boyutludur():
    kup = _kup()
    pencere = od.pencere_kes(kup, 41.1, 29.04, pd.Timestamp("2019-01-15T12:20Z"), derece=1.0, saat=1)
    assert dict(pencere.sizes) == {"saat_ofset": 3, "pressure_level": 3, "enlem_ofset": 9, "boylam_ofset": 9}
    beklenen = kup["u"].sel(valid_time="2019-01-15T12:00", latitude=41.0, longitude=29.0)
    np.testing.assert_array_equal(pencere["u"].sel(saat_ofset=0, enlem_ofset=0.0, boylam_ofset=0.0), beklenen)
    np.testing.assert_array_equal(
        pencere["u"].sel(saat_ofset=-1, enlem_ofset=1.0, boylam_ofset=-1.0).values,
        kup["u"].sel(valid_time="2019-01-15T11:00", latitude=42.0, longitude=28.0).values,
    )


def test_kup_disinda_kalan_hucre_ve_saatler_nan_olur():
    pencere = od.pencere_kes(_kup(), 43.9, 31.9, pd.Timestamp("2019-01-15T14:10Z"), derece=1.0, saat=1)
    assert np.isnan(pencere["u"].sel(saat_ofset=1)).all()
    assert np.isnan(pencere["u"].sel(saat_ofset=0, enlem_ofset=1.0)).all()
    assert np.isfinite(pencere["u"].sel(saat_ofset=0, enlem_ofset=0.0, boylam_ofset=0.0)).all()


def test_ozellik_kupu_depo_seviyelerini_kalibrasyon_alt_kumesine_indirir(monkeypatch):
    monkeypatch.setattr(config, "ERA5_BASINC_SEVIYELERI_HPA", (300.0, 250.0, 200.0))
    genis = _kup(seviyeler=(350.0, 300.0, 250.0, 225.0, 200.0, 175.0, 150.0), degiskenler=("u", "v", "t", "r"))
    dar = od.ozellik_kupu(genis)
    assert sorted(dar["pressure_level"].values.tolist()) == [200.0, 250.0, 300.0]
    assert set(dar.data_vars) == {"u", "v", "t"}
    assert od.ozellik_kupu(_kup()).sizes == _kup().sizes


def test_cds_istegi_ek_degiskeni_icerir_ve_normalize_onu_korur():
    istek = es.cds_istekleri_olustur(
        Kutu(40, 41, 29, 30),
        pd.Timestamp("2019-01-15T10Z"),
        pd.Timestamp("2019-01-15T12Z"),
        (300.0, 250.0),
        ("relative_humidity",),
    )[0]
    assert istek["variable"][-1] == "relative_humidity" and istek["pressure_level"] == ["300", "250"]
    ham = _kup(degiskenler=("u", "v", "t", "r")).rename({"valid_time": "time"})
    assert "r" in es.era5_kupunu_normalize_et(ham, "cds", ("relative_humidity",)).data_vars
    assert "r" not in es.era5_kupunu_normalize_et(ham, "cds").data_vars
    with pytest.raises(ValueError, match="Desteklenmeyen"):
        es.CdsEra5Saglayici(ek_degiskenler=("ozon",))


def _thy322_seyir_noktalari(adet=12):
    rota = pd.read_parquet(demo.demo_dosyalari()["rota"])
    seyir = rota[rota["baro_irtifa_m"].between(10000, 11500)]
    secilen = seyir.iloc[np.linspace(0, len(seyir) - 1, adet).astype(int)]
    return pd.DataFrame(
        {
            "id": np.arange(1, adet + 1),
            "zaman": pd.to_datetime(secilen["zaman"], utc=True).to_numpy(),
            "enlem": secilen["enlem"].to_numpy(),
            "boylam": secilen["boylam"].to_numpy(),
            "irtifa_ft": secilen["baro_irtifa_m"].to_numpy() / 0.3048,
        }
    )


def test_depodan_hesaplanan_ozellikler_tam_dilimle_birebir_aynidir():
    with xr.open_dataset(demo.demo_dosyalari()["era5"]) as kup:
        kup = kup.load()
    noktalar = _thy322_seyir_noktalari()
    tam = ozellikleri_cikar(noktalar.assign(irtifa_m=noktalar["irtifa_ft"] * 0.3048), od.ozellik_kupu(kup))
    assert np.isfinite(tam[OZELLIK_SUTUNLARI].to_numpy()).all()

    goreli = od.grup_penceresini_yaz(noktalar, kup)
    assert goreli.startswith("2019/01/15/grup_")
    depodan = od.depodan_ozellik_cikar(noktalar.assign(pencere_dosyasi=goreli))

    sutunlar = OZELLIK_SUTUNLARI + EK_OZELLIK_SUTUNLARI
    np.testing.assert_allclose(
        depodan.loc[noktalar["id"], sutunlar].to_numpy(dtype=float), tam[sutunlar].to_numpy(dtype=float), rtol=1e-6
    )


def test_depoda_olmayan_ornek_acik_hata_verir():
    noktalar = _thy322_seyir_noktalari(2)
    with xr.open_dataset(demo.demo_dosyalari()["era5"]) as kup:
        pencereler = od.grup_pencereleri(noktalar, kup.load())
    with pytest.raises(KeyError):
        od.pencereden_kup(pencereler, 999)
