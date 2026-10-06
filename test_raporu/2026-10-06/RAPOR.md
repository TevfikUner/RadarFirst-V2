# Türbülans Radar: Uçtan Uca Denetim Raporu (6 Ekim 2026)

> Kapsam: depo `master` @ `6084a58` (Madde 3 dahil), dal `denetim/2026-10-06`. Denetim sırasında proje kodu
> değiştirilmedi. Geliştirme DB'sine yalnızca kullanıcının izin verdiği yazımlar yapıldı: denetim kaydı satırları,
> SIGMET güncelleme, canlı GFS küpü, THY322'nin yeniden analizi ve yeniden backtest'i. Bugünün yedeği
> (`db_yedekleri/turbulans_20261006.dump`) işlemlerden önce vardı.
> Çıktılar sertifikalı EDR değildir. Sistem operasyonel karar aracı değil, karar destek aracıdır.

## Yönetici özeti

1. **Genel olgunluk: iyi; prototipten "ürün adayı"na geçmiş.** 809 testten 806'sı geçti (2'si `ag` olduğu için
   hariç, 1'i atlandı), kapsam %84,0. Lint temiz, Docker yığını ve duman testi geçti, 10/10 güvenlik denetimi beklendiği gibi.
2. API'nin çekirdek davranışı belgelerle tutarlı. A* türbülanstan ve kısıtlı sahadan kaçınıyor, kapsam dışında
   uydurma iyileşme göstermiyor, SIGMET'te fail-safe ("ÖNERİ YOK") çalışıyor. Yeniden üretilen backtest
   README tablosuyla birebir aynı.
3. **En önemli hata:** AWC'den gelen `validTimeFrom=0` değerli bir SIGMET, arşiv başlangıcını 1970 yapıyor. Bu yüzden 2019 uçuşları
   "bağımsız kanıtla kapsanıyor" gibi raporlanıyor ve bilimsel dürüstlük ilkesi ihlal ediliyor.
4. **İşletim riski:** Canlı GFS sağlayıcısı (UCAR THREDDS) bugün önce HTTP 500 ve zaman aşımı verdi, ikinci denemede
   120 sn'de indi (belgede ~15 sn). Son başarılı indirmeden bu yana 6 gün geçmişti. Sağlık raporu o sırada `bozulmus`, GFS indikten sonra `ayakta`.
5. **Bilimsel durum:** TI1 orta düzeyde ayırt edici (ROC-AUC 0,679 [0,660–0,697], 73 gün). Aktif RF modeli TI1'i
   küçük ama anlamlı farkla geçiyor (+0,030 [0,024–0,037]; değerlendirmede eğitim sızıntısı var). Konformal
   "belirsiz" oranı %63.

**Genel not: 7,5 / 10.** Mühendislik tarafı güçlü. Puanı düşürenler: veri sağlayıcı sağlamlığı, birkaç veri
bütünlüğü hatası ve doğrulama kanıtının ince olması (tek Türkiye uçuşu, ABD dışı bağımsız kanıt yok).

## Bileşen durumu

| Bileşen | Durum | Kanıt / not |
|---|---|---|
| Kurulum | ✅ | Python 3.14.4, Docker 29.1.3, Compose 2.40.3. `.env`: POSTGRES_*, API_ANAHTARI, API_PILOT_ANAHTARI, CDSAPI_RC_DOSYASI tanımlı; OpenSky için yalnızca `OPENSKY_USERNAME` var (OAuth tarayıcı girişi). Playwright + Chromium venv'de zaten kuruluydu, yeni kurulum yapılmadı. |
| Lint | ✅ | `ruff check` temiz, `ruff format --check` 203 dosya temiz, bağımlılık kilidi 3/3, `alembic` current = head (`c6f2a8d4e1b9`) |
| Birim | ✅ | 542 geçti / 0 kaldı (76 sn) |
| Veritabanı | ✅ | 235 geçti / 0 kaldı (144 sn), ayrı `-test` DB |
| Gerçek veri | ⚠️ | 52 geçti, **1 kaldı** (performans, 30,7 sn > 30 sn sınırı), 3 atlandı (2 CDS kimliği yok, 1 kökteki eski model) |
| Tarayıcı | ✅ | 8/8 (96 sn) |
| Docker | ✅ | `up --build --wait` 56 sn, duman testi 5/5, api/worker son 100 log satırında ERROR/Traceback yok. Worker'da healthcheck yok. |
| API | ✅ | 36 yol / 39 uç nokta. Depodaki `openapi.json` canlı şemayla birebir aynı. Tüm senaryolar beklenen HTTP kodunu döndürdü. |
| Simülasyon / A* | ✅ | 4 senaryo + profil listesi, aşağıdaki tablo |
| TI1 fiziği | ⚠️ | Çalışıyor, ama `ocak_2019` küpü 3 seviyeli: THY322'de 720 değerde yalnızca 10 benzersiz TI1 (veri_kontrol uyarısı) |
| ML | ⚠️ | API'de aktif RF (7817 örnek) var. Yerel CLI/Streamlit ise kökteki eski modele bakıp onu reddediyor (bulgu 3). |
| Veri sağlayıcılar | ⚠️ | ERA5 yerel ✅, SIGMET ✅ (bulgu 1 hariç), GFS ⚠️ (1. deneme hata, 2. deneme 120 sn), OpenSky ⏭️ (OAuth; önbellekteki THY322 kullanıldı) |
| Backtest | ⚠️ | DB'deki satır 01.10'dan kalmaydı (FL300, "yok", 0/0/0). Yeniden üretilince README ile aynı (0,19 / 0,32 / 0,00, yanal). `sigmet_arsivi` kanıtı yanlış (bulgu 1). |
| Web arayüzleri | ⚠️ | 0 konsol hatası, demo akışı ve yeniden hesaplama çalışıyor. Lejant sonuç tablosunu örtüyor, harita3d notu eski, Folium saati +3 sa kaymış. |
| Güvenlik | ✅ | Anahtarsız/yanlış anahtar 401, pilot→yönetici işlemi 403 (4 uç), biletsiz / `?api_key=` / sahte biletli WS 403 |

