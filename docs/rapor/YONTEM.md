# Yöntem (rapor bölümü)

Bu bölüm sistemin nasıl hesapladığını ve nasıl doğrulandığını anlatır. Ayrıntılı karar mantığı
`docs/SISTEM_KARTI.md` §3'te, deney kuralları `docs/deney_protokolu.md`'de, mimari
`docs/mimari.md`'dedir; burada yalnız sonuçları okumak için gereken kısım verilir.

## 1. Sistemin genel görünümü

```
OpenSky / ADS-B izi ──► eşleştirme (baro irtifa → ISA basınç, ERA5/GFS küpü)
                          └► Ellrod TI1, Richardson, birleşik EDR ──► PostgreSQL ──► FastAPI + WebSocket
AWC SIGMET + kısıtlı sahalar (sert) ─┐                                                  ├► 3B harita
TI1 cezası (yumuşak), OpenAP yakıt ──┴► A* rota (yanal + ±1 FL) ─────────────────────────┴► rota simülasyonu
IEM PIREP (FL280–420) ──► gece veri hattı ──► kapılı ML (TI1'i geçmezse aktifleşmez)
```

Sistem üç iş yapar: bir uçuş izini hava verisiyle eşleştirip CAT göstergelerini hesaplar; aktif
SIGMET'leri ve kısıtlı sahaları sert kısıt alarak kaçınma rotası önerir; önerilerini gerçek uçuş
izleriyle ve bağımsız etiketlerle karşılaştırır.

## 2. Veri

| Kaynak | İçerik | Çözünürlük | Kullanım |
|---|---|---|---|
| OpenSky (Trino) | ADS-B konum ve barometrik irtifa | ~1 sn | Gerçek uçuş izi |
| Copernicus ERA5 | u, v, t; 350–150 hPa arası 7 seviye | 0,25°, saatlik; ~5 gün gecikmeli | Gösterge, ML özellikleri, backtest |
| NOAA GFS (UCAR THREDDS) | u, v, t; 300/250/200 hPa | 0,25°, 3 saatlik | Uçuş öncesi planlama (en fazla 120 sa) |
| AWC SIGMET | Tehlike poligonu, irtifa bandı, geçerlilik | Canlı, 15 dk'da bir | Sert kısıt |
| IEM PIREP | Pilot türbülans raporları (ABD) | Tarihsel | ML etiketi ve doğrulama |
| NOAA MADIS (herkese açık) | Uçağın ölçtüğü EDR | Tarihsel, QC'siz ön veri | Nesnel etiket (ADR 0012) |

Lisans ve sağlayıcı sınırları `docs/VERI_KAYNAKLARI_VE_LISANSLAR.md`'dedir; CDS istek kotası kod
düzeyinde uygulanır.

## 3. Uçuş izi ile hava verisinin eşleştirilmesi

Her ADS-B noktasının barometrik irtifası ISA atmosferiyle basınca çevrilir; barometrik irtifa
yoksa GPS irtifasına düşülür ve kaynak kayda yazılır. Nokta, hava küpünün en yakın zaman ve ızgara
hücresiyle eşleşir; zamanda enterpolasyon yapılmaz. Fizik büyüklükleri (düşey rüzgâr kayması,
Richardson sayısı) uçağın basıncını çevreleyen tek katmandan (p_üst ≤ p ≤ p_alt) alınır. Küpün
yatay ya da zamansal kapsamı dışındaki noktalar tahmin edilmez, "veri yok" olarak bırakılır
(`fizik/eslestirme.py`, ADR 0005). Zaman örneklemesinin etkisi ayrıca ölçüldü (ATM-04,
`analiz/zaman_ornekleme.py`).

## 4. Türbülans göstergeleri

- **Ellrod TI1** (Ellrod ve Knapp, 1992): düşey rüzgâr kayması ile toplam yatay deformasyonun
  çarpımı (s⁻²). TI1 ve 0–1 gösterge ölçeği EDR değildir.
