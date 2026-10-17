# Kaçınma başlangıç zamanı (Fikir 18)

Üretim: 2026-10-17T14:14:32+00:00 · `turbulans-kacinma-baslangici` · indirilen 9,48 MB

> Gösterim amaçlı küçük deney; istatistiksel genelleme yapılmaz. Referans gerçek analiz değil, yeniden planlama anında başlamış en son GFS koşusunun kısa öngörülü tahminidir; R1'in koşusu referansa zamanca daha yakın olduğu için sonuç R1 lehine yanlı olabilir (bu günlerde gözlemle doğrulama yok). SIGMET ve kısıtlı sahalar yok sayıldı; yalnız seyir bölümü. Karar destek amaçlıdır, sertifikalı EDR değildir.

## Yöntem

- R0: kalkıştan 6 sa önce elde olan GFS koşusuyla tüm rota (koşu gecikmesi 5 sa).
- R1: R0 planında sürenin yarısına gelinen noktada, o an elde olan en yeni koşuyla kalan kısım yeniden planlanır.
- Referans: yeniden planlama anında ya da öncesinde başlamış koşu (R1 ile aynıysa bir sonraki). R0'ın kalan kısmı, R1 ve büyük daire (normal) kalan kısmı bu küple değerlendirilir.
- R1 yolda seviye değiştiriyorsa rota kodunun kendi seviye değişimi farkı R1'e eklenir (modelde düşey geçiş süresi 0; yakıt farkı birkaç kg, alçalmada kredi olabilir).
- A320, 35000 ft istek; TI1 eşiği 7.00e-07 (GFS'e özgü nihai eşik 18 Ekim paketine bağlı).

## Özet

- Vaka: 15 (hesaplanan 15, hata 0); referansta riskli bölüm içeren vaka 9; R1'de yeni koşu olmayan 0.
- Riskli süre kazancı (R0 kalan − R1, dk): toplam 11,9, ortalama 0,79, medyan 0,00; azalan 6, artan 3, değişmeyen 6.
- Süre maliyeti (R1 − R0 kalan, dk): ortalama -0,11, medyan -0,00, en büyük 2,56.

## Vakalar

| Rota | Kalkış | Yeniden plan | Koşular R0/R1/Ref | Öngörü (sa) | Strateji R0/R1 | Riskli dk R0 kalan / R1 / normal | R0 kendi tahmini | Kazanç dk | Süre maliyeti dk |
|---|---|---|---|---|---|---|---|---|---|
| LTFM-LTAI | 10-12T10:00 | 10:20 | 11T18 / 12T00 / 12T06 | 4,3–4,7 | irtifa_asagi / yok | 0,0 / 0,0 / 0,0 | 0,0 | 0,0 | -0,00 |
| LTFM-LTCI | 10-12T10:00 | 10:46 | 11T18 / 12T00 / 12T06 | 4,8–5,5 | yok / irtifa_asagi | 0,0 / 0,0 / 0,0 | 0,0 | 0,0 | -0,01 |
| LTBJ-LTCE | 10-12T10:00 | 10:43 | 11T18 / 12T00 / 12T06 | 4,7–5,4 | irtifa_asagi / yok | 1,1 / 0,5 / 0,5 | 0,0 | 0,5 | -0,00 |
| LTAI-LTCG | 10-12T10:00 | 10:31 | 11T18 / 12T00 / 12T06 | 4,5–5,0 | yok / yok | 0,0 / 0,0 / 0,0 | 0,0 | 0,0 | -0,01 |
| LTAJ-LTFM | 10-12T10:00 | 10:32 | 11T18 / 12T00 / 12T06 | 4,5–5,0 | yok / irtifa_asagi | 2,3 / 0,0 / 2,7 | 0,0 | 2,3 | -0,01 |
| LTFM-LTAI | 10-14T16:00 | 16:19 | 14T00 / 14T06 / 14T12 | 4,3–4,6 | irtifa_yukari / yanal | 2,0 / 1,0 / 2,0 | 11,0 | 1,0 | 2,01 |
| LTFM-LTCI | 10-14T16:00 | 16:50 | 14T00 / 14T06 / 14T12 | 4,8–5,7 | yanal / irtifa_asagi | 4,7 / 1,2 / 8,2 | 0,0 | 3,5 | -1,52 |
| LTBJ-LTCE | 10-14T16:00 | 16:47 | 14T00 / 14T06 / 14T12 | 4,8–5,5 | yanal / yanal | 2,1 / 3,5 / 10,8 | 0,0 | -1,4 | 1,07 |
| LTAI-LTCG | 10-14T16:00 | 16:30 | 14T00 / 14T06 / 14T12 | 4,5–5,0 | irtifa_yukari / yanal | 3,0 / 3,1 / 3,8 | 1,5 | -0,1 | 2,56 |
| LTAJ-LTFM | 10-14T16:00 | 16:32 | 14T00 / 14T06 / 14T12 | 4,5–5,1 | yanal / yanal | 0,0 / 3,9 / 5,1 | 0,9 | -3,9 | -1,09 |
| LTFM-LTAI | 10-16T04:00 | 04:18 | 15T12 / 15T18 / 16T00 | 4,3–4,6 | irtifa_yukari / yok | 0,0 / 0,0 / 0,0 | 0,0 | 0,0 | -0,00 |
| LTFM-LTCI | 10-16T04:00 | 04:47 | 15T12 / 15T18 / 16T00 | 4,8–5,5 | irtifa_yukari / yok | 0,0 / 0,0 / 0,0 | 0,0 | 0,0 | 0,02 |
| LTBJ-LTCE | 10-16T04:00 | 04:41 | 15T12 / 15T18 / 16T00 | 4,7–5,4 | yok / yok | 0,0 / 0,0 / 0,0 | 0,0 | 0,0 | -0,00 |
| LTAI-LTCG | 10-16T04:00 | 04:30 | 15T12 / 15T18 / 16T00 | 4,5–5,0 | yok / irtifa_yukari | 5,9 / 0,0 / 5,1 | 0,0 | 5,9 | -0,32 |
| LTAJ-LTFM | 10-16T04:00 | 04:38 | 15T12 / 15T18 / 16T00 | 4,6–5,2 | yanal / irtifa_asagi | 5,6 / 1,6 / 7,8 | 0,0 | 4,0 | -4,33 |

Koşular gün ve saat (GGTSS) olarak; "R0 kendi tahmini": R0 kalan kısmının R0 koşusuyla öngörülen riskli süresi.
Karşılaştırma: Kim vd. (2015) LTAR 1/2/3 (+16 dk, 10 dk tasarruf, +2 dk) farklı bölge ve yöntemdir; sayılar doğrudan kıyaslanmaz.
