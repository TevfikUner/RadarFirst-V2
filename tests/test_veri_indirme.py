from datetime import date

import pytest

from veri_indirme import (
    istek_boyutunu_dogrula,
    era5_veri_indir,
    IstekSinirAsimiHatasi,
    MAKS_ENLEM_BOYLAM_ARALIGI_DERECE,
    MAKS_GUN_SAYISI,
)


def test_sinirlar_icindeki_istek_kabul_edilir():
    # Hata fırlatmamalı.
    istek_boyutunu_dogrula(36.0, 42.0, 26.0, 35.0, date(2019, 1, 15), date(2019, 1, 16))


def test_cok_genis_enlem_araligi_reddedilir():
    with pytest.raises(IstekSinirAsimiHatasi):
        istek_boyutunu_dogrula(0.0, MAKS_ENLEM_BOYLAM_ARALIGI_DERECE + 5, 26.0, 30.0,
                                date(2019, 1, 1), date(2019, 1, 1))


def test_cok_genis_boylam_araligi_reddedilir():
    with pytest.raises(IstekSinirAsimiHatasi):
        istek_boyutunu_dogrula(36.0, 40.0, 0.0, MAKS_ENLEM_BOYLAM_ARALIGI_DERECE + 5,
                                date(2019, 1, 1), date(2019, 1, 1))


def test_tum_turkiye_gibi_asiri_genis_bolge_reddedilir():
    # Turkiye yaklasik 26 derece boylam genisliginde -- sinirin acikca disinda.
    with pytest.raises(IstekSinirAsimiHatasi):
        istek_boyutunu_dogrula(36.0, 42.0, 26.0, 45.0, date(2019, 1, 1), date(2019, 1, 1))


def test_cok_uzun_tarih_araligi_reddedilir():
    with pytest.raises(IstekSinirAsimiHatasi):
        istek_boyutunu_dogrula(36.0, 40.0, 26.0, 30.0,
                                date(2019, 1, 1), date(2019, 1, 1 + MAKS_GUN_SAYISI + 5))


def test_bir_yillik_veri_reddedilir():
    with pytest.raises(IstekSinirAsimiHatasi):
        istek_boyutunu_dogrula(36.0, 40.0, 26.0, 30.0, date(2019, 1, 1), date(2019, 12, 31))


def test_gecersiz_koordinat_siralamasi_value_error_verir():
    with pytest.raises(ValueError):
        istek_boyutunu_dogrula(42.0, 36.0, 26.0, 30.0, date(2019, 1, 1), date(2019, 1, 1))


def test_kuru_deneme_varsayilan_olarak_hicbir_sey_indirmez(capsys):
    sonuc = era5_veri_indir(36.0, 40.0, 26.0, 30.0, date(2019, 1, 1), date(2019, 1, 2))
    assert sonuc is None
    yakalanan = capsys.readouterr()
    assert "Kuru deneme" in yakalanan.out
    assert "GÖNDERİLMEDİ" in yakalanan.out


def test_sinir_asan_istek_kuru_denemede_bile_reddedilir():
    with pytest.raises(IstekSinirAsimiHatasi):
        era5_veri_indir(36.0, 42.0, 26.0, 45.0, date(2019, 1, 1), date(2019, 1, 1))
