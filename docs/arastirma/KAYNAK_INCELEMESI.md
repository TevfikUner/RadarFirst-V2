# Kaynak İncelemesi: GitHub "turbulence" listesi ve makale klasörü

16 Ekim 2026. Kapsam: GitHub yıldız listesi `TevfikUner/lists/turbulence` (23 depo) ve
`Desktop/BİTİRME PROJESİ/Makaleler` klasörü (23 PDF + `Silinecekler/` içinde 5 PDF).
Amaç, bu kaynaklardan Türbülans Radar'a uygulanabilir fikirleri çıkarıp sıralamak.

Okuma kuralları:
- Depolarda README, dosya ağacı ve çekirdek kaynak dosyalar `gh api` ile okundu. Hiçbir depo
  çalıştırılmadı. "Çalışıyor" ya da "doğru" denmiyorsa yalnızca README'de yazan aktarılmıştır.
- Makalelerde özet, yöntem ve sonuç bölümleri ile sayı içeren tablolar okundu. Sayılar
  makalede yazdığı gibi aktarıldı.
- **(tahmin)** etiketi kaynağın açıkça söylemediği, benim çıkarımım olan yerleri gösterir.
- Bu belge yalnızca öneri listesidir. Hiçbir öneri koda uygulanmadı. Sistem sertifikalı EDR
  üretmez; operasyonel karar aracı değil, karar destek aracıdır. Öneriler bu çerçeveyi
  değiştirmez.
- 18 Ekim ML veri dondurması nedeniyle ML etiketini, özelliklerini ya da değerlendirmesini
  değiştiren öneriler, dondurmadan **sonra** ve `docs/deney_protokolu.md`'ye önceden yazılarak
  yapılmalıdır. Bunlar listede "dondurma sonrası" diye işaretlidir.

---

## 0. Yönetici özeti

İki kaynak birlikte üç ana mesaj veriyor:

1. **TI1 eşiği veri kaynağına bağlıdır.** Ellrod ve Knapp (1992) Tablo 1'de aynı şiddet
   için eşik, modelden modele 2–3 kat değişiyor. Foudad vd. (2024) eşiğin yatay
   çözünürlüğe "çok bağlı" olduğunu, Kim ve Kim (2026) ise eşiği her basınç seviyesi için
   ayrı yüzdelikle tanımladığını yazıyor. Bizde ERA5'ten seçilen 7e-7 eşiği canlı GFS'te de
   aynen kullanılıyor (`config.TI1_ESIK_ORTA_SIDDETLI`).
2. **Literatürdeki yüksek AUC'lerin çoğu rastgele bölmeyle elde edilmiş.** Örnekler:
   Gökdeniz ve Ülkü (2026) AUC 0,904, rastgele 70/30. Gu ve Wang (2024) AUC 0,86, rastgele
   80/20. Bizim gün gruplu sonuçlarımız (ön paket: TI1 0,673–0,706, birleşik EDR 0,687–0,692)
   bunlarla doğrudan kıyaslanamaz. Bu,
   savunmada en çok sorulacak noktadır.
3. **Olasılıksal tahmin topluluk (ensemble) ister, ama GEFS şart değil.** Kim vd. (2015),
   aynı geçerlilik zamanına düşen ardışık model koşularını birleştirip (zaman gecikmeli
   topluluk) rota planlamada %10 olasılık eşiği kullanmış. Bizim canlı GFS'imiz zaten
   6 saatte bir koşuyor.

### Hemen uygulanabilecek ilk 3 öneri

Seçim ölçütü: düşük efor ve 18 Ekim dondurmasına dokunmaması. Sıralı listede (§3) etkisi
daha yüksek olan 2 ve 3 numaralı öneriler orta efor ve veri gerektirdiği için buraya
alınmadı.

| # | Öneri | Neden şimdi | Süre (tahmin) |
|---|---|---|---|
| 1 | **Literatür karşılaştırma tablosuna "bölme yöntemi" sütunu** (§3, Fikir 1) | Yalnız belge değişikliği. Jürinin "AUC'niz neden düşük?" sorusunu önceden yanıtlar. | 1–2 sa |
| 2 | **Rota ayrıklaştırma yakınsama çalışması** (§3, Fikir 5) | ML'e dokunmaz. Mevcut `turbulans-performans rota` ile yapılır. "Neden 41 ara nokta, 20 km ızgara?" sorusuna sayıyla yanıt verir. | 2–4 sa |
| 3 | **Yakıt tasarrufu için kütle belirsizlik bandı** (§3, Fikir 6) | Tek sabit kütle oranı (0,85) yerine %70–90 MTOW aralığı verilir. Küçük kod değişikliğidir, bilimsel dürüstlüğü artırır. | 2–3 sa |

Dondurmadan hemen sonra sırada: Fikir 2 (kaynağa özgü eşik), Fikir 4 (tabakalı
doğrulama), Fikir 3 (zaman gecikmeli GFS topluluğu).

---

## 1. Aşama: GitHub depoları (23)

Liste GraphQL ile alındı (`user.lists`, 23 öğe). Lisanslar GitHub meta verisinden alındı.

### 1.1 Türbülans tahmini iddia eden depolar

#### R1. fDg21G/ASTRIA-CAT (lisans yok, ⭐3)
- **Amaç:** MEMS basınç sensörleri ve uç yapay zekâ (edge AI) ile uçakta CAT'i önceden
  sezmek.
- **Veri/algoritma:** Sentetik basınç sinyali (Kelvin–Helmholtz dalgası + gürültü), Cp ve Ri
  boyutsuz özellikleri, 1D-CNN / ST-GNN + TCN.
- **Mimari:** PyTorch, Apache TVM/TFLM ile nicemleme (INT8), ARM/STM32 hedef.
- **Güçlü/zayıf:** Fizik tabanlı boyutsuzlaştırma fikri ilginç. Ancak veri tamamen
  sentetik, `data/sample_dataset.csv` yalnız başlık satırından oluşuyor ve `core_cpp/`
  boş (`.gitkeep`). README "ST-GNN + TCN, ARM Cortex-A, TVM" derken `model_performance.txt`
  "1D-CNN, Arduino Nicla Vision, TFLM, %88,5 doğruluk" diyor; iki belge çelişiyor.
- **Projeyle ilgisi:** Karşı örnek. Gerçek etiket olmadan raporlanan doğruluk anlamsızdır.
  Uçak üstü sensör kapsamımız dışında.

#### R2. animeshghiloria/Flymply (lisans yok, ⭐2)
- **Amaç:** Telemetri pencerelerinde türbülans anomalisi + Gemma-2B ile kokpit uyarı metni.
- **Veri/algoritma:** 6 değişkenli, 50 adımlık pencere üzerinde LSTM otokodlayıcı.
  Yeniden kurma hatasının eğitim dağılımındaki yüzdeliği "olasılık" sayılıyor. Gemma
  QLoRA ince ayarı sentetik veriyle yapılmış.
- **Mimari:** Flask + React/Vite, localStorage önbelleği.
- **Güçlü/zayıf:** Uyarı metnini iki satırla sınırlaması iyi bir kokpit tasarımı.
  Türbülans etiketi ve doğrulama yok; "olasılık" kalibre değil.
- **Projeyle ilgisi:** `ILGILI_CALISMALAR.md` §8'de zaten karşı örnek olarak yer alıyor.
  Denetimsiz anomali bizde ölçüldü ve ayırt edici çıkmadı.

#### R3. yijia-xu/flight-turbulence-ai (lisans yok, ⭐1)
- **Amaç:** Uçuş kodu ve tarihten yolcuya türbülans raporu.
- **Veri/algoritma:** AviationStack + OpenSky rota, Open-Meteo rüzgârı, NOAA PIREP.
  `app/tools/turbulence.py` kural tabanlı puan veriyor: 250–300 hPa hız farkı >40 →
  +4, rüzgâr >150 → +3, sıcaklık farkı >15 → +2 (birimler belirtilmemiş). LangGraph
  ajanları ve sözlük RAG kullanılıyor.
- **Mimari:** FastAPI + PostgreSQL + Streamlit + n8n ile e-posta aboneliği (uçuş öncesi uyarı).
- **Güçlü/zayıf:** Ürün akışı (abonelik, uçuş öncesi uyarı, **kalkış penceresi
  karşılaştırması** `/api/compare?days=7`) iyi tasarlanmış. Türbülans puanı uydurma
  eşiklerle hesaplanıyor ve doğrulanmamış.
- **Projeyle ilgisi:** Kalkış saati penceresi fikri (Fikir 16). Abonelik bizde webhook ile
  kısmen var.

#### R4. debjit450/skywatch-live (MIT, ⭐24)
- **Amaç:** Çok kaynaklı canlı ADS-B gözetimi, uydu takibi ve anomali tespiti.
- **Veri/algoritma:** OpenSky + ADS-B One/Airplanes.live/ADSB.lol/OGN birleşimi, kural +
  Isolation Forest/LOF + isteğe bağlı LSTM, SGP4. Hava sahası katmanı AWC SIGMET + FAA TFR.
- **Mimari:** Django/Channels/Celery/Redis/PostgreSQL/PgBouncer, Prometheus/Grafana/Jaeger,
  React + MapLibre/deck.gl.
- **Güçlü/zayıf:** Kaynak sağlığı, alım denetimi (ingestion audit) ve gözlemlenebilirlik
  olgun. Airplanes.live uç noktalarına bağımlı. Bizim 2 Ekim notumuza göre bu sağlayıcının
  genel API'si 2026-04-29'da kapandı; ilgili istemciler bu yüzden bozuk olabilir (tahmin).
  Türbülansa karşı doğrulama yok.
- **Projeyle ilgisi:** Kaynak sağlığı ve devre kesici bizde zaten var. Yeni fikir çıkmadı.

#### R5. feminaanzil/AeroContrail (MIT, ⭐1)
- **Amaç:** BAE bağlantılı uçuşlarda kalıcı iz bulutu (contrail) duyarlılığı (Ocak 2022).
- **Veri/algoritma:** OpenSky/Zenodo uç noktalarından yeniden kurulan koridorlar, 6 seviyeli
  ERA5, T ≤ −40 °C ve RHi ≥ %100 vekil ölçütü, zamansal holdout ile XGBoost.
