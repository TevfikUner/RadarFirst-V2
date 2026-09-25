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


def _bos_port_bul():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def canli_sunucu():
    pytest.importorskip("playwright.sync_api")
    if not os.environ.get("API_ANAHTARI"):
        pytest.skip("API_ANAHTARI tanımlı değil, .env dosyasını kontrol et.")

    import veritabani as vt

    try:
        with vt.motor_al().connect():
            pass
    except Exception as hata:
        pytest.skip(f"PostgreSQL'e bağlanılamadı, tarayıcı testleri atlanıyor: {hata}")

    port = _bos_port_bul()
    surec = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "api_servisi:app", "--port", str(port)],
        cwd=_PROJE_KOKU,
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
        hatalar = []
        sayfa.on("pageerror", lambda err: hatalar.append(str(err)))
        yield {"sayfa": sayfa, "hatalar": hatalar}
        tarayici.close()
