import time

import pandas as pd
import pytest
from sqlalchemy import text

from turbulans_radar import config, webhook
from turbulans_radar.depo import gorev_deposu
from turbulans_radar.depo import veritabani as vt
from turbulans_radar.isci import gorev_iscisi as gi

RISKLI = pd.DataFrame({"ti1_indeksi": [config.TI1_ESIK_ORTA_SIDDETLI * 2, 1e-8]})
SAKIN = pd.DataFrame({"ti1_indeksi": [1e-8]})


@pytest.fixture
def bildirimler(monkeypatch):
    yakalanan = []
    monkeypatch.setattr(gi, "bildirim_yayinla", lambda mesaj, motor=None: yakalanan.append(mesaj))
    return yakalanan


def _gorev(tur, **alanlar):
    return {"id": "g1", "tur": tur, "ucus_numarasi": "ISCI1", "tarih": "2019-01-01", "parametreler": None, **alanlar}


def test_api_analizi_veritabani_kaydini_zorunlu_tutar():
    assert gi.tek_ucus_analiz_et.keywords == {"kayit_zorunlu": True, "harita_uret": False}
    assert gi.rota_analiz_et.keywords == {"kayit_zorunlu": True, "harita_uret": False}


def test_riskli_ucus_analizi_tamamlanir_ve_uyari_yayinlanir(monkeypatch, bildirimler):
    monkeypatch.setattr(gi, "tek_ucus_analiz_et", lambda u, t: RISKLI)
    assert gi.gorevi_yurut(_gorev("ucus")) == {"durum": "tamamlandi"}
    assert bildirimler == [
        {
            "tip": "turbulans_uyarisi",
            "ucus_numarasi": "ISCI1",
            "tarih": "2019-01-01",
            "orta_siddetli_nokta_sayisi": 1,
            "maks_ti1": config.TI1_ESIK_ORTA_SIDDETLI * 2,
        }
    ]


def test_sakin_ya_da_bulunamayan_ucus_uyari_uretmez(monkeypatch, bildirimler):
    monkeypatch.setattr(gi, "tek_ucus_analiz_et", lambda u, t: SAKIN)
    assert gi.gorevi_yurut(_gorev("ucus")) == {"durum": "tamamlandi"}
    monkeypatch.setattr(gi, "tek_ucus_analiz_et", lambda u, t: None)
    assert gi.gorevi_yurut(_gorev("ucus")) == {"durum": "basarisiz"}
    assert bildirimler == []


def test_rota_gorevi_json_noktalarindan_izi_yeniden_kurar(monkeypatch, bildirimler):
    gorulen = {}

    def sahte_rota(rota_df, ucus_numarasi, tarih):
        gorulen["df"] = rota_df
        return SAKIN

    monkeypatch.setattr(gi, "rota_analiz_et", sahte_rota)
    noktalar = [
        {"zaman": "2019-01-15T07:05:00Z", "enlem": 39.1, "boylam": 33.5, "irtifa_m": 10500.0},
        {"zaman": "2019-01-15T07:00:00+00:00", "enlem": 39.0, "boylam": 33.0, "irtifa_m": None},
    ]
    assert gi.gorevi_yurut(_gorev("rota", parametreler={"noktalar": noktalar}))["durum"] == "tamamlandi"
    df = gorulen["df"]
    assert list(df["enlem"]) == [39.0, 39.1]
    assert str(df["zaman"].dt.tz) == "UTC" and df["geo_irtifa_m"].dtype == float
    assert set(df["ucus_numarasi"]) == {"ISCI1"}


def test_toplu_gorev_ozet_uretir_ve_riskli_ucusu_bildirir(monkeypatch, bildirimler):
    def sahte_toplu(ucus_listesi_df, kayit_zorunlu=False, ucus_tamamlandi=None, harita_uret=True):
        assert kayit_zorunlu is True and harita_uret is False
        assert list(ucus_listesi_df["ucus_numarasi"]) == ["TOPLU1"]
        ucus_tamamlandi("TOPLU1", "2019-01-01", RISKLI)
        return pd.DataFrame([{"ucus_numarasi": "TOPLU1", "durum": "başarılı", "maks_ti1": float("nan")}])

    monkeypatch.setattr(gi, "toplu_analiz_calistir", sahte_toplu)
    sonuc = gi.gorevi_yurut(
        _gorev("toplu", parametreler={"ucuslar": [{"ucus_numarasi": "TOPLU1", "tarih": "2019-01-01"}]})
    )
    assert sonuc == {
        "durum": "tamamlandi",
        "ozet": [{"ucus_numarasi": "TOPLU1", "durum": "başarılı", "maks_ti1": None}],
    }
    assert [m["ucus_numarasi"] for m in bildirimler] == ["TOPLU1"]


