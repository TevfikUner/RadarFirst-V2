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
    print(f"1) HAVA DURUMU VERI KUPU: {config.HAVA_DURUMU_DOSYASI}")
    print("=" * 60)
    try:
        ds = xr.open_dataset(config.HAVA_DURUMU_DOSYASI)
    except FileNotFoundError:
        print("Dosya bulunamadi, bu kismi atliyorum.")
        return

    for boyut_adi in ds.dims:
        boyut_degerleri = ds[boyut_adi].values
        print(f"  Boyut '{boyut_adi}': {len(boyut_degerleri)} adet deger")
        if len(boyut_degerleri) <= 10:
            print(f"    -> Degerler: {boyut_degerleri}")
        else:
            print(f"    -> Min: {boyut_degerleri.min()}  Maks: {boyut_degerleri.max()}")

    print()
    if "latitude" in ds.dims and "longitude" in ds.dims:
        lat_araligi = float(ds["latitude"].max() - ds["latitude"].min())
        lon_araligi = float(ds["longitude"].max() - ds["longitude"].min())
        print(f"  Kapsanan enlem araligi : {lat_araligi:.2f} derece")
        print(f"  Kapsanan boylam araligi: {lon_araligi:.2f} derece")
        if len(ds["latitude"]) <= 3 or len(ds["longitude"]) <= 3:
            print("  !!! UYARI: Enlem/boylam grid'i cok seyrek (3 veya daha az nokta).")
            print("      Bu, farkli konumlarin ayni hucreye 'yuvarlanmasina' ve")
            print("      butun rotanin ayni TI1 degerini almasina yol acabilir.")
    if "valid_time" in ds.dims:
        if len(ds["valid_time"]) <= 2:
            print("  !!! UYARI: Sadece 1-2 zaman adimi var.")
            print("      Ucus suresince ruzgar alani hic 'guncellenmiyor' demektir --")
            print("      butun ucus tek bir anlik goruntuye gore hesaplaniyor.")
    print()


def ucus_sonuclarini_incele(ucus_numarasi, tarih_str):
    print("=" * 60)
    print(f"2) HESAPLANAN SONUCLAR (PostgreSQL): {ucus_numarasi} / {tarih_str}")
    print("=" * 60)
    try:
        df = ucus_olcumlerini_dataframe_olarak_getir(ucus_numarasi, tarih_str)
    except VeritabaniAyarlariEksikHatasi as hata:
        print(f"Veritabanina erisilemedi: {hata}")
        return

    if df is None:
        print(f"'{ucus_numarasi}' / {tarih_str} icin kayit bulunamadi. Once main.py ile analiz calistir.")
        return
    if df.empty or "ti1_indeksi" not in df.columns:
        print("Kayitli olcum yok ya da 'ti1_indeksi' sutunu bulunamadi.")
        return

    ti1 = df["ti1_indeksi"].dropna()
    if ti1.empty:
        print("Hicbir noktada gecerli TI1 degeri yok (hepsi veri kupu kapsami disinda kalmis olabilir).")
        return

    benzersiz_sayisi = ti1.nunique()
    print(f"  Toplam nokta            : {len(df)}")
    print(f"  Gecerli TI1 degeri      : {len(ti1)}")
    print(f"  Benzersiz TI1 degeri    : {benzersiz_sayisi}")
    print(f"  TI1 min / ortalama / maks: {ti1.min():.3e} / {ti1.mean():.3e} / {ti1.max():.3e}")
    print(f"  TI1 standart sapma      : {ti1.std():.3e}")

    if benzersiz_sayisi < len(ti1) * 0.1:
        print("\n  !!! UYARI: Benzersiz deger sayisi, toplam nokta sayisinin")
        print("      %10'undan az. Bircok farkli rota noktasi AYNI hava durumu")
        print("      hucresine denk geliyor demektir -- veri kupu coz. muhtemelen")
        print("      cok kaba (dar alan/az zaman adimi ile indirilmis).")

    if "basinc_hpa" in df.columns:
        basinc_benzersiz = df["basinc_hpa"].nunique()
        print(f"\n  Rota boyunca kullanilan farkli basinc seviyesi sayisi: {basinc_benzersiz}")
        print(f"  Kullanilan basinc seviyeleri: {sorted(df['basinc_hpa'].dropna().unique())}")


def _argumanlari_ayristir(argv=None):
    ayristirici = argparse.ArgumentParser(
        description="Hava durumu veri kupunun cozunurlugunu ve PostgreSQL'deki (veritabani.py) "
                     "TI1 degerlerinin cesitliligini kontrol eder.",
    )
    ayristirici.add_argument(
        "ucus_numarasi", nargs="?", default=None,
        help="main.py ile daha once analiz edilmis bir ucus numarasi (opsiyonel)",
    )
    ayristirici.add_argument("tarih", nargs="?", default=None, help="YYYY-MM-DD (opsiyonel)")
    return ayristirici.parse_args(argv)


if __name__ == "__main__":
    argumanlar = _argumanlari_ayristir()
    nc_dosyasini_incele()
    if argumanlar.ucus_numarasi and argumanlar.tarih:
        ucus_sonuclarini_incele(argumanlar.ucus_numarasi, argumanlar.tarih)
    else:
        print("Ipucu: 'python veri_kontrol.py N10VZ 2019-01-15' seklinde ucus numarasi + tarih de ver "
              "(once main.py ile o ucusu analiz etmis olman gerekir).")