- **Bulgular (README):** Duyarlılık oranı %0,913 (300 hPa'da %2,644). Uçuşların %18,07'si
  en az bir duyarlı katmandan geçiyor. XGBoost ROC-AUC 0,9958, PR-AUC 0,5951. Yazar bunları
  "üst sınır vekil tahmin" diye etiketliyor.
- **Güçlü/zayıf:** Sızıntıya duyarlı bölme ve sınırlarını açıkça yazması örnek alınacak
  nitelikte. AUC ile PR-AUC arasındaki büyük fark sınıf dengesizliğini gösteriyor.
- **Projeyle ilgisi:** M9 ölçütü buradan alındı. Fikir 30 (Schmidt–Appleman) bunun bir
  sonraki adımı.

### 1.2 Rota optimizasyonu

#### R6. argilaga15/flight_opt_r_project (lisans yok, ⭐1)
- **Amaç:** Hava yolu ağında yakıt/süre/hava riski için çok amaçlı rota.
- **Veri/algoritma:** PSO (pyswarms), Optuna, NSGA-II (DEAP), Monte Carlo hava belirsizliği.
  Hava yolu ağı AIXM, FAA CIFP ve NATS tablolarından ya da OpenSky izlerinin ızgaraya
  oturtulmasıyla kuruluyor.
- **Güçlü/zayıf:** Veri yükleyici katmanı geniş. Ancak `weather_model.py` rüzgârı analitik
  bir sin/cos fonksiyonundan üretiyor (`30·sin(x/250)`) ve yakıt modeli tek bir yanma
  çarpanından ibaret. Pareto cephesi bu nedenle gerçek hava verisine dayanmıyor.
- **Projeyle ilgisi:** "Monte Carlo hava belirsizliği" fikri gerçek veriyle Fikir 3'e
  dönüşür.

#### R7. hemalii3/Flight-Route-Optimization-System (lisans yok, ⭐1)
- **Amaç:** Havalimanı grafında Dijkstra/A* ile maliyet en aza indirme.
- **Veri/algoritma:** Yakıt + üst uçuş ücreti + hava cezası; NOTAM kapanışı sert kısıt;
  Pareto (maliyet, süre, risk).
- **Mimari:** Java 21, Spring Boot, PostgreSQL, Podman.
- **Güçlü/zayıf:** Bacak bazlı maliyet dökümü veren REST yanıtı iyi. Ağ tohum veriyle
  geliyor ve gerçek hava yok. README'de varsayılan DB şifresi düz metin.
- **Projeyle ilgisi:** Bacak bazlı döküm ve FPL çıktısı fikri (Fikir 13).

#### R8. bogdandanciu/4D-Trajectory-Generation (lisans yok, ⭐18)
- **Amaç:** İki havalimanı arasında A320 performansıyla 4B yörünge görselleştirme.
- **Veri/algoritma:** Ortodrom + mesafeden optimum seyir seviyesi, değişken hız/düşey hız.
- **Mimari:** Saf JS + Google Maps API anahtarı.
- **Güçlü/zayıf:** Eğitim amaçlı ve sade. Rüzgâr ve hava yok.
- **Projeyle ilgisi:** Düşük. OpenAP bu işi bizde zaten yapıyor.

#### R9. junzis/opentop (NOASSERTION, ⭐53)
- **Amaç:** OpenAP tabanlı optimal uçuş yörüngesi.
- **Veri/algoritma:** Doğrudan sıralama (direct collocation) ile doğrusal olmayan optimal
  kontrol (CasADi + IPOPT). Amaçlar: yakıt, süre, maliyet indeksi, GWP/GTP. ERA5 GRIB
  rüzgârı ve **özel 4B ızgara maliyeti** (lon, lat, height, cost, ts → interpolant)
  destekleniyor. Çok uçaklı ayırma (5 NM / 1000 ft) da var.
- **Güçlü/zayıf:** README sınırları açıkça yazıyor ("örneklenmiş kısıt, sürekli yol
  garantisi değil"). Ağır bağımlılıkları var (CasADi/IPOPT). GitHub lisans alanı
  NOASSERTION; kullanmadan önce lisans dosyası okunmalı.
- **Projeyle ilgisi:** A* sonucumuz için bağımsız bir optimal kontrol referansı olabilir
  (Fikir 22). Sun vd. (2023, Makale22) aynı aracı bu amaçla kullanmış.

#### R10. junzis/openap (LGPL-3.0, ⭐170)
- **Amaç:** Açık uçak performans modeli: itki, sürükleme, yakıt (Acropole polinomları),
  emisyon (ICAO), WRAP kinematiği, uçuş safhası (`FlightPhase`), yörünge üreteci.
- **Projeyle ilgisi:** Bizde zaten kullanılıyor (`rota/performans_modeli.py`,
  `analiz/dedektor_duyarliligi.py`, `ml/tip_analizi.py`). `prop` içindeki kanat alanı ve
  MTOW ile kanat yükü hesaplanabilir (Fikir 29).

#### R11. NTNU-IMT/weather-routing-discretisation (GPL-3.0, ⭐5)
- **Amaç:** Rüzgâr itkili gemide rota + güç dağılımı. Makalenin sorusu: "ayrıklaştırma
  çözümü ne kadar etkiler?"
- **Veri/algoritma:** Izgara tabanlı 3B dinamik programlama (Rust çekirdek), ERA5 (cdsapi),
  `convergence_study.py`.
- **Güçlü/zayıf:** Tekrarlanabilirlik için tüm test senaryoları depoda. Bakım yapılmayacağı
  açıkça yazılmış.
- **Projeyle ilgisi:** **Ayrıklaştırma yakınsama çalışması** yönteminin doğrudan örneği
  (Fikir 5).

#### R12. Kicho-Fops/Spatiotemporal-Routing-Algorithm (lisans yok, ⭐1)
- **Amaç:** Değişen hava altında kara yolu rotası (Chicago).
- **Veri/algoritma:** OSMnx/NetworkX. `calculate_isochrones.py` grafı 15 dakikalık
  izokron bölgelere ayırıyor; her kenara varış zamanına uyan tahmin dilimini "dikiyor"
  (stitch). GNN ile kenar ağırlığı da var.
- **Güçlü/zayıf:** Dinamik problemi statiğe çevirme fikri basit ve etkili. Depo ~750 MB:
  NetCDF ve `__pycache__` git'e girmiş.
- **Projeyle ilgisi:** Bizde A* zaten her düğüme kendi nominal varış zamanını veriyor
  (`_a_yildiz_ile_rota_ara`, `nominal_zamanlar`). Yeni fikir çıkmadı.

#### R13. 52North/WeatherRoutingTool (MIT, ⭐66, aktif)
- **Amaç:** Hava koşullarına göre gemi rotası, yakıt odaklı.
- **Veri/algoritma:** İzokron/izofuel, genetik algoritma (pymoo) ve **MCDM R-yöntemi**
  (Rao ve Lakshmi 2021) ile Pareto kümesinden "en iyi uzlaşma" seçimi. GCR-slider
  algoritması büyük daireyi kara kesmeyecek şekilde kaydırıyor. Kısıtlar bir listede
  toplanıyor.
- **Güçlü/zayıf:** Kamu fonlu ve belgelenmiş, test ve yapılandırma örnekleri var.
- **Projeyle ilgisi:** Pareto seçeneklerimize "uzlaşma" etiketi (Fikir 28). GCR-slider
  fikri, kısıtlı sahada sapmanın bizim koridor A*'ımızdaki karşılığı.

#### R14. ManelGrifoll/SIMROUTE (lisans yok, ⭐79)
- **Amaç:** CMEMS dalga tahminiyle gemi rotası (A*). Gerçek AIS rotalarıyla karşılaştırma
  yapılmış (Grifoll vd. 2022, Ocean Eng. 255:111427).
- **Projeyle ilgisi:** "Önerilen rota ile gerçek iz karşılaştırması" bizde `rota_backtest`
  ile zaten var. Yeni fikir çıkmadı.

#### R15. SAICHARAN0719/OptimalShipRoutingAlgorithm (NOASSERTION, ⭐4)
- **Amaç:** A* + YSA ile gemi rotası, Flask.
- **Güçlü/zayıf:** Depoda `app.py.bak`, `fixed_app.py`, `fix.txt` gibi dağınık dosyalar var.
  Mühendislik kalitesi düşük.
- **Projeyle ilgisi:** Yok.

### 1.3 ADS-B ve görselleştirme

#### R16. openskynetwork/opensky-api (GPL-3.0, ⭐474)
- **Amaç:** OpenSky REST API'nin Python/Java istemcisi.
- **Önemli not (README):** 18 Mart 2026'dan beri OAuth2 istemci kimlik bilgisi zorunlu.
  Ayrıca: **"We may block AWS and other hyperscalers due to generalized abuse from these IPs."**
- **Projeyle ilgisi:** Biz Trino kullanıyoruz, REST'i kullanmıyoruz. Ancak B planındaki
  bulut sunucu seçeneği (Azure for Students) bir "hyperscaler". Bu engelin Trino'ya da
  uygulanıp uygulanmadığı belirsiz (tahmin). Bkz. Fikir 12.

#### R17. hook-365/adsb-3d (MIT, ⭐52)
- **Amaç:** readsb `aircraft.json` ile 3B/VR canlı ve geçmiş ADS-B görselleştirme, hava yolu
  yoğunluk ısı haritası, ACARS çözümleme.
- **Güçlü/zayıf:** Dürüst arayüz kararları: konumla uyuşmayan rotalar "Unverified" / "?"
  etiketiyle gösteriliyor. Akıcı hareket "gerçek verinin önüne asla tahminle geçmiyor".
  Docker entegrasyon testleri var.
- **Projeyle ilgisi:** Trafik yoğunluğu × risk "maruziyet" haritası fikri (Fikir 21).
  Etiketleme ilkesi bizim bilimsel dürüstlük kuralımızla örtüşüyor.

#### R18. kevtoe/worldview (MIT, ⭐246)
- **Amaç:** CesiumJS küresinde uçuş, uydu, AIS, deprem ve CCTV katmanları.
- **Veri:** FlightRadar24 + adsb.fi. FR24 kullanım şartlarının buna izin verip vermediği
  belirsiz (tahmin).
- **Projeyle ilgisi:** Düşük. Ölü hesap (dead-reckoning) animasyonu yalnız görsel amaçlı.

#### R19. kewonit/aeris (AGPL-3.0, ⭐351)
- **Amaç:** Next.js + MapLibre + deck.gl ile 3B canlı uçuş radarı.
- **Veri:** adsb.lol → adsb.fi → airplanes.live → OpenSky dört kademeli yedek zinciri,
  "kredi farkındalıklı" uyarlanır sorgulama (`use-flights.ts`).
- **Projeyle ilgisi:** Canlı ADS-B bizde varsayılan olarak kapalı. Kredi farkındalıklı
  sorgulama, ban riski kuralımızla uyumlu bir desen. AGPL olduğu için kod alınmamalı.

#### R20. josericodata/FlightTrackingApp (MIT, ⭐9)
- **Amaç:** Streamlit + Folium ile OpenSky canlı uçuş haritası, OurAirports ile en yakın
  meydan.
- **Projeyle ilgisi:** Yok (eğitim örneği).

### 1.4 Havacılık meteorolojisi verisi ve biçimleri

#### R21. aeharding/ppg.report (MIT, ⭐61)
- **Amaç:** Paramotor pilotlarına konumdan hava raporu.
- **Veri:** Open-Meteo yüksek rüzgârları, TAF, AWC SIGMET, **G-AIRMET**, CWA, NWS uyarıları,
  FAA TFR.
- **Güçlü/zayıf:** README'deki "Keep these free APIs free" ilkesi: her dış isteğe
  User-Agent ve önbellek (Nominatim için en az bir hafta). Bizim ban riski kuralımızla aynı.
- **Projeyle ilgisi:** G-AIRMET'in türbülans ürünleri ABD doğrulamasında operasyonel bir
  karşılaştırma tabanı olabilir (Fikir 20).

#### R22. wmo-im/iwxxm (lisans yok, ⭐63)
- **Amaç:** ICAO Ek 3 ürünleri için XML/GML şeması ve **Schematron** kuralları.
- **Projeyle ilgisi:** IWXXM 2025-2 SIGMET çıktımız resmi XSD ile doğrulandı.
  `veri/iwxxm.py` içinde Schematron doğrulaması yok (Fikir 27).

#### R23. avwx-rest/avwx-engine (MIT, ⭐124, aktif)
- **Amaç:** METAR/TAF/**PIREP**/AIREP/SIGMET/NOTAM ayrıştırma (tam tipli, test verili).
- **Projeyle ilgisi:** Bizim PIREP şiddet ayrıştırıcımız üç satırlık bir regex
  (`dogrulama/bagimsiz_kanit.pirep_siddet_sinifi`). Daha önce PIREP verisinde FL birimi
  hatası yaşandı. avwx'in `avwx/current/pirep.py` ayrıştırıcısı bağımsız bir test kâhini
  (oracle) olarak kullanılabilir (Fikir 11).

---

## 2. Aşama: Makaleler

Dosya adları klasördeki adlardır. Eski `makale_ozet.txt` farklı (28 dosyalık) bir
numaralandırmaya göre yazılmış; artık güncel değil.

### 2.1 Türbülans teşhisi, klimatoloji ve tahmin

#### Makale23. Ellrod ve Knapp (1992). *An Objective Clear-Air Turbulence Forecasting Technique: Verification and Operational Use.* Weather and Forecasting 7, 150–165
- **Not:** PDF taranmış görüntü, metin katmanı yok. Sayfalar görüntüye çevrilip okundu
  (bkz. §4).
- **Soru/yöntem:** VWS × DEF ürünü olan TI1 ve yakınsama terimli TI2'nin tanımı. NMC
  (NGM, AVN) ve AFGWC (HIRAS, GSM) modellerinde operasyonel kullanım ve doğrulama.
- **Veri/metrik:** ±3 saat içindeki PIREP'ler. Bir TI1 alanı, eşik konturu içinde **en az
  iki** orta ve üstü raporla doğrulanmış sayılıyor. Metrikler: POD, FAR ve alan tabanlı
  tehdit skoru TTS = GPC / (GPF + GPO − GPC).
- **Bulgular:**
  - **Tablo 1:** MDT eşiği AFGWC'de 8, NGM'de 4, AVN'de 2. MDT-SVR eşiği sırasıyla 12, 8, 4.
    Yazarların ifadesiyle AFGWC eşikleri NMC'ninkinin 2–3 katı, NGM'ninki AVN'ninkinin iki
    katı (birim tabloda yazmıyor; yaygın kullanım ×10⁻⁷ s⁻², tahmin).
  - NMC'de POD %70–76, FAR %22–36. AFGWC'de POD %70–84 (ortalama %81), FAR %30–48.
  - TTS 0,17 (24 sa) olarak hesaplanmış.
  - Kanada AES çalışmasında PIREP, raporun **önceki 10° boylamlık segmentindeki en büyük**
    indeks değeriyle eşleştirilmiş.
- **Kısıtlar:** Yazarlara göre başlıca hata kaynakları: jet konumunun yanlış verilmesi
  (trof/sırt amplifikasyonu), veri seyrek bölgelerde ölçülemeyen kayma ve "konvektif geri
  besleme". Konvektif ve dağ dalgası türbülansı kapsam dışı.
- **Projeye aktarılabilir:** Kaynağa özgü eşik (Fikir 2), alan oranı/TTS (Fikir 9),
  komşuluk maksimumu eşleştirmesi (Fikir 10). "En az iki rapor" kuralı, sanal PIREP'teki
  "en az iki uçak" doğrulamasıyla aynı mantıkta; raporda atıf verilebilir.

#### Makale8. Foudad, Sanchez-Gomez, Jaravel, Rochoux, Terray (2024). *Past and Future Trends in Clear-Air Turbulence Over the Northern Hemisphere.* JGR Atmospheres 129, e2023JD040261
- **Soru/yöntem:** CAT sıklığında 1980–2021 eğilimi ve gelecek projeksiyonu. Birden çok
  reanaliz, 11 CMIP6 modeli ve CNRM-CM6.1 büyük başlangıç koşulu topluluğu.
- **Veri/metrik:** 200–250 hPa. Teşhisler: TI1, −Ri, frontogenez, yatay sıcaklık gradyanı,
  NCSU1. MOG eşiği her veri kümesi için 99. yüzdelik.
- **Bulgular:** Kuzeybatı Afrika, Orta Doğu ve Doğu Asya'da MOG-CAT sıklığı son
  on yıllarda **iki katından fazla** artmış. Doğu Asya ve Orta Doğu'daki artış iç
  değişkenlik aralığının dışında, dış zorlamaya bağlanabilir. Kuzey Atlantik'te eğilim
  anlamlı değil. Yazarlar eşiğin "yatay çözünürlüğe çok bağlı" olduğunu not ediyor.
- **Kısıtlar:** CMIP6 modelleri Kuzey Atlantik'te VWS'yi düşük veriyor. Eşik seçiminde
  literatürde uzlaşı yok (%95–99,6 arası değerler kullanılıyor).
- **Projeye aktarılabilir:** Türkiye'ye komşu bölgelerde artış bulgusu, raporun
  motivasyonu için kullanılabilir (Fikir 25). Yüzdelik tabanlı ve kaynağa özgü eşik
  (Fikir 2). Çoklu teşhisin işaret uyumu fikri (Fikir 19).

#### Makale11. Kim, J. H. ve Kim, J.-H. (2026). *Combined impact of jet stream and turbulence on long-term trans-oceanic flight routes over North Atlantic Ocean using ERA5 reanalysis.* Scientific Reports 16:27143
- **Soru/yöntem:** JFK–LHR rüzgâr-optimum rotası (WOR) ile türbülanstan kaçınan rotanın
  (TOR) 44 yıllık (1979–2022) güvenlik-verim ödünleşimi.
- **Veri/metrik:** ERA5 0,25°, 3 saatlik. **TI3 = TI1 + DVT**, DVT = C·|div(t) − div(t−6 sa)|,
  C = 0,01. MOG eşiği 20–60°K bandında, **her seviye için ayrı** 98. yüzdelik.
  A* yaklaşık 1°'lik küp-küre ızgarada çalışıyor. TI3 eşiğini aşan bacaklara sonsuza yakın
  ceza veriliyor (sert kısıt), ancak meydanların 500 km yakınında ceza uygulanmıyor.
  Eşik ailesi: s97, s98, s99.1, s99.6.
- **Bulgular:** Rüzgâr değişimi en hızlı gidiş-dönüşü ~2 dk kısaltmış. Ancak CAT
  artışı nedeniyle kaçınma bedeli bu kazancı silip tersine çevirmiş. Doğuya giden uçuşlar
  orantısız etkileniyor. Kod ve veri Zenodo'da.
- **Kısıtlar:** Sabit irtifa ve Mach. TI3 yazın (konvektif dönemde) en zayıf.
- **Projeye aktarılabilir:** TI3 (Fikir 15), yön bazlı tabakalama (Fikir 4), eşik ailesiyle
  Pareto (Fikir 26). "Risk süresi" metriğinin bizde karşılığı (`riskli_sure_dk`) zaten var.

#### Makale10. Kim, Chan, Sridhar, Sharman (2015). *Combined Winds and Turbulence Prediction System for Automated Air-Traffic Management Applications.* JAMC 54
- **Soru/yöntem:** GTG yöntemi 3 km ARW modelinde uygulanmış. Aynı geçerlilik zamanına
  düşen ardışık koşular **zaman gecikmeli topluluk** (time-lagged ensemble) olarak
  birleştirilmiş. 10 teşhis × 3 üye = 30 tahmin, EDR ölçeğine eşlenmiş.
- **Veri/metrik:** Ticari uçakların yerinde EDR ölçümleri. Rota için ≥%10 SOG olasılık alanı
  kullanılmış.
- **Bulgular:** Topluluk, tek teşhislerden daha becerili. LAX–JFK örneğinde WOR, SOG
  ≥%10 alanında 52 dk geçiriyor. Kalkıştan itibaren yanal kaçınma +16 dk (%6,7) ekliyor.
  Manevra 1,5 sa geciktirilirse buna göre 10 dk (~160 km, ~760 kg yakıt) tasarruf ediliyor;
  2,5 sa geciktirilirse +2 dk.
- **Kısıtlar:** İki vaka günü. %10 eşiği keyfi; farklı eşikler ileri çalışmaya bırakılmış.
- **Projeye aktarılabilir:** Zaman gecikmeli GFS topluluğu (Fikir 3) ve kaçınma manevrasının
  başlangıç zamanı analizi (Fikir 18).

#### Makale19. Lee, M. H. F. (2025). *Clear-Air Turbulence – Generation, Predictability, and Feedback in Weather Systems.* Doktora tezi, ETH Zürich (Diss. ETH No. 31496)
- **Soru/yöntem:** CAT ile büyük ölçekli hava sistemleri arasındaki iki yönlü etkileşim.
  ~5000 MOG olayı (yerinde EDR) ERA5 hava sistemi maskeleriyle eşleştirilmiş. ECMWF
  topluluk tahmininde dört olayın öngörülebilirliği incelenmiş.
- **Bulgular:** Olayların ~%40'ı Rossby dalga kırılmasıyla (RWB, tip I, yüksek
  deformasyon), ~%30'u sıcak taşıma kuşağı yükselişiyle (WCB, tip II, **negatif PV**)
  birlikte görülüyor. Uygun teşhisle (tip I için deformasyon, tip II için negatif PV)
  topluluk, olayları **24–48 sa** önceden yüksek olasılıkla veriyor. Daha uzun öngörü
  sürelerinde konum belirsizliği büyük.
- **Kısıtlar:** Öngörülebilirlik bölümü yalnız 4 vakaya dayanıyor ve eşik duyarlılığı
  test edilmemiş (yazarın kendi ifadesi).
- **Projeye aktarılabilir:** Öngörü süresine bağlı güven uyarısı (Fikir 7), negatif PV
  göstergesi (Fikir 19), sinoptik tipe göre tabakalı doğrulama (Fikir 4).

#### Makale6. Zhang, Zhang, Yuan, Zhang, Hu, Yang (2025). *Clear-Air Turbulence over China: Climatology and Multiscale Mechanisms from First Long-Term Aircraft Reports.* Atmosphere 16, 1218
- **Soru/yöntem:** Çin sivil havacılığının 2022–2024 arasındaki 12.539 sesli türbülans
  raporu ile ERA5'ten klimatoloji çıkarılmış.
- **Bulgular:** Raporların %61'i 3000–8000 m'de. İkinci tepe 7000–11.000 m (%39,2, daha
  şiddetli). Kış payı %33,4 (jet > 30 m/s), yaz payı %21. Orta-güney ve güneybatı
  sıcak noktalarında 600–400 hPa vortisite gradyanı etkili.
- **Kısıtlar:** Ham PIREP verisi lisanslı ve paylaşılmıyor. Beceri skoru yok, yalnız tanımlayıcı.
- **Projeye aktarılabilir:** 30 m/s jet eşiğiyle tabakalama (Fikir 4). Ayrıca ulusal
  etiket kaynağının (bizde MGM başvurusu bekliyor) ne kadar değerli olduğunu gösteren
  bir örnek.

#### Makale15. Soliva Fabrega, J. (2025). *Analysis of the Trend of CAT over Europe.* Lisans tezi (danışmanlar J. Mazón, D. Pino)
- **Soru/yöntem:** 1994–2024 Avrupa'sında EI1 (TI1) eğilimi, ERA5 200/225 hPa. Prosser vd.
  (2023) yöntemiyle MOG aşım olasılığı hesaplanmış.
- **Bulgular:** Avrupa genelinde net bir artış yok. Güney Avrupa'da değerler ve oynaklık daha
  yüksek. MOG aşımında %38,6 göreli artış var (0,004 puan/yıl), ancak saçılımı büyük.
- **Kısıtlar:** Tek teşhis (Prosser vd. 21 teşhis kullanmıştı). Anlamlılık testi sınırlı.
- **Projeye aktarılabilir:** Bitirme düzeyinde bir ERA5 çalışmasının kapsamı için iyi bir
  ölçü. Türkiye bağlamı için Fikir 25.

#### Makale18. Smith, L. (2022). *Turbulence forecasting over South Africa using diagnostics from the convective scale ensemble prediction system of the Unified Model: a pilot study.* Yüksek lisans tezi, Pretoria Üniversitesi
- **Soru/yöntem:** SAWS CSEPS topluluğundan Ellrod ve TKE→EDR indeksleri, 2018'deki
  11 vaka ve 39 CAT olayında PIREP'e karşı değerlendirilmiş. Vakalar **hava rejimine** göre
  ayrılmış: kesik alçak (cut-off low), üst seviye trofu, zonal akış.
- **Bulgular:** Topluluk ortalaması ve olasılığı becerili, ancak şiddet eksik tahmin
  ediliyor. EDR genel olarak Ellrod'dan iyi. Kesik alçakta ise Ellrod daha iyi. En çok
  ıskalama trof rejiminde.
- **Kısıtlar:** Küçük örneklem ve vaka seçimi (tahmin; sınırlar bölümü metin çıkarımında
  okunamadı, bkz. §4).
- **Projeye aktarılabilir:** Rejime göre tabakalı doğrulama (Fikir 4).

### 2.2 Türbülans için makine öğrenmesi

#### Makale1. Gökdeniz, K. ve Ülkü, İ. (2026). *Predictive Modeling of High-Altitude Clear Air Turbulence in the United States: A Machine Learning Approach.* arXiv:2607.11899
- **Soru/yöntem:** ABD 200–350 hPa, IEM PIREP + ERA5 teşhisleri + BADA aerodinamik
  özellikleri (kanat yükü, sürükleme, L/D). RF, XGBoost, LightGBM, AdaBoost, LR.
  **Rastgele 70/30 bölme** ve k-katlı çapraz doğrulama.
- **Veri/metrik:** POD, FAR, CSI, TSS, AUC.
- **Bulgular:** XGBoost AUC 0,904. Coğrafi koordinatların özellik önemi %17,5. TI3 öne çıkan
  teşhis. Aerodinamik özelliklerin katkısı %3,2; MOD-SEV sınıfında POD'u 0,845'ten 0,866'ya
  çıkarıyor. Kış en yoğun mevsim.
- **Kısıtlar:** Yazarlara göre coğrafi kapsam ve tip çeşitliliği dar. Benim gözlemim:
  rastgele bölme aynı günün örneklerini eğitim ve test setine dağıtır, bu da AUC'yi
  şişirebilir. Koordinatların en önemli özellik çıkması da konum ezberine işaret edebilir
  (tahmin; yazarlar bunu topografyaya bağlıyor). BADA lisanslı veridir.
- **Projeye aktarılabilir:** Bölme yöntemine göre kıyas tablosu (Fikir 1), TI3 (Fikir 15),
  uçak tipine duyarlı risk (Fikir 29). Türk yazarlar ve SAYZEK-ATP desteği var; raporda
  yerel bir referans olarak kullanılabilir.

#### Makale21. Gu, A. ve Wang, Y. (2024). *Optimizing Clear Air Turbulence Forecasts Using the K-Nearest Neighbor Algorithm.* J. Meteor. Res. 38(6), 1064–1077
- **Soru/yöntem:** 8 teşhisli öznitelik vektörüyle ağırlıklı KNN (W-KNN, K = 27).
  Ağırlıklar Wᵢ = AUCᵢ² / ΣAUC² (Kim ve Chun 2011). ERA5 125–500 hPa, 7 yıl, Colorado
  PIREP'leri. **Null ve MOG** olayları kullanılmış, hafif raporlar dışarıda. Rastgele 80/20
  bölme + 10 katlı CV + SMOTE.
- **Bulgular:** AUC 0,86, maxTSS 0,552. Yıllara göre AUC 0,82 (2016) ile 0,91 (2022)
  arasında değişiyor. RF'yi ve topluluk ortalamasını geçiyor.
- **Kısıtlar:** Rastgele bölme ve tek bölge. KNN'nin büyük veride maliyeti yüksek.
- **Projeye aktarılabilir:** AUC² ağırlıklı birleşik EDR (Fikir 24), "hafif = negatif"
  etiket duyarlılığı (Fikir 8), yıllık/mevsimlik AUC dağılımını raporlama (Fikir 4).

### 2.3 Türbülans ve havaya duyarlı rota planlama

#### Makale14. Nair, S. S. ve Hamilton, M. (2025). *Adaptive Flight Planning using Turbulence and Weather Forecasts.* IEEE ANTEM 2025
- **Soru/yöntem:** Kuzey Atlantik'te A* ile rüzgâr + Ellrod indeksi, NAT izleriyle
  karşılaştırma.
- **Bulgular:** BA182 (Track V) ile kıyasta en büyük Ellrod değeri 4,021'e karşı 22,390,
  süre farkı 3,54 dk.
- **Kısıtlar (benim gözlemim):** Ellrod birimi "s⁻²" yazılmış ve ölçek tablosu (0–2 sakin …
  >36 aşırı) kaynaksız. Gerçek türbülans gözlemi yok; BA182'nin "şiddetli türbülans yaşadığı"
  iddiası yalnız indekse dayanıyor. Yalnız Gander/Shanwick segmenti incelenmiş.
- **Projeye aktarılabilir:** Yöntem olarak değil, karşı örnek olarak. "İndeks değeri
  gözlem değildir" ilkemizin gerekçesi.

#### Makale2. Knapp, Jameson, Measure, Butler (~2007, AMS konferans bildirisi P1.11). *Optimized Flight Routing Based on Weather Impacts Grids*
- **Soru/yöntem:** ABD Ordusu AWRT aracı. Uçağa özgü eşiklerle hava etkisi ızgarası
  (yeşil/sarı/kırmızı) ve rota optimizasyonu. Yıl metinde yazmıyor; 2006 vakası
  kullanıldığı için ~2007 (tahmin).
- **Bulgular:** Nitel bir sunum. **Rota boyunca 2B dikey kesit** görünümü (Şekil 3) var.
- **Projeye aktarılabilir:** Dikey kesit görünümü (Fikir 17). Uçağa özgü eşik fikri
  Fikir 29 ile örtüşüyor.

#### Makale3. Sydorenko, Lysa, Sikora, Martsyshyn, Miyushkovych (2025). *Optimizing Aircraft Routes in Dynamic Conditions Utilizing Multi-Criteria Parameters.* Applied Sciences 15, 6044
- **Soru/yöntem:** A*, B*, D*, D* Lite ve Dijkstra karşılaştırması ve çok ölçütlü rota.
- **Kısıtlar (benim gözlemim):** Sonuç bölümünde Dijkstra'nın "negatif kenar ağırlığı
  gerektirdiği" yazıyor; bu yanlış, Dijkstra negatif olmayan ağırlık ister. A320neo için
  "saatte 2,45 L yakıt" değeri fiziksel olarak olanaksız.
- **Projeye aktarılabilir:** Yok. Literatürde dikkatle kullanılmalı.

#### Makale4. Zhou, H. ve Hu, X.-B. (2020). *A Ripple Spreading Algorithm for Free-Flight Route Optimization in Dynamical Airspace.* IEEE SSCI 2020
- **Soru/yöntem:** Hareketli kötü hava ve kısıtlı bölgeler ile zamana bağlı rüzgârın olduğu
  ortamda dalgalanma yayılımı algoritması. Tek çalıştırmada optimum bulunuyor.
- **Bulgular:** Rüzgârlı optimum 2926 NM / 5,18 sa. Rüzgârsız rota 2908 NM ama 5,92 sa sürüyor.
  Hesaplama 67,9 sn'ye karşı 2,5 sn.
- **Kısıtlar:** Sentetik senaryo.
- **Projeye aktarılabilir:** Düşük. Zamana bağlı ağırlıkları bizde düğüm zamanları zaten
  karşılıyor. "Rüzgârsız rota daha kısa ama daha uzun sürer" örneği, `ruzgar_kazanci`
  ayrımımızı açıklamak için kullanılabilir.

#### Makale5. Su, Wen, Li, Chen, Yang (2026). *A Cooperative Trajectory Planning Method for Multi-Aircraft Thunderstorm Avoidance Based on Optimal Control and Game Equilibrium.* Aerospace 13, 537
- **Soru/yöntem:** Çok uçaklı oyun kuramı (Iterative Best Response) ve her uçak için CasADi
  NLP. Fırtınaların yaşam döngüsü modellenmiş, ara noktalara zamanında varış kısıtı var.
- **Bulgular:** A* + IBR ve ADMM'den daha dengeli sonuç. Varış hatası saniye mertebesinde.
- **Kısıtlar:** Belirsiz rüzgâr ve tahmin belirsizliği yok, irtifa boyutu yok (yazarların
  kendi notu).
- **Projeye aktarılabilir:** Düşük. Ayırma ve çok uçaklı planlama kapsam dışı. SIGMET
  hareketi bizde zaten var.

#### Makale7. Serafino, Bernabò, Cuccoli, Lupidi (2020). *Emission Pollution Reduction by EFB Implemented Trajectory Optimizer.* IEEE konferansı (adı metinde okunamadı)
- **Soru/yöntem:** Uygulanabilir yörünge grafı + Dijkstra + genetik algoritma + Pareto ile
  EFB üzerinde hava kaçınma ve emisyon. Clean Sky projesi kapsamında.
- **Bulgular:** ATR72'de 4 uçuşta yakıt ve CO₂ %7,9 azalmış. A320 simülatöründe 12 uçuş ve
  3 pilotla yakıt %3,19, NOx %6,2 azalmış. İnsan faktörü uzmanları anket, sonradan
  görüşme ve omuz üstü gözlem yapmış.
- **Projeye aktarılabilir:** E7 kullanılabilirlik oturumları için yöntem (Fikir 14).

#### Makale9. Song, Sun, Li, Wang, Shi (2026). *An observation-to-decision framework for low-altitude turbulence reconstruction and UAV route planning.* Measurement (Elsevier), doi:10.1016/j.measurement.2026.122869
- **Soru/yöntem:** Rüzgâr profil radarından bilgi damıtma (knowledge distillation) ile
  türbülans profili, Doppler radar ve yer istasyonu füzyonuyla 3B alan. Orta vade için NWP,
  kısa vade için ConvLSTM, ardından A*.
- **Kısıtlar:** Yazarlara göre bölgesel 3B türbülans için gerçek ölçüm yok; yalnız "fiziksel
  tutarlılık" gösterilmiş. Veri istek üzerine.
- **Projeye aktarılabilir:** Düşük (alçak irtifa İHA). "Gözlemden karara" zincir anlatımı
  sunum için bir şablon olabilir.

#### Makale12. Aldao Pensado, Fontenla Carrera, Veiga López, González Jorge, Martín Ortega (2024). *Turbulence-aware UAV path planning in urban environments.* ICUAS 2024
- **Yöntem/bulgular:** CFD rüzgârı ve TKE eşiğiyle kentsel İHA rotası. Sentetik vakada
  türbülansın rotayı uzattığı gösterilmiş.
- **Projeye aktarılabilir:** Yok (kentsel İHA kapsam dışı).

#### Makale13. Huang, Liu, Zhang, Chen, Deng, Zhu (2026). *Low-altitude Turbulence Intensity Prediction and Route Planning Method Based on Multi-source Meteorological Data.* ICMTIM 2026
- **Yöntem/bulgular:** IPSO-CNN-BiLSTM-öz dikkat, MAE 0,0036. NWP çıkarılınca rota 142,35'ten
  166,50 km'ye uzuyor: belirsizlik arttıkça planlayıcı daha tutucu davranıyor.
- **Projeye aktarılabilir:** Bu bulgu, konformal "belirsiz" durumun rotaya nasıl
  yansıyacağına dair bir örnek. Ancak alçak irtifa ve tek vaka olduğu için öneri
  çıkarılmadı.

### 2.4 ADS-B, emisyon ve iz bulutu

#### Makale16. Trüb, Moser, Schäfer, Pinheiro, Lenders (2018). *Monitoring Meteorological Parameters With Crowdsourced Air Traffic Control Data.* IPSN'18
- **Yöntem:** OpenSky'ın topladığı Mode S (EHS/MRAR) ve ADS-B mesajlarından sıcaklık,
  rüzgâr ve basınç çıkarımı.
- **Bulgular:** Resmi veriye göre ortalama sapma 0,11 °C, 0,09 m/s, 1,00° ve 0,10 hPa.
  İzlenen uçakların %51'inden fazlası için gözlem üretilebiliyor; AMDAR/MRAR'da bu oran %1'in
  altında.
- **Kısıtlar:** NWP'ye asimilasyonun etkisi ölçülmemiş (yazarlar ileri çalışmaya bırakmış).
- **Projeye aktarılabilir:** F7 rüzgâr asimilasyonu fizibilitesine ek. Model rüzgârının
  bağımsız doğrulaması (Fikir 23).

#### Makale17. Sun, Olive, Roosenbrand, Parzani, Strohmeier (2024). *OpenSky Report 2024: Analysis of Global Flight Contrail Formation and Mitigation Potential.* IEEE/AIAA DASC 2024
- **Yöntem:** Bir yıllık OpenSky verisi + ERA5 (fastmeteo). Kalıcı iz bulutundan kaçınmak
  için gereken **en kısa irtifa sapması** (±2000 ft) hesaplanmış.
- **Bulgular:** Uçuş mesafesinin aylık %5–9'u kalıcı iz bulutu oluşturabilirdi. Bunların
  %70'i irtifa sapmasıyla önlenebilirdi.
- **Projeye aktarılabilir:** M9'u "±1 FL seçeneği" ile bilgi amaçlı genişletme (Fikir 30).

#### Makale22. Sun, Tassanbi, Obojski, Plantholt (2023). *Evaluating Transatlantic Flight Emissions and Inefficiencies Using Space-Based ADS-B Data.* SESAR Innovation Days 2023
- **Yöntem:** Spire uydu ADS-B + OpenSky ile yörünge ve emisyon hesabı. Optimum rota
  OpenAP.top ile, rüzgârlı seyir için üretilmiş.
- **Bulgular:** Başlangıç kütlesi bilinmediği için **%70–90 MTOW aralığı** kullanılmış.
  Bir örnekte 20 t kütle farkı emisyonun ~%6,5'i kadar hata yaratıyor. Doğuya uçuşlarda
  emisyon −%20'ye kadar düşüyor, batıya uçuşlarda +%10'a kadar artıyor.
- **Projeye aktarılabilir:** Kütle belirsizlik bandı (Fikir 6). opentop ile bağımsız
  referans (Fikir 22).

### 2.5 Operasyonel algılama ve gösterim

#### Makale20. Craig, Williams, Blackburn, Linden, Stone (~2008, AMS konferans bildirisi). *Remote Detection and Real-Time Alerting for In-Cloud Turbulence*
- **Yöntem:** NEXRAD Türbülans Algılama Algoritması (NTDA, bulanık mantık). 2007'de 83 radar
  ile 5 dakikada bir 3B mozaik üretilmiş. EDR **ve buna eşlik eden güven değeri (EDC)**
  veriliyor. United pilotlarına ACARS üzerinden ASCII plan ve dikey kesit gönderilmiş;
  doğruluk ve yarar için ayrı bir geri bildirim sitesi kurulmuş.
- **Bulgular:** Yerinde EDR ile iyi uyum. Pilot geri bildirimine göre mesajlar doğru ve başka
  kaynakta olmayan bilgi veriyor.
- **Kısıtlar:** Yalnız bulut içi türbülans ve radar kapsamı. Nicel geri bildirim istatistiği
  bildiride yok.
- **Projeye aktarılabilir:** Her değerle birlikte güven verme (bizde konformal durum zaten
  var), dikey kesit (Fikir 17), geri bildirim döngüsü (Fikir 14), metin brifing.

### 2.6 `Silinecekler/` klasöründeki 5 PDF

#### SIL_Makale12. Sun, J. ve Roosenbrand, E. (2023). *Fast contrail estimation with OpenSky data.* JOAS 1 (11. OpenSky Sempozyumu)
- **Yöntem/bulgular:** FastMeteo kütüphanesi (ARCO-ERA5 Zarr, istemci-sunucu, vektörel
  enterpolasyon). Nokta sayısı arttıkça verim artıyor. Kod ve veri Zenodo'da.
- **Projeye aktarılabilir:** Bizim ARCO bulgumuz (saat başı ~324 MB) yerel bir
  önbellek/sunucu ile azaltılabilir. Ancak CDS birincil kaynak olarak kaldığı için öncelik
  düşük.

#### SIL_Makale9. Yahyasatrio, Elboghdadly, Anjum, Zhou (2025). *Automatic Contrail Detection Using Integrated Satellite Observation, Meteorological Indicators, and Air Traffic Data in the United Kingdom.* IEEE COMPSAC 2025
- **Yöntem:** Schmidt–Appleman Kriteri (SAC) + ERA5 + EUMETSAT + OpenSky. Birleşik ısı
  haritaları üretilmiş.
- **Kısıtlar:** "Ön sonuçlar" deniyor; nicel doğruluk metriği bulunamadı.
- **Projeye aktarılabilir:** M9 için SAC (Fikir 30).

#### SIL_Makale14. Veiga-Piñeiro, Aldao-Pensado, Martín-Ortega (2025). *Hybrid CFD–Deep Learning Approach for Urban Wind Flow Predictions and Risk-Aware UAV Path Planning.* Drones 9, 791
- **Yöntem/bulgular:** CFD vekil modeli (CAE + DNN) CFD'den 4000 kat hızlı, hata çoğu yerde
  <%1. TKE kısıtlı A*.
- **Projeye aktarılabilir:** Yok (kentsel İHA). Vekil model fikri ancak çok ağır bir fizik
  modeli olsaydı anlamlı olurdu.

#### SIL_Makale5. Zhou, Zhang, Liu, Yang (2025). *Trustworthy flight guidance method for civil aircraft autonomous operation based on 4D trajectory – a case study of COMAC C919.* Aerospace Sci. Technol. 167, 110641
- **Yöntem:** BERT-LSTM ile 4B yörüngeden pilotun anlayacağı kontrol talimatı metni
  üretilmiş; C919 simülatöründe denenmiş.
- **Bulgular:** Geleneksel kontrol yönlendirmesine ve yalnız yörünge görüntüsüne göre daha
  doğru uygulama ve daha az iş yükü.
- **Projeye aktarılabilir:** Önerilen rotayı insanın okuyacağı ve sisteme girebileceği bir
  biçime çevirme (Fikir 13: ICAO FPL Madde 15). LLM gerekmez.

#### SIL_Makale3. Cui, A. X. (2023). *A methodology for the design and development of an aerospace-specific data repository to support data-driven research.* Yüksek lisans tezi, Royal Military College of Canada
- **Yöntem:** Alana özgü ETL ile küçük ilişkisel veri tabanı (arşiv trafik + hava radarı) ve
  harita aracı.
- **Kısıtlar/gelecek:** Yazar, veri bütünlüğü sorununu çözmediğini ve gerçek zamanlı veriyi
  desteklemediğini kabul ediyor. Önerisi: aynı veriyi farklı kaynaklarla çapraz
  karşılaştırmak.
- **Projeye aktarılabilir:** "Kaynaklar arası çapraz doğrulama" önerisi Fikir 2'nin bir
  parçası (GFS ile ERA5 tutarlılığı).

---

## 3. Aşama: Sentez ve önceliklendirme

Sıralama: önce etki (Yüksek → Düşük), eşitlikte düşük efor öne. Etki ve efor da eşitse
sıra benim değerlendirmem.

| # | Fikir | Etki | Efor | Dondurma sonrası mı? |
|---|---|---|---|---|
| 1 | Literatür kıyasına bölme yöntemi sütunu | Yüksek | Düşük | Hayır |
| 2 | Kaynağa özgü (ERA5/GFS) yüzdelik tabanlı TI1 eşiği | Yüksek | Orta | Evet (eşik) |
| 3 | Zaman gecikmeli GFS topluluğu ile TI1 olasılığı | Yüksek | Orta | Kısmen |
| 4 | Tabakalı doğrulama (mevsim, jet, yön, rejim) | Orta | Düşük | Evet |
| 5 | Rota ayrıklaştırma yakınsama çalışması | Orta | Düşük | Hayır |
| 6 | Yakıt sonucu için kütle belirsizlik bandı | Orta | Düşük | Hayır |
| 7 | Öngörü süresine bağlı güven uyarısı | Orta | Düşük | Hayır |
| 8 | "Hafif = negatif" etiket duyarlılık analizi | Orta | Düşük | Evet |
| 9 | Uyarı alanı oranı ve alan tabanlı tehdit skoru | Orta | Düşük | Evet |
| 10 | Komşuluk maksimumuyla eşleştirme duyarlılığı | Orta | Düşük | Evet |
| 11 | PIREP ayrıştırıcısını avwx-engine ile çapraz test | Orta | Düşük | Hayır |
| 12 | B planında OpenSky "hyperscaler" engelini önceden kontrol | Orta | Düşük | Hayır |
| 13 | Önerilen rota için ICAO FPL Madde 15 dizgisi | Orta | Düşük | Hayır |
| 14 | Kullanıcı geri bildirim kaydı (E7 ile) | Orta | Düşük | Hayır |
| 15 | TI3 (Ellrod–Knox DVT) göstergesi | Orta | Orta | Evet |
| 16 | Kalkış saati penceresi karşılaştırması | Orta | Orta | Hayır |
| 17 | Rota boyunca dikey kesit görünümü | Orta | Orta | Hayır |
| 18 | Kaçınma manevrasının başlangıç zamanı analizi | Orta | Orta | Hayır |
| 19 | Ek teşhisler: frontogenez, ∇T, NCSU1, negatif PV | Orta | Orta | Evet |
| 20 | G-AIRMET ile ABD karşılaştırması | Orta | Orta | Hayır |
| 21 | Maruziyet haritası: risk × trafik yoğunluğu | Orta | Orta | Hayır |
| 22 | opentop ile A* için bağımsız optimal-kontrol referansı | Orta | Yüksek | Hayır |
| 23 | Mode S'ten türetilmiş rüzgârla model rüzgârı doğrulama | Orta | Yüksek | Hayır |
| 24 | AUC² ağırlıklı birleşik EDR | Düşük | Düşük | Evet |
| 25 | Türkiye/Avrupa CAT eğilim bağlamını rapora ekleme | Düşük | Düşük | Hayır |
| 26 | Eşik katılığı ailesiyle Pareto seçenekleri | Düşük | Düşük | Hayır |
| 27 | IWXXM Schematron doğrulaması | Düşük | Düşük | Hayır |
| 28 | Pareto seçeneklerinde MCDM "uzlaşma" etiketi | Düşük | Düşük | Hayır |
| 29 | Uçak tipine duyarlı risk (OpenAP kanat yükü) | Düşük | Orta | Evet |
| 30 | M9 için Schmidt–Appleman ölçütü ve ±1 FL önerisi | Düşük | Orta | Hayır |

### Fikir 1. Literatür kıyasına bölme yöntemi sütunu
- **Durum:** Uygulandı (16 Ekim 2026, `ILGILI_CALISMALAR.md` §5 ve §9).
- **Kaynak:** Makale1 (rastgele 70/30, AUC 0,904), Makale21 (rastgele 80/20 + SMOTE,
  AUC 0,86), Makale1'in literatür tablosu (Muñoz-Esparza 2020, AUC 0,770–0,906), R5
  (zamansal holdout, olumlu örnek).
- **Katkısı:** Akademik değer ve savunma. Gün gruplu doğrulamayla elde ettiğimiz daha düşük
  AUC'nin neden daha dürüst olduğunu tabloyla gösterir.
- **Uygulama yolu:** `docs/rapor/ILGILI_CALISMALAR.md` §9 tablosuna "bölme" sütunu (rastgele /
  gün gruplu / zamansal) ve iki yeni satır (Gökdeniz ve Ülkü 2026, Gu ve Wang 2024). §5'e
  bir paragraf eklenir; Roberts vd. (2017) zaten kaynakçada. Künyeler eklenmeden önce
  Crossref/arXiv'den doğrulanır. Bizim sayılar 18 Ekim nihai paketinden alınır.
- **Etki:** Yüksek · **Efor:** Düşük
- **Risk ve bağımlılıklar:** "Onların AUC'si şişik" denmemeli; "doğrudan kıyaslanamaz,
  çünkü bölme yöntemi farklı" denmeli. Makale1'in tam metninde bölmenin gün bazlı
  olmadığını teyit ettim (bölüm "randomly split into 70% training and 30% testing").

### Fikir 2. Kaynağa özgü (ERA5/GFS) yüzdelik tabanlı TI1 eşiği
- **Durum:** Altyapı ve ilk ölçüm yapıldı (16 Ekim; `turbulans-esik-esleme`,
  `docs/sonuclar/2026-10-16/`). GFS eşdeğeri 8,30e-7 [7,96; 8,67]e-7; tahminin tersine GFS
  daha çok "riskli" diyor. Değer 18 Ekim nihai ERA5 eşiğiyle birlikte ayarlanacak.
- **Kaynak:** Makale23 Tablo 1 (eşik modele göre 2–3 kat değişiyor), Makale8 (eşik
  çözünürlüğe çok bağlı), Makale11 (her seviye için ayrı 98. yüzdelik), SIL_Makale3 (kaynaklar
  arası çapraz karşılaştırma).
- **Katkısı:** Doğruluk ve tutarlılık. Canlı rotaların hepsi GFS ile hesaplanıyor; eşik ise
  ERA5'te seçildi. Aynı atmosfer için GFS'in TI1 dağılımı farklıysa "riskli" kararı
  kaynağa göre kayar (tahmin; henüz ölçülmedi).
- **Uygulama yolu:**
  (a) Örtüşen günler için GFS analizi (f000) ve ERA5 TI1 dağılımları aynı kutuda, seviye
  başına hesaplanır. (b) 7e-7'nin ERA5'teki yüzdeliği p* bulunur. (c) GFS eşiği, GFS
  dağılımının p* yüzdeliği olarak alınır (quantile mapping).
  `config.py`'ye `TI1_ESIK_ORTA_SIDDETLI_GFS` eklenir, `uretim_bilgisi` kullanılan eşiği
  taşır. Yeni bir CLI raporu: `turbulans-esik-esleme` (ad önerisi).
- **Etki:** Yüksek · **Efor:** Orta
- **Risk ve bağımlılıklar:** UCAR THREDDS yalnız −48 sa geriye gidiyor, ERA5 ise ~5 gün
  gecikmeli. Örtüşme için ya GFS f000 birkaç gün boyunca günlük kaydedilir ya da AWS NODD
  GFS arşivi kullanılır (arşivin varlığı kontrol edilmedi). Veri bütçesi ve ONAY gerekir.
  Bu eşleme iki kaynağı tutarlı yapar, ama GFS'in becerisini kanıtlamaz; o iş F1
  doğrulama karnesinindir. Eşik değişirse testler, demo ve ekranlar yeniden kontrol edilir.

### Fikir 3. Zaman gecikmeli GFS topluluğu ile TI1 olasılığı
- **Durum:** Uygulandı, deneysel (16 Ekim; `analiz/gfs_toplulugu.py`, rota isteğinde
  `topluluk: true`). Doğrulama veri biriktirmeyi gerektiriyor (`YAPILACAKLAR.md`).
- **Kaynak:** Makale10 (3 gecikmeli üye × 10 teşhis, rota için ≥%10 SOG), Makale19
  (topluluk 24–48 sa önce olasılık veriyor), R6 (Monte Carlo hava belirsizliği fikri).
  Ayrıca `docs/fizibilite/GEFS_FIZIBILITE.md`'ye bir alternatif.
- **Katkısı:** Belirsizliğe duyarlı karar ve akademik değer. GEFS'in 31 üyesine (adım başına
  ~42,6 MB) gerek kalmadan olasılık üretir.
