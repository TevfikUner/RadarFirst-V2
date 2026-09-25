# Değişiklik Geçmişi

Bu proje semantik sürümleme kullanmıyor (henüz tek bir sürekli geliştirilen
sürüm) -- bu yüzden değişiklikler tarih/sürüm numarası yerine tema başına
gruplanmıştır, en yeni en üstte.

## Mermaid mimari diyagramı + OpenAPI/Postman export + silme hız sınırlaması + CI kapsam raporu

- README'deki ASCII mimari diyagramının yanına, GitHub'da otomatik render
  olan bir Mermaid akış şeması eklendi (ML sınıflandırıcı + SIGMET
  doğrulama akışları dahil).
- **`openapi_disa_aktar.py`**: `openapi.json` (canlı `/openapi.json` ile
  AYNI) ve harici bir dönüştürücü gerektirmeyen, sadece OpenAPI şemasından
  üretilen bir Postman koleksiyonu (`turbulans_radar.postman_collection.json`)
  yazar -- sunucuyu ayağa kaldırmadan API'yi keşfetmek için. İkisi de
  repoya dahil (küçük, ucuza yeniden üretilebilir).
- **`DELETE /api/v1/ucuslar*`** (tekli ve toplu silme), `/analiz/*` ile
  AYNI bellek-içi hız sınırlama desenini (kendi ayrı penceresiyle) kullanır
  -- art arda çok sayıda silme isteğine karşı.
- **CI**: `pytest-cov` eklendi, her çalıştırmada terminal + XML (artifact
  olarak yüklenir) + GitHub Actions iş özetinde (`$GITHUB_STEP_SUMMARY`)
  Markdown tablo olarak kapsam raporu üretiliyor. `pyproject.toml`'a
  `[tool.coverage.*]` yapılandırması eklendi (netCDF4'ün derlenmiş
  uzantısının sahte bir `src/` yolunu kapsam dışına almak dahil).

## Test kapsamı: ml_egitimi.py/pirep_kalibrasyon_verisi_uret.py birim testleri + kalıcı Playwright testleri + performans testi

- **`tests/test_ml_egitimi.py`**: `modelleri_egit_ve_karsilastir`/`en_iyi_
  modeli_sec_ve_kaydet` sentetik (hızlı, gerçek PIREP/ERA5 gerektirmeyen)
  veriyle test edildi; `veriyi_hazirla` gerçek veriyle (yoksa atlanır).
- **`tests/test_pirep_kalibrasyon_verisi_uret.py`**: `kalibrasyon_verisini_
  hazirla`'nın ürettiği `pirep_edr` değerlerinin doğru [0,1] aralığında
  olduğunu gerçek PIREP+ERA5 verisiyle doğrular (yoksa atlanır).
- **`tests/conftest.py` + `test_web_harita3d.py` + `test_web_ucus_
  simulasyonu.py`**: daha önce sadece scratchpad'de elle çalıştırılan
  Playwright testleri artık repoda KALICI -- `api_servisi.py`'yi ayrı bir
  alt süreçte canlı ayağa kaldıran paylaşılan bir fixture (`canli_sunucu`)
  üzerinden, gerçek bir uçuşa karşı harita render'ını VE MapLibre/CesiumJS
  hatalarının bir daha geri gelmediğini doğrular. `playwright` paketi
  bilerek `requirements-dev.txt`'ye eklenmedi (CI'de chromium indirmek
  gereksiz) -- kurulu değilse otomatik atlanır.
- **`tests/test_performans.py`**: 55.000 noktalık sentetik bir rota için
  vektörel eşleştirmenin ve veritabanı yazımının makul sürede (30sn/60sn
  gevşek üst sınır) bittiğini doğrular -- amaç kesin bir benchmark değil,
  yanlışlıkla nokta-nokta bir döngüye geri dönme gibi katastrofik bir
  performans regresyonunu yakalamak.

## REST API tamamlama 2: toplam sayı, toplu silme, CSV/GeoJSON export, derin sağlık kontrolü, Swagger etiketleri

- **`GET /api/v1/ucuslar`** artık `{toplam_sayi, ucuslar}` döner (önceden
  çıplak bir liste dönüyordu, istemci limit uygulanmadan önceki toplam
  eşleşme sayısını bilemiyordu) -- **UYUMLULUK NOTU:** bu, yanıt şeklini
  değiştiren bir kırılgan değişikliktir; `web/harita3d.html` ve testler
  güncellendi.
- **`DELETE /api/v1/ucuslar`**: filtreye uyan TÜM uçuşları toplu siler.
  Filtresiz bir çağrı (tüm tabloyu YANLIŞLIKLA boşaltabileceği için) 400
  ile reddedilir -- `veritabani.ucuslari_toplu_sil_async`, hiç filtre
  koşulu yoksa `ValueError` fırlatır.
