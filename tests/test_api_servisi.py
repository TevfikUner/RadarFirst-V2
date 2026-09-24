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

import os

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
    yanit = await istemci.get("/api/v1/ucuslar/HICBIRZAMAN/1999-01-01", headers={"X-API-Key": api_anahtari})
    assert yanit.status_code == 404


async def test_analiz_tetikleme_ve_durum_sorgulama(istemci, api_anahtari, monkeypatch):
    """Gerçek OpenSky/Trino'ya bağlanmamak için tek_ucus_analiz_et sahteleniyor."""
    import pandas as pd

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
    import asyncio
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
