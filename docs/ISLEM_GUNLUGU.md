# İşlem Günlüğü

Her oturumun kısa özeti, en yeni üstte. Telefondan (GitHub mobil) okunmak için kısa tutulur.

## 2026-10-16 gece (dal `claude/geri-bildirim`)

- ✅ Fikir 14: `POST /api/v1/geri-bildirim` + yönetici özeti; migration önce -test DB'de upgrade/downgrade, yedek 16 Eki var.

## 2026-10-16 gece (dal `claude/fpl-madde15`)

- ✅ Fikir 13: önerilen rota için ICAO Madde 15 dizgisi (NON-OPERATIONAL), web brifing kartında; biçim AIP'den doğrulandı.

## 2026-10-16 gece (dal `claude/opensky-bulut-sorusu`)

- ✅ Fikir 12: OpenSky'a bulut IP/Trino sorusu taslağı → `docs/fizibilite/OPENSKY_BULUT_ERISIMI.md` (gönderim sizde).

## 2026-10-16 gece (dal `claude/ongoru-uyarisi`)

- ✅ Fikir 7: GFS rotasında kalkışa >48 sa ise `ongoru_belirsiz` uyarısı (Lee 2025; kalibre değil).

## 2026-10-16 gece (dal `claude/kutle-bandi`)

- ✅ Fikir 6: yakıt tasarrufu %70/85/90 MTOW bandıyla; seviye değişiminde %1,1–2,9 (S3), yanalda duyarsız.

## 2026-10-16 gece (dal `claude/ayriklastirma`)

- ✅ Fikir 5: 41 nokta/20 km varsayılanı ince ayara göre ≤%0,45 fark, strateji aynı; 21 nokta yetersiz → `docs/sonuclar/2026-10-16/`.

## 2026-10-16 gece (dallar `claude/gfs-ti1-esigi`, `claude/gfs-toplulugu`)

- ✅ Fikir 2: `TI1_ESIK_ORTA_SIDDETLI_GFS` (boş = davranış aynı) + `turbulans-esik-esleme`; 13 MB indirme.
- ⚠️ Ölçüm: aynı eşikte GFS %11,1, ERA5 %8,5 riskli; GFS eşdeğeri 8,30e-7. Değer 18 Eki'de ayarlanacak.
- ✅ Fikir 3: rota isteğinde `topluluk=true` → son 4 GFS koşusundan deneysel TI1 aşım oranı (rota kararına girmez).

## 2026-10-16 gece (dal `claude/literatur-bolme-yontemi`)

- ✅ Fikir 1: ILGILI_CALISMALAR §5 paragraf + §9 "değerlendirme bölmesi" sütunu; Gökdeniz 2026, Gu ve Wang 2024 eklendi (künyeler arXiv/Crossref ☑).

## 2026-10-16 akşam (dal `claude/kaynak-incelemesi`)