## Faz 2: test ayrıntısı

| Katman | Geçti | Kaldı | Atlandı | Süre | JUnit |
|---|---|---|---|---|---|
| birim | 542 | 0 | 0 | 76 sn | `junit_birim.xml` |
| veritabani | 235 | 0 | 0 | 144 sn | `junit_veritabani.xml` |
| gercek_veri | 52 | 1 | 3 | 118 sn | `junit_gercek_veri.xml` |
| tarayici | 8 | 0 | 0 | 96 sn | `junit_tarayici.xml` |
| tümü (kapsamlı) | 806 | 0 | 1 | 260 sn | `junit_tum_kapsam.xml`, `kapsam/index.html` |

Katmanların toplamı 809'u aşıyor çünkü bazı testler birden fazla işaret taşıyor. Toplanan test sayısı 809 (`-m "not ag"` ile 807).

**Başarısız test:** `tests/test_performans.py::test_buyuk_rota_vektorel_eslestirme_makul_surede_biter`.
55 000 nokta eşleştirmesi 30,7 sn sürdü, sınır 30 sn. Kök neden tahmini: ölçüm aynı anda süren gece ML işi ve imaj
derlemesi yükü altında alındı. Tek başına iki kez koşuldu, ikisinde de geçti (iki performans testi toplam 61,6 sn, test başına
≈30 sn). Yani sınırın payı yok, test kırılgan.

**Betiğin doğrulaması:** `scripts/tam_denetim.sh` (tam mod, `RAPOR_KLASORU=test_raporu/_deneme_tam`) yüksüz ikinci koşuda 838 sn'de
22/22 adımı ✅ tamamladı. `gercek_veri` 53/53 geçti, kapsam yine %84,0, Playwright konsol hatası 0. `--hizli` modu 143 sn sürdü.
Bu ikinci koşu da performans hatasının yükten kaynaklandığını doğruluyor.

**Kapsamı en düşük 10 modül:** `cli/kimlik_kontrol` %0 · `cli/ornek_ucus_bul` %0 · `cli/veri_kontrol` %0 ·
`arayuz/web_arayuzu` %0 · `cli/demo_ekranlari` %27 · `cli/performans_olcumu` %39 · `ml/gosterge_degerlendirme` %52 ·
`ml/sonuc_paketi` %55 · `analiz/toplu_analiz` %60 · `fizik/edr_esleme` %60.

**En yavaş 10 test:** `test_buyuk_rota_veritabanina_yazma` 33,5 sn · `test_buyuk_rota_vektorel_eslestirme` 30,8 sn ·
`test_simulasyon_uctan_uca_calisir` 14,2 sn · `test_kisitli_sahadan_kacinma_ozeti` 13,4 sn ·
`test_kalan_risk_yoksa_kabin_bildirimi_cikmaz` 13,2 sn · `test_kalan_riskte_bolumler_ve_kabin_onerisi` 12,6 sn ·
`test_kapsam_disinda_risk_hesaplanmadi` 12,3 sn · `test_vektorel_eslestirme_nokta_nokta_referansla_birebir_ayni` 6,3 sn ·
`test_tek_basina_ti1_kadar_iyi_olmayan_aday_aktiflestirilmez` 5,7 sn · `test_cli_surumleri_listeler_ve_geri_alir` 5,7 sn.

