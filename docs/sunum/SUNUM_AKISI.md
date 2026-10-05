# Sunum Akışı (15 dakika)

Akış: problem → yaklaşım → mimari → canlı demo → sonuçlar (dürüst sınırlamalarla)
→ gelecek çalışma. Sayılar depodaki ölçüm belgelerinden alınmıştır; her slaytın
kaynağı yanında yazılı. `[ … ]` ile işaretli yerler sunumdan önce doldurulacak
(kaynaklı literatür bilgisi ya da henüz ölçülmemiş sonuç); uydurma değer
yazılmamalıdır.

| # | Slayt | Süre | Kaynak |
|---|---|---|---|
| 1 | Başlık | 0:20 | — |
| 2 | Problem | 1:20 | E3 literatürü |
| 3 | Mevcut çözümler ve boşluk | 1:00 | E3 literatürü |
| 4 | Yaklaşım | 1:30 | README, ADR'ler |
| 5 | Mimari | 1:30 | `docs/mimari.md` |
| 6 | Canlı demo | 6:00 | `DEMO_SENARYOSU.md` |
| 7 | Sonuçlar: performans | 0:45 | `docs/PERFORMANS_RAPORU.md` |
| 8 | Sonuçlar: doğruluk ve ML | 1:00 | `docs/SISTEM_KARTI.md` §6, ML eğitim kaydı |
| 9 | Sınırlamalar | 0:45 | `docs/SISTEM_KARTI.md` §5 |
| 10 | Gelecek çalışma | 0:30 | Geliştirme planı |
| 11 | Kapanış ve sorular | 0:10 | — |

## 1. Başlık

- Türbülans Radar: gerçek uçuş izleri ve reanaliz verisiyle türbülans riski ve
  kaçınma rotası öneren karar destek sistemi
- Tevfik Uner · Danışman: Arş. Gör. Dr. Fatih Titrek · Bilgisayar Mühendisliği,
  Konya Teknik Üniversitesi · 2026

## 2. Problem

- Seyir irtifasındaki türbülans çoğu zaman görünmez (açık hava türbülansı); pilot
  raporu (PIREP) gönüllü, gecikmeli ve konumu kabadır.
- ABD'de 2009–2018 arasında Part 121 (tarifeli hava yolu) kazalarının üçte
  birinden fazlası türbülansla ilgiliydi; çoğunda uçak hasar görmedi ama en az
  bir kişi ağır yaralandı, en sık yaralananlar kabin ekibiydi (NTSB, Safety
  Research Report NTSB/SS-21/01, 10 Ağustos 2021).
- Dürüst kapsam notu: aynı rapora göre bu kazaların yaklaşık yarısı alçalma ve
  yaklaşmada, %60'ı 20.000 ft altında oldu. Sistem yalnızca seyir safhasını
  (FL280–FL420) kapsar; bu kazaların hepsini hedeflemez.
- Soru: Mevcut açık veriyle, bir dispeçerin rota kararına girdi olacak, ölçülebilir
  ve dürüst bir risk göstergesi üretilebilir mi?

## 3. Mevcut çözümler ve boşluk

- GTG (Graphical Turbulence Guidance), WAFS türbülans ürünleri, Ellrod–Knapp TI1:
  [kısa özet ve atıflar, E3]
