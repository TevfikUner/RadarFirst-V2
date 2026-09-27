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

# A*'ın yanal ızgarası (bkz. rota_optimizasyonu._YanalIzgara): her bacağın
# büyük daire yönüne göre azami açısı, toplam azami yanal sapma ve azami ızgara
# aralığı. Açı sınırı, kısa rotada keskin zikzakları, uzun rotada gereksiz dar
# koridoru önler (sınır adım sayısıyla değil mesafeyle ölçeklenir).
ROTA_MAKS_SAPMA_ACISI_DERECE = _ortam_sayi("ROTA_MAKS_SAPMA_ACISI_DERECE", 30.0)
ROTA_MAKS_YANAL_SAPMA_KM = _ortam_sayi("ROTA_MAKS_YANAL_SAPMA_KM", 400.0)
ROTA_YANAL_IZGARA_KM = _ortam_sayi("ROTA_YANAL_IZGARA_KM", 20.0)
# A*, sert kısıtların (SIGMET, kısıtlı saha) zamanını rüzgarsız hesaplar;
# gerçek varış rüzgarla kayar. Düğüm zamanı, kalkıştan geçen sürenin bu oranı
# + sabit pay kadar belirsiz sayılır (jet seviyesinde ~70 m/s rüzgar TAS'ın
# ~%30'u; yanal sapma yolu da uzatır).
ROTA_ZAMAN_BELIRSIZLIK_ORANI = _ortam_sayi("ROTA_ZAMAN_BELIRSIZLIK_ORANI", 0.3)
ROTA_ZAMAN_BELIRSIZLIK_PAYI_DAKIKA = _ortam_sayi("ROTA_ZAMAN_BELIRSIZLIK_PAYI_DAKIKA", 5.0)

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
GOREV_MAKS_DENEME = _ortam_sayi("GOREV_MAKS_DENEME", 2, int)
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
# Etkileşimli uçlar (rota simülasyonu, tahmin) katalogda olmayan bir canlı küp
# için en fazla bu kadar bekler; indirme arka planda sürer, yanıt rüzgarsız
# ön sonuçla "canli_veri_hazirlaniyor" döner (yavaş ağda istek askıda kalmaz).
CANLI_VERI_BEKLEME_SANIYE = _ortam_sayi("CANLI_VERI_BEKLEME_SANIYE", 8.0)

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
# GND referanslı üst limite eklenen arazi payı (arazi yüksekliği bilinmiyor; muhafazakâr).
OPENAIP_AGL_UST_PAYI_FT = _ortam_sayi("OPENAIP_AGL_UST_PAYI_FT", 15000.0)

# turbulans_ml_modeli.py -- aktif model, bilgi JSON'u ve model_versiyonlari/
# bu klasörde tutulur. Docker'da kalıcı bir volume'a işaret eder (bkz.
# docker-compose.yml); aksi halde geri dönüş (rollback) konteyner yeniden
# oluşturulunca kaybolurdu.
MODEL_KLASORU = _ortam_str("MODEL_KLASORU", ".")

# rota_backtest.py -- gerçek uçuşla karşılaştırılan A* rotasında kullanılan
# uçak profili (bkz. rota_optimizasyonu.UCAK_PROFILLERI).
BACKTEST_UCAK_MODELI = _ortam_str("BACKTEST_UCAK_MODELI", "A320")
