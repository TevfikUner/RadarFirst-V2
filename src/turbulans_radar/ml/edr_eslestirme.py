"""
edr_eslestirme.py
--------------------
M1: MADIS uçak EDR gözlemlerini (veri/madis_edr.py) ERA5 pencere deposundaki
(ml/ozellik_deposu.py) küplerle eşleştirir -- CDS'e yeni istek gitmez. Her
pencere bir PIREP'in ±1°, ±1 sa çevresidir; pencerenin içine düşen EDR
gözlemleri için aynı kodla (ozellikleri_cikar) ERA5 özellikleri hesaplanır.
Bir gözlem birden çok pencereye düşerse merkezi en yakın olana atanır.

Ayrıca PIREP-EDR karşılaştırması: her PIREP için çevresindeki (50 km, ±2000 ft,
±30 dk) EDR gözlemlerinin en büyüğü; PIREP etiketinin nesnel ölçümle ne kadar
örtüştüğünü gösterir.
"""

import numpy as np
import pandas as pd

from turbulans_radar.ml.ozellik_deposu import ozellik_kupu, pencere_dosyasini_ac, pencereden_kup
from turbulans_radar.veri.madis_edr import METRE_FT, edr_sinifi

_DUNYA_YARICAPI_KM = 6371.0
PIREP_TUP_KM = 50.0
PIREP_TUP_FT = 2000.0
PIREP_TUP_SURE = pd.Timedelta(minutes=30)


def _mesafe_km(e1, b1, e2, b2):
    p1, p2 = np.radians(e1), np.radians(e2)
    dp, dl = p2 - p1, np.radians(np.asarray(b2) - np.asarray(b1))
    a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * _DUNYA_YARICAPI_KM * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def pencere_icindekiler(kup, edr_df: pd.DataFrame) -> pd.DataFrame:
    """Küpün enlem/boylam aralığına ve saatlerinin ±30 dk'sına düşen gözlemler."""
    zamanlar = pd.to_datetime(kup["valid_time"].values).tz_localize("UTC")
    enlem, boylam = kup["latitude"].values, kup["longitude"].values
    maske = (
        edr_df["enlem"].between(enlem.min(), enlem.max())
        & edr_df["boylam"].between(boylam.min(), boylam.max())
        & edr_df["zaman"].between(zamanlar.min() - pd.Timedelta(minutes=30), zamanlar.max() + pd.Timedelta(minutes=30))
    )
    return edr_df[maske]


def gun_eslestir(ornekler: pd.DataFrame, edr_df: pd.DataFrame) -> pd.DataFrame:
    """ornekler: o güne ait pencereli ml_ornekleri (id, zaman, enlem, boylam,
    pencere_dosyasi). Dönüş: eşleşen EDR gözlemleri + ERA5 özellikleri +
    ml_ornek_id (penceresi kullanılan PIREP)."""
    from turbulans_radar.ml.turbulans_ml_modeli import OZELLIK_SUTUNLARI, ozellikleri_cikar

    if ornekler.empty or edr_df.empty:
        return pd.DataFrame()
    edr_df = edr_df.assign(zaman=pd.to_datetime(edr_df["zaman"], utc=True)).reset_index(drop=True)
    adaylar = []
    for goreli_yol, grup in ornekler.groupby("pencere_dosyasi", sort=False):
        pencereler = pencere_dosyasini_ac(goreli_yol)
        for satir in grup.itertuples(index=False):
            kup = pencereden_kup(pencereler, satir.id)
            icinde = pencere_icindekiler(kup, edr_df)
            if icinde.empty:
                continue
            uzaklik = _mesafe_km(satir.enlem, satir.boylam, icinde["enlem"].to_numpy(), icinde["boylam"].to_numpy())
            adaylar.append(icinde.assign(ml_ornek_id=satir.id, _uzaklik=uzaklik, _kup=[kup] * len(icinde)))
    if not adaylar:
        return pd.DataFrame()
    birlesik = pd.concat(adaylar).sort_values("_uzaklik", kind="stable")
    birlesik = birlesik[~birlesik.index.duplicated(keep="first")]
    parcalar = []
    for _, grup in birlesik.groupby("ml_ornek_id"):
        kup = grup["_kup"].iloc[0]
        noktalar = grup.assign(irtifa_m=grup["irtifa_ft"] / METRE_FT)
        ozellikler = ozellikleri_cikar(noktalar, ozellik_kupu(kup))
        parcalar.append(
            grup.drop(columns=["_kup", "_uzaklik"]).reset_index(drop=True).join(ozellikler[OZELLIK_SUTUNLARI])
        )
    sonuc = pd.concat(parcalar, ignore_index=True)
    sonuc = sonuc.dropna(subset=OZELLIK_SUTUNLARI)
    return sonuc.assign(edr_sinifi=edr_sinifi(sonuc["max_edr"])).reset_index(drop=True)


def pirep_edr_karsilastir(ornekler: pd.DataFrame, edr_df: pd.DataFrame, sinif_sutunu="sinif") -> pd.DataFrame:
    """Her PIREP için çevresindeki EDR gözlemlerinin en büyüğü ve sayısı."""
    edr_df = edr_df.assign(zaman=pd.to_datetime(edr_df["zaman"], utc=True))
    satirlar = []
    for p in ornekler.itertuples(index=False):
        zaman = pd.Timestamp(p.zaman)
        aday = edr_df[
            edr_df["zaman"].between(zaman - PIREP_TUP_SURE, zaman + PIREP_TUP_SURE)
            & (edr_df["irtifa_ft"] - p.irtifa_ft).abs().le(PIREP_TUP_FT)
        ]
        if not aday.empty:
            aday = aday[
                _mesafe_km(p.enlem, p.boylam, aday["enlem"].to_numpy(), aday["boylam"].to_numpy()) <= PIREP_TUP_KM
            ]
        satirlar.append(
            {
                "id": p.id,
                "pirep_sinif": getattr(p, sinif_sutunu),
                "edr_gozlem": len(aday),
                "maks_edr": float(aday["max_edr"].max()) if len(aday) else np.nan,
            }
        )
    df = pd.DataFrame(satirlar)
    df["edr_sinifi"] = np.where(df["edr_gozlem"] > 0, edr_sinifi(df["maks_edr"].fillna(0)), -1)
    return df
