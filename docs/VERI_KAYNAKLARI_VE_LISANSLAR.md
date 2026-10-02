# Veri Kaynakları ve Lisanslar

Türbülans Radar'ın kullandığı her dış veri kaynağının kullanım şartı, atıf
metni ve ticari kullanım durumu. Şartlar **1 Ekim 2026**'da resmi sayfalardan
kontrol edildi; sağlayıcılar şartlarını değiştirebilir, ürünleşme öncesi
yeniden kontrol edilmelidir. Bu belge hukuki görüş değildir.

## Özet tablo

| Kaynak | Sistemdeki kullanım | Lisans / şart | Atıf | Ticari kullanım | Kontrol |
|---|---|---|---|---|---|
| OpenSky Network (Trino) | Uçuş izleri (state vector) | Araştırma ve ticari olmayan amaçlar; ticari kullanım için OpenSky ile ayrı anlaşma | Schäfer ve ark. (2014) zorunlu | **Hayır** (anlaşma olmadan) | API belgesi¹ |
| Copernicus C3S ERA5 (CDS) | u, v, t basınç seviyeleri | CC BY 4.0 | DOI 10.24381/cds.bd0915c6 + Copernicus ibaresi | Evet (atıfla) | CDS veri seti sayfası |
| ARCO-ERA5 (Google Cloud) | ERA5 yedek kaynağı | Veri: ERA5 ile aynı (CC BY 4.0); kod/tarifler: Apache-2.0 | ERA5 atfı | Evet (atıfla) | GitHub deposu |
| NOAA GFS (UCAR THREDDS üzerinden) | Canlı rüzgar/sıcaklık | NOAA/NWS bilgisi kamu malı | Gerekmez; NWS içeriği ağırlıklı eserlerde kaynak belirtilmeli | Evet | NWS feragatnamesi; UCAR hizmet şartları ayrıca kontrol edilmedi |
| NOAA AWC Data API | Canlı SIGMET | ABD hükümeti hizmeti; dakikada 100 istek sınırı | Gerekmez | Evet | AWC API sayfası |
| NOAA MADIS (herkese açık arşiv) | Uçak EDR ölçümleri (M1, nesnel türbülans etiketi) | Herkese açık anonim erişim (kısıtlı veri başvurusu reddedildi, 2026-10-02); yeniden dağıtılmaz | NOAA MADIS | Doğrulanmadı | madis-data.ncep.noaa.gov |
| Iowa Environmental Mesonet (IEM) | PIREP arşivi (ML etiketi) | Kamu malı, her yasal amaçla serbest | "Iowa Environmental Mesonet of Iowa State University" (rica) | Evet | IEM feragatnamesi |
| openAIP | Kısıtlı hava sahaları (isteğe bağlı) | CC BY-NC 4.0 | openAIP | Kısıtlı² | openaip.net |
| VATSIM vatspy-data-project | FIR sınırları (koordinatsız SIGMET) | CC BY-SA 4.0 | VATSIM / VAT-Spy Data Project | Evet (atıf + aynı lisansla paylaşım) | GitHub deposu |
| Natural Earth | Örnek kısıtlı sahalar, harita altlığı | Kamu malı | Gerekmez ("Made with Natural Earth" önerilir) | Evet | naturalearthdata.com |
| Esri World Street Map karoları | Harita altlığı (çevrimiçi) | Esri kullanım şartları | "Tiles © Esri" (haritada gösteriliyor) | Ürünleşme öncesi kontrol edilmeli | **Doğrulanmadı** |
| CesiumJS | 3B simülasyon | Apache-2.0 | Lisans dosyası | Evet | npm paketi (`turbulans-statik`) |
| MapLibre GL JS | 2B harita | BSD-3-Clause | Lisans dosyası | Evet | npm paketi (`turbulans-statik`) |

