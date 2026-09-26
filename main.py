"""
main.py
--------
Projenin uçtan uca akışı:

  1. Kullanıcıdan bir UÇUŞ NUMARASI ve TARİH al.
  2. OpenSky/Trino'dan o uçuşun gerçek state-vector rotasını çek
     (callsign -> icao24 -> state_vectors_data4).
  3. Copernicus/ERA5 veri küpünü yükle.
  4. Rotadaki her noktayı en yakın hava durumu hücresiyle eşleştir ve
     Ellrod TI1 tabanlı EDR-proxy türbülans şiddetini hesapla.
  5. Sonucu PostgreSQL'e (ucuslar + edr_olcumleri tabloları) kaydet ve özet
     istatistik yazdır (süre, TI1 dağılımı) -- böylece haritadaki renklerin
     "gerçek mi yoksa şüpheli mi" olduğunu tahmin etmek yerine sayılarla
     kontrol edebiliyoruz.
  6. Zaman kaydırıcılı interaktif haritayı üret.

Eşleştirme başarısız olursa (uçuş bulunamazsa, veri küpü eksikse vb.)
pipeline çökmek yerine açıklayıcı bir mesajla nazikçe durur.
"""

import argparse
import os

from konsol_kurulumu import konsolu_utf8_yap

konsolu_utf8_yap()

import config
from eslestirme import rotayi_hava_durumuyla_eslestir
from harita import zaman_kaydiricili_harita_olustur
from hata_yardimcisi import dostane_hata_mesaji
from kimlik_dogrulama import KimlikBilgisiEksikHatasi
from turbulans_indeksleri import DINAMIK_KARARSIZLIK_ESIGI
from veri_yukleme import hava_durumu_onbellekli_yukle, trino_baglantisi_olustur, ucus_numarasi_ile_rota_cek
from veritabani import VeritabaniKayitHatasi, ucus_ve_olcumleri_kaydet


def _ozet_yazdir(eslesmis_df, ucus_numarasi, tarih_str):
    """Haritaya bakmadan önce ham sayılarla kontrol edebilmek için özet."""
    zaman_min = eslesmis_df["zaman"].min()
    zaman_maks = eslesmis_df["zaman"].max()
    sure_saniye = (zaman_maks - zaman_min).total_seconds()
    sure_saat = sure_saniye / 3600

    ti1_gecerli = eslesmis_df["ti1_indeksi"].dropna()
    nokta_sayisi = len(eslesmis_df)
    gecerli_sayisi = len(ti1_gecerli)

    print("\n" + "=" * 60)
    print(f"ÖZET: {ucus_numarasi} / {tarih_str}")
    print("=" * 60)
    print(f"Toplam nokta sayısı        : {nokta_sayisi}")
    print(f"Eşleşen (TI1 hesaplanan)   : {gecerli_sayisi} ({gecerli_sayisi / nokta_sayisi * 100:.1f}%)")
    print(f"İlk kayıt zamanı           : {zaman_min}")
    print(f"Son kayıt zamanı           : {zaman_maks}")
    print(f"Kapsanan süre              : {sure_saat:.2f} saat ({sure_saniye:.0f} saniye)")
    if gecerli_sayisi > 0:
        print(f"Ortalama örnekleme aralığı : {sure_saniye / max(nokta_sayisi - 1, 1):.1f} saniye/nokta")
        print(
            f"TI1 min / ortalama / maks  : {ti1_gecerli.min():.3e} / {ti1_gecerli.mean():.3e} / {ti1_gecerli.max():.3e} s^-2"
        )
        print(
            f"TI1 eşikleri (config.py)  : hafif < {config.TI1_ESIK_HAFIF:.0e} < orta-şiddetli < {config.TI1_ESIK_ORTA_SIDDETLI:.0e}"
        )
        hafif_alti = (ti1_gecerli < config.TI1_ESIK_HAFIF).sum()
        orta = ((ti1_gecerli >= config.TI1_ESIK_HAFIF) & (ti1_gecerli < config.TI1_ESIK_ORTA_SIDDETLI)).sum()
        siddetli = (ti1_gecerli >= config.TI1_ESIK_ORTA_SIDDETLI).sum()
        print(f"Sakin/hafif altı (yeşil)  : {hafif_alti} nokta ({hafif_alti / gecerli_sayisi * 100:.1f}%)")
        print(f"Hafif-orta (turuncu)      : {orta} nokta ({orta / gecerli_sayisi * 100:.1f}%)")
        print(f"Orta-şiddetli (kırmızı)   : {siddetli} nokta ({siddetli / gecerli_sayisi * 100:.1f}%)")

        if "dinamik_kararsizlik" in eslesmis_df.columns:
            kararsiz_sayisi = eslesmis_df["dinamik_kararsizlik"].fillna(False).astype(bool).sum()
            print(
                f"Richardson < {DINAMIK_KARARSIZLIK_ESIGI:.2f} "
                f"(dinamik kararsızlık, TI1'den BAĞIMSIZ ek gösterge): "
                f"{kararsiz_sayisi} nokta ({kararsiz_sayisi / gecerli_sayisi * 100:.1f}%)"
            )
    if not config.EDR_OLCEKLENDIRME_KATSAYISI_KALIBRE_EDILDI:
        print(
            f"[Uyarı] EDR proxy ölçeklendirme katsayısı ({config.EDR_OLCEKLENDIRME_KATSAYISI}) "
            f"HENÜZ GERÇEK PIREP/AMDAR VERİSİYLE KALİBRE EDİLMEDİ -- keyfi bir başlangıç "
            f"değeridir. Kalibre etmek için kalibrasyon.py'yi kullan, sonucu "
            f"config.EDR_OLCEKLENDIRME_KATSAYISI'ye yaz ve "
            f"EDR_OLCEKLENDIRME_KATSAYISI_KALIBRE_EDILDI = True yap."
        )
    print("=" * 60 + "\n")


