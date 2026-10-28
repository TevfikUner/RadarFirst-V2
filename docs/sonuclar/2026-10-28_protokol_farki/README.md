# Bölme ve etiket tanımının ROC-AUC'ye etkisi (§10.7, keşifsel)

Üretim: 2026-10-28T16:24:01+00:00 · commit `0c30c14e42b65a7a696abb5f3acd0af27bbad357` · 147 eğitim günü (altın test ve §10 günleri hariç) · sabit RF (RandomForest {'n_estimators': 200, 'max_depth': 5}, class_weight=balanced), temel 8 özellik · her koşulda 20 bölme.

| Koşul | Örnek (pozitif) | RF ROC-AUC | TI1 ROC-AUC | RF − TI1 | Test günlerinin eğitimde de olan oranı |
|---|---|---|---|---|---|
| Gün gruplu 70/30, hafif = negatif (bu çalışma) | 14450 (7785) | 0.702 [0.691–0.714] | 0.674 [0.662–0.694] | +0.028 | %0 |
| Rastgele örnek 70/30, hafif = negatif | 14450 (7785) | 0.701 [0.691–0.710] | 0.672 [0.664–0.682] | +0.029 | %100 |
| Gün gruplu 70/30, hafif çıkarılmış | 9014 (7146) | 0.785 [0.763–0.802] | 0.738 [0.715–0.757] | +0.047 | %0 |
| Rastgele örnek 70/30, hafif çıkarılmış (literatüre en yakın) | 9014 (7146) | 0.785 [0.772–0.805] | 0.740 [0.726–0.763] | +0.045 | %100 |

Etkiler (RF ROC-AUC ortalamaları farkı): bolme (rastgele - gun gruplu), mevcut etiket: -0.001; etiket (hafif cikarilmis - mevcut), gun gruplu: +0.083; ikisi birlikte: +0.083; TI1: etiket etkisi, gun gruplu: +0.063. Çıkarılan hafif negatif: 4174; metni bulunamadığı için hafif koşullarından düşen: 1262.

**Okuma.** Aralıklar 20 bölmenin 2,5–97,5 yüzdelikleridir, güven aralığı değildir. Rastgele bölmede aynı günün (aynı hava sisteminin) örnekleri hem eğitimde hem testtedir; gün gruplu bölmede test günleri eğitimde yoktur. Literatür değerleri (0,86–0,90; ILGILI_CALISMALAR §9) farklı bölge, özellik ve modelle elde edildi; bu tablo yalnız aynı veride bölme ve etiket tanımının yönünü ve büyüklüğünü gösterir.

Çıktılar sertifikalı EDR değildir; sistem operasyonel karar aracı değil, karar destek aracıdır.
