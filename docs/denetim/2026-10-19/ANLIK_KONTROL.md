# Anlık kontrol: şimdi yapılabilecek eksik ve hatalar

19 Ekim 2026 akşamı, master `facd1e0`. İleri tarihli işler (B-3 indirmesi, 25 Ekim `docker save`,
AIRAC, 5 Kasım video, §10 değerlendirmesi) bu listede yok.

**Bakılanlar:** CI son çalışmalar, `/saglik?derin=true`, son 24 saatin api/worker/yedek günlükleri,
`veri_kaynagi_durumlari` ve `sigmetler` (salt okuma), `pip-audit` (üç bağımlılık dosyası), tam test
takımı uyarılar açık (1.106 geçti, 61 uyarı), `docker stats`, `URETIM_HAZIRLIK.md` ve
`YAPILACAKLAR.md` açık maddeleri.

## Hatalar

| No | Bulgu | Önem | Kanıt | Çözüm |
|---|---|---|---|---|
| H-1 | CI `guvenlik` işi kırmızı: `requirements-era5.lock` içindeki aiohttp 3.14.3'te 3 yeni açık (GHSA-5wr8-gcqf-gqf3, GHSA-2g87-pp6c-29x5, GHSA-494j-54xm-rwp3), düzeltme 3.14.4 | Yüksek | CI #104 ve #105; yerel `pip-audit` aynı sonuç. Ana kilit ve dev bağımlılıkları temiz | `uv pip compile ... --upgrade-package aiohttp` (README "Bağımlılık kilidi"), sonra `docker compose build api worker` |
| H-2 | YAPILACAKLAR'da kapanmış iki madde hâlâ `[ ]`: beyan sayımları ve "komite açık bulguları" | Düşük | `docs/YAPILACAKLAR.md` 57, 66. satırlar | İşaretle, PR'ları yaz |
| H-3 | Testte kapatılmayan dosya (ResourceWarning) | Düşük | `tests/test_hava_yolu_agi.py:428` | `Path.read_text` |

Hata olmayanlar: 15:31–16:19 UTC SIGMET `ConnectError` geçici (uyku/DNS, 17:49'da iki kaynak da
başarılı, 137 aktif SIGMET). `airsigmet: boş akış` tasarım gereği (mevcut kayıtlar korunur).
Tüm sağlık kontrolleri `tamam`, uyarı yok. Diğer test uyarıları yerel venv'deki numpy 2.5/xarray
uyumundan; imajdaki sürümlerde yok.

## Eksikler (URETIM_HAZIRLIK'ta "ONAY: Hayır" olanlar; tarihe bağlı değil)

| No | Eksik | Efor | Not |
|---|---|---|---|
| P1-4 | Actions ve `postgres:16` etiketle; Dependabot yok | S | Dependabot H-1 gibi açıkları PR olarak getirir |
| S-2 | Sonuçta commit kimliği yok | S | `ARG GIT_SHA` → `uretim_bilgisi.commit` |
| P1-8 + S-5 | Esri karoları gömülü, kapatma bayrağı yok; ağsız prova Esri'ye gidiyor | S | `ALTLIK_KATMANI=dogal\|esri` |
| P1-7 | WS bileti tek kullanımlığı süreç içi (`WEB_CONCURRENCY>1`'de tekrar kullanılabilir) | S | Kullanılmış imza PostgreSQL'de (TTL 60 sn) |
| P1-2 | Migration API açılışında, öncesinde yedek yok | S | `migrate` servisi: `pg_dump` → `alembic upgrade`; önce `-test` DB'de |
| S-8 | Sunum yedeği otomasyonu yok | S | 25 Ekim `docker save` öncesi işe yarar |
| S-9 | Varsayılan hız sınırlarıyla tek IP'den eşzamanlı prova yok | S | Tablet/NAT senaryosu |
| P1-1 | Kaynak sınırları yok | S | Ölçüm 19 Ekim: api 197 MiB, worker 177 MiB, db 96 MiB (boşta); gece işi tepe değeri ölçülmeli |
| S-3 | Simülasyonda senaryo seçici yok | M | |
| S-4 | Fail-safe durumları (ÖNERİ YOK, SIGMET bayat, devre kesici) simülasyonda gösterilemiyor | M | Gerçek arşiv yoksa SENTETİK etiketli |
| P1-10 | İşletim kılavuzu yok | M | Prosedürler README'ye dağınık |

Onay gerektirenler (bu listede uygulanmaz): P1-3 izleme yığını (bildirim kanalı), Y-6
`docker builder prune` (geri alınamaz), `Turbulence-db-dondurma` DROP.
