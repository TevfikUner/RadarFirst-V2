import os

import numpy as np
import pandas as pd
import pytest
import xarray as xr
from sqlalchemy import text

from turbulans_radar import config
from turbulans_radar.depo import veritabani as vt
from turbulans_radar.veri import veri_saglayicilari as vs
from turbulans_radar.veri.veri_yukleme import hava_durumu_onbellekli_yukle


def _thredds_benzeri_ham_kup():
    zamanlar = pd.date_range("2026-09-26T09:00", periods=2, freq="3h")
    sekil = (2, 1, 3, 4)
    veri = {
        ad: (("time", "isobaric", "latitude", "longitude"), np.full(sekil, deger, dtype="float32"))
        for ad, deger in [
            ("u-component_of_wind_isobaric", 10.0),
            ("v-component_of_wind_isobaric", -5.0),
            ("Temperature_isobaric", 220.0),
        ]
    }
    ham = xr.Dataset(
        {**veri, "LatLon_721X1440-0p13S-180p00E-2": ((), 0)},
        coords={
            "time": zamanlar,
            "reftime": ("time", pd.to_datetime(["2026-09-26T00:00", "2026-09-26T06:00"])),
            "isobaric": ("isobaric", [25000.0], {"units": "Pa"}),
            "latitude": [50.0, 45.0, 40.0],
            "longitude": [280.0, 283.0, 286.0, 289.0],
        },
    )
    return ham


def test_gfs_kupu_ortak_semaya_normalize_edilir():
    kup = vs.gfs_kupunu_normalize_et(_thredds_benzeri_ham_kup())
    assert set(kup.data_vars) == {"u", "v", "t"}
    assert set(kup.dims) == {"valid_time", config.BASINC_BOYUTU, "latitude", "longitude"}
    assert kup[config.BASINC_BOYUTU].values.tolist() == [250.0]
    assert kup["longitude"].values.tolist() == [-80.0, -77.0, -74.0, -71.0]
    assert kup.attrs == {"kaynak": "gfs", "model_calisma_zamani": "2026-09-26T06:00:00"}


def test_canli_zaman_penceresi():
    simdi = pd.Timestamp.now(tz="UTC")
    assert vs.canli_zaman_mi(simdi)
    assert vs.canli_zaman_mi(simdi + pd.Timedelta(hours=config.CANLI_TAHMIN_UFKU_SAAT - 1))
    assert not vs.canli_zaman_mi(simdi - pd.Timedelta(hours=config.CANLI_GECMIS_SAAT + 1))
    assert not vs.canli_zaman_mi("2019-01-15T10:00:00")


class SahteSaglayici:
    """ERA5 Türkiye küpünün gerçek alanlarını 'şimdi'ye taşınmış zaman
    damgalarıyla GFS gibi sunar -- ağa çıkmadan uçtan uca test için. Katalogda
    ayrı bir kaynak adı kullanır ki geliştirme veritabanındaki gerçek GFS
    küpleriyle karışmasın."""

    kaynak = "test_gfs"
    zaman_adimi = "3h"

    def __init__(self):
        self.indirme_sayisi = 0

    def kup_indir(self, kutu, baslangic, bitis, hedef_yol):
        self.indirme_sayisi += 1
        era5 = hava_durumu_onbellekli_yukle(config.HAVA_DURUMU_DOSYASI)
        saatler = pd.date_range(pd.Timestamp(baslangic).ceil("3h"), pd.Timestamp(bitis).floor("3h"), freq="3h")
        kup = era5[["u", "v", "t"]].isel(valid_time=slice(0, len(saatler)))
        kup = kup.assign_coords(valid_time=saatler.tz_convert("UTC").tz_localize(None).values)
        kup.attrs = {"kaynak": "gfs", "model_calisma_zamani": "2026-09-26T06:00:00"}
        os.makedirs(os.path.dirname(hedef_yol), exist_ok=True)
        kup.to_netcdf(hedef_yol)
        return kup.attrs["model_calisma_zamani"]


