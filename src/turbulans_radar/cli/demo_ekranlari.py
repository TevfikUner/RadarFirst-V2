"""
demo_ekranlari.py
--------------------
E8 demo senaryosunun (docs/sunum/DEMO_SENARYOSU.md) ekran görüntülerini
çalışan bir API'den Playwright ile üretir; senaryo adımlarını tarayıcıda
gerçekten tıklar, bu yüzden canlı demodan önce prova olarak da kullanılır.

    TURBULANS_API_ANAHTARI=demo-yerel-yonetici turbulans-demo-ekranlari \
        --taban-url http://localhost:8000 --klasor docs/sunum/ekranlar

Ön koşul: THY322 / 2019-01-15 veritabanında (turbulans-demo ya da
`docker compose --profile demo up`). --agsiz ile tarayıcı localhost dışındaki
her isteği keser ve denenen dış adresleri raporlar (ağsız prova). API anahtarı komut satırından değil
TURBULANS_API_ANAHTARI (yoksa API_ANAHTARI) ortam değişkeninden okunur.
"""

import argparse
import os
import time
from urllib.parse import urlparse

from turbulans_radar.konsol_kurulumu import konsolu_utf8_yap

konsolu_utf8_yap()

DEMO_UCUSU, DEMO_TARIHI = "THY322", "2019-01-15"

SENARYOLAR = {
    "02_simulasyon_turbulanstan_kacinma": {
        "baslangic": (41.00, 29.00),
        "bitis": (40.50, 43.50),
        "irtifa_ft": 35000,
        "zaman": "2019-01-15T20:00",
    },
    "03_simulasyon_kisitli_sahadan_kacinma": {
        "baslangic": (38.35, 38.31),
        "bitis": (36.34, 43.13),
        "irtifa_ft": 35000,
        "zaman": "2019-01-15T20:00",
    },
}


YEREL_ADRESLER = {"localhost", "127.0.0.1", "::1"}
# Yazılımsal WebGL yükte yavaşlar; sabit bekleme yerine CZML saati 5 dk ilerleyene
# (kamera rotaya oturup çizim başlayana) kadar beklenir.
SAAT_ILERLEDI = (
    "typeof viewer !== 'undefined' && viewer.dataSources.length > 0 && "
    "Cesium.JulianDate.secondsDifference(viewer.clock.currentTime, viewer.clock.startTime) > 300"
)


def _kosul_bekle(sayfa, ifade, timeout=30_000):
    """wait_for_function dize koşulunu sayfada eval eder ve CSP (script-src 'self') bunu
    engeller; page.evaluate engellenmez (tests/conftest.py ile aynı yöntem)."""
    bitis = time.monotonic() + timeout / 1000
    while not sayfa.evaluate(ifade):
        if time.monotonic() > bitis:
            raise TimeoutError(f"Koşul {timeout} ms içinde sağlanmadı: {ifade}")
        time.sleep(0.2)


def ag_engelleyici(engellenenler: list):
    """Playwright route işleyicisi: yerel olmayan istekleri keser ve kaydeder."""

    def _isle(rota):
        adres = urlparse(rota.request.url)
        if adres.scheme in ("data", "blob") or adres.hostname in YEREL_ADRESLER:
            return rota.continue_()
        engellenenler.append(adres.hostname)
        return rota.abort("internetdisconnected")

    return _isle


def _anahtar() -> str:
    anahtar = os.environ.get("TURBULANS_API_ANAHTARI") or os.environ.get("API_ANAHTARI")
    if not anahtar:
        raise SystemExit("TURBULANS_API_ANAHTARI (ya da API_ANAHTARI) tanımlı değil.")
    return anahtar


