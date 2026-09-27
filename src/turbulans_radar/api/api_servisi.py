"""
api_servisi.py
-----------------
Hava durumu eşleştirme sonuçlarını (Ellrod TI1, Richardson, EDR proxy) JSON
olarak dışarıya sunan FastAPI servis katmanı.

Güvenlik: /api/v1/* altındaki TÜM uç noktalar 'X-API-Key' başlığıyla
korunur (bkz. api_anahtarini_dogrula). Anahtar '.env'deki API_ANAHTARI
değişkeninden okunur -- kod içine yazılmaz. /saglik kasıtlı olarak açık
bırakıldı (yaygın pratik: yük dengeleyici/monitoring health-check'i).

Sürümleme: tüm veri/analiz uç noktaları /api/v1 altında (bkz. Kurumsal API
dokümantasyonu isteği) -- ileride /api/v2 eklenirse mevcut istemciler
bozulmaz. İnteraktif Swagger dokümantasyonu FastAPI'nin ürettiği /docs
adresinde otomatik olarak hazır.

Asenkron: okuma uç noktaları (GET) veritabani.py'nin asyncpg tabanlı async
fonksiyonlarını kullanır (event loop'u bloklamaz). Uzun işler (POST
/analiz/*, /backtest/toplu, /veri/canli/hazirla) API sürecinde ÇALIŞMAZ:
analiz_gorevleri kuyruğuna eklenip hemen 202 + gorev_id döner; işçiler
(isci/gorev_iscisi.py -- gömülü ya da ayrı süreç) eşzamanlılık sınırıyla
çalıştırır, API/işçi yeniden başlasa da görev kaybolmaz.

Otomasyon (n8n): /analiz/* uç noktaları isteğe bağlı bir
'bildirim_webhook_url' alanı kabul eder -- analiz bitince sonucu oraya POST
eder (n8n'in Webhook node'u). Bu, n8n'in /analiz/durum/{gorev_id}'yi
periyodik olarak yoklamasına (polling) gerek bırakmaz.

Canlı uyarılar: /ws/uyarilar WebSocket'i, bir analiz sırasında Ellrod TI1
"orta-şiddetli" eşiğini aşan nokta bulunduğunda bağlı istemcilere anlık
bildirim yayınlar. İşçi başka bir süreçte olabileceği için uyarı PostgreSQL
NOTIFY ile gelir (bkz. _uyari_dinleyicisi).

BİLİNÇLİ OLARAK EKLENMEDİ:
  - veri_indirme.py'nin GERÇEK ERA5 indirmesini tetikleyen bir uç nokta --
    o modül, OpenSky/Copernicus'u rate-limit/ban riskine sokmamak için
    kasıtlı olarak sadece elle, açık onayla (--gercekten-indir) çalışacak
    şekilde tasarlandı; bunu otomatikleştirmek o güvenlik kararını bozar.
  - JWT/OAuth2 tabanlı kullanıcı girişi -- tek kullanıcılı/dahili bir araç
    için statik API anahtarı yeterli; çok kullanıcılı bir sürüme geçilirse
    burası JWT'ye yükseltilebilir.

Çalıştırma:
    uvicorn turbulans_radar.api.api_servisi:app --reload --port 8000
"""

import asyncio
import hashlib
import hmac
import inspect
import json
import os
import secrets
import time
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

