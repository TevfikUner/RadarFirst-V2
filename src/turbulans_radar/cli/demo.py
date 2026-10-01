"""
demo.py
----------
Kimlik bilgisi ve ağ gerektirmeyen demo: depoyla gelen THY322 (2019-01-15,
İstanbul-Doğu Anadolu) rotasını ve ERA5 dilimini (bkz. demo/README.md)
eşleştirir, türbülans özetini yazdırır, haritayı ciktilar/'a üretir ve
PostgreSQL erişilebilirse sonucu kaydeder (3B harita ve API için).

    turbulans-demo              (ya da python -m turbulans_radar.cli.demo)
"""

import argparse
import os

from turbulans_radar.konsol_kurulumu import konsolu_utf8_yap

konsolu_utf8_yap()

from turbulans_radar import config

DEMO_UCUSU = "THY322"
DEMO_TARIHI = "2019-01-15"


def demo_dosyalari() -> dict[str, str]:
    kok = config.DEMO_VERI_KLASORU
    return {
        "rota": os.path.join(kok, "opensky_onbellek", f"{DEMO_UCUSU}_{DEMO_TARIHI}.parquet"),
        "era5": os.path.join(kok, "era5", f"era5_{DEMO_UCUSU}_{DEMO_TARIHI}.nc"),
    }


def demo_calistir(harita_uret: bool = True):
    """Demo analizini çevrimdışı çalıştırır: uçuşa özel ERA5 indirmesi ve canlı
    GFS kapatılır, rota ve hava küpü yalnızca demo paketinden okunur. Dönüş:
    eşleşmiş DataFrame (başarısızsa None)."""
    if not config.DEMO_VERI_KLASORU:
        raise SystemExit("DEMO_VERI_KLASORU boş; demo paketi devre dışı.")
    eksik = [yol for yol in demo_dosyalari().values() if not os.path.isfile(yol)]
    if eksik:
        raise SystemExit(f"Demo dosyaları bulunamadı: {', '.join(eksik)} (depo kökünden çalıştırın).")
    config.ERA5_OTOMATIK_INDIRME = False
    config.CANLI_HAVA_VERISI_ETKIN = False

    from turbulans_radar.analiz.ucus_analizi import calistir

    return calistir(DEMO_UCUSU, DEMO_TARIHI, harita_uret=harita_uret)


def ana(argv=None):
    ayristirici = argparse.ArgumentParser(
        description=f"Çevrimdışı demo: {DEMO_UCUSU} / {DEMO_TARIHI} rotasını depodaki ERA5 dilimiyle analiz eder."
    )
    ayristirici.add_argument("--harita-yok", action="store_true", help="Folium haritasını üretme")
    argumanlar = ayristirici.parse_args(argv)
    sonuc = demo_calistir(harita_uret=not argumanlar.harita_yok)
    if sonuc is None:
        raise SystemExit(1)
    print(
        "Sonraki adımlar:\n"
        f"  - Harita: {os.path.join(config.CIKTI_KLASORU, f'turbulans_haritasi_{DEMO_UCUSU}_{DEMO_TARIHI}.html')}\n"
        "  - API çalışıyorsa 3B harita: http://localhost:8000/harita/harita3d.html "
        "(X-API-Key: .env'deki API_ANAHTARI)\n"
        "  - Rota simülasyonu: http://localhost:8000/harita/ucus_simulasyonu.html\n"
        "Not: Çıktılar sertifikalı EDR değildir; sistem karar destek aracıdır."
    )


if __name__ == "__main__":
    ana()