def harita3d(sayfa, taban_url, anahtar, yol):
    sayfa.goto(f"{taban_url}/harita/harita3d.html")
    sayfa.wait_for_selector("#harita")
    sayfa.fill("#giris-ucus", DEMO_UCUSU)
    sayfa.fill("#giris-tarih", DEMO_TARIHI)
    sayfa.fill("#giris-anahtar", anahtar)
    sayfa.click("#yukle-buton")
    _kosul_bekle(sayfa, "document.getElementById('durum').innerText.includes('nokta yüklendi')", timeout=60_000)
    _kosul_bekle(
        sayfa, "!document.getElementById('model-bilgisi-govde').innerText.includes('Uçuş yüklenince')", timeout=30_000
    )
    sayfa.wait_for_timeout(4000)
    sayfa.screenshot(path=yol, type="jpeg", quality=85)
    return sayfa.inner_text("#durum")


def simulasyon(sayfa, taban_url, anahtar, senaryo, yol):
    sayfa.goto(f"{taban_url}/harita/ucus_simulasyonu.html")
    sayfa.fill("#giris-anahtar", anahtar)
    sayfa.dispatch_event("#giris-anahtar", "change")
    _kosul_bekle(sayfa, "document.querySelectorAll('#ucak-modeli option[value=\"A320\"]').length > 0", timeout=30_000)
    sayfa.select_option("#ucak-modeli", "A320")
    for kimlik, deger in (
        ("#baslangic-enlem", senaryo["baslangic"][0]),
        ("#baslangic-boylam", senaryo["baslangic"][1]),
        ("#bitis-enlem", senaryo["bitis"][0]),
        ("#bitis-boylam", senaryo["bitis"][1]),
        ("#irtifa-ft", senaryo["irtifa_ft"]),
    ):
        sayfa.fill(kimlik, str(deger))
    sayfa.fill("#zaman", senaryo["zaman"])
    sayfa.click("#simule-et-buton")
    _kosul_bekle(sayfa, "document.getElementById('s-optimize-sure').innerText.trim().length > 0", timeout=120_000)
    _kosul_bekle(sayfa, SAAT_ILERLEDI, timeout=60_000)
    sayfa.wait_for_timeout(2000)
    sayfa.screenshot(path=yol, type="jpeg", quality=85)
    return sayfa.inner_text("#strateji-satiri") + " | " + sayfa.inner_text("#tasarruf-satiri")


def ana(argv=None):
    ayristirici = argparse.ArgumentParser(description="E8 demo senaryosunun ekran görüntüleri (Playwright).")
    ayristirici.add_argument("--taban-url", default="http://localhost:8000")
    ayristirici.add_argument("--klasor", default=os.path.join("docs", "sunum", "ekranlar"))
    ayristirici.add_argument("--genislik", type=int, default=1920)
    ayristirici.add_argument("--yukseklik", type=int, default=1080)
    ayristirici.add_argument("--agsiz", action="store_true", help="localhost dışındaki istekleri kes (ağsız prova)")
    argumanlar = ayristirici.parse_args(argv)
    anahtar = _anahtar()

    from playwright.sync_api import sync_playwright

    os.makedirs(argumanlar.klasor, exist_ok=True)
    with sync_playwright() as p:
        tarayici = p.chromium.launch(args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
        sayfa = tarayici.new_page(viewport={"width": argumanlar.genislik, "height": argumanlar.yukseklik})
        sayfa.set_default_navigation_timeout(120_000)
        hatalar, engellenenler = [], []
        sayfa.on("pageerror", lambda hata: hatalar.append(str(hata)))
        if argumanlar.agsiz:
            sayfa.route("**/*", ag_engelleyici(engellenenler))

        yol = os.path.join(argumanlar.klasor, "01_harita3d_THY322.jpg")
        print(f"{yol}: {harita3d(sayfa, argumanlar.taban_url, anahtar, yol)}")
        for ad, senaryo in SENARYOLAR.items():
            yol = os.path.join(argumanlar.klasor, f"{ad}.jpg")
            print(f"{yol}: {simulasyon(sayfa, argumanlar.taban_url, anahtar, senaryo, yol)}")
        tarayici.close()
    if argumanlar.agsiz:
        print("Kesilen dış istekler (adres: sayı):", {h: engellenenler.count(h) for h in sorted(set(engellenenler))})
    if hatalar:
        print("Sayfa hataları:", *hatalar, sep="\n  ")
        raise SystemExit(1)


if __name__ == "__main__":
    ana()