¹ OpenSky'ın şartlar sayfası kontrol sırasında otomatik erişime kapalıydı (HTTP 403); ifade
resmi API belgesinden (openskynetwork.github.io/opensky-api) alındı: API "research and
non-commercial purposes" içindir, ticari kullanım için contact@opensky-network.org ile
iletişime geçilmesi istenir.

² openAIP sitesine göre veri ücretli bir uygulamaya dahil edilebilir, ancak veri herkes
için ücretsiz kalmalı ve verinin kendisi satılmamalıdır.

## Kullanım sınırları ve ban riskine karşı korumalar

Sağlayıcının yazılı sınırı ile sistemin kod seviyesinde uyguladığı sınır (1 Ekim 2026).

| Kaynak | Sağlayıcının sınırı | Sistemin sınırı | Değerlendirme |
|---|---|---|---|
| OpenSky Trino | Kullanıcı başına 2 eşzamanlı + 2 kuyrukta sorgu; sorgu ≤ 30 dk; tarama ≤ 100 GB; bölüm filtresi (`hour`/`day`) zorunlu; toplu global indirme yasak; tekrarlanan ihlal hesabı askıya aldırır | Tüm süreçlerde aynı anda **1** sorgu (dağıtık kilit); günde en fazla `OPENSKY_GUNLUK_MAKS_SORGU` (400) sorgu; her sorguda bölüm filtresi ve tek gün / tek uçuş aralığı; satır sınırı 50.000; toplu analizde uçuşlar arası 2 sn; tamamlanmış uçuşlar Parquet önbelleğinden okunur; yalnızca geçici hatalarda en fazla 3 deneme | Sınırın yarısında |
| Copernicus CDS | ERA5 basınç seviyeleri için istek başına ≤ 120.000 alan; kuyruk yükü sistemce ayarlanır | Günde ≤ 150 istek, gece işi ≤ 60 istek (kota sayacı veritabanında); en büyük istek 4 değişken × 7 seviye × 24 saat = 672 alan; istekler sırayla, aralarında en az 5 sn (`CDS_ISTEKLER_ARASI_SANIYE`); istemcinin geçici hata yeniden denemesi 500'den 10'a indirildi (`CDS_ISTEMCI_MAKS_DENEME`) | Alan sınırının %1'inin altında |
| ARCO-ERA5 (Google) | Herkese açık bucket; yazılı istek sınırı yok | Yalnızca CDS başarısız olursa; uçuş başına ≤ 12 saat; disk önbelleği ≤ 20 GB; gece işinde kullanılmaz | Düşük |
| NOAA AWC | Dakikada 100 istek; yanıt başına ≤ 400 kayıt | 15 dakikada bir 2 istek (API süreci başına) | Sınırın çok altında |
| NOAA GFS (UCAR THREDDS) | Paylaşımlı kamu sunucusu; yazılı sınır bulunamadı | Aynı anda en fazla 2 bölge indirmesi; aynı küp 6 saat yeniden kullanılır | Düşük |
| NOAA MADIS | Yazılı hız sınırı bulunamadı; FTP Nisan 2026'da kapandı, HTTPS | Tek seferde tek indirme (dağıtık kilit); dosyalar arası 5 sn; gece başına en fazla 1 gün (24 saatlik dosya, ~65 MB); günde en fazla 48 dosya (veritabanı sayacı); ham dosya işlenip silinir, gün başına ~2 MB Parquet | Düşük |
| IEM PIREP | Filtresiz istek ≤ 120 gün; yazılı hız sınırı yok | Gece başına ≤ 7 istek, her biri 1 gün; istekler arası 2 sn (`ML_IEM_ISTEKLER_ARASI_SANIYE`) | Düşük |
| openAIP | API anahtarı başına (sınır belgelenmemiş) | İsteğe bağlı; günde bir ülke yenilemesi | Düşük |

Notlar:

