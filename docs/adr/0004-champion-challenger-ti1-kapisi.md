# 0004 — Kapılı model aktivasyonu: TI1 referansı + aktif model

- Durum: Kabul edildi (2026-09-30)
- İlgili kod: `ml/ml_otomatik_egitim.py` (`terfi_karari`)

## Bağlam

Gece işi her gece yeniden eğitim yapabilir. Yeni bir modelin otomatik olarak
yayına girmesi, kötü veriyle (örn. eski modeldeki irtifa filtresi hatası)
eğitilmiş bir modelin fark edilmeden kullanılması riskini taşır. Fizik tabanlı
tek gösterge (TI1) ise her zaman elde olan bir referanstır.

## Karar

Aday model yalnızca şu koşullarda aktifleşir; aksi halde yalnızca sürüm olarak saklanır:

1. Holdout yeterli (en az `ML_MIN_HOLDOUT_ORNEK` örnek, her sınıftan en az 5).
2. Holdout ROC-AUC'si tek başına TI1'i en az `ML_TI1_AUC_USTUNLUGU` (0,02) geçer.
3. Aktif model varsa F1'de en az `ML_MIN_F1_IYILESME` iyileşir ve recall
   `ML_RECALL_TOLERANSI`'ndan fazla düşmez.

Her sürüm veri kesiti, metrikler ve karar gerekçesiyle saklanır;
`turbulans-ml --geri-al` yeniden eğitimsiz geri dönüş sağlar. Holdout raporu
ayrıca TI1'e karşı eşleştirilmiş bootstrap farkını içerir.

## Sonuçlar

- "Fizikten kötü ML" yayına giremez.
- Kapı, aktif model yokken bile çalışır (TI1 her zaman vardır).

## Değerlendirilen alternatifler

- Her eğitimde aktifleştirme: reddedildi.
- Yalnızca aktif modelle kıyas: ilk model için referans olmazdı; reddedildi.
