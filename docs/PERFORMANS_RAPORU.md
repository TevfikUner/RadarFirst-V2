# Performans Raporu

Ölçüm tarihi: 1 Ekim 2026. Araç: `turbulans-performans` (`src/turbulans_radar/cli/performans_olcumu.py`);
ham sonuçlar komutla yeniden üretilebilir (bkz. §6). Sistem sertifikalı EDR üretmez;
karar destek aracıdır.

## 1. Hedefler

Hedefler, bir harekât merkezi vardiyasındaki kullanım üzerinden tanımlandı: dispeçerin
okuma ekranları "anında" (≤ 0,5 sn), nokta tahmini etkileşimli (≤ 1 sn), rota önerisi
planlama süresine göre kabul edilebilir (≤ 5 sn) olmalı. 16 eşzamanlı istek, aynı anda
çalışan bir vardiyanın üst sınırı olarak alındı.

| # | Ölçüt | Hedef |
|---|---|---|
| H1 | Tek uçuş analizi (önbellekteki rota, yerel ERA5) | ≤ 10 sn |
| H2 | Sağlık ucu p95, 4 eşzamanlı | ≤ 50 ms |
| H3 | Uçuş listesi ve uçuş detayı (1614 nokta) p95, 16 eşzamanlı | ≤ 500 ms |
| H4 | Nokta türbülans tahmini p95, 16 eşzamanlı | ≤ 1 sn |
| H5 | Rota simülasyonu (A*, önbelleksiz) p95, 16 eşzamanlı | ≤ 5 sn |
| H6 | Rota simülasyonu (önbellekte) p95, 4 eşzamanlı | ≤ 100 ms |
| H7 | Tüm yük düzeylerinde hata oranı (5xx, 429, zaman aşımı) | %0 |
| H8 | İşçi görev hızı (uçuş analizi, 2 iş parçacığı) | ≥ 10 görev/dk |
| H9 | ML gece işi, CDS isteği başına süre | ≤ 90 sn |

## 2. Ortam

| Öğe | Değer |
|---|---|
| Donanım | Intel Core i7-13700H (20 mantıksal çekirdek), 15,6 GB RAM (dizüstü) |
| Sanal ortam | WSL2 (Linux 6.18), VM'e ayrılan bellek 7,6 GB, Docker 29.1.3 |
| Yazılım | Python 3.12 (konteyner) / 3.14 (ölçüm aracı), PostgreSQL 16 (`max_connections` = 100) |
| Yığın | `docker compose` (db, api, worker), demo verisi (`.env.demo`), ağsız; ayrı proje ve portlarda |
| Hız sınırları | Kapasiteyi ölçmek için istemci başı dakikalık sınırlar (`ROTA_HESABI_DAKIKADA_MAKS`, `TAHMIN_DAKIKADA_MAKS`) yükseltildi; ağır hesap eşzamanlılık tavanı (`AGIR_HESAP_MAKS_ESZAMANLI` = 4) varsayılanında bırakıldı |
| Veri | THY322 (2019-01-15) rotası ve ERA5 dilimi (22 × 80 hücre, 3 seviye, 6 saat) |

## 3. Sonuçlar

### 3.1 Tek uçuş analizi (süreç içinde, 6 tekrar)

İlk (soğuk) çalıştırma toplamı 410 ms. Sıcak tekrarlar:

| Aşama | p50 (ms) | p95 (ms) |
|---|---|---|
| Rota okuma (Parquet önbelleği) | 9,4 | 13,1 |
| Hava küpü seçimi | 9,7 | 16,1 |
| Eşleştirme (TI1, TI2, Richardson, EDR proxy; 1614 nokta) | 23,2 | 29,8 |
| Folium haritası | 111,3 | 114,7 |
| PostgreSQL yazımı | 61,7 | 74,1 |
| **Toplam** | **222,7** | **227,9** |

