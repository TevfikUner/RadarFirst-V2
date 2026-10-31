# Yapılacaklar (ileri tarihli işler)

İleri bir tarihe ertelenen tüm işler burada tek listede tutulur. Biten madde silinmez,
`[x]` ile işaretlenir ve yanına PR/tarih yazılır. Yeni ertelenen iş buraya eklenir.

## Sıradaki işler (31 Ekim 2026, tarama sonrası; `docs/denetim/2026-10-31/TARAMA.md`)

Önerilen sıra. Ayrıntı ve kanıt tarama raporunda; numaralar aşağıdaki öncelik listesine bağlanır.

**A. Bu hafta (5 Kasım sunumundan önce)**
1. **1–4 Kasım: demo ekranları ve sunum paketi yenileme (önerilen ilk iş).** Ekranlar 19 Ekim, paket
   (`sunum_paketi_20261027`) `e73fdd8`; S-3 seçici, S-4 arıza tatbikatı, OOD kapısı, model paneli (ROC-AUC),
   `katman_cevrelenmiyor` ve Ri notu ikisinde de yok. WSL temiz klonundan (5532/8100) `turbulans-demo-ekranlari`,
   ardından `bash scripts/sunum_paketi.sh`; OneDrive'a kopya + SHA256. Bitene kadar `docker builder prune`
   **yapılmaz** (CesiumJS önbellekte). `DEMO_SENARYOSU` sayıları kontrol edilir.
