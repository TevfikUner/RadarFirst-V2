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
import hashlib
import hmac
import inspect
import json
import os
import secrets
import time
import weakref
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, timedelta
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
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from turbulans_radar import config, loglama
from turbulans_radar.analiz.sanal_pirep_hatti import izden_sanal_pirep_uret
from turbulans_radar.api import metrikler
from turbulans_radar.api.rota_onbellegi import PaylasimliRotaOnbellegi, RotaOnbellegi
from turbulans_radar.api.semalar import (
    BacktestListesiYaniti,
    BacktestSonucuYaniti,
    CanliVeriIstegi,
    DenetimKaydiYaniti,
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
    SanalPirepIzYaniti,
    SanalPirepListesiYaniti,
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
from turbulans_radar.depo.dagitik_kilit import LiderKilidi
from turbulans_radar.depo.denetim import denetim_kaydet, denetim_kayitlarini_listele
from turbulans_radar.depo.gorev_deposu import (
    AKTIF_DURUMLAR,
    aktif_gorev_var_mi,
    eski_gorevleri_temizle,
    gorev_durumlari,
    gorev_getir,
    gorev_olustur,
    kuyruk_durumu,
    son_gorevler,
)
from turbulans_radar.depo.hiz_siniri import istegi_say
from turbulans_radar.depo.kaynak_durumu import kaynak_durumlarini_getir
from turbulans_radar.depo.kup_katalogu import katalogu_listele, yerel_kupleri_katalogla
from turbulans_radar.depo.sanal_pirep_deposu import olaylari_getir
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
from turbulans_radar.fizik.sanal_pirep import kume_ozeti, olaylari_kumele
from turbulans_radar.fizik.turbulans_indeksleri import TI1_GUVENILIRLIK_NOTU
from turbulans_radar.hata_yardimcisi import dostane_hata_mesaji
from turbulans_radar.isci.gorev_iscisi import BILDIRIM_KANALI, GorevIscisi, bildirim_yayinla
from turbulans_radar.ml.turbulans_ml_modeli import (
    model_bilgisini_yukle,
    model_kullanilabilir_mi,
    model_versiyonlarini_listele,
    ozelliklerden_risk_tahmin_et,
    ozellikleri_cikar,
    risk_durumlarini_hesapla,
    versiyona_geri_don,
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
from turbulans_radar.veri.fir_sinirlari import fir_verisi_var_mi
from turbulans_radar.veri.kisitli_saha_saglayici import (
    ORNEK_KAYNAK,
    gecerli_kisitli_sahalari_getir,
    geojson_ice_aktar,
    kisitli_sahayi_sil,
    ornek_veriyi_yukle,
)
from turbulans_radar.veri.openaip_saglayici import OPENAIP_DURUM_ANAHTARI
from turbulans_radar.veri.sigmet_saglayici import (
    gecerli_sigmetleri_getir,
    kacinilacak_tehlikeler,
    kaynak_saglik_durumlari,
    sigmetleri_guncelle,
    son_guncelleme_zamani,
)
from turbulans_radar.veri.veri_saglayicilari import canli_durum_anahtari, canli_indirme_durumu
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


async def _gfs_isitma_adimi(aralik_saniye, simdi: datetime | None = None) -> str | None:
    """Son aralıkta canlı veri görevi yoksa CANLI_ISITMA_KUTUSU için GFS küpünü
    kuyruğa alır: sağlayıcı kesintisi ilk kullanıcı isteğinden önce fark edilir."""
    simdi = simdi or datetime.now(UTC)
    if await gorev_durumlari("canli_veri", simdi - timedelta(seconds=aralik_saniye)):
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
    gorev_id = await _gorev_olustur("ml_veri", parametreler=MlGeceIsiIstegi().model_dump())
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
            await _rota_onbellegini_temizle()
            if ozet["kaynak_hatalari"]:
                _logger.error("SIGMET kaynak hataları (mevcut kayıtlar korundu): %s", ozet["kaynak_hatalari"])
            _logger.info("SIGMET'ler yenilendi: %s", ozet)
        except Exception as hata:
            _logger.warning("Periyodik SIGMET yenilemesi başarısız: %s", dostane_hata_mesaji(hata))
        await asyncio.sleep(aralik_saniye)


def _yalnizca_yerel_yayin_mi() -> bool:
    return os.environ.get("API_YAYIN_ADRESI", "").strip() in ("", "127.0.0.1", "localhost", "::1")


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


# Kullanılmış biletler (imza -> bitiş): süreç başınadır; WEB_CONCURRENCY>1 iken bir
# bilet en fazla süreç sayısı kadar, yine de yalnızca 60 sn içinde kullanılabilir.
_kullanilmis_biletler: dict[str, int] = {}


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


def ws_biletini_kullan(bilet: str | None) -> bool:
    """Geçerli ve daha önce kullanılmamışsa bileti tüketir."""
    if not ws_bileti_gecerli_mi(bilet):
        return False
    simdi = time.time()
    for imza, bitis in list(_kullanilmis_biletler.items()):
        if bitis < simdi:
            del _kullanilmis_biletler[imza]
    bitis, _, _, imza = bilet.split(".")
    if imza in _kullanilmis_biletler:
        return False
    _kullanilmis_biletler[imza] = int(bitis)
    return True


# ---------------------------------------------------------------------------
# Basit bellek-içi hız sınırlama (sadece analiz tetikleme uç noktaları için
# -- OpenSky'yi dış dünyadan gelen aşırı istekle yormamak amacıyla)
# ---------------------------------------------------------------------------

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


# OpenSky callsign'ları en fazla 8 karakter, harf/rakamdan oluşur (bkz.
# veri_yukleme.py'deki ljust(8) notu). Bu desen hem anlamsız girdiyi erkenden
# 422 ile reddeder hem de SQL enjeksiyonuna karşı ikinci bir savunma katmanı
# sağlar (birincil savunma: veri_yukleme.py artık parametreli sorgu kullanıyor).
_UCUS_NUMARASI_DESENI = r"^[A-Za-z0-9]{1,8}$"


def _tarihi_dogrula(deger: str) -> str:
    try:
        date.fromisoformat(deger)
    except ValueError:
        raise ValueError("tarih 'YYYY-MM-DD' formatında geçerli bir tarih olmalı.") from None
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


class SanalPirepNoktasi(RotaNoktasiGirdisi):
    baro_irtifa_m: float | None = Field(default=None, ge=-500, le=20000, description="Barometrik irtifa (m), öncelikli")
    dikey_hiz_ms: float | None = Field(default=None, ge=-150, le=150, description="Düşey hız (m/s)")


class SanalPirepIzIstegi(BaseModel):
    ucus_numarasi: str | None = Field(default=None, pattern=_UCUS_NUMARASI_DESENI)
    icao24: str | None = Field(default=None, pattern=r"^[0-9a-fA-F]{6}$")
    noktalar: list[SanalPirepNoktasi] = Field(min_length=3, max_length=config.MAKS_STATE_VECTOR_SATIRI)


class TopluAnalizIstegi(BaseModel):
    ucuslar: list[UcusAnalizIstegi] = Field(max_length=500)
    bildirim_webhook_url: str | None = None

    @field_validator("bildirim_webhook_url")
    @classmethod
    def _webhook_gecerli_mi(cls, deger):
        return _webhook_url_dogrula(deger)


class MlGeceIsiIstegi(BaseModel):
    iem_guncelle: bool = True
    # Şema ortamdan bağımsız sabit üst sınır; fazlası ml_veri_hatti'nda kurulumun
    # ML_GECE_MAKS_CDS_ISTEK değerine indirilir (ayrıca günlük CDS tavanı geçerli).
    maks_cds_istek: int | None = Field(default=None, ge=1, le=150)
    ardindan_egitim: bool = True


class MlDurumYaniti(BaseModel):
    ornekler: dict[str, int]
    eslesmis_gun_sayisi: int
    egitim_icin_gereken_gun: int
    egitime_hazir: bool
    cds_bugun_kullanilan: int
    cds_gunluk_sinir: int
    veri_bugun_mb: float | None = None
    veri_gunluk_butce_mb: float | None = None
    iem_imleci: str | None = None
    aktif_model: dict | None = None
    son_gorevler: list[dict]
    pencere_deposu: dict | None = None
    gece_isi_saati_utc: str | None = None


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
    await _hiz_sinirini_kontrol_et(
        f"rota_hesabi:{_istemci_kimligi(request, rol)}", maks=config.ROTA_HESABI_DAKIKADA_MAKS, pencere_saniye=60
    )
    onbellek_anahtari = istek.model_dump_json()
    onceki, damga = await _rota_onbellekten_al(onbellek_anahtari)
    if onceki is not None:
        metrikler.ROTA_ONBELLEGI.labels("isabet").inc()
        return onceki
    metrikler.ROTA_ONBELLEGI.labels("iska").inc()
    async with _agir_hesap_yuvasi():
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
            )
        except (AtsAgiKullanilamazHatasi, AtsAgiHatasi, AntimeridyenHatasi) as hata:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(hata)) from None
        metrikler.ROTA_HESABI_SURESI.observe(time.monotonic() - hesap_baslangici)
    sonuc["czml"] = simulasyonu_czml_e_cevir(sonuc)
    await _rota_onbellege_koy(onbellek_anahtari, sonuc, damga)
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

        return {
            "kapsam_icinde_mi": True,
            "ti1_indeksi": float(ti1),
            "ti1_riskli_mi": bool(ti1 >= config.TI1_ESIK_ORTA_SIDDETLI),
            "ti1_guvenilirlik_notu": TI1_GUVENILIRLIK_NOTU,
            "ml_riski_var_mi": (ml_olasilik >= config.ML_KARAR_ESIGI) if ml_olasilik is not None else None,
            "ml_olasilik": ml_olasilik,
            "ml_risk_durumu": durumlar[0] if durumlar is not None else None,
            "ml_konformal_hedef_kapsama": (1 - konformal["alfa"]) if konformal else None,
            "aciklama": (
                "Fizik (Ellrod TI1) ve ML tahminleri hesaplandı."
                if ml_olasilik is not None
                else f"Fizik (Ellrod TI1) hesaplandı; {ml_notu or 'ML tahmini üretilemedi.'}"
            ),
        }

    await _hiz_sinirini_kontrol_et(
        f"tahmin:{_istemci_kimligi(request, rol)}", maks=config.TAHMIN_DAKIKADA_MAKS, pencere_saniye=60
    )
    async with _agir_hesap_yuvasi():
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
    kullanimda, uyari = model_kullanilabilir_mi(bilgi, model_var_mi=True)
    return {"egitildi_mi": True, **bilgi, "kullanimda": kullanimda, "uyari": uyari}


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
async def turbulans_model_versiyonunu_aktiflestir(
    versiyon_id: str, request: Request, rol: str = Depends(api_anahtarini_dogrula)
):
    """Geçmiş bir model versiyonunu, YENİDEN EĞİTİM GEREKMEDEN aktif model
    yapar (rollback) -- örn. yeni bir eğitim çalıştırması beklenenden kötü
    çıkarsa bir önceki versiyona dönmek için. Bilinmeyen bir versiyon_id
    404 döner."""
    await _hiz_sinirini_kontrol_et(f"model_aktiflestir:{_istemci_kimligi(request, rol)}")
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
    request: Request,
    ucus_numarasi_arama: str | None = Query(default=None, max_length=8, description="Uçuş numarasında kısmi arama"),
    baslangic_tarih: date | None = Query(default=None),
    bitis_tarih: date | None = Query(default=None),
    rol: str = Depends(api_anahtarini_dogrula),
):
    """Filtreye uyan TÜM uçuşları (CASCADE ile ölçümleriyle) siler. En az
    bir filtre ZORUNLUDUR -- filtresiz bir çağrı, tüm veritabanını
    YANLIŞLIKLA boşaltabileceği için kasıtlı olarak 400 ile reddedilir
    (tek tek silme için bkz. DELETE /ucuslar/{ucus_numarasi}/{tarih})."""
    await _hiz_sinirini_kontrol_et(f"silme:{_istemci_kimligi(request, rol)}")
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
    request: Request,
    ucus_numarasi: str = Path(pattern=_UCUS_NUMARASI_DESENI),
    tarih: date = Path(...),
    rol: str = Depends(api_anahtarini_dogrula),
):
    """Kayıtlı bir uçuşu (CASCADE ile edr_olcumleri dahil) siler. Aynı
    uçuş/tarih tekrar analiz edilmek istenirse zaten otomatik üzerine
    yazılır (bkz. ucus_ve_olcumleri_kaydet) -- bu uç nokta, bir daha analiz
    edilmeyecek kaydı veritabanından tamamen kaldırmak içindir."""
    await _hiz_sinirini_kontrol_et(f"silme:{_istemci_kimligi(request, rol)}")
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
async def ucus_analizi_baslat(istek: UcusAnalizIstegi, request: Request, rol: str = Depends(api_anahtarini_dogrula)):
    await _hiz_sinirini_kontrol_et(f"tek_ucus:{_istemci_kimligi(request, rol)}")
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
async def rota_analizi_baslat(istek: RotaAnalizIstegi, request: Request, rol: str = Depends(api_anahtarini_dogrula)):
    """
    OpenSky'a BAĞLANMADAN, dışarıdan alınmış bir ADS-B izini (başka bir
    izleme servisi, uçuş kayıt cihazı vb.) analiz eder: aynı eşleştirme,
    PostgreSQL kaydı, WebSocket uyarısı ve webhook akışı. OpenSky'ın tarayıcı
    tabanlı OAuth2 girişini gerektirmediği için sunucu/Docker ortamında da
    çalışır. Tarih, ilk noktanın UTC gününden türetilir; sonuç
    GET /ucuslar/{ucus_numarasi}/{tarih} ile okunur.
    """
    await _hiz_sinirini_kontrol_et(f"rota:{_istemci_kimligi(request, rol)}")
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
async def toplu_analiz_baslat(istek: TopluAnalizIstegi, request: Request, rol: str = Depends(api_anahtarini_dogrula)):
    await _hiz_sinirini_kontrol_et(f"toplu:{_istemci_kimligi(request, rol)}")
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
async def sigmetleri_yenile(request: Request, rol: str = Depends(api_anahtarini_dogrula)):
    """AWC'den (aviationweather.gov: ABD `airsigmet` + uluslararası `isigmet`)
    canlı SIGMET'leri çekip veritabanını günceller; akıştan düşen (iptal
    edilen) SIGMET'lerin geçerliliği sona erdirilir. n8n/cron'un periyodik
    (örn. 10-15 dk) tetiklemesi için -- ya da SIGMET_OTOMATIK_GUNCELLEME_DAKIKA
    ile API'nin kendi zamanlayıcısı kullanılır."""
    await _hiz_sinirini_kontrol_et(f"sigmet:{_istemci_kimligi(request, rol)}")
    try:
        return await asyncio.to_thread(sigmetleri_guncelle)
    finally:
        await _rota_onbellegini_temizle()


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


