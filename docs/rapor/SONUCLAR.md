# Sonuçlar (rapor bölümü, Madde 8)

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

## 0. Nihai sonuç paketi (Madde 8, 18 Ekim veri dondurması)

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

### 0.1 Altın test günleri

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

### 0.2 TI1 eşik taraması

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

### 0.3 Yalnız CAT alt kümesi (MET-07)

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

### 0.4 Nesnel etiket: MADIS ölçülen EDR

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

### 0.5 Rota backtest'i

Veritabanındaki iki uçuşta riskli nokta oranı (gerçek / büyük daire / A*), 7e-7 eşiğiyle:
THY322 1 Ocak 2019 0,00 / 0,20 / 0,00; THY322 15 Ocak 2019 0,24 / 0,39 / 0,02
([şekil](../sonuclar/2026-10-18/backtest_ucus_basina.png)). Ölçüm döngüseldir. PUE502
(bağımsız kanıtlı tek uçuş) bu veritabanında yok; açıklaması `docs/SISTEM_KARTI.md` §6'da.

Bağımsız toplu ölçüm (29 Ekim, protokol §11): NE-ABD'de 2.304 simüle rota; TI1 eşiğinin seçildiği
günler hariç, A*'ın sapma önerdiği 908 rotada PIREP tüpündeki orta-üstü payının göreli maruziyet
oranı (A* / büyük daire) 0,71 [0,58; 0,90]; 48 günün tamamında 0,83 [0,66; 1,03]
([paket](../sonuclar/2026-10-29_bagimsiz_backtest/README.md)).

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
eski hesaba göre konmuştu ve yeni fizikte daha sık aşılıyor. Risk eşiği 8 Ekim'de
eğitim günlerinden 1-SE kuralıyla 7e-7'ye çekildi (bkz. §0.2); hafif eşiği (4e-7)
hâlâ kaba bir başlangıç değeridir.

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
yalnız tartışma bölümünde yer alır. Dondurmada protokol değişmeden uygulandı; 1-SE kuralı
163 günlük veride ağaç modelini (sıralı sorguyla RF, ilk üretimde GB) seçti ve model TI1'i
geçti (§0.1).

### 2.4 RF ayarı ve bağlam özellikleri (F9 deneyi, 15 Ekim)

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

### 2.5 Dondurma sonrası yeni günler (§10, 27 Ekim; tek seferlik)

Protokol `deney_protokolu.md` §10, paket [`docs/sonuclar/2026-10-27_yeni_gun/`](../sonuclar/2026-10-27_yeni_gun/README.md).
Eğitim 163 dondurma günü, test modelin görmediği 79 gün (7.769 örnek). ROC-AUC: TI1 0,658,
temel set (RF) 0,685, geniş set (LR) 0,693.

- **H1 (geniş − temel):** +0,008 [+0,002; +0,014], desteklendi; dondurma gününe komşu 24 gün
  çıkarılınca +0,005 [−0,002; +0,012], anlamlı değil. Destek zayıf ve kırılgan.
- **TI1'e karşı:** temel +0,027 [+0,018; +0,035], geniş +0,035 [+0,026; +0,043]; ikisi de kapıyı
  geçti. 18 Ekim altın gün farkı (+0,033) modelin görmediği günlerde de korunuyor.
- Hafif raporlar negatiften çıkarılınca (Fikir 8) üç skor da belirgin yükseliyor (TI1 0,730,
  geniş 0,774), sıralama değişmiyor. Geniş setin üretime alınması ayrı karar (ONAY).

### 2.6 Model − birleşik EDR (§10.6, 28 Ekim; sonradan eklenen ikincil)

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

### 2.7 Bölme ve etiket tanımının etkisi (§10.7, 28 Ekim; keşifsel)

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

### 2.8 Göreli ekonomik değer (REV; 28 Ekim, ek analiz)

Altın test günlerinin POD/POFD'si (yeniden puanlama yok) Richardson (2000) maliyet/kayıp modeline
kondu (kurul #16). PIREP örnek taban oranında (s = 0,476) en yüksek REV: TI1 eşik zarfı 0,26, TI1 risk
eşiği (7e-7) 0,25, model (olasılık ≥ 0,5) 0,30; değer yalnız α = C/L ≈ 0,3–0,8 bandında pozitif.
Kaçınma bedeli medyanı (%2,2 sefer yakıtı, §uyarı oranı) C alınırsa TI1 risk eşiği, bir orta-üstü
karşılaşmanın kaybı sefer yakıtının %3,4–5,8'i arasındaysa "hep sap / hiç sapma"dan ucuzdur. Aynı
POD/POFD'nin MADIS EDR ≥ 0,1 oranına (s = 0,029; farklı olay, aktarılabilirlik varsayımı) uygulandığı
gösterimde bu aralık %39–114'e çıkar. POD/POFD nokta başınadır, rota başına değildir; PIREP taban oranı
operasyonel sıklık değildir; kaybın gerçek değeri bilinmiyor. Sonuç sıralama ve mertebe içindir, eşik ya
da seçim ağırlığı önerisi değildir. Paket `docs/sonuclar/2026-10-28_ekonomik_deger/` (şekil `rev_egrileri.png`).

### 2.9 GFS tahmin ufku tutarlılığı (#11; 28 Ekim, ek analiz)

UCAR THREDDS'in tuttuğu son ~7,5 günün koşularından, 23–28 Ekim 2026'daki 11 geçerlilik zamanı (00/12Z)
için f000, f024 ve f048 Türkiye kutusunda (200/250/300 hPa, 14 MB) indirildi; her zamanda 5.000 rastgele
noktada (FL310–380) TI1 karşılaştırıldı (GFS eşiği 8,3e-7). f024: Spearman medyanı 0,67 [0,61–0,77], f000'da
riskli olanların %57'si tahminde de riskli; f048: 0,50 [0,39–0,59], %43. Riskli oran ufukla değişmiyor
(%8,3 → %7,4) ama yeri değişiyor. 3 saatlik zaman örneklemesinin etkisinden (Spearman 0,923) çok daha büyük.
Referans GFS'in kendi analizidir; gözlemle (ERA5) kıyas ERA5'in yayın gecikmesi yüzünden 3 Kasım'a kaldı.
Paket `docs/sonuclar/2026-10-28_tahmin_ufku/`.

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
