# Hoca Geri Bildirimi Analizi: Operasyona Yaklaştırma Önerileri

> **Önerilerin kaynağı:** Bu belgede incelenen beş öneri, projenin bir sayfalık
> özetini değerlendiren **Doç. Dr. Fulya Aybek Çetek**'e (Eskişehir Teknik
> Üniversitesi, Havacılık ve Uzay Bilimleri Fakültesi, Hava Trafik Kontrol
> Bölümü; ATM araştırmacısı, hava trafik kontrolörü eğitmeni) aittir. Analiz,
> ölçümler ve yol haritası proje ekibine aittir.

- Proje: Türbülans Radar, Konya Teknik Üniversitesi Bilgisayar Mühendisliği bitirme projesi
- Tarih: 2 Ekim 2026. Bu analiz sırasında kodda değişiklik yapılmadı.
- Sistem sertifikalı EDR üretmez; operasyonel karar aracı değil, karar destek aracıdır.

## Uygulama durumu (2 Ekim 2026)

Bu analizden sonra yol haritası uygulandı. Kod ve testler hazır; gerçek AIP
verisi ve trafik ölçümü sırada.

| Aşama | Öneri | Durum | Commit |
|---|---|---|---|
| A0 | 3, 5: Kapsam ve kullanım zamanı | Tamam: `kapsam`, `planlama_ufku`, `sigmet_ufuk_disi` uyarısı; arayüzde ToC/ToD | 632b5f7 |
| A1 | 2: Saha aktivasyonu | Tamam: NOTAM aralıkları (`aktif_araliklar`) ve AIP haftalık takvimi (`haftalik_takvim`). **AIP ENR 5.1'den 77 saha otomatik alındı** (`turbulans-aip-sahalar`); 8'i belirsiz biçim nedeniyle elle girilecek. | c71bbf8 |
| A2 | 1: ATS yolu / FRA ağı | Tamam: graf tabanlı A*, `arama_uzayi="ats"`, uçuş planı biçiminde özet. **AIP ENR 4.4'ten 611 FRA noktalı ağ otomatik kuruldu** (`turbulans-aip-ats`). Klasik/RNAV yolları (ENR 3.1/3.2) kurulmadı; ATS modu FRA alt sınırının (FL305) altında rota bulamaz. | cde94c9 |
| A3 | 4: Ayırma göstergesi | Tamam: `turbulans-ayirma`. **Gerçek trafikle ölçüm, kullanıcı onayıyla OpenSky sorgusu gerektirir.** | a8c9ecc |

## Doğrulama sonuçları (2 Ekim 2026)

Raporda **[doğrulanmalı]** diye işaretlenen bilgiler birincil kaynaklardan
kontrol edildi:

