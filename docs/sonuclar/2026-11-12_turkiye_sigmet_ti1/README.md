# Türk TURB SIGMET alanında ERA5 TI1 (protokol §14, keşifsel)

Üretim: 2026-11-12. Ön kayıt `docs/deney_protokolu.md` §14 (TI1 hesaplanmadan yazıldı). Ham çıktı
[`sigmet_alan.json`](sigmet_alan.json). Komut:

```bash
CDSAPI_RC=<CDSAPI_RC_DOSYASI> turbulans-sigmet-alan --cikti docs/sonuclar/2026-11-12_turkiye_sigmet_ti1
```

Veri: `sigmetler` tablosunda 30 Eylül–7 Kasım arası LTAA/LTBB TURB SIGMET'leri (6 kayıt, hepsi LTAA), ERA5 (CDS,
4 istek, 1,9 MB), TI1 eşiği 7e-7. SIGMET başına 6.000 nokta; içeride = poligon, halka = poligona ≤ 300 km.

| SIGMET | Geçerlilik (UTC) | Bant | İçeride riskli | Halkada riskli | Fark d | Medyan log10 TI1 farkı |
|---|---|---|---|---|---|---|
| LTAA 4 | 13 Eki 06:00 | FL300–350 | %5,1 (215 nokta) | %2,1 | +0,030 | +0,22 |
| LTAA 5 | 22 Eki 14:50 | –FL250 | düştü (bant FL280–430 dışında) | | | |
| LTAA 6 | 22 Eki 17:00 | –FL250 | düştü (bant FL280–430 dışında) | | | |
| LTAA 14 | 27 Eki 19:00 | FL260–360 | %11,5 (1.286) | %7,1 | +0,044 | +0,11 |
| LTAA 18 | 27 Eki 23:20 | FL260–360 | %19,3 (1.157) | %11,4 | +0,079 | +0,22 |
| LTAA 12 | 7 Kas 15:00 | FL250–330 | %0,0 (383) | %4,1 | −0,041 | +0,07 |

**Birincil özet:** 4 SIGMET, ortalama d = **+0,028**, SIGMET bloklu bootstrap %95 GA **[−0,020; +0,067]**;
d > 0 olan 3/4. Ön kayıttaki okuma kuralıyla: **fark gösterilemedi** (GA sıfırı kapsıyor).

**İkincil:** medyan TI1 dört SIGMET'in dördünde de içeride daha yüksek (log10 farkı +0,07 ile +0,22 arası);
ama riskli oranlar düşük (eşiğin altında kalan yükseklik) ve bu ikincil ölçüt için karar kuralı yoktu.

## Sınırlar

- 4 kullanılabilir SIGMET, tek FIR (LTAA). İstatistiksel güç çok düşük; sonuç "TI1 Türk SIGMET'lerini
  yakalamıyor" diye de okunamaz.
- SIGMET gözlem değil uyarıdır ve NWP rehberliğinden (TI1'e benzer göstergelerden) türetilmiş olabilir; yani
  bağımsız bir referans değildir. Noktalar uzaysal olarak bağımlıdır, SIGMET içi GA verilmedi.
- ERA5 reanalizdir, operasyonel tahmin değildir. Düşük seviye SIGMET'ler (FL250 altı) küpün seviyeleri dışında
  kaldığı için incelenemedi.

Bu bir tutarlılık gözlemidir, doğrulama değildir. Çıktılar sertifikalı EDR değildir; sistem karar destek aracıdır.
SIGMET'ler biriktikçe aynı araç yeni bir klasörle (bir kez) yeniden çalıştırılabilir.
