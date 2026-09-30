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

import httpx
import pandas as pd
import pytest
from sqlalchemy import text
from starlette.testclient import TestClient

from turbulans_radar import config
from turbulans_radar.api import api_servisi
from turbulans_radar.depo import gorev_deposu
from turbulans_radar.depo import veritabani as vt
from turbulans_radar.isci import gorev_iscisi


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
def _kuyruk_temizligi(gorev_kuyrugunu_temizle):
    yield


async def _gorev_bitene_kadar_bekle(istemci, api_anahtari, gorev_id, deneme=200):
    for _ in range(deneme):
        durum = (await istemci.get(f"/api/v1/analiz/durum/{gorev_id}", headers={"X-API-Key": api_anahtari})).json()
        if durum["durum"] not in ("kuyrukta", "calisiyor"):
            return durum
        await asyncio.sleep(0.05)
    return durum


def _hiz_sayaclarini_sil():
    with vt.motor_al().begin() as baglanti:
        baglanti.execute(text("DELETE FROM hiz_siniri_sayaclari"))


@pytest.fixture(autouse=True)
def _hiz_sinirini_sifirla():
    _hiz_sayaclarini_sil()
    yield
    _hiz_sayaclarini_sil()


@pytest.fixture(autouse=True)
def _saglik_onbellegini_temizle():
    api_servisi._saglik_onbellegi.update(zaman=None, sonuc=None)
    yield
    api_servisi._saglik_onbellegi.update(zaman=None, sonuc=None)


@pytest.fixture(autouse=True)
def _rota_onbellegini_temizle():
    api_servisi._rota_onbellegi.temizle()
    yield
    api_servisi._rota_onbellegi.temizle()


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
    assert yanit.json() == {"durum": "ayakta", "veritabani": None, "kontroller": None, "uyarilar": None}


async def test_v1_anahtarsiz_401(istemci):
    yanit = await istemci.get("/api/v1/ucuslar")
    assert yanit.status_code == 401


async def test_v1_yanlis_anahtar_401(istemci):
    yanit = await istemci.get("/api/v1/ucuslar", headers={"X-API-Key": "yanlis-anahtar"})
    assert yanit.status_code == 401


async def test_v1_ascii_disi_anahtar_500_degil_401(istemci, api_anahtari):
    yanit = await istemci.get("/api/v1/esikler", headers={"X-API-Key": "anahtar-é".encode("latin-1")})
    assert yanit.status_code == 401


@pytest.mark.parametrize("bilet", ["²³.pilot.abc", "9999999999.pilot.é", "1.2", ""])
def test_bozuk_ws_bileti_hata_atmadan_reddedilir(api_anahtari, bilet):
    assert api_servisi.ws_bileti_gecerli_mi(bilet) is False


def test_ws_bileti_gecerli_ve_suresi_dolunca_gecersiz(api_anahtari):
    assert api_servisi.ws_bileti_gecerli_mi(api_servisi.ws_bileti_uret("pilot"))
    assert not api_servisi.ws_bileti_gecerli_mi(api_servisi.ws_bileti_uret("pilot", simdi=0))


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


async def test_analiz_tetikleme_ve_durum_sorgulama(istemci, api_anahtari, monkeypatch, calisan_isci):
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

    monkeypatch.setattr(gorev_iscisi, "tek_ucus_analiz_et", sahte_analiz)

    yanit = await istemci.post(
        "/api/v1/analiz/ucus",
        json={"ucus_numarasi": "TESTX", "tarih": "2019-01-01"},
        headers={"X-API-Key": api_anahtari},
    )
    assert yanit.status_code == 202
    assert yanit.json()["durum"] == "kuyrukta"
    durum = await _gorev_bitene_kadar_bekle(istemci, api_anahtari, yanit.json()["gorev_id"])
    assert durum["durum"] == "tamamlandi"
    assert (durum["tur"], durum["deneme_sayisi"]) == ("ucus", 1)
    assert durum["baslama_zamani"] is not None and durum["bitis_zamani"] is not None


async def test_hiz_siniri_asilinca_429(istemci, api_anahtari):
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


async def test_iscinin_notify_uyarisi_websocket_istemcilerine_iletilir(monkeypatch):
    """İşçi başka bir süreçte olabilir: uyarı PostgreSQL NOTIFY ile gelir."""
    yayinlanan = []

    async def sahte_yayinla(mesaj):
        yayinlanan.append(mesaj)

    monkeypatch.setattr(api_servisi.baglanti_yoneticisi, "yayinla", sahte_yayinla)
    dinleyici = asyncio.create_task(api_servisi._uyari_dinleyicisi(yeniden_deneme_saniye=0.1))
    try:
        for _ in range(100):
            await asyncio.to_thread(
                gorev_iscisi.bildirim_yayinla, {"tip": "turbulans_uyarisi", "ucus_numarasi": "NOTIFY1"}
            )
            await asyncio.sleep(0.1)
            if yayinlanan:
                break
        assert yayinlanan and yayinlanan[0] == {"tip": "turbulans_uyarisi", "ucus_numarasi": "NOTIFY1"}
    finally:
        dinleyici.cancel()


