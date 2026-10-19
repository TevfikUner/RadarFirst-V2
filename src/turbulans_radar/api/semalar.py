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
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from turbulans_radar.fizik.turbulans_indeksleri import TI1_GUVENILIRLIK_NOTU
from turbulans_radar.rota.rota_optimizasyonu import UCAK_PROFILLERI


class SaglikYaniti(BaseModel):
    """durum: ayakta | bozulmus (derin kontrolde operasyonel bir sorun:
    bayat SIGMET, veri kaynağı hatası, biriken görev kuyruğu). kontroller:
    bağımlılık başına durum; uyarilar: yapılandırma eksikleri (örn. yerel
    kütüphane yok, sadece örnek kısıtlı saha)."""

    durum: str
    veritabani: str | None = None
    kontroller: dict[str, dict] | None = None
    uyarilar: list[str] | None = None


class SistemDurumuYaniti(SaglikYaniti):
    """GET /api/v1/sistem/durum -- sağlık raporu + kaynak başına son hata metinleri."""


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
    edr_proxy: float | None = Field(
        None,
        description="Gösterge ölçeği (0-1): birleşik log-normal gösterge eşlemesi, yoksa TI1 görsel ölçeği "
        "(tanh). EDR değildir; ölçülmüş ya da sertifikalı EDR yerine kullanılamaz.",
    )
    richardson_sayisi: float | None = None
    dinamik_kararsizlik: bool | None = None
    basinc_hpa: float | None = None
    irtifa_m: float | None = None


class UcusDetayYaniti(BaseModel):
    ucus: UcusYaniti
    toplam_olcum_sayisi: int
    olcumler: list[OlcumYaniti]


class UcuslarListesiYaniti(BaseModel):
    """toplam_sayi, limit UYGULANMADAN ÖNCEKİ filtre eşleşme sayısıdır --
    istemcinin (bkz. web/harita3d.html) sayfalama/'kaç kayıt var' bilgisi
    için ucuslar listesinin uzunluğuna güvenmesi gerekmez."""

    toplam_sayi: int
    ucuslar: list[UcusYaniti]


class TopluSilmeYaniti(BaseModel):
    silinen_sayisi: int


class GorevBaslatildiYaniti(BaseModel):
    gorev_id: str
    durum: str


class GorevDurumYaniti(BaseModel):
    """Kuyruktaki görevin durumu: kuyrukta -> calisiyor -> tamamlandi |
    basarisiz | hata | yarida_kaldi. aciklama hatada, ozet sonuç üreten
    işlerde (toplu analiz, backtest, canlı veri) dolar; deneme_sayisi >1 ise
    görev işçisi durduğu için yeniden kuyruğa alınmıştır."""

    durum: str
    tur: str | None = None
    ucus_numarasi: str | None = None
    tarih: str | None = None
    aciklama: str | None = None
    ozet: list[dict] | None = None
    deneme_sayisi: int = 0
    olusturulma_zamani: datetime | None = None
    baslama_zamani: datetime | None = None
    bitis_zamani: datetime | None = None


class EsiklerYaniti(BaseModel):
    """harita3d.html gibi istemcilerin, config.py'deki renklendirme
    eşiklerini Python tarafındaki değerlerle bire bir aynı tutması için."""

    ti1_esik_hafif: float
    ti1_esik_orta_siddetli: float
    ti1_esik_orta_siddetli_gfs: float | None = None
    ti1_guvenilirlik_notu: str | None = None


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
    # koridor: büyük daire etrafında yanal ızgara; ats: yüklü ATS yolu/FRA ağı.
    arama_uzayi: Literal["koridor", "ats"] = "koridor"
    # ats modunda: ToC/ToD bu meydanların AIP FRA kalkış/varış bağlantı noktalarına bağlanır.
    kalkis_meydani: str | None = Field(default=None, pattern=r"^[A-Z]{4}$")
    varis_meydani: str | None = Field(default=None, pattern=r"^[A-Z]{4}$")
    topluluk: bool = False
    kalkis_penceresi: bool = False

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
    fl: int | None = None
    # TI1 hesaplanamadıysa (kapsam dışı) ti1 ve riskli None'dır; "riskli değil" anlamına gelmez.
    ti1: float | None = None
    birlesik_edr: float | None = None
    riskli: bool | None = None
    ti1_asim_olasiligi: float | None = None


