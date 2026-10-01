"""
sanal_pirep.py
----------------
M6: ADS-B izinden "sanal PIREP" -- seyir fazındaki bir uçağın atanmış
seviyesinden ani irtifa sapmaları. Türbülansın en doğrudan sensörü onu o anda
yaşayan uçaktır; ADS-B her uçak için barometrik irtifa ve düşey hız taşır.

Yöntem (eşikler ve dayanakları config.SANAL_PIREP_* yorumunda):
  1. İz, SANAL_PIREP_MAKS_BOSLUK_SANIYE'den uzun boşluklarda parçalara bölünür.
  2. Atanmış seviye = merkezli kayan medyan irtifa (SEVIYE_PENCERESI). Pencere
     kenarındaki noktalar (tam pencere yok), seyir alt sınırının altı ve seviye
     medyanının ±1 pencere içinde SEVIYE_DEGISIM_ESIGI'nden fazla oynadığı
     bölümler (tırmanış, alçalış, kademeli tırmanış) seyir sayılmaz.
  3. Seyirde |irtifa - seviye| >= SAPMA_ESIGI olan ardışık noktalar bir olay
     adayıdır; düşey hız varsa çevresinde DIKEY_HIZ_TUTARLILIK'a ulaşan bir
     düşey hız tepkisi aranır (yoksa tek raporluk irtifa sıçraması sayılır).
  4. Olaylar uzay-zamanda kümelenir; farklı uçakların aynı bölgede gösterdiği
     işaret tek uçağınkinden güvenilirdir.

Bu sinyal ML eğitim etiketi olarak KULLANILMAZ; yalnızca canlı olay sensörüdür.
Çıktı sertifikalı EDR ya da şiddet sınıfı değildir: sapma ve düşey hız ham
büyüklük olarak raporlanır, şiddete çevrilmez.
"""

import numpy as np
import pandas as pd

from turbulans_radar import config
from turbulans_radar.fizik.eslestirme import rota_irtifalari_ve_kaynagi

METRE_FT = 3.28084
MS_FTDK = 196.850394
_DUNYA_YARICAPI_KM = 6371.0

OLAY_SUTUNLARI = [
    "icao24",
    "ucus_numarasi",
    "zaman",
    "baslangic",
    "bitis",
    "sure_sn",
    "enlem",
    "boylam",
    "seviye_ft",
    "sapma_ft",
    "maks_dikey_hiz_ftdk",
    "irtifa_kaynagi",
]


def _mesafe_km(enlem1, boylam1, enlem2, boylam2):
    p1, p2 = np.radians(enlem1), np.radians(enlem2)
    dp, dl = p2 - p1, np.radians(np.asarray(boylam2) - np.asarray(boylam1))
    a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * _DUNYA_YARICAPI_KM * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))


def _iz_hazirla(iz_df: pd.DataFrame) -> pd.DataFrame:
    irtifa_m, kaynak = rota_irtifalari_ve_kaynagi(iz_df)
    df = pd.DataFrame(
        {
            "zaman": pd.to_datetime(iz_df["zaman"], utc=True),
            "enlem": iz_df["enlem"].astype(float).to_numpy(),
            "boylam": iz_df["boylam"].astype(float).to_numpy(),
            "irtifa_ft": irtifa_m * METRE_FT,
            "irtifa_kaynagi": kaynak,
            "dikey_hiz_ftdk": (
                pd.to_numeric(iz_df["dikey_hiz"], errors="coerce").to_numpy() * MS_FTDK
                if "dikey_hiz" in iz_df.columns
                else np.nan
            ),
        }
    )
    df = df.dropna(subset=["zaman", "enlem", "boylam", "irtifa_ft"])
    return df.sort_values("zaman").drop_duplicates("zaman").reset_index(drop=True)