async def test_analiz_durumu_dahili_alani_sizdirmiyor(istemci, api_anahtari):
    yanit = await istemci.post(
        "/api/v1/analiz/rota",
        json={
            "ucus_numarasi": "GIZLI1",
            "noktalar": [
                {"zaman": "2019-01-15T10:00:00", "enlem": 39.0, "boylam": 35.0},
                {"zaman": "2019-01-15T10:01:00", "enlem": 39.0, "boylam": 35.1},
            ],
            "bildirim_webhook_url": "https://n8n.ornek.com/webhook/gizli",
        },
        headers={"X-API-Key": api_anahtari},
    )
    durum = (
        await istemci.get(f"/api/v1/analiz/durum/{yanit.json()['gorev_id']}", headers={"X-API-Key": api_anahtari})
    ).json()
    assert durum["durum"] == "kuyrukta" and durum["tur"] == "rota"
    assert not {"parametreler", "isci", "bildirim_webhook_url", "kalp_atisi"} & set(durum)


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
        yanit = await istemci.delete("/api/v1/ucuslar?ucus_numarasi_arama=TOPSIL", headers={"X-API-Key": api_anahtari})
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
        yanit = await istemci.get("/api/v1/ucuslar?ucus_numarasi_arama=ARAAPI1", headers={"X-API-Key": api_anahtari})
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
        {
            "versiyon_id": "v2",
            "secilen_model": "Random Forest",
            "metrikler": {"recall": 0.9},
            "egitim_zamani": "2024-02-01T00:00:00+00:00",
        },
        {
            "versiyon_id": "v1",
            "secilen_model": "Random Forest",
            "metrikler": {"recall": 0.7},
            "egitim_zamani": "2024-01-01T00:00:00+00:00",
        },
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
    assert yanit.json()["veritabani"] == "erisilebilir"


async def test_saglik_derin_db_erisilemezse_503(istemci, monkeypatch):
    from sqlalchemy.ext.asyncio import create_async_engine

    bozuk_motor = create_async_engine("postgresql+asyncpg://olmayan:olmayan@127.0.0.1:1/olmayan")
    monkeypatch.setattr(api_servisi, "async_motor_al", lambda: bozuk_motor)
    yanit = await istemci.get("/saglik?derin=true")
    assert yanit.status_code == 503
    assert yanit.json()["veritabani"] == "erisilemiyor"
    await bozuk_motor.dispose()


# --- Şema, görev kaydı, webhook ve toplu yayın düzeltmeleri ---


async def test_ucak_profilleri_yakit_akisini_icerir(istemci, api_anahtari):
    yanit = await istemci.get("/api/v1/simulasyon/ucak-profilleri", headers={"X-API-Key": api_anahtari})
    assert yanit.status_code == 200
    assert all(p["yakit_akisi_kg_saat"] > 0 for p in yanit.json())


async def test_turbulans_tahmini_kapsam_disinda_200_doner(istemci, api_anahtari):
    yanit = await istemci.post(
        "/api/v1/turbulans/tahmin",
        json={"enlem": 5.0, "boylam": -150.0, "irtifa_ft": 34000, "zaman": "2019-01-15T10:00:00"},
        headers={"X-API-Key": api_anahtari},
    )
    assert yanit.status_code == 200
    assert yanit.json()["kapsam_icinde_mi"] is False


async def test_turbulans_tahmini_kapsam_icinde_ti1_doner(istemci, api_anahtari):
    if api_servisi.veri_kupune_eris() is None:
        pytest.skip(f"'{config.HAVA_DURUMU_DOSYASI}' bulunamadı.")
    yanit = await istemci.post(
        "/api/v1/turbulans/tahmin",
        json={"enlem": 39.0, "boylam": 35.0, "irtifa_ft": 34000, "zaman": "2019-01-15T10:00:00"},
        headers={"X-API-Key": api_anahtari},
    )
    assert yanit.status_code == 200
    govde = yanit.json()
    assert govde["kapsam_icinde_mi"] is True
    assert govde["ti1_indeksi"] >= 0
    assert govde["ti1_guvenilirlik_notu"] and "KANITLANMAMIŞTIR" in govde["ti1_guvenilirlik_notu"]


async def test_gorev_kuyruga_eklenir_ve_islenmeden_kuyrukta_kalir():
    gorev_id = await api_servisi._gorev_olustur("ucus", ucus_numarasi="TESTX", tarih="2019-01-01")
    gorev = await gorev_deposu.gorev_getir(gorev_id)
    assert gorev["durum"] == "kuyrukta"
    assert gorev["ucus_numarasi"] == "TESTX"


@pytest.mark.parametrize(
    "url",
    ["ftp://ornek.com/x", "http://169.254.169.254/latest/meta-data", "http://0.0.0.0:8000/", "yol/olmayan-url"],
)
async def test_gecersiz_webhook_url_422(istemci, api_anahtari, url):
    yanit = await istemci.post(
        "/api/v1/analiz/ucus",
        json={"ucus_numarasi": "TESTX", "tarih": "2019-01-01", "bildirim_webhook_url": url},
        headers={"X-API-Key": api_anahtari},
    )
    assert yanit.status_code == 422


def test_webhook_izin_listesi_disindaki_host_reddedilir(monkeypatch):
    monkeypatch.setenv("WEBHOOK_IZIN_VERILEN_HOSTLAR", "n8n.ornek.com, localhost")
    assert api_servisi._webhook_url_dogrula("http://localhost:5678/webhook/x") == "http://localhost:5678/webhook/x"
    with pytest.raises(ValueError):
        api_servisi._webhook_url_dogrula("https://baska.ornek.com/hook")


def test_websocket_api_anahtari_tanimsizsa_reddedilir(monkeypatch):
    monkeypatch.delenv("API_ANAHTARI", raising=False)
    istemci = TestClient(api_servisi.app)
    with pytest.raises(Exception):
        with istemci.websocket_connect("/ws/uyarilar?api_key=herhangi"):
            pass


