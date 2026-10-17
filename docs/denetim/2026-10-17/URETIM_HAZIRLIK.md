# Üretime geçiş ve simülasyon hazırlığı: Faz 0 denetimi

17 Ekim 2026 · depo `master` `486a153` · kod değişikliği yok. Temel ölçüm: [`temel.md`](temel.md).

Okuyucu: proje sahibi ve sonraki Faz 1 çalışması. Her satır depoda yeniden doğrulandı;
"Durum" sütunu: **Doğru** (bulgu aynen geçerli), **Kısmen** (bulgu geçerli ama gerekçesi ya da
kapsamı düzeltildi), **Yanlış** (bulgu geçersiz), **Yeni** (bu denetimde eklendi).
Yollar depo köküne görelidir; makineye özgü yollar `<DEPO>`, `<KULLANICI>` ile maskelendi.

Önem: **P0** canlıya (güvenilmeyen ağa) açılmayı engeller · **P1** üretim kalitesi ·
**P2** sonraya bırakılabilir. Efor: S (≤2 sa), M (yarım gün), L (≥1 gün).

## Özet

- 28 bulgunun 21'i **doğru**, 7'si **kısmen doğru**; **yanlış** çıkan yok. 7 **yeni** bulgu eklendi.
- En büyük boşluk ağa açılış katmanı: TLS vekili, kapalı başlama kuralı ve tarayıcı güvenlik
  başlıkları yok. Bu üçü çözülmeden API `0.0.0.0`'a açılmamalı (bugün varsayılan `127.0.0.1`).
- Kısmen doğru çıkanların ortak noktası: mekanizmanın bir kısmı zaten var (yedek şifre çözme
  zinciri doğrulanmış, Docker secret iki sır için kullanılıyor, anahtar rotasyonu README'de,
  bazı fail-safe durumları Playwright'ta). Faz 1'de bunların üzerine kurulmalı, baştan yazılmamalı.
- P0-6 (MCP) önemi **P1'e indirildi**: MCP sunucusu yalnız geliştirici makinesinde stdio ile
  çalışıyor, üretim yolunda değil; ancak imaja giriyor (P1-5).

## Ağa açılan yüzey (`docker compose config`, maskelenmiş özet)

Ham çıktı hiçbir yere yazılmadı; aşağıdaki özet yalnız yapıdır, değer içermez.

| Servis | Profil | Dış port | Önemli bağlamalar | Sır kaynağı |
|---|---|---|---|---|
| `db` | varsayılan | `127.0.0.1:5432`, `127.0.0.1:5433` → 5432 | `turbulans_pgdata` volume | ortam (`POSTGRES_PASSWORD`, varsayılan `postgres`) |
| `api` | varsayılan | `${API_YAYIN_ADRESI:-127.0.0.1}:8000` | 13 bind; `db_yedekleri` **ro**, `model_deposu` rw | `env_file: .env` + `cdsapirc` secret |
| `worker` | varsayılan | yok | `api` ile aynı 13 bind (`db_yedekleri` dahil) | `env_file: .env` + `cdsapirc` secret |
| `yedek` | varsayılan | yok | `db_yedekleri` rw, `<KULLANICI>/OneDrive/...` → `/dis_yedek` (override) | ortam `PGPASSWORD` + `yedek_parolasi` secret |
| `demo` | `demo` | yok | `ciktilar` | `env_file: .env` |

- Tanımlı profiller: yalnız `demo`. `uretim` ve `izleme` profilleri **yok** (komut hatasız
  çalışıyor ama ek servis gelmiyor).
- Hiçbir serviste `mem_limit`, `cpus`, `logging`, `read_only`, `cap_drop` yok.
- Kullanılmayan sırlar `api`/`worker`/`demo`'da boşaltılıyor (`MCP_POSTGRES_*`,
  `UYGULAMA_POSTGRES_PASSWORD`; `docker-compose.yml:17-23`). API anahtarları `worker` ve `demo`'ya
  da gidiyor (Y-4).
