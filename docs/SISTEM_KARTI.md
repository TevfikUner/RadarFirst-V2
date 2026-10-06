# Türbülans Radar — Sistem Kartı

Bu kart, sistemin ne yaptığını, hangi veriye güvendiğini, hata durumlarında
nasıl davrandığını ve bilinen sınırlarını tek yerde toplar. Buradaki tüm
sayılar depodaki kod, testler ve belgelenen doğrulama çalıştırmalarıyla
üretilmiştir.

## 1. Amaç ve kullanım sınıfı

Türbülans Radar, uçuş planlama için **tavsiye niteliğinde (advisory)** bir
karar destek sistemidir. Sistem üç işi yapar:

1. Bir uçuş rotasını hava durumu verisiyle eşleştirip açık hava türbülansı
   (CAT) göstergelerini hesaplar.
2. Aktif SIGMET'leri sert kısıt olarak uygulayarak türbülanstan kaçınan
   alternatif bir rota önerir.
3. Önerilerini gerçek uçuş izleriyle otomatik olarak karşılaştırır.

**Kapsam:** Rota önerisi yalnızca **seyir (en-route) safhası** içindir. Başlangıç
ve bitiş seyre giriş (ToC) ve seyirden çıkış (ToD) noktası kabul edilir; kalkış,
tırmanış, alçalış, SID/STAR ve yaklaşma kapsam dışıdır. Rota, ATS yolları yerine
büyük daire etrafındaki bir koridorda aranır. İsteğe bağlı olarak yüklü bir
ATS yolu/FRA ağında da aranabilir (`arama_uzayi="ats"`; ağ AIP'ten elle hazırlanır).
Diğer trafikle ayırmayı dikkate almaz; ATC talimatlarının yerini tutmaz. Geçmiş
trafikle varsayımsal minima karşılaştırması yalnızca gösterge olarak vardır
(`turbulans-ayirma`). Her rota yanıtı kapsamı `kapsam` alanında taşır.

**Kullanım zamanı:** Birincil kullanım uçuş öncesi planlamadır.
- Rüzgar ve TI1 için canlı NOAA GFS tahmini, kalkıştan en fazla 120 saat önceye
  kadar kullanılabilir.
- SIGMET'ler kısa geçerlilikle yayımlandığı için (varsayılan ufuk 4 saat,
  `SIGMET_YAYIN_UFKU_SAAT`), uçuşun bu ufkun ötesindeki kısmında "aktif SIGMET
  yok" sonucu güvence değildir. Yanıt bu durumda `sigmet_ufuk_disi` uyarısı verir.
- Kalkıştan önceki son saatlerde yeniden hesaplanmalıdır.
- Hesaplama süresi, veri hazırken rota başına 0,02–0,27 sn'dir
  (`docs/hoca_geri_bildirim_analizi.md` §3).
- Uçuş sırasında yeniden hesaplama mekanizması gösterim amaçlıdır.

Sistem **sertifikalı değildir**. Herhangi bir EFB onayı yoktur ve
operasyonel karar yetkisi pilotta ve dispeçerdedir. Üretilen değerler
gerçek bir uçuşta tek bilgi kaynağı olarak kullanılamaz.

## 2. Veri kaynakları

