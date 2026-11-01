# Güncel vaka: THY4QR İstanbul → Madrid, 25 Ekim 2026 (keşifsel)

Üretim: 2026-11-01. Komite için güncel, ADS-B kapsamı tam olan vaka (YAPILACAKLAR A2). Uçuş izi OpenSky,
hava ERA5 (CDS), SIGMET'ler AWC `isigmet` arşivi (`sigmetler` tablosu, 30 Eylül'den beri birikiyor).

## 1. SIGMET ↔ TI1 (`turbulans-sigmet-ti1`)

[`SIGMET_TI1.md`](SIGMET_TI1.md), [`sigmet_ti1.json`](sigmet_ti1.json). Komut:

```bash
turbulans-sigmet-ti1 --ucus THY4QR:2026-10-25 --ucus SXS6MG:2026-10-25 --ucus THY5HS:2026-10-24 \
  --cikti docs/sonuclar/2026-11-01_guncel_vaka
```

- THY4QR, 12:06–15:30 geçerli Belgrad TURB SIGMET'inin (LYBA U04, FL260–380) içinden geçti: içerideki 730
  noktanın %100'ünde TI1 7e-7 eşiğinin üstünde, dışarıdaki 10.450 noktada %12,8.
- SXS6MG (Londra → Antalya) aynı SIGMET'te 677 noktanın %96,8'i, dışarıda %37,5. THY5HS'nin rotasında SIGMET yok.
- Elle yapılan 31 Ekim kontrolüyle aynı sayılar çıktı. Aracın farkı irtifa bandını da uygulaması: LYBA U03/U04'ün
  bandı AWC alanında boştu, 1 Kasım'dan beri ham metinden okunuyor (`turbulans-sigmet --irtifa-onar`, 445 eski kayıt).

Sınırlar: SIGMET gözlem değil uyarıdır; ardışık noktalar bağımsız değildir; iki uçuş ve tek SIGMET. Oranlar
isabet ölçüsü değildir. Bu bir tutarlılık gözlemidir, doğrulama değildir.

## 2. OOD kapısı (`turbulans-ml-destek --ucus`)

[`ood_THY4QR.json`](ood_THY4QR.json). Aktif model `2c1740de7171…`, küp uçuşa özel 7 seviyeli ERA5 dilimi
(`era5_20261025T10_8f7c71760d.nc`):

```bash
turbulans-ml-destek --ucus THY4QR:2026-10-25 --kup era5_ucus_verisi/era5_20261025T10_8f7c71760d.nc
```

11.180 noktanın 723'ünde (%6,5) en az bir özellik eğitim desteğinin dışında; bu noktalarda ML çıktısı verilmez.
Hepsinde `yatay_deformasyon` dışarıda (sonra `ti1_indeksi` 466, `ti2_indeksi` 171). Karşılaştırma için 29 Ekim
ölçümü: Türkiye rastgele seyir noktaları %2,9, ABD altın test günleri %4,2 (`2026-10-29_ood_kapisi/`).
Kapının içinde kalmak Avrupa'da becerinin kanıtı değildir; Avrupa'da beceri ölçülmedi.

## 3. Demo senaryosu

Senaryo seçicide "İstanbul → Madrid (25 Ekim 2026), gerçek arşiv SIGMET'leri". Hava verisi
`demo/era5/era5_THY4QR_2026-10-25.nc` (rota ±400 km, 300/250/200 hPa, 11–17 UTC). SIGMET'ler
`demo/sigmet/sigmetler_2026-10-25_istanbul_madrid.json`: o pencerede kutuyla kesişen 19 gerçek mesajın tamamı
(seçme yapılmadı). FL340, 11:45 UTC kalkışta 15'i rota kısıtına giriyor ve koridorda hepsinden kaçan rota yok:
sistem ÖNERİ YOK der. Yalnız LYBA yüklenseydi 140 km yanal sapma bulunuyordu; bu yüzden fikstür seçilmedi.

Çıktılar sertifikalı EDR değildir; sistem operasyonel karar aracı değil, karar destek aracıdır.