@pytest.fixture
def sahte_canli_ortam(tmp_path, monkeypatch):
    if not os.path.exists(config.HAVA_DURUMU_DOSYASI):
        pytest.skip(f"'{config.HAVA_DURUMU_DOSYASI}' bulunamadı.")
    try:
        vt.tablolari_olustur(vt.motor_al())
    except Exception as hata:
        pytest.skip(f"PostgreSQL'e bağlanılamadı: {hata}")

    def _temizle():
        with vt.motor_al().begin() as baglanti:
            baglanti.execute(text("DELETE FROM hava_durumu_kupleri WHERE kaynak = :k"), {"k": SahteSaglayici.kaynak})

    _temizle()
    monkeypatch.setattr(config, "CANLI_VERI_KLASORU", str(tmp_path))
    saglayici = SahteSaglayici()
    monkeypatch.setattr(vs, "GfsThreddsSaglayici", lambda: saglayici)
    yield saglayici
    _temizle()


def test_canli_kup_indirilir_kataloga_yazilir_ve_yeniden_kullanilir(sahte_canli_ortam):
    simdi = pd.Timestamp.now(tz="UTC")
    kutu = vs.Kutu(37.0, 40.0, 30.0, 36.0)
    kup = vs.canli_kup_hazirla(kutu, simdi, simdi + pd.Timedelta(hours=4))
    ikinci = vs.canli_kup_hazirla(vs.Kutu(38.0, 39.0, 31.0, 35.0), simdi, simdi + pd.Timedelta(hours=2))
    assert sahte_canli_ortam.indirme_sayisi == 1
    assert ikinci is kup
    assert vs.veri_kupu_kaynagi(kup) == "gfs"


def test_gfs_adimina_denk_gelmeyen_saatlerde_de_katalogdaki_kup_yeniden_kullanilir(sahte_canli_ortam):
    gun = pd.Timestamp.now(tz="UTC").normalize()
    kutu = vs.Kutu(38.0, 39.0, 31.0, 35.0)
    vs.canli_kup_hazirla(kutu, gun + pd.Timedelta("13h10min"), gun + pd.Timedelta("15h10min"))
    vs.canli_kup_hazirla(kutu, gun + pd.Timedelta("14h50min"), gun + pd.Timedelta("16h"))
    assert sahte_canli_ortam.indirme_sayisi == 1


def test_yerel_kup_yoksa_ve_zaman_canliysa_saglayiciya_gidilir(sahte_canli_ortam):
    simdi = pd.Timestamp.now(tz="UTC")
    kup = vs.veri_kupunu_sec([38.0, 39.0], [32.0, 34.0], [simdi, simdi + pd.Timedelta(hours=1)])
    assert vs.veri_kupu_kaynagi(kup) == "gfs"

    gecmis = vs.veri_kupunu_sec([39.0], [35.0], ["2019-01-15T10:00:00"])
    assert vs.veri_kupu_kaynagi(gecmis) == "era5"
    assert vs.veri_kupunu_sec([5.0], [5.0], ["2019-01-15T10:00:00"]) is None
    assert sahte_canli_ortam.indirme_sayisi == 1


def test_canli_veri_kapaliysa_saglayiciya_gidilmez(sahte_canli_ortam, monkeypatch):
    monkeypatch.setattr(config, "CANLI_HAVA_VERISI_ETKIN", False)
    assert vs.veri_kupunu_sec([38.0], [32.0], [pd.Timestamp.now(tz="UTC")]) is None
    assert sahte_canli_ortam.indirme_sayisi == 0


def test_anlik_rota_canli_gfs_verisiyle_hesaplanir(sahte_canli_ortam):
    from turbulans_radar.rota.rota_optimizasyonu import rota_simulasyonu_olustur

    simdi = pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%dT%H:%M:%S")
    sonuc = rota_simulasyonu_olustur(38.4, 27.1, 38.5, 43.4, 34000, simdi, "A320", sigmetler=[])
    assert sonuc["ruzgar_verisi_kaynagi"] == "gfs_tahmin"
    assert "GFS" in sonuc["aciklama"]
    assert sonuc["normal_rota"]["maks_ti1"] is not None
