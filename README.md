# Türbülans Radar Projesi — Geliştirilmiş Sürüm

## Ne değişti?

| Eski | Yeni |
|---|---|
| `edr_hesaplama.py` ve `interaktif_harita.py`'de iki farklı, keyfi katsayılı EDR formülü | `turbulans_indeksleri.py`: Ellrod TI1 indeksi (Ellrod & Knapp, 1992) — havacılık meteorolojisinde CAT tahmini için gerçekten kullanılan yöntem |
| `trino_baglanti.py`'de şifre düz metin kod içinde | `kimlik_dogrulama.py` + `.env`: kimlik bilgileri ortam değişkeninden okunuyor, `.gitignore`'da korunuyor |
| `kucuk_simulasyon.py`: `np.linspace` ile UYDURULMUŞ rota | `veri_yukleme.py`: `flights_data4` üzerinden **uçuş numarasından (callsign) gerçek rota** çekiliyor |
| Sabit tek nokta sorgusu, koordinat filtresi | `ucus_numarasi_ile_rota_cek()`: callsign → icao24 → state_vectors_data4 zinciri |
| Statik harita, tek zaman anı | `harita.py`: `TimestampedGeoJson` ile zaman kaydırıcılı animasyon, gerçek uçuş bilgisi popup'ları, lejant |
| Basınç/irtifa birim karışıklığı | `birim_donusumleri.py`: ISA barometrik formülüyle metre ↔ hPa dönüşümü |

## Dosya yapısı

```
config.py                 -> sabitler, eşik değerleri
kimlik_dogrulama.py        -> .env'den güvenli kimlik bilgisi okuma
.env.example                -> kopyalanacak şifre şablonu
birim_donusumleri.py       -> irtifa <-> basınç dönüşümleri
turbulans_indeksleri.py    -> Ellrod TI1 + Richardson sayısı hesabı + EDR-proxy ölçekleme
veri_yukleme.py             -> NetCDF yükleme + OpenSky/Trino sorguları
eslestirme.py                -> uçuş rotası <-> hava durumu grid eşleştirme (vektörel)
harita.py                    -> zaman kaydırıcılı Folium haritası
main.py                      -> uçtan uca çalıştırma
ornek_ucus_bul.py           -> OpenSky'da kayıtlı gerçek callsign'ları listeler
veri_kontrol.py              -> veri küpü çözünürlüğünü / TI1 çeşitliliğini kontrol eder
kimlik_kontrol.py           -> .env'in doğru okunduğunu kontrol eder
kalibrasyon.py               -> gerçek PIREP/AMDAR verisiyle EDR ölçekleme katsayısını kalibre eder
toplu_analiz.py              -> bir CSV listesindeki birden fazla uçuşu sırayla analiz eder
web_arayuzu.py               -> tarayıcıdan kullanılabilir basit arayüz (Streamlit)
hata_yardimcisi.py           -> ham Python hatalarını anlaşılır Türkçe mesaja çevirir
veri_indirme.py              -> ERA5 verisi otomatik indirme ALTYAPISI (bkz. aşağıdaki uyarı)
konsol_kurulumu.py           -> Windows konsolunda Türkçe/özel karakterlerin çökmesini önler
models.py                     -> PostgreSQL tabloları için SQLAlchemy ORM modelleri (Ucus, EdrOlcumu)
veritabani.py                 -> PostgreSQL entegrasyonu: senkron (main.py) + asenkron (api_servisi.py) erişim
api_servisi.py                -> FastAPI REST API'si (API anahtarlı, /api/v1, async, WebSocket, webhook)
mcp_postgres_sunucusu.py      -> Claude Code/Desktop için salt okunur PostgreSQL MCP sunucusu
.mcp.json                       -> Claude Code'un mcp_postgres_sunucusu.py'yi otomatik tanıması için
pytest.ini                     -> pytest-asyncio ayarları (async testler tek event loop paylaşır)
tests/                        -> pytest birim testleri (ağ/veri gerektirmeyen kısımlar için)
```

## Kullanım

```bash
pip install -r requirements.txt
cp .env.example .env          # sonra .env içine OpenSky + PostgreSQL bilgilerini yaz
python main.py THY1234 2019-01-01
```