- **Richardson sayısı** (bulk Ri): katmanın statik kararlılığının kaymaya oranı; Ri < 0,25 ince
  kararsız katmanın işaretidir.
- **Birleşik EDR:** beş gösterge (TI1, TI2, VWS, DEF, 1/Ri) Sharman ve Pearson (2017) yöntemiyle
  log-normal EDR ölçeğine eşlenip ortalanır (C1 = −2,953, C2 = 0,602; klimatoloji pencere
  deposunun eğitim günlerinden). Uçaktan ölçülen EDR'nin yerini tutmaz.
- **Risk eşiği:** bir nokta TI1 > `TI1_ESIK_ORTA_SIDDETLI` ise "riskli" sayılır. Eşik veriden ve
  önceden yazılmış kuralla seçildi: eğitim günlerinde Peirce'i (POD − POFD) en büyüten eşiğin bir
  standart hatası içindeki en tutucu eşik (1-SE kuralı). 8 Ekim'de 7e-7 seçildi; 18 Ekim nihai
  paketinde kural 7,39e-7 verdi ve 7e-7 bandın içinde kaldığı için değişmedi. Canlı GFS için ayrı
  eşik (8,3e-7) ERA5 eşiğinin GFS dağılımındaki yüzdelik eşleniğidir.

## 5. Etiket hattı

IEM PIREP arşivinden seyir irtifasındaki (28.000–42.000 ft) raporlar alınır. IEM `FL` alanı
feet'tir; bu alanın uçuş seviyesi sanılması önceki veri setinde pist/yaklaşma raporlarının
seçilmesine yol açmıştı, hat bu bulguyla yeniden kuruldu (Bölüm 6, "Öğrenilen dersler"). Etiket
1 = orta ve üstü (LGT-MOD dahil), 0 = yok ya da hafif. Gün başına en fazla 100 PIREP sabit tohumla
seçilir. Her örnek için ERA5 penceresi (±1°, ±1 sa) indirilip depolanır; özellikler analizle aynı
kodla çıkarılır. Nesnel etiket olarak NOAA MADIS'in herkese açık uçak EDR arşivi PIREP
pencerelerinin içinden kullanılır; bu veri fiilen yalnız hafif sınıfı içerir.

## 6. Makine öğrenmesi modeli ve doğrulama protokolü

- **Soru:** ERA5'ten çıkarılan fiziksel özelliklerle eğitilen model orta ve üstü türbülansı tek
  başına TI1'den daha iyi ayırt eder mi?
- **Özellikler:** temel set 8 özellik: TI1, Ri, rüzgâr hızı, basınç, düşey kayma, yatay
  deformasyon, yatay diverjans, TI2. Geniş set 13 özellik: temel 8 + komşu TI1 en büyük/ortalama,
  kolondaki en düşük Ri, jet oranı, sıcaklık azalma oranı (protokol §10.2).
- **Bölme:** aynı günün raporları aynı hava sistemini gördüğü için rastgele bölme yapılmaz (ADR
  0003). 7 Ekim'de 80 günden rastgele 16'sı altın test günü olarak donduruldu; bu günler hiçbir
  model seçimine, kalibrasyona ya da eğitime girmez.
- **Model seçimi:** eğitim günlerinde gün gruplu, sınıf oranı korunan 5 katlı çapraz doğrulama, 3
  tekrar. Adaylar lojistik regresyon, rastgele orman, gradient boosting; en iyi modelle lojistik
  regresyonun farkı bir standart hatadan küçükse lojistik regresyon seçilir (1-SE). Olasılıklar
  Platt yöntemiyle kalibre edilir; eşikler eğitim günlerinde Peirce'i en büyütecek şekilde seçilip
  test günlerine olduğu gibi uygulanır.
- **Belirsizlik:** güven aralıkları gün bazlı blok bootstrap ile (1000 tekrar, %95). Model ile TI1
  farkı aynı bootstrap örnekleriyle eşleştirilmiş olarak hesaplanır; gün içi bağımlılık nedeniyle
  DeLong testine tercih edildi.
