"""
dagitik_kilit.py
-------------------
Süreçler/konteynerler arası kilit: PostgreSQL oturum düzeyinde advisory lock.
Kilidi tutan bağlantı koparsa (işçi çöker) PostgreSQL kilidi kendiliğinden bırakır.
"""

import hashlib
import threading
import time
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

from turbulans_radar import config
from turbulans_radar.depo.veritabani import baglanti_dizesini_olustur
from turbulans_radar.loglama import logger_al

_logger = logger_al(__name__)


class KilitZamanAsimiHatasi(TimeoutError):
    pass


class KilitAlinamadiHatasi(RuntimeError):
    pass


_motor = None
_motor_kilidi = threading.Lock()


def _kilit_motoru():
    global _motor
    if _motor is None:
        with _motor_kilidi:
            if _motor is None:
                _motor = create_engine(
                    baglanti_dizesini_olustur(),
                    poolclass=NullPool,
                    isolation_level="AUTOCOMMIT",
                    connect_args={"connect_timeout": 5},
                )
    return _motor


def kilit_anahtari(ad: str) -> int:
    return int.from_bytes(hashlib.sha256(ad.encode("utf-8")).digest()[:8], "big", signed=True)


@contextmanager
def dagitik_kilit(
    ad: str, zaman_asimi_saniye: float | None = None, yoklama_saniye: float = 1.0, motor=None, zorunlu: bool = False
):
    """zorunlu=True: veritabanına ulaşılamazsa kilitsiz sürdürmek yerine
    KilitAlinamadiHatasi fırlatır (dış servis kotası/eşzamanlılık koruması)."""
    zaman_asimi = config.DAGITIK_KILIT_ZAMAN_ASIMI_SANIYE if zaman_asimi_saniye is None else zaman_asimi_saniye
    anahtar = kilit_anahtari(ad)
    try:
        baglanti = (motor or _kilit_motoru()).connect()
    except Exception as hata:
        if zorunlu:
            raise KilitAlinamadiHatasi(
                f"'{ad}' kilidi için veritabanına bağlanılamadı; dış servis koruması olmadan sürdürülmez."
            ) from hata
        _logger.warning("Dağıtık kilit için veritabanına bağlanılamadı, '%s' kilitsiz sürdürülüyor: %s", ad, hata)
        baglanti = None
    if baglanti is None:
        yield False
        return

    try:
        son_an = time.monotonic() + zaman_asimi
        while not baglanti.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": anahtar}).scalar():
            if time.monotonic() >= son_an:
                raise KilitZamanAsimiHatasi(f"'{ad}' kilidi {zaman_asimi:.0f} sn içinde alınamadı.")
            time.sleep(yoklama_saniye)
        try:
            yield True
        finally:
            try:
                baglanti.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": anahtar})
            except Exception as hata:
                _logger.warning("'%s' kilidi açıkça bırakılamadı (bağlantı kapanınca bırakılır): %s", ad, hata)
    finally:
        baglanti.close()


class LiderKilidi:
    """Süreç ömrü boyunca tutulan advisory lock (liderlik). dene() kilidi alır
    ya da tutulduğunu doğrular; bağlantı koparsa PostgreSQL kilidi bırakır ve
    dene() False döner, başka bir süreç devralabilir. Veritabanına ulaşılamazsa
    False (kapalı kalır): dış servise giden zamanlayıcılar çoğalmasın."""

    def __init__(self, ad: str, motor=None):
        self.ad = ad
        self._anahtar = kilit_anahtari(ad)
        self._motor = motor
        self._baglanti = None

    @property
    def lider_mi(self) -> bool:
        return self._baglanti is not None

    def _kapat(self):
        baglanti, self._baglanti = self._baglanti, None
        if baglanti is not None:
            try:
                baglanti.close()
            except Exception:
                pass

    def dene(self) -> bool:
        if self._baglanti is not None:
            try:
                self._baglanti.execute(text("SELECT 1"))
                return True
            except Exception as hata:
                _logger.warning("'%s' liderlik bağlantısı koptu, liderlik bırakıldı: %s", self.ad, hata)
                self._kapat()
        try:
            baglanti = (self._motor or _kilit_motoru()).connect()
        except Exception as hata:
            _logger.warning("'%s' liderlik kilidi için veritabanına bağlanılamadı: %s", self.ad, hata)
            return False
        try:
            alindi = baglanti.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": self._anahtar}).scalar()
        except Exception as hata:
            _logger.warning("'%s' liderlik kilidi denenemedi: %s", self.ad, hata)
            alindi = False
        if not alindi:
            baglanti.close()
            return False
        self._baglanti = baglanti
        return True

    def birak(self) -> None:
        if self._baglanti is not None:
            try:
                self._baglanti.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": self._anahtar})
            except Exception:
                pass
        self._kapat()
