# İlgili Çalışmalar: iskelet (E3)

Bu dosya bir iskelettir, bitmiş metin değildir. Her başlıkta raporda ne
anlatılacağı, projeyle bağı ve okunacak kaynaklar var. Kaynak satırlarındaki
künyeler belleğe dayanır: **her birini rapora koymadan önce yayıncının sayfasında
ya da DOI ile doğrulayın** (yazar, yıl, cilt, sayfa). "Doğrulandı" sütunu bu
yüzden boş bırakıldı. Bulamadığınız bir kaynağı rapora koymayın.

Önerilen uzunluk: 2–3 sayfa; her alt başlık 1–2 paragraf.

## 1. Açık hava türbülansı ve teşhis indeksleri

- **Anlatılacak:** CAT'in kaynağı (jet akımı çevresinde rüzgar kayması,
  deformasyon, Kelvin–Helmholtz kararsızlığı); Richardson sayısı; Ellrod TI1'in
  tanımı (dikey rüzgar kayması × toplam deformasyon) ve TI2 (yakınsama terimi).
- **Projeyle bağ:** Sistemin fizik katmanı TI1 ve Richardson'dur
  (`fizik/turbulans_indeksleri.py`). TI1'in sınırını kendi verimizle ölçtük (K6).

| Kaynak (doğrulanacak) | Neden | Doğrulandı |
|---|---|---|
| Ellrod, G. P. ve Knapp, D. I. (1992). An objective clear-air turbulence forecasting technique: verification and operational use. *Weather and Forecasting*, 7(1). | TI1'in özgün kaynağı | ☐ |
| Ellrod, G. P. ve Knox, J. A. (2010). Improvements to an operational clear-air turbulence diagnostic index by addition of a divergence trend term. *Weather and Forecasting*, 25. | TI2 / yakınsama terimi | ☐ |
| Bir atmosfer dinamiği ders kitabından Richardson sayısı bölümü (ör. Holton, *An Introduction to Dynamic Meteorology*) | Ri < 0,25 ölçütünün dayanağı | ☐ |

## 2. Operasyonel türbülans tahmini: GTG ve WAFS

- **Anlatılacak:** GTG'nin çok sayıda teşhisi ağırlıklandırıp EDR'ye eşlemesi;
  WAFS küresel türbülans ürünleri; bu ürünlerin tahmin modeline (NWP) dayandığı.
- **Projeyle bağ:** Biz yeni bir tahmin ürünü iddia etmiyoruz. Farkımız, gerçek
  uçuş izi ve rota kararıyla bütünleşik, sınırlarını ölçen bir karar destek
  hattı. WAFS kıyası gelecek çalışmadır (M3).

| Kaynak (doğrulanacak) | Neden | Doğrulandı |
|---|---|---|
| Sharman, R., Tebaldi, C., Wiener, G. ve Wolff, J. (2006). An integrated approach to mid- and upper-level turbulence forecasting. *Weather and Forecasting*, 21. | GTG'nin temel makalesi | ☐ |
| Sharman, R. D. ve Pearson, J. M. (2017). Prediction of energy dissipation rates for aviation turbulence. Part I. *Journal of Applied Meteorology and Climatology*, 56. | Teşhislerin EDR'ye eşlenmesi; bizim EDR proxy'mizin sertifikalı olmadığını anlatırken | ☐ |
| ICAO Annex 3 / WAFS türbülans ürünlerini tanımlayan resmi belge | WAFS'ın ne ürettiği | ☐ |

## 3. Türbülans gözlemi: PIREP, EDR ve otomatik raporlama

- **Anlatılacak:** PIREP'in öznelliği ve konum/zaman hatası; uçakta otomatik EDR
  hesaplanıp raporlanması (ICAO EDR standardı); bu verinin erişim kısıtları.
- **Projeyle bağ:** Etiketimiz PIREP (K2); nesnel EDR için MADIS başvurusu (M1).

| Kaynak (doğrulanacak) | Neden | Doğrulandı |
|---|---|---|
| ICAO Annex 3: otomatik EDR raporlaması bölümü | EDR'nin resmi tanımı | ☐ |
| PIREP konum/zaman hatası üzerine bir doğrulama çalışması (ör. Schwartz 1996, *Weather and Forecasting*) | PIREP etiketinin gürültüsü | ☐ |
| NOAA MADIS belgeleri (uçak verisi) | M1'in veri kaynağı | ☐ |

