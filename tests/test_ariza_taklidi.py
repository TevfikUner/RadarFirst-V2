import numpy as np
import pandas as pd
import pytest

from turbulans_radar import config
from turbulans_radar.ariza_taklidi import ariza_taklidi, etkin_taklit
from turbulans_radar.rota import rota_optimizasyonu as ro
from turbulans_radar.rota.bulgular import _bulgulari_olustur
from turbulans_radar.veri import veri_saglayicilari as vs

pytestmark = pytest.mark.birim

ENLEMLER = np.array([41.0, 36.9])
BOYLAMLAR = np.array([28.9, 30.7])


@pytest.fixture
def sahte_sigmet_deposu(monkeypatch):
    monkeypatch.setattr(ro, "gecerli_sigmetleri_getir", lambda *a, **k: [])
    monkeypatch.setattr(ro, "son_guncelleme_zamani", lambda: pd.Timestamp.now(tz="UTC").to_pydatetime())
    monkeypatch.setattr(ro, "sorunlu_kaynaklar", lambda: [])


def test_taklit_yalniz_baglam_icinde_etkin_ve_bilinmeyen_reddedilir():
    with ariza_taklidi("sigmet_bayat"):
        assert etkin_taklit() == "sigmet_bayat"
    assert etkin_taklit() is None
    with pytest.raises(ValueError), ariza_taklidi("veritabani_coktu"):
        pass


def test_sigmet_erisilemedi_taklidi(sahte_sigmet_deposu):
    _, ozet = ro._sigmet_katmanini_hazirla(None, ENLEMLER, BOYLAMLAR, "2019-01-05T12:00:00", 230.0)
    assert ozet["durum"] == "aktif_sigmet_yok"
    with ariza_taklidi("sigmet_erisilemedi"):
        katman, ozet = ro._sigmet_katmanini_hazirla(None, ENLEMLER, BOYLAMLAR, "2019-01-05T12:00:00", 230.0)
    assert katman is None and ozet["durum"] == "erisilemedi"


def test_sigmet_bayat_taklidi_gecmis_tarihte_de_bayat_der(sahte_sigmet_deposu):
    _, ozet = ro._sigmet_katmanini_hazirla(None, ENLEMLER, BOYLAMLAR, "2019-01-05T12:00:00", 230.0)
    assert ozet["bayat_mi"] is False
    with ariza_taklidi("sigmet_bayat"):
        _, ozet = ro._sigmet_katmanini_hazirla(None, ENLEMLER, BOYLAMLAR, "2019-01-05T12:00:00", 230.0)
    assert ozet["bayat_mi"] is True


def test_devre_kesici_taklidi_indirmeden_canli_hata_yazar(monkeypatch):
    monkeypatch.setattr(vs, "kapsayan_veri_kupunu_bul", lambda *a, **k: None)
    monkeypatch.setattr(vs, "canli_kup_hazirla", lambda *a, **k: pytest.fail("indirme denenmemeli"))
    durum = {}
    simdi = pd.Timestamp.now(tz="UTC")
    with ariza_taklidi("devre_kesici"):
        assert vs.veri_kupunu_sec([38.0], [32.0], [simdi], durum=durum) is None
    assert "devre kesici açık" in durum["canli_hata"]


def test_gercek_devre_kesici_mesaji_rota_uyarisina_tasinir(monkeypatch):
    monkeypatch.setattr(config, "CANLI_HAVA_VERISI_ETKIN", True)
    monkeypatch.setattr(vs, "kapsayan_veri_kupunu_bul", lambda *a, **k: None)

    def devre_acik(*a, **k):
        raise vs.DevreAcikHatasi(vs.devre_acik_mesaji("gfs", 240))

    monkeypatch.setattr(vs, "canli_kup_hazirla", devre_acik)
    durum = {}
    simdi = pd.Timestamp.now(tz="UTC")
    assert vs.veri_kupunu_sec([38.0], [32.0], [simdi], durum=durum) is None
    assert "devre kesici açık, indirme 240 sn" in durum["canli_hata"]


def test_taklitte_sentetik_bulgu_ilk_sirada():
    rota = {"riskli_sayisi": 0, "sigmet_ihlali": 0, "strateji": "yanal", "yanal_sapma_km": 0.0, "irtifa_m": 10000.0}
    with ariza_taklidi("sigmet_erisilemedi"):
        bulgular = _bulgulari_olustur(False, None, None, rota, rota, 10000.0, {"durum": "erisilemedi"}, True)
    assert bulgular[0]["kod"] == "ariza_taklidi" and "SENTETİK" in bulgular[0]["metin"]
    assert any(b["kod"] == "sigmet_erisilemedi" for b in bulgular)
    assert all(
        b["kod"] != "ariza_taklidi"
        for b in _bulgulari_olustur(False, None, None, rota, rota, 10000.0, {"durum": "aktif_sigmet_yok"}, True)
    )
