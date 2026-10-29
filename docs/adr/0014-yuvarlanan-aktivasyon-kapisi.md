# 0014 — Model aktivasyon kapısı: yuvarlanan yeni günler, altın günler yalnız rapor

- Durum: Kabul edildi (2026-10-29; kurul raporu #28, VER-02)
- İlgili kod: `ml/ml_otomatik_egitim.py` (`degerlendirme_plani`, `gun_eslesme_sirasi`,
  `otomatik_egitim_calistir`), `config.ML_YUVARLANAN_KAPI_GUN`

## Bağlam

Gece kapısı her gece aynı 16 altın test gününü kullanıyordu: 7–18 Ekim arasında 12 sürüm aynı günlerde
kapıya girdi. Aynı test kümesine tekrar tekrar bakmak uyarlamalı aşırı uyum doğurur; aktif modelin altın
gün skoru artık "temiz" değildir (VER-02). §10 (19 Ekim) yeni günlerde tek seferlik temiz bir ölçüm yaptı;
kapının kendisi hâlâ altın günlerdeydi.

## Karar

Aktivasyon kararı, aktif modelin eğitiminde görmediği ve altın olmayan günlerden **eşleşme sırasına göre
en son N** günde verilir (`ML_YUVARLANAN_KAPI_GUN`, varsayılan 16). Kapı kuralı değişmez: TI1'e ve aktif
modele karşı gün eşleştirilmiş bootstrap ROC-AUC farkı, nokta fark ≥ üstünlük ve %95 GA alt sınırı > 0.

- Altın günler hiçbir eğitime girmez ve yalnız raporlanır (`holdout.altin_raporu`); karara girmez.
- Kapı günleri de adayın eğitimine girmez. Aktif model onları görmediği için şampiyon karşılaştırması temizdir.
- "Yeni gün" tarih değil eşleşme anıdır: veri geriye dönük doldurulduğu için günler, eşleşmiş örneklerinin
  en erken `guncellenme_zamani`'na göre sıralanır (yaklaşık; satır yeniden güncellenirse kayabilir).
  Böylece gece işi yeni gün ekledikçe pencere kayar ve aynı günler tekrar tekrar kullanılmaz.
- Yeni gün N'den azsa aday aktifleştirilmez, aktif model korunur (gerekçede "yetersiz"); metrikler altın
  günlerde yalnız rapor için hesaplanır.
- `ML_YUVARLANAN_KAPI_GUN=0` eski davranışa (kapı altın günlerde) döner.

Gerekçe:

- N = 16, altın küme boyutuyla aynıdır; kapının istatistiksel gücü değişmez. 29 Ekim'de aktif modele göre
  148 yeni gün vardı; son 16'sında 1.373 örnek (771 pozitif) bulunuyor.
- Pencere kaydığı için tek bir test kümesine uyarlama olmaz; her kapı kararı o ana kadar hiçbir modelin
  karar için kullanmadığı günlere dayanır (kapı günleri sonraki gecelerde eğitime geçebilir).

## Sonuçlar

- Kapı her gece farklı günlerde ölçüldüğü için sürümler arası skorlar doğrudan karşılaştırılamaz; altın gün
  raporu bu yüzden tutulur.
- Ardışık yakın günler (aynı hava sistemi) kapı penceresinde birlikte olabilir; gün gruplu bootstrap bunu
  kısmen karşılar.
- Gece işi 28 Ekim'den beri duraklatılmış durumda; karar ilk gece işinde uygulanır, aktif model bu
  değişiklikle değişmez.
- Çıktılar sertifikalı EDR değildir; sistem operasyonel karar aracı değil, karar destek aracıdır.
