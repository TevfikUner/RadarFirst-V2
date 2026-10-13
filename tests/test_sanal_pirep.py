import json

import numpy as np
import pandas as pd
import pytest
from sqlalchemy import text

from turbulans_radar import config
from turbulans_radar.analiz.sanal_pirep_hatti import izden_sanal_pirep_uret
from turbulans_radar.depo import sanal_pirep_deposu as depo
from turbulans_radar.depo import veritabani as vt
from turbulans_radar.dogrulama import sanal_pirep_dogrulama as dogrulama
from turbulans_radar.fizik.sanal_pirep import (
    METRE_FT,
    coklu_izden_olaylar,
    era5_uyumunu_ekle,
    kume_ozeti,
    olaylari_kumele,
    olaylari_tespit_et,
)

BASLANGIC = pd.Timestamp("2019-01-15 12:00", tz="UTC")
DEMO_IZI = "demo/opensky_onbellek/THY322_2019-01-15.parquet"


def _sentetik_iz(
    dakika=20, seviye_ft=35000.0, enlem=40.0, boylam=-100.0, icao24="e1e101", baslangic=BASLANGIC, sapma=None
):
    """Test için sentetik seyir izi: 1 sn örnekleme, 25 ft irtifa ve 64 ft/dk
    düşey hız kuantizasyonu (ADS-B). sapma: (başlangıç_sn, süre_sn, genlik_ft)."""
    saniye = np.arange(dakika * 60, dtype=float)
    irtifa_ft = np.full_like(saniye, seviye_ft)
    if sapma is not None:
        bas, sure, genlik = sapma
        icinde = (saniye >= bas) & (saniye <= bas + sure)
        irtifa_ft[icinde] += genlik * np.sin(np.pi * (saniye[icinde] - bas) / sure)
    dikey_ftdk = np.gradient(irtifa_ft, saniye) * 60.0
    return pd.DataFrame(
        {
            "zaman": baslangic + pd.to_timedelta(saniye, unit="s"),
            "icao24": icao24,
            "enlem": np.full_like(saniye, enlem),
            "boylam": boylam + saniye * 230.0 / (111_000.0 * np.cos(np.radians(enlem))),
            "baro_irtifa_m": np.round(irtifa_ft / 25.0) * 25.0 / METRE_FT,
            "geo_irtifa_m": irtifa_ft / METRE_FT,
            "dikey_hiz": np.round(dikey_ftdk / 64.0) * 64.0 / 196.850394,
        }
    )


def test_sakin_seyirde_olay_yok_ama_seyir_degerlendirilir():
    olaylar, ozet = olaylari_tespit_et(_sentetik_iz())
    assert olaylar.empty
    assert ozet["seyir_suresi_sn"] > 600


def test_irtifa_sapmasi_olay_uretir():
    olaylar, _ = olaylari_tespit_et(_sentetik_iz(sapma=(600, 20, 160.0)))
    assert len(olaylar) == 1
    olay = olaylar.iloc[0]
    assert 120 <= olay["sapma_ft"] <= 175
    assert abs(olay["seviye_ft"] - 35000) <= 25
    assert BASLANGIC + pd.Timedelta(seconds=600) <= olay["zaman"] <= BASLANGIC + pd.Timedelta(seconds=620)
    assert olay["maks_dikey_hiz_ftdk"] >= config.SANAL_PIREP_DIKEY_HIZ_TUTARLILIK_FTDK
    assert olay["icao24"] == "e1e101"
    assert olay["irtifa_kaynagi"] == "baro"


def _ti1_ile(iz, deger):
    iz = iz.copy()
    iz["ti1_indeksi"] = deger
    return iz