- **Aktivasyon kapısı (ADR 0004):** aday, test günlerinde TI1'e karşı ROC-AUC farkı ≥ 0,02 ve %95 GA
  alt sınırı > 0 ise, aktif model varsa ona karşı da aynı kuralla aktifleşir; aksi halde yalnız sürüm
  olarak saklanır ve geri alınabilir. 0,02 parametriktir, kalibre edilmedi. 29 Ekim'den beri kapı,
  aktif modelin görmediği son 16 yeni günde uygulanır (ADR 0014).
- **"Emin değilim" çıktısı:** çapraz-konformal tahminle her olasılık `dusuk_risk`, `yuksek_risk` ya
  da `belirsiz` durumuna çevrilir (hedef kapsama %90; ADR 0010). Eğitim dağılımının dışındaki
  girdide ML ve konformal çıktı verilmez (OOD kapısı).
- **Veri dondurma ve yeni günler:** 18 Ekim'de veri donduruldu, bir kez eğitim ve değerlendirme
  yapıldı. 19 Ekim'de, yeni günlere bakılmadan, dondurmadan sonra toplanan ≥ 30 yeni günde tek
  seferlik değerlendirme protokolü yazıldı (protokol §10); 27 Ekim'de 79 günle bir kez çalıştırıldı.
  Sonradan eklenen analizler de skorlar hesaplanmadan protokole yazıldı (§11–§13).

## 7. Rota önerisi

- **Arama uzayı:** büyük daire etrafında 41 ara noktalı bir koridorda A* (Hart vd., 1968); bacak
  açısı en fazla 30°, toplam yanal sapma en fazla 400 km, ızgara aralığı en fazla 20 km. Ayrıca
  aynı yönün bir üst ve bir alt yasal uçuş seviyesi (yarım daire kuralı, RVSM, tip tavanı) aday
  sayılır; seviye değişiminin yakıt bedeli OpenAP ile hesaplanır. İsteğe bağlı olarak FRATURK
  serbest rota ağında da aranabilir.
- **Kısıtlar ve öncelik:** (1) aktif SIGMET'e ve kısıtlı sahaya girmemek: sert, dört boyutlu kısıt
  (poligon, irtifa bandı, varış zamanındaki geçerlilik, bacağın poligonu kesmesi); (2) riskli TI1
  noktalarından kaçınmak: yumuşak kısıt; (3) en düşük yakıt ve süre.
- **Seçim kuralı (ADR 0013):** sert kısıtlara uyan adaylar arasında önce riskli TI1 nokta sayısı en az
  olan, eşitlikte en az yakıtlı aday seçilir. Riskten kaçınan aday yoksa riskli rota yine önerilir;
  güvenli rota yoksa (SIGMET) öneri yapılmaz. Kaçınılacak risk yoksa önerilen rota büyük daireyle
  aynıdır; uydurma bir iyileşme gösterilmez.
- **Kapsam:** yalnız seyir safhası; diğer trafikle ayırmayı dikkate almaz, ATC talimatının yerini
  tutmaz. Önerilen rota NON-OPERATIONAL işaretli bir FPL Madde 15 dizgisi olarak da verilir.

## 8. Uygulama ve doğrulanabilirlik

Sistem Python paketidir (`src/turbulans_radar`): FastAPI arka ucu, PostgreSQL + Alembic, kuyruklu
işçi (gece veri hattı, eğitim), dağıtık kilit; Docker Compose ile çalışır. 31 Ekim 2026'da 1.242
otomatik test vardır (birim, PostgreSQL, gerçek veri, tarayıcı); sürekli entegrasyon her değişikliği
6 işte sınar. Her rota ve tahmin yanıtı `uretim_bilgisi` taşır (yazılım sürümü, hava küpü, eşikler,
model sha256'sı, commit). Raporlanan her sayı `docs/sonuclar/` altındaki, komutu ve verisi yazılı
sonuç paketlerinden gelir.

Çıktılar sertifikalı EDR değildir; sistem operasyonel karar aracı değil, karar destek aracıdır.
