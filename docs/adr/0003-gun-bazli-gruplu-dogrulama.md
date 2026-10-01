# 0003 — Gün bazlı gruplu çapraz doğrulama ve zamansal holdout

- Durum: Kabul edildi (2026-09-30)
- İlgili kod: `ml/ml_egitimi.py`, `ml/ml_otomatik_egitim.py`

## Bağlam

Aynı gündeki PIREP'ler aynı hava sistemini (jet akımı, cephe) görür ve aynı ERA5
saatlerinden özellik alır. Rastgele bölmede aynı günün örnekleri hem eğitimde hem
testte bulunur; model hava durumunu ezberler ve skor şişer.

## Karar

- Model seçimi `StratifiedGroupKFold` ile gün grupları üzerinde yapılır.
- Terfi kararı, en son günlerin ayrıldığı zamansal holdout'ta verilir
  (`ML_HOLDOUT_ORANI`, varsayılan %20).
- Olasılık kalibrasyonu (Platt) da gün gruplu bölmelerle yapılır.
- Holdout skorları gün bazlı bootstrap güven aralığıyla raporlanır
  (bkz. [deney protokolü](../deney_protokolu.md)).

## Sonuçlar

- Skorlar daha düşük ama gerçekçi; yeni günlere genelleme ölçülür.
- En az `ML_MIN_GUN` (60) farklı gün olmadan eğitim yapılmaz.

## Değerlendirilen alternatifler

- Rastgele k-katlı CV: sızıntı nedeniyle reddedildi.
- Bölgesel gruplama: veri ABD ağırlıklı ve tek bölge; bölgesel doğrulama seti gelince eklenecek.
