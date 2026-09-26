import threading
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text, update

from turbulans_radar.depo import gorev_deposu
from turbulans_radar.depo import veritabani as vt
from turbulans_radar.depo.models import AnalizGorevi


@pytest.fixture(autouse=True)
def _db_erisilebilir_mi():
    try:
        motor = vt.motor_al()
        vt.tablolari_olustur(motor)
        with motor.connect() as baglanti:
            baglanti.execute(text("SELECT 1"))
    except Exception as hata:
        pytest.skip(f"PostgreSQL'e bağlanılamadı, görev deposu testleri atlanıyor: {hata}")


@pytest.fixture(autouse=True)
def _kuyruk_temizligi(gorev_kuyrugunu_temizle):
    yield


TEST_TURU = "test_kuyruk"


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
    assert {k: gorev[k] for k in ("durum", "tur", "ucus_numarasi", "tarih", "aciklama", "ozet", "deneme_sayisi")} == {
        "durum": "tamamlandi",
        "tur": "ucus",
        "ucus_numarasi": "DEPO1",
        "tarih": "2019-01-01",
        "aciklama": None,
        "ozet": [{"a": 1}],
        "deneme_sayisi": 0,
    }
    assert await gorev_deposu.gorev_getir("olmayan-id") is None


async def test_eski_bitmis_gorev_silinir_yeni_ve_kuyruktaki_kalir():
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
    assert (await gorev_deposu.gorev_getir(eski_calisan))["durum"] == "kuyrukta"
    await gorev_deposu.gorev_guncelle(eski_calisan, durum="hata")


async def test_kuyruktaki_gorev_bir_kez_alinir_ve_calisiyor_olur():
    gorev_id = await gorev_deposu.gorev_olustur(TEST_TURU, parametreler={"x": 1}, bildirim_webhook_url="http://a/b")
    gorev = gorev_deposu.siradaki_gorevi_al("isci-a", turler=(TEST_TURU,))
    assert (gorev["id"], gorev["parametreler"], gorev["bildirim_webhook_url"]) == (gorev_id, {"x": 1}, "http://a/b")
    assert gorev["deneme_sayisi"] == 1
    assert gorev_deposu.siradaki_gorevi_al("isci-b", turler=(TEST_TURU,)) is None
    durum = await gorev_deposu.gorev_getir(gorev_id)
    assert durum["durum"] == "calisiyor" and durum["baslama_zamani"] is not None


async def test_eszamanli_iscilerin_her_biri_farkli_gorev_alir():
    idler = {await gorev_deposu.gorev_olustur(TEST_TURU) for _ in range(6)}
    alinanlar, kilit = [], threading.Lock()

    def isci(ad):
        while (gorev := gorev_deposu.siradaki_gorevi_al(ad, turler=(TEST_TURU,))) is not None:
            with kilit:
                alinanlar.append(gorev["id"])

    is_parcaciklari = [threading.Thread(target=isci, args=(f"isci-{i}",)) for i in range(3)]
    for t in is_parcaciklari:
        t.start()
    for t in is_parcaciklari:
        t.join()
    assert sorted(alinanlar) == sorted(idler)


async def test_bitir_sadece_gorevi_tutan_isciye_izin_verir():
    gorev_id = await gorev_deposu.gorev_olustur(TEST_TURU)
    gorev_deposu.siradaki_gorevi_al("isci-a", turler=(TEST_TURU,))
    assert gorev_deposu.gorevi_bitir(gorev_id, "isci-b", "tamamlandi") is False
    assert gorev_deposu.gorevi_bitir(gorev_id, "isci-a", "tamamlandi", ozet=[{"ok": True}]) is True
    durum = await gorev_deposu.gorev_getir(gorev_id)
    assert (durum["durum"], durum["ozet"]) == ("tamamlandi", [{"ok": True}])
    assert durum["bitis_zamani"] is not None


async def _kalp_atisini_yaslandir(gorev_id, saniye):
    async with vt.async_oturum_al() as oturum:
        await oturum.execute(
            update(AnalizGorevi)
            .where(AnalizGorevi.id == gorev_id)
            .values(kalp_atisi=datetime.now(UTC) - timedelta(seconds=saniye))
        )
        await oturum.commit()


async def test_isci_olunce_gorev_yeniden_kuyruga_girer_deneme_bitince_yarida_kalir():
    gorev_id = await gorev_deposu.gorev_olustur(TEST_TURU)
    bayat = timedelta(seconds=60)

    gorev_deposu.siradaki_gorevi_al("olen-isci", turler=(TEST_TURU,))
    assert gorev_deposu.kalp_atisi_gonder([gorev_id], "olen-isci") == 1
    gorev_deposu.bayat_gorevleri_kurtar(bayat, maks_deneme=2)
    assert (await gorev_deposu.gorev_getir(gorev_id))["durum"] == "calisiyor"

    await _kalp_atisini_yaslandir(gorev_id, 120)
    gorev_deposu.bayat_gorevleri_kurtar(bayat, maks_deneme=2)
    assert (await gorev_deposu.gorev_getir(gorev_id))["durum"] == "kuyrukta"
    assert gorev_deposu.gorevi_bitir(gorev_id, "olen-isci", "tamamlandi") is False

    assert gorev_deposu.siradaki_gorevi_al("ikinci-isci", turler=(TEST_TURU,))["deneme_sayisi"] == 2
    await _kalp_atisini_yaslandir(gorev_id, 120)
    gorev_deposu.bayat_gorevleri_kurtar(bayat, maks_deneme=2)
    gorev = await gorev_deposu.gorev_getir(gorev_id)
    assert gorev["durum"] == "yarida_kaldi" and "deneme hakkı doldu" in gorev["aciklama"]


async def test_kuyruk_durumu_bekleyen_ve_calisan_gorevleri_sayar():
    once = await gorev_deposu.kuyruk_durumu()
    await gorev_deposu.gorev_olustur(TEST_TURU)
    await gorev_deposu.gorev_olustur(TEST_TURU)
    gorev_deposu.siradaki_gorevi_al("isci-a", turler=(TEST_TURU,))
    sonra = await gorev_deposu.kuyruk_durumu()
    assert sonra["kuyrukta"] == once["kuyrukta"] + 1
    assert sonra["calisiyor"] == once["calisiyor"] + 1
    assert sonra["en_eski_bekleme_saniye"] is not None