## Faz 3: yığın ve sağlık

`/saglik?derin=true` → **`bozulmus`**. Tek bozuk alt sistem `canli_gfs: hata`. Ayrıntısı: `ReadTimeout`, son başarılı
indirme 2026-09-30 12:42Z (144 sa önce). `sigmet`, `gorev_kuyrugu`, `kisitli_sahalar`, `ml_gece_isi`, `yedek`, `kup_onbellegi`,
`fir_sinirlari` → tamam. `statik_dosyalar` → yerel. Yanıtlar: `api/saglik_derin*.json`, `api/sistem_durum*.json`.
GFS'nin ikinci denemede başarıyla inmesinden sonra son demo koşusunda (`log/demo_goster_hepsi.txt`) genel durum **`ayakta`**'ya
döndü. Bozulma yalnızca sağlayıcı kaynaklıydı.

Sıra notu: Gece işi (`ml_veri`) çalışırken yalnızca `api` yeniden derlendi, böylece iş kesilmedi. İş 459/500 MB ile
`tamamlandi` olunca tüm yığın `--build` ile yeniden kuruldu. Simülasyon/türbülans sonuçları bu son yığından alındı.

## Faz 4: fonksiyonel senaryolar

### A) Simülasyon (pilot anahtarı, A320)

| Senaryo | Yanıt | Rüzgâr kaynağı | Strateji | Süre dk (N→O) | Mesafe km | Yakıt kg | CO2 kg | FL | maks TI1 (N→O) | Riskli nokta | Kısıtlı saha ihlali |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1. İstanbul→Antalya, 2019-01-05 12Z, 28000 ft | 0,61 sn | era5_gercek | yanal (7 km) | 38,6 → 38,8 | 485 → 489 | 1542 → 1554 | 4874 → 4911 | 280→**270** | 8,65e-7 → 7,81e-7 | 1 → 0 | 0 → 0 |
| 2. İstanbul→Ankara, 2019-01-15 10Z, 34000 ft | 0,08 sn | era5_gercek | yok (gereksiz) | 25,6 = 25,6 | 365 | 1023 | 3232 | 340→**330** | 6,84e-7 | 0 → 0 | 0 |
| 3. Kapsam dışı (2018-06-15) | 0,03 sn | **era5_kapsam_disi** | yok | 26,4 = 26,4 | 365 | 1057 | 3341 | 350 | — | — (hesaplanmadı) | 0 |
| 4. Malatya→Musul, bugün 14Z, FL350 (canlı) | 3,54 sn | gfs_tahmin | yanal (56 km) | 33,7 → 35,9 | 481 → 511 | 1347 → 1437 | 4256 → 4540 | 350 | 1,61e-6 → 1,46e-6 | 6 → 5 | **11 → 0** |

- **1. senaryo (demo):** Türbülanstan kaçındı (riskli 1→0, `kacinma_tam_guvenli`). FL280 yön kuralına aykırı olduğu için FL270'e
  yuvarlandı ve uyarı verildi (Madde 3 çalışıyor).
- **3. senaryo:** Dürüst. `ruzgar_hesaba_katilamadi`, TI1 `None` ("0" değil), optimize = normal, iyileşme iddiası yok.
- **4. senaryo:** Suriye (örnek veri) atlatıldı, Irak (varış) koridoru muaf, `kisitli_saha_ornek_veri` uyarısı var, 5 aktif
  SIGMET uygulandı, kalan risk dürüstçe bildirildi (`ti1_riski_kismen_kaldi`). Aynı rota 40 dk önce, GFS inmemişken ve
  Bağdat FIR'inde bandı okunamayan iki TS SIGMET aktifken **"ÖNERİ YOK"** döndürmüştü. Fail-safe tablosundaki
  davranışla aynı.
- Tarayıcıdaki demo (41.0, 29.0 → 40.5, 43.5, FL350, 2019-01-15 20Z) DEMO_SENARYOSU'yla aynı sonucu verdi: ~198 NM / ~24 dk
  riskli bölüm, FL370'e tırmanma, riskli 12 → 1, yakıt +%0,77. "Uçuş sırasında yeniden hesapla" çalıştı (yanal, ≤5 NM).
- Uçak profilleri: 4 profil, 0,002 sn.

### B) Türbülans tahmini ve ML

