import numpy as np

from kalibrasyon import katsayi_guven_araligi_hesapla, katsayi_kalibre_et


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


def test_guven_araligi_gurultusuz_veride_dar_ve_gercek_katsayiyi_kapsar():
    gercek_katsayi = 3.2
    rng = np.random.default_rng(0)
    ti1_degerleri = rng.uniform(1e-8, 1e-6, 500)
    pirep_edr_degerleri = np.tanh(
        ti1_degerleri * gercek_katsayi * 1e6
    )  # gürültüsüz -- her bootstrap örneklemi aynı ilişkiyi taşır

    alt_sinir, ust_sinir, tum_katsayilar = katsayi_guven_araligi_hesapla(
        ti1_degerleri, pirep_edr_degerleri, tekrar_sayisi=50, rastgele_uretec=np.random.default_rng(1)
    )

    # Grid-search ayrıklaştırması (adım_sayisi) yüzünden sınırlar gerçek
    # katsayıyı bire bir "kapsamayabilir" (kayan noktalı yuvarlama) -- küçük
    # bir tolerans, testin amacını (aralığın dar VE gerçek değere yakın
    # olması) bozmadan bu ayrıklaştırmayı hesaba katar.
    assert alt_sinir - 1e-6 <= gercek_katsayi <= ust_sinir + 1e-6
    assert ust_sinir - alt_sinir < 0.5  # gürültüsüz veride aralık dar olmalı
    assert len(tum_katsayilar) == 50


def test_guven_araligi_alt_sinir_ust_sinirdan_buyuk_olamaz():
    rng = np.random.default_rng(2)
    ti1_degerleri = rng.uniform(1e-8, 1e-6, 100)
    pirep_edr_degerleri = rng.uniform(0, 1, 100)  # tamamen gürültülü/rastgele gözlem

    alt_sinir, ust_sinir, _ = katsayi_guven_araligi_hesapla(
        ti1_degerleri, pirep_edr_degerleri, tekrar_sayisi=50, rastgele_uretec=np.random.default_rng(3)
    )

    assert alt_sinir <= ust_sinir


def test_guven_araligi_bos_girdi_value_error_verir():
    import pytest

    with pytest.raises(ValueError):
        katsayi_guven_araligi_hesapla([], [], tekrar_sayisi=10)


def test_guven_araligi_ayni_rastgele_uretecle_tekrarlanabilir():
    rng_tohumu = 42
    ti1_degerleri = np.random.default_rng(0).uniform(1e-8, 1e-6, 50)
    pirep_edr_degerleri = np.random.default_rng(0).uniform(0, 1, 50)

    sonuc_1 = katsayi_guven_araligi_hesapla(
        ti1_degerleri, pirep_edr_degerleri, tekrar_sayisi=20, rastgele_uretec=np.random.default_rng(rng_tohumu)
    )
    sonuc_2 = katsayi_guven_araligi_hesapla(
        ti1_degerleri, pirep_edr_degerleri, tekrar_sayisi=20, rastgele_uretec=np.random.default_rng(rng_tohumu)
    )

    assert sonuc_1[0] == sonuc_2[0]
    assert sonuc_1[1] == sonuc_2[1]
    assert np.array_equal(sonuc_1[2], sonuc_2[2])