Ağ gerektiren adımlar (OpenSky sorgusu, CDS'ten ERA5 dilimi) bu ölçümde yoktur;
gerçek bir ilk analizde süre bunlara bağlıdır (CDS dilimi tipik olarak ~40 sn, bkz. ADR 0001).

### 3.2 API gecikmesi

Her düzeyde 8 × eşzamanlılık kadar istek (en az 10), önce 2 ısınma isteği. Rota
senaryosunda her istek farklı bir varış noktası kullanır ki önbellek ölçümü bozmasın;
"önbellekli" senaryo bilerek aynı isteği tekrarlar. Tüm isteklerin yanıtı 200 oldu.

**Tek uvicorn süreci (varsayılan):**

| Senaryo | c | p50 (ms) | p95 (ms) | p99 (ms) | Verim (istek/sn) |
|---|---|---|---|---|---|
| Sağlık | 1 / 4 / 16 | 6,7 / 21,3 / 68,3 | 13,3 / 43,8 / 305,8 | 13,4 / 52,4 / 396,6 | 131 / 162 / 150 |
| Uçuş listesi | 1 / 4 / 16 | 4,9 / 13,7 / 88,4 | 5,4 / 40,3 / 429,9 | 5,6 / 41,8 / 667,7 | 202 / 217 / 112 |
| Uçuş detayı (1614 nokta) | 1 / 4 / 16 | 16,6 / 44,2 / 209,2 | 65,7 / 86,2 / 416,0 | 65,8 / 86,8 / 480,5 | 38 / 71 / 71 |
| Nokta tahmini | 1 / 4 / 16 | 27,2 / 108,1 / 433,4 | 29,5 / 130,4 / 513,9 | 30,1 / 134,8 / 557,7 | 37 / 37 / 36 |
| Rota (önbelleksiz) | 1 / 4 / 16 | 272 / 1271 / 5154 | 301 / 1427 / 5454 | 306 / 1456 / 5524 | 3,7 / 4,3 / 4,0 |
| Rota (önbellekte) | 1 / 4 / 16 | 8,8 / 17,2 / 50,4 | 14,0 / 22,4 / 392,5 | 16,3 / 24,4 / 722,6 | 103 / 218 / 130 |

**Dört uvicorn süreci (`WEB_CONCURRENCY=4`):**

| Senaryo | c | p50 (ms) | p95 (ms) | p99 (ms) | Verim (istek/sn) |
|---|---|---|---|---|---|
| Sağlık | 1 / 4 / 16 | 3,1 / 10,4 / 55,8 | 3,5 / 21,8 / 203,2 | 3,6 / 51,3 / 353,5 | 316 / 301 / 183 |
| Uçuş listesi | 1 / 4 / 16 | 5,0 / 12,8 / 58,4 | 5,4 / 42,6 / 257,2 | 5,4 / 49,4 / 440,7 | 200 / 248 / 157 |
| Uçuş detayı (1614 nokta) | 1 / 4 / 16 | 13,0 / 18,3 / 102,7 | 34,4 / 72,0 / 358,5 | 48,0 / 80,4 / 437,2 | 60 / 147 / 107 |
| Nokta tahmini | 1 / 4 / 16 | 26,3 / 35,1 / 101,8 | 28,2 / 73,1 / 302,3 | 28,8 / 82,8 / 405,0 | 38 / 91 / 110 |
| Rota (önbelleksiz) | 1 / 4 / 16 | 262 / 273 / 661 | 284 / 648 / 3952 | 293 / 654 / 4130 | 3,8 / 12,7 / 11,3 |
| Rota (önbellekte) | 1 / 4 / 16 | 7,7 / 8,4 / 49,5 | 8,7 / 455,8 / 475,5 | 8,9 / 655,2 / 674,0 | 128 / 49 / 129 |

### 3.3 İşçi görev hızı

30 uçuş analizi görevi (THY322, önbellekteki rota, yerel ERA5, veritabanına kayıt)
kuyruğa doğrudan eklendi; işçi 2 iş parçacığıyla çalıştı.

| Tamamlanan | Toplam süre | Verim | Görev süresi p50 / p95 |
|---|---|---|---|
| 30 / 30 | 3,9 sn | 467 görev/dk | 168 / 217 ms |

### 3.4 ML gece işi

| Başlangıç (UTC) | Süre | CDS isteği | Eşleşen örnek | İstek başına |
|---|---|---|---|---|
| 2026-09-30 21:18 | 68,0 dk | 60 | 1596 | 68 sn |

Tek tam çalışma ölçülebildi; süre CDS kuyruğuna bağlıdır, sistemin kendi hesabı ihmal
edilebilir düzeydedir. 1 Ekim'deki çalışma WSL sanal makinesinin iki kez kendiliğinden
yeniden başlaması nedeniyle bölündüğü için tabloya alınmadı (bayat görev kurtarma işi
iki kez de yeniden kuyruğa aldı).

## 4. Hedef karşılaştırması

| # | Hedef | 1 süreç | 4 süreç |
|---|---|---|---|
| H1 | ≤ 10 sn | ✔ 0,23 sn | — |
| H2 | ≤ 50 ms | ✔ 43,8 ms | ✔ 21,8 ms |
| H3 | ≤ 500 ms | ✔ 430 / 416 ms | ✔ 257 / 359 ms |
| H4 | ≤ 1 sn | ✔ 514 ms | ✔ 302 ms |
| H5 | ≤ 5 sn | ✘ 5,45 sn | ✔ 3,95 sn |
| H6 | ≤ 100 ms | ✔ 22 ms | ✘ 456 ms |
| H7 | %0 | ✔ | ✔ |
| H8 | ≥ 10 görev/dk | ✔ 467 | — |
| H9 | ≤ 90 sn | ✔ 68 sn (n = 1) | — |

## 5. Bulgular ve öneriler

1. **Darboğaz tek süreç.** Tek süreçte nokta tahmini (~37 istek/sn) ve rota (~4 istek/sn)
   verimi eşzamanlılıktan bağımsız sabit kalıyor: CPU ağır hesaplar `asyncio.to_thread`
   ile ayrı iş parçacığında koşsa da Python'un GIL'i nedeniyle pratikte tek çekirdekte
   sıraya giriyor. Dört süreçle aynı donanımda verim tahminde ~3 kat, rotada ~3,2 kat
   arttı; H5 sağlandı.
2. **Süreç sayısı artarken dikkat edilecekler** (`WEB_CONCURRENCY` > 1):
   - Rota önbelleği süreç başınadır; isabet oranı düşer (H6'daki gerileme). Paylaşılan
     önbellek (ör. PostgreSQL ya da Redis) ayrı bir iştir.
   - Her süreç kendi veritabanı havuzunu açar (varsayılan senkron 10+20 ve asenkron
     10+20). 4 süreç teorik olarak PostgreSQL'in 100 bağlantı sınırını aşabilir;
     `VERITABANI_HAVUZ_*` ve `ASYNC_VERITABANI_HAVUZ_*` süreç sayısına göre düşürülmeli
     ya da `max_connections` artırılmalı.
   - SIGMET, openAIP ve ML gece işi zamanlayıcıları her süreçte çalışır: SIGMET süreç
     sayısı kadar çekilir (zararsız ama gereksiz). ML gece işinde aynı anda iki görev
     oluşsa bile işçideki dağıtık kilit yalnızca birini çalıştırır. Zamanlayıcıları tek
     bir "lider" sürece bağlamak (advisory lock) sonraki iyileştirmedir.
3. **Analiz ve işçi kapasitesi bol.** Ağ gerektirmeyen bir uçuş analizi ~0,2 sn sürüyor;
   gerçek süreyi OpenSky ve CDS belirliyor. Folium haritası analiz süresinin yarısıdır
   ve API/işçi çalıştırmalarında zaten üretilmez.
4. **Gece işi dış servise bağlı.** CDS isteği başına ~68 sn; 60 isteklik gece bütçesi
   ~70 dakikada tamamlanıyor.

## 6. Tekrar üretim

```bash
# Ayrı ölçüm yığını (demo verisi, ağsız); istemci başı hız sınırları yükseltilir
cp .env.demo .env
printf 'ROTA_HESABI_DAKIKADA_MAKS=1000000\nTAHMIN_DAKIKADA_MAKS=1000000\n' >> .env
docker compose --profile demo up -d --build --wait      # 4 süreç için .env'e WEB_CONCURRENCY=4

# Ölçümler (POSTGRES_* yığının veritabanına işaret etmeli)
turbulans-performans analiz --tekrar 6 --json analiz.json
TURBULANS_API_ANAHTARI=demo-yerel-yonetici turbulans-performans api --taban-url http://localhost:8000 --json api.json
turbulans-performans gorev --adet 30 --json gorev.json
turbulans-performans gece --json gece.json             # geliştirme veritabanında
```

## 7. Ölçümün sınırları

- Yük üreteci (tek Python süreci, httpx) sunucuyla aynı makinede çalıştı ve CPU'yu
  paylaştı; hafif uçlarda 16 eşzamanlılıktaki değerler (≈150–300 istek/sn tavanı) kısmen
  istemci tarafını da ölçer.
- Ölçüm sırasında aynı makinede geliştirme yığını ve ML gece işi de çalışıyordu (gece
  işi çoğunlukla CDS'i beklediği için CPU yükü düşüktü).
- Demo hava küpü küçüktür; daha geniş bölgeli küplerde eşleştirme ve A* süreleri artar.
- Dizüstü bilgisayar, sanal makine; sunucu donanımında değerler farklı olacaktır.
