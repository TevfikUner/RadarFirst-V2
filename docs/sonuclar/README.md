# Sonuç paketleri

Rapordaki, sunumdaki, posterdeki ve sistem kartındaki her doğruluk sayısı buradaki bir
paketten alınır (Uzman Madde 8). Paket klasör adı kesme günüdür. Kesme, `olusturulma_zamani`
o güne kadar (dahil) olan örnekleri seçer. Gece işi eski satırları eşleştirerek günceller,
yeni satır eklemez; bu yüzden kesme canlı veritabanında veriyi dondurmaz. Bir paketi aynen
yeniden üretmek için o günün veritabanı yedeği gerekir. Her paketteki `SAYILAR.md`
sayıların tek listesidir ve elle düzenlenmez.

| Paket | Durum | Kesme |
|---|---|---|
| [`2026-10-07/`](2026-10-07/SAYILAR.md) | Ön paket (tarihçe): 80 gün, protokol modeli LR, kapı geçilmedi. | 7 Ekim 2026 |
| [`2026-10-16/`](2026-10-16/README.md) | Ek analizler (ML paketi değil): ERA5 → canlı GFS TI1 eşik eşlemesi; rota ayrıklaştırma yakınsaması. | 9–11 Ekim 2026 / Ocak 2019 |
| [`2026-10-17/`](2026-10-17/README.md) | Ek analiz (ML paketi değil): kaçınma başlangıç zamanı, kalkışta ve yolda planlama (Fikir 18). | 12–16 Ekim 2026 GFS |
| [`2026-10-18/`](2026-10-18/SAYILAR.md) | **Nihai paket.** Belgeler bu paketin sayılarını kullanır: 163 gün, protokol modeli RF, kapı geçildi (+0,033). Commit `5ddcd40`, üretim 18 Ekim 00:25 UTC; yedekten ve canlıdan birebir aynı üretildi (yedek `kalici/turbulans_20261018_dondurma.dump`). `ml_dondurma.json`: aday (GB) aktif 9 Ekim RF'yi geçemedi, saklandı. `ilk_uretim_sirasiz/`: sıralama düzeltmesinden önceki ilk üretim (GB +0,036), tarihçe. `rota_performansi`: 19 Ekim, şarjda, sıcak medyan 0,10–0,42 sn (kütle bandı hızlandırması sonrası; öncesi `rota_performansi_iyilestirme_oncesi.json`, 0,25–0,69 sn). | 18 Ekim 2026 |

