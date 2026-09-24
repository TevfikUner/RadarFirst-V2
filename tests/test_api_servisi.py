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
    assert yanit.json() == {"durum": "ayakta"}


async def test_v1_anahtarsiz_401(istemci):
    yanit = await istemci.get("/api/v1/ucuslar")
    assert yanit.status_code == 401


async def test_v1_yanlis_anahtar_401(istemci):
    yanit = await istemci.get("/api/v1/ucuslar", headers={"X-API-Key": "yanlis-anahtar"})
    assert yanit.status_code == 401


async def test_v1_dogru_anahtar_200(istemci, api_anahtari):
    yanit = await istemci.get("/api/v1/ucuslar", headers={"X-API-Key": api_anahtari})
    assert yanit.status_code == 200
    assert isinstance(yanit.json(), list)


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

    df = pd.DataFrame({
        "zaman": pd.to_datetime(["2019-01-01T00:00:00Z"]),
        "enlem": [40.0], "boylam": [30.0],
        "ti1_indeksi": [np.nan], "edr_proxy": [np.nan],
        "richardson_sayisi": [np.nan], "dinamik_kararsizlik": [None],
        "basinc_hpa": [np.nan],
    })
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

    df = pd.DataFrame({
        "zaman": pd.to_datetime([f"2019-01-01T00:0{i}:00Z" for i in range(3)]),
        "enlem": [40.0, 40.1, 40.2], "boylam": [30.0, 30.1, 30.2],
        "ti1_indeksi": [1e-7, 2e-7, 3e-7],
    })
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
        return pd.DataFrame({
            "zaman": pd.to_datetime(["2019-01-01T00:00:00Z"]),
            "enlem": [40.0], "boylam": [30.0],
            "ti1_indeksi": [1e-7], "edr_proxy": [0.1],
        })

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
