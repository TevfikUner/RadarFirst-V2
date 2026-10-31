# Türbülans Radar: Gerçek Uçuş İzleri ve Reanaliz Verisiyle Seyir Türbülansı Riski ve Kaçınma Rotası

Tevfik Uner · Danışman: Arş. Gör. Dr. Fatih Titrek · Bilgisayar Mühendisliği, Konya Teknik Üniversitesi · 2026

> Bu dosya `python scripts/bitirme_raporu.py` ile `docs/rapor/` altındaki bölüm dosyalarından üretilir; düzeltme bölüm dosyasında yapılır, sonra betik yeniden çalıştırılır.

## Özet

Seyir irtifasındaki açık hava türbülansı (CAT) radarda görünmez; pilot raporu (PIREP) gönüllü,
gecikmeli ve konumu kabadır. Bu çalışma, yalnız açık veriyle (OpenSky ADS-B, Copernicus ERA5,
NOAA GFS, AWC SIGMET, IEM PIREP, NOAA MADIS) gerçek bir uçuş izinde seyir türbülansı riskinin
hangi ölçülmüş beceriyle gösterilebileceğini ve bu sınırın rota kararına nasıl taşınması
gerektiğini sorar. Türbülans Radar, ADS-B izinin her noktasını barometrik irtifasına karşılık
gelen basınç seviyesinde hava verisiyle eşleştirir, Ellrod TI1 ve birleşik EDR göstergelerini
hesaplar, PIREP'lerle eğitilen kapılı bir ML modeli çalıştırır ve aktif SIGMET'leri sert, TI1'i
yumuşak kısıt alan bir A* ile kaçınma rotası önerir.

Beceri sınırlıdır. TI1, 163 günde 15.940 seyir PIREP'inde ROC-AUC 0,673 [0,661–0,684] verir;
altın test günlerinde risk eşiğinde (7e-7) yakalama 0,50, yanlış alarm 0,25'tir. Önceden
yazılmış protokolle, modelin görmediği 79 yeni günde (7.769 PIREP) model TI1'i +0,027
[+0,018; +0,035] farkla geçer (0,685'e karşı 0,658); bu fark 18 Ekim altın günlerindeki
farka (+0,033) yakındır. Model yine de ROC-AUC 0,69 civarında kaldığı için güvenlik SIGMET sert
kısıtına dayanır; TI1 yasaklamaz, adaylar arasında seçimde yakıttan önce gelir. Bağımsız rota
backtest'inde (NE-ABD, A*'ın saptığı 908 rota) PIREP tüpündeki orta ve üstü payının oranı 0,71
[0,58; 0,90] çıkmıştır. Doğrulama ABD verisiyledir; Türkiye için beceri ölçülmemiştir.

Çıktılar sertifikalı EDR değildir; sistem operasyonel karar aracı değil, karar destek aracıdır.

**Anahtar sözcükler:** açık hava türbülansı, Ellrod TI1, ERA5, ADS-B, PIREP, rota optimizasyonu,
karar destek sistemi.

# 1. Giriş

## 1.1 Problem

Türbülans, tarifeli hava taşımacılığında yaralanmalı kazaların başlıca nedenlerindendir. ABD'de
2009–2018 arasında Part 121 (tarifeli hava yolu) kazalarının üçte birinden fazlası türbülansla
ilgiliydi; çoğunda uçak hasar görmedi ama en az bir kişi ağır yaralandı, en sık yaralananlar
kabin ekibiydi (NTSB, 2021). Aynı rapora göre bu kazaların yaklaşık yarısı alçalma ve yaklaşmada,
%60'ı 20.000 ft altında oldu; bu çalışma yalnız seyir safhasını (FL280–FL420) ele aldığı için o
kazaların hepsini hedeflemez.

Seyir irtifasındaki türbülansın önemli bir kısmı bulut dışındadır (açık hava türbülansı, CAT) ve
hava radarında görünmez. Elde iki tür bilgi vardır: sayısal hava tahmini (NWP) ve reanaliz
alanlarından türetilen teşhis indeksleri (Ellrod ve Knapp, 1992; Sharman vd., 2006) ve uçaktan
gelen gözlemler. Gözlemlerin en yaygını pilot raporudur (PIREP): gönüllü, gecikmeli, konumu ve
zamanı kabadır, şiddeti özneldir (Schwartz, 1996). Uçağın ölçtüğü EDR nesneldir ama büyük ölçüde
havayollarının kapalı verisidir; herkese açık kısmı (NOAA MADIS) seyrek ve ABD ağırlıklıdır.

Operasyonel ürünler (GTG, WAFS) türbülans alanı üretir ve yerinde EDR ile doğrulanır. Bir
dispeçerin elinde ise bu alanı belirli bir uçuşun izine bağlayan, becerisinin sınırını söyleyen
ve rota kararına bu sınırla giren açık bir araç yoktur.

## 1.2 Araştırma sorusu

Yalnız açık veriyle (OpenSky ADS-B, ERA5, AWC SIGMET, IEM PIREP) gerçek bir uçuş izinde seyir
türbülansı riski hangi ölçülmüş beceriyle gösterilebilir ve bu sınır rota kararına nasıl
taşınmalıdır?

Soru iki parçalıdır. Birincisi bir ölçme sorusudur: göstergenin ve modelin becerisi, modelin
görmediği günlerde, bağımsız etiketle ve belirsizliğiyle birlikte nedir? İkincisi bir tasarım
sorusudur: becerisi sınırlı bir gösterge rota kararında hangi rolü almalıdır?

## 1.3 Kapsam

- **Türbülans türü:** yalnız açık hava türbülansı. Konvektif, bulut içi, dağ dalgası ve iz
  türbülansı kapsam dışıdır.
- **Uçuş safhası:** yalnız seyir (ToC–ToD, FL280 üstü). Kalkış, tırmanış, alçalış, SID/STAR ve
  yaklaşma kapsam dışıdır.
- **Doğrulama bölgesi:** etiketler (IEM PIREP, MADIS EDR) ABD hava sahasındandır. Rota ve arayüz
  Türkiye'de çalışır ama oradaki beceri ölçülmedi.
- **Kullanım sınıfı:** tavsiye niteliğinde karar destek. Sistem sertifikalı değildir, EFB onayı
  yoktur; karar yetkisi pilotta ve dispeçerdedir.

## 1.4 Yaklaşım ve raporun düzeni

Çalışma önce ölçer, sonra karar verir. TI1 risk eşiği, model aktivasyon kapısı ve test günleri
sonuçlar görülmeden önce yazılı kurallara bağlandı (deney protokolü; ADR 0003, 0004). Sonuç ne
çıktıysa raporlandı; olumsuz ara bulgular da (örneğin 7 Ekim ön paketinde lojistik regresyonun
TI1'i geçememesi) sonuçlar bölümündedir.

Bölüm 2 ilgili çalışmaları, Bölüm 3 veri, gösterge, model, doğrulama ve rota yöntemini anlatır.
Bölüm 4 ölçülen sonuçları, Bölüm 5 katkıları ve her birinin sınırını, Bölüm 6 sınırlamaları ve
öğrenilen dersleri verir. Bölüm 7 sonucu özetler ve gelecek çalışmayı sıralar. Raporlanan her
sayı depodaki komutla yeniden üretilebilen sonuç paketlerinden (`docs/sonuclar/`) alınmıştır.

Çıktılar sertifikalı EDR değildir; sistem operasyonel karar aracı değil, karar destek aracıdır.

# 2. İlgili Çalışmalar

Künyeler Crossref (DOI) ya da
yayıncı kaydıyla 2, 5 ve 16 Ekim 2026'da doğrulandı (☑). Resmî belgeler (ICAO, NOAA)
DOI taşımaz; adlarıyla verildi. Bir çalışmadan sayı aktarılırken yalnızca özetinde
ya da doğrulanmış metninde yazan değer kullanıldı; tam metnine erişilemeyen
çalışmalarda sayı verilmedi.

## 2.1 Açık hava türbülansı ve teşhis indeksleri

Açık hava türbülansı (CAT), bulut dışında, çoğunlukla jet akımı çevresinde ve
tropopoz yakınında görülen, uçağın algıladığı ölçekte (yaklaşık 100 m – 1 km) bir
türbülanstır. Kaynağı büyük ölçekli akıştaki düşey rüzgâr kayması ve yatay
deformasyonun ince kararsız katmanlar oluşturması, bu katmanlarda Kelvin–Helmholtz
dalgalarının kırılmasıdır. Sayısal hava tahmini (NWP) ve reanaliz modelleri bu
ölçeği çözemez; bu yüzden CAT, model alanlarından türetilen **teşhis
indeksleriyle** dolaylı olarak kestirilir.

Ellrod ve Knapp (1992) en yaygın kullanılan iki indeksi tanımladı: TI1, düşey rüzgâr
kayması (VWS) ile toplam yatay deformasyonun (DEF) çarpımıdır; TI2 buna yakınsama
terimini ekler. Ellrod ve Knox (2010) indekse diverjans eğilim terimi ekleyerek
operasyonel başarımı iyileştirdi. Kararlılık tarafında Richardson sayısı (Ri),
kayma ile durağan tabakalaşmayı oranlar; Ri < 0,25 (Miles–Howard ölçütü) dinamik
kararsızlığın klasik işaretidir. Lee vd. (2023), 41 yıllık ERA5 ile Kuzey Yarımküre
CAT klimatolojisini TI1, TI2, VWS, deformasyon, diverjans ve Ri gibi aynı
teşhislerle çıkardı. Bu çalışma, ERA5 üzerinde bu teşhislerin anlamlı bir CAT
potansiyeli verdiğini gösteren en yakın referanstır.

Bölgesel eğilimler Türkiye için de anlamlıdır. Foudad vd. (2024), birden çok reanaliz ve
11 CMIP6 modeliyle 1980–2021 döneminde orta ve üstü CAT sıklığının Kuzeybatı Afrika, Orta
Doğu ve Doğu Asya'da iki katından fazla arttığını buldu; Orta Doğu ve Doğu Asya'daki artışı
iç değişkenlik aralığının dışında, dış zorlamaya bağlanabilir olarak değerlendirdi. Kuzey
Atlantik'te eğilim anlamlı değildi. Aynı çalışma, CAT eşiğinin veri setinin yatay
çözünürlüğüne çok bağlı olduğunu vurgular. Avrupa için ERA5 ile yapılmış bir lisans tezi
(Soliva Fabrega, 2025) 1994–2024'te genel bir artış bulmadı, ancak güney Avrupa'da indeks
değerlerinin ve oynaklığın daha yüksek olduğunu gösterdi. Zhang vd. (2025) Çin'de 12.539
uçak raporuyla CAT'in kışın en sık olduğunu (raporların %33,4'ü) ve 30 m/s üzeri jetlerle
ilişkili olduğunu raporladı. He vd. (2026), yine Çin'de PIREP ve ERA5 ile CAT teşhisleri için
eşik belirleme yöntemlerini karşılaştırdı; bu, eşiği veriden bir kuralla seçen yaklaşımımızın
(TI1 7e-7, eğitim günlerinde Peirce'in 1-SE kuralı) doğrudan kıyas noktasıdır. Türkiye bu
çalışmalarda ayrı bir bölge olarak incelenmedi; yalnız komşu bölgelerdeki bulgular aktarılabilir.

**Projeyle bağ.** Fizik katmanı TI1, TI2, VWS, DEF ve Ri'yi ERA5'ten, uçağın basıncını
çevreleyen 25 hPa'lık katmandan hesaplar (`fizik/turbulans_indeksleri.py`,
`fizik/eslestirme.py`). Deformasyon küresel metrik terimleriyle, katman kalınlığı
hipsometrik denklemle bulunur.

## 2.2 Operasyonel türbülans tahmini: GTG ve WAFS

Operasyonel ürünler tek bir indekse güvenmez. ABD'nin Graphical Turbulence
Guidance (GTG) sistemi (Sharman vd., 2006), çok sayıda teşhisi NWP çıktısından
hesaplayıp gözlemlere göre ağırlıklandırarak birleştirir. Sharman ve Pearson (2017)
her teşhisi **log-normal eşlemeyle** EDR birimine çevirip birleştirmeyi önerdi:
ln EDR = a + b·ln D; b ve a, teşhisin ve EDR'nin klimatolojik ortalama ile standart
sapmasından bulunur. Seyir irtifası (20–45 kft) için ln EDR'nin ortalaması −2,953,
standart sapması 0,602'dir (Sharman ve Pearson, 2017; Kim vd., 2019 aktarımıyla).
Kim vd. (2011), aynı GTG yaklaşımını Doğu Asya'da altı yıllık PIREP'le değerlendirdi;
becerinin kışın (jet ve üst seviye cephelerle) en yüksek olduğunu, düşey çözünürlük
ve PIREP sayısıyla arttığını, öngörü süresi uzadıkça düştüğünü gösterdi.

Dünya Bölge Tahmin Merkezleri (WAFC Londra ve Washington), ICAO Ek 3 kapsamında
800 hPa üstü için küresel CAT tahmini yayımlar. Gill (2014), WAFC'nin hem
tahminci elinden çıkan SIGWX haritalarını hem de otomatik ızgara CAT tahminini
British Airways uçaklarının yerinde ölçümleriyle (GADS) ROC analiziyle doğruladı.

**Projeyle bağ.** Yeni bir tahmin ürünü iddia etmiyoruz ve GTG/WAFS ile doğruluk
karşılaştırması yapmadık (gelecek çalışma, M3). Sharman ve Pearson'ın eşlemesini
açık veriye uyguladık: teşhislerin klimatolojisini ERA5 pencere deposunun eğitim
günlerinden hesaplayıp beş göstergeyi birleştirdik (`fizik/edr_esleme.py`). Birleşik
gösterge tek başına TI1'i küçük ama anlamlı farkla geçti (altın test günlerinde ROC-AUC
0,688'e karşı 0,675; bkz. `SONUCLAR.md` §0.1).

## 2.3 Türbülans gözlemi ve doğrulama: PIREP ve EDR

