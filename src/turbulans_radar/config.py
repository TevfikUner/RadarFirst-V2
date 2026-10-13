"""
config.py
-----------
Sabitler, eşik değerleri. Her değer, kodda hiçbir değişiklik yapmadan bir
ortam değişkeniyle EZİLEBİLİR (bkz. _ortam_str/_ortam_sayi/_ortam_bool) --
örn. staging'de daha sıkı bir hız sınırı denemek veya farklı bir ortamda
farklı bir HAVA_DURUMU_DOSYASI kullanmak için kodu değiştirip yeniden
deploy etmek gerekmez, sadece ortam değişkenini ayarlamak yeterlidir.
Hiçbir ortam değişkeni verilmezse aşağıdaki varsayılanlar kullanılır -- bu
yüzden mevcut davranış hiçbir ek ayar yapılmadan AYNEN korunur.

Buradaki değerler SIR DEĞİLDİR (host adı, eşik değeri, dosya adı gibi) --
gerçek kimlik bilgileri (şifre, API anahtarı) burada değil kimlik_dogrulama.py
ve veritabani.py'nin okuduğu '.env' dosyasında tutulur.
"""

import os

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


def _ortam_str(isim, varsayilan):
    return os.environ.get(isim, varsayilan)


def _ortam_sayi(isim, varsayilan, tip=float):
    deger = os.environ.get(isim)
    return tip(deger) if deger is not None else varsayilan


def _ortam_bool(isim, varsayilan):
    deger = os.environ.get(isim)
    if deger is None:
        return varsayilan
    return deger.strip().lower() in ("1", "true", "evet", "yes")


# depo/veritabani.py -- bağlantı havuzu boyutu. SQLAlchemy'nin varsayılanı
# (pool_size=5, max_overflow=10) her iki motor (senkron + asenkron) için de
# API konteynerindeki gerçek eşzamanlılığı hesaba katmaz: aynı anda
# AGIR_HESAP_MAKS_ESZAMANLI ağır A*/tahmin hesabı (her biri SIGMET/kısıtlı
# saha/küp katalogu için senkron motoru asyncio.to_thread içinde kullanır),
# GOREV_ISCI_SAYISI gömülü işçi iş parçacığı ve sıradan liste/detay istekleri
# AYNI havuzu paylaşır. pool_timeout, havuz dolduğunda isteğin sonsuza kadar
# asılı kalması yerine açık bir hatayla (ve 503/Retry-After'a çevrilebilir
# şekilde) başarısız olmasını sağlar.
#
# WEB_CONCURRENCY > 1 iken her uvicorn süreci iki motor açar: varsayılanlarla
# 4 süreç 240 bağlantıya çıkabilir, PostgreSQL max_connections 100'dür.
# Değerler ortamda açıkça verilmediyse API süreçlerinin toplamı
# VERITABANI_API_BAGLANTI_BUTCESI'ne sığacak şekilde küçültülür (kalanı
# worker, yedek ve araçlar içindir). Tek süreçte varsayılanlar değişmez.
VERITABANI_API_BAGLANTI_BUTCESI = _ortam_sayi("VERITABANI_API_BAGLANTI_BUTCESI", 60, int)


