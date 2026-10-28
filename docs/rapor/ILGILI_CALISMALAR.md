# İlgili Çalışmalar (rapor bölümü, E3)

Bu bölüm bitirme raporuna doğrudan aktarılabilir. Künyeler Crossref (DOI) ya da
yayıncı kaydıyla 2, 5 ve 16 Ekim 2026'da doğrulandı (☑). Resmî belgeler (ICAO, NOAA)
DOI taşımaz; adlarıyla verildi. Bir çalışmadan sayı aktarılırken yalnızca özetinde
ya da doğrulanmış metninde yazan değer kullanıldı; tam metnine erişilemeyen
çalışmalarda sayı verilmedi.

## 1. Açık hava türbülansı ve teşhis indeksleri

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
ilişkili olduğunu raporladı. Türkiye bu çalışmalarda ayrı bir bölge olarak incelenmedi;
yalnız komşu bölgelerdeki bulgular aktarılabilir.

**Projeyle bağ.** Fizik katmanı TI1, TI2, VWS, DEF ve Ri'yi ERA5'ten, uçağın basıncını
çevreleyen 25 hPa'lık katmandan hesaplar (`fizik/turbulans_indeksleri.py`,
`fizik/eslestirme.py`). Deformasyon küresel metrik terimleriyle, katman kalınlığı
hipsometrik denklemle bulunur.

## 2. Operasyonel türbülans tahmini: GTG ve WAFS

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

## 3. Türbülans gözlemi ve doğrulama: PIREP ve EDR

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

## 4. ADS-B'den türbülans çıkarımı

Kopeć vd. (2016), Mode-S EHS ve ADS-B mesajlarının düşey ivmeden ya da arka plan
rüzgârından EDR'ye çevrilebileceğini bir araştırma uçağının ivmeölçer kaydıyla
karşılaştırarak gösterdi. ADS-B verisi OpenSky ağından (Schäfer vd., 2014) gelir.
Kuantizasyon (irtifa 25 ft, düşey hız 64 ft/dk) ve güncelleme sıklığı, bu yolla
elde edilebilecek ayrıntıyı sınırlar.

**Projeyle bağ.** Sanal PIREP (K8) ADS-B'yi EDR'ye çevirmez, yalnız atanmış seviyeden
ani sapmaları olay sayar; eşikleri RVSM irtifa tutma toleransından (ICAO Doc 9574)
ve kuantizasyondan türetir, çoklu uçakla doğrular (ADR 0011).

## 5. Türbülans tahmininde makine öğrenmesi

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

**Projeyle bağ.** Modelimiz açık veriyle (ERA5 + IEM PIREP) eğitilir, gün gruplu çapraz
doğrulama ve zamansal holdout kullanır, TI1'i geçmeyen aday aktifleşmez (K4). Hafif
raporlar negatif sınıftadır. Bölme ve etiket farkları §9 tablosunda yan yana verilir.

## 6. Belirsizlik: konformal tahmin

Konformal tahmin (Vovk vd., 2022) dağılım varsaymadan, seçilen hata oranında kapsama
garantisi veren tahmin kümeleri üretir. Angelopoulos ve Bates (2021) uygulamalı bir
giriş, Barber vd. (2021) çapraz-konformal (CV+) yöntemin kapsama sınırını verir.

**Projeyle bağ.** Her olasılık `dusuk_risk` / `yuksek_risk` / `belirsiz` durumuna
çevrilir (K5, ADR 0010).

## 7. Reanaliz verisi ve rota optimizasyonu

ERA5 (Hersbach vd., 2020), 0,25° ve saatlik çözünürlükte 37 basınç seviyeli küresel
reanalizdir. Rota tarafında A* (Hart vd., 1968) en kısa yol aramasının temelidir.
Cheung (2018), A* tabanlı düğüm temelli bir yörünge tahmin sistemi önerip CAT'in
kalkıştan önce hesaba katılıp nasıl kaçınılabileceğine örnek verdi; bu, bizim rota
katmanımıza yöntem olarak en yakın çalışmadır.

**Projeyle bağ.** A* araması yanal sapma ile seviye değişimini gerçek yakıt/süre
bedeliyle karşılaştırır; SIGMET ve kısıtlı sahalar sert, TI1 yumuşak kısıttır (K7).

## 8. Açık kaynak uygulamalar ve karşı örnekler

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

## 9. Karşılaştırma tablosu

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

## Kaynakça

