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
import ipaddress
import json
import os
import secrets
import time
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime
from functools import partial
from urllib.parse import urlsplit

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
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

import config
import loglama
from gorev_deposu import (
    eski_gorevleri_temizle,
    gorev_getir,
    gorev_guncelle,
    gorev_olustur,
    yarida_kalan_gorevleri_isaretle,
)
from hata_yardimcisi import dostane_hata_mesaji
from main import calistir, rota_df_ile_calistir
from rota_optimizasyonu import UCAK_PROFILLERI, rota_simulasyonu_olustur, simulasyonu_czml_e_cevir, veri_kupune_eris
from semalar import (
    EsiklerYaniti,
    GorevBaslatildiYaniti,
    GorevDurumYaniti,
    ModelBilgisiYaniti,
    ModelVersiyonuOzetiYaniti,
    RotaSimulasyonuIstegi,
    RotaSimulasyonuYaniti,
    SaglikYaniti,
    SigmetDogrulamaYaniti,
    TopluSilmeYaniti,
    TurbulansTahminIstegi,
    TurbulansTahminYaniti,
    UcakProfiliYaniti,
    UcusDetayYaniti,
    UcuslarListesiYaniti,
)
from sigmet_dogrulama import ucus_sigmet_ile_karsilastir
from toplu_analiz import toplu_analiz_calistir
from turbulans_ml_modeli import (
    model_bilgisini_yukle,
    model_versiyonlarini_listele,
    ozelliklerden_risk_tahmin_et,
    ozellikleri_cikar,
    versiyona_geri_don,
)
from veri_yukleme import hava_durumu_dosyalari
from veritabani import (
    VeritabaniAyarlariEksikHatasi,
    async_motor_al,
    ucus_detayini_getir_async,
    ucus_olcumlerini_dataframe_olarak_getir,
    ucus_sil_async,
    ucuslari_listele_async,
    ucuslari_toplu_sil_async,
)

loglama.ayarla()
_logger = loglama.logger_al(__name__)

tek_ucus_analiz_et = partial(calistir, kayit_zorunlu=True)
rota_analiz_et = partial(rota_df_ile_calistir, kayit_zorunlu=True)


@asynccontextmanager
async def _yasam_dongusu(uygulama):
    try:
        sayi = await yarida_kalan_gorevleri_isaretle()
        if sayi:
            _logger.warning("Önceki süreçten yarıda kalmış %d analiz görevi 'yarida_kaldi' olarak işaretlendi.", sayi)
    except Exception as hata:
        _logger.warning("Açılışta görev tablosuna erişilemedi: %s", dostane_hata_mesaji(hata))
    yield


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
    if not beklenen or not api_key or not secrets.compare_digest(api_key, beklenen):
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

# Görev durumu PostgreSQL'de (bkz. gorev_deposu.py, models.AnalizGorevi) --
# API yeniden başlasa da /analiz/durum/{gorev_id} çalışmaya devam eder.


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
    if deger is None:
        return None
    parcalar = urlsplit(deger)
    if parcalar.scheme not in ("http", "https") or not parcalar.hostname:
        raise ValueError("bildirim_webhook_url 'http(s)://' ile başlayan geçerli bir URL olmalı.")
    host = parcalar.hostname.lower()
    izinli_hostlar = [
        h.strip().lower() for h in os.environ.get("WEBHOOK_IZIN_VERILEN_HOSTLAR", "").split(",") if h.strip()
    ]
    if izinli_hostlar and host not in izinli_hostlar:
        raise ValueError("bildirim_webhook_url'in host'u WEBHOOK_IZIN_VERILEN_HOSTLAR listesinde değil.")
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return deger
    if ip.is_link_local or ip.is_multicast or ip.is_unspecified or ip.is_reserved:
        raise ValueError("bildirim_webhook_url link-local/multicast/ayrılmış bir adrese işaret edemez.")
    return deger


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
    ucuslar: list[UcusAnalizIstegi]
    bildirim_webhook_url: str | None = None

    @field_validator("bildirim_webhook_url")
    @classmethod
    def _webhook_gecerli_mi(cls, deger):
        return _webhook_url_dogrula(deger)


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
        if not hava_durumu_dosyalari():
            return {
                "kapsam_icinde_mi": False,
                "aciklama": f"'{config.HAVA_DURUMU_DOSYASI}' bulunamadı -- sunucuda ERA5 veri küpü yok.",
            }
        kapsam_disi_yaniti = {
            "kapsam_icinde_mi": False,
            "aciklama": (
                "Seçilen nokta/tarih/irtifa, sunucudaki ERA5 veri küplerinden hiçbirinin kapsadığı aralıkta DEĞİL."
            ),
        }
        veri_kupu = veri_kupune_eris(istek.enlem, istek.boylam, istek.zaman, irtifa_m)
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


