"""
test_web_ucus_simulasyonu.py
--------------------------------
web/ucus_simulasyonu.html'in gerçek bir tarayıcıda (Playwright + headless
Chromium) uçtan uca çalıştığını doğrular -- README'nin "3D uçuş
simülasyonu" bölümünde anlatılan manuel doğrulamanın kalıcı,
tekrarlanabilir hale getirilmiş hali. Sayfanın kendi varsayılan değerleri
(İstanbul->Antalya, 2019-01-05, 28000ft) zaten ERA5 veri küpünün
kapsadığı bölge/tarih aralığında -- ekstra bir uçuş kaydına gerek yok,
doğrudan gerçek ERA5 rüzgarıyla A* rota hesabı tetiklenir.

Gerçek bir PostgreSQL bağlantısı VE Playwright/Chromium gerektirir; ikisi
de yoksa (bkz. conftest.canli_sunucu) atlanır (skip). Ayrıca gerçek ERA5
veri küpü (config.HAVA_DURUMU_DOSYASI) sunucu tarafında bulunmalı --
bulunmazsa API "kapsam dışı" dürüst geri düşüşünü döner ve bu test o
durumu da (rota yine de hesaplanır, sadece rüzgarsız) kabul eder.
"""

import pytest


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


def test_simulasyon_uctan_uca_calisir(canli_sunucu, tarayici_sayfasi):
    sayfa = tarayici_sayfasi["sayfa"]
    sayfa.goto(f"{canli_sunucu['taban_url']}/harita/ucus_simulasyonu.html")
    sayfa.wait_for_selector("#kontrol-paneli")

    sayfa.fill("#giris-anahtar", canli_sunucu["api_anahtari"])
    sayfa.locator("#giris-anahtar").press("Tab")  # 'change' olayını tetikler -> uçak profilleri yüklenir

    sayfa.wait_for_function(
        "document.getElementById('ucak-modeli').options.length > 0 "
        "&& document.getElementById('ucak-modeli').options[0].value !== ''"
    )

    sayfa.click("#simule-et-buton")
    sayfa.wait_for_selector("#s-normal-sure:not(:empty)", timeout=30000)

    assert sayfa.inner_text("#s-normal-sure").strip() != ""
    assert sayfa.inner_text("#s-optimize-sure").strip() != ""
    assert sayfa.query_selector("canvas") is not None

    # GERÇEK TARAYICI TESTİYLE (README'de belgelenen) bulunup düzeltilen
    # CesiumJS 'imageryProvider' hatasının bir daha geri gelmediğini
    # doğrular.
    imagery_hatalari = [h for h in tarayici_sayfasi["hatalar"] if "imageryProvider" in h]
    assert imagery_hatalari == []
