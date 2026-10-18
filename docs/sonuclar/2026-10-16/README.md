# 16 Ekim 2026: ek analizler

ML sonuç paketi değildir. İki ek analiz içerir:

1. ERA5 → canlı GFS TI1 eşik eşlemesi (kaynak incelemesi Fikir 2):
   [`esik_esleme.md`](esik_esleme.md), [`esik_esleme.json`](esik_esleme.json).
2. Rota ayrıklaştırma yakınsama çalışması (Fikir 5):
   [`ayriklastirma.md`](ayriklastirma.md), [`ayriklastirma.json`](ayriklastirma.json).

# 2. Rota ayrıklaştırma yakınsaması

**Soru:** Varsayılan 41 ara nokta ve ≤ 20 km yanal ızgara sonucu ne kadar etkiliyor?
(Yöntem örneği: NTNU-IMT/weather-routing-discretisation.)

**Yöntem:** `turbulans-performans rota`'nın 5 kapsam içi senaryosu (S1–S4, S6), yerel ERA5
(Ocak 2019), canlı veri kapalı. Ara nokta {21, 41, 81} × ızgara {10, 20, 40 km}. Referans en
ince ayar (81 nokta, 10 km). Komut: `turbulans-ayriklastirma --cikti docs/sonuclar/2026-10-16`
(22 sn).

**Sonuç:**

| Senaryo | Strateji | Varsayılan − referans süre | Varsayılan − referans yakıt |
|---|---|---|---|
| S1 İstanbul→Antalya | yanal | +0,10 dk (%0,25) | +4,7 kg (%0,24) |
| S2 İzmir→Van | yok | −0,00 dk | −0,1 kg |
| S3 İstanbul→Doğu Anadolu | irtifa yukarı | −0,01 dk | −0,4 kg |
| S4 Malatya→Musul + kısıtlı saha | yanal | 0,00 dk | 0,0 kg |
| S6 İzmir→Van + sentetik SIGMET | yanal | −0,42 dk (%0,45) | −18,0 kg (%0,44) |

- Varsayılan ayar beş senaryonun hepsinde referansla aynı stratejiyi seçti; süre ve yakıt
  farkı en fazla %0,45.
- 21 nokta yetersiz: S4'te 10 km ızgarayla kısıtlı sahadan kaçınma kararı kayboldu (strateji
  "yok"), S6'da fark −2,3 dk'ya çıktı. Nedeni ayrıca incelenmedi (tahmin: seyrek noktalar
  sahanın kenarını farklı örnekliyor).
- En duyarlı durum SIGMET'ten kaçınma (S6): ızgara inceldikçe rota poligonun etrafından
  biraz daha geniş dolaşıyor, sonuç %0,5 içinde.
- 81 nokta hesap süresini yaklaşık 1,5–1,8 kat artırıyor (tek ölçüm).

**Karar:** Varsayılan (41 nokta, 20 km) korunur. Sonuçlar ayrıklaştırmaya %0,5 düzeyinde
duyarlı; bu fark, raporlanan yakıt tasarruflarının yanında küçük ama sıfır değil.

# 1. ERA5 → canlı GFS TI1 eşik eşlemesi

## Soru

`TI1_ESIK_ORTA_SIDDETLI` (7e-7) ERA5'te (7 seviye, 25–50 hPa katman) seçildi. Canlı rotalar
ise GFS ile (200/250/300 hPa, 50 hPa katman) hesaplanıyor. Ellrod ve Knapp (1992, Tablo 1)
eşiğin modelden modele 2–3 kat değiştiğini gösterdi. Aynı eşik GFS'te aynı sıklıkta mı
"riskli" der?

## Yöntem

9–11 Ekim 2026, 00/06/12/18 UTC (12 analiz saati). Kutu 30–50°K, 10–50°D, 0,5° adım,
FL300–380. GFS: THREDDS koşu bazlı veri kümesinden analiz (f000). ERA5: CDS. TI1 her iki
kaynakta rota kodunun eşleştirmesiyle (`rotayi_hava_durumuyla_eslestir`) aynı noktalarda
hesaplandı. ERA5'te 7e-7'nin yüzdeliği bulundu, GFS dağılımının aynı yüzdeliği eşdeğer eşik
olarak alındı. Güven aralığı: analiz saatleri üzerinden bootstrap (1000 tekrar). İndirme
13 MB (GFS 12 istek, CDS 3 istek). Komut:

```
turbulans-esik-esleme --baslangic 2026-10-09T00:00Z --bitis 2026-10-11T18:00Z --cikti docs/sonuclar/2026-10-16
```

Veri `ciktilar/esik_esleme/` içinde önbellekte durur; `--esik` ile yeni bir ERA5 eşiği
indirme yapmadan yeniden eşlenir.

## Sonuç

- Aynı 7e-7 eşiğinde GFS noktaların **%11,1**'ini, ERA5 **%8,5**'ini riskli sayıyor.
- GFS eşdeğer eşiği **8,30e-7** (%95 GA 7,96e-7 – 8,67e-7). Aralık 7e-7'yi içermiyor.
- Seviyeye bağımlılık güçlü: FL300'de 1,07e-6, FL380'de 6,77e-7.
- Nokta bazlı sıra uyumu orta (Spearman 0,56). Bu, iki kaynağın riskli alanların konumunda
  da tam uyuşmadığını gösterir; eşik eşlemesi bunu düzeltmez.

Beklenti tersineydi: daha kalın GFS katmanının düşey kaymayı küçülteceği, dolayısıyla
GFS TI1'inin daha düşük çıkacağı düşünülmüştü. Ölçüm tersini gösterdi. Olası açıklama
(tahmin, test edilmedi): GFS'in doğal çözünürlüğü (~13 km) ERA5'inkinden (~31 km) ince
olduğu için yatay deformasyon daha keskin çıkıyor.

## Sınırlar ve karar

- Tek bölge, tek mevsim, 3 gün. Gün içi ilişki nedeniyle etkin örneklem 12 saattir.
- Eşleme iki kaynağı tutarlı yapar; GFS'in türbülans becerisini göstermez (F1 doğrulama
  karnesi).
- `TI1_ESIK_ORTA_SIDDETLI_GFS` 16 Ekim'de boş bırakıldı. 18 Ekim nihai paketinde ERA5 eşiği
  değişmedi (7e-7, 1-SE bandının içinde), bu yüzden eşleme yeniden çalıştırılmadı ve 8,3e-7
  `.env`'ye yazıldı (18 Ekim).