# --- OpenSky'sız rota analizi (POST /analiz/rota) ---


@pytest.mark.parametrize(
    "govde",
    [
        {"ucus_numarasi": "ROTA1", "noktalar": [{"zaman": "2019-01-15T10:00:00", "enlem": 39.0, "boylam": 35.0}]},
        {
            "ucus_numarasi": "ROTA1",
            "noktalar": [
                {"zaman": "2019-01-15T10:00:00", "enlem": 95.0, "boylam": 35.0},
                {"zaman": "2019-01-15T10:01:00", "enlem": 39.0, "boylam": 35.0},
            ],
        },
        {
            "ucus_numarasi": "ROTA/../1",
            "noktalar": [
                {"zaman": "2019-01-15T10:00:00", "enlem": 39.0, "boylam": 35.0},
                {"zaman": "2019-01-15T10:01:00", "enlem": 39.0, "boylam": 35.1},
            ],
        },
    ],
)
async def test_rota_analizi_gecersiz_istek_422(istemci, api_anahtari, govde):
    yanit = await istemci.post("/api/v1/analiz/rota", json=govde, headers={"X-API-Key": api_anahtari})
    assert yanit.status_code == 422


async def test_rota_analizi_uctan_uca_kaydeder(istemci, api_anahtari, monkeypatch, tmp_path, calisan_isci):
    if api_servisi.veri_kupune_eris() is None:
        pytest.skip(f"'{config.HAVA_DURUMU_DOSYASI}' bulunamadı.")
    from turbulans_radar.analiz import ucus_analizi

    monkeypatch.setattr(ucus_analizi.config, "CIKTI_KLASORU", str(tmp_path))
    noktalar = [
        {"zaman": "2019-01-15T10:00:00+03:00", "enlem": 39.0, "boylam": 33.0, "irtifa_m": 10500.0},
        {"zaman": "2019-01-15T07:05:00Z", "enlem": 39.1, "boylam": 33.5, "irtifa_m": 10500.0},
        {"zaman": "2019-01-15T07:10:00", "enlem": 39.2, "boylam": 34.0, "irtifa_m": None},
    ]
    try:
        yanit = await istemci.post(
            "/api/v1/analiz/rota",
            json={"ucus_numarasi": "ROTAAPI1", "noktalar": noktalar},
            headers={"X-API-Key": api_anahtari},
        )
        assert yanit.status_code == 202
        durum = await _gorev_bitene_kadar_bekle(istemci, api_anahtari, yanit.json()["gorev_id"])
        assert durum["durum"] == "tamamlandi", durum
        assert durum["tarih"] == "2019-01-15"

        detay = (await istemci.get("/api/v1/ucuslar/ROTAAPI1/2019-01-15", headers={"X-API-Key": api_anahtari})).json()
        assert detay["toplam_olcum_sayisi"] == 3
        ti1 = [o["ti1_indeksi"] for o in detay["olcumler"]]
        assert ti1[0] is not None and ti1[1] is not None
        assert ti1[2] is None
    finally:
        with vt.motor_al().begin() as baglanti:
            baglanti.execute(text("DELETE FROM ucuslar WHERE ucus_numarasi = 'ROTAAPI1'"))


# --- Canlı SIGMET uç noktaları ---


async def test_sigmet_guncelle_ozet_doner(istemci, api_anahtari, monkeypatch):
    sahte_ozet = {
        "kaydedilen": 3,
        "sonlandirilan": 1,
        "silinen": 0,
        "kaynak_hatalari": {"isigmet": "boş akış"},
        "kaynaklar": {"airsigmet": {"ham": 5, "durum": "tamam"}},
    }
    monkeypatch.setattr(api_servisi, "sigmetleri_guncelle", lambda: sahte_ozet)
    yanit = await istemci.post("/api/v1/sigmet/guncelle", headers={"X-API-Key": api_anahtari})
    assert yanit.status_code == 200
    assert yanit.json() == sahte_ozet


async def test_aktif_sigmetler_listelenir_ve_filtrelenir(istemci, api_anahtari):
    from test_sigmet_saglayici import ULUSLARARASI_ORNEK

    from turbulans_radar.veri import sigmet_saglayici

    sigmet_saglayici.sigmetleri_guncelle(getirici=lambda k: [ULUSLARARASI_ORNEK], kaynaklar=("test",))
    try:
        yanit = await istemci.get(
            "/api/v1/sigmet?enlem_min=38&enlem_maks=40&boylam_min=30&boylam_maks=32",
            headers={"X-API-Key": api_anahtari},
        )
        assert yanit.status_code == 200
        assert any(s["fir_kodu"] == "LTAA" and s["tehlike"] == "TURB" for s in yanit.json())

        yanit = await istemci.get("/api/v1/sigmet?tehlike=ICE", headers={"X-API-Key": api_anahtari})
        assert not any(s["fir_kodu"] == "LTAA" and s["tehlike"] == "TURB" for s in yanit.json())
    finally:
        with vt.motor_al().begin() as baglanti:
            baglanti.execute(text("DELETE FROM sigmetler WHERE kaynak = 'test'"))
            baglanti.execute(text("DELETE FROM veri_kaynagi_durumlari WHERE kaynak = 'sigmet:test'"))