import asyncpg
import pandas as pd
from fastapi import (
    APIRouter,
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Path,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from turbulans_radar import config, loglama
from turbulans_radar.api.semalar import (
    BacktestListesiYaniti,
    BacktestSonucuYaniti,
    CanliVeriIstegi,
    EsiklerYaniti,
    GorevBaslatildiYaniti,
    GorevDurumYaniti,
    HavaDurumuKupuYaniti,
    KisitliSahaIceAktarmaYaniti,
    KisitliSahaYaniti,
    ModelBilgisiYaniti,
    ModelVersiyonuOzetiYaniti,
    RotaSimulasyonuIstegi,
    RotaSimulasyonuYaniti,
    SaglikYaniti,
    SigmetDogrulamaYaniti,
    SigmetOzetiYaniti,
    SigmetYenilemeYaniti,
    SistemDurumuYaniti,
    TopluSilmeYaniti,
    TurbulansTahminIstegi,
    TurbulansTahminYaniti,
    UcakProfiliYaniti,
    UcusDetayYaniti,
    UcuslarListesiYaniti,
    WsBiletiYaniti,
)
from turbulans_radar.cli.statik_indir import yerel_kutuphane_durumu
from turbulans_radar.depo.gorev_deposu import eski_gorevleri_temizle, gorev_getir, gorev_olustur, kuyruk_durumu
from turbulans_radar.depo.kaynak_durumu import kaynak_durumlarini_getir
from turbulans_radar.depo.kup_katalogu import katalogu_listele, yerel_kupleri_katalogla
from turbulans_radar.depo.veritabani import (
    VeritabaniAyarlariEksikHatasi,
    async_motor_al,
    asyncpg_baglanti_parametreleri,
    ucus_detayini_getir_async,
    ucus_olcumlerini_dataframe_olarak_getir,
    ucus_sil_async,
    ucuslari_listele_async,
    ucuslari_toplu_sil_async,
)
from turbulans_radar.dogrulama.rota_backtest import backtestleri_listele, ucus_backtest_et
from turbulans_radar.dogrulama.sigmet_dogrulama import ucus_sigmet_ile_karsilastir
from turbulans_radar.fizik.turbulans_indeksleri import TI1_GUVENILIRLIK_NOTU
from turbulans_radar.hata_yardimcisi import dostane_hata_mesaji
from turbulans_radar.isci.gorev_iscisi import BILDIRIM_KANALI, GorevIscisi
from turbulans_radar.ml.turbulans_ml_modeli import (
    model_bilgisini_yukle,
    model_versiyonlarini_listele,
    ozelliklerden_risk_tahmin_et,
    ozellikleri_cikar,
    versiyona_geri_don,
)
from turbulans_radar.rota.rota_optimizasyonu import (
    CANLI_VERI_HAZIRLANIYOR,
    UCAK_PROFILLERI,
    rota_simulasyonu_olustur,
    simulasyonu_czml_e_cevir,
    veri_kupune_eris,
)
from turbulans_radar.veri.fir_sinirlari import fir_verisi_var_mi
from turbulans_radar.veri.kisitli_saha_saglayici import (
    ORNEK_KAYNAK,
    gecerli_kisitli_sahalari_getir,
    geojson_ice_aktar,
    kisitli_sahayi_sil,
    ornek_veriyi_yukle,
)
from turbulans_radar.veri.sigmet_saglayici import (
    gecerli_sigmetleri_getir,
    kacinilacak_tehlikeler,
    kaynak_saglik_durumlari,
    sigmetleri_guncelle,
    son_guncelleme_zamani,
)
from turbulans_radar.veri.veri_saglayicilari import canli_durum_anahtari
from turbulans_radar.veri.veri_yukleme import hava_durumu_dosyalari, onbellek_durumu
from turbulans_radar.webhook import webhook_url_dogrula

loglama.ayarla()
_logger = loglama.logger_al(__name__)


@asynccontextmanager
async def _yasam_dongusu(uygulama):
    try:
        await asyncio.to_thread(yerel_kupleri_katalogla)
    except Exception as hata:
        _logger.warning("Yerel hava küpleri kataloğa kaydedilemedi: %s", dostane_hata_mesaji(hata))
    if config.KISITLI_SAHA_ORNEK_VERI_YUKLE:
        try:
            if sayi := await asyncio.to_thread(ornek_veriyi_yukle):
                _logger.warning("%d ÖRNEK kısıtlı hava sahası yüklendi (resmi veri değil).", sayi)
        except Exception as hata:
            _logger.warning("Örnek kısıtlı sahalar yüklenemedi: %s", dostane_hata_mesaji(hata))
    zamanlayici = None
    if config.SIGMET_OTOMATIK_GUNCELLEME_DAKIKA > 0:
        zamanlayici = asyncio.create_task(_sigmet_zamanlayicisi(config.SIGMET_OTOMATIK_GUNCELLEME_DAKIKA * 60))
    dinleyici = asyncio.create_task(_uyari_dinleyicisi())
    isci = GorevIscisi().baslat() if config.GOREV_GOMULU_ISCI else None
    yield
    for gorev in (zamanlayici, dinleyici):
        if gorev is not None:
            gorev.cancel()
    if isci is not None:
        await asyncio.to_thread(isci.durdur, 5.0)


async def _uyari_iletildi(baglanti, pid, kanal, yuk):
    await baglanti_yoneticisi.yayinla(json.loads(yuk))


async def _uyari_dinleyicisi(yeniden_deneme_saniye=30.0):
    """İşçilerin (gömülü ya da ayrı süreç) NOTIFY ile yayınladığı canlı
    uyarıları WebSocket istemcilerine iletir; bağlantı koparsa yeniden bağlanır."""
    while True:
        baglanti = None
        try:
            baglanti = await asyncpg.connect(**asyncpg_baglanti_parametreleri())
            await baglanti.add_listener(BILDIRIM_KANALI, _uyari_iletildi)
            while not baglanti.is_closed():
                await asyncio.sleep(5)
        except asyncio.CancelledError:
            if baglanti is not None:
                await baglanti.close()
            raise
        except Exception as hata:
            _logger.warning("Canlı uyarı dinleyicisi bağlanamadı: %s", dostane_hata_mesaji(hata))
        await asyncio.sleep(yeniden_deneme_saniye)


async def _sigmet_zamanlayicisi(aralik_saniye):
    """config.SIGMET_OTOMATIK_GUNCELLEME_DAKIKA > 0 ise API, n8n/cron'a gerek
    kalmadan AWC SIGMET'lerini kendi içinde periyodik olarak yeniler."""
    while True:
        try:
            ozet = await asyncio.to_thread(sigmetleri_guncelle)
            if ozet["kaynak_hatalari"]:
                _logger.error("SIGMET kaynak hataları (mevcut kayıtlar korundu): %s", ozet["kaynak_hatalari"])
            _logger.info("SIGMET'ler yenilendi: %s", ozet)
        except Exception as hata:
            _logger.warning("Periyodik SIGMET yenilemesi başarısız: %s", dostane_hata_mesaji(hata))
        await asyncio.sleep(aralik_saniye)


app = FastAPI(
    title="Türbülans Radar API",
    description="Ellrod TI1 + Richardson tabanlı türbülans eşleştirme sonuçlarını JSON olarak sunar.",
    version="1.0.0",
    lifespan=_yasam_dongusu,
)

# CORS: bir web/mobil istemcinin tarayıcıdan doğrudan bu API'ye istek
# atabilmesi için gereklidir (aksi halde tarayıcı Cross-Origin isteği
# engeller). Güvenli varsayılan: hiçbir kaynağa izin verilmez (ortam
# değişkeni verilmezse middleware hiç eklenmez); izin verilecek kaynaklar
# '.env'deki CORS_IZIN_VERILEN_KAYNAKLAR'a virgülle ayrılmış olarak yazılır.
_cors_kaynaklari = [k.strip() for k in os.environ.get("CORS_IZIN_VERILEN_KAYNAKLAR", "").split(",") if k.strip()]
if _cors_kaynaklari:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_kaynaklari,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# 3D/canlı harita önyüzü (bkz. web/harita3d.html) -- ayrı bir build aracı
# gerektirmeyen tek dosyalık bir MapLibre GL sayfası. API ile aynı origin'de
# sunulur ki fetch()/WebSocket çağrıları CORS'a takılmasın.
app.mount("/harita", StaticFiles(directory="web", html=True), name="harita")


# ---------------------------------------------------------------------------
# Güvenlik: iki rollü statik API anahtarı ('.env')
#   API_ANAHTARI       -> yönetici: her şey (n8n, operasyon).
#   API_PILOT_ANAHTARI -> pilot/EFB istemcisi (isteğe bağlı): okuma, rota
#                         simülasyonu, tahmin, canlı uyarılar. Silme, kısıtlı
#                         saha değişikliği, model aktifleştirme ve görev
#                         tetikleme 403 döner -- kokpitteki bir tabletten
#                         sızan anahtar güvenlik verisini değiştiremesin.
# ---------------------------------------------------------------------------


def _anahtar_eslesiyor(verilen: str | None, beklenen: str | None) -> bool:
    # secrets.compare_digest: '==' kısa devre yaptığı için yanıt süresinden
    # anahtarın ilk kaç karakterinin tutturulduğu sızabilir (timing attack).
    # bytes: str ile compare_digest ASCII dışı karakterde TypeError atar
    # (başlık latin-1 çözülür, örn. 'é') -- 401 yerine 500 dönerdi.
    return bool(verilen and beklenen) and secrets.compare_digest(verilen.encode(), beklenen.encode())


def api_anahtarini_dogrula(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> str:
    """Anahtarın rolünü döner: 'yonetici' ya da 'pilot'."""
    yonetici = os.environ.get("API_ANAHTARI")
    if not yonetici:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Sunucuda API_ANAHTARI tanımlı değil -- '.env' dosyasına ekle.",
        )
    if _anahtar_eslesiyor(x_api_key, yonetici):
        return "yonetici"
    if _anahtar_eslesiyor(x_api_key, os.environ.get("API_PILOT_ANAHTARI")):
        return "pilot"
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Geçersiz veya eksik API anahtarı ('X-API-Key' başlığı gerekli).",
    )


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
    """WebSocket için kısa ömürlü, sunucu anahtarıyla imzalı bilet: anahtarın
    kendisi URL'ye (proxy/erişim loglarına) yazılmasın diye."""
    govde = f"{int((simdi if simdi is not None else time.time()) + _BILET_SURESI_SANIYE)}.{rol}"
    return f"{govde}.{_bilet_imzasi(govde)}"


def ws_bileti_gecerli_mi(bilet: str | None) -> bool:
    if not bilet or not os.environ.get("API_ANAHTARI"):
        return False
    parcalar = bilet.split(".")
    # isascii: '²'.isdigit() True ama int('²') ValueError atar.
    if len(parcalar) != 3 or not (parcalar[0].isascii() and parcalar[0].isdigit()):
        return False
    bitis, rol, imza = parcalar
    beklenen = _bilet_imzasi(f"{bitis}.{rol}")
    return secrets.compare_digest(imza.encode(), beklenen.encode()) and int(bitis) >= time.time()


# ---------------------------------------------------------------------------
# Basit bellek-içi hız sınırlama (sadece analiz tetikleme uç noktaları için
# -- OpenSky'yi dış dünyadan gelen aşırı istekle yormamak amacıyla)
# ---------------------------------------------------------------------------

_ANALIZ_PENCERE_SANIYE = 60
_ANALIZ_PENCERE_BASINA_MAKS_ISTEK = 5
_analiz_istek_zamanlari: dict[str, list[float]] = {}


