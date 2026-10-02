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


def test_simulasyon_uctan_uca_calisir(canli_sunucu, tarayici_sayfasi, ekran_goruntusu):
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

    sayfa.fill("#hacim-fl-min", "300")
    sayfa.locator("#hacim-fl-min").press("Tab")
    sayfa.uncheck("#secenekleri-ciz")
    assert not [h for h in tarayici_sayfasi["hatalar"] if "TypeError" in h or "ReferenceError" in h]


def test_kisitli_sahadan_kacinma_ozeti_dogru_yazilir(canli_sunucu, tarayici_sayfasi, ekran_goruntusu):
    """Malatya -> Musul: paketle gelen örnek kısıtlı saha (Suriye) sert kısıt;
    türbülans yokken de rota değişir, özet 'iki rota aynı' DEMEMELİ."""
    sayfa = tarayici_sayfasi["sayfa"]
    sayfa.goto(f"{canli_sunucu['taban_url']}/harita/ucus_simulasyonu.html")
    sayfa.wait_for_selector("#kontrol-paneli")
    sayfa.fill("#giris-anahtar", canli_sunucu["api_anahtari"])
    sayfa.locator("#giris-anahtar").press("Tab")
    sayfa.wait_for_function("document.querySelectorAll('#ucak-modeli option[value=\"A320\"]').length > 0")
    sayfa.select_option("#ucak-modeli", "A320")
    for kimlik, deger in (
        ("#baslangic-enlem", "38.35"),
        ("#baslangic-boylam", "38.31"),
        ("#bitis-enlem", "36.34"),
        ("#bitis-boylam", "43.13"),
        ("#irtifa-ft", "36000"),
    ):
        sayfa.fill(kimlik, deger)
    sayfa.click("#simule-et-buton")
    sayfa.wait_for_selector("#s-optimize-kisit:not(:empty)", timeout=60000)

    assert sayfa.inner_text("#s-optimize-kisit").strip() == "0 / 0"
    assert sayfa.inner_text("#s-normal-kisit").strip() != "0 / 0"
    ozet = sayfa.inner_text("#tasarruf-satiri")
    assert "Sert kısıttan kaçınıldı" in ozet
    assert "iki rota aynı" not in ozet