def test_analiz_hatasi_dostane_mesajla_hata_durumuna_cevrilir(monkeypatch):
    from turbulans_radar.depo.veritabani import VeritabaniKayitHatasi

    def kayit_basarisiz(ucus_numarasi, tarih):
        raise VeritabaniKayitHatasi("Sonuçlar veritabanına kaydedilemedi.")

    monkeypatch.setattr(gi, "tek_ucus_analiz_et", kayit_basarisiz)
    assert gi.gorevi_yurut(_gorev("ucus")) == {"durum": "hata", "aciklama": "Sonuçlar veritabanına kaydedilemedi."}
    assert gi.gorevi_yurut(_gorev("bilinmeyen"))["durum"] == "hata"


@pytest.mark.parametrize(
    "hata",
    [RuntimeError("postgresql://kullanici:gizli-sifre@db:5432/x"), FileNotFoundError(2, "yok", "/app/gizli-sifre.nc")],
)
def test_beklenmeyen_hata_metni_goreve_ham_yazilmaz(monkeypatch, caplog, hata):
    def patla(ucus_numarasi, tarih):
        raise hata

    monkeypatch.setattr(gi, "tek_ucus_analiz_et", patla)
    with caplog.at_level("ERROR"):
        sonuc = gi.gorevi_yurut(_gorev("ucus"))
    assert sonuc["durum"] == "hata"
    assert "gizli-sifre" not in sonuc["aciklama"]
    assert type(hata).__name__ in sonuc["aciklama"] and "g1" in sonuc["aciklama"]
    assert "gizli-sifre" in caplog.text


def test_baglanti_hatasi_dostane_mesaj_verir(monkeypatch):
    def patla(ucus_numarasi, tarih):
        raise ConnectionError("10.0.0.5:443 reddetti")

    monkeypatch.setattr(gi, "tek_ucus_analiz_et", patla)
    aciklama = gi.gorevi_yurut(_gorev("ucus"))["aciklama"]
    assert "İnternet bağlantısında" in aciklama and "10.0.0.5" not in aciklama


@pytest.fixture
def kuyruk_veritabani(gorev_kuyrugunu_temizle):
    try:
        with vt.motor_al().connect() as baglanti:
            baglanti.execute(text("SELECT 1"))
    except Exception as hata:
        pytest.skip(f"PostgreSQL'e bağlanılamadı: {hata}")


async def test_isci_kuyruktaki_gorevi_calistirir_ve_webhooka_sonucu_gonderir(monkeypatch, kuyruk_veritabani):
    gonderilen = []
    monkeypatch.setitem(
        gi.ISLEYICILER, "test_kuyruk", lambda gorev: {"durum": "tamamlandi", "ozet": [gorev["parametreler"]]}
    )
    monkeypatch.setattr(webhook.httpx, "post", lambda url, json, timeout: gonderilen.append((url, json)))
    monkeypatch.setenv("WEBHOOK_IZIN_VERILEN_HOSTLAR", "n8n.ornek.com")
    gorev_id = await gorev_deposu.gorev_olustur(
        "test_kuyruk", parametreler={"n": 7}, bildirim_webhook_url="http://n8n.ornek.com/webhook/x"
    )

    isci = gi.GorevIscisi(isci_sayisi=2, bekleme_saniye=0.05, turler=("test_kuyruk",)).baslat()
    try:
        for _ in range(200):
            if gonderilen:
                break
            time.sleep(0.05)
    finally:
        isci.durdur(zaman_asimi=5.0)

    gorev = await gorev_deposu.gorev_getir(gorev_id)
    assert (gorev["durum"], gorev["ozet"]) == ("tamamlandi", [{"n": 7}])
    url, govde = gonderilen[0]
    assert url == "http://n8n.ornek.com/webhook/x"
    assert govde["gorev_id"] == gorev_id and govde["durum"] == "tamamlandi"
    assert "parametreler" not in govde


def test_bildirim_notify_ile_gercekten_yayinlanir(kuyruk_veritabani):
    import asyncio

    import asyncpg

    async def dinle():
        baglanti = await asyncpg.connect(**vt.asyncpg_baglanti_parametreleri())
        gelen = asyncio.get_running_loop().create_future()
        await baglanti.add_listener(gi.BILDIRIM_KANALI, lambda *args: gelen.done() or gelen.set_result(args[3]))
        await asyncio.to_thread(gi.bildirim_yayinla, {"tip": "turbulans_uyarisi", "ucus_numarasi": "NOTIFY2"})
        try:
            return await asyncio.wait_for(gelen, timeout=5)
        finally:
            await baglanti.close()

    assert '"NOTIFY2"' in asyncio.run(dinle())