class RiskliBolumYaniti(BaseModel):
    """Ardışık riskli noktalar: dispeçer dilinde yer, zaman, seviye ve uzunluk."""

    baslangic_utc: str
    bitis_utc: str
    fl: int
    uzunluk_nm: float
    sure_dk: float
    baslangic_enlem: float
    baslangic_boylam: float
    bitis_enlem: float
    bitis_boylam: float
    maks_ti1: float
    maks_birlesik_edr: float | None = None
    beklenen_siddet: str | None = None


class KabinOnerisiYaniti(BaseModel):
    metin: str
    ilk_bolum_baslangic_utc: str
    pencere_baslangic_utc: str
    pencere_bitis_utc: str
    pencere_payi_dk: float
    pencere_payi_notu: str
    bolum_sayisi: int
    toplam_sure_dk: float


class RotaSonucuYaniti(BaseModel):
    noktalar: list[RotaNoktasiYaniti]
    toplam_sure_dk: float
    mesafe_km: float
    tahmini_yakit_kg: float
    tahmini_co2_kg: float
    # None: sabit yakıt tablosu (NOx yalnız OpenAP modelinde hesaplanır).
    tahmini_nox_kg: float | None = None
    maks_yanal_sapma_km: float | None = None
    # Büyük daireye göre en büyük sapmanın yönü (seyir yönüne bakarak): L sol, R sağ.
    maks_yanal_sapma_yonu: Literal["L", "R"] | None = None
    irtifa_ft: float | None = None
    maks_ti1: float | None = None
    # None: risk hesaplanmadı (kapsam dışı / veri yok); 0 risk değildir.
    riskli_nokta_sayisi: int | None = 0
    fl: int | None = None
    riskli_bolumler: list[RiskliBolumYaniti] | None = None
    riskli_mesafe_nm: float | None = None
    riskli_sure_dk: float | None = None
    kapsam_disi_nokta_sayisi: int | None = None
    # Yer hızı − TAS (kt); + kuyruk rüzgârı, − baş rüzgârı.
    ortalama_ruzgar_bileseni_kt: float | None = None
    # Kalıcı iz bulutu duyarlı nokta sayısı (fizik/iz_bulutu.py); küpte ERA5
    # nemi yoksa None. Gözlenmiş iz bulutu değil, duyarlılık göstergesidir.
    iz_bulutu_nokta_sayisi: int | None = None
    sigmet_ihlali_sayisi: int = 0
    kisitli_saha_ihlali_sayisi: int = 0


class SigmetOzetiYaniti(BaseModel):
    id: int | None = None
    fir_kodu: str | None = None
    tehlike: str
    taban_ft: int | None = None
    tavan_ft: int | None = None
    gecerlilik_baslangic: datetime
    gecerlilik_bitis: datetime
    poligon: list[list[float]]
    hareket_yonu_derece: float | None = None
    hareket_hizi_kt: float | None = None
    yanal_tampon_nm: float | None = None


class SigmetTamponuYaniti(BaseModel):
    """Kaçınmada poligona eklenen pay; parametrik varsayım, kalibre edilmedi."""

    yanal_nm: dict[str, float] = {}
    dikey_ft: float = 0.0
    aciklama: str | None = None


class SigmetKontroluYaniti(BaseModel):
    """durum: uygulandi | aktif_sigmet_yok | erisilemedi. bayat_mi: canlı
    (şimdiye yakın) bir hesapta son SIGMET çekimi config.SIGMET_BAYATLIK_DAKIKA'dan eski."""

    durum: str
    aktif_sigmet_sayisi: int = 0
    son_guncelleme: datetime | None = None
    bayat_mi: bool = False
    sorunlu_kaynaklar: list[str] = []
    sigmetler: list[SigmetOzetiYaniti] = []
    # Uçuş penceresinin SIGMET yayın ufkunun (şimdi + yayin_ufku_saat) ötesine
    # düşen kısmı: yok | kismi | tam (o kısım için SIGMET henüz yayımlanmamış olabilir).
    yayin_ufku_disi: str = "yok"
    yayin_ufku_saat: float | None = None
    tampon: SigmetTamponuYaniti | None = None


class KisitliSahaYaniti(BaseModel):
    id: int | None = None
    dis_kimlik: str | None = None
    ad: str
    tur: str
    kaynak: str | None = None
    taban_ft: int | None = None
    tavan_ft: int | None = None
    gecerlilik_baslangic: datetime | None = None
    gecerlilik_bitis: datetime | None = None
    poligon: list[list[float]]
    aciklama: str | None = None
    # NULL: geçerlilik içinde her zaman aktif; aksi halde {araliklar, haftalik} (UTC).
    aktivasyon: dict | None = None