@v1.get(
    "/sigmet/{sigmet_id}/iwxxm",
    response_class=Response,
    responses={200: {"content": {"application/xml": {}}}},
    tags=["SIGMET"],
)
async def sigmet_iwxxm_disa_aktar(sigmet_id: int = Path(ge=1)):
    """Saklanan SIGMET'in IWXXM 2025-2 XML'i (veri/iwxxm.py). Mesaj
    NON-OPERATIONAL (TEST) işaretlidir: AWC verisinin yeniden kodlamasıdır,
    yetkili MWO yayını değildir. WMO koduna eşlenemeyen olgu 422 döner."""
    from turbulans_radar.veri.iwxxm import IwxxmEslemeHatasi, sigmet_iwxxm
    from turbulans_radar.veri.sigmet_saglayici import sigmet_getir

    bulunan = await asyncio.to_thread(sigmet_getir, sigmet_id)
    if bulunan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SIGMET bulunamadı.")
    try:
        xml = sigmet_iwxxm(*bulunan)
    except IwxxmEslemeHatasi as hata:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(hata)) from None
    return Response(content=xml, media_type="application/xml")


SANAL_PIREP_NOTU = (
    "Sanal PIREP: ADS-B'deki seyir fazı irtifa sapmasıdır; sertifikalı EDR ya da şiddet sınıfı değildir. "
    "Tek uçaklık işaret seviye değişimi ya da otopilot geçişi olabilir; 'dogrulanmis' kümeler en az "
    f"{config.SANAL_PIREP_BILDIRIM_MIN_UCAK} farklı uçağın işaretidir. Karar destek amaçlıdır."
)


