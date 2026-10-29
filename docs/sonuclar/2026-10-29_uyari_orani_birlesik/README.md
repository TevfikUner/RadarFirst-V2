# Uyarı oranı / alarm yorgunluğu ölçümü

Üretim: 2026-10-29T12:10:57.009637+00:00 · commit `af2bab8ee41ce7196ad01fedf9c31948a20038bb` · TI1 risk eşiği 7.0e-07 · 31 gün (2019-01-01'ten) × saatler [0, 6, 12, 18] × 6 şehir çifti × FL [350, 370]. Veri yerel ERA5 küpü (3 seviye, Türkiye, Ocak 2019); canlı veri, otomatik indirme, SIGMET ve kısıtlı saha kapalı (yalnız TI1 etkisi ölçülür). A320, koridor modu, varsayılan seçim kuralı (önce riskli nokta sayısı, sonra yakıt).

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

## İkinci sütun: birleşik EDR ≥ 0.0757 (protokol §12)

Uyarı = büyük daire rotasında eşiği aşan en az bir nokta. Sapma kararı TI1'le kalır; son sütun TI1 sapmalarında büyük daire → A* rotasında birleşik EDR uyarısı olan rota oranıdır.

| Grup | Rota | TI1 uyarısı | Birleşik EDR uyarısı | İkisi de | Yalnız TI1 | Yalnız birleşik | Hiçbiri | TI1 sapmasında birleşik uyarı (BD → A*) |
|---|---|---|---|---|---|---|---|---|
| **Tümü** | 1488 | %46.3 | %36.1 | %36.0 | %10.3 | %0.1 | %53.6 | %77.6 → %39.5 |
| FL350 | 744 | %52.2 | %41.4 | %41.4 | %10.8 | %0.0 | %47.8 | %79.4 → %36.3 |
| FL370 | 744 | %40.5 | %30.8 | %30.5 | %9.9 | %0.3 | %59.3 | %75.4 → %43.5 |

Eşik ABD ERA5 eğitim günlerinde TI1 7e-7 ile aynı kuralla seçildi (`2026-10-29_birlesik_esik`); Türkiye'de beceri ölçülmedi. Birleşik EDR TI1'i de içerir, iki sütun bağımsız değildir.

Çıktılar sertifikalı EDR değildir; sistem operasyonel karar aracı değil, karar destek aracıdır.
