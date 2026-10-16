import asyncio
from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field, model_validator

from turbulans_radar.api import ortak
from turbulans_radar.api.guvenlik import _YONETICI, api_anahtarini_dogrula
from turbulans_radar.depo.geri_bildirim_deposu import geri_bildirim_kaydet, geri_bildirim_ozeti
from turbulans_radar.uretim_bilgisi import yazilim_surumu

router = APIRouter(prefix="/api/v1", dependencies=[Depends(api_anahtarini_dogrula)])

_DAKIKADA_MAKS = 30


class GeriBildirimIstegi(BaseModel):
    hedef_turu: Literal["rota", "analiz", "nokta_tahmini", "genel"]
    hedef_kimligi: str | None = Field(default=None, max_length=64)
    yararli_mi: bool | None = None
    dogru_mu: bool | None = None
    aciklama: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def _bos_olmasin(self):
        if self.yararli_mi is None and self.dogru_mu is None and not (self.aciklama or "").strip():
            raise ValueError("yararli_mi, dogru_mu ya da aciklama alanlarından en az biri dolu olmalı.")
        return self


class GeriBildirimYaniti(BaseModel):
    id: int
    kaydedildi_mi: bool = True
    aciklama: str = "Teşekkürler. Kayıt kişisel veri içermez (IP, ad ya da e-posta saklanmaz)."


class GeriBildirimHedefOzeti(BaseModel):
    toplam: int
    yararli_yanitlayan: int
    yararli_evet: int
    dogru_yanitlayan: int
    dogru_evet: int


@router.post("/geri-bildirim", response_model=GeriBildirimYaniti, tags=["Geri bildirim"])
async def geri_bildirim_gonder(istek: GeriBildirimIstegi, request: Request, rol: str = Depends(api_anahtarini_dogrula)):
    await ortak._hiz_sinirini_kontrol_et(
        f"geri_bildirim:{ortak._istemci_kimligi(request, rol)}", maks=_DAKIKADA_MAKS, pencere_saniye=60
    )
    kimlik = await asyncio.to_thread(
        geri_bildirim_kaydet,
        istek.hedef_turu,
        rol,
        istek.hedef_kimligi,
        istek.yararli_mi,
        istek.dogru_mu,
        (istek.aciklama or "").strip() or None,
        yazilim_surumu(),
    )
    return {"id": kimlik}


@router.get(
    "/geri-bildirim/ozet",
    dependencies=_YONETICI,
    response_model=dict[str, GeriBildirimHedefOzeti],
    tags=["Geri bildirim"],
)
async def geri_bildirim_ozetini_getir():
    return await asyncio.to_thread(geri_bildirim_ozeti)
