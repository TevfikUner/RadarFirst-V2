# Uyarı oranı / alarm yorgunluğu ölçümü

Üretim: 2026-10-28T12:03:43.146539+00:00 · commit `50076fcec8a0ad661a06749b69dae0774f16420f` · TI1 risk eşiği 7.0e-07 · 31 gün (2019-01-01'ten) × saatler [0, 6, 12, 18] × 6 şehir çifti × FL [350, 370]. Veri yerel ERA5 küpü (3 seviye, Türkiye, Ocak 2019); canlı veri, otomatik indirme, SIGMET ve kısıtlı saha kapalı (yalnız TI1 etkisi ölçülür). A320, koridor modu, varsayılan seçim kuralı (önce riskli nokta sayısı, sonra yakıt).

| Grup | Rota | Normal rotada riskli nokta olan | Sapma önerilen | Riskli süre medyanı (dk, riskli rotalarda) | Sapmada ek yakıt medyanı (%) | Sapmada ek yakıt p90 (%) | Sapmalarda daha ucuz riskli seçenek bulunan | O seçeneğin yakıt avantajı medyanı (puan) | O seçenekte kalan riskli nokta medyanı |
|---|---|---|---|---|---|---|---|---|---|
| **Tümü** | 1488 | %46.3 | %46.3 | 12.4 | +2.2 | +8.8 | %74.7 | 6.2 | 8 |
| FL350 | 744 | %52.2 | %52.2 | 14.3 | +1.6 | +8.1 | %57.7 | 7.9 | 8.5 |
| FL370 | 744 | %40.5 | %40.5 | 10.6 | +3.4 | +9.7 | %96.7 | 4.9 | 6 |
| İstanbul→Van | 248 | %46.8 | %46.8 | 12.3 | +1.4 | +8.1 | %71.6 | 5.3 | 5 |
| İzmir→Erzurum | 248 | %48.8 | %48.8 | 13.1 | +2.3 | +8.8 | %72.7 | 6.8 | 6.5 |
| Antalya→Kars | 248 | %52.4 | %52.4 | 12.3 | +2.2 | +11.1 | %77.7 | 6.0 | 7 |
| İstanbul→Gaziantep | 248 | %46.4 | %46.4 | 13.0 | +2.7 | +8.2 | %80.0 | 6.5 | 8 |
| Ankara→Van | 248 | %37.1 | %37.1 | 14.9 | +2.2 | +10.8 | %68.5 | 6.7 | 10 |
| İzmir→Trabzon | 248 | %46.4 | %46.4 | 9.8 | +2.2 | +7.1 | %76.5 | 6.3 | 6 |

Öneri yok (sert kısıt yok, beklenen 0): 0. Sapmadan sonra hâlâ riskli nokta kalan rota: 314/689. Kaçınma bedeli medyanı (rüzgâr-optimum rotaya göre): +2.2 %. Hata: 0; ERA5 dışı veriyle dönen: 0 (tabloya girmez).

**Okuma.** "Ek yakıt" önerilen rotanın büyük daireye göre yakıt farkıdır (rüzgâr kazancını da içerir); kaçınmanın saf bedeli "kaçınma bedeli"dir. "Daha ucuz riskli seçenek": seçenekler listesinde önerilenden daha az yakıt yakan ama daha çok riskli nokta bırakan Pareto seçeneği; seçim kuralı riskli nokta sayısını yakıtla takas etmediği için önerilmez (SISTEM_KARTI §3). Rotalar aynı günlerin hava sistemlerini paylaşır, bağımsız örnek değildir; oranlar betimleyicidir, güven aralığı verilmedi. Tek bölge, tek ay, 3 seviyeli küp (FL340–360'ta riski 7 seviyeye göre az gösterir, SISTEM_KARTI §5).

**Yeniden üretim.** JSON'daki commit (`50076fc`) ölçüm anındaki HEAD'dir; araç (`analiz/uyari_orani.py`) aynı dalda sonraki commit'te eklendi, rota kodu değişmedi. Komut (WSL, proje kökü, ağsız): `EK_HAVA_DURUMU_KLASORU=/yok ERA5_UCUS_KLASORU=/yok turbulans-uyari-orani --cikti <klasör>`; süre rota başına ~0,5 sn.

Çıktılar sertifikalı EDR değildir; sistem operasyonel karar aracı değil, karar destek aracıdır.
