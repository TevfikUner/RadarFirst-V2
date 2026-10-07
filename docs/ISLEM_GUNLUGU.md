# İşlem Günlüğü

Her oturumun kısa özeti, en yeni üstte. Telefondan (GitHub mobil) okunmak için kısa tutulur.

## 2026-10-07 (dal `claude/fra-meydan-baglantisi`, Madde 5 kapanış)

- ✅ A/D rolleri meydana özgü: ENR 4.4/4.1'den 41 meydanın bağlantı noktaları okundu (`fra_meydanlari`).
- ✅ API/arayüz: isteğe bağlı `kalkis_meydani`/`varis_meydani`; IST→VAN (LTFM→LTCI) ESB … EZS, AIP'e uygun.
- ✅ Düzeltme: önceki MUS sonucu yanlıştı (MUS yalnız LTCE). Meydansız istekte bu artık uyarıda yazıyor.
- ✅ Hata düzeltildi: API şeması `ats.etiket`/`ats.uyarilar`'ı atıyordu. Tam test: 854 geçti.

## 2026-10-07 (dal `claude/enr41-seyrusefer`, Madde 5 ek)

- ✅ ENR 4.1 (62 VOR/NDB, FRA rolleriyle) ağa eklendi; tek PDF isteği. Ağ: 681 nokta, 24.838 DCT adayından 879'u elendi.
- ✅ IST→VAN artık YASEN(D) … MUS(A/D), uyarısız. A/D rolleri AIP'te meydana özgü; API meydan almadığı için genel sayılıyor.
- ✅ Sınır uç-parça muafiyeti (≤2× iç bölge uzaklığı) korundu. Tam test: 851 geçti.

## 2026-10-07 (dal `claude/fraturk-kurallari`, Uzman Madde 5)

- ✅ FRA penceresi düğüm zamanıyla: kenar sonu (belirsizlik payıyla) 02:00'den önce olmalı (ENR 1.3 §5.5.2.1).
- ✅ ToC D/E, ToD A/X rollü noktalara; FIR içinde önce D/A, yoksa E/X + `ats.uyarilar` (ENR 4.1 noktaları ağda yok).
- ✅ DCT'ler FIR içinde ve sınıra ≥5 NM (§5.2.1.6, §5.2.5): 20.514 adaydan 724'ü elendi; VATSIM sınırı yaklaşık.
- ✅ Etiket "FRATURK serbest rota (FL305+, 20:00–02:00 UTC)"; SISTEM_KARTI/README düzeltildi. Tam test: 850 geçti.

## 2026-10-07 (dal `claude/sigmet-tampon`, Uzman Madde 4)

- ✅ Gece işi: ml_veri 11:38 UTC'de başladı (çalışıyor); 6 Eki eğitimi kapıyı geçmedi (F1 0,680 / 0,701).
- ✅ SIGMET yanal tampon (TS/CONVECTIVE 20 NM, TURB/MTW 10 NM) + dikey 1000 ft; parametrik varsayım, kalibre edilmedi.
- ✅ Tampon antimeridyen bölmesinden önce km düzleminde; yanıtta `sigmet_kontrolu.tampon`; bağımsız kanıt tamponsuz.
- ✅ Tam test: 835 geçti. Demo SIGMET test kutusu küçültüldü (tamponla rota bulunamıyordu).

## 2026-10-06 (dal `claude/denetim-duzeltmeleri`, uçtan uca denetim + düzeltmeler)

- ✅ Denetim raporu `test_raporu/2026-10-06/RAPOR.md` + `ozet.html`; `scripts/tam_denetim.sh`, `scripts/demo_goster.py`.
- ✅ 10 bulgu düzeltildi: SIGMET 1970 kaydı (sahte kanıt), "NaN" havalimanı, tek model deposu, GFS ısıtma/bayatlık, eşleştirme 30,7→0,9 sn.
- ✅ Migration e9c1d4b7a2f6 (veri onarımı) -test'te up/down, dev DB'ye uygulandı; THY322 backtest yeniden üretildi.
- ✅ Tam test: 823 geçti (825 test), kapsam %85,8.

## 2026-10-06 (dal `claude/yasal-ucus-seviyesi`, Uzman Madde 3)

- ✅ Yarım daire kuralı: girdi ve dikey alternatifler aynı yönün yasal FL'sine (RVSM, tip tavanı); aykırı girişte uyarı.
- ✅ Alçalma yakıt kredisi kaldırıldı; yer hızı rüzgâr üçgeniyle (yan rüzgâr); ayırma sorgu bandı yeni FL'yi kapsıyor.
- ⚠️ Manyetik sapma sabit +5°E VARSAYIM (WMM yok). THY72C/THY606 DB'de yok, backtest tablosunda yalnız THY322.
- ✅ Tam test: 806 geçti, 1 atlandı.

## 2026-10-05/06 (kural değişikliği)

