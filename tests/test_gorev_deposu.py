from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text, update

import gorev_deposu
import veritabani as vt
from models import AnalizGorevi


@pytest.fixture(autouse=True)
def _db_erisilebilir_mi():
    try:
        motor = vt.motor_al()
        vt.tablolari_olustur(motor)
        with motor.connect() as baglanti:
            baglanti.execute(text("SELECT 1"))
    except Exception as hata:
        pytest.skip(f"PostgreSQL'e bağlanılamadı, görev deposu testleri atlanıyor: {hata}")


async def _yaslandir(gorev_id, gun):
    async with vt.async_oturum_al() as oturum:
        await oturum.execute(
            update(AnalizGorevi)
            .where(AnalizGorevi.id == gorev_id)
            .values(olusturulma_zamani=datetime.now(UTC) - timedelta(days=gun))
        )
        await oturum.commit()


async def test_olustur_guncelle_getir():
    gorev_id = await gorev_deposu.gorev_olustur("ucus", ucus_numarasi="DEPO1", tarih="2019-01-01")
    await gorev_deposu.gorev_guncelle(gorev_id, durum="tamamlandi", ozet=[{"a": 1}])
    gorev = await gorev_deposu.gorev_getir(gorev_id)
    assert gorev == {
        "durum": "tamamlandi",
        "ucus_numarasi": "DEPO1",
        "tarih": "2019-01-01",
        "aciklama": None,
        "ozet": [{"a": 1}],
    }
    assert await gorev_deposu.gorev_getir("olmayan-id") is None


async def test_eski_bitmis_gorev_silinir_yeni_ve_calisan_kalir():
    eski = await gorev_deposu.gorev_olustur("ucus")
    yeni = await gorev_deposu.gorev_olustur("ucus")
    eski_calisan = await gorev_deposu.gorev_olustur("ucus")
    for gorev_id in (eski, yeni):
        await gorev_deposu.gorev_guncelle(gorev_id, durum="tamamlandi")
    await _yaslandir(eski, 30)
    await _yaslandir(eski_calisan, 30)

    await gorev_deposu.eski_gorevleri_temizle()

    assert await gorev_deposu.gorev_getir(eski) is None
    assert (await gorev_deposu.gorev_getir(yeni))["durum"] == "tamamlandi"
    assert (await gorev_deposu.gorev_getir(eski_calisan))["durum"] == "calisiyor"
    await gorev_deposu.gorev_guncelle(eski_calisan, durum="hata")


async def test_acilista_calisan_gorevler_yarida_kaldi_olur():
    gorev_id = await gorev_deposu.gorev_olustur("toplu")
    assert await gorev_deposu.yarida_kalan_gorevleri_isaretle() >= 1
    gorev = await gorev_deposu.gorev_getir(gorev_id)
    assert gorev["durum"] == "yarida_kaldi"
    assert "yeniden başlatıldı" in gorev["aciklama"]
