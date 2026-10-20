"""/api/v1 SIGMET ve kısıtlı hava sahası uç noktaları."""

import asyncio
from datetime import UTC, datetime

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Path,
    Query,
    Request,
    status,
)
from fastapi.responses import Response

from turbulans_radar.api import ortak
from turbulans_radar.api.guvenlik import _YONETICI, api_anahtarini_dogrula
from turbulans_radar.api.semalar import (
    GorevBaslatildiYaniti,
    KisitliSahaIceAktarmaYaniti,
    KisitliSahaYaniti,
    SigmetOzetiYaniti,
    SigmetYenilemeYaniti,
)
from turbulans_radar.veri.kisitli_saha_saglayici import (
    gecerli_kisitli_sahalari_getir,
    geojson_ice_aktar,
    kisitli_sahayi_sil,
)
from turbulans_radar.veri.sigmet_saglayici import (
    gecerli_sigmetleri_getir,
    kacinilacak_tehlikeler,
    sigmetleri_guncelle,
)

# v1 ile aynı: önek ve API anahtarı her uç noktada (bkz. api_servisi.v1).
router = APIRouter(prefix="/api/v1", dependencies=[Depends(api_anahtarini_dogrula)])


@router.post("/sigmet/guncelle", dependencies=_YONETICI, response_model=SigmetYenilemeYaniti, tags=["SIGMET"])
async def sigmetleri_yenile(request: Request, rol: str = Depends(api_anahtarini_dogrula)):
    """AWC'den (aviationweather.gov: ABD `airsigmet` + uluslararası `isigmet`)
    canlı SIGMET'leri çekip veritabanını günceller; akıştan düşen (iptal
    edilen) SIGMET'lerin geçerliliği sona erdirilir. n8n/cron'un periyodik
    (örn. 10-15 dk) tetiklemesi için -- ya da SIGMET_OTOMATIK_GUNCELLEME_DAKIKA
    ile API'nin kendi zamanlayıcısı kullanılır."""
    await ortak._hiz_sinirini_kontrol_et(f"sigmet:{ortak._istemci_kimligi(request, rol)}")
    try:
        return await asyncio.to_thread(sigmetleri_guncelle)
    finally:
        await ortak._rota_onbellegini_temizle()


@router.get("/sigmet", response_model=list[SigmetOzetiYaniti], tags=["SIGMET"])
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


@router.get(
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


@router.get("/kisitli-sahalar", response_model=list[KisitliSahaYaniti], tags=["Kısıtlı Hava Sahaları"])
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


@router.post(
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
    await ortak._hiz_sinirini_kontrol_et(f"kisitli_saha:{ortak._istemci_kimligi(request, rol)}")
    try:
        return await asyncio.to_thread(geojson_ice_aktar, geojson, kaynak, eskileri_kaldir)
    finally:
        await ortak._rota_onbellegini_temizle()


@router.post(
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
    await ortak._hiz_sinirini_kontrol_et(f"kisitli_saha:{ortak._istemci_kimligi(request, rol)}")
    return ortak._kuyruga_alindi(await ortak._gorev_olustur("openaip", parametreler={"ulkeler": ulke}))


@router.delete(
    "/kisitli-sahalar/{dis_kimlik}",
    dependencies=_YONETICI,
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Kısıtlı Hava Sahaları"],
)
async def kisitli_saha_sil(
    request: Request, dis_kimlik: str = Path(max_length=128), rol: str = Depends(api_anahtarini_dogrula)
):
    await ortak._hiz_sinirini_kontrol_et(f"kisitli_saha:{ortak._istemci_kimligi(request, rol)}")
    silindi_mi = await asyncio.to_thread(kisitli_sahayi_sil, dis_kimlik)
    await ortak._rota_onbellegini_temizle()
    if not silindi_mi:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kısıtlı saha bulunamadı.")