| Nokta | HTTP | Süre | Kapsamda | TI1 (s⁻²) | ML olasılık | ML durum |
|---|---|---|---|---|---|---|
| ERA5: 40.0N 33.0E, 2019-01-15 12Z, FL350 | 200 | 1,24 sn | evet | 5,09e-7 (riskli değil) | 0,60 | belirsiz |
| Kapsam dışı: aynı nokta, 2018-06-15 | 200 | 0,02 sn | hayır | — | — | — |
| Canlı GFS: 37.5N 40.5E, bugün 14Z | 200 | 0,09 sn | evet | 6,41e-8 | 0,32 | dusuk_risk |

`model-bilgisi`: Random Forest, 2026-10-05, eğitim/test 7817/1451, ROC-AUC 0,67, recall 0,59, F1 0,62, belirsiz oranı %63.
`model-versiyonlari`: 8 sürüm. `ml/durum`: 7115 eşleşmiş örnek (günün başında 6919), 81 005 bekleyen, **73 eşleşmiş gün / 60 baraj** (eğitime hazır), bugün
459/500 MB, aktif sürüm `2026-10-05T14-27-30…_75a36885`. Bugünkü aday (`…ed019acb`) aktif modeli geçemediği için
yalnızca saklandı (holdout F1 0,680 vs 0,701). Kapılı aktivasyon çalışıyor.

### C) Veri

| Adım | HTTP | Süre | Sonuç |
|---|---|---|---|
| `GET /veri/kupler` | 200 | 0,004 sn | 36 küp (ERA5 Türkiye + KD ABD, eski bir GFS) |
| `POST /sigmet/guncelle` | 200 | 1,09 sn | 142 kaydedildi, kaynak hatası yok |
| `GET /sigmet` | 200 | 0,007 sn | 129 geçerli SIGMET, **Ankara FIR (LTAA): 2**, İstanbul FIR: 0 |
| `GET /kisitli-sahalar` | 200 | 0,006 sn | 87 saha (85 `aip_enr51` + 2 `ornek`) |
| `POST /veri/canli/hazirla` (36–42N, 26–45E, 6 sa), 1. deneme | 202 | 188,7 sn | ❌ `hata`: "Canlı hava verisi sağlayıcısından geçerli veri alınamadı" (UCAR HTTP 500 / ReadTimeout) |
| aynı, 2. deneme | 202 | **120,3 sn** | ✅ `tamamlandi` |

### D) Uçuş verisi

- DB'de tek uçuş var: **THY322 / 2019-01-15** (kalkış LTBA, varış `"NaN"`, bulgu 2). OpenSky önbelleğinde de yalnızca bu uçuş var.
- `turbulans-analiz THY322 2019-01-15` 3 sn sürdü: 1614 nokta, 720'si eşleşti (%44,6), TI1 1,81e-7 / 6,45e-7 / 8,36e-7, 43 nokta
  orta-şiddetli. Harita: `ciktilar/turbulans_haritasi_THY322_2019-01-15.html` (yenilendi).
- `GET /ucuslar/THY322/2019-01-15` 200 (0,02 sn), CSV 171 KB, GeoJSON 517 KB, `sigmet-dogrulama` 200 (ABD dışı olduğu için 0 SIGMET; doğru).
- `veri_kontrol`: küp 744 saat × 3 seviye (300/250/200) × 25×77. **10 benzersiz TI1 / 720**, aracın kendi "küp çok kaba" uyarısı çıktı.

### E) Backtest

| Kaynak | Seyir | Bölüm | Riskli oran (gerçek / BD / A*) | Strateji | A* ek süre |
|---|---|---|---|---|---|
| README (6 Eki) | FL300 → FL290 | 116 km | 0,19 / 0,32 / 0,00 | yanal | +0,4 dk |
| DB, denetimden önce (01.10 satırı) | FL300 | 116 km | 0 / 0 / 0 | yok | — |
| **Bugün yeniden üretilen** | FL300 (A* FL290) | 116 km | **0,19 / 0,32 / 0,00** | yanal | +0,43 dk |

THY72C ve THY606 DB'de yok. README bunu zaten belirtiyor. Filo özeti tek uçuşa dayanıyor.

### F) ML / kalibrasyon (salt okuma)

