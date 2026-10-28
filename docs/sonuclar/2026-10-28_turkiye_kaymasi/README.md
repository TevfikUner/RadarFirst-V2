# Türkiye girdilerinin ABD eğitim verisine göre kayması (VER-08)

Üretim: 2026-10-28T15:43:47+00:00 · commit `efc6d51016aa3652efd445ce6f896e26d1d073bc` · Türkiye: `ocak_2019_turbulans_7seviye.nc` (7 seviye, Ocak 2019), 20000 rastgele nokta (FL280–420, iç bölge, zamanda sürekli). ABD: 163 dondurma günündeki eşleşmiş seyir PIREP örnekleri (16033; kış günleri 4992).

PSI (0,10 üstü orta, 0,25 üstü belirgin; kaba kural, kalibre değil) ve en az bir özellikte ABD'nin %0.5–%99.5 aralığı dışında kalan oran:

| Karşılaştırma | ti1_indeksi | richardson_sayisi | ruzgar_hizi_ms | basinc_hpa | dusey_ruzgar_kaymasi | yatay_deformasyon | yatay_diverjans | ti2_indeksi | Destek dışı (herhangi) |
|---|---|---|---|---|---|---|---|---|---|
| Türkiye − ABD (tüm) | 0.41 | 1.04 | 0.12 | 0.18 | 0.37 | 0.30 | 0.29 | 0.42 | %3.0 |
| Türkiye − ABD (kış) | 0.60 | 1.20 | 0.50 | 0.22 | 0.73 | 0.26 | 0.36 | 0.58 | %5.4 |
| Kontrol: ABD altın − eğitim günleri | 0.01 | 0.04 | 0.11 | 0.01 | 0.02 | 0.01 | 0.02 | 0.01 | %4.0 |

**Okuma.** Kontrol satırı aynı dağılım içindeki gürültü düzeyidir. Türkiye satırları bunun belirgin üstündeyse girdi dağılımı kaymıştır; modelin ABD'de ölçülen becerisi Türkiye'ye taşınamaz. Türkiye noktaları ızgaradan rastgele, ABD örnekleri PIREP konumlarıdır (trafik ve raporlama yanlılığı); fark kısmen bu seçimden gelir. Bu bir girdi örtüşmesi ölçümüdür, Türkiye'de beceri ölçümü değildir.

**Sonuç (28 Ekim).** Türkiye girdileri ABD değer aralığının içinde (destek dışı %3,0, kışta %5,4; ABD içi kontrol
%4,0): model dışdeğerleme yapmıyor. Ama dağılım belirgin farklı: Türkiye noktaları daha sakin (5/50/95. yüzdelik TI1
3,7e-8 / 2,5e-7 / 1,3e-6, ABD 6,3e-8 / 5,0e-7 / 2,7e-6; Ri medyanı 11, ABD 2,7). ABD örnekleri raporlanan
PIREP noktaları olduğu için (%53 orta+) bu farkın bir kısmı seçimden gelir; bölge etkisi ayrılamaz. ABD'de
ölçülen beceri ve olasılık kalibrasyonu Türkiye'ye taşınamaz; Türkiye'de etiketli doğrulama gelecek çalışmadır.

Çıktılar sertifikalı EDR değildir; sistem operasyonel karar aracı değil, karar destek aracıdır.
