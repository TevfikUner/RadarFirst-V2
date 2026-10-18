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

import os
import re
from typing import Annotated, Literal

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
    TI1_ESIK_ORTA_SIDDETLI_GFS: Pozitif | None
    GFS_TOPLULUK_UYE_SAYISI: PozitifTam
    GFS_KOSU_GECIKMESI_SAAT: NegatifOlmayanTam
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
    ROTA_YAKIT_MODELI: Literal["openap", "sabit"]
    ROTA_SEYIR_KUTLE_ORANI: Annotated[float, Field(gt=0, le=1)]
    ROTA_KUTLE_BANDI: tuple[Annotated[float, Field(gt=0, le=1)], ...]
    ROTA_DIKEY_KESIT_FL: tuple[Annotated[int, Field(ge=50, le=600)], ...]
    IZ_BULUTU_OLCUTU: Literal["sac", "sabit"]
    SAC_ITKI_VERIMI: Annotated[float, Field(gt=0, lt=1)]
    SIGMET_MAKS_COZUMLENEMEYEN_ORAN: KapaliOran
    DEVRE_KESICI_ESIK: NegatifOlmayanTam
    DEVRE_KESICI_TABAN_SANIYE: Pozitif
    DEVRE_KESICI_AZAMI_SANIYE: Pozitif
    CANLI_GECMIS_SAAT: NegatifOlmayanTam
    CANLI_TAHMIN_UFKU_SAAT: NegatifOlmayanTam
    GUVENILIR_ONGORU_SAAT: PozitifTam
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


_YEREL_ADRESLER = ("", "127.0.0.1", "localhost", "::1")
_MIN_ANAHTAR_UZUNLUGU = 32
_VARSAYILAN_DB_SIFRELERI = ("", "postgres")


def yalnizca_yerel_yayin_mi(ortam=None) -> bool:
    ortam = os.environ if ortam is None else ortam
    return ortam.get("API_YAYIN_ADRESI", "").strip() in _YEREL_ADRESLER


def ag_acik_mi(ortam=None) -> bool:
    """API_YAYIN_ADRESI yerel değilse ya da AG_ACILISI açıksa (TLS vekili arkasında üretim)."""
    ortam = os.environ if ortam is None else ortam
    return not yalnizca_yerel_yayin_mi(ortam) or ortam.get("AG_ACILISI", "").strip().lower() in ("1", "true", "evet")


def _zayif_mi(deger: str) -> bool:
    return len(deger) < _MIN_ANAHTAR_UZUNLUGU or deger.lower().startswith("demo")


def ag_acilis_sorunlari(ortam=None, kaynak=config, anahtarlari_denetle=True) -> list[str]:
    """Ağa açık kurulumda başlamayı engelleyen sır ve ayar sorunları (değer yazılmaz).
    İşçi API anahtarı taşımadığı için anahtarlari_denetle=False ile çağırır."""
    ortam = os.environ if ortam is None else ortam
    if not ag_acik_mi(ortam):
        return []
    anahtarlar = [("API_ANAHTARI", ortam.get("API_ANAHTARI", ""))] if anahtarlari_denetle else []
    if anahtarlari_denetle and ortam.get("API_PILOT_ANAHTARI"):
        anahtarlar.append(("API_PILOT_ANAHTARI", ortam["API_PILOT_ANAHTARI"]))
    for girdi in filter(None, (g.strip() for g in ortam.get("API_ANAHTARLARI", "").split(",") if anahtarlari_denetle)):
        anahtarlar.append((f"API_ANAHTARLARI[{girdi.split(':', 1)[0]}]", girdi.split(":", 2)[-1].strip()))
    sorunlar = [
        f"{ad}: en az {_MIN_ANAHTAR_UZUNLUGU} karakter olmalı ve demo anahtarı olamaz"
        for ad, anahtar in anahtarlar
        if _zayif_mi(anahtar)
    ]
    sifre = ortam.get("POSTGRES_PASSWORD", "")
    if sifre in _VARSAYILAN_DB_SIFRELERI or sifre.lower().startswith("demo"):
        sorunlar.append("POSTGRES_PASSWORD: varsayılan ya da demo şifresi")
    if ortam.get("POSTGRES_USER", "postgres") in {"postgres", ortam.get("DB_SUPER_KULLANICI", "postgres")}:
        sorunlar.append(
            "POSTGRES_USER: süper kullanıcı; UYGULAMA_POSTGRES_USER/PASSWORD tanımlayın (README 'Uygulama veritabanı rolü')"
        )
    if getattr(kaynak, "KISITLI_SAHA_ORNEK_VERI_YUKLE", getattr(config, "KISITLI_SAHA_ORNEK_VERI_YUKLE")):
        sorunlar.append("KISITLI_SAHA_ORNEK_VERI_YUKLE: örnek kısıtlı sahalar açık; false yapın")
    if not getattr(kaynak, "MODEL_BUTUNLUK_ZORUNLU", getattr(config, "MODEL_BUTUNLUK_ZORUNLU")):
        sorunlar.append("MODEL_BUTUNLUK_ZORUNLU: model bütünlük denetimi kapalı; true yapın")
    return sorunlar


def ayarlari_dogrula(kaynak=config, ortam=None, anahtarlari_denetle=True) -> None:
    """Sorun varsa hepsini tek mesajda listeleyen AyarHatasi fırlatır."""
    degerler = {ad: getattr(kaynak, ad) for ad in AyarSemasi.model_fields}
    satirlar = []
    try:
        AyarSemasi.model_validate(degerler)
    except ValidationError as hata:
        satirlar = [f"{'.'.join(str(p) for p in h['loc']) or 'tutarlılık'}: {h['msg']}" for h in hata.errors()]
    satirlar += [f"ağa açık kurulum: {sorun}" for sorun in ag_acilis_sorunlari(ortam, kaynak, anahtarlari_denetle)]
    if satirlar:
        raise AyarHatasi("Geçersiz ayar (ortam değişkenleri / .env):\n  " + "\n  ".join(satirlar))
