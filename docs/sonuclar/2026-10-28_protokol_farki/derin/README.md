# Bölme ve etiket tanımının ROC-AUC'ye etkisi (§10.7, keşifsel)

Protokol: docs/deney_protokolu.md §10.7 (keşifsel); derin RF sonradan eklendi (§10.7 sonucu görüldükten sonra).

Üretim: 2026-10-28T16:25:38+00:00 · commit `bc3665cf5c3c979eff5e67fc8a2be85ad9002480` · 147 eğitim günü (altın test ve §10 günleri hariç) · sabit RF (RandomForest {'n_estimators': 200, 'max_depth': None, 'min_samples_leaf': 1}, class_weight=balanced), temel 8 özellik · her koşulda 20 bölme.

| Koşul | Örnek (pozitif) | RF ROC-AUC | TI1 ROC-AUC | RF − TI1 | Test günlerinin eğitimde de olan oranı |
|---|---|---|---|---|---|
| Gün gruplu 70/30, hafif = negatif (bu çalışma) | 14450 (7785) | 0.683 [0.672–0.695] | 0.674 [0.662–0.694] | +0.009 | %0 |
| Rastgele örnek 70/30, hafif = negatif | 14450 (7785) | 0.684 [0.673–0.693] | 0.672 [0.664–0.682] | +0.012 | %100 |
| Gün gruplu 70/30, hafif çıkarılmış | 9014 (7146) | 0.771 [0.753–0.785] | 0.738 [0.715–0.757] | +0.033 | %0 |
| Rastgele örnek 70/30, hafif çıkarılmış (literatüre en yakın) | 9014 (7146) | 0.773 [0.758–0.793] | 0.740 [0.726–0.763] | +0.033 | %100 |

Etkiler (RF ROC-AUC ortalamaları farkı): bolme (rastgele - gun gruplu), mevcut etiket: +0.001; etiket (hafif cikarilmis - mevcut), gun gruplu: +0.088; ikisi birlikte: +0.089; TI1: etiket etkisi, gun gruplu: +0.063. Çıkarılan hafif negatif: 4174; metni bulunamadığı için hafif koşullarından düşen: 1262.

**Okuma.** Aralıklar 20 bölmenin 2,5–97,5 yüzdelikleridir, güven aralığı değildir. Rastgele bölmede aynı günün (aynı hava sisteminin) örnekleri hem eğitimde hem testtedir; gün gruplu bölmede test günleri eğitimde yoktur. Literatür değerleri (0,86–0,90; ILGILI_CALISMALAR §9) farklı bölge, özellik ve modelle elde edildi; bu tablo yalnız aynı veride bölme ve etiket tanımının yönünü ve büyüklüğünü gösterir.

Çıktılar sertifikalı EDR değildir; sistem operasyonel karar aracı değil, karar destek aracıdır.
