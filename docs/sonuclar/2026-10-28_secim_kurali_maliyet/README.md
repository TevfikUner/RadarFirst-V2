# Uyarı oranı / alarm yorgunluğu ölçümü

Üretim: 2026-10-28T16:29:25.625274+00:00 · commit `f30cf0076132c06578c90abc63100ec17fc3155d` · TI1 risk eşiği 7.0e-07 · 31 gün (2019-01-01'ten) × saatler [0, 6, 12, 18] × 6 şehir çifti × FL [350, 370]. Veri yerel ERA5 küpü (3 seviye, Türkiye, Ocak 2019); canlı veri, otomatik indirme, SIGMET ve kısıtlı saha kapalı (yalnız TI1 etkisi ölçülür). A320, koridor modu, maliyet seçim kuralı (yakıt + riskli dakika × 5 dk × dakikalık yakıt; bedel kalibre edilmedi).

| Grup | Rota | Normal rotada riskli nokta olan | Sapma önerilen | Riskli süre medyanı (dk, riskli rotalarda) | Sapmada ek yakıt medyanı (%) | Sapmada ek yakıt p90 (%) | Sapmalarda daha ucuz riskli seçenek bulunan | O seçeneğin yakıt avantajı medyanı (puan) | O seçenekte kalan riskli nokta medyanı |
|---|---|---|---|---|---|---|---|---|---|
| **Tümü** | 1488 | %46.3 | %46.0 | 12.4 | +2.2 | +8.3 | %72.8 | 6.1 | 8 |
| FL350 | 744 | %52.2 | %51.6 | 14.3 | +0.9 | +7.6 | %54.9 | 7.9 | 8 |
| FL370 | 744 | %40.5 | %40.5 | 10.6 | +3.3 | +8.9 | %95.7 | 4.9 | 6 |
| İstanbul→Van | 248 | %46.8 | %46.8 | 12.3 | +1.4 | +8.1 | %71.6 | 5.2 | 5 |
| İzmir→Erzurum | 248 | %48.8 | %48.4 | 13.1 | +2.2 | +8.3 | %69.2 | 6.7 | 6 |
| Antalya→Kars | 248 | %52.4 | %52.4 | 12.3 | +2.2 | +11.1 | %77.7 | 6.0 | 7 |
| İstanbul→Gaziantep | 248 | %46.4 | %46.4 | 13.0 | +2.5 | +7.8 | %78.3 | 6.3 | 8 |
| Ankara→Van | 248 | %37.1 | %36.7 | 14.9 | +2.2 | +8.3 | %64.8 | 5.7 | 10 |
| İzmir→Trabzon | 248 | %46.4 | %45.6 | 9.8 | +2.1 | +6.7 | %73.5 | 6.2 | 6 |

Öneri yok (sert kısıt yok, beklenen 0): 0. Sapmadan sonra hâlâ riskli nokta kalan rota: 312/685. Kaçınma bedeli medyanı (rüzgâr-optimum rotaya göre): +2.2 %. Hata: 0; ERA5 dışı veriyle dönen: 0 (tabloya girmez).

**Okuma.** "Ek yakıt" önerilen rotanın büyük daireye göre yakıt farkıdır (rüzgâr kazancını da içerir); kaçınmanın saf bedeli "kaçınma bedeli"dir. "Daha ucuz riskli seçenek": seçenekler listesinde önerilenden daha az yakıt yakan ama daha çok riskli nokta bırakan Pareto seçeneği; maliyet kuralı bu seçeneği riskli dakika bedeli yakıt avantajından büyük olduğu için önermedi. Rotalar aynı günlerin hava sistemlerini paylaşır, bağımsız örnek değildir; oranlar betimleyicidir, güven aralığı verilmedi. Tek bölge, tek ay, 3 seviyeli küp (FL340–360'ta riski 7 seviyeye göre az gösterir, SISTEM_KARTI §5).

Çıktılar sertifikalı EDR değildir; sistem operasyonel karar aracı değil, karar destek aracıdır.

**Varsayılanla karşılaştırma (#1b–c, AÇIK ANLAŞMAZLIK A1).** Aynı 1.488 senaryo, aynı küp; yalnız seçim kuralı
değişti (`ROTA_SECIM_KURALI=maliyet`, `ROTA_RISKLI_DAKIKA_BEDELI_DK=5`). Önerilen rota 28 senaryoda (%1,9) değişti;
bunların 4'ünde büyük daireye dönüldü. Değişen rotalarda yakıt kazancı medyanı 6,1 puan (en çok 25,3), önerilen
rotadaki riskli süre artışı medyanı 0,0 dk (en çok +2,7 dk); 1.488 rotanın önerilen rotalarındaki toplam riskli süre
3.790,8 dk'dan 3,6 dk azaldı (maliyet kuralı nokta sayısı yerine riskli dakikayı tartar). 5 dk bedel kalibre edilmedi;
daha küçük bedel daha çok riskli rota önerir. Varsayılan değişmedi; kural kullanıcı tercihidir. Karşılaştırma iki
JSON'un `kayitlar` alanından (çift, FL, kalkış eşleşmesiyle) hesaplandı. Komut: `EK_HAVA_DURUMU_KLASORU=/yok
ERA5_UCUS_KLASORU=/yok python -m turbulans_radar.analiz.uyari_orani --secim-kurali maliyet --riskli-dakika-bedeli 5
--cikti <klasör>`; JSON'daki commit `f30cf00` kural kodunu içerir.
