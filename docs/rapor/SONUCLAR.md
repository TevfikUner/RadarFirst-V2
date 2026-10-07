# Sonuçlar (rapor bölümü, Madde 8)

Güncel sayılar §0'dadır. §1–§3 ölçüm tarihi 5 Ekim 2026. Ham sayılar `docs/rapor/veri/` altında JSON olarak durur;
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

## 0. Güncel sonuç paketi (Madde 8)

Güncel sayılar [`docs/sonuclar/2026-10-07/`](../sonuclar/2026-10-07/SAYILAR.md) ön
paketindendir: kesme 7 Ekim 2026, commit `34c6f93`, tek liste `SAYILAR.md`. Paket 18 Ekim
veri dondurmasında `docs/sonuclar/2026-10-18/` ile değiştirilir. Aşağıdaki §1–§3
ölçümleri 5 Ekim tarihlidir ve o günkü zamansal holdout'u kullanır; tarihçe olarak durur.

```
turbulans-ml-degerlendirme --kesme 2026-10-07 --cikti docs/sonuclar/2026-10-07
```

### 0.1 Altın test günleri

Değerlendirme günleri, 7 Ekim'de dondurulan 16 altın test günüdür (1.554 PIREP). Model bu
günleri görmedi: 64 eğitim gününde (6.261 PIREP) gün gruplu CV ve 1-SE kuralıyla seçildi,
seçilen Lojistik Regresyon oldu. Altın günlerde pozitif oranı 0,481'dir; PR-AUC'nin
rastgele tabanı bu orandır.

| Gösterge | ROC-AUC [%95 GA] | PR-AUC [%95 GA] | TI1'e göre ROC-AUC farkı |
|---|---|---|---|
| Birleşik EDR | 0,687 [0,655–0,717] | 0,677 [0,637–0,710] | +0,014 [+0,007; +0,020], p < 0,001 |
| Model (LR) | 0,681 [0,646–0,716] | 0,672 [0,632–0,707] | +0,008 [−0,006; +0,022], p 0,268 |
| TI1 | 0,673 [0,639–0,704] | 0,666 [0,624–0,702] | — |
| 1/Ri | 0,653 [0,626–0,678] | 0,639 [0,596–0,676] | −0,021 [−0,053; +0,011], p 0,190 |

Fizik göstergeleri eğitilmediği için tüm 80 günde de ölçülebilir: TI1 0,680
[0,662–0,697], birleşik EDR 0,692 [0,675–0,709], 1/Ri 0,652 [0,637–0,667].

Model altın günlerde TI1'i geçemedi (GA 0'ı içeriyor). Bu, 18 Ekim kapısının ön sonucudur.
Birleşik EDR'nin TI1'e üstünlüğü küçük ama tutarlı. Model olasılığında Brier 0,226, Brier
becerisi 0,095; ortalama olasılık 0,523, gözlenen oran 0,481.

Şekiller: [ROC (TI1 ve Ri)](../sonuclar/2026-10-07/roc_ti1_ri.png),
[güvenilirlik diyagramı](../sonuclar/2026-10-07/guvenilirlik_modeli.png).

### 0.2 TI1 eşik taraması

Eşik eğitim günlerinde Peirce'i (POD − POFD) en büyütecek biçimde seçildi ve altın günlere
olduğu gibi uygulandı. Taramanın tamamı JSON'da `esik_taramasi.tarama` altında.

