# §10.6 Model − birleşik EDR (28 Ekim 2026, sonradan eklenen ikincil)

Protokol `docs/deney_protokolu.md` §10.6 (commit `87e54fd`, skor hesaplanmadan önce; §10 sonucundan sonra
eklendiği için ön kayıtlı değildir). Eğitim `ml/dondurma_gunleri.json` (163 gün, 16.031 örnek); test §10 JSON'undaki
sabit 79 gün (7.772 örnek; §10'da 7.769, 28 Ekim'de yarıda kalan gece işi bu günlerde 3 örnek daha eşleştirdi).
Altın test günleri kullanılmadı.

| Skor (test, ROC-AUC [%95 GA]) | Değer |
|---|---|
| TI1 | 0,658 [0,644; 0,671] |
| Birleşik EDR | 0,669 [0,656; 0,683] |
| Temel set (8), seçilen RF | 0,685 [0,671; 0,699] (§10: 0,685) |
| Geniş set (13), seçilen LR | 0,693 [0,678; 0,708] |

| Karşılaştırma (gün bloklu eşleştirilmiş bootstrap) | Fark [%95 GA] |
|---|---|
| **Temel − birleşik EDR** (birincil) | **+0,016 [+0,010; +0,021]**, p < 0,001 → model birleşik EDR'yi geçiyor |
| Geniş − birleşik EDR | +0,024 [+0,017; +0,031] |
| Birleşik EDR − TI1 | +0,011 [+0,007; +0,015] |

**Yeniden üretim.** Komut (WSL venv, proje kökü, veritabanından yalnız okuma):
`python -m turbulans_radar.ml.yeni_gun_degerlendirmesi --birlesik-kiyas <klasör>`; JSON'daki commit `d73ec53`.
Not: `birlesik_kiyasi.json` yanlışlıkla model paneli commit'iyle (`8a716b8`) birlikte depoya girdi; içerik
`d73ec53` koduyla üretildi.

Çıktılar sertifikalı EDR değildir; sistem operasyonel karar aracı değil, karar destek aracıdır.
