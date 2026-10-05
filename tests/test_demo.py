import os

import numpy as np
import pandas as pd
import pytest

from turbulans_radar import config
from turbulans_radar.analiz import ucus_analizi
from turbulans_radar.cli import demo


@pytest.fixture
def yalniz_demo_verisi(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "HAVA_DURUMU_DOSYASI", str(tmp_path / "yok.nc"))
    monkeypatch.setattr(config, "EK_HAVA_DURUMU_KLASORU", "")
    monkeypatch.setattr(config, "ERA5_UCUS_KLASORU", "")
    monkeypatch.setattr(config, "OPENSKY_ONBELLEK_KLASORU", str(tmp_path / "opensky"))
    monkeypatch.setattr(config, "ERA5_OTOMATIK_INDIRME", True)
    monkeypatch.setattr(config, "CANLI_HAVA_VERISI_ETKIN", True)
    monkeypatch.setattr(config, "CIKTI_KLASORU", str(tmp_path / "ciktilar"))
    kayitlar = []
    monkeypatch.setattr(ucus_analizi, "ucus_ve_olcumleri_kaydet", lambda df, u, t: kayitlar.append((u, t, len(df))))
    monkeypatch.setattr(ucus_analizi, "trino_baglantisi_olustur", lambda: pytest.fail("Demo OpenSky'a bağlanmamalı"))
    monkeypatch.setattr(ucus_analizi, "ucus_hava_dilimi_hazirla", lambda *a, **k: pytest.fail("Demo ERA5 indirmemeli"))
    return kayitlar


def test_demo_paketi_depoda_ve_kucuk():
    for yol in demo.demo_dosyalari().values():
        assert os.path.isfile(yol), yol
        assert os.path.getsize(yol) < 1_000_000


def test_demo_cevrimdisi_calisir_harita_ve_kayit_uretir(yalniz_demo_verisi, tmp_path):
    sonuc = demo.demo_calistir(harita_uret=True)

    assert sonuc is not None and len(sonuc) == 1614
    gecerli = np.isfinite(sonuc["ti1_indeksi"].to_numpy(dtype=float))
    assert 500 < gecerli.sum() < len(sonuc)
    assert yalniz_demo_verisi == [("THY322", "2019-01-15", 1614)]
    assert os.path.isfile(tmp_path / "ciktilar" / "turbulans_haritasi_THY322_2019-01-15.html")
    assert config.ERA5_OTOMATIK_INDIRME is False and config.CANLI_HAVA_VERISI_ETKIN is False


ALTIN_SUTUNLAR = ["ti1_indeksi", "dusey_ruzgar_kaymasi", "yatay_deformasyon", "richardson_sayisi"]
ALTIN_DEGERLER = {
    "2019-01-15T19:39:51Z": [7.230308534336888e-07, 0.01400688940796959, 5.161965889602165e-05, 3.3576305165137983],
    "2019-01-15T19:56:59Z": [8.363713944410138e-07, 0.01304600875866315, 6.410936937978252e-05, 3.728469441661187],
    "2019-01-15T20:00:38Z": [7.68524566911208e-07, 0.01309462371003511, 5.8690084108506796e-05, 3.5361578988691167],
    "2019-01-15T21:11:53Z": [1.8075133545648178e-07, 0.00475738221546833, 3.799386453936372e-05, 17.466693679081416],
}
ALTIN_NAN_SAYISI = 894


def test_demo_altin_degerleri_degismez(yalniz_demo_verisi):
    sonuc = demo.demo_calistir(harita_uret=False).set_index("zaman")

    for sutun in ALTIN_SUTUNLAR:
        assert int(sonuc[sutun].isna().sum()) == ALTIN_NAN_SAYISI, sutun
    for zaman, beklenen in ALTIN_DEGERLER.items():
        gercek = sonuc.loc[pd.Timestamp(zaman), ALTIN_SUTUNLAR].to_numpy(dtype=float)
        np.testing.assert_allclose(gercek, beklenen, rtol=1e-6, err_msg=zaman)


def test_demo_klasoru_bossa_acik_hata(monkeypatch):
    monkeypatch.setattr(config, "DEMO_VERI_KLASORU", "")
    with pytest.raises(SystemExit, match="devre dışı"):
        demo.demo_calistir()


def test_agsiz_provada_yerel_olmayan_istek_kesilir():
    from turbulans_radar.cli.demo_ekranlari import ag_engelleyici

    class _Rota:
        def __init__(self, url):
            self.request = type("I", (), {"url": url})()
            self.sonuc = None

        def continue_(self):
            self.sonuc = "devam"

        def abort(self, neden):
            self.sonuc = neden

    engellenenler = []
    isle = ag_engelleyici(engellenenler)
    rotalar = [
        _Rota(u)
        for u in (
            "http://localhost:8000/harita/x.js",
            "data:image/png;base64,AA",
            "https://server.arcgisonline.com/t/1",
        )
    ]
    for rota in rotalar:
        isle(rota)
    assert [r.sonuc for r in rotalar] == ["devam", "devam", "internetdisconnected"]
    assert engellenenler == ["server.arcgisonline.com"]
