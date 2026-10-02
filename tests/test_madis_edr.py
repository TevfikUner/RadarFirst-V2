"""MADIS EDR (M1) testleri. NetCDF dosyaları, indirmeler ve EDR değerleri
SENTETİKTİR; ERA5 penceresi depodaki gerçek demo küpünden (THY322) kesilir."""

import gzip

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from turbulans_radar import config
from turbulans_radar.cli import demo
from turbulans_radar.ml import edr_eslestirme as ee
from turbulans_radar.ml import madis_hatti as mh
from turbulans_radar.ml import ozellik_deposu as od
from turbulans_radar.veri import madis_edr as me

ZAMAN = pd.Timestamp("2019-01-15T20:30Z")


@pytest.fixture(autouse=True)
def gecici_klasorler(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "MADIS_EDR_KLASORU", str(tmp_path / "madis"))
    monkeypatch.setattr(config, "ML_DEPO_KLASORU", str(tmp_path / "depo"))
    monkeypatch.setattr(config, "MADIS_ISTEKLER_ARASI_SANIYE", 0)


def _acars_nc(yol, kayitlar):
    """kayitlar: (zaman, enlem, boylam, irtifa_m, max_edr, med_edr, kalite)."""
    z, e, b, i, mx, md, k = (list(x) for x in zip(*kayitlar))
    xr.Dataset(
        {
            "timeObs": ("recNum", np.array([t.timestamp() for t in z], dtype="float64")),
            "latitude": ("recNum", np.array(e, dtype="float32")),
            "longitude": ("recNum", np.array(b, dtype="float32")),
            "altitude": ("recNum", np.array(i, dtype="float32")),
            "maxEDR": ("recNum", np.array(mx, dtype="float32")),
            "medEDR": ("recNum", np.array(md, dtype="float32")),
            "maxEDRDD": ("recNum", np.array([x.encode() for x in k], dtype="S1")),
        }
    ).to_netcdf(yol)


SATIRLAR = [
    (ZAMAN, 41.0, 31.0, 10668.0, 0.05, 0.02, "Z"),
    (ZAMAN, 41.0, 31.0, 3000.0, 0.30, 0.10, "Z"),
    (ZAMAN, 41.0, 31.0, 10668.0, np.nan, 0.01, "Z"),
    (ZAMAN, 41.0, 31.0, 10700.0, 9.0, 0.01, "Z"),
    (ZAMAN, 41.1, 31.1, 10700.0, 0.45, 0.20, "X"),
    (ZAMAN, 41.2, 31.2, 11000.0, 0.45, 0.20, "Z"),
]


def test_edr_cikar_seyir_gecerli_ve_qc_reddedilmemis_gozlemleri_alir(tmp_path):
    _acars_nc(tmp_path / "a.nc", SATIRLAR)
    df = me.edr_cikar(str(tmp_path / "a.nc"))
    assert list(df["max_edr"].round(2)) == [0.05, 0.45]
    assert (df["irtifa_ft"] >= config.MADIS_MIN_IRTIFA_FT).all()
    assert list(df["kalite"]) == ["Z", "Z"]


def test_edr_sinifi_icao_esikleri():
    assert list(me.edr_sinifi([0.0, 0.09, 0.1, 0.39, 0.4, 0.69, 0.7, 1.0])) == [0, 0, 1, 1, 2, 2, 3, 3]


def _gz(tmp_path):
    _acars_nc(tmp_path / "s.nc", SATIRLAR)
    return gzip.compress((tmp_path / "s.nc").read_bytes())


def test_gunluk_edr_24_dosya_bekleme_kota_ve_onbellek(tmp_path):
    icerik, istenen, uykular, sayac = _gz(tmp_path), [], [], iter(range(1, 100))
    df = me.gunluk_edr(
        "2019-01-15",
        indirici=lambda url: istenen.append(url) or (icerik if url.endswith("_0500.gz") else b""),
        sayac=lambda: next(sayac),
        uyku=uykular.append,
    )
    assert len(istenen) == 24 and istenen[0].endswith("/2019/01/15/point/acars/netcdf/20190115_0000.gz")
    assert len(uykular) == 23 and len(df) == 2
    assert len(me.gunluk_edr("2019-01-15", indirici=lambda url: pytest.fail("önbellekteyken indirdi"))) == 2


def test_gunluk_kota_asilinca_durur(tmp_path):
    with pytest.raises(me.MadisKotaAsildiHatasi):
        me.gunluk_edr("2019-01-16", indirici=lambda url: b"", sayac=lambda: config.MADIS_GUNLUK_MAKS_DOSYA + 1)


