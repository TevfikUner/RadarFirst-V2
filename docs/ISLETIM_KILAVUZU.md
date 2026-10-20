# İşletim kılavuzu (P1-10)

Tek makinelik yığının (WSL2 + Docker: db, migrate_yedegi, migrate, api, worker, yedek) günlük
işletimi. Komutlar WSL'de depo kökünde çalışır. Ayrıntılı açıklamalar README'dedir; burada yalnız
adımlar var. **Denendi** sütunu prosedürün bu makinede en son ne zaman uçtan uca çalıştırıldığını
gösterir.

Sistem karar destek aracıdır, operasyonel karar aracı değildir; çıktılar sertifikalı EDR değildir.

## 1. Başlatma, durdurma, durum

| İş | Komut | Denendi |
|---|---|---|
| Başlat | `docker compose up -d --wait` | 19 Ekim |
| Durdur (veri kalır) | `docker compose stop` | demo klonunda (19 Ekim); ana yığında denenmedi |
| Durum | `docker compose ps -a` (migrate ve migrate_yedegi "Exited (0)" olmalı) | 20 Ekim |
| Sağlık | `curl -s "http://127.0.0.1:8000/saglik?derin=true"`: tüm kontroller `tamam`, `uyarilar: []` | 20 Ekim |
| Günlükler | `docker compose logs --since 1h api worker` (her servis en çok 5 × 10 MB tutar) | 20 Ekim |

`docker compose down -v` **kullanılmaz**: veritabanı volume'unu siler (izin listesinde engelli).

## 2. Güncelleme (master'dan yeni kod)

1. Görev kuyruğu boş olmalı (worker yeniden başlar):
   `curl -s -H "X-API-Key: $API_ANAHTARI" http://127.0.0.1:8000/api/v1/ml/durum` içinde `calisiyor` yok.
2. `git pull`
3. `export GIT_SHA=$(git rev-parse HEAD) && docker compose pull db && docker compose build api worker migrate`
   (bağımlılık katmanı değişirse ~15–20 dk; `GIT_SHA` verilmezse sonuçlarda commit kimliği boş kalır).
4. `docker compose up -d --wait`: önce `migrate_yedegi` doğrulanmış yedek alır
   (`db_yedekleri/migration_oncesi/`), sonra `migrate` şemayı günceller, API ondan sonra başlar.
5. Sağlık kontrolü (§1). Denendi: 19 Ekim (yedek 11 MB, migration yok, tüm kontroller tamam).

## 3. Migration geri dönüşü

`migrate` başarısızsa API başlamaz (`docker compose logs migrate`). Geri dönmek için §4'teki
geri yükleme adımları `db_yedekleri/migration_oncesi/` altındaki en yeni dump'la uygulanır, sonra
önceki commit'e dönülüp §2 tekrarlanır. Yeni migration'lar önce `-test` veritabanında
`alembic upgrade head` + `alembic downgrade -1` ile denenir. Denenmedi (henüz başarısız migration olmadı).

## 4. Yedek ve geri yükleme

- Günlük yedek kendiliğinden: `db_yedekleri/turbulans_YYYYAAGG.dump` + `dosyalar_YYYYAAGG.tar.gz`,
  disk dışı şifreli kopya OneDrive'da (README "Veritabanı yedeği"). Kontrol: `/saglik` `yedek: tamam`.
- Tatbikat: `docker compose exec yedek sh /geri_yukleme_tatbikati.sh`; rapor
  `db_yedekleri/tatbikat/`. Denendi: 20 Ekim, GEÇTİ (4 sn, yedek servisi 512 MB sınırıyla).
- Geri yükleme (mevcut tablolar silinir):
  ```bash
  docker compose stop api worker
  docker compose exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner' < db_yedekleri/turbulans_YYYYAAGG.dump
  sh otomasyon/uygulama_rolu_olustur.sh
  docker compose start api worker
  ```
  Denendi: tatbikatın geçici sunucusunda (18 Ekim, 3 sn); canlı veritabanında denenmedi.
- Kalıcı yedekler (`db_yedekleri/kalici/`, dondurma günü) silinmez.

## 5. ML gece işi

- API zamanlayıcısı `ML_GECE_ISI_SAATI` (bu makinede 03:00 UTC) sonrasındaki ilk açılışta bir kez çalışır;
  bütçe `GUNLUK_VERI_BUTCESI_MB` (500 MB/UTC günü), CDS günde en çok 150 istek.
