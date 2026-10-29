"""
test_web_ucus_simulasyonu.py
--------------------------------
web/ucus_simulasyonu.html'in gerçek bir tarayıcıda (Playwright + headless
Chromium) uçtan uca çalıştığını doğrular -- README'nin "3D uçuş
simülasyonu" bölümünde anlatılan manuel doğrulamanın kalıcı,
tekrarlanabilir hale getirilmiş hali. Sayfanın kendi varsayılan değerleri
(İstanbul->Antalya, 2019-01-05, 29000ft) zaten ERA5 veri küpünün
kapsadığı bölge/tarih aralığında -- ekstra bir uçuş kaydına gerek yok,
doğrudan gerçek ERA5 rüzgarıyla A* rota hesabı tetiklenir.

Gerçek bir PostgreSQL bağlantısı VE Playwright/Chromium gerektirir; ikisi
de yoksa (bkz. conftest.canli_sunucu) atlanır (skip). Ayrıca gerçek ERA5
veri küpü (config.HAVA_DURUMU_DOSYASI) sunucu tarafında bulunmalı --
bulunmazsa API "kapsam dışı" dürüst geri düşüşünü döner ve bu test o
durumu da (rota yine de hesaplanır, sadece rüzgarsız) kabul eder.
"""

import pytest


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


def _simule_et(canli_sunucu, sayfa, alanlar, zaman=None):
    sayfa.goto(f"{canli_sunucu['taban_url']}/harita/ucus_simulasyonu.html")
    sayfa.wait_for_selector("#kontrol-paneli")
    sayfa.fill("#giris-anahtar", canli_sunucu["api_anahtari"])
    sayfa.locator("#giris-anahtar").press("Tab")
    sayfa.wait_for_function("document.querySelectorAll('#ucak-modeli option[value=\"A320\"]').length > 0")
    sayfa.select_option("#ucak-modeli", "A320")
    for kimlik, deger in alanlar.items():
        sayfa.fill(kimlik, deger)
    if zaman:
        sayfa.fill("#zaman", zaman)
    sayfa.click("#simule-et-buton")
    sayfa.wait_for_selector("#s-normal-turbulans:not(:empty)", timeout=60000)


def test_kapsam_disinda_risk_hesaplanmadi_yazar_kabin_bildirimi_cikmaz(canli_sunucu, tarayici_sayfasi):
    sayfa = tarayici_sayfasi["sayfa"]
    _simule_et(canli_sunucu, sayfa, {"#bitis-enlem": "40.70", "#bitis-boylam": "-74.00", "#irtifa-ft": "34000"})
    assert sayfa.inner_text("#s-normal-turbulans").strip() == "hesaplanmadı"
    assert "hesaplanmadı" in sayfa.inner_text("#tasarruf-satiri")
    assert "0 nokta" not in sayfa.inner_text("#sonuc-paneli")
    assert not sayfa.is_visible("#kabin-bildirimi")
    assert "NM" in sayfa.inner_text("#s-normal-mesafe")


def test_kalan_risk_yoksa_kabin_bildirimi_cikmaz(canli_sunucu, tarayici_sayfasi):
    sayfa = tarayici_sayfasi["sayfa"]
    _simule_et(
        canli_sunucu,
        sayfa,
        {
            "#baslangic-enlem": "38.40",
            "#baslangic-boylam": "27.10",
            "#bitis-enlem": "38.50",
            "#bitis-boylam": "43.40",
            "#irtifa-ft": "35000",
        },
        "2019-01-31T00:00",
    )
    assert not sayfa.is_visible("#kabin-bildirimi")
    assert not sayfa.is_visible("#riskli-bolumler-kutusu")
    assert "Kabin: ek öneri yok." in sayfa.inner_text("#brifing-karti")


def test_kalan_riskte_bolumler_ve_kabin_onerisi_dispecer_dilinde(canli_sunucu, tarayici_sayfasi):
    sayfa = tarayici_sayfasi["sayfa"]
    _simule_et(canli_sunucu, sayfa, {"#irtifa-ft": "31000"}, "2019-01-01T06:00")
    if sayfa.inner_text("#s-optimize-turbulans").strip() in ("hesaplanmadı", "yok"):
        return
    oneri = sayfa.inner_text("#kabin-bildirimi")
    assert "Öneri (karar kaptanındır)" in oneri and "FL310" in oneri
    assert "Kabin: olası türbülans" in sayfa.inner_text("#brifing-karti")
    assert sayfa.locator("#riskli-bolumler-tablosu tr").count() > 1
    assert "FL310" in sayfa.inner_text("#s-optimize-irtifa")
    assert ":" in sayfa.inner_text("#s-optimize-sure")


def _senaryoyla_simule_et(canli_sunucu, sayfa, kimlik):
    sayfa.goto(f"{canli_sunucu['taban_url']}/harita/ucus_simulasyonu.html")
    sayfa.wait_for_selector("#kontrol-paneli")
    sayfa.fill("#giris-anahtar", canli_sunucu["api_anahtari"])
    sayfa.locator("#giris-anahtar").press("Tab")
    sayfa.wait_for_function("document.querySelectorAll('#ucak-modeli option[value=\"A320\"]').length > 0")
    sayfa.select_option("#ucak-modeli", "A320")
    sayfa.wait_for_function(f"document.querySelectorAll('#senaryo option[value=\"{kimlik}\"]').length > 0")
    sayfa.select_option("#senaryo", kimlik)
    sayfa.click("#simule-et-buton")
    sayfa.wait_for_selector("#s-normal-turbulans:not(:empty)", timeout=60000)


def test_senaryo_secici_alanlari_doldurur_ve_aciklama_gosterir(canli_sunucu, tarayici_sayfasi):
    sayfa = tarayici_sayfasi["sayfa"]
    sayfa.goto(f"{canli_sunucu['taban_url']}/harita/ucus_simulasyonu.html")
    sayfa.wait_for_function("document.querySelectorAll('#senaryo option[value=\"risk_yok\"]').length > 0")
    sayfa.select_option("#senaryo", "risk_yok")
    assert sayfa.input_value("#baslangic-boylam") == "27.10" and sayfa.input_value("#zaman") == "2019-01-31T00:00"
    assert "Risk yoksa" in sayfa.inner_text("#senaryo-aciklamasi")


def test_guvenli_rota_yok_senaryosunda_oneri_yok_yazar(canli_sunucu, tarayici_sayfasi):
    sayfa = tarayici_sayfasi["sayfa"]
    _senaryoyla_simule_et(canli_sunucu, sayfa, "guvenli_rota_yok")
    assert "öneri yok" in sayfa.inner_text("#tasarruf-satiri")


@pytest.mark.parametrize(
    ("kimlik", "beklenen"),
    [
        ("sigmet_bayat", "SIGMET güncellemesi"),
        ("sigmet_erisilemedi", "SIGMET veritabanına erişilemedi"),
        ("devre_kesici", "devre kesici açık"),
    ],
)
def test_ariza_tatbikati_senaryolari_sentetik_etiketle_hata_durumunu_yazar(
    canli_sunucu, tarayici_sayfasi, kimlik, beklenen
):
    sayfa = tarayici_sayfasi["sayfa"]
    _senaryoyla_simule_et(canli_sunucu, sayfa, kimlik)
    aciklama = sayfa.inner_text("#aciklama")
    assert "SENTETİK ARIZA TATBİKATI" in aciklama and beklenen in aciklama
