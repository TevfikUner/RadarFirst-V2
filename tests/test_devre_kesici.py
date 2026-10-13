from datetime import UTC, datetime, timedelta

import pytest

from turbulans_radar import config
from turbulans_radar.depo.kaynak_durumu import devre_kalan_saniye

pytestmark = pytest.mark.birim

SIMDI = datetime(2026, 10, 13, 12, 0, tzinfo=UTC)


def _kayit(hata, once_saniye):
    return {"ardisik_hata_sayisi": hata, "son_deneme_zamani": SIMDI - timedelta(seconds=once_saniye)}


@pytest.fixture(autouse=True)
def ayarlar(monkeypatch):
    monkeypatch.setattr(config, "DEVRE_KESICI_ESIK", 3)
    monkeypatch.setattr(config, "DEVRE_KESICI_TABAN_SANIYE", 300.0)
    monkeypatch.setattr(config, "DEVRE_KESICI_AZAMI_SANIYE", 3600.0)


def test_esik_altinda_ve_kayit_yokken_kapali():
    assert devre_kalan_saniye(None, SIMDI) == 0.0
    assert devre_kalan_saniye(_kayit(2, 0), SIMDI) == 0.0


def test_esikte_acik_bekleme_dolunca_yari_acik():
    assert devre_kalan_saniye(_kayit(3, 100), SIMDI) == pytest.approx(200.0)
    assert devre_kalan_saniye(_kayit(3, 300), SIMDI) == 0.0


def test_bekleme_her_hatada_ikiye_katlanir_azamiyle_sinirli():
    assert devre_kalan_saniye(_kayit(4, 0), SIMDI) == pytest.approx(600.0)
    assert devre_kalan_saniye(_kayit(10, 0), SIMDI) == pytest.approx(3600.0)


def test_esik_sifirsa_kapali(monkeypatch):
    monkeypatch.setattr(config, "DEVRE_KESICI_ESIK", 0)
    assert devre_kalan_saniye(_kayit(50, 0), SIMDI) == 0.0
