# 16 Ekim 2026: ERA5 → canlı GFS TI1 eşik eşlemesi

ML sonuç paketi değildir; tek bir ek analizdir (kaynak incelemesi Fikir 2). Sayılar
[`esik_esleme.md`](esik_esleme.md) ve [`esik_esleme.json`](esik_esleme.json) dosyalarında.

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
- `TI1_ESIK_ORTA_SIDDETLI_GFS` şimdilik **boş** bırakıldı. 18 Ekim nihai paketinde ERA5
  eşiği yeniden seçileceği için GFS eşdeğeri o eşikle yeniden hesaplanıp birlikte
  ayarlanacak (bkz. `docs/YAPILACAKLAR.md`).