def test_era5_uyumu_ti1_esigine_gore_etiketler_olayi_elemez():
    iz = _sentetik_iz(sapma=(600, 20, 160.0))
    olaylar, _ = olaylari_tespit_et(iz)
    uyumlu = era5_uyumunu_ekle(olaylar, _ti1_ile(iz, config.TI1_ESIK_HAFIF * 2))
    uyumsuz = era5_uyumunu_ekle(olaylar, _ti1_ile(iz, config.TI1_ESIK_HAFIF / 10))
    assert len(uyumlu) == len(uyumsuz) == len(olaylar) == 1
    assert uyumlu["era5_uyumu"].iloc[0] == "uyumlu" and uyumsuz["era5_uyumu"].iloc[0] == "uyumsuz"
    assert uyumlu["era5_ti1"].iloc[0] == pytest.approx(config.TI1_ESIK_HAFIF * 2)


def test_era5_uyumu_ti1_yoksa_ya_da_kapsam_disindaysa_bilinmiyor():
    iz = _sentetik_iz(sapma=(600, 20, 160.0))
    olaylar, _ = olaylari_tespit_et(iz)
    assert era5_uyumunu_ekle(olaylar, iz)["era5_uyumu"].iloc[0] == "bilinmiyor"
    kapsam_disi = era5_uyumunu_ekle(olaylar, _ti1_ile(iz, np.nan))
    assert kapsam_disi["era5_uyumu"].iloc[0] == "bilinmiyor" and np.isnan(kapsam_disi["era5_ti1"].iloc[0])
    assert era5_uyumunu_ekle(olaylar.iloc[0:0], iz).empty


def test_esik_altindaki_sapma_olay_degildir():
    olaylar, _ = olaylari_tespit_et(_sentetik_iz(sapma=(600, 20, 50.0)))
    assert olaylar.empty


def test_duesey_hiz_tepkisi_olmayan_irtifa_sicramasi_elenir():
    iz = _sentetik_iz()
    iz.loc[600:602, "baro_irtifa_m"] += 2000 / METRE_FT
    olaylar, _ = olaylari_tespit_et(iz)
    assert olaylar.empty


def test_duesey_hiz_yoksa_yalniz_irtifa_sapmasi_kullanilir():
    iz = _sentetik_iz(sapma=(600, 20, 160.0)).drop(columns=["dikey_hiz"])
    olaylar, _ = olaylari_tespit_et(iz)
    assert len(olaylar) == 1
    assert np.isnan(olaylar.iloc[0]["maks_dikey_hiz_ftdk"])


def test_kademeli_tirmanis_seyir_sayilmaz():
    iz = _sentetik_iz(dakika=30)
    saniye = np.arange(len(iz), dtype=float)
    tirmanis = np.clip((saniye - 900) / 240.0, 0, 1) * 2000.0
    iz["baro_irtifa_m"] += tirmanis / METRE_FT
    iz["dikey_hiz"] = np.gradient(tirmanis, saniye) * 60.0 / 196.850394
    olaylar, _ = olaylari_tespit_et(iz)
    assert olaylar.empty


def test_seyir_alt_sinirinin_altinda_olay_uretilmez():
    olaylar, ozet = olaylari_tespit_et(_sentetik_iz(seviye_ft=20000.0, sapma=(600, 20, 160.0)))
    assert olaylar.empty
    assert ozet["seyir_suresi_sn"] == 0


def test_bosluk_kenarindaki_noktalar_seyir_sayilmaz():
    iz = _sentetik_iz(dakika=8, sapma=(250, 20, 160.0))
    iz = iz[(iz.index < 200) | (iz.index > 400)]
    olaylar, _ = olaylari_tespit_et(iz)
    assert olaylar.empty


def test_gercek_thy322_tirmanisinda_yanlis_alarm_yok():
    """Demo paketindeki gerçek OpenSky izi: tırmanış + seviyede kısa kayıt +
    1 saatlik veri boşluğu ve iki büyük irtifa hatası (2625 ft'te 33000 ft,
    31000 ft'te 1725 ft) içerir. Değerlendirilebilir seyir yoktur."""
    olaylar, ozet = olaylari_tespit_et(pd.read_parquet(DEMO_IZI))
    assert olaylar.empty
    assert ozet["seyir_suresi_sn"] == 0
    assert ozet["nokta_sayisi"] > 1000