Her script `--help` ile kullanım bilgisi verir, örn. `python main.py --help`,
`python ornek_ucus_bul.py --help`.

### PostgreSQL entegrasyonu

Analiz sonuçları artık lokal CSV yerine PostgreSQL'e yazılıyor. `.env`
dosyasına şu değişkenleri ekle (bkz. `.env.example`):

```
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=...
POSTGRES_DB=Turbulence-db
```

`main.py` her çalıştırmada `veritabani.py` üzerinden (ki bu artık ham SQL
değil, `models.py`'deki SQLAlchemy ORM modellerini kullanıyor) `ucuslar` ve
`edr_olcumleri` tablolarını (yoksa) otomatik oluşturur ve sonucu yazar; aynı
(uçuş numarası, tarih) tekrar analiz edilirse eski kayıt silinip yeniden
yazılır. Veritabanına yazma başarısız olursa (bağlantı yok, `.env` eksik
vb.) pipeline durmaz -- bir uyarı basılır ve harita yine de üretilir, sadece
o çalıştırma kalıcı olarak saklanmaz.

Not: Görev tanımında verilen bağlantı bilgileri `Turbulence-db` adlı, halen
sunucuda var olan bir veritabanını gösteriyordu; PostgreSQL entegrasyonu
maddesinde ayrıca geçen `radar_first_db` ismi bu sunucuda bulunmadığından,
gerçekten var olan `Turbulence-db` kullanıldı. Farklı bir veritabanı adı
istenirse `.env`'deki `POSTGRES_DB` değerini değiştirmek yeterli.

### FastAPI servis katmanı

```bash
uvicorn api_servisi:app --reload --port 8000
# Swagger/OpenAPI dokümantasyonu: http://localhost:8000/docs
```

**Güvenlik:** `/api/v1/*` altındaki TÜM uç noktalar `X-API-Key` başlığı
gerektirir; değer `.env`'deki `API_ANAHTARI`'dan okunur (üretmek için:
`python -c "import secrets; print(secrets.token_urlsafe(32))"`). Anahtar
yanlış/eksikse 401, sunucuda hiç tanımlı değilse 503 döner. `/saglik`
kasıtlı olarak anahtarsız (yaygın health-check pratiği).

**Sürümleme:** tüm veri/analiz uç noktaları `/api/v1` altında -- ileride
`/api/v2` eklenirse mevcut istemciler bozulmaz. Uç noktalar:
- `GET /saglik` -- anahtarsız sağlık kontrolü
- `GET /api/v1/ucuslar` -- veritabanına kaydedilmiş uçuşları listeler (asenkron, asyncpg)
- `GET /api/v1/ucuslar/{ucus_numarasi}/{tarih}` -- bir uçuşun tüm EDR/TI1 ölçüm noktalarını JSON döndürür
- `POST /api/v1/analiz/ucus` (`{"ucus_numarasi", "tarih", "bildirim_webhook_url"?}`) -- `main.py` ile aynı analizi arka planda başlatır, `gorev_id` döner
- `POST /api/v1/analiz/toplu` (`{"ucuslar": [...], "bildirim_webhook_url"?}`) -- `toplu_analiz.py` ile aynı toplu analizi arka planda başlatır
- `GET /api/v1/analiz/durum/{gorev_id}` -- tetiklenen bir analizin durumunu sorgular
- `WS /ws/uyarilar?api_key=...` -- bir analiz sırasında Ellrod TI1 "orta-şiddetli" eşiğini aşan nokta bulunursa bağlı istemcilere anlık uyarı yayınlar

**Asenkron:** okuma uç noktaları `veritabani.py`'nin `asyncpg` tabanlı async
fonksiyonlarını kullanır, event loop'u bloklamaz. Analiz tetikleme uç
noktaları, `main.py`/`toplu_analiz.py`'deki AYNI (bloklayan) mantığı
`asyncio.to_thread` ile ayrı bir thread'de çalıştırır -- o dosyaları yeniden
yazmaya gerek kalmadan.

**Hata yönetimi:** özel exception handler'lar `VeritabaniAyarlariEksikHatasi`
ve veritabanı bağlantı hatalarını 503'e, geçersiz girdiyi (`ValueError`)
400'e, beklenmeyen hataları `dostane_hata_mesaji` ile 500'e çevirir.
`/api/v1/analiz/*` uç noktaları ayrıca kendi başına basit bir hız sınırlayıcı
içerir (varsayılan: 60 saniyede en fazla 5 istek) -- dışarıdan gelen aşırı
istekle OpenSky'yi dolaylı olarak yormamak için; aşılırsa 429 döner.

**Hız sınırlama:** `POST /api/v1/analiz/*`, kendi API'sini kötüye kullanıma
karşı bellek-içi bir pencere sayaçla korur (429 Too Many Requests) --
OpenSky'ye giden isteklerin dış dünyadan tetiklenen bir döngüyle
katlanmasını önlemek için.

**Webhook bildirimi:** `bildirim_webhook_url` verilirse, analiz bitince
sonuç oraya POST edilir -- n8n'in Webhook node'u bunu dinleyip
`GET /api/v1/analiz/durum/{gorev_id}`'yi periyodik yoklamaya (polling)
gerek kalmadan tetiklenebilir.

Görev durumu bellek içinde tutulur (süreç yeniden başlarsa sıfırlanır);
kalıcı bir görev kuyruğu (Celery/RQ) gerekiyorsa ileride eklenebilir. Tek
kullanıcılı/dahili bir araç için statik API anahtarı yeterli görüldü; çok
kullanıcılı bir sürüme geçilirse JWT/OAuth2'ye yükseltilebilir.

### n8n ile periyodik otomasyon

`toplu_analiz.py`'yi doğrudan n8n'e bağlamak yerine, üstteki FastAPI uç
noktaları kullanılıyor -- n8n'in bir **Schedule Trigger**'ı, bir **HTTP
Request** node'uyla `POST /api/v1/analiz/toplu`'yu periyodik çağırır,
ardından ya `bildirim_webhook_url` ile anlık bildirim alır ya da
`GET /api/v1/analiz/durum/{gorev_id}` ile yoklayıp sonucu
`GET /api/v1/ucuslar/...`'dan okuyabilir. Bu tasarım -- betikleri n8n'in
Execute Command node'uyla doğrudan çalıştırmak yerine HTTP sınırı arkasına
koymak -- otomasyon tarafının projenin Python iç yapısını hiç bilmesine
gerek bırakmaz: `api_servisi.py`, sadece `.env`'den beslenen, `uvicorn` ile
başlatılan bağımsız bir süreçtir; n8n (veya başka bir istemci) onunla
SADECE HTTP üzerinden konuşur.

`veri_indirme.py` BİLİNÇLİ OLARAK bu otomasyona dahil edilmedi: gerçek ERA5
indirmesi hâlâ sadece elle, `--gercekten-indir` bayrağıyla çalışır --
periyodik/otomatik hale getirmek, OpenSky/Copernicus'u rate-limit/ban
riskine sokmamak için alınmış bilinçli bir güvenlik kararını bozar.

### Claude Code'dan veritabanına MCP ile bağlanmak

Proje kökündeki `.mcp.json`, `mcp_postgres_sunucusu.py`'yi Claude Code'a
tanıtır (ilk kullanımda onay istenir). Sunucu salt okunur -- sadece
`tablolari_listele`, `ucuslar_listesi`, `ucus_detayi` ve
`salt_okunur_sorgu_calistir` (sadece tek bir SELECT, yazma ifadeleri
reddedilir) araçlarını sunar. Bağlantı bilgileri `.mcp.json`'da DEĞİL,
`.env`'de tutulur -- `.mcp.json` repoya güvenle commitlenebilir.

### Web arayüzü

Terminal yerine tarayıcıdan kullanmak için:

```bash
streamlit run web_arayuzu.py
```

Uçuş numarası ve tarihi bir kutuya yazıp "Analiz Et"e basman yeterli; sonuç
tablosu ve zaman kaydırıcılı harita direkt sayfada görünür. Arkada hâlâ aynı
`main.py` mantığı (gerçek OpenSky sorgusu + hava durumu eşleştirmesi) çalışır
-- bu sadece görsel bir ön yüz.

### Birden fazla uçuşu birden analiz etmek

```bash
python toplu_analiz.py ucuslar.csv
```

`ucuslar.csv` en az `ucus_numarasi` ve `tarih` sütunlarını içermeli. Her uçuş
sonucunu PostgreSQL'e yazar ve kendi HTML haritasını normal şekilde üretir;
script ayrıca hepsinin kısa bir özetini (`toplu_analiz_ozeti.csv`) tek
tabloda toplar -- bu özet dosyası, PostgreSQL'e taşınan ham ölçüm verisinden
farklı, sadece bu çalıştırmaya özel bir rapor olduğu için CSV olarak kalmaya
devam ediyor. Bir uçuşta hata olursa diğerlerinin analizi durmaz.

### ERA5 verisini otomatik indirme -- ŞU AN AKTİF DEĞİL

`veri_indirme.py`, ileride hava durumu verisini elle indirip klasöre koyma
işini otomatikleştirmek için hazırlanmış bir ALTYAPI dosyasıdır. **Şu an
gerçek bir indirme yapmaz** -- OpenSky ve Copernicus gibi servisler çok
büyük/geniş istek gönderen hesapları geçici ya da kalıcı olarak
engelleyebildiği (rate limit / ban) için, bilinçli olarak sadece "kuru
deneme" (ne isteneceğini gösterip göndermeme) modunda çalışır. Kod
içindeki sabit güvenlik sınırları (en fazla 10x10 derecelik bölge, en fazla
3 günlük veri) aşan hiçbir istek, gerçekten indirmeye çalışılsa bile
gönderilmez. Gerçek indirmeyi açmak (`--gercekten-indir`) için ayrıca
`pip install cdsapi` ve bir Copernicus hesabı/`~/.cdsapirc` gerekir --
bunlar bu projede kurulu değildir ve kullanıcı açıkça onay vermeden devreye
girmez.

### Testleri çalıştırmak

```bash
pip install -r requirements-dev.txt
python -m pytest tests/
```

`tests/test_eslestirme.py`, gerçek `ocak_2019_turbulans.nc` dosyasını
bulamazsa otomatik olarak atlanır (dosya `.gitignore`'da, repoya dahil
değildir). Aynı şekilde `tests/test_veritabani.py` ve
`tests/test_api_servisi.py`, gerçek bir PostgreSQL bağlantısı kurulamazsa
atlanır. `pytest.ini`, async testlerin (`test_api_servisi.py`) TEK bir event
loop paylaşmasını sağlar -- gerçek bir `uvicorn` sürecini (tek event loop)
taklit etmek için; aksi halde `veritabani.py`'deki `asyncpg` engine
singleton'ı testler arası "Event loop is closed" hatası verir (bu bir kod
hatası değil, sadece test izolasyonuyla ilgili bir ayrıntı).