def _hiz_sinirini_kontrol_et(anahtar: str):
    simdi = time.monotonic()
    gecmis = [t for t in _analiz_istek_zamanlari.get(anahtar, []) if simdi - t < _ANALIZ_PENCERE_SANIYE]
    if len(gecmis) >= _ANALIZ_PENCERE_BASINA_MAKS_ISTEK:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Çok fazla analiz isteği ({_ANALIZ_PENCERE_BASINA_MAKS_ISTEK}/"
                f"{_ANALIZ_PENCERE_SANIYE}s). OpenSky'yi yormamak için lütfen bekle."
            ),
        )
    gecmis.append(simdi)
    _analiz_istek_zamanlari[anahtar] = gecmis


# ---------------------------------------------------------------------------
# Hata -> HTTP durum kodu eşlemesi
#
# ÖNEMLİ: 500/503 yanıtları istemciye ham exception mesajını (SQL, bağlantı
# dizesi, dosya yolu vb. içerebilir) DÖNMEZ -- sadece genel, güvenli bir
# mesaj döner. Tam ayrıntı (traceback dahil) sunucu tarafında (stderr)
# loglanır; işletmeni yapan kişi konsoldan/loglardan görebilir, dışarıdaki
# istemci göremez.
# ---------------------------------------------------------------------------


def _hatayi_sunucu_tarafinda_logla(hata: Exception, baglam: str = ""):
    # exc_info=hata: logging tam traceback'i kendisi formatlar (manuel
    # traceback.print_exception'a göre daha az kod, aynı sonuç) ve seviye/
    # zaman damgası gibi diğer log alanlarıyla tutarlı biçimlenir.
    _logger.error("Sunucu hatası%s", f" ({baglam})" if baglam else "", exc_info=hata)


@app.exception_handler(VeritabaniAyarlariEksikHatasi)
async def veritabani_ayar_hatasi_isle(request: Request, hata: VeritabaniAyarlariEksikHatasi):
    # Bu mesaj bilerek operatöre yönelik ve güvenli (sır içermiyor):
    # ".env eksik" gibi bir kurulum talimatı, dahili bir hata detayı değil.
    return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content={"detail": str(hata)})


@app.exception_handler(SQLAlchemyError)
async def veritabani_baglanti_hatasi_isle(request: Request, hata: SQLAlchemyError):
    _hatayi_sunucu_tarafinda_logla(hata, f"{request.method} {request.url.path}")
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": "Veritabanına şu anda ulaşılamıyor. Lütfen daha sonra tekrar dene."},
    )


@app.exception_handler(ValueError)
async def deger_hatasi_isle(request: Request, hata: ValueError):
    # ValueError burada neredeyse hep uygulamanın KENDİSİ tarafından, bilerek
    # ve güvenli bir mesajla fırlatılıyor (örn. "'ucuslar' listesi boş
    # olamaz") -- bu yüzden mesajı doğrudan göstermek güvenli.
    return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"detail": str(hata)})


@app.exception_handler(Exception)
async def genel_hata_isle(request: Request, hata: Exception):
    _hatayi_sunucu_tarafinda_logla(hata, f"{request.method} {request.url.path}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Sunucuda beklenmeyen bir hata oluştu. Sorun devam ederse yöneticiyle iletişime geç."},
    )


# ---------------------------------------------------------------------------
# WebSocket ile canlı türbülans uyarıları
# ---------------------------------------------------------------------------


class _BaglantiYoneticisi:
    def __init__(self):
        self.baglantilar: list[WebSocket] = []

    async def baglan(self, websocket: WebSocket):
        await websocket.accept()
        self.baglantilar.append(websocket)

    def ayril(self, websocket: WebSocket):
        if websocket in self.baglantilar:
            self.baglantilar.remove(websocket)

    async def yayinla(self, mesaj: dict):
        for websocket in list(self.baglantilar):
            try:
                await websocket.send_json(mesaj)
            except Exception:
                self.ayril(websocket)


baglanti_yoneticisi = _BaglantiYoneticisi()


