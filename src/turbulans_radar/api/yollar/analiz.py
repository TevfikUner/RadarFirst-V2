"""/api/v1 analiz, sanal PIREP, canlı ADS-B, hava küpleri ve backtest uç noktaları."""

import asyncio
import os
from datetime import UTC, date, datetime, timedelta

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

import pandas as pd
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Path,
    Query,
    Request,
    status,
)
from pydantic import BaseModel, Field, field_validator

from turbulans_radar import config
from turbulans_radar.analiz.sanal_pirep_hatti import izden_sanal_pirep_uret
from turbulans_radar.api import ortak
from turbulans_radar.api.guvenlik import _YONETICI, api_anahtarini_dogrula
from turbulans_radar.api.semalar import (
    BacktestListesiYaniti,
    BacktestSonucuYaniti,
    CanliVeriIstegi,
    GorevBaslatildiYaniti,
    GorevDurumYaniti,
    HavaDurumuKupuYaniti,
    SanalPirepIzYaniti,
    SanalPirepListesiYaniti,
)
from turbulans_radar.depo.gorev_deposu import (
    aktif_gorev_var_mi,
    gorev_getir,
)
from turbulans_radar.depo.kup_katalogu import katalogu_listele
from turbulans_radar.depo.sanal_pirep_deposu import olaylari_getir
from turbulans_radar.dogrulama.rota_backtest import backtestleri_listele, ucus_backtest_et
from turbulans_radar.fizik.sanal_pirep import kume_ozeti, olaylari_kumele
from turbulans_radar.isci.gorev_iscisi import bildirim_yayinla

# v1 ile aynı: önek ve API anahtarı her uç noktada (bkz. api_servisi.v1).
router = APIRouter(prefix="/api/v1", dependencies=[Depends(api_anahtarini_dogrula)])


class UcusAnalizIstegi(BaseModel):
    ucus_numarasi: str = Field(pattern=ortak._UCUS_NUMARASI_DESENI)
    tarih: str  # YYYY-MM-DD
    bildirim_webhook_url: str | None = None

    @field_validator("tarih")
    @classmethod
    def _tarih_gecerli_mi(cls, deger):
        return ortak._tarihi_dogrula(deger)

    @field_validator("bildirim_webhook_url")
    @classmethod
    def _webhook_gecerli_mi(cls, deger):
        return ortak._webhook_url_dogrula(deger)


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
    ucus_numarasi: str = Field(pattern=ortak._UCUS_NUMARASI_DESENI)
    noktalar: list[RotaNoktasiGirdisi] = Field(min_length=2, max_length=config.MAKS_STATE_VECTOR_SATIRI)
    bildirim_webhook_url: str | None = None

    @field_validator("bildirim_webhook_url")
    @classmethod
    def _webhook_gecerli_mi(cls, deger):
        return ortak._webhook_url_dogrula(deger)


class SanalPirepNoktasi(RotaNoktasiGirdisi):
    baro_irtifa_m: float | None = Field(default=None, ge=-500, le=20000, description="Barometrik irtifa (m), öncelikli")
    dikey_hiz_ms: float | None = Field(default=None, ge=-150, le=150, description="Düşey hız (m/s)")


class SanalPirepIzIstegi(BaseModel):
    ucus_numarasi: str | None = Field(default=None, pattern=ortak._UCUS_NUMARASI_DESENI)
    icao24: str | None = Field(default=None, pattern=r"^[0-9a-fA-F]{6}$")
    noktalar: list[SanalPirepNoktasi] = Field(min_length=3, max_length=config.MAKS_STATE_VECTOR_SATIRI)


class TopluAnalizIstegi(BaseModel):
    ucuslar: list[UcusAnalizIstegi] = Field(max_length=500)
    bildirim_webhook_url: str | None = None

    @field_validator("bildirim_webhook_url")
    @classmethod
    def _webhook_gecerli_mi(cls, deger):
        return ortak._webhook_url_dogrula(deger)


