"""
api_servisi.py
-----------------
Hava durumu eşleştirme sonuçlarını (Ellrod TI1, Richardson, gösterge ölçeği -- EDR değildir) JSON
olarak dışarıya sunan FastAPI servis katmanı.

Yapı: bu dosya uygulama, ara katmanlar, zamanlayıcılar, WebSocket, sağlık/metrik ve
simülasyon/tahmin uçlarını tutar. Anahtar ve rol doğrulaması api/guvenlik.py'de, router'ların
paylaştığı yardımcılar (hız sınırı, ağır hesap yuvası, rota önbelleği, görev kuyruğu) api/ortak.py'de,
diğer uç nokta grupları api/yollar/ altındadır (ucuslar, analiz, hava_sahasi, ml).

Güvenlik: /api/v1/* altındaki TÜM uç noktalar 'X-API-Key' başlığıyla
korunur (bkz. api_anahtarini_dogrula). Anahtar '.env'deki API_ANAHTARI
değişkeninden okunur -- kod içine yazılmaz. /saglik kasıtlı olarak açık
bırakıldı (yaygın pratik: yük dengeleyici/monitoring health-check'i).

Sürümleme: tüm veri/analiz uç noktaları /api/v1 altında (bkz. Kurumsal API
dokümantasyonu isteği) -- ileride /api/v2 eklenirse mevcut istemciler
bozulmaz. İnteraktif Swagger dokümantasyonu FastAPI'nin ürettiği /docs
adresindedir; API ağa açılınca kapanır (bkz. api_belgeleri_acik_mi).

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
import glob
import inspect
import json
import os
import time
import weakref
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qsl, urlencode

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
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from turbulans_radar import config, loglama
from turbulans_radar.api import metrikler, ortak
from turbulans_radar.api.guvenlik import (
    _BILET_SURESI_SANIYE,
    _YONETICI,
    _anahtar_ayarlarini_denetle,
    _anahtari_coz,
    _yalnizca_yerel_yayin_mi,
    api_anahtarini_dogrula,
    ws_bileti_uret,
    ws_biletini_kullan,
)
from turbulans_radar.api.semalar import (
    DenetimKaydiYaniti,
    EsiklerYaniti,
    RotaSimulasyonuIstegi,
    RotaSimulasyonuYaniti,
    SaglikYaniti,
    SistemDurumuYaniti,
    TurbulansTahminIstegi,
    TurbulansTahminYaniti,
    UcakProfiliYaniti,
    WsBiletiYaniti,
)
from turbulans_radar.api.yollar import analiz, hava_sahasi, ml, ucuslar
from turbulans_radar.api.yollar.ml import MlGeceIsiIstegi
from turbulans_radar.cli.statik_indir import yerel_kutuphane_durumu
from turbulans_radar.depo.dagitik_kilit import LiderKilidi
from turbulans_radar.depo.denetim import denetim_kaydet, denetim_kayitlarini_listele
from turbulans_radar.depo.gorev_deposu import (
    AKTIF_DURUMLAR,
    aktif_gorev_var_mi,
    gorev_durumlari,
    gorev_olustur,
    kuyruk_durumu,
    son_gorevler,
)
from turbulans_radar.depo.kaynak_durumu import devre_kalan_saniye, kaynak_durumlarini_getir
from turbulans_radar.depo.kup_katalogu import yerel_kupleri_katalogla
from turbulans_radar.depo.veritabani import (
    VeritabaniAyarlariEksikHatasi,
    async_motor_al,
    asyncpg_baglanti_parametreleri,
)
from turbulans_radar.fizik.turbulans_indeksleri import TI1_GUVENILIRLIK_NOTU
from turbulans_radar.hata_yardimcisi import dostane_hata_mesaji
from turbulans_radar.isci.gorev_iscisi import BILDIRIM_KANALI, GorevIscisi
from turbulans_radar.ml.turbulans_ml_modeli import (
    ml_karar_esigi,
    model_bilgisini_yukle,
    model_kullanilabilir_mi,
    ozelliklerden_risk_tahmin_et,
    ozellikleri_cikar,
    risk_durumlarini_hesapla,
)
from turbulans_radar.rota.hava_yolu_agi import AtsAgiHatasi
from turbulans_radar.rota.rota_optimizasyonu import (
    CANLI_VERI_HAZIRLANIYOR,
    UCAK_PROFILLERI,
    AntimeridyenHatasi,
    AtsAgiKullanilamazHatasi,
    rota_simulasyonu_olustur,
    simulasyonu_czml_e_cevir,
    veri_kupune_eris,
)
from turbulans_radar.uretim_bilgisi import uretim_bilgisi
from turbulans_radar.veri.fir_sinirlari import fir_verisi_var_mi
from turbulans_radar.veri.kisitli_saha_saglayici import (
    ORNEK_KAYNAK,
    gecerli_kisitli_sahalari_getir,
    ornek_veriyi_yukle,
)
from turbulans_radar.veri.openaip_saglayici import OPENAIP_DURUM_ANAHTARI
from turbulans_radar.veri.sigmet_saglayici import (
    kaynak_saglik_durumlari,
    sigmetleri_guncelle,
    son_guncelleme_zamani,
)
from turbulans_radar.veri.veri_saglayicilari import canli_durum_anahtari, canli_indirme_durumu, veri_kupu_kaynagi
from turbulans_radar.veri.veri_yukleme import hava_durumu_dosyalari, onbellek_durumu

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
    _anahtar_ayarlarini_denetle()
    dinleyici = asyncio.create_task(_uyari_dinleyicisi())
    lider = LiderKilidi(ZAMANLAYICI_LIDER_KILIDI)
    fabrikalar = _zamanlayici_fabrikalari()
    lider_dongusu = asyncio.create_task(_zamanlayici_lider_dongusu(lider, fabrikalar)) if fabrikalar else None
    isci = GorevIscisi().baslat() if config.GOREV_GOMULU_ISCI else None
    yield
    for gorev in (dinleyici, lider_dongusu):
        if gorev is not None:
            gorev.cancel()
    await asyncio.to_thread(lider.birak)
    if isci is not None:
        await asyncio.to_thread(isci.durdur, 5.0)


ZAMANLAYICI_LIDER_KILIDI = "api_zamanlayicilari"
KONFORMAL_DOGRULANAN_KAYNAKLAR = {"era5"}


def _zamanlayici_fabrikalari() -> list:
    """Açık olan, dış servise giden zamanlayıcılar (coroutine fabrikaları)."""
    fabrikalar = []
    if config.SIGMET_OTOMATIK_GUNCELLEME_DAKIKA > 0:
        fabrikalar.append(lambda: _sigmet_zamanlayicisi(config.SIGMET_OTOMATIK_GUNCELLEME_DAKIKA * 60))
    if config.OPENAIP_OTOMATIK_GUNCELLEME_SAAT > 0:
        if os.environ.get("OPENAIP_API_ANAHTARI"):
            fabrikalar.append(lambda: _openaip_zamanlayicisi(config.OPENAIP_OTOMATIK_GUNCELLEME_SAAT * 3600))
        else:
            _logger.warning("OPENAIP_OTOMATIK_GUNCELLEME_SAAT açık ama OPENAIP_API_ANAHTARI yok; yenileme kapalı.")
    if config.CANLI_ISITMA_SAAT > 0 and config.CANLI_HAVA_VERISI_ETKIN:
        fabrikalar.append(lambda: _gfs_isitma_zamanlayicisi(config.CANLI_ISITMA_SAAT * 3600))
    if config.ML_GECE_ISI_SAATI:
        try:
            _gece_isi_saati(config.ML_GECE_ISI_SAATI)
            fabrikalar.append(lambda: _ml_gece_zamanlayicisi(config.ML_GECE_ISI_SAATI))
        except ValueError as hata:
            _logger.error("ML_GECE_ISI_SAATI geçersiz, ML gece işi zamanlayıcısı kapalı: %s", hata)
    return fabrikalar


async def _zamanlayici_lider_dongusu(lider, fabrikalar=None, yoklama_saniye=None):
    """Zamanlayıcıları yalnızca lider kilidini tutan API süreci çalıştırır
    (WEB_CONCURRENCY > 1'de AWC/openAIP/CDS'e giden istekler çoğalmasın).
    Liderlik kaybedilirse zamanlayıcılar durdurulur, başka süreç devralır."""
    fabrikalar = _zamanlayici_fabrikalari() if fabrikalar is None else fabrikalar
    yoklama = config.ZAMANLAYICI_LIDER_YOKLAMA_SANIYE if yoklama_saniye is None else yoklama_saniye
    gorevler = []
    try:
        while True:
            lider_mi = await asyncio.to_thread(lider.dene)
            if lider_mi and not gorevler:
                gorevler = [asyncio.create_task(fabrika()) for fabrika in fabrikalar]
                _logger.info("Bu API süreci zamanlayıcı lideri (%d zamanlayıcı başlatıldı).", len(gorevler))
            elif not lider_mi and gorevler:
                for gorev in gorevler:
                    gorev.cancel()
                gorevler = []
                _logger.warning("Zamanlayıcı liderliği kaybedildi; zamanlayıcılar durduruldu.")
            await asyncio.sleep(yoklama)
    finally:
        for gorev in gorevler:
            gorev.cancel()


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


def _openaip_yenilemesi_gerekli_mi(aralik_saniye) -> bool:
    """Son DENEME (başarı değil) aralıktan eskiyse: başarısız bir çekim de bir
    sonraki aralığa kadar tekrar denenmez (openAIP'i hata döngüsünde yormaz)."""
    kayitlar = kaynak_durumlarini_getir([OPENAIP_DURUM_ANAHTARI])
    if not kayitlar:
        return True
    return (datetime.now(UTC) - kayitlar[0]["son_deneme_zamani"]).total_seconds() >= aralik_saniye


async def _openaip_zamanlayici_adimi(aralik_saniye) -> str | None:
    """Gerekiyorsa openAIP yenilemesini işçi kuyruğuna ekler (API'de değil
    işçide çalışır, API yeniden başlasa da kaybolmaz). Zaten bekleyen/çalışan
    bir openAIP görevi varsa eklemez -- birden fazla API kopyası çoğaltmasın."""
    if not await asyncio.to_thread(_openaip_yenilemesi_gerekli_mi, aralik_saniye):
        return None
    if await aktif_gorev_var_mi("openaip"):
        return None
    gorev_id = await gorev_olustur("openaip", parametreler={"ulkeler": None})
    _logger.info("openAIP otomatik yenilemesi kuyruğa alındı (%s).", gorev_id)
    return gorev_id


async def _openaip_zamanlayicisi(aralik_saniye, kontrol_saniye=600.0):
    while True:
        try:
            await _openaip_zamanlayici_adimi(aralik_saniye)
        except Exception as hata:
            _logger.warning("openAIP zamanlayıcısı çalışamadı: %s", dostane_hata_mesaji(hata))
        await asyncio.sleep(min(kontrol_saniye, aralik_saniye))


_GFS_ISITMA_HATA_BEKLEME = timedelta(minutes=30)


async def _gfs_isitma_adimi(aralik_saniye, simdi: datetime | None = None) -> str | None:
    """Son aralıkta canlı veri görevi yoksa CANLI_ISITMA_KUTUSU için GFS küpünü
    kuyruğa alır: sağlayıcı kesintisi ilk kullanıcı isteğinden önce fark edilir.
    Başarısız deneme (ör. açılışta DNS hazır değilken) tüm aralığı değil, yalnızca
    _GFS_ISITMA_HATA_BEKLEME'yi bekletir."""
    simdi = simdi or datetime.now(UTC)
    pencere = timedelta(seconds=aralik_saniye)
    durumlar = await gorev_durumlari("canli_veri", simdi - pencere)
    if any(d not in ("hata", "yarida_kaldi") for d in durumlar):
        return None
    if durumlar and await gorev_durumlari("canli_veri", simdi - min(pencere, _GFS_ISITMA_HATA_BEKLEME)):
        return None
    if await aktif_gorev_var_mi("canli_veri"):
        return None
    gorev_id = await gorev_olustur(
        "canli_veri",
        parametreler={
            "kutu": list(config.CANLI_ISITMA_KUTUSU),
            "baslangic": simdi.isoformat(),
            "saat_sayisi": config.CANLI_ISITMA_SAAT_SAYISI,
        },
    )
    _logger.info("Canlı GFS ısıtması kuyruğa alındı (%s).", gorev_id)
    return gorev_id


async def _gfs_isitma_zamanlayicisi(aralik_saniye, kontrol_saniye=600.0):
    while True:
        try:
            await _gfs_isitma_adimi(aralik_saniye)
        except Exception as hata:
            _logger.warning("GFS ısıtma zamanlayıcısı çalışamadı: %s", dostane_hata_mesaji(hata))
        await asyncio.sleep(min(kontrol_saniye, aralik_saniye))


def _gece_isi_saati(deger: str) -> tuple[int, int]:
    saat, _, dakika = deger.partition(":")
    saat, dakika = int(saat), int(dakika or 0)
    if not (0 <= saat < 24 and 0 <= dakika < 60):
        raise ValueError(f"'{deger}' SS:DD biçiminde olmalı")
    return saat, dakika


async def _ml_gece_zamanlayici_adimi(saat_metni: str, simdi: datetime | None = None) -> str | None:
    """Bugünün planlı saati geçtiyse ve o saatten sonra başarıyla biten ya da
    süren bir ml_veri görevi yoksa gece işini kuyruğa alır. Bilgisayar
    kapanır/uyursa görev yarida_kaldi/hata olabilir: aynı gün en fazla
    ML_GECE_GUNLUK_MAKS_DENEME kez yeniden denenir (CDS/MADIS günlük kotaları
    veritabanında olduğu için yeniden deneme sınırları aşamaz). Kuyrukta/çalışan
    bir ML işi varsa eklemez."""
    simdi = simdi or datetime.now(UTC)
    saat, dakika = _gece_isi_saati(saat_metni)
    planli = simdi.replace(hour=saat, minute=dakika, second=0, microsecond=0)
    if simdi < planli:
        return None
    durumlar = await gorev_durumlari("ml_veri", planli)
    if any(d not in ("yarida_kaldi", "hata") for d in durumlar) or len(durumlar) >= config.ML_GECE_GUNLUK_MAKS_DENEME:
        return None
    if await aktif_gorev_var_mi("ml_veri") or await aktif_gorev_var_mi("ml_egitim"):
        return None
    gorev_id = await ortak._gorev_olustur("ml_veri", parametreler=MlGeceIsiIstegi().model_dump())
    _logger.info("ML gece işi zamanlayıcıyla kuyruğa alındı (%s, planlı %s UTC).", gorev_id, saat_metni)
    return gorev_id


async def _ml_gece_zamanlayicisi(saat_metni: str, kontrol_saniye=300.0):
    while True:
        try:
            await _ml_gece_zamanlayici_adimi(saat_metni)
        except Exception as hata:
            _logger.warning("ML gece işi zamanlayıcısı çalışamadı: %s", dostane_hata_mesaji(hata))
        await asyncio.sleep(kontrol_saniye)


async def _sigmet_zamanlayicisi(aralik_saniye):
    """config.SIGMET_OTOMATIK_GUNCELLEME_DAKIKA > 0 ise API, n8n/cron'a gerek
    kalmadan AWC SIGMET'lerini kendi içinde periyodik olarak yeniler."""
    while True:
        try:
            ozet = await asyncio.to_thread(sigmetleri_guncelle)
            await ortak._rota_onbellegini_temizle()
            if ozet["kaynak_hatalari"]:
                _logger.error("SIGMET kaynak hataları (mevcut kayıtlar korundu): %s", ozet["kaynak_hatalari"])
            _logger.info("SIGMET'ler yenilendi: %s", ozet)
        except Exception as hata:
            _logger.warning("Periyodik SIGMET yenilemesi başarısız: %s", dostane_hata_mesaji(hata))
        await asyncio.sleep(aralik_saniye)


def api_belgeleri_acik_mi() -> bool:
    """/docs, /redoc, /openapi.json: API_BELGELERI_ACIK açıkça verilmediyse
    yalnızca API bu makineye bağlıyken (API_YAYIN_ADRESI yerel/boş) açıktır;
    ağa açılınca uç nokta listesi anahtarsız görünmesin."""
    acik = os.environ.get("API_BELGELERI_ACIK", "").strip().lower()
    if acik:
        return acik in ("1", "true", "evet", "acik")
    return _yalnizca_yerel_yayin_mi()


_BELGELER_ACIK = api_belgeleri_acik_mi()

app = FastAPI(
    title="Türbülans Radar API",
    description="Ellrod TI1 + Richardson tabanlı türbülans eşleştirme sonuçlarını JSON olarak sunar.",
    version="1.0.0",
    lifespan=_yasam_dongusu,
    docs_url="/docs" if _BELGELER_ACIK else None,
    redoc_url="/redoc" if _BELGELER_ACIK else None,
    openapi_url="/openapi.json" if _BELGELER_ACIK else None,
)


class _GovdeCokBuyukHatasi(Exception):
    pass


class _GovdeBoyutSiniriMiddleware:
    """Starlette, bir isteğin gövdesini (dict/JSON body parametreleri için)
    ayrıştırmadan/alan bazlı sınırlara (örn. kisitli_saha_saglayici.MAKS_
    OZELLIK) ulaşmadan ÖNCE tamamen belleğe okur -- bu ASGI katmanı olmadan
    Content-Length'i büyük (ya da hiç) beyan edilmemiş bir istek, doğrulama
    hiç çalışmadan bellek sıçramasına yol açabilir. Content-Length varsa
    erken (gövde hiç okunmadan) 413 döner; yoksa (chunked/yanlış beyan)
    gövdeyi akış sırasında sayıp sınırı aynı şekilde zorlar."""

    def __init__(self, app, maks_bayt: int):
        self.app = app
        self.maks_bayt = maks_bayt

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        for isim, deger in scope.get("headers") or []:
            if isim == b"content-length":
                try:
                    if int(deger) > self.maks_bayt:
                        await self._413_dondur(send)
                        return
                except ValueError:
                    pass
                break

        toplam_bayt = 0

        async def _sinirli_receive():
            nonlocal toplam_bayt
            mesaj = await receive()
            if mesaj["type"] == "http.request":
                toplam_bayt += len(mesaj.get("body") or b"")
                if toplam_bayt > self.maks_bayt:
                    raise _GovdeCokBuyukHatasi()
            return mesaj

        try:
            await self.app(scope, _sinirli_receive, send)
        except _GovdeCokBuyukHatasi:
            await self._413_dondur(send)

    @staticmethod
    async def _413_dondur(send):
        await send(
            {
                "type": "http.response.start",
                "status": status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                "headers": [(b"content-type", b"application/json")],
            }
        )
        await send({"type": "http.response.body", "body": b'{"detail":"Istek govdesi cok buyuk."}'})


app.add_middleware(_GovdeBoyutSiniriMiddleware, maks_bayt=int(config.MAKS_ISTEK_GOVDESI_MB * 1024 * 1024))

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
# Güvenlik: rollü statik API anahtarları ('.env')
#   API_ANAHTARI       -> yönetici: her şey (n8n, operasyon). Zorunlu; WS
#                         biletlerinin imza anahtarıdır da.
#   API_PILOT_ANAHTARI -> pilot/EFB istemcisi (isteğe bağlı): okuma, rota
#                         simülasyonu, tahmin, canlı uyarılar. Silme, kısıtlı
#                         saha değişikliği, model aktifleştirme ve görev
#                         tetikleme 403 döner -- kokpitteki bir tabletten
#                         sızan anahtar güvenlik verisini değiştiremesin.
#   API_ANAHTARLARI    -> isteğe bağlı, kişi/cihaz başına anahtarlar:
#                         'kimlik:rol:anahtar' virgülle ayrılmış (örn.
#                         'ops-ayse:yonetici:...,efb-tc-jfa:pilot:...').
#                         Denetim kaydında kimlik görünür; rotasyon için yeni
#                         anahtar eklenir, eskisi çıkarılır.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Basit bellek-içi hız sınırlama (sadece analiz tetikleme uç noktaları için
# -- OpenSky'yi dış dünyadan gelen aşırı istekle yormamak amacıyla)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Denetim kaydı: /api/v1 altındaki her değiştirici istek (bkz. depo/denetim.py)
# ---------------------------------------------------------------------------

_DENETLENEN_YONTEMLER = {"POST", "PUT", "PATCH", "DELETE"}
_DENETIM_DISI_YOLLAR = {"/api/v1/ws-bileti"}
# Sorgu dizesinde sır taşıyabilecek parametreler (n8n webhook URL'leri gizli
# yol belirteci içerir) denetim tablosuna maskelenerek yazılır.
_MASKELENEN_PARAMETRELER = {"bildirim_webhook_url", "api_key", "bilet"}


def _denetim_yolu(request: Request) -> str:
    if not request.url.query:
        return request.url.path
    parcalar = [
        (ad, "***" if ad in _MASKELENEN_PARAMETRELER else deger)
        for ad, deger in parse_qsl(request.url.query, keep_blank_values=True)
    ]
    return f"{request.url.path}?{urlencode(parcalar)}"


@app.middleware("http")
async def _http_metrikleri(request: Request, call_next):
    baslangic = time.monotonic()
    durum_kodu = 500
    try:
        yanit = await call_next(request)
        durum_kodu = yanit.status_code
        return yanit
    finally:
        # Ham yol değil route şablonu: her uçuş numarası ayrı seri açmasın.
        rota = request.scope.get("route")
        if rota is not None and getattr(rota, "path", None):
            yol = rota.path
        else:
            yol = "/harita" if request.url.path.startswith("/harita") else "eslesmeyen"
        metrikler.HTTP_ISTEKLERI.labels(request.method, yol, str(durum_kodu)).inc()
        metrikler.HTTP_SURESI.labels(request.method, yol).observe(time.monotonic() - baslangic)


@app.middleware("http")
async def _denetim_kaydi_tut(request: Request, call_next):
    yol = request.url.path
    if request.method not in _DENETLENEN_YONTEMLER or not yol.startswith("/api/v1/") or yol in _DENETIM_DISI_YOLLAR:
        return await call_next(request)
    baslangic = time.monotonic()
    durum_kodu = 500
    try:
        yanit = await call_next(request)
        durum_kodu = yanit.status_code
        return yanit
    finally:
        try:
            await denetim_kaydet(
                getattr(request.state, "kimlik", "kimliksiz"),
                getattr(request.state, "rol", None),
                request.method,
                _denetim_yolu(request),
                durum_kodu,
                request.client.host if request.client else None,
                int((time.monotonic() - baslangic) * 1000),
            )
        except Exception as hata:
            # Kayıt yazılamasa da istek sonucu değişmez; kayıp ERROR loglanır.
            _logger.error("Denetim kaydı yazılamadı (%s %s): %s", request.method, yol, dostane_hata_mesaji(hata))


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


_PAKET_KLASORU = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + os.sep


def _uygulama_hatasi_mi(hata: BaseException) -> bool:
    """Hata bu paketin kodunda mı fırlatıldı (son çerçeve)? Uygulama, kullanıcı
    girdisi için ValueError'ı bilerek ve güvenli bir mesajla fırlatır (örn.
    "'ucuslar' listesi boş olamaz"); kütüphane içinden gelen ValueError ise iç
    ayrıntı taşıyabilir ve bir doğrulama açığına işaret eder."""
    son = hata.__traceback__
    while son is not None and son.tb_next is not None:
        son = son.tb_next
    return son is not None and os.path.abspath(son.tb_frame.f_code.co_filename).startswith(_PAKET_KLASORU)


@app.exception_handler(ValueError)
async def deger_hatasi_isle(request: Request, hata: ValueError):
    if _uygulama_hatasi_mi(hata):
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"detail": str(hata)})
    return await genel_hata_isle(request, hata)


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
    """Her istemcinin kendi sınırlı kuyruğu ve gönderici görevi vardır.
    ESKİDEN yayın sıralı ve zaman aşımsızdı: tek bir yavaş/donmuş istemci
    (kötü bağlantılı bir kokpit tableti) tüm pilotlara giden türbülans
    uyarılarını bekletebiliyordu. Artık yayinla hiç beklemez; kuyruğu dolan
    (WS_ISTEMCI_KUYRUK_BOYUTU) ya da bir mesajı WS_GONDERIM_ZAMAN_ASIMI_SANIYE
    içinde alamayan istemci 1013 ile düşürülür -- istemci yeniden bağlanır."""

    def __init__(self):
        self._kuyruklar: dict[WebSocket, asyncio.Queue] = {}
        self._gondericiler: dict[WebSocket, asyncio.Task] = {}
        self._dusurmeler: set[asyncio.Task] = set()

    @property
    def baglantilar(self) -> list[WebSocket]:
        return list(self._kuyruklar)

    async def baglan(self, websocket: WebSocket):
        await websocket.accept()
        kuyruk = asyncio.Queue(maxsize=config.WS_ISTEMCI_KUYRUK_BOYUTU)
        self._kuyruklar[websocket] = kuyruk
        self._gondericiler[websocket] = asyncio.create_task(self._gonder(websocket, kuyruk))

    def ayril(self, websocket: WebSocket):
        self._kuyruklar.pop(websocket, None)
        gonderici = self._gondericiler.pop(websocket, None)
        if gonderici is not None and gonderici is not asyncio.current_task():
            gonderici.cancel()

    async def _gonder(self, websocket: WebSocket, kuyruk: asyncio.Queue):
        try:
            while True:
                mesaj = await kuyruk.get()
                await asyncio.wait_for(websocket.send_json(mesaj), timeout=config.WS_GONDERIM_ZAMAN_ASIMI_SANIYE)
        except asyncio.CancelledError:
            raise
        except Exception as hata:
            _logger.warning("WebSocket istemcisine gönderilemedi, düşürülüyor: %s", type(hata).__name__)
            await self._dusur(websocket)

    async def _dusur(self, websocket: WebSocket):
        self.ayril(websocket)
        try:
            await websocket.close(code=1013)
        except Exception:
            pass

    async def yayinla(self, mesaj: dict):
        for websocket, kuyruk in list(self._kuyruklar.items()):
            try:
                kuyruk.put_nowait(mesaj)
            except asyncio.QueueFull:
                _logger.warning("Yavaş WebSocket istemcisi düşürüldü (kuyruk dolu).")
                gorev = asyncio.create_task(self._dusur(websocket))
                self._dusurmeler.add(gorev)
                gorev.add_done_callback(self._dusurmeler.discard)


