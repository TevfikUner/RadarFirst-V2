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


HAVA_DURUMU_DOSYASI = _ortam_str("HAVA_DURUMU_DOSYASI", "ocak_2019_turbulans.nc")

# Ana küpe EK olarak taranan ERA5 küpleri klasörü (bkz.
# veri_yukleme.kapsayan_veri_kupunu_bul): analiz/rota/tahmin, noktaları en
# iyi kapsayan küpü otomatik seçer. Varsayılan, ml_veri_indir.py'nin gerçek
# ABD (Kuzeydoğu, 2018-2020, seçili günler) küplerini indirdiği klasördür.
# Boş bırakılırsa sadece HAVA_DURUMU_DOSYASI kullanılır.
EK_HAVA_DURUMU_KLASORU = _ortam_str("EK_HAVA_DURUMU_KLASORU", "era5_egitim_verisi")

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

# Copernicus/ERA5 veri küpündeki basınç seviyesi boyutunun adı.
# (eslestirme.py bunu kullanıyordu ama tanımlı değildi -- eksikti, eklendi.)
BASINC_BOYUTU = _ortam_str("BASINC_BOYUTU", "pressure_level")

# Bir noktanın basıncı, veri küpündeki en alçak/en yüksek basınç seviyesinden
# bu kadar (hPa) fazla uzaksa irtifa olarak kapsam dışı sayılır (bkz.
# eslestirme._kapsam_disi_maskesi_hesapla). 50 hPa = tipik ERA5 seviye aralığı;
# 200-300 hPa küpünde yaklaşık FL265-FL445 kabul edilir.
DIKEY_KAPSAM_TOLERANSI_HPA = _ortam_sayi("DIKEY_KAPSAM_TOLERANSI_HPA", 50.0)

# Ellrod TI1 indeksi için şiddet eşikleri (s^-2 cinsinden).
# (harita.py bunları kullanıyordu ama config.py'de hiç tanımlı değildi --
# eksikti, eklendi.) Bu değerler Ellrod & Knapp (1992) literatüründeki
# tipik CAT (Clear Air Turbulence) sınıflandırma aralıklarına yakın kaba
# başlangıç değerleridir -- gerçek PIREP/AMDAR gözlemleriyle kalibre
# edilmesi önerilir, "kesin" bir eşik değildir.
TI1_ESIK_HAFIF = _ortam_sayi("TI1_ESIK_HAFIF", 4e-7)
TI1_ESIK_ORTA_SIDDETLI = _ortam_sayi("TI1_ESIK_ORTA_SIDDETLI", 8e-7)

# turbulans_indeksleri.ti1_den_edr_proxy_olcegine_cevir()'in kullandığı
# ölçeklendirme katsayısı. Gerçek IEM PIREP (ABD hava sahası, 2018-2020) +
# eşleşen gerçek ERA5 verisiyle (bkz. pirep_kalibrasyon_verisi_uret.py,
# kalibrasyon.py -- AYNI 179 örneklik gerçek gözlem seti turbulans_ml_
# modeli.py'nin eğitiminde de kullanıldı) kalibre edildi: 0.23 (ortalama
# karesel hata: 0.093). BELİRSİZLİK: 179 örneklik bootstrap ile hesaplanan
# %95 güven aralığı [0.15, 0.34] (bkz. kalibrasyon.katsayi_guven_araligi_
# hesapla) -- nokta tahmini (0.23) TEK bir sayı gibi görünse de örneklem
# küçük olduğu için gerçek belirsizlik bu kadar geniş, "kesin" bir değer
# değildir. DÜRÜSTLÜK NOTU: bu depodaki örnek veri kümesi (Türkiye/
# Ocak-2019) için gerçek PIREP/AMDAR yok (bkz. README), bu yüzden katsayı
# BÖLGEDEN BAĞIMSIZ bir fiziksel ilişkiye (TI1 -> gözlemlenen şiddet)
# dayanıyor -- ML sınıflandırıcısının özellik seçiminde de AYNI gerekçeyle
# enlem/boylam kasıtlı dışarıda bırakılmıştı. Yeniden kalibre etmek için:
# python pirep_kalibrasyon_verisi_uret.py && python kalibrasyon.py
# pirep_kalibrasyon_verisi.csv
EDR_OLCEKLENDIRME_KATSAYISI = _ortam_sayi("EDR_OLCEKLENDIRME_KATSAYISI", 0.23)
EDR_OLCEKLENDIRME_KATSAYISI_KALIBRE_EDILDI = _ortam_bool("EDR_OLCEKLENDIRME_KATSAYISI_KALIBRE_EDILDI", True)

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
