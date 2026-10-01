import os

import numpy as np
import pandas as pd
import pytest
from sqlalchemy import text

from turbulans_radar import config
from turbulans_radar.depo import veritabani as vt
from turbulans_radar.dogrulama import rota_backtest as rb
from turbulans_radar.fizik.eslestirme import rotayi_hava_durumuyla_eslestir
from turbulans_radar.veri.veri_yukleme import hava_durumu_onbellekli_yukle


def _olcum_df(dakikalar, ti1_dolu):
    zamanlar = pd.Timestamp("2019-01-15T10:00:00", tz="UTC") + pd.to_timedelta(dakikalar, unit="min")
    return pd.DataFrame(
        {
            "zaman": zamanlar.as_unit("us"),
            "enlem": np.linspace(39.0, 39.5, len(dakikalar)),
            "boylam": np.linspace(30.0, 35.0, len(dakikalar)),
            "ti1_indeksi": [1e-7 if d else np.nan for d in ti1_dolu],
            "irtifa_m": 10000.0,
        }
    )


def test_seyir_bolumu_en_uzun_kesintisiz_bloktur():
    dakikalar = list(range(0, 12)) + list(range(40, 70))
    seyir = rb._seyir_bolumu(_olcum_df(dakikalar, [True] * len(dakikalar)))
    assert len(seyir) == 30
    assert pd.Timestamp(seyir["zaman"].iloc[0]) == pd.Timestamp("2019-01-15T10:40:00", tz="UTC")


def test_kapsam_ici_nokta_yetersizse_backtest_yapilmaz():
    with pytest.raises(rb.BacktestYapilamadiHatasi):
        rb._seyir_bolumu(_olcum_df(list(range(20)), [False] * 15 + [True] * 5))


def test_yeniden_ornekleme_uclari_ve_mikrosaniye_zamanlari_korur():
    seyir = _olcum_df(list(range(30)), [True] * 30)
    ornek = rb._yeniden_ornekle(seyir, 41)
    assert len(ornek["enlem"]) == 41
    assert ornek["enlem"][0] == pytest.approx(39.0) and ornek["boylam"][-1] == pytest.approx(35.0)
    assert ornek["zaman"][0] == pd.Timestamp("2019-01-15T10:00:00", tz="UTC")
    assert ornek["zaman"][-1] == pd.Timestamp("2019-01-15T10:29:00", tz="UTC")


@pytest.fixture
def kayitli_ucus():
    if not os.path.exists(config.HAVA_DURUMU_DOSYASI):
        pytest.skip(f"'{config.HAVA_DURUMU_DOSYASI}' bulunamadı.")
    try:
        vt.tablolari_olustur(vt.motor_al())
    except Exception as hata:
        pytest.skip(f"PostgreSQL'e bağlanılamadı: {hata}")
    n = 60
    rota = pd.DataFrame(
        {
            "zaman": pd.Timestamp("2019-01-05T12:00:00", tz="UTC") + pd.to_timedelta(np.arange(n), unit="min"),
            "enlem": np.linspace(41.0, 36.9, n),
            "boylam": np.linspace(28.9, 30.7, n),
            "geo_irtifa_m": 28000 * 0.3048,
        }
    )
    eslesmis = rotayi_hava_durumuyla_eslestir(rota, hava_durumu_onbellekli_yukle(config.HAVA_DURUMU_DOSYASI))
    vt.ucus_ve_olcumleri_kaydet(eslesmis, "BTEST1", "2019-01-05")
    yield "BTEST1", "2019-01-05"
    with vt.motor_al().begin() as baglanti:
        baglanti.execute(text("DELETE FROM ucuslar WHERE ucus_numarasi = 'BTEST1'"))


def test_uctan_uca_backtest_kaydedilir_ve_listelenir(kayitli_ucus):
    sonuc = rb.ucus_backtest_et(*kayitli_ucus)
    assert sonuc["seyir_irtifasi_ft"] == 28000.0
    assert sonuc["veri_kaynagi"] == "era5"
    assert sonuc["gercek_riskli_oran"] is not None
    assert sonuc["optimize_riskli_oran"] <= sonuc["buyuk_daire_riskli_oran"]
    assert sonuc["optimize_sigmet_ihlali"] == 0
    # 2019 Türkiye: ne sistemin SIGMET arşivi ne IEM kapsıyor -- kanıt yok, "sıfır" değil.
    assert sonuc["kanit_kaynaklari"] == []
    assert sonuc["gercek_turb_sigmet"] is None and sonuc["optimize_mog_pirep"] is None

    ikinci = rb.ucus_backtest_et(*kayitli_ucus)
    kayitlar = [s for s in rb.backtestleri_listele()["sonuclar"] if s["ucus_numarasi"] == "BTEST1"]
    assert len(kayitlar) == 1
    assert kayitlar[0]["optimize_mesafe_km"] == pytest.approx(ikinci["optimize_mesafe_km"])
    assert ("BTEST1", "2019-01-05") not in rb.backtest_edilmemis_ucuslar(limit=1000)