2. **3 Kasım: #11 devamı + ATM-05 (madde 4, ONAY 28 Ekim).** `turbulans-tahmin-ufku --indir --baslangic
   2026-10-28T12 --bitis 2026-11-03T00` (~15 MB; 28 Ekim 12Z koşusu 4–5 Kasım'da UCAR'dan silinir). ERA5 kıyas aracı
   31 Ekim'de yazıldı (`--era5`; 23 Ekim ile CDS'ten denendi, 1 MB önbellekte). İndirmeden sonra:
   `CDSAPI_RC=<CDSAPI_RC_DOSYASI> turbulans-tahmin-ufku --era5 --baslangic 2026-10-23T00 --bitis 2026-11-03T00
   --cikti docs/sonuclar/2026-11-03_tahmin_ufku` (ERA5 ~5 gün gecikmeli: ~29 Ekim'e kadarki zamanlar, ~7 CDS isteği,
   ~7 MB). ATM-05 eşlemesi aynı raporda; eşik farkı çıkarsa `.env` değişikliği ONAY.
3. **5 Kasım: E8 yedek video ve soğuk açılış provası** (madde 22). 1. madde bitmeden çekilmez.
4. **5 Kasım Perşembe 23:55: Hafta 6 ilerleme raporu.** Hafta aralığı kullanıcıya sorulur (öneri 30 Ekim–5 Kasım);
   Hafta 5 e-postasının gönderildiği doğrulanır (madde 2).

**B. Kullanıcı kararı bekleyenler**
5. Masaüstü `yedekler/` klasöründeki eski şifreli bundle/mirror'ların silinmesi (GitHub tarafı 31 Ekim'de kapandı;
   geri alınamaz).
6. Herkese açık depoda `CLAUDE.md` ve `.claude/settings.json` (kurul JRİ-01): kalsın mı, kaldırılsın mı (geçmişte
   kalır; geçmiş yeniden yazılmaz).
7. Gece işinin yeniden açılması (madde 18; kotasız internette düşük bütçe önerisi: CDS 10, MADIS kapalı, ~130 MB).
8. Eski dallar: uzakta 49, yerelde 57 `claude/*` (çoğu birleşmiş); uzak dalları silmek paylaşılan durumu değiştirir.

**C. Komite hazırlığı (kullanıcı açınca; madde 19–24)**
9. Bütünleşik bitirme raporu (en büyük eksik teslimat; `docs/rapor/` yalnız bölüm taslakları).
10. Savunma hazırlığı ve danışmana YZ beyanı e-postası (beyan 31 Ekim'de güncellendi).
11. Komite sunumuna §10'un 79 günlük sonucu ve tek cümlelik katkı/konumlandırma slaytı (30 Ekim sunumunda yok).
12. Demoya ABD vakası + ML modeli; iki seçim kuralının yan yana gösterimi; E7 kullanılabilirlik oturumları.

**D. Sunum sonrası**
13. MİM-02 (madde 10); A2/VER-09 (madde 12; birleşik EDR ızgarada da TI1'den iyi, ilk aday); Fikir 10'un
    `eslestirme.py` modu ve eşiğin yeniden seçimi (ONAY).
14. Türkiye TURB SIGMET ↔ TI1 (madde 29; 5 TURB SIGMET için GFS arşivi yok, küçük ERA5 kutusu, ONAY); Faz 2 (madde 30);
    `rojak` kıyası (madde 31).
15. `Turbulence-db-dondurma` DROP ve `docker builder prune` (~65 GB; madde 25, sunum paketi yenilendikten sonra, ONAY);
    #25 yerel Swagger (kotasız internet).

## Öncelik sırası (28 Ekim 2026 gece, kurul raporu sonrası)

Açık maddelerin önem sırası; ayrıntı aşağıdaki bölümlerde ve depo dışındaki kurul raporunda (28 Ekim, §0).
Kurul A ve B grubu bitti (PR #140–#145). Gece işi 28 Ekim'den beri kullanıcı kararıyla kapalı.

**1. Tarihli (takvime bağlı)**
1. ~~29 Ekim, ilk iş (kullanıcı): GitHub Destek talebi P0-9 / kurul #21~~ (29 Ekim: talep açıldı, PR #1 commit
   referanslarının kaldırılması istendi). 31 Ekim doğrulandı: şifreli commit API'de 422 "No commit found",
   PR #1 404. Kalan tek iz masaüstü `yedekler/` bundle'ları (silme kullanıcı kararı, geri alınamaz).
2. **29 Ekim 23:55 (kullanıcı):** haftalık ilerleme raporu Hafta 5'in e-postayla gönderimi (PDF'ler
   masaüstünde, #136); 28 Ekim gelişmeleri (kurul A/B grubu) eklenebilir. 31 Ekim: gönderildiği doğrulanmadı.
   Sonraki: Hafta 6, 5 Kasım Perşembe 23:55 (hafta aralığı kullanıcıya sorulur).
3. ~~29–30 Ekim (kurul #19): AIRAC kontrolü~~ (29 Ekim: günlük "yenilendi", AIRAC 11/26 yürürlük 29 Eki, bitiş
   26 Kas, 682 nokta/85 saha; `/saglik?derin=true` `ats_agi` "tamam". "AMDT 06/26" değişmeyen ENR 4.1'in numarası.)
4. **3 Kasım (kurul #11 devamı + ATM-05; ONAY 28 Ekim):** 28 Ekim–3 Kasım GFS koşuları
   (`turbulans-tahmin-ufku --indir`, ~15 MB) ve ERA5 kıyası (ERA5'in yayınlandığı geçerlilik zamanları, küçük
   CDS kutusu; araç 31 Ekim'de `tahmin_ufku.py --era5` olarak eklendi). Aynı f000 ve ERA5 verisiyle ERA5 → GFS TI1 eşik eşlemesi
   3 gün yerine ~10 günle yeniden ölçülür (ATM-05); eşik değişirse ONAY.

**2. Proje iyileştirme (önem sırasıyla)**
5. ~~Kurul #3, bağımsız rota backtest'i~~ (29 Ekim, protokol §11, `docs/sonuclar/2026-10-29_bagimsiz_backtest/`):
   bağımsız günlerde sapmalı 908 rotada göreli maruziyet oranı 0,71 [0,58; 0,90]; 48 günün tamamında
   0,83 [0,66; 1,03]. SISTEM_KARTI:17 ve §6 güncellendi. A1 (ADR 0013) için girdi: `sozluksel` kural
   bağımsız kanıtla tutarlı; yeniden değerlendirme gerekmedi.
6. ~~Kurul #4 kalanı~~ (29 Ekim, protokol §12): birleşik EDR eşiği 0,0757 (TI1 ile aynı 1-SE kuralı); uyarı
   oranı birleşik EDR'de %36,1, TI1'de %46,3 (`2026-10-29_uyari_orani_birlesik/`). Eşik A2 için de girdi.
7. ~~S-4 kalanı~~ (29 Ekim): `ARIZA_TAKLIDI_ETKIN` (yalnız `.env.demo`) + rota isteğinde `ariza_taklidi`; seçicide
   üç SENTETİK tatbikat senaryosu, Playwright testli. Gerçek devre kesici mesajı da artık rota uyarısına yazılıyor.
8. ~~Kurul #28 (P3, VER-02): yuvarlanan kapı~~ (29 Ekim, ADR 0014): kapı aktif modelin görmediği, eşleşme
   sırasına göre son 16 yeni günde; altın günler yalnız rapor; yeni gün yetersizse aktif model korunur.
9. ~~Kurul #29 (P3, VER-08 devamı): OOD kapısı~~ (29 Ekim, `ml/destek_kapisi.py`, `turbulans-ml-destek`): destek
   dışı girdide `/turbulans/tahmin` ML/konformal çıktı vermez. Türkiye %2,9, ABD altın kontrol %4,2 kapanıyor;
   marjinal kapı Türkiye'yi ayırmıyor (`docs/sonuclar/2026-10-29_ood_kapisi/`).
10. **MİM-02:** `rota_simulasyonu_olustur` bölme (altın çıktı ile bayt bayt aynı; sunum sonrası).
11. **Kurul #25 / MİM-08:** yerel Swagger (kotasız internette; statik katman değişince Docker CesiumJS'i yeniden indirir).
12. **A2 / VER-09 (sunum sonrası):** birleşik EDR ya da ML'in rota cezasına girmesi (eşik seçimi ve GFS doğrulaması önce).
13. **ATM-06:** GTG referans AUC'si yalnız Sharman vd. (2006) tam metni bulunursa.
14. ~~mypy tüm pakete, `Mapped[datetime]`~~ (29 Ekim: 140 dosya temiz, 13 hata düzeltildi; 35 zaman sütunu
    `Mapped[datetime]`/`date`). `cli/demo_ekranlari` testi %27 → %66. Kalan: diğer araştırma CLI'larına test.

**3. Araştırma (yeni günlerde, önce protokole yazılarak)**

31 Ekim kararı (kullanıcı "önerdiğini uygula, önermediğini ertele" dedi): yerel veriyle yapılabilen 15. madde yapıldı.
Ertelenenler ve nedenleri: #25 Swagger (kotasız internet), ATM-06 (Sharman 2006 tam metni yok), gece işi (kullanıcı
emri), MİM-02 ve A2 (kurul: sunum öncesi regresyon riski), Fikir 29 (kazanç küçük), Fikir 18/20 (yeni gün verisi
gerekir, gece işi kapalı), Fikir 23 (OpenSky girişi kullanıcıda), F7/OpenSky/F5 (ONAY ve veri bütçesi).
15. ~~Fikir 11 devamı, Fikir 9, 10, 15, 19, 24~~ (31 Ekim, protokol §13, keşifsel; `2026-10-31_kesifsel_gostergeler/`,
    `2026-10-31_uyari_alani/`). Kalan: Fikir 29 (beklenen kazanç küçük), NCSU1 (birincil kaynak yok, ATM-06 ile aynı),
    Fikir 10'un `fizik/eslestirme.py`'ye mod olarak girmesi ve eşiğin yeniden seçilmesi (sunum sonrası, ONAY).
16. GFS topluluk oranı, Fikir 18 devamı, Fikir 20, Fikir 23, F7 rüzgâr asimilasyonu (veri bütçesi, ONAY).
17. Daha fazla OpenSky uçuşu (önce kota hesabı, ONAY); F5 yakıt sütunu (migration, ONAY).
18. Gece işinin yeniden açılması (kullanıcı emri; `ML_GECE_ISI_SAATI`).
29. **(30 Ekim, vize sonrası)** Türkiye TURB SIGMET'leri ↔ TI1 kıyası: 30 Eylül'den biriken LTAA/LTBB SIGMET'lerinin
    zaman ve alanında canlı GFS ile TI1; bölgesel uyuşmazlık itirazına ilk Türkiye kanıtı (küçük örneklem).
30. **(30 Ekim)** Faz 2, tırmanma/alçalma için ayrı model: 400–850 hPa, CAPE, arazi; FL100–FL280 PIREP'leri konvektif /
    dağ dalgası / rüzgâr kesmesi diye ayrı etiket. Seyir modeline karıştırılmaz. Dayanak: Lee ve Chun (2025).
31. **(30 Ekim)** İndekslerin `rojak` (Imperial College) ile aynı ERA5 üzerinde kıyası; Zhu vd. 2026, Gökdeniz ve
    Ülkü 2026, He vd. 2026 ve iki derlemenin `docs/rapor/ILGILI_CALISMALAR.md`'ye eklenmesi
    (`docs/arastirma/LITERATUR_TARAMASI_2026-10-30.pdf`).

**4. Komite öncesi hazırlık (kullanıcı açana kadar ertelendi; kurul raporu §8)**
19. Savunma hazırlığı (#5) ve danışmana YZ beyanı e-postası (K-1).
20. Bütünleşik bitirme raporu (#6).
21. Sunum: §10 birincil kanıt ve etiket gerekçesi (#14), katkı cümlesi ve konumlandırma slaytı (#15).
22. Demo: ABD vakası + ML modeli (#17, OPS-05), iki seçim kuralının yan yana gösterimi (A1); E8 yedek video ve
    soğuk açılış provası (#8, 5 Kasım).
23. E7 kullanılabilirlik oturumları / pilotlarla deneme (#13, OPS-03).
24. Rapor tesliminden hemen önce `scripts/beyan_sayimlari.py --kontrol` (K-2; 31 Ekim'de güncellendi:
    424 commit / 1.242 test / 47.829 satırın 665'i; sonraki her commit sayıyı yeniden eskitir).

**5. Teslim sonrası / koşullu**
25. `Turbulence-db-dondurma` DROP ve `docker builder prune` (~50 GB); ikisi de geri alınamaz, ONAY.
26. Kurul #30: GTG/WAFS kıyası; MGM ve IATA Turbulence Aware başvurusu (kullanıcı, dış iletişim). 30 Ekim: TUSAŞ,
    Boeing, Airbus, DLR, NASA, MGM ve IATA için e-posta taslakları hazır (masaüstü, depo dışı); danışman onayı bekliyor.
27. P0-7 hibrit topoloji ADR'si (yalnız B planına geçilirse).
28. Eski commit imzalarının temizliği (force-push; önerilen: yapılmaması).

## 18 Ekim 2026 — ML veri dondurma

- [x] (18 Ekim, commit `5ddcd40`, sıralı sorgu; RF +0,033, kapı geçildi; dondurmada aday aktif RF'yi geçemedi)
  `turbulans-ml-degerlendirme --kesme 2026-10-18 --cikti docs/sonuclar/2026-10-18`,
  `turbulans-ml --dondurma-raporu docs/sonuclar/2026-10-18`.
- [x] (19 Ekim: 0,10–0,42 sn; kütle bandı yavaşlatmıştı, sonuç aynı kalacak şekilde hızlandırıldı) Şarjdayken: `turbulans-performans rota --json docs/sonuclar/2026-10-18/rota_performansi.json`
  (17 Ekim gecesi dizüstü pildeydi); sonra SISTEM_KARTI'daki `2026-10-07/rota_performansi.md`
  bağlantısı ve süreleri güncellenir.
- [x] (18 Ekim) Ön paket (2026-10-07) sayılarını nihai `SAYILAR.md` ile değiştir: SISTEM_KARTI,
  SONUCLAR §0, KATKILAR, SUNUM_AKISI §8, poster, DEMO_SENARYOSU, ILGILI_CALISMALAR,
  `TI1_GUVENILIRLIK_NOTU`, README "Kısa cevap", PROJE_ISLEYISI; `docs/sonuclar/README.md`
  tablosu; ARAC_KULLANIMI_BEYANI commit/satır sayımları güncel git'e göre.
- [x] (18 Ekim: 7,39e-7; 7e-7 1-SE bandının içinde, config değişmedi, SONUCLAR §0.2) `esik_taramasi.bir_se.esik` 7e-7'den belirgin farklıysa `TI1_ESIK_ORTA_SIDDETLI`'yi
  güncelle; eşiğe bağlı testler, demo senaryosu ve ekranlar yeniden kontrol edilir.
- [x] (18 Ekim: ERA5 eşiği değişmedi, 16 Ekim ölçümü geçerli; `.env`'ye 8,3e-7 yazıldı, API/işçi
  yeniden başlatıldı; demo ekranları ERA5 kullandığı için değişmedi) GFS eşiği: nihai ERA5 eşiğiyle `turbulans-esik-esleme --baslangic 2026-10-09T00:00Z
  --bitis 2026-10-11T18:00Z --esik <yeni> --cikti docs/sonuclar/2026-10-18` (veri önbellekte,
  indirme yok). 16 Ekim ölçümü: 7e-7 ↔ GFS 8,30e-7 [7,96; 8,67]e-7. Sonucu
  `TI1_ESIK_ORTA_SIDDETLI_GFS`'e (`.env`) yaz, API/worker'ı yeniden başlat; demo ekranları GFS
  kullanıyorsa yeniden kontrol et. Örneklemi büyütmek için `--bitis 2026-10-13T18:00Z`
  (12–13 Ekim için ~2 MB GFS + ~5 MB ERA5 ek indirme; THREDDS koşuları ~8 gün durur).
- [x] (18 Ekim, SONUCLAR §0.4: 0,041) MADIS önsel kayma gösterimi (`model_olasilik_onsel_duzeltilmis`) pakette çıkınca
  SONUCLAR §0.4'e tek satır not.
- [x] (18 Ekim) SUNUM_AKISI §10 (F1 doğrulama karnesi) ve poster "Sonraki" satırını nihai pakete bağla.
- [x] (16 Ekim, ekranlar yenilendi; demo sayıları değişmedi: %9,55 ek yakıt, 26 dk kaçınma) Demo ekranlarını temiz klondan yenile: brifing kartına FPL Madde 15, dikey kesit, kalkış
  penceresi ve kütle bandı eklendi (16 Ekim, PR #62–#71); `DEMO_SENARYOSU` metnini kontrol et.

## 18 Ekim gecesinden kalanlar (P0 oturumu, PR #85–#96)

Yarım kalan ya da dış koşul bekleyen işler. Ayrıntı: `docs/ISLEM_GUNLUGU.md` 18 Ekim satırları,
`docs/denetim/2026-10-17/URETIM_HAZIRLIK.md` "Faz 1 durumu" tablosu.

- [x] (19 Ekim: imaj derlendi; api ve worker yeni imajda, iki harita sayfası 200, CSP başlığı var) **Docker imajını yeniden derle (öncelikli):** 18 Ekim 01:00 UTC'de npm'e
  (`registry.npmjs.org`) erişilemedi; `docker compose build api worker` Cesium indirmesinde
  takıldı ve durduruldu. Çalışan imaj #90 öncesi koddan: CSP ve güvenlik başlıkları (#91),
  `ORDER BY id` (#89), `*_FILE` (#93), işçinin anahtarsız kapalı başlaması (#94) imajda yok.
  npm dönünce derle, `docker compose up -d api worker`, ardından `/harita` yanıtında
  `content-security-policy` başlığını ve iki sayfanın açıldığını kontrol et.
- [x] (19 Ekim, yukarıdaki madde) **Rota performansı (şarjdayken):** yukarıdaki 18 Ekim maddesi; SISTEM_KARTI §1'deki
  `docs/sonuclar/2026-10-07/rota_performansi.md` bağlantısı ve süreler nihai pakete taşınır.
- [x] (19 Ekim, temiz klon `071ecdb`, sayılar aynı; ekran aracı CSP'ye takılıyordu, düzeltildi) **Demo ekranlarını yenile:** `TI1_GUVENILIRLIK_NOTU` metni (15.940 PIREP / 163 gün) ve
  `harita3d.html`'deki "karar destek aracıdır" satırı değişti; `docs/sunum/ekranlar/`
  görüntüleri eski metni gösteriyor. İmaj derlendikten sonra temiz klondan (5532/8100 portları).
- [x] (29 Ekim: talep açıldı; GitHub yanıtı bekleniyor) **GitHub Destek talebi (P0-9, kullanıcı):** PR #1'deki eski OpenSky şifresi; metin
  `docs/guvenlik/GUVENLIK_TARAMASI_2026-10-05.md`. Depo herkese açılmadan önce şart.
  19 Ekim: kullanıcı başka bir zaman kendisi gönderecek (GitHub web formu; Claude gönderemez).
- [ ] **Y-6 `docker builder prune` (~50 GB):** imaj npm erişimiyle başarıyla derlendikten sonra
  (önbellek silinirse Cesium yeniden indirilir). Geri alınamaz, ONAY.
- [ ] **`Turbulence-db-dondurma` veritabanı:** dondurma yedeğinin geri yüklenmiş kopyası,
  yeniden üretim kanıtı için bırakıldı (`POSTGRES_DB=Turbulence-db-dondurma turbulans-ml-degerlendirme
  --kesme 2026-10-18`). Sunumdan sonra gerekmiyorsa silinebilir (DROP, ONAY).
- [x] (19 Ekim, PR #105: 308 commit; teslim günü `scripts/beyan_sayimlari.py --kontrol`) **ARAC_KULLANIMI_BEYANI sayımları:** 18 Ekim'de 284 commit sayıldı, sonra 12 PR daha
  girdi; rapor teslim edilmeden önce yeniden sayılır.
- [x] (19 Ekim, `docker-compose.uretim.yml`) **Y-2:** `uretim` profilinde DB host portları (5432/5433) yayınlanmasın; compose profilleri
  port kaldıramadığı için `docker-compose.uretim.yml` override'ı gerekir (P2).
- [ ] **P0-7 hibrit topoloji ADR'si:** yalnız B planına (sanal sunucu) geçilirse; koddan önce ONAY.
- [x] (19 Ekim, PR #100–#106: P1-1 (worker hariç), P1-2, P1-4, P1-5, P1-7, P1-8, P1-9 bitti; kalanlar aşağıda ayrı maddeler) **P1 listesi (URETIM_HAZIRLIK §P1):** P1-1 kaynak sınırı/log rotasyonu, P1-2 migration
  öncesi yedek, P1-3 izleme yığını, P1-4 imaj/Action sabitleme, P1-5 `.dockerignore` (MCP sunucusu
  ve belgeler imajdan çıkar), P1-6 derin sağlık anahtarsız, P1-7 WS bileti çok süreçli, P1-8 Esri
  karo kapatma bayrağı, P1-9 AIRAC (29 Ekim maddesi), P1-10 işletim kılavuzu + DB şifre rotasyonu.

## Ertelenenler (19 Ekim anlık kontrolünden; `docs/denetim/2026-10-19/ANLIK_KONTROL.md`)

- [x] (20 Ekim: derlendi, `GIT_SHA` = master, Prometheus profili açık, tüm sağlık kontrolleri tamam) **Sonraki oturumun başında: yığını güncel imajlarla derle (19 Ekim'de uzun sürdüğü için yarıda bırakıldı).**
  #114 (postgres 16 yeni özet) ve #115 (python 3.12-slim yeni özet) master'da, çalışan yığın bir önceki
  imajlarda (sağlıklı). Görev kuyruğu boşken WSL'de: `export GIT_SHA=$(git rev-parse HEAD) && docker compose
  pull db && docker compose build api worker migrate && docker compose up -d --wait` (~20 dk; taban imaj
  değiştiği için bağımlılıklar yeniden kurulur). Sonra `/saglik?derin=true` "tamam" ve `migrate_yedegi` yedeği.
- [x] (20 Ekim, birleşti) **PR #116 (CI postgres servis imajı compose ile aynı özette):** CI'ı geçince birleştir; yalnız
  `.github/workflows/ci.yml` iki satır.

- [x] (20 Ekim: önerilen (a) uygulandı, önbellek isabeti sınırdan muaf) **Rota hız sınırı kararı (S-9, kullanıcı 19 Ekim'de erteledi):** aynı NAT arkasındaki 10 cihazda
  rota isteklerinin %40'ı 429 aldı; önbellekten dönen rota da sınıra takılıyor (`PERFORMANS_RAPORU.md`
  §5.5). Seçenekler: (a) önbellek isabetini sınırdan muaf tutmak, (b) sınırı cihaz/anahtar başına
  yapmak, (c) `ROTA_HESABI_DAKIKADA_MAKS`'ı yükseltmek. Karar kullanıcıda; sonra uygulanır ve S-9 yeniden ölçülür.
- [x] (20 Ekim: `web/veri/senaryolar.json`, 7 senaryo, yalnız demo/test vakaları; Playwright) **S-3 senaryo seçici (M):** `web/ucus_simulasyonu.html` 2019 değerleriyle sabit açılıyor;
  `web/veri/senaryolar.json` + açılır liste, senaryo başına Playwright testi.
- [x] (29 Ekim) **S-4 başarısızlık durumları simülasyonda (M):** "ÖNERİ YOK", SIGMET bayat, `erisilemedi`, devre
  kesici gösterilebilsin; demo profilinde fikstür (gerçek arşiv yoksa SENTETİK etiketli).
  20 Ekim: "ÖNERİ YOK" (Beyrut → Bağdat, örnek Suriye sahası) ve kapsam dışı senaryoları seçicide, Playwright
  testli. 29 Ekim: SIGMET bayat/`erisilemedi` ve devre kesici SENTETİK arıza tatbikatı olarak seçicide (S-4 bitti).
- [x] (20 Ekim: `docs/ISLETIM_KILAVUZU.md`; tatbikat ve sağlık denendi, şifre rotasyonu ve canlı geri yükleme denenmedi diye işaretli) **P1-10 işletim kılavuzu (M):** `docs/ISLETIM_KILAVUZU.md` (başlatma/durdurma, yedek ve geri
  yükleme, migration, AIRAC, gece işi, anahtar ve DB şifre rotasyonu); her prosedür bir kez denenir.
- [x] (20 Ekim: `--profile izleme` Prometheus + 5 alarm, bildirim kanalı yok (önerilen); ayrı izleme anahtarı) **P1-3 izleme yığını (ONAY: bildirim kanalı):** `izleme/prometheus.yml`, `alarmlar.yml`,
  `--profile izleme`; bildirim kanalı (e-posta/Telegram vb.) kullanıcı seçer.
- [x] (20 Ekim: ağa açıkken anahtarsız derin yanıt yalnız `durum`; yerelde ayrıntılı kalır) **P1-6 kalan kısmı:** üretimde anahtarsız `/saglik?derin=true` yalnız `{"durum"}` dönsün
  (bugün bileşen adı + durum dönüyor, ayrıntı yok).
- [x] (20 Ekim: gece işi tepe 687 MiB, sınır 2g) **Worker bellek sınırı (P1-1 kalan):** bir gece işi sırasında `docker stats` ile tepe bellek
  ölçülür, sonra `docker-compose.yml`'de worker'a payla `mem_limit` yazılır (ölçümsüz sınır işi OOM ile öldürebilir).
- [x] (19 Ekim, PR #104–#105: yalnız B-3 kaldı, 20 Ekim maddesinde) **Komite incelemesinin açık bulguları:** `docs/denetim/2026-10-17/KOMITE_INCELEMESI.md`;
  kapananlar dosya sonundaki "18 Ekim durumu" bölümünde, kalanlar (ör. B-8 çoklu karşılaştırma için
  dondurma sonrası yeni günlerde değerlendirme, T-1 üçüncü kişi yeniden üretimi) savunma öncesi gözden geçirilir.
- [x] (19 Ekim: gece işi bitti, aday aktifi geçemedi +0,001; imaj sonra derlendi) **Bu gece (03:00 UTC) eğitimi eski imajla çalışır:** sıralı sorgu yok, yani aday seçimi RF/GB
  arasında satır sırasına bağlı kalabilir; karar kapısı etkilenmez. İmaj derlenince kendiliğinden düzelir.

## 18 Ekim sonrası (paket çıktıktan sonra)

- [x] (18 Ekim: §5/§6'daki 32 kod adı kodda var; README paket ağacı yeniden yazıldı ve iki yönlü
  kodla eşleşiyor; test sayısı CI #93'ten 1.066, kapsam %84,5) Madde 10 adım 6: SISTEM_KARTI §5/§6
  ve README mimari/paket ağacının kodla çelişki denetimi; test sayısı CI'dan alınır.
- [x] (19 Ekim: `deney_protokolu.md` §10, test günleri = `ml/dondurma_gunleri.json` dışındaki ≥30 gün; değerlendirme kodu ve çalıştırma kaldı) Yeni ML protokolü (F9 devamı): `docs/deney_protokolu.md`'ye geniş özellik setini
  (temel 8 + 5 bağlam) ve aday modelleri önceden yaz. Değerlendirme dondurmadan SONRA
  toplanan yeni günlerde yapılır; aynı 16 altın gün kullanılmaz (bkz. SONUCLAR §2.4).
- [x] (19 Ekim: `turbulans-ml-yeni-gun`; 19 Ekim'de 16 yeni gün / 1.509 örnek, skor yok) **§10 değerlendirme kodu:** test günü filtresi (`dondurma_gunleri.json` dışı), iki özellik seti,
  Fikir 4/8 tabloları ve ±1 gün duyarlılığı; test günlerine bakmadan commit'lenir, sonra ≥30 yeni
  gün olunca bir kez çalıştırılır (19 Ekim'de 16 yeni gün vardı).
- [x] (27 Ekim, `docs/sonuclar/2026-10-27_yeni_gun/`: 79 gün; H1 +0,008 [+0,002; +0,014], komşu günsüz anlamlı değil; iki set TI1 kapısını geçti) **§10 değerlendirmesini bir kez çalıştır:** her gece işi sonrası `turbulans-ml-yeni-gun --durum`;
  `yeterli: true` olunca `turbulans-ml-yeni-gun --cikti docs/sonuclar/<tarih>`, sonuç ne çıkarsa raporlanır.
- [x] (20 Ekim: 57,6 MB indirildi; Spearman 0,81, eşdeğer eşik 6,5e-7; `docs/sonuclar/2026-10-20_turkiye_7seviye/`) **20 Ekim, gece işinden önceki ilk oturum (ONAY alındı, komite B-3):** Türkiye ERA5 7 seviye
  (31 CDS isteği, 15.624 alan, ≤130 MB; 19 Ekim bütçesi dolu olduğu için ertelendi; aynı UTC günü
  gece işi bütçesinden düşer). `docker compose exec -T worker python - indir --gercekten-indir <
  scripts/turkiye_kupu_7seviye.py`, sonra WSL'de `python scripts/turkiye_kupu_7seviye.py karsilastir`
  (dosyayı `ciktilar/`dan köke taşır, rapor `docs/sonuclar/2026-10-20_turkiye_7seviye/`). Yeni küp ayrı
  dosya; varsayılan `HAVA_DURUMU_DOSYASI` değişmez. Sonuç SISTEM_KARTI ve KOMITE_INCELEMESI B-3'e yazılır.
- [ ] Daha fazla OpenSky uçuşu: önce OpenSky kotası hesabı, sonra ONAY.
- [ ] F7 rüzgâr asimilasyonu küçük deneyi (5–10 gün, 2021 sonrası MADIS günleri + AWS GFS;
  bkz. `docs/fizibilite/RUZGAR_ASIMILASYONU.md`): gece veri bütçesine eklenmeden ONAY.
- [ ] İsteğe bağlı: F5 backtest yakıtı için kalıcı veritabanı sütunu (migration; önce
  `-test` DB'de upgrade/downgrade, geliştirme DB'si için ONAY). Şu an yalnız yanıtta.

- [x] (17 Ekim, 15 vaka, 9,5 MB; `docs/sonuclar/2026-10-17/`) **Fikir 18 deneyi:** son 8 gün içinde
  3–5 rota, R0 (kalkış −6 sa) planı ile yolda R1 yeniden planı; ~10 MB tek seferlik indirme (ONAY).
  Plan: `docs/fizibilite/KAYNAK_INCELEMESI_FIZIBILITE.md`.
- [ ] Fikir 18 devamı (isteğe bağlı): dondurma sonrası MADIS/PIREP günlerinde aynı deney gözlemle
  doğrulanırsa referans yanlılığı kalkar; yeni protokole aday.
- [ ] **Fikir 20:** 2021 sonrası yeni günler toplanırsa IEM G-AIRMET arşiviyle karşılaştırma.
- [ ] **Fikir 23:** tek uçuşluk `rollcall_replies_data4` deneme sorgusu (OpenSky girişi kullanıcıda).
- [ ] **GFS topluluk oranının doğrulanması (Fikir 3 devamı):** THREDDS koşuları ~8 gün
  durduğu için geçmiş günlerde değerlendirme ancak veri biriktirilerek yapılabilir. Gece
  işine günlük GFS koşu dilimi eklemek veri bütçesine girer (ONAY). Ölçüt: MADIS EDR / PIREP
  günlerinde güvenilirlik diyagramı ve Brier skoru; rota kararına alınması ayrı karar.

### Kaynak incelemesinden (16 Ekim, `docs/arastirma/KAYNAK_INCELEMESI.md` §3)

Kural: her biri ÖNCE `docs/deney_protokolu.md`'ye (hipotez, metrik, karar ölçütü) yazılır,
SONRA dondurmadan sonra toplanan yeni günlerde çalıştırılır; aynı 16 altın gün yeniden
kullanılmaz. Böylece sonuç görüldükten sonra seçim (p-hacking) olmaz. Öncelik sırası
jüri sorularına doğrudan yanıt verenler önde.

- [x] (27 Ekim, §10.3-2, `2026-10-27_yeni_gun/` `tabakalar`: mevsim ve 30 m/s rüzgâr tabakaları) **Fikir 4 — Tabakalı doğrulama** (protokol §10.3-2'de kayıtlı): mevsim, 250 hPa rüzgâr sınıfı (<30 / ≥30 m/s),
  backtest için uçuş yönü; tabaka başına n, ROC-AUC, bootstrap GA. `ml/degerlendirme.py`.
- [x] (27 Ekim, §10.3-3: 6.992 metinli örneğin 2.079'u hafif negatif; çıkarılınca TI1 0,654 → 0,730, temel model
  0,683 → 0,772) **Fikir 8 — "Hafif = negatif" duyarlılığı** (protokol §10.3-3'te kayıtlı): hafif raporlar negatiften çıkarılır,
  AUC/Peirce yeniden; birincil sonuç değişmez, yalnız duyarlılık tablosu.
- [x] (31 Ekim, §13.5, `2026-10-31_uyari_alani/`: 41 bağımsız NE-ABD gününde POD–alan AUC TI1 0,631, birleşik EDR
  +0,024 [+0,013; +0,037]; 7e-7'de ızgaranın %16,3'ü uyarıda, POD 0,33, POFD 0,18; TTS hesaplanmadı) **Fikir 9 — Uyarı alanı oranı:** seçili eşikte riskli ızgara/nokta oranı ve
  "POD – uyarı alanı" eğrisi; TTS yalnız MADIS günlerinde. `ml/gosterge_degerlendirme.py`.
  Rota düzeyindeki sapma oranı 28 Ekim'de ölçüldü (`docs/sonuclar/2026-10-28_uyari_orani/`); ızgara/POD eğrisi açık.
- [x] (31 Ekim, §13.1: §10'un 79 gününde ±1 hücre/seviye/saat maksimumu TI1'den +0,027 [+0,017; +0,037], yalnız
  yatay +0,020 [+0,016; +0,024]; 7e-7'de POD 0,49 → 0,85 ama POFD 0,25 → 0,64, eşik yeniden seçilmeden kullanılamaz;
  eslestirme.py modu ONAY ile sunum sonrası) **Fikir 10 — Komşuluk maksimumu eşleştirmesi:** ±1 hücre / ±1 sa pencerede TI1
  maksimumu, iki sınıfa birlikte; `fizik/eslestirme.py`'de isteğe bağlı mod.
- [x] (20 Ekim, `docs/sonuclar/2026-10-20_pirep_ayristirici/`: 500'de 499 uyuşma; çoklu /TB grubu %0,24 etiketi çevirir, aşağıdaki maddeye) **Fikir 11 — PIREP ayrıştırıcı çapraz testi:** 500 ham IEM PIREP, `pirep_siddet_sinifi`
  ile avwx-engine karşılaştırması; uyuşmazlık çıkarsa etiket değişikliği ayrıca karar.
- [x] (31 Ekim, §13.2: test günlerinde 22, eğitimde 38 etiket 0→1, 1→0 yok; ROC-AUC farkları ≤ +0,002, etiket
  gürültüsü bu kaynaktan sonucu değiştirmiyor) **Fikir 11 devamı — çoklu /TB grubu etiketi:** IEM yalnız ilk grubu alıyor (`TB NEG 350/MOD 355` -> negatif);
  seyir raporlarının %0,24'ünde etiket döner. En şiddetli grubu alan etiket, dondurma sonrası yeni günlerde
  duyarlılık olarak (protokole önceden yazılarak) değerlendirilir; dondurulmuş paket değişmez.
- [x] (31 Ekim, §13.6: pencere deposunda t−6 sa yok; NE-ABD küplerinde 41 günde POD–alan AUC TI3 − TI1 +0,015
  [−0,010; +0,043], PIREP ROC-AUC +0,007 [−0,030; +0,039]: fark gösterilemedi) **Fikir 15 — TI3 (Ellrod–Knox DVT):** TI3 = TI1 + 0,01·|div(t) − div(t−6 sa)|; ERA5
  pencere deposunda t−6 sa var mı önce kontrol; TI1'e karşı yeni günlerde.
- [x] (31 Ekim, §13.4: tek başına hepsi TI1'den zayıf (FRONT 0,518, |FRONT| 0,591, |∇T| 0,559, −PV 0,510; TI1 0,658);
  temel + 3 teşhis − temel −0,004 [−0,010; +0,002], F9 adayı değil; NCSU1 kaynak yokluğundan hesaplanmadı) **Fikir 19 — Ek teşhisler:** frontogenez, ∇T, NCSU1, negatif PV; F9 geniş özellik
  setine aday olarak protokole yazılır (3 seviyeyle PV kaba).
- [x] (31 Ekim, §13.3: ağırlıklar 0,18–0,21, neredeyse eşit; ağırlıklı − eşit −0,0003 [−0,0005; −0,0001], pratikte
  sıfır; eşit ağırlık kalır) **Fikir 24 — AUC² ağırlıklı birleşik EDR:** ağırlıklar yalnız eğitim günlerinden;
  `fizik/edr_esleme.py`'ye seçenek.
- [ ] **Fikir 29 — Uçak tipine duyarlı risk:** OpenAP `prop` ile kanat yükü (BADA lisanslı,
  kullanılmaz); F9 adayı. Beklenen kazanç küçük (Gökdeniz ve Ülkü 2026: katkı %3,2).

## 20 Ekim denetiminden ertelenenler (`docs/denetim/2026-10-20/DENETIM.md` §8)

- [ ] **5 Kasım sunumundan sonra:** `rota_simulasyonu_olustur` (~460 satır, iç içe kapanışlar ortak
  yerel durumu paylaşıyor) adım fonksiyonlarına bölünür. Önce master'dan altın çıktı alınır
  (koridor + ATS, 4 senaryo, rota + CZML JSON); bölmeden sonra çıktı bayt bayt aynı olmalı
  (D-5'te #126 böyle doğrulandı).
- [x] **mypy'yi kademeli genişlet:** 28 Ekim'de `rota/`, `isci/`, `analiz/`, `dogrulama/`, ardından `veri/` ve
  `ml/` eklendi (109 dosya temiz; bulgular tip ek açıklaması, `cast(CursorResult, …)` ve değişken adı ayrımıyla
  giderildi, davranış değişmedi). Kalan: `arayuz/`, `cli/` ve kök modüller; `depo/models.py` zaman sütunları
  `Mapped[object]` (ileride `Mapped[datetime]`).
- [ ] **Düşük öncelik:** araştırma CLI'larına test (`cli/demo_ekranlari` %27,
  `cli/performans_olcumu` %51); karar destek yolunda değiller.

## Tarihli hatırlatmalar

- [x] (27 Ekim: `~/sunum_paketi_20261027`, 477 MB, OneDrive `TurbulansRadar_Yedekleri/sunum_paketi_20261027`, SHA256 OK; `compose wait` hatası düzeltildi) **25 Ekim:** sunum için Docker imajı yedeği: WSL'de `bash scripts/sunum_paketi.sh` (S-8; temiz klon,
  demo, ağsız ekran provası, `docker save`, SHA256SUMS). Çıktıyı OneDrive'a kopyala. Betik 19 Ekim'de
  yalnız sözdizimi ve compose ayarıyla denendi; ilk gerçek çalıştırma bu gün.
- [x] (29 Ekim: "yenilendi", AIRAC 11/26, bitiş 26 Kasım; 30 Ekim "guncel") **29–30 Ekim (AIRAC bitişi, otomatik; ONAY 19 Ekim, komite O-3):** "TurbulansRadar AIRAC
  yenileme" Windows görevi (her gün 12:00) yeniler; yalnız kontrol: `ciktilar/airac_yenile.log`
  "yenilendi" ve `db_aktarildi: true` diyor mu, `/saglik` `ats_agi` "tamam" mı. Görev ENR 1.3 FRA
  cümlesini bulamazsa (ör. H24'e geçiş) eski ağı korur ve BAŞARISIZ yazar; o zaman ENR 1.3 elle okunur.
- [x] (27 Ekim: PDF'ler hazırlandı, #136; e-posta gönderimi kullanıcıda, yukarıda madde 2) **29 Ekim Perşembe 23:55:** haftalık ilerleme raporu Hafta 5 (23 Ekim teslimi yapılmadı;
  `docs/rapor/ILERLEME_RAPORU.md` + `scripts/ilerleme_raporu_pdf.py`, PDF'ler masaüstüne).
- [ ] **3 Kasım (#11 devamı; ONAY 28 Ekim):** `turbulans-tahmin-ufku --indir --baslangic 2026-10-28T12 --bitis
  2026-11-03T00` (UCAR yalnız son ~7,5 günün koşularını tutar; ~15 MB), sonra tüm aralıkla (23 Ekim–3 Kasım)
  yeniden rapor. Aynı gün ERA5 kıyası: ERA5'in yayınlandığı geçerlilik zamanları (~5 gün gecikme) için küçük
  CDS kutusu, GFS f000/f024/f048 TI1'i ERA5 TI1'ine karşı (31 Ekim: `turbulans-tahmin-ufku --era5`).
- [ ] **5 Kasım:** E8 yedek demo videosu (3–5 dk, metin `docs/sunum/DEMO_SENARYOSU.md` §4;
  ekranlar temiz klondan).
- [ ] Sunum konuşulmaya başlanınca: E7 kullanılabilirlik oturumları (katılımcı bulmak zaman alır).
- [ ] **Rapor tesliminden hemen önce (komite Y-1):** `python scripts/beyan_sayimlari.py --kontrol`;
  farklıysa `docs/rapor/ARAC_KULLANIMI_BEYANI.md` paragrafı güncel sayılarla yenilenir.

## Kullanıcı kararı bekleyenler

- [x] (28 Ekim) A1 rota seçim kuralının varsayılanı: `sozluksel` kaldı, `maliyet` bayrak (ADR 0013).

- [x] (29 Ekim: talep açıldı, "Remove the commit references"; PR sayfası kalır) GitHub Destek talebi (P0-9): PR #1'deki eski OpenSky şifresinin temizlenmesi; ayrıntı "18 Ekim gecesinden
  kalanlar" bölümünde. Kullanıcı gönderecek (19 Ekim'de ertelendi); depo herkese açılmadan önce şart.
- [x] (16 Ekim, kullanıcı gönderdi) OpenSky'a bulut IP / Trino sorusu (`docs/fizibilite/OPENSKY_BULUT_ERISIMI.md`).
- [x] (17 Ekim) OpenSky yanıtı geldi, özet `OPENSKY_BULUT_ERISIMI.md`'de: hiperölçekli bulut IP'leri giriş
  noktasında engelli (Trino dahil), Hetzner garantisiz; B planında OpenSky sorguları dizüstünde kalır.
- [ ] Avrupa/Türkiye nesnel etiket kaynağı için MGM'ye ve IATA Turbulence Aware'a başvuru
  (dış iletişim; bkz. `docs/fizibilite/TURKIYE_ETIKET_KAYNAKLARI.md`).
- [ ] Eski commit mesajlarındaki yapay zekâ imzalarının temizliği (force-push gerektirir;
  önerilen: yapılmaması).