def _bakimi_kisa_calistir(isci):
    import threading

    isci._bakim_dur.clear()
    is_parcacigi = threading.Thread(target=isci._bakim_dongusu, daemon=True)
    is_parcacigi.start()
    time.sleep(0.2)
    isci._bakim_dur.set()
    is_parcacigi.join(2)


def test_bakim_dongusu_saglik_dosyasini_yalniz_veritabanina_ulasinca_tazeler(monkeypatch, tmp_path):
    import os

    dosya = tmp_path / "isci_saglik"
    monkeypatch.setattr(config, "ISCI_SAGLIK_DOSYASI", str(dosya))
    monkeypatch.setattr(config, "GOREV_KALP_ATISI_SANIYE", 0.02)
    monkeypatch.setattr(gi, "bayat_gorevleri_kurtar", lambda *a: {})
    isci = gi.GorevIscisi(turler=("yok",))

    isci._saglik_isaretle()
    os.utime(dosya, (0, 0))
    _bakimi_kisa_calistir(isci)
    assert dosya.stat().st_mtime > 1e9

    def veritabani_yok(*a):
        raise RuntimeError("veritabanı yok")

    monkeypatch.setattr(gi, "bayat_gorevleri_kurtar", veritabani_yok)
    os.utime(dosya, (0, 0))
    _bakimi_kisa_calistir(isci)
    assert dosya.stat().st_mtime == 0


def test_zaman_asimi_yalniz_suresi_sinirli_turlerde_ve_bir_kez(monkeypatch):
    monkeypatch.setattr(config, "GOREV_MAKS_SURE_SANIYE", 10.0)
    monkeypatch.setattr(config, "GOREV_SURE_SINIRSIZ_TURLER", ("ml_veri",))
    bitirilen = []
    monkeypatch.setattr(gi, "gorevi_bitir", lambda gorev_id, isci, **alanlar: bitirilen.append((gorev_id, alanlar)))
    isci = gi.GorevIscisi(turler=("yok",))
    isci._dur.set()
    isci._baslangiclar = {"eski": ("ucus", 0.0), "ml": ("ml_veri", 0.0), "yeni": ("ucus", 95.0)}
    isci._calisanlar = {"eski", "ml", "yeni"}

    assert isci.zaman_asimlarini_denetle(simdi=100.0) == ["eski"]
    assert isci._calisanlar == {"ml", "yeni"} and isci._zaman_asimi == {"eski"}
    assert bitirilen[0][0] == "eski" and bitirilen[0][1]["durum"] == "yarida_kaldi"
    assert "Zaman aşımı" in bitirilen[0][1]["aciklama"]
    assert isci.zaman_asimlarini_denetle(simdi=200.0) == ["yeni"]

    monkeypatch.setattr(config, "GOREV_MAKS_SURE_SANIYE", 0)
    isci._baslangiclar["baska"] = ("ucus", 0.0)
    assert isci.zaman_asimlarini_denetle(simdi=1e6) == []


async def test_takilan_gorev_zaman_asimina_duser_yerine_acilan_is_parcacigi_kuyrugu_isler(
    monkeypatch, kuyruk_veritabani
):
    monkeypatch.setattr(config, "GOREV_MAKS_SURE_SANIYE", 0.3)
    monkeypatch.setattr(config, "GOREV_KALP_ATISI_SANIYE", 0.05)
    durdurma_goruldu = []

    def takilan(gorev):
        while not gorev["_durdur"]():
            time.sleep(0.02)
        durdurma_goruldu.append(gorev["id"])
        return {"durum": "tamamlandi"}

    monkeypatch.setitem(gi.ISLEYICILER, "test_takilan", takilan)
    monkeypatch.setitem(gi.ISLEYICILER, "test_hizli", lambda gorev: {"durum": "tamamlandi"})
    takilan_id = await gorev_deposu.gorev_olustur("test_takilan")
    isci = gi.GorevIscisi(isci_sayisi=1, bekleme_saniye=0.05, turler=("test_takilan", "test_hizli")).baslat()
    try:
        for _ in range(100):
            if (await gorev_deposu.gorev_getir(takilan_id))["durum"] == "yarida_kaldi":
                break
            time.sleep(0.05)
        hizli_id = await gorev_deposu.gorev_olustur("test_hizli")
        for _ in range(100):
            if (await gorev_deposu.gorev_getir(hizli_id))["durum"] == "tamamlandi":
                break
            time.sleep(0.05)
    finally:
        isci.durdur(zaman_asimi=5.0)

    takilan_gorev = await gorev_deposu.gorev_getir(takilan_id)
    assert takilan_gorev["durum"] == "yarida_kaldi" and "Zaman aşımı" in takilan_gorev["aciklama"]
    assert durdurma_goruldu == [takilan_id]
    assert (await gorev_deposu.gorev_getir(hizli_id))["durum"] == "tamamlandi"