class KisitliSahaKontroluYaniti(BaseModel):
    """durum: uygulandi | kisitli_saha_yok | erisilemedi. muaf_tutulanlar:
    kalkış/varış noktasını içerdiği için uygulanmayan sahalar. ornek_veri_mi:
    sahalardan biri paketle gelen ÖRNEK veriden (resmi değil)."""

    durum: str
    uygulanan_saha_sayisi: int = 0
    muaf_tutulanlar: list[str] = []
    ornek_veri_mi: bool = False
    sahalar: list[KisitliSahaYaniti] = []


class KisitliSahaIceAktarmaYaniti(BaseModel):
    kaydedilen: int
    kaldirilan: int


class SigmetYenilemeYaniti(BaseModel):
    """kaynak_hatalari boş değilse o kaynağın mevcut SIGMET'leri korunmuştur
    (akış çekilemedi ya da güvenilir değil); kaynaklar: kaynak başına sayım."""

    kaydedilen: int
    sonlandirilan: int
    silinen: int
    kaynak_hatalari: dict[str, str]
    kaynaklar: dict[str, dict] = {}


class RotaBulgusuYaniti(BaseModel):
    """'aciklama' metnindeki her cümlenin makine-okunur karşılığı; istemci
    (EFB) metni ayrıştırmadan kendi dilinde gösterebilir. seviye: bilgi |
    uyari | kritik. kod örnekleri: veri_gfs_tahmin, veri_era5, ti1_risk_yok,
    ti1_risk_var, ruzgar_hesaba_katilamadi, sigmet_erisilemedi,
    sigmet_uygulandi, sigmet_bayat, sigmet_ufuk_disi, kisitli_saha_erisilemedi,
    kisitli_saha_uygulandi, kisitli_saha_uc_koridoru, kisitli_saha_ornek_veri,
    guvenli_rota_yok, sapma_gereksiz, kacinma_sert_kisit, kacinma_tam_guvenli,
    ti1_riski_kismen_kaldi."""

    kod: str
    seviye: Literal["bilgi", "uyari", "kritik"]
    parametreler: dict = {}


class KapsamYaniti(BaseModel):
    safha: str
    arama_uzayi: str = "koridor"
    aciklama: str


class AtsNoktasiYaniti(BaseModel):
    """Uçuş planı biçimine yakın: 'yol' bu noktaya gelen hava yolu (DCT: doğrudan)."""

    nokta: str
    yol: str | None = None


class AtsRotaYaniti(BaseModel):
    kaynak: str
    etiket: str = ""
    normal_rota: list[AtsNoktasiYaniti]
    optimize_rota: list[AtsNoktasiYaniti]
    buyuk_daire_km: float
    uyarilar: list[str] = []


class PlanlamaUfkuYaniti(BaseModel):
    """kullanim: gecmis_analiz | ucus_oncesi_planlama. tahmin_ufku_disi: kalkış
    canlı GFS tahmin ufkundan ileride (rüzgar/TI1 yok)."""

    kullanim: str
    kalkisa_kalan_saat: float
    tahmin_ufku_saat: int
    sigmet_yayin_ufku_saat: float
    tahmin_ufku_disi: bool
    guvenilir_ongoru_saat: int | None = None
    ongoru_belirsiz: bool = False


class RotaSecenegiYaniti(BaseModel):
    """Zaman-risk seçeneği (Pareto): sert kısıtlara uyan ve süre/yakıt ile riskli
    nokta sayısında başka bir seçenek tarafından baskılanmayan rota."""

    strateji: str
    onerilen: bool
    toplam_sure_dk: float
    ek_sure_dk: float
    tahmini_yakit_kg: float
    tahmini_nox_kg: float | None = None
    ek_yakit_yuzde: float
    riskli_nokta_sayisi: int | None
    iz_bulutu_nokta_sayisi: int | None = None
    maks_ti1: float | None = None
    irtifa_ft: float
    maks_yanal_sapma_km: float = 0.0
    noktalar: list[RotaNoktasiYaniti]


class UretimBilgisiYaniti(BaseModel):
    """Sonucun hangi yazılım sürümü, hava verisi, eşik ve (varsa) modelle
    üretildiği; hesaplanmayan alanlar None'dır."""

    yazilim_surumu: str
    yazilim_commit: str | None = None
    uretim_zamani: str
    hava_verisi: dict | None = None
    esikler: dict
    model: dict | None = None
    parametreler: dict = {}


