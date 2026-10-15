# Gözlemlerle rüzgâr düzeltme (F7) fizibilite notu

15 Ekim 2026. Amaç: canlı GFS rüzgârını uçak gözlemleriyle düzeltip (optimal
interpolasyon) TI1'i yeniden hesaplamak; "ERA5'te seçilen eşik GFS'ye doğrulanmadan
aktarılır" sınırlamasına bir deney önermek. Kod yazılmadı.

## Yöntem (önerilen)

- Durum x: uçuş seviyelerinde u, v. Arka plan x_b: GFS.
- Gözlem operatörü H: çift doğrusal interpolasyon (zaman ve seviye en yakın).
- B = σ_b² · exp(−d²/L²), L ≈ 150–300 km; σ_b GFS–ERA5 farkından tahmin edilir.
- R = σ_o² · I, σ_o MADIS `windSpeedError` alanından ya da sabit 2–3 m/s.
- Az gözlemde kapalı form: x_a = x_b + BHᵀ(HBHᵀ + R)⁻¹(y − Hx_b).
- Doğrulama: uçak bazında gözlem dışarıda bırakıp rüzgâr RMSE'si; sonra analiz
  alanından ve ham GFS'den hesaplanan TI1'in MADIS EDR'ye karşı ROC-AUC'si.

## Kontrol edilenler

| Soru | Sonuç |
|---|---|
| MADIS herkese açık ACARS dosyasında rüzgâr var mı? | Evet: `windSpeed` (m/s), `windDir`, `temperature`, QC alanları ve `windSpeedError`. 2019-01-15 18Z: 41.120 kayıt, 34.257'sinde rüzgâr; FL280 üstü 12.214 |
| Bölgesel kapsam (aynı saat, FL280 üstü) | Avrupa kutusu (35–60°K, 10°B–30°D) 489, Türkiye kutusu (34–43°K, 25–45°D) 23 rüzgâr gözlemi. Türkiye'de EDR yok ama rüzgâr gözlemi var |
| Bugün ham MADIS dosyası tutuluyor mu? | Hayır: dosya işlenip silinir, yalnız EDR Parquet'e yazılır. Rüzgâr için yeniden indirme gerekir (gün başına ~65 MB, MADIS sınırı gece başına 1 gün) |
| MADIS EDR günleri için geçmiş GFS var mı? | EDR günleri 2018-01-06 – 2019-06-12 (12 gün). AWS `noaa-gfs-bdp-pds` 2021'den başlıyor (gfs.20190115 yok, gfs.20210101 var). NCEI geçmiş analiz yolunda 2019-01-15 bulunamadı (404). NCAR RDA kontrol edilmedi (hesap gerekir) |
| ERA5 arka plan olabilir mi? | Uygun değil: ERA5 aynı uçak gözlemlerini zaten özümsemiştir, döngüsel olur |

## Sonuç

Yöntem uygulanabilir ve veri alanları mevcut. Engel, aynı günlerde GFS + MADIS EDR +
MADIS rüzgârı birlikte bulunması:

1. **Uygulanabilir yol:** 2021 sonrası MADIS günleri seçilir (AWS GFS mevcut). Bu günler
   için MADIS EDR ve rüzgâr indirilir; ERA5 penceresi yalnız karşılaştırma için gerekir.
   Veri bütçesi: gün başına ~65 MB MADIS + GFS koridor kesiti. Günlük 500 MB bütçeyle
   gece başına 1 gün.
2. **Canlı mod:** Türkiye üzerinde saatte birkaç düzine FL280 üstü rüzgâr gözlemi var.
   Canlı GFS'nin çevrimiçi düzeltmesi mümkün, ama EDR olmadığı için orada doğrulanamaz.
   Doğrulama ABD'de yapılıp sonuç bölgeye aktarılmak zorunda.

Öneri: 18 Ekim'den sonra, 1. yol için 5–10 günlük küçük bir deney. Önce rüzgâr
RMSE'si (gözlem dışarıda bırakılarak), sonra TI1 ROC-AUC. Gece veri bütçesine
eklenmeden önce ONAY gerekir.
