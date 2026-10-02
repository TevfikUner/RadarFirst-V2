"""
madis_edr.py
---------------
M1: uçakların yerinde (in-situ) ölçtüğü türbülans (EDR) -- NOAA MADIS herkese
açık ACARS arşivi (https://madis-data.ncep.noaa.gov/madisPublic1/data/archive/
YYYY/MM/DD/point/acars/netcdf/YYYYMMDD_HH00.gz, saatlik, ~2-3 MB). Kısıtlı erişim
başvurusu reddedildi (2026-10-02); public dosyalar maxEDR/medEDR içeriyor.

Yalnızca seyir irtifasındaki (MADIS_MIN_IRTIFA_FT) geçerli EDR gözlemleri günlük
Parquet'e (MADIS_EDR_KLASORU/YYYY/MM/DD.parquet) yazılır; ham dosya silinir.
Ham veri ve Parquet depoya konmaz.

Kalite: public arşivde EDR'nin QC tanımlayıcısı 'Z' = "Preliminary data, no QC
checks performed" (NWS Codes Registry). Bu yüzden makullük filtresi uygulanır
(0 <= EDR <= MADIS_EDR_MAKS) ve tanımlayıcı her gözlemle saklanır.

Şiddet sınıfları (ICAO Annex 3 §2.6, A41-WP/235'te aktarıldığı üzere; tepe EDR,
m^(2/3) s^-1): hafif 0.1-0.4, orta 0.4-0.7, şiddetli > 0.7 (config.EDR_ESIK_*).

Ban koruması: tek seferde tek indirme (dağıtık kilit), dosyalar arası
MADIS_ISTEKLER_ARASI_SANIYE, günde en fazla MADIS_GUNLUK_MAKS_DOSYA dosya
(veritabanı sayacı), geçici hatada az ve üstel aralıklı yeniden deneme.
"""

import gzip
import os
import tempfile
import time
import uuid

import httpx
import numpy as np
import pandas as pd

from turbulans_radar import config
from turbulans_radar.depo.dagitik_kilit import dagitik_kilit
from turbulans_radar.depo.hiz_siniri import KOTA_ONEKI, istegi_say_senkron
from turbulans_radar.loglama import logger_al
from turbulans_radar.yeniden_deneme import gecici_hatada_yeniden_dene

_logger = logger_al(__name__)

METRE_FT = 3.28084
KOTA_ANAHTARI = f"{KOTA_ONEKI}madis_gunluk_dosya"
SUTUNLAR = ["zaman", "enlem", "boylam", "irtifa_ft", "max_edr", "med_edr", "kalite"]


class MadisKotaAsildiHatasi(RuntimeError):
    pass


def dosya_url(gun, saat: int) -> str:
    gun = pd.Timestamp(gun)
    return f"{config.MADIS_ARSIV_URL}/{gun:%Y/%m/%d}/point/acars/netcdf/{gun:%Y%m%d}_{saat:02d}00.gz"


def gun_yolu(gun) -> str:
    gun = pd.Timestamp(gun)
    return os.path.join(config.MADIS_EDR_KLASORU, f"{gun:%Y}", f"{gun:%m}", f"{gun:%d}.parquet")


