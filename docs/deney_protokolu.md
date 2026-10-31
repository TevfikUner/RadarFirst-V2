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

1. **Altın test günleri:** 2026-10-07'de eşleşmiş 80 günden rastgele 16'sı
   (%20, `numpy.random.default_rng(0)`) seçilip `ml/altin_test_gunleri.json`
   dosyasına donduruldu (`turbulans-ml --altin-gunleri-dondur`; dosya varsa
   üzerine yazmaz). Bu günler hiçbir sürümün model seçimine, kalibrasyonuna ya da
   nihai eğitimine girmez; her sürümün eğitim gün listesi kayda yazılır
   (`egitim_gunleri`). Dosya yoksa en son %20 gün (zamansal holdout) kullanılır.
   Rastgele seçim, 2018–2020'ye dağınık günlerde testin tek mevsime (yalnız
   2020 baharı) yığılmasını önler.
2. **Model seçimi:** eğitim günlerinde gün gruplu, sınıf oranı korunan 5 katlı
   çapraz doğrulama (`StratifiedGroupKFold`), 3 tekrar, tekrar tohumları 0, 1, 2.
   Aday modeller: lojistik regresyon, rastgele orman, gradient boosting (sınıf
   dengeli ağırlık; model tohumu 42). Ölçüt CV ROC-AUC; en iyi modelle lojistik
   regresyonun farkı en iyi modelin kat ROC-AUC standart hatasından küçükse
   lojistik regresyon seçilir (1-SE kuralı).
3. **Olasılık kalibrasyonu:** sigmoid (Platt), aynı gün gruplu bölmelerle.
4. **Eşikler:** model ve TI1 için eğitim günlerinde Peirce'ı (POD − POFD)
   maksimize eden eşik seçilir (model için kat dışı kalibre olasılıklar) ve
   test günlerine olduğu gibi uygulanır.

Aynı gündeki PIREP'ler aynı hava sistemini gördüğü için rastgele bölme yapılmaz
(bkz. [ADR 0003](adr/0003-gun-bazli-gruplu-dogrulama.md)).

## 4. Referanslar

| Referans | Kullanım |
|---|---|
| Tek başına TI1 | Sürekli skor olarak ROC-AUC; eğitim günlerindeki Peirce eşiğinde POD/POFD |
| Kalibre TI1 | Tek değişkenli lojistik (log10 TI1), eğitim günlerinde; Brier referansı |
| İklimsel (sabit oran) | Brier becerisi = 1 − Brier / [p(1−p)] |
| Aktif model | Champion/challenger: eşleştirilmiş ROC-AUC farkı |
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

[ADR 0004](adr/0004-champion-challenger-ti1-kapisi.md): test kümesi yeterli
olmalı (≥50 örnek, her sınıftan ≥5). Aday − TI1 ROC-AUC farkı ≥ 0,02 **ve** gün
bazlı eşleştirilmiş bootstrap %95 GA alt sınırı > 0 olmalı; aktif model varsa
ona karşı da aynı kural uygulanır. Altın günleri eğitiminde görmüş aktif model
karşılaştırmada yok sayılır. 0,02 parametriktir, kalibre edilmedi.

**Veri dondurma:** 18 Ekim 2026'daki `ml_ornekleri` ile bir kez eğitim ve
değerlendirme yapılır (`turbulans-ml --dondurma-raporu docs/sonuclar/2026-10-18`).
Sonuç ne çıkarsa raporlanır; "model TI1'i geçemedi" de geçerli bir bulgudur.

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
  bölgesel doğrulama seti olmadan bu bölgeler için skor raporlanmaz. Yerel MADIS
  deposunda Avrupa'da FL280 üstü 21.167 EDR gözlemi var ama yalnızca 28'i hafif+;
  Türkiye/Doğu Akdeniz'de 0 (11 gün, 13 Eki 2026 sayımı). Bu bir doğrulama seti sayılmaz.
- **Reanaliz:** ERA5 ~5 gün gecikmelidir ve "geçmişi bilerek" üretilmiştir; tahmin
  verisiyle (GFS/IFS) skorlar düşük olacaktır (planda M3).
- **Düşey çözünürlük:** 3 seviye (~1,3–1,6 km aralık) ince katman kaymasını
  kaçırır; Richardson hiç 0,25'in altına inmez. 7 seviyelik veri pencere deposunda
  birikmektedir ([ADR 0002](adr/0002-era5-pencere-deposu.md)).

