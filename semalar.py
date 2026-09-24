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

from pydantic import BaseModel


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
