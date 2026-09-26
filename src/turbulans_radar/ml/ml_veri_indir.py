"""
ml_veri_indir.py
-------------------
ML türbülans sınıflandırıcısını eğitmek için, gerçek IEM PIREP arşivinin
en yoğun olduğu (Kuzeydoğu ABD hava koridoru, ~40-50N/-80--70W) bölge/
tarihler için gerçek ERA5 rüzgar+sıcaklık verisini indirir. Kullanıcının
kendi Copernicus CDS hesabıyla (~/.cdsapirc) çalışır -- bu, projenin
veri_indirme.py'sindeki "gerçek indirme sadece açık onayla" ilkesinin bir
devamıdır, tek seferlik ve denetimli bir eğitim-verisi toplama işlemidir.

era5_indirme_plani.csv'deki (gerçek PIREP yoğunluğu analizinden gelen) her
(yıl, ay, gün listesi) kombinasyonu için ayrı bir ERA5 indirme isteği
gönderir, era5_egitim_verisi/ klasörüne kaydeder.
"""

import cdsapi
import pandas as pd

ALAN = [50, -80, 40, -70]  # [Kuzey, Batı, Güney, Doğu] -- CDS format
BASINC_SEVIYELERI = ["300", "250", "200"]
DEGISKENLER = ["temperature", "u_component_of_wind", "v_component_of_wind"]

plan = pd.read_csv("era5_indirme_plani.csv", parse_dates=["baslangic"])
gunler = set()
for _, satir in plan.iterrows():
    for g in pd.date_range(satir["baslangic"], periods=3):
        gunler.add(g)

gunler_df = pd.DataFrame({"tarih": sorted(gunler)})
gunler_df["yil"] = gunler_df["tarih"].dt.year
gunler_df["ay"] = gunler_df["tarih"].dt.month

istemci = cdsapi.Client()

import os

os.makedirs("era5_egitim_verisi", exist_ok=True)

for (yil, ay), grup in gunler_df.groupby(["yil", "ay"]):
    gunler_listesi = sorted(grup["tarih"].dt.day.unique().tolist())
    hedef = f"era5_egitim_verisi/{yil}_{ay:02d}.nc"
    if os.path.exists(hedef):
        print(f"[Atlandi] {hedef} zaten var.")
        continue
    istek = {
        "product_type": ["reanalysis"],
        "variable": DEGISKENLER,
        "year": [str(yil)],
        "month": [f"{ay:02d}"],
        "day": [f"{g:02d}" for g in gunler_listesi],
        "time": [f"{s:02d}:00" for s in range(0, 24, 3)],  # 3 saatte bir yeterli
        "pressure_level": BASINC_SEVIYELERI,
        "area": ALAN,
        "data_format": "netcdf",
    }
    print(f"[Indiriliyor] {yil}-{ay:02d}, gunler={gunler_listesi} -> {hedef}")
    istemci.retrieve("reanalysis-era5-pressure-levels", istek, hedef)
    print(f"[Tamamlandi] {hedef}")

print("Tum indirmeler tamamlandi.")
