# GFS tahmin ufku tutarlılığı (TI1)

Üretim: 2026-10-28T17:08:16+00:00 · commit `dbddc88a692aa96143eadc380d5bc23aa0ca14a0` · geçerlilik 2026-10-23T00:00:00+00:00 – 2026-10-28T00:00:00+00:00 (her 12 sa) · kutu [31.0, 46.0, 20.0, 51.0] · [200.0, 250.0, 300.0] hPa · her geçerlilikte 5000 rastgele nokta (FL310–380) · TI1 risk eşiği 8.3e-07.

Referans f000 (aynı geçerlilik zamanındaki koşunun analizi). "Riskli" = TI1 > eşik.

| Ufuk | Geçerlilik | Spearman medyanı [en az–en çok] | Aynı karar medyanı | f000 riskli oranı | Tahmin riskli oranı | f000'da riskli olanın tahminde de riskli olma oranı | Tahminde riskli olanın f000'da da riskli olma oranı |
|---|---|---|---|---|---|---|---|
| f024 | 11 | 0.668 [0.612–0.773] | 0.933 | 0.083 | 0.081 | 0.567 | 0.605 |
| f048 | 11 | 0.500 [0.392–0.587] | 0.913 | 0.083 | 0.074 | 0.434 | 0.417 |

Eksik geçerlilik (dosyası olmayan): 0.

**Okuma.** Ölçü GFS'in kendi kendisiyle tutarlılığıdır: f024/f048'in f000'a benzemesi doğruluk değil, öngörülebilirliktir; f000 de bir tahmindir ve gözlem değildir. Geçerlilik zamanları aynı hava sistemlerini paylaşır, bağımsız örnek değildir; değerler betimleyicidir. Tek bölge (Türkiye kutusu), tek mevsim, 3 basınç seviyesi. Ürünün 48 saatlik `ongoru_belirsiz` sınırı literatürden (Lee, 2025) alınmıştır; bu tablo o sınırı kalibre etmez, yalnız bu dönemde TI1'in yerinin ufukla ne kadar değiştiğini gösterir.

Çıktılar sertifikalı EDR değildir; sistem operasyonel karar aracı değil, karar destek aracıdır.
