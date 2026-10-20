"""Router'ların paylaştığı yardımcılar: hız sınırı, ağır hesap yuvası, girdi doğrulama, görev kuyruğu."""

import asyncio
import time
import weakref
from contextlib import asynccontextmanager
from datetime import date

from fastapi import (
    HTTPException,
    Request,
    status,
)
from sqlalchemy.exc import SQLAlchemyError

from turbulans_radar import config, loglama
from turbulans_radar.api import metrikler
from turbulans_radar.api.rota_onbellegi import PaylasimliRotaOnbellegi, RotaOnbellegi
from turbulans_radar.api.semalar import (
    RotaSimulasyonuYaniti,
)
from turbulans_radar.depo.gorev_deposu import (
    eski_gorevleri_temizle,
    gorev_olustur,
)
from turbulans_radar.depo.hiz_siniri import istegi_say
from turbulans_radar.depo.veritabani import (
    VeritabaniAyarlariEksikHatasi,
)
from turbulans_radar.hata_yardimcisi import dostane_hata_mesaji
from turbulans_radar.ucus_kurallari import UCUS_NUMARASI_DESENI
from turbulans_radar.webhook import webhook_url_dogrula

_logger = loglama.logger_al(__name__)

_ANALIZ_PENCERE_SANIYE = 60


_ANALIZ_PENCERE_BASINA_MAKS_ISTEK = 5


_yerel_sayaclar: dict[tuple[str, int], tuple[int, int]] = {}


def _yerel_istegi_say(anahtar: str, pencere_saniye: int) -> int:
    """Veritabanı yokken yedek sabit pencere sayacı (süreç başına)."""
    simdi = int(time.time())
    for (k, sure), (p, _) in list(_yerel_sayaclar.items()):
        if p != simdi // sure:
            del _yerel_sayaclar[(k, sure)]
    _, sayi = _yerel_sayaclar.get((anahtar, pencere_saniye), (0, 0))
    _yerel_sayaclar[(anahtar, pencere_saniye)] = (simdi // pencere_saniye, sayi + 1)
    return sayi + 1


async def _hiz_sinirini_kontrol_et(
    anahtar: str, maks: int = _ANALIZ_PENCERE_BASINA_MAKS_ISTEK, pencere_saniye: int = _ANALIZ_PENCERE_SANIYE
):
    """Sayaç PostgreSQL'de (bkz. depo/hiz_siniri.py): tüm API süreçleri aynı
    sınırı paylaşır. Veritabanına ulaşılamazsa istek reddedilmez, sayaç süreç
    belleğine düşer: rota hesabı gibi uçlar veritabanı olmadan da çalışabildiği
    için sayaç arızası pilotun rota almasını engellememeli, ama sınır da kalkmamalı."""
    try:
        sayi = await istegi_say(anahtar, pencere_saniye)
    except (SQLAlchemyError, OSError, VeritabaniAyarlariEksikHatasi) as hata:
        _logger.warning(
            "Hız sınırı sayacına ulaşılamadı, süreç içi sayaç kullanılıyor (%s): %s", anahtar, dostane_hata_mesaji(hata)
        )
        sayi = _yerel_istegi_say(anahtar, pencere_saniye)
    if sayi > maks:
        metrikler.HIZ_SINIRI_REDDI.labels(anahtar.split(":", 1)[0]).inc()
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Çok fazla istek ({maks}/{pencere_saniye}s). Lütfen biraz bekleyip tekrar dene.",
            headers={"Retry-After": str(pencere_saniye)},
        )


def _istemci_kimligi(request: Request, rol: str) -> str:
    """Pilot uçlarında sınır rol + istemci IP'si başınadır: aynı pilot anahtarını
    paylaşan tabletlerden biri diğerlerinin kotasını tüketemesin. Ters vekil
    arkasında gerçek IP için uvicorn --proxy-headers/--forwarded-allow-ips."""
    return f"{rol}:{request.client.host if request.client else '?'}"


_agir_hesap_semaforlari: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Semaphore]" = (
    weakref.WeakKeyDictionary()
)