baglanti_yoneticisi = _BaglantiYoneticisi()


@app.websocket("/ws/uyarilar")
async def uyarilar_websocket(websocket: WebSocket, bilet: str | None = None):
    """Kimlik: POST /api/v1/ws-bileti'den alınan 60 sn'lik, tek kullanımlık
    bilet. ?api_key= kabul edilmez (anahtar URL'de/loglarda kalırdı)."""
    if not os.environ.get("API_ANAHTARI") or not ws_biletini_kullan(bilet):
        await websocket.close(code=4401)
        return
    await baglanti_yoneticisi.baglan(websocket)
    try:
        while True:
            await websocket.receive_text()
    except (WebSocketDisconnect, RuntimeError):
        # RuntimeError: yavaş istemci sunucu tarafından kapatıldıysa (bkz.
        # _BaglantiYoneticisi._dusur) receive artık çağrılamaz.
        pass
    finally:
        baglanti_yoneticisi.ayril(websocket)


# ---------------------------------------------------------------------------
# /api/v1 -- API anahtarı gerektiren tüm veri/analiz uç noktaları
# ---------------------------------------------------------------------------

v1 = APIRouter(prefix="/api/v1", dependencies=[Depends(api_anahtarini_dogrula)])

# Uzun işler PostgreSQL kuyruğunda (bkz. gorev_deposu.py, isci/gorev_iscisi.py)
# -- API yeniden başlasa da /analiz/durum/{gorev_id} çalışmaya devam eder.


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
        "ti1_guvenilirlik_notu": TI1_GUVENILIRLIK_NOTU,
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
async def rota_simulasyonu(istek: RotaSimulasyonuIstegi, request: Request, rol: str = Depends(api_anahtarini_dogrula)):
    """
    Verilen başlangıç/bitiş/irtifa/tarih/uçak için iki rota üretir: büyük
    daire ("normal") ve ERA5 rüzgarına göre yanal kaydırılmış en hızlı aday
    ("optimize") -- bkz. rota_optimizasyonu.py (kapsam dışı bölge/tarih için
    dürüst geri düşüş davranışı dahil). A* CPU ağır olduğu ve pilot anahtarı
    da çağırabildiği için istemci başına hız sınırı (ROTA_HESABI_DAKIKADA_MAKS)
    ve süreç başına eşzamanlılık tavanı uygulanır; hesap ayrı thread'dedir.
    """
    await ortak._hiz_sinirini_kontrol_et(
        f"rota_hesabi:{ortak._istemci_kimligi(request, rol)}", maks=config.ROTA_HESABI_DAKIKADA_MAKS, pencere_saniye=60
    )
    onbellek_anahtari = istek.model_dump_json()
    onceki, damga = await ortak._rota_onbellekten_al(onbellek_anahtari)
    if onceki is not None:
        metrikler.ROTA_ONBELLEGI.labels("isabet").inc()
        return onceki
    metrikler.ROTA_ONBELLEGI.labels("iska").inc()
    async with ortak._agir_hesap_yuvasi():
        hesap_baslangici = time.monotonic()
        try:
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
                arama_uzayi=istek.arama_uzayi,
                kalkis_meydani=istek.kalkis_meydani,
                varis_meydani=istek.varis_meydani,
            )
        except (AtsAgiKullanilamazHatasi, AtsAgiHatasi, AntimeridyenHatasi) as hata:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(hata)) from None
        metrikler.ROTA_HESABI_SURESI.observe(time.monotonic() - hesap_baslangici)
    sonuc["czml"] = simulasyonu_czml_e_cevir(sonuc)
    await ortak._rota_onbellege_koy(onbellek_anahtari, sonuc, damga)
    return sonuc