def edr_cikar(nc_yolu: str) -> pd.DataFrame:
    """Saatlik ACARS NetCDF'inden seyir irtifasındaki geçerli EDR gözlemleri."""
    import xarray as xr

    with xr.open_dataset(nc_yolu, decode_times=False, mask_and_scale=True) as veri:
        if "maxEDR" not in veri or "medEDR" not in veri:
            return pd.DataFrame(columns=SUTUNLAR)
        df = pd.DataFrame(
            {
                "zaman_unix": veri["timeObs"].values.astype(float),
                "enlem": veri["latitude"].values.astype(float),
                "boylam": veri["longitude"].values.astype(float),
                "irtifa_ft": veri["altitude"].values.astype(float) * METRE_FT,
                "max_edr": veri["maxEDR"].values.astype(float),
                "med_edr": veri["medEDR"].values.astype(float),
                "kalite": [
                    (k.decode("ascii", "ignore") if isinstance(k, bytes) else str(k)).strip() or None
                    for k in (veri["maxEDRDD"].values if "maxEDRDD" in veri else [None] * veri.sizes["recNum"])
                ],
            }
        )
    gecerli = (
        np.isfinite(df[["zaman_unix", "enlem", "boylam", "irtifa_ft", "max_edr", "med_edr"]]).all(axis=1)
        & df["max_edr"].between(0, config.MADIS_EDR_MAKS)
        & df["med_edr"].between(0, config.MADIS_EDR_MAKS)
        & df["enlem"].between(-90, 90)
        & df["boylam"].between(-180, 180)
        & (df["irtifa_ft"] >= config.MADIS_MIN_IRTIFA_FT)
        & (df["kalite"] != "X")
    )
    df = df[gecerli].copy()
    df["zaman"] = pd.to_datetime(df["zaman_unix"], unit="s", utc=True)
    return df[SUTUNLAR].drop_duplicates(["zaman", "enlem", "boylam", "irtifa_ft"]).reset_index(drop=True)


@gecici_hatada_yeniden_dene()
def _indir(url: str) -> bytes:
    yanit = httpx.get(url, timeout=httpx.Timeout(30.0, read=180.0), follow_redirects=True)
    if yanit.status_code == 404:
        return b""
    yanit.raise_for_status()
    return yanit.content


def _kotayi_tuket(sayac=None) -> int:
    sayi = (sayac or (lambda: istegi_say_senkron(KOTA_ANAHTARI, 86400)))()
    if sayi > config.MADIS_GUNLUK_MAKS_DOSYA:
        raise MadisKotaAsildiHatasi(f"Günlük MADIS dosya sınırı ({config.MADIS_GUNLUK_MAKS_DOSYA}) doldu.")
    return sayi


def saatlik_edr(gun, saat: int, indirici=None) -> pd.DataFrame:
    icerik = (indirici or _indir)(dosya_url(gun, saat))
    if not icerik:
        return pd.DataFrame(columns=SUTUNLAR)
    with tempfile.TemporaryDirectory() as gecici:
        yol = os.path.join(gecici, "acars.nc")
        with open(yol, "wb") as dosya:
            dosya.write(gzip.decompress(icerik))
        return edr_cikar(yol)


def gunluk_edr(gun, indirici=None, sayac=None, uyku=time.sleep) -> pd.DataFrame:
    """Bir günün 24 saatlik dosyasını sırayla işler ve Parquet'e yazar; zaten
    varsa indirmeden okur. Kilit ve kota bu fonksiyondadır."""
    yol = gun_yolu(gun)
    if os.path.exists(yol):
        return pd.read_parquet(yol)
    parcalar = []
    with dagitik_kilit("madis_indirme", zaman_asimi_saniye=0):
        for saat in range(24):
            if saat:
                uyku(config.MADIS_ISTEKLER_ARASI_SANIYE)
            _kotayi_tuket(sayac)
            parcalar.append(saatlik_edr(gun, saat, indirici))
    df = pd.concat(parcalar, ignore_index=True) if parcalar else pd.DataFrame(columns=SUTUNLAR)
    os.makedirs(os.path.dirname(yol), exist_ok=True)
    gecici = f"{yol}.{uuid.uuid4().hex[:12]}.yaziliyor"
    try:
        df.to_parquet(gecici, index=False)
        os.replace(gecici, yol)
    finally:
        if os.path.exists(gecici):
            os.remove(gecici)
    _logger.info("MADIS EDR %s: %d seyir gözlemi.", pd.Timestamp(gun).date(), len(df))
    return df


def edr_sinifi(max_edr) -> np.ndarray:
    """0 yok (< hafif eşiği), 1 hafif, 2 orta, 3 şiddetli (ICAO tepe EDR eşikleri)."""
    edr = np.asarray(max_edr, dtype=float)
    return (
        (edr >= config.EDR_ESIK_HAFIF).astype(int)
        + (edr >= config.EDR_ESIK_ORTA).astype(int)
        + (edr >= config.EDR_ESIK_SIDDETLI).astype(int)
    )