## Bilinmesi gerekenler / sınırlamalar

- **TI1/EDR proxy, sertifikalı bir EDR değeri değildir.** ERA5 benzeri ~25-30 km
  çözünürlüklü reanaliz verisinden hesaplanan bir türbülans olasılık göstergesidir.
  Gerçek operasyonel kullanım için PIREP/AMDAR gözlemleriyle kalibre edilmesi gerekir.
- `flights_data4` tablosunda `callsign` alanı 8 karakter, boşlukla doldurulmuş
  (padded) saklanır; eşleştirme bunu otomatik yapıyor.
- Yatay deformasyon hesabı için veri kübünün ilgili zaman dilimindeki tüm
  enlem/boylam grid'ine ihtiyaç var (tek nokta yetmiyor) — `eslestirme.py`
  bunu `differentiate()` ile grid üzerinde hesaplayıp sonra noktaya en yakın
  hücreyi okuyor.
- Proje gerçek bir uçuşla (OpenSky/Trino bağlantısı + gerçek `.nc` verisi)
  uçtan uca test edildi ve çalıştığı doğrulandı.
- `config.EDR_OLCEKLENDIRME_KATSAYISI` kalibre edilene kadar (bkz.
  `kalibrasyon.py`) her çalıştırmanın sonunda `main.py` "kalibre edilmedi"
  uyarısı basar -- EDR proxy değerlerinin hâlâ keyfi bir katsayıya
  dayandığını unutmamak için.

