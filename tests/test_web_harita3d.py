"""
test_web_harita3d.py
-----------------------
web/harita3d.html'in gerçek bir tarayıcıda (Playwright + headless
Chromium) uçtan uca çalıştığını doğrular -- README'de anlatılan manuel
doğrulamanın (bkz. "3D/canlı harita önyüzü" bölümü) kalıcı, tekrarlanabilir
hale getirilmiş hali. Bu testler MapLibre 4.7.1 -> 5.8.0 geçişinde bulunan
gerçek 'setProjection' hatasının bir daha sessizce geri gelmemesini sağlar.

Gerçek bir PostgreSQL bağlantısı VE Playwright/Chromium gerektirir; ikisi
de yoksa (bkz. conftest.canli_sunucu) atlanır (skip).
"""

import pandas as pd
import pytest

import veritabani as vt

_UCUS_NO = "PWHARITA"
_TARIH = "2019-01-15"


@pytest.fixture
def kayitli_ucus():
    df = pd.DataFrame(
        {
            "zaman": pd.to_datetime(["2019-01-15T10:00:00Z", "2019-01-15T10:10:00Z"]),
            "enlem": [40.0, 40.2],
            "boylam": [30.0, 30.3],
            "ti1_indeksi": [1e-7, 9e-7],
        }
    )
    vt.ucus_ve_olcumleri_kaydet(df, _UCUS_NO, _TARIH)
    yield
    from sqlalchemy import text

    with vt.motor_al().begin() as baglanti:
        baglanti.execute(text("DELETE FROM ucuslar WHERE ucus_numarasi = :un"), {"un": _UCUS_NO})


@pytest.fixture(scope="module")
def tarayici_sayfasi(canli_sunucu):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        tarayici = p.chromium.launch()
        sayfa = tarayici.new_page()
        hatalar = []
        sayfa.on("pageerror", lambda err: hatalar.append(str(err)))
        yield {"sayfa": sayfa, "hatalar": hatalar}
        tarayici.close()


def test_ucus_yuklenip_harita_render_olur(canli_sunucu, tarayici_sayfasi, kayitli_ucus):
    sayfa = tarayici_sayfasi["sayfa"]
    sayfa.goto(f"{canli_sunucu['taban_url']}/harita/harita3d.html")
    sayfa.wait_for_selector("#harita")

    sayfa.fill("#giris-ucus", _UCUS_NO)
    sayfa.fill("#giris-tarih", _TARIH)
    sayfa.fill("#giris-anahtar", canli_sunucu["api_anahtari"])
    sayfa.click("#yukle-buton")
    sayfa.wait_for_timeout(3000)

    assert "2 nokta yüklendi" in sayfa.inner_text("#durum")
    assert sayfa.query_selector("canvas.maplibregl-canvas") is not None
    assert sayfa.is_visible("#zaman-kontrolu")

    # GERÇEK TARAYICI TESTİYLE bulunan hatanın (MapLibre'de setProjection
    # hiç olmaması / "Style is not done loading") bir daha geri gelmediğini
    # doğrular -- bkz. CHANGELOG.
    hatalar = tarayici_sayfasi["hatalar"]
    setprojection_hatalari = [h for h in hatalar if "setProjection" in h or "Style is not done" in h]
    assert setprojection_hatalari == []


def test_silme_ve_arama_arayuzden_calisir(canli_sunucu, tarayici_sayfasi, kayitli_ucus):
    sayfa = tarayici_sayfasi["sayfa"]
    sayfa.goto(f"{canli_sunucu['taban_url']}/harita/harita3d.html")
    sayfa.wait_for_selector("#harita")
    sayfa.fill("#giris-anahtar", canli_sunucu["api_anahtari"])

    sayfa.fill("#ucuslar-arama", _UCUS_NO)
    sayfa.click("#ucuslar-arama-buton")
    sayfa.wait_for_timeout(1500)
    assert _UCUS_NO in sayfa.inner_text("#kayitli-ucuslar-listesi")

    sayfa.fill("#giris-ucus", _UCUS_NO)
    sayfa.fill("#giris-tarih", _TARIH)
    sayfa.once("dialog", lambda d: d.accept())
    sayfa.click("#sil-buton")
    sayfa.wait_for_timeout(1500)
    assert "silindi" in sayfa.inner_text("#durum")

    # Fixture'ın kendi teardown'ı zaten temizler ama silme burada da
    # gerçekleştiği için tekrar denemek 404 vermeli -- kayitli_ucus
    # fixture'ının DELETE'i "kayıt zaten yok" durumunda sessizce 0 satır
    # siler, hataya yol açmaz.
