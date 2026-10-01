# 0010 — Risk olasılığına konformal belirsizlik durumu

- Durum: Kabul edildi (2026-10-01)
- İlgili kod: `ml/belirsizlik.py`, `ml/ml_otomatik_egitim.py`, `POST /api/v1/turbulans/tahmin`

## Bağlam

Model tek bir olasılık veriyordu. Dispeçer 0,55'in dar mı geniş mi bir aralıkta
olduğunu bilemiyor; "düşük risk, eminim" ile "veri yetersiz" ayrılmıyordu.
Belirsizliğin modelden bağımsız, istatistiksel güvencesi olan bir biçimde
verilmesi gerekiyordu.

## Karar

- İkili sınıflandırma için bölünmüş/çapraz konformal tahmin. Uyumsuzluk skoru
  s = 1 − p(gerçek sınıf); eşik q, kalibrasyon skorlarının
  ⌈(n+1)(1−α)⌉/n yüzdeliği; α = `ML_KONFORMAL_ALFA` (0,10).
- Tahmin kümesi {y : 1 − p(y) ≤ q}. {1} → `yuksek_risk`, {0} → `dusuk_risk`,
  {0, 1} ya da boş küme → `belirsiz`.
- Kalibrasyon skorları gün gruplu çapraz doğrulamanın kat dışı, Platt kalibre
  olasılıklarındandır (aynı günün PIREP'leri aynı katta). Yayındaki model tüm
  veriyle eğitildiği için ayrı bir kalibrasyon kümesi kalmaz; çapraz-konformal
  bu yüzden seçildi.
- Aynı yöntem yalnızca eğitim günleriyle tekrarlanıp zamansal holdout'ta
  gerçekleşen kapsama ölçülür ve sürüm kaydına yazılır
  (`konformal.holdout_dogrulamasi`).
- `ml_riski_var_mi` eşiği `ML_KARAR_ESIGI` ile yapılandırılabilir (risk iştahı).

## Sonuçlar

- API ve 3B harita "belirsiz" durumunu ayrı gösterir; kapsama her eğitimde ölçülür.
- Güvence değiştirilebilirlik varsayımına dayanır; mevsimsel kayma bunu bozabilir.
  Bu nedenle kapsama zamansal holdout'ta (en son günler) raporlanır ve her
  gece yeniden hesaplanır.
- Kat dışı skorlarla kurulan eşik, ayrı bir kalibrasyon kümesi kullanan bölünmüş
  konformal kadar sıkı bir garanti vermez (CV+ türü yöntemlerde kuramsal alt sınır
  1−2α'dır). Bu yüzden belirleyici olan, holdout'ta ölçülen gerçek kapsamadır.
- Eski (konformal eşiksiz) model sürümleri için alan `null` döner; uydurma durum üretilmez.
- Meteorolojik belirsizlik (ensemble yayılımı) tahmin modu (geliştirme planı M3) gelince eklenecek.

## Değerlendirilen alternatifler

- Bootstrap ile olasılık aralığı: kapsama güvencesi yok; reddedildi.
- Sınıf koşullu (Mondrian) konformal: sınıflar yaklaşık dengeli (~%50) olduğu
  için şimdilik gerekmedi; dengesiz nesnel EDR etiketlerine (M1) geçilince değerlendirilecek.
