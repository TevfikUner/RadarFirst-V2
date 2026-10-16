# TI1 eşik eşlemesi: ERA5 → canlı GFS

Üretim: 2026-10-16T13:09:28.811479+00:00. Kutu [30.0, 50.0, 10.0, 50.0], 0.5° adım, FL [300, 320, 340, 360, 380], 12 analiz saati.

ERA5 seviyeleri [350.0, 300.0, 250.0, 225.0, 200.0, 175.0, 150.0] hPa, canlı GFS seviyeleri [200.0, 250.0, 300.0] hPa. TI1 her iki kaynakta da rota kodunun kullandığı eşleştirmeyle (`rotayi_hava_durumuyla_eslestir`) aynı noktalarda hesaplandı.

| Ölçü | Değer |
|---|---|
| Eşleşen nokta | 182655 |
| ERA5 eşiği | 7.00e-07 |
| ERA5'te eşiğin yüzdeliği | %91.5 |
| GFS eşdeğer eşik | 8.30e-07 |
| GFS eşdeğer eşik %95 GA (zaman bootstrap) | 7.96e-07 – 8.67e-07 |
| ERA5 riskli oran | %8.5 |
| GFS riskli oran (aynı eşikte) | %11.1 |
| Medyan TI1 ERA5 / GFS | 1.59e-07 / 1.84e-07 |
| Spearman (nokta bazlı) | 0.56 |

| Seviye | n | ERA5 riskli | GFS riskli (aynı eşik) | GFS eşdeğer eşik |
|---|---|---|---|---|
| FL300 | 36531 | %5.7 | %10.5 | 1.07e-06 |
| FL320 | 36531 | %7.3 | %11.1 | 9.25e-07 |
| FL340 | 36531 | %10.0 | %12.2 | 7.93e-07 |
| FL360 | 36531 | %9.5 | %12.2 | 8.16e-07 |
| FL380 | 36531 | %9.9 | %9.3 | 6.77e-07 |

Bu eşleme iki kaynağın TI1 dağılımlarını tutarlı kılar; GFS'in türbülans becerisini kanıtlamaz (o, PIREP/MADIS'e karşı doğrulama karnesinin işidir). Örneklem tek bölge ve kısa bir dönemdir. `TI1_ESIK_ORTA_SIDDETLI_GFS` bu rapordan otomatik ayarlanmaz; değer onayla `.env`'e yazılır.
