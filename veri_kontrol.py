"""
veri_kontrol.py
-----------------
Turuncu/tek renkli haritanın sebebini TAHMIN etmek yerine, verinin gercek
cozunurlugunu (kac farkli zaman/enlem/boylam/basinc noktasi oldugunu)
ve hesaplanan TI1 degerlerinin ne kadar CESITLI oldugunu gosterir.

Kullanim:
    python veri_kontrol.py eslesme_sonuclari_N10VZ_2019-01-15.csv
"""

import sys
import numpy as np
import pandas as pd
import xarray as xr

import config


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


def csv_sonuclarini_incele(csv_yolu):
    print("=" * 60)
    print(f"2) HESAPLANAN SONUCLAR: {csv_yolu}")
    print("=" * 60)
    df = pd.read_csv(csv_yolu)

    if "ti1_indeksi" not in df.columns:
        print("CSV'de 'ti1_indeksi' sutunu yok, dosya main.py'nin urettigi CSV mi kontrol et.")
        return

    ti1 = df["ti1_indeksi"].dropna()
    benzersiz_sayisi = ti1.nunique()
    print(f"  Toplam satir            : {len(df)}")
    print(f"  Gecerli TI1 degeri      : {len(ti1)}")
    print(f"  Benzersiz TI1 degeri    : {benzersiz_sayisi}")
    print(f"  TI1 min / ortalama / maks: {ti1.min():.3e} / {ti1.mean():.3e} / {ti1.max():.3e}")
    print(f"  TI1 standart sapma      : {ti1.std():.3e}")

    if benzersiz_sayisi < len(ti1) * 0.1:
        print("\n  !!! UYARI: Benzersiz deger sayisi, toplam nokta sayisinin")
        print("      %10'undan az. Bircok farkli rota noktasi AYNI hava durumu")
        print("      hucresine denk geliyor demektir -- veri kupu coz. muhtemelen")
        print("      cok kaba (dar alan/az zaman adimi ile indirilmis).")

    if "enlem" in df.columns and "basinc_hpa" in df.columns:
        basinc_benzersiz = df["basinc_hpa"].nunique()
        print(f"\n  Rota boyunca kullanilan farkli basinc seviyesi sayisi: {basinc_benzersiz}")
        print(f"  Kullanilan basinc seviyeleri: {sorted(df['basinc_hpa'].dropna().unique())}")


if __name__ == "__main__":
    nc_dosyasini_incele()
    if len(sys.argv) >= 2:
        csv_sonuclarini_incele(sys.argv[1])
    else:
        print("Ipucu: 'python veri_kontrol.py eslesme_sonuclari_N10VZ_2019-01-15.csv' seklinde CSV yolu da ver.")