| Kaynak | İçerik | Tazelik / çözünürlük | Kapsam | Sistemdeki yeri |
|---|---|---|---|---|
| OpenSky (Trino) | Uçuş state vector'leri (konum, irtifa) | Tarihsel; ~1 sn örnekleme | ADS-B alıcı ağına bağlı; boşluklar olabilir | `veri/veri_yukleme.py` |
| Dışarıdan ADS-B izi | Aynı içerik, kullanıcının yüklediği | — | — | `POST /api/v1/analiz/rota` |
| Copernicus ERA5 | u, v, t (200/250/300 hPa) | Reanaliz, ~5 gün gecikmeli; 0.25°, 1 saatlik | Yerel küpler: Türkiye (Ocak 2019), Kuzeydoğu ABD (2018-2020 seçili günler) | `veri/veri_yukleme.py` |
| NOAA GFS (UCAR THREDDS) | u, v, t (200/250/300 hPa) | Tahmin; 0.25°, 3 saatlik adım, 6 saatlik döngü | Küresel; şimdi −48 sa / +120 sa | `veri/veri_saglayicilari.py` |
| AWC SIGMET (`airsigmet`, `isigmet`) | Tehlike poligonu, irtifa bandı, geçerlilik | Canlı (API zamanlayıcısı 15 dakikada bir yeniler) | ABD + AWC'ye ulaşan uluslararası mesajlar (Ankara FIR dahil) | `veri/sigmet_saglayici.py` |
| Kısıtlı hava sahaları (GeoJSON) | Çatışma bölgesi, P/R/D sahası, NOTAM'lı geçici kısıt: poligon, irtifa bandı, geçerlilik | Operatörün içe aktardığı kadar güncel | Paketle gelen örnek: Suriye ve Irak (Natural Earth ülke sınırı, resmi değil) | `veri/kisitli_saha_saglayici.py` |
| IEM PIREP | Pilot türbülans raporları | Tarihsel | ABD | Yalnızca ML eğitimi ve kalibrasyon |
| NOAA MADIS (public) | Uçağın ölçtüğü EDR (maks/medyan) | Tarihsel, QC'siz ön veri ('Z') | ABD ağırlıklı, küresel | Nesnel türbülans etiketi ve PIREP doğrulaması (ADR 0012) |
| Sanal PIREP (M6) | ADS-B izinden seyir fazı irtifa sapması | Analiz edilen iz ya da havayolu beslemesi kadar taze | İzin kapsadığı yer | `fizik/sanal_pirep.py`; canlı olay sensörü, ML etiketi değil |

## 3. Karar mantığı

- **Türbülans göstergeleri:** Ellrod TI1 (dikey rüzgar kayması × yatay
  deformasyon) ve bulk Richardson sayısı. Bir nokta, TI1 değeri
  `TI1_ESIK_ORTA_SIDDETLI` (8e-7 s⁻²) eşiğini aşarsa "riskli" sayılır.
- **Rota adayları:**
  - A* ile yanal sapma: büyük daire etrafında 41 ara nokta; her bacağın büyük
    daire yönüne göre açısı en fazla 30°, toplam sapma en fazla 400 km, ızgara
    aralığı en fazla 20 km (kısa rotada açı sınırına göre daralır). Sapma
    uçlarda kendiliğinden kademeli sınırlanır.
  - Aynı yönün bir üst ya da bir alt yasal FL'sine geçiş (yarım daire kuralı,
    RVSM, tip tavanı; manyetik sapma sabit +5°E varsayımı): geçici seviyeye
    gidiş ve planlanan seviyeye dönüşün yaklaşık yakıt bedeli hesaba katılır
    (alçalmaya kredi yok; seviyeye bağlı seyir yakıt akışı modellenmez).
    Kurala aykırı girilen seviye en yakın yasal FL'ye yuvarlanır, uyarı verilir.
- **Öncelik sırası:**
  1. Aktif SIGMET'e ve kısıtlı/yasak hava sahasına **girmemek** (sert
     kısıtlar). Kısıt dört boyutludur: poligon, irtifa bandı, uçağın o
     noktaya varış zamanındaki geçerlilik ve iki nokta arasındaki bacağın
     poligonu kesmesi. A* varış zamanını rüzgarsız hesapladığı için geçerlilik,
     geçen sürenin %30'u + 5 dk belirsizlik payıyla kontrol edilir. Kalkış ya da varış noktasını içeren kısıtlı saha
     (örn. varış ülkesi) muaf tutulur ve raporlanır.
  2. Riskli TI1 noktalarından kaçınmak (yumuşak kısıt, 6 saatlik sanal ceza).
  3. En düşük yakıt/süre.
- Kaçınılacak bir risk yoksa önerilen rota büyük daireyle birebir aynıdır;
  uydurma bir "iyileşme" gösterilmez.
