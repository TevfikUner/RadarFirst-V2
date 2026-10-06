"""
edr_kalibrasyonu.py
----------------------
TI1 -> EDR proxy ölçeklendirme katsayısını (tanh ölçeği) ml_ornekleri'ndeki
doğru irtifalı PIREP'lerle yeniden kalibre eder: en son günler test için
ayrılır, katsayı eğitim günlerinde uydurulur, güven aralığı gün bazlı
bootstrap ile hesaplanır. Proxy sertifikalı EDR değildir; PIREP şiddet
sınıfının (0/0.5/1) beklenen değerine uyan görsel bir ölçektir.
"""

import argparse
import json

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from turbulans_radar import config
from turbulans_radar.depo.models import MlOrnegi
from turbulans_radar.depo.veritabani import motor_al
from turbulans_radar.fizik.kalibrasyon import _kayip_hesapla, katsayi_kalibre_et
from turbulans_radar.ml.ml_otomatik_egitim import zamansal_holdout

SINIF_MAKS_DEGERI = 2


def kalibrasyon_verisi(motor=None) -> pd.DataFrame:
    sorgu = select(MlOrnegi.zaman, MlOrnegi.sinif, MlOrnegi.ozellikler["ti1_indeksi"].as_float()).where(
        MlOrnegi.durum == "eslesti"
    )
    with Session(motor or motor_al()) as oturum:
        satirlar = oturum.execute(sorgu).all()
    df = pd.DataFrame(satirlar, columns=["zaman", "sinif", "ti1_indeksi"]).dropna()
    df["pirep_edr"] = df["sinif"] / SINIF_MAKS_DEGERI
    df["gun"] = pd.to_datetime(df["zaman"], utc=True).dt.strftime("%Y-%m-%d")
    return df.reset_index(drop=True)


def gun_bazli_guven_araligi(df, tekrar=300, guven=0.95, tohum=0, arama_araligi=(0.01, 3.0), adim_sayisi=600):
    rng = np.random.default_rng(tohum)
    gun_gruplari = [g for _, g in df.groupby("gun")]
    katsayilar = np.empty(tekrar)
    for i in range(tekrar):
        ornek = pd.concat([gun_gruplari[j] for j in rng.integers(0, len(gun_gruplari), len(gun_gruplari))])
        katsayilar[i], _ = katsayi_kalibre_et(
            ornek["ti1_indeksi"], ornek["pirep_edr"], arama_araligi=arama_araligi, adim_sayisi=adim_sayisi
        )
    alt = (1 - guven) / 2 * 100
    return float(np.percentile(katsayilar, alt)), float(np.percentile(katsayilar, 100 - alt))


def edr_kalibrasyonu_calistir(df=None, motor=None, tekrar=300, arama_araligi=(0.01, 3.0), adim_sayisi=600) -> dict:
    df = kalibrasyon_verisi(motor) if df is None else df
    if df["gun"].nunique() < 5:
        raise ValueError(f"Kalibrasyon için en az 5 farklı gün gerekli ({df['gun'].nunique()} var).")
    test = zamansal_holdout(df["gun"])
    egitim_df, test_df = df[~test], df[test]
    yeni, egitim_mse = katsayi_kalibre_et(
        egitim_df["ti1_indeksi"], egitim_df["pirep_edr"], arama_araligi=arama_araligi, adim_sayisi=adim_sayisi
    )
    eski = config.EDR_OLCEKLENDIRME_KATSAYISI_ESKI
    mevcut = config.EDR_OLCEKLENDIRME_KATSAYISI
    tum_veri, _ = katsayi_kalibre_et(
        df["ti1_indeksi"], df["pirep_edr"], arama_araligi=arama_araligi, adim_sayisi=adim_sayisi
    )
    alt, ust = gun_bazli_guven_araligi(df, tekrar=tekrar, arama_araligi=arama_araligi, adim_sayisi=adim_sayisi)
    return {
        "yeni_katsayi_tum_veri": tum_veri,
        "guven_araligi_95": [alt, ust],
        "egitim_katsayisi": yeni,
        "mevcut_katsayi": mevcut,
        "eski_katsayi": eski,
        "test_mse_yeni": _kayip_hesapla(yeni, test_df["ti1_indeksi"].to_numpy(), test_df["pirep_edr"].to_numpy()),
        "test_mse_mevcut": _kayip_hesapla(mevcut, test_df["ti1_indeksi"].to_numpy(), test_df["pirep_edr"].to_numpy()),
        "test_mse_eski": _kayip_hesapla(eski, test_df["ti1_indeksi"].to_numpy(), test_df["pirep_edr"].to_numpy()),
        "test_mse_sabit_ortalama": float(np.mean((test_df["pirep_edr"] - egitim_df["pirep_edr"].mean()) ** 2)),
        "egitim_mse": egitim_mse,
        "ornek": len(df),
        "gun": int(df["gun"].nunique()),
        "egitim_ornek": len(egitim_df),
        "test_ornek": len(test_df),
        "test_gunleri": sorted(test_df["gun"].unique().tolist()),
    }


def ana(argv=None):
    ayristirici = argparse.ArgumentParser(description="EDR proxy katsayısını ml_ornekleri ile yeniden kalibre eder.")
    ayristirici.add_argument("--tekrar", type=int, default=300, help="Gün bazlı bootstrap tekrar sayısı")
    argumanlar = ayristirici.parse_args(argv)
    print(json.dumps(edr_kalibrasyonu_calistir(tekrar=argumanlar.tekrar), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    ana()