class RuzgarKazanciYaniti(BaseModel):
    sure_dk: float
    yakit_yuzde: float


class KacinmaBedeliYaniti(BaseModel):
    ek_sure_dk: float
    ek_yakit_yuzde: float


class ReferansKarsilastirmasiYaniti(BaseModel):
    """Tasarrufu ikiye ayırır: büyük daire -> rüzgâr-optimum (yalnız rüzgâr) ve
    rüzgâr-optimum -> optimize rota (kaçınmanın bedeli). Rüzgâr-optimum rota risk
    katmanlarını yok sayar; kendi riskli_nokta_sayisi'ni taşır."""

    referans: Literal["ruzgar_optimum_koridor", "ats_planli", "buyuk_daire"]
    ruzgar_optimum_rota: RotaSonucuYaniti | None = None
    ruzgar_kazanci: RuzgarKazanciYaniti | None = None
    kacinma_bedeli: KacinmaBedeliYaniti | None = None


class YakitModeliYaniti(BaseModel):
    kaynak: Literal["openap", "sabit"]
    baslangic_kutle_kg: float | None = None
    kutle_orani_notu: str
    aciklama: str
    openap_surumu: str | None = None


class IzBulutuSeviyeSecenegiYaniti(BaseModel):
    fl: int
    duyarli_nokta_sayisi: int | None = None


class IzBulutuSeviyeBilgisiYaniti(BaseModel):
    fl: int
    duyarli_nokta_sayisi: int
    secenekler: list[IzBulutuSeviyeSecenegiYaniti]
    aciklama: str


class DikeyKesitYaniti(BaseModel):
    fl: list[int]
    mesafe_nm: list[float]
    ti1: list[list[float | None] | None]
    esik: float
    basinc_seviyeleri_hpa: list[float]
    aciklama: str


class KalkisPenceresiSatiriYaniti(BaseModel):
    fark_saat: int
    kalkis_utc: str
    veri: str
    normal_riskli_sure_dk: float | None = None
    optimize_riskli_sure_dk: float | None = None
    optimize_sure_dk: float | None = None
    optimize_yakit_kg: float | None = None
    strateji: str
    guvenli_rota_bulundu_mu: bool


class KalkisPenceresiYaniti(BaseModel):
    bilgi_notu: str
    satirlar: list[KalkisPenceresiSatiriYaniti]
    hatalar: list[dict] = []


class FplMadde15Yaniti(BaseModel):
    madde15: str
    nokta_sayisi: int
    aciklama: str


class YakitBandiYaniti(BaseModel):
    kutle_oranlari: list[float]
    yakit_tasarrufu_yuzde: list[float | None]
    en_dusuk: float | None = None
    en_yuksek: float | None = None
    aciklama: str


class ToplulukRotaOzetiYaniti(BaseModel):
    en_yuksek: float | None = None
    yari_ve_ustu_nokta_sayisi: int = 0
    hesaplanan_nokta_sayisi: int = 0


class ToplulukYaniti(BaseModel):
    hesaplandi_mi: bool
    neden: str | None = None
    uye_sayisi: int = 0
    kosular: list[str] = []
    eksik_kosular: list[dict] = []
    esik: float | None = None
    rotalar: dict[str, ToplulukRotaOzetiYaniti] = {}
    aciklama: str


