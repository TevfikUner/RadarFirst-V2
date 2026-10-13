"""/api/v1/ucuslar: kayıtlı uçuşlar, dışa aktarım, SIGMET doğrulaması."""

import asyncio
import json
from datetime import date

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

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
    SigmetDogrulamaYaniti,
    TopluSilmeYaniti,
    UcusDetayYaniti,
    UcuslarListesiYaniti,
)
from turbulans_radar.depo.veritabani import (
    ucus_detayini_getir_async,
    ucus_olcumlerini_dataframe_olarak_getir,
    ucus_sil_async,
    ucuslari_listele_async,
    ucuslari_toplu_sil_async,
)
from turbulans_radar.dogrulama.sigmet_dogrulama import ucus_sigmet_ile_karsilastir

# v1 ile aynı: önek ve API anahtarı her uç noktada (bkz. api_servisi.v1).
router = APIRouter(prefix="/api/v1", dependencies=[Depends(api_anahtarini_dogrula)])


@router.get("/ucuslar", response_model=UcuslarListesiYaniti, tags=["Uçuşlar"])
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


@router.delete("/ucuslar", dependencies=_YONETICI, response_model=TopluSilmeYaniti, tags=["Uçuşlar"])
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
    await ortak._hiz_sinirini_kontrol_et(f"silme:{ortak._istemci_kimligi(request, rol)}")
    if not any([ucus_numarasi_arama, baslangic_tarih, bitis_tarih]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Toplu silme için en az bir filtre gerekli (ucus_numarasi_arama/baslangic_tarih/bitis_tarih).",
        )
    silinen_sayisi = await ucuslari_toplu_sil_async(
        ucus_numarasi_arama=ucus_numarasi_arama, baslangic_tarih=baslangic_tarih, bitis_tarih=bitis_tarih
    )
    return {"silinen_sayisi": silinen_sayisi}


@router.get("/ucuslar/{ucus_numarasi}/{tarih}", response_model=UcusDetayYaniti, tags=["Uçuşlar"])
async def ucus_detayi(
    ucus_numarasi: str = Path(pattern=ortak._UCUS_NUMARASI_DESENI),
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


@router.delete(
    "/ucuslar/{ucus_numarasi}/{tarih}", dependencies=_YONETICI, status_code=status.HTTP_204_NO_CONTENT, tags=["Uçuşlar"]
)
async def ucus_sil(
    request: Request,
    ucus_numarasi: str = Path(pattern=ortak._UCUS_NUMARASI_DESENI),
    tarih: date = Path(...),
    rol: str = Depends(api_anahtarini_dogrula),
):
    """Kayıtlı bir uçuşu (CASCADE ile edr_olcumleri dahil) siler. Aynı
    uçuş/tarih tekrar analiz edilmek istenirse zaten otomatik üzerine
    yazılır (bkz. ucus_ve_olcumleri_kaydet) -- bu uç nokta, bir daha analiz
    edilmeyecek kaydı veritabanından tamamen kaldırmak içindir."""
    await ortak._hiz_sinirini_kontrol_et(f"silme:{ortak._istemci_kimligi(request, rol)}")
    silindi_mi = await ucus_sil_async(ucus_numarasi, tarih.isoformat())
    if not silindi_mi:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Uçuş bulunamadı.")


@router.get("/ucuslar/{ucus_numarasi}/{tarih}/csv", tags=["Uçuşlar"])
async def ucus_csv_disa_aktar(
    ucus_numarasi: str = Path(pattern=ortak._UCUS_NUMARASI_DESENI),
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


@router.get("/ucuslar/{ucus_numarasi}/{tarih}/geojson", tags=["Uçuşlar"])
async def ucus_geojson_disa_aktar(
    ucus_numarasi: str = Path(pattern=ortak._UCUS_NUMARASI_DESENI),
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


@router.get("/ucuslar/{ucus_numarasi}/{tarih}/sigmet-dogrulama", response_model=SigmetDogrulamaYaniti, tags=["Uçuşlar"])
async def ucus_sigmet_dogrulamasi(
    ucus_numarasi: str = Path(pattern=ortak._UCUS_NUMARASI_DESENI),
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
