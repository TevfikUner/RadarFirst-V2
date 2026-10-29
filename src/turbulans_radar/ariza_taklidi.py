"""Demo arıza tatbikatı (S-4): SIGMET bayat/erişilemedi ve devre kesici durumları sunucuyu bozmadan
yalnız o istek için taklit edilir. config.ARIZA_TAKLIDI_ETKIN kapalıyken API isteği reddeder; sonuçta
'ariza_taklidi' bulgusu SENTETİK etiketiyle yer alır."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

TAKLITLER = ("sigmet_bayat", "sigmet_erisilemedi", "devre_kesici")

_etkin: ContextVar[str | None] = ContextVar("ariza_taklidi", default=None)


@contextmanager
def ariza_taklidi(ad: str | None) -> Iterator[None]:
    if ad is not None and ad not in TAKLITLER:
        raise ValueError(f"Bilinmeyen arıza taklidi: {ad}")
    belirtec = _etkin.set(ad)
    try:
        yield
    finally:
        _etkin.reset(belirtec)


def etkin_taklit() -> str | None:
    return _etkin.get()


def taklit_mi(ad: str) -> bool:
    return _etkin.get() == ad
