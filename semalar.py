"""
semalar.py
------------
api_servisi.py için Pydantic YANIT (response) modelleri.

Öncesinde uç noktalar ham dict/list[dict] döndürüyordu; FastAPI bunlardan
bir şema üretemediği için Swagger/OpenAPI dokümantasyonunda (/docs) yanıt
alanları "any" olarak görünüyordu. Bu modeller alan adlarını/tiplerini
açıkça tanımlayarak /docs'u gerçek bir API sözleşmesine dönüştürür --
FastAPI, veritabani.py'nin döndürdüğü dict'leri bu modellere göre otomatik
doğrulayıp serileştirir (fonksiyonların kendisini değiştirmeye gerek yok).
"""

from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator

from rota_optimizasyonu import UCAK_PROFILLERI


class SaglikYaniti(BaseModel):
    durum: str


class UcusYaniti(BaseModel):
    id: int
    ucus_numarasi: str
    tarih: date
    icao24: str | None = None
    kalkis_havaalani: str | None = None
    varis_havaalani: str | None = None
    olusturulma_zamani: datetime


class OlcumYaniti(BaseModel):
    zaman: datetime
    enlem: float
    boylam: float
    ti1_indeksi: float | None = None
    edr_proxy: float | None = None
    richardson_sayisi: float | None = None
    dinamik_kararsizlik: bool | None = None
    basinc_hpa: float | None = None


class UcusDetayYaniti(BaseModel):
    ucus: UcusYaniti
    toplam_olcum_sayisi: int
    olcumler: list[OlcumYaniti]


class GorevBaslatildiYaniti(BaseModel):
    gorev_id: str
    durum: str


class GorevDurumYaniti(BaseModel):
    """Görev durumu, ilerledikçe farklı alanlar kazanır (aciklama sadece
    hatada, ozet sadece toplu analizde dolar) -- bu yüzden hepsi opsiyonel."""

    durum: str
    ucus_numarasi: str | None = None
    tarih: str | None = None
    aciklama: str | None = None
    ozet: list[dict] | None = None


class EsiklerYaniti(BaseModel):
    """harita3d.html gibi istemcilerin, config.py'deki renklendirme
    eşiklerini Python tarafındaki değerlerle bire bir aynı tutması için."""

    ti1_esik_hafif: float
    ti1_esik_orta_siddetli: float


class SigmetYaniti(BaseModel):
    etiket: str | None = None
    baslangic: str
    bitis: str
    poligon: list[tuple[float, float]]


class SigmetDogrulamaYaniti(BaseModel):
    """sigmet_dogrulama.py'nin ürettiği karşılaştırma raporu -- bkz. o
    modülün docstring'i (SADECE ABD hava sahası için gerçek veri döner)."""

    toplam_turbulans_sigmeti: int
    orta_siddetli_nokta_sayisi: int
    sigmetle_ortusen_nokta_sayisi: int
    ortusme_orani: float | None = None
    sigmetler: list[SigmetYaniti]


class RotaSimulasyonuIstegi(BaseModel):
    """web/ucus_simulasyonu.html'nin gönderdiği istek -- bkz. rota_optimizasyonu.py."""

    baslangic_enlem: float = Field(ge=-90, le=90)
    baslangic_boylam: float = Field(ge=-180, le=180)
    bitis_enlem: float = Field(ge=-90, le=90)
    bitis_boylam: float = Field(ge=-180, le=180)
    irtifa_ft: float = Field(ge=1000, le=45000)
    zaman: str  # ISO 8601 (örn. '2019-01-15T10:00:00')
    ucak_modeli: str

    @field_validator("zaman")
    @classmethod
    def _zaman_gecerli_mi(cls, deger):
        try:
            datetime.fromisoformat(deger)
        except ValueError:
            raise ValueError("zaman ISO 8601 formatında olmalı (örn. '2019-01-15T10:00:00').") from None
        return deger

    @field_validator("ucak_modeli")
    @classmethod
    def _ucak_modeli_gecerli_mi(cls, deger):
        if deger not in UCAK_PROFILLERI:
            raise ValueError(f"Bilinmeyen ucak_modeli: '{deger}'. Geçerli seçenekler: {list(UCAK_PROFILLERI)}")
        return deger


class RotaNoktasiYaniti(BaseModel):
    enlem: float
    boylam: float
    irtifa_m: float
    zaman: str


class RotaSonucuYaniti(BaseModel):
    noktalar: list[RotaNoktasiYaniti]
    toplam_sure_dk: float
    mesafe_km: float
    tahmini_yakit_kg: float
    tahmini_co2_kg: float
    maks_yanal_sapma_km: float | None = None
    irtifa_ft: float | None = None
    maks_ti1: float | None = None
    riskli_nokta_sayisi: int = 0


class RotaSimulasyonuYaniti(BaseModel):
    ruzgar_verisi_kaynagi: str
    aciklama: str
    ucak_modeli: str
    ucak_etiketi: str
    turbulanstan_kacinildi_mi: bool
    kacinma_stratejisi: str
    normal_rota: RotaSonucuYaniti
    optimize_rota: RotaSonucuYaniti
    sure_tasarrufu_dk: float
    yakit_tasarrufu_yuzde: float
    co2_farki_kg: float
    czml: list[dict]


class UcakProfiliYaniti(BaseModel):
    kod: str
    etiket: str
    tas_ms: float


class TurbulansTahminIstegi(BaseModel):
    """turbulans_ml_modeli.py'nin gerçek IEM PIREP + ERA5 verisiyle eğitilmiş
    sınıflandırıcısını, fizik tabanlı Ellrod TI1 ile karşılaştırmalı olarak
    tek bir nokta için sorgular."""

    enlem: float = Field(ge=-90, le=90)
    boylam: float = Field(ge=-180, le=180)
    irtifa_ft: float = Field(ge=1000, le=45000)
    zaman: str

    @field_validator("zaman")
    @classmethod
    def _zaman_gecerli_mi(cls, deger):
        try:
            datetime.fromisoformat(deger)
        except ValueError:
            raise ValueError("zaman ISO 8601 formatında olmalı (örn. '2019-01-15T10:00:00').") from None
        return deger


class TurbulansTahminYaniti(BaseModel):
    kapsam_icinde_mi: bool
    ti1_indeksi: float | None = None
    ti1_riskli_mi: bool | None = None
    ml_riski_var_mi: bool | None = None
    ml_olasilik: float | None = None
    aciklama: str
    yakit_akisi_kg_saat: float
