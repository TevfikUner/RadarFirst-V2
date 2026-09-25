"""
kalibrasyon.py
----------------
turbulans_indeksleri.ti1_den_edr_proxy_olcegine_cevir() içindeki
`olceklendirme_katsayisi` (varsayılan 1.5) TAMAMEN KEYFİ bir başlangıç
değeridir -- README'de de böyle belgelenmiştir. Bu script, gerçek PIREP
(Pilot Report) veya AMDAR gözlemleriyle eşleştirilmiş TI1 değerlerinden bu
katsayıyı EN KÜÇÜK KARELER ile kalibre etmek için bir araçtır.

Bu script kendisi veri üretmez, sadece verilen gözlem CSV'sine göre en iyi
katsayıyı bulan bir ARAÇTIR -- gözlem CSV'sini `pirep_kalibrasyon_verisi_
uret.py` üretir (turbulans_ml_modeli.py'nin ML eğitimi için indirdiği AYNI
gerçek IEM PIREP + ERA5 verisini kullanarak). Bu depodaki örnek Türkiye/
Ocak-2019 veri kümesi için gerçek PIREP/AMDAR yok (bkz. README) -- bu
yüzden mevcut kalibrasyon ABD hava sahası verisine, bölgeden bağımsız bir
fiziksel ilişkiye dayanıyor.

Beklenen girdi CSV formatı (en az şu iki sütun):
    ti1_indeksi   -- main.py'nin PostgreSQL'e yazdığı edr_olcumleri
                      tablosundan (bkz. veri_kontrol.py, veritabani.py)
    pirep_edr     -- aynı nokta/zaman için gözlemlenen türbülans şiddeti,
                      0 (sakin) ile 1 (şiddetli) arasında normalize edilmiş

Kullanım:
    python kalibrasyon.py gozlem_verisi.csv
    python kalibrasyon.py gozlem_verisi.csv --arama-araligi 0.1 10
"""

import argparse

from konsol_kurulumu import konsolu_utf8_yap

konsolu_utf8_yap()

import numpy as np
import pandas as pd


def _kayip_hesapla(katsayi, ti1_degerleri, pirep_edr_degerleri):
    """Tahmin edilen EDR proxy ile gözlemlenen PIREP EDR'si arasındaki
    ortalama karesel hata (MSE)."""
    tahmin = np.tanh(ti1_degerleri * katsayi * 1e6)
    return float(np.mean((tahmin - pirep_edr_degerleri) ** 2))


def katsayi_kalibre_et(ti1_degerleri, pirep_edr_degerleri, arama_araligi=(0.01, 20.0), adim_sayisi=2000):
    """
    ti1_den_edr_proxy_olcegine_cevir()'deki olceklendirme_katsayisi'nı, verilen
    (ti1, gözlemlenen_edr) çiftlerine en iyi uyan (en küçük ortalama karesel
    hatalı) değere kalibre eder. tanh doğrusal olmadığı için kapalı-form bir
    çözüm yok; tek parametreli olduğundan basit bir grid-search yeterli
    (scipy gibi ek bir bağımlılık gerektirmez).

    Dönüş: (en_iyi_katsayi, en_iyi_katsayidaki_ortalama_karesel_hata)
    """
    ti1_degerleri = np.asarray(ti1_degerleri, dtype=float)
    pirep_edr_degerleri = np.asarray(pirep_edr_degerleri, dtype=float)

    if len(ti1_degerleri) == 0:
        raise ValueError("Kalibrasyon için en az bir (ti1, gözlemlenen_edr) çifti gerekli.")
    if len(ti1_degerleri) != len(pirep_edr_degerleri):
        raise ValueError("ti1_degerleri ve pirep_edr_degerleri aynı uzunlukta olmalı.")

    adaylar = np.linspace(arama_araligi[0], arama_araligi[1], adim_sayisi)
    kayiplar = np.array([_kayip_hesapla(k, ti1_degerleri, pirep_edr_degerleri) for k in adaylar])
    en_iyi_indeks = int(np.argmin(kayiplar))
    return float(adaylar[en_iyi_indeks]), float(kayiplar[en_iyi_indeks])