- **`GET /api/v1/ucuslar/{ucus}/{tarih}/csv`** ve **`/geojson`**: bir
  uçuşun TÜM ölçümlerini (JSON uç noktasındaki 5000 satır tavanı olmadan)
  CSV/GeoJSON olarak indirir -- QGIS/geopandas gibi harici araçlarla
  kullanmak için.
- **`GET /saglik?derin=true`**: varsayılan (anahtarsız, sığ) davranış
  DEĞİŞMEDİ; `derin=true` ile PostgreSQL'e gerçekten bağlanmayı dener,
  erişilemezse 503 döner (deploy sonrası "DB'ye gerçekten erişiyor muyum"
  kontrolü için).
- Swagger (`/docs`) artık uç noktaları Uçuşlar/Analiz/Simülasyon/Türbülans
  Tahmini/Eşikler/Sistem etiketleriyle gruplar.
- `web/harita3d.html`'e "Sil" butonu, "Kayıtlı uçuşlar" arama/filtreleme
  listesi ve gerçek metriklerle dolan "ML Türbülans Modeli" paneli
  eklenmişti (bir önceki bölüm); bu sefer de yeni `toplam_sayi` alanına
  göre güncellendi ve gösterilen/toplam sayı bilgisi eklendi.

## EDR katsayısı gerçek veriyle kalibre edildi + harita3d.html gerçek tarayıcıda test edildi (2 gerçek hata düzeltildi)

- **Kalibrasyon:** `config.EDR_OLCEKLENDIRME_KATSAYISI` artık keyfi bir
  başlangıç değeri (1.5) değil -- yeni `pirep_kalibrasyon_verisi_uret.py`,
  ML sınıflandırıcısı için zaten indirilmiş olan GERÇEK IEM PIREP + ERA5
  verisini (179 örnek) `kalibrasyon.py`'nin beklediği formata çevirir;
  sonuç katsayı (0.23, ortalama karesel hata 0.093) `config.py`'ye
  yazıldı, `EDR_OLCEKLENDIRME_KATSAYISI_KALIBRE_EDILDI` artık `True`
  (main.py'nin "kalibre edilmedi" uyarısı artık basılmıyor). Dürüstlük
  notu: bu ABD hava sahası verisine dayanan, bölgeden bağımsız bir
  kalibrasyondur -- Türkiye/Ocak-2019 örnek veri kümesine özgü değildir.
- **`web/harita3d.html` ilk kez gerçek bir tarayıcıda (Playwright +
  headless Chromium) uçtan uca test edildi** -- gerçek bir uçuş (THY322,
  2019-01-15) analiz edilip sayfaya yüklendi, render doğrulandı. GERÇEK
  bir hata bulundu ve düzeltildi: önceden sabitlenen MapLibre 4.7.1'de
  `harita.setProjection` metodu HİÇ YOKTU (kod içi yorum var olduğunu
  YANLIŞ varsayıyordu) -- 5.8.0'a yükseltildi (hâlâ klasik `<script>` ile
  çalışan UMD paket, 6.x'in aksine). Ardından setProjection'ı `Map`
  constructor'ından hemen sonra çağırmanın "Style is not done loading"
  hatası verdiği görüldü; "globe" projeksiyonu doğrudan constructor'ın
  `projection` seçeneğine taşındı.
- `ml_egitimi.py` yeniden çalıştırılıp `turbulans_ml_modeli_bilgisi.json`
  gerçek verilerle üretildi (bkz. bir önceki bölümdeki yeni uç nokta).

## REST API tamamlama: uçuş silme, listeleme filtreleri, ML model bilgisi uç noktası

Mevcut uç noktalar CRUD'un sadece Create/Read kısmını kapsıyordu (silme
sadece yeniden analizle "üzerine yazma" şeklinde dolaylı vardı) ve
`GET /api/v1/ucuslar` sadece `limit` alıyordu; ayrıca `ml_egitimi.py`'nin
ürettiği gerçek model metrikleri (recall, F1, ROC-AUC vb.) sadece
README/CSV'de duruyordu, API üzerinden okunamıyordu. Üç gerçek eksik
kapatıldı:

- **`DELETE /api/v1/ucuslar/{ucus_numarasi}/{tarih}`**: bir uçuş kaydını
  (CASCADE ile `edr_olcumleri` dahil) siler -- bulunamazsa 404, silinirse
  204. `veritabani.py`'ye asenkron `ucus_sil_async` eklendi.
- **`GET /api/v1/ucuslar` filtreleme**: `ucus_numarasi_arama` (kısmi
  eşleşme) ve `baslangic_tarih`/`bitis_tarih` opsiyonel sorgu parametreleri
  eklendi -- büyüyen bir veri kümesinde belirli bir uçuşu/tarih aralığını
  bulmak artık tüm listeyi çekip istemci tarafında filtrelemeyi
  gerektirmiyor.
