"""
veri_kontrol.py
-----------------
Turuncu/tek renkli haritanın sebebini TAHMİN etmek yerine, verinin gerçek
çözünürlüğünü (kaç farklı zaman/enlem/boylam/basınç noktası olduğunu) ve
hesaplanan TI1 değerlerinin ne kadar ÇEŞİTLİ olduğunu gösterir.

NOT: main.py artık sonucu bir CSV'ye değil PostgreSQL'e yazıyor (bkz.
veritabani.py) -- bu script de artık eski `eslesme_sonuclari_*.csv`
dosyasını değil, doğrudan veritabanındaki kayıtları okuyor.

Kullanım:
    python veri_kontrol.py N10VZ 2019-01-15
"""

import argparse

from konsol_kurulumu import konsolu_utf8_yap

konsolu_utf8_yap()

import xarray as xr

import config
from veritabani import VeritabaniAyarlariEksikHatasi, ucus_olcumlerini_dataframe_olarak_getir


def nc_dosyasini_incele():
    print("=" * 60)
    print(f"1) HAVA DURUMU VERİ KÜPÜ: {config.HAVA_DURUMU_DOSYASI}")
    print("=" * 60)
    try:
        ds = xr.open_dataset(config.HAVA_DURUMU_DOSYASI)
    except FileNotFoundError:
        print("Dosya bulunamadı, bu kısmı atlıyorum.")
        return

    for boyut_adi in ds.dims:
        boyut_degerleri = ds[boyut_adi].values
        print(f"  Boyut '{boyut_adi}': {len(boyut_degerleri)} adet değer")
        if len(boyut_degerleri) <= 10:
            print(f"    -> Değerler: {boyut_degerleri}")
        else:
            print(f"    -> Min: {boyut_degerleri.min()}  Maks: {boyut_degerleri.max()}")

    print()
    if "latitude" in ds.dims and "longitude" in ds.dims:
        lat_araligi = float(ds["latitude"].max() - ds["latitude"].min())
        lon_araligi = float(ds["longitude"].max() - ds["longitude"].min())
        print(f"  Kapsanan enlem aralığı : {lat_araligi:.2f} derece")
        print(f"  Kapsanan boylam aralığı: {lon_araligi:.2f} derece")
        if len(ds["latitude"]) <= 3 or len(ds["longitude"]) <= 3:
            print("  !!! UYARI: Enlem/boylam grid'i çok seyrek (3 veya daha az nokta).")
            print("      Bu, farklı konumların aynı hücreye 'yuvarlanmasına' ve")
            print("      bütün rotanın aynı TI1 değerini almasına yol açabilir.")
    if "valid_time" in ds.dims:
        if len(ds["valid_time"]) <= 2:
            print("  !!! UYARI: Sadece 1-2 zaman adımı var.")
            print("      Uçuş süresince rüzgar alanı hiç 'güncellenmiyor' demektir --")
            print("      bütün uçuş tek bir anlık görüntüye göre hesaplanıyor.")
    print()


def ucus_sonuclarini_incele(ucus_numarasi, tarih_str):
    print("=" * 60)
    print(f"2) HESAPLANAN SONUÇLAR (PostgreSQL): {ucus_numarasi} / {tarih_str}")
    print("=" * 60)
    try:
        df = ucus_olcumlerini_dataframe_olarak_getir(ucus_numarasi, tarih_str)
    except VeritabaniAyarlariEksikHatasi as hata:
        print(f"Veritabanına erişilemedi: {hata}")
        return

    if df is None:
        print(f"'{ucus_numarasi}' / {tarih_str} için kayıt bulunamadı. Önce main.py ile analiz çalıştır.")
        return
    if df.empty or "ti1_indeksi" not in df.columns:
        print("Kayıtlı ölçüm yok ya da 'ti1_indeksi' sütunu bulunamadı.")
        return

    ti1 = df["ti1_indeksi"].dropna()
    if ti1.empty:
        print("Hiçbir noktada geçerli TI1 değeri yok (hepsi veri küpü kapsamı dışında kalmış olabilir).")
        return

    benzersiz_sayisi = ti1.nunique()
    print(f"  Toplam nokta             : {len(df)}")
    print(f"  Geçerli TI1 değeri       : {len(ti1)}")
    print(f"  Benzersiz TI1 değeri     : {benzersiz_sayisi}")
    print(f"  TI1 min / ortalama / maks: {ti1.min():.3e} / {ti1.mean():.3e} / {ti1.max():.3e}")
    print(f"  TI1 standart sapma       : {ti1.std():.3e}")

    if benzersiz_sayisi < len(ti1) * 0.1:
        print("\n  !!! UYARI: Benzersiz değer sayısı, toplam nokta sayısının")
        print("      %10'undan az. Birçok farklı rota noktası AYNI hava durumu")
        print("      hücresine denk geliyor demektir -- veri küpü çözünürlüğü muhtemelen")
        print("      çok kaba (dar alan/az zaman adımı ile indirilmiş).")

    if "basinc_hpa" in df.columns:
        basinc_benzersiz = df["basinc_hpa"].nunique()
        print(f"\n  Rota boyunca kullanılan farklı basınç seviyesi sayısı: {basinc_benzersiz}")
        print(f"  Kullanılan basınç seviyeleri: {sorted(df['basinc_hpa'].dropna().unique())}")


def _argumanlari_ayristir(argv=None):
    ayristirici = argparse.ArgumentParser(
        description="Hava durumu veri küpünün çözünürlüğünü ve PostgreSQL'deki (veritabani.py) "
        "TI1 değerlerinin çeşitliliğini kontrol eder.",
    )
    ayristirici.add_argument(
        "ucus_numarasi",
        nargs="?",
        default=None,
        help="main.py ile daha önce analiz edilmiş bir uçuş numarası (opsiyonel)",
    )
    ayristirici.add_argument("tarih", nargs="?", default=None, help="YYYY-MM-DD (opsiyonel)")
    return ayristirici.parse_args(argv)


if __name__ == "__main__":
    argumanlar = _argumanlari_ayristir()
    nc_dosyasini_incele()
    if argumanlar.ucus_numarasi and argumanlar.tarih:
        ucus_sonuclarini_incele(argumanlar.ucus_numarasi, argumanlar.tarih)
    else:
        print(
            "İpucu: 'python veri_kontrol.py N10VZ 2019-01-15' şeklinde uçuş numarası + tarih de ver "
            "(önce main.py ile o uçuşu analiz etmiş olman gerekir)."
        )
