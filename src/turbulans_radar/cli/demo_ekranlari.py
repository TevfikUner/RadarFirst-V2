"""
demo_ekranlari.py
--------------------
E8 demo senaryosunun (docs/sunum/DEMO_SENARYOSU.md) ekran görüntülerini
çalışan bir API'den Playwright ile üretir; senaryo adımlarını tarayıcıda
gerçekten tıklar, bu yüzden canlı demodan önce prova olarak da kullanılır.

    TURBULANS_API_ANAHTARI=demo-yerel-yonetici turbulans-demo-ekranlari \
        --taban-url http://localhost:8000 --klasor docs/sunum/ekranlar

Ön koşul: THY322 / 2019-01-15 veritabanında (turbulans-demo ya da
`docker compose --profile demo up`). API anahtarı komut satırından değil
TURBULANS_API_ANAHTARI (yoksa API_ANAHTARI) ortam değişkeninden okunur.
"""

import argparse
import os

from turbulans_radar.konsol_kurulumu import konsolu_utf8_yap

konsolu_utf8_yap()

DEMO_UCUSU, DEMO_TARIHI = "THY322", "2019-01-15"

SENARYOLAR = {
    "02_simulasyon_turbulanstan_kacinma": {
        "baslangic": (41.00, 29.00),
        "bitis": (40.50, 43.50),
        "irtifa_ft": 36000,
        "zaman": "2019-01-15T20:00",
    },
    "03_simulasyon_kisitli_sahadan_kacinma": {
        "baslangic": (38.35, 38.31),
        "bitis": (36.34, 43.13),
        "irtifa_ft": 36000,
        "zaman": "2019-01-15T20:00",
    },
}


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
    sayfa.wait_for_function("document.getElementById('durum').innerText.includes('nokta yüklendi')", timeout=60_000)
    sayfa.wait_for_function(
        "!document.getElementById('model-bilgisi-govde').innerText.includes('Uçuş yüklenince')", timeout=30_000
    )
    sayfa.wait_for_timeout(4000)
    sayfa.screenshot(path=yol, type="jpeg", quality=85)
    return sayfa.inner_text("#durum")


def simulasyon(sayfa, taban_url, anahtar, senaryo, yol):
    sayfa.goto(f"{taban_url}/harita/ucus_simulasyonu.html")
    sayfa.fill("#giris-anahtar", anahtar)
    sayfa.dispatch_event("#giris-anahtar", "change")
    sayfa.wait_for_function(
        "document.querySelectorAll('#ucak-modeli option[value=\"A320\"]').length > 0", timeout=30_000
    )
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
    sayfa.wait_for_function("document.getElementById('s-optimize-sure').innerText.trim().length > 0", timeout=120_000)
    sayfa.wait_for_timeout(6000)
    sayfa.screenshot(path=yol, type="jpeg", quality=85)
    return sayfa.inner_text("#strateji-satiri") + " | " + sayfa.inner_text("#tasarruf-satiri")


def ana(argv=None):
    ayristirici = argparse.ArgumentParser(description="E8 demo senaryosunun ekran görüntüleri (Playwright).")
    ayristirici.add_argument("--taban-url", default="http://localhost:8000")
    ayristirici.add_argument("--klasor", default=os.path.join("docs", "sunum", "ekranlar"))
    ayristirici.add_argument("--genislik", type=int, default=1920)
    ayristirici.add_argument("--yukseklik", type=int, default=1080)
    argumanlar = ayristirici.parse_args(argv)
    anahtar = _anahtar()

    from playwright.sync_api import sync_playwright

    os.makedirs(argumanlar.klasor, exist_ok=True)
    with sync_playwright() as p:
        tarayici = p.chromium.launch(args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
        sayfa = tarayici.new_page(viewport={"width": argumanlar.genislik, "height": argumanlar.yukseklik})
        sayfa.set_default_navigation_timeout(120_000)
        hatalar = []
        sayfa.on("pageerror", lambda hata: hatalar.append(str(hata)))

        yol = os.path.join(argumanlar.klasor, "01_harita3d_THY322.jpg")
        print(f"{yol}: {harita3d(sayfa, argumanlar.taban_url, anahtar, yol)}")
        for ad, senaryo in SENARYOLAR.items():
            yol = os.path.join(argumanlar.klasor, f"{ad}.jpg")
            print(f"{yol}: {simulasyon(sayfa, argumanlar.taban_url, anahtar, senaryo, yol)}")
        tarayici.close()
    if hatalar:
        print("Sayfa hataları:", *hatalar, sep="\n  ")
        raise SystemExit(1)


if __name__ == "__main__":
    ana()
