# Türbülans Radar — Mimari

Bu belge sistemi C4 modelinin üç düzeyinde (bağlam, konteyner, bileşen) ve
iki ana veri akışıyla anlatır. Diyagramlar Mermaid'dir; GitHub ve çoğu
Markdown görüntüleyici doğrudan çizer. Tasarım kararlarının gerekçeleri
[adr/](adr/) altındadır; davranış ve sınırlar [SISTEM_KARTI.md](SISTEM_KARTI.md)'dadır.

Sistem sertifikalı EDR üretmez; operasyonel karar aracı değil, karar destek aracıdır.

## 1. Bağlam

Sistem kimlere hizmet eder ve hangi dış sistemlere dayanır.

```mermaid
flowchart LR
    DIS(["Dispeçer / uçuş harekât"])
    PIL(["Pilot (EFB, salt pilot rolü)"])
    OPR(["Operatör / yönetici"])
    N8N(["Dış zamanlayıcı<br/>(n8n/cron, isteğe bağlı)"])

    TR["<b>Türbülans Radar</b><br/>Rota-hava eşleştirme, türbülans göstergeleri,<br/>SIGMET/kısıtlı saha kısıtlı A* rota,<br/>ML risk olasılığı"]

    OS[("OpenSky Network<br/>Trino, OAuth2")]
    CDS[("Copernicus CDS<br/>ERA5")]
    ARCO[("ARCO-ERA5<br/>Google Cloud Zarr")]
    GFS[("NOAA GFS<br/>UCAR THREDDS")]
    AWC[("NOAA AWC<br/>SIGMET API")]
    IEM[("Iowa Env. Mesonet<br/>PIREP")]
    OAIP[("openAIP<br/>kısıtlı sahalar")]

    DIS -->|"rota simülasyonu, uçuş analizi"| TR
    PIL -->|"tahmin, canlı uyarı (WebSocket)"| TR
    OPR -->|"veri, model, kısıtlı saha yönetimi"| TR
    N8N -->|"gece işi, SIGMET yenileme"| TR

    TR -->|"uçuş izi"| OS
    TR -->|"uçuşa özel ERA5 dilimi"| CDS
    TR -.->|"CDS başarısızsa"| ARCO
    TR -->|"canlı rüzgar/sıcaklık"| GFS
    TR -->|"aktif SIGMET"| AWC
    TR -->|"ML etiketi"| IEM
    TR -->|"isteğe bağlı"| OAIP
```

## 2. Konteynerler

`docker compose` üç servis çalıştırır: `db`, `api`, `worker` (`--profile demo`
ile ek olarak tek seferlik `demo`). Ağır işler API'de değil işçide çalışır;
iki servis kuyruğu ve kilitleri PostgreSQL üzerinden paylaşır.

```mermaid
flowchart TB
    subgraph istemci["İstemciler"]
        H3D["web/harita3d.html<br/>MapLibre 2B/3B harita"]
        SIM["web/ucus_simulasyonu.html<br/>CesiumJS rota karşılaştırma"]
        STR["Streamlit arayüzü"]
        CLI["CLI araçları<br/>turbulans-analiz, -ml, -backtest, -demo"]
        MCP["MCP sunucusu<br/>salt okunur SQL"]
    end

    subgraph yigin["docker compose"]
        API["<b>api</b><br/>FastAPI REST + WebSocket<br/>API anahtarı rolleri, hız sınırı,<br/>denetim kaydı, /metrics"]
        ISCI["<b>worker</b><br/>görev işçisi<br/>ucus, rota, toplu, backtest,<br/>canli_veri, openaip, ml_veri, ml_egitim"]
        DB[("<b>db</b> PostgreSQL 16<br/>uçuşlar, ölçümler, görev kuyruğu,<br/>SIGMET, kısıtlı sahalar, küp kataloğu,<br/>ml_ornekleri, denetim")]
        DISK[("Paylaşılan disk<br/>ERA5 dilimleri, ARCO önbelleği,<br/>OpenSky Parquet önbelleği,<br/>GFS küpleri, model deposu")]
    end

    H3D & SIM -->|"HTTPS + X-API-Key"| API
    STR & CLI -.->|"paket modüllerini doğrudan çağırır"| DB
    MCP --> DB
    API -->|"görev ekle"| DB
    ISCI -->|"FOR UPDATE SKIP LOCKED"| DB
    ISCI -->|"NOTIFY uyarı"| DB
    DB -->|"LISTEN"| API
    API & ISCI --> DISK
```