- Bu projenin farkı (E3'teki "Katkılar" bölümüyle aynı dil):
  - Gerçek ADS-B izi + barometrik irtifayla seviye seçimi + ERA5 eşleştirmesi tek
    hatta; risk, rota optimizasyonuna (A*) sert ve yumuşak kısıt olarak giriyor.
  - Seyir irtifası PIREP veri hattı ve PIREP irtifa hatasının (FL feet) tespiti ve
    düzeltilmesi.
  - Kapılı model aktivasyonu (TI1 referansı + aktif model), konformal "belirsiz" durumu.
  - ADS-B'den gözleme dayalı sanal PIREP kanalı (M6).

## 4. Yaklaşım

Dört katman, her biri ayrı doğrulanır:

1. **Veri:** OpenSky (uçuş izi), Copernicus ERA5 (CDS birincil, ARCO yedek), NOAA GFS
   (canlı), AWC SIGMET, IEM PIREP (etiket).
2. **Fizik:** Ellrod TI1, Richardson sayısı; nokta, uçağın barometrik irtifasına
   karşılık gelen basınç seviyesinde değerlendirilir (ADR 0005).
3. **Öğrenme:** Seyir irtifası PIREP'leriyle gece kendiliğinden büyüyen veri seti; gün
   gruplu çapraz doğrulama, zamansal holdout, bootstrap güven aralıkları, konformal
   belirsizlik (ADR 0003, 0004, 0010).
4. **Karar:** A* rota: önce SIGMET ve kısıtlı sahaya girmemek (sert), sonra riskli
   TI1'den kaçınmak (yumuşak), sonra yakıt/süre. Kaçınacak risk yoksa rota büyük
   daireyle aynı kalır.

## 5. Mimari

- `docs/mimari.md` konteyner diyagramı: API (FastAPI), işçi, PostgreSQL (kuyruk,
  dağıtık kilit, LISTEN/NOTIFY), web önyüzleri (MapLibre, CesiumJS), dış kaynaklar.
- Üç cümle: uzun işler PostgreSQL kuyruğunda (`FOR UPDATE SKIP LOCKED`); gece ML işi
  API'nin kendi zamanlayıcısıyla çalışıyor; dış servislere kilit ve günlük tavan.
- 11 mimari karar kaydı (`docs/adr/`).

## 6. Canlı demo

`DEMO_SENARYOSU.md` §2. Ağsız; olmazsa yedek video.

## 7. Sonuçlar: performans

Dizüstü (i7-13700H, WSL2), demo verisi, 1 Ekim 2026:

| Ölçüt | Hedef | Ölçülen |
|---|---|---|
| Tek uçuş analizi (1614 nokta) | ≤ 10 sn | 0,23 sn |
| Nokta tahmini p95, 16 eşzamanlı | ≤ 1 sn | 0,30 sn (4 süreç) |
| Rota (A*) p95, 16 eşzamanlı | ≤ 5 sn | 3,95 sn (4 süreç); 5,45 sn (1 süreç) ✘ |
| İşçi görev hızı | ≥ 10/dk | 467/dk |
| Hata oranı | %0 | %0 |

Bulgu: tek süreçte GIL darboğazı; 4 süreçle aynı donanımda verim ~3 kat.

## 8. Sonuçlar: doğruluk ve ML

- **TI1'in bağımsız becerisi sınırlı:** Seyir irtifasındaki 6218 PIREP'te ROC-AUC 0,67
  (holdout 0,71); config eşiğinde yakalama 0,49, yanlış alarm 0,16. Gerçek bir uçuşta (PUE502) aktif
  TURB SIGMET'in işaret ettiği türbülansı TI1 yakalamadı. Bu yüzden güvenlik garantisi
  SIGMET sert kısıtından gelir; TI1 yumuşak göstergedir.
- **Backtest (15 Ocak 2019):** Riskli nokta oranı gerçek uçuşlarda 0,28, önerilen
  rotalarda 0,00; büyük daireye göre +2–5 dk. Ölçüm döngüseldir (A* TI1'i düşürür,
  başarı TI1 ile ölçülür); bunu açıkça söyleyin.
- **ML:** [İlk gerçek eğitimden sonra doldurulacak — 60 eşleşmiş gün eşiği: F1, ROC-AUC
  ve %95 güven aralıkları (gün blok bootstrap), TI1'e göre eşleştirilmiş AUC farkı ve
  p-değeri, zamansal holdout'ta konformal kapsama (hedef %90)]. Kaynak:
  `GET /api/v1/turbulans/model-bilgisi`.
- **Sanal PIREP (M6):** İlk küçük ölçüm (2 Ekim 2026, 16 değerlendirilebilir PIREP):
  POD 1/8 = 0,13 (%95 Wilson 0,02–0,47), POFD 0/8 = 0 (0–0,32). Dedektör tutucu;
  örneklem küçük, aralıklar geniş. Eşik bu örneklemle ayarlanmadı.

## 9. Sınırlamalar

- Çıktılar sertifikalı EDR değildir; sistem karar destek aracıdır, operasyonel kararın
  tek dayanağı değildir.
- Etiket PIREP'tir (öznel, gecikmeli); nesnel EDR etiketi için NOAA MADIS başvurusu
  yapıldı (M1).
- OpenSky verisi ticari olmayan araştırma içindir; ürünleşmede havayolunun kendi
  ADS-B akışı gerekir (`POST /analiz/rota`, `POST /sanal-pirep/iz` bunun için).
- Örnek kısıtlı sahalar ülke sınırından türetilmiştir, resmi AIP/NOTAM değildir.

## 10. Gelecek çalışma

Geliştirme planındaki sırayla: M1 nesnel EDR etiketi (MADIS) → M3 tahmin modu ve
WAFS kıyası → M6 sanal PIREP POD/POFD ölçümü → M4 uçak tipine duyarlı risk → M7
OGC API – EDR ve IWXXM.

## 11. Kapanış

- Depo, demo komutu ve belge bağlantıları; "Sorularınız?"

## Yedek slaytlar

- Test ve CI: 753 test (birim, PostgreSQL, gerçek veri, Playwright); CI'da 5 iş
  (lint, güvenlik, test, tarayıcı, docker); sır taraması ve SBOM.
- Veri lisansları ve sağlayıcı sınırları (`docs/VERI_KAYNAKLARI_VE_LISANSLAR.md`).
- Konformal yöntemin özeti (ADR 0010) ve PIREP irtifa hatasının hikâyesi.
