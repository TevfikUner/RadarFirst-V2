"""API anahtarı, rol (yonetici/pilot) ve WebSocket bileti doğrulaması."""

import asyncio
import hashlib
import hmac
import os
import secrets
import time

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from fastapi import (
    Depends,
    Header,
    HTTPException,
    Request,
    status,
)

from turbulans_radar import loglama
from turbulans_radar.ayar_dogrulama import yalnizca_yerel_yayin_mi

_logger = loglama.logger_al(__name__)

_ROLLER = ("yonetici", "pilot")


def _anahtar_eslesiyor(verilen: str | None, beklenen: str | None) -> bool:
    # secrets.compare_digest: '==' kısa devre yaptığı için yanıt süresinden
    # anahtarın ilk kaç karakterinin tutturulduğu sızabilir (timing attack).
    # bytes: str ile compare_digest ASCII dışı karakterde TypeError atar
    # (başlık latin-1 çözülür, örn. 'é') -- 401 yerine 500 dönerdi.
    return bool(verilen and beklenen) and secrets.compare_digest(verilen.encode(), beklenen.encode())


def _tanimli_anahtarlar() -> list[tuple[str, str, str]]:
    """(kimlik, rol, anahtar) listesi. Biçimi bozuk API_ANAHTARLARI girdileri
    atlanır (açılışta bir kez uyarılır, bkz. _anahtar_ayarlarini_denetle)."""
    anahtarlar = []
    if yonetici := os.environ.get("API_ANAHTARI"):
        anahtarlar.append(("yonetici", "yonetici", yonetici))
    if pilot := os.environ.get("API_PILOT_ANAHTARI"):
        anahtarlar.append(("pilot", "pilot", pilot))
    for girdi in os.environ.get("API_ANAHTARLARI", "").split(","):
        if _gecerli_anahtar_girdisi(girdi):
            anahtarlar.append(tuple(p.strip() for p in girdi.split(":", 2)))
    return anahtarlar


def _anahtar_ayarlarini_denetle():
    gecersiz = [
        g for g in os.environ.get("API_ANAHTARLARI", "").split(",") if g.strip() and not _gecerli_anahtar_girdisi(g)
    ]
    if gecersiz:
        _logger.warning(
            "API_ANAHTARLARI'nda %d geçersiz girdi atlandı ('kimlik:rol:anahtar', rol: %s).", len(gecersiz), _ROLLER
        )
    if not _yalnizca_yerel_yayin_mi():
        _logger.warning(
            "API ağa açık (API_YAYIN_ADRESI=%s): TLS yok, anahtarlar düz HTTP'den gider -- "
            "güvenilmeyen ağda TLS sonlandıran bir ters vekil kullan (README 'Güvenlik').",
            os.environ["API_YAYIN_ADRESI"],
        )


def _gecerli_anahtar_girdisi(girdi: str) -> bool:
    parcalar = [p.strip() for p in girdi.split(":", 2)]
    return len(parcalar) == 3 and bool(parcalar[0]) and parcalar[1] in _ROLLER and bool(parcalar[2])


def _anahtari_coz(verilen: str | None) -> tuple[str, str] | None:
    """Eşleşen anahtarın (kimlik, rol) çifti. Sabit süre için TÜM anahtarlar
    karşılaştırılır (ilk eşleşmede dönülmez)."""
    bulunan = None
    for kimlik, rol, anahtar in _tanimli_anahtarlar():
        if _anahtar_eslesiyor(verilen, anahtar) and bulunan is None:
            bulunan = (kimlik, rol)
    return bulunan


def api_anahtarini_dogrula(request: Request, x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> str:
    """Anahtarın rolünü döner: 'yonetici' ya da 'pilot'. Kimlik denetim kaydı
    için request.state'e yazılır."""
    if not os.environ.get("API_ANAHTARI"):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Sunucuda API_ANAHTARI tanımlı değil -- '.env' dosyasına ekle.",
        )
    cozum = _anahtari_coz(x_api_key)
    if cozum is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Geçersiz veya eksik API anahtarı ('X-API-Key' başlığı gerekli).",
        )
    request.state.kimlik, request.state.rol = cozum
    return cozum[1]


def yonetici_gerekli(rol: str = Depends(api_anahtarini_dogrula)):
    if rol != "yonetici":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bu işlem yönetici anahtarı gerektirir; pilot anahtarı sadece okuma ve rota hesabı yapabilir.",
        )


_YONETICI = [Depends(yonetici_gerekli)]


_BILET_SURESI_SANIYE = 60


def _bilet_imzasi(govde: str) -> str:
    return hmac.new(os.environ["API_ANAHTARI"].encode(), govde.encode(), hashlib.sha256).hexdigest()


def ws_bileti_uret(rol: str, simdi: float | None = None) -> str:
    """WebSocket için kısa ömürlü, sunucu anahtarıyla imzalı, tek kullanımlık
    bilet: anahtarın kendisi URL'ye (proxy/erişim loglarına) yazılmasın diye.
    Rastgele ek, aynı saniyede üretilen biletlerin birbirinden ayrılmasını sağlar."""
    bitis = int((simdi if simdi is not None else time.time()) + _BILET_SURESI_SANIYE)
    govde = f"{bitis}.{rol}.{secrets.token_urlsafe(12)}"
    return f"{govde}.{_bilet_imzasi(govde)}"


def ws_bileti_gecerli_mi(bilet: str | None) -> bool:
    if not bilet or not os.environ.get("API_ANAHTARI"):
        return False
    parcalar = bilet.split(".")
    # isascii: '²'.isdigit() True ama int('²') ValueError atar.
    if len(parcalar) != 4 or not (parcalar[0].isascii() and parcalar[0].isdigit()):
        return False
    bitis, rol, ek, imza = parcalar
    beklenen = _bilet_imzasi(f"{bitis}.{rol}.{ek}")
    return secrets.compare_digest(imza.encode(), beklenen.encode()) and int(bitis) >= time.time()


async def ws_biletini_kullan(bilet: str | None) -> bool:
    """Geçerli ve daha önce kullanılmamışsa bileti tüketir. Kullanılmışlık PostgreSQL'de
    tutulur (P1-7): WEB_CONCURRENCY>1 iken de bilet yalnız bir kez kullanılır."""
    if not ws_bileti_gecerli_mi(bilet):
        return False
    from turbulans_radar.depo.hiz_siniri import ilk_kullanim_mi

    bitis, _, _, imza = bilet.split(".")
    return await asyncio.to_thread(ilk_kullanim_mi, f"wsbilet:{imza}", int(bitis))


def _yalnizca_yerel_yayin_mi() -> bool:
    return yalnizca_yerel_yayin_mi()
