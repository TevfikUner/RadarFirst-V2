"""
test_api_servisi.py
----------------------
api_servisi.py testleri.

ÖNEMLİ: FastAPI'nin senkron TestClient'ı (starlette.testclient.TestClient),
her isteği KENDİ event loop'unda çalıştırır. api_servisi.py'deki okuma uç
noktaları asyncpg tabanlı, TEK bir engine singleton'ı üzerinden çalıştığı
için (gerçek bir uvicorn sürecinde olduğu gibi, tek event loop varsayımıyla)
TestClient ile karışınca "Event loop is closed" hatası verir -- bu bir
kod hatası DEĞİL, sadece test aracının event loop'u her istekte
yenilemesinden kaynaklanıyor. Bu yüzden testler httpx.AsyncClient +
ASGITransport ile TEK bir event loop üzerinden (gerçek dağıtımı taklit
ederek) yazıldı.

Gerçek bir PostgreSQL bağlantısı gerektirir; bağlanılamazsa atlanır (skip).
"""

import asyncio
import os
import time

import httpx
import pandas as pd
import pytest
from sqlalchemy import text
from starlette.testclient import TestClient

import api_servisi
import config
import veritabani as vt


@pytest.fixture(autouse=True)
def _db_erisilebilir_mi():
    try:
        motor = vt.motor_al()
        vt.tablolari_olustur(motor)
        with motor.connect() as baglanti:
            baglanti.execute(text("SELECT 1"))
    except Exception as hata:
        pytest.skip(f"PostgreSQL'e bağlanılamadı, API testleri atlanıyor: {hata}")


@pytest.fixture(autouse=True)
def _hiz_sinirini_sifirla():
    api_servisi._analiz_istek_zamanlari.clear()
    api_servisi._gorevler.clear()
    yield
    api_servisi._analiz_istek_zamanlari.clear()
    api_servisi._gorevler.clear()


@pytest.fixture
def api_anahtari():
    anahtar = os.environ.get("API_ANAHTARI")
    if not anahtar:
        pytest.skip("API_ANAHTARI tanımlı değil, .env dosyasını kontrol et.")
    return anahtar


