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
turbulans_indeksleri.py    -> Ellrod TI1 + Richardson sayısı hesabı + EDR-proxy ölçekleme
veri_yukleme.py             -> NetCDF yükleme + OpenSky/Trino sorguları
eslestirme.py                -> uçuş rotası <-> hava durumu grid eşleştirme (vektörel)
harita.py                    -> zaman kaydırıcılı Folium haritası
main.py                      -> uçtan uca çalıştırma
ornek_ucus_bul.py           -> OpenSky'da kayıtlı gerçek callsign'ları listeler
veri_kontrol.py              -> veri küpü çözünürlüğünü / TI1 çeşitliliğini kontrol eder
kimlik_kontrol.py           -> .env'in doğru okunduğunu kontrol eder
kalibrasyon.py               -> gerçek PIREP/AMDAR verisiyle EDR ölçekleme katsayısını kalibre eder
toplu_analiz.py              -> bir CSV listesindeki birden fazla uçuşu sırayla analiz eder
web_arayuzu.py               -> tarayıcıdan kullanılabilir basit arayüz (Streamlit)
hata_yardimcisi.py           -> ham Python hatalarını anlaşılır Türkçe mesaja çevirir
veri_indirme.py              -> ERA5 verisi otomatik indirme ALTYAPISI (bkz. aşağıdaki uyarı)
konsol_kurulumu.py           -> Windows konsolunda Türkçe/özel karakterlerin çökmesini önler
tests/                        -> pytest birim testleri (ağ/veri gerektirmeyen kısımlar için)
```

## Kullanım

```bash
pip install -r requirements.txt
cp .env.example .env          # sonra .env içine kendi OpenSky bilgilerini yaz
python main.py THY1234 2019-01-01
```

Her script `--help` ile kullanım bilgisi verir, örn. `python main.py --help`,
`python ornek_ucus_bul.py --help`.

### Web arayüzü

Terminal yerine tarayıcıdan kullanmak için:

```bash
streamlit run web_arayuzu.py
```

Uçuş numarası ve tarihi bir kutuya yazıp "Analiz Et"e basman yeterli; sonuç
tablosu ve zaman kaydırıcılı harita direkt sayfada görünür. Arkada hâlâ aynı
`main.py` mantığı (gerçek OpenSky sorgusu + hava durumu eşleştirmesi) çalışır
-- bu sadece görsel bir ön yüz.

### Birden fazla uçuşu birden analiz etmek

```bash
python toplu_analiz.py ucuslar.csv
```

`ucuslar.csv` en az `ucus_numarasi` ve `tarih` sütunlarını içermeli. Her uçuş
kendi CSV/HTML çıktısını normal şekilde üretir; script ayrıca hepsinin kısa
bir özetini (`toplu_analiz_ozeti.csv`) tek tabloda toplar. Bir uçuşta hata
olursa diğerlerinin analizi durmaz.

### ERA5 verisini otomatik indirme -- ŞU AN AKTİF DEĞİL

`veri_indirme.py`, ileride hava durumu verisini elle indirip klasöre koyma
işini otomatikleştirmek için hazırlanmış bir ALTYAPI dosyasıdır. **Şu an
gerçek bir indirme yapmaz** -- OpenSky ve Copernicus gibi servisler çok
büyük/geniş istek gönderen hesapları geçici ya da kalıcı olarak
engelleyebildiği (rate limit / ban) için, bilinçli olarak sadece "kuru
deneme" (ne isteneceğini gösterip göndermeme) modunda çalışır. Kod
içindeki sabit güvenlik sınırları (en fazla 10x10 derecelik bölge, en fazla
3 günlük veri) aşan hiçbir istek, gerçekten indirmeye çalışılsa bile
gönderilmez. Gerçek indirmeyi açmak (`--gercekten-indir`) için ayrıca
`pip install cdsapi` ve bir Copernicus hesabı/`~/.cdsapirc` gerekir --
bunlar bu projede kurulu değildir ve kullanıcı açıkça onay vermeden devreye
girmez.

### Testleri çalıştırmak

```bash
pip install -r requirements-dev.txt
python -m pytest tests/
```

`tests/test_eslestirme.py`, gerçek `ocak_2019_turbulans.nc` dosyasını
bulamazsa otomatik olarak atlanır (dosya `.gitignore`'da, repoya dahil
değildir).

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
- Proje gerçek bir uçuşla (OpenSky/Trino bağlantısı + gerçek `.nc` verisi)
  uçtan uca test edildi ve çalıştığı doğrulandı.

## Sonraki adımlar için fikirler

- ~~Deformasyon/kayma hesabını tüm grid üzerinde vektörel olarak önceden
  hesaplayıp `.sel()` ile hızlandırmak.~~ Yapıldı: `eslestirme.py` artık tüm
  rotayı tek seferde vektörel eşleştiriyor (gerçek veriyle ölçülen kazanç:
  ~250x, bkz. modülün başındaki not).
- ~~Richardson sayısı gibi ek kararlılık indeksleri ekleyip TI1 ile
  birleştirmek.~~ Yapıldı: `turbulans_indeksleri.richardson_sayisi_hesapla`
  bilerek TI1'e keyfi bir katsayıyla karıştırılmadan, ayrı bir
  `richardson_sayisi`/`dinamik_kararsizlik` sütunu olarak ekleniyor.
- ~~Gerçek PIREP verisiyle karşılaştırıp ölçekleme katsayısını kalibre
  etmek.~~ Kısmen yapıldı: `kalibrasyon.py` bunun için bir araç sağlıyor,
  ama gerçek PIREP/AMDAR gözlem verisi bu depoda YOK -- kalibrasyonu
  çalıştırmak için kullanıcının kendi gözlem CSV'sini sağlaması gerekiyor.
- Trino/OpenSky sorgularının başarısız senaryoları (rate limit, OAuth2
  zaman aşımı) için yeniden deneme (retry) mantığı eklemek.
- ~~Terminal yerine tarayıcıdan kullanılabilir basit bir arayüz.~~ Yapıldı:
  `web_arayuzu.py` (`streamlit run web_arayuzu.py`).
- ~~Birden fazla uçuşu tek seferde analiz edebilmek.~~ Yapıldı:
  `toplu_analiz.py`.
- ~~Hata mesajlarını daha anlaşılır hale getirmek.~~ Yapıldı:
  `hata_yardimcisi.py`, `main.py`/`toplu_analiz.py`/`web_arayuzu.py`
  tarafından kullanılıyor.
- ~~Hava durumu verisini otomatik indirme.~~ Sadece ALTYAPISI hazırlandı
  (`veri_indirme.py`) -- rate-limit/ban riski nedeniyle gerçek indirme
  bilinçli olarak kapalı, bkz. yukarıdaki "ERA5 verisini otomatik indirme"
  bölümü.
