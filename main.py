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
  5. Zaman kaydırıcılı interaktif haritayı üret.

Eşleştirme başarısız olursa (uçuş bulunamazsa, veri küpü eksikse vb.)
pipeline çökmek yerine açıklayıcı bir mesajla nazikçe durur — kod
yapısı, "yapamıyorsan bırak" prensibine göre tasarlandı.
"""

import sys

import config
from veri_yukleme import hava_durumu_yukle, trino_baglantisi_olustur, ucus_numarasi_ile_rota_cek
from eslestirme import rotayi_hava_durumuyla_eslestir
from harita import zaman_kaydiricili_harita_olustur
from kimlik_dogrulama import KimlikBilgisiEksikHatasi


def calistir(ucus_numarasi: str, tarih_str: str, cikti_dosyasi: str = "turbulans_haritasi.html"):
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