- ✅ master'a birleştirme Claude'a devredildi: PR şartı, pre-push kancası ve deny satırları kalktı; force-push yasağı duruyor (PR #8, #9).

## 2026-10-05 (dal `claude/edr-kalibrasyon-yeni-fizik`, Uzman Madde 2 kapanış)

- ✅ EDR proxy katsayısı yeni fizikle yeniden kalibre: 0,40 → 0,27 (GA 0,25–0,28; 6218 PIREP, 64 gün); test MSE 0,082 → 0,076.
- ✅ MADIS float32 yuvarlama yerelde doğrulandı: 4 gün, sınıf≥1 ham 2258 → yuvarlamalı 3193.
- ✅ Tam test: 797 geçti, 1 atlandı.

## 2026-10-05 (dal `claude/yazilim-guvencesi`, Uzman Madde 1)

- ✅ DB yoksa dış servis çağrıları (OpenSky/CDS/ARCO/MADIS/ADS-B) kilitsiz çalışmaz; OpenSky kotası reddeder.
- ✅ Gerçek küp testleri ana küp yoksa demo küpüyle koşar; CI'da atlanırsa iş kırmızı. Demo altın değer testi eklendi.
- ✅ Tam test: 797 geçti, 1 atlandı (eski ML modeli); `model_versiyonlari/` dosya sayısı değişmedi.

## 2026-10-05 (dal `claude/guvenlik-sertlestirme`)

- ✅ Sızma testindeki 2 yüksek risk kapandı: konteyner artık .env/yedek/.git göremiyor, kod salt okunur (canlı doğrulandı).
- 🔴 Sızma testi: 2 yüksek (konteyner /veri ile .env okuyor, kod yazılabilir), 3 orta; docs/guvenlik/SIZMA_TESTI_2026-10-05.md.

- ✅ Güvenlik taraması: 11 madde doğrulandı; ayrıntı docs/guvenlik/GUVENLIK_TARAMASI_2026-10-05.md.
- ✅ API/işçi artık süper kullanıcı değil `turbulans_uygulama` rolüyle (önce -test, sonra asıl DB; öncesinde yedek).
- ✅ OneDrive yedekleri gpg AES256 şifreli; şifresizler silindi, çözme bayt bayt doğrulandı.
- ✅ WS ?api_key= kapandı, bilet tek kullanımlık; /docs ağa açılınca kapanır; pilot anahtarı üretildi.
- ✅ Konteynerlere süper kullanıcı/MCP şifresi gitmiyor; hız sınırı DB yokken süreç içi sayaca düşer.
- ✅ Windows PG17: servis devre dışı, 6 güvenlik duvarı kuralı silindi; PR #6 açıldı.
- ⚠️ Kullanıcıda: yedek parolasını PC dışına kaydetme, GitHub Destek (depo gizli, acil değil). Disk şifrelemesi: istenmedi.

## 2026-10-05 (dal `claude/fizik-cekirdegi`)

- ✅ Madde 2 fizik: çevreleyen katman, 7 seviye, metrik terimler, hipsometrik; TI1 AUC 0,644 → 0,671.
- ✅ Birleşik EDR (Sharman-Pearson): PIREP 0,684 vs TI1 0,671 (+0,013, p<0,001); holdout +0,012.
- ✅ DB: 6220 PIREP + 12232 EDR özelliği yeni fizikle yazıldı (önce yedek); 1597 penceresiz kuyrukta.
- ⚠️ Docker imajı dal koduyla derlendi (gece işi yeni fizikle çalışır); PR birleşince fark kalmaz.
- ✅ Yeni fizikli aday TI1'i geçti (0,730 vs 0,707) ama F1'de aktif modeli geçemedi; aktif model aynı.
- ✅ Madde 6 dispeç: riskli bölüm UTC/FL/NM, "hesaplanmadı" ≠ 0, kabin önerisi, NM/h:mm/FL arayüz.
- ✅ Madde 8: docs/rapor/SONUCLAR.md + güvenilirlik diyagramı; MADIS 4 gün (GA için 5 gerekli).
- ✅ LOF: gerçek veride %68 tekrar → kuantizasyon titreşimi; sonuç değişmedi (ADR 0011).
- ✅ Madde 9: literatür tam metin (21 künye doğrulandı), katkı farkları, sınırlamalar, dersler.

## 2026-10-04

- ✅ Git kuralları: master'a doğrudan push yasak (.githooks/pre-push), iş claude/<konu> dalında, birleştirme PR ile.
- ✅ `alembic downgrade` (Bash) artık yasak değil, "önce sor"da; PowerShell karşılığını yasaktan çıkarmak kullanıcıda.

- ⚠️ Disk dışı yedek: yedekler OneDrive\TurbulansRadar_Yedekleri'ne de kopyalanıyor; OneDrive'a giriş yapılana dek buluta gitmez.
- ✅ OpenSky önbelleği günlük dosya arşivine eklendi.

- ✅ Güvenlik: `.claude/settings.json` deny listesi (rm -rf, docker compose down -v, DROP/TRUNCATE, force-push); test edildi, engelliyor.
- ✅ CLAUDE.md: dal `master`, mobil izleme kuralları eklendi.
- ✅ V1 (RadarFirst) şifre temizliği: commit yeniden yazıldı (5decb4a), kullanıcı force-push etti; GitHub'da eski commit'e işaret eden dal/PR yok.
- ✅ Yedek: günlük pg_dump + dosya arşivi zaten çalışıyor (`db_yedekleri/`).
- ✅ API yalnızca 127.0.0.1:8000; DB yalnızca localhost.
- ✅ Docker giriş betiği: süreçler uid 1000, Linux'ta yazma izni sorunu çözüldü (ca393f8).
- ✅ Denetim: yüksek/orta/düşük öncelikli maddeler kapandı; 750 test geçti.
- ✅ DB şifresi döndürüldü (43 karakter), MCP salt okunur rolle Docker DB'yi okuyor.