- **`GET /api/v1/turbulans/model-bilgisi`**: `ml_egitimi.py` artık seçilen
  modeli (`*.joblib`) kaydederken yanına `turbulans_ml_modeli_bilgisi.json`
  da yazıyor (seçilen model adı, test metrikleri, özellik listesi, eğitim
  tarihi); yeni uç nokta bunu okuyup döner. Model henüz eğitilmediyse
  (projenin genelindeki "uydurma değer üretme" ilkesiyle AYNI şekilde)
  `egitildi_mi: false` ile dürüstçe bildirir.

## Gerçek gözlem verisiyle eğitilmiş ML türbülans sınıflandırıcısı (bitirme projesi komisyon kriterleri)

Komisyon rubriğinin "minimum gereksinim" maddesi: TI1/Richardson gibi fizik
formülü tabanlı göstergelerin yanına, GERÇEK gözlem verisiyle etiketli,
çalışan bir makine öğrenmesi sınıflandırıcısı eklendi -- önceki sürümde
"Bilinçli olarak yapılmayanlar" altında "bu depoda gerçek PIREP/AMDAR verisi
yok, uydurma etiketle model eğitmek 'uydurma katsayı' hatasını tekrarlar"
denilerek ertelenmişti; bu sefer gerçek veri bulunarak yapıldı.

- **Gerçek eğitim verisi:** Bu depodaki Türkiye/Ocak-2019 örnek veri kümesi
  için gerçek türbülans etiketi yok. Bunun yerine `ml_veri_indir.py`, ABD
  hava sahasına özgü halka açık **IEM PIREP arşivinden** (mesonet.agron.
  iastate.edu) 2018-2020 arası pilot türbülans raporlarını ve eşleşen gerçek
  **ERA5** rüzgar/sıcaklık verisini (kullanıcının kendi Copernicus CDS API
  anahtarıyla, `cdsapi` paketi ile) indirdi -- 15 ayrı (yıl, ay) penceresi,
  toplam ~4700 ham PIREP kaydı işlenip FL250-400 arası, gerçekten türbülans
  metni içeren 179 gerçek etiketli örneğe (63 pozitif orta-şiddetli+ / 116
  negatif) indirgendi.
- **`turbulans_ml_modeli.py`:** Özellik çıkarma (`ozellikleri_cikar`,
  projenin ANA eşleştirme kodu `eslestirme.py` yeniden kullanılarak) ve
  tahmin (`turbulans_riski_tahmin_et`) modülü. Özellikler BİLİNÇLİ OLARAK
  bölgeden bağımsız tutuldu (enlem/boylam YOK -- yoksa model ABD'nin
  bölgesel hava düzenine ezberler, Türkiye gibi hiç görmediği bir bölgede
  anlamsızlaşırdı): `ti1_indeksi`, `richardson_sayisi`, `ruzgar_hizi_ms`,
  `basinc_hpa`. Model eğitilmemişse (`.joblib` yoksa) uydurma bir tahmin
  dönmez, dürüstçe `None` döner.
- **`ml_egitimi.py`:** Lojistik Regresyon, Random Forest ve Gradient
  Boosting eğitilip **recall'a göre** karşılaştırıldı (accuracy değil --
  havacılıkta kaçırılan gerçek türbülans/false negative en kritik hata
  türüdür). Gerçek sonuçlar (134 eğitim / 45 test örneği):

  | Model | Accuracy | Precision | Recall | F1 | ROC-AUC |
  |---|---|---|---|---|---|
  | Lojistik Regresyon | 0.578 | 0.421 | 0.500 | 0.457 | 0.644 |
  | **Random Forest (seçildi)** | 0.756 | 0.632 | **0.750** | 0.686 | 0.843 |
  | Gradient Boosting | 0.800 | 0.733 | 0.688 | 0.710 | 0.852 |

  Gradient Boosting accuracy/F1'de biraz önde olsa da Random Forest daha
  yüksek recall'u nedeniyle seçildi (test kümesindeki 16 gerçek türbülans
  vakasının 12'sini yakalıyor, 4'ünü kaçırıyor; Gradient Boosting 11
  yakalayıp 5 kaçırıyor).
- Yeni uç nokta: `POST /api/v1/turbulans/tahmin` -- tek nokta için fizik
  (TI1) ve ML tahminini karşılaştırmalı döner.
- `tests/test_turbulans_ml_modeli.py`: özellik sütunu doğruluğu, kapsam
  dışı/NaN senkronizasyonu, model yokken dürüst `None` dönüşü ve (model
  eğitildiğinde) olasılığın 0-1 aralığında olduğunu doğrulayan testler
  eklendi.