@v1.post("/turbulans/tahmin", response_model=TurbulansTahminYaniti, tags=["Türbülans Tahmini"])
async def turbulans_tahmini(istek: TurbulansTahminIstegi, request: Request, rol: str = Depends(api_anahtarini_dogrula)):
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
        _, ml_notu = model_kullanilabilir_mi()
        bilgi = model_bilgisini_yukle() if ml_olasilik is not None else None
        durumlar = risk_durumlarini_hesapla([ml_olasilik], bilgi) if ml_olasilik is not None else None
        konformal = (bilgi or {}).get("konformal") if durumlar is not None else None
        kaynak = veri_kupu_kaynagi(veri_kupu)
        konformal_notu = None
        if konformal and kaynak not in KONFORMAL_DOGRULANAN_KAYNAKLAR:
            konformal, konformal_notu = None, f"Konformal kapsama {kaynak} girdisinde doğrulanmadı (yalnızca ERA5)."

        return {
            "kapsam_icinde_mi": True,
            "veri_kaynagi": kaynak,
            "ti1_indeksi": float(ti1),
            "ti1_riskli_mi": bool(ti1 >= config.TI1_ESIK_ORTA_SIDDETLI),
            "ti1_guvenilirlik_notu": TI1_GUVENILIRLIK_NOTU,
            "ml_riski_var_mi": (ml_olasilik >= ml_karar_esigi(bilgi)) if ml_olasilik is not None else None,
            "ml_olasilik": ml_olasilik,
            "ml_risk_durumu": durumlar[0] if durumlar is not None else None,
            "ml_konformal_hedef_kapsama": (1 - konformal["alfa"]) if konformal else None,
            "ml_konformal_notu": konformal_notu,
            "uretim_bilgisi": uretim_bilgisi(veri_kupu, bilgi),
            "aciklama": (
                "Fizik (Ellrod TI1) ve ML tahminleri hesaplandı."
                if ml_olasilik is not None
                else f"Fizik (Ellrod TI1) hesaplandı; {ml_notu or 'ML tahmini üretilemedi.'}"
            ),
        }

    await ortak._hiz_sinirini_kontrol_et(
        f"tahmin:{ortak._istemci_kimligi(request, rol)}", maks=config.TAHMIN_DAKIKADA_MAKS, pencere_saniye=60
    )
    async with ortak._agir_hesap_yuvasi():
        return await asyncio.to_thread(_hesapla)


