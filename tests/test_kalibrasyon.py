import numpy as np

from kalibrasyon import katsayi_kalibre_et


def test_bilinen_katsayidan_uretilen_veride_ayni_katsayiyi_bulur():
    gercek_katsayi = 3.2
    rng = np.random.default_rng(0)
    ti1_degerleri = rng.uniform(1e-8, 1e-6, 500)
    pirep_edr_degerleri = np.tanh(ti1_degerleri * gercek_katsayi * 1e6)  # gürültüsüz sentetik gözlem

    bulunan_katsayi, hata = katsayi_kalibre_et(ti1_degerleri, pirep_edr_degerleri)

    assert abs(bulunan_katsayi - gercek_katsayi) < 0.05
    assert hata < 1e-6


def test_bos_girdi_hata_verir():
    import pytest
    with pytest.raises(ValueError):
        katsayi_kalibre_et([], [])


def test_uzunluk_uyusmazligi_hata_verir():
    import pytest
    with pytest.raises(ValueError):
        katsayi_kalibre_et([1e-7, 2e-7], [0.1])