@app.websocket("/ws/uyarilar")
async def uyarilar_websocket(websocket: WebSocket, bilet: str | None = None, api_key: str | None = None):
    """Kimlik: POST /api/v1/ws-bileti'den alınan 60 sn'lik bilet. Eski
    istemciler için ?api_key= hâlâ kabul edilir ama önerilmez (anahtar URL'de
    loglanır)."""
    yonetici = os.environ.get("API_ANAHTARI")
    anahtar_gecerli = _anahtar_eslesiyor(api_key, yonetici) or _anahtar_eslesiyor(
        api_key, os.environ.get("API_PILOT_ANAHTARI")
    )
    if not yonetici or not (ws_bileti_gecerli_mi(bilet) or anahtar_gecerli):
        await websocket.close(code=4401)
        return
    await baglanti_yoneticisi.baglan(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        baglanti_yoneticisi.ayril(websocket)


# ---------------------------------------------------------------------------
# /api/v1 -- API anahtarı gerektiren tüm veri/analiz uç noktaları
# ---------------------------------------------------------------------------

v1 = APIRouter(prefix="/api/v1", dependencies=[Depends(api_anahtarini_dogrula)])

# Uzun işler PostgreSQL kuyruğunda (bkz. gorev_deposu.py, isci/gorev_iscisi.py)
# -- API yeniden başlasa da /analiz/durum/{gorev_id} çalışmaya devam eder.


# OpenSky callsign'ları en fazla 8 karakter, harf/rakamdan oluşur (bkz.
# veri_yukleme.py'deki ljust(8) notu). Bu desen hem anlamsız girdiyi erkenden
# 422 ile reddeder hem de SQL enjeksiyonuna karşı ikinci bir savunma katmanı
# sağlar (birincil savunma: veri_yukleme.py artık parametreli sorgu kullanıyor).
_UCUS_NUMARASI_DESENI = r"^[A-Za-z0-9]{1,8}$"


def _tarihi_dogrula(deger: str) -> str:
    try:
        date.fromisoformat(deger)
    except ValueError:
        raise ValueError("tarih 'YYYY-MM-DD' formatında geçerli bir tarih olmalı.")
    return deger


def _webhook_url_dogrula(deger: str | None) -> str | None:
    """Bkz. webhook.py: biçim + izin listesi + iç ağ adresi kontrolü (SSRF)."""
    return webhook_url_dogrula(deger)


class UcusAnalizIstegi(BaseModel):
    ucus_numarasi: str = Field(pattern=_UCUS_NUMARASI_DESENI)
    tarih: str  # YYYY-MM-DD
    bildirim_webhook_url: str | None = None

    @field_validator("tarih")
    @classmethod
    def _tarih_gecerli_mi(cls, deger):
        return _tarihi_dogrula(deger)

    @field_validator("bildirim_webhook_url")
    @classmethod
    def _webhook_gecerli_mi(cls, deger):
        return _webhook_url_dogrula(deger)


class RotaNoktasiGirdisi(BaseModel):
    zaman: datetime
    enlem: float = Field(ge=-90, le=90)
    boylam: float = Field(ge=-180, le=180)
    irtifa_m: float | None = Field(default=None, ge=-500, le=20000, description="Geometrik irtifa (m); yoksa null")

    @field_validator("zaman")
    @classmethod
    def _utc_yap(cls, deger: datetime):
        return deger.replace(tzinfo=UTC) if deger.tzinfo is None else deger.astimezone(UTC)


class RotaAnalizIstegi(BaseModel):
    ucus_numarasi: str = Field(pattern=_UCUS_NUMARASI_DESENI)
    noktalar: list[RotaNoktasiGirdisi] = Field(min_length=2, max_length=config.MAKS_STATE_VECTOR_SATIRI)
    bildirim_webhook_url: str | None = None

    @field_validator("bildirim_webhook_url")
    @classmethod
    def _webhook_gecerli_mi(cls, deger):
        return _webhook_url_dogrula(deger)


class TopluAnalizIstegi(BaseModel):
    ucuslar: list[UcusAnalizIstegi] = Field(max_length=500)
    bildirim_webhook_url: str | None = None

    @field_validator("bildirim_webhook_url")
    @classmethod
    def _webhook_gecerli_mi(cls, deger):
        return _webhook_url_dogrula(deger)


@v1.post("/ws-bileti", response_model=WsBiletiYaniti, tags=["Sistem"])
async def ws_bileti(rol: str = Depends(api_anahtarini_dogrula)):
    """/ws/uyarilar?bilet=... için 60 sn geçerli bilet (yönetici ya da pilot)."""
    return {"bilet": ws_bileti_uret(rol), "gecerlilik_saniye": _BILET_SURESI_SANIYE}


@v1.get("/esikler", response_model=EsiklerYaniti, tags=["Eşikler"])
async def esikleri_getir():
    """web/harita3d.html gibi istemcilerin, renklendirme eşiklerini
    config.py ile bire bir aynı tutabilmesi için (sabitleri JS'e
    kopyalamak yerine tek kaynaktan okumak)."""
    return {
        "ti1_esik_hafif": config.TI1_ESIK_HAFIF,
        "ti1_esik_orta_siddetli": config.TI1_ESIK_ORTA_SIDDETLI,
    }


@v1.get("/simulasyon/ucak-profilleri", response_model=list[UcakProfiliYaniti], tags=["Simülasyon"])
async def ucak_profillerini_getir():
    """web/ucus_simulasyonu.html'in uçak modeli seçim listesini doldurmak
    içindir -- sabitler tek kaynaktan (rota_optimizasyonu.py) okunur."""
    return [
        {"kod": kod, "etiket": p["etiket"], "tas_ms": p["tas_ms"], "yakit_akisi_kg_saat": p["yakit_akisi_kg_saat"]}
        for kod, p in UCAK_PROFILLERI.items()
    ]


@v1.post("/simulasyon/rota", response_model=RotaSimulasyonuYaniti, tags=["Simülasyon"])
async def rota_simulasyonu(istek: RotaSimulasyonuIstegi):
    """
    Verilen başlangıç/bitiş/irtifa/tarih/uçak için iki rota üretir: büyük
    daire ("normal") ve ERA5 rüzgarına göre yanal kaydırılmış en hızlı aday
    ("optimize") -- bkz. rota_optimizasyonu.py (kapsam dışı bölge/tarih için
    dürüst geri düşüş davranışı dahil). Dış bir servise istek atmadığı için
    (sadece yerel NetCDF dosyasını okur) ayrı bir hız sınırlaması yok; event
    loop'u bloklamaması için hesaplama ayrı bir thread'de çalıştırılır.
    """
    sonuc = await asyncio.to_thread(
        rota_simulasyonu_olustur,
        istek.baslangic_enlem,
        istek.baslangic_boylam,
        istek.bitis_enlem,
        istek.bitis_boylam,
        istek.irtifa_ft,
        istek.zaman,
        istek.ucak_modeli,
        canli_bekleme_saniye=config.CANLI_VERI_BEKLEME_SANIYE,
    )
    sonuc["czml"] = simulasyonu_czml_e_cevir(sonuc)
    return sonuc


@v1.post("/turbulans/tahmin", response_model=TurbulansTahminYaniti, tags=["Türbülans Tahmini"])
async def turbulans_tahmini(istek: TurbulansTahminIstegi):
    """
    Tek bir nokta için HEM fizik tabanlı (Ellrod TI1) HEM gerçek IEM PIREP +
    ERA5 verisiyle eğitilmiş ML sınıflandırıcısının (bkz. turbulans_ml_
    modeli.py, ml_egitimi.py) tahminini karşılaştırmalı döner. ML modeli
    henüz eğitilip kaydedilmediyse (`turbulans_ml_modeli.joblib` yok)
    `ml_olasilik`/`ml_riski_var_mi` dürüstçe None döner -- uydurma bir
    tahmin üretilmez.
    """

    def _hesapla():
        irtifa_m = istek.irtifa_ft * 0.3048
        kapsam_disi_yaniti = {
            "kapsam_icinde_mi": False,
            "aciklama": (
                "Seçilen nokta/tarih/irtifa için kapsayan hava verisi yok: ne sunucudaki ERA5 küpleri "
                f"({len(hava_durumu_dosyalari())} dosya) ne de canlı GFS (şimdi -{config.CANLI_GECMIS_SAAT} sa / "
                f"+{config.CANLI_TAHMIN_UFKU_SAAT} sa) bu noktayı kapsıyor."
            ),
        }
        veri_durumu = {}
        veri_kupu = veri_kupune_eris(
            istek.enlem,
            istek.boylam,
            istek.zaman,
            irtifa_m,
            durum=veri_durumu,
            canli_bekleme_saniye=config.CANLI_VERI_BEKLEME_SANIYE,
        )
        if veri_kupu is None and veri_durumu.get("canli_hazirlaniyor"):
            return {"kapsam_icinde_mi": False, "aciklama": CANLI_VERI_HAZIRLANIYOR}
        if veri_kupu is None and veri_durumu.get("canli_hata"):
            return {"kapsam_icinde_mi": False, "aciklama": veri_durumu["canli_hata"]}
        if veri_kupu is None:
            return kapsam_disi_yaniti

        nokta_df = pd.DataFrame(
            {"zaman": [istek.zaman], "enlem": [istek.enlem], "boylam": [istek.boylam], "irtifa_m": [irtifa_m]}
        )
        ozellikler = ozellikleri_cikar(nokta_df, veri_kupu)
        ti1 = ozellikler["ti1_indeksi"].iloc[0]
        if pd.isna(ti1):
            return kapsam_disi_yaniti

        ml_sonuc = ozelliklerden_risk_tahmin_et(ozellikler)
        ml_olasilik = float(ml_sonuc[0]) if ml_sonuc is not None and not pd.isna(ml_sonuc[0]) else None

        return {
            "kapsam_icinde_mi": True,
            "ti1_indeksi": float(ti1),
            "ti1_riskli_mi": bool(ti1 >= config.TI1_ESIK_ORTA_SIDDETLI),
            "ti1_guvenilirlik_notu": TI1_GUVENILIRLIK_NOTU,
            "ml_riski_var_mi": (ml_olasilik >= 0.5) if ml_olasilik is not None else None,
            "ml_olasilik": ml_olasilik,
            "aciklama": (
                "Fizik (Ellrod TI1) ve ML tahminleri hesaplandı."
                if ml_olasilik is not None
                else "Fizik (Ellrod TI1) hesaplandı; ML modeli henüz eğitilmedi (bkz. ml_egitimi.py)."
            ),
        }

    return await asyncio.to_thread(_hesapla)


@v1.get("/turbulans/model-bilgisi", response_model=ModelBilgisiYaniti, tags=["Türbülans Tahmini"])
async def turbulans_model_bilgisi():
    """ml_egitimi.py'nin kaydettiği model metadata'sını (seçilen model,
    metrikler, özellik listesi, eğitim tarihi) döner. Model henüz
    eğitilmediyse (bkz. turbulans/tahmin'deki aynı ilke) uydurma bir bilgi
    üretmez, dürüstçe egitildi_mi=False döner."""
    bilgi = await asyncio.to_thread(model_bilgisini_yukle)
    if bilgi is None:
        return {"egitildi_mi": False}
    return {"egitildi_mi": True, **bilgi}


@v1.get("/turbulans/model-versiyonlari", response_model=list[ModelVersiyonuOzetiYaniti], tags=["Türbülans Tahmini"])
async def turbulans_model_versiyonlari():
    """ml_egitimi.py'nin her çalıştırmasında biriktirdiği TÜM model
    versiyonlarını (en yeni önce) döner -- hiç eğitim yapılmadıysa boş
    liste. Aktif olan (şu an /turbulans/tahmin'in kullandığı) versiyonu
    ayırt etmek için GET /turbulans/model-bilgisi'ndeki egitim_zamani ile
    karşılaştırılabilir."""
    return await asyncio.to_thread(model_versiyonlarini_listele)


@v1.post(
    "/turbulans/model-versiyonlari/{versiyon_id}/aktiflestir",
    dependencies=_YONETICI,
    response_model=ModelBilgisiYaniti,
    tags=["Türbülans Tahmini"],
)
async def turbulans_model_versiyonunu_aktiflestir(versiyon_id: str):
    """Geçmiş bir model versiyonunu, YENİDEN EĞİTİM GEREKMEDEN aktif model
    yapar (rollback) -- örn. yeni bir eğitim çalıştırması beklenenden kötü
    çıkarsa bir önceki versiyona dönmek için. Bilinmeyen bir versiyon_id
    404 döner."""
    _hiz_sinirini_kontrol_et("model_aktiflestir")
    try:
        aktif_bilgi = await asyncio.to_thread(versiyona_geri_don, versiyon_id)
    except ValueError as hata:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(hata)) from hata
    return {"egitildi_mi": True, **aktif_bilgi}