def seyir_maskesi(df: pd.DataFrame) -> pd.DataFrame:
    """df'ye 'seviye_ft', 'sapma_ft' ve 'seyirde' sütunlarını ekler."""
    pencere = config.SANAL_PIREP_SEVIYE_PENCERESI_SANIYE
    yarim = pd.Timedelta(seconds=pencere / 2)
    df = df.copy()
    df["parca"] = (df["zaman"].diff().dt.total_seconds() > config.SANAL_PIREP_MAKS_BOSLUK_SANIYE).cumsum()
    seviye = pd.Series(np.nan, index=df.index)
    seviye_oynamasi = pd.Series(np.nan, index=df.index)
    kenardan_uzak = pd.Series(False, index=df.index)
    for _, parca in df.groupby("parca"):
        zamanli = parca.set_index("zaman")["irtifa_ft"]
        medyan = zamanli.rolling(f"{pencere}s", center=True).median()
        oynama = (
            medyan.rolling(f"{2 * pencere}s", center=True).max() - medyan.rolling(f"{2 * pencere}s", center=True).min()
        )
        seviye.loc[parca.index] = medyan.to_numpy()
        seviye_oynamasi.loc[parca.index] = oynama.to_numpy()
        bas, son = parca["zaman"].iloc[0], parca["zaman"].iloc[-1]
        kenardan_uzak.loc[parca.index] = ((parca["zaman"] - bas >= yarim) & (son - parca["zaman"] >= yarim)).to_numpy()
    df["seviye_ft"] = seviye
    df["sapma_ft"] = df["irtifa_ft"] - df["seviye_ft"]
    df["seyirde"] = (
        kenardan_uzak
        & (df["seviye_ft"] >= config.SANAL_PIREP_MIN_IRTIFA_FT)
        & (seviye_oynamasi <= config.SANAL_PIREP_SEVIYE_DEGISIM_ESIGI_FT)
    )
    return df


def olaylari_tespit_et(iz_df: pd.DataFrame, icao24=None, ucus_numarasi=None) -> tuple[pd.DataFrame, dict]:
    """Tek uçağın izinden olaylar. iz_df: zaman, enlem, boylam ve
    baro_irtifa_m / geo_irtifa_m; varsa dikey_hiz (m/s). Dönüş: (olaylar,
    özet) -- özet 'seyir_suresi_sn' değerlendirilebilen seyir süresidir (olay
    yokluğu ancak bu süre > 0 ise 'sakin' anlamına gelir)."""
    if icao24 is None and "icao24" in iz_df.columns and len(iz_df):
        icao24 = str(iz_df["icao24"].iloc[0])
    if ucus_numarasi is None and "ucus_numarasi" in iz_df.columns and len(iz_df):
        ucus_numarasi = str(iz_df["ucus_numarasi"].iloc[0]).strip() or None
    df = _iz_hazirla(iz_df)
    bos = pd.DataFrame(columns=OLAY_SUTUNLARI)
    if len(df) < 3:
        return bos, {"nokta_sayisi": len(df), "seyir_suresi_sn": 0.0, "olay_sayisi": 0}
    df = seyir_maskesi(df)
    adim = df["zaman"].diff().dt.total_seconds().fillna(0.0)
    seyir_suresi = float(adim[df["seyirde"] & df["seyirde"].shift(fill_value=False)].sum())

    aday = df["seyirde"] & (df["sapma_ft"].abs() >= config.SANAL_PIREP_SAPMA_ESIGI_FT)
    olaylar = []
    if aday.any():
        adaylar = df[aday]
        grup = (adaylar["zaman"].diff().dt.total_seconds() > config.SANAL_PIREP_OLAY_BIRLESTIRME_SANIYE).cumsum()
        dikey_hiz_var = df["dikey_hiz_ftdk"].notna().any()
        tolerans = pd.Timedelta(seconds=config.SANAL_PIREP_MAKS_BOSLUK_SANIYE)
        for _, olay in adaylar.groupby(grup):
            bas, son = olay["zaman"].iloc[0], olay["zaman"].iloc[-1]
            cevre = df[(df["zaman"] >= bas - tolerans) & (df["zaman"] <= son + tolerans)]
            maks_dikey = float(cevre["dikey_hiz_ftdk"].abs().max()) if dikey_hiz_var else np.nan
            if dikey_hiz_var and not maks_dikey >= config.SANAL_PIREP_DIKEY_HIZ_TUTARLILIK_FTDK:
                continue
            tepe = olay.loc[olay["sapma_ft"].abs().idxmax()]
            olaylar.append(
                {
                    "icao24": icao24,
                    "ucus_numarasi": ucus_numarasi,
                    "zaman": tepe["zaman"],
                    "baslangic": bas,
                    "bitis": son,
                    "sure_sn": float((son - bas).total_seconds()),
                    "enlem": float(tepe["enlem"]),
                    "boylam": float(tepe["boylam"]),
                    "seviye_ft": float(tepe["seviye_ft"]),
                    "sapma_ft": float(tepe["sapma_ft"]),
                    "maks_dikey_hiz_ftdk": maks_dikey,
                    "irtifa_kaynagi": tepe["irtifa_kaynagi"],
                }
            )
    sonuc = pd.DataFrame(olaylar, columns=OLAY_SUTUNLARI) if olaylar else bos
    return sonuc, {"nokta_sayisi": len(df), "seyir_suresi_sn": seyir_suresi, "olay_sayisi": len(sonuc)}