- Üretilen veri/model dosyaları (`pirep_ham/`, `era5_egitim_verisi/`,
  `*.joblib`, `ml_model_karsilastirmasi.csv`, `ml_karisiklik_matrisi.png`)
  büyük/yeniden üretilebilir oldukları için `.gitignore`'a eklendi.

## 3D uçuş simülasyonu: dinamik yeniden hesaplama + kabin bildirimi çerçevelemesi

Komisyon rubriğinin "tam not getirecek" ve "vizyon" kategorilerindeki iki
maddesi için:

- **Dinamik rota güncelleme:** `web/ucus_simulasyonu.html`'e "🔄 Uçuş
  sırasında yeniden hesapla" butonu eklendi -- simülasyon oynarken uçağın o
  anki (Cesium'un CZML interpolasyonuyla bulunan) konumu yeni başlangıç
  noktası olarak alınır ve AYNI hedefe, AYNI gerçek backend (`/api/v1/
  simulasyon/rota`, dolayısıyla A* + irtifa karşılaştırması) yeniden
  çağrılır -- sahte bir "meteorolojik değişiklik" senaryosu değil, gerçek
  bir uçuş-içi yeniden planlama mekanizmasıdır. Gerçek tarayıcıda test
  edildi (41dk → o anki konumdan itibaren 33dk, tutarlı).
- **Kabin içi bildirim çerçevelemesi:** Riskli türbülans tespit edildiğinde
  (tam veya kısmi atlatma), zaten var olan `/ws/uyarilar` WebSocket uyarı
  mantığının simülasyon sayfasındaki karşılığı olarak, gerçek TI1 şiddetine
  dayalı bir "kabin ekibine bildirim" banner'ı gösterilir -- mesaj metni
  açıkça "illüstratif" olarak işaretlenir, uydurma bir canlı sistem gibi
  sunulmaz.

## 3D uçuş simülasyonu: A* rota araması + CO2 raporlama (bitirme projesi komisyon kriterleri)

Bitirme projesi komisyon rubriğindeki "algoritmik rota optimizasyonu (A*/
genetik algoritma)" ve "yeşil havacılık (CO2 raporlama)" maddelerini
karşılamak için:

- **A\* graf araması (`_a_yildiz_ile_rota_ara`):** Önceki "birkaç sabit yanal
  kaydırma adayı dene" yaklaşımı, büyük daire etrafında kurulan gerçek bir
  ızgara üzerinde çalışan, admissible sezgiselli, garantili-optimal bir A*
  aramasıyla değiştirildi. İlk ızgara çok kaba (100 km/adım) olduğu için A*
  rotanın başında/sonunda ani bir sıçrama yapıp koruyordu (gerçek veriyle
  ölçüldüğünde ESKİ yöntemden bile daha uzun/pahalı çıktı, %8.9 yerine %29.6
  ekstra yakıt) -- ızgara inceltilip (20 km/adım) başlangıca/bitişe yakın
  erişilebilir sapmayı kademelendiren bir "zarf" eklenerek düzeltildi (şimdi
  %7.1 ekstra yakıtla, daha küçük ve gerçekçi bir sapmayla aynı türbülansı
  atlatıyor -- eski yöntemden bile daha iyi).
- **CO2 raporlama:** Her iki rotanın tahmini yakıtından, ICAO/IPCC'nin
  standart jet yakıtı emisyon katsayısıyla (`CO2_KG_PER_KG_YAKIT = 3.16`)
  tahmini CO2 emisyonu hesaplanıp API yanıtına (`tahmini_co2_kg`,
  `co2_farki_kg`) ve sonuç paneline eklendi.
- `tests/test_rota_optimizasyonu.py`'ye A*'ın gerçek ERA5 verisiyle tam
  atlatma/kısmi atlatma senaryolarını doğru bulduğunu ve CO2'nin yakıtla
  doğru orantılı olduğunu doğrulayan testler eklendi (10/10 geçiyor).
- **Çok faktörlü maliyet -- irtifa değişimi:** Komisyon rubriğindeki "uçak
  dinamikleri ve çok faktörlü maliyet (özellikle irtifa değiştirirken
  tırmanma/alçalma yakıtı)" maddesi için, optimize rota artık YANAL A* yolu
  ile bir üst/alt basınç seviyesine geçme (gerçek tırmanma/alçalma yakıt/
  süre maliyetiyle, bkz. `_irtifa_degisimi_maliyeti`) arasından TOPLAM
  maliyeti en düşük güvenli seçeneği seçiyor. Gerçek veriyle test edilen bir
  senaryoda (İstanbul→Antalya, 5 Ocak 2019, 28000ft), irtifa artırma
  (+6000ft) stratejisi yanal A* aramasından (%7.1 ekstra yakıt) daha ucuz
  çıktı (%2.7 ekstra yakıt) -- bu, gerçek uçuş operasyonlarında da pilotların
  neden genelde önce irtifa değişikliği istediğini yansıtıyor. Yanıta
  `kacinma_stratejisi` ve her iki rota için `irtifa_ft` alanları eklendi;
  sonuç paneli seçilen stratejiyi ve irtifaları ayrı ayrı gösteriyor.

