"""
pirep_kalibrasyon_verisi_uret.py
-----------------------------------
kalibrasyon.py, "ti1_indeksi" + "pirep_edr" (0-1 normalize) sütunlarını
içeren bir gözlem CSV'si bekler ama bu depoda böyle bir dosya YOKTU --
Türkiye/Ocak-2019 veri kümesi için gerçek PIREP/AMDAR gözlemi olmadığı
için kalibrasyon.py'nin kendisi "bu aracı sen kendi verinle çalıştır"
diyordu.

ml_veri_indir.py + ml_egitimi.py ile ML sınıflandırıcısı için GERÇEK IEM
PIREP + eşleşen gerçek ERA5 verisi indirilip diske kaydedildi
(pirep_ust_seviye_siniflandirilmis.csv, era5_egitim_verisi/*.nc) -- bu
script, o AYNI gerçek veriyi (ml_egitimi.veriyi_hazirla ile aynı eşleştirme
mantığıyla) kalibrasyon.py'nin beklediği formata çevirir:

  - ti1_indeksi: turbulans_ml_modeli.ozellikleri_cikar'ın hesapladığı Ellrod
    TI1 (projenin ANA fizik göstergesi).
  - pirep_edr: PIREP'in 3 seviyeli "sinif" sütunu (0=yok/hafif, 1=orta,
    2=şiddetli -- bkz. ml_egitimi.py) [0, 1] aralığına doğrusal olarak
    ölçeklenir (sinif / 2).

Çalıştırma:
    python -m turbulans_radar.ml.pirep_kalibrasyon_verisi_uret
    python -m turbulans_radar.fizik.kalibrasyon pirep_kalibrasyon_verisi.csv
"""

import glob

import pandas as pd
import xarray as xr

from turbulans_radar.konsol_kurulumu import konsolu_utf8_yap
from turbulans_radar.ml.turbulans_ml_modeli import ozellikleri_cikar, ozellikleri_temizle

konsolu_utf8_yap()

PIREP_DOSYASI = "pirep_ust_seviye_siniflandirilmis.csv"
ERA5_KLASORU = "era5_egitim_verisi"
CIKTI_DOSYASI = "pirep_kalibrasyon_verisi.csv"

# PIREP "sinif" sütununun (0/1/2) [0, 1] aralığına ölçeklenmesi için
# bölen -- ml_egitimi.py'deki en yüksek sinif değeriyle AYNI olmalı.
SINIF_MAKS_DEGERI = 2


def kalibrasyon_verisini_hazirla():
    pirep = pd.read_csv(PIREP_DOSYASI, parse_dates=["VALID"])
    pirep["irtifa_m"] = pirep["FL"] * 100 * 0.3048
    pirep = pirep.rename(columns={"VALID": "zaman", "LAT": "enlem", "LON": "boylam"})

    tum_satirlar = []
    for dosya_yolu in sorted(glob.glob(f"{ERA5_KLASORU}/*.nc")):
        yil_ay = dosya_yolu.split("\\")[-1].split("/")[-1].replace(".nc", "")
        yil, ay = yil_ay.split("_")
        alt = pirep[(pirep["zaman"].dt.year == int(yil)) & (pirep["zaman"].dt.month == int(ay))]
        if alt.empty:
            continue
        veri_kupu = xr.open_dataset(dosya_yolu)
        ozellikler = ozellikleri_cikar(alt, veri_kupu)
        temiz_ozellikler, temiz_sinif = ozellikleri_temizle(ozellikler, alt["sinif"].reset_index(drop=True))
        veri_kupu.close()
        if not temiz_ozellikler.empty:
            tum_satirlar.append(
                pd.DataFrame(
                    {
                        "ti1_indeksi": temiz_ozellikler["ti1_indeksi"],
                        "pirep_edr": temiz_sinif.to_numpy() / SINIF_MAKS_DEGERI,
                    }
                )
            )
            print(f"[{yil_ay}] {len(temiz_ozellikler)} gerçek eşleşen gözlem eklendi")

    return pd.concat(tum_satirlar, ignore_index=True)


if __name__ == "__main__":
    print("Gerçek PIREP + gerçek ERA5 verisinden kalibrasyon gözlem seti kuruluyor...\n")
    gozlem_df = kalibrasyon_verisini_hazirla()
    gozlem_df.to_csv(CIKTI_DOSYASI, index=False)
    print(f"\nToplam {len(gozlem_df)} gerçek gözlem -> '{CIKTI_DOSYASI}' dosyasına yazıldı.")
    print(f"Şimdi çalıştır: python kalibrasyon.py {CIKTI_DOSYASI}")
