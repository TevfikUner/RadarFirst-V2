# Zaman örneklemesinin TI1'e etkisi (ATM-04)

Üretim: 2026-10-28T13:05:02+00:00 · commit `698c7c8aee16ca662267b9b99521a2bdae562550` · küp `ocak_2019_turbulans.nc` (saatlik) · 20000 rastgele nokta (iç bölge, FL310–380, zamanda sürekli) · risk eşiği 7.0e-07. Referans: saatlik küp (en yakın saat, ≤ 30 dk kayma). Karşılaştırılan: küpün her N. saati (en yakın adım, ≤ N/2 sa kayma). Yalnız zaman örneklemesinin etkisidir; GFS'in tahmin hatasını ve 0,25°'lik uzay örneklemesini içermez.

| Adım | Nokta | Spearman | Risk eşiğinde aynı karar | Riskli oranı (saatlik / seyrek) | Saatlikte riskli olanın seyrekte de riskli oranı | Medyan |log10 fark| |
|---|---|---|---|---|---|---|
| 3 sa | 20000 | 0.923 | %95.9 | %15.4 / %15.3 | %86.3 | 0.048 |
| 6 sa | 19946 | 0.816 | %92.4 | %15.3 / %15.2 | %74.7 | 0.113 |

Çıktılar sertifikalı EDR değildir; sistem operasyonel karar aracı değil, karar destek aracıdır.
