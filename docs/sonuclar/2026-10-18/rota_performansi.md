### Rota kararı (11 tekrar; sıcak medyan 0.1–0.42 sn)

| Senaryo | Veri | Mesafe (km) | Strateji | Soğuk (ms) | Sıcak medyan (maks) | A* medyan (ms) |
|---|---|---|---|---|---|---|
| S1 İstanbul→Antalya FL290 | era5_gercek | 482 | yanal | 1330.5 | 383.2 (414.4) | 96.2 |
| S2 İzmir→Van FL350 | era5_gercek | 1418 | yok | 122.0 | 123.0 (163.8) | 15.2 |
| S3 İstanbul→Doğu Anadolu FL350 | era5_gercek | 1162 | irtifa_yukari | 437.8 | 391.0 (439.9) | 83.7 |
| S4 Malatya→Musul FL370 + örnek kısıtlı sahalar | era5_gercek | 481 | yanal | 409.1 | 414.1 (445.9) | 123.9 |
| S5 İstanbul→New York FL340 (kapsam dışı) | era5_kapsam_disi | 8066 | yok | 101.1 | 102.9 (109.8) | çağrılmadı |
| S6 İzmir→Van FL350 + sentetik TURB SIGMET | era5_gercek | 1418 | yanal | 423.3 | 415.7 (437.1) | 102.8 |

19 Ekim 2026, dizüstü şarjda, WSL2 (i7-13700H), `turbulans-performans rota --tekrar 11`.

İlk ölçüm (aynı gün, `rota_performansi_iyilestirme_oncesi.json`) 0,25–0,69 sn verdi: 7 Ekim'e
(0,03–0,45 sn) göre yavaşlama, 16 Ekim'de eklenen kütle bandından geliyordu (3 kütle oranı × 2 rota
için OpenAP seyir yakıtı, adım adım; S5'te sürenin ~%94'ü). Aynı kütle oranı ve aday için seyir
yakıtı artık bir kez hesaplanıyor, NOx adım dizisi üzerinde tek çağrıyla hesaplanıyor. Altı senaryonun
yanıtı önce/sonra birebir aynı (yalnız saate bağlı `uretim_zamani` ve `kalkisa_kalan_saat` farklı).