## 10. Dondurma sonrası protokol (F9 devamı; 19 Ekim 2026, yeni günlere bakılmadan yazıldı)

Bu bölüm, 18 Ekim nihai paketinden (`docs/sonuclar/2026-10-18`) sonraki ilk ML
değerlendirmesini önceden sabitler. Kayıt zamanı bu bölümü ekleyen commit'tir. Yazıldığı
anda geliştirme veritabanında dondurmada olmayan 16 eşleşmiş gün vardı; yalnız sayıldı,
hiçbir skoru hesaplanmadı. Bu bölüm değerlendirmeden sonra değiştirilmez; değişiklik
gerekirse ayrı alt madde olarak, tarihiyle ve "sonuçtan sonra" notuyla eklenir.

### 10.1 Test ve eğitim günleri

- **Dondurma günleri:** `ml/dondurma_gunleri.json`, 163 gün (dondurma yedeğinin geri
  yüklendiği `Turbulence-db-dondurma` veritabanından, `durum='eslesti'`, UTC günü). Dosya
  üzerine yazılmaz.
- **Test günleri:** eşleşmiş olup bu listede olmayan günler. `olusturulma_zamani` kesmesi
  kullanılmaz: satırlar dondurmadan önce oluşturulup sonra eşleşebiliyor.
- **Eğitim:** dondurma günlerinin tamamı (16 altın gün dahil; bu protokolde test değiller).
- **Ne zaman:** test günleri ilk kez **≥ 30 gün** ve ADR 0004 yeterliliğini (≥ 50 örnek,
  her sınıftan ≥ 5) sağladığında **bir kez**. Ara bakış yok; "biraz daha gün bekleyelim"
  kararı skora bakılarak verilmez.
- **Kod:** `turbulans-ml-yeni-gun` (`ml/yeni_gun_degerlendirmesi.py`), test günlerine bakılmadan
  commit'lendi. `--durum` yalnız gün/örnek sayısını verir; `--cikti <klasör>` koşul sağlanmadan skor
  hesaplamaz ve `yeni_gun_degerlendirmesi.json` varsa üzerine yazmaz.

### 10.2 Birincil hipotez (H1)

Geniş özellik setiyle eğitilen protokol modeli, test günlerinde temel setle eğitilen protokol
modelinden daha yüksek ROC-AUC verir.

| Öğe | Tanım |
|---|---|
| Temel set (8) | `MODEL_OZELLIK_SUTUNLARI`: TI1, Ri, rüzgâr hızı, basınç, düşey kayma, yatay deformasyon, yatay diverjans, TI2 |
| Geniş set (13) | Temel 8 + `rf_deneyi.BAGLAM_SUTUNLARI`: komşu TI1 maks/ort, kolon en düşük Ri, jet oranı, sıcaklık azalma oranı |
| Aday modeller | §3'tekilerle aynı: lojistik (dengeli), RF (200 ağaç, derinlik 5), GB (150, derinlik 3); ayarlı RF aday değil (F9: kazanç +0,001–0,003) |
| Seçim | §3 madde 2–4 aynen (gün gruplu CV, 1-SE, Platt, Peirce eşiği eğitim günlerinde); her set için ayrı |
| Ölçüt | Geniş − temel ROC-AUC, gün bloklu eşleştirilmiş bootstrap (§5); %95 GA alt sınırı > 0 ise H1 desteklenir |

Sonuç ne çıkarsa raporlanır; "geniş set fark yaratmadı" da bulgudur.

### 10.3 İkincil analizler (önceden kayıtlı; birincil sonucu değiştirmez)

1. **TI1'e karşı:** iki modelin TI1 ile farkı, ADR 0004 kapısıyla (≥ 0,02 ve GA alt > 0).
   Geniş set kapıyı geçse bile üretime alınması ayrı karardır (gece işinin bağlam
   özelliklerini üretmesi gerekir; ONAY).
2. **Tabakalı doğrulama (Fikir 4):** mevsim (DJF/MAM/JJA/SON) ve örnek noktasındaki rüzgâr
   hızı (< 30 / ≥ 30 m/s). Tabaka başına gün, örnek, model ve TI1 ROC-AUC [%95 GA]. Örnek
   < 50 ya da bir sınıfı < 5 olan tabaka raporlanmaz. Çoklu karşılaştırma düzeltmesi
   yapılmaz; yalnız GA ile, "keşifsel" etiketiyle yorumlanır.