def _pencereli_ornek():
    from test_ozellik_deposu import _thy322_seyir_noktalari

    with xr.open_dataset(demo.demo_dosyalari()["era5"]) as kup:
        kup = kup.load()
    nokta = _thy322_seyir_noktalari().iloc[[5]].reset_index(drop=True)
    goreli = od.grup_penceresini_yaz(nokta, kup)
    return nokta.assign(pencere_dosyasi=goreli, sinif=1)


def test_pencere_icindeki_edr_era5_ozellikleriyle_eslesir_disindaki_atlanir():
    ornek = _pencereli_ornek()
    p = ornek.iloc[0]
    edr = pd.DataFrame(
        {
            "zaman": [p.zaman, p.zaman, p.zaman + pd.Timedelta(hours=5)],
            "enlem": [p.enlem + 0.1, p.enlem + 5.0, p.enlem],
            "boylam": [p.boylam - 0.1, p.boylam, p.boylam],
            "irtifa_ft": [p.irtifa_ft, p.irtifa_ft, p.irtifa_ft],
            "max_edr": [0.15, 0.5, 0.5],
            "med_edr": [0.05, 0.2, 0.2],
            "kalite": ["Z", "Z", "Z"],
        }
    )
    sonuc = ee.gun_eslestir(ornek, edr)
    assert len(sonuc) == 1 and sonuc.iloc[0]["max_edr"] == 0.15
    assert sonuc.iloc[0]["edr_sinifi"] == 1 and sonuc.iloc[0]["ml_ornek_id"] == p.id
    assert np.isfinite(sonuc.iloc[0]["ti1_indeksi"])


def test_pirep_edr_karsilastirmasi_tupu_uygular():
    pirepler = pd.DataFrame(
        {
            "id": [1, 2],
            "zaman": [ZAMAN, ZAMAN],
            "enlem": [40.0, 30.0],
            "boylam": [-100.0, -90.0],
            "irtifa_ft": [35000.0] * 2,
            "sinif": [1, 0],
        }
    )
    edr = pd.DataFrame(
        {
            "zaman": [ZAMAN + pd.Timedelta(minutes=10), ZAMAN, ZAMAN + pd.Timedelta(hours=2)],
            "enlem": [40.2, 40.0, 40.0],
            "boylam": [-100.0, -100.0, -100.0],
            "irtifa_ft": [35500.0, 39000.0, 35000.0],
            "max_edr": [0.45, 0.9, 0.9],
        }
    )
    k = ee.pirep_edr_karsilastir(pirepler, edr)
    assert list(k["edr_gozlem"]) == [1, 0]
    assert list(k["edr_sinifi"]) == [2, -1]


def test_madis_adimi_indirilmisleri_esler_yenilerden_sinirli_sayida_indirir(monkeypatch):
    gunler = pd.DataFrame({"gun": pd.to_datetime(["2019-06-12", "2019-06-13", "2019-06-14"]), "pencere": [9, 8, 7]})
    monkeypatch.setattr(mh, "_pencereli_gunler", lambda motor: gunler)
    monkeypatch.setattr(mh.os.path, "exists", lambda yol: "2019/06/12" in yol.replace("\\", "/"))
    islenen = []
    monkeypatch.setattr(
        mh,
        "gunu_isle",
        lambda gun, motor, getirici: islenen.append(str(gun.date())) or {"yeni_pencere": 1, "eklenen": 3},
    )
    ozet = mh.madis_adimi(motor=object(), maks_gun=1)
    assert islenen == ["2019-06-12", "2019-06-13"]
    assert ozet == {"madis_eslestirilen_gun": 1, "madis_indirilen_gun": 1, "madis_eklenen": 6}


@pytest.fixture
def motor():
    from sqlalchemy import text

    from turbulans_radar.depo import veritabani as vt

    try:
        motor = vt.motor_al()
        vt.tablolari_olustur(motor)
    except Exception as hata:
        pytest.skip(f"PostgreSQL'e bağlanılamadı: {hata}")
    yield motor
    with motor.begin() as baglanti:
        baglanti.execute(text("DELETE FROM edr_ornekleri WHERE kaynak = 'madis_acars' AND ml_ornek_id = -1"))


def test_edr_ornekleri_kaydi_tekrarlanmaz(motor):
    from turbulans_radar.ml.turbulans_ml_modeli import OZELLIK_SUTUNLARI

    df = pd.DataFrame(
        [
            {
                "zaman": ZAMAN,
                "enlem": 40.0,
                "boylam": -100.0,
                "irtifa_ft": 35000.0,
                "max_edr": 0.12,
                "med_edr": 0.05,
                "kalite": "Z",
                "edr_sinifi": 1,
                "ml_ornek_id": -1,
                **dict.fromkeys(OZELLIK_SUTUNLARI, 1.0),
            }
        ]
    )
    assert mh.edr_orneklerini_kaydet(df, motor) == 1
    assert mh.edr_orneklerini_kaydet(df, motor) == 0