async def test_rota_simulasyonu_sigmet_kontrolu_alanini_icerir(istemci, api_anahtari):
    yanit = await istemci.post(
        "/api/v1/simulasyon/rota",
        json={
            "baslangic_enlem": 41.0,
            "baslangic_boylam": 28.9,
            "bitis_enlem": 40.7,
            "bitis_boylam": -74.0,
            "irtifa_ft": 34000,
            "zaman": "2019-01-15T10:00:00",
            "ucak_modeli": "A320",
        },
        headers={"X-API-Key": api_anahtari},
    )
    assert yanit.status_code == 200
    govde = yanit.json()
    assert govde["guvenli_rota_bulundu_mu"] is True
    assert govde["sigmet_kontrolu"]["durum"] in ("aktif_sigmet_yok", "uygulandi")
    assert "sigmet_ihlali_sayisi" in govde["normal_rota"]


# --- Veri sağlayıcı uç noktaları ---


@pytest.mark.parametrize(
    "govde",
    [
        {"enlem_min": 40, "enlem_maks": 38, "boylam_min": 30, "boylam_maks": 36},
        {"enlem_min": 0, "enlem_maks": 60, "boylam_min": 0, "boylam_maks": 10},
        {"enlem_min": 30, "enlem_maks": 40, "boylam_min": -60, "boylam_maks": 20},
    ],
    ids=["ters_kutu", "enlem_cok_genis", "boylam_cok_genis"],
)
async def test_canli_veri_hazirla_gecersiz_kutu_400(istemci, api_anahtari, govde):
    yanit = await istemci.post("/api/v1/veri/canli/hazirla", json=govde, headers={"X-API-Key": api_anahtari})
    assert yanit.status_code == 400


async def test_canli_veri_hazirla_gorev_olarak_kup_ozetini_uretir(istemci, api_anahtari, monkeypatch, calisan_isci):
    if api_servisi.veri_kupune_eris() is None:
        pytest.skip(f"'{config.HAVA_DURUMU_DOSYASI}' bulunamadı.")
    sahte_kup = api_servisi.veri_kupune_eris().isel(valid_time=slice(0, 3)).copy()
    sahte_kup.attrs = {"kaynak": "gfs", "model_calisma_zamani": "2026-09-26T06:00:00"}
    monkeypatch.setattr(gorev_iscisi, "canli_kup_hazirla", lambda kutu, bas, bit: sahte_kup)
    yanit = await istemci.post(
        "/api/v1/veri/canli/hazirla",
        json={"enlem_min": 37, "enlem_maks": 40, "boylam_min": 30, "boylam_maks": 36, "saat_sayisi": 6},
        headers={"X-API-Key": api_anahtari},
    )
    assert yanit.status_code == 202
    durum = await _gorev_bitene_kadar_bekle(istemci, api_anahtari, yanit.json()["gorev_id"])
    assert durum["durum"] == "tamamlandi" and durum["tur"] == "canli_veri"
    (ozet,) = durum["ozet"]
    assert ozet["kaynak"] == "gfs"
    assert ozet["basinc_seviyeleri_hpa"] == [200.0, 250.0, 300.0]


async def test_kup_katalogu_listelenir(istemci, api_anahtari):
    yanit = await istemci.get("/api/v1/veri/kupler?limit=5", headers={"X-API-Key": api_anahtari})
    assert yanit.status_code == 200
    assert isinstance(yanit.json(), list)


# --- Backtest uç noktaları ---


async def test_backtest_olmayan_ucus_400(istemci, api_anahtari):
    yanit = await istemci.post("/api/v1/backtest/ucuslar/YOKUCUS1/1999-01-01", headers={"X-API-Key": api_anahtari})
    assert yanit.status_code == 400


async def test_backtest_listesi_ozet_ve_sonuc_doner(istemci, api_anahtari):
    yanit = await istemci.get("/api/v1/backtest", headers={"X-API-Key": api_anahtari})
    assert yanit.status_code == 200
    govde = yanit.json()
    assert govde["ozet"]["ucus_sayisi"] == len(govde["sonuclar"])


async def test_toplu_backtest_gorev_olarak_calisir(istemci, api_anahtari, monkeypatch, calisan_isci):
    sahte = [{"ucus_numarasi": "X1", "tarih": "2019-01-01", "durum": "atlandi", "aciklama": "küp yok"}]
    monkeypatch.setattr(gorev_iscisi, "toplu_backtest", lambda limit: sahte)
    yanit = await istemci.post("/api/v1/backtest/toplu?limit=5", headers={"X-API-Key": api_anahtari})
    assert yanit.status_code == 202
    durum = await _gorev_bitene_kadar_bekle(istemci, api_anahtari, yanit.json()["gorev_id"])
    assert durum["durum"] == "tamamlandi"
    assert durum["ozet"] == sahte


async def test_turbulans_tahmini_yerel_kup_yokken_canli_veriyi_kullanir(istemci, api_anahtari, monkeypatch):
    kup = api_servisi.veri_kupune_eris()
    if kup is None:
        pytest.skip(f"'{config.HAVA_DURUMU_DOSYASI}' bulunamadı.")
    monkeypatch.setattr(api_servisi, "hava_durumu_dosyalari", lambda: [])
    monkeypatch.setattr(api_servisi, "veri_kupune_eris", lambda *a, **k: kup)
    yanit = await istemci.post(
        "/api/v1/turbulans/tahmin",
        json={"enlem": 39.0, "boylam": 35.0, "irtifa_ft": 34000, "zaman": "2019-01-15T10:00:00"},
        headers={"X-API-Key": api_anahtari},
    )
    assert yanit.status_code == 200
    assert yanit.json()["kapsam_icinde_mi"] is True