@router.post(
    "/analiz/ucus",
    dependencies=_YONETICI,
    status_code=status.HTTP_202_ACCEPTED,
    response_model=GorevBaslatildiYaniti,
    tags=["Analiz"],
)
async def ucus_analizi_baslat(istek: UcusAnalizIstegi, request: Request, rol: str = Depends(api_anahtarini_dogrula)):
    await ortak._hiz_sinirini_kontrol_et(f"tek_ucus:{ortak._istemci_kimligi(request, rol)}")
    gorev_id = await ortak._gorev_olustur(
        "ucus", ucus_numarasi=istek.ucus_numarasi, tarih=istek.tarih, webhook_url=istek.bildirim_webhook_url
    )
    return ortak._kuyruga_alindi(gorev_id)


@router.post(
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
    await ortak._hiz_sinirini_kontrol_et(f"rota:{ortak._istemci_kimligi(request, rol)}")
    tarih = min(n.zaman for n in istek.noktalar).date().isoformat()
    gorev_id = await ortak._gorev_olustur(
        "rota",
        ucus_numarasi=istek.ucus_numarasi,
        tarih=tarih,
        parametreler={"noktalar": [n.model_dump(mode="json") for n in istek.noktalar]},
        webhook_url=istek.bildirim_webhook_url,
    )
    return ortak._kuyruga_alindi(gorev_id)


@router.post(
    "/analiz/toplu",
    dependencies=_YONETICI,
    status_code=status.HTTP_202_ACCEPTED,
    response_model=GorevBaslatildiYaniti,
    tags=["Analiz"],
)
async def toplu_analiz_baslat(istek: TopluAnalizIstegi, request: Request, rol: str = Depends(api_anahtarini_dogrula)):
    await ortak._hiz_sinirini_kontrol_et(f"toplu:{ortak._istemci_kimligi(request, rol)}")
    if not istek.ucuslar:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="'ucuslar' listesi boş olamaz.")
    gorev_id = await ortak._gorev_olustur(
        "toplu",
        parametreler={"ucuslar": [u.model_dump(exclude={"bildirim_webhook_url"}) for u in istek.ucuslar]},
        webhook_url=istek.bildirim_webhook_url,
    )
    return ortak._kuyruga_alindi(gorev_id)


@router.get("/analiz/durum/{gorev_id}", response_model=GorevDurumYaniti, tags=["Analiz"])
async def analiz_durumu(gorev_id: str):
    """Kuyruktaki uzun işlerin (analiz, toplu analiz, backtest, canlı veri)
    durumu: kuyrukta -> calisiyor -> tamamlandi | basarisiz | hata |
    yarida_kaldi. Sonucu olan işlerde (toplu, backtest, canlı veri) sonuç
    'ozet' alanındadır."""
    gorev = await gorev_getir(gorev_id)
    if gorev is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bilinmeyen gorev_id.")
    return gorev


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


