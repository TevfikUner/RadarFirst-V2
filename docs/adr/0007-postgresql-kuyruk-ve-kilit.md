# 0007 — Görev kuyruğu ve dağıtık kilit PostgreSQL'de

- Durum: Kabul edildi
- İlgili kod: `depo/gorev_deposu.py`, `depo/dagitik_kilit.py`, `isci/gorev_iscisi.py`

## Bağlam

Uzun işler (analiz, backtest, ML veri hattı) API sürecinden ayrılmalı, işçi
yeniden başlasa da kaybolmamalı ve birden fazla işçi aynı ERA5 dilimini iki kez
indirmemeli.

## Karar

- Kuyruk `analiz_gorevleri` tablosudur; işçiler `FOR UPDATE SKIP LOCKED` ile görev alır
  ve kalp atışı gönderir. Kalp atışı kesilen görev `GOREV_MAKS_DENEME`'ye kadar
  yeniden kuyruğa girer.
- Süreçler arası kilit PostgreSQL oturum düzeyinde advisory lock'tur.
- Canlı uyarılar işçiden API'ye `NOTIFY`/`LISTEN` ile taşınır.

## Sonuçlar

- Ek altyapı (Redis, RabbitMQ) yok; tek bağımlılık zaten var olan PostgreSQL.
- Görev geçmişi sorgulanabilir (`/analiz/durum`, `/ml/durum`).
- Çok yüksek görev hızında bir mesaj kuyruğu kadar ölçeklenmez; bu sistemin yükünde gerekmez.

## Değerlendirilen alternatifler

- Celery + Redis: ek servis ve işletim yükü; reddedildi.
