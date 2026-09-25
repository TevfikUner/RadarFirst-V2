# Türbülans Radar

Gerçek bir uçuşun (OpenSky/Trino) rotasını, gerçek bir hava durumu veri
küpüyle (Copernicus/ERA5) eşleştirip Ellrod TI1 indeksi ve bulk Richardson
sayısıyla türbülans şiddeti/dinamik kararsızlık tahmini üreten uçtan uca bir
sistem. Sonuçlar PostgreSQL'e yazılır, zaman kaydırıcılı bir Folium
haritasında görselleştirilir, bir FastAPI servisi ve MCP sunucusu üzerinden
JSON/veritabanı olarak dışarıya açılır.

**Önemli sınırlama:** TI1/EDR proxy, sertifikalı bir EDR (Eddy Dissipation
Rate) değeri DEĞİLDİR -- ~25-30 km çözünürlüklü reanaliz verisinden
hesaplanan bir araştırma/görselleştirme göstergesidir. Ölçeklendirme
katsayısı artık gerçek IEM PIREP + ERA5 gözlemleriyle kalibre edildi (bkz.
[Sınırlamalar](#bilinmesi-gerekenler--sınırlamalar), `kalibrasyon.py`) --
ama bu bölgeden bağımsız, kaba bir kalibrasyondur, sertifikalı bir EDR
sensörünün yerini TUTMAZ.

## Mimari

```
                         ┌─────────────────┐
  OpenSky/Trino ────────►│  veri_yukleme.py │
  (callsign→icao24→rota) └────────┬─────────┘
                                  │
  Copernicus/ERA5 (.nc) ──────────┤
                                  ▼
                          ┌───────────────┐      ┌────────────────────┐
                          │ eslestirme.py │─────►│ turbulans_indeksleri│
                          │ (TI1+Richard.)│      │ (Ellrod TI1, Ri)    │
                          └───────┬───────┘      └────────────────────┘
                                  │
                    ┌─────────────┼─────────────┐
                    ▼             ▼             ▼
             veritabani.py   harita.py      main.py /
             (PostgreSQL,    (Folium HTML)  toplu_analiz.py /
              models.py)                    web_arayuzu.py (CLI/UI)
                    │
      ┌─────────────┼─────────────────┐
      ▼             ▼                 ▼
api_servisi.py  mcp_postgres_    (Alembic ile
(FastAPI REST   sunucusu.py      şema yönetimi)
 + WebSocket)   (Claude Code
                 için salt okunur)
```

Dosya dosya kısa açıklama:

```
config.py                     -> sabitler, eşik değerleri (ortam değişkeniyle ezilebilir)
kimlik_dogrulama.py            -> .env'den güvenli OpenSky kimlik bilgisi okuma
birim_donusumleri.py           -> irtifa <-> basınç dönüşümleri (ISA formülü)
turbulans_indeksleri.py        -> Ellrod TI1 + Richardson sayısı hesabı + EDR-proxy ölçekleme
veri_yukleme.py                 -> NetCDF yükleme + OpenSky/Trino sorguları (parametreli, retry'li)
eslestirme.py                    -> uçuş rotası <-> hava durumu grid eşleştirme (vektörel)
harita.py                        -> zaman kaydırıcılı Folium haritası (büyük rotalarda seyreltilir)
main.py                          -> uçtan uca çalıştırma (CLI)
ornek_ucus_bul.py               -> OpenSky'da kayıtlı gerçek callsign'ları listeler
veri_kontrol.py                  -> veri küpü çözünürlüğünü / TI1 çeşitliliğini kontrol eder
kimlik_kontrol.py               -> .env'in doğru okunduğunu kontrol eder
kalibrasyon.py                   -> gerçek PIREP/AMDAR verisiyle EDR ölçekleme katsayısını kalibre eder
pirep_kalibrasyon_verisi_uret.py -> ML eğitimi için indirilen gerçek IEM PIREP+ERA5 verisinden kalibrasyon.py'nin beklediği gözlem CSV'sini üretir
toplu_analiz.py                  -> bir CSV listesindeki birden fazla uçuşu sırayla analiz eder
web_arayuzu.py                   -> tarayıcıdan kullanılabilir arayüz (Streamlit)
hata_yardimcisi.py               -> ham Python hatalarını anlaşılır Türkçe mesaja çevirir
veri_indirme.py                  -> ERA5 verisi otomatik indirme ALTYAPISI (gerçek indirme kapalı)
konsol_kurulumu.py               -> Windows konsolunda Türkçe/özel karakter çökmesini önler
loglama.py                        -> api_servisi.py için ortak logging yapılandırması
models.py                         -> PostgreSQL tabloları için SQLAlchemy ORM modelleri
veritabani.py                     -> PostgreSQL erişimi: senkron (CLI) + asenkron (API)
migrations/, alembic.ini          -> Alembic veritabanı şema migration'ları
semalar.py                        -> api_servisi.py için Pydantic yanıt (response) modelleri
sigmet_dogrulama.py               -> TI1'i gerçek AWC SIGMET uyarılarıyla karşılaştırır (SADECE ABD hava sahası)
web/harita3d.html                 -> tek dosyalık MapLibre GL 3D/canlı harita önyüzü (api_servisi.py sunar)
rota_optimizasyonu.py             -> gerçek ERA5 rüzgarına göre büyük daire vs yakıt-optimize rota hesabı + CZML üretimi
web/ucus_simulasyonu.html         -> tek dosyalık CesiumJS 3D uçuş simülasyonu önyüzü (api_servisi.py sunar)
web/models/ucak.glb               -> 3D uçak modeli (CesiumJS resmi örnek verisi, Apache 2.0)
turbulans_ml_modeli.py            -> gerçek IEM PIREP + ERA5 ile eğitilmiş türbülans risk sınıflandırıcısı (özellik çıkarma + tahmin)
ml_veri_indir.py                  -> ML eğitim verisi: PIREP raporlarına eşleşen gerçek ERA5 pencerelerini Copernicus CDS'ten indirir
ml_egitimi.py                     -> ML eğitim/karşılaştırma betiği (Lojistik Regresyon / Random Forest / Gradient Boosting, recall'a göre seçim)
api_servisi.py                    -> FastAPI REST API'si (API anahtarlı, /api/v1, async, WebSocket)
mcp_postgres_sunucusu.py         -> Claude Code/Desktop için salt okunur PostgreSQL MCP sunucusu
.mcp.json                          -> Claude Code'un mcp_postgres_sunucusu.py'yi tanıması için
Dockerfile, docker-compose.yml     -> tek komutla (Postgres + API) çalıştırma
.github/workflows/ci.yml           -> lint + test GitHub Actions iş akışı
pyproject.toml, .pre-commit-config.yaml -> ruff lint/format + pre-commit ayarları
tests/, pytest.ini                 -> pytest birim testleri (async testler tek event loop paylaşır)
ciktilar/                           -> üretilen harita HTML'leri ve özet CSV (git'e dahil değil)
```

## Kurulum

```bash
git clone <bu-repo>
cd files
pip install -r requirements.txt
cp .env.example .env          # OpenSky + PostgreSQL + API_ANAHTARI bilgilerini gir
alembic upgrade head          # veritabanı şemasını kur (tek seferlik)
```

`.env`'e girilmesi gerekenler (bkz. `.env.example`): `OPENSKY_USERNAME`/
`OPENSKY_PASSWORD` (OpenSky hesabı, tarihsel veri erişimi onaylanmış
olmalı -- https://opensky-network.org/my-opensky/request-data),
`POSTGRES_*` (host/port/kullanıcı/şifre/veritabanı), `API_ANAHTARI`
(`python -c "import secrets; print(secrets.token_urlsafe(32))"` ile üret).

Hava durumu veri küpünü (`ocak_2019_turbulans.nc`, Copernicus/ERA5'ten
manuel indirilmiş) proje köküne koyman gerekir -- büyük olduğu için
`.gitignore`'da, repoya dahil değildir.

### Docker ile çalıştırma (alternatif)

```bash
docker compose up --build
```

Bu, PostgreSQL'i ve `api_servisi.py`'yi (önce `alembic upgrade head`
çalıştırıp) tek komutla ayağa kaldırır. `.env` dosyanın hazır olması
gerekir; `POSTGRES_HOST` konteynerler arası iletişim için otomatik olarak
compose servis adına (`db`) çevrilir. API `http://localhost:8000`'de,
Swagger `http://localhost:8000/docs`'ta olur.

## Kullanım

### Tek bir uçuşu analiz etmek (CLI)

```bash
python ornek_ucus_bul.py                    # gerçek, o gün kayıtlı bir callsign bul
python main.py THY1234 2019-01-01           # analiz et -- PostgreSQL'e yazar + harita üretir
```

Her script `--help` ile kullanım bilgisi verir. Sonuç `ucuslar`/
`edr_olcumleri` tablolarına yazılır (aynı uçuş/tarih tekrar analiz
edilirse eski kayıt silinip yenisiyle değiştirilir); harita
`ciktilar/turbulans_haritasi_<uçuş>_<tarih>.html`'e kaydedilir.

### Web arayüzü

```bash
streamlit run web_arayuzu.py
```

Uçuş numarası ve tarihi bir kutuya yazıp "Analiz Et"e basman yeterli;
sonuç tablosu ve harita direkt sayfada görünür. Arkada aynı `main.py`
mantığı çalışır -- bu sadece görsel bir ön yüz.

### Birden fazla uçuşu birden analiz etmek

```bash
python toplu_analiz.py ucuslar.csv     # en az ucus_numarasi, tarih sütunları
```

Her uçuş kendi kaydını PostgreSQL'e yazar ve kendi haritasını üretir; ayrıca
hepsinin özetini `ciktilar/toplu_analiz_ozeti.csv`'de toplar. Bir uçuşta
hata olursa diğerlerinin analizi durmaz; OpenSky'yi yormamak için uçuşlar
arasına kısa bir bekleme konur.

### Veri kalitesini kontrol etmek

```bash
python veri_kontrol.py N10VZ 2019-01-15     # önce main.py ile analiz etmiş olman gerekir
```

Veri küpünün çözünürlüğünü (grid/zaman adımı) ve PostgreSQL'deki TI1
değerlerinin ne kadar çeşitli olduğunu (çok az benzersiz değer varsa veri
küpü muhtemelen çok kaba) kontrol eder.

## FastAPI servis katmanı

```bash
uvicorn api_servisi:app --reload --port 8000
# Swagger/OpenAPI: http://localhost:8000/docs
```

### Uç noktalar

| Metod | Yol | Açıklama |
|---|---|---|
| GET | `/saglik` | Anahtarsız sağlık kontrolü |
| GET | `/api/v1/ucuslar` | Kaydedilmiş uçuşları listeler (`limit`, 1-500; `ucus_numarasi_arama` kısmi eşleşme, `baslangic_tarih`/`bitis_tarih` ile filtrelenebilir) |
| GET | `/api/v1/ucuslar/{ucus_numarasi}/{tarih}` | Bir uçuşun ölçüm noktaları (`olcum_limit`/`olcum_offset` ile sayfalı) |
| DELETE | `/api/v1/ucuslar/{ucus_numarasi}/{tarih}` | Kayıtlı bir uçuşu (ölçümleriyle birlikte) siler -- bulunamazsa 404, silinirse 204 |
| POST | `/api/v1/analiz/ucus` | Tek bir uçuşu arka planda analiz eder, `gorev_id` döner |
| POST | `/api/v1/analiz/toplu` | Birden fazla uçuşu arka planda analiz eder |
| GET | `/api/v1/analiz/durum/{gorev_id}` | Tetiklenen bir analizin durumunu sorgular |
| GET | `/api/v1/esikler` | TI1 renklendirme eşiklerini döner (web/harita3d.html bunları kullanır) |
| GET | `/api/v1/ucuslar/{ucus_numarasi}/{tarih}/sigmet-dogrulama` | TI1'i gerçek AWC SIGMET'leriyle karşılaştırır |
| GET | `/api/v1/simulasyon/ucak-profilleri` | 3D uçuş simülasyonu için uçak modeli seçim listesi |
| POST | `/api/v1/simulasyon/rota` | Büyük daire vs rüzgar-optimize rota + CZML döner (bkz. aşağıdaki bölüm) |
| POST | `/api/v1/turbulans/tahmin` | Tek nokta için fizik (TI1) + gerçek PIREP verisiyle eğitilmiş ML tahminini karşılaştırmalı döner |
| GET | `/api/v1/turbulans/model-bilgisi` | ML modelinin seçim gerekçesi/metrikleri (recall, F1, ROC-AUC vb.) + eğitim tarihini döner; model henüz eğitilmediyse dürüstçe `egitildi_mi: false` |
| WS | `/ws/uyarilar?api_key=...` | TI1 "orta-şiddetli" eşiği aşılınca canlı uyarı yayınlar |
| GET | `/harita/harita3d.html` | 3D/canlı harita önyüzü (statik, tarayıcıda açılır) |
| GET | `/harita/ucus_simulasyonu.html` | 3D uçuş simülasyonu önyüzü (statik, tarayıcıda açılır) |

Örnek:

```bash
curl -X POST http://localhost:8000/api/v1/analiz/ucus \
  -H "X-API-Key: $API_ANAHTARI" -H "Content-Type: application/json" \
  -d '{"ucus_numarasi": "THY1234", "tarih": "2019-01-01"}'

curl http://localhost:8000/api/v1/ucuslar/THY1234/2019-01-01 \
  -H "X-API-Key: $API_ANAHTARI"
```

### Güvenlik ve sağlamlık

- **API anahtarı:** `/api/v1/*` altındaki tüm uç noktalar `X-API-Key`
  başlığı gerektirir (`.env` -> `API_ANAHTARI`), sabit zamanlı
  (`secrets.compare_digest`) karşılaştırılır. Anahtar yanlış/eksikse 401,
  sunucuda hiç tanımlı değilse 503.
- **Girdi doğrulama:** `tarih` gerçek bir tarih olarak, `ucus_numarasi`
  harf/rakam + en fazla 8 karakter olarak doğrulanır (422 döner).
- **Hata gizliliği:** 500/503 yanıtları ham exception mesajını (SQL,
  bağlantı dizesi vb.) istemciye döndürmez; tam ayrıntı sunucu tarafında
  (stderr, `loglama.py`) loglanır.
- **Hız sınırlama:** `/api/v1/analiz/*`, kendi API'sini kötüye kullanıma
  karşı bellek-içi bir pencere sayaçla korur (varsayılan: 60 saniyede en
  fazla 5 istek, aşılırsa 429) -- dışarıdan tetiklenen aşırı istekle
  OpenSky'yi dolaylı yormamak için.
- **Asenkron:** okuma uç noktaları `asyncpg` tabanlı, event loop'u
  bloklamaz. Analiz tetikleme, `main.py`/`toplu_analiz.py`'deki aynı
  (bloklayan) mantığı `asyncio.to_thread` ile ayrı bir thread'de çalıştırır.
- **CORS:** varsayılan kapalı; `.env`'deki `CORS_IZIN_VERILEN_KAYNAKLAR`
  (virgülle ayrılmış origin listesi) ile açılır.
- **Görev durumu** bellek içinde tutulur ve kendiliğinden temizlenir
  (bitmiş görevler 1 saat sonra, sözlük 5000'i aşarsa en eskiler önce
  silinir). Kalıcı bir görev kuyruğu (Celery/RQ) gerekiyorsa eklenebilir.
- **Webhook bildirimi:** `bildirim_webhook_url` verilirse, analiz bitince
  sonuç oraya POST edilir -- n8n'in Webhook node'u bunu dinleyip
  `/api/v1/analiz/durum/{gorev_id}`'yi periyodik yoklamaya gerek bırakmaz.

**Bilinçli olarak eklenmedi:** `veri_indirme.py`'nin gerçek ERA5 indirmesini
tetikleyen bir uç nokta (rate-limit/ban riski), JWT/OAuth2 kullanıcı girişi
(tek kullanıcılı/dahili bir araç için statik anahtar yeterli görüldü, çok
kullanıcılı bir sürüme geçilirse yükseltilebilir).

## 3D/canlı harita önyüzü

```bash
uvicorn api_servisi:app --reload --port 8000
# tarayıcıda aç: http://localhost:8000/harita/harita3d.html
```

`web/harita3d.html`, build aracı gerektirmeyen tek dosyalık bir MapLibre GL
JS sayfasıdır -- `api_servisi.py` tarafından API ile AYNI origin'de sunulur
(`app.mount("/harita", ...)`), bu yüzden `fetch()`/WebSocket çağrıları
CORS'a takılmaz. Sayfaya uçuş numarası, tarih ve API anahtarını (bir kez
girilir, `localStorage`'da tutulur) yazıp "Yükle"ye basman yeterli:

- Rota, `GET /api/v1/ucuslar/{ucus}/{tarih}`'ten çekilip TI1 şiddetine göre
  renklendirilmiş noktalar + çizgi olarak "globe" (3D küre) projeksiyonunda
  gösterilir; alttaki zaman kaydırıcısı ile rota an be an oynatılabilir.
- `GET /api/v1/ucuslar/{ucus}/{tarih}/sigmet-dogrulama`'dan gelen gerçek
  SIGMET poligonları (varsa) sarı bir katman olarak haritaya eklenir.
- `/ws/uyarilar`'a bağlanıp, bir analiz sırasında orta-şiddetli türbülans
  tespit edilirse ekranda anlık bir uyarı (toast) gösterir.
- Harita karosu (tile), `harita.py`'de daha önce yaşanan "CartoDB anahtar
  istemeye başladı" sorununu tekrarlamamak için YİNE anahtarsız Esri World
  Street Map'i kullanır; MapLibre CDN sürümü (5.8.0) BİLEREK sabitlendi
  (daha yeni sürümler -- 6.x -- klasik `<script>` ile çalışan UMD paketini
  kaldırıp sadece ES module dağıtıyor).

Bu sayfa gerçek bir tarayıcıda (Playwright + headless Chromium) uçtan uca
test EDİLDİ: gerçek bir uçuş (THY322, 2019-01-15, 1614 nokta) analiz edilip
sayfaya API anahtarıyla yüklendi, rota/TI1 renklendirmesi/zaman kaydırıcısı
render oldu (bkz. yukarıdaki ekran görüntüsü niteliğindeki doğrulama). Bu
test GERÇEK bir hata ortaya çıkardı ve düzeltildi: `harita.setProjection`
metodu, önceden sabitlenen MapLibre 4.7.1'de YOKTU (kod içi yorum bunun
var olduğunu YANLIŞ varsayıyordu) -- 5.8.0'a geçildi. Ardından
`setProjection`'ı `Map` constructor'ından hemen sonra çağırmanın "Style is
not done loading" hatası verdiği görüldü; "globe" projeksiyonu artık
doğrudan constructor'ın `projection` seçeneğine taşındı, `harita.on("load",
...)` içinde bir savunmacı ikinci deneme daha bırakıldı.

## 3D uçuş simülasyonu (normal rota vs türbülanstan-kaçınma rota)

```bash
uvicorn api_servisi:app --reload --port 8000
# tarayıcıda aç: http://localhost:8000/harita/ucus_simulasyonu.html
```

`web/ucus_simulasyonu.html`, `web/harita3d.html` ile AYNI desende (tek
dosyalık, build aracı yok, `api_servisi.py` API ile aynı origin'den sunar)
ama CesiumJS tabanlı bir 3D küre sayfasıdır. Başlangıç/bitiş enlem-boylamı,
irtifa, tarih-saat ve uçak modelini girip "Simüle Et"e basınca:

- `POST /api/v1/simulasyon/rota` (bkz. `rota_optimizasyonu.py`) iki GERÇEK
  rota hesaplar: **normal rota** (iki nokta arası büyük daire) ve **optimize
  rota**. Optimize rotanın önceliği ÖNCE GÜVENLİK, SONRA MALİYET:
  1. Normal rota üzerinde, projenin ANA analiz koduyla (Ellrod TI1 --
     `eslestirme.py`/`turbulans_indeksleri.py`, gerçek ERA5 verisiyle) riskli
     türbülans var mı bakılır.
  2. **Riskli türbülans YOKSA**, optimize rota normal rotayla **birebir
     aynıdır** -- uydurma bir sapma gösterilmez.
  3. **Riskli türbülans VARSA**, adım 3'te açıklanan **A\* (A-star) graf
     araması** o bölgeyi TAMAMEN atlatan, ERA5 rüzgarına göre de en ucuz olan
     yolu bulur; ızgarada riski tam ortadan kaldıran bir yol yoksa, riski en
     aza indiren yol dürüstçe seçilir ("tamamen güvenli" diye yalan
     söylenmez).
  - Bu sıralamanın nedeni: türbülansın kendisi doğrudan çok fazla yakıt
    yaktırmaz (asıl yakıt belirleyicisi rüzgardır) -- türbülanstan kaçınmak
    genelde yol uzatıp FAZLADAN yakıt gerektirir (gerçek uçuşlarda da böyle);
    değeri güvenlik/konfordur. Bu yüzden "optimize rota her zaman ucuzdur"
    varsayılmaz, sonuç panelinde bazen "ekstra yakıt: güvenlik için sapmanın
    bedeli" olarak dürüstçe gösterilir.
- **A\* araması (bkz. `_a_yildiz_ile_rota_ara`):** Büyük daire etrafında,
  her ara noktada 20 km aralıklarla ±400 km'ye kadar yanal seviyelerden
  oluşan bir IZGARA kurulur; ızgaranın her düğümünün TI1'i projenin ana
  analiz koduyla (`eslestirme.py`) tek bir vektörel çağrıda hesaplanır. Her
  kenarın maliyeti gerçek ERA5 rüzgarına göre uçuş süresi + (riskli
  türbülans içeriyorsa) büyük bir ceza olarak tanımlanır; A*, kalan mesafe
  tabanlı **admissible** (asla aşırı tahmin etmeyen) bir sezgiselle
  başlangıçtan bitişe TOPLAM MALİYETİ EN AZA indiren yolu **garantili
  optimal** şekilde bulur. Erken sürümde ızgara çok kaba (100 km/adım) olduğu
  için A*'ın rotanın hemen başında/sonunda ani bir sıçrama yapıp onu
  koruduğu (eski, daha basit "birkaç aday dene" yaklaşımından bile daha uzun
  bir rota) gerçek veriyle tespit edildi -- ızgara inceltilip (20 km/adım)
  başlangıca/bitişe yakın erişilebilir sapma bir "zarf" ile kademelendirilerek
  düzeltildi.
- **Çok faktörlü karşılaştırma -- irtifa değişimi (tırmanma/alçalma):**
  Riskli türbülanstan kaçınmanın YANAL sapma dışında ikinci bir GERÇEK
  stratejisi daha var: aynı yatay rotada kalıp bir üst/alt basınç seviyesine
  geçmek (bazı CAT katmanları irtifaya bağlıdır). Tırmanma/alçalma KENDİ
  İÇİNDE de bir yakıt/süre maliyeti taşır (tırmanma seyrin ÜZERİNDE, alçalma
  ALTINDA bir yakıt akışıyla modellenir -- bkz. `_irtifa_degisimi_maliyeti`,
  halka açık tipik jet performansı mertebeleri, resmi performans verisi
  DEĞİL). `rota_simulasyonu_olustur`, yanal A* yolu ile irtifa değişimi
  adayları arasından TOPLAM maliyeti (temel seyir yakıtı + tırmanma/alçalma
  bedeli) en düşük, güvenliği sağlayan seçeneği seçer -- bazen irtifa
  değiştirmek yanal sapmadan hem daha güvenli HEM daha ucuz çıkar. Seçilen
  strateji (`kacinma_stratejisi`: "yanal"/"irtifa_yukari"/"irtifa_asagi") ve
  optimize rotanın kendi irtifası (`irtifa_ft`) yanıtta ayrı alanlar olarak
  döner; sonuç panelinde de gösterilir.
- Her iki rota, gerçek bir 3D uçak modeliyle (`web/models/ucak.glb` --
  CesiumJS'in kendi resmi örnek verisi, Apache 2.0 lisanslı) zaman-senkronize
  CZML animasyonu olarak sahneye eklenir (mavi = normal, yeşil = optimize);
  Cesium'un yerleşik zaman çizelgesi/oynatma kontrolleriyle izlenebilir.
- Sonuç panelinde süre, mesafe, tahmini yakıt, **tahmini CO2 emisyonu**
  (`CO2_KG_PER_KG_YAKIT = 3.16` -- ICAO/IPCC'nin standart, halka açık jet
  yakıtı emisyon katsayısı) VE riskli türbülans nokta sayısı (normal vs
  optimize) ayrı ayrı karşılaştırılır.
- **Dinamik rota güncelleme:** "🔄 Uçuş sırasında yeniden hesapla" butonu,
  simülasyon oynarken uçağın O ANKİ (Cesium'un kendi interpolasyonuyla
  bulunan) konumunu yeni başlangıç noktası alıp AYNI hedefe, AYNI gerçek
  backend'i (A* + irtifa karşılaştırması) yeniden çağırır -- uydurma bir
  "canlı meteorolojik değişiklik" simülasyonu değil, gerçek bir yeniden
  planlama çağrısıdır.
- **Kabin içi bildirim çerçevelemesi:** Riskli türbülans tespit edildiğinde,
  zaten var olan `/ws/uyarilar` WebSocket uyarı mantığının simülasyon
  sayfasındaki karşılığı olarak, gerçek TI1 şiddetine dayalı (ama arayüz
  çerçevelemesi illüstratif) bir "kabin ekibine bildirim" mesajı gösterilir.

**Kapsam/dürüstlük sınırlaması:** Gerçek ERA5 rüzgar/türbülans verisi SADECE
`config.HAVA_DURUMU_DOSYASI` küpünün kapsadığı bölge/tarih için var (bu
depodaki varsayılan veri: Türkiye/Doğu Akdeniz, Ocak 2019 -- enlem 36-42,
boylam 26-45). Seçilen başlangıç/bitiş/tarih bu aralığın dışındaysa, kod
`sigmet_dogrulama.py`'deki AYNI ilkeyle SESSİZCE uydurma bir "iyileşme"
göstermez -- `ruzgar_verisi_kaynagi: "era5_kapsam_disi"` döner, iki rota da
sadece uçağın hava hızıyla (rüzgarsız/türbülanssız) hesaplanır ve arayüzde bu
açıkça belirtilir. Bu veri kümesiyle demo yapmak için başlangıç/bitiş
noktalarını bu bölgenin içinde ve tarihi Ocak 2019 içinde seçmen gerekir
(sayfa varsayılan olarak İstanbul↔Antalya, 5 Ocak 2019, 28000ft ile açılır --
bu rotada gerçek bir türbülans noktası tespit edilip tamamen atlatılıyor) --
gerçek dünyadaki uçuş rotanı/tarihini görmek istersen, kendi ERA5 veri
küpünü indirip `HAVA_DURUMU_DOSYASI` ortam değişkeniyle o dosyayı gösterebilirsin.

Cesium ion hesabı/token'ı GEREKTİRMEZ: harita.py/harita3d.html'de anahtarsız
Esri tile'a geçilme ilkesiyle aynı şekilde, burada da Cesium'un varsayılan
ion terrain/imagery'si yerine anahtarsız Esri World Street Map (imagery) +
düz elipsoid (terrain) kullanılır.

Bu sayfa (diğer statik önyüzlerin aksine) gerçek bir tarayıcıda (Playwright +
headless Chromium) uçtan uca test EDİLDİ: API anahtarı girme, uçak profili
listesinin yüklenmesi, "Simüle Et"e tıklama, sonuç panelinin dolması ve
haritanın gerçekten render olması otomatik olarak doğrulandı. Bu test bir
GERÇEK hatayı ortaya çıkardı ve düzeltildi: CesiumJS 1.104+'ta `Viewer`'ın
`imageryProvider` kurucu seçeneği artık sessizce HİÇBİR KATMAN EKLEMİYOR
(deprecated) -- internetteki birçok eski örnek hâlâ bunu kullanıyor. Doğru
yol `baseLayer`'a bir `Cesium.ImageryLayer` örneği vermek (bkz. sayfadaki
kod içi not). Ayrıca `viewer.flyTo(dataSource)`'un, zamana bağlı (dinamik)
konumlu varlıklarda TÜM rotayı değil sadece varlığın O ANKİ tekil konumunu
kapsadığı fark edildi -- kamera artık sunucudan gelen ham koordinatlardan
hesaplanan bir dikdörtgene uçuyor, CZML'nin `path` özelliği de (sadece o ana
kadar uçulmuş izi gösterdiği için) ayrı, zamana bağlı olmayan statik bir ön
izleme çizgisiyle tamamlandı.

## Makine öğrenmesi tabanlı türbülans sınıflandırıcısı

TI1/Richardson sayısı fizik FORMÜLÜNE dayanır; komisyon rubriğinin "minimum
gereksinim" maddesi olarak bunun yanına, GERÇEK gözlem verisiyle etiketli,
çalışan bir ML sınıflandırıcısı eklendi.

**Neden bu depodaki Türkiye/Ocak-2019 verisiyle değil?** Bu veri kümesi için
gerçek, doğrulanmış türbülans etiketi yok (ne SIGMET -- sadece ABD hava
sahası, ne PIREP/AMDAR). Uydurma etiketle model eğitmek yerine (bu tam
olarak projenin başında düzeltilen "uydurma katsayı" hatasının bir
versiyonu olurdu), ABD hava sahasına özgü, halka açık **IEM PIREP arşivinden**
(mesonet.agron.iastate.edu) 2018-2020 arası gerçek pilot türbülans raporları
+ eşleşen gerçek **ERA5** verisi indirilip (`ml_veri_indir.py`,
`ml_egitimi.py`) GERÇEK bir eğitim kümesi kuruldu:

- 179 gerçek, etiketli örnek (63 pozitif orta-şiddetli+ türbülans / 116
  negatif) -- FL250-400 arası, projenin `TI1_ESIK_ORTA_SIDDETLI` eşiğiyle
  AYNI ikili eşik felsefesiyle etiketlendi.
- Özellikler bilinçli olarak **bölgeden bağımsız** tutuldu (enlem/boylam
  KASITLI OLARAK dışarıda bırakıldı -- yoksa model ABD'nin bölgesel hava
  düzenine ezberler, Türkiye gibi hiç görmediği bir bölgede anlamsızlaşırdı):
  `ti1_indeksi`, `richardson_sayisi`, `ruzgar_hizi_ms`, `basinc_hpa`.
- Üç sınıflandırıcı (Lojistik Regresyon, Random Forest, Gradient Boosting)
  eğitilip **recall'a** göre karşılaştırıldı (accuracy değil -- havacılık
  güvenliğinde kaçırılan gerçek türbülans/false negative en kritik hata
  türüdür). 134 eğitim / 45 test örneği üzerinde gerçek sonuçlar:

  | Model | Accuracy | Precision | Recall | F1 | ROC-AUC |
  |---|---|---|---|---|---|
  | Lojistik Regresyon | 0.578 | 0.421 | 0.500 | 0.457 | 0.644 |
  | **Random Forest (seçildi)** | **0.756** | **0.632** | **0.750** | **0.686** | **0.843** |
  | Gradient Boosting | 0.800 | 0.733 | 0.688 | 0.710 | 0.852 |

  Gradient Boosting accuracy/F1'de biraz önde olsa da Random Forest daha
  yüksek recall'u (0.750 vs 0.688 -- test kümesindeki 16 gerçek türbülans
  vakasından 12'sini yakalıyor, sadece 4 kaçırıyor) nedeniyle seçildi;
  havacılıkta bir false negative (kaçırılan gerçek türbülans) bir false
  positive'den (gereksiz uyarı) çok daha pahalıya mal olur.
- `POST /api/v1/turbulans/tahmin`, tek bir nokta için hem fizik (TI1) hem
  ML olasılığını karşılaştırmalı döner. Model dosyası (`*.joblib`) repoya
  DAHİL DEĞİL (üretilmiş/büyük artefakt, `.gitignore`) -- `ml_veri_indir.py`
  ardından `ml_egitimi.py` ile yeniden üretilebilir. Model henüz
  üretilmediyse `turbulans_riski_tahmin_et` uydurma bir tahmin dönmez,
  dürüstçe `None` döner.
- `ml_egitimi.py`, seçilen modeli (`*.joblib`) kaydederken YANINDA
  `turbulans_ml_modeli_bilgisi.json`'ı da yazar (seçilen model adı, test
  metrikleri, özellik listesi, eğitim tarihi) -- bu da repoya dahil değil
  (üretilmiş artefakt). `GET /api/v1/turbulans/model-bilgisi`, bu dosyayı
  okuyup döner; henüz eğitilmediyse `egitildi_mi: false` ile dürüstçe
  bildirir.

```bash
python ml_veri_indir.py   # IEM PIREP + eşleşen gerçek ERA5 verisini indirir (Copernicus CDS API anahtarı gerekir, ~/.cdsapirc)
python ml_egitimi.py      # 3 modeli eğitir/karşılaştırır, recall'a göre en iyisini turbulans_ml_modeli.joblib olarak kaydeder
```

## SIGMET/AIRMET doğrulaması

Bu depodaki örnek veri kümesi (Türkiye/Doğu Akdeniz, Ocak 2019) için gerçek
PIREP/AMDAR gözlem verisi yok (bkz. `kalibrasyon.py`; ML sınıflandırıcısı
için ABD hava sahasından indirilen gerçek IEM PIREP verisi ayrı bir konu --
bkz. [Makine öğrenmesi tabanlı türbülans sınıflandırıcısı](#makine-öğrenmesi-tabanlı-türbülans-sınıflandırıcısı))
-- ama SIGMET'ler (Significant Meteorological Information) de gerçek,
operasyonel "burada tehlikeli hava durumu var" uyarılarıdır ve halka açık,
ücretsiz bir arşivden çekilebilirler. `sigmet_dogrulama.py`, hesaplanan TI1
"orta-şiddetli" noktalarını, Iowa Environmental Mesonet'in (IEM) 2005'ten
bugüne arşivlediği ABD Aviation Weather Center (AWC) SIGMET kayıtlarıyla
karşılaştırır -- gerçek zaman/konum eşleşmesi (poligon içi + geçerlilik
penceresi) kontrol edilir, sadece TÜRBÜLANSLA ilgili SIGMET'ler (metninde
"TURB" geçenler) dikkate alınır.

```bash
python sigmet_dogrulama.py THY1234 2019-01-01
# veya API üzerinden:
curl http://localhost:8000/api/v1/ucuslar/THY1234/2019-01-01/sigmet-dogrulama \
  -H "X-API-Key: $API_ANAHTARI"
```

**ÖNEMLİ SINIRLAMA:** Bu arşiv SADECE ABD'nin meteorolojik sorumluluk
sahasını (CONUS + New York/Oakland/Anchorage Oceanic FIR'ları gibi ABD
kontrolündeki okyanus bölgeleri) kapsar. Bu depodaki örnek veri kümesi
(Türkiye/Doğu Akdeniz, Ocak 2019) için GERÇEKTEN eşleşen bir SIGMET
bulunmaz -- bu bir hata değil, beklenen ve dürüst bir sonuçtur
(`sigmetle_ortusen_nokta_sayisi=0` döner). Özellik, ABD hava sahasında
geçen herhangi bir uçuş/tarih için gerçek anlamda doğrulama sağlar (bkz.
modülün kendi docstring'indeki örnek: Anchorage FIR, 2019-01-15, gerçek bir
"OCNL SEV TURB" SIGMET'i ile doğrulandı).

## n8n ile periyodik otomasyon

`toplu_analiz.py`'yi doğrudan çağırmak yerine, n8n'in bir **Schedule
Trigger**'ı bir **HTTP Request** node'uyla `POST /api/v1/analiz/toplu`'yu
periyodik çağırır; ardından ya `bildirim_webhook_url` ile anlık bildirim
alır ya da `GET /api/v1/analiz/durum/{gorev_id}`'yi yoklar. Bu tasarım,
otomasyon tarafının projenin Python iç yapısını hiç bilmesine gerek
bırakmaz -- `api_servisi.py` sadece `.env`'den beslenen, `uvicorn`/Docker
ile başlatılan bağımsız bir HTTP servisidir.

## Claude Code'dan veritabanına MCP ile bağlanmak

Proje kökündeki `.mcp.json`, `mcp_postgres_sunucusu.py`'yi Claude Code'a
tanıtır (ilk kullanımda onay istenir). Sunucu **salt okunur** -- sadece
`tablolari_listele`, `ucuslar_listesi`, `ucus_detayi` ve
`salt_okunur_sorgu_calistir` (sadece tek bir `SELECT`, yazma ifadeleri
reddedilir) araçlarını sunar. Bağlantı bilgileri `.mcp.json`'da DEĞİL,
`.env`'de tutulur.

## Veritabanı şeması (Alembic)

```bash
alembic upgrade head       # şemayı kur/güncelle
alembic current             # hangi migration'da olduğunu gösterir
alembic revision --autogenerate -m "kisa aciklama"   # yeni migration
```

Bağlantı bilgisi `alembic.ini`'ye yazılmaz; `migrations/env.py`, tıpkı
`veritabani.py` gibi, `.env`'den okur.

## Testleri çalıştırmak

```bash
pip install -r requirements-dev.txt
pytest tests/
```

`test_eslestirme.py` gerçek `.nc` dosyasını, `test_veritabani.py`/
`test_api_servisi.py` gerçek bir PostgreSQL bağlantısını bulamazsa
otomatik atlanır (skip) -- CI'da Postgres bir servis konteyneriyle
sağlanır, `.nc` dosyası (büyük olduğu için) sağlanmaz.

## Geliştirme araçları

```bash
ruff check .              # lint
ruff format .              # biçimlendir
pre-commit install         # her commit'te otomatik çalıştır
```

`.github/workflows/ci.yml`, her push/PR'da lint ve testleri (gerçek bir
PostgreSQL servis konteyneriyle) çalıştırır.

## Bilinmesi gerekenler / sınırlamalar

- **TI1/EDR proxy, sertifikalı bir EDR değeri değildir** -- yukarıya bakın.
- `flights_data4` tablosunda `callsign` alanı 8 karakter, boşlukla
  doldurulmuş (padded) saklanır; eşleştirme bunu otomatik yapar.
- Yatay deformasyon hesabı için veri kübünün ilgili zaman dilimindeki tüm
  enlem/boylam grid'ine ihtiyaç var (tek nokta yetmiyor).
- `config.EDR_OLCEKLENDIRME_KATSAYISI` (0.23), `pirep_kalibrasyon_verisi_
  uret.py` ile üretilen gerçek IEM PIREP + ERA5 gözlem setiyle (179 örnek,
  ML sınıflandırıcısıyla AYNI veri) `kalibrasyon.py` kullanılarak kalibre
  edildi -- ama bu ABD hava sahası verisine dayanan, bölgeden bağımsız kaba
  bir kalibrasyondur, Türkiye/Ocak-2019 örnek veri kümesine özgü DEĞİLDİR
  (bkz. yukarıdaki "Önemli sınırlama").
- Proje gerçek bir uçuşla (OpenSky/Trino + gerçek `.nc` verisi) uçtan uca
  test edildi.
- Bu ortamda Docker daemon'ı kurulu olmadığından `Dockerfile`/
  `docker-compose.yml` YAML olarak doğrulandı ama `docker compose up
  --build` ile uçtan uca denenemedi.
- `sigmet_dogrulama.py`, SADECE ABD Aviation Weather Center'ın sorumlu
  olduğu hava sahaları için gerçek veri döner -- bu depodaki örnek veri
  kümesi (Türkiye) için örtüşme çıkmaması beklenen bir durumdur (yukarıya
  bakın).
- `web/harita3d.html` ve `web/ucus_simulasyonu.html`, ikisi de gerçek bir
  tarayıcıda (Playwright + headless Chromium) uçtan uca test EDİLDİ --
  ikisinde de gerçek hatalar bulunup düzeltildi: `ucus_simulasyonu.html`
  için CesiumJS'in `imageryProvider` seçeneğinin artık sessizce hiçbir
  katman eklememesi (bkz. "3D uçuş simülasyonu" bölümü), `harita3d.html`
  için MapLibre 4.7.1'de `setProjection` metodunun HİÇ olmaması ve
  constructor'dan hemen sonra çağrılınca "Style is not done loading"
  vermesi (bkz. yukarıdaki "3D/canlı harita önyüzü" bölümü). Uçak
  "modelleri" arasındaki performans farkı (seyir hızı/yakıt akışı) halka
  açık, tipik değerlerdir -- resmi üretici performans verisi DEĞİLDİR.

## Değişiklik geçmişi

Projenin geçmiş halinden bugüne kadarki tüm önemli değişiklikler için bkz.
[CHANGELOG.md](CHANGELOG.md).

## Lisans

[MIT](LICENSE)
