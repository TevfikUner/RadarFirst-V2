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
| 10 | Gelecek çalışma | 0:30 | Geliştirme planı, ürün ekibi raporu |
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

- Ellrod ve Knapp (1992) TI1; GTG çok teşhisli birleşimi (Sharman vd., 2006);
  log-normal EDR eşlemesi (Sharman ve Pearson, 2017); WAFS ızgara CAT ürünleri (Gill,
  2014). Hepsi NWP alanı üretir, yerinde EDR ya da PIREP'le doğrulanır.
- ML ile EDR tahmini (Muñoz-Esparza vd., 2020) kapalı yerinde EDR'ye dayanır; ADS-B'den
  EDR (Kopeć vd., 2016) araştırma uçağı ivmeölçeriyle doğrulanır; A* ile CAT'ten kaçınma
  (Cheung, 2018) tek örnek olaydır. Künyeler ve tablo: `docs/rapor/ILGILI_CALISMALAR.md` §9.
- Bu projenin farkı, yalnız çekirdek (E3'teki "Katkılar" bölümüyle aynı dil; "ilk"
  denmez):
  - K1: Gerçek ADS-B izi + barometrik irtifayla seviye seçimi + ERA5 eşleştirmesi.
  - K2: Seyir irtifası PIREP etiket hattı; IEM FL feet hatasının tespiti (yan katkı).
  - K6: TI1'in sınırı bağımsız etiketle (PIREP, MADIS EDR) ölçüldü ve ürüne yansıdı.
  - K7: Bu sınır rota kararının yapısına taşındı: SIGMET sert, TI1 yumuşak kısıt (A*).
- Mühendislik ekleri (kapılı ML, konformal "belirsiz", sanal PIREP, contrail, IWXXM,
  n8n, MCP) ana slaytlarda anılmaz; yedek slaytlardadır.

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

Bu bölümdeki her sayı `docs/sonuclar/2026-10-18/SAYILAR.md` nihai paketinden alındı (18 Ekim
veri dondurması). Aralıklar gün bazlı blok bootstrap %95 GA'dır.

- **TI1'in bağımsız becerisi sınırlı:** Seyir irtifasındaki 15.940 PIREP'te (163 gün) ROC-AUC
  0,673 [0,661–0,684]. Altın test günlerinde 0,675 [0,641–0,706]. Risk eşiğinde (7e-7)
  yakalama 0,501, yanlış alarm 0,248. Gerçek bir uçuşta (PUE502, 26 Eylül, tarihçe) aktif
  TURB SIGMET'in işaret ettiği türbülansı TI1 yakalamadı. Bu yüzden güvenlik garantisi
  SIGMET sert kısıtından gelir; TI1 yumuşak göstergedir.
- **Eşik veriden seçildi:** Eğitim günlerinde Peirce'i en büyüten TI1 eşiği 4,96e-7
  (altın günlerde POD 0,622, POFD 0,373). Risk eşiği, bunun bir standart hatası içindeki
  en tutucu eşik: 8 Ekim'de 7e-7 seçildi (1-SE kuralı; yanlış alarm daha az). Nihai pakette
  kural 7,39e-7 verdi; 7e-7 bandın içinde kaldığı için değişmedi. Eski 8e-7 bandın dışındaydı.
- **Yalnız CAT:** CB/TS/TCU/MTN WAVE/LLWS geçen raporlar dışlanınca altın günlerde TI1
  0,670 [0,634–0,708]; sonuç değişmiyor.
- **Backtest (ERA5, THY322):** Riskli nokta oranı (gerçek / büyük daire / A*): 1 Ocak 2019
  0,00 / 0,20 / 0,00; 15 Ocak 2019 0,24 / 0,39 / 0,02. Ölçüm döngüseldir (A* TI1'i
  düşürür, başarı TI1 ile ölçülür); bunu açıkça söyleyin.
- **ML (nihai):** Protokol modeli (1-SE kuralı bu kez Random Forest'ı seçti; GB ile berabere)
  altın test günlerinde (16 gün, 1.583 PIREP) ROC-AUC 0,708 [0,677–0,738]. TI1'e göre fark
  +0,033 [+0,018; +0,049], p < 0,001: kapı geçildi. Jüri "neden RF?" derse: CV'de RF ile GB
  berabere (0,0001 fark); ilk, sırasız üretimde GB seçilmişti (+0,036). Sıralama düzeltilince
  paket yedekten birebir yeniden üretilebilir oldu; iki durumda da model TI1'i geçiyor. 7 Ekim ön paketinde (80 gün) LR geçememişti
  (+0,008); bunu da söyleyin, sonuç veri hacmine duyarlı. Birleşik EDR TI1'i küçük ama
  anlamlı farkla geçiyor: 0,688, fark +0,013 [+0,007; +0,020]. F1 0,645; konformal kapsama
  0,907 (hedef 0,90), ama örneklerin %60'ı "belirsiz" kalıyor.
- **Çalışan model farklı:** Canlıda 9 Ekim'de kapıdan geçen Random Forest aktif (altın
  günlerde 0,707, TI1'e göre +0,033). Dondurma raporunda yeni GB aday onu geçemedi (+0,003
  [−0,001; +0,008]) ve saklandı. Jüri "raporlanan ile çalışan model aynı mı?" diye sorarsa:
  hayır, ikisi de aynı altın günlerde ölçüldü ve ikisi de TI1'i geçiyor.