3. **"Hafif = negatif" duyarlılığı (Fikir 8):** yerel IEM arşivindeki TURBULENCE metniyle
   sınıfı 0 olan örnekler "hafif" (`LGT`, `LIGHT` geçer) ve "yok" diye ayrılır. Hafifler
   çıkarılınca, aynı modellerle (yeniden eğitmeden) ve aynı eşiklerle ROC-AUC ve Peirce
   yeniden hesaplanır. Yalnız metni bulunan örnekler kullanılır; aynı alt kümede birincil
   sayılar da yan yana verilir.
4. **Ardışık gün sızıntısı:** dondurma gününe ±1 gün komşu test günleri çıkarılarak H1
   farkı yeniden verilir (aynı hava sistemi iki güne yayılabilir).

### 10.4 Keşifsel (hipotez değil)

Fikir 9 (uyarı alanı oranı; TTS yalnız MADIS günlerinde), 10 (komşuluk maksimumu), 15 (TI3),
19 (frontogenez, ∇T, NCSU1, PV), 24 (AUC² ağırlıklı birleşik EDR) ve 29 (uçak tipi) bu
protokolün test günlerinde **ancak** her biri hipotez, metrik ve karar ölçütüyle bu bölüme
test günlerine bakılmadan eklenirse çalıştırılır. Sonradan eklenenler yalnız "keşifsel"
olarak raporlanır.

### 10.5 Geçerlilik tehditleri

- Yeni günler de 2018–2020 ABD PIREP'idir: zaman olarak yeni değil, yalnız modelin
  görmediği günlerdir. Bu, dağılım kaymasını değil aynı dağılımda genellemeyi ölçer.
- Hangi günlerin eşleşeceğini gece işinin sırası belirler (rastgele örnek değil); test
  günlerinin tarih ve mevsim dağılımı raporda verilir.
- Bağlam özellikleri `rf_deneyi.baglam_ozelliklerini_hesapla` ile ERA5 pencere
  deposundan sonradan hesaplanır; penceresi olmayan örnekler iki setten de çıkarılır ki
  iki model aynı örneklerde karşılaştırılsın.

### 10.6 Sonradan eklenen ikincil karşılaştırma: model − birleşik EDR (28 Ekim 2026, §10 sonucundan sonra)

**Not:** Bu alt madde §10 değerlendirmesi (27 Ekim) yapılıp sonuçları görüldükten sonra, kurul
incelemesinin VER-04 bulgusu üzerine eklendi; ön kayıtlı değildir ve yalnız "sonradan eklenen
ikincil" olarak raporlanır. Birleşik EDR'nin bu test günlerindeki skoru eklenme anında
hesaplanmamıştı; TI1 ve modellerin skorları biliniyordu.

- **Soru:** Protokol modeli, eğitimsiz fizik birleşimi olan birleşik EDR'yi (`fizik/edr_esleme.py`,
  sabit katsayılar) geçiyor mu?
- **Veri:** §10 ile aynı: eğitim `ml/dondurma_gunleri.json` (163 gün), test
  `docs/sonuclar/2026-10-27_yeni_gun/yeni_gun_degerlendirmesi.json`'daki sabit 79 günlük liste
  (o tarihten sonra eşleşen günler girmez). Altın test günleri ayrıca kullanılmaz.
- **Modeller:** §10.2 ile aynı temel ve geniş set protokol modelleri, aynı seçim kuralıyla yeniden
  eğitilir; yeniden üretilen temel set ROC-AUC'si §10 değeriyle (0,685) yan yana verilir.
- **Ölçüt:** temel − birleşik EDR ROC-AUC farkı, gün bloklu eşleştirilmiş bootstrap (§5). %95 GA alt
  sınırı > 0 ise "model birleşik EDR'yi geçiyor" denir; değilse "geçtiği gösterilemedi". Geniş − birleşik
  EDR ve birleşik EDR − TI1 de verilir. Birleşik EDR'si hesaplanamayan örnekler tüm skorlardan çıkarılır.
- **Çıktı:** `birlesik_kiyasi.json`, bir kez; dosya varsa üzerine yazılmaz. Sonuç ne çıkarsa raporlanır.

### 10.7 Keşifsel: bölme ve etiket tanımının ROC-AUC'ye etkisi (28 Ekim 2026, skor hesaplanmadan yazıldı)