@v1.delete("/ucuslar", response_model=TopluSilmeYaniti, tags=["Uçuşlar"])
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


@v1.delete("/ucuslar/{ucus_numarasi}/{tarih}", status_code=status.HTTP_204_NO_CONTENT, tags=["Uçuşlar"])
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


async def _gorev_olustur(tur, ucus_numarasi=None, tarih=None):
    await eski_gorevleri_temizle()
    return await gorev_olustur(tur, ucus_numarasi=ucus_numarasi, tarih=tarih)


async def _gorevi_bitir_ve_bildir(gorev_id, webhook_url, **alanlar):
    await gorev_guncelle(gorev_id, **alanlar)
    await _webhooku_bildir(webhook_url, {"gorev_id": gorev_id, **(await gorev_getir(gorev_id))})


async def _tek_ucus_arkaplan_gorevi(gorev_id, ucus_numarasi, tarih, webhook_url):
    await _analiz_arkaplan_gorevi(
        gorev_id, lambda: tek_ucus_analiz_et(ucus_numarasi, tarih), ucus_numarasi, tarih, webhook_url
    )


async def _analiz_arkaplan_gorevi(gorev_id, analiz_fonksiyonu, ucus_numarasi, tarih, webhook_url):
    try:
        sonuc = await asyncio.to_thread(analiz_fonksiyonu)
        alanlar = {"durum": "tamamlandi" if sonuc is not None else "basarisiz"}
        await _yuksek_riskli_noktalari_yayinla(sonuc, ucus_numarasi, tarih)
    except Exception as hata:
        alanlar = {"durum": "hata", "aciklama": dostane_hata_mesaji(hata)}
    await _gorevi_bitir_ve_bildir(gorev_id, webhook_url, **alanlar)


@v1.post("/analiz/ucus", status_code=status.HTTP_202_ACCEPTED, response_model=GorevBaslatildiYaniti, tags=["Analiz"])
async def ucus_analizi_baslat(istek: UcusAnalizIstegi, arkaplan_gorevleri: BackgroundTasks):
    _hiz_sinirini_kontrol_et("tek_ucus")
    gorev_id = await _gorev_olustur("ucus", ucus_numarasi=istek.ucus_numarasi, tarih=istek.tarih)
    arkaplan_gorevleri.add_task(
        _tek_ucus_arkaplan_gorevi, gorev_id, istek.ucus_numarasi, istek.tarih, istek.bildirim_webhook_url
    )
    return {"gorev_id": gorev_id, "durum": "baslatildi"}


async def _toplu_arkaplan_gorevi(gorev_id, ucus_listesi_df, webhook_url):
    dongu = asyncio.get_running_loop()

    def _ucus_tamamlandi(ucus_numarasi, tarih, eslesmis_df):
        asyncio.run_coroutine_threadsafe(_yuksek_riskli_noktalari_yayinla(eslesmis_df, ucus_numarasi, tarih), dongu)

    try:
        ozet_df = await asyncio.to_thread(
            toplu_analiz_calistir, ucus_listesi_df, kayit_zorunlu=True, ucus_tamamlandi=_ucus_tamamlandi
        )
        ozet = ozet_df.astype(object).where(ozet_df.notna(), None).to_dict(orient="records")
        alanlar = {"durum": "tamamlandi", "ozet": ozet}
    except Exception as hata:
        alanlar = {"durum": "hata", "aciklama": dostane_hata_mesaji(hata)}
    await _gorevi_bitir_ve_bildir(gorev_id, webhook_url, **alanlar)