| Eşik | Altın günlerde POD | POFD | CSI |
|---|---|---|---|
| Peirce eşiği 5,3e-7 (eğitim günlerinden) | 0,605 | 0,349 | 0,439 |
| `TI1_ESIK_HAFIF` 4e-7 | 0,683 | 0,440 | 0,463 |
| 1-SE eşiği 7,06e-7 (eğitim günlerinden) | 0,498 | 0,247 | 0,393 |
| `TI1_ESIK_ORTA_SIDDETLI` 7e-7 (config, risk eşiği; 8 Ekim'e kadar 8e-7) | 0,502 | 0,252 | 0,395 |

Peirce eşiğinde altın günlerdeki Peirce 0,256 [0,188–0,313]. Ri için aynı yöntem Ri < 2,37
verdi. Klasik 0,25 sınırı ERA5 çözünürlüğünde çok seyrek aşılır (bkz. §1.1).

Seviyeye göre (her seviyede eşik o seviyenin eğitim örnekleriyle seçildi):

| Seviye | Seviye eşiği | POD / POFD / CSI (seviye eşiği) | POD / POFD / CSI (genel eşik) | Test örneği |
|---|---|---|---|---|
| 175 hPa | 5,7e-7 | 0,596 / 0,286 / 0,419 | 0,635 / 0,312 / 0,434 | 129 |
| 200 hPa | 6,7e-7 | 0,527 / 0,246 / 0,418 | 0,611 / 0,297 / 0,465 | 269 |
| 225 hPa | 5,5e-7 | 0,619 / 0,403 / 0,403 | 0,626 / 0,413 / 0,404 | 361 |
| 250 hPa | 4,3e-7 | 0,615 / 0,411 / 0,437 | 0,562 / 0,350 / 0,417 | 528 |
| 300 hPa | 5,1e-7 | 0,676 / 0,286 / 0,550 | 0,667 / 0,286 / 0,543 | 189 |
| 350 hPa | 1,1e-6 | 0,256 / 0,128 / 0,227 | 0,590 / 0,410 / 0,418 | 78 |

175–300 hPa'da seviye eşikleri genel eşiğe yakın (4,3–6,7e-7) ve CSI'yi belirgin
iyileştirmiyor. 350 hPa'da eğitim örneği az ve seviye eşiği testte kötüleşiyor. Tek genel
eşik yeterli görünüyor.

**Risk eşiği kararı (8 Ekim).** Peirce'i en büyüten eşik ile daha yüksek eşikler arasındaki
beceri farkı küçüktür; yüksek eşik daha az yanlış alarm verir. Gerçek olay oranı düşük
olduğu için (MADIS'te %3) yanlış alarm pahalıdır. Bu yüzden model seçimindeki 1-SE
kuralının eşik karşılığı uygulandı: eğitim günlerinde Peirce'i en yüksek değerin (0,284)
gün bazlı bootstrap standart hatası (0,018) içinde kalan en yüksek eşik, 7,06e-7.
`TI1_ESIK_ORTA_SIDDETLI` 8e-7'den 7e-7'ye indi. Eski 8e-7 bu bandın dışındaydı (eğitim
Peirce'i 0,250). Kural yalnız eğitim günlerini kullanır; 18 Ekim paketinde aynı kuralla
yeniden hesaplanır (`esik_taramasi.bir_se`).

### 0.3 Yalnız CAT alt kümesi (MET-07)

Sistemin kapsamı açık hava türbülansıdır. PIREP metninde CB, TS (+TSRA, VCTS, TSTM gibi
türevler), TCU, MTN WAVE ya da LLWS geçen raporlar dışlandı. Ham metin yalnız yerel IEM
arşivinde (2018–Mart 2020) var: 6.764 örneğin metni bulundu, 119'u (%1,8) CAT dışı
işaretlendi ve bunların pozitif oranı 0,420. Altın günlerde metinli 1.369 örnekten 1.353'ü
kaldı.

| Gösterge | Yalnız CAT, altın günler | Yalnız CAT, tüm günler |
|---|---|---|
| Birleşik EDR | 0,683 [0,649–0,720] | 0,692 [0,674–0,709] |
| Model | 0,678 [0,638–0,724] | — |
| TI1 | 0,669 [0,632–0,707] | 0,679 [0,660–0,697] |
| 1/Ri | 0,652 [0,621–0,685] | 0,653 [0,639–0,669] |

CAT dışı raporlar çok az olduğu için dışlamak sonucu değiştirmiyor. Nisan 2020 sonrası
günlerin metni yok; bu günler iki alt kümede de yer almıyor.

### 0.4 Nesnel etiket: MADIS ölçülen EDR

20.144 ölçüm, 607'si hafif ve üstü (taban oran 0,030), 6 gün. Sınıflar
`madis_edr.edr_sinifi` ile yeniden hesaplandı. Orta ve üstü ölçüm yok (0), yani
değerlendirme yalnız hafif sınıfı ayırt etmeyi ölçer. Örnekler PIREP pencerelerinden
geldiği için seçim yanlılığı vardır; QC "Z" ön veridir.

| Gösterge | ROC-AUC [%95 GA] | PR-AUC [%95 GA] | TI1'e göre fark |
|---|---|---|---|
| Birleşik EDR | 0,738 [0,667–0,825] | 0,102 [0,072–0,154] | +0,032 [+0,014; +0,049], p < 0,001 |
| Model | 0,734 [0,664–0,820] | 0,092 [0,071–0,128] | +0,028 [+0,002; +0,045], p 0,036 |
| TI1 | 0,706 [0,631–0,801] | 0,091 [0,062–0,144] | — |
| 1/Ri | 0,696 [0,648–0,741] | 0,076 [0,047–0,106] | −0,010 [−0,073; +0,069], p 0,702 |

PR-AUC taban orandan yaklaşık üç kat yüksek, ama mutlak değeri düşük. %3'lük bir olayda
ROC-AUC 0,7 sıralamanın rastgeleden iyi olduğunu söyler; uyarıların çoğunun yanlış alarm
olacağını gizler. Model olasılığı ortalama 0,510, Brier becerisi −8,36: olasılık PIREP
taban oranına göre kalibre olduğu için ölçülen sıklık olarak okunamaz (§4).

### 0.5 Rota backtest'i

Veritabanındaki iki uçuşta riskli nokta oranı (gerçek / büyük daire / A*), 7e-7 eşiğiyle:
THY322 1 Ocak 2019 0,00 / 0,20 / 0,00; THY322 15 Ocak 2019 0,24 / 0,39 / 0,02
([şekil](../sonuclar/2026-10-07/backtest_ucus_basina.png)). Ölçüm döngüseldir. PUE502
(bağımsız kanıtlı tek uçuş) bu veritabanında yok; açıklaması `docs/SISTEM_KARTI.md` §6'da.

## 1. Fizik çekirdeği (Madde 2) — tarihçe, 5 Ekim

### 1.1 Düzeltmenin etkisi

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
eski hesaba göre konmuştu ve yeni fizikte daha sık aşılıyor. Eşikleri yeniden
kalibre etmek veri dondurma (18 Ekim) öncesinde yapılacak açık bir iştir.

### 1.2 Birleşik gösterge (log-normal EDR eşlemesi)

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

## 2. Makine öğrenmesi modeli (PIREP) — §2.1–2.2 tarihçe, 5 Ekim

### 2.1 Holdout sonuçları

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

### 2.2 Eğitim geçmişi ve olumsuz ara bulgu

Holdout her çalıştırmada son %20 güne kayar; satırlar birbiriyle doğrudan
karşılaştırılamaz, her satır kendi holdout'unda TI1 ile karşılaştırılır.

| Tarih | Fizik | Seçilen model | Model ROC-AUC | TI1 ROC-AUC | Karar |
|---|---|---|---|---|---|
| 3 Eki 2026 | eski | Gradient Boosting | 0,646 [0,62–0,67] | 0,667 [0,63–0,70] | Kapı geçilmedi (saklandı) |
| 4 Eki 2026 | eski | Gradient Boosting | 0,631 | 0,642 | Kapı geçilmedi (saklandı) |
| 5 Eki 2026 (gece işi) | eski | Random Forest | 0,686 | 0,666 | Aktifleştirildi |
| 5 Eki 2026 (yeni fizik) | yeni | Random Forest | 0,730 [0,684–0,774] | 0,707 [0,657–0,755] | TI1 kapısı geçildi; aktif modeli F1'de geçemedi (0,695'e karşı 0,704), saklandı |

**Olumsuz ara bulgu (3 Ekim):** Doğru irtifalı veriyle yapılan ilk gerçek eğitimde model
tek başına TI1'i geçemedi (0,646'ya karşı 0,667). Kapılı aktivasyon modeli devreye
almadı. Bu sonuç olduğu gibi raporlanır: o veri hacminde ML'in fizik göstergesine
eklediği bir değer yoktu. Veri büyüdükçe (64 gün) ve fizik düzeltildikçe model TI1'i
anlamlı ama küçük bir farkla geçti (+0,023, GA alt sınırı +0,002).

Şu an aktif olan model eski fizikle hesaplanmış özelliklerle eğitildi. Yeni fizik
özellikleri üzerinde holdout ROC-AUC'si aynıdır (0,730). Bu tutarsızlık, yeni fizikle
eğitilen bir aday aktif modeli geçtiğinde kendiliğinden kapanır; gece işi her gece
aday üretir.

### 2.3 Duyarlılık analizleri (Madde 7, isteğe bağlı)

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
yalnız tartışma bölümünde yer alır.

## 3. Nesnel değerlendirme: MADIS ölçülen EDR (M1) — tarihçe, 5 Ekim (güncel: §0.4)

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

## 4. PIREP raporlama yanlılığı (Madde 7)

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

## 5. Sanal PIREP ve denetimsiz taban

Kural tabanlı sanal PIREP: POD 1/8, POFD 0/8 (16 PIREP). LOF tabanı, ADS-B
kuantizasyonu nedeniyle seyir noktalarının %68'inin aynı vektör olmasıyla
bozuluyordu. Kuantizasyon titreşimiyle düzeltildikten sonra da denetimsiz yöntemler
ayırt edici çıkmadı. Ayrıntı: ADR 0011.

## 6. Veri dondurma

Veri ve protokol **18 Ekim 2026**'da dondurulur. Bu tarihten sonra eğitim verisi,
etiket tanımı, holdout kuralı ve kapı ölçütü değişmez. Rapordaki nihai sayılar bu
tarihteki veritabanı yedeğinden yukarıdaki komutlarla yeniden üretilir. Dondurmadan
önce açık işler:

- ~~Penceresiz 1.597 örneğin yeni fizikle yeniden indirilmesi~~ (7 Eki: penceresiz eşleşmiş örnek kalmadı)
- ~~TI1 eşiklerinin yeni fiziğe göre yeniden değerlendirilmesi~~ (8 Eki: §0.2, 1-SE kuralıyla 7e-7)
- ~~MADIS'te en az 5 güne ulaşılması (GA için)~~ (7 Eki: 6 gün, §0.4)
