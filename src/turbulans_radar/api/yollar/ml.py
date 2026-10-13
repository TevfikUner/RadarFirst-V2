"""/api/v1 makine öğrenmesi uç noktaları: model bilgisi/sürümleri, gece işi, ML durumu."""

import asyncio

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    status,
)
from pydantic import BaseModel, Field

from turbulans_radar.api import ortak
from turbulans_radar.api.guvenlik import _YONETICI, api_anahtarini_dogrula
from turbulans_radar.api.semalar import (
    GorevBaslatildiYaniti,
    ModelBilgisiYaniti,
    ModelVersiyonuOzetiYaniti,
)
from turbulans_radar.depo.gorev_deposu import (
    aktif_gorev_var_mi,
)
from turbulans_radar.ml.turbulans_ml_modeli import (
    model_bilgisini_yukle,
    model_kullanilabilir_mi,
    model_versiyonlarini_listele,
    versiyona_geri_don,
)

# v1 ile aynı: önek ve API anahtarı her uç noktada (bkz. api_servisi.v1).
router = APIRouter(prefix="/api/v1", dependencies=[Depends(api_anahtarini_dogrula)])


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


@router.get("/turbulans/model-bilgisi", response_model=ModelBilgisiYaniti, tags=["Türbülans Tahmini"])
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


@router.get("/turbulans/model-versiyonlari", response_model=list[ModelVersiyonuOzetiYaniti], tags=["Türbülans Tahmini"])
async def turbulans_model_versiyonlari():
    """ml_egitimi.py'nin her çalıştırmasında biriktirdiği TÜM model
    versiyonlarını (en yeni önce) döner -- hiç eğitim yapılmadıysa boş
    liste. Aktif olan (şu an /turbulans/tahmin'in kullandığı) versiyonu
    ayırt etmek için GET /turbulans/model-bilgisi'ndeki egitim_zamani ile
    karşılaştırılabilir."""
    return await asyncio.to_thread(model_versiyonlarini_listele)


@router.post(
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
    await ortak._hiz_sinirini_kontrol_et(f"model_aktiflestir:{ortak._istemci_kimligi(request, rol)}")
    try:
        aktif_bilgi = await asyncio.to_thread(versiyona_geri_don, versiyon_id)
    except ValueError as hata:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(hata)) from hata
    return {"egitildi_mi": True, **aktif_bilgi}


@router.post(
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
    await ortak._hiz_sinirini_kontrol_et(f"ml_gece:{ortak._istemci_kimligi(request, rol)}")
    if await aktif_gorev_var_mi("ml_veri") or await aktif_gorev_var_mi("ml_egitim"):
        raise HTTPException(status.HTTP_409_CONFLICT, "Bir ML gece işi zaten kuyrukta ya da çalışıyor.")
    parametreler = (istek or MlGeceIsiIstegi()).model_dump()
    return ortak._kuyruga_alindi(await ortak._gorev_olustur("ml_veri", parametreler=parametreler))


@router.get("/ml/durum", response_model=MlDurumYaniti, tags=["Makine Öğrenmesi"])
async def ml_durumu():
    """ML veri hattının ve gece işinin durumu: örnek sayıları, eşleşmiş gün
    sayısı (eğitim ML_MIN_GUN'dan önce yapılmaz), bugünkü CDS kullanımı, IEM
    imleci, aktif model sürümü ve son ml_veri/ml_egitim görevleri."""
    from turbulans_radar.ml.ml_veri_hatti import ml_durum_ozeti

    return await asyncio.to_thread(ml_durum_ozeti)