def havuz_boyutlari(surec_sayisi: int, butce: int, boyut: int, tasma: int) -> tuple[int, int]:
    """Motor başına (pool_size, max_overflow): surec_sayisi x 2 motor x (boyut + tasma) <= butce."""
    tavan = max(2, butce // (2 * max(1, surec_sayisi)))
    yeni_boyut = min(boyut, max(1, tavan // 3))
    return yeni_boyut, max(0, min(tasma, tavan - yeni_boyut))


def _havuz_ayari(boyut_adi: str, tasma_adi: str) -> tuple[int, int]:
    boyut = _ortam_sayi(boyut_adi, 10, int)
    tasma = _ortam_sayi(tasma_adi, 20, int)
    if boyut_adi in os.environ or tasma_adi in os.environ:
        return boyut, tasma
    surec = _ortam_sayi("WEB_CONCURRENCY", 1, int) if (os.environ.get("WEB_CONCURRENCY") or "").strip() else 1
    return havuz_boyutlari(surec, VERITABANI_API_BAGLANTI_BUTCESI, boyut, tasma)


VERITABANI_HAVUZ_BOYUTU, VERITABANI_HAVUZ_TASMA = _havuz_ayari("VERITABANI_HAVUZ_BOYUTU", "VERITABANI_HAVUZ_TASMA")
VERITABANI_HAVUZ_ZAMAN_ASIMI_SANIYE = _ortam_sayi("VERITABANI_HAVUZ_ZAMAN_ASIMI_SANIYE", 10.0)
ASYNC_VERITABANI_HAVUZ_BOYUTU, ASYNC_VERITABANI_HAVUZ_TASMA = _havuz_ayari(
    "ASYNC_VERITABANI_HAVUZ_BOYUTU", "ASYNC_VERITABANI_HAVUZ_TASMA"
)
ASYNC_VERITABANI_HAVUZ_ZAMAN_ASIMI_SANIYE = _ortam_sayi("ASYNC_VERITABANI_HAVUZ_ZAMAN_ASIMI_SANIYE", 10.0)

HAVA_DURUMU_DOSYASI = _ortam_str("HAVA_DURUMU_DOSYASI", "ocak_2019_turbulans.nc")

# Ana küpe EK olarak taranan ERA5 küpleri klasörü (bkz.
# veri_yukleme.kapsayan_veri_kupunu_bul): analiz/rota/tahmin, noktaları en
# iyi kapsayan küpü otomatik seçer. Varsayılan, ml_veri_indir.py'nin gerçek
# ABD (Kuzeydoğu, 2018-2020, seçili günler) küplerini indirdiği klasördür.
# Boş bırakılırsa sadece HAVA_DURUMU_DOSYASI kullanılır.
EK_HAVA_DURUMU_KLASORU = _ortam_str("EK_HAVA_DURUMU_KLASORU", "era5_egitim_verisi")

ERA5_UCUS_KLASORU = _ortam_str("ERA5_UCUS_KLASORU", "era5_ucus_verisi")
# Uçuşa özel ERA5 dilimine eklenen değişkenler (CDS istek sayısı aynı, dosya
# ~%30 büyür): bağıl nem iz bulutu duyarlılığı için (fizik/iz_bulutu.py).
ERA5_UCUS_EK_DEGISKENLER = tuple(
    d.strip() for d in _ortam_str("ERA5_UCUS_EK_DEGISKENLER", "relative_humidity").split(",") if d.strip()
)
# Fizik özellikleri (kayma, Ri) uçağı çevreleyen katmandan alınır; 25 hPa'lık
# seviyeler jet çekirdeğindeki ince katmanı (Ri < 0,25) görünür kılar. ML deposu
# ile aynı küme: eğitim ve kullanım aynı katman kalınlığını görür.
ERA5_BASINC_SEVIYELERI_HPA = tuple(
    float(s) for s in _ortam_str("ERA5_BASINC_SEVIYELERI_HPA", "350,300,250,225,200,175,150").split(",") if s.strip()
)
ERA5_YAYIN_GECIKMESI_GUN = _ortam_sayi("ERA5_YAYIN_GECIKMESI_GUN", 5, int)
ERA5_UCUS_MAKS_SAAT = _ortam_sayi("ERA5_UCUS_MAKS_SAAT", 24, int)
ERA5_UCUS_MAKS_HUCRE_SAAT = _ortam_sayi("ERA5_UCUS_MAKS_HUCRE_SAAT", 500_000, int)
ARCO_ERA5_URL = _ortam_str("ARCO_ERA5_URL", "gs://gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3")
ARCO_ONBELLEK_KLASORU = _ortam_str("ARCO_ONBELLEK_KLASORU", "era5_arco_onbellek")
ARCO_MAKS_SAAT = _ortam_sayi("ARCO_MAKS_SAAT", 12, int)
ARCO_ONBELLEK_MAKS_GB = _ortam_sayi("ARCO_ONBELLEK_MAKS_GB", 20.0)
DAGITIK_KILIT_ZAMAN_ASIMI_SANIYE = _ortam_sayi("DAGITIK_KILIT_ZAMAN_ASIMI_SANIYE", 1800.0)
# Birden çok API süreci (WEB_CONCURRENCY > 1) varken dış servise giden
# zamanlayıcıları (SIGMET, openAIP, ML gece işi) yalnızca lider kilidini tutan
# süreç çalıştırır; diğerleri bu aralıkla liderliği devralmayı dener.
ZAMANLAYICI_LIDER_YOKLAMA_SANIYE = _ortam_sayi("ZAMANLAYICI_LIDER_YOKLAMA_SANIYE", 60.0)
CDS_GUNLUK_MAKS_ISTEK = _ortam_sayi("CDS_GUNLUK_MAKS_ISTEK", 150, int)
# cdsapi istemcisi geçici hatada varsayılan olarak 500 kez (120 sn arayla)
# yeniden dener; bir arızada saatlerce istek göndermesin diye sınırlanır
# (10 deneme ≈ en fazla ~20 dk). Ardışık CDS istekleri arasına nezaket beklemesi.
CDS_ISTEMCI_MAKS_DENEME = _ortam_sayi("CDS_ISTEMCI_MAKS_DENEME", 10, int)
CDS_ISTEKLER_ARASI_SANIYE = _ortam_sayi("CDS_ISTEKLER_ARASI_SANIYE", 5.0)

ML_PIREP_ARSIV_KLASORU = _ortam_str("ML_PIREP_ARSIV_KLASORU", "pirep_ham")
ML_MIN_IRTIFA_FT = _ortam_sayi("ML_MIN_IRTIFA_FT", 28000.0)
ML_MAKS_IRTIFA_FT = _ortam_sayi("ML_MAKS_IRTIFA_FT", 42000.0)
ML_GUNLUK_MAKS_PIREP = _ortam_sayi("ML_GUNLUK_MAKS_PIREP", 100, int)
ML_GRUP_MAKS_HUCRE_SAAT = _ortam_sayi("ML_GRUP_MAKS_HUCRE_SAAT", 400_000, int)
ML_MAKS_DENEME = _ortam_sayi("ML_MAKS_DENEME", 3, int)
ML_GECE_MAKS_CDS_ISTEK = _ortam_sayi("ML_GECE_MAKS_CDS_ISTEK", 30, int)
# Veri işinin (CDS + MADIS) UTC günü başına indirme bütçesi (depo/veri_butcesi.py).
# Ölçülen CDS isteği ort. ~13 MB (1-20 MB); 500 MB ≈ 30 CDS isteği + 1 MADIS günü. 0 = kapalı.
GUNLUK_VERI_BUTCESI_MB = _ortam_sayi("GUNLUK_VERI_BUTCESI_MB", 500.0)
# "SS:DD" (UTC) verilirse API, ML gece işini (POST /ml/gece-isi ile aynı) her gün
# bu saatte kendisi kuyruğa alır; n8n gerekmez. API o saatte kapalıysa aynı gün
# açıldığında bir kez telafi eder. Boş = kapalı (docker-compose varsayılanı 23:07).
ML_GECE_ISI_SAATI = _ortam_str("ML_GECE_ISI_SAATI", "").strip()
# Görev yarıda kalır/hata verirse (ör. bilgisayar uykuya geçti) aynı gün en fazla bu kadar deneme.
ML_GECE_GUNLUK_MAKS_DENEME = _ortam_sayi("ML_GECE_GUNLUK_MAKS_DENEME", 3, int)
ML_IEM_BASLANGIC = _ortam_str("ML_IEM_BASLANGIC", "2020-04-01")
ML_IEM_GECELIK_MAKS_GUN = _ortam_sayi("ML_IEM_GECELIK_MAKS_GUN", 7, int)
# Eşleşme bekleyen PIREP bu sayıyı aşınca IEM'den yeni gün çekilmez (gece ~300-800 eşleşme yapılıyor). 0 = sınırsız.
ML_IEM_MAKS_BEKLEYEN = _ortam_sayi("ML_IEM_MAKS_BEKLEYEN", 5000, int)
# IEM'in yazılı hız sınırı yok; günlük PIREP istekleri arasında nezaket beklemesi.
ML_IEM_ISTEKLER_ARASI_SANIYE = _ortam_sayi("ML_IEM_ISTEKLER_ARASI_SANIYE", 2.0)
# Açılışta ağ/DNS hazır olmadan başlayan gece işi için: yalnızca istek sunucuya ulaşmadığında yeniden dener.
ML_IEM_AG_DENEME = _ortam_sayi("ML_IEM_AG_DENEME", 3, int)
ML_IEM_AG_BEKLEME_SANIYE = _ortam_sayi("ML_IEM_AG_BEKLEME_SANIYE", 60.0)
# veri/madis_edr.py (M1): NOAA MADIS herkese açık ACARS arşivi, uçak EDR ölçümleri.
# Saatlik dosya ~2-3 MB; gece işi en fazla MADIS_GECE_MAKS_GUN gün (24 dosya/gün)
# indirir, dosyalar arası bekleme, günlük dosya tavanı (veritabanı sayacı).
MADIS_ARSIV_URL = _ortam_str("MADIS_ARSIV_URL", "https://madis-data.ncep.noaa.gov/madisPublic1/data/archive")
MADIS_EDR_KLASORU = _ortam_str("MADIS_EDR_KLASORU", "madis_edr")
MADIS_ISTEKLER_ARASI_SANIYE = _ortam_sayi("MADIS_ISTEKLER_ARASI_SANIYE", 5.0)
MADIS_GUNLUK_MAKS_DOSYA = _ortam_sayi("MADIS_GUNLUK_MAKS_DOSYA", 48, int)
MADIS_GECE_ETKIN = _ortam_bool("MADIS_GECE_ETKIN", True)
MADIS_GECE_MAKS_GUN = _ortam_sayi("MADIS_GECE_MAKS_GUN", 1, int)
MADIS_MIN_IRTIFA_FT = _ortam_sayi("MADIS_MIN_IRTIFA_FT", ML_MIN_IRTIFA_FT)
# Makullük üst sınırı (QC'siz 'Z' veride aşırı değerleri eler); ICAO şiddetli eşiğinin çok üstü.
MADIS_EDR_MAKS = _ortam_sayi("MADIS_EDR_MAKS", 1.5)
# ICAO Annex 3 §2.6 tepe EDR (m^(2/3) s^-1): hafif 0.1-0.4, orta 0.4-0.7, şiddetli > 0.7
# (A41-WP/235). Aynı EDR farklı uçak tiplerinde farklı hissedilir; ayarlanabilir.
EDR_ESIK_HAFIF = _ortam_sayi("EDR_ESIK_HAFIF", 0.1)
EDR_ESIK_ORTA = _ortam_sayi("EDR_ESIK_ORTA", 0.4)
EDR_ESIK_SIDDETLI = _ortam_sayi("EDR_ESIK_SIDDETLI", 0.7)
ML_MIN_ORNEK = _ortam_sayi("ML_MIN_ORNEK", 300, int)
ML_MIN_GUN = _ortam_sayi("ML_MIN_GUN", 60, int)
ML_HOLDOUT_ORANI = _ortam_sayi("ML_HOLDOUT_ORANI", 0.2)
ML_MIN_HOLDOUT_ORNEK = _ortam_sayi("ML_MIN_HOLDOUT_ORNEK", 50, int)
# Terfi kapısı (Uzman Madde 7): aday hem TI1'i hem aktif modeli altın test günlerinde
# eşleştirilmiş ROC-AUC farkıyla geçmeli: nokta farkı >= üstünlük VE gün bazlı
# bootstrap %95 GA alt sınırı > 0. 0,02 parametriktir, kalibre edilmedi.
ML_TI1_AUC_USTUNLUGU = _ortam_sayi("ML_TI1_AUC_USTUNLUGU", 0.02)
ML_SAMPIYON_AUC_USTUNLUGU = _ortam_sayi("ML_SAMPIYON_AUC_USTUNLUGU", 0.02)
# Altın test günleri bir kez seçilip dosyaya dondurulur (turbulans-ml --altin-gunleri-dondur);
# bu günler hiçbir eğitime girmez. Dosya yoksa zamansal holdout (ML_HOLDOUT_ORANI) kullanılır.
ML_ALTIN_TEST_DOSYASI = _ortam_str(
    "ML_ALTIN_TEST_DOSYASI", os.path.join(os.path.dirname(__file__), "ml", "altin_test_gunleri.json")
)
ML_ALTIN_TEST_TOHUM = _ortam_sayi("ML_ALTIN_TEST_TOHUM", 0, int)
# ml/degerlendirme.py -- gün bazlı blok bootstrap tekrar sayısı (güven aralıkları ve
# modelin TI1'e karşı eşleştirilmiş ROC-AUC farkı; bkz. docs/deney_protokolu.md).
ML_BOOTSTRAP_TEKRAR = _ortam_sayi("ML_BOOTSTRAP_TEKRAR", 1000, int)
# ml/belirsizlik.py -- konformal tahmin kümesinin hata payı: gerçek sınıf kümede en
# az 1-alfa olasılıkla bulunur (0.10 -> %90). Küme iki sınıfı da içeriyorsa (ya da
# hiçbirini) yanıt "belirsiz" olur. ML_KARAR_ESIGI: ml_riski_var_mi için olasılık
# eşiği (risk iştahı; düşürmek daha çok uyarı, yükseltmek daha az uyarı demektir).
# Verilmezse modelin eğitim günlerinde Peirce'ı maksimize eden eşiği, o da yoksa 0.5.
ML_KONFORMAL_ALFA = _ortam_sayi("ML_KONFORMAL_ALFA", 0.10)
# ml/model_butunlugu.py -- True: sha256 kaydı olmayan model dosyası yüklenmez (varsayılan kapalı:
# eski modeller `turbulans-ml --muhurle` ile mühürlenene kadar uyarıyla yüklenir).
MODEL_BUTUNLUK_ZORUNLU = _ortam_bool("MODEL_BUTUNLUK_ZORUNLU", False)
# arayuz/web_arayuzu.py (Streamlit) kayıtlı uçuş silme isteğini bu API'ye yönetici anahtarıyla gönderir.
API_TABAN_URL = _ortam_str("API_TABAN_URL", "http://localhost:8000")
ML_KARAR_ESIGI = _ortam_sayi("ML_KARAR_ESIGI", None)
ML_ESKI_MODELI_KULLAN = _ortam_bool("ML_ESKI_MODELI_KULLAN", False)
# ml/ozellik_deposu.py -- gece işinin indirdiği ERA5 dilimi silinmeden önce her
# PIREP'in çevresindeki pencere (±PENCERE_DERECE, ±PENCERE_SAAT, tüm seviyeler)
# bu klasöre yazılır; yeni bir özellik CDS'e gitmeden yeniden hesaplanabilir.
# Depo açıkken ML indirmesi ML_DEPO_BASINC_SEVIYELERI_HPA ve ek değişkenleri
# (bağıl nem) içerir; özellikler ERA5_BASINC_SEVIYELERI_HPA alt kümesinden
# hesaplanır (varsayılanda ikisi aynı 7 seviye). Boş klasör = kapalı.
ML_DEPO_KLASORU = _ortam_str("ML_DEPO_KLASORU", "ml_ozellik_deposu")
ML_DEPO_BASINC_SEVIYELERI_HPA = tuple(
    float(s) for s in _ortam_str("ML_DEPO_BASINC_SEVIYELERI_HPA", "350,300,250,225,200,175,150").split(",") if s.strip()
)
ML_DEPO_EK_DEGISKENLER = tuple(
    d.strip() for d in _ortam_str("ML_DEPO_EK_DEGISKENLER", "relative_humidity").split(",") if d.strip()
)
ML_DEPO_PENCERE_DERECE = _ortam_sayi("ML_DEPO_PENCERE_DERECE", 1.0)
ML_DEPO_PENCERE_SAAT = _ortam_sayi("ML_DEPO_PENCERE_SAAT", 1, int)
ERA5_OTOMATIK_INDIRME = _ortam_bool("ERA5_OTOMATIK_INDIRME", True)

OPENSKY_ONBELLEK_KLASORU = _ortam_str("OPENSKY_ONBELLEK_KLASORU", "opensky_onbellek")
OPENSKY_ONBELLEK_MIN_YAS_SAAT = _ortam_sayi("OPENSKY_ONBELLEK_MIN_YAS_SAAT", 24, int)

# Depoyla gelen, kimlik bilgisi gerektirmeyen demo paketi (bkz. demo/README.md):
# <klasör>/era5/*.nc yerel küp olarak taranır, <klasör>/opensky_onbellek/ rota
# önbelleğinin salt okunur yedeğidir. Boş bırakılırsa devre dışı.
DEMO_VERI_KLASORU = _ortam_str("DEMO_VERI_KLASORU", "demo")

# OpenSky Trino Veritabanı Ayarları
# ÖNEMLİ: OpenSky 2024'te yeni backend'e geçti. Catalog "opensky" DEĞİL,
# "minio"; schema ise "osky". Kaynak: resmi doküman
# https://openskynetwork.github.io/opensky-api/trino.html
TRINO_HOST = _ortam_str("TRINO_HOST", "trino.opensky-network.org")
TRINO_PORT = _ortam_sayi("TRINO_PORT", 443, int)
TRINO_CATALOG = _ortam_str("TRINO_CATALOG", "minio")
TRINO_SCHEMA = _ortam_str("TRINO_SCHEMA", "osky")

# Trino artık state_vectors_data4 gibi tablolarda 'hour' partition
# sütununda filtre ZORUNLU tutuyor (partition filtresi olmayan sorgular
# Trino 479+ tarafından otomatik reddediliyor). Bu yüzden veri_yukleme.py
# her state-vector sorgusuna hour filtresi de ekliyor.
MAKS_STATE_VECTOR_SATIRI = _ortam_sayi("MAKS_STATE_VECTOR_SATIRI", 50_000, int)

# OpenSky Trino kuralları (openskynetwork.github.io/opensky-api/trino.html): kullanıcı
# başına en fazla 2 eşzamanlı + 2 kuyrukta sorgu, sorgu başına 30 dk; tekrarlanan
# ihlal hesabı askıya aldırır. Sistem genelinde (tüm süreçler) aynı anda yalnızca
# bir sorgu çalışır (dağıtık kilit) ve günlük sorgu sayısı burada sınırlanır
# (bir uçuş = 2 sorgu; yeniden denemeler de sayılır).
OPENSKY_GUNLUK_MAKS_SORGU = _ortam_sayi("OPENSKY_GUNLUK_MAKS_SORGU", 400, int)
OPENSKY_SORGU_KILIDI_BEKLEME_SANIYE = _ortam_sayi("OPENSKY_SORGU_KILIDI_BEKLEME_SANIYE", 1800.0)

# veri_yukleme.py -- bu boyuttan (MB) küçük küpler tamamen belleğe yüklenir;
# büyükleri (örn. GB boyutlu ERA5 arşivi) sadece rotanın bölge/zaman
# penceresiyle okunur. Tüm yüklenen küp/pencereler KUP_ONBELLEK_MAKS_MB
# bütçeli bir LRU önbellekte tutulur (bütçe aşılınca en eski atılır).
KUP_TAM_YUKLEME_ESIGI_MB = _ortam_sayi("KUP_TAM_YUKLEME_ESIGI_MB", 256.0)
KUP_ONBELLEK_MAKS_MB = _ortam_sayi("KUP_ONBELLEK_MAKS_MB", 2048.0)

# Copernicus/ERA5 veri küpündeki basınç seviyesi boyutunun adı.
# (eslestirme.py bunu kullanıyordu ama tanımlı değildi -- eksikti, eklendi.)
BASINC_BOYUTU = _ortam_str("BASINC_BOYUTU", "pressure_level")

# Bir noktanın basıncı, veri küpündeki en alçak/en yüksek basınç seviyesinden
# bu kadar (hPa) fazla uzaksa irtifa olarak kapsam dışı sayılır (bkz.
# eslestirme._kapsam_disi_maskesi_hesapla). 50 hPa = tipik ERA5 seviye aralığı;
# 200-300 hPa küpünde yaklaşık FL265-FL445 kabul edilir.
DIKEY_KAPSAM_TOLERANSI_HPA = _ortam_sayi("DIKEY_KAPSAM_TOLERANSI_HPA", 50.0)

# Ellrod TI1 indeksi için şiddet eşikleri (s^-2 cinsinden). Hafif eşiği
# Ellrod & Knapp (1992) çevresindeki kaba bir başlangıç değeridir (yalnız
# görsel sınıf). Risk eşiği (orta ve üstü) veriden seçildi (Madde 8, 8 Ekim
# 2026): altın test günleri dışındaki 64 günde, Peirce'i en yüksek eşiğin
# (5,3e-7) gün bazlı bootstrap 1 SE'si içindeki en tutucu eşik 7,06e-7
# (degerlendirme.bir_se_esigi; model seçimindeki 1-SE kuralıyla aynı mantık:
# beceride eşdeğer seçenekler arasında daha az yanlış alarm). Eski 8e-7 bu
# bandın dışındaydı. 18 Ekim nihai paketinde aynı kuralla yeniden hesaplanır
# (sonuc_paketi.json: esik_taramasi.bir_se). Kesin bir eşik değildir.
TI1_ESIK_HAFIF = _ortam_sayi("TI1_ESIK_HAFIF", 4e-7)
TI1_ESIK_ORTA_SIDDETLI = _ortam_sayi("TI1_ESIK_ORTA_SIDDETLI", 7e-7)
# Dispeç ekranında bundan kısa riskli bölümler listelenmez. 0 = her riskli nokta
# (mevcut davranış); eşik kalibre edilmedi.
RISKLI_BOLUM_MIN_NM = _ortam_sayi("RISKLI_BOLUM_MIN_NM", 0.0)

# turbulans_indeksleri.ti1_den_edr_proxy_olcegine_cevir()'in kullandığı
# ölçeklendirme katsayısı. 2026-10-05 sürümü (Madde 2 fiziği: çevreleyen
# katman, metrik terimler, hipsometrik kalınlık): ml_ornekleri'ndeki seyir
# irtifası IEM PIREP'leri (ABD, 6218 örnek, 64 gün) + saatlik ERA5 ile
# yeniden kalibre edildi (turbulans-edr-kalibrasyon): 0.27, gün bazlı
# bootstrap %95 GA [0.25, 0.28]; zamansal test (son 13 gün, 1151 örnek) MSE
# 0.076 (önceki 0.40: 0.082, eski 0.23: 0.076). Tanh ölçeği sabit ortalama
# tahmininden (MSE 0.067) daha kötü tahmin eder: görselleştirme ölçeğidir,
# risk için ML olasılığı kullanılmalı. 0.40 (2026-10-01) eski fizikle uyduruldu.
# Eski 0.23, 300-400 FEET'teki PIREP'lerle (hatalı irtifa filtresi) uyduruldu.
# Bu "TI1 görsel ölçeği"dir, EDR değildir: katsayı EDR ölçümüne değil PIREP sınıf
# koduna (sinif/2) uydurulur (MET-05, VRB-09); bölgeden bağımsız bir ilişkiye dayanır.
EDR_OLCEKLENDIRME_KATSAYISI = _ortam_sayi("EDR_OLCEKLENDIRME_KATSAYISI", 0.27)
EDR_OLCEKLENDIRME_KATSAYISI_ESKI = 0.23
# Eski adı EDR_OLCEKLENDIRME_KATSAYISI_KALIBRE_EDILDI ("kalibre" EDR'ye kalibrasyon sanılıyordu).
TI1_GORSEL_OLCEK_PIREP_SINIFINA_UYDURULDU = _ortam_bool("TI1_GORSEL_OLCEK_PIREP_SINIFINA_UYDURULDU", True)

# toplu_analiz.py, art arda çok sayıda uçuş için Trino/OpenSky sorgusu atar.
# OpenSky gibi servisler kısa sürede çok fazla istek gönderen hesapları
# rate-limit/ban riskiyle karşı karşıya bırakabildiği için, uçuşlar arasına
# bilerek küçük bir bekleme koyuyoruz.
TOPLU_ANALIZ_ISTEKLER_ARASI_BEKLEME_SANIYE = _ortam_sayi("TOPLU_ANALIZ_ISTEKLER_ARASI_BEKLEME_SANIYE", 2.0)

# Üretilen dosyaların (harita HTML'leri, toplu analiz özet CSV'si) yazıldığı
# klasör. Önceden bunlar proje köküne (kaynak koduyla aynı yere) yazılıyordu
# -- her çalıştırma proje klasörünü biraz daha dağıtıyordu. Artık hepsi tek
# bir alt klasörde toplanıyor (main.py/toplu_analiz.py bu klasörü yoksa
# otomatik oluşturur).
CIKTI_KLASORU = _ortam_str("CIKTI_KLASORU", "ciktilar")
# Yeni harita üretilirken CIKTI_KLASORU'ndaki bundan (gün) eski
# turbulans_haritasi_*.html dosyaları silinir (0 = kapalı). Ham veri
# PostgreSQL'de durduğu için harita her zaman yeniden üretilebilir.
CIKTI_SAKLAMA_GUN = _ortam_sayi("CIKTI_SAKLAMA_GUN", 30, int)

# harita.py'nin ürettiği zaman kaydırıcılı animasyon (TimestampedGeoJson),
# nokta sayısı arttıkça ağırlaşan bir HTML üretir -- 50.000 noktalık bir
# uçuşta tarayıcı gözle görülür şekilde yavaşlıyordu. Rota bu sayıdan uzunsa,
# SADECE animasyon noktaları eşit aralıklarla seyreltilir (ham veri zaten
# PostgreSQL'de tam haliyle duruyor, bu sadece görselleştirme içindir).
HARITA_MAKS_ANIMASYON_NOKTASI = _ortam_sayi("HARITA_MAKS_ANIMASYON_NOKTASI", 2000, int)

# rota_optimizasyonu.py -- 3D uçuş simülasyonu (web/ucus_simulasyonu.html)
# için üretilen rota kaç ara noktadan oluşsun. Fazla nokta CZML animasyonunu
# pürüzsüzleştirir ama rüzgar-optimal rota aramasını (her aday x her nokta
# için bir ERA5 okuması) yavaşlatır.
ROTA_SIMULASYONU_NOKTA_SAYISI = _ortam_sayi("ROTA_SIMULASYONU_NOKTA_SAYISI", 41, int)

# A*'ın yanal ızgarası (bkz. rota_optimizasyonu._YanalIzgara): her bacağın
# büyük daire yönüne göre azami açısı, toplam azami yanal sapma ve azami ızgara
# aralığı. Açı sınırı, kısa rotada keskin zikzakları, uzun rotada gereksiz dar
# koridoru önler (sınır adım sayısıyla değil mesafeyle ölçeklenir).
ROTA_MAKS_SAPMA_ACISI_DERECE = _ortam_sayi("ROTA_MAKS_SAPMA_ACISI_DERECE", 30.0)
ROTA_MAKS_YANAL_SAPMA_KM = _ortam_sayi("ROTA_MAKS_YANAL_SAPMA_KM", 400.0)
ROTA_YANAL_IZGARA_KM = _ortam_sayi("ROTA_YANAL_IZGARA_KM", 20.0)
# Zaman-risk seçenekleri (Pareto): önerilen rotaya ek olarak A* bu TI1 ceza
# değerleriyle (riskli düğüm başına saniye) yeniden çalıştırılır; sert
# kısıtlara (SIGMET, kısıtlı saha) uyan ve süre/yakıt ile riskli nokta
# sayısında birbirine üstün olmayan rotalar dispeçere seçenek olarak sunulur.
# Boş = kapalı.
ROTA_PARETO_CEZALARI_SANIYE = [
    float(d) for d in _ortam_str("ROTA_PARETO_CEZALARI_SANIYE", "300,60,0").split(",") if d.strip()
]
# A*, sert kısıtların (SIGMET, kısıtlı saha) zamanını rüzgarsız hesaplar;
# gerçek varış rüzgarla kayar. Düğüm zamanı, kalkıştan geçen sürenin bu oranı
# + sabit pay kadar belirsiz sayılır (jet seviyesinde ~70 m/s rüzgar TAS'ın
# ~%30'u; yanal sapma yolu da uzatır).
ROTA_ZAMAN_BELIRSIZLIK_ORANI = _ortam_sayi("ROTA_ZAMAN_BELIRSIZLIK_ORANI", 0.3)
ROTA_ZAMAN_BELIRSIZLIK_PAYI_DAKIKA = _ortam_sayi("ROTA_ZAMAN_BELIRSIZLIK_PAYI_DAKIKA", 5.0)
# rota/ucus_seviyeleri.py: yarım daire kuralı manyetik ize göre uygulanır.
# Manyetik sapma (doğu +) tüm rotalar için SABİT alınır: Türkiye için ~+5°E
# VARSAYIMDIR (NOAA WMM ile teyit edilmedi; ABD/Avrupa dışı rotalarda yanlış olabilir).
MANYETIK_SAPMA_DERECE = _ortam_sayi("MANYETIK_SAPMA_DERECE", 5.0)
# rota/hava_yolu_agi.py -- ATS yolları / FRA ağı (AIP'ten elle hazırlanır, depoya
# konmaz; bkz. docs/veri_hazirlama/ATS_AGI_HAZIRLAMA.md). ToC/ToD ağa en yakın
# ATS_AGI_BAGLANTI_SAYISI noktaya (en fazla ATS_AGI_BAGLANTI_KM) DCT bağlanır;
# uzun segmentler risk kontrolü için ATS_AGI_ARA_NOKTA_KM'lik parçalara bölünür.
ATS_AGI_DOSYASI = _ortam_str("ATS_AGI_DOSYASI", os.path.join("ats_verisi", "ats_agi.json"))
ATS_AGI_BAGLANTI_KM = _ortam_sayi("ATS_AGI_BAGLANTI_KM", 150.0)
ATS_AGI_BAGLANTI_SAYISI = _ortam_sayi("ATS_AGI_BAGLANTI_SAYISI", 3, int)
ATS_AGI_ARA_NOKTA_KM = _ortam_sayi("ATS_AGI_ARA_NOKTA_KM", 60.0)
# Meydan verilince ToC/ToD'nin o meydanın AIP FRA bağlantı noktalarına (A/D)
# en uzak bağlantısı (km); AIP'te sınır yok, saçma uzun bağlantıyı önlemek için.
ATS_AGI_MEYDAN_BAGLANTI_KM = _ortam_sayi("ATS_AGI_MEYDAN_BAGLANTI_KM", 500.0)

# isci/gorev_iscisi.py -- uzun işlerin kuyruğu (analiz_gorevleri). API kendi
# içinde gömülü bir işçi başlatır (GOREV_GOMULU_ISCI); ayrı işçi süreçleri
# (turbulans-isci, docker-compose 'worker' servisi) kullanılıyorsa kapatılır.
# GOREV_ISCI_SAYISI: bir süreçte aynı anda çalışan en fazla görev. Kalp atışı
# GOREV_BAYAT_SANIYE'den eski görev (işçisi öldü) GOREV_MAKS_DENEME'ye kadar
# yeniden kuyruğa girer.
GOREV_GOMULU_ISCI = _ortam_bool("GOREV_GOMULU_ISCI", True)
GOREV_ISCI_SAYISI = _ortam_sayi("GOREV_ISCI_SAYISI", 2, int)
GOREV_KUYRUK_BEKLEME_SANIYE = _ortam_sayi("GOREV_KUYRUK_BEKLEME_SANIYE", 1.0)
GOREV_KALP_ATISI_SANIYE = _ortam_sayi("GOREV_KALP_ATISI_SANIYE", 15.0)
GOREV_BAYAT_SANIYE = _ortam_sayi("GOREV_BAYAT_SANIYE", 120.0)
ISCI_SAGLIK_DOSYASI = _ortam_str("ISCI_SAGLIK_DOSYASI", "")
GOREV_MAKS_DENEME = _ortam_sayi("GOREV_MAKS_DENEME", 2, int)
# Ayrı işçi SIGTERM alınca çalışan görevi bu kadar bekler (ML işi süren CDS isteğini bitirip durur);
# docker-compose'daki stop_grace_period bundan uzun olmalı, yoksa Docker SIGKILL atar.
GOREV_DURDURMA_BEKLEME_SANIYE = _ortam_sayi("GOREV_DURDURMA_BEKLEME_SANIYE", 240.0)
# Boş değilse işçi sadece bu türlerdeki görevleri alır (virgülle: ucus,rota,toplu,backtest,canli_veri).
GOREV_ISCI_TURLERI = tuple(t.strip() for t in _ortam_str("GOREV_ISCI_TURLERI", "").split(",") if t.strip())

# sigmet_saglayici.py / risk_katmanlari.py -- canlı AWC SIGMET'leri.
# A*'ın SERT kısıt olarak kaçındığı tehlike türleri (AWC 'hazard' alanı):
# TURB/MTW (türbülans/dağ dalgası), TS/CONVECTIVE (oraj), VA (volkanik kül),
# TC (tropikal siklon). ICE (buzlanma) varsayılan olarak DAHİL DEĞİL -- jet
# seyir irtifasında genelde rota değil irtifa kararıdır; istenirse eklenir.
SIGMET_KACINILACAK_TEHLIKELER = tuple(
    t.strip().upper()
    for t in _ortam_str("SIGMET_KACINILACAK_TEHLIKELER", "TURB,MTW,TS,CONVECTIVE,VA,TC").split(",")
    if t.strip()
)
# Süresi dolmuş SIGMET'ler bu kadar gün saklanır (geçmiş rota kararlarının izlenebilirliği için).
SIGMET_SAKLAMA_GUN = _ortam_sayi("SIGMET_SAKLAMA_GUN", 30, int)
# Canlı (şimdiye yakın) bir rota hesabında son SIGMET çekimi bundan eskiyse yanıt "bayat" uyarısı taşır.
SIGMET_BAYATLIK_DAKIKA = _ortam_sayi("SIGMET_BAYATLIK_DAKIKA", 30, int)
# SIGMET'ler en fazla 4 sa geçerlilikle yayımlanır (VA ve TC için 6 sa; ICAO
# Annex 3 / DWD SIGMET bilgi notu, Ekim 2026). Uçuşun şimdiden bu süreden sonraki
# kısmı için henüz SIGMET yayımlanmamış olabilir; rota yanıtı bunu belirtir.
SIGMET_YAYIN_UFKU_SAAT = _ortam_sayi("SIGMET_YAYIN_UFKU_SAAT", 4.0)
# >0 ise API kendi içinde bu aralıkla (dakika) SIGMET çeker; 0 = kapalı (n8n/cron tetikler).
SIGMET_OTOMATIK_GUNCELLEME_DAKIKA = _ortam_sayi("SIGMET_OTOMATIK_GUNCELLEME_DAKIKA", 0, int)
# Bir kaynağın akışındaki SIGMET kayıtlarının bu orandan fazlası çözümlenemezse
# (AWC şema değişikliği şüphesi) çekim HATA sayılır: mevcut kayıtlar
# sonlandırılmaz, kaynak "başarılı güncelleme" almaz -- sessizce "SIGMET yok"a
# düşülmez (bkz. sigmet_saglayici._akis_sagligini_denetle).
SIGMET_MAKS_COZUMLENEMEYEN_ORAN = _ortam_sayi("SIGMET_MAKS_COZUMLENEMEYEN_ORAN", 0.25)
# Tehlike alanı okunamayan SIGMET'ler bu etiketle saklanır ve A* tarafından
# (muhafazakâr olarak) her zaman kaçınılır.
SIGMET_BILINMEYEN_TEHLIKE = "BILINMIYOR"
# Hareket yönü verilmiş ama hızı bilinmeyen ("MOV NE", spd=UNK) SIGMET için
# varsayılan en yüksek hız: alan 0 ile bu hız arasındaki tüm konumları süpürür.
SIGMET_BILINMEYEN_HIZ_KT = _ortam_sayi("SIGMET_BILINMEYEN_HIZ_KT", 30.0)
# SIGMET kaçınmasında poligona eklenen yanal (NM, tehlike türüne göre) ve dikey
# (ft, taban altı/tavan üstü) tampon. PARAMETRİK VARSAYIM, KALİBRE EDİLMEDİ:
# SIGMET poligonları kabadır; konvektif alandan ~20 NM uzak durma hat pratiği
# (FAA AC 00-24C'ye atfedilir, kaynaktan teyit edilmedi), TURB/MTW için 10 NM
# ve RVSM dikey ayırması kadar 1000 ft seçildi. Listede olmayan tür
# SIGMET_YANAL_TAMPON_VARSAYILAN_NM alır; tehlikesi bilinmeyen SIGMET en büyük
# tamponu alır (muhafazakâr). Ortam: "TS:20,CONVECTIVE:20,TURB:10,MTW:10".
SIGMET_YANAL_TAMPON_NM = {
    tur.strip().upper(): float(nm)
    for tur, nm in (
        parca.split(":")
        for parca in _ortam_str("SIGMET_YANAL_TAMPON_NM", "TS:20,CONVECTIVE:20,TURB:10,MTW:10").split(",")
        if parca.strip()
    )
}
SIGMET_YANAL_TAMPON_VARSAYILAN_NM = _ortam_sayi("SIGMET_YANAL_TAMPON_VARSAYILAN_NM", 10.0)
SIGMET_DIKEY_TAMPON_FT = _ortam_sayi("SIGMET_DIKEY_TAMPON_FT", 1000.0)
# Koordinatsız SIGMET'lerin FIR'ın tamamı olarak uygulanması için FIR sınırları
# (turbulans-statik indirir; bkz. veri/fir_sinirlari.py).
FIR_SINIRLARI_DOSYASI = _ortam_str("FIR_SINIRLARI_DOSYASI", os.path.join("veri_dosyalari", "fir_sinirlari.geojson"))

# veri_saglayicilari.py -- anlık rota için CANLI hava verisi (ERA5 reanalizi
# birkaç gün gecikmeli yayınlandığı için "şimdi"yi kapsamaz). NOAA GFS 0.25°,
# UCAR THREDDS NetCDF Subset Service üzerinden NetCDF olarak alınır (GRIB2
# çözücü/ecCodes gerektirmez). Noktaları hiçbir ERA5 küpü kapsamıyorsa ve
# zaman [şimdi - CANLI_GECMIS_SAAT, şimdi + CANLI_TAHMIN_UFKU_SAAT] içindeyse
# devreye girer; indirilen küpler hava_durumu_kupleri kataloğuna kaydedilip
# yeniden kullanılır.
CANLI_HAVA_VERISI_ETKIN = _ortam_bool("CANLI_HAVA_VERISI_ETKIN", True)
GFS_THREDDS_URL = _ortam_str(
    "GFS_THREDDS_URL", "https://thredds.ucar.edu/thredds/ncss/grid/grib/NCEP/GFS/Global_0p25deg/Best"
)
CANLI_VERI_KLASORU = _ortam_str("CANLI_VERI_KLASORU", "canli_veri")
CANLI_BASINC_SEVIYELERI_HPA = tuple(
    float(s) for s in _ortam_str("CANLI_BASINC_SEVIYELERI_HPA", "200,250,300").split(",") if s.strip()
)
CANLI_GECMIS_SAAT = _ortam_sayi("CANLI_GECMIS_SAAT", 48, int)
CANLI_TAHMIN_UFKU_SAAT = _ortam_sayi("CANLI_TAHMIN_UFKU_SAAT", 120, int)
# Aynı bölge/zaman için indirilmiş bir GFS küpü, model çalıştırması bundan
# eskiyse yeniden kullanılmaz (GFS 6 saatte bir yeni döngü yayınlar).
CANLI_KUP_TAZELIK_SAAT = _ortam_sayi("CANLI_KUP_TAZELIK_SAAT", 6, int)
# Geçerliliği bu kadar saat önce bitmiş canlı küpler (dosya + katalog kaydı) silinir.
CANLI_KUP_SAKLAMA_SAAT = _ortam_sayi("CANLI_KUP_SAKLAMA_SAAT", 48, int)
CANLI_ISITMA_SAAT = _ortam_sayi("CANLI_ISITMA_SAAT", 0.0)
CANLI_ISITMA_KUTUSU = tuple(float(s) for s in _ortam_str("CANLI_ISITMA_KUTUSU", "36,42,26,45").split(",") if s.strip())
CANLI_ISITMA_SAAT_SAYISI = _ortam_sayi("CANLI_ISITMA_SAAT_SAYISI", 12, int)
# Etkileşimli uçlar (rota simülasyonu, tahmin) katalogda olmayan bir canlı küp
# için en fazla bu kadar bekler; indirme arka planda sürer, yanıt rüzgarsız
# ön sonuçla "canli_veri_hazirlaniyor" döner (yavaş ağda istek askıda kalmaz).
CANLI_VERI_BEKLEME_SANIYE = _ortam_sayi("CANLI_VERI_BEKLEME_SANIYE", 8.0)
# Süreç başına aynı anda en fazla kaç farklı bölge için canlı küp indirilir;
# fazlası kuyrukta bekler (metrik: turbulans_canli_indirme{durum="bekliyor"}).
# UCAR THREDDS paylaşımlı bir kamu sunucusu olduğu için bilerek düşük tutulur.
CANLI_INDIRME_ISCI_SAYISI = _ortam_sayi("CANLI_INDIRME_ISCI_SAYISI", 2, int)

# kisitli_saha_saglayici.py -- True iken API açılışında, tabloda 'ornek'
# kaynaklı kayıt yoksa paketle gelen ÖRNEK kısıtlı sahalar (Natural Earth
# ülke sınırından Suriye/Irak) yüklenir. Resmi AIP/CZIB verisiyle çalışan bir
# kurulumda kapatılmalıdır.
KISITLI_SAHA_ORNEK_VERI_YUKLE = _ortam_bool("KISITLI_SAHA_ORNEK_VERI_YUKLE", True)
# Kalkış/varış noktasını içeren kısıtlı sahada (örn. varış ülkesi) sadece planlı
# rotanın (büyük daire) bu kadar km çevresi serbesttir; sahanın geri kalanına
# sapma önerilmez.
KISITLI_SAHA_UC_KORIDORU_KM = _ortam_sayi("KISITLI_SAHA_UC_KORIDORU_KM", 100.0)
# openaip_saglayici.py -- gerçek kısıtlı saha verisi (OPENAIP_API_ANAHTARI .env'de).
# Türler (openAIP kodları): 1 Restricted, 2 Danger, 3 Prohibited, 8 TRA, 9 TSA.
OPENAIP_ULKELER = tuple(u.strip() for u in _ortam_str("OPENAIP_ULKELER", "TR").split(",") if u.strip())
OPENAIP_SAHA_TURLERI = tuple(int(t) for t in _ortam_str("OPENAIP_SAHA_TURLERI", "1,3").split(",") if t.strip())
# >0 ise API, openAIP kısıtlı sahalarını bu aralıkla (saat) işçi kuyruğu
# üzerinden yeniler (OPENAIP_API_ANAHTARI gerekir; AIRAC döngüsü 28 gün, NOTAM
# kaynaklı değişiklikler için günlük önerilir). 0 = kapalı (n8n/cron tetikler).
OPENAIP_OTOMATIK_GUNCELLEME_SAAT = _ortam_sayi("OPENAIP_OTOMATIK_GUNCELLEME_SAAT", 0.0)
# GND referanslı üst limite eklenen arazi payı (arazi yüksekliği bilinmiyor; muhafazakâr).
OPENAIP_AGL_UST_PAYI_FT = _ortam_sayi("OPENAIP_AGL_UST_PAYI_FT", 15000.0)

# api_servisi.py -- pilot anahtarının da çağırabildiği CPU ağır uçlar: istemci
# (rol + IP) başına dakikalık istek sınırı ve süreç başına aynı anda en fazla
# kaç A*/tahmin hesabı çalışacağı. Tavan doluysa istek en fazla
# AGIR_HESAP_BEKLEME_SANIYE bekler, sonra 503 + Retry-After döner.
ROTA_HESABI_DAKIKADA_MAKS = _ortam_sayi("ROTA_HESABI_DAKIKADA_MAKS", 20, int)
TAHMIN_DAKIKADA_MAKS = _ortam_sayi("TAHMIN_DAKIKADA_MAKS", 60, int)
# POST /api/v1/sanal-pirep/iz: havayolu ADS-B beslemesi uçak başına sık iz gönderebilir.
SANAL_PIREP_IZ_DAKIKADA_MAKS = _ortam_sayi("SANAL_PIREP_IZ_DAKIKADA_MAKS", 120, int)
# veri/canli_adsb.py -- süreli canlı ADS-B oturumu (sanal PIREP için). Varsayılan
# kapalı. adsb.fi açık veri sınırı saniyede 1 istek; oturum aralığı onun 10 katı.
CANLI_ADSB_ETKIN = _ortam_bool("CANLI_ADSB_ETKIN", False)
CANLI_ADSB_SAGLAYICILAR = tuple(
    s.strip() for s in _ortam_str("CANLI_ADSB_SAGLAYICILAR", "adsb_fi,adsb_lol").split(",") if s.strip()
)
CANLI_ADSB_ARALIK_SANIYE = _ortam_sayi("CANLI_ADSB_ARALIK_SANIYE", 10.0)
CANLI_ADSB_MIN_ARALIK_SANIYE = _ortam_sayi("CANLI_ADSB_MIN_ARALIK_SANIYE", 5.0)
CANLI_ADSB_SURE_DK = _ortam_sayi("CANLI_ADSB_SURE_DK", 15.0)
CANLI_ADSB_MAKS_SURE_DK = _ortam_sayi("CANLI_ADSB_MAKS_SURE_DK", 60.0)
CANLI_ADSB_GUNLUK_MAKS_ISTEK = _ortam_sayi("CANLI_ADSB_GUNLUK_MAKS_ISTEK", 1000, int)
CANLI_ADSB_429_BEKLEME_SANIYE = _ortam_sayi("CANLI_ADSB_429_BEKLEME_SANIYE", 300.0)
CANLI_ADSB_HATA_BEKLEME_SANIYE = _ortam_sayi("CANLI_ADSB_HATA_BEKLEME_SANIYE", 60.0)
CANLI_ADSB_MERKEZ_ENLEM = _ortam_sayi("CANLI_ADSB_MERKEZ_ENLEM", 39.0)
CANLI_ADSB_MERKEZ_BOYLAM = _ortam_sayi("CANLI_ADSB_MERKEZ_BOYLAM", 35.0)
CANLI_ADSB_YARICAP_NM = _ortam_sayi("CANLI_ADSB_YARICAP_NM", 250.0)
CANLI_ADSB_KULLANICI_AJANI = _ortam_str(
    "CANLI_ADSB_KULLANICI_AJANI", "TurbulansRadar/1.0 (KTUN bitirme projesi; ticari olmayan arastirma)"
)
AGIR_HESAP_MAKS_ESZAMANLI = _ortam_sayi("AGIR_HESAP_MAKS_ESZAMANLI", 4, int)
AGIR_HESAP_BEKLEME_SANIYE = _ortam_sayi("AGIR_HESAP_BEKLEME_SANIYE", 15.0)
# api/rota_onbellegi.py -- aynı rota isteğinin sonucu bu kadar saniye yeniden
# kullanılır (0 = kapalı). SIGMET/kısıtlı saha API'de değişince anında
# boşaltılır; worker'daki değişiklikler en geç bu süre sonra yansır.
ROTA_ONBELLEK_SANIYE = _ortam_sayi("ROTA_ONBELLEK_SANIYE", 60.0)
ROTA_ONBELLEK_MAKS_KAYIT = _ortam_sayi("ROTA_ONBELLEK_MAKS_KAYIT", 256, int)
# Birden çok API süreci varken önbellek PostgreSQL'de paylaşılır (süreç başına
# önbellekte isabet oranı düşüyordu, PERFORMANS_RAPORU H6); temizlik her
# sürece ve worker'a anında yansır. Varsayılan: WEB_CONCURRENCY > 1 ise açık.
ROTA_ONBELLEK_PAYLASIMLI = _ortam_bool(
    "ROTA_ONBELLEK_PAYLASIMLI", (os.environ.get("WEB_CONCURRENCY") or "1").strip() not in ("", "1")
)

# api_servisi.py -- her isteğin gövdesi (Content-Length ya da chunked ise
# akış sırasında sayılarak) bu boyutu (MB) aşarsa 413 ile erken reddedilir.
# Starlette/FastAPI, boyut kontrolünden ÖNCE gövdeyi tamamen belleğe okur --
# bu sınır olmadan (örn. yönetici anahtarı sızmışsa) POST /kisitli-sahalar
# gibi ham `dict` gövdesi alan uçlar keyfi büyüklükte bir bellek sıçramasına
# açık kalırdı; MAKS_OZELLIK/MAKS_KOSE gibi alan bazlı sınırlar da zaten
# gövde TAMAMEN ayrıştırıldıktan SONRA devreye giriyor.
MAKS_ISTEK_GOVDESI_MB = _ortam_sayi("MAKS_ISTEK_GOVDESI_MB", 20.0)

# api_servisi.py /ws/uyarilar -- istemci başına bekleyen en fazla mesaj ve tek
# mesajın gönderim zaman aşımı; aşan (yavaş/donmuş) istemci düşürülür, diğer
# pilotların uyarıları beklemez.
WS_ISTEMCI_KUYRUK_BOYUTU = _ortam_sayi("WS_ISTEMCI_KUYRUK_BOYUTU", 100, int)
WS_GONDERIM_ZAMAN_ASIMI_SANIYE = _ortam_sayi("WS_GONDERIM_ZAMAN_ASIMI_SANIYE", 5.0)

# depo/denetim.py -- API denetim kayıtları bu kadar gün saklanır.
DENETIM_SAKLAMA_GUN = _ortam_sayi("DENETIM_SAKLAMA_GUN", 180, int)

# Anahtarsız /saglik?derin=true yanıtı bu kadar saniye önbellekte tutulur
# (0 = kapalı); yönetici /api/v1/sistem/durum her zaman taze hesaplanır.
SAGLIK_ONBELLEK_SANIYE = _ortam_sayi("SAGLIK_ONBELLEK_SANIYE", 15.0)
# Sağlık raporunda uyarı eşikleri: son başarılı ML gece işi ve son yedek bundan eskiyse.
# Bilgisayar günlerce kapalı kaldıysa uyarı beklenen ve doğru bir durumdur.
SAGLIK_ML_GECE_MAKS_YAS_SAAT = _ortam_sayi("SAGLIK_ML_GECE_MAKS_YAS_SAAT", 48.0)
YEDEK_KLASORU = _ortam_str("YEDEK_KLASORU", "db_yedekleri")
SAGLIK_YEDEK_MAKS_YAS_SAAT = _ortam_sayi("SAGLIK_YEDEK_MAKS_YAS_SAAT", 36.0)
# Canlı GFS isteğe bağlı indirilir: bu süredir başarılı indirme yoksa ve hata da yoksa durum 'bosta'.
SAGLIK_GFS_BOSTA_SAAT = _ortam_sayi("SAGLIK_GFS_BOSTA_SAAT", 24.0)

# turbulans_ml_modeli.py -- aktif model, bilgi JSON'u ve model_versiyonlari/
# bu klasörde tutulur. Docker aynı proje klasörünü /app/model_deposu'na bağlar
# (bkz. docker-compose.yml): konteyner ile yerel araçlar aynı modeli görür.
MODEL_KLASORU = _ortam_str("MODEL_KLASORU", "model_deposu")

# rota_backtest.py -- gerçek uçuşla karşılaştırılan A* rotasında kullanılan
# uçak profili (bkz. rota_optimizasyonu.UCAK_PROFILLERI).
BACKTEST_UCAK_MODELI = _ortam_str("BACKTEST_UCAK_MODELI", "A320")

# fizik/sanal_pirep.py (M6) -- ADS-B izinden seyir fazı irtifa sapması olayları.
# Başlangıç eşikleri kalibre EDİLMEMİŞTİR; dayanakları:
#   sapma: RVSM otopilot irtifa tutma toleransı ±65 ft (türbülanssız düz uçuş)
#          + ADS-B barometrik irtifa kuantizasyonu 25 ft = 90 ft
#   düşey hız tutarlılığı: ADS-B düşey hız kuantizasyonu 64 ft/dk'nın 2 katı;
#          düşey hız tepkisi olmayan irtifa sıçraması transponder hatası sayılır
#   seviye değişimi: RVSM toplam düşey hata sınırı 300 ft
# Seyir alt sınırı ML ile aynı (seyir irtifası PIREP tanımı). Kümeleme ve
# PIREP doğrulama tüpü bagimsiz_kanit.py'deki 50 km / ±2000 ft / ±1 sa ile aynı.
SANAL_PIREP_MIN_IRTIFA_FT = _ortam_sayi("SANAL_PIREP_MIN_IRTIFA_FT", ML_MIN_IRTIFA_FT)
SANAL_PIREP_SEVIYE_PENCERESI_SANIYE = _ortam_sayi("SANAL_PIREP_SEVIYE_PENCERESI_SANIYE", 300, int)
SANAL_PIREP_SEVIYE_DEGISIM_ESIGI_FT = _ortam_sayi("SANAL_PIREP_SEVIYE_DEGISIM_ESIGI_FT", 300.0)
SANAL_PIREP_SAPMA_ESIGI_FT = _ortam_sayi("SANAL_PIREP_SAPMA_ESIGI_FT", 90.0)
SANAL_PIREP_DIKEY_HIZ_TUTARLILIK_FTDK = _ortam_sayi("SANAL_PIREP_DIKEY_HIZ_TUTARLILIK_FTDK", 128.0)
SANAL_PIREP_MAKS_BOSLUK_SANIYE = _ortam_sayi("SANAL_PIREP_MAKS_BOSLUK_SANIYE", 30, int)
SANAL_PIREP_OLAY_BIRLESTIRME_SANIYE = _ortam_sayi("SANAL_PIREP_OLAY_BIRLESTIRME_SANIYE", 60, int)
SANAL_PIREP_KUME_YARICAPI_KM = _ortam_sayi("SANAL_PIREP_KUME_YARICAPI_KM", 50.0)
SANAL_PIREP_KUME_IRTIFA_FARKI_FT = _ortam_sayi("SANAL_PIREP_KUME_IRTIFA_FARKI_FT", 2000.0)
SANAL_PIREP_KUME_SURESI_DAKIKA = _ortam_sayi("SANAL_PIREP_KUME_SURESI_DAKIKA", 60, int)
# WebSocket'e yalnızca bu kadar farklı uçağın doğruladığı olaylar yayınlanır
# (tek uçaklık işaret seviye değişimi/otopilot geçişi olabilir).
SANAL_PIREP_BILDIRIM_MIN_UCAK = _ortam_sayi("SANAL_PIREP_BILDIRIM_MIN_UCAK", 2, int)
# dogrulama/sanal_pirep_dogrulama.py -- PIREP çevresi OpenSky sorgusu (her biri
# tek sorgu; kilit + günlük tavan veri_yukleme._sorgu_calistir'da).
SANAL_PIREP_DOGRULAMA_MAKS_SORGU = _ortam_sayi("SANAL_PIREP_DOGRULAMA_MAKS_SORGU", 20, int)
SANAL_PIREP_DOGRULAMA_PENCERE_DAKIKA = _ortam_sayi("SANAL_PIREP_DOGRULAMA_PENCERE_DAKIKA", 30, int)
# dogrulama/ayirma_gostergesi.py (hoca önerisi 4, yalnızca gösterge). Minimalar
# AIP Türkiye'den (Ekim 2026): ENR 1.6 §4.1 yatay radar ayırması asgari 5 NM;
# ENR 1.8 EUR-RVSM (FL290-FL410) RVSM onaylı uçaklar arası dikey 1000 ft.
# OpenSky: uçuş başına tek sorgu, pencere sınırlı.
AYIRMA_YATAY_NM = _ortam_sayi("AYIRMA_YATAY_NM", 5.0)
AYIRMA_DIKEY_FT = _ortam_sayi("AYIRMA_DIKEY_FT", 1000.0)
AYIRMA_ADIM_SANIYE = _ortam_sayi("AYIRMA_ADIM_SANIYE", 10, int)
AYIRMA_MAKS_PENCERE_SAAT = _ortam_sayi("AYIRMA_MAKS_PENCERE_SAAT", 3.0)
AYIRMA_ONBELLEK_KLASORU = _ortam_str("AYIRMA_ONBELLEK_KLASORU", f"{OPENSKY_ONBELLEK_KLASORU}/trafik")
SANAL_PIREP_ONBELLEK_KLASORU = _ortam_str("SANAL_PIREP_ONBELLEK_KLASORU", f"{OPENSKY_ONBELLEK_KLASORU}/pirep_cevresi")
