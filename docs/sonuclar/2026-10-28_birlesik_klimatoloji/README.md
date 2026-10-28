# Birleşik EDR klimatolojisinin altın günlere duyarlılığı (28 Ekim 2026, VER-07)

Soru: Birleşik EDR'nin log-normal eşleme klimatolojisi (`fizik/edr_esleme_katsayilari.json`, 5 Ekim, 49 gün)
yalnız zamansal holdout günlerini dışladı; 16 altın test gününün bir kısmının pencereleri içinde olabilir. Etiket
kullanılmadığı için klasik sızıntı değildir; bu analiz etkisini ölçer. Üretim katsayı dosyası değiştirilmedi.

Pencere deposundan iki klimatoloji gün gün toplandı: dondurma eğitim günleri (147 = 163 − 16 altın gün) ve altın
günler dahil 163 gün. Altın günlerdeki aynı 1.583 örnekte birleşik EDR üç katsayı kümesiyle puanlandı.

| Katsayı kümesi | Altın günlerde ROC-AUC [%95 GA] |
|---|---|
| Mevcut (5 Ekim, 49 gün) | 0,688 [0,656; 0,717] |
| Eğitim günleri (147, altın günler hariç) | 0,688 [0,656; 0,717] |
| Altın günler dahil (163) | 0,688 [0,656; 0,717] |

| Fark (gün bloklu eşleştirilmiş bootstrap) | Fark [%95 GA] |
|---|---|
| Eğitim − mevcut | +0,0001 [−0,0003; +0,0005], p 0,59 |
| Altın dahil − mevcut | +0,0001 [−0,0002; +0,0003], p 0,53 |
| Altın dahil − eğitim | −0,0000 [−0,0002; +0,0001], p 0,77 |

**Sonuç.** Altın günlerin normalizasyona girmesinin birleşik EDR skoruna etkisi yok (≤ 0,0001 ROC-AUC); 18 Ekim
paketindeki birleşik EDR sayıları geçerli. ln ortalamaları en çok 0,08 (ters Richardson) kayıyor, sıralamayı değiştirmiyor.

**Yeniden üretim.** `turbulans-birlesik-klimatoloji --cikti <klasör>` (WSL venv, veritabanından yalnız okuma, pencere
deposu yerel; ~12 dk). JSON'daki commit ölçüm anındaki HEAD'dir.

Çıktılar sertifikalı EDR değildir; sistem operasyonel karar aracı değil, karar destek aracıdır.
