# Değişiklik Geçmişi

Bu proje semantik sürümleme kullanmıyor (henüz tek bir sürekli geliştirilen
sürüm) -- bu yüzden değişiklikler tarih/sürüm numarası yerine tema başına
gruplanmıştır, en yeni en üstte.

## Kod kalitesi ve dağıtım araçları

- **ruff + pre-commit:** `pyproject.toml`'da lint kuralları (E/F/W/I);
  `.pre-commit-config.yaml` ile `ruff check`/`ruff format` + temel dosya
  hijyeni hook'ları. Tüm kod tabanı bir kez `ruff format` ile taban
  çizgisine getirildi (sadece biçimlendirme, davranış değişikliği yok).
- **Merkezi konfigürasyon:** `config.py`'deki hemen hemen her sabit artık
  aynı isimde bir ortam değişkeniyle kod değiştirmeden ezilebilir.
- **Pydantic response modelleri + CORS:** API uç noktaları artık
  `response_model=` ile Swagger'da gerçek bir şema gösteriyor (`semalar.py`).
  CORS, `CORS_IZIN_VERILEN_KAYNAKLAR` ortam değişkeniyle açılır; varsayılan
  kapalı.
- **Tutarlılık:** Kod tabanındaki ASCII-transliterasyonlu Türkçe metinler
  (`cozunurlugunu` gibi) gerçek Türkçe karakterlere çevrildi. `harita.py`'deki
  `pd_isna`, pandas'ın kendi `pd.isna()`'sını yeniden yazmak yerine ona ince
  bir sarmalayıcı oldu.
