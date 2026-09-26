from turbulans_radar.hata_yardimcisi import dostane_hata_mesaji
from turbulans_radar.veri.kimlik_dogrulama import KimlikBilgisiEksikHatasi


def test_kimlik_hatasi_oldugu_gibi_dondurulur():
    hata = KimlikBilgisiEksikHatasi("OPENSKY_USERNAME eksik.")
    assert dostane_hata_mesaji(hata) == "OPENSKY_USERNAME eksik."


def test_dosya_bulunamadi_hatasi_dosya_adini_icerir():
    hata = FileNotFoundError(2, "No such file or directory")
    hata.filename = "ocak_2019_turbulans.nc"
    mesaj = dostane_hata_mesaji(hata)
    assert "ocak_2019_turbulans.nc" in mesaj


def test_baglanti_hatasi_internet_mesaji_verir():
    mesaj = dostane_hata_mesaji(ConnectionError("Connection refused"))
    assert "İnternet" in mesaj


def test_zaman_asimi_hatasi_internet_mesaji_verir():
    mesaj = dostane_hata_mesaji(TimeoutError("timed out"))
    assert "İnternet" in mesaj


def test_bilinmeyen_hata_turunu_ve_mesajini_icerir():
    mesaj = dostane_hata_mesaji(KeyError("beklenmedik_anahtar"))
    assert "KeyError" in mesaj
    assert "beklenmedik_anahtar" in mesaj


def test_trino_modulunden_gelen_hata_ozel_mesaj_verir():
    class SahteTrinoHatasi(Exception):
        pass

    SahteTrinoHatasi.__module__ = "trino.exceptions"
    mesaj = dostane_hata_mesaji(SahteTrinoHatasi("401 Access Denied"))
    assert "OpenSky" in mesaj or "Trino" in mesaj
