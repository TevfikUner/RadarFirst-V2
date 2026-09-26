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

from turbulans_radar.depo import veritabani as vt

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
    return pd.DataFrame(
        {
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
        }
    )


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


def test_listeleme_ucus_numarasi_aramasi_filtreler(motor):
    vt.ucus_ve_olcumleri_kaydet(_ornek_df(), _TEST_UCUS_NUMARASI, _TEST_TARIH, motor)

    eslesen = vt.ucuslari_listele(motor, ucus_numarasi_arama=_TEST_UCUS_NUMARASI[:6])
    assert any(u["ucus_numarasi"] == _TEST_UCUS_NUMARASI for u in eslesen)

    eslesmeyen = vt.ucuslari_listele(motor, ucus_numarasi_arama="HICBIRZAMANOLMAYACAKBIRUCUS")
    assert eslesmeyen == []


def test_listeleme_tarih_araligi_filtreler(motor):
    vt.ucus_ve_olcumleri_kaydet(_ornek_df(), _TEST_UCUS_NUMARASI, _TEST_TARIH, motor)

    kapsayan = vt.ucuslari_listele(
        motor, ucus_numarasi_arama=_TEST_UCUS_NUMARASI, baslangic_tarih="1999-12-31", bitis_tarih="2000-01-02"
    )
    assert len(kapsayan) == 1

    kapsamayan = vt.ucuslari_listele(
        motor, ucus_numarasi_arama=_TEST_UCUS_NUMARASI, baslangic_tarih="2001-01-01", bitis_tarih="2001-01-02"
    )
    assert kapsamayan == []


async def test_ucus_sil_async_var_olani_siler(motor):
    vt.ucus_ve_olcumleri_kaydet(_ornek_df(), _TEST_UCUS_NUMARASI, _TEST_TARIH, motor)

    silindi_mi = await vt.ucus_sil_async(_TEST_UCUS_NUMARASI, _TEST_TARIH)
    assert silindi_mi is True
    assert vt.ucus_detayini_getir(_TEST_UCUS_NUMARASI, _TEST_TARIH, motor) is None


def test_ucus_sil_senkron_art_arda_iki_silmede_calisir(motor):
    """web_arayuzu.py (Streamlit) regresyonu: önceden asyncio.run(ucus_sil_async)
    kullanılıyordu ve İKİNCİ silme 'Event loop is closed' ile patlıyordu."""
    ikinci_ucus = _TEST_UCUS_NUMARASI + "2"
    vt.ucus_ve_olcumleri_kaydet(_ornek_df(), _TEST_UCUS_NUMARASI, _TEST_TARIH, motor)
    vt.ucus_ve_olcumleri_kaydet(_ornek_df(), ikinci_ucus, _TEST_TARIH, motor)
    try:
        assert vt.ucus_sil(_TEST_UCUS_NUMARASI, _TEST_TARIH, motor) is True
        assert vt.ucus_sil(ikinci_ucus, _TEST_TARIH, motor) is True
        assert vt.ucus_sil(ikinci_ucus, _TEST_TARIH, motor) is False
    finally:
        with motor.begin() as baglanti:
            baglanti.execute(text("DELETE FROM ucuslar WHERE ucus_numarasi = :un"), {"un": ikinci_ucus})


async def test_ucus_sil_async_olmayani_false_doner(motor):
    silindi_mi = await vt.ucus_sil_async("HICBIRZAMAN", "1999-01-01")
    assert silindi_mi is False


async def test_ucuslari_listele_async_toplam_sayi_limitten_bagimsizdir(motor):
    """toplam_sayi, limit UYGULANMADAN ÖNCEKİ filtre eşleşme sayısı olmalı --
    aksi halde istemci 'daha fazla kayıt var mı' bilemez."""
    vt.ucus_ve_olcumleri_kaydet(_ornek_df(), _TEST_UCUS_NUMARASI, _TEST_TARIH, motor)

    sonuc = await vt.ucuslari_listele_async(limit=1, ucus_numarasi_arama=_TEST_UCUS_NUMARASI)
    assert sonuc["toplam_sayi"] == 1
    assert len(sonuc["ucuslar"]) == 1

    sonuc_bos = await vt.ucuslari_listele_async(ucus_numarasi_arama="HICBIRZAMANOLMAYACAKBIRUCUS")
    assert sonuc_bos == {"toplam_sayi": 0, "ucuslar": []}


async def test_ucuslari_toplu_sil_async_filtresiz_value_error_verir(motor):
    with pytest.raises(ValueError):
        await vt.ucuslari_toplu_sil_async()


async def test_ucuslari_toplu_sil_async_eslesenleri_siler(motor):
    vt.ucus_ve_olcumleri_kaydet(_ornek_df(), _TEST_UCUS_NUMARASI, _TEST_TARIH, motor)

    silinen_sayisi = await vt.ucuslari_toplu_sil_async(ucus_numarasi_arama=_TEST_UCUS_NUMARASI)
    assert silinen_sayisi == 1
    assert vt.ucus_detayini_getir(_TEST_UCUS_NUMARASI, _TEST_TARIH, motor) is None