async def test_canli_veri_bozuk_yanitta_gorev_hata_olur_ic_ayrinti_sizmaz(
    istemci, api_anahtari, monkeypatch, calisan_isci
):
    def bozuk(*args, **kwargs):
        raise ValueError(r"C:\gizli\canli_veri\gfs_x.nc açılamadı")

    monkeypatch.setattr(gorev_iscisi, "canli_kup_hazirla", bozuk)
    yanit = await istemci.post(
        "/api/v1/veri/canli/hazirla",
        json={"enlem_min": 37, "enlem_maks": 40, "boylam_min": 30, "boylam_maks": 36},
        headers={"X-API-Key": api_anahtari},
    )
    assert yanit.status_code == 202
    durum = await _gorev_bitene_kadar_bekle(istemci, api_anahtari, yanit.json()["gorev_id"])
    assert durum["durum"] == "hata"
    assert durum["aciklama"] == gorev_iscisi.CANLI_VERI_HATA_MESAJI
    assert "gizli" not in str(durum)


# --- Kısıtlı hava sahaları ---


async def test_kisitli_saha_ice_aktarma_listeleme_ve_silme(istemci, api_anahtari):
    from test_kisitli_saha_saglayici import _koleksiyon, _ozellik

    basliklar = {"X-API-Key": api_anahtari}
    try:
        yanit = await istemci.post(
            "/api/v1/kisitli-sahalar?kaynak=test_saha", json=_koleksiyon(_ozellik()), headers=basliklar
        )
        assert yanit.status_code == 200 and yanit.json() == {"kaydedilen": 1, "kaldirilan": 0}

        yanit = await istemci.get(
            "/api/v1/kisitli-sahalar?enlem_min=38&enlem_maks=40&boylam_min=30&boylam_maks=32", headers=basliklar
        )
        assert any(s["dis_kimlik"] == "test_saha:p1" and s["tur"] == "KISITLI" for s in yanit.json())

        yanit = await istemci.post(
            "/api/v1/kisitli-sahalar?kaynak=test_saha", json={"type": "Feature"}, headers=basliklar
        )
        assert yanit.status_code == 400 and "FeatureCollection" in yanit.json()["detail"]

        assert (await istemci.delete("/api/v1/kisitli-sahalar/test_saha:p1", headers=basliklar)).status_code == 204
        assert (await istemci.delete("/api/v1/kisitli-sahalar/test_saha:p1", headers=basliklar)).status_code == 404
    finally:
        with vt.motor_al().begin() as baglanti:
            baglanti.execute(text("DELETE FROM kisitli_hava_sahalari WHERE kaynak = 'test_saha'"))


# --- Sağlık / izleme ---

_KONTROLLER = {
    "sigmet",
    "canli_gfs",
    "gorev_kuyrugu",
    "kisitli_sahalar",
    "kup_onbellegi",
    "statik_dosyalar",
    "fir_sinirlari",
}


async def test_derin_saglik_tum_bagimliliklari_raporlar_ham_hata_sizdirmaz(istemci):
    yanit = await istemci.get("/saglik?derin=true")
    assert yanit.status_code == 200
    govde = yanit.json()
    assert govde["durum"] in ("ayakta", "bozulmus") and govde["veritabani"] == "erisilebilir"
    assert set(govde["kontroller"]) == _KONTROLLER
    assert all("durum" in k and "son_hata" not in k and "kaynaklar" not in k for k in govde["kontroller"].values())
    assert isinstance(govde["uyarilar"], list)


async def test_sistem_durumu_anahtar_ister_ve_ayrinti_verir(istemci, api_anahtari):
    assert (await istemci.get("/api/v1/sistem/durum")).status_code == 401
    yanit = await istemci.get("/api/v1/sistem/durum", headers={"X-API-Key": api_anahtari})
    assert yanit.status_code == 200
    assert "kaynaklar" in yanit.json()["kontroller"]["sigmet"]


async def test_biriken_gorev_kuyrugu_sagligi_bozar():
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import update

    from turbulans_radar.depo.models import AnalizGorevi

    gorev_id = await gorev_deposu.gorev_olustur("test_kuyruk")
    try:
        async with vt.async_oturum_al() as oturum:
            await oturum.execute(
                update(AnalizGorevi)
                .where(AnalizGorevi.id == gorev_id)
                .values(olusturulma_zamani=datetime.now(UTC) - timedelta(minutes=10))
            )
            await oturum.commit()
        rapor = await api_servisi._saglik_raporu(ayrintili=False)
        assert rapor["kontroller"]["gorev_kuyrugu"]["durum"] == "birikiyor"
        assert rapor["durum"] == "bozulmus"
    finally:
        with vt.motor_al().begin() as baglanti:
            baglanti.execute(text("DELETE FROM analiz_gorevleri WHERE id = :id"), {"id": gorev_id})


async def test_saglik_kontrolu_hatasi_raporu_dusurmez(monkeypatch):
    def cokuyor():
        raise ConnectionError("THREDDS kataloğu yanıt vermedi")

    monkeypatch.setattr(api_servisi, "_canli_gfs_kontrolu", cokuyor)
    rapor = await api_servisi._saglik_raporu(ayrintili=False)
    assert rapor["kontroller"]["canli_gfs"] == {"durum": "hata"}
    assert rapor["durum"] == "bozulmus"


# --- Roller: yönetici ve pilot anahtarı ---

PILOT = "pilot-anahtari-deneme"


@pytest.fixture
def pilot(monkeypatch, api_anahtari):
    monkeypatch.setenv("API_PILOT_ANAHTARI", PILOT)
    return {"X-API-Key": PILOT}


