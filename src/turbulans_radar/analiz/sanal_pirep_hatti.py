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

from turbulans_radar import config, loglama
from turbulans_radar.depo.sanal_pirep_deposu import bildirim_zamanini_isle, olaylari_kaydet
from turbulans_radar.fizik.sanal_pirep import olaylari_tespit_et

_logger = loglama.logger_al(__name__)


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
    }


def izden_sanal_pirep_uret(
    iz_df, kaynak: str, yayinla: Callable[[dict], None], icao24=None, ucus_numarasi=None, motor=None
) -> dict:
    olaylar, ozet = olaylari_tespit_et(iz_df, icao24=icao24, ucus_numarasi=ucus_numarasi)
    kayitlar = olaylari_kaydet(olaylar, kaynak, motor=motor)
    bildirilen = []
    for kayit in kayitlar:
        if kayit["ucak_sayisi"] < config.SANAL_PIREP_BILDIRIM_MIN_UCAK:
            continue
        try:
            yayinla(bildirim_mesaji(kayit))
            bildirilen.append(kayit["id"])
        except Exception as hata:
            _logger.warning("Sanal PIREP bildirimi yayınlanamadı (%s): %s", kayit["id"], type(hata).__name__)
    bildirim_zamanini_isle(bildirilen, motor=motor)
    return {**ozet, "kaydedilen": len(kayitlar), "bildirilen": len(bildirilen), "olaylar": kayitlar}