## 3D uçuş simülasyonu: optimizasyon önceliği "önce güvenlik, sonra yakıt" olarak düzeltildi

İlk sürüm SADECE rüzgara göre en hızlı/ucuz rotayı arıyordu -- bu da
türbülans hiç yokken bile "optimize rota" iki rotayı gereksiz yere görsel
olarak ayrıştırıyordu (sanki gerçek uçuş rotası keyfi değiştiriliyormuş
gibi görünüyordu). Proje sahibiyle netleştirildi: türbülansın kendisi
doğrudan çok fazla yakıt yaktırmaz (asıl yakıt belirleyicisi rüzgardır);
türbülanstan kaçınmanın asıl değeri YOLCU GÜVENLİĞİ/KONFORUdur ve bu, ondan
kaçmak için rotadan sapmanın genelde FAZLADAN yakıt gerektirmesi anlamına
gelir (gerçek uçuşlarda da böyledir).

- **`rota_optimizasyonu.py`** artık ÖNCE riskli türbülanstan (gerçek Ellrod
  TI1 indeksi -- projenin ANA analiz kodu `eslestirme.py`/
  `turbulans_indeksleri.py` doğrudan yeniden kullanılarak hesaplanır) kaçınan,
  SONRA (o kısıt altında) en ucuz rotayı bulan bir öncelik sırası kullanıyor:
  riskli türbülans yoksa optimize rota normal rotayla BİREBİR AYNI kalır;
  varsa onu tamamen atlatan (mümkünse rüzgardan da faydalanan) bir alternatif
  aranır, hiçbir aday riski tam ortadan kaldıramıyorsa riski en aza indiren
  aday dürüstçe seçilir ("tamamen güvenli" diye yalan söylenmez).
- Yanıta `turbulanstan_kacinildi_mi` (bool) ve her iki rota için `maks_ti1`/
  `riskli_nokta_sayisi` alanları eklendi; `web/ucus_simulasyonu.html`'nin
  sonuç paneli artık süre/mesafe/yakıtın yanında riskli türbülans nokta
  sayısını da gösteriyor ve "ekstra yakıt: güvenlik için sapmanın bedeli"
  gibi durumları dürüstçe ayırt ediyor.
- Sayfanın varsayılan demo değerleri, gerçek ERA5 verisiyle doğrulanmış,
  görünür bir türbülanstan-kaçınma örneği gösterecek şekilde güncellendi
  (İstanbul↔Antalya, 5 Ocak 2019, 28000ft).
- `tests/test_rota_optimizasyonu.py`, üç gerçek senaryoyu (türbülans yok ->
  rotalar aynı; türbülans var -> tamamen atlatılıyor; türbülans var ama
  tamamen atlatılamıyor -> risk azaltılıyor, dürüstçe raporlanıyor) gerçek
  ERA5 verisiyle doğrulayacak şekilde yeniden yazıldı.

## 3D uçuş simülasyonu: rüzgar bazlı rota optimizasyonu (bitirme projesi vitrini)

Bitirme projesi sunumu için, kullanıcının seçtiği başlangıç/bitiş/irtifa/
tarih/uçak modeliyle iki rotayı 3D olarak karşılaştıran yeni bir vitrin
özelliği:

- **`rota_optimizasyonu.py`:** Büyük daire ("normal") rotası ile, projenin
  gerçek ERA5 rüzgar veri küpünü kullanarak toplam uçuş süresini/yakıtını en
  aza indiren yanal olarak kaydırılmış ("optimize") rotayı hesaplar. Seçilen
  bölge/tarih veri küpünün kapsamı dışındaysa (bu depoda varsayılan: Türkiye/
  Doğu Akdeniz, Ocak 2019), uydurma bir "iyileşme" göstermek yerine
  `sigmet_dogrulama.py`'deki AYNI dürüstlük ilkesiyle "kapsam dışı" sonucu
  döner ve iki rota da sadece uçağın hava hızıyla hesaplanır.
- **`web/ucus_simulasyonu.html`:** CesiumJS ile build aracı gerektirmeyen tek
  dosyalık bir 3D küre sayfası -- iki rotayı CZML olarak yükler, gerçek bir 3D
  uçak modeliyle (`web/models/ucak.glb`, CesiumJS'in resmi örnek verisi,
  Apache 2.0) zaman-senkronize animasyonla gösterir. `web/harita3d.html`'de
  CartoDB'nin anahtar istemeye başlamasıyla yaşanan sorunu tekrarlamamak için
  benimsenen ilkeyle, Cesium ion hesabı/token'ı GEREKTİRMEZ (anahtarsız Esri
  imagery + düz elipsoid terrain).
