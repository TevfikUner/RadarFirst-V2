"""
sanal_pirep_hatti.py
----------------------
M6 akışı: iz -> olay tespiti (fizik/sanal_pirep.py) -> kayıt
(depo/sanal_pirep_deposu.py) -> en az SANAL_PIREP_BILDIRIM_MIN_UCAK farklı
uçağın doğruladığı olaylar için /ws/uyarilar bildirimi (tip 'sanal_pirep').

Girdiler: işçide her uçuş/rota analizinin izi (OpenSky'a ek sorgu yok) ve
POST /api/v1/sanal-pirep/iz ile dışarıdan gelen canlı izler.
"""

from collections.abc import Callable

import pandas as pd

from turbulans_radar import config, loglama
from turbulans_radar.depo.sanal_pirep_deposu import bildirim_zamanini_isle, olaylari_kaydet
from turbulans_radar.fizik.sanal_pirep import era5_uyumunu_ekle, olaylari_tespit_et

_logger = loglama.logger_al(__name__)


def _ucak_adi(icao24, ucus_numarasi) -> str:
    gecerli = [d for d in (icao24, ucus_numarasi) if isinstance(d, str) and d]
    return (gecerli[0] if gecerli else "bilinmiyor")[:16]


def _utc_ns(zaman) -> int:
    t = pd.Timestamp(zaman)
    return (t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")).value


def bildirim_mesaji(kayit: dict) -> dict:
    return {
        "tip": "sanal_pirep",
        "id": kayit["id"],
        "ucak": kayit["ucak"],
        "ucus_numarasi": kayit["ucus_numarasi"],
        "zaman": kayit["zaman"].isoformat(),
        "enlem": kayit["enlem"],
        "boylam": kayit["boylam"],
        "seviye_ft": round(kayit["seviye_ft"]),
        "sapma_ft": round(kayit["sapma_ft"]),
        "ucak_sayisi": kayit["ucak_sayisi"],
        "kaynak": kayit["kaynak"],
        "era5_uyumu": kayit.get("era5_uyumu", "bilinmiyor"),
        "era5_ti1": kayit.get("era5_ti1"),
    }


def izden_sanal_pirep_uret(
    iz_df, kaynak: str, yayinla: Callable[[dict], None], icao24=None, ucus_numarasi=None, motor=None
) -> dict:
    olaylar, ozet = olaylari_tespit_et(iz_df, icao24=icao24, ucus_numarasi=ucus_numarasi)
    kayitlar = olaylari_kaydet(olaylar, kaynak, motor=motor)
    uyum = {
        (_ucak_adi(o.icao24, o.ucus_numarasi), _utc_ns(o.zaman)): (
            o.era5_uyumu,
            None if pd.isna(o.era5_ti1) else float(o.era5_ti1),
        )
        for o in era5_uyumunu_ekle(olaylar, iz_df).itertuples()
    }
    bildirilen = []
    for kayit in kayitlar:
        kayit["era5_uyumu"], kayit["era5_ti1"] = uyum.get(
            (kayit["ucak"], _utc_ns(kayit["zaman"])), ("bilinmiyor", None)
        )
        if kayit["ucak_sayisi"] < config.SANAL_PIREP_BILDIRIM_MIN_UCAK:
            continue
        try:
            yayinla(bildirim_mesaji(kayit))
            bildirilen.append(kayit["id"])
        except Exception as hata:
            _logger.warning("Sanal PIREP bildirimi yayınlanamadı (%s): %s", kayit["id"], type(hata).__name__)
    bildirim_zamanini_isle(bildirilen, motor=motor)
    return {**ozet, "kaydedilen": len(kayitlar), "bildirilen": len(bildirilen), "olaylar": kayitlar}