- **Uygulama yolu:** Geçerlilik zamanı T için son N = 3–4 GFS koşusunun (00/06/12/18Z)
  T'ye düşen adımları alınır. Her ızgara noktasında P(TI1 > eşik) = aşan üye oranı olur.
  Önce yalnız yanıtta deneysel bir `ti1_olasiligi` alanı olarak eklenir; rota kararına
  girmez. MADIS/PIREP günlerinde güvenilirlik diyagramı ile değerlendirilir; karar
  ancak bundan sonra verilir.
- **Etki:** Yüksek · **Efor:** Orta
- **Risk ve bağımlılıklar:** İndirme hacmi N katına çıkar; THREDDS kullanım sınırları
  kontrol edilmeli ve önbellek şart (ban riski kuralı). Gecikmeli üyeler eşit değildir
  (eski koşu daha zayıf); ağırlıklandırma bir varsayımdır. GEFS notundaki kural geçerli:
  "olasılık, doğrulama karnesi olmadan ürünleşmez".

### Fikir 4. Tabakalı doğrulama (mevsim, jet hızı, uçuş yönü, sinoptik rejim)
- **Kaynak:** Makale18 (rejime göre Ellrod/EDR farkı), Makale6 (kış %33,4, jet > 30 m/s),
  Makale11 (doğu/batı asimetrisi), Makale21 (yıllara göre AUC 0,82–0,91), Makale19 (RWB/WCB
  tipleri).