**Not:** Kurul incelemesinin #7 maddesi üzerine eklendi; hipotez değil, metodolojik gösterimdir.
Ön kayıtlı birincil sonucu (§10.2) ya da model aktivasyonunu değiştirmez. Literatürdeki 0,86–0,90
değerleriyle (ILGILI_CALISMALAR §9) farkın ne kadarının bölme ve etiket tanımından geldiğini ölçer.

- **Veri:** Yalnız 147 eğitim günü: `ml/dondurma_gunleri.json` (163 gün) eksi
  `ml/altin_test_gunleri.json` (16 gün). §10 test günleri ve altın günler kullanılmaz.
- **Model:** sabit Random Forest (`rf_deneyi.TEMEL_RF`: 200 ağaç, derinlik 5, `class_weight="balanced"`),
  temel 8 özellik; hiperparametre araması yok (koşullar arasında yalnız bölme ve etiket değişir).
  Referans olarak TI1 (eğitimsiz) aynı test parçalarında puanlanır.
- **Koşullar (2 × 2):** bölme ∈ {gün gruplu 70/30 (günlerin %30'u test), rastgele örnek 70/30
  (katmanlı)} × etiket ∈ {mevcut (hafif = negatif), hafif negatifler çıkarılmış (yalnız NEG ve orta-üstü)}.
  Hafif tanımı §10.3 ile aynı (`hafif_mi`, IEM arşiv metni); metni bulunamayan örnekler yalnız
  "hafif çıkarılmış" koşullarından düşer.
- **Tekrar:** her koşulda 20 bölme (tohum 0–19); her bölmede RF ve TI1 test ROC-AUC'si. Rapor:
  ortalama ve 2,5–97,5 yüzdelik aralığı; RF − TI1 farkı da aynı biçimde.
- **Okuma:** "rastgele − gün gruplu" farkı bölmenin şişirmesini, "hafif çıkarılmış − mevcut" farkı
  etiket tanımının etkisini gösterir. Literatür değerleriyle aynı eksende "daha iyi / daha kötü"
  yorumu yapılmaz (veri, bölge ve özellikler farklı).
- **Çıktı:** `docs/sonuclar/2026-10-28_protokol_farki/protokol_farki.json` + README; bir kez, üzerine
  yazılmaz. Sonuç ne çıkarsa raporlanır.
- **Sonradan ek (28 Ekim 2026, §10.7 sonucu görüldükten sonra):** sabit RF'nin derinliği 5 olduğu için
  aynı günün örneklerini ezberleme kapasitesi düşüktür; literatürdeki modeller (XGBoost, KNN) daha
  esnektir. Aynı 2 × 2 tasarım, aynı 20 bölmeyle bir kez de derin RF'yle (`max_depth=None`,
  `min_samples_leaf=1`) çalıştırılır; çıktı `docs/sonuclar/2026-10-28_protokol_farki/derin/`. Ön kayıtlı
  değildir, "sonradan eklenen keşifsel" diye raporlanır.

## 11. Bağımsız rota backtest'i (kurul #3; 29 Ekim 2026, tüp sayımı yapılmadan yazıldı)

**Soru:** A* rotası (TI1 yumuşak kısıtıyla), aynı uçuşun büyük daire rotasına göre, rota tüpündeki
PIREP'ler içinde daha düşük bir orta-üstü oranına mı maruz kalıyor? TI1 ile optimize edilen rotayı
TI1 ile ölçmek döngüseldir; burada ölçüt, ne TI1'in ne A*'ın gördüğü pilot raporlarıdır.

**Yazılmadan önce görülenler:** küplerin kapsamı ve günleri; kutudaki seyir PIREP'lerinin toplam
sayısı (48 günde 1.015; orta-üstü 674; net NEG 96); 6 deneme rotasının TI1 çıktısı (tüp sayımı yok).

- **Hava verisi:** `era5_egitim_verisi/` NE-ABD küpleri (40–50°K, 80–70°B; 300/250/200 hPa; 3 sa),
  48 gün. Yalnız `ruzgar_verisi_kaynagi = era5_gercek` dönen ve iki rotada da TI1 riski hesaplanan
  senaryolar girer. Ağ, canlı veri ve otomatik indirme kapalı.
