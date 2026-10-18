# Sayılar (sonuç paketi)

Kesme: 2026-10-18 · üretim: 2026-10-17T23:39:56+00:00 · commit `45caf3ce890f816407c2bcbf9b3e6e722451ddc8`

Bu dosya `turbulans-ml-degerlendirme --cikti` ile üretilir; elle düzenlenmez. Kaynak: `sonuc_paketi.json` (anahtar sütunu). GA: gün bazlı blok bootstrap %95. Çıktılar sertifikalı EDR değildir; sistem karar destek aracıdır.

| Sayı | Değer | JSON anahtarı |
|---|---|---|
| Eşleşmiş PIREP (seyir irtifası) | 15.940 | `veri.ornek` |
| Gün | 163 | `veri.gun` |
| Pozitif oranı (orta ve üstü) | 0,532 | `veri.pozitif_orani` |
| Eğitim örnek / gün | 14.357 / 147 | `veri.egitim_ornek, egitim_gun` |
| Altın test örnek / gün | 1.583 / 16 | `veri.test_ornek, test_gun` |
| Protokol modeli (1-SE) | Gradient Boosting | `model.secilen` |
| Model ROC-AUC (altın günler) | 0,710 [0,680–0,740] | `pirep_test.skorlar.Model.roc_auc` |
| Model PR-AUC (altın günler) | 0,692 [0,652–0,724] | `pirep_test.skorlar.Model.pr_auc` |
| Model − TI1 ROC-AUC farkı | +0,036 [+0,019; +0,053], p < 0,001 | `pirep_test.skorlar.Model.ti1_farki` |
| TI1 ROC-AUC (altın günler) | 0,675 [0,641–0,706] | `pirep_test.skorlar.TI1.roc_auc` |
| TI1 PR-AUC (altın günler) | 0,665 [0,622–0,701] | `pirep_test.skorlar.TI1.pr_auc` |
| 1/Ri ROC-AUC (altın günler) | 0,655 [0,627–0,681] | `pirep_test.skorlar.1/Ri.roc_auc` |
| 1/Ri PR-AUC (altın günler) | 0,636 [0,589–0,674] | `pirep_test.skorlar.1/Ri.pr_auc` |
| 1/Ri − TI1 ROC-AUC farkı | -0,020 [-0,052; +0,011], p 0,202 | `pirep_test.skorlar.1/Ri.ti1_farki` |
| Birleşik EDR ROC-AUC (altın günler) | 0,688 [0,656–0,717] | `pirep_test.skorlar.Birleşik EDR.roc_auc` |
| Birleşik EDR PR-AUC (altın günler) | 0,675 [0,634–0,709] | `pirep_test.skorlar.Birleşik EDR.pr_auc` |
| Birleşik EDR − TI1 ROC-AUC farkı | +0,013 [+0,007; +0,020], p < 0,001 | `pirep_test.skorlar.Birleşik EDR.ti1_farki` |
| Model Brier / Brier becerisi (altın günler) | 0,217 / 0,128 | `model_olasilik_test.brier, brier_becerisi` |
| Model ortalama olasılık / gözlenen oran (altın günler) | 0,518 / 0,476 | `model_olasilik_test` |
| TI1 ROC-AUC (tüm günler) | 0,673 [0,661–0,684] | `pirep_tum_gunler_fizik.skorlar.TI1.roc_auc` |
| 1/Ri ROC-AUC (tüm günler) | 0,655 [0,644–0,666] | `pirep_tum_gunler_fizik.skorlar.1/Ri.roc_auc` |
| Birleşik EDR ROC-AUC (tüm günler) | 0,688 [0,676–0,698] | `pirep_tum_gunler_fizik.skorlar.Birleşik EDR.roc_auc` |
| TI1 Peirce eşiği (eğitim günleri) | 4.96e-07 | `esik_taramasi.peirce_esigi` |
| Peirce eşiğinde test POD / POFD / CSI | 0,622 / 0,373 / 0,441 | `esik_taramasi.test` |
| Peirce eşiğinde test Peirce | 0,249 [0,177–0,308] | `esik_taramasi.test.peirce` |
| TI1 1-SE eşiği (eğitim günleri; Peirce max − SE) | 7.39e-07 (Peirce max 0,256, SE 0,011) | `esik_taramasi.bir_se` |
| 1-SE eşiğinde test POD / POFD / CSI | 0,481 / 0,230 / 0,384 | `esik_taramasi.bir_se_test` |
| Ri Peirce eşiği (eğitim günleri; Ri altı riskli) | 2,27 | `esik_taramasi.ri_peirce_esigi.ri` |
| TI1_ESIK_HAFIF (4e-07) test POD / POFD / CSI | 0,682 / 0,439 / 0,460 | `esik_taramasi.config_esikleri.TI1_ESIK_HAFIF.test` |
| TI1_ESIK_ORTA_SIDDETLI (7e-07) test POD / POFD / CSI | 0,501 / 0,248 / 0,394 | `esik_taramasi.config_esikleri.TI1_ESIK_ORTA_SIDDETLI.test` |
| 175 hPa: eşik; test POD/POFD/CSI seviye eşiğiyle | genel eşikle | 4.3e-07; 0,692/0,358/0,444 | 0,673/0,333/0,443 (test n=133) | `esik_taramasi.seviyeye_gore[0]` |
| 200 hPa: eşik; test POD/POFD/CSI seviye eşiğiyle | genel eşikle | 6.7e-07; 0,523/0,239/0,416 | 0,621/0,303/0,469 (test n=274) | `esik_taramasi.seviyeye_gore[1]` |
| 225 hPa: eşik; test POD/POFD/CSI seviye eşiğiyle | genel eşikle | 6.8e-07; 0,510/0,314/0,359 | 0,637/0,457/0,395 (test n=367) | `esik_taramasi.seviyeye_gore[2]` |
| 250 hPa: eşik; test POD/POFD/CSI seviye eşiğiyle | genel eşikle | 4.6e-07; 0,590/0,387/0,426 | 0,578/0,368/0,423 (test n=534) | `esik_taramasi.seviyeye_gore[3]` |
| 300 hPa: eşik; test POD/POFD/CSI seviye eşiğiyle | genel eşikle | 4.3e-07; 0,717/0,341/0,559 | 0,689/0,307/0,549 (test n=194) | `esik_taramasi.seviyeye_gore[4]` |
| 350 hPa: eşik; test POD/POFD/CSI seviye eşiğiyle | genel eşikle | 7.3e-07; 0,385/0,190/0,319 | 0,615/0,429/0,421 (test n=81) | `esik_taramasi.seviyeye_gore[5]` |
| Metni olan / CAT dışı işaretli örnek | 14.493 / 233 | `cat_alt_kumesi` |
| CAT dışı örneklerde pozitif oranı | 0,438 | `cat_alt_kumesi.cat_disi_pozitif_orani` |
| Altın günlerde metinli / yalnız CAT örnek | 1.398 / 1.382 | `cat_alt_kumesi.test_metinli.ornek, test_cat.ornek` |
| Model ROC-AUC, yalnız CAT (altın günler) | 0,710 [0,674–0,747] | `cat_alt_kumesi.test_cat.skorlar.Model.roc_auc` |
| TI1 ROC-AUC, yalnız CAT (altın günler) | 0,670 [0,634–0,708] | `cat_alt_kumesi.test_cat.skorlar.TI1.roc_auc` |
| 1/Ri ROC-AUC, yalnız CAT (altın günler) | 0,654 [0,623–0,687] | `cat_alt_kumesi.test_cat.skorlar.1/Ri.roc_auc` |
| Birleşik EDR ROC-AUC, yalnız CAT (altın günler) | 0,684 [0,650–0,721] | `cat_alt_kumesi.test_cat.skorlar.Birleşik EDR.roc_auc` |
| TI1 ROC-AUC, yalnız CAT (tüm günler) | 0,673 [0,661–0,685] | `cat_alt_kumesi.tum_gunler_cat_fizik.skorlar.TI1.roc_auc` |
| 1/Ri ROC-AUC, yalnız CAT (tüm günler) | 0,656 [0,644–0,667] | `cat_alt_kumesi.tum_gunler_cat_fizik.skorlar.1/Ri.roc_auc` |
| Birleşik EDR ROC-AUC, yalnız CAT (tüm günler) | 0,688 [0,676–0,699] | `cat_alt_kumesi.tum_gunler_cat_fizik.skorlar.Birleşik EDR.roc_auc` |
| MADIS ölçüm / pozitif / gün | 45.075 / 1.310 / 14 | `madis` |
| MADIS orta ve üstü ölçüm | 1 | `madis.orta_ve_ustu` |
| MADIS Model ROC-AUC | 0,779 [0,738–0,816] | `madis.skorlar.Model.roc_auc` |
| MADIS Model PR-AUC | 0,126 [0,095–0,165] | `madis.skorlar.Model.pr_auc` |
| MADIS Model − TI1 ROC-AUC farkı | +0,057 [+0,031; +0,082], p < 0,001 | `madis.skorlar.Model.ti1_farki` |
| MADIS TI1 ROC-AUC | 0,722 [0,669–0,779] | `madis.skorlar.TI1.roc_auc` |
| MADIS TI1 PR-AUC | 0,105 [0,073–0,154] | `madis.skorlar.TI1.pr_auc` |
| MADIS 1/Ri ROC-AUC | 0,722 [0,672–0,766] | `madis.skorlar.1/Ri.roc_auc` |
| MADIS 1/Ri PR-AUC | 0,085 [0,058–0,116] | `madis.skorlar.1/Ri.pr_auc` |
| MADIS 1/Ri − TI1 ROC-AUC farkı | -0,000 [-0,060; +0,053], p 0,942 | `madis.skorlar.1/Ri.ti1_farki` |
| MADIS Birleşik EDR ROC-AUC | 0,757 [0,710–0,804] | `madis.skorlar.Birleşik EDR.roc_auc` |
| MADIS Birleşik EDR PR-AUC | 0,115 [0,085–0,161] | `madis.skorlar.Birleşik EDR.pr_auc` |
| MADIS Birleşik EDR − TI1 ROC-AUC farkı | +0,035 [+0,020; +0,050], p < 0,001 | `madis.skorlar.Birleşik EDR.ti1_farki` |
| MADIS taban oran (hafif ve üstü) | 0,029 | `madis.taban_oran` |
| MADIS model ortalama olasılık | 0,509 | `madis.model_olasilik.ortalama_olasilik` |
| MADIS model Brier becerisi | -8,549 | `madis.model_olasilik.brier_becerisi` |
| MADIS model Brier becerisi, önsel kayma düzeltmeli (gösterim, iyimser) | 0,043 | `madis.model_olasilik_onsel_duzeltilmis.brier_becerisi` |
| Backtest THY322 2019-01-01 riskli oran (gerçek / büyük daire / A*) | 0,00 / 0,20 / 0,00 | `backtest[0]` |
| Backtest THY322 2019-01-15 riskli oran (gerçek / büyük daire / A*) | 0,24 / 0,39 / 0,02 | `backtest[1]` |
