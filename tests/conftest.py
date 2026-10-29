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

# Yerel .env gece işi saatini açabilir; testlerde (canlı test sunucusu dahil)
# ML zamanlayıcısı test veritabanına görev eklemesin.
os.environ["ML_GECE_ISI_SAATI"] = ""
os.environ["CANLI_ISITMA_SAAT"] = "0"
os.environ["MADIS_GECE_ETKIN"] = "false"
os.environ["GUNLUK_VERI_BUTCESI_MB"] = "0"


def _test_veritabanina_yonlendir():
    if os.environ.get("CI") or not os.environ.get("POSTGRES_DB"):
        return None
    test_db = os.environ.get("POSTGRES_TEST_DB") or f"{os.environ['POSTGRES_DB']}-test"
    if test_db == os.environ["POSTGRES_DB"]:
        return None
    try:
        import psycopg2
        from psycopg2 import sql

        baglanti = psycopg2.connect(
            host=os.environ.get("POSTGRES_HOST"),
            port=os.environ.get("POSTGRES_PORT", "5432"),
            user=os.environ.get("POSTGRES_USER"),
            password=os.environ.get("POSTGRES_PASSWORD"),
            dbname="postgres",
            connect_timeout=5,
        )
        baglanti.autocommit = True
        with baglanti.cursor() as imlec:
            imlec.execute("SELECT 1 FROM pg_database WHERE datname = %s", (test_db,))
            if imlec.fetchone() is None:
                imlec.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(test_db)))
        baglanti.close()
    except Exception:
        pass
    os.environ["POSTGRES_DB"] = test_db
    return test_db


_TEST_VERITABANI = _test_veritabanina_yonlendir()

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
        "gercek_senaryo",
        "gercek_veri_var_mi",
        "kayitli_ucus",
        "sahte_canli_ortam",
        "veri_kupu",
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
        env={
            **os.environ,
            "PYTHONPATH": os.path.join(_PROJE_KOKU, "src"),
            "GOREV_GOMULU_ISCI": "false",
            "ARIZA_TAKLIDI_ETKIN": "true",
        },
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


def _kosul_bekle(sayfa, ifade, timeout=30_000):
    """wait_for_function'ın CSP'ye takılmayan karşılığı: Playwright dize koşulu sayfada eval
    ile değerlendirir ve CSP script-src 'self' bunu engeller; page.evaluate engellenmez."""
    bitis = time.monotonic() + timeout / 1000
    while not sayfa.evaluate(ifade):
        if time.monotonic() > bitis:
            raise TimeoutError(f"Koşul {timeout} ms içinde sağlanmadı: {ifade}")
        time.sleep(0.1)


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
        sayfa.wait_for_function = lambda ifade, timeout=30_000, **_: _kosul_bekle(sayfa, ifade, timeout)
        hatalar, csp_ihlalleri = [], []
        sayfa.on("pageerror", lambda err: hatalar.append(str(err)))
        sayfa.on(
            "console",
            lambda mesaj: "Content Security Policy" in mesaj.text and csp_ihlalleri.append(mesaj.text),
        )
        yield {"sayfa": sayfa, "hatalar": hatalar}
        tarayici.close()
        assert csp_ihlalleri == [], f"CSP ihlali: {csp_ihlalleri[:3]}"


@pytest.fixture
def ekran_goruntusu(request, tarayici_sayfasi):
    """TARAYICI_EKRAN_KLASORU tanımlıysa test sonunda tam sayfa ekran görüntüsü
    alır (CI bunları artifact olarak saklar)."""
    yield
    klasor = os.environ.get("TARAYICI_EKRAN_KLASORU")
    if klasor:
        os.makedirs(klasor, exist_ok=True)
        tarayici_sayfasi["sayfa"].screenshot(path=os.path.join(klasor, f"{request.node.name}.png"), full_page=True)


@pytest.fixture(autouse=True)
def _cds_nezaket_beklemesi_kapali(monkeypatch):
    from turbulans_radar import config

    monkeypatch.setattr(config, "CDS_ISTEKLER_ARASI_SANIYE", 0.0)


@pytest.fixture(autouse=True)
def _model_versiyonlari_gecici_klasorde(monkeypatch, tmp_path):
    from turbulans_radar.ml import turbulans_ml_modeli as tm

    klasor = tmp_path / "model_versiyonlari"
    monkeypatch.setattr(tm, "MODEL_VERSIYONLARI_KLASORU", str(klasor))
    monkeypatch.setattr(tm, "MODEL_VERSIYONLARI_MANIFEST_YOLU", str(klasor / "manifest.json"))


@pytest.fixture(autouse=True)
def _model_butunlugu_varsayilan(monkeypatch):
    """Yerel .env'deki MODEL_BUTUNLUK_ZORUNLU testlerin sonucunu değiştirmesin."""
    from turbulans_radar import config

    monkeypatch.setattr(config, "MODEL_BUTUNLUK_ZORUNLU", False)


@pytest.fixture(autouse=True)
def _altin_test_gunleri_gecici(monkeypatch, tmp_path):
    from turbulans_radar import config

    monkeypatch.setattr(config, "ML_ALTIN_TEST_DOSYASI", str(tmp_path / "altin_test_gunleri.json"))


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
