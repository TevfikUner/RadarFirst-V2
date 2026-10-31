import numpy as np
import pandas as pd
import pytest

from turbulans_radar.analiz import tahmin_ufku as tu

xr = pytest.importorskip("xarray")
pytestmark = pytest.mark.birim


def _kup(zaman, tohum):
    rng = np.random.default_rng(tohum)
    enlem, boylam, seviye = np.arange(42.0, 35.75, -0.25), np.arange(26.0, 32.25, 0.25), [300.0, 250.0, 200.0]
    sekil = (1, len(seviye), len(enlem), len(boylam))
    boyutlar = ("valid_time", "pressure_level", "latitude", "longitude")
    return xr.Dataset(
        {
            "u": (boyutlar, rng.normal(20, 8, sekil)),
            "v": (boyutlar, rng.normal(0, 8, sekil)),
            "t": (boyutlar, rng.normal(220, 2, sekil)),
        },
        coords={
            "valid_time": [zaman.tz_convert(None)],
            "pressure_level": seviye,
            "latitude": enlem,
            "longitude": boylam,
        },
    )


def test_gerekli_dosyalar_her_gecerlilik_icin_uc_kosuyu_ister():
    zamanlar = tu.gecerlilik_zamanlari("2026-10-23T00", "2026-10-24T00")
    assert len(zamanlar) == 3
    ciftler = tu.gerekli_dosyalar(zamanlar)
    assert (pd.Timestamp("2026-10-21T00", tz="UTC"), 48) in ciftler
    assert (pd.Timestamp("2026-10-23T00", tz="UTC"), 24) in ciftler
    assert len(ciftler) == 9


def test_indir_var_olani_atlar_ve_ayni_kup_ufuklar_ozdes_cikar(tmp_path):
    zamanlar = tu.gecerlilik_zamanlari("2026-10-23T00", "2026-10-23T12")
    istekler = []

    class Sahte:
        izgara_derece, zaman_adimi = 0.25, "3h"

        def __init__(self, url):
            self.url = url

        def kup_indir(self, kutu, baslangic, bitis, yol):
            istekler.append((self.url, baslangic))
            _kup(pd.Timestamp(baslangic), tohum=int(pd.Timestamp(baslangic).timestamp()) % 1000).to_netcdf(yol)

    ozet = tu.indir(str(tmp_path), zamanlar, saglayici_fabrikasi=Sahte, bekle=lambda s: None)
    assert len(ozet["indirilen"]) == len(tu.gerekli_dosyalar(zamanlar)) and not ozet["hata"]
    assert "GFS_Global_0p25deg_20261021_0000.grib2" in istekler[0][0]
    tekrar = tu.indir(str(tmp_path), zamanlar, saglayici_fabrikasi=Sahte, bekle=lambda s: None)
    assert not tekrar["indirilen"] and len(tekrar["var_olan"]) == len(ozet["indirilen"])

    rapor = tu.olcum_yap(str(tmp_path), zamanlar, nokta_sayisi=300, esik=1e-7)
    assert not rapor["eksik_gecerlilik"] and len(rapor["kayitlar"]) == 4
    assert all(k["spearman"] == pytest.approx(1.0) and k["ayni_karar_orani"] == 1.0 for k in rapor["kayitlar"])
    assert set(rapor["ozet"]) == {"f024", "f048"}
    metin = tu.markdown_ozeti(
        {
            "parametreler": {
                "baslangic": "a",
                "bitis": "b",
                "adim_saat": 12,
                "kutu": [],
                "seviyeler_hpa": [],
                "nokta_sayisi": 300,
            },
            "commit": None,
            "uretim_zamani": "t",
            **rapor,
        }
    )
    assert "| f048 | 2 |" in metin and "sertifikalı EDR değildir" in metin


def test_era5_getirici_gecikmedeki_zamani_sormaz_gun_basina_bir_kez_ister_hatayi_kaydeder():
    zamanlar = tu.gecerlilik_zamanlari("2026-10-23T00", "2026-10-25T00")
    istekler = []

    def getir(gun, saatler, kutu, klasor):
        istekler.append((gun, tuple(saatler)))
        if gun.day == 24:
            raise RuntimeError("CDS yok")
        return f"kup-{gun.day}"

    era5_getir, hatalar = tu.era5_getirici(zamanlar, "k", gecikme_gun=5, simdi="2026-10-29T12", getir=getir)
    assert [era5_getir(v) for v in zamanlar] == ["kup-23", "kup-23", None, None, None]
    assert istekler == [
        (pd.Timestamp("2026-10-23", tz="UTC"), (0, 12)),
        (pd.Timestamp("2026-10-24", tz="UTC"), (0, 12)),
    ]
    assert set(hatalar) == {"2026-10-24"}


def test_olcum_yap_era5_ile_ufuklari_ve_esik_eslemesini_raporlar(tmp_path):
    zamanlar = tu.gecerlilik_zamanlari("2026-10-23T00", "2026-10-23T12")
    for kosu, ufuk in tu.gerekli_dosyalar(zamanlar):
        gecerlilik = kosu + pd.Timedelta(hours=ufuk)
        _kup(gecerlilik, tohum=int(gecerlilik.timestamp()) % 1000).to_netcdf(tu.dosya_yolu(str(tmp_path), kosu, ufuk))

    def era5_getir(v):
        return None if v.hour == 12 else xr.load_dataset(tu.dosya_yolu(str(tmp_path), v, 0))

    rapor = tu.olcum_yap(
        str(tmp_path), zamanlar, nokta_sayisi=300, esik=1e-7, era5_getir=era5_getir, era5_esik=1e-7, tekrar=20
    )
    era5 = rapor["era5"]
    assert era5["eksik_gecerlilik"] == [zamanlar[1].isoformat()]
    assert {k["ufuk_saat"] for k in era5["kayitlar"]} == {0, 24, 48}
    assert all(k["spearman"] == pytest.approx(1.0) and k["ayni_karar_orani"] == 1.0 for k in era5["kayitlar"])
    assert set(era5["ozet"]) == {"f000", "f024", "f048"}
    esleme = era5["esik_esleme"]["genel"]
    assert esleme["n"] == 300 and esleme["spearman"] == pytest.approx(1.0)
    assert set(era5["esik_esleme"]["seviyeler"]) <= {f"FL{f}" for f in range(310, 390, 10)}
    metin = tu.markdown_ozeti(
        {
            "parametreler": {
                "baslangic": "a",
                "bitis": "b",
                "adim_saat": 12,
                "kutu": [],
                "seviyeler_hpa": [],
                "nokta_sayisi": 300,
            },
            "commit": None,
            "uretim_zamani": "t",
            **rapor,
        }
    )
    assert "| f000 | 1 |" in metin and "ATM-05" in metin and "sertifikalı EDR değildir" in metin


def test_olcum_yap_era5_yoksa_esleme_bos():
    rapor = tu.olcum_yap("yok", tu.gecerlilik_zamanlari("2026-10-23T00", "2026-10-23T00"), era5_getir=lambda v: None)
    assert rapor["era5"]["esik_esleme"] is None and rapor["era5"]["ozet"] == {}