- **Katkısı:** Akademik derinlik. "TI1 nerede işe yarıyor, nerede yaramıyor?" sorusuna
  yanıt verir. Literatürde en çok tekrarlanan analiz biçimi.
- **Uygulama yolu:** `ml/degerlendirme.py`'ye bir tabaka seçici eklenir: mevsim (DJF/MAM/JJA/
  SON), 250 hPa rüzgâr hızı sınıfı (<30 ve ≥30 m/s), backtest için uçuş yönü (doğu/batı
  bileşeni). Her tabaka için n, ROC-AUC ve bootstrap güven aralığı raporlanır; sonuç
  paketine bir tablo eklenir. Sinoptik rejim (RWB/WCB) maske gerektirdiği için sonraya
  bırakılır.
- **Etki:** Orta · **Efor:** Düşük
- **Risk ve bağımlılıklar:** Önceden kaydedilmemiş bir analiz olduğu için "keşifsel"
  etiketiyle verilmeli. Tabaka başına n küçük, çoklu karşılaştırma sorunu var; yalnız
  güven aralığıyla yorumlanır.

### Fikir 5. Rota ayrıklaştırma yakınsama çalışması
- **Durum:** Yapıldı (16 Ekim; `turbulans-ayriklastirma`). Varsayılan ince ayara %0,45 içinde;
  21 nokta yetersiz. Varsayılan korunur.
