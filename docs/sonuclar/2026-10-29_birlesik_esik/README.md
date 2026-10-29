# Birleşik EDR rota eşiği (kurul #4 kalanı, protokol §12)

Üretim: 2026-10-29T12:02:47+00:00 · commit `14949700875a1ac23affbf3bd75a6eda790bf658` · veritabanı `Turbulence-db-dondurma` · kesme 2026-10-18. Eğitim 147 gün (14357 örnek; birleşik EDR'si hesaplanan 14357); altın test 16 gün (1583 örnek).

**Seçilen eşik (1-SE kuralı):** birleşik EDR ≥ **0.0757** m^(2/3) s⁻¹ (Peirce-maks eşiği 0.0668, Peirce 0.281, SE 0.011).

**Kontrol:** aynı kural aynı çerçevede TI1 için 7.39e-07 verdi (nihai paket 7,39e-7; Peirce-maks 4.96e-07).

| Altın test günleri (bilgi) | Eşik | POD | POFD | Peirce | Örnek |
|---|---|---|---|---|---|
| Birleşik EDR | 0.07566 | 0.545 | 0.264 | 0.281 | 1583 |
| TI1 7e-7 | 7e-07 | 0.501 | 0.248 | 0.253 | 1583 |

Eşik ABD ERA5 verisinden seçildi; Türkiye'de beceri ölçülmedi. Birleşik EDR TI1'i de içerir. Rota sapma kararı TI1'le kalır; bu eşik yalnız uyarı oranının ikinci sütunu içindir (§12).

Çıktılar sertifikalı EDR değildir; sistem operasyonel karar aracı değil, karar destek aracıdır.
