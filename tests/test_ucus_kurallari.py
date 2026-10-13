import pytest

from turbulans_radar.ucus_kurallari import tarih_gecerli_mi, ucus_bilgisini_dogrula, ucus_numarasi_gecerli_mi

pytestmark = pytest.mark.birim


@pytest.mark.parametrize("ucus", ["THY322", "a1", "THY12345"])
def test_gecerli_ucus_numaralari(ucus):
    assert ucus_numarasi_gecerli_mi(ucus)


@pytest.mark.parametrize("ucus", ["../etc", "THY 322", "THY322;DROP", "", "A" * 9, None, "THY322\n"])
def test_gecersiz_ucus_numaralari(ucus):
    assert not ucus_numarasi_gecerli_mi(ucus)


@pytest.mark.parametrize(
    "tarih,beklenen", [("2019-01-15", True), ("2019-13-45", False), ("15-01-2019", False), ("2019-01-15\n", False)]
)
def test_tarih(tarih, beklenen):
    assert tarih_gecerli_mi(tarih) is beklenen


def test_dogrula_bosluklari_kirpar_ve_hatayi_acik_soyler():
    assert ucus_bilgisini_dogrula(" THY322 ", " 2019-01-15 ") == ("THY322", "2019-01-15")
    with pytest.raises(ValueError, match="Uçuş numarası"):
        ucus_bilgisini_dogrula("../x", "2019-01-15")
    with pytest.raises(ValueError, match="Tarih"):
        ucus_bilgisini_dogrula("THY322", "dun")
