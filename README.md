# Türbülans Radar Projesi — Geliştirilmiş Sürüm

## Ne değişti?

| Eski | Yeni |
|---|---|
| `edr_hesaplama.py` ve `interaktif_harita.py`'de iki farklı, keyfi katsayılı EDR formülü | `turbulans_indeksleri.py`: Ellrod TI1 indeksi (Ellrod & Knapp, 1992) — havacılık meteorolojisinde CAT tahmini için gerçekten kullanılan yöntem |
| `trino_baglanti.py`'de şifre düz metin kod içinde | `kimlik_dogrulama.py` + `.env`: kimlik bilgileri ortam değişkeninden okunuyor, `.gitignore`'da korunuyor |
| `kucuk_simulasyon.py`: `np.linspace` ile UYDURULMUŞ rota | `veri_yukleme.py`: `flights_data4` üzerinden **uçuş numarasından (callsign) gerçek rota** çekiliyor |
| Sabit tek nokta sorgusu, koordinat filtresi | `ucus_numarasi_ile_rota_cek()`: callsign → icao24 → state_vectors_data4 zinciri |
| Statik harita, tek zaman anı | `harita.py`: `TimestampedGeoJson` ile zaman kaydırıcılı animasyon, gerçek uçuş bilgisi popup'ları, lejant |
| Basınç/irtifa birim karışıklığı | `birim_donusumleri.py`: ISA barometrik formülüyle metre ↔ hPa dönüşümü |

## Dosya yapısı

```
config.py                 -> sabitler, eşik değerleri
kimlik_dogrulama.py        -> .env'den güvenli kimlik bilgisi okuma
.env.example                -> kopyalanacak şifre şablonu
birim_donusumleri.py       -> irtifa <-> basınç dönüşümleri
turbulans_indeksleri.py    -> Ellrod TI1 hesabı + EDR-proxy ölçekleme
veri_yukleme.py             -> NetCDF yükleme + OpenSky/Trino sorguları
eslestirme.py                -> uçuş rotası <-> hava durumu grid eşleştirme
harita.py                    -> zaman kaydırıcılı Folium haritası
main.py                      -> uçtan uca çalıştırma
```

## Kullanım

```bash
pip install -r requirements.txt
cp .env.example .env          # sonra .env içine kendi OpenSky bilgilerini yaz
python main.py THY1234 2019-01-01
```

## Bilinmesi gerekenler / sınırlamalar

- **TI1/EDR proxy, sertifikalı bir EDR değeri değildir.** ERA5 benzeri ~25-30 km
  çözünürlüklü reanaliz verisinden hesaplanan bir türbülans olasılık göstergesidir.
  Gerçek operasyonel kullanım için PIREP/AMDAR gözlemleriyle kalibre edilmesi gerekir.
- `flights_data4` tablosunda `callsign` alanı 8 karakter, boşlukla doldurulmuş
  (padded) saklanır; eşleştirme bunu otomatik yapıyor.
- Yatay deformasyon hesabı için veri kübünün ilgili zaman dilimindeki tüm
  enlem/boylam grid'ine ihtiyaç var (tek nokta yetmiyor) — `eslestirme.py`
  bunu `differentiate()` ile grid üzerinde hesaplayıp sonra noktaya en yakın
  hücreyi okuyor.
- Bu ortamda `ocak_2019_turbulans.nc` dosyası ve OpenSky ağ bağlantısı
  mevcut olmadığı için kod, yalnızca birim/matematik fonksiyonları (numpy)
  seviyesinde test edildi; `xarray`/`trino` gerektiren kısımlar sözdizimi
  (syntax) düzeyinde doğrulandı. Kendi ortamında `.nc` dosyanla çalıştırıp
  kontrol etmen gerekiyor.

## Sonraki adımlar için fikirler

- Deformasyon/kayma hesabını tüm grid üzerinde vektörel olarak önceden hesaplayıp
  `.sel()` ile hızlandırmak (şu an her rota noktası için yeniden hesaplanıyor).
- Richardson sayısı gibi ek kararlılık indeksleri ekleyip TI1 ile birleştirmek.
- Gerçek PIREP verisiyle karşılaştırıp `EDR_PROXY_OLCEKLENDIRME_KATSAYISI`'nı kalibre etmek.