def test_toplu_backtestte_bir_ucusun_beklenmeyen_hatasi_digerlerini_durdurmaz(monkeypatch):
    monkeypatch.setattr(
        rb,
        "backtest_edilmemis_ucuslar",
        lambda limit, motor=None: [("HATA1", "2019-01-01"), ("IYI1", "2019-01-01"), ("KUPSUZ", "2019-01-01")],
    )

    def sahte_backtest(ucus_numarasi, tarih, motor=None):
        if ucus_numarasi == "HATA1":
            raise ConnectionError("veritabanı bağlantısı koptu")
        if ucus_numarasi == "KUPSUZ":
            raise rb.BacktestYapilamadiHatasi("küp yok")
        return {}

    monkeypatch.setattr(rb, "ucus_backtest_et", sahte_backtest)
    sonuclar = rb.toplu_backtest(limit=10)
    assert [s["durum"] for s in sonuclar] == ["hata", "tamamlandi", "atlandi"]


def _kare(tehlike, enlem0, enlem1, boylam0, boylam1):
    return {
        "id": None,
        "fir_kodu": "LTAA",
        "tehlike": tehlike,
        "taban_ft": None,
        "tavan_ft": None,
        "gecerlilik_baslangic": pd.Timestamp("2019-01-05T11:00:00", tz="UTC"),
        "gecerlilik_bitis": pd.Timestamp("2019-01-05T15:00:00", tz="UTC"),
        "poligon": [[boylam0, enlem0], [boylam1, enlem0], [boylam1, enlem1], [boylam0, enlem1], [boylam0, enlem0]],
    }


def test_backtestte_a_yildiz_turbulans_sigmetini_gormez_ve_bagimsiz_kanit_kaydedilir(kayitli_ucus, monkeypatch):
    from turbulans_radar.dogrulama.bagimsiz_kanit import BagimsizKanit

    turb = _kare("TURB", 38.5, 39.5, 29.4, 30.2)
    oraj = _kare("TS", 10.0, 11.0, 10.0, 11.0)
    monkeypatch.setattr(rb, "gecerli_sigmetleri_getir", lambda *a, **k: [turb, oraj])
    a_yildizin_gordugu = []
    gercek_simulasyon = rb.rota_simulasyonu_olustur

    def izleyen_simulasyon(*args, **kwargs):
        a_yildizin_gordugu.append([s["tehlike"] for s in kwargs["sigmetler"]])
        return gercek_simulasyon(*args, **kwargs)

    monkeypatch.setattr(rb, "rota_simulasyonu_olustur", izleyen_simulasyon)

    def sahte_kanit(baslangic, bitis, kutu, motor=None):
        pirep = pd.DataFrame(
            [(pd.Timestamp("2019-01-05T12:29:00", tz="UTC"), 39.0, 29.78, 28000.0, 1)],
            columns=["zaman", "enlem", "boylam", "irtifa_ft", "sinif"],
        )
        return BagimsizKanit(kaynaklar=["test"], turb_sigmetleri=[turb], pirepler=pirep)

    sonuc = rb.ucus_backtest_et(*kayitli_ucus, kanit_toplayici=sahte_kanit)
    assert a_yildizin_gordugu == [["TS"]]
    assert sonuc["kanit_kaynaklari"] == ["test"]
    assert sonuc["gercek_turb_sigmet"] > 0
    assert (sonuc["gercek_pirep_raporu"], sonuc["gercek_mog_pirep"]) == (1, 1)

    ozet = rb.backtestleri_listele()["ozet"]
    assert ozet["bagimsiz_kanitli_ucus_sayisi"] >= 1
    assert ozet["turb_sigmet_karsilastirilabilir_ucus"] >= 1


def test_seyir_bolumu_tekil_hatali_noktayi_ve_tirmanisi_disarida_birakir():
    """THY322 deseni: kalkışta 2775 ft'te tek bir kapsam içi nokta, 11 dk sonra
    tırmanış ve seyir. Seyir, gerçek seyirle başlamalı."""
    dakikalar = [0] + list(range(11, 16)) + list(range(16, 60))
    olcum = _olcum_df(dakikalar, [True] * len(dakikalar))
    olcum.loc[0, "irtifa_m"] = 2775 * 0.3048
    olcum.loc[1:5, "irtifa_m"] = np.linspace(6900, 8500, 5)
    seyir = rb._seyir_bolumu(olcum)
    assert pd.Timestamp(seyir["zaman"].iloc[0]) == pd.Timestamp("2019-01-15T10:16:00", tz="UTC")
    assert (seyir["irtifa_m"] == 10000.0).all()
