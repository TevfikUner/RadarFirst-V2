# 17 Ekim 2026: kaçınma başlangıç zamanı (Fikir 18)

ML sonuç paketi değildir. Ayrıntılı tablo: [`kacinma_baslangici.md`](kacinma_baslangici.md),
ham sonuç: [`kacinma_baslangici.json`](kacinma_baslangici.json).

**Soru:** Kaçınmayı kalkıştan önce bir kez planlamak (R0) ile uçuşun ortasında daha yeni GFS
koşusuyla yeniden planlamak (R1) arasında riskli süre ve maliyet ne kadar değişiyor?
(Kim vd. 2015, LTAR 1/2/3.)

**Yöntem:** 5 Türkiye rotası (LTFM–LTAI, LTFM–LTCI, LTBJ–LTCE, LTAI–LTCG, LTAJ–LTFM) × 3 kalkış
(12 Ekim 10:00, 14 Ekim 16:00, 16 Ekim 04:00 UTC) = 15 vaka; A320, FL350 istek.
- R0: kalkıştan 6 sa önce elde olan koşu (koşu gecikmesi 5 sa) ile tüm rota.
- R1: R0 planında sürenin yarısında, o an elde olan en yeni koşuyla kalan kısım. Kalan kısım
  için öngörü süresi R0'da ~16–18 sa, R1'de ~10–12 sa.
- Referans: yeniden planlama anında başlamış koşunun 4–6 sa öngörülü tahmini. R0'ın kalan
  kısmı, R1 ve kaçınmasız büyük daire bu küple değerlendirilir.
- SIGMET ve kısıtlı sahalar yok sayıldı. TI1 eşiği 7e-7 (GFS'e özgü nihai eşik 18 Ekim paketine bağlı).
- Komut: `turbulans-kacinma-baslangici --cikti docs/sonuclar/2026-10-17` (9 THREDDS koşusu, 9,5 MB, tek seferlik).

**Sonuç:**

| | Toplam riskli süre (15 vaka) |
|---|---|
| Kaçınmasız büyük daire (kalan kısım) | 46,1 dk |
| R0 (kalkıştan önce planlanan kaçınma, kalan kısım) | 26,7 dk |
| R1 (yolda yeniden planlanan kaçınma) | 14,8 dk |

- Referansta 9 vakada riskli bölüm var. Yeniden planlama bunların 6'sında riskli süreyi azalttı,
  3'ünde artırdı (en kötü +3,9 dk: LTAJ–LTFM, 14 Ekim). Riskli vakalarda kazanç ortalama 1,3 dk,
  medyan 1,0 dk.
- 6 vakada R0'ın kendi koşusu kalan kısımda risk öngörmüyordu, ama referans koşu riskli bölüm
  gösterdi: ~16–18 sa öngörülü tahmin riskin yerini kaçırabiliyor.
- Süre maliyeti pratikte sıfır: ortalama −0,1 dk, en büyük +2,6 dk. Yakıt farkı −162…+112 kg.

**Sınırlar (sonucu okurken):**
- 15 vaka küçük bir örneklem; gösterim amaçlıdır, istatistiksel genelleme yapılmaz.
- Referans gözlem değil, daha yeni bir tahmindir. R1'in koşusu referansa zamanca daha yakın
  olduğu için sonuç R1 lehine yanlı olabilir. Bu günler için PIREP/MADIS doğrulaması yok.
- Kim vd. (2015) sayıları farklı bölge ve yöntemdir; doğrudan kıyaslanmaz.
- Karar destek amaçlıdır, sertifikalı EDR değildir. Uçuş sırasında yeniden planlama ATC onayı
  ve operasyonel kısıtlara bağlıdır.