| Konteyner | Sorumluluk | Teknoloji |
|---|---|---|
| api | REST/WebSocket, kimlik ve rol, hafif hesaplar (tahmin, rota simülasyonu), görev kuyruğuna ekleme, SIGMET zamanlayıcısı | FastAPI, uvicorn, SQLAlchemy (asyncpg + psycopg2) |
| worker | Uzun işler: uçuş analizi, toplu analiz, backtest, canlı veri, openAIP, ML veri hattı ve eğitim | Python iş parçacıkları, kalp atışı, bayat görev kurtarma |
| db | Tüm kalıcı durum, görev kuyruğu, dağıtık kilit (advisory lock), hız sınırı sayaçları | PostgreSQL 16, Alembic |
| Disk önbellekleri | Izgara verisi (NetCDF/Zarr) ve rota önbelleği; meta veri DB'deki katalogda | NetCDF, Parquet |

## 3. Bileşenler

`src/turbulans_radar/` paketleri ve bağımlılık yönü (üstteki alttakini kullanır).

```mermaid
flowchart TB
    subgraph sunum["Sunum"]
        api["api/<br/>api_servisi, semalar,<br/>metrikler, rota_onbellegi"]
        arayuz["arayuz/<br/>harita (Folium), web_arayuzu"]
        cli["cli/<br/>demo, statik_indir,<br/>veri_kontrol, mcp"]
    end
    subgraph uygulama["Uygulama"]
        isci["isci/<br/>gorev_iscisi"]
        analiz["analiz/<br/>ucus_analizi, toplu_analiz"]
        dogrulama["dogrulama/<br/>rota_backtest, bagimsiz_kanit,<br/>sigmet_dogrulama"]
        ml["ml/<br/>ml_veri_hatti, ml_otomatik_egitim,<br/>turbulans_ml_modeli, degerlendirme,<br/>edr_kalibrasyonu"]
        rota["rota/<br/>rota_optimizasyonu (A*),<br/>risk_katmanlari"]
    end
    subgraph alan["Alan (fizik)"]
        fizik["fizik/<br/>eslestirme, turbulans_indeksleri,<br/>birim_donusumleri, kalibrasyon"]
    end
    subgraph altyapi["Altyapı"]
        veri["veri/<br/>era5_saglayici, veri_saglayicilari (GFS),<br/>veri_yukleme (OpenSky, küp seçimi),<br/>sigmet_saglayici, kisitli_saha, openaip"]
        depo["depo/<br/>models, veritabani, gorev_deposu,<br/>dagitik_kilit, hiz_siniri, kup_katalogu"]
    end

    api --> analiz & rota & ml & depo
    cli & arayuz --> analiz
    isci --> analiz & dogrulama & ml & veri
    analiz --> fizik & veri & depo & arayuz
    dogrulama --> rota & fizik & veri
    ml --> fizik & veri & depo
    rota --> fizik & veri & depo
    veri --> depo
```

Ortak sözleşme: tüm hava kaynakları (yerel ERA5, uçuşa özel ERA5, ARCO, GFS)
aynı şemaya normalize edilir — değişkenler `u, v, t`; boyutlar `valid_time`,
`pressure_level` (hPa), `latitude` (azalan), `longitude` (-180..180). Böylece
`fizik/` ve `rota/` verinin kaynağını bilmez.

## 4. Veri akışı: uçuş analizi

