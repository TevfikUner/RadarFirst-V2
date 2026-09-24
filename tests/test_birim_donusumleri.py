import math

from birim_donusumleri import (
    basinc_hpa_to_irtifa_metre,
    en_yakin_basinc_seviyesi,
    irtifa_metre_to_basinc_hpa,
)


def test_deniz_seviyesinde_basinc_yaklasik_standart_atmosfer():
    assert math.isclose(irtifa_metre_to_basinc_hpa(0), 1013.25, rel_tol=1e-9)


def test_basinc_irtifa_donusumu_ters_islemdir():
    for irtifa in [0, 1000, 5500, 10_000, 11_000]:
        basinc = irtifa_metre_to_basinc_hpa(irtifa)
        geri_donusen_irtifa = basinc_hpa_to_irtifa_metre(basinc)
        assert math.isclose(irtifa, geri_donusen_irtifa, rel_tol=1e-6, abs_tol=1e-3)


def test_basinc_irtifa_ile_ters_orantili():
    basinc_dusuk_irtifa = irtifa_metre_to_basinc_hpa(0)
    basinc_yuksek_irtifa = irtifa_metre_to_basinc_hpa(10_000)
    assert basinc_yuksek_irtifa < basinc_dusuk_irtifa


def test_en_yakin_basinc_seviyesi_tam_esleme():
    seviyeler = [1000, 850, 700, 500, 250]
    assert en_yakin_basinc_seviyesi(700, seviyeler) == 700


def test_en_yakin_basinc_seviyesi_araya_dusen_deger():
    seviyeler = [1000, 850, 700, 500, 250]
    assert en_yakin_basinc_seviyesi(260, seviyeler) == 250
    assert en_yakin_basinc_seviyesi(240, seviyeler) == 250