@router.post(
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
    await ortak._hiz_sinirini_kontrol_et(
        f"canli_adsb:{ortak._istemci_kimligi(request, rol)}", maks=2, pencere_saniye=3600
    )
    if await aktif_gorev_var_mi("canli_adsb"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Bir canlı ADS-B oturumu zaten sürüyor.")
    return ortak._kuyruga_alindi(
        await ortak._gorev_olustur("canli_adsb", parametreler=(istek or CanliAdsbOturumIstegi()).model_dump())
    )


@router.post(
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
    await ortak._hiz_sinirini_kontrol_et(
        f"sanal_pirep:{ortak._istemci_kimligi(request, rol)}",
        maks=config.SANAL_PIREP_IZ_DAKIKADA_MAKS,
        pencere_saniye=60,
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
    async with ortak._agir_hesap_yuvasi():
        return await asyncio.to_thread(
            izden_sanal_pirep_uret,
            iz_df,
            "canli_iz",
            bildirim_yayinla,
            icao24=istek.icao24.lower() if istek.icao24 else None,
            ucus_numarasi=istek.ucus_numarasi,
        )


@router.get("/sanal-pirep", response_model=SanalPirepListesiYaniti, tags=["Sanal PIREP"])
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


_CANLI_VERI_MAKS_KUTU_DERECE = (40.0, 60.0)


@router.get("/veri/kupler", response_model=list[HavaDurumuKupuYaniti], tags=["Veri Sağlayıcı"])
async def hava_durumu_kupleri(limit: int = Query(default=50, ge=1, le=500)):
    """Veri sağlayıcıların indirip kataloğa kaydettiği küpler (en yeni önce)."""
    kupler = await asyncio.to_thread(katalogu_listele, limit)
    return [{**k, "dosya_adi": os.path.basename(k["dosya_yolu"])} for k in kupler]


@router.post(
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
    await ortak._hiz_sinirini_kontrol_et(f"canli_veri:{ortak._istemci_kimligi(request, rol)}")
    if istek.enlem_min >= istek.enlem_maks or istek.boylam_min >= istek.boylam_maks:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Kutu sınırları geçersiz (min < maks olmalı).")
    enlem_genisligi, boylam_genisligi = istek.enlem_maks - istek.enlem_min, istek.boylam_maks - istek.boylam_min
    if enlem_genisligi > _CANLI_VERI_MAKS_KUTU_DERECE[0] or boylam_genisligi > _CANLI_VERI_MAKS_KUTU_DERECE[1]:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Kutu en fazla {_CANLI_VERI_MAKS_KUTU_DERECE[0]:.0f}° x {_CANLI_VERI_MAKS_KUTU_DERECE[1]:.0f}° olabilir.",
        )
    try:
        webhook = ortak._webhook_url_dogrula(istek.bildirim_webhook_url)
    except ValueError as hata:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(hata)) from hata
    baslangic = istek.baslangic or datetime.now(UTC)
    gorev_id = await ortak._gorev_olustur(
        "canli_veri",
        parametreler={
            "kutu": [istek.enlem_min, istek.enlem_maks, istek.boylam_min, istek.boylam_maks],
            "baslangic": baslangic.isoformat(),
            "saat_sayisi": istek.saat_sayisi,
        },
        webhook_url=webhook,
    )
    return ortak._kuyruga_alindi(gorev_id)


@router.post(
    "/backtest/ucuslar/{ucus_numarasi}/{tarih}",
    dependencies=_YONETICI,
    response_model=BacktestSonucuYaniti,
    tags=["Backtest"],
)
async def ucus_backtesti(
    ucus_numarasi: str = Path(pattern=ortak._UCUS_NUMARASI_DESENI),
    tarih: date = Path(...),
):
    """Analiz edilmiş bir uçuşun gerçek izini, aynı giriş/çıkış noktaları için
    büyük daire ve A* rotasıyla AYNI ölçütle karşılaştırır (bkz. rota_backtest.py)
    ve sonucu kaydeder. Hava küpü seyir bölümünü kapsamıyorsa 400."""
    async with ortak._agir_hesap_yuvasi():
        return await asyncio.to_thread(ucus_backtest_et, ucus_numarasi, tarih.isoformat())


@router.post(
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
    await ortak._hiz_sinirini_kontrol_et(f"backtest:{ortak._istemci_kimligi(request, rol)}")
    try:
        webhook = ortak._webhook_url_dogrula(bildirim_webhook_url)
    except ValueError as hata:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(hata)) from hata
    gorev_id = await ortak._gorev_olustur(
        "backtest", parametreler={"limit": limit, "yenile": yenile}, webhook_url=webhook
    )
    return ortak._kuyruga_alindi(gorev_id)


@router.get("/backtest", response_model=BacktestListesiYaniti, tags=["Backtest"])
async def backtest_sonuclari():
    """Tüm backtest sonuçları + filo geneli özet (A*'ın gerçek uçuşlara göre
    ortalama riskli nokta oranı, riskin azaltıldığı uçuş oranı, ek mesafe/süre)."""
    return await asyncio.to_thread(backtestleri_listele)