## Kod incelemesinden gelen düzeltmeler

Bir kod incelemesinde bulunan 6 sorun giderildi:

1. **NaN → NULL:** Veri küpünün kapsamı dışındaki noktalar (`ti1_indeksi`,
   `edr_proxy`, ...) `NaN` olarak hesaplanıyor; bunlar veritabanına artık
   `NULL` olarak yazılıyor (`veritabani._nan_ise_none`). Önceden `NaN` olarak
   yazılan bir satır API'den okunduğunda "Out of range float values are not
   JSON compliant" hatasıyla 500'e düşüyordu.
2. **SQL enjeksiyonu:** `veri_yukleme.py` ve `ornek_ucus_bul.py`, uçuş
   numarası/icao24/önek gibi değerleri artık f-string ile SQL'e gömmüyor;
   Trino'nun parametreli sorgu desteğini (`?` yer tutucuları +
   `cursor.execute(sorgu, parametreler)`) kullanıyor. Bu değerler artık
   `api_servisi.py` üzerinden dışarıdan da tetiklenebildiği için önemliydi.
3. **Gereksiz OAuth2 girişi:** `trino_baglantisi_olustur()` her çağrıda YENİ
   bir `OAuth2Authentication()` oluşturuyordu; bu, trino kütüphanesinin
   token önbelleğini sıfırlayıp her analiz için ayrı bir tarayıcı girişi
   istenmesine yol açıyordu (toplu analizde veya API'den ardışık istekte
   özellikle sorunluydu). Artık süreç boyunca tek bir örnek yeniden
   kullanılıyor (`veri_yukleme._oauth2_kimlik_dogrulamasini_al`).