- **Sanal PIREP (gözlem kanalı):** Seyirdeki uçağın atanmış seviyesinden
  ≥ 90 ft sapması (düşey hız tepkisiyle birlikte) olay sayılır; en az 2 farklı
  uçağın 50 km / ±2000 ft / ±60 dk içinde doğruladığı olay `/ws/uyarilar`'a
  gider. Rota kararına girmez; dispeçere bilgi verir. Sapma ham büyüklüktür,
  EDR ya da şiddet sınıfı değildir; eşikler kalibre edilmemiştir (ADR 0011).

## 4. Hata durumlarında davranış (fail-safe)

| Durum | Sistemin davranışı |
|---|---|
| SIGMET'e ve kısıtlı sahalara girmeyen geçerli bir rota yok (örn. varış noktası SIGMET içinde, koridoru kesen bir yasak saha) | **Öneri yapılmaz**: `guvenli_rota_bulundu_mu: false`, açıklamada "ÖNERİ YOK", normal rota gösterilir. |
| Kısıtlı saha kalkış ya da varış noktasını içeriyor (örn. varış ülkesi) | Sahada sadece planlı rotanın ±100 km koridoru serbest bırakılır, geri kalanı kısıt olarak uygulanır; `muaf_tutulanlar`'da raporlanır. |
| Kısıtlı saha veritabanına erişilemiyor | Rota hesaplanır; `kisitli_saha_kontrolu.durum = "erisilemedi"` ve açıklamada UYARI yer alır. |
| Kullanılan kısıtlı sahalar paketle gelen örnek veriden | `kisitli_saha_kontrolu.ornek_veri_mi: true` ve açıklamada NOT. |
| SIGMET veritabanına erişilemiyor | Rota hesaplanır; `sigmet_kontrolu.durum = "erisilemedi"` ve açıklamada UYARI yer alır. |
| Canlı bir hesapta SIGMET kaynaklarından birinin son BAŞARILI çekimi 30 dakikadan eski | `sigmet_kontrolu.bayat_mi: true`, `sorunlu_kaynaklar` doldurulur, açıklamada kaynak adıyla UYARI. |
| AWC'nin bir uç noktası yanıt vermiyor | Diğer kaynak işlenir; yanıt vermeyen kaynağın mevcut kayıtlarına dokunulmaz. |
| AWC akışı boş, liste değil ya da SIGMET'lerinin %25'inden fazlası çözümlenemiyor (şema değişikliği) | Kaynak hatası sayılır: mevcut SIGMET'ler sonlandırılmaz, `kaynak_hatalari` doldurulur, kaynak başarılı güncelleme almaz (bayatlık uyarısı devreye girer). |
| Tek SIGMET'te birden fazla poligon (`geom: "AREAS"`) | Her alan ayrı kayıt olarak saklanır ve uygulanır. |
| SIGMET koordinatsız geldi (örn. "ENTIRE FIR") | FIR sınır verisi varsa ve FIR kodu biliniyorsa alan FIR'ın TAMAMINA genişletilir (muhafazakâr); yoksa eski davranış (eleme). Bu genişletme şema-uyuşmazlığı eşiğinde çözümlenemeyen gibi sayılır. |
| SIGMET'in geçerlilik başlangıcı geçersiz (AWC'de görülen `validTimeFrom=0`) | Başlangıç ham metindeki `VALID ddhhmm/ddhhmm` alanından, o da yoksa bitiş − 4 sa'ten türetilir; bağımsız kanıtta arşiv başlangıcı kaydın alınma zamanından en fazla 12 sa geriye gider (1970 tarihli kayıt 2019 uçuşlarını sahte biçimde 'kapsıyordu'). |
| SIGMET'in irtifa bandı ya da tehlike türü okunamıyor | Bant genişletilir (taban yer, tavan sınırsız); tehlike `BILINMIYOR` olur ve her zaman kaçınılır. |
| Bir SIGMET iptal edildi (canlı akıştan düştü) | Geçerliliği o an sona erdirilir; artık rotayı saptırmaz. |
| AWC'den geçersiz (kendini kesen) ya da 180° boylamını kesen bir SIGMET poligonu geldi | Geometri onarılır/bölünür; yalnızca gerçek alan yasaklanır. |
| İstenen irtifa canlı sağlayıcının basınç seviyelerinin dışında (örn. FL100) | İndirme yapılmaz; rota/tahmin hava verisi olmadan (kapsam dışı olarak) döner. |
| Canlı veri sağlayıcısı bozuk ya da geçersiz yanıt döndü | `POST /veri/canli/hazirla` görevi `hata` olur, genel bir mesajla (iç ayrıntı sızdırılmaz); rota/tahmin hava verisi olmadan devam eder. |
| Toplu backtest'te bir uçuş beklenmeyen hatayla düştü | O uçuş `hata` olarak raporlanır, diğerleri işlenmeye devam eder. |
| Hava verisi yok (bölge, tarih ya da irtifa kapsam dışı) | Rota rüzgarsız, sadece TAS ile hesaplanır ve TI1 raporlanmaz; bu durum açıkça belirtilir. SIGMET ve kısıtlı saha kısıtları yine uygulanır. |
| Canlı GFS sağlayıcısı yanıt vermedi | Aynı rüzgarsız hesap; ama `ruzgar_verisi_kaynagi: canli_veri_alinamadi` ve açıklamada UYARI ("kapsam dışı" denmez). Sonuç `veri_kaynagi_durumlari`'na yazılır, `/saglik?derin=true` `canli_gfs: hata` gösterir. |
| Canlı GFS uzun süredir başarıyla indirilemiyor (sağlayıcı kesintisi) | Docker'da API zamanlayıcısı `CANLI_ISITMA_SAAT` (6 sa) aralıkla Türkiye kutusunu önceden hazırlatır; `SAGLIK_GFS_BOSTA_SAAT`'ten (24 sa) eski başarıda `/saglik?derin=true` `canli_gfs: bayat` ve genel `bozulmus` döner (6 Ekim 2026 denetiminde UCAR 6 gün yanıtsız kalmış, fark edilmemişti). |
| Canlı GFS indirmesi 8 sn'de bitmedi (yavaş ağ) | Rota/tahmin beklemeden rüzgarsız ön sonuç döner (`canli_veri_hazirlaniyor`, SIGMET ve kısıtlı sahalar uygulanmış); indirme arka planda sürer, sayfa hesabı kendiliğinden tekrarlar. |
| SIGMET bayat, bir veri kaynağı hata veriyor ya da görev kuyruğu birikiyor | `/saglik?derin=true` genel durumu `bozulmus` döner (HTTP 200; monitoring gövdeye bakar). |
| Kokpitte bağlantı zayıf ya da yok | Kütüphaneler API sunucusundan gelir; altlık harita yerel (NaturalEarthII / ülke sınırları). Sadece Esri karoları eksik kalır. |
| Bir noktanın irtifası/zamanı küpün seviyelerinden ya da zaman adımlarından uzak | O nokta için TI1 NaN bırakılır; en yakın hücreden uydurma değer üretilmez. |
| Analiz sonucu veritabanına yazılamadı (API) | Görev `hata` durumuna geçer; "tamamlandı" gösterilmez. |
| API ya da işçi görev bitmeden yeniden başladı/çöktü | Kuyruktaki görevler kaybolmaz. Çalışan görevin kalp atışı kesilir; `GOREV_BAYAT_SANIYE` (120 sn) sonra görev yeniden kuyruğa girer, `GOREV_MAKS_DENEME` (2) aşılırsa `yarida_kaldi` olur. API'nin yeniden başlaması başka süreçteki işçinin görevine dokunmaz. |
| Webhook adresi iç ağa (localhost, 10.x, bulut metadata) işaret ediyor ya da oraya çözümleniyor | İstek 422 ile reddedilir; gönderim anında çözümlenen IP iç ağdaysa gönderilmez (izin listesindeki host'lar hariç). |
| Uzun ya da ağır bir iş (toplu analiz, yavaş ağda GFS indirme) | API'yi bloklamaz: iş kuyruğa girer, en fazla `GOREV_ISCI_SAYISI` iş aynı anda çalışır. |

## 5. Bilinen sınırlamalar

**Fiziksel gösterge**
- Kapsam yalnızca açık hava türbülansıdır (CAT). Konvektif, bulut içi, dağ dalgası
  ve iz türbülansı kapsam dışıdır; yalnız seyir safhası (FL280 üstü) değerlendirilir.
- EDR tahmini (birleşik EDR, `fizik/edr_esleme.py`) sertifikalı bir EDR değeri
  değildir: TI1, TI2, VWS, DEF ve 1/Ri log-normal eşlemeyle (Sharman & Pearson
  2017; C1 = −2,953, C2 = 0,602) EDR'ye çevrilip ortalanır; göstergelerin
  klimatolojisi ABD PIREP pencerelerinden gelir. Katsayı dosyası yoksa TI1'in
  tanh ölçeği yedek olarak kullanılır.
- ERA5/GFS'nin ~25-30 km çözünürlüğü küçük ölçekli türbülansı çözemez.
- Düşey rüzgar kayması ve Richardson sayısı uçağın basıncını çevreleyen tek
  katmandan hesaplanır (ERA5 varsayılanı 350–150 hPa, 7 seviye; jet çevresinde
  25 hPa ≈ 700 m); katman kalınlığı hipsometrik denklemle, deformasyon ve
  diverjans küresel metrik terimleriyle hesaplanır. Canlı GFS küpü 3 seviyeyle
  indirildiği için orada katman 50 hPa'dır.
- Hava verisi zaman ve konumda en yakın ızgara noktasından okunur,
  enterpolasyon yapılmaz: GFS'in 3 saatlik adımında 1,5 saate, 0,25°
  ızgarada ~0,125°'ye kadar kayma olabilir.
- Küp sınırının 0,125° dışına kadar (zamanda 3 saate kadar) noktalar kapsam
  içi sayılır ve kenar değerini alır.
- Seyir irtifasındaki 6218 PIREP'te (64 gün) TI1'in tek başına ayırt
  ediciliği orta düzeydedir (ROC-AUC 0,67 [0,65–0,69]; zamansal holdout'ta
  0,71, `TI1_ESIK_ORTA_SIDDETLI`'de POD 0,49, POFD 0,16). Fizik düzeltmesinden
  önce aynı örneklerde 0,64'tü; eski 0,44 değeri 300-400 feet'teki PIREP'leri
  seçen hatalı bir irtifa filtresinden geliyordu. Ayrıntı: `docs/rapor/SONUCLAR.md`. Bu, tek başına KANITLANMAMIŞ bir gösterge olduğu anlamına
  gelir; bu not (`TI1_GUVENILIRLIK_NOTU`, bkz. `fizik/turbulans_indeksleri.py`)
  artık `POST /simulasyon/rota` ve `POST /turbulans/tahmin` yanıtlarında ayrı
  bir alan olarak (`ti1_guvenilirlik_notu`) ve iki web arayüzünde de
  gösteriliyor -- bugün rota güvenliğinin gerçek garantisi TI1'den değil
  SIGMET sert kısıtından geliyor (bkz. "Bağımsız kanıt" bölümü, PUE502 uçuşu).
- EDR ölçekleme katsayısı 0.27'dir (Madde 2 fiziğiyle, gün bazlı bootstrap
  %95 GA [0.25, 0.28], 6218 PIREP / 64 gün; önceki 0.40 eski fizikle). Tanh
  ölçeği sabit ortalama tahmininden daha iyi tahmin etmez (test MSE 0.076 vs
  0.067); görselleştirme ölçeğidir. Birleşik EDR log-normal eşlemeyi kullanır,
  tanh yalnızca yedektir.

**ML sınıflandırıcısı**
- Aktif model (Random Forest, 5 Ekim 2026) doğru irtifalı PIREP'lerle eğitildi ve
  holdout'ta TI1'i geçti (bkz. `docs/rapor/SONUCLAR.md`). Yeni aday her gece
  eğitilir ve yalnızca holdout'ta TI1 referansını ve aktif modeli geçerse aktifleşir.
- Olasılık, "PIREP verilmiş bir noktada orta+ türbülans" oranına göredir
  (PIREP'lerde pozitif oran ~%52, MADIS ölçümlerinde hafif+ ~%3): raporlama
  yanlılığı nedeniyle mutlak sıklık olarak okunmamalıdır.
  TI1'i geçmek için ROC-AUC farkı hem `ML_TI1_AUC_USTUNLUGU`'nu aşmalı hem de
  gün bazlı eşleştirilmiş bootstrap aralığının alt sınırı 0'ın üstünde
  olmalıdır (holdout her gece yeniden kullanılır). Aday, gün gruplu CV
  ROC-AUC'siyle seçilir; özellikler TI1, Richardson, rüzgar hızı, basınç,
  düşey kayma, deformasyon, diverjans ve TI2'dir.
- Yalnızca ABD verisiyle doğrulanmıştır. `ml_riski_var_mi` için olasılık eşiği
  `ML_KARAR_ESIGI` (varsayılan 0.5) ile yapılandırılır.
- Konformal belirsizlik: yeni veri hattıyla eğitilen her model bir konformal
  eşikle saklanır; `POST /turbulans/tahmin` olasılığın yanında
  `ml_risk_durumu` (`dusuk_risk` / `yuksek_risk` / `belirsiz`) döner. Hedef
  kapsama %90'dır (`ML_KONFORMAL_ALFA` = 0.10); gerçekleşen kapsama zamansal
  holdout'ta ölçülüp sürüm kaydına yazılır. "Belirsiz", verinin bu güven
  düzeyinde iki sınıfı ayırmaya yetmediği anlamına gelir; güvenli demek değildir.
- Ek bir işaret olarak raporlanır; rota kararına girmez.

**Rota modeli**
- Seyir irtifası sabittir; kalkış ve iniş fazları modellenmez.
- Bacak açısı büyük daire yönüne göre sınırlanır; ardışık iki bacak arasındaki
  dönüş en fazla bunun iki katıdır (60°). Dönüş yarıçapı modellenmez.
- Uçak performans değerleri (TAS, yakıt akışı) tipik, halka açık değerlerdir.
- Hava yolu yapısı ve ATC kısıtları modellenmez. Kısıtlı/yasak sahalar ve
  NOTAM'lı geçici kısıtlar yalnızca içe aktarıldıkları kadar bilinir; paketle
  gelen örnek veri (Suriye, Irak) ülke sınırından türetilmiştir, resmi FIR/CZIB
  sınırı değildir.

**SIGMET**
- 180° boylamını (antimeridyen) kesen poligonlar -180..180 aralığında
  ikiye bölünerek uygulanır; kendini kesen (geçersiz) halkalar onarılır.
  Rotanın kendisi 180° boylamını kesiyorsa (Pasifik geçişleri) desteklenmez;
  istek 400 ile reddedilir (sonuç güvence sayılamayacağı için hesaplanmaz).
- Hareketli SIGMET'ler bildirilen yön/hızla doğrusal kaydırılır (şekil
  değişimi, "INTSF/WKN" yoğunlaşma/zayıflama modellenmez); hızı bilinmeyenler
  0-30 kt aralığında süpürülür. 3D sahne alanı yayın anındaki konumunda çizer.
- İptal tespiti, SIGMET'in canlı akıştan düşmesine dayanır.
- Buzlanma (ICE) varsayılan kaçınma setinde yoktur
  (`SIGMET_KACINILACAK_TEHLIKELER` ile eklenebilir).
- Uluslararası kapsam, AWC'ye ulaşan mesajlarla sınırlıdır.
- FIR sınır verisi (VATSIM vatspy-data-project, CC BY-SA 4.0) simülasyon
  topluluğunun güncel tuttuğu yaklaşık çizimlerdir, resmi AIP sınırı değildir;
  `turbulans-statik` çalıştırılmazsa hiç yoktur.

**GFS**
- UCAR THREDDS ücretsiz bir akademik servistir; hizmet düzeyi garantisi (SLA)
  yoktur.
- Zaman adımı 3 saattir; yeni bir döngü birkaç saat gecikmeyle yayınlanır.

**Backtest**
- Bağımsız kanıt (TURB SIGMET, PIREP) yalnızca kapsanan uçuşlarda vardır:
  sistemin SIGMET arşivi başladıktan sonraki uçuşlar ve ABD hava sahası.
  IEM SIGMET arşivinde irtifa bandı yoktur (tüm irtifalar sayılır).
- Şu anki sonuçlar 3 gerçek uçuşun 100-260 km'lik seyir bölümlerine
  dayanır. Bölümlerin kısa olmasının nedenleri OpenSky kapsama boşlukları ve
  küp sınırıdır. Sonuçlar istatistiksel bir kanıt değil, doğrulama hattının
  çalıştığının gösterimidir.

**İşletim**
- Hız sınırı sayaçları PostgreSQL'dedir (tüm API süreçleri paylaşır);
  veritabanına ulaşılamazsa sınır atlanır (fail-open).
- Anahtarsız `/saglik?derin=true` yalnızca kontrol başına durumu verir;
  ayrıntı (zamanlar, hata metinleri) `GET /api/v1/sistem/durum`'dadır.
  Gece işi ve yedek tazeliği uyarı düzeyinde raporlanır.
- İşçi durdurulunca çalışan görevi 240 sn bekler; ML gece işi süren CDS
  isteğini bitirip `yarida_kaldi` olarak durur.
- Görev kuyruğu PostgreSQL'dedir; işçiler 1 sn aralıkla yoklar (kuyruğa
  giriş ile başlama arasında ~1 sn gecikme).