Pilot raporları (PIREP) öznel, uçak tipine bağlı ve konum/zamanda kabadır;
türbülans olmayan durumlar çok az raporlanır. Schwartz (1996), PIREP'lerin
nicel kullanımındaki bu sorunları ve doğrulamada nasıl ele alınabileceğini
tartıştı. Nesnel alternatif, uçağın kendi sensörlerinden hesaplanıp otomatik
yayımlanan girdap yitim hızıdır (EDR, ε^1/3, m^2/3 s^-1; ICAO Ek 3'te tanımlı).
Sharman vd. (2014), ABD'de yaklaşık 200 uçaktan 137 milyonu aşkın otomatik EDR
kaydını tanımladı ve PIREP şiddet sınıflarıyla karşılaştırdı. NTSB (2021), Part 121
taşımacılığında türbülans kaynaklı yaralanmaları inceleyip olayların önemli bir
kısmının alçak irtifada ve iniş/yaklaşmada olduğunu raporladı; bu, seyir CAT'ine
odaklanan kapsamımızın sınırını belirler.

**Projeyle bağ.** Eğitim etiketi PIREP'tir (orta ve üstü). Nesnel doğrulama için
NOAA MADIS'in herkese açık ACARS EDR kayıtlarını kullanıyoruz (M1, ADR 0012).
Bizim verimizde PIREP'lerin %52'si pozitifken MADIS ölçümlerinde hafif ve üstü
oranı %3'tür. Bu fark PIREP'in raporlama yanlılığını sayısal olarak gösterir;
PIREP'le eğitilmiş olasılıklar mutlak sıklık olarak okunamaz.

## 2.4 ADS-B'den türbülans çıkarımı

Kopeć vd. (2016), Mode-S EHS ve ADS-B mesajlarının düşey ivmeden ya da arka plan
rüzgârından EDR'ye çevrilebileceğini bir araştırma uçağının ivmeölçer kaydıyla
karşılaştırarak gösterdi. ADS-B verisi OpenSky ağından (Schäfer vd., 2014) gelir.
Kuantizasyon (irtifa 25 ft, düşey hız 64 ft/dk) ve güncelleme sıklığı, bu yolla
elde edilebilecek ayrıntıyı sınırlar.

**Projeyle bağ.** Sanal PIREP (K8) ADS-B'yi EDR'ye çevirmez, yalnız atanmış seviyeden
ani sapmaları olay sayar; eşikleri RVSM irtifa tutma toleransından (ICAO Doc 9574)
ve kuantizasyondan türetir, çoklu uçakla doğrular (ADR 0011).

## 2.5 Türbülans tahmininde makine öğrenmesi

Muñoz-Esparza vd. (2020), HRRR modelinin değişkenlerini ve GTG teşhislerini girdi
alan rastgele orman ve gradyan artırımlı regresyon ağaçlarını yerinde EDR'ye karşı
eğitti. Rastgele orman, EDR < 0,1 bölgesinde hataları belirgin biçimde azalttı;
boş ve hafif türbülansın ayırt edilmesini iyileştirip yanlış alarmları düşürdü.
Bu tür çalışmalarda değerlendirmenin nasıl bölündüğü belirleyicidir: aynı günün
gözlemleri birbirine bağımlıdır ve rastgele bölme becerisini şişirebilir. Roberts vd.
(2017), zamansal ve uzamsal yapılı verilerde blok/gruplu çapraz doğrulamayı
gerekçelendirir.

Yakın tarihli iki çalışma bizimkine benzer açık verilerle yüksek AUC raporlar.
Gökdeniz ve Ülkü (2026), ABD'de 200–350 hPa için ERA5 teşhisleri, IEM PIREP ve BADA
aerodinamik özellikleriyle XGBoost'ta AUC 0,904 elde etti. Gu ve Wang (2024),
Colorado'da sekiz teşhisli ağırlıklı KNN ile AUC 0,86 elde etti. İki çalışmada da veri
rastgele bölündü (70/30 ve 80/20). Gu ve Wang ayrıca hafif raporları dışarıda bırakıp
yalnız türbülanssız ve orta-üstü olayları kullandı. Rastgele bölmede aynı günün, hatta
aynı hava sisteminin örnekleri hem eğitim hem test kümesinde yer alır. Bu yüzden bu
değerler gün gruplu doğrulamayla elde edilen değerlerle doğrudan kıyaslanamaz. Kendi
147 eğitim günümüzde ölçtük (deney protokolü §10.7, `docs/sonuclar/2026-10-28_protokol_farki/`):
rastgele örnek 70/30 bölme ROC-AUC'yi gün gruplu bölmeye göre değiştirmedi (−0,001; derin
RF'de +0,001), hafif raporları çıkarmak ise 0,083 artırdı (0,702 → 0,785; TI1'de +0,063).
Yani bizim özelliklerimizle (koordinat yok) farkın ölçülebilen kısmı etiket tanımından
gelir; 0,785 ile 0,86–0,90 arasındaki kalan fark bölge, özellik ve modelle ilgilidir ve
ölçülmedi.
Gökdeniz ve Ülkü'de en önemli özellik coğrafi koordinatlardır (%17,5). Yazarlar bunu
topografyaya bağlıyor, ama konuma bağlı bir ezberle de açıklanabilir; koordinatlı bir
modelde rastgele bölmenin etkisini ölçmedik.

Zhu vd. (2026), ERA5 ve LiDAR verisinden EDR tahmin eden ve verisi az bölgelere genellemeyi
hedefleyen bir transfer öğrenme modeli (CAT-TLNet) kurdu, PIREP'lerle değerlendirdi ve tahmini
tam ve kısmi kaçınma rotası optimizasyonuna bağladı (Kuzey Amerika). Tahmini rota planlamasıyla
birleştirmesi bakımından bu projeye en yakın çalışmadır (değerlendirme özet düzeyinde yapıldı).
Özetinde gerçek ADS-B izi, SIGMET sert kısıtı ve çalışan bir karar destek sistemi yer almaz;
transfer öğrenme ise Türkiye'deki etiket yokluğu için bir gelecek çalışma yoludur. Alanın iki
güncel derlemesi makine öğrenmesi yöntemlerini (Li vd. 2026) ve CAT'in havacılık işletmesine
etkisini (Di Vito vd. 2025) özetler.

**Projeyle bağ.** Modelimiz açık veriyle (ERA5 + IEM PIREP) eğitilir, gün gruplu çapraz
doğrulama ve zamansal holdout kullanır, TI1'i geçmeyen aday aktifleşmez (K4). Hafif
raporlar negatif sınıftadır. Bölme ve etiket farkları §9 tablosunda yan yana verilir.

## 2.6 Belirsizlik: konformal tahmin

Konformal tahmin (Vovk vd., 2022) dağılım varsaymadan, seçilen hata oranında kapsama
garantisi veren tahmin kümeleri üretir. Angelopoulos ve Bates (2021) uygulamalı bir
giriş, Barber vd. (2021) çapraz-konformal (CV+) yöntemin kapsama sınırını verir.

**Projeyle bağ.** Her olasılık `dusuk_risk` / `yuksek_risk` / `belirsiz` durumuna
çevrilir (K5, ADR 0010).

## 2.7 Reanaliz verisi ve rota optimizasyonu

ERA5 (Hersbach vd., 2020), 0,25° ve saatlik çözünürlükte 37 basınç seviyeli küresel
reanalizdir. Rota tarafında A* (Hart vd., 1968) en kısa yol aramasının temelidir.
Cheung (2018), A* tabanlı düğüm temelli bir yörünge tahmin sistemi önerip CAT'in
kalkıştan önce hesaba katılıp nasıl kaçınılabileceğine örnek verdi; bu, bizim rota
katmanımıza yöntem olarak en yakın çalışmadır.

**Projeyle bağ.** A* araması yanal sapma ile seviye değişimini gerçek yakıt/süre
bedeliyle karşılaştırır; SIGMET ve kısıtlı sahalar sert, TI1 yumuşak kısıttır (K7).

## 2.8 Açık kaynak uygulamalar ve karşı örnekler

Hakemli yayın değildir; raporda "yazılım" olarak, depo adresi ve erişim tarihiyle
(2 Ekim 2026) verilir. Bu depoların çoğu türbülans "tahmini" üretir ama gerçek
türbülans etiketiyle (PIREP ya da yerinde EDR) karşılaştırma ve başarı ölçütü
raporlamaz. Bir sistemin tahmin ettiğini söylemesi, ölçüldüğü anlamına gelmez.

