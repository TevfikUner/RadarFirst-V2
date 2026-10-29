# OOD kapısı (kurul #29): ilk ölçüm

Üretim: 2026-10-29 · `ml/destek_kapisi.py` · aktif model `2c1740de7171…` (Random Forest, 79 eğitim günü).

Destek aralığı: aktif modelin eğitim günlerindeki 7.761 eşleşmiş örnekten özellik başına %0,5–%99,5
(model 7.759 örnekle eğitildi; 2 örnek sonradan eklendi, dosyada not edildi). `turbulans-ml-destek` ile
`model_deposu/destek_araligi.json`'a yazıldı; model SHA-256'sı değişince geçersiz olur.

| Girdi | Örnek | En az bir özellik destek dışı (ML çıktısı kapanır) |
|---|---|---|
| Türkiye, Ocak 2019 7 seviyeli küp, rastgele seyir noktası (FL280–420, tohum 0) | 20.000 | %2,9 |
| Kontrol: ABD altın test günleri (eğitimde görülmedi) | 1.583 | %4,2 |

Türkiye'de en çok dışarıda kalan özellikler: `richardson_sayisi` (251), `ti1_indeksi` (234),
`yatay_deformasyon` (177), `dusey_ruzgar_kaymasi` (128).

**Okuma.** Marjinal destek kapısı aşırı değerleri yakalar, ama Türkiye girdilerini ABD'den ayırmaz: kapanma
oranı kontroldekiyle aynı düzeyde. #10'daki kayma (PSI 0,4–1,2) dağılımın şeklindedir, desteğin dışında
değil. Kapının içinde kalmak Türkiye'de becerinin kanıtı değildir; Türkiye'de beceri ölçülmedi.
Özelliklerin birlikte görülmemiş birleşimleri (çok değişkenli OOD) bu kapıyla yakalanmaz.

Çıktılar sertifikalı EDR değildir; sistem operasyonel karar aracı değil, karar destek aracıdır.