- API/kuyruk üzerinden tetiklenen analizler (`/analiz/ucus`, `/analiz/rota`,
  `/analiz/toplu`) HTML harita üretmez (sonuç PostgreSQL'de, `GET
  /ucuslar/{ucus}/{tarih}` ile okunur); harita yalnızca CLI'dan
  (`turbulans-analiz`, `turbulans-toplu-analiz`) üretilir.

## 6. Doğrulama durumu

- **Otomatik testler:** 825 test (6 Ekim 2026; 2'si gerçek dış servise
  istek attığı için varsayılan çalıştırmada hariç), kod kapsamı ~%86. Kapsamı: birim testleri, gerçek PostgreSQL
  üzerinde API, depo ve görev kuyruğu testleri (eşzamanlı işçiler, ölen işçi
  kurtarma, LISTEN/NOTIFY), gerçek ERA5 küpüyle eşleştirme ve rota testleri,
  Playwright ile iki web önyüzünün tarayıcı testleri. Ağa çıkan bileşenler
  (GFS, AWC, IEM, npm) testlerde sahte sağlayıcılarla çalışır.
- **Eşdeğerlik testleri:** Vektörleştirme ve risk katmanı yeniden
  düzenlemelerinden sonra ML özellikleri ve örnek rotalar eski kodla birebir
  aynı çıktı.
- **Şema:** Her Alembic migration'ı boş bir veritabanında upgrade/downgrade
  ve ORM modelleriyle şema karşılaştırması yapılarak doğrulandı.
- **Canlı doğrulama (26 Eylül 2026):**
  - AWC'den 126 SIGMET alındı.
  - Aktif Ankara FIR fırtına SIGMET'inden Malatya → Musul yönü rotası 20 km
    yanal sapmayla kaçındı.
  - Varışı SIGMET içinde kalan bir rota için "öneri yok" döndü.
  - Türkiye bölgesi için GFS küpü ~15 saniyede indi, ikinci istek katalogdan
    anında geldi.
  - AWC uluslararası akışında daha önce sessizce atılan `geom: "AREAS"` (çok
    poligonlu) biçimi bulundu; düzeltmeden sonra 110 SIGMET'in tamamı
    çözümlendi.
  - Malatya → Musul (örnek kısıtlı saha verisi): büyük daire Suriye'yi 13
    nokta/bacakta kesiyor; A* 60 km sapmayla kaçındı, Irak (varış ülkesi) muaf.
  - A* (mesafe/açı tabanlı ızgara): İzmir-Van 38-58 ms, tam rota kararı
    0.26-0.29 sn; İstanbul-New York 1481 düğüm, 70 ms.
  - Çok süreçli kurulum (API + ayrı işçi süreci): rota analizi isteği 78 ms'de
    202 döndü, işçi analizi 0.5 sn'de bitirdi, riskli nokta uyarısı NOTIFY ile
    WebSocket istemcisine ulaştı.
  - Tüm dış ağ engelliyken iki web önyüzü de açıldı (CesiumJS yerelden 1.7 sn;
    CDN'den ~55 KB/s bağlantıda 106 sn sürüyordu); altlık harita yerel.
  - Küp belleği: İzmir-Van için pencereli okuma 1.2 MB (tüm küp 69 MB); eski
    davranış ilk istekte 16 küpü (92 MB) belleğe alıyordu.
- **Backtest (15 Ocak 2019, ERA5):** Riskli nokta oranı, gerçek uçuşlarda
  ortalama 0.28, önerilen rotalarda 0.00. Üç uçuşun ikisinde risk tırmanma
  ile azaldı; büyük daireye göre ek süre 2-5 dakika. Bu ölçüm döngüseldir
  (A* TI1'i düşürür, başarı TI1 ile ölçülür); bu uçuşlar için bağımsız kanıt
  kaynağı yoktur.
- **Bağımsız kanıtlı backtest (26 Eylül 2026, canlı GFS):** Gerçek bir
  uçuşta (PUE502, Brezilya, FL350) aktif TURB SIGMET maruziyeti gerçek iz 30,
  büyük daire 28, A* 33 nokta/bacak; TI1 üç rotada da risk görmedi. TI1
  katmanı bu olayı yakalamadı; SIGMET sert kısıtı canlı kullanımda bunu
  telafi eder, ama TI1'in tek başına bağımsız becerisi şimdilik
  kanıtlanmamıştır.

- **Sanal PIREP (M6, 1 Ekim 2026):** Tespit sentetik izlerle (seyir, sapma,
  transponder sıçraması, kademeli tırmanış, veri boşluğu) ve gerçek THY322
  iziyle test edildi; gerçek izde tırmanış ve iki büyük irtifa hatası yanlış
  alarm üretmedi.
- **Sanal PIREP POD/POFD (2 Ekim 2026, ilk küçük ölçüm):** 20 seyir PIREP'i
  (10 orta ve üstü, 10 yok/hafif), her biri için OpenSky'dan çevresindeki ADS-B
  izleri (±30 dk); 4'ünün çevresinde ADS-B verisi yoktu. POD 1/8 = 0,13 (%95
  Wilson 0,02–0,47), POFD 0/8 = 0 (0–0,32). Örneklem çok küçük, aralıklar geniş.
  Tanı: PIREP tüpündeki seyir uçaklarının çoğunda sapma 0–50 ft (ADS-B 25 ft
  adımları); 1000–3000 ft'lik irtifa sıçramaları düşey hız kontrolüyle elendi.
  Dedektör bu haliyle tutucudur (yanlış alarm görülmedi, yakalama düşük);
  eşikler bu örneklemle ayarlanmadı.

**Erişim**
- İki statik anahtar (yönetici, pilot); kullanıcı başına kimlik, süre sınırlı
  oturum ve denetim kaydı yok. Çok kullanıcılı bir filo için OAuth2/OIDC gerekir.

## 7. Uygun olmayan kullanımlar

- Gerçek bir uçuşta operasyonel kararın tek dayanağı olarak kullanmak.
- TI1/EDR proxy değerlerini sertifikalı EDR ölçümü yerine koymak.
- ML metriklerini, doğrulanmadığı bölgelere (örn. Türkiye) genellemek.
- Yönetici anahtarını kokpitteki cihaza koymak (pilot anahtarı kullanılmalı).
- SIGMET kontrolü "erişilemedi" ya da "bayat" durumundayken önerilen rotayı
  SIGMET'ten arındırılmış saymak.