def coklu_izden_olaylar(izler_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Birden çok uçağın izi (icao24 sütunu ile ayrılır). Dönüş: (olaylar,
    uçak başına özet)."""
    olay_listesi, ozetler = [], []
    for icao24, iz in izler_df.groupby("icao24"):
        olaylar, ozet = olaylari_tespit_et(iz, icao24=str(icao24))
        if not olaylar.empty:
            olay_listesi.append(olaylar)
        ozetler.append({"icao24": str(icao24), **ozet})
    olaylar = pd.concat(olay_listesi, ignore_index=True) if olay_listesi else pd.DataFrame(columns=OLAY_SUTUNLARI)
    return olaylar, pd.DataFrame(ozetler)


def yakin_mi(enlem1, boylam1, zaman1, irtifa1_ft, enlem2, boylam2, zaman2, irtifa2_ft, yaricap_km, sure, irtifa_ft):
    """Vektörel uzay-zaman yakınlığı (kümeleme ve PIREP eşleştirmesi ortak)."""
    zaman_farki = (pd.to_datetime(zaman1, utc=True) - pd.to_datetime(zaman2, utc=True)).abs()
    return (
        (np.asarray(_mesafe_km(enlem1, boylam1, enlem2, boylam2)) <= yaricap_km)
        & (np.abs(np.asarray(irtifa1_ft, dtype=float) - np.asarray(irtifa2_ft, dtype=float)) <= irtifa_ft)
        & np.asarray(zaman_farki <= sure)
    )


def _ucak_kimligi(olaylar: pd.DataFrame) -> pd.Series:
    return olaylar["icao24"].where(olaylar["icao24"].notna(), olaylar["ucus_numarasi"]).astype(str)


def olaylari_kumele(olaylar: pd.DataFrame) -> pd.DataFrame:
    """Uzay-zaman yakınlığıyla bağlantılı olaylar aynı kümeye girer (birleşim-
    bul). Her olaya 'kume' ve kümesindeki farklı uçak sayısı 'ucak_sayisi'
    eklenir."""
    df = olaylar.reset_index(drop=True).copy()
    if df.empty:
        df["kume"] = pd.Series(dtype=int)
        df["ucak_sayisi"] = pd.Series(dtype=int)
        return df
    ebeveyn = list(range(len(df)))

    def kok(i):
        while ebeveyn[i] != i:
            ebeveyn[i] = ebeveyn[ebeveyn[i]]
            i = ebeveyn[i]
        return i

    seviye = df["seviye_ft"] + df["sapma_ft"]
    sure = pd.Timedelta(minutes=config.SANAL_PIREP_KUME_SURESI_DAKIKA)
    for i in range(len(df)):
        yakinlar = yakin_mi(
            df.at[i, "enlem"],
            df.at[i, "boylam"],
            df.at[i, "zaman"],
            seviye.iat[i],
            df["enlem"].to_numpy(),
            df["boylam"].to_numpy(),
            df["zaman"],
            seviye.to_numpy(),
            config.SANAL_PIREP_KUME_YARICAPI_KM,
            sure,
            config.SANAL_PIREP_KUME_IRTIFA_FARKI_FT,
        )
        for j in np.flatnonzero(yakinlar):
            ebeveyn[kok(int(j))] = kok(i)
    df["kume"] = [kok(i) for i in range(len(df))]
    df["kume"] = df["kume"].rank(method="dense").astype(int) - 1
    df["ucak_sayisi"] = _ucak_kimligi(df).groupby(df["kume"]).transform("nunique").astype(int)
    return df


def kume_ozeti(kumelenmis: pd.DataFrame) -> list[dict]:
    ozet = []
    for kume, grup in kumelenmis.groupby("kume"):
        ozet.append(
            {
                "kume": int(kume),
                "olay_sayisi": len(grup),
                "ucak_sayisi": int(grup["ucak_sayisi"].iloc[0]),
                "ilk_zaman": grup["zaman"].min(),
                "son_zaman": grup["zaman"].max(),
                "enlem": float(grup["enlem"].mean()),
                "boylam": float(grup["boylam"].mean()),
                "seviye_ft": float(grup["seviye_ft"].median()),
                "maks_sapma_ft": float(grup["sapma_ft"].abs().max()),
                "dogrulanmis": int(grup["ucak_sayisi"].iloc[0]) >= config.SANAL_PIREP_BILDIRIM_MIN_UCAK,
            }
        )
    return ozet
