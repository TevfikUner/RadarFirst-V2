# Türbülans Radar

Gerçek bir uçuşun (OpenSky/Trino) rotasını, gerçek bir hava durumu veri
küpüyle (Copernicus/ERA5) eşleştirip Ellrod TI1 indeksi ve bulk Richardson
sayısıyla türbülans şiddeti/dinamik kararsızlık tahmini üreten uçtan uca bir
sistem. Sonuçlar PostgreSQL'e yazılır, zaman kaydırıcılı bir Folium
haritasında görselleştirilir, bir FastAPI servisi ve MCP sunucusu üzerinden
JSON/veritabanı olarak dışarıya açılır.

**Önemli sınırlama:** TI1/EDR proxy, sertifikalı bir EDR (Eddy Dissipation
Rate) değeri DEĞİLDİR -- ~25-30 km çözünürlüklü reanaliz verisinden
hesaplanan bir araştırma/görselleştirme göstergesidir. Gerçek operasyonel
kullanım için PIREP/AMDAR gözlemleriyle kalibre edilmesi gerekir (bkz.
[Sınırlamalar](#bilinmesi-gerekenler--sınırlamalar), `kalibrasyon.py`).

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
| GET | `/api/v1/ucuslar` | Kaydedilmiş uçuşları listeler (`limit`, 1-500) |
| GET | `/api/v1/ucuslar/{ucus_numarasi}/{tarih}` | Bir uçuşun ölçüm noktaları (`olcum_limit`/`olcum_offset` ile sayfalı) |
| POST | `/api/v1/analiz/ucus` | Tek bir uçuşu arka planda analiz eder, `gorev_id` döner |
| POST | `/api/v1/analiz/toplu` | Birden fazla uçuşu arka planda analiz eder |
| GET | `/api/v1/analiz/durum/{gorev_id}` | Tetiklenen bir analizin durumunu sorgular |
| GET | `/api/v1/esikler` | TI1 renklendirme eşiklerini döner (web/harita3d.html bunları kullanır) |
| GET | `/api/v1/ucuslar/{ucus_numarasi}/{tarih}/sigmet-dogrulama` | TI1'i gerçek AWC SIGMET'leriyle karşılaştırır |
| WS | `/ws/uyarilar?api_key=...` | TI1 "orta-şiddetli" eşiği aşılınca canlı uyarı yayınlar |
| GET | `/harita/harita3d.html` | 3D/canlı harita önyüzü (statik, tarayıcıda açılır) |

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
  Street Map'i kullanır; MapLibre CDN sürümü (4.7.1) BİLEREK sabitlendi
  (daha yeni sürümler -- 6.x -- klasik `<script>` ile çalışan UMD paketini
  kaldırıp sadece ES module dağıtıyor).

Bu sayfa gerçek bir tarayıcıda test EDİLEMEDİ (bu ortamda tarayıcı/Docker
yok) -- FastAPI üzerinden sunulduğu, tüm uç noktaları doğru çağırdığı ve
JS'in sözdizimsel olarak geçerli olduğu doğrulandı, ama gerçek render/
WebGL davranışını görmek için tarayıcıda açıp denemen gerekiyor.

## SIGMET/AIRMET doğrulaması

Gerçek PIREP/AMDAR gözlem verisi bu depoda yok (bkz. `kalibrasyon.py`) --
ama SIGMET'ler (Significant Meteorological Information) de gerçek,
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
- `config.EDR_OLCEKLENDIRME_KATSAYISI` kalibre edilene kadar (bkz.
  `kalibrasyon.py`) `main.py` her çalıştırma sonunda uyarı basar.
- Proje gerçek bir uçuşla (OpenSky/Trino + gerçek `.nc` verisi) uçtan uca
  test edildi.
- Bu ortamda Docker daemon'ı kurulu olmadığından `Dockerfile`/
  `docker-compose.yml` YAML olarak doğrulandı ama `docker compose up
  --build` ile uçtan uca denenemedi.
- `sigmet_dogrulama.py`, SADECE ABD Aviation Weather Center'ın sorumlu
  olduğu hava sahaları için gerçek veri döner -- bu depodaki örnek veri
  kümesi (Türkiye) için örtüşme çıkmaması beklenen bir durumdur (yukarıya
  bakın).
- `web/harita3d.html` gerçek bir tarayıcıda test EDİLEMEDİ (bu ortamda
  tarayıcı yok) -- API entegrasyonu ve JS sözdizimi doğrulandı, gerçek
  render davranışı için tarayıcıda denenmesi gerekir.

## Değişiklik geçmişi

Projenin geçmiş halinden bugüne kadarki tüm önemli değişiklikler için bkz.
[CHANGELOG.md](CHANGELOG.md).

## Lisans

[MIT](LICENSE)
