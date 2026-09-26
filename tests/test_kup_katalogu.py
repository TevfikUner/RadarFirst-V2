import os

import pytest
from sqlalchemy import text

from turbulans_radar import config
from turbulans_radar.depo import veritabani as vt
from turbulans_radar.depo.kup_katalogu import katalogu_listele, yerel_kupleri_katalogla
from turbulans_radar.veri.veri_yukleme import hava_durumu_dosyalari


@pytest.fixture(autouse=True)
def _gereksinimler():
    if not os.path.exists(config.HAVA_DURUMU_DOSYASI):
        pytest.skip(f"'{config.HAVA_DURUMU_DOSYASI}' bulunamadı.")
    try:
        vt.tablolari_olustur(vt.motor_al())
    except Exception as hata:
        pytest.skip(f"PostgreSQL'e bağlanılamadı: {hata}")


def _era5_kayit_sayisi():
    with vt.motor_al().connect() as baglanti:
        return baglanti.execute(text("SELECT count(*) FROM hava_durumu_kupleri WHERE kaynak = 'era5'")).scalar_one()


def test_yerel_era5_kupleri_kataloga_bir_kez_kaydedilir():
    dosyalar = hava_durumu_dosyalari()
    assert yerel_kupleri_katalogla() == len(dosyalar)
    assert yerel_kupleri_katalogla() == len(dosyalar)
    assert _era5_kayit_sayisi() == len(dosyalar)

    ana_kup = next(k for k in katalogu_listele(500) if k["dosya_yolu"] == config.HAVA_DURUMU_DOSYASI)
    assert ana_kup["kaynak"] == "era5"
    assert ana_kup["basinc_seviyeleri_hpa"] == [200.0, 250.0, 300.0]
    assert (ana_kup["enlem_min"], ana_kup["enlem_maks"]) == (36.0, 42.0)