| Ölçüm | Belge | Bugün |
|---|---|---|
| EDR ölçek katsayısı | 0,27 [0,25, 0,28] (6218 PIREP / 64 gün) | **0,265 [0,250, 0,280]** (7113 / 73 gün). İstemdeki 0,40 [0,35, 0,44] eski fiziğe ait. |
| Tanh ölçeği test MSE (yeni / sabit ortalama) | 0,076 / 0,067 | 0,0755 / 0,0671 (tanh, sabit ortalamadan iyi değil; belgeyle tutarlı) |
| TI1 ROC-AUC | 0,67 [0,65, 0,69] | **0,679 [0,660, 0,697]** |
| Aktif model ROC-AUC (tüm eşleşmiş veri, sızıntılı) | holdout'ta TI1'i geçti | 0,709 [0,692, 0,725]; fark +0,030 [0,024, 0,037] |
| `turbulans-ml --listele` | — | Yerelde 3 eski sürüm, konteynerde 8 sürüm (bulgu 3) |

`turbulans-edr-kalibrasyon` ve `turbulans-ml-degerlendirme` yalnızca stdout'a yazıyor, dosya ya da config değiştirmiyor.

### G) Güvenlik

| Deneme | Beklenen | Sonuç |
|---|---|---|
| Anahtarsız / yanlış anahtar `GET /ucuslar` | 401 | ✅ 401 / 401 |
| Pilot: `GET /sistem/durum`, `POST /sigmet/guncelle`, `DELETE /kisitli-sahalar/x`, `DELETE /ucuslar?…` | 403 | ✅ 4 × 403 |
| Anahtarsız `/saglik` | 200 | ✅ |
| `/ws/uyarilar` biletsiz, `?api_key=` ile, sahte biletle | red | ✅ 3 × HTTP 403 |

## Faz 5: görseller

`ekran/`: 8 PNG + `simulasyon_akisi.webm` (≈30 sn, 1280×720). Playwright konsol hatası: **0**.
Folium haritası, harita3d (THY322 + zaman kaydırıcısı + SIGMET katmanı), Swagger (39 blok) ve Streamlit açılış ekranı alındı.

## Belgelerde iddia edilen ve bugün ölçülen

| Ölçüt | Belge | Bugün | Değerlendirme |
|---|---|---|---|
| Test sayısı | 753 (SISTEM_KARTI, 4 Eki); istemde 307 | 809 toplandı, 806 geçti | Belge geride kalmış |
| Kod kapsamı | ~%84 | %84,0 | ✅ |
| A* / rota kararı süresi | 0,02–0,27 sn (veri hazırken) | 0,03–0,08 sn (kısa rota), 0,61 sn (İst→Antalya, ilk istek), 3,5 sn (canlı GFS, küp yükleme dahil) | ⚠️ İlk/soğuk istek aralığın dışında |
| GFS indirme | ~15 sn (Türkiye) | 1. deneme hata (189 sn), 2. deneme 120 sn | ❌ Sağlayıcı yavaş/kararsız |
| Backtest THY322 | 0,19 / 0,32 / 0,00 yanal | Aynı (yeniden üretimden sonra) | ✅ DB satırı bayattı |
| EDR katsayısı | 0,27 [0,25–0,28] | 0,265 [0,250–0,280] | ✅ |
| TI1 ROC-AUC | 0,67 [0,65–0,69] | 0,679 [0,660–0,697] | ✅ (daha fazla örnek) |
| ML (aktif) | RF, 5 Eki, TI1'i geçti | RF, 7817 örnek, CV ROC-AUC 0,67; bugünkü aday geçemedi | ✅ |
| Demo (THY322 harita) | 1614 nokta, 720 hesaplandı | 1614 / 720 | ✅ |
| Demo (simülasyon) | ~198 NM / 24 dk, FL370, 12→1, %0,8 | ~198 NM / 24 dk, FL370, 12→1, %0,77 | ✅ |
| Canlı SIGMET | 126 SIGMET (26 Eyl) | 129 geçerli, Ankara FIR 2 | ✅ |

## Bulunan hatalar (önem sırasıyla, hiçbiri uygulanmadı)