def calistir(ucus_numarasi: str, tarih_str: str, cikti_dosyasi: str = None, kayit_zorunlu: bool = False):
    os.makedirs(config.CIKTI_KLASORU, exist_ok=True)
    if cikti_dosyasi is None:
        # Her uçuş/tarih için ayrı dosya adı -- farklı uçuşları denerken
        # birbirinin üzerine yazmasın diye. ciktilar/ altına yazılır --
        # proje kökü artık her çalıştırmada yeni bir HTML'le dolmuyor.
        cikti_dosyasi = os.path.join(config.CIKTI_KLASORU, f"turbulans_haritasi_{ucus_numarasi}_{tarih_str}.html")

    print(f"1. '{ucus_numarasi}' uçuşu {tarih_str} tarihi için OpenSky'da aranıyor...")
    try:
        baglanti = trino_baglantisi_olustur()
    except KimlikBilgisiEksikHatasi as hata:
        print(f"[Durduruldu] {hata}")
        return None

    rota_df = ucus_numarasi_ile_rota_cek(baglanti, ucus_numarasi, tarih_str)
    if rota_df is None:
        print(
            "[Durduruldu] Uçuş/OpenSky verisiyle eşleşme sağlanamadı. "
            "Uçuş numarasını, tarihi veya OpenSky kapsama alanını kontrol et."
        )
        return None
    print(f"   -> {len(rota_df)} state-vector kaydı bulundu.")

    print("2. Hava durumu veri küpü yükleniyor...")
    try:
        veri_kupu = hava_durumu_onbellekli_yukle(config.HAVA_DURUMU_DOSYASI)
    except FileNotFoundError as hata:
        print(f"[Durduruldu] {hata}")
        return None

    print("3. Rota, hava durumu verisiyle eşleştiriliyor ve türbülans şiddeti hesaplanıyor...")
    eslesmis_df = rotayi_hava_durumuyla_eslestir(rota_df, veri_kupu)

    try:
        ucus_ve_olcumleri_kaydet(eslesmis_df, ucus_numarasi, tarih_str)
        print(f"   -> Ham sonuçlar PostgreSQL'e kaydedildi (ucus_numarasi={ucus_numarasi}, tarih={tarih_str}).")
    except Exception as hata:
        if kayit_zorunlu:
            raise VeritabaniKayitHatasi(
                "Analiz tamamlandı ama sonuçlar veritabanına kaydedilemedi -- sunucu loglarını kontrol et."
            ) from hata
        print(f"[Uyarı] Sonuçlar veritabanına kaydedilemedi: {dostane_hata_mesaji(hata)}")
        print("   -> Harita yine de üretilecek, ama bu çalıştırma kalıcı olarak saklanmadı.")

    _ozet_yazdir(eslesmis_df, ucus_numarasi, tarih_str)

    print("4. İnteraktif harita oluşturuluyor...")
    zaman_kaydiricili_harita_olustur(eslesmis_df, dosya_adi=cikti_dosyasi)

    print("Tamamlandı.")
    return eslesmis_df


def _argumanlari_ayristir(argv=None):
    ayristirici = argparse.ArgumentParser(
        description="Bir uçuşun gerçek rotasını türbülans şiddetiyle (Ellrod TI1 + Richardson) eşleştirir "
        "ve zaman kaydırıcılı interaktif bir harita üretir.",
    )
    ayristirici.add_argument(
        "ucus_numarasi",
        nargs="?",
        default="THY1234",
        help="OpenSky callsign, örn. THY1234 (varsayılan: THY1234 -- örnek uçuş için ornek_ucus_bul.py kullan)",
    )
    ayristirici.add_argument(
        "tarih",
        nargs="?",
        default="2019-01-01",
        help="YYYY-MM-DD formatında tarih (varsayılan: 2019-01-01)",
    )
    ayristirici.add_argument(
        "--cikti",
        default=None,
        metavar="DOSYA.html",
        help="Harita çıktısının kaydedileceği dosya adı (varsayılan: turbulans_haritasi_<uçuş>_<tarih>.html)",
    )
    return ayristirici.parse_args(argv)


if __name__ == "__main__":
    argumanlar = _argumanlari_ayristir()
    if argumanlar.ucus_numarasi == "THY1234" and argumanlar.tarih == "2019-01-01":
        print(
            "[Bilgi] Argüman verilmedi, örnek değerler kullanılıyor: THY1234 / 2019-01-01 "
            "(gerçek bir uçuş için: python ornek_ucus_bul.py)"
        )

    try:
        calistir(argumanlar.ucus_numarasi, argumanlar.tarih, cikti_dosyasi=argumanlar.cikti)
    except Exception as hata:
        print(f"\n[Hata] {dostane_hata_mesaji(hata)}")
        raise SystemExit(1) from hata
