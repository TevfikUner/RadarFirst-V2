# Uçtan uca denetim — 20 Ekim 2026

Dal `claude/denetim-2026-10-20`, başlangıç master `ddb1db4`. Ham çıktılar depoya alınmadı (oturum
geçici klasörü); bu dosya özetidir.

## 1. Özet

Proje sağlığı: **önce 8,5/10, sonra 8,6/10.** Statik kontroller, bağımlılık taraması, 1.126 test
(birim + veritabanı + gerçek veri + tarayıcı), duman testi ve derin sağlık kontrolü baştan temizdi.
Önceki denetimlerin (6, 13, 17, 19 Ekim) bıraktığı bir gerilik yok. Bu turda iki küçük hata
düzeltildi; büyük kalan borç kod yapısı (tek dosyada 2.333 satırlık rota modülü) ve tip denetiminin
olmaması.

## 2. Proje haritası

| Katman | Yer | İş |
|---|---|---|
| Fizik | `fizik/` | Ellrod TI1, Richardson, hipsometrik kalınlık, EDR gösterge ölçeği, sanal PIREP |
| Veri | `veri/` | ERA5 (CDS/ARCO), canlı GFS (THREDDS), OpenSky/Trino, AWC SIGMET, openAIP, MADIS, IWXXM |
| Depo | `depo/` | PostgreSQL (SQLAlchemy + asyncpg), görev kuyruğu (SKIP LOCKED), advisory lock, hız sınırı |
| Rota | `rota/` | A* (koridor/ATS ağı), SIGMET ve kısıtlı saha sert kısıtı, OpenAP yakıt, Pareto |
| ML | `ml/` | IEM PIREP + ERA5 örnekleri, gece işi, kapılı aktivasyon, konformal belirsizlik |
| API | `api/` | FastAPI, rollü anahtar, WS bileti, CSP, Prometheus, denetim kaydı |
| İşçi | `isci/` | Kuyruk işçisi, kalp atışı, NOTIFY ile canlı uyarı, SSRF korumalı webhook |
| Arayüz | `arayuz/`, `web/` | Streamlit, MapLibre 3B harita, CesiumJS simülasyon |
| Altyapı | kök | Docker Compose (db, migrate, api, worker, yedek, prometheus), Alembic, CI (6 iş) |

Ana akış: istemci → `/api/v1` (anahtar + rol + hız sınırı) → kısa işler API'de (`asyncio.to_thread`),
uzun işler `analiz_gorevleri` kuyruğuna → işçi OpenSky/ERA5/GFS'ten veri alır, `eslestirme` ile TI1
hesaplar, PostgreSQL'e yazar → NOTIFY ile WebSocket'e, webhook ile n8n'e bildirim.

## 3. Önce / sonra

| Kontrol | Önce | Sonra |
|---|---|---|
| ruff check | temiz | temiz |
| ruff format | 297 dosya temiz | 297 dosya temiz |
| pip check | temiz | temiz |
| pip-audit (3 dosya) | 0 açık | 0 açık |
| mypy (yapılandırılmamış, bilgi amaçlı) | 134 bulgu | 134 (değişmedi) |
| alembic | current = head (`a7c3e9f1b2d4`) | aynı |
| openapi.json | kodla aynı | aynı |
| Testler (ag hariç) | 1.126 geçti, 0 kaldı, 60 uyarı | **1.132 geçti** (+6 yeni), 0 kaldı, 60 uyarı |
| Kapsam | %85,7 | %85,8 |
| Duman testi (Docker yığını) | geçti | geçti |
| `/saglik?derin=true` | ayakta, uyarı yok | ayakta, uyarı yok |
| api/worker logu (24 sa) | 0 ERROR/Traceback | 0 |

Uyarıların tamamı yerel Python 3.14 ortamındaki numpy 2.5 / xarray ABI uyarısı; Docker imajında
(3.12) yok. mypy bulgularından örneklenen ~20'sinin hepsi tip çıkarımı kaynaklı yanlış alarm
(`*args` açılımı, `dict` değer tipi `object` çıkarımı); çalışma zamanı hatası bulunmadı.

## 4. Bulgular ve yapılanlar

| No | Dosya:satır | Kategori | Önem | Sorun | Durum |
|---|---|---|---|---|---|
| D-1 | `isci/gorev_iscisi.py:259,263` | Güvenlik (log) | Orta | n8n webhook yolu gizli belirteç taşır; denetim kaydı maskeliyordu ama işçi uyarı logları URL'yi olduğu gibi yazıyordu | **Düzeltildi** (`webhook.log_icin_maskele`, test) |
| D-2 | `config.py:67` | Hata yönetimi | Düşük | `.env`'de boş sayısal değer (`TI1_ESIK_ORTA_SIDDETLI_GFS=`) süreci değişken adı olmadan `could not convert string to float` ile durduruyordu | **Düzeltildi** (boş → varsayılan, geçersiz → adıyla hata; test) |
| D-3 | `isci/gorev_iscisi.py:250` | Güvenlik | Düşük | Görev hatasında `aciklama` ham istisna metnini içerir; `/analiz/durum` ile pilot anahtarına da görünür (gorev_id tahmin edilemez UUID) | Onay bekliyor |
| D-4 | `arayuz/web_arayuzu.py:133` | Hata | Düşük | `contextlib.redirect_stdout` süreç geneli; iki Streamlit oturumu aynı anda analiz yaparsa günlükler karışır | Not (tek kullanıcılı araç) |
| D-5 | `rota/rota_optimizasyonu.py` | Mimari | Orta | 2.333 satır; `rota_simulasyonu_olustur` ~460 satır, iç içe 8 fonksiyon | Onay bekliyor |
| D-6 | proje geneli | Test/araç | Orta | Tip denetimi yok; mypy 134 yanlış alarm veriyor, gerçek hatayı gürültüde saklar | Onay bekliyor |
| D-7 | 8 modül (`api/*`, `config`, `depo/veritabani`) | Kod kalitesi | Düşük | `load_dotenv()` her modülde tekrar | Not |
| D-8 | `api/yollar/analiz.py:166` | Kullanılabilirlik | Düşük | Toplu analizde uçuş başına `bildirim_webhook_url` sessizce yok sayılıyor | Not |