@v1.get("/ucuslar", response_model=UcuslarListesiYaniti, tags=["Uçuşlar"])
async def ucuslar_listesi(
    limit: int = Query(default=100, ge=1, le=500),
    ucus_numarasi_arama: str | None = Query(default=None, max_length=8, description="Uçuş numarasında kısmi arama"),
    baslangic_tarih: date | None = Query(default=None),
    bitis_tarih: date | None = Query(default=None),
):
    return await ucuslari_listele_async(
        limit=limit,
        ucus_numarasi_arama=ucus_numarasi_arama,
        baslangic_tarih=baslangic_tarih,
        bitis_tarih=bitis_tarih,
    )


@v1.delete("/ucuslar", dependencies=_YONETICI, response_model=TopluSilmeYaniti, tags=["Uçuşlar"])
async def ucuslari_toplu_sil(
    ucus_numarasi_arama: str | None = Query(default=None, max_length=8, description="Uçuş numarasında kısmi arama"),
    baslangic_tarih: date | None = Query(default=None),
    bitis_tarih: date | None = Query(default=None),
):
    """Filtreye uyan TÜM uçuşları (CASCADE ile ölçümleriyle) siler. En az
    bir filtre ZORUNLUDUR -- filtresiz bir çağrı, tüm veritabanını
    YANLIŞLIKLA boşaltabileceği için kasıtlı olarak 400 ile reddedilir
    (tek tek silme için bkz. DELETE /ucuslar/{ucus_numarasi}/{tarih})."""
    _hiz_sinirini_kontrol_et("silme")
    if not any([ucus_numarasi_arama, baslangic_tarih, bitis_tarih]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Toplu silme için en az bir filtre gerekli (ucus_numarasi_arama/baslangic_tarih/bitis_tarih).",
        )
    silinen_sayisi = await ucuslari_toplu_sil_async(
        ucus_numarasi_arama=ucus_numarasi_arama, baslangic_tarih=baslangic_tarih, bitis_tarih=bitis_tarih
    )
    return {"silinen_sayisi": silinen_sayisi}


@v1.get("/ucuslar/{ucus_numarasi}/{tarih}", response_model=UcusDetayYaniti, tags=["Uçuşlar"])
async def ucus_detayi(
    ucus_numarasi: str = Path(pattern=_UCUS_NUMARASI_DESENI),
    tarih: date = Path(...),
    olcum_limit: int = Query(default=1000, ge=1, le=5000),
    olcum_offset: int = Query(default=0, ge=0),
):
    detay = await ucus_detayini_getir_async(
        ucus_numarasi, tarih.isoformat(), olcum_limit=olcum_limit, olcum_offset=olcum_offset
    )
    if detay is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Uçuş bulunamadı. Önce POST /api/v1/analiz/ucus ile analiz tetikle.",
        )
    return detay


@v1.delete(
    "/ucuslar/{ucus_numarasi}/{tarih}", dependencies=_YONETICI, status_code=status.HTTP_204_NO_CONTENT, tags=["Uçuşlar"]
)
async def ucus_sil(
    ucus_numarasi: str = Path(pattern=_UCUS_NUMARASI_DESENI),
    tarih: date = Path(...),
):
    """Kayıtlı bir uçuşu (CASCADE ile edr_olcumleri dahil) siler. Aynı
    uçuş/tarih tekrar analiz edilmek istenirse zaten otomatik üzerine
    yazılır (bkz. ucus_ve_olcumleri_kaydet) -- bu uç nokta, bir daha analiz
    edilmeyecek kaydı veritabanından tamamen kaldırmak içindir."""
    _hiz_sinirini_kontrol_et("silme")
    silindi_mi = await ucus_sil_async(ucus_numarasi, tarih.isoformat())
    if not silindi_mi:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Uçuş bulunamadı.")


@v1.get("/ucuslar/{ucus_numarasi}/{tarih}/csv", tags=["Uçuşlar"])
async def ucus_csv_disa_aktar(
    ucus_numarasi: str = Path(pattern=_UCUS_NUMARASI_DESENI),
    tarih: date = Path(...),
):
    """Bir uçuşun TÜM ölçümlerini (JSON uç noktasındaki sayfalama/5000
    tavanı OLMADAN -- QGIS gibi harici araçlarda kullanmak için) CSV olarak
    indirir."""
    df = await asyncio.to_thread(ucus_olcumlerini_dataframe_olarak_getir, ucus_numarasi, tarih.isoformat())
    if df is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Uçuş bulunamadı. Önce POST /api/v1/analiz/ucus ile analiz tetikle.",
        )
    csv_metni = df.to_csv(index=False)
    dosya_adi = f"{ucus_numarasi}_{tarih.isoformat()}.csv"
    return Response(
        content=csv_metni,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{dosya_adi}"'},
    )


@v1.get("/ucuslar/{ucus_numarasi}/{tarih}/geojson", tags=["Uçuşlar"])
async def ucus_geojson_disa_aktar(
    ucus_numarasi: str = Path(pattern=_UCUS_NUMARASI_DESENI),
    tarih: date = Path(...),
):
    """Bir uçuşun TÜM ölçümlerini (sayfalama olmadan) bir GeoJSON
    FeatureCollection'ı olarak döner -- web/harita3d.html'in kendi
    içinde ürettiği nokta koleksiyonuyla AYNI şema, ama QGIS/geopandas gibi
    harici araçlarda doğrudan açılabilir bir dosya olarak."""
    df = await asyncio.to_thread(ucus_olcumlerini_dataframe_olarak_getir, ucus_numarasi, tarih.isoformat())
    if df is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Uçuş bulunamadı. Önce POST /api/v1/analiz/ucus ile analiz tetikle.",
        )

    def _geojson_ozelligi(kayit):
        boylam, enlem = kayit.pop("boylam"), kayit.pop("enlem")
        return {"type": "Feature", "geometry": {"type": "Point", "coordinates": [boylam, enlem]}, "properties": kayit}

    kayitlar = df.astype(object).where(df.notna(), None).to_dict(orient="records")
    koleksiyon = {"type": "FeatureCollection", "features": [_geojson_ozelligi(k) for k in kayitlar]}
    dosya_adi = f"{ucus_numarasi}_{tarih.isoformat()}.geojson"
    return Response(
        content=json.dumps(koleksiyon, default=str),
        media_type="application/geo+json",
        headers={"Content-Disposition": f'attachment; filename="{dosya_adi}"'},
    )