def _olay(icao24, dakika, enlem, boylam, seviye=35000.0):
    zaman = BASLANGIC + pd.Timedelta(minutes=dakika)
    return {
        "icao24": icao24,
        "ucus_numarasi": None,
        "zaman": zaman,
        "baslangic": zaman,
        "bitis": zaman + pd.Timedelta(seconds=10),
        "sure_sn": 10.0,
        "enlem": enlem,
        "boylam": boylam,
        "seviye_ft": seviye,
        "sapma_ft": 150.0,
        "maks_dikey_hiz_ftdk": 640.0,
        "irtifa_kaynagi": "baro",
    }


def test_kumeleme_farkli_ucaklari_birlestirir_uzaktakini_ayirir():
    olaylar = pd.DataFrame(
        [
            _olay("e1e101", 0, 40.0, -100.0),
            _olay("e1e101", 2, 40.0, -99.9),
            _olay("e1e102", 10, 40.1, -100.1),
            _olay("e1e103", 10, 45.0, -90.0),
            _olay("e1e104", 10, 40.0, -100.0, seviye=39000.0),
        ]
    )
    kumelenmis = olaylari_kumele(olaylar)
    assert kumelenmis["kume"].nunique() == 3
    assert kumelenmis.loc[:2, "kume"].nunique() == 1
    assert list(kumelenmis["ucak_sayisi"]) == [2, 2, 2, 1, 1]
    ozet = {k["olay_sayisi"]: k for k in kume_ozeti(kumelenmis)}
    assert ozet[3]["dogrulanmis"] is True
    assert sum(k["dogrulanmis"] for k in kume_ozeti(kumelenmis)) == 1


def test_bos_olay_kumesi():
    bos = olaylari_kumele(pd.DataFrame(columns=list(_olay("x", 0, 0, 0))))
    assert bos.empty and "kume" in bos.columns
    assert kume_ozeti(bos) == []


def test_coklu_iz_ucak_basina_ayrilir():
    izler = pd.concat(
        [_sentetik_iz(icao24="e1e101", sapma=(600, 20, 160.0)), _sentetik_iz(icao24="e1e102", enlem=41.0)]
    )
    olaylar, ozetler = coklu_izden_olaylar(izler)
    assert list(olaylar["icao24"]) == ["e1e101"]
    assert set(ozetler["icao24"]) == {"e1e101", "e1e102"}


# --- Doğrulama (POD/POFD) ---


def test_wilson_araligi():
    alt, ust = dogrulama.wilson_araligi(0, 10)
    assert alt == 0.0 and ust == pytest.approx(0.2775, abs=1e-3)
    alt, ust = dogrulama.wilson_araligi(5, 10)
    assert alt == pytest.approx(0.2366, abs=1e-3) and ust == pytest.approx(0.7634, abs=1e-3)
    assert dogrulama.wilson_araligi(0, 0) is None


def _pirep(sinif=1, anahtar="test|1"):
    return {
        "pirep_anahtari": anahtar,
        "zaman": BASLANGIC + pd.Timedelta(minutes=10),
        "enlem": 40.0,
        "boylam": -98.0,
        "irtifa_ft": 35000.0,
        "sinif": sinif,
    }


def test_pirep_cevresi_sorgusu_bolum_filtresi_ve_sinirlar():
    sorgu, p = dogrulama.pirep_cevresi_sorgusu(_pirep())
    assert "hour >= ?" in sorgu and f"LIMIT {config.MAKS_STATE_VECTOR_SATIRI}" in sorgu
    zaman = int(_pirep()["zaman"].timestamp())
    pencere = config.SANAL_PIREP_DOGRULAMA_PENCERE_DAKIKA * 60
    assert p[0] % 3600 == 0 and p[1] % 3600 == 0 and p[1] - p[0] <= 2 * 3600
    assert p[2] == zaman - pencere and p[3] == zaman + pencere
    assert p[4] < 40.0 < p[5] and p[6] < -98.0 < p[7]
    assert p[8] < 35000 / METRE_FT < p[9]


