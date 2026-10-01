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