# ---------------------------------------------------------------------------
# Sağlık / izleme
# ---------------------------------------------------------------------------

_SAGLIKSIZ_DURUMLAR = {"bayat", "hata", "birikiyor"}
_UYARI_DURUMLARI = {"cdn_yedegi", "ornek_veri", "veri_yok", "son_deneme_basarisiz", "gecikmis", "yok", "eski"}
_KUYRUK_BIRIKME_ESIGI_SANIYE = 120


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
    indirmeler = canli_indirme_durumu()
    kayitlar = kaynak_durumlarini_getir([canli_durum_anahtari("gfs")])
    if not kayitlar:
        return {"durum": "kullanilmadi", "indirmeler": indirmeler}
    kayit = kayitlar[0]
    son_basari = kayit["son_basari_zamani"]
    yas_saat = (datetime.now(UTC) - son_basari).total_seconds() / 3600 if son_basari else None
    if kayit["ardisik_hata_sayisi"]:
        durum = "hata"
    elif yas_saat is None or yas_saat > config.SAGLIK_GFS_BOSTA_SAAT:
        durum = "bayat" if config.CANLI_ISITMA_SAAT > 0 else "bosta"
    else:
        durum = "tamam"
    return {
        "durum": durum,
        "son_basari_yas_saat": round(yas_saat, 1) if yas_saat is not None else None,
        "son_basarili_indirme": son_basari,
        "son_deneme": kayit["son_deneme_zamani"],
        "ardisik_hata_sayisi": kayit["ardisik_hata_sayisi"],
        "son_hata": kayit["son_hata"],
        "devre_kesici_kalan_saniye": round(devre_kalan_saniye(kayit)),
        "indirmeler": indirmeler,
    }