**1. [Yüksek, bilimsel dürüstlük] SIGMET `validTimeFrom=0` 1970 tarihli kayıt üretiyor; arşiv 1970'ten başlıyor sanılıyor.**
- Yer: [src/turbulans_radar/veri/sigmet_saglayici.py:68](../../src/turbulans_radar/veri/sigmet_saglayici.py#L68) (`_zaman`), `:240`
  (yalnızca `None` reddediliyor), [arsiv_baslangici :416](../../src/turbulans_radar/veri/sigmet_saglayici.py#L416),
  [dogrulama/bagimsiz_kanit.py:138](../../src/turbulans_radar/dogrulama/bagimsiz_kanit.py#L138).
- Kanıt: `sigmetler` id 3637, `isigmet`, NFFF (Fiji) TURB, `gecerlilik_baslangic = 1970-01-01`, ham metin `VALID 312345/010345`.
  `arsiv_baslangici()` 1970 döndürüyor. THY322 (2019) backtest'i `kanit_kaynaklari=["sigmet_arsivi"]`, `*_turb_sigmet=0` diyor.
  README ise "2019 Türkiye uçuşlarında kanıt alanları dürüstçe boş" diyor.
- Tekrar üretme: `SELECT min(gecerlilik_baslangic) FROM sigmetler;` → 1970. Ardından `POST /api/v1/backtest/ucuslar/THY322/2019-01-15`.
- Önerilen düzeltme: `_zaman` ≤ 0 epoch değerini `None` saysın (kayıt `gecerlilik_yok` olarak elensin ya da ham metindeki
  `VALID ddhhmm/ddhhmm` alanından türetilsin). `arsiv_baslangici` makul olmayan değerleri dışlasın (örn. `alinma_zamani - SIGMET_SAKLAMA_GUN`'den
  eskileri). Mevcut satır için migration/temizlik gerekir (önce `-test` DB'de).

**2. [Orta, veri bütünlüğü] Varış havalimanı `"NaN"` metni olarak yazılıyor.**
- Yer: [src/turbulans_radar/depo/veritabani.py:252](../../src/turbulans_radar/depo/veritabani.py#L252) (`bos_ise_al`).
- Kanıt: `GET /ucuslar` → THY322 `varis_havaalani: "NaN"`. `turbulans-analiz` ile yeniden analizden sonra da aynı.
- Önerilen düzeltme: `pd.isna(deger)` ise `None` döndür. Mevcut kayıtları `UPDATE … SET varis_havaalani=NULL WHERE varis_havaalani='NaN'` ile temizle.

**3. [Orta, tutarlılık] Yerel araçlarla konteyner farklı model deposunu görüyor.**
- Yer: [src/turbulans_radar/config.py:517](../../src/turbulans_radar/config.py#L517) (`MODEL_KLASORU` varsayılanı `.`). Compose
  `/app/model_deposu` volume'unu kullanıyor; `.env`'de `MODEL_KLASORU` yok.
- Kanıt: Streamlit kenar çubuğu "aktif ML modeli eski veri hattıyla eğitildiği için kullanılmıyor" diyor, oysa API'de RF aktif
  (`ekran/07_streamlit.png`). `turbulans-ml --listele` yerelde 3, konteynerde 8 sürüm gösteriyor. Yerel `turbulans-ml-degerlendirme` model metriği üretmiyor.
  Kökteki `turbulans_ml_modeli.joblib` 167 örnekli eski model; kapı onu doğru şekilde reddediyor.
- Önerilen düzeltme: Yerel kullanım için belgelere/`.env.example`'a model deposunun ortak bir yolunu ekle (ya da Streamlit'i konteynerde
  çalıştır). Kökteki eski 167 örnekli dosyaları arşivle.

**4. [Orta, işletim] Canlı GFS sağlayıcısı kararsız ve 6 gün boyunca fark edilmedi.**
- Kanıt: `sistem/durum.canli_gfs`: son başarı 2026-09-30, `ReadTimeout`; worker logunda UCAR NCSS `HTTP/1.1 500`. Doğrudan katalog isteği 30 sn'de yanıtsız kaldı.
  İkinci deneme 120 sn sürdü.
- Sistem doğru davranıyor (rüzgârsız hesap, `canli_veri_hazirlaniyor`, `bozulmus`). Eksik olan, düzenli bir ısınma isteği ya da alarm.
- Önerilen düzeltme: n8n ile periyodik `/veri/canli/hazirla` ısınması ve `canli_gfs` için 24 sa'ten eski başarıya alarm. B planı
  olarak ikinci bir sağlayıcı (README'deki ECMWF Open Data notu). GFS küplerinde `model_calisma_zamani` NULL kalıyor; açıklama
  "model çalıştırması bilinmiyor UTC" diyor ([rota_optimizasyonu.py:1532](../../src/turbulans_radar/rota/rota_optimizasyonu.py#L1532)).

**5. [Düşük–orta, test] Performans testinin payı yok.**
- Yer: `tests/test_performans.py:72` (30 sn sınırı). Gerçek süre ≈30 sn, yük altında 30,7 sn.
- Önerilen düzeltme: Sınırı göreli yap (referans ölçüme oranla) ya da `gercek_veri` koşusundan ayrı, yüksüz bir işte çalıştır.

**6. [Düşük, arayüz] Simülasyon sayfasında lejant sonuç tablosunu örtüyor.**
- Yer: `web/ucus_simulasyonu.html:71` (`#lejant` sağ alt, sabit). 1600×950'de "Seviye / İz bulutu / SIGMET-saha / Strateji"
  satırları lejantın altında kalıyor (`ekran/01_simulasyon_sonuc.png`).
- Önerilen düzeltme: Sonuç paneli açıkken lejantı sola al ya da daraltılabilir yap.

**7. [Düşük, tutarlılık] harita3d'deki TI1 notu eski rakamları gösteriyor.**
- Yer: `web/harita3d.html:135`: "1600 seyir PIREP'inde ROC-AUC 0.69". Simülasyon sayfası ve SISTEM_KARTI ise "6218 PIREP, 0.67" diyor.
- Önerilen düzeltme: Notu `GET /turbulans/model-bilgisi` ya da `TI1_GUVENILIRLIK_NOTU`'ndan alacak şekilde tek kaynağa bağla.

**8. [Düşük] Folium zaman etiketi tarayıcının yerel saatini gösteriyor.**
- Yer: `src/turbulans_radar/arayuz/harita.py:165-194` (`TimestampedGeoJson`, ISO zaman). THY322 19:39Z, ekranda 22:39 görünüyor (`ekran/08_folium_THY322.png`).
- Önerilen düzeltme: Etikete "UTC" yaz ya da zamanı UTC'ye sabitle.

**9. [Düşük, belge] `ti1_guvenilirlik_notu` her zaman dönmüyor.**
- `POST /turbulans/tahmin` kapsam dışında ve "hazırlanıyor" yanıtında bu alanı boş bırakıyor. README ve SISTEM_KARTI ise "her zaman bulunur" diyor
  (`api_servisi.py:1215` yalnızca hesaplanan dalda). Ya belge düzeltilmeli ya da alan her yanıta eklenmeli.

**10. [Düşük, işletim] Worker'da healthcheck yok.** `docker compose --wait` worker'ı yalnızca "çalışıyor" diye kabul ediyor. Kuyruk kalp
atışına dayalı bir healthcheck eklenebilir.

**Not (hata değil):** WSL içindeki git `core.autocrlf` tanımsız olduğu için 159 dosyayı "değişmiş" gösteriyor. Windows git temiz.
`git -c core.autocrlf=true` kullanılmalı. Streamlit varsayılan olarak 0.0.0.0'a bağlanıyor ("External URL"); yalnızca yerelde
kullanılacaksa `--server.address 127.0.0.1` önerilir. `config.EDR_OLCEKLENDIRME_KATSAYISI_ESKI = 0.23` ama belgeler "önceki 0.40" diyor;
kalibrasyon çıktısındaki `eski_katsayi` alanı yanıltıcı olabilir.

## Test edilemeyenler ve nedenleri

| Bileşen | Neden |
|---|---|
| `-m ag` testleri, CDS/ERA5 indirmesi, `POST /ml/gece-isi` | Kota. Kullanıcı yasakladı. Gece işi zamanlayıcıyla zaten çalışıp bitti. |
| OpenSky/Trino canlı çekim | ⏭️ atlandı: OAuth (tarayıcı girişi). Önbellekteki THY322 kullanıldı. |
| THY72C, THY606, N10VZ | DB'de ve OpenSky önbelleğinde yok. |
| ABD dışı bağımsız kanıt (IEM PIREP/SIGMET) | Türkiye uçuşlarını kapsamıyor (belgelendiği gibi). |
| Sanal PIREP canlı akışı, n8n, MCP sunucusu | Bu denetimin kapsamında çalıştırılmadı (birim/DB testleri geçti). |
| 2 `gercek_veri` testi (`test_era5_gercek_ag`) | WSL ortamında CDS kimliği yok, atlandı. |

## Bilimsel sınırlamalar

- **TI1 ayırt ediciliği orta:** ROC-AUC 0,679 [0,660–0,697] (73 gün, 7113 PIREP; yalnızca ABD). Türkiye'ye genellenemez.
- **PUE502 kör noktası** hâlâ geçerli: TI1 aktif TURB SIGMET'ini görmedi. Güvenliğin asıl dayanağı SIGMET sert kısıtı. Bugünkü
  denetimde de güvenli rota kararını SIGMET ve kısıtlı sahalar belirledi.
- **Döngüsel backtest:** A* TI1'i düşürüyor, başarı yine TI1 ile ölçülüyor. Tek Türkiye uçuşu var ve onun bağımsız kanıtı da (bulgu 1)
  aslında yok.
- **ML:** Aktif RF modeli TI1'i küçük bir farkla geçiyor (+0,03 ROC-AUC). Pozitif oran ~%52 (raporlama yanlılığı). Konformal "belirsiz"
  oranı %63, yani tahminlerin çoğunda model iki sınıfı ayıramıyor. **Eski 167 örnekli model artık geçerli değil:** kapı onu reddediyor,
  API 7817 örnekli modeli kullanıyor. Kökteki dosya kafa karıştırıcı bir kalıntı.
- **Küp çözünürlüğü:** `ocak_2019` küpü 3 basınç seviyeli. Çevreleyen katman 50 hPa'ya düşüyor; THY322'de 720 değerin 10'u benzersiz.
- EDR proxy sertifikalı değil. Tanh ölçeği sabit ortalamadan iyi tahmin etmiyor (MSE 0,0755 vs 0,0671), yalnızca görselleştirme amaçlı.

## Öncelikli 5 sonraki adım

1. Bulgu 1'i düzelt (epoch 0 SIGMET + arşiv başlangıcı), mevcut satırı temizle ve THY322 backtest'ini yeniden üret.
2. Bulgu 2'yi düzelt (`NaN` → NULL) ve veri temizliği yap.
3. GFS için periyodik ısınma + alarm ekle; ikinci sağlayıcıyı (ECMWF Open Data) değerlendir.
4. Yerel ve konteyner model deposunu tekleştir (`MODEL_KLASORU`), kökteki eski modeli arşivle, Streamlit mesajını düzelt.
5. Doğrulama kanıtını genişlet: n8n ile daha çok uçuş analiz et (`/backtest/toplu`), Türkiye için 7 seviyeli ERA5 dilimleri kullan,
   performans testini kararlı hale getir, belgelerdeki test sayısını ve harita3d notunu güncelle.

## Kendin dene

| Ne | Nasıl |
|---|---|
| Rota simülasyonu | <http://localhost:8000/harita/ucus_simulasyonu.html>. Anahtar: `.env`'deki **`API_ANAHTARI`** (ya da `API_PILOT_ANAHTARI`). |
| 3B harita | <http://localhost:8000/harita/harita3d.html>. Uçuş **THY322**, tarih **2019-01-15**, **Yükle**. |
| Swagger | <http://localhost:8000/docs> |
| Streamlit | <http://localhost:8501> |
| Folium haritası | `ciktilar/turbulans_haritasi_THY322_2019-01-15.html` |
| Görsel pano | `test_raporu/2026-10-06/ozet.html` |
| Terminal demosu | `python scripts/demo_goster.py --bekle` (WSL: `~/.venvs/turbulans/bin/python scripts/demo_goster.py --bekle`) |
| Tam denetim | WSL'de `bash scripts/tam_denetim.sh` (`--hizli`, `--tarayicisiz`, `--build-zorla`) |
| Kapatma | `docker compose stop` · Streamlit: `wsl -d Ubuntu -- pkill -f "streamlit run"` (volume silen komut kullanmayın) |

**Simülasyon için hazır senaryolar:**
1. **Demo, türbülanstan kaçınma:** 41.0, 29.0 → 40.5, 43.5 · 35000 ft · 2019-01-15 20:00 · A320. Beklenen: büyük dairede ~198 NM / ~24 dk
   kırmızı bölüm, öneri FL370'e tırmanma, riskli 12 → 1, yakıt +%0,8, kabin bildirimi.
2. **Kısıtlı saha + canlı veri:** 38.35, 38.31 → 36.34, 43.13 · 35000 ft · bugünün saati (UTC, ≤120 sa ileri) · A320. Beklenen: GFS
   inerken önce "hazırlanıyor" uyarısı, sonra ~55 km yanal sapmayla Suriye (örnek veri) atlatılır, Irak muaf, mor kısıt ve SIGMET
   poligonları görünür. Bölgede bandı bilinmeyen aktif SIGMET varsa sonuç dürüstçe "ÖNERİ YOK" olabilir.
3. **Kapsam dışı dürüstlüğü:** 40.98, 28.82 → 40.13, 32.99 · 35000 ft · 2018-06-15 12:00. Beklenen: "Risk hesaplanmadı", optimize = normal,
   uydurma tasarruf yok.

## Dosyalar

`junit_*.xml` · `log/` (pytest, docker, duman testi, ML CLI, demo çıktıları) · `api/*.json` (her senaryonun istek ve yanıtı,
`_ozet_*.json` süre tabloları) · `ekran/` (PNG + WEBM + konsol hataları) · `kapsam/index.html` · `openapi/openapi.json` · `statik/`.
Büyük çıktılar commit'lenmedi (`.git/info/exclude`). Commit'te yalnızca bu dosya, `ozet.html` ve iki betik var.