class CanliAdsbOturumIstegi(BaseModel):
    """Süreli canlı ADS-B oturumu (adsb.fi / adsb.lol; bkz. veri/canli_adsb.py).
    Boş alanlar config varsayılanıdır; sınırlar sunucuda da zorlanır."""

    sure_dk: float | None = Field(default=None, gt=0, le=60)
    aralik_saniye: float | None = Field(default=None, ge=5, le=29)
    enlem: float | None = Field(default=None, ge=-90, le=90)
    boylam: float | None = Field(default=None, ge=-180, le=180)
    yaricap_nm: float | None = Field(default=None, gt=0, le=250)


@v1.post(
    "/sanal-pirep/canli-oturum",
    dependencies=_YONETICI,
    status_code=status.HTTP_202_ACCEPTED,
    response_model=GorevBaslatildiYaniti,
    tags=["Sanal PIREP"],
)
async def canli_adsb_oturumu_baslat(
    request: Request, istek: CanliAdsbOturumIstegi | None = None, rol: str = Depends(api_anahtarini_dogrula)
):
    """Bölgeyi kısa aralıkla sorgulayıp izleri sanal PIREP hattına veren süreli
    oturumu işçi kuyruğuna alır. CANLI_ADSB_ETKIN kapalıysa 409. Veri:
    adsb.fi (kişisel/ticari olmayan kullanım, atıf zorunlu) ve ADSB.lol (ODbL)."""
    if not config.CANLI_ADSB_ETKIN:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Canlı ADS-B kapalı (CANLI_ADSB_ETKIN).")
    await _hiz_sinirini_kontrol_et(f"canli_adsb:{_istemci_kimligi(request, rol)}", maks=2, pencere_saniye=3600)
    if await aktif_gorev_var_mi("canli_adsb"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Bir canlı ADS-B oturumu zaten sürüyor.")
    return _kuyruga_alindi(
        await _gorev_olustur("canli_adsb", parametreler=(istek or CanliAdsbOturumIstegi()).model_dump())
    )


@v1.post(
    "/sanal-pirep/iz",
    dependencies=_YONETICI,
    response_model=SanalPirepIzYaniti,
    tags=["Sanal PIREP"],
)
async def sanal_pirep_izi(istek: SanalPirepIzIstegi, request: Request, rol: str = Depends(api_anahtarini_dogrula)):
    """Havayolunun kendi ADS-B/ACARS beslemesinden bir uçağın son izi (canlı
    kullanım; OpenSky'a bağlanmaz). Seyirdeki irtifa sapmaları kaydedilir;
    yakınında başka uçakların da olayı varsa /ws/uyarilar'a 'sanal_pirep'
    mesajı gider. İz, atanmış seviyeyi kurabilmek için en az birkaç dakikalık
    seyir içermelidir (config.SANAL_PIREP_SEVIYE_PENCERESI_SANIYE)."""
    await _hiz_sinirini_kontrol_et(
        f"sanal_pirep:{_istemci_kimligi(request, rol)}", maks=config.SANAL_PIREP_IZ_DAKIKADA_MAKS, pencere_saniye=60
    )
    iz_df = pd.DataFrame(
        {
            "zaman": [n.zaman for n in istek.noktalar],
            "enlem": [n.enlem for n in istek.noktalar],
            "boylam": [n.boylam for n in istek.noktalar],
            "geo_irtifa_m": [n.irtifa_m for n in istek.noktalar],
            "baro_irtifa_m": [n.baro_irtifa_m for n in istek.noktalar],
            "dikey_hiz": [n.dikey_hiz_ms for n in istek.noktalar],
        }
    )
    for sutun in ("geo_irtifa_m", "baro_irtifa_m", "dikey_hiz"):
        iz_df[sutun] = pd.to_numeric(iz_df[sutun], errors="coerce")
    if iz_df[["geo_irtifa_m", "baro_irtifa_m"]].isna().all(axis=None):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="İzde irtifa yok (irtifa_m ya da baro_irtifa_m)."
        )
    async with _agir_hesap_yuvasi():
        return await asyncio.to_thread(
            izden_sanal_pirep_uret,
            iz_df,
            "canli_iz",
            bildirim_yayinla,
            icao24=istek.icao24.lower() if istek.icao24 else None,
            ucus_numarasi=istek.ucus_numarasi,
        )


