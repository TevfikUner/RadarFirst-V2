import contextvars
import functools

from turbulans_radar import config

_etkin_esik = contextvars.ContextVar("etkin_ti1_esigi", default=None)


def kaynak_ti1_esigi(kaynak: str | None) -> float:
    if kaynak == "gfs" and config.TI1_ESIK_ORTA_SIDDETLI_GFS is not None:
        return float(config.TI1_ESIK_ORTA_SIDDETLI_GFS)
    return float(config.TI1_ESIK_ORTA_SIDDETLI)


def etkin_ti1_esigi() -> float:
    deger = _etkin_esik.get()
    return float(config.TI1_ESIK_ORTA_SIDDETLI) if deger is None else deger


def kaynaga_gore_ayarla(kaynak: str | None) -> float:
    esik = kaynak_ti1_esigi(kaynak)
    _etkin_esik.set(esik)
    return esik


def ayri_esik_baglaminda(fonksiyon):
    @functools.wraps(fonksiyon)
    def sarmalayici(*args, **kwargs):
        return contextvars.copy_context().run(fonksiyon, *args, **kwargs)

    return sarmalayici