@v1.post("/analiz/rota", status_code=status.HTTP_202_ACCEPTED, response_model=GorevBaslatildiYaniti, tags=["Analiz"])
async def rota_analizi_baslat(istek: RotaAnalizIstegi, arkaplan_gorevleri: BackgroundTasks):
    """
    OpenSky'a BAĞLANMADAN, dışarıdan alınmış bir ADS-B izini (başka bir
    izleme servisi, uçuş kayıt cihazı vb.) analiz eder: aynı eşleştirme,
    PostgreSQL kaydı, WebSocket uyarısı ve webhook akışı. OpenSky'ın tarayıcı
    tabanlı OAuth2 girişini gerektirmediği için sunucu/Docker ortamında da
    çalışır. Tarih, ilk noktanın UTC gününden türetilir; sonuç
    GET /ucuslar/{ucus_numarasi}/{tarih} ile okunur.
    """
    _hiz_sinirini_kontrol_et("rota")
    rota_df = pd.DataFrame([n.model_dump() for n in istek.noktalar]).rename(columns={"irtifa_m": "geo_irtifa_m"})
    rota_df["zaman"] = pd.to_datetime(rota_df["zaman"], utc=True)
    rota_df["geo_irtifa_m"] = rota_df["geo_irtifa_m"].astype(float)
    rota_df = rota_df.sort_values("zaman").reset_index(drop=True)
    rota_df["ucus_numarasi"] = istek.ucus_numarasi
    tarih = rota_df["zaman"].iloc[0].date().isoformat()

    gorev_id = await _gorev_olustur("rota", ucus_numarasi=istek.ucus_numarasi, tarih=tarih)
    arkaplan_gorevleri.add_task(
        _analiz_arkaplan_gorevi,
        gorev_id,
        lambda: rota_analiz_et(rota_df, istek.ucus_numarasi, tarih),
        istek.ucus_numarasi,
        tarih,
        istek.bildirim_webhook_url,
    )
    return {"gorev_id": gorev_id, "durum": "baslatildi"}


@v1.post("/analiz/toplu", status_code=status.HTTP_202_ACCEPTED, response_model=GorevBaslatildiYaniti, tags=["Analiz"])
async def toplu_analiz_baslat(istek: TopluAnalizIstegi, arkaplan_gorevleri: BackgroundTasks):
    _hiz_sinirini_kontrol_et("toplu")
    if not istek.ucuslar:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="'ucuslar' listesi boş olamaz.")
    ucus_listesi_df = pd.DataFrame([u.model_dump(exclude={"bildirim_webhook_url"}) for u in istek.ucuslar])
    gorev_id = await _gorev_olustur("toplu")
    arkaplan_gorevleri.add_task(_toplu_arkaplan_gorevi, gorev_id, ucus_listesi_df, istek.bildirim_webhook_url)
    return {"gorev_id": gorev_id, "durum": "baslatildi"}


@v1.get("/analiz/durum/{gorev_id}", response_model=GorevDurumYaniti, tags=["Analiz"])
async def analiz_durumu(gorev_id: str):
    gorev = await gorev_getir(gorev_id)
    if gorev is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bilinmeyen gorev_id.")
    return gorev


app.include_router(v1)


@app.get("/saglik", response_model=SaglikYaniti, tags=["Sistem"])
async def saglik_kontrolu(
    derin: bool = Query(default=False, description="True ise PostgreSQL'e gerçekten bağlanmayı dener"),
):
    """Kasıtlı olarak API anahtarı gerektirmez (yaygın health-check pratiği).
    Varsayılan (sığ) davranış DEĞİŞMEDİ -- sadece süreç ayakta mı diye bakar,
    her yük dengeleyici probunda PostgreSQL'e gitmeyi zorlamaz.
    `?derin=true` ile gerçek bir PostgreSQL bağlantısı denenir (deploy
    sonrası 'DB'ye GERÇEKTEN erişiyor muyum' diye elle/monitoring'den
    kontrol için)."""
    if not derin:
        return {"durum": "ayakta"}
    try:
        motor = async_motor_al()
        async with motor.connect() as baglanti:
            await baglanti.execute(text("SELECT 1"))
        return {"durum": "ayakta", "veritabani": "erisilebilir"}
    except Exception as hata:
        _logger.warning("Derin sağlık kontrolünde PostgreSQL'e erişilemedi: %s", dostane_hata_mesaji(hata))
        return JSONResponse(status_code=503, content={"durum": "ayakta", "veritabani": "erisilemiyor"})
