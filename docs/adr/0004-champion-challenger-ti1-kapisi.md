# 0004 — Kapılı model aktivasyonu: TI1 referansı + aktif model

- Durum: Kabul edildi (2026-09-30); 2026-10-07'de güncellendi (Uzman Madde 7)
- İlgili kod: `ml/ml_otomatik_egitim.py` (`terfi_karari`, `altin_test_gunleri`)

## Bağlam

Gece işi her gece yeniden eğitim yapabilir. Yeni bir modelin otomatik olarak
yayına girmesi, kötü veriyle (örn. eski modeldeki irtifa filtresi hatası)
eğitilmiş bir modelin fark edilmeden kullanılması riskini taşır. Fizik tabanlı
tek gösterge (TI1) ise her zaman elde olan bir referanstır.

## Karar

Değerlendirme kümesi, bir kez seçilip `ml/altin_test_gunleri.json` dosyasına
dondurulan **altın test günleridir** (2026-10-07: 80 eşleşmiş günden rastgele 16,
tohum 0; `turbulans-ml --altin-gunleri-dondur`, dosya varsa üzerine yazmaz). Bu
günler hiçbir sürümün eğitimine girmez; yayına giren model de yalnızca eğitim
günleriyle eğitilir ve sürüm kaydına `egitim_gunleri` yazılır. Dosya yoksa
zamansal holdout (en son `ML_HOLDOUT_ORANI` gün) kullanılır ve kayıtta belirtilir.

Aday model yalnızca şu koşullarda aktifleşir; aksi halde yalnızca sürüm olarak saklanır:

1. Test kümesi yeterli (en az `ML_MIN_HOLDOUT_ORNEK` örnek, her sınıftan en az 5).
2. Aday − TI1 ROC-AUC farkı ≥ `ML_TI1_AUC_USTUNLUGU` (0,02) **ve** gün bazlı
   eşleştirilmiş bootstrap %95 GA alt sınırı > 0.
3. Aktif model varsa aynı kural ona karşı: fark ≥ `ML_SAMPIYON_AUC_USTUNLUGU`
   (0,02) ve alt sınır > 0. Altın günleri eğitiminde görmüş (ya da eğitim gün
   listesi olmayan) aktif model karşılaştırmada yok sayılır.

0,02 parametriktir, kalibre edilmedi. Eşik gerektiren metrikler (POD, POFD,
Peirce) her iki skor için de eğitim günlerinde Peirce'ı maksimize eden eşikle
hesaplanır; Brier referansı tek değişkenli lojistik "kalibre TI1"dir. Aday,
gün gruplu CV ROC-AUC'siyle seçilir; Lojistik Regresyon ile farkı en iyi modelin
kat standart hatasından küçükse Lojistik Regresyon seçilir (1-SE kuralı).

Her sürüm veri kesiti, metrikler ve karar gerekçesiyle saklanır;
`turbulans-ml --geri-al` yeniden eğitimsiz geri dönüş sağlar.

## Sonuçlar

- "Fizikten kötü ML" yayına giremez.
- Kapı, aktif model yokken bile çalışır (TI1 her zaman vardır).
- Altın test günleri her gece yeni adaylarla yeniden kullanılır; bu çoklu
  karşılaştırma, nokta farkının yanında GA alt sınırının istenmesinin nedenidir.
- Eski kural (aktif modele karşı 0,5 eşiğinde F1/recall) kaldırıldı: eşiğe bağlıydı
  ve gürültü düzeyindeki farkları ödüllendirebiliyordu.

## Değerlendirilen alternatifler

- Her eğitimde aktifleştirme: reddedildi.
- Yalnızca aktif modelle kıyas: ilk model için referans olmazdı; reddedildi.