@asynccontextmanager
async def _agir_hesap_yuvasi():
    """A*/tahmin gibi CPU ağır hesaplar için süreç başına eşzamanlılık tavanı
    (config.AGIR_HESAP_MAKS_ESZAMANLI). Tavan doluysa istek süresiz kuyrukta
    beklemez: AGIR_HESAP_BEKLEME_SANIYE sonra 503 + Retry-After döner.
    Semafor olay döngüsü başına tutulur (asyncio nesneleri döngüye bağlanır)."""
    dongu = asyncio.get_running_loop()
    semafor = _agir_hesap_semaforlari.get(dongu)
    if semafor is None:
        semafor = _agir_hesap_semaforlari[dongu] = asyncio.Semaphore(config.AGIR_HESAP_MAKS_ESZAMANLI)
    try:
        await asyncio.wait_for(semafor.acquire(), timeout=config.AGIR_HESAP_BEKLEME_SANIYE)
    except TimeoutError:
        metrikler.AGIR_HESAP_REDDI.inc()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Sunucu şu an çok sayıda rota/tahmin hesaplıyor. Birkaç saniye sonra tekrar dene.",
            headers={"Retry-After": "5"},
        ) from None
    try:
        yield
    finally:
        semafor.release()


# OpenSky callsign'ları en fazla 8 karakter, harf/rakamdan oluşur (bkz.
# veri_yukleme.py'deki ljust(8) notu). Bu desen hem anlamsız girdiyi erkenden
# 422 ile reddeder hem de SQL enjeksiyonuna karşı ikinci bir savunma katmanı
# sağlar (birincil savunma: veri_yukleme.py artık parametreli sorgu kullanıyor).
_UCUS_NUMARASI_DESENI = UCUS_NUMARASI_DESENI


def _tarihi_dogrula(deger: str) -> str:
    try:
        date.fromisoformat(deger)
    except ValueError:
        raise ValueError("tarih 'YYYY-MM-DD' formatında geçerli bir tarih olmalı.") from None
    return deger


def _webhook_url_dogrula(deger: str | None) -> str | None:
    """Bkz. webhook.py: biçim + izin listesi + iç ağ adresi kontrolü (SSRF)."""
    return webhook_url_dogrula(deger)


async def _gorev_olustur(tur, ucus_numarasi=None, tarih=None, parametreler=None, webhook_url=None):
    await eski_gorevleri_temizle()
    return await gorev_olustur(
        tur, ucus_numarasi=ucus_numarasi, tarih=tarih, parametreler=parametreler, bildirim_webhook_url=webhook_url
    )


def _kuyruga_alindi(gorev_id):
    return {"gorev_id": gorev_id, "durum": "kuyrukta"}


_rota_onbellegi = RotaOnbellegi(config.ROTA_ONBELLEK_SANIYE, config.ROTA_ONBELLEK_MAKS_KAYIT)


_paylasimli_rota_onbellegi = (
    PaylasimliRotaOnbellegi(config.ROTA_ONBELLEK_SANIYE, config.ROTA_ONBELLEK_MAKS_KAYIT)
    if config.ROTA_ONBELLEK_PAYLASIMLI
    else None
)


async def _rota_onbellegini_temizle():
    _rota_onbellegi.temizle()
    if _paylasimli_rota_onbellegi is not None:
        try:
            await _paylasimli_rota_onbellegi.temizle()
        except Exception as hata:
            _logger.warning("Paylaşılan rota önbelleği temizlenemedi: %s", dostane_hata_mesaji(hata))


async def _rota_onbellekten_al(anahtar):
    """(sonuc ya da None, damga). Paylaşılan önbellek okunamazsa iska sayılır."""
    if _paylasimli_rota_onbellegi is None:
        return _rota_onbellegi.al(anahtar), _rota_onbellegi.nesil
    try:
        return await _paylasimli_rota_onbellegi.al(anahtar)
    except Exception as hata:
        _logger.warning("Paylaşılan rota önbelleği okunamadı: %s", dostane_hata_mesaji(hata))
        return None, None


async def _rota_onbellege_koy(anahtar, sonuc, damga):
    if _paylasimli_rota_onbellegi is None:
        _rota_onbellegi.koy(anahtar, sonuc, damga)
        return
    try:
        await _paylasimli_rota_onbellegi.koy(
            anahtar, RotaSimulasyonuYaniti.model_validate(sonuc).model_dump(mode="json"), damga
        )
    except Exception as hata:
        _logger.warning("Paylaşılan rota önbelleğine yazılamadı: %s", dostane_hata_mesaji(hata))