- ML gece işini hem API zamanlayıcısı (`ML_GECE_ISI_SAATI`) hem n8n tetiklerse ikinci
  çalışma da CDS sayacına takılır: günlük 150 sınırı aşılamaz.
- Sanal PIREP doğrulaması (`turbulans-sanal-pirep dogrula`) varsayılan olarak OpenSky'a
  sorgu atmaz; `--maks-yeni-sorgu` en fazla 20'dir, her PIREP tek sorgu (1–2 saatlik
  bölüm, ~180 km kutu, ±3000 ft, satır sınırı 50.000) ve sonuç Parquet önbelleğine
  yazılır. Aynı kilit ve günlük tavan geçerlidir.
- Birden çok API süreci çalışsa da zamanlayıcıları (SIGMET, openAIP, ML gece işi) yalnızca
  lider kilidini tutan süreç çalıştırır; istekler süreç sayısıyla çoğalmaz.
- Sayaçlar UTC gece yarısı sıfırlanır; `GET /api/v1/ml/durum` bugünkü CDS kullanımını gösterir.

## Atıf metinleri

Rapor, sunum ve arayüzde kullanılacak metinler:

- **OpenSky:** Matthias Schäfer, Martin Strohmeier, Vincent Lenders, Ivan Martinovic and
  Matthias Wilhelm. "Bringing Up OpenSky: A Large-scale ADS-B Sensor Network for
  Research". In *Proceedings of the 13th IEEE/ACM International Symposium on Information
  Processing in Sensor Networks (IPSN)*, pages 83-94, April 2014.
- **ERA5:** Hersbach, H. ve ark. (2023): ERA5 hourly data on pressure levels from 1940 to
  present. Copernicus Climate Change Service (C3S) Climate Data Store (CDS),
  DOI: 10.24381/cds.bd0915c6. Ayrıca: "Contains modified Copernicus Climate Change
  Service information 2026." Yöntem atfı: Hersbach, H. ve ark. (2020), *QJRMS* 146(730),
  1999-2049.
- **IEM:** "PIREP verisi: Iowa Environmental Mesonet of Iowa State University."
- **NOAA:** "SIGMET: NOAA Aviation Weather Center; canlı model: NOAA GFS (UCAR THREDDS)."
  NOAA'nın onayladığı izlenimi verilmez.
- **openAIP:** "Hava sahası verisi: openAIP (CC BY-NC 4.0), openaip.net."
- **FIR sınırları:** "VAT-Spy Data Update Project (CC BY-SA 4.0)." Sınırlar simülasyon
  topluluğunun çizimidir, resmi AIP sınırı değildir.

## Ürünleşme açısından sonuç

Bitirme projesi ve araştırma kullanımı için tüm kaynaklar uygundur. Havayolu
entegrasyonu (ticari kullanım) için iki kaynak değişmelidir:

1. **Uçuş izi (OpenSky):** Havayolunun kendi ADS-B/ACARS akışı ya da lisanslı bir
   ADS-B sağlayıcısı. Kod tarafında `POST /api/v1/analiz/rota` dışarıdan iz kabul ettiği
   için kaynak değişimi veri hattını etkilemez.
2. **Kısıtlı hava sahası (openAIP):** Resmi AIP ENR 5.1, EASA CZIB ve NOTAM verisi
   (`kisitli_saha_saglayici` GeoJSON içe aktarımı bu amaçla vardır).

Esri karolarının ticari kullanımı ayrıca kontrol edilmeli; çevrimdışı altlık
(Natural Earth) lisans sorunu olmadan her zaman kullanılabilir.

## Bu depodaki demo verisi

`demo/` klasöründeki dosyalar yukarıdaki kaynaklardan türetilmiştir (bkz.
`demo/README.md`): THY322 rotası OpenSky'dan (ticari olmayan kullanım şartı
geçerlidir), ERA5 dilimi Copernicus CDS'ten (CC BY 4.0). Yeniden dağıtımda
atıf metinleri korunmalıdır.