def test_pirep_isabeti_tupteki_olayi_bulur():
    iz = _sentetik_iz(sapma=(600, 20, 160.0), boylam=-99.6)
    isabet = dogrulama.pirep_isabeti(_pirep(), iz)
    assert isabet["degerlendirilebilir"] and isabet["isabet"]
    sakin = dogrulama.pirep_isabeti(_pirep(), _sentetik_iz(boylam=-99.6))
    assert sakin["degerlendirilebilir"] and not sakin["isabet"]
    bos = dogrulama.pirep_isabeti(_pirep(), pd.DataFrame())
    assert not bos["degerlendirilebilir"]


def test_dogrulama_varsayilan_olarak_opensky_sorgusu_atmaz(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "SANAL_PIREP_ONBELLEK_KLASORU", str(tmp_path))
    pozitif, negatif = _pirep(1, "test|poz"), _pirep(0, "test|neg")
    monkeypatch.setattr(dogrulama, "pirepleri_sec", lambda *a, **k: [pozitif, negatif])
    _sentetik_iz(sapma=(600, 20, 160.0), boylam=-99.6).to_parquet(dogrulama.onbellek_yolu("test|poz"))

    def _yasak(*a, **k):
        raise AssertionError("OpenSky'a sorgu gönderilmemeliydi")

    import turbulans_radar.veri.veri_yukleme as veri_yukleme

    monkeypatch.setattr(veri_yukleme, "_sorgu_calistir", _yasak)
    sonuc = dogrulama.dogrulama_calistir(1, 1, maks_yeni_sorgu=0)
    assert sonuc["yeni_opensky_sorgusu"] == 0
    assert sonuc["onbellekte_olmayan_sorgulanmayan"] == 1
    assert sonuc["pod"]["isabet"] == 1 and sonuc["pod"]["degerlendirilebilir"] == 1
    assert sonuc["pofd"]["degerlendirilebilir"] == 0
    json.dumps(sonuc)


def test_dogrulama_yeni_sorguyu_sinirlar_ve_onbellege_yazar(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "SANAL_PIREP_ONBELLEK_KLASORU", str(tmp_path))
    monkeypatch.setattr(config, "TOPLU_ANALIZ_ISTEKLER_ARASI_BEKLEME_SANIYE", 0)
    pirepler = [_pirep(1, f"test|{i}") for i in range(3)]
    monkeypatch.setattr(dogrulama, "pirepleri_sec", lambda *a, **k: pirepler)
    sorgular = []

    def _sahte_sorgu(baglanti, sorgu, sutunlar, parametreler):
        sorgular.append(parametreler)
        iz = _sentetik_iz(boylam=-98.5)
        return pd.DataFrame(
            {
                "zaman_unix": (iz["zaman"] - pd.Timestamp(0, tz="UTC")).dt.total_seconds().astype(int),
                "icao24": iz["icao24"],
                "enlem": iz["enlem"],
                "boylam": iz["boylam"],
                "hiz": 230.0,
                "yon": 90.0,
                "dikey_hiz": iz["dikey_hiz"],
                "geo_irtifa_m": iz["geo_irtifa_m"],
                "baro_irtifa_m": iz["baro_irtifa_m"],
            }
        )

    import turbulans_radar.veri.veri_yukleme as veri_yukleme

    monkeypatch.setattr(veri_yukleme, "_sorgu_calistir", _sahte_sorgu)
    sonuc = dogrulama.dogrulama_calistir(3, 0, maks_yeni_sorgu=2, baglanti=object())
    assert len(sorgular) == 2 and sonuc["yeni_opensky_sorgusu"] == 2
    assert sonuc["onbellekte_olmayan_sorgulanmayan"] == 1
    assert sonuc["pod"]["degerlendirilebilir"] == 2 and sonuc["pod"]["isabet"] == 0
    dogrulama.dogrulama_calistir(3, 0, maks_yeni_sorgu=2, baglanti=object())
    assert len(sorgular) == 3