- Durum: `GET /api/v1/ml/durum` (`son_gorevler`, `veri_bugun_mb`). Elle başlatma:
  `curl -X POST -H "X-API-Key: $API_ANAHTARI" http://127.0.0.1:8000/api/v1/ml/gece-isi` (409: zaten sürüyor).
- Eğitim kararı otomatiktir (aday aktif modeli altın günlerde geçemezse yalnız saklanır).
  Geri alma: `turbulans-ml --geri-al VERSIYON_ID`. Denendi: gece işi her gün; geri alma yalnız testlerde (`tests/test_ml_otomatik_egitim.py`), canlıda denenmedi.
- Dondurma sonrası değerlendirme: `turbulans-ml-yeni-gun --durum`; ≥30 yeni gün olunca bir kez
  `--cikti` (protokol §10, sonuca önceden bakılmaz).

## 6. AIRAC (ATS ağı ve ENR 5.1)

Windows görevi "TurbulansRadar AIRAC yenileme" her gün 12:00'de çalışır, döngü bitmediyse istek atmaz.
Günlük `ciktilar/airac_yenile.log`, durum `ats_verisi/.airac_durum.json`. Döngü sonunda "yenilendi" ve
`db_aktarildi: true` beklenir; BAŞARISIZ yazarsa (ör. ENR 1.3 FRA cümlesi değişti) eski veri korunur ve
ENR 1.3 elle okunur (`docs/veri_hazirlama/ATS_AGI_HAZIRLAMA.md`). Elle: `python -m turbulans_radar.cli.airac_yenile --zorla`.
Denendi: 19 Ekim ("güncel", istek yok); ilk gerçek yenileme 29 Ekim.

## 7. Anahtar ve şifre rotasyonu

- **API anahtarı:** `.env` `API_ANAHTARLARI`'na yeni `kimlik:rol:anahtar` eklenir,
  `docker compose up -d api`, istemciler geçince eskisi çıkarılır (README "Güvenlik ve sağlamlık").
- **Uygulama DB rolü şifresi:** `.env` `UYGULAMA_POSTGRES_PASSWORD` değiştirilir,
  `sh otomasyon/uygulama_rolu_olustur.sh` (rol şifresini günceller; önce `"Turbulence-db-test"` ile),
  sonra `docker compose up -d api worker`.
- **Süper kullanıcı şifresi:** `docker compose exec db psql -U postgres -c "ALTER ROLE postgres PASSWORD '...'"`,
  `.env` `POSTGRES_PASSWORD` güncellenir, `docker compose up -d` (yedek servisi yeni şifreyi alır).
  Sırlar dosyadan da verilebilir (`*_FILE`, Docker secret). Yeni şifre koda ve sohbete yazılmaz.
- Denenmedi (şifre değişikliği canlı bağlantıları keser; sunum sonrası bir kez denenir).

## 9. İzleme (Prometheus)

- Başlat: `docker compose --profile izleme up -d prometheus`; arayüz `http://127.0.0.1:9090`
  ("Alerts" sekmesi; bildirim kanalı yok). Hedef durumu: "Status > Targets", `turbulans_api` UP olmalı.
- Anahtar: `.env` `API_ANAHTARLARI` içindeki `prometheus:yonetici:...` ve aynı anahtarı tutan
  `PROMETHEUS_ANAHTAR_DOSYASI` (depo dışı). Rotasyon §7'deki API anahtarı adımlarıyla; ikisi birlikte değişir.
- Alarm eşikleri `izleme/alarmlar.yml`; değişince `docker compose restart prometheus`.

## 8. Sık sorunlar

| Belirti | Neden | Çözüm |
|---|---|---|
| SIGMET `ConnectError`, GFS hatası | Uykudan sonra WSL DNS | 30 dk içinde kendini toplar; sürerse `wsl --shutdown`, Docker yeniden |
| Derleme `statik_indir` adımında takılıyor | npm erişilemiyor | Durdur, eski imajla devam et, npm dönünce §2 |
| Gece işi `yarida_kaldi` | Bilgisayar uykuya geçti | Aynı gün en çok 3 kez kendiliğinden yeniden dener |
| Rota 429 | IP başına 20 hesap/dk | Önbellekteki rota sayılmaz; NAT'lı kurulumda `ROTA_HESABI_DAKIKADA_MAKS` |
| `migrate_yedegi` başarısız | DB erişilemiyor ya da disk dolu | `docker compose logs migrate_yedegi`; yer aç, §1 başlat |
| CI `guvenlik` kırmızı | Yeni yayımlanan bağımlılık açığı | `pip-audit` çıktısındaki paketi README "Bağımlılık kilidi"ndeki `uv pip compile --upgrade-package` ile yükselt |
