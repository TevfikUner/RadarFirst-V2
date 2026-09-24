"""
test_veritabani.py
---------------------
veritabani.py, gerçek bir PostgreSQL bağlantısı gerektirir ('.env'deki
POSTGRES_* değişkenleri). Bağlantı kurulamazsa (sunucu kapalı, '.env' eksik
vb.) bu testler atlanır (skip) -- tıpkı test_eslestirme.py'nin gerçek '.nc'
dosyası olmadan atlanması gibi.

Testler kendi kayıtlarını ('PYTEST_TEST_UCUSU' uçuş numarasıyla) oluşturup
sonunda temizler; gerçek veriye dokunmaz.
"""

import pandas as pd
import pytest
from sqlalchemy import text

import veritabani as vt

_TEST_UCUS_NUMARASI = "PYTEST_TEST_UCUSU"
_TEST_TARIH = "2000-01-01"


@pytest.fixture
def motor():
    try:
        motor = vt.motor_al()
        vt.tablolari_olustur(motor)
    except Exception as hata:
        pytest.skip(f"PostgreSQL'e bağlanılamadı, veritabanı testleri atlanıyor: {hata}")
    yield motor
    with motor.begin() as baglanti:
        baglanti.execute(
            text("DELETE FROM ucuslar WHERE ucus_numarasi = :un"),
            {"un": _TEST_UCUS_NUMARASI},
        )


def _ornek_df():
    return pd.DataFrame({
        "zaman": pd.to_datetime(["2000-01-01T00:00:00Z", "2000-01-01T00:10:00Z"]),
        "enlem": [40.0, 40.1],
        "boylam": [30.0, 30.1],
        "ti1_indeksi": [1e-7, 5e-7],
        "edr_proxy": [0.1, 0.3],
        "richardson_sayisi": [0.5, 0.1],
        "dinamik_kararsizlik": [False, True],
        "basinc_hpa": [250.0, 250.0],
        "icao24": ["test123", "test123"],
        "kalkis_havaalani": ["AAAA", "AAAA"],
        "varis_havaalani": ["BBBB", "BBBB"],
    })


def test_ucus_ve_olcumleri_kaydet_ve_geri_oku(motor):
    ucus_id = vt.ucus_ve_olcumleri_kaydet(_ornek_df(), _TEST_UCUS_NUMARASI, _TEST_TARIH, motor)
    assert ucus_id is not None

    detay = vt.ucus_detayini_getir(_TEST_UCUS_NUMARASI, _TEST_TARIH, motor)
    assert detay is not None
    assert detay["ucus"]["icao24"] == "test123"
    assert len(detay["olcumler"]) == 2


def test_ayni_ucus_yeniden_kaydedilince_eskisi_silinir(motor):
    vt.ucus_ve_olcumleri_kaydet(_ornek_df(), _TEST_UCUS_NUMARASI, _TEST_TARIH, motor)
    vt.ucus_ve_olcumleri_kaydet(_ornek_df(), _TEST_UCUS_NUMARASI, _TEST_TARIH, motor)

    with motor.connect() as baglanti:
        sayim = baglanti.execute(
            text("SELECT count(*) FROM ucuslar WHERE ucus_numarasi = :un"),
            {"un": _TEST_UCUS_NUMARASI},
        ).scalar_one()
    assert sayim == 1


def test_bilinmeyen_ucus_none_doner(motor):
    assert vt.ucus_detayini_getir("HICBIRZAMAN", "1999-01-01", motor) is None