async def test_pilot_anahtari_okuyabilir_ve_rota_hesaplayabilir(istemci, pilot):
    assert (await istemci.get("/api/v1/ucuslar", headers=pilot)).status_code == 200
    assert (await istemci.get("/api/v1/kisitli-sahalar", headers=pilot)).status_code == 200
    yanit = await istemci.post(
        "/api/v1/simulasyon/rota",
        json={
            "baslangic_enlem": 5.0,
            "baslangic_boylam": 10.0,
            "bitis_enlem": 5.0,
            "bitis_boylam": 25.0,
            "irtifa_ft": 36000,
            "zaman": "2019-01-15T00:00:00",
            "ucak_modeli": "A320",
        },
        headers=pilot,
    )
    assert yanit.status_code == 200


@pytest.mark.parametrize(
    "yontem, yol",
    [
        ("delete", "/api/v1/ucuslar/YOKUCUS1/1999-01-01"),
        ("delete", "/api/v1/ucuslar?ucus_numarasi_arama=YOK"),
        ("post", "/api/v1/kisitli-sahalar?kaynak=test_saha"),
        ("delete", "/api/v1/kisitli-sahalar/ornek:ornek-irak"),
        ("post", "/api/v1/turbulans/model-versiyonlari/x/aktiflestir"),
        ("post", "/api/v1/sigmet/guncelle"),
        ("post", "/api/v1/backtest/toplu"),
        ("get", "/api/v1/sistem/durum"),
    ],
)
async def test_pilot_anahtari_yonetici_islemlerinde_403(istemci, pilot, yontem, yol):
    yanit = await istemci.request(yontem.upper(), yol, headers=pilot, json={} if yontem == "post" else None)
    assert yanit.status_code == 403


async def test_pilot_anahtari_gorev_tetikleyemez(istemci, pilot):
    yanit = await istemci.post(
        "/api/v1/analiz/ucus", json={"ucus_numarasi": "TESTX", "tarih": "2019-01-01"}, headers=pilot
    )
    assert yanit.status_code == 403


def test_ws_bileti_ile_baglanilir_bozuk_ya_da_suresi_gecmis_bilet_reddedilir(api_anahtari, monkeypatch):
    monkeypatch.setenv("API_PILOT_ANAHTARI", PILOT)
    istemci = TestClient(api_servisi.app)
    bilet = istemci.post("/api/v1/ws-bileti", headers={"X-API-Key": PILOT}).json()["bilet"]
    with istemci.websocket_connect(f"/ws/uyarilar?bilet={bilet}"):
        pass
    gecmis = api_servisi.ws_bileti_uret("pilot", simdi=0)
    oynanmis = bilet.replace("pilot", "yonetici")
    for gecersiz in (gecmis, oynanmis, "1.2.3"):
        with pytest.raises(Exception):
            with istemci.websocket_connect(f"/ws/uyarilar?bilet={gecersiz}"):
                pass


async def test_hiz_siniri_sayaci_veritabaninda_paylasilir():
    """Sayaç süreç belleğinde değil PostgreSQL'de: başka bir API süreci aynı
    anahtarı artırsa da (burada doğrudan istegi_say ile) sınır ortak işler."""
    from turbulans_radar.depo.hiz_siniri import istegi_say

    assert [await istegi_say("paylasim_testi", 60) for _ in range(3)] == [1, 2, 3]
    with pytest.raises(api_servisi.HTTPException) as hata:
        await api_servisi._hiz_sinirini_kontrol_et("paylasim_testi", maks=3)
    assert hata.value.status_code == 429 and hata.value.headers["Retry-After"] == "60"


async def test_pilot_rota_hesabi_istemci_basina_sinirlanir(istemci, api_anahtari, monkeypatch):
    monkeypatch.setattr(config, "ROTA_HESABI_DAKIKADA_MAKS", 0)
    govde = {
        "baslangic_enlem": 41.0,
        "baslangic_boylam": 28.9,
        "bitis_enlem": 39.9,
        "bitis_boylam": 32.8,
        "irtifa_ft": 34000,
        "zaman": "2019-01-15T10:00:00",
        "ucak_modeli": "A320",
    }
    yanit = await istemci.post("/api/v1/simulasyon/rota", json=govde, headers={"X-API-Key": api_anahtari})
    assert yanit.status_code == 429 and "Retry-After" in yanit.headers


async def test_hiz_siniri_sayacina_ulasilamazsa_istek_engellenmez(monkeypatch):
    from sqlalchemy.exc import OperationalError

    async def ulasilamaz(*_):
        raise OperationalError("SELECT", {}, Exception("baglanti yok"))

    monkeypatch.setattr(api_servisi, "istegi_say", ulasilamaz)
    await api_servisi._hiz_sinirini_kontrol_et("herhangi", maks=0)


async def test_agir_hesap_tavani_doluysa_503(monkeypatch):
    monkeypatch.setattr(config, "AGIR_HESAP_MAKS_ESZAMANLI", 1)
    monkeypatch.setattr(config, "AGIR_HESAP_BEKLEME_SANIYE", 0.05)
    monkeypatch.setattr(api_servisi, "_agir_hesap_semaforlari", api_servisi.weakref.WeakKeyDictionary())
    async with api_servisi._agir_hesap_yuvasi():
        with pytest.raises(api_servisi.HTTPException) as hata:
            async with api_servisi._agir_hesap_yuvasi():
                pass
    assert hata.value.status_code == 503 and hata.value.headers["Retry-After"] == "5"
    async with api_servisi._agir_hesap_yuvasi():
        pass


