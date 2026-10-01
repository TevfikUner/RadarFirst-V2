# 0006 — Yerel testler için ayrı PostgreSQL veritabanı

- Durum: Kabul edildi (2026-10-01)
- İlgili kod: `tests/conftest.py`

## Bağlam

Yerel testler geliştirme veritabanını kullanırken, çalışan Docker işçisi testlerin
kuyruğa eklediği görevleri alıp gerçek dış servislere gidebiliyor, test temizliği
ise geliştirme verisine (örn. günlük CDS kota sayacı) dokunabiliyordu.

## Karar

Yerelde testler otomatik olarak `<POSTGRES_DB>-test` veritabanına bağlanır (ad
`POSTGRES_TEST_DB` ile değiştirilebilir). CI kendi geçici veritabanını kullanır.

## Sonuçlar

- İşçiyi durdurmadan test çalıştırılabilir; geliştirme verisi kirlenmez.
- Şema Alembic migration'larıyla kurulduğu için migration hataları testte yakalanır.

## Değerlendirilen alternatifler

- SQLite: JSONB, GiST ve `ON CONFLICT` PostgreSQL'e özgü; reddedildi.
- Ayrı Docker konteyneri: mümkün ama aynı sunucuda ayrı veritabanı yeterli.
