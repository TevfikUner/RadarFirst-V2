"""
conftest.py
-------------
Gerçek tarayıcı (Playwright) testleri için (test_web_harita3d.py,
test_web_ucus_simulasyonu.py) paylaşılan, canlı bir API sunucusu fixture'ı.

NEDEN AYRI BİR ALT SÜREÇ (subprocess) OLARAK ÇALIŞTIRILIYOR?
api_servisi.py'nin asyncpg motoru (veritabani._async_motor) process-global
bir singleton ve İLK kullanıldığı event loop'a bağlanıyor. test_api_
servisi.py'deki testler zaten pytest'in SESSION-scope event loop'unu
paylaşıyor (bkz. pytest.ini). Sunucuyu aynı process içinde (örn. bir
thread'de kendi event loop'uyla) çalıştırmak, asyncpg motorunun İKİ FARKLI
event loop'a bağlanmaya çalışmasına ("attached to a different loop" hatası)
yol açardı. Gerçek bir alt süreç, kendi taze Python yorumlayıcısı + event
loop'uyla bu sorunu tamamen ortadan kaldırıyor -- tıpkı gerçek bir
`uvicorn` dağıtımının çalışma şekli gibi.

Görev kuyruğu (analiz_gorevleri) geliştirme veritabanında paylaşılır: kuyruğa
görev ekleyen testler gorev_kuyrugunu_temizle ile kendi bıraktıklarını siler
-- yoksa sonradan başlayan gerçek bir işçi bunları gerçek analizle
(OpenSky'a bağlanarak) çalıştırırdı. Tarayıcı testlerinin sunucusu bu yüzden
gömülü işçi olmadan başlatılır.
"""

import os
import socket
import subprocess
import sys
import time

import httpx
import pytest

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

_PROJE_KOKU = os.path.dirname(os.path.dirname(__file__))

_KATMAN_FIXTURELARI = {
    "veritabani": {
        "_db_erisilebilir_mi",
        "_gereksinimler",
        "canli_sunucu",
        "kayitli_ucus",
        "kuyruk_veritabani",
        "motor",
        "sahte_canli_ortam",
        "test_veritabani",
    },
    "gercek_veri": {
        "_gereksinimler",
        "_kupler_var_mi",
        "gercek_veri_var_mi",
        "kayitli_ucus",
        "sahte_canli_ortam",
        "veri_kupu",
        "veri_kupu_mevcut_mu",
    },
    "tarayici": {"canli_sunucu", "tarayici_sayfasi"},
}
_DIS_KATMANLAR = ("veritabani", "gercek_veri", "tarayici", "ag")


def pytest_collection_modifyitems(config, items):
    for oge in items:
        fixturelar = set(getattr(oge, "fixturenames", ()))
        for katman, adlar in _KATMAN_FIXTURELARI.items():
            if fixturelar & adlar:
                oge.add_marker(katman)
        if not any(oge.get_closest_marker(k) for k in _DIS_KATMANLAR):
            oge.add_marker("birim")


def _bos_port_bul():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def canli_sunucu():
    pytest.importorskip("playwright.sync_api")
    if not os.environ.get("API_ANAHTARI"):
        pytest.skip("API_ANAHTARI tanımlı değil, .env dosyasını kontrol et.")

    from turbulans_radar.depo import veritabani as vt

    try:
        with vt.motor_al().connect():
            pass
    except Exception as hata:
        pytest.skip(f"PostgreSQL'e bağlanılamadı, tarayıcı testleri atlanıyor: {hata}")

    port = _bos_port_bul()
    surec = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "turbulans_radar.api.api_servisi:app", "--port", str(port)],
        cwd=_PROJE_KOKU,
        env={**os.environ, "PYTHONPATH": os.path.join(_PROJE_KOKU, "src"), "GOREV_GOMULU_ISCI": "false"},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    taban_url = f"http://127.0.0.1:{port}"
    try:
        for _ in range(60):
            try:
                if httpx.get(f"{taban_url}/saglik", timeout=1).status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(0.5)
        else:
            surec.terminate()
            pytest.fail("Test sunucusu zamanında ayağa kalkmadı.")
        yield {"taban_url": taban_url, "api_anahtari": os.environ["API_ANAHTARI"]}
    finally:
        surec.terminate()
        try:
            surec.wait(timeout=10)
        except subprocess.TimeoutExpired:
            surec.kill()


@pytest.fixture(scope="module")
def tarayici_sayfasi(canli_sunucu):
    from playwright.sync_api import Error as PlaywrightHatasi
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        try:
            tarayici = p.chromium.launch()
        except PlaywrightHatasi as hata:
            # `pip install playwright` yapılmış ama `playwright install chromium`
            # unutulmuşsa -- hata yerine atla.
            pytest.skip(f"Chromium başlatılamadı (playwright install chromium?): {hata}")
        sayfa = tarayici.new_page()
        # CesiumJS (~5.8 MB) CDN'den iniyor; yavaş ağda 30 sn'lik varsayılan
        # sayfa yükleme sınırı aşılıp test, kod hatası olmadan düşüyordu.
        sayfa.set_default_navigation_timeout(120_000)
        hatalar = []
        sayfa.on("pageerror", lambda err: hatalar.append(str(err)))
        yield {"sayfa": sayfa, "hatalar": hatalar}
        tarayici.close()


@pytest.fixture
def gorev_kuyrugunu_temizle():
    """Test sırasında kuyruğa eklenip bitmemiş (kuyrukta/calisiyor) görevleri siler."""
    from sqlalchemy import text

    from turbulans_radar.depo import veritabani as vt

    try:
        with vt.motor_al().connect() as baglanti:
            baslangic = baglanti.execute(text("SELECT now()")).scalar_one()
    except Exception:
        yield
        return
    yield
    with vt.motor_al().begin() as baglanti:
        baglanti.execute(
            text(
                "DELETE FROM analiz_gorevleri WHERE olusturulma_zamani >= :baslangic "
                "AND durum IN ('kuyrukta', 'calisiyor')"
            ),
            {"baslangic": baslangic},
        )


@pytest.fixture
def calisan_isci():
    """Test süresince aynı süreçte kuyruğu işleyen bir görev işçisi."""
    from turbulans_radar.isci.gorev_iscisi import GorevIscisi

    isci = GorevIscisi(isci_sayisi=1, bekleme_saniye=0.05).baslat()
    yield isci
    isci.durdur(zaman_asimi=10.0)