async def test_derin_saglik_onbellekten_doner_ve_suresi_dolunca_yenilenir(istemci, monkeypatch):
    cagri = {"sayi": 0}

    async def sayan_rapor(ayrintili):
        cagri["sayi"] += 1
        return {"durum": "ayakta", "veritabani": "erisilebilir", "kontroller": {}, "uyarilar": []}

    monkeypatch.setattr(api_servisi, "_saglik_raporu", sayan_rapor)
    monkeypatch.setattr(config, "SAGLIK_ONBELLEK_SANIYE", 60.0)
    yanitlar = await asyncio.gather(*(istemci.get("/saglik?derin=true") for _ in range(5)))
    assert all(y.status_code == 200 for y in yanitlar) and cagri["sayi"] == 1

    api_servisi._saglik_onbellegi["zaman"] -= 61
    await istemci.get("/saglik?derin=true")
    assert cagri["sayi"] == 2

    monkeypatch.setattr(config, "SAGLIK_ONBELLEK_SANIYE", 0.0)
    api_servisi._saglik_onbellegi.update(zaman=None, sonuc=None)
    await istemci.get("/saglik?derin=true")
    await istemci.get("/saglik?derin=true")
    assert cagri["sayi"] == 4


# --- Kişi başına anahtarlar ve denetim kaydı ---


async def _denetim_kayitlari(yol_parcasi):
    with vt.motor_al().connect() as baglanti:
        return baglanti.execute(
            text("SELECT kimlik, rol, yontem, yol, durum_kodu FROM denetim_kayitlari WHERE yol LIKE :y ORDER BY id"),
            {"y": f"%{yol_parcasi}%"},
        ).all()


async def test_kisiye_ozel_anahtar_rolunu_alir_ve_denetime_kimligiyle_yazilir(istemci, api_anahtari, monkeypatch):
    monkeypatch.setenv(
        "API_ANAHTARLARI", "ops-deneme:yonetici:kisisel-yonetici-anahtari, efb-deneme:pilot:kisisel-pilot"
    )
    yanit = await istemci.delete(
        "/api/v1/kisitli-sahalar/denetim-testi-yok", headers={"X-API-Key": "kisisel-yonetici-anahtari"}
    )
    assert yanit.status_code == 404
    yanit = await istemci.delete("/api/v1/kisitli-sahalar/denetim-testi-yok", headers={"X-API-Key": "kisisel-pilot"})
    assert yanit.status_code == 403
    yanit = await istemci.delete("/api/v1/kisitli-sahalar/denetim-testi-yok", headers={"X-API-Key": "yanlis"})
    assert yanit.status_code == 401

    kayitlar = await _denetim_kayitlari("denetim-testi-yok")
    assert [(k.kimlik, k.rol, k.yontem, k.durum_kodu) for k in kayitlar[-3:]] == [
        ("ops-deneme", "yonetici", "DELETE", 404),
        ("efb-deneme", "pilot", "DELETE", 403),
        ("kimliksiz", None, "DELETE", 401),
    ]
    liste = await istemci.get("/api/v1/denetim?kimlik=efb-deneme", headers={"X-API-Key": api_anahtari})
    assert liste.status_code == 200 and liste.json()[0]["durum_kodu"] == 403
    assert (await istemci.get("/api/v1/denetim", headers={"X-API-Key": "kisisel-pilot"})).status_code == 403


def test_bicimi_bozuk_anahtar_girdisi_atlanir(monkeypatch):
    monkeypatch.setenv("API_ANAHTARLARI", "eksik:yonetici,:pilot:x,a:superuser:y,gecerli:pilot:z:iki-nokta")
    assert [a for a in api_servisi._tanimli_anahtarlar() if a[0] not in ("yonetici", "pilot")] == [
        ("gecerli", "pilot", "z:iki-nokta")
    ]


async def test_denetimde_webhook_url_maskelenir(istemci, api_anahtari):
    await istemci.post(
        "/api/v1/backtest/toplu?limit=1&bildirim_webhook_url=https://n8n.ornek.com/webhook/gizli-belirtec",
        headers={"X-API-Key": api_anahtari},
    )
    (kayit,) = (await _denetim_kayitlari("/api/v1/backtest/toplu"))[-1:]
    assert "gizli-belirtec" not in kayit.yol and "bildirim_webhook_url=%2A%2A%2A" in kayit.yol


# --- WebSocket yayını: istemci başına kuyruk ---


class _SahteWebSocket:
    def __init__(self, gecikme=0.0):
        self.gecikme, self.alinan, self.kapanis_kodu = gecikme, [], None

    async def accept(self):
        pass

    async def send_json(self, mesaj):
        await asyncio.sleep(self.gecikme)
        self.alinan.append(mesaj)

    async def close(self, code=1000):
        self.kapanis_kodu = code


async def test_yavas_istemci_digerlerinin_uyarisini_geciktirmez_ve_dusurulur(monkeypatch):
    monkeypatch.setattr(config, "WS_GONDERIM_ZAMAN_ASIMI_SANIYE", 0.2)
    yonetici = api_servisi._BaglantiYoneticisi()
    hizli, donmus = _SahteWebSocket(), _SahteWebSocket(gecikme=3600)
    await yonetici.baglan(hizli)
    await yonetici.baglan(donmus)

    baslangic = asyncio.get_running_loop().time()
    await yonetici.yayinla({"n": 1})
    assert asyncio.get_running_loop().time() - baslangic < 0.05
    for _ in range(50):
        if hizli.alinan and donmus.kapanis_kodu:
            break
        await asyncio.sleep(0.02)
    assert hizli.alinan == [{"n": 1}]
    assert donmus.kapanis_kodu == 1013 and yonetici.baglantilar == [hizli]
    yonetici.ayril(hizli)


