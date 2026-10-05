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
- Denetimsiz karşılaştırma tabanı (`turbulans-anomali-tabani`, 2 Ekim 2026; aynı 16
  PIREP, aynı tüp, önbellekten, eşit alarm bütçesi = kuralın işaretlediği seyir
  noktası oranı %0,12): kural POD 1/8, POFD 0/8 (Peirce +0,13); Isolation Forest POD
  2/8, POFD 3/8 (−0,13); LOF POD 5/8, POFD 5/8 (0). Denetimsiz yöntemler daha çok
  alarm verse de türbülans bildirilen ve bildirilmeyen PIREP'leri ayırt etmedi
  (POD ≈ POFD); kural daha seçici. Aralıklar geniş ve çakışıyor, ön bulgudur.
  Denetimsiz işaretler etiket olarak kullanılmaz.
- LOF düzeltmesi (5 Ekim 2026): gerçek veride seyir noktalarının %68'i ADS-B
  kuantizasyonu (25 ft, 64 ft/dk) yüzünden birebir aynı özellik vektörüydü (en büyük
  küme 17.034 nokta). LOF "Duplicate values" uyarısı verdi, skorlar ~1e11'e çıktı ve
  alarm kümesi komşu sayısına bağlıydı (k=20 ile k=400 arasında 79 alarmın 4'ü ortak).
  Yukarıdaki LOF satırı bu yüzden geçersizdir. Özellikler artık kuantizasyon aralığı
  içinde düzgün titreşimle (dither) açılıyor; uyarı kalktı. Yeniden ölçüm (aynı 16
  PIREP, tohum 0–3): LOF POD 3–4/8, POFD 4–5/8 (Peirce −0,25…0); Isolation Forest
  POD 2–4/8, POFD 3–4/8 (−0,13…+0,13); kural değişmedi (1/8, 0/8). Sonuç aynı:
  denetimsiz yöntemler ayırt edici değil.
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
- Denetimsiz anomali tespitini (Isolation Forest/LOF; fikir debjit450/skywatch-live)
  dedektör yapmak: doğrulanmış referansı yok ve ilk karşılaştırmada ayırt edicilik
  göstermedi; yalnızca karşılaştırma tabanı olarak tutuldu.