def katsayi_guven_araligi_hesapla(
    ti1_degerleri,
    pirep_edr_degerleri,
    tekrar_sayisi=1000,
    guven_seviyesi=0.95,
    arama_araligi=(0.01, 20.0),
    adim_sayisi=2000,
    rastgele_uretec=None,
):
    """
    katsayi_kalibre_et TEK bir nokta tahmini döner ama bu tahminin ne kadar
    GÜVENİLİR olduğunu (örneklem küçükse -- burada 179 gözlem -- farklı bir
    örneklemde ne kadar farklı çıkabileceğini) göstermez. Bootstrap
    resampling -- aynı büyüklükte, YERİNE KOYARAK rastgele bir örneklem
    tekrar tekrar çekilip her birinde katsayı yeniden hesaplanır -- bu
    belirsizliği doğrudan veriden tahmin eder, normal dağılım gibi bir
    varsayım gerektirmez.

    Dönüş: (alt_sinir, ust_sinir, tum_katsayilar) -- guven_seviyesi'ne
    karşılık gelen persentil aralığı ve TÜM bootstrap katsayıları (ileri
    analiz/histogram için).
    """
    rng = rastgele_uretec or np.random.default_rng()
    ti1_degerleri = np.asarray(ti1_degerleri, dtype=float)
    pirep_edr_degerleri = np.asarray(pirep_edr_degerleri, dtype=float)
    n = len(ti1_degerleri)
    if n == 0:
        raise ValueError("Güven aralığı için en az bir (ti1, gözlemlenen_edr) çifti gerekli.")

    tum_katsayilar = np.empty(tekrar_sayisi)
    for i in range(tekrar_sayisi):
        indeksler = rng.integers(0, n, n)
        katsayi, _ = katsayi_kalibre_et(
            ti1_degerleri[indeksler],
            pirep_edr_degerleri[indeksler],
            arama_araligi=arama_araligi,
            adim_sayisi=adim_sayisi,
        )
        tum_katsayilar[i] = katsayi

    alt_yuzde = (1 - guven_seviyesi) / 2 * 100
    ust_yuzde = 100 - alt_yuzde
    alt_sinir, ust_sinir = np.percentile(tum_katsayilar, [alt_yuzde, ust_yuzde])
    return float(alt_sinir), float(ust_sinir), tum_katsayilar


def _argumanlari_ayristir(argv=None):
    ayristirici = argparse.ArgumentParser(
        description="Gerçek PIREP/AMDAR gözlemleriyle TI1->EDR proxy ölçeklendirme katsayısını kalibre eder. "
        "Bu depoda gerçek gözlem verisi YOKTUR -- kendi eşleştirdiğin CSV'yi vermen gerekir.",
    )
    ayristirici.add_argument(
        "gozlem_csv",
        help="En az 'ti1_indeksi' ve 'pirep_edr' (0-1 arası) sütunlarını içeren CSV dosyası",
    )
    ayristirici.add_argument(
        "--arama-araligi",
        type=float,
        nargs=2,
        default=(0.01, 20.0),
        metavar=("MIN", "MAKS"),
        help="Katsayı için taranacak aralık (varsayılan: 0.01 20.0)",
    )
    ayristirici.add_argument(
        "--guven-araligi-atla",
        action="store_true",
        help="Bootstrap güven aralığı hesabını atla (varsayılan: 1000 tekrarla hesaplanır, ~179 gözlemde birkaç saniye sürer)",
    )
    ayristirici.add_argument(
        "--tekrar-sayisi",
        type=int,
        default=1000,
        help="Bootstrap tekrar sayısı (varsayılan: 1000 -- daha yüksek değer daha kararlı ama daha yavaş bir aralık verir)",
    )
    return ayristirici.parse_args(argv)


if __name__ == "__main__":
    argumanlar = _argumanlari_ayristir()
    df = pd.read_csv(argumanlar.gozlem_csv)

    for sutun in ("ti1_indeksi", "pirep_edr"):
        if sutun not in df.columns:
            raise SystemExit(
                f"[Hata] '{argumanlar.gozlem_csv}' dosyasında '{sutun}' sütunu yok. "
                f"Beklenen sütunlar: ti1_indeksi, pirep_edr."
            )

    df = df.dropna(subset=["ti1_indeksi", "pirep_edr"])
    if df.empty:
        raise SystemExit("[Hata] Geçerli (NaN olmayan) satır kalmadı.")

    katsayi, hata = katsayi_kalibre_et(
        df["ti1_indeksi"].to_numpy(),
        df["pirep_edr"].to_numpy(),
        arama_araligi=tuple(argumanlar.arama_araligi),
    )

    print(f"{len(df)} gözlem kullanıldı.")
    print(f"Kalibre edilmiş olceklendirme_katsayisi: {katsayi:.4f}  (ortalama karesel hata: {hata:.4f})")

    if not argumanlar.guven_araligi_atla:
        print(f"\n%95 güven aralığı hesaplanıyor ({argumanlar.tekrar_sayisi} bootstrap tekrarı)...")
        alt_sinir, ust_sinir, _ = katsayi_guven_araligi_hesapla(
            df["ti1_indeksi"].to_numpy(),
            df["pirep_edr"].to_numpy(),
            tekrar_sayisi=argumanlar.tekrar_sayisi,
            arama_araligi=tuple(argumanlar.arama_araligi),
        )
        print(
            f"%95 güven aralığı: [{alt_sinir:.4f}, {ust_sinir:.4f}]  "
            f"(genişlik: {ust_sinir - alt_sinir:.4f} -- ne kadar dar, katsayı o kadar güvenilir)"
        )

    print(
        "\nBu değeri config.py içindeki EDR_OLCEKLENDIRME_KATSAYISI'ye yaz ve "
        "EDR_OLCEKLENDIRME_KATSAYISI_KALIBRE_EDILDI'yi True yap -- böylece "
        "main.py artık 'kalibre edilmedi' uyarısı vermez."
    )
