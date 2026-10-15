# Avrupa/Türkiye nesnel etiket kaynakları (F4)

15 Ekim 2026, masa başı araştırma. Veri indirilmedi, başvuru yapılmadı.

## Bugünkü durum

- Doğrulama yalnız ABD'dedir. Yerel MADIS EDR deposunda (11 gün, FL280 üstü) Avrupa
  kutusunda 21.167 gözlem var, yalnız 28'i hafif ve üstü. Türkiye/Doğu Akdeniz
  kutusunda 0 gözlem var (`docs/SISTEM_KARTI.md`).
- IEM PIREP'in Türkiye kutusundaki kayıtları yanlış konumlanmış ABD raporlarıdır.
- SIGMET arşivi LTAA'yı kapsar, ama bağımsız kanıttır, nokta etiketi değildir.

## Adaylar

| Kaynak | Ne verir | Erişim | Değerlendirme |
|---|---|---|---|
| WMO AMDAR (E-AMDAR/EUMETNET; GTS, WIS2) | EDR ve DEVG içeren uçak raporları | WMO-IATA WICAP kısıtları nedeniyle uçak gözlemleri "Core" veri değil. Türbülans verisinde kısıt daha sıkı; WMO ile IATA arasında küresel bir paylaşım anlaşması yok (WMO veri politikası sunumu, ~2021). Erişim NMHS üzerinden, Türkiye için MGM | Üniversitenin doğrudan erişimi olası görünmüyor; MGM araştırma iş birliği gerekir |
| IATA Turbulence Aware | Canlı ve tarihsel EDR (CSV): zaman, irtifa, konum, tepe/ortalama EDR, rüzgar, sıcaklık | Kullanıcılar arasında "University research departments" sayılıyor; şartlar ve ücret yayımlanmamış. Veri havayollarınındır, yayım bir danışma grubunun denetiminde. İletişim: iataturbulence@iata.org | En doğrudan aday; başvuru ve şart öğrenme gerekir |
| EMADDC Mode-S EHS (KNMI) | Rüzgar ve sıcaklık | EUMETNET | Türbülans ölçmez; etiket olamaz |
| AMDAR DEVG → EDR (Kim vd., 2020) | DEVG'den türetilmiş EDR | AMDAR erişimine bağlı | Yöntem var; Avrupa'da yerinde EDR ile genel olarak tutarlı. Veri sorunu aynı kalıyor |
| THY / MGM doğrudan | — | Kamuya açık bilgi bulunamadı | Bilinmiyor |

Not: WMO ABO bülteni (2026), EDR raporlamasının arttığını ama Doğu Avrupa'da hâlâ
düşük olduğunu söylüyor. Erişim olsa bile Türkiye üzerindeki ölçüm sayısı ayrıca
kontrol edilmeli.

## Öneri

1. Danışman üzerinden MGM'ye araştırma amaçlı AMDAR/EDR veri talebi.
2. IATA Turbulence Aware'a akademik erişim şartları sorusu.
3. Bu sürede Türkiye için ML metrikleri genellenmez; yalnız SIGMET bağımsız kanıtı
   raporlanır.

Bu iki adım dış iletişimdir; gönderim kararı proje sahibinindir.

## Kaynaklar

- WMO, Unified Data Policy sunumu, "Impact on Aircraft-Based Observations":
  https://fpaw.aero/sites/default/files/144/talk3-selfpresentation-lockett-presentation.pdf
- WMO ABO veri sayfası: https://community.wmo.int/site/knowledge-hub/programmes-and-initiatives/aircraft-based-observations/aircraft-based-observations-data
- WMO ABO bülteni, cilt 28: https://community.wmo.int/media/magazine-article/wmo-abo-newsletter-volume-28
- EUMETNET ABO: https://www.eumetnet.eu/observations/aircraft-based-observations/
- IATA Turbulence Aware (meteoroloji): https://www.iata.org/en/services/data/safety/turbulence-platform/meteo/
- IATA, ICAO APAC MET-ATM semineri 2025 sunumu: https://www.icao.int/sites/default/files/APAC/Meetings/2025/2025%20ATFMSG15/MET-ATM%20Seminar/SP11-Turbulence-Aware-Facilitating-industry-shift-to-data-driven-turbulence-mitigation-IATA.pdf
- Kim vd. (2020), AMT 13, 1373–1385: https://amt.copernicus.org/articles/13/1373/2020/