## 4. ADS-B'den türbülans çıkarımı

- **Anlatılacak:** ADS-B irtifa/düşey hız verisinden türbülans olayı ya da EDR
  türetme girişimleri; kuantizasyon ve güncelleme hızı sınırları.
- **Projeyle bağ:** Sanal PIREP (K8) bu fikrin, EDR'ye çevirmeden ve çoklu uçak
  doğrulamasıyla, ürün içinde uygulanmış halidir.

| Kaynak (doğrulanacak) | Neden | Doğrulandı |
|---|---|---|
| Google Scholar'da arayın: "ADS-B" "turbulence" "eddy dissipation rate" | Bu alanda birkaç güncel çalışma var; künyeyi buradan almayın, aramayla bulun | ☐ |
| Schäfer, M., Strohmeier, M., Lenders, V., Martinovic, I. ve Wilhelm, M. (2014). Bringing up OpenSky. IPSN 2014. | Veri kaynağı (zorunlu atıf) | ☐ |
| ICAO Doc 9574 (RVSM el kitabı): irtifa tutma toleransı | Sanal PIREP eşiğinin dayanağı (±65 ft) | ☐ |

## 5. Türbülans tahmininde makine öğrenmesi

- **Anlatılacak:** Teşhis indekslerini ya da NWP alanlarını girdi alan sınıflandırıcı
  ve regresyon çalışmaları; tipik olarak rastgele bölme kullanılması ve bunun yol
  açtığı sızıntı; olasılık kalibrasyonu.
- **Projeyle bağ:** Gün gruplu doğrulama, zamansal holdout, kapılı aktivasyon (K4).

| Kaynak (doğrulanacak) | Neden | Doğrulandı |
|---|---|---|
| Google Scholar'da arayın: "machine learning" "clear-air turbulence" "PIREP" | 2–3 güncel çalışma seçin | ☐ |
| Roberts, D. R. ve ark. (2017). Cross-validation strategies for data with temporal, spatial, hierarchical, or phylogenetic structure. *Ecography*. | Gruplu/blok doğrulamanın gerekçesi | ☐ |

## 6. Belirsizlik: konformal tahmin

| Kaynak (doğrulanacak) | Neden | Doğrulandı |
|---|---|---|
| Vovk, V., Gammerman, A. ve Shafer, G. *Algorithmic Learning in a Random World* (Springer). | Konformal tahminin temeli | ☐ |
| Angelopoulos, A. N. ve Bates, S. "A Gentle Introduction to Conformal Prediction and Distribution-Free Uncertainty Quantification" (arXiv). | Uygulamalı özet; split/cross-conformal | ☐ |
| Barber, R. F. ve ark. "Predictive inference with the jackknife+" (*Annals of Statistics*). | CV+ için 1−2α alt sınırı (ADR 0010'da geçiyor) | ☐ |

## 7. Reanaliz verisi ve rota optimizasyonu

| Kaynak (doğrulanacak) | Neden | Doğrulandı |
|---|---|---|
| Hersbach, H. ve ark. (2020). The ERA5 global reanalysis. *QJRMS*, 146(730), 1999–2049. | ERA5 (repo atıf metninde de var) | ☐ |
| Hart, Nilsson ve Raphael (1968). A formal basis for the heuristic determination of minimum cost paths. *IEEE Trans. Systems Science and Cybernetics*. | A* algoritması | ☐ |
| Rüzgar ya da hava olayından kaçınan uçuş rotası optimizasyonu üzerine 1–2 çalışma (Scholar: "flight trajectory optimization" "turbulence avoidance") | Rota katmanının bağlamı | ☐ |

## Bölümün kapanış paragrafı (taslak cümle)

"Literatürdeki operasyonel ürünler (GTG, WAFS) tahmin modeline dayalı türbülans
alanları üretir; ML çalışmaları ise çoğunlukla çevrimdışı sınıflandırma başarımını
raporlar. Bu çalışma, açık veriyle gerçek uçuş izlerini, ölçülmüş sınırlarıyla bir
risk göstergesini ve bu göstergeye dayalı rota kararını tek bir işletilebilir
sistemde birleştirmeyi hedefler [K1–K9]."
