"""
pirep_kalibrasyon_verisi_uret.py
-----------------------------------
KULLANIM DIŞI. Eski EDR kalibrasyon gözlem setini, hatalı irtifa filtresiyle
üretilmiş pirep_ust_seviye_siniflandirilmis.csv'den kuruyordu (IEM'in feet
cinsinden FL sütunu uçuş seviyesi sanılmış, 300-400 feet'teki PIREP'ler
seçilmişti). Yerine: turbulans-edr-kalibrasyon (ml/edr_kalibrasyonu.py).
"""

from turbulans_radar.ml.turbulans_ml_modeli import ESKI_VERI_HATTI_MESAJI, EskiVeriHattiHatasi

PIREP_DOSYASI = "pirep_ust_seviye_siniflandirilmis.csv"
ERA5_KLASORU = "era5_egitim_verisi"
CIKTI_DOSYASI = "pirep_kalibrasyon_verisi.csv"
SINIF_MAKS_DEGERI = 2


def kalibrasyon_verisini_hazirla():
    raise EskiVeriHattiHatasi(ESKI_VERI_HATTI_MESAJI)


if __name__ == "__main__":
    raise SystemExit(ESKI_VERI_HATTI_MESAJI)