async def test_kuyrugu_dolan_istemci_dusurulur(monkeypatch):
    monkeypatch.setattr(config, "WS_ISTEMCI_KUYRUK_BOYUTU", 2)
    monkeypatch.setattr(config, "WS_GONDERIM_ZAMAN_ASIMI_SANIYE", 3600)
    yonetici = api_servisi._BaglantiYoneticisi()
    yavas = _SahteWebSocket(gecikme=3600)
    await yonetici.baglan(yavas)
    for i in range(4):
        await yonetici.yayinla({"n": i})
    for _ in range(50):
        if yavas.kapanis_kodu:
            break
        await asyncio.sleep(0.02)
    assert yavas.kapanis_kodu == 1013 and yonetici.baglantilar == []


# --- openAIP otomatik yenileme ---


def _openaip_durumunu_sil():
    with vt.motor_al().begin() as baglanti:
        baglanti.execute(text("DELETE FROM veri_kaynagi_durumlari WHERE kaynak = 'kisitli:openaip'"))


async def test_openaip_zamanlayicisi_tek_gorev_kuyruga_alir(monkeypatch):
    with vt.motor_al().connect() as baglanti:
        if baglanti.execute(
            text("SELECT 1 FROM analiz_gorevleri WHERE tur = 'openaip' AND durum IN ('kuyrukta', 'calisiyor')")
        ).first():
            pytest.skip("Geliştirme veritabanında bekleyen gerçek bir openAIP görevi var.")
    monkeypatch.setattr(api_servisi, "_openaip_yenilemesi_gerekli_mi", lambda aralik: True)
    gorev_id = await api_servisi._openaip_zamanlayici_adimi(3600)
    assert gorev_id is not None
    assert await api_servisi._openaip_zamanlayici_adimi(3600) is None  # ikinci kopya çoğaltmaz


def test_openaip_yenileme_zamani_son_denemeye_gore(monkeypatch):
    from turbulans_radar.depo.kaynak_durumu import kaynak_durumunu_kaydet

    _openaip_durumunu_sil()
    try:
        assert api_servisi._openaip_yenilemesi_gerekli_mi(3600) is True
        kaynak_durumunu_kaydet("kisitli:openaip", False, "deneme hatası")
        assert api_servisi._openaip_yenilemesi_gerekli_mi(3600) is False  # hata da bir deneme sayılır
        assert api_servisi._openaip_yenilemesi_gerekli_mi(0) is True
    finally:
        _openaip_durumunu_sil()


def test_otomatik_yenileme_acikken_basari_yoksa_kisitli_saha_bayat(monkeypatch):
    _openaip_durumunu_sil()
    monkeypatch.setattr(config, "OPENAIP_OTOMATIK_GUNCELLEME_SAAT", 24.0)
    kontrol = api_servisi._kisitli_saha_kontrolu()
    assert kontrol["durum"] == "bayat" and kontrol["openaip_son_basari"] is None
    monkeypatch.setattr(config, "OPENAIP_OTOMATIK_GUNCELLEME_SAAT", 0.0)
    assert "openaip_son_basari" not in api_servisi._kisitli_saha_kontrolu()


# --- Prometheus metrikleri ---


async def test_metrics_yonetici_ister_route_sablonuyla_etiketler(istemci, api_anahtari, monkeypatch):
    monkeypatch.setenv("API_PILOT_ANAHTARI", "metrik-pilot")
    assert (await istemci.get("/metrics")).status_code == 401
    assert (await istemci.get("/metrics", headers={"X-API-Key": "metrik-pilot"})).status_code == 403

    await istemci.get("/api/v1/ucuslar/METRIK1/1999-01-01", headers={"X-API-Key": api_anahtari})
    yanit = await istemci.get("/metrics", headers={"Authorization": f"Bearer {api_anahtari}"})
    assert yanit.status_code == 200 and yanit.headers["content-type"].startswith("text/plain")
    metin = yanit.text
    assert 'yol="/api/v1/ucuslar/{ucus_numarasi}/{tarih}"' in metin and "METRIK1" not in metin
    for ad in (
        "turbulans_http_istekleri_total",
        "turbulans_http_istek_suresi_saniye_bucket",
        "turbulans_gorev_kuyrugu",
        "turbulans_sigmet_yas_saniye",
        "turbulans_ws_baglanti_sayisi",
    ):
        assert ad in metin


def test_json_log_bicimi_satir_basina_ayrisabilir_nesne(monkeypatch):
    import json
    import logging

    from turbulans_radar import loglama

    monkeypatch.setenv("LOG_BICIMI", "json")
    bicimleyici = loglama._bicimleyici()
    try:
        raise ValueError("örnek hata")
    except ValueError:
        kayit = logging.LogRecord("turbulans.deneme", logging.ERROR, __file__, 1, "Görev %s bitti", ("g1",), None)
        kayit.exc_info = __import__("sys").exc_info()
    nesne = json.loads(bicimleyici.format(kayit))
    assert (nesne["seviye"], nesne["kaynak"], nesne["mesaj"]) == ("ERROR", "turbulans.deneme", "Görev g1 bitti")
    assert "ValueError: örnek hata" in nesne["hata"] and nesne["zaman"].endswith("+00:00")
    monkeypatch.setenv("LOG_BICIMI", "metin")
    assert not isinstance(loglama._bicimleyici(), loglama.JsonBicimleyici)