def _kisitli_saha_kontrolu():
    simdi = datetime.now(UTC)
    sahalar = gecerli_kisitli_sahalari_getir(simdi, simdi)
    ornek = sum(s["kaynak"] == ORNEK_KAYNAK for s in sahalar)
    durum = "veri_yok" if not sahalar else ("ornek_veri" if ornek == len(sahalar) else "tamam")
    sonuc = {"aktif_saha_sayisi": len(sahalar), "ornek_saha_sayisi": ornek}
    if config.OPENAIP_OTOMATIK_GUNCELLEME_SAAT > 0:
        # Otomatik yenileme açıkken iki aralık boyunca başarı yoksa kısıtlı
        # saha verisi bayat sayılır (yeni ilan edilen yasak saha A*'a girmez).
        kayitlar = kaynak_durumlarini_getir([OPENAIP_DURUM_ANAHTARI])
        son_basari = kayitlar[0]["son_basari_zamani"] if kayitlar else None
        sonuc["openaip_son_basari"] = son_basari
        if kayitlar and kayitlar[0]["son_hata"]:
            sonuc["son_hata"] = kayitlar[0]["son_hata"]
        esik = timedelta(hours=2 * config.OPENAIP_OTOMATIK_GUNCELLEME_SAAT)
        if son_basari is None or simdi - son_basari > esik:
            durum = "bayat"
    return {"durum": durum, **sonuc}