Bakılıp sorun bulunmayanlar: anahtar karşılaştırması (sabit süre, bytes), WS bileti (imza + DB'de tek
kullanım), CSP ve güvenlik başlıkları, gövde boyutu sınırı, SSRF + DNS rebinding koruması, MCP salt
okunur sorgu katmanı, tüm SQL'in parametreli olması (Trino dahil), toplu silmede LIKE joker kaçışı,
model geri alma (manifest + SHA-256), görev kuyruğu (SKIP LOCKED, kalp atışı, sahiplik kontrollü
bitirme), advisory lock (AUTOCOMMIT), web sayfalarındaki `innerHTML` kullanımları (yalnız sayısal
sunucu verisi), SIGMET ayrıştırmada kayıt başına hata izolasyonu, TI1/deformasyon formülleri
(katı cisim dönmesinde sıfır).

## 5. Onay bekleyenler

1. **D-5 rota modülünü bölmek** (aday, zamanlama, bulgular, CZML ayrı dosyalara). Davranış
   değişmez ama 2.300 satırlık taşıma; sunum (5 Kasım) öncesi risk/fayda tartılmalı.
2. **D-6 mypy'yi kademeli açmak**: `pyproject.toml`'a `[tool.mypy]` + önce `api/`, `depo/`,
   `fizik/` için CI adımı; yeni dev bağımlılığı demek.
3. **D-3 görev hata metni**: API'ye genel mesaj, ayrıntı yalnız log ve yönetici `/sistem/durum`'da.
   Operatörün `/analiz/durum`'dan gördüğü ayrıntı azalır.

## 6. Kalan riskler ve teknik borç

- Araştırma/CLI modüllerinde kapsam düşük (`cli/demo_ekranlari` %27, `arayuz/web_arayuzu` %46,
  `cli/performans_olcumu` %51); karar destek yolu değil.
- Yerel geliştirme Python 3.14, üretim 3.12; CI ikisini de koşuyor, yerel uyarılar bu farktan.
- Bilimsel sınır değişmedi: çıktılar sertifikalı EDR değildir, sistem karar destek aracıdır.

## 7. Yol haritası

1. Bu dalın birleşmesi + `api`/`worker` imajının yeniden derlenmesi (D-1/D-2 çalışan konteynerde).
2. D-6 (dar kapsamlı mypy) — en ucuz kalıcı kazanç.
3. 5 Kasım sonrası D-5 bölme.
4. D-3 ve D-8 kullanıcı kararına göre.

## 8. Uygulama durumu (20 Ekim akşamı, kullanıcı tüm maddeleri onayladı)

| No | Yapılan | PR |
|---|---|---|
| D-1, D-2 | Webhook log maskesi; boş sayısal ortam değişkeni | #124 |
| D-6 | mypy `api/`, `depo/`, `fizik/` için açık (`pyproject` `[tool.mypy]`, CI 3.12 adımı, `tam_denetim.sh`); 19 tip hatası giderildi | #125 |
| D-3 | Görev hatası `/analiz/durum` ve webhook'a ham istisna metni yazmaz: hata türü + görev kimliği, ayrıntı logda; kimlik/kayıt/bağlantı hataları dostane mesajla | #125 |
| D-8 | Toplu analizde uçuş başına webhook 422 ile reddedilir | #125 |
| D-4 | Streamlit analizleri süreç geneli kilitle sıraya girer; AppTest testleri, arayüz kapsamı %46 → %75 | #125 |
| D-7 | `load_dotenv` yalnız `config.py`'de (8 tekrar kaldırıldı; her modülde `.env` yüklendiği doğrulandı) | #125 |
| D-5 | `rota_optimizasyonu.py` 2.333 → 1.170 satır: `a_yildiz`, `geometri`, `ruzgar`, `brifing`, `bulgular`, `czml`. Testlerin yamaladığı adlar ana modülde; 4 senaryoda (ATS dahil) master ile çıktı bayt bayt aynı | #126 |

`rota_simulasyonu_olustur` (~460 satır, iç içe kapanışlar) bölünmedi: kapanışlar ortak yerel durumu
paylaşıyor; ayırmak davranış riski taşır, ayrı ve testle desteklenen bir iş olarak bırakıldı.
Kapsamı düşük kalan araştırma CLI'ları (`demo_ekranlari`, `performans_olcumu`) karar destek yolu
olmadığı için test eklenmedi.
