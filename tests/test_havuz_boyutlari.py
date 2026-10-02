import pytest

from turbulans_radar import config


def test_tek_surecte_varsayilan_havuz_degismez():
    assert config.havuz_boyutlari(1, 60, 10, 20) == (10, 20)


@pytest.mark.parametrize("surec", [2, 4, 8])
def test_cok_surecte_toplam_baglanti_butceyi_asmaz(surec):
    boyut, tasma = config.havuz_boyutlari(surec, 60, 10, 20)
    assert boyut >= 1 and surec * 2 * (boyut + tasma) <= 60


def test_dort_surecte_eski_varsayilan_postgresql_sinirini_asardi():
    assert 4 * 2 * (10 + 20) > 100
    boyut, tasma = config.havuz_boyutlari(4, 60, 10, 20)
    assert 4 * 2 * (boyut + tasma) <= 60


def test_cok_fazla_surecte_motor_basi_en_az_bir_arti_bir_kalir():
    assert config.havuz_boyutlari(32, 60, 10, 20) == (1, 1)