```mermaid
flowchart LR
    A["Uçuş no + tarih"] --> B{"OpenSky Parquet<br/>önbelleği"}
    B -->|"yok"| C["Trino sorgusu<br/>callsign → icao24 → state vector"]
    C --> B2["önbelleğe yaz<br/>(uçuş ≥24 sa önce bittiyse)"]
    B -->|"var"| D
    B2 --> D["Barometrik irtifa → basınç<br/>(yoksa GPS irtifası)"]
    D --> E{"Yerel küp<br/>kapsıyor mu?"}
    E -->|"hayır, ERA5 dönemi"| F["CDS dilimi<br/>(kota + dağıtık kilit)<br/>başarısızsa ARCO"]
    E -->|"hayır, son 48 sa"| G["Canlı GFS"]
    E -->|"evet"| H
    F & G --> H["Eşleştirme: TI1, TI2, VWS,<br/>deformasyon, diverjans, Richardson,<br/>EDR proxy (kapsam dışı = NaN)"]
    H --> I[("ucuslar,<br/>edr_olcumleri")]
    H --> J["Folium haritası"]
    I --> K["API: GeoJSON/CSV, 3B harita,<br/>backtest, WebSocket uyarısı"]
```

## 5. Veri akışı: ML veri hattı ve eğitim

```mermaid
flowchart LR
    P1["IEM PIREP arşivi<br/>+ artımlı IEM"] --> P2["Seyir irtifası filtresi<br/>28–42 bin ft (feet)"]
    P2 --> P3[("ml_ornekleri<br/>durum: bekliyor")]
    N["API zamanlayıcısı (ML_GECE_ISI_SAATI)<br/>ya da POST /ml/gece-isi"] --> W["işçi: ml_veri"]
    P3 --> W
    W --> G["Gün/bölge gruplama<br/>(hücre-saat sınırı)"]
    G --> CDS["CDS dilimi, 7 seviye + bağıl nem<br/>gecelik 30, günlük 150 istek, 500 MB/gün"]
    CDS --> OZ["Özellik çıkarımı<br/>(300/250/200 hPa, analizle aynı kod)"]
    CDS --> DEP[("Pencere deposu<br/>±1°, ±1 sa, NetCDF")]
    OZ --> P4[("ml_ornekleri<br/>eslesti + özellikler<br/>+ pencere_dosyasi")]
    DEP -.->|"yeni özellik: CDS'siz yeniden hesap"| OZ
    P4 --> E["işçi: ml_egitim<br/>gün bazlı gruplu CV, Platt,<br/>konformal eşik, bootstrap GA"]
    E --> K{"Zamansal holdout:<br/>TI1'i +0,02 AUC geçiyor mu?<br/>Aktif modeli F1'de geçiyor mu?"}
    K -->|"evet"| AKT["Aktif model"]
    K -->|"hayır"| SUR["Yalnızca sürüm<br/>(geri alınabilir)"]
```

## 6. Çapraz konular

| Konu | Uygulama | Yer |
|---|---|---|
| Kimlik ve yetki | Yönetici/pilot rolleri, kişi/cihaz başına anahtar, WebSocket bileti | `api/api_servisi.py` |
| Kötüye kullanım | İstemci başına dakikalık sınır, ağır hesap eşzamanlılık tavanı, gövde boyutu sınırı | `depo/hiz_siniri.py`, `config.py` |
| Dış kota | CDS günlük/gecelik istek sınırı kod seviyesinde | `veri/era5_saglayici.py` |
| Eşzamanlılık | Kuyruk `SKIP LOCKED`, indirmelerde advisory lock | `depo/gorev_deposu.py`, `depo/dagitik_kilit.py` |
| Gözlemlenebilirlik | JSON log, Prometheus `/metrics`, derin sağlık, kaynak durumu tablosu, denetim kaydı | `loglama.py`, `api/metrikler.py` |
| Sırlar | `.env` / Docker secret; gitleaks (pre-commit + CI) | `CONTRIBUTING.md` |
| Fail-safe | Güvenli rota yoksa öneri yapılmaz; veri yoksa uydurma değer yok | `docs/SISTEM_KARTI.md` §4 |