- **Senaryolar (sabit, sonuca bakılmadan):** 8 şehir çifti (JFK→YUL, BOS→YYZ, EWR→YQB, YYZ→BDL,
  SYR→BOS, YOW→JFK, ROC→YQB, BUF→BOS) × küpte bulunan her gün × kalkış 12, 15, 18 UTC × FL340 ve
  FL370; A320, koridor modu, varsayılan seçim kuralı (`sozluksel`, ADR 0013), TI1 eşiği 7e-7.
  SIGMET ve kısıtlı saha verilmez (yalnız TI1 etkisi ölçülür).
- **Bağımsız kanıt:** yerel IEM arşivi (`pirep_ham/`), seyir irtifası, `/OV UNK` hariç, yinelenenler
  atılır. Tüp `bagimsiz_kanit.tupteki_pirepler` ile aynı: rota noktasına 50 km, ±2000 ft (noktanın
  kendi irtifası; A* irtifa değiştirirse yeni irtifa), ±1 sa. Etiket ML etiketiyle aynıdır:
  orta-üstü (M) = `pirep_siddet_sinifi ≥ 1` (LGT-MOD dahil), kontrol (N) = 0 (NEG ve hafif).
- **Bağımsızlık:** 48 günün 7'si `ml/dondurma_gunleri.json`'da (TI1 eşiği ve model bu günlerin
  PIREP'lerini gördü). **Birincil sonuç bu 7 gün çıkarılmış 41 günde** verilir.
- **Birincil ölçüt:** A*'ın büyük daireden ayrıldığı (`kacinma_stratejisi ≠ yok`) senaryolarda
  göreli maruziyet oranı GMO = (ΣM_A* / ΣN_A*) / (ΣM_BD / ΣN_BD). GMO < 1: A* tüpündeki raporlar
  arasında orta-üstü payı daha düşük. Belirsizlik: kalkış gününe göre bloklu bootstrap
  (2.000 tekrar, tohum 0, %95 yüzdelik aralık).
- **Karar okuması:** üst sınır < 1 ise "bağımsız kanıt A*'ın orta-üstü maruziyetini azalttığını
  destekliyor"; alt sınır > 1 ise "artırdı"; aralık 1'i içeriyorsa "fark gösterilemedi". ΣM ya da ΣN
  herhangi bir rotada 0 kalırsa ya da sapmalı rotalarda toplam tüp raporu 30'dan azsa sonuç
  "yetersiz örneklem" diye raporlanır. Sonuç ne çıkarsa raporlanır; senaryolar, tüp ve eşik
  değiştirilmez.
- **İkincil (önceden kayıtlı, birincil okumayı değiştirmez):** (a) 48 günün tamamı; (b) tüm
  senaryolar (sapmasızlar dahil; iki rota aynı olduğu için GMO'yu 1'e çeker); (c) net etiket
  (`duyarlilik_analizi.net_etiket`: LGT içermeyen orta-üstü / LGT içermeyen NEG-SMOOTH); (d) fark
  tüpü: yalnız büyük daire tüpündeki ("kaçınılan") ve yalnız A* tüpündeki ("girilen") raporlarda
  orta-üstü payı; (e) FL ve kaçınma stratejisine (yanal / irtifa) göre kırılım; (f) döngüsel
  referans: aynı rotalarda TI1 riskli nokta sayısı.
- **Geçerlilik tehditleri:** PIREP'ler trafiğin olduğu yerde ve çoğunlukla türbülans görülünce
  verilir (orta-üstü payı yüksek, %66); oran ölçütü yoğunluk farkını kısmen giderir ama raporlama
  yanlılığını gidermez. Tüpler aynı günün raporlarını paylaşır (bu yüzden gün bloklu GA). A* tüpü
  büyük daire tüpüyle büyük ölçüde örtüşür; etki seyreltilir. Tek bölge, 48 gün, 3 seviyeli küp.
  ERA5 uçak rüzgâr/sıcaklık gözlemlerini özümser, türbülans raporlarını özümsemez.
- **Çıktı:** `docs/sonuclar/2026-10-29_bagimsiz_backtest/` (`bagimsiz_backtest.json` + README);
  bir kez çalıştırılır, üzerine yazılmaz. Zaman kutusu 2 gün; bitmezse SISTEM_KARTI'ndaki
  "gerçek uçuş izleriyle karşılaştırır" iddiası "doğrulama hattı gösterimi" diye yazılır.

## 12. Birleşik EDR rota eşiği ve uyarı oranının ikinci sütunu (kurul #4 kalanı; 29 Ekim 2026, eşik hesaplanmadan yazıldı)

**Amaç:** Uyarı oranını (28 Ekim, `2026-10-28_uyari_orani`) TI1 7e-7'nin yanında birleşik EDR eşiğiyle de
vermek. Birleşik EDR'nin rota eşiği yoktu; eşik önce aşağıdaki kuralla seçilir, sonra uyarı oranına uygulanır.
Rota sapma kararı TI1'le kalır (birleşik EDR'nin rota cezasına girmesi A2/VER-09, sunum sonrası).