- **GitHub Actions CI:** her push/PR'da lint (`ruff check` + `ruff format
  --check`) ve test (gerçek bir PostgreSQL servis konteyneriyle: `alembic
  upgrade head` + `pytest`) job'ları çalışır.
- **Docker:** `Dockerfile` + `docker-compose.yml` ile Postgres + `api_servisi.py`
  tek komutla (`docker compose up`) ayağa kalkar; bağlantı bilgileri `.env`'den
  okunur, image'a gömülmez.

## Performans, loglama, migration, çıktı klasörü

- **Toplu (bulk) veritabanı yazımı:** `ucus_ve_olcumleri_kaydet`, satır satır
  ORM nesnesi oluşturmak yerine tüm tabloyu vektörel olarak sözlük listesine
  çevirip TEK bir toplu `INSERT` ile yazıyor (gerçek veriyle ölçüldü: 5000
  satır ~0.5 saniye).
- **`print()` yerine `logging`:** `api_servisi.py`'nin kendi tanı/hata
  mesajları artık `loglama.py` üzerinden seviyeli/filtrelenebilir
  (`LOG_SEVIYESI`, isteğe bağlı `LOG_DOSYASI`) `logging` kullanıyor. CLI
  araçlarının (`main.py`, `toplu_analiz.py`, `web_arayuzu.py`) insan için
  tasarlanmış adım adım çıktısı bilinçli olarak `print()` olarak kaldı.
- **Alembic migration'ları:** Veritabanı şeması artık kod içinde örtük
  (`create_all`) değil, `migrations/` altındaki migration'larla yönetiliyor.
- **Görev kaydı bellek sızıntısı düzeltmesi:** `api_servisi.py`'deki
  `_gorevler` sözlüğü artık kendiliğinden temizleniyor (TTL + sayı tavanı).
- **`veri_kontrol.py` güncellendi:** Artık üretilmeyen
  `eslesme_sonuclari_*.csv` yerine doğrudan PostgreSQL'den okuyor, ve
  örnekleme yanlılığı olmaması için TÜM ölçüm noktalarını inceliyor.
- **Çıktı klasörü:** Harita HTML'leri ve toplu analiz özeti artık proje
  köküne değil `ciktilar/` altına yazılıyor.
- **Büyük rotalarda hafif harita:** `harita.py`'nin animasyonu artık çok
  uzun rotalarda (>2000 nokta) seyreltiliyor; ham veri PostgreSQL'de tam
  haliyle duruyor.

## Kritik güvenlik ve sağlamlık düzeltmeleri

- **NaN → NULL:** Veri küpünün kapsamı dışındaki noktalar veritabanına
  artık `NaN` değil `NULL` olarak yazılıyor -- önceden bu, API'den
  okunduğunda "Out of range float values are not JSON compliant" hatasıyla
  500'e düşüyordu.
- **SQL enjeksiyonu düzeltmesi:** `veri_yukleme.py` ve `ornek_ucus_bul.py`
  artık kullanıcı girdisini f-string ile SQL'e gömmüyor; Trino'nun
  parametreli sorgu desteğini kullanıyor.
- **Gereksiz OAuth2 girişi düzeltmesi:** `trino_baglantisi_olustur()` artık
  süreç boyunca tek bir `OAuth2Authentication` nesnesini yeniden kullanıyor
  -- eskiden her çağrıda yenisi oluşturulup token önbelleği sıfırlanıyordu.
- **Hata mesajı sızıntısı düzeltmesi:** API'nin 500/503 yanıtları artık ham
  exception mesajını istemciye döndürmüyor; tam ayrıntı sunucu tarafında
  loglanıyor.
- **Girdi doğrulama:** `tarih`/`ucus_numarasi` formatı doğrulanıyor, liste
  uç noktaları sayfalanıyor ve üst sınırlara sahip.
- **Zamanlamaya dayanıklı anahtar karşılaştırması:** API anahtarı artık
  `secrets.compare_digest` ile karşılaştırılıyor.

## PostgreSQL, FastAPI ve MCP entegrasyonu

- **PostgreSQL entegrasyonu:** `veritabani.py` + `models.py` (SQLAlchemy
  ORM) -- lokal CSV çıktısının yerini `ucuslar`/`edr_olcumleri` tabloları
  aldı.
- **FastAPI REST API'si:** `api_servisi.py` -- API anahtarlı, `/api/v1`
  sürümlü, async okuma uç noktaları, WebSocket ile canlı uyarı, n8n için
  webhook bildirimi.
- **MCP sunucusu:** `mcp_postgres_sunucusu.py` + `.mcp.json` -- Claude
  Code'un veritabanına salt okunur MCP ile bağlanabilmesi için.
- **n8n otomasyonu:** `toplu_analiz.py` doğrudan değil, `api_servisi.py`'nin
  `/analiz/*` uç noktaları üzerinden -- otomasyon tarafının projenin Python
  iç yapısını hiç bilmesine gerek kalmaz.
- **Bilinçli olarak eklenmedi:** `veri_indirme.py`'nin gerçek ERA5
  indirmesini tetikleyen bir uç nokta (rate-limit/ban riski nedeniyle
  hâlâ sadece elle çalışıyor), JWT/OAuth2 (tek kullanıcılı araç için statik
  API anahtarı yeterli görüldü).

## Güvenilirlik iyileştirmeleri (retry, kalibrasyon uyarısı)

- **Trino/OpenSky retry mantığı:** `veri_yukleme.py` artık `tenacity` ile
  SADECE geçici ağ/sunucu hatalarında, üstel artan aralarla ve en fazla 3
  denemeyle yeniden deniyor -- OpenSky'yi yormamak için deneme sayısı
  bilerek düşük. `toplu_analiz.py` uçuşlar arasına bekleme koyuyor.
- **Kalibrasyon uyarısı:** `config.EDR_OLCEKLENDIRME_KATSAYISI` kalibre
  edilene kadar `main.py` her çalıştırma sonunda uyarı basıyor.
- **`harita.py` için birim testleri eklendi.**

## Performans, Richardson indeksi, toplu analiz, web arayüzü ve hata iyileştirmeleri

- Deformasyon/kayma hesabı tüm grid üzerinde vektörel hale getirildi
  (gerçek veriyle ölçülen kazanç: ~250x).
- Richardson sayısı gibi ek bir kararlılık indeksi eklendi
  (`turbulans_indeksleri.richardson_sayisi_hesapla`) -- TI1'e keyfi bir
  katsayıyla karıştırılmadan, ayrı bir sütun olarak.
- `kalibrasyon.py`: gerçek PIREP/AMDAR verisiyle ölçekleme katsayısını
  kalibre etmek için bir araç (gerçek gözlem verisi bu depoda yok).
- Terminalden bağımsız, tarayıcıdan kullanılabilir bir arayüz
  (`web_arayuzu.py`, Streamlit).
- Birden fazla uçuşu tek seferde analiz etme (`toplu_analiz.py`).
- Anlaşılır Türkçe hata mesajları (`hata_yardimcisi.py`).

## Moduler mimari kurulumu

Projenin ilk büyük refactor'ü -- tek dosyalık, keyfi katsayılı bir
prototipten modüler bir mimariye geçiş:

| Eski | Yeni |
|---|---|
| `edr_hesaplama.py` ve `interaktif_harita.py`'de iki farklı, keyfi katsayılı EDR formülü | `turbulans_indeksleri.py`: Ellrod TI1 indeksi (Ellrod & Knapp, 1992) — havacılık meteorolojisinde CAT tahmini için gerçekten kullanılan yöntem |
| `trino_baglanti.py`'de şifre düz metin kod içinde | `kimlik_dogrulama.py` + `.env`: kimlik bilgileri ortam değişkeninden okunuyor |
| `kucuk_simulasyon.py`: `np.linspace` ile uydurulmuş rota | `veri_yukleme.py`: `flights_data4` üzerinden uçuş numarasından (callsign) gerçek rota çekiliyor |
| Sabit tek nokta sorgusu, koordinat filtresi | `ucus_numarasi_ile_rota_cek()`: callsign → icao24 → state_vectors_data4 zinciri |
| Statik harita, tek zaman anı | `harita.py`: `TimestampedGeoJson` ile zaman kaydırıcılı animasyon, gerçek uçuş bilgisi popup'ları, lejant |
| Basınç/irtifa birim karışıklığı | `birim_donusumleri.py`: ISA barometrik formülüyle metre ↔ hPa dönüşümü |

## Bilinçli olarak yapılmayanlar

- **Offline-first Flutter mobil arayüz:** Projede hiç Flutter/mobil kod
  yok; bu, backend'e bir özellik eklemek değil, ayrı bir mobil uygulama
  geliştirme projesi gerektirir. API tarafı (JSON uç noktaları + WebSocket
  canlı uyarı) buna hazır durumda; mobil istemci ayrı bir iş olarak ele
  alınmalı.
- **Yapay zeka destekli tahmin modeli:** `kalibrasyon.py`'nin de belirttiği
  gibi bu depoda gerçek PIREP/AMDAR gözlem verisi yok. Etiketlenmiş gerçek
  veri olmadan bir ML modeli "eğitmek", projenin başında düzeltilen "uydurma
  katsayı" hatasının bir versiyonunu (bu sefer sahte bir model görünümü
  altında) tekrarlamak olurdu. Gerçek gözlem verisi sağlanırsa, üzerine bir
  tahmin modeli kurmak anlamlı hale gelir.
- **20+ modülü `turbulans_radar/` paketi + `scripts/` altında yeniden
  yapılandırmak:** Bilinçli olarak ayrı, kendi başına bir iş olarak
  bırakıldı -- TÜM import'ları, `.mcp.json` yolunu, `alembic.ini`'yi ve
  test dosyalarını aynı anda etkileyen büyük bir refactor.
