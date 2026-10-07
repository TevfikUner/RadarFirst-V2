# Katkılar (rapor bölümü taslağı, E3)

Bu bölüm bitirme raporuna doğrudan aktarılabilir. Her katkının yanında depoda
nerede görüleceği, sınırı ve literatürdeki en yakın çalışmadan farkı yazılıdır
(künyeler: `ILGILI_CALISMALAR.md`); jüri sorusunda kanıt buradan gösterilir.

Sistem sertifikalı EDR üretmez; karar destek aracıdır.

## Özet

Türbülans Radar, açık veri kaynaklarını (OpenSky ADS-B, Copernicus ERA5, NOAA GFS,
AWC SIGMET, IEM PIREP) tek bir otonom arka uçta birleştirerek seyir irtifasında
türbülans riskini hesaplayan, belirsizliğini söyleyen ve riskten kaçınan rotayı
öneren bir karar destek sistemidir. Katkılar üç grupta toplanır: veri ve etiket
kalitesi, değerlendirme ve belirsizlik, karar ve işletim.

## 1. Veri ve etiket kalitesi

**K1. Gerçek uçuş izinin hava verisiyle barometrik irtifa üzerinden eşleştirilmesi.**
Her ADS-B noktası, uçağın barometrik irtifasına karşılık gelen ISA basınç
seviyesinde ve en yakın ERA5 zaman/ızgara hücresinde değerlendirilir; küpün
kapsamadığı noktalar tahmin edilmez, "veri yok" olarak bırakılır.
- Kanıt: `fizik/eslestirme.py`, ADR 0005; demo: THY322'nin 1614 noktasının 720'si
  150–350 hPa içinde.
- Sınır: ERA5 0,25° ve saatliktir; türbülansın ölçeği bunun altındadır.
- En yakın çalışmadan farkı: Lee vd. (2023) aynı ERA5 teşhislerini ızgara klimatolojisi olarak hesaplar; biz onları gerçek ADS-B izinin barometrik seviyesinde, uçağı çevreleyen katmandan nokta nokta hesaplıyor ve kapsam dışını tahmin etmeden "veri yok" bırakıyoruz.

**K2. PIREP irtifa hatasının tespiti ve seyir irtifası etiket hattı.**
IEM PIREP arşivindeki `FL` alanının feet cinsinden olduğu, önceki veri setinin bu
yüzden seyir yerine 300–400 ft'teki (pist/yaklaşma) raporları seçtiği bulundu.
Etiket hattı ham arşivden doğru filtreyle (FL280–FL420) yeniden kuruldu. Doğru
veride TI1'in ROC-AUC'si 0,44'ten 0,71'e çıktı (tarihçe: 1 Ekim, 10 gün × 100 PIREP,
gerçek CDS). Güncel değer 7.815 PIREP'te 0,680 (`docs/sonuclar/2026-10-07/SAYILAR.md`).
- Kanıt: `ml/ml_veri_hatti.py`, `dogrulama/bagimsiz_kanit.py` (`pirepleri_normalize_et`).
- Sınır: PIREP öznel ve gecikmelidir; nesnel EDR etiketi için NOAA MADIS başvurusu
  yapıldı (geliştirme planı M1).
- En yakın çalışmadan farkı: Schwartz (1996) PIREP'in nicel kullanımındaki gürültüyü genel olarak tartışır; biz açık IEM arşivinde somut iki hatayı (FL alanının feet olması, /OV UNK konumu) bulup etiket hattını bunlara göre yeniden kurduk.

**K3. Kendiliğinden büyüyen, kotalı ve tekrar indirmesiz eğitim verisi.**
Gece işi IEM'den yeni PIREP'leri çeker, gün/bölge gruplarıyla küçük ERA5 dilimleri
ister (gece ≤ 60, gün ≤ 150 CDS isteği) ve dilimleri bir pencere deposunda saklar;
yeni bir özellik denemek için veri yeniden indirilmez.
- Kanıt: `ml/ml_veri_hatti.py`, `ml/ozellik_deposu.py`, ADR 0002; durum
  `GET /api/v1/ml/durum`.