- **Eşik verisi:** dondurma veritabanı (`Turbulence-db-dondurma`, nihai paketin kaynağı), `ml_ornekleri`
  `eslesti`; eğitim günleri = `ml/dondurma_gunleri.json` eksi `ml/altin_test_gunleri.json` (147 gün; TI1
  eşiğinin seçildiği günler). Skor: `edr_esleme.birlesik_edr` (mevcut `edr_esleme_katsayilari.json`).
- **Eşik kuralı (TI1 7e-7 ile aynı):** `degerlendirme.bir_se_esigi`: Peirce'i en yüksek eşiğin gün bazlı
  bootstrap SE'si içindeki en yüksek eşik (`ML_BOOTSTRAP_TEKRAR`, tohum 0). Peirce-maks eşiği de raporlanır.
  **Kontrol:** aynı çerçevede aynı kural TI1 için nihai paketteki 7,39e-7'yi vermeli; vermezse fark yazılır.
- **Bilgi amaçlı:** altın test günlerinde seçilen eşiğin POD, POFD, Peirce'i TI1 7e-7'nin yanında. Karar yok.
- **Uyarı oranı:** 28 Ekim senaryoları aynen (Türkiye Ocak 2019 küpü, 6 çift × 31 gün × 00/06/12/18 UTC ×
  FL350/370, A320, `sozluksel`). Yeni sütunlar: büyük daire rotasında birleşik EDR ≥ eşik noktası olan rota
  oranı; iki göstergenin uyuşması (ikisi de / yalnız TI1 / yalnız birleşik / hiçbiri); TI1 sapmasından sonra
  A* rotasında birleşik riskli nokta kalan rota oranı. **Kontrol:** TI1 sütunları 28 Ekim sonucuyla aynı çıkmalı.
- **Geçerlilik tehditleri:** katsayılar ve eşik ABD ERA5 verisinden; Türkiye'de beceri ölçülmedi (VER-08).
  Birleşik EDR TI1'i de içerir, iki sütun bağımsız değildir.
- **Çıktı:** `docs/sonuclar/2026-10-29_birlesik_esik/` ve `docs/sonuclar/2026-10-29_uyari_orani_birlesik/`;
  bir kez, üzerine yazılmaz. Sonuç ne çıkarsa raporlanır.

## 13. Keşifsel göstergeler: Fikir 9, 10, 11 devamı, 15, 19, 24 (31 Ekim 2026, skorlar hesaplanmadan yazıldı)

**Not:** §10.4'ün istediği ön kayıt. Yazıldığı anda §10 test günlerinde TI1, temel ve geniş set skorları
biliniyordu (`2026-10-27_yeni_gun/`); aşağıdaki yeni skorların hiçbiri hesaplanmamıştı. Hepsi
**keşifsel**dir: birincil sonucu (§10.2), model aktivasyonunu ve rota kararını değiştirmez; üretime alınması
ayrı karardır (ONAY). Çoklu karşılaştırma düzeltmesi yapılmaz, yalnız GA ile okunur. Sonuç ne çıkarsa raporlanır.

**Ortak (13.1–13.4, örnek düzeyi):** eğitim `ml/dondurma_gunleri.json` (163 gün), test §10'un sabit 79 günlük
listesi (`2026-10-27_yeni_gun/yeni_gun_degerlendirmesi.json`, `veri.test_gunleri`). Örnekler §10 ile aynı
(`_veriyi_hazirla`, geniş set tam). Bir göstergesi hesaplanamayan örnek yalnız o karşılaştırmadan düşer, sayısı
yazılır. Fark: ROC-AUC(a) − ROC-AUC(b), gün bloklu eşleştirilmiş bootstrap (`eslestirilmis_auc_farki`,
`ML_BOOTSTRAP_TEKRAR`, tohum 0). Okuma: GA alt > 0 "a daha iyi ayırıyor", üst < 0 "daha kötü", aksi
"fark gösterilemedi". Eşik gereken yerde Peirce-maks eşiği eğitim günlerinde seçilir (`peirce_esigi`), test
günlerine aynen uygulanır. Çıktı `docs/sonuclar/2026-10-31_kesifsel_gostergeler/kesifsel_gostergeler.json`
+ README; bir kez, dosya varsa üzerine yazılmaz. Kod `turbulans-kesifsel-gostergeler`.