- Yeni uç noktalar: `POST /api/v1/simulasyon/rota` (iki rota + CZML döner) ve
  `GET /api/v1/simulasyon/ucak-profilleri` (uçak modeli seçim listesi).
  `semalar.py`'ye karşılık gelen Pydantic modelleri, `tests/
  test_rota_optimizasyonu.py`'ye birim testleri eklendi.
- **Bilinçli sınırlama:** Uçak "modelleri" arasındaki fark sadece seyir hızı/
  yakıt akışı gibi yaklaşık performans katsayılarıdır (halka açık, tipik
  değerler -- resmi üretici verisi değildir); 3D görselleştirmede hepsi aynı
  jenerik uçak modelini kullanır.
- **Gerçek tarayıcıda doğrulama:** Bu sayfa, projenin diğer statik
  önyüzlerinden farklı olarak Playwright + headless Chromium ile uçtan uca
  test edildi ve bu test GERÇEK bir hata buldu: CesiumJS 1.104+'ta
  `Viewer`'ın `imageryProvider` seçeneği artık sessizce hiçbir katman
  eklemiyor (deprecated, yerine `baseLayer: new Cesium.ImageryLayer(...)`
  gerekiyor) -- düzeltilmeden önce harita dokusu hiç render olmuyordu.
  Ayrıca `viewer.flyTo(dataSource)`'un dinamik konumlu varlıklarda tüm
  rotayı değil sadece o anki tekil konumu kapsadığı fark edildi; kamera artık
  ham koordinatlardan hesaplanan bir dikdörtgene uçuyor ve CZML'ye, sadece
  uçulmuş izi değil TÜM rotayı en baştan gösteren ayrı bir statik ön izleme
  çizgisi eklendi.

## GitHub yıldızlarından esinlenilen özellikler: SIGMET doğrulama + 3D harita

Projenin sahibinin GitHub yıldızları (uçuş takibi, havacılık meteorolojisi
ve türbülans tahmini üzerine ~46 depo) incelenip iki fikir hayata geçirildi:

- **SIGMET/AIRMET doğrulaması (`sigmet_dogrulama.py`):** Hesaplanan TI1
  "orta-şiddetli" noktaları, Iowa Environmental Mesonet'in arşivlediği
  gerçek ABD Aviation Weather Center SIGMET kayıtlarıyla (poligon içi +
  zaman penceresi eşleşmesi) karşılaştırılıyor -- gerçek PIREP verisi
  olmasa da, gerçek bir operasyonel uyarı kaynağıyla dürüst bir
  karşılaştırma. SADECE ABD hava sahası için anlamlı sonuç verir; bu
  depodaki Türkiye örnek verisi için (beklenen şekilde) örtüşme çıkmaz.
- **3D/canlı harita önyüzü (`web/harita3d.html`):** MapLibre GL JS ile
  build aracı gerektirmeyen tek dosyalık bir 3D küre (globe) haritası --
  rotayı TI1 şiddetine göre renklendirir, gerçek SIGMET poligonlarını
  overlay olarak gösterir, zaman kaydırıcısıyla oynatılabilir ve
  `/ws/uyarilar` WebSocket'inden canlı uyarı toast'ları gösterir.
- Bu ikisini API'ye bağlamak için `GET /api/v1/esikler` ve
  `GET /api/v1/ucuslar/{ucus}/{tarih}/sigmet-dogrulama` uç noktaları,
  `semalar.py`'ye karşılık gelen Pydantic modelleri eklendi.

## Kod kalitesi ve dağıtım araçları

- **ruff + pre-commit:** `pyproject.toml`'da lint kuralları (E/F/W/I);
  `.pre-commit-config.yaml` ile `ruff check`/`ruff format` + temel dosya
  hijyeni hook'ları. Tüm kod tabanı bir kez `ruff format` ile taban
  çizgisine getirildi (sadece biçimlendirme, davranış değişikliği yok).
- **Merkezi konfigürasyon:** `config.py`'deki hemen hemen her sabit artık
  aynı isimde bir ortam değişkeniyle kod değiştirmeden ezilebilir.
- **Pydantic response modelleri + CORS:** API uç noktaları artık
  `response_model=` ile Swagger'da gerçek bir şema gösteriyor (`semalar.py`).
  CORS, `CORS_IZIN_VERILEN_KAYNAKLAR` ortam değişkeniyle açılır; varsayılan
  kapalı.
- **Tutarlılık:** Kod tabanındaki ASCII-transliterasyonlu Türkçe metinler
  (`cozunurlugunu` gibi) gerçek Türkçe karakterlere çevrildi. `harita.py`'deki
  `pd_isna`, pandas'ın kendi `pd.isna()`'sını yeniden yazmak yerine ona ince
  bir sarmalayıcı oldu.
- **GitHub Actions CI:** her push/PR'da lint (`ruff check` + `ruff format
  --check`) ve test (gerçek bir PostgreSQL servis konteyneriyle: `alembic
  upgrade head` + `pytest`) job'ları çalışır.
- **Docker:** `Dockerfile` + `docker-compose.yml` ile Postgres + `api_servisi.py`
  tek komutla (`docker compose up`) ayağa kalkar; bağlantı bilgileri `.env`'den
  okunur, image'a gömülmez.

## Performans, loglama, migration, çıktı klasörü

- **Toplu (bulk) veritabanı yazımı:** `ucus_ve_olcumleri_kaydet`, satır satır
  ORM nesnesi oluşturmak yerine tüm tabloyu vektörel olarak sözlük listesine
  çevirip TEK bir toplu `INSERT` ile yazıyor (gerçek veriyle ölçüldü: 5000
  satır ~0.5 saniye).
- **`print()` yerine `logging`:** `api_servisi.py`'nin kendi tanı/hata
  mesajları artık `loglama.py` üzerinden seviyeli/filtrelenebilir
  (`LOG_SEVIYESI`, isteğe bağlı `LOG_DOSYASI`) `logging` kullanıyor. CLI
  araçlarının (`main.py`, `toplu_analiz.py`, `web_arayuzu.py`) insan için
  tasarlanmış adım adım çıktısı bilinçli olarak `print()` olarak kaldı.
- **Alembic migration'ları:** Veritabanı şeması artık kod içinde örtük
  (`create_all`) değil, `migrations/` altındaki migration'larla yönetiliyor.
- **Görev kaydı bellek sızıntısı düzeltmesi:** `api_servisi.py`'deki
  `_gorevler` sözlüğü artık kendiliğinden temizleniyor (TTL + sayı tavanı).
- **`veri_kontrol.py` güncellendi:** Artık üretilmeyen
  `eslesme_sonuclari_*.csv` yerine doğrudan PostgreSQL'den okuyor, ve
  örnekleme yanlılığı olmaması için TÜM ölçüm noktalarını inceliyor.
- **Çıktı klasörü:** Harita HTML'leri ve toplu analiz özeti artık proje
  köküne değil `ciktilar/` altına yazılıyor.
- **Büyük rotalarda hafif harita:** `harita.py`'nin animasyonu artık çok
  uzun rotalarda (>2000 nokta) seyreltiliyor; ham veri PostgreSQL'de tam
  haliyle duruyor.

## Kritik güvenlik ve sağlamlık düzeltmeleri

- **NaN → NULL:** Veri küpünün kapsamı dışındaki noktalar veritabanına
  artık `NaN` değil `NULL` olarak yazılıyor -- önceden bu, API'den
  okunduğunda "Out of range float values are not JSON compliant" hatasıyla
  500'e düşüyordu.
- **SQL enjeksiyonu düzeltmesi:** `veri_yukleme.py` ve `ornek_ucus_bul.py`
  artık kullanıcı girdisini f-string ile SQL'e gömmüyor; Trino'nun
  parametreli sorgu desteğini kullanıyor.
- **Gereksiz OAuth2 girişi düzeltmesi:** `trino_baglantisi_olustur()` artık
  süreç boyunca tek bir `OAuth2Authentication` nesnesini yeniden kullanıyor
  -- eskiden her çağrıda yenisi oluşturulup token önbelleği sıfırlanıyordu.
- **Hata mesajı sızıntısı düzeltmesi:** API'nin 500/503 yanıtları artık ham
  exception mesajını istemciye döndürmüyor; tam ayrıntı sunucu tarafında
  loglanıyor.
- **Girdi doğrulama:** `tarih`/`ucus_numarasi` formatı doğrulanıyor, liste
  uç noktaları sayfalanıyor ve üst sınırlara sahip.
- **Zamanlamaya dayanıklı anahtar karşılaştırması:** API anahtarı artık
  `secrets.compare_digest` ile karşılaştırılıyor.

## PostgreSQL, FastAPI ve MCP entegrasyonu

- **PostgreSQL entegrasyonu:** `veritabani.py` + `models.py` (SQLAlchemy
  ORM) -- lokal CSV çıktısının yerini `ucuslar`/`edr_olcumleri` tabloları
  aldı.
- **FastAPI REST API'si:** `api_servisi.py` -- API anahtarlı, `/api/v1`
  sürümlü, async okuma uç noktaları, WebSocket ile canlı uyarı, n8n için
  webhook bildirimi.
- **MCP sunucusu:** `mcp_postgres_sunucusu.py` + `.mcp.json` -- Claude
  Code'un veritabanına salt okunur MCP ile bağlanabilmesi için.
- **n8n otomasyonu:** `toplu_analiz.py` doğrudan değil, `api_servisi.py`'nin
  `/analiz/*` uç noktaları üzerinden -- otomasyon tarafının projenin Python
  iç yapısını hiç bilmesine gerek kalmaz.
- **Bilinçli olarak eklenmedi:** `veri_indirme.py`'nin gerçek ERA5
  indirmesini tetikleyen bir uç nokta (rate-limit/ban riski nedeniyle
  hâlâ sadece elle çalışıyor), JWT/OAuth2 (tek kullanıcılı araç için statik
  API anahtarı yeterli görüldü).

## Güvenilirlik iyileştirmeleri (retry, kalibrasyon uyarısı)

- **Trino/OpenSky retry mantığı:** `veri_yukleme.py` artık `tenacity` ile
  SADECE geçici ağ/sunucu hatalarında, üstel artan aralarla ve en fazla 3
  denemeyle yeniden deniyor -- OpenSky'yi yormamak için deneme sayısı
  bilerek düşük. `toplu_analiz.py` uçuşlar arasına bekleme koyuyor.
- **Kalibrasyon uyarısı:** `config.EDR_OLCEKLENDIRME_KATSAYISI` kalibre
  edilene kadar `main.py` her çalıştırma sonunda uyarı basıyor.
- **`harita.py` için birim testleri eklendi.**

## Performans, Richardson indeksi, toplu analiz, web arayüzü ve hata iyileştirmeleri

- Deformasyon/kayma hesabı tüm grid üzerinde vektörel hale getirildi
  (gerçek veriyle ölçülen kazanç: ~250x).
- Richardson sayısı gibi ek bir kararlılık indeksi eklendi
  (`turbulans_indeksleri.richardson_sayisi_hesapla`) -- TI1'e keyfi bir
  katsayıyla karıştırılmadan, ayrı bir sütun olarak.
- `kalibrasyon.py`: gerçek PIREP/AMDAR verisiyle ölçekleme katsayısını
  kalibre etmek için bir araç (gerçek gözlem verisi bu depoda yok).
- Terminalden bağımsız, tarayıcıdan kullanılabilir bir arayüz
  (`web_arayuzu.py`, Streamlit).
- Birden fazla uçuşu tek seferde analiz etme (`toplu_analiz.py`).
- Anlaşılır Türkçe hata mesajları (`hata_yardimcisi.py`).

## Moduler mimari kurulumu

Projenin ilk büyük refactor'ü -- tek dosyalık, keyfi katsayılı bir
prototipten modüler bir mimariye geçiş:

| Eski | Yeni |
|---|---|
| `edr_hesaplama.py` ve `interaktif_harita.py`'de iki farklı, keyfi katsayılı EDR formülü | `turbulans_indeksleri.py`: Ellrod TI1 indeksi (Ellrod & Knapp, 1992) — havacılık meteorolojisinde CAT tahmini için gerçekten kullanılan yöntem |
| `trino_baglanti.py`'de şifre düz metin kod içinde | `kimlik_dogrulama.py` + `.env`: kimlik bilgileri ortam değişkeninden okunuyor |
| `kucuk_simulasyon.py`: `np.linspace` ile uydurulmuş rota | `veri_yukleme.py`: `flights_data4` üzerinden uçuş numarasından (callsign) gerçek rota çekiliyor |
| Sabit tek nokta sorgusu, koordinat filtresi | `ucus_numarasi_ile_rota_cek()`: callsign → icao24 → state_vectors_data4 zinciri |
| Statik harita, tek zaman anı | `harita.py`: `TimestampedGeoJson` ile zaman kaydırıcılı animasyon, gerçek uçuş bilgisi popup'ları, lejant |
| Basınç/irtifa birim karışıklığı | `birim_donusumleri.py`: ISA barometrik formülüyle metre ↔ hPa dönüşümü |

## Bilinçli olarak yapılmayanlar

- **Offline-first Flutter mobil arayüz:** Projede hiç Flutter/mobil kod
  yok; bu, backend'e bir özellik eklemek değil, ayrı bir mobil uygulama
  geliştirme projesi gerektirir. API tarafı (JSON uç noktaları + WebSocket
  canlı uyarı) buna hazır durumda; mobil istemci ayrı bir iş olarak ele
  alınmalı.
- **20+ modülü `turbulans_radar/` paketi + `scripts/` altında yeniden
  yapılandırmak:** Bilinçli olarak ayrı, kendi başına bir iş olarak
  bırakıldı -- TÜM import'ları, `.mcp.json` yolunu, `alembic.ini`'yi ve
  test dosyalarını aynı anda etkileyen büyük bir refactor.