| [`2026-10-29_bagimsiz_backtest/`](2026-10-29_bagimsiz_backtest/README.md) | Bağımsız rota backtest'i (#3, protokol §11): NE-ABD 2.304 simüle rota; bağımsız günlerde sapmalı 908 rotada PIREP tüpü orta-üstü payı göreli maruziyet oranı 0,71 [0,58; 0,90]; 48 günün tamamında 0,83 [0,66; 1,03]. | NE-ABD ERA5, 48 gün (2018–2020) |
| [`2026-10-28_tahmin_ufku/`](2026-10-28_tahmin_ufku/README.md) | Ek analiz (#11): GFS f024/f048'in f000'a göre TI1 tutarlılığı; Spearman 0,67 / 0,50, riskli noktaların %57 / %43'ü korunuyor. | 23–28 Ekim 2026 GFS |
| [`2026-10-28_ekonomik_deger/`](2026-10-28_ekonomik_deger/README.md) | Ek analiz (#16): REV; PIREP taban oranında en yüksek REV TI1 0,26, model 0,30, yalnız α ≈ 0,3–0,8'de pozitif. | 18 Ekim altın günler |
| [`2026-10-28_secim_kurali_maliyet/`](2026-10-28_secim_kurali_maliyet/README.md) | Ek analiz (#1b–c): `maliyet` seçim kuralı (5 dk bedel) uyarı oranı senaryolarında; önerilen rota 28/1.488'de değişti. | Ocak 2019 ERA5 |
| [`2026-10-28_protokol_farki/`](2026-10-28_protokol_farki/README.md) | §10.7 (keşifsel): 147 eğitim gününde rastgele bölme RF ROC-AUC'yi değiştirmedi (−0,001; derin RF +0,001), hafif raporları çıkarmak +0,083 (0,702 → 0,785). | 147 eğitim günü |
| [`2026-10-28_birlesik_kiyas/`](2026-10-28_birlesik_kiyas/README.md) | §10.6 (sonradan eklenen ikincil): §10'un 79 gününde temel model − birleşik EDR +0,016 [+0,010; +0,021]; birleşik EDR − TI1 +0,011. | §10 günleri (27 Ekim listesi) |
| [`2026-10-28_zaman_ornekleme/`](2026-10-28_zaman_ornekleme/README.md) | Ek analiz: 3 saatlik zaman örneklemesinin TI1'e etkisi (saatlik küpe göre Spearman 0,923, aynı karar %95,9). | Ocak 2019 ERA5 |
| [`2026-10-28_birlesik_klimatoloji/`](2026-10-28_birlesik_klimatoloji/README.md) | Ek analiz (VER-07): birleşik EDR klimatolojisine altın günlerin girmesinin etkisi yok (altın gün ROC-AUC 0,688, fark ≤ 0,0001). | 163 dondurma günü |
| [`2026-10-28_turkiye_kaymasi/`](2026-10-28_turkiye_kaymasi/README.md) | Ek analiz (VER-08): Türkiye girdileri ABD aralığında (destek dışı %3,0) ama dağılım belirgin farklı (PSI Ri 1,04, TI1 0,41); beceri ölçümü değil. | Ocak 2019 ERA5 (7 seviye) |
| [`2026-10-28_uyari_orani/`](2026-10-28_uyari_orani/README.md) | Ek analiz (ML paketi değil): toplu rota simülasyonuyla uyarı/sapma oranı; 1.488 rotanın %46,3'ünde sapma, ek yakıt medyanı %2,2 (p90 %8,8). | Ocak 2019 ERA5 |
| [`2026-10-27_yeni_gun/`](2026-10-27_yeni_gun/README.md) | §10 tek seferlik değerlendirme: 79 yeni test günü; geniş − temel +0,008 [+0,002; +0,014] (komşu günsüz anlamlı değil), iki set de TI1 kapısını geçti. Yedek `kalici/turbulans_20261027_yeni_gun.dump`. | 27 Ekim 2026 (gece işi sonrası) |

## Paketin içeriği

- `sonuc_paketi.json`: commit hash, kesme, veri sayıları, protokol modeli, altın test
  günlerinde Model/TI1/1/Ri/birleşik EDR için ROC-AUC ve PR-AUC (gün bazlı blok
  bootstrap %95 GA), TI1'e karşı eşleştirilmiş ROC-AUC farkı ve p değeri, TI1 eşik
  taraması (genel ve seviyeye göre), yalnız CAT alt kümesi, MADIS ölçülen EDR, rota
  backtest'i.
- `SAYILAR.md`: aynı sayılar, JSON anahtarlarıyla birlikte.
- `roc_ti1_ri.png`: altın günlerde TI1 ve Ri ROC eğrisi. Eğitim günlerinde seçilen Peirce
  eşikleri ve config eşiği işaretli.
- `guvenilirlik_modeli.png`: modelin güvenilirlik diyagramı (PIREP altın günler, MADIS).
- `backtest_ucus_basina.png`: veritabanındaki her backtest uçuşu için riskli nokta oranı.
  Bu ölçüm TI1 ile yapılır ve döngüseldir.
- `rota_performansi.md` / `.json`: `turbulans-performans rota` ile rota kararı süresi.
- `ml_dondurma.json` (yalnız nihai pakette): `turbulans-ml --dondurma-raporu` ile gece
  kapısının bir kez çalıştırılması; aday, aktif model ve TI1 karşılaştırması, konformal
  kapsama, kayma özeti ve kaydedilen sürüm.

## Yeniden üretme

```
turbulans-ml-degerlendirme --kesme 2026-10-18 --cikti docs/sonuclar/2026-10-18
turbulans-performans rota --json docs/sonuclar/2026-10-18/rota_performansi.json
turbulans-ml --dondurma-raporu docs/sonuclar/2026-10-18
```

Komut, protokol modelini aynı kurallarla yeniden eğitir: altın test günleri dışında gün
gruplu CV, 1-SE seçimi ve sigmoid kalibrasyon. Aktif model kullanılmaz. Aynı veritabanı
yedeği ve aynı commit ile sayılar aynı çıkar (bootstrap tohumu 0).

### Üçüncü kişi için (nihai paket)

Dondurma yedeği depoda değildir ve herkese açık yayımlanmaz: içindeki OpenSky uçuş verisi
yalnız araştırma amaçlı, yeniden dağıtımı kısıtlı lisanslıdır. Komite ya da hakem isterse iki
dosya özel bir bağlantıyla verilir; bütünlük aşağıdaki sha256 ile denetlenir.

| Dosya | Boyut | sha256 |
|---|---|---|
| `turbulans_20261018_dondurma.dump` (`pg_dump -Fc`, 18 Ekim 00:02 UTC) | 10,4 MB | `c73d5271c4128f5b73f803d84b5c7be61306933a6b5224db767168ad5ac7f734` |
| `dosyalar_20261018_dondurma.tar.gz` (`model_deposu`, `madis_edr`, `ml_ozellik_deposu`, `opensky_onbellek`) | 242,4 MB | `cd261464339dfaf830d2f36af21e4ba79afbe29a68af0814ae84c5516d4dcdcc` |

1. `sha256sum` ile iki dosyayı tabloyla karşılaştırın; tutmazsa devam etmeyin.
2. Depoyu `5ddcd40` commit'inde açın, `.env.example`'dan `.env` oluşturun, `docker compose up -d db`.
3. Arşivi depo köküne açın (`tar -xzf dosyalar_20261018_dondurma.tar.gz`).
4. Dump'ı boş veritabanına yükleyin (README "Veritabanı yedeği"):
   `docker compose exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner' < turbulans_20261018_dondurma.dump`.
5. Gece işi veriyi değiştirmesin diye `.env`'de `ML_GECE_ISI_SAATI=` (boş) bırakın,
   `docker compose up -d api worker`, sonra yukarıdaki üç komutu `api` konteynerinde çalıştırın.
6. Üretilen `SAYILAR.md` depodakiyle aynı olmalı (`rota_performansi` süreleri makineye bağlıdır). 18 Ekim'de paket bu yedekten ve canlı
   veritabanından ayrı ayrı üretildi, çıktılar birebir aynıydı. Başka bir makinede uçtan uca
   denenmedi.

## Okurken dikkat

- **Etiket yanlılığı.** PIREP'lerin yaklaşık yarısı pozitiftir; pilotlar sakin havayı
  nadiren raporlar. Model olasılığı mutlak türbülans sıklığı değildir. MADIS
  güvenilirlik eğrisi bu yüzden köşegenin çok altındadır (bkz. `docs/rapor/SONUCLAR.md` §4).
- **CAT alt kümesi.** PIREP metninde CB, TS (+TSRA, VCTS, TSTM gibi türevler), TCU,
  MTN WAVE ya da LLWS geçen raporlar dışlanır. Ham metin yalnız yerel IEM arşivinde
  (2018–Mart 2020) var. Metni olmayan günler iki alt kümede de yoktur.
- **MADIS.** Elimizde yalnız hafif sınıf var, orta ve üstü ölçüm yok. Örnekler PIREP
  pencerelerinden geldiği için seçim yanlılığı vardır. QC "Z" ön veridir. MADIS günleri
  modelin eğitim günleriyle çakışabilir.
- **Backtest.** Riskli oran TI1 ile ölçülür; A* de TI1'i düşürür. Bağımsız kanıt
  (SIGMET/PIREP) yalnız kapsadığı uçuşlarda vardır.
- **PUE502** (26 Eylül 2026, canlı GFS) bu pakette yoktur. Uçuş ve backtest kaydı
  3 Ekim öncesi veritabanında kaldı ve yedeklerde de bulunmuyor. Sayıları tarihçedir
  (bkz. `docs/SISTEM_KARTI.md` §6).

Çıktılar sertifikalı EDR değildir; sistem operasyonel karar aracı değil, karar destek
aracıdır.