### 13.1 Fikir 10: komşuluk maksimumu eşleştirmesi

- **Skorlar:** (A) `ti1_komsu_maks` (mevcut bağlam özelliği: ±1 hücre 0,25°, ±1 seviye, ±1 sa; 81 nokta);
  (B) yalnız yatay: aynı saat ve katmanda ±1 hücre (9 nokta) TI1 en büyüğü. İki sınıfa birlikte uygulanır.
- **Ölçüt:** A − TI1 ve B − TI1 ROC-AUC farkı. Eşikte: her skorun eğitim Peirce-maks eşiğinde test POD,
  POFD, Peirce; TI1 7e-7 kural eşiğinde de TI1 ve A için POD/POFD (pencerenin iki sınıfı birlikte büyüttüğünü
  göstermek için).
- **Okuma:** A ya da B'nin GA alt > 0 olması, nokta eşleştirmenin konum/zaman hatası yüzünden ayırma
  kaybettiğine işaret eder; `fizik/eslestirme.py`'ye mod eklemek ayrı karardır.

### 13.2 Fikir 11 devamı: çoklu /TB grubu etiketi

- **Etiket:** yerel IEM arşivinin ham `REPORT` metninde `/TB` alanı ve onu izleyen, bilinen bir alan koduyla
  (OV, TM, FL, TP, SK, WX, TA, WV, TB, IC, RM) başlamayan `/` gruplarının tamamı; `pirep_siddet_sinifi` bu
  birleşik metne uygulanır (en şiddetli grup). y_çok = sınıf ≥ 1. `REPORT` bulunamayan ya da `/TB` alanı
  ayrıştırılamayan örnek bu analizden düşer.
- **Kontrol:** tek gruplu raporlarda y_çok, mevcut etiketle aynı olmalı; farklı çıkanlar sayılır ve yazılır.
- **Ölçüt:** test günlerinde etiketi değişen örnek sayısı (0→1, 1→0) ve eğitim günlerindeki sayı (eğitim
  yeniden yapılmaz). Aynı skorlarla (TI1, birleşik EDR, §10 protokol modelleri temel ve geniş; eğitim etiketi
  değişmez) ROC-AUC(y_çok) − ROC-AUC(y), gün bloklu bootstrap.
- **Okuma:** değişen örnek az olacağı için fark büyük olasılıkla GA içinde kalır; bu da "etiket gürültüsü bu
  kaynaktan sonucu değiştirmiyor" diye raporlanır.

### 13.3 Fikir 24: AUC² ağırlıklı birleşik EDR

- **Ağırlık:** `edr_esleme` göstergelerinin (TI1, TI2, |VWS|, DEF, 1/Ri) EDR'ye eşlenmiş değerleri için
  eğitim günlerinde ROC-AUC_i; w_i = AUC_i² / Σ AUC_j² (Gu ve Wang 2024, Kim ve Chun 2011). Birleşik =
  Σ w_i·EDR_i, o noktada tanımsız gösterge varsa kalan ağırlıklar yeniden normalize edilir.
- **Ölçüt:** ağırlıklı − eşit ağırlıklı birleşik EDR ve ağırlıklı − TI1 ROC-AUC farkı (ikisinin de tanımlı
  olduğu test örneklerinde). Ağırlıklar ve eğitim AUC'leri raporlanır.

### 13.4 Fikir 19: ek teşhisler

- **Teşhisler** (pencere deposundan, noktanın en yakın seviyesinde; düşey türev çevreleyen katmandan):
  - FRONT: 2B kinematik frontogenez, F = −|∇θ|⁻¹[θx²·ux + θx·θy·(vx + uy) + θy²·vy] (Bluestein 1993);
    skor F, ayrıca |F| ayrı satır.
  - TEMPG: |∇T| (Sharman vd. 2006, Gu ve Wang 2024 Tablo 2).
  - PV: hidrostatik izobarik yaklaşım, PV = −g·(ζ + f)·∂θ/∂p; skor −PV (düşük/negatif PV riskli,
    Makale19). Sınıf başına PV < 0 payı da tanımlayıcı olarak verilir.
  - NCSU1 **hesaplanmaz**: formülün birincil kaynağı (Sharman vd. 2006) elde yok; uydurulmaz (ATM-06 ile aynı).