async def _ml_gece_isi_kontrolu():
    """Gece işi karar destek çıktısını etkilemez; sorunları 'uyarilar'a düşer."""
    if not config.ML_GECE_ISI_SAATI:
        return {"durum": "kapali"}
    gorevler = await son_gorevler("ml_veri")
    son_bitmis = next((g for g in gorevler if g["durum"] not in AKTIF_DURUMLAR), None)
    son_basarili = next((g["bitis_zamani"] for g in gorevler if g["durum"] == "tamamlandi"), None)
    aktif = any(g["durum"] in AKTIF_DURUMLAR for g in gorevler)
    if son_bitmis is not None and son_bitmis["durum"] != "tamamlandi" and not aktif:
        durum = "son_deneme_basarisiz"
    elif not aktif and (
        son_basarili is None or datetime.now(UTC) - son_basarili > timedelta(hours=config.SAGLIK_ML_GECE_MAKS_YAS_SAAT)
    ):
        durum = "gecikmis"
    else:
        durum = "tamam"
    return {
        "durum": durum,
        "calisiyor": aktif,
        "son_deneme_durumu": son_bitmis["durum"] if son_bitmis else None,
        "son_basarili_bitis": son_basarili,
    }


def _yedek_kontrolu():
    """docker-compose'un 'yedek' servisinin dosyaları (API'ye salt okunur bağlı)."""
    if not os.path.isdir(config.YEDEK_KLASORU):
        return {"durum": "kapali"}
    simdi = time.time()
    sonuc, durum = {}, "tamam"
    for ad, desen in (("veritabani", "turbulans_*.dump"), ("dosyalar", "dosyalar_*.tar.gz")):
        dosyalar = glob.glob(os.path.join(config.YEDEK_KLASORU, desen))
        if not dosyalar:
            sonuc[f"{ad}_yas_saat"] = None
            durum = "yok"
            continue
        yas = (simdi - max(os.path.getmtime(d) for d in dosyalar)) / 3600
        sonuc[f"{ad}_yas_saat"] = round(yas, 1)
        if yas > config.SAGLIK_YEDEK_MAKS_YAS_SAAT and durum == "tamam":
            durum = "eski"
    return {"durum": durum, **sonuc}


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
    kısıtlı saha) 'uyarilar'da listelenir. Anahtarsız raporda kontrol başına
    yalnızca durum vardır; zamanlar, sayılar, sürümler ve hata metinleri sadece
    ayrıntılı (API anahtarlı) raporda yer alır."""
    kontroller = {
        "sigmet": await _kontrol_et(_sigmet_kontrolu),
        "canli_gfs": await _kontrol_et(_canli_gfs_kontrolu),
        "gorev_kuyrugu": await _kontrol_et(_gorev_kuyrugu_kontrolu),
        "kisitli_sahalar": await _kontrol_et(_kisitli_saha_kontrolu),
        "ml_gece_isi": await _kontrol_et(_ml_gece_isi_kontrolu),
        "yedek": await _kontrol_et(_yedek_kontrolu),
        "kup_onbellegi": {"durum": "tamam", **onbellek_durumu()},
        "statik_dosyalar": yerel_kutuphane_durumu(),
        "fir_sinirlari": {"durum": "tamam" if await asyncio.to_thread(fir_verisi_var_mi) else "veri_yok"},
    }
    if not ayrintili:
        kontroller = {ad: {"durum": k["durum"]} for ad, k in kontroller.items()}
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


@v1.get("/denetim", dependencies=_YONETICI, response_model=list[DenetimKaydiYaniti], tags=["Sistem"])
async def denetim_kayitlari(
    limit: int = Query(default=100, ge=1, le=1000),
    kimlik: str | None = Query(default=None, max_length=64, description="Sadece bu anahtar kimliğinin kayıtları"),
    baslangic: datetime | None = Query(default=None, description="Bu zamandan sonraki kayıtlar"),
):
    """Değiştirici isteklerin (POST/PUT/PATCH/DELETE) denetim kaydı, en yeni
    önce: kim (anahtar kimliği), hangi rolle, ne yaptı, sonuç kodu. Reddedilen
    denemeler 'kimliksiz' görünür. Sorgu dizesindeki webhook URL'si maskelenir."""
    return await denetim_kayitlarini_listele(limit, kimlik, baslangic)