- En yakın çalışmadan farkı: Muñoz-Esparza vd. (2020) sabit ve kapalı bir yerinde EDR veri kümesiyle çalışır; bizim eğitim verimiz açık kaynaklardan her gece sağlayıcı kotaları içinde büyür ve ham pencereler saklandığı için yeni bir özellik yeniden indirmeden denenir.

## 2. Değerlendirme ve belirsizlik

**K4. Sızıntıya dayanıklı değerlendirme protokolü ve kapılı model aktivasyonu.**
Aynı günün raporları aynı katta kalır (gün gruplu çapraz doğrulama), en son günler
zamansal holdout'tur; güven aralıkları gün blok bootstrap ile, TI1'e göre fark
eşleştirilmiş AUC testiyle verilir. Aday model ancak holdout ROC-AUC'de TI1'i en az
0,02 geçer ve aktif modelin F1'ini iyileştirirse aktif olur; aksi halde yalnızca
sürüm olarak saklanır ve geri alınabilir.
- Kanıt: `ml/degerlendirme.py`, `ml/ml_otomatik_egitim.py`, ADR 0003, 0004,
  `docs/deney_protokolu.md`.
- En yakın çalışmadan farkı: Roberts vd. (2017) gruplu doğrulamayı genel olarak önerir; biz onu gün gruplu CV, zamansal holdout ve TI1'e karşı eşleştirilmiş bootstrap farkının alt sınırına bağlı otomatik bir aktivasyon kapısına dönüştürdük.

**K5. "Emin değilim" diyebilen tahmin.**
Çapraz-konformal tahminle her olasılık `dusuk_risk`, `yuksek_risk` ya da `belirsiz`
durumuna çevrilir (hedef kapsama %90); gerçekleşen kapsama zamansal holdout'ta
ölçülüp model sürümüyle saklanır.
- Kanıt: `ml/belirsizlik.py`, ADR 0010.
- En yakın çalışmadan farkı: Angelopoulos ve Bates (2021) çapraz-konformal yöntemi genel olarak anlatır; biz onu türbülans olasılığını "belirsiz" diyebilen üç durumlu bir karar çıktısına çevirip gerçekleşen kapsamayı holdout'ta ölçtük.

**K6. Fizik göstergesinin sınırının ölçülmesi ve ürüne yansıtılması.**
TI1'in bağımsız becerisi seyir PIREP'lerinde ölçüldü: 7.815 PIREP, ROC-AUC 0,680
[0,662–0,697]; altın test günlerinde 0,673, config eşiğinde yakalama 0,448, yanlış alarm
0,201; MADIS ölçülen EDR'de 0,706 (`docs/sonuclar/2026-10-07/SAYILAR.md`). Gerçek bir
uçuşta (PUE502) aktif TURB SIGMET'i
yakalamadığı gösterildi. Sonuç, her rota yanıtında ve arayüzde gösterilen bir
güvenilirlik notuna ve güvenliğin SIGMET sert kısıtına dayandırılmasına dönüştü.
- Kanıt: `fizik/turbulans_indeksleri.py` (`TI1_GUVENILIRLIK_NOTU`),
  `dogrulama/bagimsiz_kanit.py`, `docs/SISTEM_KARTI.md` §6.
- En yakın çalışmadan farkı: Kim vd. (2011) ile Sharman ve Pearson (2017) teşhislerin becerisini ölçüp operasyonel birleşime ağırlık olarak kullanır; biz ölçülen sınırı (TI1 ROC-AUC 0,68) ürün davranışına taşıdık: TI1 yumuşak, SIGMET sert kısıt, her yanıtta güvenilirlik notu.

## 3. Karar ve işletim

