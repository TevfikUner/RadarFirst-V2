"""
toplu_analiz.py
-----------------
main.py tek bir uçuşu analiz eder; bu script ise bir LİSTE halinde verilen
birden fazla uçuşu sırayla analiz eder ve hepsinin özetini TEK bir tabloda
toplar (main.py'yi her uçuş için elle tek tek çalıştırmak yerine).

Girdi CSV formatı (en az şu iki sütun, başlık satırıyla):
    ucus_numarasi,tarih
    THY72C,2019-01-15
    N10VZ,2019-01-15

Kullanım:
    python toplu_analiz.py ucuslar.csv
    python toplu_analiz.py ucuslar.csv --cikti ozet.csv

Her uçuş kendi CSV/HTML çıktısını main.py ile aynı şekilde üretir (bu script
ekstra olarak sadece hepsinin kısa bir özetini çıkarır). Bir uçuşta hata
oluşursa (uçuş bulunamadı, bağlantı sorunu vb.) diğer uçuşların analizi
DURMAZ -- sadece o uçuş "başarısız" olarak işaretlenip bir sonrakine geçilir.
"""

import argparse
import os
import time

from konsol_kurulumu import konsolu_utf8_yap

konsolu_utf8_yap()

import pandas as pd

import config
from hata_yardimcisi import dostane_hata_mesaji
from main import calistir


def toplu_analiz_calistir(ucus_listesi_df: pd.DataFrame) -> pd.DataFrame:
    """
    ucus_listesi_df: 'ucus_numarasi' ve 'tarih' sütunlarını içeren DataFrame.
    Dönüş: her uçuş için bir özet satırı içeren DataFrame.
    """
    sonuclar = []
    toplam = len(ucus_listesi_df)

    for i, satir in ucus_listesi_df.iterrows():
        if i > 0 and config.TOPLU_ANALIZ_ISTEKLER_ARASI_BEKLEME_SANIYE > 0:
            # OpenSky'yi art arda isteklerle yormamak için uçuşlar arasında bekle.
            time.sleep(config.TOPLU_ANALIZ_ISTEKLER_ARASI_BEKLEME_SANIYE)

        ucus_no = str(satir["ucus_numarasi"]).strip()
        tarih = str(satir["tarih"]).strip()

        print(f"\n{'=' * 60}")
        print(f"[{i + 1}/{toplam}] {ucus_no} / {tarih} analiz ediliyor...")
        print("=" * 60)

        try:
            eslesmis_df = calistir(ucus_no, tarih)
        except Exception as hata:
            print(f"[Hata] {dostane_hata_mesaji(hata)}")
            sonuclar.append(
                {
                    "ucus_numarasi": ucus_no,
                    "tarih": tarih,
                    "durum": "hata",
                    "aciklama": dostane_hata_mesaji(hata),
                    "nokta_sayisi": None,
                    "eslesen_nokta_sayisi": None,
                    "ti1_ortalama": None,
                    "dinamik_kararsizlik_sayisi": None,
                }
            )
            continue

        if eslesmis_df is None:
            sonuclar.append(
                {
                    "ucus_numarasi": ucus_no,
                    "tarih": tarih,
                    "durum": "başarısız",
                    "aciklama": "Uçuş/veri eşleştirilemedi (yukarıdaki konsol mesajlarına bak).",
                    "nokta_sayisi": None,
                    "eslesen_nokta_sayisi": None,
                    "ti1_ortalama": None,
                    "dinamik_kararsizlik_sayisi": None,
                }
            )
            continue

        ti1_gecerli = eslesmis_df["ti1_indeksi"].dropna()
        dinamik_kararsizlik_sayisi = (
            int(eslesmis_df["dinamik_kararsizlik"].fillna(False).astype(bool).sum())
            if "dinamik_kararsizlik" in eslesmis_df.columns
            else None
        )
        sonuclar.append(
            {
                "ucus_numarasi": ucus_no,
                "tarih": tarih,
                "durum": "başarılı",
                "aciklama": "",
                "nokta_sayisi": len(eslesmis_df),
                "eslesen_nokta_sayisi": len(ti1_gecerli),
                "ti1_ortalama": float(ti1_gecerli.mean()) if len(ti1_gecerli) > 0 else None,
                "dinamik_kararsizlik_sayisi": dinamik_kararsizlik_sayisi,
            }
        )

    return pd.DataFrame(sonuclar)


def _argumanlari_ayristir(argv=None):
    ayristirici = argparse.ArgumentParser(
        description="Bir CSV listesindeki birden fazla uçuşu sırayla analiz eder ve özetini tek tabloda toplar.",
    )
    ayristirici.add_argument(
        "ucus_listesi_csv",
        help="'ucus_numarasi' ve 'tarih' sütunlarını içeren CSV dosyası",
    )
    ayristirici.add_argument(
        "--cikti",
        default=None,
        metavar="DOSYA.csv",
        help=f"Özet tablosunun kaydedileceği dosya (varsayılan: {config.CIKTI_KLASORU}/toplu_analiz_ozeti.csv)",
    )
    return ayristirici.parse_args(argv)


if __name__ == "__main__":
    argumanlar = _argumanlari_ayristir()

    try:
        ucus_listesi_df = pd.read_csv(argumanlar.ucus_listesi_csv)
    except FileNotFoundError:
        raise SystemExit(f"[Hata] '{argumanlar.ucus_listesi_csv}' bulunamadı.")

    for sutun in ("ucus_numarasi", "tarih"):
        if sutun not in ucus_listesi_df.columns:
            raise SystemExit(
                f"[Hata] '{argumanlar.ucus_listesi_csv}' dosyasında '{sutun}' sütunu yok. "
                f"Beklenen sütunlar: ucus_numarasi, tarih."
            )

    ozet_df = toplu_analiz_calistir(ucus_listesi_df)

    cikti_dosyasi = argumanlar.cikti
    if cikti_dosyasi is None:
        os.makedirs(config.CIKTI_KLASORU, exist_ok=True)
        cikti_dosyasi = os.path.join(config.CIKTI_KLASORU, "toplu_analiz_ozeti.csv")
    ozet_df.to_csv(cikti_dosyasi, index=False)

    print(f"\n{'=' * 60}")
    print("TOPLU ANALİZ ÖZETİ")
    print("=" * 60)
    print(ozet_df.to_string(index=False))
    print(f"\nÖzet kaydedildi: {cikti_dosyasi}")

    basarili_sayisi = (ozet_df["durum"] == "başarılı").sum()
    print(f"{basarili_sayisi}/{len(ozet_df)} uçuş başarıyla analiz edildi.")