@v1.get("/sistem/durum", dependencies=_YONETICI, response_model=SistemDurumuYaniti, tags=["Sistem"])
async def sistem_durumu():
    """/saglik?derin=true ile aynı rapor, ek olarak kaynak başına son hata
    metinleriyle (API anahtarı gerektirir -- dış servis hata ayrıntıları
    herkese açık uçta gösterilmez)."""
    if not await _veritabani_erisilebilir_mi():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Veritabanına şu anda ulaşılamıyor.")
    return await _saglik_raporu(ayrintili=True)


async def _anlik_metrikleri_guncelle():
    try:
        kuyruk = await kuyruk_durumu()
        metrikler.GOREV_KUYRUGU.labels("kuyrukta").set(kuyruk["kuyrukta"])
        metrikler.GOREV_KUYRUGU.labels("calisiyor").set(kuyruk["calisiyor"])
        metrikler.KUYRUK_EN_ESKI_BEKLEME.set(kuyruk["en_eski_bekleme_saniye"] or 0)
    except Exception as hata:
        _logger.warning("Kuyruk metrikleri okunamadı: %s", dostane_hata_mesaji(hata))
    try:
        son = await asyncio.to_thread(son_guncelleme_zamani)
        metrikler.SIGMET_YASI.set((datetime.now(UTC) - son).total_seconds() if son else float("nan"))
    except Exception as hata:
        _logger.warning("SIGMET yaşı metriği okunamadı: %s", dostane_hata_mesaji(hata))
    indirmeler = canli_indirme_durumu()
    metrikler.CANLI_INDIRME.labels("calisiyor").set(indirmeler["calisiyor"])
    metrikler.CANLI_INDIRME.labels("bekliyor").set(indirmeler["bekliyor"])
    metrikler.WS_BAGLANTILARI.set(len(baglanti_yoneticisi.baglantilar))


