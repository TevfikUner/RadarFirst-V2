# Uyarı alanı ve POD–alan eğrisi; TI3 (protokol §13.5–13.6, keşifsel)

Üretim 2026-10-31T02:27:46+00:00 · commit `735262e68dc4a080583a748f08a70964f70b1476` · NE-ABD ERA5 küpleri (`era5_egitim_verisi`, 300/250/200 hPa, 3 sa), ızgara FL300/330/360/390, PIREP FL300–390. Bağımlı (dondurma) günler birincilden çıkarıldı: 2018-01-12, 2018-02-15, 2018-04-16, 2019-05-06, 2020-02-11, 2020-02-12, 2020-02-27. Küp zamanına en yakın adımı 90 dakikadan uzak olan PIREP'ler (blok sınırında, sonraki gün küpte yok) atıldı. (22 PIREP)

POD–alan AUC: uyarı alanı oranı (ızgaranın eşik üstü payı) eksenine karşı orta-üstü PIREP'lerin eşik üstü payı; rastgele 0,5. Eşikler her skorun ızgara dağılımının %50–%99,5 yüzdelikleri, %50'nin altı (1,1)'e düz çizgi. Gün bloklu bootstrap (2.000). TTS hesaplanmadı (gözlenen alan PIREP'ten bilinemez).

## Birincil: bağımsız günler

41 gün; ızgara 1837368 nokta (üç skorun da tanımlı olduğu, 1995552 noktadan); PIREP 660 (429 orta-üstü, 231 kontrol).

| Skor | POD–alan AUC | %95 GA | POD @ alan %10 | POD @ alan %20 | PIREP ROC-AUC |
|---|---|---|---|---|---|
| TI1 | 0,631 | [0,585; 0,671] | 0,226 [0,162; 0,292] | 0,380 [0,310; 0,449] | 0,587 |
| birlesik_edr | 0,654 | [0,606; 0,698] | 0,273 [0,199; 0,333] | 0,422 [0,339; 0,502] | 0,601 |
| TI3 | 0,646 | [0,607; 0,684] | 0,254 [0,192; 0,314] | 0,403 [0,337; 0,477] | 0,594 |

| Fark (POD–alan AUC) | Fark | %95 GA | Okuma |
|---|---|---|---|
| birlesik_edr - TI1 | +0,024 | [+0,013; +0,037] | daha iyi |
| TI3 - TI1 | +0,015 | [-0,010; +0,043] | fark gösterilemedi |

| PIREP ROC-AUC farkı | Fark | %95 GA |
|---|---|---|
| TI3 - TI1 | +0,007 | [-0,030; +0,039] |
| birlesik_edr - TI1 | +0,014 | [-0,003; +0,033] |

| Kural eşiği | Eşik | Uyarı alanı | POD (orta-üstü) | POFD (kontrol) |
|---|---|---|---|---|
| TI1 | 7e-07 | 0,163 | 0,329 | 0,177 |
| birlesik_edr | 0,0757 | 0,178 | 0,382 | 0,199 |

DVT/TI1 oranı medyanı: ızgara 0,91, PIREP 0,84.

## İkincil: tüm günler

48 gün; ızgara 2141568 nokta (üç skorun da tanımlı olduğu, 2336256 noktadan); PIREP 755 (494 orta-üstü, 261 kontrol).

| Skor | POD–alan AUC | %95 GA | POD @ alan %10 | POD @ alan %20 | PIREP ROC-AUC |
|---|---|---|---|---|---|
| TI1 | 0,641 | [0,598; 0,679] | 0,243 [0,180; 0,302] | 0,393 [0,325; 0,456] | 0,591 |
| birlesik_edr | 0,665 | [0,622; 0,703] | 0,277 [0,218; 0,340] | 0,435 [0,358; 0,507] | 0,604 |
| TI3 | 0,654 | [0,613; 0,690] | 0,259 [0,203; 0,317] | 0,419 [0,350; 0,481] | 0,592 |

| Fark (POD–alan AUC) | Fark | %95 GA | Okuma |
|---|---|---|---|
| birlesik_edr - TI1 | +0,024 | [+0,014; +0,035] | daha iyi |
| TI3 - TI1 | +0,013 | [-0,009; +0,037] | fark gösterilemedi |

| PIREP ROC-AUC farkı | Fark | %95 GA |
|---|---|---|
| TI3 - TI1 | +0,002 | [-0,029; +0,030] |
| birlesik_edr - TI1 | +0,013 | [-0,001; +0,030] |

| Kural eşiği | Eşik | Uyarı alanı | POD (orta-üstü) | POFD (kontrol) |
|---|---|---|---|---|
| TI1 | 7e-07 | 0,166 | 0,348 | 0,192 |
| birlesik_edr | 0,0757 | 0,181 | 0,405 | 0,222 |

DVT/TI1 oranı medyanı: ızgara 0,91, PIREP 0,78.

Tek bölge, 3 seviye, birkaç yüz PIREP; PIREP'ler trafik ve raporlama yanlılığı taşır. Keşifseldir; rota kararı ve eşikler değişmez. Çıktılar sertifikalı EDR değildir; sistem operasyonel karar aracı değil, karar destek aracıdır.
