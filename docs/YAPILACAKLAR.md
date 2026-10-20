# Yapılacaklar (ileri tarihli işler)

İleri bir tarihe ertelenen tüm işler burada tek listede tutulur. Biten madde silinmez,
`[x]` ile işaretlenir ve yanına PR/tarih yazılır. Yeni ertelenen iş buraya eklenir.

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
- [ ] **GitHub Destek talebi (P0-9, kullanıcı):** PR #1'deki eski OpenSky şifresi; metin
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

- [ ] **Sonraki oturumun başında: yığını güncel imajlarla derle (19 Ekim'de uzun sürdüğü için yarıda bırakıldı).**
  #114 (postgres 16 yeni özet) ve #115 (python 3.12-slim yeni özet) master'da, çalışan yığın bir önceki
  imajlarda (sağlıklı). Görev kuyruğu boşken WSL'de: `export GIT_SHA=$(git rev-parse HEAD) && docker compose
  pull db && docker compose build api worker migrate && docker compose up -d --wait` (~20 dk; taban imaj
  değiştiği için bağımlılıklar yeniden kurulur). Sonra `/saglik?derin=true` "tamam" ve `migrate_yedegi` yedeği.
- [ ] **PR #116 (CI postgres servis imajı compose ile aynı özette):** CI'ı geçince birleştir; yalnız
  `.github/workflows/ci.yml` iki satır.

- [x] (20 Ekim: önerilen (a) uygulandı, önbellek isabeti sınırdan muaf) **Rota hız sınırı kararı (S-9, kullanıcı 19 Ekim'de erteledi):** aynı NAT arkasındaki 10 cihazda
  rota isteklerinin %40'ı 429 aldı; önbellekten dönen rota da sınıra takılıyor (`PERFORMANS_RAPORU.md`
  §5.5). Seçenekler: (a) önbellek isabetini sınırdan muaf tutmak, (b) sınırı cihaz/anahtar başına
  yapmak, (c) `ROTA_HESABI_DAKIKADA_MAKS`'ı yükseltmek. Karar kullanıcıda; sonra uygulanır ve S-9 yeniden ölçülür.
- [ ] **S-3 senaryo seçici (M):** `web/ucus_simulasyonu.html` 2019 değerleriyle sabit açılıyor;
  `web/veri/senaryolar.json` + açılır liste, senaryo başına Playwright testi.
- [ ] **S-4 başarısızlık durumları simülasyonda (M):** "ÖNERİ YOK", SIGMET bayat, `erisilemedi`, devre
  kesici gösterilebilsin; demo profilinde fikstür (gerçek arşiv yoksa SENTETİK etiketli).
- [ ] **P1-10 işletim kılavuzu (M):** `docs/ISLETIM_KILAVUZU.md` (başlatma/durdurma, yedek ve geri
  yükleme, migration, AIRAC, gece işi, anahtar ve DB şifre rotasyonu); her prosedür bir kez denenir.
- [ ] **P1-3 izleme yığını (ONAY: bildirim kanalı):** `izleme/prometheus.yml`, `alarmlar.yml`,
  `--profile izleme`; bildirim kanalı (e-posta/Telegram vb.) kullanıcı seçer.
- [ ] **P1-6 kalan kısmı:** üretimde anahtarsız `/saglik?derin=true` yalnız `{"durum"}` dönsün
  (bugün bileşen adı + durum dönüyor, ayrıntı yok).
- [ ] **Worker bellek sınırı (P1-1 kalan):** bir gece işi sırasında `docker stats` ile tepe bellek
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
- [ ] **§10 değerlendirmesini bir kez çalıştır:** her gece işi sonrası `turbulans-ml-yeni-gun --durum`;
  `yeterli: true` olunca `turbulans-ml-yeni-gun --cikti docs/sonuclar/<tarih>`, sonuç ne çıkarsa raporlanır.
- [ ] **20 Ekim, gece işinden önceki ilk oturum (ONAY alındı, komite B-3):** Türkiye ERA5 7 seviye
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

- [ ] **Fikir 4 — Tabakalı doğrulama** (protokol §10.3-2'de kayıtlı): mevsim, 250 hPa rüzgâr sınıfı (<30 / ≥30 m/s),
  backtest için uçuş yönü; tabaka başına n, ROC-AUC, bootstrap GA. `ml/degerlendirme.py`.
- [ ] **Fikir 8 — "Hafif = negatif" duyarlılığı** (protokol §10.3-3'te kayıtlı): hafif raporlar negatiften çıkarılır,
  AUC/Peirce yeniden; birincil sonuç değişmez, yalnız duyarlılık tablosu.
- [ ] **Fikir 9 — Uyarı alanı oranı:** seçili eşikte riskli ızgara/nokta oranı ve
  "POD – uyarı alanı" eğrisi; TTS yalnız MADIS günlerinde. `ml/gosterge_degerlendirme.py`.
- [ ] **Fikir 10 — Komşuluk maksimumu eşleştirmesi:** ±1 hücre / ±1 sa pencerede TI1
  maksimumu, iki sınıfa birlikte; `fizik/eslestirme.py`'de isteğe bağlı mod.
- [ ] **Fikir 11 — PIREP ayrıştırıcı çapraz testi:** 500 ham IEM PIREP, `pirep_siddet_sinifi`
  ile avwx-engine karşılaştırması; uyuşmazlık çıkarsa etiket değişikliği ayrıca karar.
- [ ] **Fikir 15 — TI3 (Ellrod–Knox DVT):** TI3 = TI1 + 0,01·|div(t) − div(t−6 sa)|; ERA5
  pencere deposunda t−6 sa var mı önce kontrol; TI1'e karşı yeni günlerde.
- [ ] **Fikir 19 — Ek teşhisler:** frontogenez, ∇T, NCSU1, negatif PV; F9 geniş özellik
  setine aday olarak protokole yazılır (3 seviyeyle PV kaba).
- [ ] **Fikir 24 — AUC² ağırlıklı birleşik EDR:** ağırlıklar yalnız eğitim günlerinden;
  `fizik/edr_esleme.py`'ye seçenek.
- [ ] **Fikir 29 — Uçak tipine duyarlı risk:** OpenAP `prop` ile kanat yükü (BADA lisanslı,
  kullanılmaz); F9 adayı. Beklenen kazanç küçük (Gökdeniz ve Ülkü 2026: katkı %3,2).

## Tarihli hatırlatmalar

- [ ] **25 Ekim:** sunum için Docker imajı yedeği: WSL'de `bash scripts/sunum_paketi.sh` (S-8; temiz klon,
  demo, ağsız ekran provası, `docker save`, SHA256SUMS). Çıktıyı OneDrive'a kopyala. Betik 19 Ekim'de
  yalnız sözdizimi ve compose ayarıyla denendi; ilk gerçek çalıştırma bu gün.
- [ ] **29–30 Ekim (AIRAC bitişi, otomatik; ONAY 19 Ekim, komite O-3):** "TurbulansRadar AIRAC
  yenileme" Windows görevi (her gün 12:00) yeniler; yalnız kontrol: `ciktilar/airac_yenile.log`
  "yenilendi" ve `db_aktarildi: true` diyor mu, `/saglik` `ats_agi` "tamam" mı. Görev ENR 1.3 FRA
  cümlesini bulamazsa (ör. H24'e geçiş) eski ağı korur ve BAŞARISIZ yazar; o zaman ENR 1.3 elle okunur.
- [ ] **5 Kasım:** E8 yedek demo videosu (3–5 dk, metin `docs/sunum/DEMO_SENARYOSU.md` §4;
  ekranlar temiz klondan).
- [ ] Sunum konuşulmaya başlanınca: E7 kullanılabilirlik oturumları (katılımcı bulmak zaman alır).
- [ ] **Rapor tesliminden hemen önce (komite Y-1):** `python scripts/beyan_sayimlari.py --kontrol`;
  farklıysa `docs/rapor/ARAC_KULLANIMI_BEYANI.md` paragrafı güncel sayılarla yenilenir.

## Kullanıcı kararı bekleyenler

- [ ] GitHub Destek talebi (P0-9): PR #1'deki eski OpenSky şifresinin temizlenmesi; ayrıntı "18 Ekim gecesinden
  kalanlar" bölümünde. Kullanıcı gönderecek (19 Ekim'de ertelendi); depo herkese açılmadan önce şart.
- [x] (16 Ekim, kullanıcı gönderdi) OpenSky'a bulut IP / Trino sorusu (`docs/fizibilite/OPENSKY_BULUT_ERISIMI.md`).
- [x] (17 Ekim) OpenSky yanıtı geldi, özet `OPENSKY_BULUT_ERISIMI.md`'de: hiperölçekli bulut IP'leri giriş
  noktasında engelli (Trino dahil), Hetzner garantisiz; B planında OpenSky sorguları dizüstünde kalır.
- [ ] Avrupa/Türkiye nesnel etiket kaynağı için MGM'ye ve IATA Turbulence Aware'a başvuru
  (dış iletişim; bkz. `docs/fizibilite/TURKIYE_ETIKET_KAYNAKLARI.md`).
- [ ] Eski commit mesajlarındaki yapay zekâ imzalarının temizliği (force-push gerektirir;
  önerilen: yapılmaması).
