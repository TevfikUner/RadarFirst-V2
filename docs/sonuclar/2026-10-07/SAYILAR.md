# Sayılar (sonuç paketi)

Kesme: 2026-10-07 · üretim: 2026-10-07T20:23:44+00:00 · commit `34c6f9378072840bc16fb7fa2ae7495fc8d30ad2`

Bu dosya `turbulans-ml-degerlendirme --cikti` ile üretilir; elle düzenlenmez. Kaynak: `sonuc_paketi.json` (anahtar sütunu). GA: gün bazlı blok bootstrap %95. Çıktılar sertifikalı EDR değildir; sistem karar destek aracıdır.

| Sayı | Değer | JSON anahtarı |
|---|---|---|
| Eşleşmiş PIREP (seyir irtifası) | 7.815 | `veri.ornek` |
| Gün | 80 | `veri.gun` |
| Pozitif oranı (orta ve üstü) | 0,520 | `veri.pozitif_orani` |
| Eğitim örnek / gün | 6.261 / 64 | `veri.egitim_ornek, egitim_gun` |
| Altın test örnek / gün | 1.554 / 16 | `veri.test_ornek, test_gun` |
| Protokol modeli (1-SE) | Lojistik Regresyon | `model.secilen` |
| Model ROC-AUC (altın günler) | 0,681 [0,646–0,716] | `pirep_test.skorlar.Model.roc_auc` |
| Model PR-AUC (altın günler) | 0,672 [0,632–0,707] | `pirep_test.skorlar.Model.pr_auc` |
| Model − TI1 ROC-AUC farkı | +0,008 [-0,006; +0,022], p 0,268 | `pirep_test.skorlar.Model.ti1_farki` |
| TI1 ROC-AUC (altın günler) | 0,673 [0,639–0,704] | `pirep_test.skorlar.TI1.roc_auc` |
| TI1 PR-AUC (altın günler) | 0,666 [0,624–0,702] | `pirep_test.skorlar.TI1.pr_auc` |
| 1/Ri ROC-AUC (altın günler) | 0,653 [0,626–0,678] | `pirep_test.skorlar.1/Ri.roc_auc` |
| 1/Ri PR-AUC (altın günler) | 0,639 [0,596–0,676] | `pirep_test.skorlar.1/Ri.pr_auc` |
| 1/Ri − TI1 ROC-AUC farkı | -0,021 [-0,053; +0,011], p 0,190 | `pirep_test.skorlar.1/Ri.ti1_farki` |
| Birleşik EDR ROC-AUC (altın günler) | 0,687 [0,655–0,717] | `pirep_test.skorlar.Birleşik EDR.roc_auc` |
| Birleşik EDR PR-AUC (altın günler) | 0,677 [0,637–0,710] | `pirep_test.skorlar.Birleşik EDR.pr_auc` |
| Birleşik EDR − TI1 ROC-AUC farkı | +0,014 [+0,007; +0,020], p < 0,001 | `pirep_test.skorlar.Birleşik EDR.ti1_farki` |
| Model Brier / Brier becerisi (altın günler) | 0,226 / 0,095 | `model_olasilik_test.brier, brier_becerisi` |
| Model ortalama olasılık / gözlenen oran (altın günler) | 0,523 / 0,481 | `model_olasilik_test` |
| TI1 ROC-AUC (tüm günler) | 0,680 [0,662–0,697] | `pirep_tum_gunler_fizik.skorlar.TI1.roc_auc` |
| 1/Ri ROC-AUC (tüm günler) | 0,652 [0,637–0,667] | `pirep_tum_gunler_fizik.skorlar.1/Ri.roc_auc` |
| Birleşik EDR ROC-AUC (tüm günler) | 0,692 [0,675–0,709] | `pirep_tum_gunler_fizik.skorlar.Birleşik EDR.roc_auc` |
| TI1 Peirce eşiği (eğitim günleri) | 5.30e-07 | `esik_taramasi.peirce_esigi` |
| Peirce eşiğinde test POD / POFD / CSI | 0,605 / 0,349 / 0,439 | `esik_taramasi.test` |
| Peirce eşiğinde test Peirce | 0,256 [0,188–0,313] | `esik_taramasi.test.peirce` |
| Ri Peirce eşiği (eğitim günleri; Ri altı riskli) | 2,37 | `esik_taramasi.ri_peirce_esigi.ri` |
| TI1_ESIK_HAFIF (4e-07) test POD / POFD / CSI | 0,683 / 0,440 / 0,463 | `esik_taramasi.config_esikleri.TI1_ESIK_HAFIF.test` |
| TI1_ESIK_ORTA_SIDDETLI (8e-07) test POD / POFD / CSI | 0,448 / 0,201 / 0,369 | `esik_taramasi.config_esikleri.TI1_ESIK_ORTA_SIDDETLI.test` |
| 175 hPa: eşik; test POD/POFD/CSI seviye eşiğiyle | genel eşikle | 5.7e-07; 0,596/0,286/0,419 | 0,635/0,312/0,434 (test n=129) | `esik_taramasi.seviyeye_gore[0]` |
| 200 hPa: eşik; test POD/POFD/CSI seviye eşiğiyle | genel eşikle | 6.7e-07; 0,527/0,246/0,418 | 0,611/0,297/0,465 (test n=269) | `esik_taramasi.seviyeye_gore[1]` |
| 225 hPa: eşik; test POD/POFD/CSI seviye eşiğiyle | genel eşikle | 5.5e-07; 0,619/0,403/0,403 | 0,626/0,413/0,404 (test n=361) | `esik_taramasi.seviyeye_gore[2]` |
| 250 hPa: eşik; test POD/POFD/CSI seviye eşiğiyle | genel eşikle | 4.3e-07; 0,615/0,411/0,437 | 0,562/0,350/0,417 (test n=528) | `esik_taramasi.seviyeye_gore[3]` |
| 300 hPa: eşik; test POD/POFD/CSI seviye eşiğiyle | genel eşikle | 5.1e-07; 0,676/0,286/0,550 | 0,667/0,286/0,543 (test n=189) | `esik_taramasi.seviyeye_gore[4]` |
| 350 hPa: eşik; test POD/POFD/CSI seviye eşiğiyle | genel eşikle | 1.1e-06; 0,256/0,128/0,227 | 0,590/0,410/0,418 (test n=78) | `esik_taramasi.seviyeye_gore[5]` |
| Metni olan / CAT dışı işaretli örnek | 6.764 / 119 | `cat_alt_kumesi` |
| CAT dışı örneklerde pozitif oranı | 0,420 | `cat_alt_kumesi.cat_disi_pozitif_orani` |
| Altın günlerde metinli / yalnız CAT örnek | 1.369 / 1.353 | `cat_alt_kumesi.test_metinli.ornek, test_cat.ornek` |
| Model ROC-AUC, yalnız CAT (altın günler) | 0,678 [0,638–0,724] | `cat_alt_kumesi.test_cat.skorlar.Model.roc_auc` |
| TI1 ROC-AUC, yalnız CAT (altın günler) | 0,669 [0,632–0,707] | `cat_alt_kumesi.test_cat.skorlar.TI1.roc_auc` |
| 1/Ri ROC-AUC, yalnız CAT (altın günler) | 0,652 [0,621–0,685] | `cat_alt_kumesi.test_cat.skorlar.1/Ri.roc_auc` |
| Birleşik EDR ROC-AUC, yalnız CAT (altın günler) | 0,683 [0,649–0,720] | `cat_alt_kumesi.test_cat.skorlar.Birleşik EDR.roc_auc` |
| TI1 ROC-AUC, yalnız CAT (tüm günler) | 0,679 [0,660–0,697] | `cat_alt_kumesi.tum_gunler_cat_fizik.skorlar.TI1.roc_auc` |
| 1/Ri ROC-AUC, yalnız CAT (tüm günler) | 0,653 [0,639–0,669] | `cat_alt_kumesi.tum_gunler_cat_fizik.skorlar.1/Ri.roc_auc` |
| Birleşik EDR ROC-AUC, yalnız CAT (tüm günler) | 0,692 [0,674–0,709] | `cat_alt_kumesi.tum_gunler_cat_fizik.skorlar.Birleşik EDR.roc_auc` |
| MADIS ölçüm / pozitif / gün | 20.144 / 607 / 6 | `madis` |
| MADIS orta ve üstü ölçüm | 0 | `madis.orta_ve_ustu` |
| MADIS Model ROC-AUC | 0,734 [0,664–0,820] | `madis.skorlar.Model.roc_auc` |
| MADIS Model PR-AUC | 0,092 [0,071–0,128] | `madis.skorlar.Model.pr_auc` |
| MADIS Model − TI1 ROC-AUC farkı | +0,028 [+0,002; +0,045], p 0,036 | `madis.skorlar.Model.ti1_farki` |
| MADIS TI1 ROC-AUC | 0,706 [0,631–0,801] | `madis.skorlar.TI1.roc_auc` |
| MADIS TI1 PR-AUC | 0,091 [0,062–0,144] | `madis.skorlar.TI1.pr_auc` |
| MADIS 1/Ri ROC-AUC | 0,696 [0,648–0,741] | `madis.skorlar.1/Ri.roc_auc` |
| MADIS 1/Ri PR-AUC | 0,076 [0,047–0,106] | `madis.skorlar.1/Ri.pr_auc` |
| MADIS 1/Ri − TI1 ROC-AUC farkı | -0,010 [-0,073; +0,069], p 0,702 | `madis.skorlar.1/Ri.ti1_farki` |
| MADIS Birleşik EDR ROC-AUC | 0,738 [0,667–0,825] | `madis.skorlar.Birleşik EDR.roc_auc` |
| MADIS Birleşik EDR PR-AUC | 0,102 [0,072–0,154] | `madis.skorlar.Birleşik EDR.pr_auc` |
| MADIS Birleşik EDR − TI1 ROC-AUC farkı | +0,032 [+0,014; +0,049], p < 0,001 | `madis.skorlar.Birleşik EDR.ti1_farki` |
| MADIS taban oran (hafif ve üstü) | 0,030 | `madis.taban_oran` |
| MADIS model ortalama olasılık | 0,510 | `madis.model_olasilik.ortalama_olasilik` |
| MADIS model Brier becerisi | -8,364 | `madis.model_olasilik.brier_becerisi` |
| Backtest THY322 2019-01-01 riskli oran (gerçek / büyük daire / A*) | 0,00 / 0,05 / 0,00 | `backtest[0]` |
| Backtest THY322 2019-01-15 riskli oran (gerçek / büyük daire / A*) | 0,19 / 0,32 / 0,00 | `backtest[1]` |
