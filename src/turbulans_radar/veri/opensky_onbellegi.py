"""
opensky_onbellegi.py
-----------------------
OpenSky rotalarının (uçuş numarası + tarih) Parquet disk önbelleği: tamamlanmış
uçuşlar değişmediği için aynı uçuş Trino'ya ikinci kez sorulmaz.
"""

import os
import re
import uuid

import pandas as pd

from turbulans_radar import config
from turbulans_radar.loglama import logger_al

_logger = logger_al(__name__)

_GUVENLI_UCUS_NUMARASI = re.compile(r"[A-Z0-9]{2,8}")


def rota_onbellek_yolu(ucus_numarasi: str, tarih_str: str) -> str | None:
    ucus = str(ucus_numarasi).strip().upper()
    if not _GUVENLI_UCUS_NUMARASI.fullmatch(ucus):
        return None
    try:
        tarih = pd.Timestamp(tarih_str)
    except (ValueError, TypeError):
        return None
    return os.path.join(config.OPENSKY_ONBELLEK_KLASORU, f"{ucus}_{tarih:%Y-%m-%d}.parquet")


def rota_onbellekte_var_mi(ucus_numarasi: str, tarih_str: str) -> bool:
    yol = rota_onbellek_yolu(ucus_numarasi, tarih_str)
    return yol is not None and os.path.exists(yol)


def rota_onbellekten_oku(ucus_numarasi: str, tarih_str: str) -> pd.DataFrame | None:
    yol = rota_onbellek_yolu(ucus_numarasi, tarih_str)
    if yol is None or not os.path.exists(yol):
        return None
    try:
        return pd.read_parquet(yol)
    except Exception as hata:
        _logger.warning("OpenSky rota önbelleği okunamadı, yeniden sorgulanacak (%s): %s", yol, hata)
        return None


def rota_onbellege_yaz(rota_df: pd.DataFrame, ucus_numarasi: str, tarih_str: str) -> str | None:
    yol = rota_onbellek_yolu(ucus_numarasi, tarih_str)
    if yol is None or rota_df is None or rota_df.empty:
        return None
    son_zaman = pd.to_datetime(rota_df["zaman"], utc=True).max()
    if son_zaman > pd.Timestamp.now(tz="UTC") - pd.Timedelta(hours=config.OPENSKY_ONBELLEK_MIN_YAS_SAAT):
        return None
    os.makedirs(os.path.dirname(yol) or ".", exist_ok=True)
    gecici = f"{yol}.{uuid.uuid4().hex[:12]}.yaziliyor"
    try:
        rota_df.to_parquet(gecici, index=False)
        os.replace(gecici, yol)
    except Exception as hata:
        _logger.warning("OpenSky rotası önbelleğe yazılamadı (%s): %s", yol, hata)
        if os.path.exists(gecici):
            os.remove(gecici)
        return None
    return yol
