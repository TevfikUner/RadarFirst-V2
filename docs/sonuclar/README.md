# Sonuç paketleri

Rapordaki, sunumdaki, posterdeki ve sistem kartındaki her doğruluk sayısı buradaki bir
paketten alınır (Uzman Madde 8). Paket klasör adı kesme günüdür. Kesme, o güne kadar
(dahil) veritabanına girmiş örnekleri seçer. Her paketteki `SAYILAR.md` sayıların tek
listesidir ve elle düzenlenmez.

| Paket | Durum | Kesme |
|---|---|---|
| [`2026-10-07/`](2026-10-07/SAYILAR.md) | **Ön paket.** Belgeler şimdilik bu paketin sayılarını kullanır. | 7 Ekim 2026 |
| [`2026-10-16/`](2026-10-16/README.md) | Ek analizler (ML paketi değil): ERA5 → canlı GFS TI1 eşik eşlemesi; rota ayrıklaştırma yakınsaması. | 9–11 Ekim 2026 / Ocak 2019 |
| [`2026-10-17/`](2026-10-17/README.md) | Ek analiz (ML paketi değil): kaçınma başlangıç zamanı, kalkışta ve yolda planlama (Fikir 18). | 12–16 Ekim 2026 GFS |
| `2026-10-18/` | Nihai paket, veri dondurma günü üretilecek. Belgelerdeki sayılar o gün bu paketle değiştirilir. | 18 Ekim 2026 |

## Paketin içeriği

- `sonuc_paketi.json`: commit hash, kesme, veri sayıları, protokol modeli, altın test
  günlerinde Model/TI1/1/Ri/birleşik EDR için ROC-AUC ve PR-AUC (gün bazlı blok
  bootstrap %95 GA), TI1'e karşı eşleştirilmiş ROC-AUC farkı ve p değeri, TI1 eşik
  taraması (genel ve seviyeye göre), yalnız CAT alt kümesi, MADIS ölçülen EDR, rota
  backtest'i.
- `SAYILAR.md`: aynı sayılar, JSON anahtarlarıyla birlikte.
- `roc_ti1_ri.png`: altın günlerde TI1 ve Ri ROC eğrisi. Eğitim günlerinde seçilen Peirce
  eşikleri ve config eşiği işaretli.
- `guvenilirlik_modeli.png`: modelin güvenilirlik diyagramı (PIREP altın günler, MADIS).
- `backtest_ucus_basina.png`: veritabanındaki her backtest uçuşu için riskli nokta oranı.
  Bu ölçüm TI1 ile yapılır ve döngüseldir.
- `rota_performansi.md` / `.json`: `turbulans-performans rota` ile rota kararı süresi.

## Yeniden üretme

```
turbulans-ml-degerlendirme --kesme 2026-10-18 --cikti docs/sonuclar/2026-10-18
turbulans-performans rota --json docs/sonuclar/2026-10-18/rota_performansi.json
turbulans-ml --dondurma-raporu docs/sonuclar/2026-10-18
```

Komut, protokol modelini aynı kurallarla yeniden eğitir: altın test günleri dışında gün
gruplu CV, 1-SE seçimi ve sigmoid kalibrasyon. Aktif model kullanılmaz. Aynı veritabanı
yedeği ve aynı commit ile sayılar aynı çıkar (bootstrap tohumu 0).

## Okurken dikkat

- **Etiket yanlılığı.** PIREP'lerin yaklaşık yarısı pozitiftir; pilotlar sakin havayı
  nadiren raporlar. Model olasılığı mutlak türbülans sıklığı değildir. MADIS
  güvenilirlik eğrisi bu yüzden köşegenin çok altındadır (bkz. `docs/rapor/SONUCLAR.md` §4).
- **CAT alt kümesi.** PIREP metninde CB, TS (+TSRA, VCTS, TSTM gibi türevler), TCU,
  MTN WAVE ya da LLWS geçen raporlar dışlanır. Ham metin yalnız yerel IEM arşivinde
  (2018–Mart 2020) var. Metni olmayan günler iki alt kümede de yoktur.
- **MADIS.** Elimizde yalnız hafif sınıf var, orta ve üstü ölçüm yok. Örnekler PIREP
  pencerelerinden geldiği için seçim yanlılığı vardır. QC "Z" ön veridir. MADIS günleri
  modelin eğitim günleriyle çakışabilir.
- **Backtest.** Riskli oran TI1 ile ölçülür; A* de TI1'i düşürür. Bağımsız kanıt
  (SIGMET/PIREP) yalnız kapsadığı uçuşlarda vardır.
- **PUE502** (26 Eylül 2026, canlı GFS) bu pakette yoktur. Uçuş ve backtest kaydı
  3 Ekim öncesi veritabanında kaldı ve yedeklerde de bulunmuyor. Sayıları tarihçedir
  (bkz. `docs/SISTEM_KARTI.md` §6).

Çıktılar sertifikalı EDR değildir; sistem operasyonel karar aracı değil, karar destek
aracıdır.
