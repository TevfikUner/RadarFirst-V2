# GEFS fizibilite notu (F2)

15 Ekim 2026. Amaç: "GEFS olasılığı" maddesine ölçülmüş bir boyut vermek. Bu not
bir tahmin ürünü önermez; GEFS olasılığı F1 doğrulama karnesi olmadan ürünleşmez.

## Erişim

| Konu | Durum |
|---|---|
| Kaynak | AWS Open Data, `noaa-gefs-pds` (us-east-1), NOAA NODD |
| Hesap | Gerekmez (anonim HTTPS / S3) |
| Lisans | "NOAA data disseminated through NODD are open to the public and can be used as desired"; atıf istenir, NOAA ile ilişki ya da onay ima edilemez |
| Hız sınırı | Kayıt sayfasında yazılı sınır yok. Yine de tek seferde tek indirme ve gecelik bütçe uygulanmalı |
| UCAR THREDDS | `grib/NCEP/GEFS/catalog.xml` 404 döndü (15 Eki); canlı GFS'in yolu GEFS için kullanılamıyor |
| NOMADS | Kontrol edilmedi |

## Ürün

- 0,5° `pgrb2ap5`: UGRD/VGRD 200, 250, 300 hPa ve TMP 200, 250 hPa. TMP 300 hPa
  yalnız `pgrb2bp5` dosyasında. 0,25° `pgrb2sp25` bu seviyeleri içermiyor.
- Üyeler: `gec00` (kontrol) ve `gep01`–`gep30`; 3 saatlik adımlar, günde 4 döngü.
- S3 uzaysal alt küme yapmaz. `.idx` dosyasındaki bayt aralıklarıyla yalnız gereken
  GRIB2 mesajları alınır, ama her mesaj küreseldir. Koridor kesiti indirmeden sonra yapılır.

## Ölçüm (tek indirme)

Döngü 2026-10-14 00Z, adım f006, üye `gep01`. 6 HTTP Range isteğiyle 9 mesaj (u, v, t ×
200/250/300 hPa):

| Ölçü | Değer |
|---|---|
| İndirilen | 1.375.279 bayt (küresel, 3 × 361 × 720) |
| Türkiye kutusu (36–42°K, 26–45°D; `CANLI_ISITMA_KUTUSU`) | 3 × 13 × 39 ızgara, u/v/t float32 = 18.252 bayt |

Ölçüm değil, çarpım:

- Bir adım, 31 üye: ~42,6 MB indirme, Türkiye kesiti ~0,57 MB.
- ~2 saatlik bir uçuş 1–2 adıma düşer: ~43–85 MB indirme.

## Sınırlar

- Çözünürlük 0,5° ve 3 saat; ERA5 0,25° ve 1 saat. TI1'in yatay türevleri kabalaşır.
  Bu farkın TI1 dağılımına etkisi ölçülmedi.
- Günlük veri bütçesi (~500 MB, gece işi) ile birlikte düşünülmeli. Döngü başına tek bir
  adım bile bütçenin yaklaşık %9'u eder.
- Üye olasılığı (riskli üye oranı) doğrulanmış bir olasılık değildir. Kalibrasyonu F1
  karnesiyle ölçülmeden sunulmaz.

## Slayt için tek cümle

GEFS: 31 üye, 0,5°; bir tahmin adımı ~43 MB indirme, Türkiye kesiti ~0,6 MB (15 Ekim 2026 ölçümü).
