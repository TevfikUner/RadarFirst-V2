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
fonksiyonlarını kullanır (event loop'u bloklamaz). Analiz tetikleme uç
noktaları (POST /analiz/*), main.py/toplu_analiz.py'deki AYNI (senkron,
bloklayan) mantığı `asyncio.to_thread` ile ayrı bir thread'de çalıştırır --
event loop'u bloklamadan, main.py'yi yeniden yazmaya gerek kalmadan.

Otomasyon (n8n): /analiz/* uç noktaları isteğe bağlı bir
'bildirim_webhook_url' alanı kabul eder -- analiz bitince sonucu oraya POST
eder (n8n'in Webhook node'u). Bu, n8n'in /analiz/durum/{gorev_id}'yi
periyodik olarak yoklamasına (polling) gerek bırakmaz.

Canlı uyarılar: /ws/uyarilar WebSocket'i, bir analiz sırasında Ellrod TI1
"orta-şiddetli" eşiğini aşan nokta bulunduğunda bağlı istemcilere anlık
bildirim yayınlar (örn. ileride bir mobil/masaüstü istemci bunu dinleyebilir).

BİLİNÇLİ OLARAK EKLENMEDİ:
  - veri_indirme.py'nin GERÇEK ERA5 indirmesini tetikleyen bir uç nokta --
    o modül, OpenSky/Copernicus'u rate-limit/ban riskine sokmamak için
    kasıtlı olarak sadece elle, açık onayla (--gercekten-indir) çalışacak
    şekilde tasarlandı; bunu otomatikleştirmek o güvenlik kararını bozar.
  - JWT/OAuth2 tabanlı kullanıcı girişi -- tek kullanıcılı/dahili bir araç
    için statik API anahtarı yeterli; çok kullanıcılı bir sürüme geçilirse
    burası JWT'ye yükseltilebilir.

Çalıştırma:
    uvicorn api_servisi:app --reload --port 8000
"""

import asyncio
import os
import secrets
import time
import uuid
from datetime import date

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

import httpx
import pandas as pd
from fastapi import (
    APIRouter,
    BackgroundTasks,
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
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.exc import SQLAlchemyError

import config
import loglama
from hata_yardimcisi import dostane_hata_mesaji
from main import calistir as tek_ucus_analiz_et
from semalar import (
    EsiklerYaniti,
    GorevBaslatildiYaniti,
    GorevDurumYaniti,
    SaglikYaniti,
    SigmetDogrulamaYaniti,
    UcusDetayYaniti,
    UcusYaniti,
)
from sigmet_dogrulama import ucus_sigmet_ile_karsilastir
from toplu_analiz import toplu_analiz_calistir
from veritabani import (
    VeritabaniAyarlariEksikHatasi,
    ucus_detayini_getir_async,
    ucus_olcumlerini_dataframe_olarak_getir,
    ucuslari_listele_async,
)

loglama.ayarla()
_logger = loglama.logger_al(__name__)

app = FastAPI(
    title="Türbülans Radar API",
    description="Ellrod TI1 + Richardson tabanlı türbülans eşleştirme sonuçlarını JSON olarak sunar.",
    version="1.0.0",
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
# Güvenlik: statik API anahtarı ('.env' -> API_ANAHTARI)
# ---------------------------------------------------------------------------


def api_anahtarini_dogrula(x_api_key: str | None = Header(default=None, alias="X-API-Key")):
    beklenen = os.environ.get("API_ANAHTARI")
    if not beklenen:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Sunucuda API_ANAHTARI tanımlı değil -- '.env' dosyasına ekle.",
        )
    # secrets.compare_digest: '==' karakter karakter kısa devre yaptığı için
    # yanıt süresinden doğru anahtarın ilk kaç karakterinin tutturulduğunu
    # sızdırabilir (timing attack); sabit zamanlı karşılaştırma bunu önler.
    if not x_api_key or not secrets.compare_digest(x_api_key, beklenen):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Geçersiz veya eksik API anahtarı ('X-API-Key' başlığı gerekli).",
        )


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
async def uyarilar_websocket(websocket: WebSocket, api_key: str | None = None):
    beklenen = os.environ.get("API_ANAHTARI")
    if beklenen and (not api_key or not secrets.compare_digest(api_key, beklenen)):
        await websocket.close(code=4401)
        return
    await baglanti_yoneticisi.baglan(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        baglanti_yoneticisi.ayril(websocket)


async def _yuksek_riskli_noktalari_yayinla(eslesmis_df, ucus_numarasi, tarih):
    if eslesmis_df is None or eslesmis_df.empty or "ti1_indeksi" not in eslesmis_df.columns:
        return
    riskli = eslesmis_df[eslesmis_df["ti1_indeksi"] >= config.TI1_ESIK_ORTA_SIDDETLI]
    if riskli.empty:
        return
    await baglanti_yoneticisi.yayinla(
        {
            "tip": "turbulans_uyarisi",
            "ucus_numarasi": ucus_numarasi,
            "tarih": tarih,
            "orta_siddetli_nokta_sayisi": int(len(riskli)),
            "maks_ti1": float(riskli["ti1_indeksi"].max()),
        }
    )


async def _webhooku_bildir(webhook_url, govde):
    if not webhook_url:
        return
    try:
        async with httpx.AsyncClient(timeout=10) as istemci:
            await istemci.post(webhook_url, json=govde)
    except Exception as hata:
        _logger.warning("Webhook bildirimi gönderilemedi (%s): %s", webhook_url, dostane_hata_mesaji(hata))


# ---------------------------------------------------------------------------
# /api/v1 -- API anahtarı gerektiren tüm veri/analiz uç noktaları
# ---------------------------------------------------------------------------

v1 = APIRouter(prefix="/api/v1", dependencies=[Depends(api_anahtarini_dogrula)])

# Süreç yeniden başlarsa sıfırlanan basit bellek-içi görev durumu takibi --
# iskelet amaçlı; kalıcı bir görev kuyruğu (Celery/RQ) gerekirse eklenebilir.
#
# ÖNEMLİ: Bu sözlük eskiden HİÇ temizlenmiyordu -- süreç uzun süre ayakta
# kaldıkça (özellikle n8n gibi bir araç periyodik olarak analiz tetikledikçe)
# sınırsız büyüyüp bir bellek sızıntısına yol açıyordu. Artık her yeni görev
# oluşturulmadan önce, belirli bir süre önce BİTMİŞ (çalışmakta olan değil)
# görevler otomatik temizleniyor; ayrıca sözlük büyüklüğüne sabit bir tavan
# konarak (aşırı istek/hız sınırı aşımı gibi uç durumlarda bile) sınırsız
# büyüme kesin olarak engelleniyor.
_gorevler: dict[str, dict] = {}
_GOREV_SAKLAMA_SANIYE = 3600  # bitmiş görevler 1 saat sonra siliniyor
_GOREV_SAYISI_TAVANI = 5000


def _eski_gorevleri_temizle():
    simdi = time.monotonic()
    bitmis_durumlar = ("tamamlandi", "hata", "basarisiz")
    for gid in [
        g
        for g, v in _gorevler.items()
        if v.get("durum") in bitmis_durumlar and simdi - v.get("_olusturulma", simdi) > _GOREV_SAKLAMA_SANIYE
    ]:
        del _gorevler[gid]

    # Süre dolmadan bile sözlük çok büyürse (örn. çok kısa aralıklarla çok
    # sayıda görev tetiklenirse) en eski bitmiş görevleri silerek tavanı koru.
    if len(_gorevler) > _GOREV_SAYISI_TAVANI:
        bitmis_gorevler = sorted(
            (g for g in _gorevler.items() if g[1].get("durum") in bitmis_durumlar),
            key=lambda g: g[1].get("_olusturulma", 0),
        )
        fazlalik = len(_gorevler) - _GOREV_SAYISI_TAVANI
        for gid, _ in bitmis_gorevler[:fazlalik]:
            del _gorevler[gid]


def _gorev_disari_ver(gorev: dict) -> dict:
    """Dışa dönen yanıttan '_olusturulma' gibi dahili alanları çıkarır."""
    return {k: v for k, v in gorev.items() if not k.startswith("_")}


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


class UcusAnalizIstegi(BaseModel):
    ucus_numarasi: str = Field(pattern=_UCUS_NUMARASI_DESENI)
    tarih: str  # YYYY-MM-DD
    bildirim_webhook_url: str | None = None

    @field_validator("tarih")
    @classmethod
    def _tarih_gecerli_mi(cls, deger):
        return _tarihi_dogrula(deger)


class TopluAnalizIstegi(BaseModel):
    ucuslar: list[UcusAnalizIstegi]
    bildirim_webhook_url: str | None = None


@v1.get("/esikler", response_model=EsiklerYaniti)
async def esikleri_getir():
    """web/harita3d.html gibi istemcilerin, renklendirme eşiklerini
    config.py ile bire bir aynı tutabilmesi için (sabitleri JS'e
    kopyalamak yerine tek kaynaktan okumak)."""
    return {
        "ti1_esik_hafif": config.TI1_ESIK_HAFIF,
        "ti1_esik_orta_siddetli": config.TI1_ESIK_ORTA_SIDDETLI,
    }


@v1.get("/ucuslar", response_model=list[UcusYaniti])
async def ucuslar_listesi(limit: int = Query(default=100, ge=1, le=500)):
    return await ucuslari_listele_async(limit=limit)


@v1.get("/ucuslar/{ucus_numarasi}/{tarih}", response_model=UcusDetayYaniti)
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


@v1.get("/ucuslar/{ucus_numarasi}/{tarih}/sigmet-dogrulama", response_model=SigmetDogrulamaYaniti)
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


async def _tek_ucus_arkaplan_gorevi(gorev_id, ucus_numarasi, tarih, webhook_url):
    _gorevler[gorev_id] = {
        "durum": "calisiyor",
        "ucus_numarasi": ucus_numarasi,
        "tarih": tarih,
        "_olusturulma": time.monotonic(),
    }
    try:
        sonuc = await asyncio.to_thread(tek_ucus_analiz_et, ucus_numarasi, tarih)
        _gorevler[gorev_id]["durum"] = "tamamlandi" if sonuc is not None else "basarisiz"
        await _yuksek_riskli_noktalari_yayinla(sonuc, ucus_numarasi, tarih)
    except Exception as hata:
        _gorevler[gorev_id]["durum"] = "hata"
        _gorevler[gorev_id]["aciklama"] = dostane_hata_mesaji(hata)
    await _webhooku_bildir(webhook_url, {"gorev_id": gorev_id, **_gorev_disari_ver(_gorevler[gorev_id])})


@v1.post("/analiz/ucus", status_code=status.HTTP_202_ACCEPTED, response_model=GorevBaslatildiYaniti)
async def ucus_analizi_baslat(istek: UcusAnalizIstegi, arkaplan_gorevleri: BackgroundTasks):
    _hiz_sinirini_kontrol_et("tek_ucus")
    _eski_gorevleri_temizle()
    gorev_id = str(uuid.uuid4())
    arkaplan_gorevleri.add_task(
        _tek_ucus_arkaplan_gorevi, gorev_id, istek.ucus_numarasi, istek.tarih, istek.bildirim_webhook_url
    )
    return {"gorev_id": gorev_id, "durum": "baslatildi"}


async def _toplu_arkaplan_gorevi(gorev_id, ucus_listesi_df, webhook_url):
    _gorevler[gorev_id] = {"durum": "calisiyor", "_olusturulma": time.monotonic()}
    try:
        ozet_df = await asyncio.to_thread(toplu_analiz_calistir, ucus_listesi_df)
        _gorevler[gorev_id]["durum"] = "tamamlandi"
        _gorevler[gorev_id]["ozet"] = ozet_df.to_dict(orient="records")
    except Exception as hata:
        _gorevler[gorev_id]["durum"] = "hata"
        _gorevler[gorev_id]["aciklama"] = dostane_hata_mesaji(hata)
    await _webhooku_bildir(webhook_url, {"gorev_id": gorev_id, **_gorev_disari_ver(_gorevler[gorev_id])})


@v1.post("/analiz/toplu", status_code=status.HTTP_202_ACCEPTED, response_model=GorevBaslatildiYaniti)
async def toplu_analiz_baslat(istek: TopluAnalizIstegi, arkaplan_gorevleri: BackgroundTasks):
    _hiz_sinirini_kontrol_et("toplu")
    _eski_gorevleri_temizle()
    if not istek.ucuslar:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="'ucuslar' listesi boş olamaz.")
    ucus_listesi_df = pd.DataFrame([u.model_dump(exclude={"bildirim_webhook_url"}) for u in istek.ucuslar])
    gorev_id = str(uuid.uuid4())
    arkaplan_gorevleri.add_task(_toplu_arkaplan_gorevi, gorev_id, ucus_listesi_df, istek.bildirim_webhook_url)
    return {"gorev_id": gorev_id, "durum": "baslatildi"}


@v1.get("/analiz/durum/{gorev_id}", response_model=GorevDurumYaniti)
async def analiz_durumu(gorev_id: str):
    gorev = _gorevler.get(gorev_id)
    if gorev is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bilinmeyen gorev_id.")
    return _gorev_disari_ver(gorev)


app.include_router(v1)


@app.get("/saglik", response_model=SaglikYaniti)
def saglik_kontrolu():
    """Kasıtlı olarak API anahtarı gerektirmez (yaygın health-check pratiği)."""
    return {"durum": "ayakta"}