def test_cli_iz_komutu(capsys):
    dogrulama.ana(["iz", DEMO_IZI])
    cikti = capsys.readouterr().out
    assert '"olay_sayisi": 0' in cikti and "Olay yok." in cikti


# --- Veritabanı ---


@pytest.fixture
def motor():
    try:
        motor = vt.motor_al()
        vt.tablolari_olustur(motor)
    except Exception as hata:
        pytest.skip(f"PostgreSQL'e bağlanılamadı: {hata}")
    _temizle(motor)
    yield motor
    _temizle(motor)


def _temizle(motor):
    with motor.begin() as baglanti:
        baglanti.execute(text("DELETE FROM sanal_pirepler WHERE ucak LIKE 'e1e1%'"))


def test_kayit_tekrarlanmaz_ve_komsu_ucak_sayilir(motor):
    ilk = depo.olaylari_kaydet(pd.DataFrame([_olay("e1e101", 0, 40.0, -100.0)]), "test", motor=motor)
    assert len(ilk) == 1 and ilk[0]["ucak_sayisi"] == 1
    assert depo.olaylari_kaydet(pd.DataFrame([_olay("e1e101", 0, 40.0, -100.0)]), "test", motor=motor) == []
    ikinci = depo.olaylari_kaydet(
        pd.DataFrame([_olay("e1e102", 10, 40.1, -100.1), _olay("e1e103", 10, 45.0, -90.0)]), "test", motor=motor
    )
    assert [k["ucak_sayisi"] for k in ikinci] == [2, 1]
    okunan = depo.olaylari_getir(BASLANGIC - pd.Timedelta(hours=1), BASLANGIC + pd.Timedelta(hours=1), motor=motor)
    assert set(okunan["ucak"]) >= {"e1e101", "e1e102", "e1e103"}


def test_tarih_cizgisinde_komsu_bulunur(motor):
    depo.olaylari_kaydet(pd.DataFrame([_olay("e1e105", 0, 50.0, 179.9)]), "test", motor=motor)
    yeni = depo.olaylari_kaydet(pd.DataFrame([_olay("e1e106", 5, 50.0, -179.9)]), "test", motor=motor)
    assert yeni[0]["ucak_sayisi"] == 2


def test_hat_yalnizca_dogrulanmis_olayi_bildirir(motor):
    mesajlar = []
    ilk = izden_sanal_pirep_uret(
        _sentetik_iz(icao24="e1e101", sapma=(600, 20, 160.0)), "test", mesajlar.append, motor=motor
    )
    assert ilk["kaydedilen"] == 1 and ilk["bildirilen"] == 0 and mesajlar == []
    ikinci = izden_sanal_pirep_uret(
        _sentetik_iz(
            icao24="e1e102", enlem=40.05, baslangic=BASLANGIC + pd.Timedelta(minutes=5), sapma=(600, 20, -160.0)
        ),
        "test",
        mesajlar.append,
        motor=motor,
    )
    assert ikinci["bildirilen"] == 1
    assert mesajlar[0]["tip"] == "sanal_pirep" and mesajlar[0]["ucak_sayisi"] == 2
    assert mesajlar[0]["era5_uyumu"] == "bilinmiyor" and mesajlar[0]["era5_ti1"] is None
    json.dumps(mesajlar[0])
    with motor.connect() as baglanti:
        bildirim = baglanti.execute(
            text("SELECT bildirim_zamani FROM sanal_pirepler WHERE ucak = 'e1e102'")
        ).scalar_one()
    assert bildirim is not None