class RotaSimulasyonuYaniti(BaseModel):
    ruzgar_verisi_kaynagi: str
    aciklama: str
    bulgular: list[RotaBulgusuYaniti] = []
    ucak_modeli: str
    ucak_etiketi: str
    turbulanstan_kacinildi_mi: bool
    kacinma_stratejisi: str
    sigmetten_kacinildi_mi: bool = False
    kisitli_sahadan_kacinildi_mi: bool = False
    guvenli_rota_bulundu_mu: bool = True
    sigmet_kontrolu: SigmetKontroluYaniti | None = None
    kisitli_saha_kontrolu: KisitliSahaKontroluYaniti | None = None
    normal_rota: RotaSonucuYaniti
    optimize_rota: RotaSonucuYaniti
    referans_karsilastirmasi: ReferansKarsilastirmasiYaniti | None = None
    # Yalnızca önerilen rotada kalan risk varsa dolu (karar kaptanındır).
    kabin_onerisi: KabinOnerisiYaniti | None = None
    dikey_kesit: DikeyKesitYaniti | None = None
    iz_bulutu_seviye_bilgisi: IzBulutuSeviyeBilgisiYaniti | None = None
    fpl_madde15: FplMadde15Yaniti | None = None
    # Var olan sonucun 3 satırlık özeti (rota, kalan risk, kabin); yeni hesap yok.
    brifing_karti: list[str] = []
    sure_tasarrufu_dk: float
    ti1_guvenilirlik_notu: str
    yakit_modeli: YakitModeliYaniti | None = None
    uretim_bilgisi: UretimBilgisiYaniti | None = None
    yakit_tasarrufu_yuzde: float
    co2_farki_kg: float
    yakit_tasarrufu_yuzde_araligi: YakitBandiYaniti | None = None
    secenekler: list[RotaSecenegiYaniti] = []
    kapsam: KapsamYaniti | None = None
    planlama_ufku: PlanlamaUfkuYaniti | None = None
    ats: AtsRotaYaniti | None = None
    topluluk: ToplulukYaniti | None = None
    kalkis_penceresi: KalkisPenceresiYaniti | None = None
    czml: list[dict]


class UcakProfiliYaniti(BaseModel):
    kod: str
    etiket: str
    tas_ms: float
    yakit_akisi_kg_saat: float


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
    veri_kaynagi: str | None = None
    ti1_indeksi: float | None = None
    ti1_riskli_mi: bool | None = None
    ti1_guvenilirlik_notu: str = TI1_GUVENILIRLIK_NOTU
    ml_riski_var_mi: bool | None = None
    ml_olasilik: float | None = None
    ml_risk_durumu: Literal["dusuk_risk", "yuksek_risk", "belirsiz"] | None = None
    ml_konformal_hedef_kapsama: float | None = None
    ml_konformal_notu: str | None = None
    uretim_bilgisi: UretimBilgisiYaniti | None = None
    aciklama: str


class ModelVersiyonuOzetiYaniti(BaseModel):
    """model_versiyonlari/manifest.json'daki bir kaydın özeti -- tam
    ModelBilgisiYaniti'nin aksine sadece listelemede gösterilecek alanlar."""

    versiyon_id: str
    secilen_model: str
    metrikler: dict
    egitim_zamani: str


class ModelBilgisiYaniti(BaseModel):
    """turbulans_ml_modeli.model_bilgisini_yukle()'nin döndürdüğü metadata --
    ml_egitimi.py çalıştırılıp model henüz kaydedilmediyse SADECE
    egitildi_mi=False döner (uydurma bilgi üretilmez)."""

    egitildi_mi: bool
    secilen_model: str | None = None
    metrikler: dict | None = None
    ozellik_sutunlari: list[str] | None = None
    egitim_orneklem_sayisi: int | None = None
    test_orneklem_sayisi: int | None = None
    egitim_zamani: str | None = None
    veri_kaynagi: str | None = None
    kullanimda: bool | None = None
    uyari: str | None = None
    konformal: dict | None = None


class HavaDurumuKupuYaniti(BaseModel):
    """hava_durumu_kupleri kataloğundaki bir küp (bkz. kup_katalogu.py)."""

    kaynak: str
    model_calisma_zamani: datetime | None = None
    gecerlilik_baslangic: datetime
    gecerlilik_bitis: datetime
    enlem_min: float
    enlem_maks: float
    boylam_min: float
    boylam_maks: float
    basinc_seviyeleri_hpa: list[float]
    dosya_adi: str
    durum: str = "hazir"
    boyut_bayt: int | None = None


class CanliVeriIstegi(BaseModel):
    """POST /veri/canli/hazirla -- bir bölge/zaman için canlı GFS küpünü
    önceden indirir (örn. n8n her GFS döngüsünden sonra sık kullanılan
    bölgeler için), böylece ilk rota isteği indirme süresini beklemez."""

    enlem_min: float = Field(ge=-90, le=90)
    enlem_maks: float = Field(ge=-90, le=90)
    boylam_min: float = Field(ge=-180, le=180)
    boylam_maks: float = Field(ge=-180, le=180)
    baslangic: datetime | None = None
    saat_sayisi: int = Field(default=12, ge=1, le=120)
    bildirim_webhook_url: str | None = None


class BacktestYakitiYaniti(BaseModel):
    ucak_modeli_varsayimi: str
    karsilastirilabilir: bool
    gercek_yakit_kg: float
    gercek_nox_kg: float
    gercek_ortalama_tas_ms: float
    buyuk_daire_yakit_kg: float
    optimize_yakit_kg: float
    aciklama: str


