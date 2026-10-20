# PIREP türbülans etiketi: bağımsız ayrıştırıcıyla çapraz kontrol (Fikir 11)

20 Ekim 2026 · `scripts/pirep_ayristirici_capraz.py` · avwx-engine 1.9.5 · yerel IEM arşivi (2018–Mart 2020).
Yalnız rapor; eğitim etiketi ve dondurulmuş paket değişmedi.

**Kapsam.** 1.570.530 ham PIREP'ten seyir irtifasında (`ML_MIN_IRTIFA_FT`–`ML_MAKS_IRTIFA_FT`) ve IEM
türbülans alanı dolu 420.067 rapor. Rastgele 500 rapor (tohum 0): eğitim etiketi IEM `TURBULENCE`
alanından, karşılaştırma avwx-engine'in ham `REPORT` metninden çıkardığı türbülans şiddetinden; ikisi de
aynı `pirep_siddet_sinifi` eşlemesiyle sınıflandırıldı (fark yalnız alan çıkarımından gelir).

| | avwx: yok/hafif | orta | orta-şiddetli+ | ayrıştıramadı |
|---|---|---|---|---|
| IEM: yok/hafif | 201 | 0 | 0 | 1 |
| IEM: orta | 0 | 293 | 0 | 0 |
| IEM: orta-şiddetli+ | 0 | 0 | 5 | 0 |

500 raporun 499'unda sınıf aynı, uyuşmazlık yok (`ozet.json`).

**Sınırlama (karşılaştırmanın göremediği).** avwx-engine de IEM gibi yalnız ilk `/TB` grubunu alıyor.
Ham metinde ikinci grubu olan raporlar ayrıca sayıldı (bizim basit desenimizle, bağımsız değil):
420.067 raporun 2.975'inde `/TB` sonrası ikinci bir şiddet grubu var; bunların 1.023'ünde ikinci grup
daha şiddetli ve **994'ünde (%0,24) pozitif/negatif etiket tersine dönerdi** (örnek: `TB NEG 350/MOD 355`
IEM'de `NEG 350` -> negatif). Etiketin çoğunlukla negatif yönde yanlış olduğu bu küçük alt küme
eşleşmiş ~18 bin örnekte kabaca 40 örneğe denk gelir.

**Karar.** Dondurulmuş veri ve etiket değişmez (deney protokolü). Çoklu `/TB` grubunun en şiddetlisini
almak, dondurma sonrası yeni günlerde etiket duyarlılığı olarak değerlendirilecek aday (YAPILACAKLAR).
