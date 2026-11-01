# Demo veri paketi

Kimlik bilgisi ve ağ gerektirmeden sistemi uçtan uca göstermek için depoya
konmuş küçük, türetilmiş gerçek veri. Kullanımı: README "Beş dakikada çalıştır".

| Dosya | İçerik | Kaynak | Boyut |
|---|---|---|---|
| `opensky_onbellek/THY322_2019-01-15.parquet` | THY322 uçuşunun 1614 state vector'ü (2019-01-15 19:39–21:11 UTC, İstanbul'dan doğuya) | OpenSky Network (Trino `state_vectors_data4`) | ~60 KB |
| `era5/era5_THY322_2019-01-15.nc` | u, v, t; 300/250/200 hPa; 2019-01-15 18–23 UTC; 38.25–43.5°K, 26.75–46.5°D; 0.25°, saatlik | Copernicus CDS, ERA5 basınç seviyeleri | ~230 KB |
| `era5/era5_THY4QR_2026-10-25.nc` | u, v, t; 300/250/200 hPa; 2026-10-25 11–17 UTC; 36.5–47°K, 8.5°B–33.75°D (THY4QR İstanbul → Madrid rotasının ±400 km'si); 0.25°, saatlik | Copernicus CDS, ERA5 basınç seviyeleri | ~880 KB |
| `sigmet/sigmetler_2026-10-25_istanbul_madrid.json` | 19 uluslararası SIGMET (TURB, TS, ICE); 25 Ekim 11–17 UTC penceresinde aynı kutuyla kesişenlerin tamamı | AWC `isigmet`, o gün `sigmetler` tablosuna alınmış, değiştirilmemiş | ~28 KB |

SHA-256:

```
0e3f124fde03529b6ec87e23b7459bb57a7a400d6a938822ba0699eaa21e4633  era5/era5_THY322_2019-01-15.nc
a5e89567272f6e183635fd2e11fd7b2c1c9aba48834a96daceb6569153ca28ef  era5/era5_THY4QR_2026-10-25.nc
f9da4e3e51e122623cd05915154ea55533f00afea297d50a650d40cb870b2f89  opensky_onbellek/THY322_2019-01-15.parquet
ad0f643d3054dc3ab02380d3e71a145324a373b58ce30131c391f05ad14937f6  sigmet/sigmetler_2026-10-25_istanbul_madrid.json
```

## Nasıl üretildi

- Rota: `turbulans-analiz THY322 2019-01-15` çalıştırmasının OpenSky rota önbelleği
  (`veri/opensky_onbellegi.py`); değiştirilmedi.
- ERA5 dilimi: aynı çalıştırmada `veri/era5_saglayici.py`'nin CDS'ten indirdiği
  uçuşa özel dilim (kutu rotanın ±2°'si, zaman ±1 saat); değiştirilmedi. Yerel
  Ocak 2019 küpüyle bit düzeyinde aynı olduğu doğrulandı.
- THY4QR ERA5 kutusu (1 Kasım 2026): `CdsEra5Saglayici(basinc_seviyeleri_hpa=(300, 250, 200))` ile tek CDS
  isteği; kutu rota kaçınma koridorunu (±400 km) kapsayacak kadar geniş. Uçuş izi pakette yok (yalnız rota
  simülasyonu senaryosu); analiz sonuçları `docs/sonuclar/2026-11-01_guncel_vaka/`.
- SIGMET'ler: geliştirme veritabanının `sigmetler` tablosundan `id` ve `alinma_zamani` dışındaki sütunlar.
  İrtifa bandı boş gelen LYBA U03/U04'ün bandı ham metinden (`FL290/380`, `FL260/380`) okunmuş haliyle.

## Sistem nasıl kullanır

`config.DEMO_VERI_KLASORU` (varsayılan `demo`, boş bırakılırsa kapalı):

- `demo/era5/*.nc` diğer yerel ERA5 küpleriyle birlikte taranır; yalnızca
  kapsadığı bölge/zaman için seçilir.
- `demo/opensky_onbellek/` asıl rota önbelleğinde olmayan uçuşlar için salt
  okunur yedektir.
- `demo/sigmet/*.json` yalnız `DEMO_SIGMET_FIKSTURU_YUKLE=true` iken (`.env.demo`) API açılışında
  `demo_arsiv` kaynağıyla yüklenir; rota bulgusu bunların canlı uyarı olmadığını yazar, saklama süresiyle
  silinmez. Üretim ayar denetimi bu bayrak açıkken ağa açılmayı reddeder.

## Sınırlar ve lisans

- Analiz için tek uçuş (THY322), 3 basınç seviyesi. Uçuşun tırmanış/alçalış noktaları
  150–350 hPa dışında kaldığı için kapsam dışıdır (NaN); bu beklenen davranıştır.
- PIREP içermez; SIGMET yalnız 25 Ekim senaryosu için arşiv mesajıdır; ML modeli ve bağımsız kanıt bu paketle gösterilemez.
- OpenSky verisi yalnızca araştırma ve ticari olmayan kullanım içindir; ERA5
  CC BY 4.0'dır. Atıf metinleri: `docs/VERI_KAYNAKLARI_VE_LISANSLAR.md`.
- Çıktılar sertifikalı EDR değildir; sistem karar destek aracıdır.