- ✅ Kaynak incelemesi: 23 yıldızlı depo + 28 makale (5'i Silinecekler) → `docs/arastirma/KAYNAK_INCELEMESI.md`.
- ✅ 30 fikir etki/efor sırasıyla; ilk 3: literatür kıyasına bölme sütunu, ayrıklaştırma yakınsaması, kütle bandı.
- ⚠️ Kod değişmedi; ML'e dokunan öneriler 18 Eki dondurması sonrasına işaretli.

## 2026-10-16 (dal `claude/ilerleme-raporu`)

- ✅ Gece işi 11:02 UTC'de başladı (çalışıyor).
- ✅ Hocaya haftalık ilerleme raporu: `docs/rapor/ILERLEME_RAPORU.md` (Cuma–Perşembe haftaları, sade dil, her hafta alta eklenir).
- ✅ PDF: `python scripts/ilerleme_raporu_pdf.py` → `ILERLEME_RAPORU.pdf` (tamamı, e-posta) + `_SON_HAFTA.pdf` (çıktı).
- ✅ Rapor sadeleştirildi: künye (Tevfik ÜNER / Fatih TİTREK), Hafta 4 = 9–16 Eki, plan bölümü kaldırıldı; son hafta PDF tek sayfa.

## 2026-10-15 akşam (dallar `claude/openap-yakit`, `claude/demo-ekranlari-openap`, `claude/deneyler-f9-f3-f6`)

- ✅ F1 OpenAP yakıt + NOx (PR #47): kütle/irtifa/düşey hıza bağlı; demo %9,7→%9,5, FL370 seçeneği −%2,0 yakıt.
- ✅ Demo ekranları temiz klondan (5532/8100 portları) yenilendi; brifing kutusu ve NOx satırı görünür (PR #48).
- ✅ API + worker yeni imajla; ilk worker derlemesi kilit yazılırken düştü, yeniden derleme temiz.
- ✅ F3 tip analizi: ağır − hafif kanat yükü farkı −0,014 [−0,041; +0,012] → anlamlı değil.
- ✅ F6 dedektör: 90 ft'te %50, ≥120 ft'te ~%100 tespit; 5–15 ft gürültüde yanlış alarm 0.
- ⚠️ F5 backtest yakıtı: THY322 bölümleri TAS 154–166 m/s (tırmanış) → karşılaştırılamaz işaretli.
- ✅ F7 notu: MADIS'te rüzgâr var (Türkiye kutusunda saatte ~23 FL280+); 2019 için GFS arşivi yok.
- ✅ F9 (altın gün dışı CV): ayar +0,001; bağlam özellikleri +0,008; en iyi geniş lojistik 0,711 (TI1 0,674).
- ✅ İleri tarihli tüm işler tek dosyada: `docs/YAPILACAKLAR.md`.

## 2026-10-15 (dal `claude/kabin-penceresi`)

- ✅ Kabin önerisi: tek saat yerine ±15 dk pencere (KABIN_PENCERE_PAYI_DK, kalibre edilmedi), emir kipi kalktı.
- ✅ Brifing kartı: `brifing_karti` 3 satır (rota, kalan risk, kabin) API + simülasyon ekranında; 964 test geçti.
- ✅ Gelecek çalışma slaytı/poster: bitmiş M1/M6/IWXXM çıktı; ürün yönü F1–F4 eklendi.
- ✅ GEFS ölçümü: 1 üye/adım 1,38 MB indirme, Türkiye kesiti 18 KB → 31 üye ~43 MB/adım.
- ✅ Türkiye etiket notu: uçak EDR'si WMO-IATA kısıtlı; adaylar MGM ve IATA Turbulence Aware.
- ⏳ 18 Eki sonrası: 7 seviyeli Türkiye ERA5 + OpenSky büyütmesi (kota kararı).
- ✅ Belgelerdeki eski test/CI sayıları: 974 test, 6 iş, kapsam %85 (sunum, poster, sistem kartı, katkılar).

## 2026-10-15 (dal `claude/kok-temizligi`)

- ✅ Gece işi 16:39 UTC'de kendiliğinden başladı; 14 Eki adayı aktif modeli geçemedi (+0,001).
- ✅ Kök temizliği: trino.jar, eski proje zip'i, kök harita HTML'leri silindi; eski CSV/PNG/log `arsiv/` içine tar.gz (git dışı).

## 2026-10-14 (dallar `claude/ci-fatura-notu`, `claude/demo-uretilebilirlik`)

- ⚠️ CI 13 Eki 16:20'den beri kırmızı: işler başlamıyor (GitHub faturalandırma/harcama limiti, özel depo). Kod hatası yok.
- ✅ Yerel doğrulama: ruff check + format temiz, pytest 964 geçti (tarayıcı/ağ hariç).
- ✅ CI yeniden yeşil (depo public yapıldı); geçmiş sır taraması temiz.
- ✅ Madde 10 (PR #42): .dockerignore + LF → geliştirici/temiz klon bağlamı bayt bayt aynı, imaj 1,78→1,46 GB.
- ✅ AIRAC alanları (ATS ağı bitişi 29 Eki) → rota `ats.uyarilar` + `/saglik ats_agi: eski`.
- ✅ 2 kullanım dışı modül silindi, 3 CLI komut oldu; CI demo işi (temiz makinede 80 sn), ubuntu-24.04.
- ✅ Ağsız demo provası (temiz klon, DNS kapalı) geçti; yalnız Esri karoları kesildi (652).
- ⚠️ Senaryo 2 anlatımı geliştirme küpünden (FL370) alınmıştı; temiz klon yanal 105 NM/%9,7 veriyor → belge, poster, ekranlar düzeltildi.
- ✅ demo_ekranlari: sabit 6 sn yerine Cesium saati ilerleyince çekim (ekran 03 boş çıkıyordu).
- ⏳ 18 Eki: SISTEM_KARTI/README mimari denetimi; 29 Eki: AIP yeniden indirme.

## 2026-10-13 (dallar `claude/kayma-izleme`, `claude/api-router-ayrimi`, `claude/ayar-dogrulama`)

- ✅ ML özellik kayması (PSI/KS): gerçek veride 7.761 referans / 3.588 yeni örnek, maks PSI 0,025 (kararlı); `turbulans-ml --kayma`.
- ✅ api_servisi 2.231→~1.270 satır: guvenlik, ortak, yollar/ (4 router); OpenAPI şeması birebir aynı.
- ✅ Başlangıçta pydantic ayar doğrulaması; 'ture' gibi değerler artık hata. Tam pydantic-settings yapılmadı (gerekçe CHANGELOG). 933 test geçti.

## 2026-10-13 (dallar `claude/devre-kesici`, `claude/uretim-bilgisi`, `claude/uretim-ortami-ayarlari`)

- ✅ Canlı GFS devre kesici: 3 ardışık hatadan sonra 5 dk→1 sa üstel bekleme, sonuç "alınamadı" (risk yok değil).
- ✅ Rota/tahmin yanıtında `uretim_bilgisi`: sürüm, hava küpü, eşikler, model sha256.
- ✅ `MODEL_BUTUNLUK_ZORUNLU=true` yerel .env'de; `FORWARDED_ALLOW_IPS` compose + üretim örneğinde. 913 test geçti.

## 2026-10-13 (fark denetimi, dallar `claude/model-butunlugu`, `claude/dry-cografya-dogrulama`)

- ✅ Model dosyası sha256 doğrulaması (`turbulans-ml --muhurle`), Streamlit silme artık API + yönetici anahtarı.
- ✅ Haversine 6→1 (`fizik/cografya.py`), uçuş no/tarih kuralı tek yerde (`ucus_kurallari.py`; CLI artık doğruluyor).
- ⚠️ Açık: api_servisi bölme (L), üretim bilgisi/provenance, devre kesici, drift. Rapor: `test_raporu/2026-10-13/RAPOR.md`. 905 test geçti.

## 2026-10-13 (dal `claude/ruzgar-optimum-referans`)

- ✅ Uzman raporu (2. tur) süzüldü: rüzgâr-optimum referans rota; yanıtta `referans_karsilastirmasi` (rüzgâr kazancı / kaçınma bedeli ayrı), 3B arayüzde satır.
- ✅ Sanal PIREP bildirimine ERA5 TI1 uyum etiketi (`era5_uyumu`); olayı elemez, DB'ye yazılmaz.
- ⚠️ Avrupa genellemesi: yerel MADIS'te Avrupa 21.167 gözlem ama 28 hafif+, Türkiye 0 → skor raporlanmaz, sınırlama yazıldı.
- ✅ Belgeler: kinematik uçulabilirlik hesabı (25° yatış), CI/alçalma kredisi ve kanat yüklemesi kapsam dışı gerekçesi.

## 2026-10-08 (işletim, dal `claude/gfs-imaj-yenileme`)

- ✅ Canlı GFS 6 Eki 15:06'dan beri inmiyordu: API konteyneri PR #29'dan önce başlatılmıştı (DNS hatasında 6 sa kilit). Yalnız API yeniden derlendi; 16:07 UTC'de indirme başarılı, derin sağlık "ayakta".
- ✅ Güvenlik taraması: uygulama rolü, MCP şifresi, pilot anahtarı, WS bileti zaten düzgün; OneDrive yedeği parolayla açılıp yerel dump'la aynı çıktı. Windows PG17 kaldırıldı, eski proje kopyası silindi (kullanıcı).

## 2026-10-08 (dal `claude/uzman-raporu-eksikleri`)

- ✅ Uzman raporu taraması: Madde 1–9 kabul kriterleri kodda karşılanıyor; kalan belge eksikleri kapatıldı.
- ✅ MADIS "başvuru yapıldı" → herkese açık arşiv (sunum, poster, KATKILAR); SINIRLAMALAR sayıları ön pakete hizalandı.
- ✅ SISTEM_KARTI §5: ERA5→GFS aktarımı doğrulanmadı (MET-06), ATFCM/CTOT, uçak tipi, Item 15, yakıt modeli, backtest FRA, görev süresi.
- ✅ Alembic gidiş-dönüş testi (YZL-05): her göç geri alınınca şema önceki haline dönüyor. 910 test geçti, ruff temiz.

## 2026-10-08 (dal `claude/gfs-isitma-yeniden-deneme`)

- ✅ GFS ısıtması başarısız denemeden sonra 6 sa değil 30 dk sonra yeniden dener (açılışta DNS hazır değilken 2 kez kilitlenmişti). 909 test geçti.
- ✅ Gece işi 8 Eki 14:43 UTC'de (açılışta) başladı; CDS indirmesi sürüyor.

## 2026-10-08 (dal `claude/hizli-tarama`, hızlı tarama)

- ✅ ruff temiz, 908 test geçti (atlanan yok), yığın sağlıklı, belgelerde kırık bağlantı yok; kod değişikliği gerekmedi.
- ⚠️ Canlı GFS 7 Eki 19:05 UTC'de DNS hatası (geçici; DNS şimdi çalışıyor, sonraki ısıtmada düzelir). Madde 10 ertelendi.

## 2026-10-08 (dal `claude/proje-isleyisi`)

- ✅ Çekirdek anlatım kartı yerine tüm akışı anlatan `docs/sunum/PROJE_ISLEYISI.md` (veri → filtre → eşleştirme → rota → model → doğrulama).
- ⚠️ Commit mesajlarındaki yapay zekâ satırlarının temizlenmesi (geçmişi yeniden yazma) güvenlik denetimince engellendi; kullanıcı kararı bekleniyor.

## 2026-10-08 (dal `claude/beyan-ve-anlatim-karti`, Madde 9 kullanıcı adımları)

- ✅ YZ beyanı: biçim tek paragraf (yöntem sonu); yazar alanı git'ten (ilk 2 commit'ten kalan satır %1,9). Danışman e-postası taslak.
- ✅ Çekirdek anlatım kartı `docs/sunum/CEKIRDEK_ANLATIM_KARTI.md`: 4 modül, formüller, satır bağlantıları, jüri soruları.
- ⚠️ Kararsız test düzeldi: TI1 önbellek testinde `kalkisa_kalan_saat` şimdiye bağlıydı (36 sn yuvarlama); saat sabitlendi.

## 2026-10-08 (dal `claude/tez-cercevesi-readme`, Madde 9 kapanışı)

- ✅ README ilk ekranı: problem, araştırma sorusu, ön paket sayılarıyla kısa cevap, demo, çekirdek (K1/K2/K6/K7) ve ekler.
- ✅ Sunum akışı: literatür özeti dolduruldu, çekirdek/mühendislik eki ayrımı, ekler yedek slaytta.
- ✅ Araç kullanımı (YZ) beyanı taslağı `docs/rapor/ARAC_KULLANIMI_BEYANI.md`; biçim danışmana, `[YAZAR]` alanı Tevfik'te.
- ✅ Literatür tablosundaki eski 0,730 ön paketle (LR 0,681, +0,008 anlamsız) değişti. Tam test 908 geçti.

## 2026-10-08 (dal `claude/esik-ve-rota-hizi`, Madde 8 açık kararları)

- ✅ TI1 risk eşiği 8e-7 → 7e-7: eğitim günlerinde Peirce max'ın 1 SE'si içindeki en tutucu eşik (1-SE kuralı).
- ✅ Altın günlerde 7e-7: POD 0,50, POFD 0,25 (8e-7: 0,45 / 0,20). Backtest yeniden: 15 Oca A* 0,02 (tam sıfır değil).
- ✅ Rota yavaşlığının nedeni: Pareto için 4 A* + seviye adayları (tasarım). Rüzgâr tek okuma + TI1 paylaşımı: %30 hızlı.
- ✅ Şarjda rota 0,03–0,45 sn (dün pilde 1,3 sn). Sonuç birebir aynı (eşdeğerlik testleri). Tam test 908 geçti, 4 dk.
- ✅ Docker api/worker yeni kodla derlendi; demo ekranları yeniden çekildi; ön paket yeniden üretildi.

## 2026-10-07 (dal `claude/sonuc-paketi-dondurma`, Madde 8)

- ✅ `turbulans-ml-degerlendirme --kesme --cikti`: commit hash'li JSON + SAYILAR.md + 3 PNG; ön paket `docs/sonuclar/2026-10-07/`.
- ⚠️ Altın günlerde LR 0,681 vs TI1 0,673, fark [−0,006; +0,022] → kapı geçilmedi (ön sonuç). Birleşik EDR TI1'i geçiyor (+0,014).
- ✅ TI1 Peirce eşiği 5,3e-7 (config 8e-7 değişmedi, karar açık); CAT alt kümesi sonucu değiştirmiyor; MADIS 6 gün, GA'lı.
- ✅ "EDR proxy" → gösterge/TI1 görsel ölçeği (EDR değildir); bayrak `TI1_GORSEL_OLCEK_PIREP_SINIFINA_UYDURULDU`.
- ⚠️ `turbulans-performans rota`: sıcak 0,08–1,36 sn (pilde), eski iddia 0,02–0,27 sn; A* 0,3–0,4 sn. Nedeni incelenmedi.
- ✅ PUE502 28→33 nedeni SISTEM_KARTI §6 ve README'de (kayıt DB'de yok, yeniden üretilemedi).

## 2026-10-07 (dal `claude/ml-duyarlilik`, Madde 7 isteğe bağlı)

- ✅ `turbulans-ml-duyarlilik`: gün/ISO hafta/ay gruplu CV; LR AUC 0,699/0,698/0,698 → sızıntı izi yok.
- ✅ Net örnek deneyi (NEG/SMOOTH vs LGT'siz MOD+): anlamlı iyileşme yok; etiket tanımı korunur.
- ⚠️ Yan bulgu: altın günlerde RF/GB TI1'i geçiyor, 1-SE'nin seçtiği LR geçmiyor; protokol değişmez (test'e bakarak seçim olur).
- ✅ Penceresiz eşleşmiş örnek kalmadı (SONUCLAR §6 güncellendi). Ayrıntı: `docs/rapor/SONUCLAR.md` §2.3.

## 2026-10-07 (dal `claude/ml-protokolu`, Madde 7)

- ✅ Altın test günleri donduruldu (80 günden rastgele 16, tohum 0, `ml/altin_test_gunleri.json`); hiçbir eğitime girmez.
- ✅ Seçim CV AUC + 1-SE (LR), GB dengeli; kapı TI1 ve aktif modele karşı fark ≥0,02 ve GA alt > 0; Peirce eşikleri, kalibre TI1.
- ✅ API `veri_kaynagi`; GFS'de konformal kapsama `null` + "doğrulanmadı". README eski tablo tarihçeye indi.
- ✅ Docker imajı yeniden derlendi; api/worker yeni protokolde (16 altın gün yüklü).
- ✅ CI 6 Eki'den beri kırmızıydı: gitleaks RFC 6455 örnek WebSocket anahtarını sır sandı; yanlış pozitif işaretlendi (PR #20), CI yeşil.
- ⚠️ Ön sonuç (geçici klasör): LR, AUC 0,681 vs TI1 0,673, fark [−0,006; 0,022] → kapı geçilmedi. 18 Eki dondurma bekliyor.

## 2026-10-07 (dal `claude/sapma-yonu`, Madde 6 kapanış)

- ✅ Madde 6 kabul kriterleri koda karşı doğrulandı; tek eksik "NM L/R of track" yönüydü, eklendi (`maks_yanal_sapma_yonu`).
- ✅ Tam test 855 geçti; tarayıcı (Playwright) 8/8 geçti.

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
