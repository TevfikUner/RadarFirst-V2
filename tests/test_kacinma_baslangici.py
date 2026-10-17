import numpy as np
import pandas as pd
import pytest

from turbulans_radar.analiz import kacinma_baslangici as kb
from turbulans_radar.rota import rota_optimizasyonu as ro

xr = pytest.importorskip("xarray")


def _sentetik_kup(baslangic="2026-10-12T00:00Z", saat=24):
    lat = np.arange(46.0, 33.75, -0.25)
    lon = np.arange(22.0, 38.25, 0.25)
    zaman = pd.date_range(pd.Timestamp(baslangic), periods=saat // 3 + 1, freq="3h").tz_convert(None)
    seviyeler = [300.0, 250.0, 200.0]
    sekil = (len(zaman), len(seviyeler), len(lat), len(lon))
    u = np.broadcast_to(np.array([20.0, 25.0, 22.0])[None, :, None, None], sekil).copy()
    t = np.broadcast_to(np.array([229.0, 221.0, 217.0])[None, :, None, None], sekil).copy()
    boyutlar = ["valid_time", "pressure_level", "latitude", "longitude"]
    return xr.Dataset(
        {"u": (boyutlar, u), "v": (boyutlar, np.zeros(sekil)), "t": (boyutlar, t)},
        coords={"valid_time": zaman, "pressure_level": seviyeler, "latitude": lat, "longitude": lon},
        attrs={"kaynak": "gfs"},
    )


def test_elde_olan_ve_referans_kosusu():
    assert kb.elde_olan_kosu("2026-10-12T10:20Z", 5) == pd.Timestamp("2026-10-12T00:00Z")
    assert kb.elde_olan_kosu("2026-10-12T04:00Z", 5) == pd.Timestamp("2026-10-11T18:00Z")
    assert kb.referans_kosusu("2026-10-12T10:20Z", pd.Timestamp("2026-10-12T00:00Z")) == pd.Timestamp(
        "2026-10-12T06:00Z"
    )
    assert kb.referans_kosusu("2026-10-12T05:30Z", pd.Timestamp("2026-10-12T00:00Z")) == pd.Timestamp(
        "2026-10-12T06:00Z"
    )


def test_ara_nokta_suresinin_yarisi_ve_uclardan_uzak():
    noktalar = [{"zaman": f"2026-10-12T10:{d:02d}:00Z"} for d in range(11)]
    assert kb.ara_nokta_indeksi(noktalar) == 5
    assert kb.ara_nokta_indeksi(noktalar[:3]) == 1


def test_seviye_degisimi_ek_maliyeti_rota_ozetinden_farktir():
    yol = {"sure_dk": 30.0, "yakit_kg": 1000.0}
    assert kb.seviye_degisimi_ek_maliyeti({"toplam_sure_dk": 31.5, "tahmini_yakit_kg": 1040.0}, yol) == {
        "sure_dk": 1.5,
        "yakit_kg": 40.0,
    }
    ek = kb.seviye_degisimi_ek_maliyeti({"toplam_sure_dk": 30.0, "tahmini_yakit_kg": 998.0}, yol)
    assert ek == {"sure_dk": 0.0, "yakit_kg": -2.0}
    assert kb.seviye_degisimi_ek_maliyeti({"toplam_sure_dk": 30.0, "tahmini_yakit_kg": None}, yol)["yakit_kg"] is None


def test_vaka_verilen_kosu_kuplerini_kullanir_ve_riskiz_alanda_kazanc_sifir(monkeypatch):
    def _indirme_yok(*_, **__):
        raise AssertionError("veri_kupu verildiği halde küp seçimi çağrıldı")

    monkeypatch.setattr(ro, "veri_kupune_eris", _indirme_yok)
    istenen = []
    kup = _sentetik_kup()

    def sahte_kup(kosu, bas, bit):
        istenen.append(kosu)
        return kup

    vaka = kb.vaka_calistir("LTFM-LTAI", "2026-10-12T10:00:00Z", "kullanilmaz", kup_fonksiyonu=sahte_kup)
    assert [k.isoformat() for k in istenen] == [
        "2026-10-11T18:00:00+00:00",
        "2026-10-12T00:00:00+00:00",
        "2026-10-12T06:00:00+00:00",
    ]
    assert vaka["r1_yeni_kosu_mu"] is True
    assert vaka["kalkis_utc"] < vaka["yeniden_planlama_utc"]
    assert vaka["riskli_sure_kazanci_dk"] == 0.0
    assert vaka["degerlendirme"]["r0_kalan"]["kapsam_disi_nokta"] == 0
    assert abs(vaka["sure_maliyeti_dk"]) < 1.0

    ozet = kb.ozetle([vaka, {"rota": "LTFM-LTCI", "kalkis_utc": "2026-10-12T10:00:00+00:00", "hata": "X: y"}])
    assert ozet["hesaplanan"] == 1 and ozet["hata"] == 1 and ozet["kazanc_sifir"] == 1 and ozet["riskli_vaka"] == 0
    rapor = {
        "uretim_zamani": "2026-10-17T00:00:00+00:00",
        "indirilen_mb": 0.0,
        "uyari": kb.UYARI,
        "ayarlar": {"plan_oncesi_saat": 6, "kosu_gecikmesi_saat": 5, "ucak": "A320", "irtifa_ft": 35000},
        "ozet": ozet,
        "vakalar": [vaka, {"rota": "LTFM-LTCI", "kalkis_utc": "2026-10-12T10:00:00+00:00", "hata": "X: y"}],
    }
    metin = kb.markdown_ozeti(rapor)
    assert "Fikir 18" in metin and "sertifikalı EDR değildir" in metin and "hata: X: y" in metin