- **Nesnel etiket (MADIS):** 45.075 ölçüm, 14 gün, fiilen yalnız hafif sınıf (taban oran
  0,029; orta ve üstü 1 ölçüm). ROC-AUC model 0,775 [0,734–0,814], TI1 0,722 [0,669–0,779];
  PR-AUC 0,126 ve 0,105. Model olasılığı ortalama 0,505; PIREP yanlılığı nedeniyle mutlak
  sıklık değildir. Seçim yanlılığı var: örnekler PIREP pencerelerinden geliyor.
- **Sanal PIREP (M6):** İlk küçük ölçüm (2 Ekim 2026, 16 değerlendirilebilir PIREP):
  POD 1/8 = 0,13 (%95 Wilson 0,02–0,47), POFD 0/8 = 0 (0–0,32). Dedektör tutucu;
  örneklem küçük, aralıklar geniş. Eşik bu örneklemle ayarlanmadı.

## 9. Sınırlamalar

- Çıktılar sertifikalı EDR değildir; sistem karar destek aracıdır, operasyonel kararın
  tek dayanağı değildir.
- Etiket PIREP'tir (öznel, gecikmeli). Nesnel etiket olarak NOAA MADIS'in herkese açık
  uçak EDR arşivi kullanılır (ADR 0012); 6 gün, yalnız hafif sınıf, ön sonuç.
- OpenSky verisi ticari olmayan araştırma içindir; ürünleşmede havayolunun kendi
  ADS-B akışı gerekir (`POST /analiz/rota`, `POST /sanal-pirep/iz` bunun için).
- Örnek kısıtlı sahalar ülke sınırından türetilmiştir, resmi AIP/NOTAM değildir.

## 10. Gelecek çalışma

Ürün yönü: önce ölçmek, sonra tahmin etmek. Doğrulama karnesi olmayan bir tahmin
ürünü eklenmez.

- **F1 Doğrulama karnesi:** kaynak başına (PIREP, MADIS EDR) dönemsel ROC-AUC, PR-AUC,
  POD/POFD. Bugünkü sonuç paketi (`docs/sonuclar/`) ABD doğrulama karnesinin ilk
  örneğidir: 18 Ekim nihai paketi (`docs/sonuclar/2026-10-18/`), PIREP 16 altın gün ve MADIS
  14 gün. Sonraki adım aynı karneyi dondurmadan sonra toplanan yeni günlerde üretmek.
- **F2 GEFS olasılığı:** topluluk (ensemble) üyelerinden rota koridorunda risk olasılığı;
  31 üye, 0,5°; bir tahmin adımı ~43 MB indirme, Türkiye kesiti ~0,6 MB (15 Ekim ölçümü,
  `docs/fizibilite/GEFS_FIZIBILITE.md`).
- **F3 Kabin penceresi:** öneri bugün ±15 dk parametrik pencere verir (kalibre edilmedi);
  pay ölçülen olay zamanlarıyla kalibre edilecek.
- **F4 Türkiye etiket havuzu:** MADIS'te bölge için yeterli ölçüm yok; Avrupa/Türkiye
  için nesnel etiket kaynağı gerekir. Uçak EDR'si WMO-IATA kısıtlı; aday yollar MGM ve
  IATA Turbulence Aware (`docs/fizibilite/TURKIYE_ETIKET_KAYNAKLARI.md`).
- Geliştirme planından kalanlar: M3 tahmin modu ve WAFS kıyası, M4 uçak tipine duyarlı
  risk, M7 OGC API – EDR.

Konuşmacı notu: F1–F4 ürün yönü maddeleridir, slayt 8'deki F1 skoruyla karıştırmayın.
M1 (MADIS), M6 (sanal PIREP) ve IWXXM dışa aktarımı bitti; slayt 8 ve yedek slaytlarda.

## 11. Kapanış

- Depo, demo komutu ve belge bağlantıları; "Sorularınız?"

## Yedek slaytlar

Mühendislik ekleri (çekirdek K1, K2, K6, K7 değil; soru gelirse açılır, yeni özellik
eklenmez):

- Kapılı model aktivasyonu ve konformal "belirsiz" durumu (K4, K5; ADR 0004, 0010).
- Sanal PIREP: ADS-B'den gözleme dayalı olay kanalı (K8, M6).
- İz bulutu (contrail) duyarlılığı, IWXXM dışa aktarımı, n8n otomasyonu, MCP sunucusu,
  3B uçuş simülasyonu.
- İşletim: kuyruk, dağıtık kilit, yedek, sağlayıcı sınırları (K9).

Diğer:

- Test ve CI: 1.157 test (28 Ekim 2026; birim, PostgreSQL, gerçek veri, Playwright); CI'da 6 iş
  (lint, güvenlik, test [Python 3.12 ve 3.14], tarayıcı, docker, demo); sır taraması ve SBOM.
- Veri lisansları ve sağlayıcı sınırları (`docs/VERI_KAYNAKLARI_VE_LISANSLAR.md`).
- Konformal yöntemin özeti (ADR 0010) ve PIREP irtifa hatasının hikâyesi.
