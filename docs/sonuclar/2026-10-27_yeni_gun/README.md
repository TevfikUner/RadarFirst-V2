# §10 yeni gün değerlendirmesi (27 Ekim 2026, tek seferlik)

Protokol `docs/deney_protokolu.md` §10 (19 Ekim, test günlerine bakılmadan yazıldı). Eğitim
`ml/dondurma_gunleri.json`'daki 163 gün (16.031 örnek); test bu listede olmayan 79 eşleşmiş gün
(7.769 örnek, %55,3 pozitif; 2018-01-14 – 2020-05-30). Bir kez çalıştırıldı, sonuç ne çıktıysa
aşağıda; "biraz daha gün bekleyelim" kararı skora bakılarak verilmedi.

| Skor (test, ROC-AUC [%95 GA]) | Değer |
|---|---|
| TI1 | 0,658 [0,644; 0,671] |
| Temel set (8), seçilen RF | 0,685 [0,671; 0,699] |
| Geniş set (13), seçilen LR | 0,693 [0,678; 0,708] |

| Karşılaştırma (gün bloklu eşleştirilmiş bootstrap) | Fark [%95 GA] | Sonuç |
|---|---|---|
| **H1:** geniş − temel | +0,008 [+0,002; +0,014], p = 0,008 | Desteklendi (alt sınır > 0) |
| Dondurma gününe ±1 komşu 24 gün çıkarılınca H1 | +0,005 [−0,002; +0,012], p = 0,164 | Anlamlı değil |
| Temel − TI1 (ADR 0004 kapısı, ≥ 0,02) | +0,027 [+0,018; +0,035] | Geçti |
| Geniş − TI1 | +0,035 [+0,026; +0,043] | Geçti |

Peirce (eğitim günlerinde seçilen eşikle): TI1 0,229, temel 0,260, geniş 0,276.

**Yorum.** Geniş özellik seti farkı küçük (+0,008) ve ardışık gün sızıntısı çıkarılınca GA
sıfırı kapsıyor; H1 desteği zayıf ve kırılgan olarak raporlanır. Modelin TI1'e üstünlüğü 18 Ekim
altın günlerindeki farka (+0,033) yakın ve modelin görmediği günlerde de korunuyor. Geniş setin
üretime alınması ayrı karardır (gece işinin bağlam özelliklerini üretmesi gerekir; ONAY).
Yeni günler de 2018–2020 ABD PIREP'idir: dağılım kayması değil, aynı dağılımda genelleme ölçülür.

**İkincil (keşifsel, çoklu karşılaştırma düzeltmesi yok).**
- Mevsim (gün / örnek; TI1 / temel / geniş): DJF 20 / 1.997: 0,655 / 0,687 / 0,691;
  MAM 30 / 2.873: 0,664 / 0,696 / 0,706; JJA 17 / 1.699: 0,647 / 0,655 / 0,671;
  SON 12 / 1.200: 0,657 / 0,690 / 0,694. Yazın model üstünlüğü en küçük, GA'lar örtüşüyor.
- Rüzgâr: < 30 m/s (3.403): 0,663 / 0,682 / 0,692; ≥ 30 m/s (4.366): 0,648 / 0,681 / 0,688.
- "Hafif = negatif" (Fikir 8): metni bulunan 6.992 örneğin 2.079'u hafif negatif. Hafifler
  çıkarılınca ROC-AUC 0,730 / 0,772 / 0,774, Peirce 0,343 / 0,392 / 0,396 (aynı alt kümede
  birincil: 0,654 / 0,683 / 0,693). Sıralama değişmiyor; hafif raporlar ayrımı belirgin zorlaştırıyor.

**Yeniden üretim.** Worker imajı commit `819f471` (imajdan bu yana `src/` değişmedi;
JSON'daki `commit: null` konteynerde git olmamasından). Komut:
`docker compose exec -T worker python -m turbulans_radar.ml.yeni_gun_degerlendirmesi --cikti <klasör>`.
Veri: gece işi bittikten sonra alınan `db_yedekleri/kalici/turbulans_20261027_yeni_gun.dump`
(sha256 `bbb1a26a3f07925617ca82975bcc0ee36ba56c54193681608860d9942319c882`); bağlam özellikleri
`ml_ozellik_deposu` pencere deposundan. JSON sha256
`16f1f17e566058e8e7d3243669dec3c50a4b694ecc89c031f23c4baf4faf9e97`.

Çıktılar sertifikalı EDR değildir; sistem operasyonel karar aracı değil, karar destek aracıdır.
