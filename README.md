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
veritabani.py                 -> PostgreSQL entegrasyonu: ucuslar/edr_olcumleri tabloları
api_servisi.py                -> FastAPI REST API iskeleti (JSON çıktı + analiz tetikleme)
mcp_postgres_sunucusu.py      -> Claude Code/Desktop için salt okunur PostgreSQL MCP sunucusu
.mcp.json                       -> Claude Code'un mcp_postgres_sunucusu.py'yi otomatik tanıması için
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

`main.py` her çalıştırmada `veritabani.py` üzerinden `ucuslar` ve
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
```

Uç noktalar:
- `GET /saglik` -- basit sağlık kontrolü
- `GET /ucuslar` -- veritabanına kaydedilmiş uçuşları listeler
- `GET /ucuslar/{ucus_numarasi}/{tarih}` -- bir uçuşun tüm EDR/TI1 ölçüm noktalarını JSON döndürür
- `POST /analiz/ucus` (`{"ucus_numarasi": "...", "tarih": "YYYY-MM-DD"}`) -- `main.py` ile aynı analizi arka planda başlatır, `gorev_id` döner
- `POST /analiz/toplu` (`{"ucuslar": [{"ucus_numarasi": "...", "tarih": "..."}, ...]}`) -- `toplu_analiz.py` ile aynı toplu analizi arka planda başlatır
- `GET /analiz/durum/{gorev_id}` -- tetiklenen bir analizin durumunu sorgular

Bu bir İSKELETtir: görev durumu bellek içinde tutulur (süreç yeniden
başlarsa sıfırlanır); kalıcı bir görev kuyruğu gerekiyorsa ileride eklenebilir.

### n8n ile periyodik otomasyon

`toplu_analiz.py`'yi doğrudan n8n'e bağlamak yerine, üstteki FastAPI uç
noktaları kullanılıyor -- n8n'in bir **Schedule Trigger**'ı, bir **HTTP
Request** node'uyla `POST /analiz/toplu`'yu periyodik çağırır, ardından
`GET /analiz/durum/{gorev_id}` ile tamamlanmayı bekleyip sonucu
`GET /ucuslar/...`'dan okuyabilir. Bu, n8n'in Execute Command node'uyla
yerel Python scriptleri çalıştırmasından daha taşınabilir (n8n ve proje
aynı makinede olmak zorunda değil).

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
değildir).

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