- **Kaynak:** R11 (NTNU, `convergence_study.py`; makalenin tüm sorusu bu).
- **Katkısı:** Akademik titizlik. "41 ara nokta / ≤ 20 km ızgara / 30° sınırı" seçiminin
  sonucu değiştirmediğini (ya da ne kadar değiştirdiğini) sayıyla gösterir.
- **Uygulama yolu:** `turbulans-performans rota` mevcut demo ve backtest rotalarında ara
  nokta {21, 41, 81} ve ızgara {10, 20, 40 km} ile taranır. Ölçüler: süre, yakıt,
  `riskli_sure_dk`, hesaplama süresi. Çıktı `docs/sonuclar/<tarih>/ayriklastirma.md`
  dosyasına yazılır. Parametreler sabitse, yalnız bu çalışma için geçersiz kılma (override)
  eklenir (tahmin; parametrelerin şu an ayarlanabilir olup olmadığı kontrol edilmedi).
- **Etki:** Orta · **Efor:** Düşük
- **Risk ve bağımlılıklar:** 81 noktada çalışma süresi artar; ölçüm şarjda yapılmalı
  (bkz. performans notu).

### Fikir 6. Yakıt sonucu için kütle belirsizlik bandı
- **Durum:** Uygulandı (16 Ekim; `yakit_tasarrufu_yuzde_araligi`, brifing kartı). Seviye değişimi
  tasarrufu kütleye duyarlı (S3: %1,1–2,9).