@pytest.fixture
async def istemci():
    transport = httpx.ASGITransport(app=api_servisi.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_saglik_anahtarsiz_erisilebilir(istemci):
    yanit = await istemci.get("/saglik")
    assert yanit.status_code == 200
    assert yanit.json() == {"durum": "ayakta", "veritabani": None}


async def test_v1_anahtarsiz_401(istemci):
    yanit = await istemci.get("/api/v1/ucuslar")
    assert yanit.status_code == 401


async def test_v1_yanlis_anahtar_401(istemci):
    yanit = await istemci.get("/api/v1/ucuslar", headers={"X-API-Key": "yanlis-anahtar"})
    assert yanit.status_code == 401


async def test_v1_dogru_anahtar_200(istemci, api_anahtari):
    yanit = await istemci.get("/api/v1/ucuslar", headers={"X-API-Key": api_anahtari})
    assert yanit.status_code == 200
    govde = yanit.json()
    assert isinstance(govde["ucuslar"], list)
    assert isinstance(govde["toplam_sayi"], int)


async def test_olmayan_ucus_404(istemci, api_anahtari):
    yanit = await istemci.get("/api/v1/ucuslar/YOKUCUS1/1999-01-01", headers={"X-API-Key": api_anahtari})
    assert yanit.status_code == 404


async def test_gecersiz_ucus_numarasi_formati_422(istemci, api_anahtari):
    """8 karakterden uzun / alfanumerik olmayan ucus_numarasi 422 ile reddedilmeli."""
    yanit = await istemci.get("/api/v1/ucuslar/COKUZUNBIRUCUSNUMARASI/1999-01-01", headers={"X-API-Key": api_anahtari})
    assert yanit.status_code == 422


async def test_gecersiz_tarih_formati_422(istemci, api_anahtari):
    yanit = await istemci.get("/api/v1/ucuslar/TESTX/gecersiz-tarih", headers={"X-API-Key": api_anahtari})
    assert yanit.status_code == 422


async def test_limit_ust_siniri_asilinca_422(istemci, api_anahtari):
    yanit = await istemci.get("/api/v1/ucuslar?limit=999999", headers={"X-API-Key": api_anahtari})
    assert yanit.status_code == 422


async def test_analiz_istegi_gecersiz_ucus_numarasi_422(istemci, api_anahtari):
    yanit = await istemci.post(
        "/api/v1/analiz/ucus",
        json={"ucus_numarasi": "COKUZUNBIRUCUSNUMARASI", "tarih": "2019-01-01"},
        headers={"X-API-Key": api_anahtari},
    )
    assert yanit.status_code == 422


async def test_analiz_istegi_gecersiz_tarih_422(istemci, api_anahtari):
    yanit = await istemci.post(
        "/api/v1/analiz/ucus",
        json={"ucus_numarasi": "TESTX", "tarih": "01-01-2019"},
        headers={"X-API-Key": api_anahtari},
    )
    assert yanit.status_code == 422


async def test_nan_degerler_null_olarak_donuyor(istemci, api_anahtari):
    """Kapsam dışı noktalardaki NaN, veritabanına None olarak yazılıp API'den
    JSON 'null' olarak dönmeli -- 'Out of range float' hatası vermemeli."""
    import numpy as np

    df = pd.DataFrame(
        {
            "zaman": pd.to_datetime(["2019-01-01T00:00:00Z"]),
            "enlem": [40.0],
            "boylam": [30.0],
            "ti1_indeksi": [np.nan],
            "edr_proxy": [np.nan],
            "richardson_sayisi": [np.nan],
            "dinamik_kararsizlik": [None],
            "basinc_hpa": [np.nan],
        }
    )
    vt.ucus_ve_olcumleri_kaydet(df, "NANAPI", "2019-01-01")
    try:
        yanit = await istemci.get("/api/v1/ucuslar/NANAPI/2019-01-01", headers={"X-API-Key": api_anahtari})
        assert yanit.status_code == 200
        govde = yanit.json()
        assert govde["olcumler"][0]["ti1_indeksi"] is None
        assert govde["toplam_olcum_sayisi"] == 1
    finally:
        with vt.motor_al().begin() as baglanti:
            baglanti.execute(text("DELETE FROM ucuslar WHERE ucus_numarasi = 'NANAPI'"))


async def test_olcum_sayfalama(istemci, api_anahtari):

    df = pd.DataFrame(
        {
            "zaman": pd.to_datetime([f"2019-01-01T00:0{i}:00Z" for i in range(3)]),
            "enlem": [40.0, 40.1, 40.2],
            "boylam": [30.0, 30.1, 30.2],
            "ti1_indeksi": [1e-7, 2e-7, 3e-7],
        }
    )
    vt.ucus_ve_olcumleri_kaydet(df, "SAYFAAPI", "2019-01-01")
    try:
        yanit = await istemci.get(
            "/api/v1/ucuslar/SAYFAAPI/2019-01-01?olcum_limit=2&olcum_offset=1",
            headers={"X-API-Key": api_anahtari},
        )
        assert yanit.status_code == 200
        govde = yanit.json()
        assert govde["toplam_olcum_sayisi"] == 3
        assert len(govde["olcumler"]) == 2
    finally:
        with vt.motor_al().begin() as baglanti:
            baglanti.execute(text("DELETE FROM ucuslar WHERE ucus_numarasi = 'SAYFAAPI'"))


async def test_analiz_tetikleme_ve_durum_sorgulama(istemci, api_anahtari, monkeypatch):
    """Gerçek OpenSky/Trino'ya bağlanmamak için tek_ucus_analiz_et sahteleniyor."""

    def sahte_analiz(ucus_numarasi, tarih):
        return pd.DataFrame(
            {
                "zaman": pd.to_datetime(["2019-01-01T00:00:00Z"]),
                "enlem": [40.0],
                "boylam": [30.0],
                "ti1_indeksi": [1e-7],
                "edr_proxy": [0.1],
            }
        )

    monkeypatch.setattr(api_servisi, "tek_ucus_analiz_et", sahte_analiz)

    yanit = await istemci.post(
        "/api/v1/analiz/ucus",
        json={"ucus_numarasi": "TESTX", "tarih": "2019-01-01"},
        headers={"X-API-Key": api_anahtari},
    )
    assert yanit.status_code == 202
    gorev_id = yanit.json()["gorev_id"]

    # BackgroundTasks yanıt döndükten hemen sonra çalışır; anahtar burada
    # gerçek zamanlama garantisi vermez ama sahte fonksiyon anlık olduğu için
    # pratikte tamamlanmış olur.
    for _ in range(20):
        durum = await istemci.get(f"/api/v1/analiz/durum/{gorev_id}", headers={"X-API-Key": api_anahtari})
        if durum.json().get("durum") in ("tamamlandi", "hata", "basarisiz"):
            break
        await asyncio.sleep(0.05)
    assert durum.status_code == 200
    assert durum.json()["durum"] == "tamamlandi"


async def test_hiz_siniri_asilinca_429(istemci, api_anahtari, monkeypatch):
    monkeypatch.setattr(api_servisi, "tek_ucus_analiz_et", lambda un, t: None)

    son_yanit = None
    for _ in range(api_servisi._ANALIZ_PENCERE_BASINA_MAKS_ISTEK + 1):
        son_yanit = await istemci.post(
            "/api/v1/analiz/ucus",
            json={"ucus_numarasi": "TESTX", "tarih": "2019-01-01"},
            headers={"X-API-Key": api_anahtari},
        )
    assert son_yanit.status_code == 429


async def test_silme_hiz_siniri_asilinca_429(istemci, api_anahtari):
    """DELETE /ucuslar/{..} ve DELETE /ucuslar (toplu) AYNI 'silme' hız
    sınırlama penceresini paylaşır -- ikisi karışık çağrılsa bile toplam
    istek sayısı sınırı aşınca 429 dönmeli."""
    son_yanit = None
    for i in range(api_servisi._ANALIZ_PENCERE_BASINA_MAKS_ISTEK + 1):
        son_yanit = await istemci.delete(
            f"/api/v1/ucuslar/YOKUCUS{i % 9}/1999-01-01", headers={"X-API-Key": api_anahtari}
        )
    assert son_yanit.status_code == 429


async def test_bilinmeyen_gorev_id_404(istemci, api_anahtari):
    yanit = await istemci.get("/api/v1/analiz/durum/olmayan-id", headers={"X-API-Key": api_anahtari})
    assert yanit.status_code == 404


# --- WebSocket testleri: sync TestClient kullanılır (kendi iç thread/loop'unu
# yönetir, asyncpg engine'e dokunmadığı için yukarıdaki event-loop sorunu
# burada geçerli değil). ---


def test_websocket_anahtarsiz_reddedilir(api_anahtari):
    istemci = TestClient(api_servisi.app)
    with pytest.raises(Exception):
        with istemci.websocket_connect("/ws/uyarilar"):
            pass


def test_websocket_dogru_anahtarla_kabul_edilir(api_anahtari):
    istemci = TestClient(api_servisi.app)
    with istemci.websocket_connect(f"/ws/uyarilar?api_key={api_anahtari}"):
        pass


async def test_yuksek_riskli_noktalar_yayinlanir(monkeypatch):
    yayinlanan = []

    async def sahte_yayinla(mesaj):
        yayinlanan.append(mesaj)

    monkeypatch.setattr(api_servisi.baglanti_yoneticisi, "yayinla", sahte_yayinla)

    df_riskli = pd.DataFrame({"ti1_indeksi": [config.TI1_ESIK_ORTA_SIDDETLI + 1e-8]})
    await api_servisi._yuksek_riskli_noktalari_yayinla(df_riskli, "TESTX", "2019-01-01")
    assert len(yayinlanan) == 1
    assert yayinlanan[0]["tip"] == "turbulans_uyarisi"


async def test_dusuk_riskli_noktalar_yayinlanmaz(monkeypatch):
    yayinlanan = []

    async def sahte_yayinla(mesaj):
        yayinlanan.append(mesaj)

    monkeypatch.setattr(api_servisi.baglanti_yoneticisi, "yayinla", sahte_yayinla)

    df_sakin = pd.DataFrame({"ti1_indeksi": [config.TI1_ESIK_HAFIF / 2]})
    await api_servisi._yuksek_riskli_noktalari_yayinla(df_sakin, "TESTX", "2019-01-01")
    assert yayinlanan == []


# --- Görev kaydı temizliği (bellek sızıntısı düzeltmesi) ---


def test_eski_bitmis_gorev_temizlenir():
    api_servisi._gorevler["eski"] = {
        "durum": "tamamlandi",
        "_olusturulma": time.monotonic() - api_servisi._GOREV_SAKLAMA_SANIYE - 1,
    }
    api_servisi._eski_gorevleri_temizle()
    assert "eski" not in api_servisi._gorevler


def test_yeni_bitmis_gorev_silinmez():
    api_servisi._gorevler["yeni"] = {"durum": "tamamlandi", "_olusturulma": time.monotonic()}
    api_servisi._eski_gorevleri_temizle()
    assert "yeni" in api_servisi._gorevler


def test_calisan_eski_gorev_silinmez():
    """'calisiyor' durumundaki bir görev, ne kadar eski olursa olsun silinmemeli."""
    api_servisi._gorevler["calisiyor"] = {
        "durum": "calisiyor",
        "_olusturulma": time.monotonic() - api_servisi._GOREV_SAKLAMA_SANIYE - 1,
    }
    api_servisi._eski_gorevleri_temizle()
    assert "calisiyor" in api_servisi._gorevler


def test_gorev_disari_ver_dahili_alani_gizler():
    disari = api_servisi._gorev_disari_ver({"durum": "tamamlandi", "_olusturulma": 123.0})
    assert "_olusturulma" not in disari
    assert disari == {"durum": "tamamlandi"}


async def test_analiz_durumu_dahili_alani_sizdirmiyor(istemci, api_anahtari, monkeypatch):
    monkeypatch.setattr(api_servisi, "tek_ucus_analiz_et", lambda un, t: None)
    yanit = await istemci.post(
        "/api/v1/analiz/ucus",
        json={"ucus_numarasi": "TESTX", "tarih": "2019-01-01"},
        headers={"X-API-Key": api_anahtari},
    )
    gorev_id = yanit.json()["gorev_id"]
    for _ in range(20):
        durum = await istemci.get(f"/api/v1/analiz/durum/{gorev_id}", headers={"X-API-Key": api_anahtari})
        if durum.json().get("durum") != "calisiyor":
            break
        await asyncio.sleep(0.05)
    assert "_olusturulma" not in durum.json()


# --- Eşikler, SIGMET doğrulama ve 3D harita önyüzü ---


async def test_esikler_config_ile_ayni(istemci, api_anahtari):
    yanit = await istemci.get("/api/v1/esikler", headers={"X-API-Key": api_anahtari})
    assert yanit.status_code == 200
    govde = yanit.json()
    assert govde["ti1_esik_hafif"] == config.TI1_ESIK_HAFIF
    assert govde["ti1_esik_orta_siddetli"] == config.TI1_ESIK_ORTA_SIDDETLI


async def test_sigmet_dogrulama_olmayan_ucus_404(istemci, api_anahtari):
    yanit = await istemci.get(
        "/api/v1/ucuslar/YOKUCUS1/1999-01-01/sigmet-dogrulama", headers={"X-API-Key": api_anahtari}
    )
    assert yanit.status_code == 404


async def test_sigmet_dogrulama_gercek_http_istegi_yapmadan_calisir(istemci, api_anahtari, monkeypatch):
    """Gerçek IEM servisine bağlanmamak için sigmet_dogrulama sahteleniyor."""
    sahte_sonuc = {
        "toplam_turbulans_sigmeti": 1,
        "orta_siddetli_nokta_sayisi": 2,
        "sigmetle_ortusen_nokta_sayisi": 1,
        "ortusme_orani": 0.5,
        "sigmetler": [
            {
                "etiket": "TEST",
                "baslangic": "2019-01-15T00:00:00Z",
                "bitis": "2019-01-15T04:00:00Z",
                "poligon": [[40.0, 30.0], [41.0, 30.0], [41.0, 31.0]],
            }
        ],
    }
    monkeypatch.setattr(api_servisi, "ucus_sigmet_ile_karsilastir", lambda df: sahte_sonuc)

    df = pd.DataFrame(
        {
            "zaman": pd.to_datetime(["2019-01-15T01:00:00Z"]),
            "enlem": [40.5],
            "boylam": [30.5],
            "ti1_indeksi": [1e-6],
        }
    )
    vt.ucus_ve_olcumleri_kaydet(df, "SIGTEST1", "2019-01-15")
    try:
        yanit = await istemci.get(
            "/api/v1/ucuslar/SIGTEST1/2019-01-15/sigmet-dogrulama", headers={"X-API-Key": api_anahtari}
        )
        assert yanit.status_code == 200
        assert yanit.json() == sahte_sonuc
    finally:
        with vt.motor_al().begin() as baglanti:
            baglanti.execute(text("DELETE FROM ucuslar WHERE ucus_numarasi = 'SIGTEST1'"))


async def test_ucus_silme_var_olani_204_ile_siler(istemci, api_anahtari):
    df = pd.DataFrame(
        {
            "zaman": pd.to_datetime(["2019-01-01T00:00:00Z"]),
            "enlem": [40.0],
            "boylam": [30.0],
            "ti1_indeksi": [1e-7],
        }
    )
    vt.ucus_ve_olcumleri_kaydet(df, "SILAPI1", "2019-01-01")

    yanit = await istemci.delete("/api/v1/ucuslar/SILAPI1/2019-01-01", headers={"X-API-Key": api_anahtari})
    assert yanit.status_code == 204

    kontrol = await istemci.get("/api/v1/ucuslar/SILAPI1/2019-01-01", headers={"X-API-Key": api_anahtari})
    assert kontrol.status_code == 404


async def test_ucus_silme_olmayani_404_doner(istemci, api_anahtari):
    yanit = await istemci.delete("/api/v1/ucuslar/YOKUCUS1/1999-01-01", headers={"X-API-Key": api_anahtari})
    assert yanit.status_code == 404


async def test_toplu_silme_filtresiz_400_doner(istemci, api_anahtari):
    """Filtresiz bir toplu silme, tüm tabloyu YANLIŞLIKLA boşaltabileceği
    için kasıtlı olarak reddedilmeli."""
    yanit = await istemci.delete("/api/v1/ucuslar", headers={"X-API-Key": api_anahtari})
    assert yanit.status_code == 400


async def test_toplu_silme_filtreyle_eslesenleri_siler(istemci, api_anahtari):
    df = pd.DataFrame(
        {
            "zaman": pd.to_datetime(["2019-01-01T00:00:00Z"]),
            "enlem": [40.0],
            "boylam": [30.0],
            "ti1_indeksi": [1e-7],
        }
    )
    vt.ucus_ve_olcumleri_kaydet(df, "TOPSIL1", "2019-01-01")
    vt.ucus_ve_olcumleri_kaydet(df, "TOPSIL2", "2019-01-01")
    try:
        yanit = await istemci.delete(
            "/api/v1/ucuslar?ucus_numarasi_arama=TOPSIL", headers={"X-API-Key": api_anahtari}
        )
        assert yanit.status_code == 200
        assert yanit.json()["silinen_sayisi"] == 2

        kontrol = await istemci.get("/api/v1/ucuslar/TOPSIL1/2019-01-01", headers={"X-API-Key": api_anahtari})
        assert kontrol.status_code == 404
    finally:
        with vt.motor_al().begin() as baglanti:
            baglanti.execute(text("DELETE FROM ucuslar WHERE ucus_numarasi LIKE 'TOPSIL%'"))


async def test_ucuslar_ucus_numarasi_aramasi_filtreler(istemci, api_anahtari):
    df = pd.DataFrame(
        {
            "zaman": pd.to_datetime(["2019-01-01T00:00:00Z"]),
            "enlem": [40.0],
            "boylam": [30.0],
            "ti1_indeksi": [1e-7],
        }
    )
    vt.ucus_ve_olcumleri_kaydet(df, "ARAAPI1", "2019-01-01")
    try:
        yanit = await istemci.get(
            "/api/v1/ucuslar?ucus_numarasi_arama=ARAAPI1", headers={"X-API-Key": api_anahtari}
        )
        assert yanit.status_code == 200
        govde = yanit.json()
        assert govde["toplam_sayi"] == 1
        assert len(govde["ucuslar"]) == 1
        assert govde["ucuslar"][0]["ucus_numarasi"] == "ARAAPI1"
    finally:
        with vt.motor_al().begin() as baglanti:
            baglanti.execute(text("DELETE FROM ucuslar WHERE ucus_numarasi = 'ARAAPI1'"))


async def test_model_bilgisi_egitilmemisse_durustce_false_doner(istemci, api_anahtari, monkeypatch):
    monkeypatch.setattr(api_servisi, "model_bilgisini_yukle", lambda: None)
    yanit = await istemci.get("/api/v1/turbulans/model-bilgisi", headers={"X-API-Key": api_anahtari})
    assert yanit.status_code == 200
    assert yanit.json() == {
        "egitildi_mi": False,
        "secilen_model": None,
        "metrikler": None,
        "ozellik_sutunlari": None,
        "egitim_orneklem_sayisi": None,
        "test_orneklem_sayisi": None,
        "egitim_zamani": None,
    }


async def test_model_bilgisi_egitilmisse_metadata_doner(istemci, api_anahtari, monkeypatch):
    sahte_bilgi = {
        "secilen_model": "Random Forest",
        "metrikler": {"recall": 0.75},
        "ozellik_sutunlari": ["ti1_indeksi"],
        "egitim_orneklem_sayisi": 134,
        "test_orneklem_sayisi": 45,
        "egitim_zamani": "2024-01-01T00:00:00+00:00",
    }
    monkeypatch.setattr(api_servisi, "model_bilgisini_yukle", lambda: sahte_bilgi)
    yanit = await istemci.get("/api/v1/turbulans/model-bilgisi", headers={"X-API-Key": api_anahtari})
    assert yanit.status_code == 200
    govde = yanit.json()
    assert govde["egitildi_mi"] is True
    assert govde["secilen_model"] == "Random Forest"


async def test_model_versiyonlari_listesi_doner(istemci, api_anahtari, monkeypatch):
    sahte_versiyonlar = [
        {"versiyon_id": "v2", "secilen_model": "Random Forest", "metrikler": {"recall": 0.9}, "egitim_zamani": "2024-02-01T00:00:00+00:00"},
        {"versiyon_id": "v1", "secilen_model": "Random Forest", "metrikler": {"recall": 0.7}, "egitim_zamani": "2024-01-01T00:00:00+00:00"},
    ]
    monkeypatch.setattr(api_servisi, "model_versiyonlarini_listele", lambda: sahte_versiyonlar)
    yanit = await istemci.get("/api/v1/turbulans/model-versiyonlari", headers={"X-API-Key": api_anahtari})
    assert yanit.status_code == 200
    assert yanit.json() == sahte_versiyonlar


async def test_model_versiyonu_aktiflestir_basarili(istemci, api_anahtari, monkeypatch):
    sahte_aktif_bilgi = {
        "secilen_model": "Random Forest",
        "metrikler": {"recall": 0.9},
        "ozellik_sutunlari": ["ti1_indeksi"],
        "egitim_orneklem_sayisi": 179,
        "test_orneklem_sayisi": 45,
        "egitim_zamani": "2024-02-01T00:00:00+00:00",
    }
    monkeypatch.setattr(api_servisi, "versiyona_geri_don", lambda versiyon_id: sahte_aktif_bilgi)
    yanit = await istemci.post(
        "/api/v1/turbulans/model-versiyonlari/v2/aktiflestir", headers={"X-API-Key": api_anahtari}
    )
    assert yanit.status_code == 200
    govde = yanit.json()
    assert govde["egitildi_mi"] is True
    assert govde["egitim_zamani"] == "2024-02-01T00:00:00+00:00"


async def test_model_versiyonu_aktiflestir_bilinmeyen_id_404(istemci, api_anahtari, monkeypatch):
    def _hata_firlat(versiyon_id):
        raise ValueError(f"Bilinmeyen versiyon_id: '{versiyon_id}'.")

    monkeypatch.setattr(api_servisi, "versiyona_geri_don", _hata_firlat)
    yanit = await istemci.post(
        "/api/v1/turbulans/model-versiyonlari/olmayan/aktiflestir", headers={"X-API-Key": api_anahtari}
    )
    assert yanit.status_code == 404


async def test_harita3d_sayfasi_sunuluyor(istemci):
    yanit = await istemci.get("/harita/harita3d.html")
    assert yanit.status_code == 200
    assert "maplibregl" in yanit.text


# --- CSV/GeoJSON dışa aktarma ---


async def test_csv_disa_aktarma_olmayan_ucus_404(istemci, api_anahtari):
    yanit = await istemci.get("/api/v1/ucuslar/YOKUCUS1/1999-01-01/csv", headers={"X-API-Key": api_anahtari})
    assert yanit.status_code == 404


async def test_csv_disa_aktarma_gercek_veriyi_doner(istemci, api_anahtari):
    df = pd.DataFrame(
        {
            "zaman": pd.to_datetime(["2019-01-01T00:00:00Z", "2019-01-01T00:10:00Z"]),
            "enlem": [40.0, 40.1],
            "boylam": [30.0, 30.1],
            "ti1_indeksi": [1e-7, 5e-7],
        }
    )
    vt.ucus_ve_olcumleri_kaydet(df, "CSVAPI1", "2019-01-01")
    try:
        yanit = await istemci.get("/api/v1/ucuslar/CSVAPI1/2019-01-01/csv", headers={"X-API-Key": api_anahtari})
        assert yanit.status_code == 200
        assert yanit.headers["content-type"].startswith("text/csv")
        assert "attachment" in yanit.headers["content-disposition"]
        satirlar = yanit.text.strip().splitlines()
        assert len(satirlar) == 3  # başlık + 2 ölçüm
        assert "ti1_indeksi" in satirlar[0]
    finally:
        with vt.motor_al().begin() as baglanti:
            baglanti.execute(text("DELETE FROM ucuslar WHERE ucus_numarasi = 'CSVAPI1'"))


async def test_geojson_disa_aktarma_olmayan_ucus_404(istemci, api_anahtari):
    yanit = await istemci.get("/api/v1/ucuslar/YOKUCUS1/1999-01-01/geojson", headers={"X-API-Key": api_anahtari})
    assert yanit.status_code == 404


async def test_geojson_disa_aktarma_gecerli_feature_collection_doner(istemci, api_anahtari):
    df = pd.DataFrame(
        {
            "zaman": pd.to_datetime(["2019-01-01T00:00:00Z"]),
            "enlem": [40.5],
            "boylam": [30.5],
            "ti1_indeksi": [1e-7],
        }
    )
    vt.ucus_ve_olcumleri_kaydet(df, "GEOAPI1", "2019-01-01")
    try:
        yanit = await istemci.get("/api/v1/ucuslar/GEOAPI1/2019-01-01/geojson", headers={"X-API-Key": api_anahtari})
        assert yanit.status_code == 200
        assert yanit.headers["content-type"].startswith("application/geo+json")
        govde = yanit.json()
        assert govde["type"] == "FeatureCollection"
        assert len(govde["features"]) == 1
        ozellik = govde["features"][0]
        assert ozellik["geometry"]["coordinates"] == [30.5, 40.5]  # [boylam, enlem]
        assert ozellik["properties"]["ti1_indeksi"] == 1e-7
    finally:
        with vt.motor_al().begin() as baglanti:
            baglanti.execute(text("DELETE FROM ucuslar WHERE ucus_numarasi = 'GEOAPI1'"))


# --- Derin sağlık kontrolü ---


async def test_saglik_derin_gercek_db_ile_basarili(istemci):
    yanit = await istemci.get("/saglik?derin=true")
    assert yanit.status_code == 200
    assert yanit.json() == {"durum": "ayakta", "veritabani": "erisilebilir"}


async def test_saglik_derin_db_erisilemezse_503(istemci, monkeypatch):
    from sqlalchemy.ext.asyncio import create_async_engine

    bozuk_motor = create_async_engine("postgresql+asyncpg://olmayan:olmayan@127.0.0.1:1/olmayan")
    monkeypatch.setattr(api_servisi, "async_motor_al", lambda: bozuk_motor)
    yanit = await istemci.get("/saglik?derin=true")
    assert yanit.status_code == 503
    assert yanit.json()["veritabani"] == "erisilemiyor"
    await bozuk_motor.dispose()
