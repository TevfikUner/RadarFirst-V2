# Demo veri paketi

Kimlik bilgisi ve ağ gerektirmeden sistemi uçtan uca göstermek için depoya
konmuş küçük, türetilmiş gerçek veri. Kullanımı: README "Beş dakikada çalıştır".

| Dosya | İçerik | Kaynak | Boyut |
|---|---|---|---|
| `opensky_onbellek/THY322_2019-01-15.parquet` | THY322 uçuşunun 1614 state vector'ü (2019-01-15 19:39–21:11 UTC, İstanbul'dan doğuya) | OpenSky Network (Trino `state_vectors_data4`) | ~60 KB |
| `era5/era5_THY322_2019-01-15.nc` | u, v, t; 300/250/200 hPa; 2019-01-15 18–23 UTC; 38.25–43.5°K, 26.75–46.5°D; 0.25°, saatlik | Copernicus CDS, ERA5 basınç seviyeleri | ~230 KB |

SHA-256:

```
0e3f124fde03529b6ec87e23b7459bb57a7a400d6a938822ba0699eaa21e4633  era5/era5_THY322_2019-01-15.nc
f9da4e3e51e122623cd05915154ea55533f00afea297d50a650d40cb870b2f89  opensky_onbellek/THY322_2019-01-15.parquet
```

## Nasıl üretildi

- Rota: `turbulans-analiz THY322 2019-01-15` çalıştırmasının OpenSky rota önbelleği
  (`veri/opensky_onbellegi.py`); değiştirilmedi.
- ERA5 dilimi: aynı çalıştırmada `veri/era5_saglayici.py`'nin CDS'ten indirdiği
  uçuşa özel dilim (kutu rotanın ±2°'si, zaman ±1 saat); değiştirilmedi. Yerel
  Ocak 2019 küpüyle bit düzeyinde aynı olduğu doğrulandı.

## Sistem nasıl kullanır

`config.DEMO_VERI_KLASORU` (varsayılan `demo`, boş bırakılırsa kapalı):

- `demo/era5/*.nc` diğer yerel ERA5 küpleriyle birlikte taranır; yalnızca
  kapsadığı bölge/zaman için seçilir.
- `demo/opensky_onbellek/` asıl rota önbelleğinde olmayan uçuşlar için salt
  okunur yedektir.

## Sınırlar ve lisans

- Tek uçuş, tek gün, 3 basınç seviyesi. Uçuşun tırmanış/alçalış noktaları
  150–350 hPa dışında kaldığı için kapsam dışıdır (NaN); bu beklenen davranıştır.
- PIREP ve SIGMET içermez; ML modeli ve bağımsız kanıt bu paketle gösterilemez.
- OpenSky verisi yalnızca araştırma ve ticari olmayan kullanım içindir; ERA5
  CC BY 4.0'dır. Atıf metinleri: `docs/VERI_KAYNAKLARI_VE_LISANSLAR.md`.
- Çıktılar sertifikalı EDR değildir; sistem karar destek aracıdır.