@v1.get("/ucuslar/{ucus_numarasi}/{tarih}/sigmet-dogrulama", response_model=SigmetDogrulamaYaniti, tags=["Uçuşlar"])
async def ucus_sigmet_dogrulamasi(
    ucus_numarasi: str = Path(pattern=_UCUS_NUMARASI_DESENI),
    tarih: date = Path(...),
):
    """Hesaplanan TI1 'orta-şiddetli' noktalarını gerçek AWC SIGMET
    uyarılarıyla karşılaştırır (bkz. sigmet_dogrulama.py). SADECE ABD hava
    sahası için gerçek bir örtüşme çıkar; başka bölgeler için boş/sıfır
    sonuç dönmesi beklenen, dürüst bir durumdur -- hata değildir."""
    df = await asyncio.to_thread(ucus_olcumlerini_dataframe_olarak_getir, ucus_numarasi, tarih.isoformat())
    if df is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Uçuş bulunamadı. Önce POST /api/v1/analiz/ucus ile analiz tetikle.",
        )
    return await asyncio.to_thread(ucus_sigmet_ile_karsilastir, df)


async def _gorev_olustur(tur, ucus_numarasi=None, tarih=None, parametreler=None, webhook_url=None):
    await eski_gorevleri_temizle()
    return await gorev_olustur(
        tur, ucus_numarasi=ucus_numarasi, tarih=tarih, parametreler=parametreler, bildirim_webhook_url=webhook_url
    )


def _kuyruga_alindi(gorev_id):
    return {"gorev_id": gorev_id, "durum": "kuyrukta"}


@v1.post(
    "/analiz/ucus",
    dependencies=_YONETICI,
    status_code=status.HTTP_202_ACCEPTED,
    response_model=GorevBaslatildiYaniti,
    tags=["Analiz"],
)
async def ucus_analizi_baslat(istek: UcusAnalizIstegi):
    _hiz_sinirini_kontrol_et("tek_ucus")
    gorev_id = await _gorev_olustur(
        "ucus", ucus_numarasi=istek.ucus_numarasi, tarih=istek.tarih, webhook_url=istek.bildirim_webhook_url
    )
    return _kuyruga_alindi(gorev_id)


@v1.post(
    "/analiz/rota",
    dependencies=_YONETICI,
    status_code=status.HTTP_202_ACCEPTED,
    response_model=GorevBaslatildiYaniti,
    tags=["Analiz"],
)
async def rota_analizi_baslat(istek: RotaAnalizIstegi):
    """
    OpenSky'a BAĞLANMADAN, dışarıdan alınmış bir ADS-B izini (başka bir
    izleme servisi, uçuş kayıt cihazı vb.) analiz eder: aynı eşleştirme,
    PostgreSQL kaydı, WebSocket uyarısı ve webhook akışı. OpenSky'ın tarayıcı
    tabanlı OAuth2 girişini gerektirmediği için sunucu/Docker ortamında da
    çalışır. Tarih, ilk noktanın UTC gününden türetilir; sonuç
    GET /ucuslar/{ucus_numarasi}/{tarih} ile okunur.
    """
    _hiz_sinirini_kontrol_et("rota")
    tarih = min(n.zaman for n in istek.noktalar).date().isoformat()
    gorev_id = await _gorev_olustur(
        "rota",
        ucus_numarasi=istek.ucus_numarasi,
        tarih=tarih,
        parametreler={"noktalar": [n.model_dump(mode="json") for n in istek.noktalar]},
        webhook_url=istek.bildirim_webhook_url,
    )
    return _kuyruga_alindi(gorev_id)


@v1.post(
    "/analiz/toplu",
    dependencies=_YONETICI,
    status_code=status.HTTP_202_ACCEPTED,
    response_model=GorevBaslatildiYaniti,
    tags=["Analiz"],
)
async def toplu_analiz_baslat(istek: TopluAnalizIstegi):
    _hiz_sinirini_kontrol_et("toplu")
    if not istek.ucuslar:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="'ucuslar' listesi boş olamaz.")
    gorev_id = await _gorev_olustur(
        "toplu",
        parametreler={"ucuslar": [u.model_dump(exclude={"bildirim_webhook_url"}) for u in istek.ucuslar]},
        webhook_url=istek.bildirim_webhook_url,
    )
    return _kuyruga_alindi(gorev_id)


@v1.get("/analiz/durum/{gorev_id}", response_model=GorevDurumYaniti, tags=["Analiz"])
async def analiz_durumu(gorev_id: str):
    """Kuyruktaki uzun işlerin (analiz, toplu analiz, backtest, canlı veri)
    durumu: kuyrukta -> calisiyor -> tamamlandi | basarisiz | hata |
    yarida_kaldi. Sonucu olan işlerde (toplu, backtest, canlı veri) sonuç
    'ozet' alanındadır."""
    gorev = await gorev_getir(gorev_id)
    if gorev is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bilinmeyen gorev_id.")
    return gorev


@v1.post("/sigmet/guncelle", dependencies=_YONETICI, response_model=SigmetYenilemeYaniti, tags=["SIGMET"])
async def sigmetleri_yenile():
    """AWC'den (aviationweather.gov: ABD `airsigmet` + uluslararası `isigmet`)
    canlı SIGMET'leri çekip veritabanını günceller; akıştan düşen (iptal
    edilen) SIGMET'lerin geçerliliği sona erdirilir. n8n/cron'un periyodik
    (örn. 10-15 dk) tetiklemesi için -- ya da SIGMET_OTOMATIK_GUNCELLEME_DAKIKA
    ile API'nin kendi zamanlayıcısı kullanılır."""
    _hiz_sinirini_kontrol_et("sigmet")
    return await asyncio.to_thread(sigmetleri_guncelle)


@v1.get("/sigmet", response_model=list[SigmetOzetiYaniti], tags=["SIGMET"])
async def aktif_sigmetleri_listele(
    tehlike: list[str] | None = Query(default=None, description="Örn. TURB, TS; verilmezse A*'ın kaçındığı set"),
    enlem_min: float = Query(default=-90, ge=-90, le=90),
    enlem_maks: float = Query(default=90, ge=-90, le=90),
    boylam_min: float = Query(default=-180, ge=-180, le=180),
    boylam_maks: float = Query(default=180, ge=-180, le=180),
):
    """ŞU AN geçerli SIGMET'ler (verilen kutuyla kesişenler) -- önyüzlerin
    haritada yasak bölgeleri çizmesi için."""
    simdi = datetime.now(UTC)
    return await asyncio.to_thread(
        gecerli_sigmetleri_getir,
        simdi,
        simdi,
        enlem_min,
        enlem_maks,
        boylam_min,
        boylam_maks,
        tehlike or kacinilacak_tehlikeler(),
    )


