"""
ayar_dogrulama.py
-------------------
config.py'deki ortam değişkeni ayarlarının tip, aralık ve tutarlılık doğrulaması
(pydantic). API ve işçi başlarken çalışır; hatalı bir değer (örn. eşiklerin yer
değiştirmesi, 0-1 dışında bir oran, ters sıralı sınırlar) sessizce yanlış sonuç
üretmek yerine süreç açılırken tüm sorunları birlikte listeleyerek durdurur.

config.X modül arayüzü bilerek korunur (54 modül ve testlerin yamaları buna
dayanır); bu katman değerleri kopyalamaz, yalnız denetler. Her ayar burada
olmak zorunda değil: yanlış değerinin sonucu sessiz ve önemli olanlar seçildi.
"""

import re
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from turbulans_radar import config

Pozitif = Annotated[float, Field(gt=0)]
NegatifOlmayan = Annotated[float, Field(ge=0)]
Oran = Annotated[float, Field(gt=0, lt=1)]
KapaliOran = Annotated[float, Field(ge=0, le=1)]
PozitifTam = Annotated[int, Field(ge=1)]
NegatifOlmayanTam = Annotated[int, Field(ge=0)]


class AyarHatasi(ValueError):
    pass


class AyarSemasi(BaseModel):
    model_config = ConfigDict(extra="ignore")

    TI1_ESIK_HAFIF: Pozitif
    TI1_ESIK_ORTA_SIDDETLI: Pozitif
    EDR_ESIK_HAFIF: Pozitif
    EDR_ESIK_ORTA: Pozitif
    EDR_ESIK_SIDDETLI: Pozitif
    ML_KONFORMAL_ALFA: Oran
    ML_HOLDOUT_ORANI: Oran
    ML_KARAR_ESIGI: Oran | None
    ML_MIN_IRTIFA_FT: Pozitif
    ML_MAKS_IRTIFA_FT: Pozitif
    ML_MIN_ORNEK: PozitifTam
    ML_MIN_GUN: PozitifTam
    ML_GECE_ISI_SAATI: str
    VERITABANI_HAVUZ_BOYUTU: PozitifTam
    VERITABANI_HAVUZ_TASMA: NegatifOlmayanTam
    ASYNC_VERITABANI_HAVUZ_BOYUTU: PozitifTam
    ASYNC_VERITABANI_HAVUZ_TASMA: NegatifOlmayanTam
    AGIR_HESAP_MAKS_ESZAMANLI: PozitifTam
    GOREV_ISCI_SAYISI: NegatifOlmayanTam
    GOREV_KALP_ATISI_SANIYE: Pozitif
    GOREV_BAYAT_SANIYE: Pozitif
    ROTA_SIMULASYONU_NOKTA_SAYISI: Annotated[int, Field(ge=3)]
    ROTA_MAKS_SAPMA_ACISI_DERECE: Annotated[float, Field(gt=0, lt=90)]
    ROTA_MAKS_YANAL_SAPMA_KM: NegatifOlmayan
    ROTA_YANAL_IZGARA_KM: Pozitif
    ROTA_ZAMAN_BELIRSIZLIK_ORANI: KapaliOran
    KABIN_PENCERE_PAYI_DK: NegatifOlmayan
    SIGMET_MAKS_COZUMLENEMEYEN_ORAN: KapaliOran
    DEVRE_KESICI_ESIK: NegatifOlmayanTam
    DEVRE_KESICI_TABAN_SANIYE: Pozitif
    DEVRE_KESICI_AZAMI_SANIYE: Pozitif
    CANLI_GECMIS_SAAT: NegatifOlmayanTam
    CANLI_TAHMIN_UFKU_SAAT: NegatifOlmayanTam
    CANLI_BASINC_SEVIYELERI_HPA: tuple[Annotated[float, Field(gt=0, le=1100)], ...]
    CANLI_ISITMA_KUTUSU: tuple[float, ...]
    CANLI_ADSB_ARALIK_SANIYE: Pozitif
    CANLI_ADSB_MIN_ARALIK_SANIYE: Pozitif
    CANLI_ADSB_SURE_DK: Pozitif
    CANLI_ADSB_MAKS_SURE_DK: Pozitif
    CANLI_ADSB_MERKEZ_ENLEM: Annotated[float, Field(ge=-90, le=90)]
    CANLI_ADSB_MERKEZ_BOYLAM: Annotated[float, Field(ge=-180, le=180)]
    MAKS_ISTEK_GOVDESI_MB: Pozitif
    GUNLUK_VERI_BUTCESI_MB: NegatifOlmayan

    @field_validator("ML_GECE_ISI_SAATI")
    @classmethod
    def _saat(cls, deger: str) -> str:
        if deger and not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", deger):
            raise ValueError("boş ya da SS:DD (UTC) olmalı")
        return deger

    @field_validator("CANLI_BASINC_SEVIYELERI_HPA")
    @classmethod
    def _seviyeler(cls, deger):
        if not deger:
            raise ValueError("en az bir basınç seviyesi gerekli")
        return deger

    @field_validator("CANLI_ISITMA_KUTUSU")
    @classmethod
    def _kutu(cls, deger):
        if len(deger) != 4:
            raise ValueError("enlem_min,enlem_maks,boylam_min,boylam_maks (4 sayı) olmalı")
        enlem_min, enlem_maks, boylam_min, boylam_maks = deger
        if not (-90 <= enlem_min < enlem_maks <= 90 and -180 <= boylam_min < boylam_maks <= 180):
            raise ValueError("sınırlar ters sıralı ya da aralık dışı")
        return deger

    @model_validator(mode="after")
    def _tutarlilik(self):
        sorunlar = []
        for kucuk, buyuk in (
            ("TI1_ESIK_HAFIF", "TI1_ESIK_ORTA_SIDDETLI"),
            ("EDR_ESIK_HAFIF", "EDR_ESIK_ORTA"),
            ("EDR_ESIK_ORTA", "EDR_ESIK_SIDDETLI"),
            ("ML_MIN_IRTIFA_FT", "ML_MAKS_IRTIFA_FT"),
            ("GOREV_KALP_ATISI_SANIYE", "GOREV_BAYAT_SANIYE"),
            ("CANLI_ADSB_MIN_ARALIK_SANIYE", "CANLI_ADSB_ARALIK_SANIYE"),
            ("CANLI_ADSB_SURE_DK", "CANLI_ADSB_MAKS_SURE_DK"),
            ("DEVRE_KESICI_TABAN_SANIYE", "DEVRE_KESICI_AZAMI_SANIYE"),
        ):
            if getattr(self, kucuk) > getattr(self, buyuk):
                sorunlar.append(f"{kucuk} ({getattr(self, kucuk)}) {buyuk}'den ({getattr(self, buyuk)}) büyük olamaz")
        if sorunlar:
            raise ValueError("; ".join(sorunlar))
        return self


def ayarlari_dogrula(kaynak=config) -> None:
    """Sorun varsa hepsini tek mesajda listeleyen AyarHatasi fırlatır."""
    degerler = {ad: getattr(kaynak, ad) for ad in AyarSemasi.model_fields}
    try:
        AyarSemasi.model_validate(degerler)
    except ValidationError as hata:
        satirlar = [f"{'.'.join(str(p) for p in h['loc']) or 'tutarlılık'}: {h['msg']}" for h in hata.errors()]
        raise AyarHatasi("Geçersiz ayar (ortam değişkenleri / .env):\n  " + "\n  ".join(satirlar)) from None
