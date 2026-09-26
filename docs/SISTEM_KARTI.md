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
| AWC SIGMET (`airsigmet`, `isigmet`) | Tehlike poligonu, irtifa bandı, geçerlilik | Canlı (API zamanlayıcısı ya da n8n ile yenilenir) | ABD + AWC'ye ulaşan uluslararası mesajlar (Ankara FIR dahil) | `veri/sigmet_saglayici.py` |
| IEM PIREP | Pilot türbülans raporları | Tarihsel | ABD | Yalnızca ML eğitimi ve kalibrasyon |

## 3. Karar mantığı

- **Türbülans göstergeleri:** Ellrod TI1 (dikey rüzgar kayması × yatay
  deformasyon) ve bulk Richardson sayısı. Bir nokta, TI1 değeri
  `TI1_ESIK_ORTA_SIDDETLI` (8e-7 s⁻²) eşiğini aşarsa "riskli" sayılır.
- **Rota adayları:**
  - A* ile yanal sapma: büyük daire etrafında ±400 km, 20 km adımlı ızgara,
    41 ara nokta; sapma uçlarda kademeli olarak sınırlanır.
  - Bir üst ya da bir alt basınç seviyesine geçiş: tırmanma ve alçalmanın
    yaklaşık yakıt ve süre bedeli hesaba katılır.
- **Öncelik sırası:**
  1. Aktif SIGMET'e **girmemek** (sert kısıt). Kısıt dört boyutludur:
     poligon, irtifa bandı, uçağın o noktaya varış zamanındaki geçerlilik
     ve iki nokta arasındaki bacağın poligonu kesmesi.
  2. Riskli TI1 noktalarından kaçınmak (yumuşak kısıt, 6 saatlik sanal ceza).
  3. En düşük yakıt/süre.
- Kaçınılacak bir risk yoksa önerilen rota büyük daireyle birebir aynıdır;
  uydurma bir "iyileşme" gösterilmez.

## 4. Hata durumlarında davranış (fail-safe)

| Durum | Sistemin davranışı |
|---|---|
| SIGMET'e girmeyen geçerli bir rota yok (örn. varış noktası SIGMET içinde) | **Öneri yapılmaz**: `guvenli_rota_bulundu_mu: false`, açıklamada "ÖNERİ YOK", normal rota gösterilir. |
| SIGMET veritabanına erişilemiyor | Rota hesaplanır; `sigmet_kontrolu.durum = "erisilemedi"` ve açıklamada UYARI yer alır. |
| Canlı bir hesapta son SIGMET çekimi 30 dakikadan eski | `sigmet_kontrolu.bayat_mi: true` ve açıklamada UYARI. |
| AWC'nin bir uç noktası yanıt vermiyor | Diğer kaynak işlenir; yanıt vermeyen kaynağın mevcut kayıtlarına dokunulmaz. |
| Bir SIGMET iptal edildi (canlı akıştan düştü) | Geçerliliği o an sona erdirilir; artık rotayı saptırmaz. |
| Hava verisi yok (bölge, tarih ya da irtifa kapsam dışı; GFS indirilemedi) | Rota rüzgarsız, sadece TAS ile hesaplanır ve TI1 raporlanmaz; bu durum açıkça belirtilir. SIGMET kısıtı yine uygulanır. |
| Bir noktanın irtifası/zamanı küpün seviyelerinden ya da zaman adımlarından uzak | O nokta için TI1 NaN bırakılır; en yakın hücreden uydurma değer üretilmez. |
| Analiz sonucu veritabanına yazılamadı (API) | Görev `hata` durumuna geçer; "tamamlandı" gösterilmez. |
| API görev bitmeden yeniden başladı | Açılışta bu görevler `yarida_kaldi` olarak işaretlenir. |

## 5. Bilinen sınırlamalar

**Fiziksel gösterge**
- TI1'den türetilen EDR proxy sertifikalı bir EDR değeri değildir.
- ERA5/GFS'nin ~25-30 km çözünürlüğü küçük ölçekli türbülansı çözemez.
- 167 PIREP gözleminde TI1'in tek başına ayırt ediciliği zayıftır
  (ROC-AUC 0.44).
- EDR ölçekleme katsayısı 0.23'tür; %95 güven aralığı [0.13, 0.33].

**ML sınıflandırıcısı**
- 167 örnek; gün bazında gruplu çapraz doğrulamayla ROC-AUC 0.656 ± 0.043,
  recall 0.554 ± 0.077.
- Yalnızca ABD verisiyle doğrulanmıştır; karar eşiği 0.5'te sabittir.
- Ek bir işaret olarak raporlanır; rota kararına girmez.

**Rota modeli**
- Seyir irtifası sabittir; kalkış ve iniş fazları modellenmez.
- Uçak performans değerleri (TAS, yakıt akışı) tipik, halka açık değerlerdir.
- Hava sahası yapısı, ATC kısıtları, NOTAM ve yasak sahalar modellenmez.

**SIGMET**
- 180° boylamını (antimeridyen) kesen poligonlar desteklenmez.
- İptal tespiti, SIGMET'in canlı akıştan düşmesine dayanır.
- Buzlanma (ICE) varsayılan kaçınma setinde yoktur
  (`SIGMET_KACINILACAK_TEHLIKELER` ile eklenebilir).
- Uluslararası kapsam, AWC'ye ulaşan mesajlarla sınırlıdır.

**GFS**
- UCAR THREDDS ücretsiz bir akademik servistir; hizmet düzeyi garantisi (SLA)
  yoktur.
- Zaman adımı 3 saattir; yeni bir döngü birkaç saat gecikmeyle yayınlanır.

**Backtest**
- Şu anki sonuçlar 3 gerçek uçuşun 100-260 km'lik seyir bölümlerine
  dayanır. Bölümlerin kısa olmasının nedenleri OpenSky kapsama boşlukları ve
  küp sınırıdır. Sonuçlar istatistiksel bir kanıt değil, doğrulama hattının
  çalıştığının gösterimidir.

**İşletim**
- Hız sınırı bellekte ve süreç başına tutulur.
- Açılışta yarıda kalan görevlerin işaretlenmesi tek süreçli dağıtımı
  varsayar.

## 6. Doğrulama durumu

- **Otomatik testler:** 215 test. Kapsamı: birim testleri, gerçek PostgreSQL
  üzerinde API ve depo testleri, gerçek ERA5 küpüyle eşleştirme ve rota
  testleri, Playwright ile iki web önyüzünün tarayıcı testleri. Ağa çıkan
  bileşenler (GFS, AWC) testlerde sahte sağlayıcılarla çalışır.
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
- **Backtest (15 Ocak 2019, ERA5):** Riskli nokta oranı, gerçek uçuşlarda
  ortalama 0.28, önerilen rotalarda 0.00. Üç uçuşun ikisinde risk tırmanma
  ile azaldı; büyük daireye göre ek süre 2-5 dakika.

## 7. Uygun olmayan kullanımlar

- Gerçek bir uçuşta operasyonel kararın tek dayanağı olarak kullanmak.
- TI1/EDR proxy değerlerini sertifikalı EDR ölçümü yerine koymak.
- ML metriklerini, doğrulanmadığı bölgelere (örn. Türkiye) genellemek.
- SIGMET kontrolü "erişilemedi" ya da "bayat" durumundayken önerilen rotayı
  SIGMET'ten arındırılmış saymak.
