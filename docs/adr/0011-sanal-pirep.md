# 0011 — ADS-B'den sanal PIREP: canlı olay sensörü

- Durum: Kabul edildi (2026-10-01)
- İlgili kod: `fizik/sanal_pirep.py`, `depo/sanal_pirep_deposu.py`, `analiz/sanal_pirep_hatti.py`,
  `dogrulama/sanal_pirep_dogrulama.py`, `POST /api/v1/sanal-pirep/iz`, `GET /api/v1/sanal-pirep`

## Bağlam

Sistemin bütün türbülans bilgisi modelden (ERA5/GFS + TI1 + ML) geliyordu. Türbülansın
en doğrudan sensörü onu o anda yaşayan uçaktır; ADS-B her uçak için barometrik irtifa ve
düşey hız taşır ama kullanılmıyordu. PIREP gönüllüdür, gecikir ve konumu kabadır.

## Karar

- Seyir fazındaki uçağın atanmış seviyesinden (5 dk merkezli kayan medyan) ani irtifa
  sapmaları olay sayılır. Eşiklerin dayanağı:
  - sapma 90 ft = RVSM otopilot irtifa tutma toleransı ±65 ft + ADS-B 25 ft kuantizasyonu;
  - düşey hız tutarlılığı 128 ft/dk = 64 ft/dk kuantizasyonun 2 katı (düşey hız tepkisi
    olmayan irtifa sıçraması transponder hatasıdır);
  - seviye değişimi 300 ft = RVSM toplam düşey hata sınırı; tırmanış/alçalış ve
    kademeli tırmanış seyir sayılmaz;
  - seyir alt sınırı ML ile aynı (FL280).
- Olaylar uzay-zamanda kümelenir (50 km, ±2000 ft, ±60 dk; `bagimsiz_kanit.py`'deki PIREP
  tüpüyle aynı). WebSocket'e yalnızca en az 2 farklı uçağın doğruladığı olaylar gider.
- Girdi iki yoldan gelir: işçideki her uçuş/rota analizinin izi (OpenSky'a ek sorgu yok)
  ve havayolunun kendi beslemesi için `POST /api/v1/sanal-pirep/iz`. OpenSky canlı API'si
  sorgulanmaz.
- Sinyal ML eğitim etiketi olarak KULLANILMAZ. Sapma ham büyüklük olarak raporlanır; EDR
  ya da şiddet sınıfına çevrilmez.
- Doğrulama: ml_ornekleri PIREP'lerinin çevresindeki ADS-B izleriyle POD (sınıf ≥ 1) ve
  POFD (sınıf 0), Wilson %95 aralığıyla. PIREP başına tek OpenSky sorgusu, sonuç Parquet
  önbelleğinde; varsayılan çalıştırma yalnızca önbelleği kullanır.

## Sonuçlar

- Model dışı, gözleme dayalı ikinci bir türbülans kanalı; uyarı gecikmesi
  `bildirim_zamani - bitis` olarak her olayda kayıtlı.
- Eşikler kalibre edilmemiştir. İlk küçük ölçüm (2 Ekim 2026, 16 değerlendirilebilir
  PIREP): POD 1/8 = 0,13 (%95 Wilson 0,02–0,47), POFD 0/8 = 0 (0–0,32). Dedektör
  tutucu; operasyonel güven için daha büyük örneklem gerekir. Eşik bu örneklemle
  ayarlanmadı (16 örnekle ayar aşırı uyum olurdu).
- Yanlış alarm kaynakları: dalga takibi, otopilot mod geçişi, ATC'nin verdiği küçük
  seviye düzeltmeleri. Çoklu uçak doğrulaması bunun için vardır.
- ADS-B'de PIREP'i veren uçak tanınamaz; doğrulamada tüpteki herhangi bir uçağın olayı
  isabet sayılır.
- OpenSky verisi ticari olmayan araştırma içindir; ürünleşmede havayolunun kendi akışı
  ya da lisanslı bir ADS-B sağlayıcısı gerekir (`POST /sanal-pirep/iz` bunun için).

## Değerlendirilen alternatifler

- ADS-B'den EDR türetmek: uçak tipine ve kütleye bağlı tepki fonksiyonu gerektirir; bu
  verilerle uydurma katsayı olurdu. Reddedildi.
- OpenSky canlı REST API'sini periyodik taramak: kredi/ban riski ve lisans; reddedildi.
- Tek uçak olaylarını da yayınlamak: yanlış alarm yükü; eşik `SANAL_PIREP_BILDIRIM_MIN_UCAK`
  ile ayarlanabilir bırakıldı.
