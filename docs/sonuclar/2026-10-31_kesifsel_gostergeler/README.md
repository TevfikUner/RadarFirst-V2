# Keşifsel göstergeler (protokol §13.1–13.4)

Üretim 2026-10-31T02:45:31+00:00 · commit `735262e68dc4a080583a748f08a70964f70b1476`. Eğitim 163 dondurma günü (16031 örnek), test §10'un sabit 79 günü (7772 örnek). Kontrol: temel set test ROC-AUC 0,685 (§10: 0,685). Hepsi keşifseldir; birincil sonuç, model ve rota kararı değişmez.

## Fikir 10: komşuluk maksimumu (7772 örnek)

ROC-AUC: TI1 0,658, A (±1 hücre/seviye/saat) 0,686, B (yalnız yatay ±1 hücre) 0,678.

| Karşılaştırma | ROC-AUC farkı | %95 GA | Okuma |
|---|---|---|---|
| A_komsu_maks - TI1 | +0,0274 | [+0,0173; +0,0371] | daha iyi ayırıyor |
| B_yatay_maks - TI1 | +0,0200 | [+0,0158; +0,0241] | daha iyi ayırıyor |

| 7e-7 kural eşiği | POD | POFD | Peirce |
|---|---|---|---|
| TI1 | 0,485 | 0,253 | 0,233 |
| A_komsu_maks | 0,853 | 0,644 | 0,209 |

| Eğitim Peirce-maks eşiği | Eşik | POD | POFD | Peirce |
|---|---|---|---|---|
| TI1 | 4,94e-07 | 0,606 | 0,377 | 0,229 |
| A_komsu_maks | 1,14e-06 | 0,680 | 0,406 | 0,274 |
| B_yatay_maks | 7,95e-07 | 0,585 | 0,324 | 0,261 |

## Fikir 11 devamı: çoklu /TB grubu etiketi

Test: 7772 örneğin 5896'inde ham rapor bulundu; 248 çok gruplu; etiket 0→1 22, 1→0 0; tek grupta ayrıştırma farkı 0. Eğitim günlerinde 0→1 38, 1→0 0 (eğitim yeniden yapılmadı).

| Karşılaştırma | ROC-AUC farkı | %95 GA | Okuma |
|---|---|---|---|
| TI1: AUC(y_çok) − AUC(y) | +0,0011 | [-0,0011; +0,0037] | fark gösterilemedi |
| birlesik_edr: AUC(y_çok) − AUC(y) | +0,0016 | [-0,0005; +0,0041] | fark gösterilemedi |
| temel: AUC(y_çok) − AUC(y) | +0,0022 | [+0,0000; +0,0047] | daha iyi ayırıyor |
| genis: AUC(y_çok) − AUC(y) | +0,0015 | [-0,0007; +0,0042] | fark gösterilemedi |

## Fikir 24: AUC² ağırlıklı birleşik EDR (7772 örnek)

Ağırlıklar (eğitim AUC): ti1_indeksi 0,211 (0,673), ti2_indeksi 0,209 (0,670), dusey_ruzgar_kaymasi 0,195 (0,647), yatay_deformasyon 0,184 (0,629), ters_richardson 0,200 (0,655). Test ROC-AUC: ağırlıklı 0,669, eşit 0,669, TI1 0,658.

| Karşılaştırma | ROC-AUC farkı | %95 GA | Okuma |
|---|---|---|---|
| agirlikli - esit | -0,0003 | [-0,0005; -0,0001] | daha kötü ayırıyor |
| agirlikli - TI1 | +0,0109 | [+0,0068; +0,0149] | daha iyi ayırıyor |

## Fikir 19: ek teşhisler (7772 örnek; NCSU1 hesaplanmadı)

Tek başına ROC-AUC: TI1 0,658, FRONT 0,518, abs(FRONT) 0,591, TEMPG 0,559, -PV 0,510. PV < 0 payı: orta-üstü 0,081, kontrol 0,055.

| Karşılaştırma | ROC-AUC farkı | %95 GA | Okuma |
|---|---|---|---|
| FRONT − TI1 | -0,1405 | [-0,1596; -0,1207] | daha kötü ayırıyor |
| abs(FRONT) − TI1 | -0,0677 | [-0,0814; -0,0543] | daha kötü ayırıyor |
| TEMPG − TI1 | -0,0993 | [-0,1161; -0,0830] | daha kötü ayırıyor |
| -PV − TI1 | -0,1486 | [-0,1759; -0,1199] | daha kötü ayırıyor |
| temel + 3 teşhis (Lojistik Regresyon) − temel (Random Forest) | -0,0039 | [-0,0098; +0,0022] | fark gösterilemedi |

Çoklu karşılaştırma düzeltmesi yapılmadı; satırlar keşifseldir. Çıktılar sertifikalı EDR değildir; sistem operasyonel karar aracı değil, karar destek aracıdır.
