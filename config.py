
# config.py
HAVA_DURUMU_DOSYASI = "ocak_2019_turbulans.nc"

# OpenSky Trino Veritabanı Ayarları
# ÖNEMLİ: OpenSky 2024'te yeni backend'e geçti. Catalog "opensky" DEĞİL,
# "minio"; schema ise "osky". Kaynak: resmi doküman
# https://openskynetwork.github.io/opensky-api/trino.html
TRINO_HOST = "trino.opensky-network.org"
TRINO_PORT = 443
TRINO_CATALOG = "minio"
TRINO_SCHEMA = "osky"

# Trino artık state_vectors_data4 gibi tablolarda 'hour' partition
# sütununda filtre ZORUNLU tutuyor (partition filtresi olmayan sorgular
# Trino 479+ tarafından otomatik reddediliyor). Bu yüzden veri_yukleme.py
# her state-vector sorgusuna hour filtresi de ekliyor.
MAKS_STATE_VECTOR_SATIRI = 50_000

# Copernicus/ERA5 veri küpündeki basınç seviyesi boyutunun adı.
# (eslestirme.py bunu kullanıyordu ama tanımlı değildi -- eksikti, eklendi.)
BASINC_BOYUTU = "pressure_level"

# Ellrod TI1 indeksi için şiddet eşikleri (s^-2 cinsinden).
# (harita.py bunları kullanıyordu ama config.py'de hiç tanımlı değildi --
# eksikti, eklendi.) Bu değerler Ellrod & Knapp (1992) literatüründeki
# tipik CAT (Clear Air Turbulence) sınıflandırma aralıklarına yakın kaba
# başlangıç değerleridir -- gerçek PIREP/AMDAR gözlemleriyle kalibre
# edilmesi önerilir, "kesin" bir eşik değildir.
TI1_ESIK_HAFIF = 4e-7
TI1_ESIK_ORTA_SIDDETLI = 8e-7