@v1.get("/kisitli-sahalar", response_model=list[KisitliSahaYaniti], tags=["Kısıtlı Hava Sahaları"])
async def kisitli_sahalari_listele(
    enlem_min: float = Query(default=-90, ge=-90, le=90),
    enlem_maks: float = Query(default=90, ge=-90, le=90),
    boylam_min: float = Query(default=-180, ge=-180, le=180),
    boylam_maks: float = Query(default=180, ge=-180, le=180),
):
    """ŞU AN geçerli (süresizler dahil) kısıtlı/yasak hava sahaları -- A*'ın
    SIGMET gibi sert kısıt olarak kaçındığı alanlar."""
    simdi = datetime.now(UTC)
    return await asyncio.to_thread(
        gecerli_kisitli_sahalari_getir, simdi, simdi, enlem_min, enlem_maks, boylam_min, boylam_maks
    )


@v1.post(
    "/kisitli-sahalar",
    dependencies=_YONETICI,
    response_model=KisitliSahaIceAktarmaYaniti,
    tags=["Kısıtlı Hava Sahaları"],
)
async def kisitli_sahalari_ice_aktar(
    geojson: dict,
    kaynak: str = Query(min_length=1, max_length=32, pattern=r"^[a-z0-9_\-]+$"),
    eskileri_kaldir: bool = Query(default=False, description="Bu kaynağın yeni veride olmayan kayıtlarını sil"),
):
    """GeoJSON FeatureCollection içe aktarır (Polygon/MultiPolygon; properties:
    kimlik, ad, tur, taban_ft, tavan_ft, baslangic, bitis, aciklama). Örn. n8n
    bir NOTAM akışından geçici kısıtları `kaynak=notam` ile iter. Aynı
    kaynak:kimlik ikinci kez gelirse güncellenir."""
    _hiz_sinirini_kontrol_et("kisitli_saha")
    return await asyncio.to_thread(geojson_ice_aktar, geojson, kaynak, eskileri_kaldir)


@v1.post(
    "/kisitli-sahalar/openaip",
    dependencies=_YONETICI,
    status_code=status.HTTP_202_ACCEPTED,
    response_model=GorevBaslatildiYaniti,
    tags=["Kısıtlı Hava Sahaları"],
)
async def openaip_sahalarini_yenile(ulke: list[str] | None = Query(default=None, description="ISO ülke kodu(ları)")):
    """Gerçek kısıtlı/yasak sahaları openAIP'ten çekip 'openaip' kaynağını tam
    yeniler (OPENAIP_API_ANAHTARI gerekir; AIRAC döngüsünde n8n tetikleyebilir).
    Kuyruğa girer; sonuç GET /analiz/durum/{gorev_id}."""
    _hiz_sinirini_kontrol_et("kisitli_saha")
    return _kuyruga_alindi(await _gorev_olustur("openaip", parametreler={"ulkeler": ulke}))


@v1.delete(
    "/kisitli-sahalar/{dis_kimlik}",
    dependencies=_YONETICI,
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Kısıtlı Hava Sahaları"],
)
async def kisitli_saha_sil(dis_kimlik: str = Path(max_length=128)):
    _hiz_sinirini_kontrol_et("kisitli_saha")
    if not await asyncio.to_thread(kisitli_sahayi_sil, dis_kimlik):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kısıtlı saha bulunamadı.")


_CANLI_VERI_MAKS_KUTU_DERECE = (40.0, 60.0)


@v1.get("/veri/kupler", response_model=list[HavaDurumuKupuYaniti], tags=["Veri Sağlayıcı"])
async def hava_durumu_kupleri(limit: int = Query(default=50, ge=1, le=500)):
    """Veri sağlayıcıların indirip kataloğa kaydettiği küpler (en yeni önce)."""
    kupler = await asyncio.to_thread(katalogu_listele, limit)
    return [{**k, "dosya_adi": os.path.basename(k["dosya_yolu"])} for k in kupler]


@v1.post(
    "/veri/canli/hazirla",
    dependencies=_YONETICI,
    status_code=status.HTTP_202_ACCEPTED,
    response_model=GorevBaslatildiYaniti,
    tags=["Veri Sağlayıcı"],
)
async def canli_veri_hazirla(istek: CanliVeriIstegi):
    """Verilen bölge/zaman için canlı NOAA GFS küpünü arka planda hazırlar
    (katalogda taze bir küp varsa onu kullanır, yoksa indirir). Yavaş ağda
    indirme dakikalar sürebildiği için istek beklemez: 202 + gorev_id döner,
    küp özeti GET /analiz/durum/{gorev_id} yanıtının 'ozet' alanındadır."""
    _hiz_sinirini_kontrol_et("canli_veri")
    if istek.enlem_min >= istek.enlem_maks or istek.boylam_min >= istek.boylam_maks:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Kutu sınırları geçersiz (min < maks olmalı).")
    enlem_genisligi, boylam_genisligi = istek.enlem_maks - istek.enlem_min, istek.boylam_maks - istek.boylam_min
    if enlem_genisligi > _CANLI_VERI_MAKS_KUTU_DERECE[0] or boylam_genisligi > _CANLI_VERI_MAKS_KUTU_DERECE[1]:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Kutu en fazla {_CANLI_VERI_MAKS_KUTU_DERECE[0]:.0f}° x {_CANLI_VERI_MAKS_KUTU_DERECE[1]:.0f}° olabilir.",
        )
    try:
        webhook = _webhook_url_dogrula(istek.bildirim_webhook_url)
    except ValueError as hata:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(hata)) from hata
    baslangic = istek.baslangic or datetime.now(UTC)
    gorev_id = await _gorev_olustur(
        "canli_veri",
        parametreler={
            "kutu": [istek.enlem_min, istek.enlem_maks, istek.boylam_min, istek.boylam_maks],
            "baslangic": baslangic.isoformat(),
            "saat_sayisi": istek.saat_sayisi,
        },
        webhook_url=webhook,
    )
    return _kuyruga_alindi(gorev_id)


@v1.post(
    "/backtest/ucuslar/{ucus_numarasi}/{tarih}",
    dependencies=_YONETICI,
    response_model=BacktestSonucuYaniti,
    tags=["Backtest"],
)
async def ucus_backtesti(
    ucus_numarasi: str = Path(pattern=_UCUS_NUMARASI_DESENI),
    tarih: date = Path(...),
):
    """Analiz edilmiş bir uçuşun gerçek izini, aynı giriş/çıkış noktaları için
    büyük daire ve A* rotasıyla AYNI ölçütle karşılaştırır (bkz. rota_backtest.py)
    ve sonucu kaydeder. Hava küpü seyir bölümünü kapsamıyorsa 400."""
    return await asyncio.to_thread(ucus_backtest_et, ucus_numarasi, tarih.isoformat())


@v1.post(
    "/backtest/toplu",
    dependencies=_YONETICI,
    status_code=status.HTTP_202_ACCEPTED,
    response_model=GorevBaslatildiYaniti,
    tags=["Backtest"],
)
async def toplu_backtest_baslat(
    limit: int = Query(default=20, ge=1, le=200),
    bildirim_webhook_url: str | None = Query(default=None),
):
    """Henüz backtest'i olmayan uçuşları arka planda karşılaştırır (örn. n8n'in
    gece tetiklemesi); sonuç /analiz/durum/{gorev_id} ve webhook ile alınır."""
    _hiz_sinirini_kontrol_et("backtest")
    try:
        webhook = _webhook_url_dogrula(bildirim_webhook_url)
    except ValueError as hata:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(hata)) from hata
    gorev_id = await _gorev_olustur("backtest", parametreler={"limit": limit}, webhook_url=webhook)
    return _kuyruga_alindi(gorev_id)