| Depo | Ne yapıyor | Eksik olan (README'ye göre, 2 Ekim 2026) | Kullanım |
|---|---|---|---|
| animeshghiloria/Flymply | PyTorch LSTM otokodlayıcı; yeniden kurma hatasını "anomali/türbülans" sayar; Gemma-2B ile kokpit uyarısı | Türbülans etiketi, doğrulama verisi ve başarı metriği yok; tek commit | Karşı örnek |
| yijia-xu/flight-turbulence-ai | Open-Meteo + NOAA PIREP + LLM ile yolcuya rapor | Türbülans indeksi ya da ölçülmüş doğruluk yok; LLM metni | Karşı örnek |
| debjit450/skywatch-live | Kural + Isolation Forest/LOF/otokodlayıcı ile ADS-B anomalisi | Türbülansa karşı doğrulama yok | Fikir: denetimsiz taban (bizde ölçüldü, ayırt edici çıkmadı) |
| feminaanzil/AeroContrail | ERA5 ile iz bulutu duyarlılığı (T ≤ −40 °C, RHi ≥ %100), zamansal holdout | — (yöntemini açıkça veriyor) | Fikir: M9 ölçütü |
| argilaga15/flight_opt_r_project, hemalii3/Flight-Route-Optimization-System | Çok amaçlı rota (NSGA-II / ağırlıklı Pareto) | Gerçek hava verisiyle sonuç yok | Fikir: zaman–risk seçenekleri |
| hook-365/adsb-3d, kevtoe/worldview | 3B ADS-B görselleştirme | — | Fikir: seviye bandı, oynatma |

Raporu teslim etmeden önce depoları açıp README'lerin hâlâ aynı olduğunu kontrol
edin. Yalnızca README'de yazanı aktarın; kodu çalıştırmadıysanız "çalıştırdık"
demeyin.

## 2.9 Karşılaştırma tablosu

| Çalışma | Yöntem | Veri / etiket | Metrik | Değerlendirme bölmesi | Bu çalışmadaki karşılığı |
|---|---|---|---|---|---|
| Ellrod ve Knapp (1992) | TI1 = VWS × DEF | NWP, PIREP | POD, FAR, alan tehdit skoru | Bölme yok: operasyonel tahminlerin ±3 sa PIREP'le doğrulaması; eşik modele göre ayrı | TI1: PIREP ROC-AUC 0,673, altın günler 0,675, MADIS 0,722 (14 gün) |
| Sharman vd. (2006), GTG | Çok teşhisli ağırlıklı birleşim | NWP (RUC), PIREP | PODy–PODn / AUC | — | Birleşik EDR: PIREP 0,688, altın günler 0,688 |
| Sharman ve Pearson (2017) | Teşhislerin log-normal EDR eşlemesi | NWP, yerinde EDR | EDR hatası, AUC | — | Aynı eşleme, ERA5 klimatolojisiyle (`edr_esleme.py`) |
| Kim vd. (2011) | GTG teşhisleri, mevsimsel analiz | NWP, 6 yıl PIREP (Doğu Asya) | AUC | — | Yalnız ABD, 163 gün (147 eğitim, 16 altın test); mevsim analizi yok |
| Gill (2014) | WAFC SIGWX + ızgara CAT | Yerinde ölçüm (GADS) | ROC | — | WAFS karşılaştırması yok (M3) |
| Muñoz-Esparza vd. (2020) | Rastgele orman, gradyan artırımı | HRRR + GTG, yerinde EDR | EDR hatası, kategori ayrımı | — | Protokolle seçilen rastgele orman, ERA5 + PIREP; altın günler ROC-AUC 0,708, TI1'den +0,033 [+0,018; +0,049] (kapı geçildi; 7 Ekim ön paketinde LR geçememişti) |
| Gökdeniz ve Ülkü (2026) | XGBoost, LightGBM, RF, AdaBoost, LR; BADA aerodinamik özellikleri | ERA5 200–350 hPa, IEM PIREP (ABD); 1 = CAT var | POD, FAR, CSI, TSS, AUC | Rastgele 70/30 + k-katlı CV | AUC 0,904 (XGBoost). Bizim gün gruplu değerlerimizle doğrudan kıyaslanamaz |
| Gu ve Wang (2024) | Ağırlıklı KNN (K = 27), 8 teşhis, AUC² ağırlık | ERA5 125–500 hPa, 7 yıl Colorado PIREP; yalnız türbülanssız ve orta-üstü (hafif dışarıda) | ROC, maxTSS, güvenilirlik | Rastgele 80/20 + 10 katlı CV, SMOTE | AUC 0,86, maxTSS 0,552. Bölme ve etiket tanımı farklı; bizde hafif raporlar negatif |
| Kopeć vd. (2016) | ADS-B/Mode-S'ten EDR | Araştırma uçağı ivmeölçeri | Karşılaştırma | — | ADS-B'den yalnız olay (EDR yok), POD 1/8, POFD 0/8 |
| Cheung (2018) | A* ile CAT'ten kaçınan rota | NWP CAT alanı | Örnek olay | — | A* + SIGMET sert / TI1 yumuşak kısıt, yakıt bedeliyle |
| **Bu çalışma** | TI1 referansı, birleşik EDR, kapılı ML | ERA5 + IEM PIREP (ABD), MADIS EDR; 1 = orta ve üstü | ROC-AUC, Peirce, eşleştirilmiş fark | Gün gruplu CV (147 gün) + rastgele seçilip dondurulmuş 16 altın test günü | — |

"Değerlendirme bölmesi" sütununda "—", o çalışmanın bölme yönteminin tam metinden
okunmadığını gösterir. Gökdeniz ve Ülkü (2026), Gu ve Wang (2024) ve Ellrod ve Knapp
(1992) dışındaki çalışmaların AUC değerleri bilerek verilmedi: tam metinlerine
erişilemedi ve özetleri sayı içermiyor. Bu üç çalışmanın sayıları 16 Ekim'de tam
metinden okundu. Sayıları rapora aktarmadan önce makalelerden okuyun; okuyamadığınız
sayıyı yazmayın. Rastgele bölmeyle elde edilen AUC değerleri, gün gruplu değerlerle aynı
eksende "daha iyi / daha kötü" diye yorumlanmamalıdır.

## Kapanış paragrafı

Operasyonel ürünler (GTG, WAFS) NWP'ye dayalı türbülans alanları üretir ve yerinde
EDR ile doğrulanır. ML çalışmaları ise çoğunlukla kapalı (havayolu) EDR verisiyle
çevrimdışı başarım raporlar. Bu çalışma, yalnız açık veriyle gerçek uçuş izlerini,
ölçülmüş sınırlarıyla bir risk göstergesini ve bu göstergeye dayalı rota kararını tek
bir işletilebilir sistemde birleştirir (K1–K9). Doğruluğu operasyonel ürünlerle değil,
bağımsız etiketlere (PIREP, MADIS EDR) karşı kendi referansı olan TI1'le ölçer.

# 3. Yöntem

Bu bölüm sistemin nasıl hesapladığını ve nasıl doğrulandığını anlatır. Ayrıntılı karar mantığı
`docs/SISTEM_KARTI.md` §3'te, deney kuralları `docs/deney_protokolu.md`'de, mimari
`docs/mimari.md`'dedir; burada yalnız sonuçları okumak için gereken kısım verilir.

## 3.1 Sistemin genel görünümü

```
OpenSky / ADS-B izi ──► eşleştirme (baro irtifa → ISA basınç, ERA5/GFS küpü)
                          └► Ellrod TI1, Richardson, birleşik EDR ──► PostgreSQL ──► FastAPI + WebSocket
AWC SIGMET + kısıtlı sahalar (sert) ─┐                                                  ├► 3B harita
TI1 cezası (yumuşak), OpenAP yakıt ──┴► A* rota (yanal + ±1 FL) ─────────────────────────┴► rota simülasyonu
IEM PIREP (FL280–420) ──► gece veri hattı ──► kapılı ML (TI1'i geçmezse aktifleşmez)
```

Sistem üç iş yapar: bir uçuş izini hava verisiyle eşleştirip CAT göstergelerini hesaplar; aktif
SIGMET'leri ve kısıtlı sahaları sert kısıt alarak kaçınma rotası önerir; önerilerini gerçek uçuş
izleriyle ve bağımsız etiketlerle karşılaştırır.

## 3.2 Veri

| Kaynak | İçerik | Çözünürlük | Kullanım |
|---|---|---|---|
| OpenSky (Trino) | ADS-B konum ve barometrik irtifa | ~1 sn | Gerçek uçuş izi |
| Copernicus ERA5 | u, v, t; 350–150 hPa arası 7 seviye | 0,25°, saatlik; ~5 gün gecikmeli | Gösterge, ML özellikleri, backtest |
| NOAA GFS (UCAR THREDDS) | u, v, t; 300/250/200 hPa | 0,25°, 3 saatlik | Uçuş öncesi planlama (en fazla 120 sa) |
| AWC SIGMET | Tehlike poligonu, irtifa bandı, geçerlilik | Canlı, 15 dk'da bir | Sert kısıt |
| IEM PIREP | Pilot türbülans raporları (ABD) | Tarihsel | ML etiketi ve doğrulama |
| NOAA MADIS (herkese açık) | Uçağın ölçtüğü EDR | Tarihsel, QC'siz ön veri | Nesnel etiket (ADR 0012) |

Lisans ve sağlayıcı sınırları `docs/VERI_KAYNAKLARI_VE_LISANSLAR.md`'dedir; CDS istek kotası kod
düzeyinde uygulanır.

## 3.3 Uçuş izi ile hava verisinin eşleştirilmesi

Her ADS-B noktasının barometrik irtifası ISA atmosferiyle basınca çevrilir; barometrik irtifa
yoksa GPS irtifasına düşülür ve kaynak kayda yazılır. Nokta, hava küpünün en yakın zaman ve ızgara
hücresiyle eşleşir; zamanda enterpolasyon yapılmaz. Fizik büyüklükleri (düşey rüzgâr kayması,
Richardson sayısı) uçağın basıncını çevreleyen tek katmandan (p_üst ≤ p ≤ p_alt) alınır. Küpün
yatay ya da zamansal kapsamı dışındaki noktalar tahmin edilmez, "veri yok" olarak bırakılır
(`fizik/eslestirme.py`, ADR 0005). Zaman örneklemesinin etkisi ayrıca ölçüldü (ATM-04,
`analiz/zaman_ornekleme.py`).

## 3.4 Türbülans göstergeleri

- **Ellrod TI1** (Ellrod ve Knapp, 1992): düşey rüzgâr kayması ile toplam yatay deformasyonun
  çarpımı (s⁻²). TI1 ve 0–1 gösterge ölçeği EDR değildir.
- **Richardson sayısı** (bulk Ri): katmanın statik kararlılığının kaymaya oranı; Ri < 0,25 ince
  kararsız katmanın işaretidir.
- **Birleşik EDR:** beş gösterge (TI1, TI2, VWS, DEF, 1/Ri) Sharman ve Pearson (2017) yöntemiyle
  log-normal EDR ölçeğine eşlenip ortalanır (C1 = −2,953, C2 = 0,602; klimatoloji pencere
  deposunun eğitim günlerinden). Uçaktan ölçülen EDR'nin yerini tutmaz.
- **Risk eşiği:** bir nokta TI1 > `TI1_ESIK_ORTA_SIDDETLI` ise "riskli" sayılır. Eşik veriden ve
  önceden yazılmış kuralla seçildi: eğitim günlerinde Peirce'i (POD − POFD) en büyüten eşiğin bir
  standart hatası içindeki en tutucu eşik (1-SE kuralı). 8 Ekim'de 7e-7 seçildi; 18 Ekim nihai
  paketinde kural 7,39e-7 verdi ve 7e-7 bandın içinde kaldığı için değişmedi. Canlı GFS için ayrı
  eşik (8,3e-7) ERA5 eşiğinin GFS dağılımındaki yüzdelik eşleniğidir.

## 3.5 Etiket hattı

IEM PIREP arşivinden seyir irtifasındaki (28.000–42.000 ft) raporlar alınır. IEM `FL` alanı
feet'tir; bu alanın uçuş seviyesi sanılması önceki veri setinde pist/yaklaşma raporlarının
seçilmesine yol açmıştı, hat bu bulguyla yeniden kuruldu (Bölüm 6, "Öğrenilen dersler"). Etiket
1 = orta ve üstü (LGT-MOD dahil), 0 = yok ya da hafif. Gün başına en fazla 100 PIREP sabit tohumla
seçilir. Her örnek için ERA5 penceresi (±1°, ±1 sa) indirilip depolanır; özellikler analizle aynı
kodla çıkarılır. Nesnel etiket olarak NOAA MADIS'in herkese açık uçak EDR arşivi PIREP
pencerelerinin içinden kullanılır; bu veri fiilen yalnız hafif sınıfı içerir.

## 3.6 Makine öğrenmesi modeli ve doğrulama protokolü

- **Soru:** ERA5'ten çıkarılan fiziksel özelliklerle eğitilen model orta ve üstü türbülansı tek
  başına TI1'den daha iyi ayırt eder mi?
- **Özellikler:** temel set 8 özellik: TI1, Ri, rüzgâr hızı, basınç, düşey kayma, yatay
  deformasyon, yatay diverjans, TI2. Geniş set 13 özellik: temel 8 + komşu TI1 en büyük/ortalama,
  kolondaki en düşük Ri, jet oranı, sıcaklık azalma oranı (protokol §10.2).
- **Bölme:** aynı günün raporları aynı hava sistemini gördüğü için rastgele bölme yapılmaz (ADR
  0003). 7 Ekim'de 80 günden rastgele 16'sı altın test günü olarak donduruldu; bu günler hiçbir
  model seçimine, kalibrasyona ya da eğitime girmez.
- **Model seçimi:** eğitim günlerinde gün gruplu, sınıf oranı korunan 5 katlı çapraz doğrulama, 3
  tekrar. Adaylar lojistik regresyon, rastgele orman, gradient boosting; en iyi modelle lojistik
  regresyonun farkı bir standart hatadan küçükse lojistik regresyon seçilir (1-SE). Olasılıklar
  Platt yöntemiyle kalibre edilir; eşikler eğitim günlerinde Peirce'i en büyütecek şekilde seçilip
  test günlerine olduğu gibi uygulanır.
- **Belirsizlik:** güven aralıkları gün bazlı blok bootstrap ile (1000 tekrar, %95). Model ile TI1
  farkı aynı bootstrap örnekleriyle eşleştirilmiş olarak hesaplanır; gün içi bağımlılık nedeniyle
  DeLong testine tercih edildi.
- **Aktivasyon kapısı (ADR 0004):** aday, test günlerinde TI1'e karşı ROC-AUC farkı ≥ 0,02 ve %95 GA
  alt sınırı > 0 ise, aktif model varsa ona karşı da aynı kuralla aktifleşir; aksi halde yalnız sürüm
  olarak saklanır ve geri alınabilir. 0,02 parametriktir, kalibre edilmedi. 29 Ekim'den beri kapı,
  aktif modelin görmediği son 16 yeni günde uygulanır (ADR 0014).
- **"Emin değilim" çıktısı:** çapraz-konformal tahminle her olasılık `dusuk_risk`, `yuksek_risk` ya
  da `belirsiz` durumuna çevrilir (hedef kapsama %90; ADR 0010). Eğitim dağılımının dışındaki
  girdide ML ve konformal çıktı verilmez (OOD kapısı).
- **Veri dondurma ve yeni günler:** 18 Ekim'de veri donduruldu, bir kez eğitim ve değerlendirme
  yapıldı. 19 Ekim'de, yeni günlere bakılmadan, dondurmadan sonra toplanan ≥ 30 yeni günde tek
  seferlik değerlendirme protokolü yazıldı (protokol §10); 27 Ekim'de 79 günle bir kez çalıştırıldı.
  Sonradan eklenen analizler de skorlar hesaplanmadan protokole yazıldı (§11–§13).

## 3.7 Rota önerisi

- **Arama uzayı:** büyük daire etrafında 41 ara noktalı bir koridorda A* (Hart vd., 1968); bacak
  açısı en fazla 30°, toplam yanal sapma en fazla 400 km, ızgara aralığı en fazla 20 km. Ayrıca
  aynı yönün bir üst ve bir alt yasal uçuş seviyesi (yarım daire kuralı, RVSM, tip tavanı) aday
  sayılır; seviye değişiminin yakıt bedeli OpenAP ile hesaplanır. İsteğe bağlı olarak FRATURK
  serbest rota ağında da aranabilir.
- **Kısıtlar ve öncelik:** (1) aktif SIGMET'e ve kısıtlı sahaya girmemek: sert, dört boyutlu kısıt
  (poligon, irtifa bandı, varış zamanındaki geçerlilik, bacağın poligonu kesmesi); (2) riskli TI1
  noktalarından kaçınmak: yumuşak kısıt; (3) en düşük yakıt ve süre.
- **Seçim kuralı (ADR 0013):** sert kısıtlara uyan adaylar arasında önce riskli TI1 nokta sayısı en az
  olan, eşitlikte en az yakıtlı aday seçilir. Riskten kaçınan aday yoksa riskli rota yine önerilir;
  güvenli rota yoksa (SIGMET) öneri yapılmaz. Kaçınılacak risk yoksa önerilen rota büyük daireyle
  aynıdır; uydurma bir iyileşme gösterilmez.
- **Kapsam:** yalnız seyir safhası; diğer trafikle ayırmayı dikkate almaz, ATC talimatının yerini
  tutmaz. Önerilen rota NON-OPERATIONAL işaretli bir FPL Madde 15 dizgisi olarak da verilir.

## 3.8 Uygulama ve doğrulanabilirlik

Sistem Python paketidir (`src/turbulans_radar`): FastAPI arka ucu, PostgreSQL + Alembic, kuyruklu
işçi (gece veri hattı, eğitim), dağıtık kilit; Docker Compose ile çalışır. 31 Ekim 2026'da 1.242
otomatik test vardır (birim, PostgreSQL, gerçek veri, tarayıcı); sürekli entegrasyon her değişikliği
6 işte sınar. Her rota ve tahmin yanıtı `uretim_bilgisi` taşır (yazılım sürümü, hava küpü, eşikler,
model sha256'sı, commit). Raporlanan her sayı `docs/sonuclar/` altındaki, komutu ve verisi yazılı
sonuç paketlerinden gelir.

Çıktılar sertifikalı EDR değildir; sistem operasyonel karar aracı değil, karar destek aracıdır.

## 3.9 Araç kullanımı beyanı

Bu projede yazılım geliştirme aracı olarak Anthropic'in Claude Code yapay zekâ
asistanı (Claude Sonnet 5 ve Claude Opus 5.5 modelleri) kullanıldı. Depodaki
birleştirme dışı 424 commit'in 208'inde asistan ortak yazar olarak işaretlidir
(`Co-Authored-By`; 2026-10-31 itibarıyla). 8 Ekim'e kadar 202 commit'in 200'ü işaretliydi;
yazar o tarihten sonra işareti eklememeye karar verdi, bu dönemde de asistan aynı şekilde
kullanıldı (oturum kayıtları `docs/ISLEM_GUNLUGU.md`). İşaret taşımayan ilk iki commit'ten
(21–22 Eylül 2026) bugüne kalan kod, Python satırlarının yaklaşık %1,4'üdür (47.829
satırın 665'i; `git blame -w`); kodun geri kalanı asistanla birlikte yazıldı. Asistan şu
aşamalarda kullanıldı: kod ve test yazımı, hata ayıklama, belge ve rapor taslakları,
literatür künyelerinin yayıncı/Crossref kayıtlarından doğrulanması ve dış inceleme
maddelerinin uygulanması. Araştırma sorusu, kapsam (yalnız CAT, seyir safhası), veri
kaynakları ve sağlayıcı sınırları, kabul kriterleri ve sonuçların yorumu yazara aittir;
yazarın asistana bıraktığı kararlar önceden yazılı bir kurala bağlandı ve belgelendi
(örnek: TI1 risk eşiği, eğitim günlerinde Peirce maksimumunun bir standart hatası
içindeki en tutucu eşik; `docs/rapor/SONUCLAR.md`). Asistan çıktısı üç yolla denetlendi:
otomatik testler (2026-10-31'de 1.242 test) ve sürekli entegrasyon her değişikliği
sınar, ana dala birleştirme testlerin ve statik denetimin temiz olmasına bağlıdır; raporlanan her sayı depodaki komutla yeniden üretilebilen sonuç
paketinden (`docs/sonuclar/`) alındı; tasarım, dış bir inceleme raporunun maddelerine
göre kabul kriterleriyle izlendi. Çekirdek modüllerin (`fizik/eslestirme.py`,
`fizik/turbulans_indeksleri.py`, A* maliyet fonksiyonu ve sezgiseli,
`ml/degerlendirme.py`) tasarımı ve doğrulanması savunmada yazar tarafından anlatılır
(proje işleyişi: `docs/sunum/PROJE_ISLEYISI.md`).

# 4. Sonuçlar

Güncel (nihai) sayılar §0'dadır. §1–§3 ölçüm tarihi 5 Ekim 2026. Ham sayılar `docs/rapor/veri/` altında JSON olarak durur;
her tablo aşağıdaki komutlarla yeniden üretilir. Güven aralıkları (GA) gün bazlı blok
bootstrap ile %95'tir (aynı günün raporları birlikte örneklenir; bkz.
`docs/deney_protokolu.md`). "TI1'e göre fark" aynı bootstrap örnekleriyle
eşleştirilmiş ROC-AUC farkıdır; p iki yönlüdür. Çıktılar sertifikalı EDR değildir;
sistem karar destek aracıdır.

```
turbulans-gosterge-degerlendirme --onceki ciktilar/ozellikler_onceki_20261005T1434.parquet \
    --cikti docs/rapor/veri/gosterge_degerlendirme_era5_pencere.json
turbulans-sonuc-paketi --klasor docs/rapor/veri
turbulans-madis degerlendir
```

Veri: seyir irtifasında (FL280–FL420) IEM PIREP'leri, ABD hava sahası, 64 gün;
etiket "orta ve üstü" (LGT-MOD dahil). Nesnel etiket: NOAA MADIS herkese açık ACARS
maxEDR (QC "Z", ön veri), PIREP pencerelerinin içinden (±1°, ±1 sa).

## 4.0 Nihai sonuç paketi (Madde 8, 18 Ekim veri dondurması)

Güncel sayılar [`docs/sonuclar/2026-10-18/`](../sonuclar/2026-10-18/SAYILAR.md) nihai
paketindendir: kesme 18 Ekim 2026, commit `5ddcd40`, üretim 18 Ekim 00:25 UTC, tek liste
`SAYILAR.md`. Paket dondurma yedeğinden (`db_yedekleri/kalici/turbulans_20261018_dondurma.dump`)
ve canlı veritabanından ayrı ayrı üretildi; iki çıktı birebir aynı. 7 Ekim ön paketi ([`2026-10-07/`](../sonuclar/2026-10-07/SAYILAR.md))
tarihçe olarak durur. Aşağıdaki §1–§3 ölçümleri 5 Ekim tarihlidir ve o günkü zamansal
holdout'u kullanır; onlar da tarihçedir.

```
turbulans-ml-degerlendirme --kesme 2026-10-18 --cikti docs/sonuclar/2026-10-18
turbulans-ml --dondurma-raporu docs/sonuclar/2026-10-18
```

### 4.0.1 Altın test günleri

Değerlendirme günleri, 7 Ekim'de dondurulan 16 altın test günüdür (1.583 PIREP). Model bu
günleri görmedi: 147 eğitim gününde (14.357 PIREP; tümü 163 gün, 15.940 PIREP) gün gruplu
CV ve 1-SE kuralıyla seçildi. CV'de Random Forest 0,7000, Gradient Boosting 0,6999,
Lojistik Regresyon 0,689 (SE ~0,004); LR'nin farkı SE'den büyük olduğu için seçilen
Random Forest oldu. RF ile GB arasındaki fark (0,0001) SE'nin çok altındadır; ikisinden
hangisinin seçildiği anlamlı değildir. Altın günlerde pozitif oranı 0,476'dır; PR-AUC'nin
rastgele tabanı bu orandır.

| Gösterge | ROC-AUC [%95 GA] | PR-AUC [%95 GA] | TI1'e göre ROC-AUC farkı |
|---|---|---|---|
| Model (RF) | 0,708 [0,677–0,738] | 0,688 [0,649–0,719] | +0,033 [+0,018; +0,049], p < 0,001 |
| Birleşik EDR | 0,688 [0,656–0,717] | 0,675 [0,634–0,709] | +0,013 [+0,007; +0,020], p < 0,001 |
| TI1 | 0,675 [0,641–0,706] | 0,665 [0,622–0,701] | — |
| 1/Ri | 0,655 [0,627–0,681] | 0,636 [0,589–0,674] | −0,020 [−0,052; +0,011], p 0,202 |

Fizik göstergeleri eğitilmediği için tüm 163 günde de ölçülebilir: TI1 0,673
[0,661–0,684], birleşik EDR 0,688 [0,676–0,698], 1/Ri 0,655 [0,644–0,666].

**Kapı sonucu:** protokol modeli altın günlerde TI1'i anlamlı farkla geçti (GA 0'ı
içermiyor). 7 Ekim ön paketinde (80 gün) seçilen LR geçememişti (+0,008 [−0,006; +0,022]).
Kural ve altın günler değişmedi; veri iki katına çıkınca 1-SE kuralı LR yerine ağaç modelini
seçti. Birleşik EDR'nin TI1'e üstünlüğü küçük ama tutarlı. Model olasılığında Brier 0,219,
Brier becerisi 0,122; ortalama olasılık 0,519, gözlenen oran 0,476.

**Paketin iki kez üretilmesi (şeffaflık notu).** İlk üretimde (17 Ekim 23:40 UTC, commit
`45caf3c`) eğitim sorgusu sırasızdı; 1-SE kuralı Gradient Boosting'i seçti: 0,710
[0,680–0,740], TI1'e göre +0,036 [+0,019; +0,053]. Yedekten yeniden üretimde satır sırası
değişince RF seçildi; RF ve GB satır sırasına duyarlıdır ve CV'de berabere oldukları için
seçim sıraya göre değişiyordu. Sorgular birincil anahtara göre sıralandı (PR #89) ve paket
yeniden üretildi. Düzeltme sonuca bakılarak seçim değildir: kural, altın günler ve veri
değişmedi; iki üretimde de model TI1'i anlamlı geçiyor. İlk çıktı
[`ilk_uretim_sirasiz/`](../sonuclar/2026-10-18/ilk_uretim_sirasiz/SAYILAR.md) altında durur.

**Raporlanan model ile çalışan model.** Canlı sistemde 9 Ekim'de gece kapısından geçen
Random Forest aktiftir (79 eğitim günü, 7.759 PIREP; aynı 1-SE kuralıyla seçildi). Aynı
altın günlerde ROC-AUC'si 0,707, TI1'e göre +0,033 [+0,018; +0,048]. Dondurma raporu
(`ml_dondurma.json`, sıralama düzeltmesinden önce üretildi; aday GB, 0,710) yeni adayı aktif
modelle karşılaştırdı: fark +0,003 [−0,001; +0,008], anlamlı değil; aday yalnız sürüm olarak
saklandı, aktif model değişmedi. Dondurma raporu bir model sürümü kaydettiği için yeniden
çalıştırılmadı (aynı altın günlerde bir karşılaştırma daha olurdu).
9 Ekim aktivasyon kararı altın günlerde verildi. Bu model seçimi değil kapı kararıdır, ama
7–18 Ekim arasında 12 sürüm aynı 16 günde kapıya girdi ve biri aktifleşti (çoklu
karşılaştırma). Bu yüzden aktif modelin altın gün skoru protokol modelininki kadar temiz
değildir. Protokol modeli altın günlerde iki kez ölçüldü (yukarıdaki not); ikisi de seçime
etki etmedi.

Şekiller: [ROC (TI1 ve Ri)](../sonuclar/2026-10-18/roc_ti1_ri.png),
[güvenilirlik diyagramı](../sonuclar/2026-10-18/guvenilirlik_modeli.png).

### 4.0.2 TI1 eşik taraması

Eşik eğitim günlerinde Peirce'i (POD − POFD) en büyütecek biçimde seçildi ve altın günlere
olduğu gibi uygulandı. Taramanın tamamı JSON'da `esik_taramasi.tarama` altında.

| Eşik | Altın günlerde POD | POFD | CSI |
|---|---|---|---|
| Peirce eşiği 4,96e-7 (eğitim günlerinden) | 0,622 | 0,373 | 0,441 |
| `TI1_ESIK_HAFIF` 4e-7 | 0,682 | 0,439 | 0,460 |
| 1-SE eşiği 7,39e-7 (eğitim günlerinden) | 0,481 | 0,230 | 0,384 |
| `TI1_ESIK_ORTA_SIDDETLI` 7e-7 (config, risk eşiği; 8 Ekim'e kadar 8e-7) | 0,501 | 0,248 | 0,394 |

Peirce eşiğinde altın günlerdeki Peirce 0,249 [0,177–0,308]. Ri için aynı yöntem Ri < 2,27
verdi. Klasik 0,25 sınırı ERA5 çözünürlüğünde çok seyrek aşılır (bkz. §1.1).

Seviyeye göre (her seviyede eşik o seviyenin eğitim örnekleriyle seçildi):

| Seviye | Seviye eşiği | POD / POFD / CSI (seviye eşiği) | POD / POFD / CSI (genel eşik) | Test örneği |
|---|---|---|---|---|
| 175 hPa | 4,3e-7 | 0,692 / 0,358 / 0,444 | 0,673 / 0,333 / 0,443 | 133 |
| 200 hPa | 6,7e-7 | 0,523 / 0,239 / 0,416 | 0,621 / 0,303 / 0,469 | 274 |
| 225 hPa | 6,8e-7 | 0,510 / 0,314 / 0,359 | 0,637 / 0,457 / 0,395 | 367 |
| 250 hPa | 4,6e-7 | 0,590 / 0,387 / 0,426 | 0,578 / 0,368 / 0,423 | 534 |
| 300 hPa | 4,3e-7 | 0,717 / 0,341 / 0,559 | 0,689 / 0,307 / 0,549 | 194 |
| 350 hPa | 7,3e-7 | 0,385 / 0,190 / 0,319 | 0,615 / 0,429 / 0,421 | 81 |

Seviye eşikleri genel eşiğe yakın (4,3–7,3e-7) ve CSI'yi tutarlı biçimde iyileştirmiyor
(175, 250 ve 300 hPa'da biraz iyi; 200, 225 ve 350 hPa'da kötü). Tek genel eşik yeterli
görünüyor.

**Risk eşiği kararı (8 Ekim; 18 Ekim'de yeniden hesaplandı).** Peirce'i en büyüten eşik ile
daha yüksek eşikler arasındaki beceri farkı küçüktür; yüksek eşik daha az yanlış alarm verir.
Gerçek olay oranı düşük olduğu için (MADIS'te %3) yanlış alarm pahalıdır. Bu yüzden model
seçimindeki 1-SE kuralının eşik karşılığı uygulandı: eğitim günlerinde Peirce'i en yüksek
değerin gün bazlı bootstrap standart hatası içinde kalan en yüksek eşik. 7 Ekim'de 7,06e-7
(Peirce maks 0,284, SE 0,018) çıktı ve `TI1_ESIK_ORTA_SIDDETLI` 8e-7'den 7e-7'ye indi.
Nihai pakette aynı kural 7,39e-7 verdi (Peirce maks 0,256, SE 0,011). 7e-7 yeni bandın da
içinde: eğitim Peirce'i 6,6e-7'de 0,251, 7,6e-7'de 0,239, bandın alt sınırı 0,245. Bu yüzden
config değiştirilmedi; eşiğe bağlı testler ve demo ekranları aynı kalır.

### 4.0.3 Yalnız CAT alt kümesi (MET-07)

Sistemin kapsamı açık hava türbülansıdır. PIREP metninde CB, TS (+TSRA, VCTS, TSTM gibi
türevler), TCU, MTN WAVE ya da LLWS geçen raporlar dışlandı. Ham metin yalnız yerel IEM
arşivinde (2018–Mart 2020) var: 14.493 örneğin metni bulundu, 233'ü (%1,6) CAT dışı
işaretlendi ve bunların pozitif oranı 0,438. Altın günlerde metinli 1.398 örnekten 1.382'si
kaldı.

| Gösterge | Yalnız CAT, altın günler | Yalnız CAT, tüm günler |
|---|---|---|
| Model | 0,707 [0,671–0,745] | — |
| Birleşik EDR | 0,684 [0,650–0,721] | 0,688 [0,676–0,699] |
| TI1 | 0,670 [0,634–0,708] | 0,673 [0,661–0,685] |
| 1/Ri | 0,654 [0,623–0,687] | 0,656 [0,644–0,667] |

CAT dışı raporlar çok az olduğu için dışlamak sonucu değiştirmiyor. Nisan 2020 sonrası
günlerin metni yok; bu günler iki alt kümede de yer almıyor.

### 4.0.4 Nesnel etiket: MADIS ölçülen EDR

45.075 ölçüm, 1.310'u hafif ve üstü (taban oran 0,029), 14 gün. Sınıflar
`madis_edr.edr_sinifi` ile yeniden hesaplandı. Orta ve üstü ölçüm yalnız 1 tane; yani
değerlendirme fiilen hafif sınıfı ayırt etmeyi ölçer. Örnekler PIREP pencerelerinden
geldiği için seçim yanlılığı vardır; QC "Z" ön veridir. MADIS günleri modelin eğitim
günleriyle çakışabilir (model MADIS etiketini görmedi, aynı günlerin PIREP'lerini gördü).

| Gösterge | ROC-AUC [%95 GA] | PR-AUC [%95 GA] | TI1'e göre fark |
|---|---|---|---|
| Model | 0,775 [0,734–0,814] | 0,126 [0,093–0,169] | +0,053 [+0,028; +0,077], p < 0,001 |
| Birleşik EDR | 0,757 [0,710–0,804] | 0,115 [0,085–0,161] | +0,035 [+0,020; +0,050], p < 0,001 |
| TI1 | 0,722 [0,669–0,779] | 0,105 [0,073–0,154] | — |
| 1/Ri | 0,722 [0,672–0,766] | 0,085 [0,058–0,116] | −0,000 [−0,060; +0,053], p 0,942 |

PR-AUC taban orandan 3–4 kat yüksek, ama mutlak değeri düşük. %3'lük bir olayda ROC-AUC
0,7–0,8 sıralamanın rastgeleden iyi olduğunu söyler; uyarıların çoğunun yanlış alarm
olacağını gizler. Model olasılığı ortalama 0,505, Brier becerisi −8,50: olasılık PIREP taban
oranına göre kalibre olduğu için ölçülen sıklık olarak okunamaz (§4). Önsel kayma
düzeltmesiyle (PIREP taban oranından MADIS taban oranına) Brier becerisi 0,041 olur; bu
yalnız bir gösterimdir, düzeltme aynı veriden yapıldığı için iyimserdir ve karara girmez.

### 4.0.5 Rota backtest'i

Veritabanındaki iki uçuşta riskli nokta oranı (gerçek / büyük daire / A*), 7e-7 eşiğiyle:
THY322 1 Ocak 2019 0,00 / 0,20 / 0,00; THY322 15 Ocak 2019 0,24 / 0,39 / 0,02
([şekil](../sonuclar/2026-10-18/backtest_ucus_basina.png)). Ölçüm döngüseldir. PUE502
(bağımsız kanıtlı tek uçuş) bu veritabanında yok; açıklaması `docs/SISTEM_KARTI.md` §6'da.

Bağımsız toplu ölçüm (29 Ekim, protokol §11): NE-ABD'de 2.304 simüle rota; TI1 eşiğinin seçildiği
günler hariç, A*'ın sapma önerdiği 908 rotada PIREP tüpündeki orta-üstü payının göreli maruziyet
oranı (A* / büyük daire) 0,71 [0,58; 0,90]; 48 günün tamamında 0,83 [0,66; 1,03]
([paket](../sonuclar/2026-10-29_bagimsiz_backtest/README.md)).

## 4.1 Fizik çekirdeği (Madde 2) — tarihçe, 5 Ekim

### 4.1.1 Düzeltmenin etkisi

Düzeltmeler: kayma ve Ri uçağın basıncını çevreleyen katmandan (7 seviye, jet
çevresinde 25 hPa), katman kalınlığı hipsometrik denklemle, deformasyon ve diverjans
küresel metrik terimleriyle; yatay kapsam toleransı 0,125°.

| Ölçüt (aynı 6.220 PIREP) | Eski fizik (3 seviye) | Yeni fizik (7 seviye) |
|---|---|---|
| TI1 ROC-AUC (orta ve üstü) | 0,644 [0,623–0,664] | 0,671 [0,651–0,690] |
| Ri < 0,25 olan örnek oranı | %0,34 | %1,37 |
| Ri < 1 olan örnek oranı | %8,3 | %20,8 |
| Ri medyanı | 5,70 | 2,82 |

Yeni fizikte Ri < 0,25 pozitif örneklerde %1,97, negatiflerde %0,71'dir. İnce
kararsız katman artık görülebiliyor ama ERA5 çözünürlüğünde hâlâ seyrek.

Seviyelere göre TI1 ≥ eşik oranı (yeni seviye; eski sütunda o örneğin eski hesapta
kullanılan seviye):

| Yeni seviye (hPa) | Örnek | Eski seviye | TI1 ≥ 4e-7 (eski → yeni) | TI1 ≥ 8e-7 (eski → yeni) |
|---|---|---|---|---|
| 175 | 530 | 200 | %37,2 → %54,2 | %17,2 → %30,2 |
| 200 | 973 | 200 | %46,8 → %57,5 | %21,1 → %33,3 |
| 225 | 1.414 | 200 / 250 | %39,7 → %56,5 | %17,7 → %31,2 |
| 250 | 2.214 | 250 | %40,7 → %55,0 | %19,2 → %31,3 |
| 300 | 825 | 300 | %56,1 → %57,9 | %30,9 → %34,2 |
| 350 | 264 | 300 | %55,3 → %60,2 | %31,1 → %30,3 |

Eski hesapta seviyeler arasında belirgin bir dengesizlik vardı. Seyrin yoğun olduğu
250 hPa'da kayma 200–300 hPa arasından (~2,6 km) alındığı için seyreliyordu. Yeni
hesapta oranlar seviyeler arasında birbirine yaklaştı. Sabit eşikler (4e-7, 8e-7)
eski hesaba göre konmuştu ve yeni fizikte daha sık aşılıyor. Risk eşiği 8 Ekim'de
eğitim günlerinden 1-SE kuralıyla 7e-7'ye çekildi (bkz. §0.2); hafif eşiği (4e-7)
hâlâ kaba bir başlangıç değeridir.

### 4.1.2 Birleşik gösterge (log-normal EDR eşlemesi)

Beş gösterge (TI1, TI2, VWS, DEF, 1/Ri) Sharman ve Pearson (2017) yöntemiyle EDR'ye
eşlenip ortalandı. Eşleme için C1 = −2,953 ve C2 = 0,602 (20–45 kft) kullanıldı;
göstergelerin klimatolojisi pencere deposunun 49 eğitim gününden, 1,44 milyon ızgara
hücresinden geldi. Başarı ölçütü: birleşik göstergenin ROC-AUC'si tek başına TI1'i
geçmeli.

| Gösterge | PIREP, tümü (6.218 örnek, 64 gün) | TI1'e göre fark | PIREP holdout (1.151 örnek, 13 gün) | TI1'e göre fark |
|---|---|---|---|---|
| **Birleşik EDR** | **0,684 [0,666–0,702]** | **+0,013 [+0,010, +0,017], p < 0,001** | **0,719 [0,671–0,766]** | **+0,012 [+0,003, +0,021], p = 0,012** |
| TI1 | 0,671 [0,651–0,690] | — | 0,707 [0,657–0,755] | — |
| TI2 | 0,646 [0,625–0,666] | −0,025 | 0,682 [0,631–0,728] | −0,026 |
| 1/Ri | 0,647 [0,631–0,662] | −0,024 | 0,668 [0,615–0,714] | −0,040 |
| VWS | 0,641 [0,624–0,660] | −0,030 | 0,664 [0,611–0,721] | −0,043 |
| DEF | 0,630 [0,610–0,647] | −0,042 | 0,668 [0,623–0,709] | −0,039 |

**Sonuç:** Ölçüt sağlandı. Birleşik gösterge TI1'i hem tüm veride hem holdout'ta küçük
ama anlamlı bir farkla geçiyor. Tek tek göstergelerin hiçbiri TI1'i geçmiyor; kazanç
birleşimden geliyor. Fark küçük (≈ +0,01). Pratik anlamı, operasyonel bir iyileşme
değil, birleşimin zarar vermediği ve tutarlı yönde katkı sağladığıdır.

MADIS hafif ve üstü (12.232 ölçüm, 372 pozitif, **4 gün**, ön sonuç, GA yok):
birleşik EDR 0,773, TI1 0,735, 1/Ri 0,729, TI2 0,696, VWS 0,691, DEF 0,669. Orta ve
üstü MADIS ölçümü yok (0 örnek).

## 4.2 Makine öğrenmesi modeli (PIREP) — §2.1–2.2 tarihçe, 5 Ekim

### 4.2.1 Holdout sonuçları

Model, aktif modelle aynı türdedir (Random Forest, olasılığı sigmoid ile kalibre
edilmiş). Yalnız eğitim günlerinde (5.067 örnek, 51 gün) eğitilip zamansal holdout'ta
(son 13 gün) değerlendirildi. Aktif (nihai) model holdout'u da gördüğü için holdout'ta
değerlendirilmedi.

| Gösterge | Holdout ROC-AUC [%95 GA] | TI1'e göre fark [%95 GA] | p |
|---|---|---|---|
| **Model** | **0,730 [0,684–0,774]** | **+0,023 [+0,002, +0,044]** | **0,042** |
| Birleşik EDR | 0,719 [0,671–0,766] | +0,012 [+0,003, +0,021] | 0,012 |
| TI1 | 0,707 [0,657–0,755] | — | — |

| Model olasılık ölçütü (holdout) | Değer |
|---|---|
| Brier | 0,210 [0,196–0,222] |
| Brier becerisi (iklimsel taban oranına göre) | 0,157 |
| POD / POFD (eşik 0,5) | 0,70 / 0,35 |
| Ortalama olasılık / gözlenen oran | 0,533 / 0,529 |

Güvenilirlik diyagramı: [`veri/guvenilirlik_diyagrami.svg`](veri/guvenilirlik_diyagrami.svg).
PIREP holdout'ta noktalar köşegene yakın; olasılık PIREP taban oranına göre
kalibre. MADIS serisi köşegenin çok altında (bkz. §3).

### 4.2.2 Eğitim geçmişi ve olumsuz ara bulgu

7 Ekim'e kadar holdout her çalıştırmada son %20 güne kayıyordu; o satırlar birbiriyle
doğrudan karşılaştırılamaz, her satır kendi holdout'unda TI1 ile karşılaştırılır. 7 Ekim'den
sonra holdout 16 altın test günüdür; bu satırlar birbiriyle karşılaştırılabilir.

| Tarih | Fizik | Seçilen model | Model ROC-AUC | TI1 ROC-AUC | Karar |
|---|---|---|---|---|---|
| 3 Eki 2026 | eski | Gradient Boosting | 0,646 [0,62–0,67] | 0,667 [0,63–0,70] | Kapı geçilmedi (saklandı) |
| 4 Eki 2026 | eski | Gradient Boosting | 0,631 | 0,642 | Kapı geçilmedi (saklandı) |
| 5 Eki 2026 (gece işi) | eski | Random Forest | 0,686 | 0,666 | Aktifleştirildi |
| 5 Eki 2026 (yeni fizik) | yeni | Random Forest | 0,730 [0,684–0,774] | 0,707 [0,657–0,755] | TI1 kapısı geçildi; aktif modeli F1'de geçemedi (0,695'e karşı 0,704), saklandı |
| 7 Eki 2026 (ön paket, altın günler) | yeni | Lojistik Regresyon | 0,681 [0,646–0,716] | 0,673 [0,639–0,704] | Kapı geçilmedi (+0,008 [−0,006; +0,022]) |
| 9 Eki 2026 (gece işi, altın günler) | yeni | Random Forest | 0,707 | 0,675 [0,641–0,706] | TI1'i geçti (+0,033 [+0,018; +0,048]), aktifleştirildi; bugün de aktif |
| 18 Eki 2026 (dondurma raporu, altın günler) | yeni | Gradient Boosting | 0,710 [0,680–0,740] | 0,675 [0,641–0,706] | TI1'i geçti (+0,036); aktif modeli geçemedi (+0,003 [−0,001; +0,008]), saklandı |
| 18 Eki 2026 (nihai paket, sıralı sorgu) | yeni | Random Forest | 0,708 [0,677–0,738] | 0,675 [0,641–0,706] | TI1'i geçti (+0,033 [+0,018; +0,049]); paket modeli, sürüm kaydedilmez |

**Olumsuz ara bulgu (3 Ekim):** Doğru irtifalı veriyle yapılan ilk gerçek eğitimde model
tek başına TI1'i geçemedi (0,646'ya karşı 0,667). Kapılı aktivasyon modeli devreye
almadı. Bu sonuç olduğu gibi raporlanır: o veri hacminde ML'in fizik göstergesine
eklediği bir değer yoktu. Veri büyüdükçe (64 gün) ve fizik düzeltildikçe model TI1'i
anlamlı ama küçük bir farkla geçti (+0,023, GA alt sınırı +0,002).

5 Ekim'de aktif olan eski fizikli model, 9 Ekim'de yeni fizikle eğitilen Random Forest
aktifleşince devreden çıktı. O tarihten bu yana aktif model 9 Ekim RF'sidir (bkz. §0.1).

### 4.2.3 Duyarlılık analizleri (Madde 7, isteğe bağlı)

7 Ekim 2026'daki veriyle yapıldı: 7.815 örnek, 80 gün. Altın test günleri 16 gün ve
1.554 örnek. Komut `turbulans-ml-duyarlilik --cikti docs/rapor/veri`, ham sayılar
[`veri/ml_duyarlilik.json`](veri/ml_duyarlilik.json). Bu analizler eğitim protokolünü
ve aktif modeli değiştirmez.

**Gruplu CV (VRB-07).** Altın günler dışındaki 64 günde 5 kat ve 3 tekrarla CV yapıldı.
Gruplar gün, ISO hafta ya da takvim ayıdır.

| Gruplama | Grup | LR ROC-AUC (±SE) | RF | GB | 1-SE seçimi |
|---|---|---|---|---|---|
| Gün | 64 | 0,699 ± 0,009 | 0,705 | 0,698 | LR |
| ISO hafta | 50 | 0,698 ± 0,012 | 0,704 | 0,698 | LR |
| Ay | 27 | 0,698 ± 0,008 | 0,705 | 0,698 | LR |

Aynı veride TI1'in ROC-AUC'si 0,682'dir. Gruplar kabalaştıkça AUC değişmiyor; komşu
günler arasında sızıntıya dair bir iz yok. Sınırlama: günler 2018–2020'ye seyrek
dağılmış, 64 gün 50 ayrı haftaya düşüyor. Bu yüzden hafta gruplaması güne çok yakın ve
testin gücü sınırlı.

**Net örnek deneyi.** Bu deneyde yalnız net örneklerle eğitim yapıldı. Net negatif:
PIREP metni NEG/SMOOTH/SMTH ve hafif yok. Net pozitif: orta ve üstü, LGT/LT yok.
LGT-MOD gibi karışık raporlar dışarıda kaldı. Her model türü, altın günlerde standart
etiketle ölçüldü. Ham metin yalnız yerel IEM arşivinde (2018–Mart 2020) var. Eşleşmiş
örneklerin 6.759'unun metni bulundu; Nisan 2020 sonrası 12 günün metni yok, bu günler
net ve metinli eğitime girmedi. Kalibrasyon yapılmadı; ROC-AUC sıralamaya bağlı
olduğundan karşılaştırma için yeterli.

| Eğitim verisi | Örnek (pozitif oranı) | LR | RF | GB | Net − tüm, GA'sı 0'ı içeriyor mu |
|---|---|---|---|---|---|
| Tümü | 6.261 (%53) | 0,681 | 0,704 | 0,706 | — |
| Metni olanlar | 5.390 (%53) | 0,680 | 0,704 | 0,701 | — |
| Yalnız net | 2.390 (%73) | 0,685 | 0,701 | 0,708 | Üçünde de evet (LR +0,004 [−0,001; +0,008]) |

Aynı günlerde TI1'in ROC-AUC'si 0,673. Net etiketle eğitmek anlamlı bir iyileşme
getirmedi. LGT-MOD'u pozitife katan etiket tanımı korunuyor.

**Yan bulgu (karar değil).** Altın günlerde kalibre edilmemiş RF ve GB, TI1'i
sırasıyla +0,031 [+0,016; +0,047] ve +0,033 [+0,013; +0,053] farkla geçiyor. Protokolün
1-SE kuralıyla seçtiği LR ise geçemiyor (+0,008 [−0,006; +0,022]). Bu fark yalnız test
günlerine bakılarak görüldü. Seçim kuralını buna göre değiştirmek test verisine bakarak
model seçmek olur. Bu yüzden 18 Ekim dondurmasında protokol değişmeden uygulanır; bulgu
yalnız tartışma bölümünde yer alır. Dondurmada protokol değişmeden uygulandı; 1-SE kuralı
163 günlük veride ağaç modelini (sıralı sorguyla RF, ilk üretimde GB) seçti ve model TI1'i
geçti (§0.1).

### 4.2.4 RF ayarı ve bağlam özellikleri (F9 deneyi, 15 Ekim)

Komut `turbulans-ml-rf-deneyi --cikti docs/rapor/veri`, ham sayılar
[`veri/rf_deneyi.json`](veri/rf_deneyi.json). Altın test günleri okuma anında dışlandı:
12.855 örnek, 132 gün, pozitif oranı %54. Dış 5 kat gün gruplu CV; ayarlı RF iç 3 katta
RandomizedSearch (12 deneme) ile seçildi. Fark aralıkları kat dışı tahminlerde gün bazlı
eşleştirilmiş bootstrap. Aynı günlerde TI1 ROC-AUC 0,674. Protokol modeli, aktif model ve
sonuç paketi değişmedi.

| Özellikler | Lojistik | Sığ RF (derinlik 5) | Ayarlı RF | Ayarlı − sığ RF |
|---|---|---|---|---|
| Temel 8 | 0,690 | 0,699 | 0,700 | +0,001 [−0,000; +0,002] |
| Temel 8 + 5 bağlam | 0,711 | 0,706 | 0,709 | +0,003 [+0,001; +0,005] |

- Ayar neredeyse hiçbir şey kazandırmadı. İç CV en sık `min_samples_leaf` 20–100,
  `max_features` sqrt seçti.
- Bağlam özellikleri ayarlı RF'te +0,008 [+0,005; +0,012] ekledi. Geniş setle lojistik
  TI1'i +0,038 [+0,032; +0,044] geçiyor (temel setle +0,017).
- Permütasyon önemi (ROC-AUC düşüşü): yatay deformasyon 0,028, kolon en düşük Ri 0,022,
  düşey kayma 0,017, diverjans 0,012, Ri 0,010. Komşu TI1 maks/ort ≤ 0,002; TI1'in kendisi
  ~0, çünkü bilgisi kayma ve deformasyonda zaten var. Bağlam katkısının çoğu kolon Ri'sinden.
- OOB ROC-AUC gün gruplu CV ile neredeyse aynı (0,701 / 0,700; 0,711 / 0,709). Bu
  ayarlarda aynı günün örnekleri OOB'yi şişirmedi; beklenen iyimserlik gözlenmedi.

Bunlar eğitim günlerinde CV sonuçlarıdır, altın gün sonucu değildir. Geniş set ya da
yeni model, 18 Ekim'den sonra önceden yazılmış bir protokolle ve dondurmadan sonra
toplanan yeni günlerde değerlendirilecek. Aynı 16 altın günde değerlendirmek, bu
deneye bakıldıktan sonra seçim yapmak olurdu.

### 4.2.5 Dondurma sonrası yeni günler (§10, 27 Ekim; tek seferlik)

Protokol `deney_protokolu.md` §10, paket [`docs/sonuclar/2026-10-27_yeni_gun/`](../sonuclar/2026-10-27_yeni_gun/README.md).
Eğitim 163 dondurma günü, test modelin görmediği 79 gün (7.769 örnek). ROC-AUC: TI1 0,658,
temel set (RF) 0,685, geniş set (LR) 0,693.

- **H1 (geniş − temel):** +0,008 [+0,002; +0,014], desteklendi; dondurma gününe komşu 24 gün
  çıkarılınca +0,005 [−0,002; +0,012], anlamlı değil. Destek zayıf ve kırılgan.
- **TI1'e karşı:** temel +0,027 [+0,018; +0,035], geniş +0,035 [+0,026; +0,043]; ikisi de kapıyı
  geçti. 18 Ekim altın gün farkı (+0,033) modelin görmediği günlerde de korunuyor.
- Hafif raporlar negatiften çıkarılınca (Fikir 8) üç skor da belirgin yükseliyor (TI1 0,730,
  geniş 0,774), sıralama değişmiyor. Geniş setin üretime alınması ayrı karar (ONAY).

### 4.2.6 Model − birleşik EDR (§10.6, 28 Ekim; sonradan eklenen ikincil)

Kurul incelemesi (VER-04) üzerine §10 sonucundan sonra protokole eklendi (`docs/deney_protokolu.md`
§10.6, commit `87e54fd`, skordan önce). Aynı 163 eğitim günü ve §10'un 79 test günü (7.772 örnek;
§10'da 7.769, 28 Ekim'de yarıda kalan gece işi bu günlerde 3 örnek daha eşleştirmiş). Yeniden
üretilen temel model ROC-AUC'si 0,685 (§10 ile aynı). Birleşik EDR 0,669 [0,656; 0,683].

| Karşılaştırma (gün bloklu eşleştirilmiş bootstrap) | Fark [%95 GA] |
|---|---|
| Temel (RF) − birleşik EDR | +0,016 [+0,010; +0,021], p < 0,001 |
| Geniş (LR) − birleşik EDR | +0,024 [+0,017; +0,031] |
| Birleşik EDR − TI1 | +0,011 [+0,007; +0,015] |

Model, eğitimsiz fizik birleşimini (Sharman–Pearson eşlemesi) de küçük ama anlamlı farkla geçiyor;
birleşik EDR de TI1'i geçiyor (18 Ekim altın günlerdeki +0,013 ile tutarlı). Ön kayıtlı değildir,
"sonradan eklenen ikincil" olarak okunmalıdır. Paket `docs/sonuclar/2026-10-28_birlesik_kiyas/`.

### 4.2.7 Bölme ve etiket tanımının etkisi (§10.7, 28 Ekim; keşifsel)

Literatürdeki 0,86–0,90 ile farkın kaynağını ayırmak için (kurul #7) yalnız 147 eğitim gününde
(14.450 örnek; altın ve §10 günleri hariç) sabit RF (200 ağaç, derinlik 5) ve TI1, 2 × 2 koşulda,
her biri 20 bölmeyle puanlandı (protokol §10.7, commit `708ea6e`, skordan önce).

| Koşul | RF ROC-AUC | TI1 ROC-AUC |
|---|---|---|
| Gün gruplu 70/30, hafif = negatif (bu çalışma) | 0,702 [0,691–0,714] | 0,674 |
| Rastgele örnek 70/30, hafif = negatif | 0,701 [0,691–0,710] | 0,672 |
| Gün gruplu 70/30, hafif çıkarılmış | 0,785 [0,763–0,802] | 0,738 |
| Rastgele örnek 70/30, hafif çıkarılmış | 0,785 [0,772–0,805] | 0,740 |

Aralıklar 20 bölmenin 2,5–97,5 yüzdelikleridir. Rastgele bölme bu veride AUC'yi şişirmedi
(−0,001); sonuç görüldükten sonra eklenen derin RF (`max_depth=None`) varyantında da +0,001 (§2.4'teki
OOB bulgusuyla tutarlı). Hafif raporları çıkarmak 0,083 (TI1'de 0,063) artırdı. Farkın ölçülen
kısmı etiket tanımından gelir; kalan ~0,08–0,12 bölge, özellik (koordinat, BADA) ve modelle ilgilidir,
ölçülmedi. Paket `docs/sonuclar/2026-10-28_protokol_farki/`.

### 4.2.8 Göreli ekonomik değer (REV; 28 Ekim, ek analiz)

Altın test günlerinin POD/POFD'si (yeniden puanlama yok) Richardson (2000) maliyet/kayıp modeline
kondu (kurul #16). PIREP örnek taban oranında (s = 0,476) en yüksek REV: TI1 eşik zarfı 0,26, TI1 risk
eşiği (7e-7) 0,25, model (olasılık ≥ 0,5) 0,30; değer yalnız α = C/L ≈ 0,3–0,8 bandında pozitif.
Kaçınma bedeli medyanı (%2,2 sefer yakıtı, §uyarı oranı) C alınırsa TI1 risk eşiği, bir orta-üstü
karşılaşmanın kaybı sefer yakıtının %3,4–5,8'i arasındaysa "hep sap / hiç sapma"dan ucuzdur. Aynı
POD/POFD'nin MADIS EDR ≥ 0,1 oranına (s = 0,029; farklı olay, aktarılabilirlik varsayımı) uygulandığı
gösterimde bu aralık %39–114'e çıkar. POD/POFD nokta başınadır, rota başına değildir; PIREP taban oranı
operasyonel sıklık değildir; kaybın gerçek değeri bilinmiyor. Sonuç sıralama ve mertebe içindir, eşik ya
da seçim ağırlığı önerisi değildir. Paket `docs/sonuclar/2026-10-28_ekonomik_deger/` (şekil `rev_egrileri.png`).

### 4.2.9 GFS tahmin ufku tutarlılığı (#11; 28 Ekim, ek analiz)

UCAR THREDDS'in tuttuğu son ~7,5 günün koşularından, 23–28 Ekim 2026'daki 11 geçerlilik zamanı (00/12Z)
için f000, f024 ve f048 Türkiye kutusunda (200/250/300 hPa, 14 MB) indirildi; her zamanda 5.000 rastgele
noktada (FL310–380) TI1 karşılaştırıldı (GFS eşiği 8,3e-7). f024: Spearman medyanı 0,67 [0,61–0,77], f000'da
riskli olanların %57'si tahminde de riskli; f048: 0,50 [0,39–0,59], %43. Riskli oran ufukla değişmiyor
(%8,3 → %7,4) ama yeri değişiyor. 3 saatlik zaman örneklemesinin etkisinden (Spearman 0,923) çok daha büyük.
Referans GFS'in kendi analizidir; gözlemle (ERA5) kıyas ERA5'in yayın gecikmesi yüzünden 3 Kasım'a kaldı.
Paket `docs/sonuclar/2026-10-28_tahmin_ufku/`.

### 4.2.10 Keşifsel göstergeler (protokol §13; 31 Ekim, skorlardan önce kayıtlı)

Hepsi keşifseldir; birincil sonuç, model ve rota kararı değişmedi. Örnek düzeyi §10'un sabit 79 test
gününde (7.772 örnek; §10'da 7.769, o günlere sonradan 3 örnek eşleşti; temel set ROC-AUC 0,685 aynı):

| Analiz | Sonuç (ROC-AUC farkı, gün bloklu %95 GA) |
|---|---|
| Fikir 10, komşuluk maksimumu (±1 hücre/seviye/saat) − TI1 | +0,027 [+0,017; +0,037]; yalnız yatay ±1 hücre +0,020 [+0,016; +0,024] |
| Aynı pencere, 7e-7 eşiğinde | POD 0,49 → 0,85, POFD 0,25 → 0,64 (pencere iki sınıfı birlikte büyütür; eşik yeniden seçilmeli) |
| Fikir 11 devamı, çoklu /TB grubunun en şiddetlisi | 22 test etiketi 0→1 (1→0 yok); TI1, birleşik EDR ve modellerde etki ≤ +0,002 |
| Fikir 24, AUC² ağırlıklı − eşit ağırlıklı birleşik EDR | −0,0003 [−0,0005; −0,0001]; ağırlıklar 0,18–0,21, pratikte fark yok |
| Fikir 19, tek başına (TI1 0,658) | frontogenez 0,518, \|F\| 0,591, \|∇T\| 0,559, −PV 0,510; hepsi TI1'den zayıf |
| Fikir 19, temel + 3 teşhis − temel model | −0,004 [−0,010; +0,002]; F9 adayı değil (NCSU1 kaynak yokluğundan hesaplanmadı) |

Izgara düzeyi NE-ABD ERA5 küplerinde, dondurma günleri çıkarılmış 41 günde (660 PIREP, FL300–390): POD–uyarı
alanı eğrisinin altındaki alan TI1 0,631 [0,585; 0,671], birleşik EDR 0,654 (TI1'e göre +0,024 [+0,013; +0,037]),
TI3 0,646 (+0,015 [−0,010; +0,043], fark gösterilemedi; Fikir 15). 7e-7 eşiğinde ızgaranın %16,3'ü uyarı
alanında, orta-üstü PIREP'lerin %33'ü (POD) ve kontrol raporlarının %18'i (POFD) eşik üstünde. TTS hesaplanmadı.
Okuma: nokta eşleştirme PIREP konum/zaman hatası yüzünden ayırma kaybediyor; birleşik EDR'nin TI1'e üstünlüğü ızgara
düzeyinde de görülüyor (A2 için ilk aday). Paketler `docs/sonuclar/2026-10-31_kesifsel_gostergeler/` ve
`docs/sonuclar/2026-10-31_uyari_alani/`.

## 4.3 Nesnel değerlendirme: MADIS ölçülen EDR (M1) — tarihçe, 5 Ekim (güncel: §0.4)

Etiket: MADIS maxEDR ≥ 0,1 (hafif ve üstü). 12.232 ölçüm, 372 pozitif (%3,0), 4 gün.
Gün bazlı GA için en az 5 gün gerektiğinden aralık verilmedi; sonuçlar **ön sonuçtur**.
MADIS günlerinin dördü de modelin eğitim günleriyle çakışıyor. Model MADIS etiketini
hiç görmedi, ama aynı günlerin PIREP'leriyle eğitildi. Bu yüzden değerlendirme
iyimser olabilir.

| Gösterge | ROC-AUC (nokta) |
|---|---|
| Model (eğitim günleriyle eğitilmiş Random Forest) | 0,794 |
| Birleşik EDR | 0,773 |
| TI1 | 0,735 |

| Model olasılık ölçütü (MADIS) | Değer |
|---|---|
| Brier | 0,247 |
| Brier becerisi | −7,4 |
| Ortalama olasılık / gözlenen oran | 0,485 / 0,030 |

Model sıralamada (ROC-AUC) MADIS'te de TI1'den iyi, ama **olasılıkları ölçülen
sıklığa göre kalibre değil**. Ortalama tahmin %49, gerçek oran %3; Brier becerisi
negatif. Nedeni §4'teki raporlama yanlılığıdır. Bu yüzden arayüzde olasılık mutlak
sıklık olarak sunulmaz.

## 4.4 PIREP raporlama yanlılığı (Madde 7)

PIREP'lerin **%52,3'ü pozitif** (orta ve üstü; 6.218 örnek); holdout'ta %52,9. Aynı
pencerelerdeki MADIS ölçümlerinde hafif ve üstü oranı **%3,0**, orta ve üstü
**%0**'dır. Pilotlar türbülans yaşadığında rapor verir, sakin havayı nadiren raporlar.
Bu yüzden PIREP örneklemi türbülansa doğru güçlü biçimde yanlıdır. Sonuçları:

- Modelin olasılığı "PIREP verilmiş bir noktada orta ve üstü türbülans" olasılığıdır;
  bir uçuş noktasındaki mutlak türbülans sıklığı değildir.
- ROC-AUC taban orandan bağımsız olduğu için sıralama becerisi anlamlıdır; Brier ve
  güvenilirlik ise etiket kaynağına bağlıdır (§2.1 ile §3'ü karşılaştırın).
- "Negatif" PIREP'ler (sakin raporlar) de seçilmiş bir örneklemdir; rastgele noktaları
  temsil etmez.

## 4.5 Sanal PIREP ve denetimsiz taban

Kural tabanlı sanal PIREP: POD 1/8, POFD 0/8 (16 PIREP). LOF tabanı, ADS-B
kuantizasyonu nedeniyle seyir noktalarının %68'inin aynı vektör olmasıyla
bozuluyordu. Kuantizasyon titreşimiyle düzeltildikten sonra da denetimsiz yöntemler
ayırt edici çıkmadı. Ayrıntı: ADR 0011.

## 4.6 Veri dondurma

Veri ve protokol **18 Ekim 2026**'da donduruldu (nihai paket 18 Ekim 00:25 UTC, commit
`5ddcd40`). Bu tarihten sonra eğitim verisi, etiket tanımı, holdout kuralı ve kapı ölçütü
değişmez. Rapordaki nihai sayılar `db_yedekleri/kalici/turbulans_20261018_dondurma.dump`
yedeğinden (18 Ekim 00:02 UTC; saklama süresiyle silinmez, disk dışında şifreli kopyası var)
yukarıdaki komutla yeniden üretilir: yedekten ve canlıdan üretilen paketler birebir aynı
çıktı. Geri yükleme tatbikatı da bu yedekle yapıldı (README "Veritabanı yedeği"). Canlı veritabanında gece işi eşleşen örnekleri
güncellemeye devam ettiği için aynı komut canlı veride farklı sayı verir; kesme
`olusturulma_zamani`'na göredir ve sonradan eşleşen eski satırları dışlamaz.
Dondurmadan önce kapanan işler:

- ~~Penceresiz 1.597 örneğin yeni fizikle yeniden indirilmesi~~ (7 Eki: penceresiz eşleşmiş örnek kalmadı)
- ~~TI1 eşiklerinin yeni fiziğe göre yeniden değerlendirilmesi~~ (8 Eki: §0.2, 1-SE kuralıyla 7e-7)
- ~~MADIS'te en az 5 güne ulaşılması (GA için)~~ (7 Eki: 6 gün, §0.4)

# 5. Katkılar

Her katkının yanında depoda
nerede görüleceği, sınırı ve literatürdeki en yakın çalışmadan farkı yazılıdır
(künyeler: `ILGILI_CALISMALAR.md`); jüri sorusunda kanıt buradan gösterilir.

Sistem sertifikalı EDR üretmez; karar destek aracıdır.

## Özet

Türbülans Radar, açık veri kaynaklarını (OpenSky ADS-B, Copernicus ERA5, NOAA GFS,
AWC SIGMET, IEM PIREP) tek bir otonom arka uçta birleştirerek seyir irtifasında
türbülans riskini hesaplayan, belirsizliğini söyleyen ve riskten kaçınan rotayı
öneren bir karar destek sistemidir. Katkılar üç grupta toplanır: veri ve etiket
kalitesi, değerlendirme ve belirsizlik, karar ve işletim.

## 5.1 Veri ve etiket kalitesi

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
gerçek CDS). Güncel değer 15.940 PIREP'te (163 gün) 0,673 (`docs/sonuclar/2026-10-18/SAYILAR.md`).
- Kanıt: `ml/ml_veri_hatti.py`, `dogrulama/bagimsiz_kanit.py` (`pirepleri_normalize_et`).
- Sınır: PIREP öznel ve gecikmelidir. Nesnel etiket olarak NOAA MADIS'in herkese açık
  uçak EDR arşivi kullanılır (geliştirme planı M1, ADR 0012); yalnız 14 gün ve fiilen hafif sınıf.
- En yakın çalışmadan farkı: Schwartz (1996) PIREP'in nicel kullanımındaki gürültüyü genel olarak tartışır; biz açık IEM arşivinde somut iki hatayı (FL alanının feet olması, /OV UNK konumu) bulup etiket hattını bunlara göre yeniden kurduk.

**K3. Kendiliğinden büyüyen, kotalı ve tekrar indirmesiz eğitim verisi.**
Gece işi IEM'den yeni PIREP'leri çeker, gün/bölge gruplarıyla küçük ERA5 dilimleri
ister (gece ≤ 60, gün ≤ 150 CDS isteği) ve dilimleri bir pencere deposunda saklar;
yeni bir özellik denemek için veri yeniden indirilmez.
- Kanıt: `ml/ml_veri_hatti.py`, `ml/ozellik_deposu.py`, ADR 0002; durum
  `GET /api/v1/ml/durum`.
- En yakın çalışmadan farkı: Muñoz-Esparza vd. (2020) sabit ve kapalı bir yerinde EDR veri kümesiyle çalışır; bizim eğitim verimiz açık kaynaklardan her gece sağlayıcı kotaları içinde büyür ve ham pencereler saklandığı için yeni bir özellik yeniden indirmeden denenir.

## 5.2 Değerlendirme ve belirsizlik

**K4. Sızıntıya dayanıklı değerlendirme protokolü ve kapılı model aktivasyonu.**
Aynı günün raporları aynı katta kalır (gün gruplu çapraz doğrulama); değerlendirme,
hiçbir eğitime girmeyen dondurulmuş altın test günlerindedir; güven aralıkları gün blok
bootstrap ile, TI1'e göre fark eşleştirilmiş AUC testiyle verilir. Aday model ancak altın
günlerde ROC-AUC farkı TI1'e karşı en az 0,02 ve %95 GA alt sınırı 0'ın üstündeyse, aktif
model varsa ona karşı da aynı kural (≥ 0,02, alt sınır > 0) sağlanırsa aktif olur; aksi
halde yalnızca sürüm olarak saklanır ve geri alınabilir.
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
TI1'in bağımsız becerisi seyir PIREP'lerinde ölçüldü: 15.940 PIREP, ROC-AUC 0,673
[0,661–0,684]; altın test günlerinde 0,675, veriden seçilen eşikte (7e-7) yakalama 0,501,
yanlış alarm 0,248; MADIS ölçülen EDR'de 0,722 (`docs/sonuclar/2026-10-18/SAYILAR.md`). Gerçek bir
uçuşta (PUE502) aktif TURB SIGMET'i
yakalamadığı gösterildi. Sonuç, her rota yanıtında ve arayüzde gösterilen bir
güvenilirlik notuna ve güvenliğin SIGMET sert kısıtına dayandırılmasına dönüştü.
- Kanıt: `fizik/turbulans_indeksleri.py` (`TI1_GUVENILIRLIK_NOTU`),
  `dogrulama/bagimsiz_kanit.py`, `docs/SISTEM_KARTI.md` §6.
- En yakın çalışmadan farkı: Kim vd. (2011) ile Sharman ve Pearson (2017) teşhislerin becerisini ölçüp operasyonel birleşime ağırlık olarak kullanır; biz ölçülen sınırı (TI1 ROC-AUC 0,673) ürün davranışına taşıdık: TI1 yumuşak, SIGMET sert kısıt, her yanıtta güvenilirlik notu.

## 5.3 Karar ve işletim

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
- Ağsız demo paketi; 1.182 otomatik test (28 Ekim 2026) ve 6 işli CI (sır taraması, SBOM, tarayıcı
  testleri, ağsız demo dahil); ölçülmüş performans raporu.
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

# 6. Sınırlamalar ve Öğrenilen Dersler

## 6.1 Sınırlamalar

**Sertifikasyon yok.** Sistem sertifikalı EDR üretmez ve operasyonel karar aracı
değildir; karar destek aracıdır. Birleşik EDR, reanalizden türetilmiş bir tahmindir.
Uçaktan ölçülen EDR'nin yerini tutmaz. Kabin önerisi "karar kaptanındır" ifadesiyle
verilir. Hiçbir çıktı havacılık otoritesinin onayından geçmemiştir.

**Kapsam yalnızca açık hava türbülansı (CAT).** Konvektif, bulut içi, dağ dalgası ve
iz türbülansı kapsam dışıdır. Yalnızca seyir safhası (ToC–ToD, FL280 üstü)
değerlendirilir. NTSB (2021) türbülans yaralanmalarının önemli bir kısmının alçak
irtifada ve yaklaşmada olduğunu gösterir; bu olaylar sistemin göremediği yerdedir.

**Yalnızca ABD verisi.** Eğitim etiketleri (IEM PIREP) ve nesnel doğrulama (MADIS EDR)
ABD hava sahasındandır; 163 gün, 15.940 PIREP (16 gün altın test). Türkiye ya da Avrupa
için geçerlilik gösterilmedi. Rota ve arayüz Türkiye'de çalışır ama oradaki beceri ölçülmedi.
Yerel MADIS EDR deposu bu açığı kapatmaz: 11 günde Avrupa'da (35–60°K, 10°B–30°D) FL280 üstü
21.167 gözlem var ama yalnızca 28'i hafif ve üstü (EDR ≥ 0,1); Türkiye/Doğu Akdeniz'de (34–43°K,
25–45°D) hiç yok. O günler için Avrupa ERA5 penceresi de indirilmemiştir. 28 pozitifle ROC-AUC
güven aralığı anlamlı olmayacağından Avrupa skoru raporlanmaz.
Göstergelerin log-normal eşleme klimatolojisi de ABD PIREP pencerelerinden gelir.

**Doğrulama reanalize dayalı.** Göstergeler ERA5 reanalizinden (0,25°, saatlik)
hesaplanır. Reanaliz, uçuş anında elde olmayan ve gözlemlerle düzeltilmiş bir "en iyi
tahmin"dir. Bu yüzden ölçülen beceri, gerçek zamanlı bir tahmin modelinin (GFS)
becerisinin üst sınırına yakındır; canlı GFS ile beceri ayrıca ölçülmedi. Canlı GFS
küpü 3 seviyeyle indirildiği için kayma orada 50 hPa'lık katmandan hesaplanır.
Eğitim ise 25 hPa'lık katmanla yapıldı.

**Etiket kaynaklı sınırlar.** PIREP'ler türbülansa doğru güçlü biçimde yanlıdır:
pozitif oranı %53, aynı yerlerdeki MADIS ölçümlerinde hafif ve üstü %3. Model
olasılıkları bu yüzden mutlak sıklık değildir. MADIS ölçümleri yalnız 14 gündür, kalite
kontrolsüzdür (QC "Z") ve PIREP pencerelerinin içinden gelir; sonuçlar ön sonuçtur.

**İstatistiksel sınırlar.** Birleşik EDR'nin TI1'e üstünlüğü anlamlı ama küçüktür
(altın test günlerinde +0,013 ROC-AUC). Model TI1'i geçti (+0,033 [+0,018; +0,049];
`docs/sonuclar/2026-10-18/SAYILAR.md`), ama 7 Ekim ön paketinde 80 günle geçememişti; sonuç
veri hacmine duyarlı. Altın test 16 gündür; güven aralıkları geniştir. Aynı 16 gün 9 Ekim'de
canlı modelin aktivasyon kararında da kullanıldı.
Sanal PIREP 16 PIREP'le ölçüldü ve eşikleri kalibre edilmedi. ATC ayırma komutu ve TCAS uyarısı ayrıca
elenmez (seviye değişimi seyir sayılmaz, düşey hız tepkisi aranır, bildirim için ≥ 2 uçak gerekir);
bildirimdeki ERA5 TI1 uyum etiketi olayı elemez ve başarımı ölçülmedi.
Kazanç raporlarken büyük daire referansı rüzgâr kazancını da içerir; kaçınma bedeli ayrıca
`referans_karsilastirmasi.kacinma_bedeli` ile rüzgâr-optimum rotaya göre verilir. TI1 risk eşiği 8 Ekim'de
eğitim günlerinden 1-SE kuralıyla 7e-7 seçildi; hafif eşiği (4e-7) hâlâ kaba bir
başlangıç değeridir.

**Çözünürlük.** ERA5'in 0,25° ızgarası ve 25 hPa'lık katmanı, uçağın algıladığı
ölçeği (yaklaşık 100 m – 1 km) çözemez; ince kararsız katmanlar (Ri < 0,25)
örneklerin yalnızca %1,4'ünde görülür. PIREP'ler en yakın ızgara noktası ve saatle eşleşir; konum
ve zaman hatası bu eşleştirmede ayırma kaybettirir: ±1 hücre/seviye/saat penceresindeki TI1 maksimumu
ROC-AUC'yi 0,027 artırır (protokol §13.1, keşifsel). Rota kararı nokta değerini kullanmaya devam eder.

**Aktarım ve kapsam dışı bırakılanlar.** Eşikler, birleşik EDR katsayıları ve model
ERA5 ile seçildi; canlı GFS'ye doğrulanmadan aktarılır. Eşikler mevsime göre ayrılmadı.
Türbülans riski uçak tipinden, yakıt akışı irtifa ve kütleden bağımsızdır. Sanal PIREP
seviye değişikliğini olay saymaz. ICAO uçuş planı (Item 15/EET) üretilmez; ATFCM/CTOT ve
sektör kapasitesi kapsam dışıdır. Backtest FRA modunu ölçmez. Bunlar bilinçli kapsam
kararlarıdır; ayrıntı `docs/SISTEM_KARTI.md` §5'te.

**Operasyonel karşılaştırma yok.** GTG ve WAFS ürünleriyle aynı veride doğruluk
karşılaştırması yapılmadı (M3). Sistemin operasyonel ürünlerden iyi ya da kötü olduğu
söylenemez.

## 6.2 Öğrenilen dersler

Her olay için ne olduğu (tespit), neye yol açtığı (etki) ve tekrarını önlemek için ne
yapıldığı (önlem) yazılıdır.

### 6.2.1 Git geçmişinde şifre sızıntısı

- **Tespit:** 21 Eylül 2026'da OpenSky şifresi Türkçe adlı bir değişkene düz metin
  yazılıp `kimlik_dogrulama.py` içinde commit'lendi. Ertesi gün koddan kaldırıldı ama
  git geçmişinde kaldı. Varsayılan sır tarayıcı kuralları Türkçe değişken adlarını
  tanımadığı için otomatik olarak yakalanmadı. Önceki sürümün (V1) ayrı deposunda da
  Trino bağlantı dosyasında düz metin kullanıcı adı ve şifre vardı.
- **Etki:** Şifre GitHub'daki geçmişte okunabilir durumdaydı. Hesabın kendisi, veri
  kotası ve kullanım şartları risk altındaydı.
- **Önlem:** Şifre 1 Ekim'de değiştirildi. Geçmiş 2 Ekim'de `git filter-repo` ile
  yalnızca ilgili blob'daki değer silinerek temizlendi; V1 deposu 4 Ekim'de düzeltildi.
  Sırlar artık yalnız `.env` ya da Docker secret'tan okunuyor. Her commit'te ve CI'da
  Türkçe değişken adlarını da tanıyan gitleaks taraması çalışıyor; CI, Türkçe adlı
  sahte bir sırrın yakalandığını her çalıştırmada doğruluyor (ADR 0008). Kalan iz: GitHub'daki PR #1 eski
  commit'leri tutuyor; depo herkese açılmadan önce GitHub'dan "sensitive data removal"
  istenecek.

### 6.2.2 FL alanının feet sanılması

- **Tespit:** 30 Eylül 2026'da, ML veri hattı yeniden kurulurken ham IEM PIREP arşivi
  eski eğitim CSV'siyle karşılaştırıldı. Eşleşen 1.754 kaydın medyan "FL" değeri 300–400
  çıktı. IEM'in `FL` sütununun uçuş seviyesi değil **feet** olduğu anlaşıldı
  (FL360 → 36000).
- **Etki:** Eski veri seti "FL 300–400" filtresiyle seyir yerine 300–400 ft'teki (pist,
  yaklaşma, rüzgâr kesmesi) raporları seçmişti; bunlar 200–300 hPa ERA5'le
  eşleştirilmişti. O veriyle TI1'in ROC-AUC'si 0,44 ölçülmüş (rastgeleden kötü), 167
  örnekli ilk model ve EDR ölçek katsayısı bu hatalı veriye dayanmıştı.
- **Önlem:** Etiket hattı ham arşivden doğru birimle (FL280–FL420) yeniden kuruldu. Aynı
  ölçüm doğru veride 0,71 verdi (tarihçe: 1 Ekim, 1.000 PIREP; güncel değer
  `docs/sonuclar/` paketinde). Eski model kullanım dışı bırakıldı, eski hat açık bir
  hata mesajıyla kapatıldı (`ESKI_VERI_HATTI_MESAJI`). Ders: dış veri kaynağının
  birimini belgesine güvenmeden ham değerin dağılımıyla doğrula.

### 6.2.3 Konumu bilinmeyen PIREP'ler (/OV UNK)

- **Tespit:** 3 Ekim 2026'da PIREP konumları incelenirken IEM'in konumu bilinmeyen
  raporları (`/OV UNK`) UNK istasyonuna (Unalakleet, Alaska) yerleştirdiği görüldü.
- **Etki:** Arşivde seyir irtifasında 145 rapor yanlış konumla eğitim ve doğrulama
  verisine girebiliyordu; veritabanında 40 kayıt etkilenmişti. Bu raporlar Alaska'daki
  ERA5 hücreleriyle eşleşip gerçek konumlarından bağımsız etiket üretiyordu.
- **Önlem:** Ayrıştırmada `/OV UNK` raporları atılıyor ve bunun için test var
  (`dogrulama/bagimsiz_kanit.py`, commit 9a19e07); etkilenen 40 kayıt kapsam dışı
  bırakıldı. Ders: "bilinmiyor" değeri sessizce varsayılan bir değere dönüştürülmemeli,
  açıkça reddedilmelidir. Aynı ilke eşleştirmede de uygulanır: kapsam dışı nokta "0
  risk" değil "hesaplanmadı" olarak raporlanır.

# 7. Sonuç ve Gelecek Çalışma

## 7.1 Sonuç

Araştırma sorusunun ölçme kısmına cevap şudur: yalnız açık veriyle, gerçek uçuş izinin
barometrik seviyesinde hesaplanan TI1 seyir türbülansını sınırlı bir beceriyle ayırt eder
(15.940 PIREP'te ROC-AUC 0,673). PIREP'lerle eğitilen model bu sınırı küçük ama tutarlı bir
farkla aşar: önceden yazılmış protokolle, modelin görmediği 79 yeni günde +0,027
[+0,018; +0,035]; 18 Ekim altın günlerinde +0,033 [+0,018; +0,049]. Fark iki bağımsız ölçümde
benzerdir, ama mutlak beceri ROC-AUC 0,69 civarındadır.

Tasarım kısmına cevap bu ölçümden çıkar: becerisi bu düzeyde olan bir gösterge rota kararında
güvenlik garantisi veremez. Bu yüzden güvenlik SIGMET ve kısıtlı saha sert kısıtına dayanır; TI1
yumuşak kısıttır, yasaklamaz ama adaylar arasında seçimde yakıttan önce gelir. Bu ayrım ürünün
davranışına taşındı: her yanıt güvenilirlik notu, üretim bilgisi ve gerektiğinde "belirsiz" ya da
"kapsam dışı" durumu taşır. Bağımsız rota backtest'i (NE-ABD) önerilen rotaların PIREP tüpündeki
orta ve üstü payını 0,71 [0,58; 0,90] oranına indirdiğini gösterir; tek bölge ve simüle rota
olduğu için bu bir operasyonel kazanç iddiası değildir.

Çıktılar sertifikalı EDR değildir; sistem operasyonel karar aracı değil, karar destek aracıdır.

## 7.2 Gelecek çalışma

Ürün yönü: önce ölçmek, sonra tahmin etmek. Doğrulama karnesi olmayan bir tahmin ürünü eklenmez.

1. **Türkiye ve Avrupa için nesnel etiket.** Bugünkü beceri yalnız ABD verisiyle ölçüldü; MADIS'te
   Türkiye için ölçüm yok. Aday yollar MGM ve IATA Turbulence Aware'dır
   (`docs/fizibilite/TURKIYE_ETIKET_KAYNAKLARI.md`). Etiket gelene kadar Türkiye TURB SIGMET'leri
   ile TI1'in küçük örneklemli kıyası ilk kanıt olabilir. Transfer öğrenme (Zhu vd., 2026) etiket
   yokluğu için bir yoldur.
2. **Doğrulama karnesi.** Kaynak başına (PIREP, MADIS EDR) dönemsel ROC-AUC, PR-AUC, POD/POFD;
   dondurmadan sonra toplanan yeni günlerde düzenli üretim.
3. **Birleşik EDR ya da ML'in rota cezasına girmesi.** Birleşik EDR, ızgara düzeyinde de TI1'den iyi
   (POD–alan AUC +0,024 [+0,013; +0,037], protokol §13.5); eşik seçimi ve GFS doğrulaması önce
   yapılır.
4. **Tahmin ufku ve topluluk.** GFS TI1'inin riskli alanları 24 saatte bile yarı yarıya kayıyor
   (f000'da riskli olanların f024'te %57'si riskli); ERA5'e karşı kıyas ve GEFS topluluk olasılığı
   48 saatlik `ongoru_belirsiz` sınırının kalibrasyonu için gereklidir.
5. **Tırmanma ve alçalma.** Kazaların yarısı alçak irtifada; 400–850 hPa, CAPE ve arazi bilgisiyle
   seyir modelinden ayrı bir model ve ayrı etiketler (konvektif, dağ dalgası, rüzgâr kesmesi).
6. **Kullanılabilirlik.** Dispeçer ve pilotlarla kullanılabilirlik oturumları; geri bildirim kaydı
   bugün yalnız kullanıcı algısını ölçer.

# Kaynakça

- ☑ Angelopoulos, A. N. ve Bates, S. (2021). A gentle introduction to conformal prediction and distribution-free uncertainty quantification. arXiv:2107.07511.
- ☑ Barber, R. F., Candès, E. J., Ramdas, A. ve Tibshirani, R. J. (2021). Predictive inference with the jackknife+. *The Annals of Statistics*, 49(1). https://doi.org/10.1214/20-AOS1965
- ☑ Cheung, J. C. H. (2018). Flight planning: node-based trajectory prediction and turbulence avoidance. *Meteorological Applications*, 25(1), 78–85. https://doi.org/10.1002/met.1671
- ☑ Di Vito, V., Zollo, A. L., Cerasuolo, G., Montesarchio, M. ve Bucchignani, E. (2025). Clear-air turbulence and aviation operations: A literature review. *Sustainability*, 17(9), 4065. https://doi.org/10.3390/su17094065
- ☑ Ellrod, G. P. ve Knapp, D. I. (1992). An objective clear-air turbulence forecasting technique: verification and operational use. *Weather and Forecasting*, 7(1), 150–165. https://doi.org/10.1175/1520-0434(1992)007<0150:AOCATF>2.0.CO;2
- ☑ Ellrod, G. P. ve Knox, J. A. (2010). Improvements to an operational clear-air turbulence diagnostic index by addition of a divergence trend term. *Weather and Forecasting*, 25(2), 789–798. https://doi.org/10.1175/2009WAF2222290.1
- ☑ Foudad, M., Sanchez-Gomez, E., Jaravel, T., Rochoux, M. C. ve Terray, L. (2024). Past and future trends in clear-air turbulence over the Northern Hemisphere. *Journal of Geophysical Research: Atmospheres*, 129(13), e2023JD040261. https://doi.org/10.1029/2023JD040261
- ☑ Gill, P. G. (2014). Objective verification of World Area Forecast Centre clear air turbulence forecasts. *Meteorological Applications*, 21(1), 3–11. https://doi.org/10.1002/met.1288
- ☑ Gökdeniz, K. ve Ülkü, İ. (2026). Predictive modeling of high-altitude clear air turbulence in the United States: A machine learning approach. arXiv:2607.11899 [physics.ao-ph].
- ☑ Gu, A. ve Wang, Y. (2024). Optimizing clear air turbulence forecasts using the K-nearest neighbor algorithm. *Journal of Meteorological Research*, 38(6), 1064–1077. https://doi.org/10.1007/s13351-024-4060-7
- ☑ Hart, P. E., Nilsson, N. J. ve Raphael, B. (1968). A formal basis for the heuristic determination of minimum cost paths. *IEEE Transactions on Systems Science and Cybernetics*, 4(2), 100–107. https://doi.org/10.1109/TSSC.1968.300136
- ☑ He, Q., Gao, Z., Xu, X. ve Li, Y. (2026). A comparative study of threshold-setting methods for clear-air turbulence diagnosis over China using PIREPs and ERA5 data. *Atmosphere*, 17(10), 931. https://doi.org/10.3390/atmos17100931
- ☑ Hersbach, H. vd. (2020). The ERA5 global reanalysis. *Quarterly Journal of the Royal Meteorological Society*, 146(730), 1999–2049. https://doi.org/10.1002/qj.3803
- ☐ ICAO. *Annex 3 to the Convention on International Civil Aviation: Meteorological Service for International Air Navigation* (EDR raporlaması ve WAFS).
- ☐ ICAO. *Doc 9574: Manual on a 300 m (1 000 ft) Vertical Separation Minimum* (RVSM irtifa tutma toleransı).
- ☑ Kim, J.-H., Chun, H.-Y., Sharman, R. D. ve Keller, T. L. (2011). Evaluations of upper-level turbulence diagnostics performance using the Graphical Turbulence Guidance (GTG) system and pilot reports (PIREPs) over East Asia. *Journal of Applied Meteorology and Climatology*, 50(9), 1936–1951. https://doi.org/10.1175/JAMC-D-10-05017.1
- ☑ Kim, S.-H., Chun, H.-Y., Kim, J.-H., Sharman, R. D. ve Strahan, M. (2019). Retrieval of eddy dissipation rate from derived equivalent vertical gust included in Aircraft Meteorological Data Relay (AMDAR). *Atmospheric Measurement Techniques Discussions* (ön baskı). https://doi.org/10.5194/amt-2019-442
- ☑ Kopeć, J. M., Kwiatkowski, K., de Haan, S. ve Malinowski, S. P. (2016). Retrieving atmospheric turbulence information from regular commercial aircraft using Mode-S and ADS-B. *Atmospheric Measurement Techniques*, 9(5), 2253–2265. https://doi.org/10.5194/amt-9-2253-2016
- ☑ Lee, J. H., Kim, J.-H., Sharman, R. D., Kim, J. ve Son, S.-W. (2023). Climatology of clear-air turbulence in upper troposphere and lower stratosphere in the Northern Hemisphere using ERA5 reanalysis data. *Journal of Geophysical Research: Atmospheres*, 128(1), e2022JD037679. https://doi.org/10.1029/2022JD037679
- ☑ Li, K., Huang, B., Wang, H., Fu, N., Liu, H., Yan, X. ve Pan, Y. (2026). A review of machine learning methods for aviation turbulence identification and forecasting. *IEEE Access*, 14, 131476–131486. https://doi.org/10.1109/ACCESS.2026.3726047
- ☑ Muñoz-Esparza, D., Sharman, R. D. ve Deierling, W. (2020). Aviation turbulence forecasting at upper levels with machine learning techniques based on regression trees. *Journal of Applied Meteorology and Climatology*, 59(11), 1883–1899. https://doi.org/10.1175/JAMC-D-20-0116.1
- ☑ NTSB (2021). *Preventing Turbulence-Related Injuries in Air Carrier Operations Conducted Under 14 CFR Part 121*. Safety Research Report NTSB/SS-21/01.
- ☑ Roberts, D. R. vd. (2017). Cross-validation strategies for data with temporal, spatial, hierarchical, or phylogenetic structure. *Ecography*, 40(8), 913–929. https://doi.org/10.1111/ecog.02881
- ☑ Schäfer, M., Strohmeier, M., Lenders, V., Martinovic, I. ve Wilhelm, M. (2014). Bringing up OpenSky: A large-scale ADS-B sensor network for research. *IPSN-14 Proceedings*, 83–94. https://doi.org/10.1109/IPSN.2014.6846743
- ☑ Schwartz, B. (1996). The quantitative use of PIREPs in developing aviation weather guidance products. *Weather and Forecasting*, 11(3), 372–384. https://doi.org/10.1175/1520-0434(1996)011<0372:TQUOPI>2.0.CO;2
- ☐ Soliva Fabrega, J. (2025). *Analysis of the Trend of CAT (Clear Air Turbulence) over Europe*. Lisans tezi, Aerospace Systems Engineering (danışmanlar J. Mazón Bueso, D. Pino González). Kurum ve erişim adresi tezden ayrıca alınmalı.
- ☑ Sharman, R. D., Cornman, L. B., Meymaris, G., Pearson, J. ve Farrar, T. (2014). Description and derived climatologies of automated in situ eddy-dissipation-rate reports of atmospheric turbulence. *Journal of Applied Meteorology and Climatology*, 53(6), 1416–1432. https://doi.org/10.1175/JAMC-D-13-0329.1
- ☑ Sharman, R. D. ve Pearson, J. M. (2017). Prediction of energy dissipation rates for aviation turbulence. Part I: Forecasting nonconvective turbulence. *Journal of Applied Meteorology and Climatology*, 56(2), 317–337. https://doi.org/10.1175/JAMC-D-16-0205.1
- ☑ Sharman, R., Tebaldi, C., Wiener, G. ve Wolff, J. (2006). An integrated approach to mid- and upper-level turbulence forecasting. *Weather and Forecasting*, 21(3), 268–287. https://doi.org/10.1175/WAF924.1
- ☑ Vovk, V., Gammerman, A. ve Shafer, G. (2022). *Algorithmic Learning in a Random World* (2. baskı). Springer. https://doi.org/10.1007/978-3-031-06649-8
- ☑ Zhang, W., Zhang, X., Yuan, W., Zhang, C., Hu, M. ve Yang, T. (2025). Clear-air turbulence over China: climatology and multiscale mechanisms from first long-term aircraft reports. *Atmosphere*, 16(10), 1218. https://doi.org/10.3390/atmos16101218
- ☑ Zhu, C., Zhang, C., Ng, K. K. H., Chan, P. W. ve Delahaye, D. (2026). Enhancing air traffic safety through clear-air turbulence prediction and trajectory optimisation. *Transportation Research Part C: Emerging Technologies*, 190, 105791. https://doi.org/10.1016/j.trc.2026.105791
- ☐ Holton, J. R. *An Introduction to Dynamic Meteorology* (Richardson sayısı bölümü; baskı ve sayfa kitaptan alınmalı).