- Uygulama süreçleri uid 1000 ile çalışıyor (API PID 1 `Uid: 1000`); `docker compose exec`
  varsayılanı root (README:428-430'da belgelenmiş).

## P0: canlıya geçişi engelleyenler

| No | Bulgu | Önem | Durum | Kanıt | Önerilen çözüm | Efor | ONAY? |
|---|---|---|---|---|---|---|---|
| P0-1 | TLS sonlandıran ters vekil yok; yalnız README önerisi | P0 | Doğru | `README.md:425-427`; depoda Caddyfile/nginx yok; compose'da `uretim` profili yok | `--profile uretim` ile `caddy` (otomatik sertifika, HSTS, HTTP→HTTPS); API portu yalnız iç ağ; `FORWARDED_ALLOW_IPS` vekil adresi | M | Hayır (alan adı/sertifika seçimi için evet) |
| P0-2 | Ağa açılışta kapalı başlama yok: yalnız uyarı loglanıyor; demo anahtarı, `postgres` varsayılan şifresi, kısa anahtar, örnek saha ve kapalı model bütünlüğü ile açılabiliyor | P0 | Doğru | `api/guvenlik.py:61-66` (yalnız `_logger.warning`); `ayar_dogrulama.py` sır/ağ kuralı içermiyor; `docker-compose.yml:20,51,151` (`:-postgres`); `config.py:202` `MODEL_BUTUNLUK_ZORUNLU` varsayılan `False`; `config.py:507` `KISITLI_SAHA_ORNEK_VERI_YUKLE` varsayılan `True`; `.env.demo:9,12-13` herkesçe bilinen değerler | `ayar_dogrulama.py`'ye "ağa açıksa" kuralları: demo anahtarı, varsayılan DB şifresi, <32 karakter anahtar, örnek saha açık, bütünlük kapalı, `UYGULAMA_POSTGRES_*` boş (süper kullanıcıya düşme, Y-1) → API ve işçi başlamaz, tek mesaj. Birim testleri | S–M | Hayır |
| P0-3 | Tarayıcı güvenlik başlıkları yok (CSP, frame-ancestors, nosniff, Referrer-Policy); anahtar `sessionStorage`'da | P0 | Doğru | `src`/`web` içinde başlık adı geçmiyor; canlı yanıtta yalnız `server: uvicorn` (`temel.md`); `web/harita3d.html:157,374,547`, `web/ucus_simulasyonu.html:210,642,713`; satır içi `<script>` blokları (`harita3d.html:28,153`, `ucus_simulasyonu.html:35,206`) ve `onerror=` öznitelikleri CSP `script-src 'self'`'i şimdilik engelliyor | Önce satır içi betikleri `web/*.js`'e taşı (CDN yedeği kalkınca `onerror` da gider), sonra başlıklar (middleware; Caddy varsa orada da). Playwright CSP açıkken | M | Hayır |
| P0-4 | CDN yedeği SRI'sız `document.write` ile yükleniyor | P0 | Doğru | `web/harita3d.html:26,29`; `web/ucus_simulasyonu.html:33,36`; `/saglik` `cdn_yedegi` yalnız uyarı (`api_servisi.py:944`) | Üretimde CDN yedeği kaldırılır (kütüphaneler imajda: `web/vendor/` mevcut); `cdn_yedegi` üretimde hata | S | Hayır |
| P0-5 | Tüm DB dökümleri API konteynerine (ro) bağlı | P0 | Kısmen | `docker-compose.yml:39` ortak volume → **API ve işçi** (Y-3); API içinde 14 dosya (`.dump` + `dosyalar_*.tar.gz`) listelendi; okuyan tek yer `api_servisi.py:1045-1050` (yalnız tazelik) | `yedek` servisi `yedek_durumu.json` yazsın, API yalnız onu okusun; `db_yedekleri` bağlaması iki servisten de kalksın. Duman testi: API'de `.dump` yok | S | Hayır |
| P0-6 | MCP sunucusu `MCP_POSTGRES_*` boşsa `POSTGRES_*`'a (süper kullanıcı olabilir) düşüyor; regex filtresi fonksiyon çağrılarını engellemiyor | **P1** | Kısmen | `cli/mcp_postgres_sunucusu.py:114-123` (dolu olanı yazar, boşsa sessiz geçer), `:43-57` filtre; `postgresql_readonly=True` yazmayı engelliyor ama `pg_terminate_backend`, süper kullanıcıda `pg_read_file` gibi fonksiyonlar mümkün. Bu makinede `MCP_POSTGRES_*` dolu. Sunucu yalnız `.mcp.json` ile yerelde stdio çalışıyor, üretim yolunda değil | MCP_* eksikse başlamayı reddet; fonksiyon kara listesi (`set_config`, `pg_*`, `lo_*`, `dblink`); imajdan çıkar (P1-5) | S | Hayır |
| P0-7 | Hibrit topoloji (OpenSky dizüstünde, API sunucuda) tasarlanmadı | P0 (B planı seçilirse) | Doğru | `docs/fizibilite/OPENSKY_BULUT_ERISIMI.md:50-56`; `docs/adr/` 0001–0012, topoloji ADR'si yok. Not: dış iz gönderme ucu zaten var (`POST /api/v1/analiz/rota`, `api/yollar/analiz.py:130`) | ADR 0013: (a) dizüstü dış izi `POST /analiz/rota` ile gönderir, (b) imzalı Parquet senkronu, (c) OpenSky'sız sunucu; güvenlik, kota, hata durumları | M | **Evet** (kod öncesi) |
| P0-8 | Geri yükleme denenmiyor; RPO/RTO tanımsız | P0 | Kısmen | `otomasyon/db_yedekle.sh:20` yalnız `pg_restore -l`. Ancak elle prosedür README'de (`README.md:1487-1494`) ve 8 Ekim'de disk dışı `.gpg` kopyanın çözülüp yerel dump ile sha256 eşleştiği doğrulandı (veritabanına yükleme yapılmadı). RPO/RTO hiçbir belgede yok | `otomasyon/geri_yukleme_tatbikati.sh`: son dump'ı geçici bir postgres konteynerine yükle, tablo satır sayılarını karşılaştır, rapora yaz; haftalık. RPO (24 sa) / RTO hedefi `docs/ISLETIM_KILAVUZU.md`'de | S–M | Hayır |
| P0-9 | Sır yönetimi tek `.env`; rotasyon yok; PR #1'deki eski OpenSky sırrı | P0 (depo herkese açılırsa) | Kısmen | Docker secret iki sır için zaten kullanılıyor (`cdsapirc`, `yedek_parolasi`; `docker-compose.yml:105,137,165,187-191`). `API_ANAHTARI`/`POSTGRES_PASSWORD` için `*_FILE` desteği yok. API anahtarı rotasyonu README'de var (`README.md:402-405`, `API_ANAHTARLARI`); DB şifresi rotasyonu yok. PR #1 Destek talebi bekliyor (`docs/guvenlik/GUVENLIK_TARAMASI_2026-10-05.md:10,30-38`); şifrenin kendisi geçersiz | `*_FILE` desteği (`config`/`guvenlik`/`veritabani`), üretimde secret; DB şifresi rotasyon runbook'u (P1-10). Depo görünürlüğü değişmeden önce GitHub Destek talebi | M | **Evet** (Destek talebi dış iletişim) |

## P1: üretim kalitesi

| No | Bulgu | Önem | Durum | Kanıt | Önerilen çözüm | Efor | ONAY? |
|---|---|---|---|---|---|---|---|
| P1-1 | Kaynak sınırı ve log rotasyonu yok | P1 | Doğru | compose özeti: hiçbir serviste `mem_limit`/`cpus`/`logging` yok | Servis başına sınır (değerler `PERFORMANS_RAPORU.md` ölçümlerinden), `json-file` `max-size: 10m`, `max-file: 5` | S | Hayır |
| P1-2 | Migration API açılışında, öncesinde yedek yok | P1 | Doğru | `Dockerfile:54` `alembic upgrade head && uvicorn`; işçi API'ye bağlı (`docker-compose.yml:119-122`) | Tek seferlik `migrate` servisi (önce `pg_dump`, sonra upgrade); `api` `service_completed_successfully` ile bağlı | S | Hayır |
| P1-3 | İzleme yığını yok | P1 | Doğru | `izleme/`, `prometheus*` yok; `/metrics` ve örnek alarmlar yalnız README (`README.md:1354`) | `izleme/prometheus.yml`, `alarmlar.yml`, `--profile izleme` | M | Evet (bildirim kanalı) |
| P1-4 | Tedarik zinciri sabitlemesi eksik | P1 | Doğru | `docker-compose.yml:47,143` `postgres:16`; CI `postgres:16` (`ci.yml:75,139`); Actions `@v4/@v5` etiketle (`ci.yml:12-13` vd.); Dependabot/Renovate yok. Python taban imajı digest'li (`Dockerfile:8`), bağımlılıklar hash'li kilitli | Digest + commit SHA sabitleme, `.github/dependabot.yml` | S | Hayır |
| P1-5 | `.dockerignore` eksik | P1 | Doğru | `.dockerignore` bu yolları dışlamıyor; çalışan imajda **var**: `CLAUDE.md`, `.mcp.json`, `docs/`, `scripts/`, `.githooks/`, `.env.demo`, `.env.uretim.example`, Postman koleksiyonu (`temel.md`) | Ekle; CI'da `docker run … test ! -e /app/.mcp.json` | S | Hayır |
| P1-6 | `/saglik?derin=true` anahtarsız iç durum veriyor; `server: uvicorn` | P1 | Kısmen | `api_servisi.py:1184-1197`: anahtarsız, ama `ayrintili=False` ile yalnız bileşen adı + durum döner, ayrıntı yok; 15 sn önbellekli (`:1204-1230`). `server: uvicorn` canlı yanıtta görüldü; `Dockerfile:54`'te `--no-server-header`/`--proxy-headers` yok | Üretimde anahtarsız uçta yalnız `{"durum"}`; `--no-server-header --proxy-headers` | S | Hayır |
| P1-7 | WS bileti tek kullanımlığı süreç içi | P1 | Doğru | `api/guvenlik.py:131,146-158` (`_kullanilmis_biletler` sözlüğü; yorumda sınır belirtilmiş). Varsayılan `WEB_CONCURRENCY=1`, üretim örneğinde 4 (`.env.uretim.example`) | Kullanılmış imza PostgreSQL'de (TTL 60 sn); 4 süreçli test | S | Hayır |
| P1-8 | Lisans: Esri karoları koda gömülü, kapatma bayrağı yok | P1 | Doğru | `web/harita3d.html:210`, `web/ucus_simulasyonu.html:264`; `docs/VERI_KAYNAKLARI_VE_LISANSLAR.md` | `ALTLIK_KATMANI=dogal|esri` (varsayılan doğal), canlı yayın öncesi lisans listesi; "hukuki görüş değildir" notu | S | Hayır |
| P1-9 | AIRAC 29 Ekim'de bitiyor | P1 | Doğru | `ats_verisi/ats_agi.json` `airac_bitis: 2026-10-29`; `/saglik` bu tarihi yalnız raporluyor (`api_servisi.py:1069`), uyarı üretmiyor | 29 Ekim'de AIP yenileme (dış indirme, ONAY); bitişe 7 gün kala `/saglik` uyarısı | S | Evet (indirme) |
| P1-10 | İşletim kılavuzu yok | P1 | Doğru | `docs/` altında kılavuz/runbook yok; prosedürler README'ye dağılmış (yedek `:1487`, anahtar `:402`) | `docs/ISLETIM_KILAVUZU.md`; her prosedür bir kez denenir | M | Hayır |

## Simülasyon hazırlığı

| No | Bulgu | Önem | Durum | Kanıt | Önerilen çözüm | Efor | ONAY? |
|---|---|---|---|---|---|---|---|
| S-1 | GFS için ayrı TI1 eşiği boş | P1 | Doğru | `config.py:283` varsayılan `None`; `.env`'de tanımlı değil; `SISTEM_KARTI.md:78` (%11,1 / %8,5, eşdeğer 8,30e-7) | **18 Ekim dondurmasından sonra** `turbulans-esik-esleme` → `TI1_ESIK_ORTA_SIDDETLI_GFS`; sonuç ne çıkarsa | S | Hayır (ek indirme gerekirse evet) |
| S-2 | Sonuçta commit kimliği yok | P1 | Doğru | `uretim_bilgisi.py:17-25` yalnız paket sürümü; `SISTEM_KARTI.md:110` "Commit kimliği yoktur" | `ARG GIT_SHA` → `uretim_bilgisi.commit`; test 40 karakter | S | Hayır |
| S-3 | Senaryo seçici yok; sayfa 2019 değerleriyle açılıyor | P1 | Doğru | `web/ucus_simulasyonu.html:89-98` sabit `value=` (41.00/28.90 → 36.90/30.70, `2019-01-05T12:00`); `web/veri/` yalnız `ulke_sinirlari.geojson` | `web/veri/senaryolar.json` + açılır liste; senaryo başına Playwright | M | Hayır |
| S-4 | Fail-safe durumları simülasyonda gösterilemiyor | P1 | Kısmen | Playwright'ta kısıtlı saha ve kapsam dışı var (`tests/test_web_ucus_simulasyonu.py:52,95`); "ÖNERİ YOK" metni arayüzde var (`ucus_simulasyonu.html:422`) ama tetikleyen senaryo yok; SIGMET bayat, `erisilemedi`, devre kesici tarayıcıda test edilmiyor (`SISTEM_KARTI.md` §4) | Demo profilinde fikstürler (gerçek arşiv; yoksa **SENTETİK** etiketli), üretimde yüklenemez; durum başına Playwright | M–L | Hayır |
| S-5 | Ağsız prova dış adrese gidiyor (Esri) | P1 | Doğru | `docs/sunum/DEMO_SENARYOSU.md:35-36` (`--agsiz` listesinde yalnız `server.arcgisonline.com`) | P1-8 bayrağıyla demo profilinde Esri kapalı; liste boş | S | Hayır |
| S-6 | Dondurma sonrası belge senkronu | P1 | Doğru | `docs/YAPILACAKLAR.md` "18 Ekim" maddeleri; `scripts/` içinde sayı tutarlılığı betiği yok | `docs/sonuclar/2026-10-18/SAYILAR.md` tek kaynak + `scripts/sayi_tutarliligi.py` (CI'da uyarı) | M | Hayır |
| S-7 | "Uçuş sırasında yeniden hesapla" gösterim amaçlı ama etiketsiz | P1 | Doğru | `web/ucus_simulasyonu.html:116-118` düğmede etiket yok; genel not `:147` ve TI1 notu `:465` var | Düğme yanında kalıcı "gösterim amaçlı · NON-OPERATIONAL" | S | Hayır |
| S-8 | Sunum yedeği otomasyonu yok | P1 | Doğru | `docs/YAPILACAKLAR.md:84,88` (25 Ekim `docker save`, 5 Kasım video); `scripts/` içinde betik yok | `scripts/sunum_paketi.sh` (temiz klon → demo → ekranlar → `docker save` → sha256) | S | Hayır |
| S-9 | Eşzamanlı kullanım provası yok | P1 | Kısmen | `docs/PERFORMANS_RAPORU.md:17-22` 4/16 eşzamanlı ölçüm **var**, ama hız sınırları yükseltilerek (`:34`). Varsayılan sınırlarla, aynı NAT IP'sindeki birden çok tabletle 429 oranı ölçülmedi (sınır IP başına: `api/ortak.py:86-90`) | Varsayılan sınırlar + tek IP'den 10 eşzamanlı istemci; p95 ve 429 oranı | S | Hayır |

## Yeni bulgular

| No | Bulgu | Önem | Kanıt | Önerilen çözüm | Efor | ONAY? |
|---|---|---|---|---|---|---|
| Y-1 | Kapalı başlama kuralının bir parçası: `UYGULAMA_POSTGRES_*` boşsa API/işçi süper kullanıcıyla, o da boşsa `postgres/postgres` ile bağlanıyor | P0 (P0-2'ye dahil) | `docker-compose.yml:13-20` | P0-2 kuralına ekle | — | Hayır |
| Y-2 | `db` iki host portu açıyor (5432 ve 5433); 5433 yalnız Windows MCP için | P2 | `docker-compose.yml:55-60` (ikisi de `127.0.0.1`) | `uretim` profilinde 5432 dahil hiçbir DB portu yayınlanmasın | S | Hayır |
| Y-3 | `db_yedekleri` işçiye de bağlı (P0-5'in kapsamı daha geniş) | P0 (P0-5'e dahil) | `docker-compose.yml:39,129` | P0-5 ile birlikte | — | Hayır |
| Y-4 | API anahtarları `worker` ve `demo`'ya da gidiyor (kullanmıyorlar) | P2 | `docker-compose.yml:123-124,180-181` `env_file: .env`; `x-uygulama-db` yalnız DB sırlarını boşaltıyor; anahtar yalnız `api/` ve CLI araçlarında kullanılıyor | `worker`/`demo` için `API_ANAHTARI: ""`, `API_PILOT_ANAHTARI: ""` | S | Hayır |
| Y-5 | `harita3d.html`'de "karar destek amaçlıdır / sertifikalı EDR değildir" ifadesi yok (yalnız TI1 doğrulanmamıştır notu) | P2 | `web/harita3d.html:134-135`; karşılaştırma `ucus_simulasyonu.html:147` | Lejant altına aynı cümle | S | Hayır |
| Y-6 | Docker derleme önbelleği ve kullanılmayan imajlar ~50 GB (dizüstü diski) | P2 | `docker system df` (17 Ekim): build cache 25,5 GB, imajlar 25,6 GB geri kazanılabilir | `docker builder prune` (geri alınamaz) | S | **Evet** |
| Y-7 | Dizüstü uykudan çıkınca WSL'de geçici DNS hataları; GFS/SIGMET 30 dk'da kendini topluyor | P2 (yalnız dizüstü) | 16–17 Ekim `docker compose logs` (`Temporary failure in name resolution`) | B planında sunucuda yok; dizüstünde izlenir | — | Hayır |

## P2 (yalnız listelendi, yapılmayacak)

- Çok kullanıcılı kimlik (OIDC), anahtarların DB'de hash'li saklanması.
- `sessionStorage` yerine kısa ömürlü HttpOnly çerez/oturum belirteci.
- Avrupa/Türkiye nesnel etiket kaynağı (MGM, IATA Turbulence Aware): dış iletişim.
- `GUVENILIR_ONGORU_SAAT` (48 sa) ve `ROTA_SEYIR_KUTLE_ORANI` (0,85) kalibre edilmedi.
- ML modeli Türkiye'de doğrulanmadı; rota kararına girmediği sürece P2.
- Y-2, Y-4, Y-5, Y-6, Y-7.

## Önerilen P0 sırası (onaya sunulur)

1. **P0-2 + Y-1 kapalı başlama** (S–M): en ucuz ve diğer her şeyin emniyet kemeri; yanlış
   `.env` ile ağa açılmayı imkânsız kılar.
2. **P0-4 CDN yedeğini kaldır** (S) → **P0-3 satır içi betikleri dışarı al + güvenlik başlıkları** (M):
   P0-4 önce gelir çünkü `onerror`/`document.write` CSP'nin önündeki engeldir.
3. **P0-5 + Y-3 yedekleri API/işçiden ayır** (S).
4. **P0-1 TLS vekili `--profile uretim`** (M): 1–3'ten sonra; vekil başlıkları da taşır.
5. **P0-8 geri yükleme tatbikatı + RPO/RTO** (S–M): veri kaybı önceliği nedeniyle 18 Ekim
   dondurmasından önce bir kez çalıştırılması da düşünülebilir (yalnız geçici konteyner, DB'ye dokunmaz).
6. **P0-9 `*_FILE` sır desteği** (M); GitHub Destek talebi ayrı ONAY.
7. **P0-7 hibrit topoloji ADR'si** (M): yalnız B planına geçilirse; kod öncesi ONAY.
8. P0-6 → P1 olarak P1-5 ile birlikte.

Faz 1'e onaysız geçilmez.