- **Ölçüt:** her teşhisin tek başına ROC-AUC'si ve TI1 farkı. Ayrıca "temel + FRONT, TEMPG, PV" (11 özellik)
  protokol modeli (§3 seçim kuralı, eğitim günlerinde) − temel set farkı (H1 ile aynı biçim).
- **Okuma:** model farkı GA alt > 0 ise F9 geniş setine aday; üretime alınması gece işinin bu teşhisleri
  üretmesini gerektirir (ONAY).

### 13.5 Fikir 9: ızgara düzeyinde uyarı alanı ve POD–alan eğrisi (NE-ABD küpleri)

- **Veri:** `era5_egitim_verisi/` NE-ABD küpleri (48 gün; 40–50°K, 80–70°B, 0,25°, 3 sa, 300/250/200 hPa),
  zaman ekseninde birleştirilir. **Birincil: `ml/dondurma_gunleri.json`'daki 7 gün çıkarılmış 41 gün**
  (§11 ile aynı). Ağ yok, indirme yok.
- **Hacim:** kutudaki tüm ızgara noktaları × küpün tüm zamanları × FL300, FL330, FL360, FL390
  (`rotayi_hava_durumuyla_eslestir`; küpün çevrelediği aralık). **PIREP'ler:** yerel IEM arşivi
  (`bagimsiz_backtest.arsiv_pireplerini_oku`), kutu içi, FL300–FL390, aynı günler; aynı fonksiyonla eşlenir.
  Orta-üstü (M) = sınıf ≥ 1, kontrol (N) = 0.
- **Skorlar:** TI1, birleşik EDR (sabit katsayılar), TI3 (13.6).
- **Eğri:** eşikler = her skorun birleşik ızgara dağılımının %50–%99,5 yüzdelikleri (0,5 adım) + kural eşikleri
  (TI1 7e-7, birleşik EDR 0,0757). Her eşikte uyarı alanı oranı A (ızgara noktalarının eşik üstü payı),
  POD_M (M raporlarının eşik üstü payı) ve POFD (N raporlarının eşik üstü payı).
- **Özet ölçüt:** POD_M–A eğrisinin altındaki alan (AUC_A; (0,0) ve (1,1) uçlarıyla yamuk; rastgele 0,5) ve
  A = %10 ile %20'deki POD_M (doğrusal ara değer). Belirsizlik: gün bloklu bootstrap (2.000, tohum 0); TI1'e
  karşı farklar eşleştirilmiş. Kural eşiklerinde A, POD_M, POFD.
- **Kapsam dışı:** TTS (gözlenen alan PIREP'lerden bilinemez; MADIS günleri bu küplerde yok).

### 13.6 Fikir 15: TI3 (Ellrod–Knox DVT; NE-ABD küpleri)

- **Tanım:** TI3 = TI1 + C·|DIV(t) − DIV(t − 6 sa)|, C = 0,01 (Kim ve Kim 2026, Lee vd. 2023 izlenerek); DIV
  noktanın en yakın seviyesinde, `yatay_diverjans_hesapla`. Pencere deposu yalnız ±1 sa tuttuğu için örnek
  düzeyinde (13.1–13.4) **yapılamaz**; NE-ABD küpleri 3 saatlik ve çoğunlukla ardışık 3 günlük bloklar olduğu
  için orada hesaplanır. t − 6 sa küpte yoksa (blok başı) TI3 tanımsızdır, nokta düşer.
- **Ölçüt:** 41 günde PIREP düzeyinde ROC-AUC (TI3 − TI1, aynı PIREP'ler, gün bloklu eşleştirilmiş bootstrap);
  13.5 eğrisinde TI3 satırı. DVT/TI1 oranının medyanı tanımlayıcı olarak verilir.
- **Çıktı (13.5–13.6):** `docs/sonuclar/2026-10-31_uyari_alani/uyari_alani.json` + README + şekil; bir kez,
  üzerine yazılmaz. Kod `turbulans-uyari-alani`.
- **Geçerlilik tehditleri:** 3 seviye, tek bölge, 41 gün, birkaç yüz PIREP; PIREP'ler trafik ve raporlama
  yanlılığı taşır (orta-üstü payı yüksek). ERA5'te 6 saatlik DIV farkı analiz artımlarını da içerir.
