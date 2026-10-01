# 0009 — Kimlik bilgisi gerektirmeyen depo içi demo paketi

- Durum: Kabul edildi (2026-10-01)
- İlgili dosyalar: `demo/`, `.env.demo`, `cli/demo.py`, `docker-compose.yml` (`demo` profili)

## Bağlam

Temiz bir klonda veri, model ve kimlik bilgisi yoktu; sistemi başka biri
çalıştıramıyor, sonuçlar bağımsız olarak doğrulanamıyordu. Canlı sunumda ağ ya da
kimlik sorunu demoyu bozabilir.

## Karar

THY322 (2019-01-15) için gerçek rota (OpenSky Parquet, ~60 KB) ve onu kapsayan ERA5
dilimi (~230 KB) depoya konur. `DEMO_VERI_KLASORU` küp taramasına ve rota
önbelleğine salt okunur yedek olarak eklenir. `turbulans-demo` analizi çevrimdışı
çalıştırır; `docker compose --profile demo up` yığını kurup demo uçuşunu
veritabanına yazar.

## Sonuçlar

- Projeyi hiç görmemiş biri dakikalar içinde 3B haritayı görebilir (temiz kopyada denendi).
- Paket küçük olduğu için sürüm dosyası (release asset) yerine depoda tutulur.
- Demo ML modeli, PIREP ve SIGMET içermez; bunlar gerçek kurulum gerektirir.

## Değerlendirilen alternatifler

- Sürüm dosyası olarak yayınlamak: ek indirme adımı ve ağ gerektirir; paket bunu gerektirecek kadar büyük değil.
- Sentetik veri: gerçek davranışı göstermez; reddedildi.