@app.get("/metrics", include_in_schema=False)
async def prometheus_metrikleri(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    authorization: str | None = Header(default=None),
):
    """Prometheus metin biçimi. Yönetici anahtarı ister: X-API-Key ya da
    'Authorization: Bearer <anahtar>' (Prometheus scrape_config'in
    authorization ayarı). Metrikler iç yapı bilgisi taşıdığı için açık değil."""
    verilen = x_api_key
    if not verilen and authorization and authorization.lower().startswith("bearer "):
        verilen = authorization[7:].strip()
    cozum = _anahtari_coz(verilen) if os.environ.get("API_ANAHTARI") else None
    if cozum is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Metrikler için yönetici anahtarı gerekli.")
    if cozum[1] != "yonetici":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Metrikler için yönetici anahtarı gerekli.")
    await _anlik_metrikleri_guncelle()
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


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
    kod, govde = await _derin_saglik_onbellekli()
    return JSONResponse(status_code=kod, content=govde) if kod != 200 else govde


_saglik_onbellegi: dict = {"zaman": None, "sonuc": None}
_saglik_kilitleri: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Lock]" = weakref.WeakKeyDictionary()


async def _derin_saglik_onbellekli():
    """Anahtarsız /saglik?derin=true her çağrıda veritabanına gidip tüm aktif
    kısıtlı sahaları çekiyordu (dışarıdan ucuz bir yük büyütme yüzeyi). Sonuç
    SAGLIK_ONBELLEK_SANIYE boyunca yeniden kullanılır; aynı anda gelen istekler
    tek bir hesaplamayı bekler (kilit). /sistem/durum (yönetici) önbelleksizdir."""
    sure = config.SAGLIK_ONBELLEK_SANIYE

    def taze_mi():
        zaman = _saglik_onbellegi["zaman"]
        return zaman is not None and time.monotonic() - zaman < sure

    if taze_mi():
        return _saglik_onbellegi["sonuc"]
    dongu = asyncio.get_running_loop()
    kilit = _saglik_kilitleri.get(dongu)
    if kilit is None:
        kilit = _saglik_kilitleri[dongu] = asyncio.Lock()
    async with kilit:
        if taze_mi():
            return _saglik_onbellegi["sonuc"]
        if await _veritabani_erisilebilir_mi():
            sonuc = (200, await _saglik_raporu(ayrintili=False))
        else:
            sonuc = (503, {"durum": "bozulmus", "veritabani": "erisilemiyor"})
        if sure > 0:
            _saglik_onbellegi.update(zaman=time.monotonic(), sonuc=sonuc)
        return sonuc


app.include_router(v1)
# Alt router'lar kendi /api/v1 öneki ve anahtar korumasıyla doğrudan uygulamaya bağlanır (önek
# include sırasında verilirse FastAPI metrik etiketindeki route şablonunu öneksiz bırakıyor).
for _yollar in (ucuslar, analiz, hava_sahasi, ml):
    app.include_router(_yollar.router)