@v1.get("/backtest", response_model=BacktestListesiYaniti, tags=["Backtest"])
async def backtest_sonuclari():
    """Tüm backtest sonuçları + filo geneli özet (A*'ın gerçek uçuşlara göre
    ortalama riskli nokta oranı, riskin azaltıldığı uçuş oranı, ek mesafe/süre)."""
    return await asyncio.to_thread(backtestleri_listele)


app.include_router(v1)


# ---------------------------------------------------------------------------
# Sağlık / izleme
# ---------------------------------------------------------------------------

_SAGLIKSIZ_DURUMLAR = {"bayat", "hata", "birikiyor"}
_UYARI_DURUMLARI = {"cdn_yedegi", "ornek_veri", "veri_yok"}
_KUYRUK_BIRIKME_ESIGI_SANIYE = 120
_AYRINTI_ALANLARI = ("son_hata", "kaynaklar")


def _sigmet_kontrolu():
    durumlar = kaynak_saglik_durumlari()
    son = son_guncelleme_zamani()
    yas_dakika = (datetime.now(UTC) - son).total_seconds() / 60 if son else None
    hatali = [d for d in durumlar if d.get("ardisik_hata_sayisi")]
    if hatali:
        durum = "hata"
    elif yas_dakika is None or yas_dakika > config.SIGMET_BAYATLIK_DAKIKA:
        durum = "bayat"
    else:
        durum = "tamam"
    return {
        "durum": durum,
        "son_basarili_guncelleme": son,
        "yas_dakika": round(yas_dakika, 1) if yas_dakika is not None else None,
        "otomatik_guncelleme_dakika": config.SIGMET_OTOMATIK_GUNCELLEME_DAKIKA,
        "kaynaklar": {
            d["kaynak"]: {k: d.get(k) for k in ("son_basari_zamani", "ardisik_hata_sayisi", "son_hata")}
            for d in durumlar
        },
    }


def _canli_gfs_kontrolu():
    if not config.CANLI_HAVA_VERISI_ETKIN:
        return {"durum": "kapali"}
    kayitlar = kaynak_durumlarini_getir([canli_durum_anahtari("gfs")])
    if not kayitlar:
        return {"durum": "kullanilmadi"}
    kayit = kayitlar[0]
    return {
        "durum": "hata" if kayit["ardisik_hata_sayisi"] else "tamam",
        "son_basarili_indirme": kayit["son_basari_zamani"],
        "son_deneme": kayit["son_deneme_zamani"],
        "ardisik_hata_sayisi": kayit["ardisik_hata_sayisi"],
        "son_hata": kayit["son_hata"],
    }


def _kisitli_saha_kontrolu():
    simdi = datetime.now(UTC)
    sahalar = gecerli_kisitli_sahalari_getir(simdi, simdi)
    ornek = sum(s["kaynak"] == ORNEK_KAYNAK for s in sahalar)
    durum = "veri_yok" if not sahalar else ("ornek_veri" if ornek == len(sahalar) else "tamam")
    return {"durum": durum, "aktif_saha_sayisi": len(sahalar), "ornek_saha_sayisi": ornek}


async def _gorev_kuyrugu_kontrolu():
    kuyruk = await kuyruk_durumu()
    birikiyor = kuyruk["kuyrukta"] > 0 and (kuyruk["en_eski_bekleme_saniye"] or 0) > _KUYRUK_BIRIKME_ESIGI_SANIYE
    return {"durum": "birikiyor" if birikiyor else "tamam", **kuyruk, "gomulu_isci": config.GOREV_GOMULU_ISCI}


async def _kontrol_et(kontrol):
    try:
        return await kontrol() if inspect.iscoroutinefunction(kontrol) else await asyncio.to_thread(kontrol)
    except Exception as hata:
        _logger.warning("Sağlık kontrolü başarısız (%s): %s", kontrol.__name__, dostane_hata_mesaji(hata))
        return {"durum": "hata", "son_hata": dostane_hata_mesaji(hata)}


async def _saglik_raporu(ayrintili: bool) -> dict:
    """EFB'nin güvendiği her dış bağımlılığın durumu. Operasyonel sorunlar
    (bayat SIGMET, veri kaynağı hatası, biriken kuyruk) genel durumu 'bozulmus'
    yapar; yapılandırma eksikleri (CDN'e düşen kütüphaneler, sadece örnek
    kısıtlı saha) 'uyarilar'da listelenir. Ham hata metinleri sadece ayrıntılı
    (API anahtarlı) raporda yer alır."""
    kontroller = {
        "sigmet": await _kontrol_et(_sigmet_kontrolu),
        "canli_gfs": await _kontrol_et(_canli_gfs_kontrolu),
        "gorev_kuyrugu": await _kontrol_et(_gorev_kuyrugu_kontrolu),
        "kisitli_sahalar": await _kontrol_et(_kisitli_saha_kontrolu),
        "kup_onbellegi": {"durum": "tamam", **onbellek_durumu()},
        "statik_dosyalar": yerel_kutuphane_durumu(),
        "fir_sinirlari": {"durum": "tamam" if await asyncio.to_thread(fir_verisi_var_mi) else "veri_yok"},
    }
    if not ayrintili:
        kontroller = {ad: {k: v for k, v in k_.items() if k not in _AYRINTI_ALANLARI} for ad, k_ in kontroller.items()}
    return {
        "durum": "bozulmus" if any(k["durum"] in _SAGLIKSIZ_DURUMLAR for k in kontroller.values()) else "ayakta",
        "veritabani": "erisilebilir",
        "kontroller": kontroller,
        "uyarilar": [f"{ad}: {k['durum']}" for ad, k in kontroller.items() if k["durum"] in _UYARI_DURUMLARI],
    }


async def _veritabani_erisilebilir_mi() -> bool:
    try:
        async with async_motor_al().connect() as baglanti:
            await baglanti.execute(text("SELECT 1"))
        return True
    except Exception as hata:
        _logger.warning("Derin sağlık kontrolünde PostgreSQL'e erişilemedi: %s", dostane_hata_mesaji(hata))
        return False


@v1.get("/sistem/durum", dependencies=_YONETICI, response_model=SistemDurumuYaniti, tags=["Sistem"])
async def sistem_durumu():
    """/saglik?derin=true ile aynı rapor, ek olarak kaynak başına son hata
    metinleriyle (API anahtarı gerektirir -- dış servis hata ayrıntıları
    herkese açık uçta gösterilmez)."""
    if not await _veritabani_erisilebilir_mi():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Veritabanına şu anda ulaşılamıyor.")
    return await _saglik_raporu(ayrintili=True)


@app.get("/saglik", response_model=SaglikYaniti, tags=["Sistem"])
async def saglik_kontrolu(
    derin: bool = Query(default=False, description="True ise veritabanı ve tüm dış bağımlılıklar kontrol edilir"),
):
    """Kasıtlı olarak API anahtarı gerektirmez (yaygın health-check pratiği).
    Varsayılan (sığ) davranış sadece süreç ayakta mı diye bakar, her yük
    dengeleyici probunda PostgreSQL'e gitmez. `?derin=true`: PostgreSQL
    (erişilemezse 503) + SIGMET tazeliği, canlı GFS, görev kuyruğu,
    kısıtlı sahalar, küp önbelleği ve yerel kütüphaneler; operasyonel bir
    sorun varsa durum 'bozulmus' olur (HTTP 200, monitoring gövdeye bakar)."""
    if not derin:
        return {"durum": "ayakta"}
    if not await _veritabani_erisilebilir_mi():
        return JSONResponse(status_code=503, content={"durum": "ayakta", "veritabani": "erisilemiyor"})
    return await _saglik_raporu(ayrintili=False)