- ☑ Angelopoulos, A. N. ve Bates, S. (2021). A gentle introduction to conformal prediction and distribution-free uncertainty quantification. arXiv:2107.07511.
- ☑ Barber, R. F., Candès, E. J., Ramdas, A. ve Tibshirani, R. J. (2021). Predictive inference with the jackknife+. *The Annals of Statistics*, 49(1). https://doi.org/10.1214/20-AOS1965
- ☑ Cheung, J. C. H. (2018). Flight planning: node-based trajectory prediction and turbulence avoidance. *Meteorological Applications*, 25(1), 78–85. https://doi.org/10.1002/met.1671
- ☑ Ellrod, G. P. ve Knapp, D. I. (1992). An objective clear-air turbulence forecasting technique: verification and operational use. *Weather and Forecasting*, 7(1), 150–165. https://doi.org/10.1175/1520-0434(1992)007<0150:AOCATF>2.0.CO;2
- ☑ Ellrod, G. P. ve Knox, J. A. (2010). Improvements to an operational clear-air turbulence diagnostic index by addition of a divergence trend term. *Weather and Forecasting*, 25(2), 789–798. https://doi.org/10.1175/2009WAF2222290.1
- ☑ Foudad, M., Sanchez-Gomez, E., Jaravel, T., Rochoux, M. C. ve Terray, L. (2024). Past and future trends in clear-air turbulence over the Northern Hemisphere. *Journal of Geophysical Research: Atmospheres*, 129(13), e2023JD040261. https://doi.org/10.1029/2023JD040261
- ☑ Gill, P. G. (2014). Objective verification of World Area Forecast Centre clear air turbulence forecasts. *Meteorological Applications*, 21(1), 3–11. https://doi.org/10.1002/met.1288
- ☑ Gökdeniz, K. ve Ülkü, İ. (2026). Predictive modeling of high-altitude clear air turbulence in the United States: A machine learning approach. arXiv:2607.11899 [physics.ao-ph].
- ☑ Gu, A. ve Wang, Y. (2024). Optimizing clear air turbulence forecasts using the K-nearest neighbor algorithm. *Journal of Meteorological Research*, 38(6), 1064–1077. https://doi.org/10.1007/s13351-024-4060-7
- ☑ Hart, P. E., Nilsson, N. J. ve Raphael, B. (1968). A formal basis for the heuristic determination of minimum cost paths. *IEEE Transactions on Systems Science and Cybernetics*, 4(2), 100–107. https://doi.org/10.1109/TSSC.1968.300136
- ☑ Hersbach, H. vd. (2020). The ERA5 global reanalysis. *Quarterly Journal of the Royal Meteorological Society*, 146(730), 1999–2049. https://doi.org/10.1002/qj.3803
- ☐ ICAO. *Annex 3 to the Convention on International Civil Aviation: Meteorological Service for International Air Navigation* (EDR raporlaması ve WAFS).
- ☐ ICAO. *Doc 9574: Manual on a 300 m (1 000 ft) Vertical Separation Minimum* (RVSM irtifa tutma toleransı).
- ☑ Kim, J.-H., Chun, H.-Y., Sharman, R. D. ve Keller, T. L. (2011). Evaluations of upper-level turbulence diagnostics performance using the Graphical Turbulence Guidance (GTG) system and pilot reports (PIREPs) over East Asia. *Journal of Applied Meteorology and Climatology*, 50(9), 1936–1951. https://doi.org/10.1175/JAMC-D-10-05017.1
- ☑ Kim, S.-H., Chun, H.-Y., Kim, J.-H., Sharman, R. D. ve Strahan, M. (2019). Retrieval of eddy dissipation rate from derived equivalent vertical gust included in Aircraft Meteorological Data Relay (AMDAR). *Atmospheric Measurement Techniques Discussions* (ön baskı). https://doi.org/10.5194/amt-2019-442
- ☑ Kopeć, J. M., Kwiatkowski, K., de Haan, S. ve Malinowski, S. P. (2016). Retrieving atmospheric turbulence information from regular commercial aircraft using Mode-S and ADS-B. *Atmospheric Measurement Techniques*, 9(5), 2253–2265. https://doi.org/10.5194/amt-9-2253-2016
- ☑ Lee, J. H., Kim, J.-H., Sharman, R. D., Kim, J. ve Son, S.-W. (2023). Climatology of clear-air turbulence in upper troposphere and lower stratosphere in the Northern Hemisphere using ERA5 reanalysis data. *Journal of Geophysical Research: Atmospheres*, 128(1), e2022JD037679. https://doi.org/10.1029/2022JD037679
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
- ☐ Holton, J. R. *An Introduction to Dynamic Meteorology* (Richardson sayısı bölümü; baskı ve sayfa kitaptan alınmalı).
