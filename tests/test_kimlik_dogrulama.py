import pytest

from turbulans_radar.veri import kimlik_dogrulama as kd


@pytest.fixture(autouse=True)
def temiz_ortam(monkeypatch):
    for ad in kd.KULLANICI_DEGISKENLERI + kd.SIFRE_DEGISKENLERI:
        monkeypatch.delenv(ad, raising=False)
    return monkeypatch


def test_ingilizce_adlar_okunur(temiz_ortam):
    temiz_ortam.setenv("OPENSKY_USERNAME", "pilot1")
    temiz_ortam.setenv("OPENSKY_PASSWORD", "s1fre")
    assert kd.kimlik_bilgilerini_al() == ("pilot1", "s1fre")


def test_turkce_adlar_yedek_olarak_okunur(temiz_ortam):
    temiz_ortam.setenv("OPENSKY_KULLANICI", "pilot2")
    temiz_ortam.setenv("OPENSKY_SIFRE", "s2fre")
    assert kd.kimlik_bilgilerini_al() == ("pilot2", "s2fre")


def test_ingilizce_adlar_onceliklidir_ve_bos_deger_atlanir(temiz_ortam):
    temiz_ortam.setenv("OPENSKY_USERNAME", "  ")
    temiz_ortam.setenv("OPENSKY_KULLANICI", "pilot3")
    assert kd.kimlik_bilgilerini_al() == ("pilot3", None)


def test_kullanici_yoksa_anlasilir_hata(temiz_ortam):
    with pytest.raises(kd.KimlikBilgisiEksikHatasi, match="OPENSKY_KULLANICI"):
        kd.kimlik_bilgilerini_al()