- **Kaynak:** Makale22 (%70–90 MTOW; 20 t fark ≈ emisyonun %6,5'i).
- **Katkısı:** Bilimsel dürüstlük. Tek bir "yakıt tasarrufu %X" yerine bir aralık verilir.
  Şu an kütle oranı sabit (`ROTA_SEYIR_KUTLE_ORANI = 0,85`).
- **Uygulama yolu:** Seçilen rotaların yakıtı `rota/performans_modeli.py` ile 0,70 / 0,85 /
  0,90 oranlarında yeniden hesaplanır. Yanıta `yakit_tasarrufu_yuzde_araligi` eklenir. Yanal
  A* araması tekrarlanmaz, çünkü kenar maliyeti saniye cinsinden ve kütleden bağımsız
  (`_kenar_maliyeti_saniye`). Seviye değişimi ise yakıt akışına bağlı
  (`_irtifa_degisimi_maliyeti`), bu yüzden seviye seçimi kütleyle değişebilir. Bant her
  kütle için ayrı raporlanmalı.
- **Etki:** Orta · **Efor:** Düşük
- **Risk ve bağımlılıklar:** API şeması değişir; `semalar.py` ve testler güncellenir. Demo
  sayıları da etkilenir.

### Fikir 7. Öngörü süresine bağlı güven uyarısı
- **Durum:** Uygulandı (16 Ekim; `planlama_ufku.ongoru_belirsiz`, `ongoru_belirsiz` bulgusu).
- **Kaynak:** Makale19 (CAT ~24–48 sa önceden öngörülebiliyor; öncesinde konum belirsizliği
  büyük), `ILGILI_CALISMALAR`'daki Kim vd. (2011) (beceri öngörü süresiyle düşüyor).
- **Katkısı:** Kullanıcı deneyimi ve dürüstlük. Canlı GFS +120 sa'e kadar kullanılıyor; 4 gün
  sonraki bir uçuş için TI1 konumunun güvenilmez olduğu söylenmiyor.
- **Uygulama yolu:** `planlama_ufku()` yanıtına `ongoru_suresi_saat` eklenir. 48 sa'i
  aşınca `ongoru_belirsiz` uyarısı ve brifing kartına bir satır eklenir: "Kalkıştan önceki
  48 saat içinde yeniden hesaplayın."
- **Etki:** Orta · **Efor:** Düşük
- **Risk ve bağımlılıklar:** 48 sa sınırı 4 vakalık bir çalışmadan geliyor; kalibre bir sınır
  değil, literatüre dayalı bir kural. Metinde öyle yazılmalı.

### Fikir 8. "Hafif = negatif" etiket duyarlılık analizi
- **Kaynak:** Makale21 (yalnız Null ve MOG kullanılmış), Makale23 (LGT-MDT ayrı sınıf).
- **Katkısı:** Doğruluk yorumu. Etiketimizde 0 = yok/hafif. Hafif raporlar sınır
  durumlardır ve AUC'yi aşağı çekebilir (tahmin).
- **Uygulama yolu:** Dondurma paketinde ek bir varyant: hafif raporlar negatiflerden
  çıkarılır, aynı günlerde AUC ve Peirce yeniden hesaplanır. Birincil sonuç değişmez, yalnız
  duyarlılık tablosu eklenir.
- **Etki:** Orta · **Efor:** Düşük
- **Risk ve bağımlılıklar:** Önceden `deney_protokolu.md`'ye "duyarlılık analizi" diye
  yazılmalı. Negatif sayısı azalır, güven aralıkları genişler.

### Fikir 9. Uyarı alanı oranı ve alan tabanlı tehdit skoru
- **Kaynak:** Makale23 (TTS = GPC / (GPF + GPO − GPC); fazla alan tahmini başlıca
  sorunlardan biri).
- **Katkısı:** Değerlendirme ve rota bağlantısı. Yüksek POD, her yeri "riskli" boyayarak da
  elde edilebilir. Bu durumda kaçınma bedeli de büyür.
- **Uygulama yolu:** Seçili eşikte ızgaranın ve rota noktalarının riskli oranı hesaplanır;
  "POD – uyarı alanı oranı" eğrisi çizilir. `ml/gosterge_degerlendirme.py`'ye bir fonksiyon
  ve sonuç paketine bir şekil eklenir.
- **Etki:** Orta · **Efor:** Düşük
- **Risk ve bağımlılıklar:** PIREP'ler seyrek olduğu için GPO (gözlenen alan) tam bilinemez;
  TTS'yi yalnız MADIS günlerinde vermek daha doğru.

### Fikir 10. Komşuluk maksimumuyla eşleştirme duyarlılığı
- **Kaynak:** Makale23 (Kanada AES: raporun önceki 10° segmentindeki en büyük değer).
- **Katkısı:** Doğruluk yorumu. PIREP konum ve zaman hatası nokta eşleştirmede becerinin
  bir kısmını kaybettirir.
- **Uygulama yolu:** `fizik/eslestirme.py`'de isteğe bağlı mod: ±1 hücre (0,25°) ve ±1 saat
  penceresinde TI1'in en büyüğü. Hem pozitif hem negatif örnekler için uygulanır; AUC farkı
  raporlanır.
- **Etki:** Orta · **Efor:** Düşük
- **Risk ve bağımlılıklar:** Pencere hem doğru hem yanlış alarmları büyütür; adil olması için
  iki sınıfa birlikte uygulanmalı ve önceden kaydedilmeli.

### Fikir 11. PIREP ayrıştırıcısını avwx-engine ile çapraz test
- **Kaynak:** R23 (avwx-engine, MIT, `avwx/current/pirep.py` ve test verileri).
- **Katkısı:** Veri kalitesi. Etiketimizi `pirep_siddet_sinifi` belirliyor: `SEV|EXTM`
  içeriyorsa 2, `MOD|MDT` içeriyorsa 1, yoksa 0. Geçmişte PIREP verisinde birim hatası
  yaşandı (FL feet).
- **Uygulama yolu:** IEM'den rastgele seçilen 500 ham PIREP iki ayrıştırıcıdan geçirilir;
  uyuşmazlık tablosu `docs/veri_hazirlama/` altına yazılır. avwx yalnız geliştirme
  bağımlılığı olarak eklenir ve yalnız test sırasında kullanılır.
- **Etki:** Orta · **Efor:** Düşük
- **Risk ve bağımlılıklar:** avwx'in IEM metin biçimini doğrudan ayrıştırıp ayrıştıramayacağı
  denenmedi (tahmin). Uyuşmazlık çıkarsa ve etiket değişirse bu bir dondurma sonrası işidir.

### Fikir 12. B planında OpenSky "hyperscaler" engelini önceden kontrol
- **Durum:** E-posta taslağı hazır (`docs/fizibilite/OPENSKY_BULUT_ERISIMI.md`); gönderim kullanıcıda.
- **Kaynak:** R16 README: "We may block AWS and other hyperscalers".
- **Katkısı:** Risk azaltma. B planında önerilen Azure for Students bir hyperscaler; taşıma
  yapıldıktan sonra OpenSky erişimi kesilirse gece işi durur.
- **Uygulama yolu:** B planı devreye girmeden önce bu kuralın Trino'ya da uygulanıp
  uygulanmadığı OpenSky belgelerinden ya da destek ekibinden öğrenilir. Hetzner için de
  aynısı yapılır. Bulgu `b-plani-sanal-sunucu` notuna eklenir.
- **Etki:** Orta · **Efor:** Düşük
- **Risk ve bağımlılıklar:** OpenSky'a yazmak bir dış iletişimdir; önce kullanıcı onayı gerekir.

### Fikir 13. Önerilen rota için ICAO FPL Madde 15 dizgisi
- **Durum:** Uygulandı (16 Ekim; `rota/fpl.py`, web brifing kartı). Düzeltme: iki koordinat
  noktası arasında DCT yazılmaz (aşağıdaki örnek yanlıştı; AIP ENR 1.10'dan doğrulandı).
- **Kaynak:** SIL_Makale5 (4B yörüngeyi uygulanabilir talimata çevirme), Makale20 (ACARS
  metin mesajı), R7 (bacak bazlı döküm).
- **Katkısı:** Kullanıcı deneyimi ve demo. Dispeçer, önerilen rotayı kopyalayıp planlama
  aracına yapıştırabilir.
- **Uygulama yolu:** Rota yanıtına `fpl_madde15` alanı eklenir. Örnek biçim:
  `N0450F350 DCT 4012N03015E DCT …`; FRA modunda nokta adları kullanılır, seviye değişimi
  `/N0450F370` olarak yazılır. "NON-OPERATIONAL" notu taşır.
- **Etki:** Orta · **Efor:** Düşük
- **Risk ve bağımlılıklar:** Kesin biçim ICAO Doc 4444 Ek 2'den doğrulanmalı. Burada
  yazılan örnek benim bilgime dayanıyor ve kaynaktan teyit edilmedi (tahmin).

### Fikir 14. Kullanıcı geri bildirim kaydı (E7 ile)
- **Durum:** Uygulandı (16 Ekim; migration `a7c3e9f1b2d4`, `-test` DB'de upgrade/downgrade denendi;
  E7 paketine iki soru).
- **Kaynak:** Makale20 (doğruluk ve yarar için pilot geri bildirim sitesi), Makale7 (anket,
  sonradan görüşme, omuz üstü gözlem).
- **Katkısı:** Kullanıcı deneyimi ve akademik değer. E7 kullanılabilirlik oturumlarına ölçülebilir
  çıktı sağlar.
- **Uygulama yolu:** `POST /api/v1/geri-bildirim` {rota/analiz kimliği, yararli_mi, dogru_mu,
  not}. E7 protokolüne NTDA tarzı iki soru ve SUS eklenir.
- **Etki:** Orta · **Efor:** Düşük
- **Risk ve bağımlılıklar:** Yeni tablo için migration gerekir: önce `-test` veritabanında
  upgrade/downgrade denenir, geliştirme veritabanı için ONAY alınır. Kişisel veri
  toplanmamalı.

### Fikir 15. TI3 (Ellrod–Knox DVT) göstergesi
- **Kaynak:** Makale11 (TI3 = TI1 + C·|div(t) − div(t−6 sa)|, C = 0,01), Makale1 (TI3 öne
  çıkan özellik), Ellrod ve Knox (2010) (`ILGILI_CALISMALAR`'da zaten var).
- **Katkısı:** Doğruluk. Antisiklonik akış ve atalet-çekim dalgası kaynaklı CAT'i de
  kapsar. Gerçek kazanç bizim verimizde ölçülmeden bilinemez.
- **Uygulama yolu:** `fizik/turbulans_indeksleri.py`'ye
  `ti3_indeksi_hesapla(ti1, diverjans_simdi, diverjans_6sa_once, katsayi=0.01)`
  eklenir. `yatay_diverjans_hesapla` zaten var. GFS'te 6 saatlik adım hazır; ERA5 pencere
  deposunda t−6 sa alınır. Değerlendirme yeni protokolle, dondurma sonrası günlerde TI1'e
  karşı yapılır.
- **Etki:** Orta · **Efor:** Orta
- **Risk ve bağımlılıklar:** ERA5 pencere deposunun t−6 saati içerip içermediği kontrol
  edilmedi (tahmin). C katsayısı ızgaraya bağlı olabilir. Rota kararına alınması ayrı bir
  karardır.

### Fikir 16. Kalkış saati penceresi karşılaştırması
- **Durum:** Uygulandı, yalnız bilgi (16 Ekim; `kalkis_penceresi: true`, web brifing kartı). S1 örneği:
  12Z'de normal rota 6,3 dk riskli, 13Z/14Z'de 0.
- **Kaynak:** R3 (`/api/compare`, kalkış pencereleri), Makale11 (günlük kalkış değişimi).
- **Katkısı:** Kullanıcı deneyimi. Dispeçere "2 saat sonra kalkılırsa riskli süre 18'den 4
  dakikaya iner" gibi bir seçenek sunar.
- **Uygulama yolu:** `rota_simulasyonu_olustur` kalkış için −3…+3 sa aralığında 7 kez
  çalıştırılır (rota başına 0,03–0,45 sn). Yanıta `kalkis_penceresi` [{fark_saat,
  riskli_sure_dk, sure_dk, yakit_kg}] eklenir ve arayüzde küçük bir tablo gösterilir.
- **Etki:** Orta · **Efor:** Orta
- **Risk ve bağımlılıklar:** SIGMET ufku (4 sa) ve GFS adımları sınırlı; uyarılar her
  pencerede ayrı verilmeli. Kalkış saati operasyonel olarak serbest değildir (slot).

### Fikir 17. Rota boyunca dikey kesit görünümü
- **Durum:** Uygulandı (16 Ekim; `rota/dikey_kesit.py`, web brifing kartında ısı şeridi; ek ~10 ms).
- **Kaynak:** Makale2 (AWRT Şekil 3), Makale20 (ASCII dikey kesit), Makale10 ("alan dikeyde
  derin, bu yüzden yanal kaçınma seçildi").
- **Katkısı:** Kullanıcı deneyimi ve sunum. Seviye değişimi mi, yanal sapma mı seçildiğini
  görsel olarak açıklar.
- **Uygulama yolu:** Arayüzde mesafe × FL ekseninde TI1 ısı şeridi, planlanan ve alternatif
  seviyeler çizilir. Veri mevcut küpten gelir (`arayuz/harita.py` ya da yeni bir panel).
- **Etki:** Orta · **Efor:** Orta
- **Risk ve bağımlılıklar:** Yalnız 3 basınç seviyesi (200/250/300 hPa) var; kesit kaba
  olur ve bu arayüzde yazılmalı.

### Fikir 18. Kaçınma manevrasının başlangıç zamanı analizi
- **Durum:** Fizibilite yapıldı: son ~8 gün için yapılabilir (`docs/fizibilite/KAYNAK_INCELEMESI_FIZIBILITE.md`).
- **Kaynak:** Makale10 (LTAR 1/2/3: +16 dk, 10 dk tasarruf, +2 dk).
- **Katkısı:** Akademik değer. Uçuş sırasında yeniden hesaplamanın değerini sayıyla gösterir
  (bizde şu an gösterim amaçlı).
- **Uygulama yolu:** Backtest ya da demo rotalarında kaçınma k. ara noktadan, o saatteki
  daha yeni GFS koşusuyla başlatılır ve kalkıştan başlatılan kaçınmayla karşılaştırılır.
- **Etki:** Orta · **Efor:** Orta
- **Risk ve bağımlılıklar:** Geçmiş GFS koşuları gerekir (THREDDS −48 sa sınırı).

### Fikir 19. Ek teşhisler: frontogenez, ∇T, NCSU1, negatif PV
- **Kaynak:** Makale8 (çoklu teşhis ve işaret uyumu), Makale21 (UBF, VOSQ, TEMPG, Brown2),
  Makale19 (WCB tipinde negatif PV, olayların ~%30'u).
- **Katkısı:** Doğruluk ve akademik değer. TI1'in kaçırdığı tip II olaylar yakalanabilir.
- **Uygulama yolu:** F9 "geniş özellik seti" protokolüne (zaten planlı: temel 8 + 5 bağlam)
  aday olarak yazılır. PV, 200/250/300 hPa'dan θ'nın düşey gradyanı ve mutlak vortisite
  ile hesaplanır.
- **Etki:** Orta · **Efor:** Orta
- **Risk ve bağımlılıklar:** 3 seviyeyle PV kaba olur (tahmin). Özellik sayısı arttıkça
  aşırı uyum riski büyür; önceden kayıt şart.

### Fikir 20. G-AIRMET ile ABD karşılaştırması
- **Durum:** Fizibilite: mevcut ML/MADIS günleriyle (2018–2020) örtüşme 0 gün (IEM arşivi Mart 2021'den);
  dondurma sonrası 2021+ günlerde yapılabilir.
- **Kaynak:** R21 (AWC G-AIRMET), Makale23 (1/3 alan örtüşmesi ölçütü).
- **Katkısı:** Değerlendirme. ABD günlerinde operasyonel bir ürünle kıyas yapılır (WAFS
  kıyası zaten "sonraki" listesinde).
- **Uygulama yolu:** `dogrulama/sigmet_dogrulama.py` deseniyle TI1 riskli alanları ile
  G-AIRMET türbülans poligonları karşılaştırılır.
- **Etki:** Orta · **Efor:** Orta
- **Risk ve bağımlılıklar:** AWC'nin geçmiş G-AIRMET arşivi sunup sunmadığı bilinmiyor
  (tahmin). Sağlayıcı sınırları önce okunmalı.

### Fikir 21. Maruziyet haritası: risk × trafik yoğunluğu
- **Kaynak:** R17 (hava yolu yoğunluk ısı haritası), Makale11 (rota başına CAT karşılaşma
  olasılığı), Makale8 (bölgesel artış).
- **Katkısı:** Sunum ve motivasyon. "Riskli alanlardan geçen uçuş oranı" gibi tek bir
  etkileyici şekil.
- **Uygulama yolu:** OpenSky Parquet önbelleğindeki izlerden ızgara yoğunluğu çıkarılır ve
  TI1 aşım sıklığıyla çarpılır; sonuç `docs/sonuclar`'a yazılır.
- **Etki:** Orta · **Efor:** Orta
- **Risk ve bağımlılıklar:** Türkiye için yalnız Ocak 2019 ERA5 var; genelleme yapılamaz.

### Fikir 22. opentop ile A* için bağımsız optimal-kontrol referansı
- **Kaynak:** R9 (özel 4B ızgara maliyeti), Makale22 (OpenAP.top ile optimum rota).
- **Katkısı:** Akademik doğrulama. A*'ın sürekli optimuma göre ne kadar alt-optimal olduğunu
  ölçer.
- **Uygulama yolu:** TI1 maliyet ızgarası (lon, lat, height, cost, ts) opentop interpolantına
  verilir; aynı kalkış-varış için `Cruise` yakıt + λ·ızgara amacıyla çözülür ve A*
  sonucuyla karşılaştırılır.
- **Etki:** Orta · **Efor:** Yüksek
- **Risk ve bağımlılıklar:** CasADi/IPOPT bağımlılığı ağır. Lisans NOASSERTION; dosyası
  okunmalı. λ seçimi A*'taki 6 saatlik ceza ile eşdeğer kurulmalı.

### Fikir 23. Mode S'ten türetilmiş rüzgârla model rüzgârı doğrulama
- **Durum:** Fizibilite: Trino `rollcall_replies_data4` mevcut; Türkiye kapsaması ve hacim için tek uçuşluk
  deneme gerekiyor (OpenSky girişi kullanıcıda).
- **Kaynak:** Makale16 (0,09 m/s, %51+ kapsama). F7 fizibilite notu.
- **Katkısı:** Doğruluk. Yakıt ve süre sonuçlarının dayandığı rüzgârın hatası ölçülür.
- **Uygulama yolu:** OpenSky Trino'daki Mode S yanıtlarından (BDS 5,0/6,0) TAS ve yön çıkarılır;
  rüzgâr = yer hızı vektörü − hava hızı vektörü. Örnek rotalarda ERA5/GFS ile
  karşılaştırılır.
- **Etki:** Orta · **Efor:** Yüksek
- **Risk ve bağımlılıklar:** EHS kapsaması Avrupa'da yoğun, Türkiye'de belirsiz (tahmin).
  Trino'da bu tabloların varlığı ve kotası kontrol edilmedi; ban riski kuralı geçerli.

### Fikir 24. AUC² ağırlıklı birleşik EDR
- **Kaynak:** Makale21 (Wᵢ = AUCᵢ² / ΣAUC², Kim ve Chun 2011).
- **Katkısı:** Küçük bir doğruluk kazancı olabilir. Bizde birleşik EDR eşit ağırlıklı
  (`fizik/edr_esleme.py`) ve TI1'e göre farkı zaten küçük (0,684'e karşı 0,671).
- **Uygulama yolu:** Ağırlıklar yalnız eğitim günlerindeki AUC'den hesaplanır ve
  `edr_esleme.py`'ye seçenek olarak eklenir.
- **Etki:** Düşük · **Efor:** Düşük
- **Risk ve bağımlılıklar:** Ağırlık seçimi test günlerine sızmamalı.

### Fikir 25. Türkiye/Avrupa CAT eğilim bağlamını rapora ekleme
- **Kaynak:** Makale8 (Orta Doğu ve KB Afrika'da 2 katından fazla artış), Makale15 (Avrupa'da
  net artış yok, güneyde daha yüksek), Makale6 (Çin klimatolojisi).
- **Katkısı:** Akademik bağlam. "Neden Türkiye?" sorusuna literatürden bir yanıt.
- **Uygulama yolu:** `ILGILI_CALISMALAR.md` §1'e bir paragraf eklenir.
- **Etki:** Düşük · **Efor:** Düşük
- **Risk ve bağımlılıklar:** Türkiye bu çalışmaların hiçbirinde ayrı bir bölge olarak
  analiz edilmemiş; ancak "komşu bölgeler" denebilir.

### Fikir 26. Eşik katılığı ailesiyle Pareto seçenekleri
- **Kaynak:** Makale11 (s97–s99.6 TOR ailesi).
- **Katkısı:** Kullanıcı deneyimi. "En sert %1'den kaçın" ile "%2'den kaçın" gibi seçenekler,
  saniye cinsinden cezadan daha kolay anlaşılır.
- **Uygulama yolu:** `ROTA_PARETO_CEZALARI_SANIYE` yerine ya da yanında, yüzdelik eşik
  düzeyleriyle A* çalıştırılır.
- **Etki:** Düşük · **Efor:** Düşük
- **Risk ve bağımlılıklar:** Fikir 2'nin yüzdelik altyapısına bağlı.

### Fikir 27. IWXXM Schematron doğrulaması
- **Kaynak:** R22 (resmi Schematron kuralları).
- **Katkısı:** Standart uyumu. XSD'nin kontrol etmediği iş kuralları (örneğin geçerlilik
  aralıkları) da sınanır.
- **Uygulama yolu:** Testte `lxml.isoschematron` ile SIGMET çıktısı doğrulanır.
- **Etki:** Düşük · **Efor:** Düşük
- **Risk ve bağımlılıklar:** Schematron sürümünün 2025-2 ile uyumu kontrol edilmeli.

### Fikir 28. Pareto seçeneklerinde MCDM "uzlaşma" etiketi
- **Kaynak:** R13 (`mcdm.py`, R-yöntemi).
- **Katkısı:** Kullanıcı deneyimi. Kullanıcının sırasına göre bir seçenek "uzlaşma" diye
  işaretlenir.
- **Uygulama yolu:** Pareto seçenek listesine sıra ağırlıklı bir puan ve etiket eklenir.
- **Etki:** Düşük · **Efor:** Düşük
- **Risk ve bağımlılıklar:** Tek bir "en iyi" önerisi, ödünleşimi gizleyebilir. Tüm seçenekler
  görünür kalmalı.

### Fikir 29. Uçak tipine duyarlı risk (OpenAP kanat yükü)
- **Kaynak:** Makale1 (aerodinamik özellikler %3,2 katkı, MOD-SEV POD +0,021), Makale2
  (uçağa özgü eşik), poster "Sonraki" listesindeki "uçak tipine duyarlı risk".
- **Katkısı:** Küçük bir doğruluk kazancı ve kabin uyarısını tipe göre ölçeklendirme.
- **Uygulama yolu:** BADA lisanslı olduğundan OpenAP `prop` kullanılır (kanat alanı, MTOW →
  W/S). `ml/tip_analizi.py` genişletilir; F9 protokolüne aday özellik olarak yazılır.
- **Etki:** Düşük · **Efor:** Orta
- **Risk ve bağımlılıklar:** PIREP tip kodlarının OpenAP tiplerine eşlenmesi eksik kalabilir.

### Fikir 30. M9 için Schmidt–Appleman ölçütü ve ±1 FL önerisi
- **Kaynak:** SIL_Makale9 (SAC), Makale17 (±2000 ft ile %70 önleme), SIL_Makale12, R5.
- **Katkısı:** Akademik doğruluk. Şu anki ölçüt (T ≤ −40 °C, RHi ≥ %100) basit bir vekil.
- **Uygulama yolu:** `fizik/iz_bulutu.py`'ye basınca ve itki verimine bağlı SAC eşik
  sıcaklığı eklenir. İz bulutu bölgesinde ±1 FL seçeneği bilgi amaçlı gösterilir.
- **Etki:** Düşük · **Efor:** Orta
- **Risk ve bağımlılıklar:** Formül birincil kaynaktan (Schumann 1996) alınmalı; burada
  yazılmadı. Proje odağı türbülans.

### Karar (16 Ekim, kullanıcı)

- Dondurma sonrası (`YAPILACAKLAR.md`'ye yazıldı): 4, 8, 9, 10, 11, 15, 19, 24, 29.
- Yapılmayacak: 21 (Türkiye verisi yetersiz), 22 (bağımlılık/lisans), 28 (tek "uzlaşma"
  etiketi ödünleşimi gizler).
- Sırayla uygulanacak: 2, 3, 5, 6, 7, 12 (e-posta taslağı), 13, 14, 16, 17, 18/20/23
  (önce fizibilite), 25, 26, 27, 30.

### 3.1 Zaten projede olanlar ya da bilinçli olarak önerilmeyenler

| Fikir | Kaynak | Durum |
|---|---|---|
| Rota boyunca "risk süresi" | Makale11 | Var: `riskli_sure_dk` |
| Düğüm bazlı varış zamanıyla tahmin dilimi seçme | R12, Makale4 | Var: A* `nominal_zamanlar` |
| SIGMET hareket vektörü | Makale5 | Var: `sigmet_saglayici._hareket` |
| Pareto zaman-risk seçenekleri | R6, R7, Makale7 | Var (2 Ekim) |
| Değerle birlikte güven/belirsizlik | Makale20 (EDC) | Var: konformal durum |
| Gün gruplu doğrulama, zamansal holdout | R5 | Var (ADR 0003) |
| Uçuş safhası ayrımı | R10 | Var: OpenAP `FlightPhase` |
| Denetimsiz ADS-B anomalisi | R2, R4 | Ölçüldü, ayırt edici çıkmadı |
| LLM ile uyarı metni | R2, R3 | Önerilmiyor: doğrulanamaz ve uydurma riski var |
| Uçak üstü sensör, edge AI | R1 | Kapsam dışı |
| Alçak irtifa / kentsel İHA yöntemleri | Makale9, 12, 13, SIL_14 | Kapsam dışı |
| Gemi rotası algoritmaları (izofuel, DP) | R13, R14, R15 | A* yeterli; yalnız yöntem fikirleri alındı |
| Çok uçaklı ayırma / oyun kuramı | Makale5, R9 | Kapsam dışı (ATC'nin yerini tutmaz) |

---

## 4. Erişilemeyen ya da tam okunamayan kaynaklar

| Kaynak | Durum |
|---|---|
| Makale23 (Ellrod ve Knapp 1992) | Metin katmanı yok (taranmış). Sayfalar 70–110 dpi görüntüye çevrildi; s. 1, 4, 5, 6, 7, 8 ve 15 okundu. s. 9–14 (vaka çalışmaları, şekiller) ayrıntılı okunmadı. |
| Makale19 (ETH doktora tezi, 234 s.) | Özet, §3.4.4 ve §4.5 okundu. Bölüm 5–6 (PV etkisi) yalnız içindekilerden. |
| Makale18 (Pretoria YL tezi) | Özet ve içindekiler okundu. "6.2 Limitations" bölümü metin çıkarımında bulunamadı; sınırlar yorumu tahmindir. |
| SIL_Makale3 (RMC YL tezi, 165 s.) | Özet ve sonuç okundu. |
| Diğer makaleler | Özet, yöntem, sonuç ve sayı içeren tablolar okundu; tüm şekiller ve ekler incelenmedi. |
| Makale2, Makale20 | Yıl metinde açık değil; ~2007 ve ~2008 olarak verildi (tahmin). |
| Makale7 | Konferans adı metinde okunamadı. |
| R1 ASTRIA-CAT | `ASTRIA-CAT_Technical_Whitepaper.pdf` okunmadı. |
| R5 AeroContrail | 5 MB'lık defter (notebook) açılmadı; README'ye dayanıldı. |
| R2, R4, R17–R19 | Ön yüz kodları okunmadı; README ve dosya ağacı esas alındı. |
| R13 52North | Belgelendirme sitesi okunmadı; kod dosyaları okundu. |
| Tüm depolar | Hiçbiri çalıştırılmadı ya da test edilmedi. |
| `makale_ozet.txt` | 28 dosyalık eski numaralandırmaya göre yazılmış; artık güncel değil. |

Erişilemeyen bir depo ya da açılamayan bir PDF yok: 23/23 depo ve 28/28 PDF'e erişildi.