@v1.get("/sanal-pirep", response_model=SanalPirepListesiYaniti, tags=["Sanal PIREP"])
async def sanal_pirepleri_listele(
    son_saat: float = Query(default=3.0, gt=0, le=24 * 30),
    bitis: datetime | None = Query(default=None, description="Pencerenin sonu (UTC); verilmezse şimdi"),
    enlem_min: float = Query(default=-90, ge=-90, le=90),
    enlem_maks: float = Query(default=90, ge=-90, le=90),
    boylam_min: float = Query(default=-180, ge=-180, le=180),
    boylam_maks: float = Query(default=180, ge=-180, le=180),
    sadece_dogrulanmis: bool = Query(default=False),
):
    """Koridordaki sanal PIREP'ler ve uzay-zaman kümeleri (dispeçer/önyüz için)."""
    if bitis is None:
        bitis = datetime.now(UTC)
    else:
        bitis = bitis.replace(tzinfo=UTC) if bitis.tzinfo is None else bitis.astimezone(UTC)

    def _hesapla():
        olaylar = olaylari_getir(
            bitis - timedelta(hours=son_saat), bitis, enlem_min, enlem_maks, boylam_min, boylam_maks
        )
        kumelenmis = olaylari_kumele(olaylar)
        kumeler = kume_ozeti(kumelenmis)
        if sadece_dogrulanmis:
            gecerli = {k["kume"] for k in kumeler if k["dogrulanmis"]}
            kumeler = [k for k in kumeler if k["dogrulanmis"]]
            kumelenmis = kumelenmis[kumelenmis["kume"].isin(gecerli)]
        olay_kayitlari = kumelenmis.drop(columns=["kume"], errors="ignore").astype(object)
        olay_kayitlari = olay_kayitlari.where(olay_kayitlari.notna(), None).to_dict(orient="records")
        return {"kumeler": kumeler, "olaylar": olay_kayitlari, "aciklama": SANAL_PIREP_NOTU}

    return await asyncio.to_thread(_hesapla)


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
    request: Request,
    kaynak: str = Query(min_length=1, max_length=32, pattern=r"^[a-z0-9_\-]+$"),
    eskileri_kaldir: bool = Query(default=False, description="Bu kaynağın yeni veride olmayan kayıtlarını sil"),
    rol: str = Depends(api_anahtarini_dogrula),
):
    """GeoJSON FeatureCollection içe aktarır (Polygon/MultiPolygon; properties:
    kimlik, ad, tur, taban_ft, tavan_ft, baslangic, bitis, aciklama). Örn. n8n
    bir NOTAM akışından geçici kısıtları `kaynak=notam` ile iter. Aynı
    kaynak:kimlik ikinci kez gelirse güncellenir."""
    await _hiz_sinirini_kontrol_et(f"kisitli_saha:{_istemci_kimligi(request, rol)}")
    try:
        return await asyncio.to_thread(geojson_ice_aktar, geojson, kaynak, eskileri_kaldir)
    finally:
        await _rota_onbellegini_temizle()