**K7. Öncelik sıralı, dört boyutlu kısıtlı rota optimizasyonu.**
A* araması yanal sapma ile bir üst/alt seviyeye geçişi gerçek yakıt/süre bedeliyle
karşılaştırır. Öncelik: (1) SIGMET ve kısıtlı sahaya girmemek: poligon, irtifa
bandı, varış zamanındaki geçerlilik ve bacak kesişimiyle, zaman belirsizliği
payıyla; (2) riskli TI1'den kaçınmak; (3) yakıt. Kaçınacak risk yoksa rota büyük
daireyle aynı kalır; güvenli rota yoksa öneri verilmez.
- Kanıt: `rota/rota_optimizasyonu.py`, `rota/risk_katmanlari.py`; demo ekranları
  `docs/sunum/ekranlar/`.
- En yakın çalışmadan farkı: Cheung (2018) A* ile CAT'ten kaçınmayı bir örnek olayla gösterir; biz yanal sapmayı seviye değişimiyle yakıt bedeli üzerinden karşılaştıran, SIGMET ve kısıtlı sahayı varış zamanında sert kısıt sayan ve kalan riski dispeçere UTC/FL/NM olarak veren bir karar akışı kurduk.

**K8. ADS-B'den gözleme dayalı ikinci türbülans kanalı (sanal PIREP).**
Seyirdeki uçağın atanmış seviyesinden ani sapmaları, eşikleri RVSM otopilot
toleransı ve ADS-B kuantizasyonundan türetilerek olay sayılır; çoklu uçak
doğrulaması yapılır ve dispeçere WebSocket ile iletilir. İlk ölçüm (16 PIREP):
POD 1/8, POFD 0/8.
- Kanıt: `fizik/sanal_pirep.py`, ADR 0011.
- Sınır: Örneklem küçük; eşikler kalibre edilmedi; sapma EDR değildir.
- En yakın çalışmadan farkı: Kopeć vd. (2016) ADS-B/Mode-S'ten EDR türetir; biz EDR'ye çevirmeden yalnız atanmış seviyeden sapmayı olay sayıp çoklu uçakla doğruluyor ve PIREP'e karşı POD/POFD ile ölçüyoruz.

**K9. Üretime yakın işletim mühendisliği.**
- Uzun işler için PostgreSQL kuyruğu (`FOR UPDATE SKIP LOCKED`) ve dağıtık kilit.
- Sağlayıcı yasaklarına karşı korumalar: tek eşzamanlı OpenSky sorgusu, günlük
  tavanlar, istek aralıkları, zamanlayıcı lider kilidi.
- Ağsız demo paketi; 780 otomatik test ve 5 işli CI (sır taraması, SBOM, tarayıcı
  testleri dahil); ölçülmüş performans raporu.
- Kanıt: ADR 0006–0009, `docs/PERFORMANS_RAPORU.md`, `docs/VERI_KAYNAKLARI_VE_LISANSLAR.md`.
- En yakın çalışmadan farkı: İncelenen açık kaynak türbülans projeleri (İlgili Çalışmalar §8) doğrulama ve işletim altyapısı içermez; bizde kuyruk, kilit, yedek, sağlayıcı yasak korumaları ve otomatik testler ölçülmüş performansla birlikte gelir.

## Özgünlük beyanı

Bu çalışmanın katkısı yeni bir türbülans teşhisi ya da tahmin ürünü değildir.
Katkı, bilinen yöntemleri (Ellrod TI1, Sharman–Pearson eşlemesi, gruplu doğrulama,
konformal tahmin, A*) yalnız açık veriyle tek bir işletilebilir karar destek
sisteminde birleştirmek ve bunu yaparken üç şeyi ölçülebilir kılmaktır:
(a) gerçek ADS-B izinin barometrik irtifayla reanalize eşlenmesi ve sonucun rota
optimizasyonuna sert/yumuşak kısıt olarak girmesi; (b) fizik göstergesinin sınırının
bağımsız etiketlerle (PIREP, MADIS EDR) ölçülüp ürün davranışına yansıtılması;
(c) modelin ancak bu göstergeyi istatistiksel olarak geçtiğinde devreye girmesi.
Yan katkı: açık IEM PIREP arşivinde irtifa birimi ve konum hatalarının bulunup
belgelenmesi. GTG ve WAFS gibi operasyonel ürünlerle doğruluk karşılaştırması
yapılmadı; bu gelecek çalışmadır (M3).
