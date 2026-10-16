# Rota ayrıklaştırma yakınsama çalışması

Üretim: 2026-10-16T13:28:02.001379+00:00. Referans en ince ayar: 81 ara nokta, 10 km yanal ızgara. Varsayılan: 41 nokta, 20 km. Farklar önerilen (optimize) rotanın referansa göre farkıdır. Veri yerel ERA5 (Ocak 2019); canlı veri ve otomatik indirme kapalı.

| Senaryo | Nokta | Izgara (km) | Strateji | Süre farkı (dk) | Yakıt farkı (kg) | Riskli süre farkı (dk) | Hesap (ms) |
|---|---|---|---|---|---|---|---|
| S1 İstanbul→Antalya FL290 | 21 | 10 | yanal | -0.53 | -25.4 | +0.2 | 1423 |
| S1 İstanbul→Antalya FL290 | 21 | 20 | yanal | +0.26 | +12.6 | +0.2 | 314 |
| S1 İstanbul→Antalya FL290 | 21 | 40 | yanal | +0.26 | +12.6 | +0.2 | 327 |
| S1 İstanbul→Antalya FL290 | 41 | 10 | yanal | +0.10 | +4.7 | -0.3 | 406 |
| S1 İstanbul→Antalya FL290 | 41 **(varsayılan)** | 20 | yanal | +0.10 | +4.7 | -0.3 | 415 |
| S1 İstanbul→Antalya FL290 | 41 | 40 | yanal | +0.10 | +4.7 | -0.3 | 385 |
| S1 İstanbul→Antalya FL290 | 81 | 10 | yanal | +0.00 | +0.0 | +0.0 | 656 |
| S1 İstanbul→Antalya FL290 | 81 | 20 | yanal | +0.00 | +0.0 | +0.0 | 686 |
| S1 İstanbul→Antalya FL290 | 81 | 40 | yanal | +0.00 | +0.0 | +0.0 | 688 |
| S2 İzmir→Van FL350 | 21 | 10 | yok | +0.00 | +0.2 | +0.0 | 126 |
| S2 İzmir→Van FL350 | 21 | 20 | yok | +0.00 | +0.2 | +0.0 | 98 |
| S2 İzmir→Van FL350 | 21 | 40 | yok | +0.00 | +0.2 | +0.0 | 92 |
| S2 İzmir→Van FL350 | 41 | 10 | yok | -0.00 | -0.1 | +0.0 | 145 |
| S2 İzmir→Van FL350 | 41 **(varsayılan)** | 20 | yok | -0.00 | -0.1 | +0.0 | 140 |
| S2 İzmir→Van FL350 | 41 | 40 | yok | -0.00 | -0.1 | +0.0 | 114 |
| S2 İzmir→Van FL350 | 81 | 10 | yok | +0.00 | +0.0 | +0.0 | 180 |
| S2 İzmir→Van FL350 | 81 | 20 | yok | +0.00 | +0.0 | +0.0 | 208 |
| S2 İzmir→Van FL350 | 81 | 40 | yok | +0.00 | +0.0 | +0.0 | 195 |
| S3 İstanbul→Doğu Anadolu FL350 | 21 | 10 | irtifa_yukari | -0.03 | -1.1 | +0.0 | 426 |
| S3 İstanbul→Doğu Anadolu FL350 | 21 | 20 | irtifa_yukari | -0.03 | -1.1 | +0.0 | 383 |
| S3 İstanbul→Doğu Anadolu FL350 | 21 | 40 | irtifa_yukari | -0.03 | -1.1 | +0.0 | 341 |
| S3 İstanbul→Doğu Anadolu FL350 | 41 | 10 | irtifa_yukari | -0.01 | -0.4 | +0.0 | 469 |
| S3 İstanbul→Doğu Anadolu FL350 | 41 **(varsayılan)** | 20 | irtifa_yukari | -0.01 | -0.4 | +0.0 | 423 |
| S3 İstanbul→Doğu Anadolu FL350 | 41 | 40 | irtifa_yukari | -0.01 | -0.4 | +0.0 | 416 |
| S3 İstanbul→Doğu Anadolu FL350 | 81 | 10 | irtifa_yukari | +0.00 | +0.0 | +0.0 | 652 |
| S3 İstanbul→Doğu Anadolu FL350 | 81 | 20 | irtifa_yukari | +0.00 | +0.0 | +0.0 | 679 |
| S3 İstanbul→Doğu Anadolu FL350 | 81 | 40 | irtifa_yukari | +0.00 | +0.0 | +0.0 | 641 |
| S4 Malatya→Musul FL370 + örnek kısıtlı sahalar | 21 | 10 | yok ≠ ref | -2.16 | -94.5 | +0.0 | 198 |
| S4 Malatya→Musul FL370 + örnek kısıtlı sahalar | 21 | 20 | yanal | -0.02 | -0.8 | +0.0 | 344 |
| S4 Malatya→Musul FL370 + örnek kısıtlı sahalar | 21 | 40 | yanal | -0.02 | -0.8 | +0.0 | 326 |
| S4 Malatya→Musul FL370 + örnek kısıtlı sahalar | 41 | 10 | yanal | +0.00 | +0.0 | +0.0 | 426 |
| S4 Malatya→Musul FL370 + örnek kısıtlı sahalar | 41 **(varsayılan)** | 20 | yanal | +0.00 | +0.0 | +0.0 | 433 |
| S4 Malatya→Musul FL370 + örnek kısıtlı sahalar | 41 | 40 | yanal | +0.00 | +0.0 | +0.0 | 443 |
| S4 Malatya→Musul FL370 + örnek kısıtlı sahalar | 81 | 10 | yanal | +0.00 | +0.0 | +0.0 | 753 |
| S4 Malatya→Musul FL370 + örnek kısıtlı sahalar | 81 | 20 | yanal | +0.00 | +0.0 | +0.0 | 800 |
| S4 Malatya→Musul FL370 + örnek kısıtlı sahalar | 81 | 40 | yanal | +0.00 | +0.0 | +0.0 | 782 |
| S6 İzmir→Van FL350 + sentetik TURB SIGMET | 21 | 10 | yanal | -2.29 | -99.5 | +0.0 | 505 |
| S6 İzmir→Van FL350 + sentetik TURB SIGMET | 21 | 20 | yanal | -1.91 | -82.6 | +0.0 | 388 |
| S6 İzmir→Van FL350 + sentetik TURB SIGMET | 21 | 40 | yanal | -0.43 | -18.6 | +0.0 | 359 |
| S6 İzmir→Van FL350 + sentetik TURB SIGMET | 41 | 10 | yanal | -1.83 | -79.3 | +0.0 | 539 |
| S6 İzmir→Van FL350 + sentetik TURB SIGMET | 41 **(varsayılan)** | 20 | yanal | -0.42 | -18.0 | +0.0 | 455 |
| S6 İzmir→Van FL350 + sentetik TURB SIGMET | 41 | 40 | yanal | -0.29 | -12.4 | +0.0 | 449 |
| S6 İzmir→Van FL350 + sentetik TURB SIGMET | 81 | 10 | yanal | +0.00 | +0.0 | +0.0 | 757 |
| S6 İzmir→Van FL350 + sentetik TURB SIGMET | 81 | 20 | yanal | +0.13 | +5.6 | +0.0 | 770 |
| S6 İzmir→Van FL350 + sentetik TURB SIGMET | 81 | 40 | yanal | +0.13 | +5.6 | +0.0 | 747 |

Hesap süresi tek ölçümdür (soğuk/sıcak ayrılmadı); yalnız ayarlar arası göreli karşılaştırma içindir. Yakıt ve süre modelin kendi tahminidir; gerçek uçuş değildir.