4. **Hata mesajı sızıntısı:** API'nin 500/503 yanıtları artık ham exception
   mesajını (SQL, bağlantı dizesi vb. içerebilir) istemciye DÖNDÜRMÜYOR --
   genel, güvenli bir mesaj döner; tam ayrıntı (traceback dahil) sunucu
   tarafında (stderr) loglanır.
5. **Girdi doğrulama:** `tarih` artık gerçek bir tarih olarak doğrulanıyor
   (path parametresinde `date` tipi, istek gövdesinde pydantic validator),
   `ucus_numarasi` harf/rakam ve en fazla 8 karakterle sınırlı, `GET
   /api/v1/ucuslar`'ın `limit`i 1-500 aralığına sabitlendi, ölçüm listesi
   artık `olcum_limit`/`olcum_offset` ile sayfalanıyor (`toplam_olcum_sayisi`
   alanıyla birlikte) -- daha önce 50.000 noktalık bir uçuş tek seferde
   dönüyordu.
6. **Zamanlamaya dayanıklı anahtar karşılaştırması:** API anahtarı artık
   `==` yerine `secrets.compare_digest` ile karşılaştırılıyor (timing
   attack'e karşı).

## Sonraki adımlar için fikirler

- ~~Deformasyon/kayma hesabını tüm grid üzerinde vektörel olarak önceden
  hesaplayıp `.sel()` ile hızlandırmak.~~ Yapıldı: `eslestirme.py` artık tüm
  rotayı tek seferde vektörel eşleştiriyor (gerçek veriyle ölçülen kazanç:
  ~250x, bkz. modülün başındaki not).
- ~~Richardson sayısı gibi ek kararlılık indeksleri ekleyip TI1 ile
  birleştirmek.~~ Yapıldı: `turbulans_indeksleri.richardson_sayisi_hesapla`
  bilerek TI1'e keyfi bir katsayıyla karıştırılmadan, ayrı bir
  `richardson_sayisi`/`dinamik_kararsizlik` sütunu olarak ekleniyor.
- ~~Gerçek PIREP verisiyle karşılaştırıp ölçekleme katsayısını kalibre
  etmek.~~ Kısmen yapıldı: `kalibrasyon.py` bunun için bir araç sağlıyor,
  ama gerçek PIREP/AMDAR gözlem verisi bu depoda YOK -- kalibrasyonu
  çalıştırmak için kullanıcının kendi gözlem CSV'sini sağlaması gerekiyor.
- ~~Trino/OpenSky sorgularının başarısız senaryoları (rate limit, OAuth2
  zaman aşımı) için yeniden deneme (retry) mantığı eklemek.~~ Yapıldı:
  `veri_yukleme.py` artık `tenacity` ile SADECE geçici ağ/sunucu
  hatalarında (bağlantı kopması, 502/503/504, dahili Trino hatası), üstel
  artan aralarla (2s, 4s, 8s) ve en fazla 3 denemeyle yeniden deniyor --
  OpenSky'yi art arda isteklerle yormamak için deneme sayısı bilerek düşük.
  Ayrıca `toplu_analiz.py` artık uçuşlar arasına
  `config.TOPLU_ANALIZ_ISTEKLER_ARASI_BEKLEME_SANIYE` kadar bekleme koyuyor.
- ~~Terminal yerine tarayıcıdan kullanılabilir basit bir arayüz.~~ Yapıldı:
  `web_arayuzu.py` (`streamlit run web_arayuzu.py`).
- ~~Birden fazla uçuşu tek seferde analiz edebilmek.~~ Yapıldı:
  `toplu_analiz.py`.
- ~~Hata mesajlarını daha anlaşılır hale getirmek.~~ Yapıldı:
  `hata_yardimcisi.py`, `main.py`/`toplu_analiz.py`/`web_arayuzu.py`
  tarafından kullanılıyor.
- ~~Hava durumu verisini otomatik indirme.~~ Sadece ALTYAPISI hazırlandı
  (`veri_indirme.py`) -- rate-limit/ban riski nedeniyle gerçek indirme
  bilinçli olarak kapalı, bkz. yukarıdaki "ERA5 verisini otomatik indirme"
  bölümü.
- ~~PostgreSQL entegrasyonu.~~ Yapıldı: `veritabani.py`, lokal CSV çıktısının
  yerine `ucuslar`/`edr_olcumleri` tablolarına yazıyor, bkz. "PostgreSQL
  entegrasyonu" bölümü.
- ~~FastAPI REST API iskeleti.~~ Yapıldı: `api_servisi.py`, bkz. "FastAPI
  servis katmanı" bölümü.
- ~~n8n gibi bir araçla periyodik otomasyon.~~ Yapıldı (HTTP tabanlı):
  `toplu_analiz.py` doğrudan değil, `api_servisi.py`'nin `/analiz/*` uç
  noktaları üzerinden -- bkz. "n8n ile periyodik otomasyon" bölümü.
  `veri_indirme.py` bilinçli olarak otomasyona dahil edilmedi.
- ~~Claude Code'dan veritabanına MCP ile bağlanmak.~~ Yapıldı:
  `mcp_postgres_sunucusu.py` + proje kökündeki `.mcp.json`, bkz. "Claude
  Code'dan veritabanına MCP ile bağlanmak" bölümü.
- ~~API güvenliği (statik anahtar), asenkron uç noktalar, yapılandırılmış
  hata yönetimi, ORM modelleri, API sürümleme/Swagger, WebSocket ile canlı
  uyarı, n8n için webhook bildirimi.~~ Yapıldı -- bkz. "FastAPI servis
  katmanı" ve "n8n ile periyodik otomasyon" bölümleri, `models.py`.
- **Bilinçli olarak YAPILMADI -- Offline-first Flutter mobil arayüz:**
  projede hiç Flutter/mobil kod yok; bu, ayrı bir mobil uygulama
  geliştirme projesi gerektirir (sadece backend'e bir özellik eklemek
  değil). API tarafı (JSON uç noktaları + WebSocket canlı uyarı) buna
  hazır durumda; mobil istemci ayrı bir iş olarak ele alınmalı.
- **Bilinçli olarak YAPILMADI -- Yapay zeka destekli tahmin modeli:**
  `kalibrasyon.py`'nin başındaki notta da açıkça yazdığı gibi, bu depoda
  GERÇEK PIREP/AMDAR gözlem verisi YOK. Etiketlenmiş gerçek veri olmadan
  bir ML modeli "eğitmek", projenin başında eleştirilip düzeltilen
  "uydurma katsayı" hatasının bir versiyonunu (bu sefer sahte bir model
  görünümü altında) tekrarlamak olurdu. Gerçek gözlem verisi sağlanırsa
  (bkz. `kalibrasyon.py`), üzerine bir tahmin modeli kurmak anlamlı hale gelir.
