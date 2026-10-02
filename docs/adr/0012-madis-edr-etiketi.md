# 0012 — MADIS herkese açık uçak EDR ölçümleri: nesnel türbülans etiketi

- Durum: Kabul edildi (2026-10-02)
- İlgili kod: `veri/madis_edr.py`, `ml/edr_eslestirme.py`, `ml/madis_hatti.py`, `edr_ornekleri` tablosu

## Bağlam

ML etiketi pilot raporuydu (PIREP): gönüllü, öznel, gecikmeli ve türbülanslı
durumlara yanlı. Geliştirme planı M1 nesnel etiket (uçağın kendi ölçtüğü EDR)
istiyordu. NOAA MADIS kısıtlı veri başvurumuz reddedildi (yalnızca public erişim).
Public ACARS arşivi incelendi: saatlik dosyalarda `maxEDR`/`medEDR` var
(2019-01-15 18Z: 41.120 kaydın 7.492'sinde EDR, FL280+ 5.425).

## Karar

- Public arşivden (HTTPS) yalnızca ERA5 penceresi olan PIREP günleri indirilir;
  gece başına en fazla 1 gün (24 dosya), dosyalar arası 5 sn, günde ≤ 48 dosya.
  Ham dosya işlenip silinir; yalnızca seyir irtifasındaki EDR günlük Parquet'te tutulur.
- EDR gözlemleri mevcut ERA5 pencere deposuyla eşleştirilir: CDS'e yeni istek
  gitmez. Pencere içine düşen her gözlem için aynı özellik kodu çalışır.
- Şiddet sınıfları ICAO Annex 3 §2.6 tepe EDR (A41-WP/235): hafif 0,1–0,4,
  orta 0,4–0,7, şiddetli > 0,7 (ayarlanabilir).
- QC: public verinin tanımlayıcısı 'Z' (ön veri, QC yapılmamış; NWS Codes Registry).
  Makullük filtresi (0 ≤ EDR ≤ 1,5) uygulanır, 'X' (reddedilmiş) atılır.

## Sonuçlar

- İlk gün (2019-06-12): 88.546 seyir EDR gözlemi, 54 pencerede 2.818 eşleşme;
  sınıflar 2.792 yok / 26 hafif / 0 orta. Nesnel etiket çok dengesizdir.
- PIREP-EDR karşılaştırması yapılabilir hale geldi (100 PIREP'in 14'ünün
  çevresinde EDR; türbülans yok diyen 6/6 PIREP'te EDR 0, türbülans bildiren
  8'in 2'sinde hafif EDR). Tek gün; genelleme yapılmaz.
- Public sürümün kısıtlı sürüme göre eksik olup olmadığı bilinmiyor; MADIS'e
  soruldu (kullanıcı e-postası, 2026-10-02).
- Veri yeniden dağıtılmaz; depoya ve demoya konmaz.

## Değerlendirilen alternatifler

- Kısıtlı MADIS erişimi: reddedildi; danışman üzerinden yeniden başvuru açık seçenek.
- NCAR in-situ EDR programı, WMO AMDAR: araştırma anlaşması gerektirdiği düşünülüyor (doğrulanmadı).
- EDR için ayrı ERA5 indirmesi: CDS kotasını PIREP hattıyla paylaşır; pencere deposu yeterli.
