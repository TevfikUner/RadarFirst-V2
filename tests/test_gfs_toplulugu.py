import os
import time

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from turbulans_radar.analiz import gfs_toplulugu as gt

pytestmark = pytest.mark.birim


def _kup(kayma_carpani, zamanlar):
    seviyeler = [300.0, 250.0, 200.0]
    lat = np.arange(44.0, 33.75, -0.25)
    lon = np.arange(24.0, 36.25, 0.25)
    zaman = pd.DatetimeIndex(zamanlar).tz_convert(None)
    sekil = (len(zaman), len(seviyeler), len(lat), len(lon))
    boylam_dalgasi = np.sin(np.radians(lon) * 40)[None, None, None, :]
    u = (30.0 + kayma_carpani * np.array([0.0, 15.0, 0.0])[None, :, None, None]) * (1 + 0.3 * boylam_dalgasi)
    u = np.broadcast_to(u, sekil).copy()
    t = np.broadcast_to(np.array([229.0, 221.0, 217.0])[None, :, None, None], sekil).copy()
    boyutlar = ["valid_time", "pressure_level", "latitude", "longitude"]
    return xr.Dataset(
        {"u": (boyutlar, u), "v": (boyutlar, np.zeros(sekil)), "t": (boyutlar, t)},
        coords={"valid_time": zaman, "pressure_level": seviyeler, "latitude": lat, "longitude": lon},
        attrs={"kaynak": "gfs"},
    )


class _SahteSaglayici:
    kaynak = "gfs"
    zaman_adimi = "3h"
    izgara_derece = 0.25
    cagrilar = []

    def __init__(self, url):
        self.url = url

    def kup_indir(self, kutu, baslangic, bitis, hedef_yol):
        _SahteSaglayici.cagrilar.append(self.url)
        if "HATA" in self.url:
            raise ConnectionError("yok")
        _kup(1.0, pd.date_range(baslangic, bitis, freq="3h")).to_netcdf(hedef_yol)


def test_aday_kosular_yayin_gecikmesini_ve_gecerlilik_saatini_gozetir():
    kosular = gt.aday_kosular("2026-10-17T12:00Z", 4, simdi="2026-10-16T20:00Z", gecikme_saat=5)
    assert [k.isoformat() for k in kosular] == [
        "2026-10-16T12:00:00+00:00",
        "2026-10-16T06:00:00+00:00",
        "2026-10-16T00:00:00+00:00",
        "2026-10-15T18:00:00+00:00",
    ]
    gecmis = gt.aday_kosular("2026-10-16T07:30Z", 2, simdi="2026-10-16T20:00Z", gecikme_saat=5)
    assert gecmis[0].isoformat() == "2026-10-16T06:00:00+00:00"


def test_asim_olasiligi_uye_orani_ve_kapsam_disinda_nan():
    zamanlar = pd.date_range("2026-10-17T00:00Z", periods=3, freq="3h")
    uyeler = [(None, _kup(c, zamanlar)) for c in (0.2, 1.0, 1.0, 3.0)]
    noktalar = pd.DataFrame(
        {
            "zaman": pd.to_datetime(["2026-10-17T03:00Z", "2026-10-17T03:00Z", "2026-10-25T00:00Z"]),
            "enlem": [39.0, 39.0, 39.0],
            "boylam": [30.0, 30.0, 30.0],
            "geo_irtifa_m": [10500.0, 10500.0, 10500.0],
        }
    )
    ti1 = gt.rotayi_hava_durumuyla_eslestir(noktalar.copy(), uyeler[1][1])["ti1_indeksi"].iloc[0]
    olasilik, sayi = gt.asim_olasiligi(uyeler, noktalar, esik=ti1 * 0.999)
    assert olasilik[0] == pytest.approx(0.75)
    assert sayi[0] == 4
    assert np.isnan(olasilik[2]) and sayi[2] == 0


def test_rota_sonucuna_topluluk_noktalara_yazilir_eksik_kosu_raporlanir(tmp_path, monkeypatch):
    monkeypatch.setattr(
        gt, "gfs_kosu_url", lambda k: f"http://x/GFS_{'HATA' if k.hour == 18 else 'ok'}_{k:%Y%m%d_%H%M}"
    )
    _SahteSaglayici.cagrilar = []
    noktalar = [
        {"enlem": 39.0, "boylam": 29.0 + i, "irtifa_m": 10500.0, "zaman": f"2026-10-17T0{i}:00:00+00:00"}
        for i in range(3)
    ]
    sonuc = {
        "uretim_bilgisi": {"hava_verisi": {"kaynak": "gfs"}},
        "normal_rota": {"noktalar": [dict(n) for n in noktalar]},
        "optimize_rota": {"noktalar": [dict(n) for n in noktalar]},
    }
    gt.rota_sonucuna_topluluk_ekle(
        sonuc, uye_sayisi=4, simdi="2026-10-16T20:00Z", klasor=str(tmp_path), saglayici_fabrikasi=_SahteSaglayici
    )
    t = sonuc["topluluk"]
    assert t["hesaplandi_mi"] and t["uye_sayisi"] == 3
    assert [e["kosu"] for e in t["eksik_kosular"]] == ["2026-10-15T18:00:00+00:00"]
    assert all(0.0 <= n["ti1_asim_olasiligi"] <= 1.0 for n in sonuc["optimize_rota"]["noktalar"])
    assert set(t["rotalar"]) == {"normal_rota", "optimize_rota"}
    assert "Deneysel" in t["aciklama"]
    cagri_sayisi = len(_SahteSaglayici.cagrilar)
    gt.rota_sonucuna_topluluk_ekle(
        sonuc, uye_sayisi=4, simdi="2026-10-16T20:00Z", klasor=str(tmp_path), saglayici_fabrikasi=_SahteSaglayici
    )
    assert len(_SahteSaglayici.cagrilar) == cagri_sayisi + 1


def test_gfs_disi_rotada_topluluk_hesaplanmaz():
    sonuc = gt.rota_sonucuna_topluluk_ekle({"uretim_bilgisi": {"hava_verisi": {"kaynak": "era5_cds"}}})
    assert sonuc["topluluk"]["hesaplandi_mi"] is False


def test_yalniz_kendi_eski_dosyalari_silinir(tmp_path):
    eski = tmp_path / "gfs_kosu_2026100100_abc.nc"
    yabanci = tmp_path / "baska.nc"
    yeni = tmp_path / "gfs_kosu_2026101600_def.nc"
    for yol in (eski, yabanci, yeni):
        yol.write_bytes(b"x")
    eski_zaman = time.time() - 72 * 3600
    os.utime(eski, (eski_zaman, eski_zaman))
    os.utime(yabanci, (eski_zaman, eski_zaman))
    assert gt.eski_uye_dosyalarini_temizle(str(tmp_path), saklama_saat=48) == 1
    assert not eski.exists() and yabanci.exists() and yeni.exists()