| Konu | Sonuç | Kaynak |
|---|---|---|
| AIP bölüm numaraları | ATS yolları **ENR 3.1** (klasik) ve **ENR 3.2** (RNAV), önemli noktalar ENR 4.4, P/R/D ENR 5.1, askerî sahalar ENR 5.2, FRA haritası **ENR 6.3**. Önceki "ENR 3" ifadesi böyle düzeltildi. | [AIP Türkiye ENR 0.6](https://www.dhmi.gov.tr/AIPDocuments/LT_ENR_0_6_en.pdf), AIRAC AMDT 03/26 |
| Türkiye'de FRA | **Var.** 27 Kasım 2025'ten beri FL305 ve üzerinde. ENR 4.4 her noktanın FRA rolünü veriyor: giriş, çıkış, ara nokta, varış ve kalkış bağlantısı. Başlangıçta 2025–26 kışında yerel 23:00–05:00 arasında uygulanıyordu; **güncel uygulama saatleri doğrulanmadı.** | [Türkiye Today](https://www.turkiyetoday.com/business/turkiye-launches-free-route-airspace-system-to-shorten-flights-cut-emissions-3210434), [AIP Türkiye ENR 4.4](https://www.dhmi.gov.tr/AIPDocuments/LT_ENR_4_4_en.pdf) (AIRAC AMDT 09/26) |
| Yatay ayırma | Asgari **5 NM** radar ayırması (bazı TMA'larda yaklaşma kontrolünde 3 NM) | [AIP Türkiye ENR 1.6](https://www.dhmi.gov.tr/AIPDocuments/LT_ENR_1_6_en.pdf) §4.1–4.2 |
| Dikey ayırma | FL290–FL410 EUR-RVSM sahası; RVSM onaylı uçaklar arası **1000 ft**, onaysız devlet uçakları gibi durumlarda 2000 ft | [AIP Türkiye ENR 1.8](https://www.dhmi.gov.tr/AIPDocuments/LT_ENR_1_8_en.pdf) §1 |
| SIGMET geçerliliği | En fazla **4 saat**; volkanik kül ve tropikal siklon için **6 saat** | [DWD SIGMET bilgi notu](https://www.dwd.de/EN/ourservices/aviation_lf_09_information_material/sigmet.pdf?__blob=publicationFile&v=1), [ICAO APAC SIGMET Rehberi](https://www.icao.int/sites/default/files/APAC/Documents/edocs/APAC-Regional-SIGMET-Guide-8th-edition-Nov-2020-final.pdf) |
| AIP verisinin yeniden dağıtımı | Doğrulanmadı. İndirilen PDF'ler ve üretilen veri `ats_verisi/` altında yerelde tutulur, depoya konmaz. | — |

Hocamızın verdiği ayırma değerleri AIP ile örtüşüyor. Önemli bir sonuç: Türkiye'de
seyir irtifasında (FL305+) FRA uygulandığı için, mevcut serbest koridor araması
gerçek operasyona hava yolu ağından daha yakın. ATS modu da bu nedenle
klasik/RNAV yolları yerine FRA noktaları üzerinden kuruldu.

İşaretler: **[doğrulanmalı]** = proje ekibinin erişip kontrol edemediği ya da
belleğe dayanan bilgi; rapora ya da koda girmeden önce birincil kaynaktan
(AIP Türkiye, ICAO belgeleri, sağlayıcı sayfası) teyit edilmelidir.

---

## 1. Mevcut rota sisteminin yapısı (Adım 1)

### 1.1 İlgili dosyalar

| Dosya | Görev |
|---|---|
| `src/turbulans_radar/rota/rota_optimizasyonu.py` | Arama uzayı, A*, aday rotalar, yakıt/süre, API yanıtı (`rota_simulasyonu_olustur`) |
| `src/turbulans_radar/rota/risk_katmanlari.py` | Sert/yumuşak kısıt katmanları: `Ti1CezaKatmani`, `PoligonKisitKatmani`, `SigmetKisitKatmani`, `KisitliSahaKatmani` |
| `src/turbulans_radar/veri/sigmet_saglayici.py` | AWC SIGMET çekme, normalize etme, veritabanı (`gecerli_sigmetleri_getir`) |
| `src/turbulans_radar/veri/kisitli_saha_saglayici.py` | P/R/D, çatışma bölgesi, NOTAM'lı geçici kısıt (GeoJSON içe aktarım) |
| `src/turbulans_radar/veri/openaip_saglayici.py` | openAIP'ten R/P sahaları (anahtar gerekir; şu an kurulu değil) |
| `src/turbulans_radar/veri/veri_saglayicilari.py` | Hava küpü seçimi: yerel ERA5 ya da canlı NOAA GFS |
| `src/turbulans_radar/api/api_servisi.py` | `POST /api/v1/simulasyon/rota` |
| `web/ucus_simulasyonu.html` | 3B simülasyon; "Uçuş sırasında yeniden hesapla" düğmesi |

### 1.2 Arama uzayı: grid mi, graf mı?

**Büyük daire etrafında kurulan yanal bir koridor grafı.** Serbest bir
enlem/boylam ızgarası ya da hava yolu ağı değildir (`_YanalIzgara`,
`_yanal_izgara_dugum_konumlari`, `_komsu_dugumler`):

- Kalkış ve varış arası büyük daire rotası `ROTA_SIMULASYONU_NOKTA_SAYISI` = 41 noktaya bölünür.
- Her ara noktada rotaya dik yönde ±k × aralık km kaydırılmış düğümler bulunur.
  Aralık en fazla 20 km (`ROTA_YANAL_IZGARA_KM`), toplam sapma en fazla 400 km
  (`ROTA_MAKS_YANAL_SAPMA_KM`).
- Kenarlar yalnızca i'den i+1'e gider. Bacak başına yanal kayma, büyük daireye
  göre en fazla 30° açıyla sınırlıdır (`ROTA_MAKS_SAPMA_ACISI_DERECE`). Uçlar
  sabit olduğu için sapma kalkış ve varışa doğru daralır.
- Başlangıç ve bitiş noktaları kullanıcının girdiği serbest koordinatlardır;
  waypoint, havalimanı ya da prosedür kavramı yoktur.

### 1.3 Boyutlar: 2B, 3B, zaman

| Boyut | Durum | Kanıt |
|---|---|---|
| Yatay | A* 2B koridor grafında arar | `_a_yildiz_ile_rota_ara` |
| İrtifa | A* sabit irtifada arar. Dikey alternatif, **tüm rotanın** bir üst ya da bir alt basınç seviyesine taşınmasıdır; tırmanma ve alçalma için kaba bir yakıt/süre bedeli eklenir (1500 ft/dk, tırmanmada +%50, alçalmada −%30 yakıt). Rota içinde kademeli seviye değişimi yoktur. Seviyeler hava küpündeki basınç seviyelerinden gelir (ör. 250 hPa ≈ 34.000 ft); yasal uçuş seviyesi tablosu ve yarım daire kuralı kullanılmaz. | `_en_yakin_komsu_basinc_seviyeleri`, `_irtifa_degisimi_maliyeti` |
| Zaman | Her düğüme rüzgarsız TAS ile nominal varış zamanı atanır. Hava verisi ve kısıtların geçerliliği bu zamana göre okunur. Zaman belirsizliği payı, geçen sürenin %30'u + 5 dk'dır. Seçilen rota rüzgarla yeniden zamanlanır; çıktı, zaman damgalı nokta listesidir (basit bir 4D yörünge). | `_a_yildiz_ile_rota_ara`, `_rotayi_zamanla`, `ROTA_ZAMAN_BELIRSIZLIK_*` |

### 1.4 Maliyet fonksiyonu

- **Kenar maliyeti (saniye):** mesafe / yer hızı. Yer hızı = TAS + rüzgarın rota
  yönündeki bileşeni (ERA5 ya da GFS u, v); alt sınır TAS'ın %20'si.
- **Yumuşak kısıt:** Ellrod TI1 ≥ 8×10⁻⁷ s⁻² olan düğüme girişte 6 saatlik sanal
  ceza (`TURBULANS_CEZASI_SANIYE`).
- **Sert kısıt:** SIGMET ve kısıtlı sahaların içindeki düğümler ve bunları kesen
  kenarlar graftan çıkarılır. Kontrol 4 boyutludur: poligon, irtifa bandı, varış
  zamanındaki geçerlilik ve SIGMET'in hareket yönü/hızıyla kaydırılması.
- **Sezgisel:** kalan büyük daire mesafesi / (1,8 × TAS). Hiçbir zaman fazla
  tahmin etmez (admissible), bu yüzden A* çözümü bu grafta optimaldir.
- **Aday seçimi:** yanal A* rotası ile bir üst/alt seviye adayları arasından önce
  sert kısıtı sağlayanlar, sonra türbülansı tamamen atlatanlar, en son en az
  yakıtlı olan seçilir. Kaçınılacak risk yoksa rota büyük daireyle aynı kalır;
  sert kısıtı sağlayan aday yoksa öneri verilmez.
- **Uçak modeli:** Dört tip için sabit TAS ve yakıt akışı. Yaklaşık değerlerdir,
  üretici performans verisi değildir.

### 1.5 Hava ve SIGMET verisinin modele girişi

- **Rüzgar ve TI1:** Rota bölgesini kapsayan yerel ERA5 küpü seçilir. Uçuş
  şimdiden en fazla 48 saat önce ya da 120 saat sonraysa canlı NOAA GFS küpü
  indirilir (`CANLI_GECMIS_SAAT`, `CANLI_TAHMIN_UFKU_SAAT`). GFS küpü 6 saat
  boyunca yeniden kullanılır. Kapsam dışı bölgelerde rüzgar ve TI1 uydurulmaz;
  rota rüzgarsız hesaplanır ve yanıtta bu belirtilir.
- **SIGMET:** API zamanlayıcısı AWC'den (ABD iç ve uluslararası SIGMET'ler,
  Ankara FIR dahil) periyodik çeker ve veritabanına yazar. Rota hesabı, uçuş zaman
  penceresiyle kesişen ve kaçınılacak tehlike türündeki (TURB, MTW, TS, VA, TC…)
  SIGMET'leri sert kısıt yapar.
- **Kısıtlı sahalar:** GeoJSON (`turbulans-kisitli-saha ice-aktar`,
  `POST /api/v1/kisitli-sahalar`) ya da openAIP. Paketle gelen örnek veri (Suriye
  ve Irak) Natural Earth ülke sınırından türetilmiştir, resmi sınır değildir.

---

## 2. Öneri bazında durum tespiti (Adım 2)

### Özet tablo

| # | Öneri | Mevcut durum | Uygunluk (bitirme kapsamı) | İş yükü |
|---|---|---|---|---|
| 1 | ATS yolları / FRA üzerinden rota | **YOK** | Basitleştirilmiş hali uygun: seçili senaryolar için elle hazırlanmış küçük bir hava yolu alt ağı | Orta–Yüksek (asıl yük veri hazırlığı) |
| 2 | P/R/D ve aktif askerî sahalar | **KISMEN VAR** | Uygun | Düşük–Orta |
| 3 | Kapsam: yalnız seyir safhası | **KISMEN VAR** (fiilen seyir; açıkça beyan edilmemiş) | Uygun | Düşük |
| 4 | Diğer trafiklerle ayırma | **YOK** | Tam hali kapsam dışı; yalnızca geçmiş veride "çatışma göstergesi" uygun | Yüksek (tam) / Orta (gösterge) |
| 5 | Kullanım zamanı ve hesaplama süresi | **KISMEN VAR** (süre ölçülü; ufuk ve kullanım beyanı yok) | Uygun | Düşük |

### Öneri 1: ATS yolları / Serbest Rota Sahası (FRA)

**Mevcut durum: YOK.** Arama uzayı büyük daire etrafındaki yanal koridor
grafıdır (§1.2). Waypoint, hava yolu ya da FRA giriş/çıkış noktası kavramı yoktur
(`_YanalIzgara`, `_komsu_dugumler`). Üretilen rota ATC'ye bu haliyle dosyalanabilir
bir uçuş planı rotası değildir.

**İşimize yarayacak altyapı:** Risk katmanları grafa bağlı değildir.
`degerlendir(konumlar, zamanlar, kenarlar, irtifa_m)` herhangi bir düğüm ve kenar
kümesini kabul eder. SIGMET, kısıtlı saha ve TI1 kontrolleri bir hava yolu grafında
da değişmeden kullanılabilir. Aday değerlendirmesi (`_aday`) de herhangi bir
enlem/boylam listesiyle çalışır.

**Uygunluk ve basitleştirilmiş öneri:**
- Tüm Türkiye ağı bitirme süresi için fazla büyük; veri çıkarımı ayrı bir proje.
- Öneri: demo senaryolarının geçtiği 2–3 koridor için (ör. İstanbul–Ankara–Doğu
  Anadolu; Malatya–güneydoğu) elle hazırlanmış küçük bir ağ kurmak.
  - Düğümler: önemli noktalar (adı + koordinat).
  - Kenarlar: hava yolu segmentleri; varsa alt/üst seviye ve yön bilgisi.
- Graf üzerinde genel bir A* çalıştırmak; kenar maliyeti ve risk katmanları aynı kalır.
- Mevcut koridor grafı "serbest rota (karşılaştırma)" modu olarak kalır. Böylece
  "ATS yolu kısıtının bedeli" de ölçülebilir; bu, raporda ilginç bir sonuç olur.
- FRA uygulanan bir sahada giriş/çıkış noktaları arası doğrudan bacak (DCT) kenarları eklenir.

**İş yükü: Orta–Yüksek.** Kod kısmı orta (genel graf A* + veri yükleyici + API
parametresi, birkaç gün). Asıl yük veri hazırlığı: PDF tablolarından koordinat ve
segment çıkarmak, elle kontrol etmek.

**Veri gereksinimi:**
- **AIP Türkiye (DHMİ):** ATS yolları ENR 3.1 (klasik) ve 3.2 (RNAV) bölümlerinde, önemli noktaların
  koordinatları ENR 4.4'te **[doğrulanmalı: Türkiye AIP'sindeki bölüm numaraları
  ve güncel AIRAC sürümü]**. Ücretsiz görüntülenebilir PDF; makinece okunur bir
  sürüm olup olmadığı **[doğrulanmalı]**. Elle ya da yarı otomatik çıkarım gerekir.
  Çıkarılan verinin depoda yeniden dağıtılıp dağıtılamayacağı **[doğrulanmalı]**;
  şüpheli durumda yalnızca yerel dosya olarak tutulur, depoya konmaz.
- **Türkiye'de FRA uygulaması** olup olmadığı ve sınırları **[doğrulanmalı]**.
  Uygulanmıyorsa FRA kısmı yalnızca "senaryo" olarak, açıkça varsayımsal diye işaretlenir.
- **openAIP** hava yolu verisi sunuyor mu **[doğrulanmalı]**. Mevcut entegrasyonumuz
  yalnızca hava sahası çekiyor.
- **Ticari navigasyon veritabanları** (ARINC 424): lisanslı; kapsam dışı.

**Mimariye etkisi:**
- Yeni modüller: `rota/hava_yolu_agi.py` (graf + A*), `veri/ats_yollari.py`
  (yükleyici ve doğrulama; GeoJSON/CSV).
- `rota_simulasyonu_olustur` içinde "arama uzayı" seçimi.
- API'de isteğe bağlı `arama_uzayi` alanı (varsayılan mevcut davranış; geriye uyumlu).
- Web formunda nokta adıyla giriş.
- **Kırılabilecekler:** Rota backtest sonuçları (`dogrulama/rota_backtest.py`) yeni
  modda farklı çıkar; mevcut testler varsayılan modu koruduğu sürece etkilenmez.
  Uç noktalar ağ dışındaysa en yakın ağ noktasına bağlanma kuralı gerekir; bu bir
  tasarım kararı ve test kapsamı ister.

### Öneri 2: Yasak, tahditli ve aktif askerî sahalar

**Mevcut durum: KISMEN VAR.**
- **Model hazır:** `KisitliSahaKatmani` (`PoligonKisitKatmani`) yatay poligon, alt/üst
  seviye (`taban_ft`/`tavan_ft`) ve geçerlilik aralığıyla (`gecerlilik_baslangic`/
  `gecerlilik_bitis`) 4 boyutlu sert kısıt uygular. Bacağın poligonu kesmesi de
  kontrol edilir.
  - Saha türleri: `SAHA_TURLERI` = CATISMA, YASAK, KISITLI, TEHLIKELI, GECICI.
  - NOTAM'lı geçici kısıt için içe aktarım ucu var: `POST /api/v1/kisitli-sahalar?kaynak=notam`.
- **Eksikler:**
  1. **Resmi veri yok.** Paketteki örnek veri ülke sınırıdır. openAIP entegrasyonu
     var ama API anahtarı kurulu değil; varsayılan olarak yalnızca R ve P türleri
     alınıyor, D, TRA ve TSA alınmıyor (`OPENAIP_SAHA_TURLERI` = "1,3").
  2. **Yinelenen aktivasyon takvimi yok.** Bir kayıt tek bir geçerlilik aralığı
     taşıyor. "Hafta içi 06:00–15:00" gibi yinelenen saatler ancak her aralık ayrı
     kayıt olarak girilerek modellenebilir.
  3. **NOTAM'lar otomatik çekilmiyor.** Uç nokta GeoJSON bekliyor; NOTAM metnini
     poligona çeviren bir ayrıştırıcı yok. openAIP sağlayıcısı, NOTAM ile
     etkinleşen sahaları NOTAM verisi olmadığı için sürekli etkin sayıyor
     (muhafazakâr varsayım).
  4. **Alt/üst sınır referansları:** openAIP'te GND referanslı üst sınır, arazi
     yüksekliği bilinmediği için `OPENAIP_AGL_UST_PAYI_FT` kadar yükseltiliyor.
     AIP'ten gelen FL ve AMSL değerleri için birim dönüşümü belgelenmeli.

**Uygunluk: Uygun.** Mekanizma zaten var; iş, veri ve takvim modeli.

**Önerilen sürüm:**
- Senaryo bölgesi için AIP ENR 5.1 (P/R/D) **[doğrulanmalı: bölüm ve AIRAC]**
  sahalarını elle GeoJSON'a geçirmek ve mevcut içe aktarımla yüklemek.
- Askerî tatbikat ve eğitim sahaları (ENR 5.2 **[doğrulanmalı]**) için "aktif zaman
  aralıkları" alanı: bir sahaya birden çok aralık ya da basit bir haftalık takvim.
- Demo ve test için birkaç NOTAM aktivasyonunu elle girilmiş GeoJSON olarak yüklemek.
- Otomatik NOTAM entegrasyonu kapsam dışı (aşağıya bakın).

**İş yükü: Düşük–Orta.** Takvim alanı ve testleri 2–3 gün; veri hazırlığı sahaların
sayısına bağlı.

**Veri gereksinimi:**
- AIP Türkiye ENR 5.x: ücretsiz PDF, elle çıkarım **[doğrulanmalı]**.
- openAIP: ücretsiz anahtar; CC BY-NC 4.0, yani ticari olmayan kullanım.
- NOTAM akışı: Türkiye NOTAM'larına ücretsiz ve programla erişim **[doğrulanmalı]**.
  EUROCONTROL EAD ve benzeri servisler kayıt ya da sözleşme isteyebilir.

**Mimariye etkisi:**
- `kisitli_saha_saglayici.py` (GeoJSON şeması: yeni `aktif_araliklar` alanı).
- `models.KisitliHavaSahasi` ve bir Alembic göçü.
- `PoligonKisitKatmani._aktif_maskesi` (birden çok aralık).
- **Geriye uyumluluk:** Tek aralıklı mevcut kayıtlar aynen çalışmalı; bunu
  mevcut testler korur.

### Öneri 3: Kapsam: tüm uçuş mu, düz uçuş mu?

**Mevcut durum: KISMEN VAR.**
- Rota optimizasyonu **fiilen yalnızca seyir safhasıdır**. Uç noktalar seyir
  irtifasında kabul edilir; kalkış, tırmanış, alçalış, SID/STAR ve yaklaşma yoktur
  (§1.3).
- Uçuş analizi (`analiz/ucus_analizi.py`) ise ADS-B izinin tamamını alır. Ancak
  TI1 yalnızca hava küpünün basınç seviyeleri içinde hesaplanır (150–350 hPa,
  yaklaşık FL265 üstü); altındaki noktalar "veri yok" kalır.
- ML eğitim verisi de seyir irtifasıdır (FL280–FL420; `ML_MIN_IRTIFA_FT`).
- **Eksik olan:** Bu kapsam belgelerde ve API yanıtında açıkça "en-route/cruise"
  diye beyan edilmiyor. Kullanıcı, kalkış ve varış noktası olarak havalimanı
  koordinatı girince sistem bunu seyirdeymiş gibi işliyor.

**Uygunluk: Uygun.** Hocamızın önerisi (yalnızca düz uçuş) mevcut tasarımla örtüşüyor.

**Önerilen iş:**
- Kapsamı README, sistem kartı ve API açıklamasında açıkça yazmak.
- Uç noktaları "seyre giriş (ToC) / seyirden çıkış (ToD) noktası" diye adlandırmak.
- Yanıta `kapsam: "seyir"` alanı eklemek.
- İsteğe bağlı: Havalimanı koordinatı girilirse ToC/ToD için kaba bir mesafe payı
  bırakıldığını yanıtta belirtmek.

**İş yükü: Düşük.** Belge ve küçük bir API alanı; 1 gün.

**Veri gereksinimi:** Yok.

**Mimariye etkisi:** Yanıt şeması (`semalar.RotaSimulasyonuYaniti`), `openapi.json`,
web etiketleri. Kırıcı değişiklik yok.

### Öneri 4: Diğer trafiklerle emniyet ayırması

**Mevcut durum: YOK.**
- Önerilen rota başka uçaklara göre hiç kontrol edilmiyor.
- OpenSky verisi yalnızca **geçmiş** uçuş izleri için kullanılıyor (Trino;
  `veri/veri_yukleme.py`). Canlı trafik akışı yok.
- Uygulanmış zaman damgalı 4D yörünge (§1.3) iyi bir başlangıç noktası.

**Ayırma minimaları:** Hocamızın verdiği değerler (seyirde yatay yaklaşık 5 NM,
RVSM sahasında dikey 1000 ft) bu belgede **varsayım** olarak alınmıştır. Uygulanacak
kesin değerler ilgili hava sahası ve gözetim türüne göre ICAO Doc 4444 ve AIP
Türkiye'den **[doğrulanmalı]**.

**Uygunluk:**
- **Tam hali kapsam dışı olmalı.** Yeni rotanın ayırmayı garanti etmesi, diğer
  uçakların **gelecekteki** yörüngelerinin bilinmesini ister.
  - Uçuş öncesi planlamada (saatler önce) bu bilgi yok. Ayırma, uçuş sırasında
    ATC'nin taktik sorumluluğudur.
  - Taktik kullanımda bile, diğer uçakların niyetini bilmeden hareketli engel
    modeli (sabit hızla ileri izdüşüm) yalnızca kısa ufukta anlamlıdır.
  - Ayrıca OpenSky'ın canlı verisi ticari olmayan araştırma içindir ve istek kotası
    vardır; sık sorgu hesabın askıya alınmasına yol açabilir. Proje kuralımız gereği
    kota aşan bir tasarım kabul edilmez.
- **Uygun basitleştirilmiş sürüm: "çatışma göstergesi" (conflict probe).**
  - Yalnızca **geçmiş veri ve backtest modunda** çalışır. Önerilen rota, aynı zaman
    penceresinde gerçekten uçmuş trafiğin OpenSky izleriyle karşılaştırılır.
  - Varsayımsal minimaların ihlal edildiği noktalar raporlanır.
  - Rota bunları kaçınma kısıtı olarak kullanmaz; yalnızca bilgi verir.
  - Böylece "ATS yollarına uymayan serbest rota, gerçek trafikle kaç kez çakışırdı?"
    sorusu ölçülebilir.

**İş yükü:** Tam hali (hareketli engelli 4D arama) **Yüksek**: zaman boyutlu graf,
yörünge izdüşümü, belirsizlik. Gösterge sürümü **Orta**: 3–5 gün; ADS-B verisi
önbellekten okunursa ek sorgu gerekmez.

**Veri gereksinimi:**
- OpenSky Trino, geçmiş state vector'ler: ücretsiz araştırma hesabı.
- Mevcut korumalar (tek eşzamanlı sorgu, günlük 400 tavanı) korunmalı; bölge × saat
  başına tek sorgu yapılıp önbelleğe yazılmalı.
- OpenSky canlı REST API'sinin kredi ve kota kuralları **[doğrulanmalı]**; canlı
  kullanım bu yüzden önerilmez.

**Mimariye etkisi:**
- Yeni `dogrulama/ayirma_gostergesi.py`.
- `rota_backtest.py` sonucuna ek alan.
- Rota A*'ı değişmez.
- Sanal PIREP doğrulamasındaki "PIREP çevresi iz" sorgusuna benzer, bölge ve zaman
  sınırlı bir sorgu kullanılır.

### Öneri 5: Kullanım zamanı: planlama mı, taktik mi?

**Mevcut durum: KISMEN VAR.**
- **(a) Hesaplama süresi** ölçüldü (§3). Ayrıca `docs/PERFORMANS_RAPORU.md`'de
  eşzamanlı yük altındaki API gecikmeleri var.
- **(b) Planlama ufku** kodda veri pencereleriyle belirleniyor ama hiçbir yerde
  beyan edilmiyor:
  - **Rüzgar ve TI1:** Canlı GFS tahmini uçuş zamanı şimdiden en fazla 120 saat
    sonrası için kullanılabilir (`CANLI_TAHMIN_UFKU_SAAT`). Yerel ERA5 yalnızca
    geçmiş içindir (reanaliz; yaklaşık 5 gün gecikmeli).
  - **SIGMET:** Rota, uçuş zaman penceresiyle kesişen SIGMET'leri kullanıyor
    (`gecerli_sigmetleri_getir`). SIGMET'ler kısa geçerlilikli olduğu için birkaç
    saatten ileri bir uçuşta henüz yayımlanmış SIGMET olmayabilir. Geçerlilik
    genelde en fazla 4 saat, VA/TC için daha uzun **[doğrulanmalı: ICAO Annex 3]**.
  - **Bulunan eksik:** Böyle bir durumda yanıt `aktif_sigmet_yok` diyor. "Uçuş
    zamanı için henüz SIGMET yayımlanmamış olabilir" ayrımı yapılmıyor. Bu,
    kullanıcıyı yanıltabilecek bir eksik ve kolay düzeltilebilir.
  - **Kısıtlı sahalar:** AIP ve NOTAM'la önceden bilinir; ufku sınırlamaz.
- **Taktik kullanım:** Arayüzde "Uçuş sırasında yeniden hesapla" düğmesi var
  (`web/ucus_simulasyonu.html`, `ucusSirasindaYenidenHesapla`). Uçağın o anki
  simüle konumundan aynı hedefe gerçek bir yeniden hesaplama yapıyor. Ancak:
  - Gerçek uçak konumu girdisi yok.
  - Hava verisi yerel ve statik ERA5 olduğunda sonuç çoğu zaman aynı çıkıyor.

**Uygunluk: Uygun.**

**Önerilen konumlandırma:**
- **Birincil:** Uçuş öncesi stratejik/ön-taktik planlama. Dispeçer; uçuştan 24–2
  saat önce GFS tahmini TI1 ve bilinen P/R/D/NOTAM ile, kalkıştan önceki son 4
  saatte ise ek olarak geçerli SIGMET'lerle değerlendirir.
- **İkincil (gösterim amaçlı):** Taktik yeniden planlama.
- Saat aralıkları önerimizdir; havayolu harekât pratiğine göre **[doğrulanmalı]**.

**Önerilen iş:**
- Yanıta `planlama_ufku` bilgisi eklemek: veri kaynağı ve geçerlilik.
- Uçuş zamanı SIGMET ufkunun ötesindeyse açık bir uyarı.
- Belgede kullanım zamanını beyan etmek.

**İş yükü: Düşük.** 1–2 gün.

**Veri gereksinimi:** Yok (mevcut GFS ve SIGMET).

**Mimariye etkisi:**
- `_sigmet_katmanini_hazirla` ve `_bulgulari_olustur` (yeni bulgu kodu), yanıt şeması.
- Kırıcı değişiklik yok.

---

## 3. Hesaplama süresi ölçümü (Adım 3)

**Ortam:** Intel Core i7-13700H (20 mantıksal çekirdek) dizüstü, WSL2, Python 3.14.
Tek süreç, ağsız: yerel ERA5 küpleri, canlı GFS kapalı. SIGMET ve saha listeleri
doğrudan verildi, veritabanı okunmadı. Her senaryo 6 kez çalıştırıldı; ilki "soğuk"
(küp okuma dahil), kalan 5'in medyanı ve en yükseği "sıcak". "A* süresi" yalnızca
graf aramasıdır; toplam süre aday rotaların rüzgarla zamanlanmasını ve TI1/kısıt
kontrollerini de içerir.

| Senaryo | Veri | Mesafe | Sonuç | Soğuk | Sıcak medyan (en yüksek) | A* medyan |
|---|---|---|---|---|---|---|
| S1 İstanbul→Antalya, FL280, 05.01.2019 12:00 | ERA5 | 482 km | 1 riskli nokta; yanal kaçınma | 807 ms | 202 ms (206) | 32 ms |
| S2 İzmir→Van, FL340, 05.01.2019 12:00 | ERA5 | 1408 km | Risk yok; büyük daire | 66 ms | 67 ms (70) | çağrılmadı |
| S3 İstanbul→Doğu Anadolu, FL360, 15.01.2019 20:00 | ERA5 | 1221 km | 4 riskli nokta; 53 km yanal | 299 ms | 254 ms (262) | 32 ms |
| S4 Malatya→Musul, FL360, örnek kısıtlı sahalar | ERA5 | 481 km | Sahaya 11 ihlal → 0; yanal | 259 ms | 258 ms (265) | 38 ms |
| S5 İstanbul→New York, FL370 | Kapsam dışı (rüzgarsız) | 8056 km | Risk yok | 21 ms | 21 ms (22) | çağrılmadı |
| S6 İzmir→Van, FL340 + **sentetik** TURB SIGMET | ERA5 | 1408 km | SIGMET 7 ihlal → 0; 20 km yanal | 265 ms | 265 ms (268) | 41 ms |
| S7 İstanbul→New York, FL370 + **sentetik** TURB SIGMET | Rüzgarsız | 8056 km | SIGMET 3 ihlal → 0; 260 km yanal | 111 ms | 78 ms (95) | 43 ms |

S6 ve S7'deki SIGMET'ler yalnızca A* süresini ölçmek için konmuş sentetik test
poligonlarıdır (FIR kodu "TEST"); gerçek bir hava durumu iddiası taşımaz.

**Ek ölçümler (depodaki belgelerden):**
- **API üzerinden rota:** p50 262 ms (tek istek). 16 eşzamanlı istekte p95 3,95 sn
  (4 API süreci) ve 5,45 sn (1 süreç). Kaynak: `docs/PERFORMANS_RAPORU.md`,
  1 Ekim 2026.
- **Hava verisi hazır değilse süre ağa bağlıdır:**
  - Türkiye bölgesi için canlı GFS küpü yaklaşık 15 sn (`docs/SISTEM_KARTI.md`,
    26 Eylül 2026); aynı küp 6 saat yeniden kullanılır.
  - Uçuşa özel ERA5 dilimi CDS'ten tipik olarak yaklaşık 40 sn (ADR 0001).

**Sonuç:** Veri hazırken bir rota kararı 0,02–0,27 saniyede (sıcak) hesaplanıyor;
A* aramasının payı 30–45 ms. Hesaplama süresi hem planlama hem taktik kullanım
için darboğaz değildir. Belirleyici olan veri tazeliği ve ilk veri indirmesidir
(saniyeler–dakika).

**Tekrar üretim:** Ölçüm betiği `rota_simulasyonu_olustur`'u doğrudan çağırıp
`_a_yildiz_ile_rota_ara`'yı zamanlayan küçük bir Python betiğidir; depoya
eklenmedi. İstenirse `turbulans-performans` aracına "rota senaryoları" bölümü
olarak eklenebilir.

---

## 4. Yol haritası (Adım 4)

### Öncelik ve bağımlılıklar

- **Saha kısıtları (2), graf yapısına (1) bağlı değil.** Risk katmanları
  `konumlar` + `kenarlar` alan grafa bağımsız bileşenlerdir (§2, Öneri 1). Bu yüzden
  önce 2 yapılabilir; 1 geldiğinde aynı katmanlar yeni grafta kullanılır.
- **3 ve 5** hemen yapılabilir, düşük maliyetli ve savunmada en çok sorulacak
  sorulara cevap verir.
- **4 (gösterge),** 4D yörüngeye ve geçmiş trafik verisine dayanır. 1'den sonra
  yapılırsa "ATS rotası vs serbest rota" karşılaştırmasına girdi olur.

### Aşamalar

| Aşama | İçerik | Etkilenen dosyalar | Test | Kaba süre |
|---|---|---|---|---|
| **A0: Kapsam ve kullanım beyanı** (Öneri 3, 5) | Yanıta `kapsam: "seyir"` ve `planlama_ufku` alanları; SIGMET ufkunun ötesindeki uçuş için bulgu ("henüz SIGMET yayımlanmamış olabilir"); README, sistem kartı ve API açıklaması | `rota/rota_optimizasyonu.py` (`_sigmet_katmanini_hazirla`, `_bulgulari_olustur`), `api/semalar.py`, `openapi.json`, `web/ucus_simulasyonu.html`, belgeler | Birim: ufuk dışı uçuşta bulgu üretilir, ufuk içinde üretilmez; mevcut rota testleri değişmeden geçer | 1–2 gün |
| **A1: Saha modeli** (Öneri 2) | Sahaya birden çok aktif aralık (ya da haftalık takvim); senaryo bölgesi için AIP ENR 5.x'ten elle hazırlanmış GeoJSON; birkaç örnek NOTAM aktivasyonu; openAIP türlerine D/TRA/TSA eklemek isteğe bağlı | `veri/kisitli_saha_saglayici.py`, `depo/models.py` + göç, `rota/risk_katmanlari.py` (`_aktif_maskesi`), yeni veri dosyası (yerel; lisansa göre) | Birim: aralık dışında saha yok sayılır, içinde yasak; geriye uyumluluk; tarayıcı: kısıtlı saha senaryosu | 2–3 gün + veri hazırlığı |
| **A2: Hava yolu ağı** (Öneri 1, basitleştirilmiş) | Seçili koridorlar için önemli nokta ve hava yolu segment dosyası; genel graf A*; `arama_uzayi` parametresi ("koridor" varsayılan, "ats"); uç noktaları ağa bağlama kuralı; ATS ve serbest rota bedeli karşılaştırması; varsa FRA DCT kenarları | yeni `rota/hava_yolu_agi.py`, yeni `veri/ats_yollari.py`, `rota/rota_optimizasyonu.py` (strateji seçimi), `api/semalar.py`, web formu | Birim: küçük sentetik ağda bilinen en kısa yol; SIGMET'li kenar atlanır; gerçek veriyle demo senaryosu; mevcut testler varsayılan modda aynı | 1–2 hafta (veri çıkarımı dahil) |
| **A3: Ayırma göstergesi** (Öneri 4, yalnızca gösterge) | Backtest modunda önerilen rota ile aynı zaman penceresindeki geçmiş OpenSky trafiği arasında varsayımsal minima (5 NM / 1000 ft) ihlallerini raporlamak; rota kararına girmez | yeni `dogrulama/ayirma_gostergesi.py`, `dogrulama/rota_backtest.py`, belgeler | Birim: sentetik iki yörüngede ihlal sayısı; OpenSky sorgusu yalnızca kullanıcı onayıyla, kota içinde, önbellekli | 3–5 gün |

Süreler tek kişi için kaba tahmindir; veri hazırlığı (AIP'ten çıkarım) en belirsiz kalemdir.

### Kapsam dışı bırakılması önerilenler (gerekçeli)

- **Ayırmayı garanti eden 4D arama (hareketli engelli):** Uçuş öncesinde diğer
  trafiğin gelecekteki yörüngesi bilinmez. Ayırma, ATC'nin taktik sorumluluğudur.
  Canlı ADS-B ile kısa ufuklu bir izdüşüm de lisans (OpenSky ticari olmayan
  kullanım) ve kota riski taşır. Gösterge sürümü (A3) bu boşluğu dürüstçe ölçer.
- **Otomatik NOTAM ayrıştırma:** NOTAM metinlerinden poligon ve seviye çıkarmak
  ayrı bir doğal dil/format işleme problemidir; ücretsiz ve programla erişilebilir
  bir Türkiye NOTAM akışı **[doğrulanmalı]**. Elle girilmiş örnek aktivasyonlar
  mekanizmayı göstermeye yeter.
- **Tüm Türkiye ATS ağı ve SID/STAR:** Veri hacmi bitirme süresini aşar. Kapsam,
  hocamızın önerisiyle uyumlu olarak seyir safhasıdır.
- **Yasal uçuş seviyesi tablosu ve rota içi kademeli tırmanış:** A2 ile birlikte
  gündeme gelir. Şimdilik "irtifa alternatifleri basınç seviyesinden türetilir"
  sınırlaması belgede açıkça yazılı kalmalı.

---

## 5. Hocamıza yanıt için kısa özet

> Değerli önerileriniz için teşekkür ederiz. Durumu kısaca özetliyoruz:
>
> **Kapsam:** Rota optimizasyonu yalnızca seyir (en-route) safhasını kapsıyor;
> kalkış, tırmanış, alçalış ve terminal prosedürleri kapsam dışında. Önerinizle
> uyumlu olarak bunu sistemde ve raporda açıkça beyan edeceğiz.
>
> **Kullanım zamanı:** Sistemi öncelikle uçuş öncesi planlama aracı olarak
> konumlandırıyoruz. Uçuştan 120 saate kadar önce NOAA GFS tahminine dayalı
> türbülans göstergesi ve bilinen kısıtlı sahalarla, kalkıştan önceki son saatlerde
> ise ek olarak geçerli SIGMET'lerle değerlendirme yapılabiliyor. Uçuş zamanı
> SIGMET geçerlilik ufkunun ötesindeyse sistemin bunu açıkça belirtmesini
> sağlayacağız. Uçuş sırasında yeniden hesaplama mekanizması var ama şimdilik
> gösterim amaçlı.
>
> **Hesaplama süresi:** Hava verisi hazırken bir rota kararı dizüstü bir
> bilgisayarda 0,02–0,27 saniyede hesaplanıyor (A* aramasının payı 30–45 ms; 480 ile
> 8000 km arası 7 senaryo). Belirleyici olan veri indirme süresi: canlı GFS bölge
> verisi yaklaşık 15 saniye; aynı veri 6 saat yeniden kullanılıyor.
>
> **Diğer öneriler:**
> - Yasak/tahditli sahalar zaten poligon, alt/üst seviye ve geçerlilik aralığıyla
>   modelleniyor. Resmi AIP verisi ve askerî sahaların yinelenen aktivasyon
>   takvimi ekleyeceğiz.
> - ATS yolları için seçili koridorlarda AIP'ten hazırlanmış küçük bir hava yolu
>   ağı üzerinde graf tabanlı A* planlıyoruz.
> - Diğer trafikle ayırmayı, uçuş öncesinde diğer trafiğin yörüngesi bilinmediği
>   ve bu ATC'nin taktik sorumluluğu olduğu için garanti etmeyi hedeflemiyoruz.
>   Bunun yerine geçmiş ADS-B verisiyle önerilen rotanın varsayımsal ayırma
>   minimalarını kaç kez ihlal ederdi sorusunu ölçen bir gösterge eklemeyi öneriyoruz.
