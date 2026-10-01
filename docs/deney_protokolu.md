# Deney Protokolü — ML Türbülans Risk Modeli

Bu protokol, ML sonuçlarının nasıl üretildiğini, hangi referansla kıyaslandığını
ve nasıl raporlandığını sabitler. Kodun kendisi protokolü uygular; aşağıdaki her
madde ilgili koda bağlıdır. Sonuçlar sertifikalı EDR değildir; sistem karar
destek aracıdır.

## 1. Soru

Saatlik ERA5'ten çıkarılan fiziksel özelliklerle eğitilen model, seyir
irtifasında orta ve üstü türbülansı **tek başına TI1'den** daha iyi ayırt eder mi?

## 2. Veri

| Öğe | Tanım | Kod |
|---|---|---|
| Örnek | IEM PIREP, 28.000–42.000 ft (IEM `FL` sütunu feet'tir), türbülans alanı dolu | `ml/ml_veri_hatti.py` |
| Örnekleme | Gün başına en fazla 100 PIREP, sabit tohumla (0) rastgele | `seyir_pireplerini_sec` |
| Etiket | 1 = orta ve üstü (LGT-MOD dahil), 0 = yok/hafif | `dogrulama/bagimsiz_kanit.pirep_siddet_sinifi` |
| Özellik | TI1, Richardson, rüzgar hızı, basınç (300/250/200 hPa ERA5'ten, analizle aynı kod) | `ml/turbulans_ml_modeli.ozellikleri_cikar` |
| Kapsam | Yalnızca ABD hava sahası (PIREP kaynağı) | — |

Veri yeterliliği: en az `ML_MIN_GUN` = 60 farklı gün ve `ML_MIN_ORNEK` = 300 örnek
olmadan model eğitilmez ve model sonucu raporlanmaz (`otomatik_egitim_calistir`).
Durum: `GET /api/v1/ml/durum` → `eslesmis_gun_sayisi`, `egitime_hazir`.

## 3. Bölme

1. **Zamansal holdout:** en son `ML_HOLDOUT_ORANI` = %20 gün tamamen ayrılır;
   model seçimi ve kalibrasyon bu günleri görmez (`zamansal_holdout`).
2. **Model seçimi:** kalan günlerde gün gruplu, sınıf oranı korunan 5 katlı çapraz
   doğrulama (`StratifiedGroupKFold`), 3 tekrar, tekrar tohumları 0, 1, 2. Aday
   modeller: lojistik regresyon, rastgele orman, gradient boosting (model tohumu 42).
3. **Olasılık kalibrasyonu:** sigmoid (Platt), aynı gün gruplu bölmelerle.

Aynı gündeki PIREP'ler aynı hava sistemini gördüğü için rastgele bölme yapılmaz
(bkz. [ADR 0003](adr/0003-gun-bazli-gruplu-dogrulama.md)).

## 4. Referanslar

| Referans | Kullanım |
|---|---|
| Tek başına TI1 | Sürekli skor olarak ROC-AUC; `TI1_ESIK_ORTA_SIDDETLI` (8e-7 s⁻²) eşiğinde POD/POFD |
| İklimsel (sabit oran) | Brier becerisi = 1 − Brier / [p(1−p)] |
| Aktif model | Champion/challenger: F1 ve recall |
| WAFS | Planlandı (geliştirme planı M3); şu an yok |

## 5. Metrikler ve belirsizlik

- Ayırt etme: ROC-AUC. Eşikte: POD, POFD, FAR, CSI, Peirce. Olasılık: Brier,
  Brier becerisi, güvenilirlik tablosu (`ml/degerlendirme.py`).
- **Güven aralığı:** gün bazlı blok bootstrap (günler iadeli örneklenir, gün
  içindeki tüm PIREP'ler birlikte gelir), `ML_BOOTSTRAP_TEKRAR` = 1000 tekrar,
  %95 yüzdelik aralık. Tek sınıflı tekrarlar (AUC tanımsız) atılır, geçerli tekrar
  sayısı raporlanır.
- **Anlamlılık:** model ile TI1'in ROC-AUC farkı aynı bootstrap örnekleriyle
  (eşleştirilmiş) hesaplanır; iki yönlü p = 2 · min(P(fark ≤ 0), P(fark ≥ 0)).
  p < 0,05 ise fark anlamlı sayılır. Gün bloklu bootstrap, PIREP'lerin gün içi
  bağımlılığını hesaba kattığı için DeLong testine (bağımsızlık varsayar) tercih edildi.

## 6. Karar kuralı (model aktivasyonu)

[ADR 0004](adr/0004-champion-challenger-ti1-kapisi.md): holdout yeterli olmalı
(≥50 örnek, her sınıftan ≥5), aday ROC-AUC'si TI1'i en az 0,02 geçmeli ve aktif
model varsa F1'de ≥0,01 iyileşip recall'ı en fazla 0,02 düşürmelidir. Güven
aralıkları ve p değeri kararla birlikte sürüm kaydına yazılır; kapı şimdilik
nokta tahminine dayanır (60 günlük holdout'ta ~12 gün ile anlamlılık şartı modeli
pratikte hiç aktifleştirmeyebilir; veri büyüdükçe yeniden değerlendirilecek).

## 7. Raporlama şablonu

Her sonuç tablosu şu sütunları içerir:

| Metrik | Model [%95 GA] | TI1 [%95 GA] | Fark [%95 GA] | p | Gün / örnek |
|---|---|---|---|---|---|
| ROC-AUC | … | … | … | … | … |
| Brier | … | — | — | — | … |

Kaynak: sürüm kaydındaki `holdout.guven_araliklari` (`turbulans-ml --listele`,
`model_versiyonlari/manifest.json`) ya da `turbulans-ml-degerlendirme` çıktısındaki
`guven_araliklari`. Not: `turbulans-ml-degerlendirme` aktif modeli tüm eşleşmiş
veride ölçer; model bu verinin bir kısmıyla eğitildiği için yalnızca holdout
skorları genelleme kanıtıdır.

## 8. Tekrar üretim

```bash
# Veri (gece işi; CDS kotası korumalı)
curl -X POST -H "X-API-Key: $API_ANAHTARI" http://localhost:8000/api/v1/ml/gece-isi
# Eğitim + holdout raporu (güven aralıkları dahil)
turbulans-ml
# Tüm eşleşmiş veride aktif model ve TI1
turbulans-ml-degerlendirme
# Depodaki ERA5 pencerelerinden özelliklerin aynı çıktığının kontrolü
turbulans-ml-depo --dogrula 200
```

Tohumlar ve eşikler `config.py`'dedir; ortam değişkeniyle değiştirilen her değer
sürüm kaydında değil `.env`'de durur, bu yüzden raporla birlikte kullanılan `.env`
farkı belirtilmelidir.

## 9. Geçerlilik tehditleri

- **Etiket yanlılığı:** PIREP gönüllüdür; pilotlar türbülansı raporlar, sakin
  havayı nadiren. Veride pozitif oranı (~%50) gerçek sıklık değildir; kalibre
  olasılık "raporlanan PIREP'ler içindeki oran"dır, sahadaki alarm oranı değildir.
  Nesnel EDR etiketi (MADIS in-situ, QAR) geliştirme planında M1'dir.
- **Coğrafya:** yalnızca ABD verisi. Türkiye/Avrupa'ya genelleme iddia edilmez;
  bölgesel doğrulama seti olmadan bu bölgeler için skor raporlanmaz.
- **Reanaliz:** ERA5 ~5 gün gecikmelidir ve "geçmişi bilerek" üretilmiştir; tahmin
  verisiyle (GFS/IFS) skorlar düşük olacaktır (planda M3).
- **Düşey çözünürlük:** 3 seviye (~1,3–1,6 km aralık) ince katman kaymasını
  kaçırır; Richardson hiç 0,25'in altına inmez. 7 seviyelik veri pencere deposunda
  birikmektedir ([ADR 0002](adr/0002-era5-pencere-deposu.md)).