class BacktestSonucuYaniti(BaseModel):
    """rota_backtest.py -- gerçek iz vs büyük daire vs A* rotası (aynı ölçütle).
    *_riskli_oran: TI1 >= eşik nokta oranı (hava verisi yoksa None).
    Bağımsız kanıt (bkz. bagimsiz_kanit.py; kaynak kapsamıyorsa None):
    *_turb_sigmet: aktif TURB/MTW SIGMET'ine giren nokta + bacak sayısı (A* bunları
    görmez); *_pirep_raporu / *_mog_pirep: rota tüpündeki türbülans raporları /
    orta ve üstü olanlar. kanit_kaynaklari: kanıtı sağlayan kaynaklar."""

    ucus_numarasi: str
    tarih: str
    ucak_modeli: str
    seyir_irtifasi_ft: float
    veri_kaynagi: str
    kacinma_stratejisi: str
    guvenli_rota_bulundu_mu: bool
    gercek_mesafe_km: float
    gercek_sure_dk: float
    gercek_riskli_oran: float | None = None
    gercek_sigmet_ihlali: int
    buyuk_daire_mesafe_km: float
    buyuk_daire_sure_dk: float
    buyuk_daire_riskli_oran: float | None = None
    buyuk_daire_sigmet_ihlali: int
    optimize_mesafe_km: float
    optimize_sure_dk: float
    optimize_riskli_oran: float | None = None
    optimize_sigmet_ihlali: int
    kanit_kaynaklari: list[str] | None = None
    gercek_turb_sigmet: int | None = None
    gercek_pirep_raporu: int | None = None
    gercek_mog_pirep: int | None = None
    buyuk_daire_turb_sigmet: int | None = None
    buyuk_daire_pirep_raporu: int | None = None
    buyuk_daire_mog_pirep: int | None = None
    optimize_turb_sigmet: int | None = None
    optimize_pirep_raporu: int | None = None
    optimize_mog_pirep: int | None = None
    olusturulma_zamani: datetime | None = None
    # Yalnız yeni çalıştırmanın yanıtında (OpenAP); veritabanına yazılmaz.
    yakit: BacktestYakitiYaniti | None = None


class BacktestListesiYaniti(BaseModel):
    ozet: dict
    sonuclar: list[BacktestSonucuYaniti]


class WsBiletiYaniti(BaseModel):
    bilet: str
    gecerlilik_saniye: int


class DenetimKaydiYaniti(BaseModel):
    """GET /api/v1/denetim -- bir değiştirici isteğin denetim kaydı."""

    id: int
    zaman: datetime
    kimlik: str
    rol: str | None = None
    yontem: str
    yol: str
    durum_kodu: int
    istemci_ip: str | None = None
    sure_ms: int


class SanalPirepOlayiYaniti(BaseModel):
    """M6: ADS-B izinden seyir fazı irtifa sapması. Ham büyüklüktür; EDR ya
    da şiddet sınıfı değildir. ucak_sayisi: POST yanıtında kayıt anındaki,
    GET'te olayın kümesindeki farklı uçak sayısı (kendisi dahil)."""

    id: int | None = None
    ucak: str | None = None
    icao24: str | None = None
    ucus_numarasi: str | None = None
    kaynak: str
    zaman: datetime
    baslangic: datetime
    bitis: datetime
    enlem: float
    boylam: float
    seviye_ft: float
    sapma_ft: float
    maks_dikey_hiz_ftdk: float | None = None
    sure_sn: float
    irtifa_kaynagi: str | None = None
    ucak_sayisi: int = 1
    bildirim_zamani: datetime | None = None


class SanalPirepKumesiYaniti(BaseModel):
    kume: int
    olay_sayisi: int
    ucak_sayisi: int
    ilk_zaman: datetime
    son_zaman: datetime
    enlem: float
    boylam: float
    seviye_ft: float
    maks_sapma_ft: float
    dogrulanmis: bool


class SanalPirepListesiYaniti(BaseModel):
    kumeler: list[SanalPirepKumesiYaniti]
    olaylar: list[SanalPirepOlayiYaniti]
    aciklama: str


class SanalPirepIzYaniti(BaseModel):
    nokta_sayisi: int
    seyir_suresi_sn: float
    olay_sayisi: int
    kaydedilen: int
    bildirilen: int
    olaylar: list[SanalPirepOlayiYaniti]
