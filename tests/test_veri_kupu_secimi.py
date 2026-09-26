import os

import pytest

from turbulans_radar import config
from turbulans_radar.rota.rota_optimizasyonu import rota_simulasyonu_olustur, veri_kupune_eris
from turbulans_radar.veri.veri_yukleme import hava_durumu_dosyalari, kapsayan_veri_kupunu_bul, veri_kupu_adi


@pytest.fixture(scope="module", autouse=True)
def _kupler_var_mi():
    if not os.path.exists(config.HAVA_DURUMU_DOSYASI) or not os.path.isdir(config.EK_HAVA_DURUMU_KLASORU):
        pytest.skip("Gerçek ERA5 küpleri bulunamadı, küp seçimi testleri atlanıyor.")


def test_dosya_listesi_ana_kupu_ilk_sirada_icerir():
    dosyalar = hava_durumu_dosyalari()
    assert dosyalar[0] == config.HAVA_DURUMU_DOSYASI
    assert len(dosyalar) > 1


def test_noktalari_kapsayan_kup_secilir():
    assert veri_kupu_adi(veri_kupune_eris(39.0, 35.0, "2019-01-15T10:00:00", 10000)) == config.HAVA_DURUMU_DOSYASI
    assert veri_kupu_adi(veri_kupune_eris(45.0, -75.0, "2018-01-13T12:00:00", 11000)) == "2018_01.nc"


def test_hicbir_kupun_kapsamadigi_nokta_icin_none():
    assert kapsayan_veri_kupunu_bul([0.0], [0.0], ["2019-01-15T10:00:00"]) is None
    assert veri_kupune_eris(39.0, 35.0, "2019-01-15T10:00:00", 300) is None


def test_abd_rotasi_ek_kuple_gercek_ruzgarla_hesaplanir():
    sonuc = rota_simulasyonu_olustur(42.4, -71.0, 47.5, -79.0, 36000, "2018-01-13T12:00:00", "B738")
    assert sonuc["ruzgar_verisi_kaynagi"] == "era5_gercek"
    assert "2018_01.nc" in sonuc["aciklama"]


def test_kup_seviyelerinin_cok_altindaki_rota_kapsam_disidir():
    sonuc = rota_simulasyonu_olustur(41.0, 28.9, 36.9, 30.7, 3000, "2019-01-05T12:00:00", "A320")
    assert sonuc["ruzgar_verisi_kaynagi"] == "era5_kapsam_disi"