@v1.post(
    "/kisitli-sahalar/openaip",
    dependencies=_YONETICI,
    status_code=status.HTTP_202_ACCEPTED,
    response_model=GorevBaslatildiYaniti,
    tags=["Kısıtlı Hava Sahaları"],
)
async def openaip_sahalarini_yenile(
    request: Request,
    ulke: list[str] | None = Query(default=None, description="ISO ülke kodu(ları)"),
    rol: str = Depends(api_anahtarini_dogrula),
):
    """Gerçek kısıtlı/yasak sahaları openAIP'ten çekip 'openaip' kaynağını tam
    yeniler (OPENAIP_API_ANAHTARI gerekir; AIRAC döngüsünde n8n tetikleyebilir).
    Kuyruğa girer; sonuç GET /analiz/durum/{gorev_id}."""
    await _hiz_sinirini_kontrol_et(f"kisitli_saha:{_istemci_kimligi(request, rol)}")
    return _kuyruga_alindi(await _gorev_olustur("openaip", parametreler={"ulkeler": ulke}))


@v1.post(
    "/ml/gece-isi",
    dependencies=_YONETICI,
    status_code=status.HTTP_202_ACCEPTED,
    response_model=GorevBaslatildiYaniti,
    tags=["Makine Öğrenmesi"],
)
async def ml_gece_isini_baslat(
    request: Request, istek: MlGeceIsiIstegi | None = None, rol: str = Depends(api_anahtarini_dogrula)
):
    """n8n'in gecelik tek tetikleyicisi: yeni IEM PIREP'lerini çeker, bekleyen
    PIREP'leri CDS'ten ERA5 ile eşleştirir (gecelik ML_GECE_MAKS_CDS_ISTEK ve
    günlük CDS_GUNLUK_MAKS_ISTEK sınırlarıyla), ardından aday model eğitir;
    aday yalnızca holdout'ta aktif modeli geçerse aktifleştirilir. Aynı anda
    ikinci bir ML işi kuyruğa alınmaz (409)."""
    await _hiz_sinirini_kontrol_et(f"ml_gece:{_istemci_kimligi(request, rol)}")
    if await aktif_gorev_var_mi("ml_veri") or await aktif_gorev_var_mi("ml_egitim"):
        raise HTTPException(status.HTTP_409_CONFLICT, "Bir ML gece işi zaten kuyrukta ya da çalışıyor.")
    parametreler = (istek or MlGeceIsiIstegi()).model_dump()
    return _kuyruga_alindi(await _gorev_olustur("ml_veri", parametreler=parametreler))


