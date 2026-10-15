import pytest

from turbulans_radar import config
from turbulans_radar.rota import performans_modeli


def test_kutle_azaldikca_saatlik_yakit_azalir():
    bir_saat = performans_modeli.seyir_yakiti("A320", 3600.0, 230.0, 11277.6)
    iki_saat = performans_modeli.seyir_yakiti("A320", 7200.0, 230.0, 11277.6)
    assert 2000 < bir_saat["yakit_kg"] < 3500
    assert iki_saat["yakit_kg"] - bir_saat["yakit_kg"] < bir_saat["yakit_kg"]
    assert bir_saat["nox_kg"] > 0


def test_seviye_degisimi_gidis_donus_net_ek_yakiti_kucuk_ve_simetrik():
    ek = performans_modeli.seviye_degisimi_ek_yakiti("A320", 10668.0, 11277.6, 230.0, 1500.0)
    assert ek == pytest.approx(performans_modeli.seviye_degisimi_ek_yakiti("A320", 11277.6, 10668.0, 230.0, 1500.0))
    assert abs(ek) < 50
    assert performans_modeli.seviye_degisimi_ek_yakiti("A320", 10668.0, 10668.0, 230.0, 1500.0) == 0.0


def test_baslangic_kutlesi_mtow_oranidir(monkeypatch):
    monkeypatch.setattr(config, "ROTA_SEYIR_KUTLE_ORANI", 0.5)
    assert performans_modeli.baslangic_kutlesi_kg("A320") == pytest.approx(78000 * 0.5)


def test_sabit_model_ya_da_desteklenmeyen_tip_none_doner(monkeypatch):
    assert performans_modeli.seyir_yakiti("C172", 3600.0, 60.0, 3000.0) is None
    monkeypatch.setattr(config, "ROTA_YAKIT_MODELI", "sabit")
    assert performans_modeli.kullanilabilir_mi("A320") is False
    assert performans_modeli.seyir_yakiti("A320", 3600.0, 230.0, 11277.6) is None
    assert performans_modeli.seviye_degisimi_ek_yakiti("A320", 10668.0, 11277.6, 230.0, 1500.0) is None
