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
  5. Sonucu bir CSV'ye kaydet ve özet istatistik yazdır (süre, TI1 dağılımı)
     -- böylece haritadaki renklerin "gerçek mi yoksa şüpheli mi" olduğunu
     tahmin etmek yerine sayılarla kontrol edebiliyoruz.
  6. Zaman kaydırıcılı interaktif haritayı üret.

Eşleştirme başarısız olursa (uçuş bulunamazsa, veri küpü eksikse vb.)
pipeline çökmek yerine açıklayıcı bir mesajla nazikçe durur.
"""

import sys

import config
from veri_yukleme import hava_durumu_yukle, trino_baglantisi_olustur, ucus_numarasi_ile_rota_cek
from eslestirme import rotayi_hava_durumuyla_eslestir
from harita import zaman_kaydiricili_harita_olustur
from kimlik_dogrulama import KimlikBilgisiEksikHatasi


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
    print(f"Eşleşen (TI1 hesaplanan)   : {gecerli_sayisi} ({gecerli_sayisi/nokta_sayisi*100:.1f}%)")
    print(f"İlk kayıt zamanı           : {zaman_min}")
    print(f"Son kayıt zamanı           : {zaman_maks}")
    print(f"Kapsanan süre              : {sure_saat:.2f} saat ({sure_saniye:.0f} saniye)")
    if gecerli_sayisi > 0:
        print(f"Ortalama örnekleme aralığı : {sure_saniye / max(nokta_sayisi - 1, 1):.1f} saniye/nokta")
        print(f"TI1 min / ortalama / maks  : {ti1_gecerli.min():.3e} / {ti1_gecerli.mean():.3e} / {ti1_gecerli.max():.3e} s⁻²")
        print(f"TI1 eşikleri (config.py)  : hafif < {config.TI1_ESIK_HAFIF:.0e} < orta-şiddetli < {config.TI1_ESIK_ORTA_SIDDETLI:.0e}")
        hafif_alti = (ti1_gecerli < config.TI1_ESIK_HAFIF).sum()
        orta = ((ti1_gecerli >= config.TI1_ESIK_HAFIF) & (ti1_gecerli < config.TI1_ESIK_ORTA_SIDDETLI)).sum()
        siddetli = (ti1_gecerli >= config.TI1_ESIK_ORTA_SIDDETLI).sum()
        print(f"Sakin/hafif altı (yeşil)  : {hafif_alti} nokta ({hafif_alti/gecerli_sayisi*100:.1f}%)")
        print(f"Hafif-orta (turuncu)      : {orta} nokta ({orta/gecerli_sayisi*100:.1f}%)")
        print(f"Orta-şiddetli (kırmızı)   : {siddetli} nokta ({siddetli/gecerli_sayisi*100:.1f}%)")
    print("=" * 60 + "\n")


def calistir(ucus_numarasi: str, tarih_str: str, cikti_dosyasi: str = None):
    if cikti_dosyasi is None:
        # Her uçuş/tarih için ayrı dosya adı -- farklı uçuşları denerken
        # birbirinin üzerine yazmasın diye.
        cikti_dosyasi = f"turbulans_haritasi_{ucus_numarasi}_{tarih_str}.html"
    csv_dosyasi = f"eslesme_sonuclari_{ucus_numarasi}_{tarih_str}.csv"

    print(f"1. '{ucus_numarasi}' uçuşu {tarih_str} tarihi için OpenSky'da aranıyor...")
    try:
        baglanti = trino_baglantisi_olustur()
    except KimlikBilgisiEksikHatasi as hata:
        print(f"[Durduruldu] {hata}")
        return None

    rota_df = ucus_numarasi_ile_rota_cek(baglanti, ucus_numarasi, tarih_str)
    if rota_df is None:
        print("[Durduruldu] Uçuş/OpenSky verisiyle eşleşme sağlanamadı. "
              "Uçuş numarasını, tarihi veya OpenSky kapsama alanını kontrol et.")
        return None
    print(f"   -> {len(rota_df)} state-vector kaydı bulundu.")

    print("2. Hava durumu veri küpü yükleniyor...")
    try:
        veri_kupu = hava_durumu_yukle(config.HAVA_DURUMU_DOSYASI)
    except FileNotFoundError as hata:
        print(f"[Durduruldu] {hata}")
        return None

    print("3. Rota, hava durumu verisiyle eşleştiriliyor ve türbülans şiddeti hesaplanıyor...")
    eslesmis_df = rotayi_hava_durumuyla_eslestir(rota_df, veri_kupu)

    eslesmis_df.to_csv(csv_dosyasi, index=False)
    print(f"   -> Ham sonuçlar kaydedildi: {csv_dosyasi} (Excel'de açıp inceleyebilirsin)")

    _ozet_yazdir(eslesmis_df, ucus_numarasi, tarih_str)

    print("4. İnteraktif harita oluşturuluyor...")
    zaman_kaydiricili_harita_olustur(eslesmis_df, dosya_adi=cikti_dosyasi)

    print("Tamamlandı.")
    return eslesmis_df


if __name__ == "__main__":
    # Örnek kullanım: python main.py THY1234 2019-01-01
    if len(sys.argv) >= 3:
        ucus_no = sys.argv[1]
        tarih = sys.argv[2]
    else:
        ucus_no = "THY1234"   # örnek değer - kendi uçuş numaranla değiştir
        tarih = "2019-01-01"
        print(f"[Bilgi] Argüman verilmedi, örnek değerler kullanılıyor: {ucus_no} / {tarih}")

    calistir(ucus_no, tarih)