@v1.get("/ml/durum", response_model=MlDurumYaniti, tags=["Makine Öğrenmesi"])
async def ml_durumu():
    """ML veri hattının ve gece işinin durumu: örnek sayıları, eşleşmiş gün
    sayısı (eğitim ML_MIN_GUN'dan önce yapılmaz), bugünkü CDS kullanımı, IEM
    imleci, aktif model sürümü ve son ml_veri/ml_egitim görevleri."""
    from turbulans_radar.ml.ml_veri_hatti import ml_durum_ozeti

    return await asyncio.to_thread(ml_durum_ozeti)


@v1.delete(
    "/kisitli-sahalar/{dis_kimlik}",
    dependencies=_YONETICI,
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Kısıtlı Hava Sahaları"],
)
async def kisitli_saha_sil(
    request: Request, dis_kimlik: str = Path(max_length=128), rol: str = Depends(api_anahtarini_dogrula)
):
    await _hiz_sinirini_kontrol_et(f"kisitli_saha:{_istemci_kimligi(request, rol)}")
    silindi_mi = await asyncio.to_thread(kisitli_sahayi_sil, dis_kimlik)
    await _rota_onbellegini_temizle()
    if not silindi_mi:
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
async def canli_veri_hazirla(istek: CanliVeriIstegi, request: Request, rol: str = Depends(api_anahtarini_dogrula)):
    """Verilen bölge/zaman için canlı NOAA GFS küpünü arka planda hazırlar
    (katalogda taze bir küp varsa onu kullanır, yoksa indirir). Yavaş ağda
    indirme dakikalar sürebildiği için istek beklemez: 202 + gorev_id döner,
    küp özeti GET /analiz/durum/{gorev_id} yanıtının 'ozet' alanındadır."""
    await _hiz_sinirini_kontrol_et(f"canli_veri:{_istemci_kimligi(request, rol)}")
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
    async with _agir_hesap_yuvasi():
        return await asyncio.to_thread(ucus_backtest_et, ucus_numarasi, tarih.isoformat())


@v1.post(
    "/backtest/toplu",
    dependencies=_YONETICI,
    status_code=status.HTTP_202_ACCEPTED,
    response_model=GorevBaslatildiYaniti,
    tags=["Backtest"],
)
async def toplu_backtest_baslat(
    request: Request,
    limit: int = Query(default=20, ge=1, le=200),
    yenile: bool = Query(default=False),
    bildirim_webhook_url: str | None = Query(default=None),
    rol: str = Depends(api_anahtarini_dogrula),
):
    """Henüz backtest'i olmayan uçuşları arka planda karşılaştırır (örn. n8n'in
    gece tetiklemesi); yenile=true mevcut backtest'leri de en eskiden başlayarak
    yeniden hesaplar (algoritma değişince bayat sonuç kalmasın). Sonuç
    /analiz/durum/{gorev_id} ve webhook ile alınır."""
    await _hiz_sinirini_kontrol_et(f"backtest:{_istemci_kimligi(request, rol)}")
    try:
        webhook = _webhook_url_dogrula(bildirim_webhook_url)
    except ValueError as hata:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(hata)) from hata
    gorev_id = await _gorev_olustur("backtest", parametreler={"limit": limit, "yenile": yenile}, webhook_url=webhook)
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
