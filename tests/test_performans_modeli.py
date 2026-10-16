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


def test_iz_yakiti_sabit_izde_seyir_yakitina_esittir():
    zaman = [0.0, 1800.0, 3600.0]
    iz = performans_modeli.iz_yakiti("A320", zaman, [230.0] * 3, [11277.6] * 3)
    seyir = performans_modeli.seyir_yakiti("A320", 3600.0, 230.0, 11277.6, adim_s=1800.0)
    assert iz["yakit_kg"] == pytest.approx(seyir["yakit_kg"])
    tirmanis = performans_modeli.iz_yakiti("A320", [0.0, 60.0], [230.0] * 2, [10668.0, 11277.6])
    duz = performans_modeli.iz_yakiti("A320", [0.0, 60.0], [230.0] * 2, [10972.8] * 2)
    assert tirmanis["yakit_kg"] > duz["yakit_kg"]


def test_kutle_orani_parametresi_agir_ucakta_daha_cok_yakar():
    hafif = performans_modeli.seyir_yakiti("A320", 3600.0, 230.0, 11277.6, kutle_orani=0.70)
    agir = performans_modeli.seyir_yakiti("A320", 3600.0, 230.0, 11277.6, kutle_orani=0.90)
    varsayilan = performans_modeli.seyir_yakiti("A320", 3600.0, 230.0, 11277.6)
    assert hafif["yakit_kg"] < varsayilan["yakit_kg"] < agir["yakit_kg"]
    assert performans_modeli.baslangic_kutlesi_kg("A320", 0.70) < performans_modeli.baslangic_kutlesi_kg("A320")
