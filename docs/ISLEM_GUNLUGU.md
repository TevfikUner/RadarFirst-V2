# İşlem Günlüğü

Her oturumun kısa özeti, en yeni üstte. Telefondan (GitHub mobil) okunmak için kısa tutulur.

## 2026-10-28

- ✅ A grubu devam: zaman örneklemesi (3 sa: Spearman 0,923, aynı karar %95,9); birleşik EDR klimatolojisi altın gün etkisi yok (≤ 0,0001); TI1 katman/seviye seçimi Ellrod–Knapp 1992 ile doğrulandı.
- ✅ A grubu: §10.6 model − birleşik EDR +0,016 [+0,010; +0,021] (`docs/sonuclar/2026-10-28_birlesik_kiyas/`); `katman_cevrelenmiyor` rota uyarısı; model paneli test günü ROC-AUC'si.
- ✅ AWC `airsigmet` 27 Eki 23:42'den beri HTTP 204 (veri yok) dönüyordu, derin sağlık sahte `bozulmus` veriyordu: 204 artık geçerli boş akış; mevcut SIGMET'ler erken sonlandırılmaz.
- ✅ Kurul incelemesi hızlı kazanımları (rapor depo dışında): rota seçim kuralı belgelerde kodla aynı; kapı kuralı/test sayısı/TI1 ölçeği docstring'i/"güvenli" ifadeleri düzeltildi; Ri < 0,25 sayacına çözünürlük notu.
- ✅ Uyarı oranı ölçümü (`turbulans-uyari-orani`, `docs/sonuclar/2026-10-28_uyari_orani/`): 1.488 rotanın %46,3'ünde sapma, ek yakıt medyanı %2,2 (p90 %8,8). 1.153 test, 1.141 geçti.
- ⚠️ Gece işi kullanıcı yeni emir verene kadar durduruldu (mobil kota): `.env` `ML_GECE_ISI_SAATI=` boş; bugünkü iş 44,8 MB'ta kesildi, veri korundu.
- ✅ "TurbulansRadar AIRAC yenileme" görevi artık `conhost --headless` ile gizli çalışıyor (siyah pencere yok); deneme sonucu 0.

## 2026-10-27

- ✅ Hızlı tarama (`docs/denetim/2026-10-27/TARAMA.md`): ruff/mypy/pip-audit temiz, 1.066 test; küp kataloğu testleri %48→%86, `pr_hazir_mi.sh`, 2 küçük düzeltme.
- ✅ Gece işi 494,7 MB; aday aktif RF'yi geçemedi (+0,006). Dependabot: #129 postgres, #130 prometheus 3.15.1 (promtool geçti), CI özeti #134; #128 gereksiz.
- ✅ §10 tek seferlik (79 gün / 7.769 örnek): H1 geniş − temel +0,008 [+0,002; +0,014]; komşu günsüz anlamlı değil. TI1 kapısı iki sette geçti.
- ✅ §10 yedeği `db_yedekleri/kalici/turbulans_20261027_yeni_gun.dump`; paket `docs/sonuclar/2026-10-27_yeni_gun/`, SONUCLAR §2.5.
- ✅ Yığın yeni imajlarla (commit `e73fdd8`), derin sağlık tamam; `ats_agi` "bitiyor" (AIRAC 29–30 Ekim, beklenen).
- ✅ Hafta 5 raporu 17–29 Ekim (#136; Hafta 4 16 Ekim'de bittiği için), son hafta PDF tek sayfa, masaüstünde.
- ✅ Sunum paketi 477 MB, OneDrive'da SHA256 OK; betikte `compose wait` çıkmış demo konteynerini görmüyordu → `docker wait`.

## 2026-10-26

- ✅ Gece işi 21–26 Ekim 6/6 tamamlandı (346–397 MB/gün); aday aktif RF'yi geçemedi. §10: 70 yeni gün, yeterli.
- ✅ CI e-posta gürültüsü: CI yalnız master push + PR'da (çift çalışma yok); pip-audit ayrı haftalık iş akışında.
- ✅ CI güvenlik kırmızıydı: pillow 13.0.0 (37 açık; streamlit 1.66.1 gerekti), gitpython, certifi, otel; 1.143 test geçti.
- ✅ YAPILACAKLAR'a önem sırası bölümü eklendi; 25 Ekim sunum paketi ve 23 Ekim haftalık rapor gecikti.

## 2026-10-20

- ✅ Denetimden kalan 3 iş YAPILACAKLAR'a yazıldı (rota akış fonksiyonunu bölme 5 Kasım sonrası, mypy genişletme, CLI testleri).
- ✅ Denetim onayları: mypy (api/depo/fizik), görev hata metni, toplu webhook 422, Streamlit kilidi, load_dotenv (#125); rota modülü 6 dosyaya bölündü, çıktı aynı (#126).
- ✅ Uçtan uca denetim (`docs/denetim/2026-10-20/DENETIM.md`): 1.132 test, %85,8 kapsam, 0 açık; webhook URL log maskesi + boş sayısal ortam değişkeni düzeltildi; 3 madde onay bekliyor.
- ✅ S-9 kararı: önbellekteki rota hız sınırına sayılmıyor; P1-6 ağa açıkken anahtarsız sağlık yalnız durum.
- ✅ S-3 senaryo seçici; S-4 kısmen (ÖNERİ YOK, kapsam dışı); P1-10 işletim kılavuzu; tatbikat GEÇTİ (4 sn).
- ✅ P1-3 Prometheus izleme profili + 5 alarm (promtool geçti); ayrı izleme anahtarı `.env`'de.
- ⚠️ Fikir 11: avwx ile 499/500 uyuşma; IEM ikinci /TB grubunu atıyor, seyir raporlarının %0,24'ünde etiket döner (dondurulmuş veri değişmedi).
- ✅ B-3: 7 seviyeli küp (57,6 MB); 3 seviyeyle Spearman 0,81, eşdeğer eşik 6,5e-7, FL340–360'ta 3 seviye riski %26–32 az.
- ✅ Gece işi: 493 MB, 188 gün; aday aktifi geçemedi (+0,002). Worker tepe 687 MiB → sınır 2g. §10: 25/30 gün.
- ✅ Yığın yeni imajlarla (postgres/python yamaları), Prometheus açık (hedef UP, 5 alarm inaktif).

## 2026-10-19 (gece; anlık kontrol, `docs/denetim/2026-10-19/ANLIK_KONTROL.md`)

- ✅ YAPILACAKLAR "Ertelenenler": rota sınırı kararı, S-3, S-4, P1-3, P1-6, P1-10, worker sınırı (#113).
- ⚠️ Dependabot ilk çalışmada büyük sürüm PR'ları açtı (postgres 18, python 3.14); kapatıldı, ayar düzeltildi (#113).
- ✅ Güvenlik yamalı imaj özetleri birleşti (#114 postgres 16, #115 python 3.12-slim).
- ⚠️ Yığının yeni imajlarla derlenmesi uzun sürdüğü için yarıda bırakıldı, PR #116 CI bekliyor; ikisi YAPILACAKLAR'da (#117).

- ✅ H-1: CI güvenlik kırmızıydı, aiohttp 3.14.3 → 3.14.5 (3 açık); H-2/H-3 belge ve test temizliği.
- ✅ P1-4 SHA/digest sabitleme + Dependabot; S-2 sonuçta commit; P1-8/S-5 `ALTLIK_KATMANI`.
- ✅ P1-7 WS bileti DB'de; P1-2 migration öncesi yedek + `migrate` servisi; P1-1 ölçüme dayalı sınırlar.
- ⚠️ S-9: tek IP'den 10 istemcide rota %40 429, önbellek isabeti de sınıra takılıyor (karar bekliyor).
- ⚠️ S-8 betiği yazıldı, ilk gerçek çalıştırma 25 Ekim.

## 2026-10-19 (akşam; komite açık maddeleri)

- ⚠️ B-3: 7 seviyeli Türkiye küpü betiği hazır (kuru deneme: 31 istek, ≤130 MB); bütçe dolu (461,8/500), indirme 20 Ekim.
- ✅ T-1: dondurma yedeği talep üzerine; sha256 ve yeniden üretim adımları `docs/sonuclar/README.md`.
- ✅ C-10: `test_sayi_tutarliligi.py`, ön paket sayısı tarihçe dışında geçerse CI kırmızı.
- ✅ T-4: deformasyon/diverjans MetPy ile gerçek ERA5'te aynı (~1e-6); `metpy` dev bağımlılığı.
- ✅ T-2: kapsam alt sınırı `fail_under = 80`.
- ✅ Y-1: beyan 308 commit / 41.808 satır / 1.099 test; `scripts/beyan_sayimlari.py --kontrol`.
- ✅ O-3: AIRAC otomatik yenileme (`cli/airac_yenile.py`), Windows görevi 12:00 kaydedildi, ilk çalışma "güncel".

## 2026-10-19 (öğleden sonra; PR #99–#102)

- ✅ Rota performansı (şarjda): kütle bandı yavaşlatmıştı (0,25–0,69 sn); yinelenen OpenAP hesabı kaldırıldı, sonuç aynı, 0,10–0,42 sn.
- ✅ `deney_protokolu.md` §10: yeni günlerde geniş özellik seti, Fikir 4/8 önceden kayıtlı; 163 dondurma günü `ml/dondurma_gunleri.json`.
- ✅ P1-5 `.dockerignore`, P1-1 log rotasyonu, P1-6 sunucu başlığı, P1-9 AIRAC 7 gün uyarısı, Y-2 `docker-compose.uretim.yml`, S-7 etiketi.
- ✅ Komite C-3, C-5, C-8 belge düzeltmeleri; durum KOMITE_INCELEMESI "19 Ekim durumu".
- ✅ Yığın yeni imajla yeniden başlatıldı (log sınırı etkin, `server` başlığı yok); AWC `airsigmet` boş akış (204), dış kaynak.
- ✅ §10 kodu `turbulans-ml-yeni-gun` (sentetik testli); `--durum`: 16 yeni gün / 1.509 örnek, eşik 30, skor hesaplanmadı.
- ✅ Demo ekranları temiz klondan yenilendi (sayılar aynı); ekran aracı CSP'ye takılıyordu, `page.evaluate` yoklamasıyla düzeltildi.

## 2026-10-19

- ✅ 18 Ekim CI hata e-postaları: 21 kırmızı çalışmanın hepsi gitleaks yanlış pozitifi (#95 ile çözüldü), gerçek sır yok.
- ✅ Birleşmiş 95 uzak `claude/*` dalı silindi; açık PR yoktu.
- ✅ npm döndü, `docker compose build api worker` başarılı; api yeni imajda, iki harita sayfası 200 ve CSP başlığı var.
- ✅ Gece işi bitti (~500 MB, eğitim: aday aktifi geçemedi, +0,001); ardından worker yeni imajla başlatıldı, sağlıklı.

## 2026-10-18 (kapanış; PR #97)

- ✅ Kalan ve yarım işler YAPILACAKLAR "18 Ekim gecesinden kalanlar" bölümünde (imaj derlemesi öncelikli).
- ✅ Yerel tam test 1.078/1.078, ruff ve gitleaks temiz; CI #95 tüm işler yeşil.

## 2026-10-18 (Madde 10 adım 6; PR #95–#96)

- ✅ CI güvenlik işi kırmızıydı: testteki sahte anahtar gitleaks yanlış pozitifi (#95), gerçek sır yok.
- ✅ README paket ağacı kodla iki yönlü eşleşiyor; SISTEM_KARTI test sayısı CI'dan (1.066, kapsam %84,5).

## 2026-10-18 (P0 devamı; PR #91–#94)

- ✅ P0-4/P0-3 CSP + güvenlik başlıkları (#91), tarayıcı 8/8; P0-1 Caddy TLS vekili (#92); P0-9 `*_FILE` (#93).
- ✅ GFS eşiği 8,3e-7 `.env`'de, API/işçi yeniden başlatıldı; Y-4, Y-5 (#94). Durum tablosu URETIM_HAZIRLIK başında.
- ⚠️ npm erişilemiyor: imaj derlemesi Cesium indirmesinde takıldı, durduruldu; CSP canlı imajda yok.

## 2026-10-18 (tam yetkiyle P0 listesi; PR #88–#90)

- ✅ P0-8: haftalık geri yükleme tatbikatı (3 sn, 16 tablo aynı), RPO 24 sa / RTO 15 dk; dondurma yedeği `kalici/`.
- ✅ P0-2 + Y-1: ağa açılışta zayıf anahtar/şifre, süper kullanıcı, örnek saha, kapalı bütünlükle başlamaz.
- ✅ P0-5 + Y-3: dump'lar API/işçide yok; sağlık raporu `yedek_durumu.json`'dan.
- ⚠️ Yedekten yeniden üretimde model seçimi değişti (RF/GB berabere, sorgu sırasız) → ORDER BY id (PR #89).
- ✅ Nihai paket deterministik: yedekten = canlıdan; RF 0,708, +0,033 [+0,018; +0,049]. İlk üretim `ilk_uretim_sirasiz/`.

## 2026-10-18 (dal `claude/dondurma-2026-10-18`, `claude/nihai-paket-belgeler`)

- ✅ C-9 düzeltildi (PR #86): kalibre TI1 ikili metrikleri doğru eşikle.
- ✅ Nihai paket `docs/sonuclar/2026-10-18/` (commit 45caf3c): GB 0,710, TI1 0,675, fark +0,036 → kapı geçildi.
- ✅ Dondurma raporu: aday aktif 9 Ekim RF'yi geçemedi (+0,003), saklandı; aktif model değişmedi.
- ✅ 1-SE eşiği 7,39e-7; 7e-7 bandın içinde, config değişmedi. Belgelerdeki ön paket sayıları değiştirildi.
- ⚠️ Rota performansı ölçülmedi (pilde); GFS eşiğini `.env`'ye yazmak onay bekliyor.
- ⚠️ Önceki satırdaki "gece işi yok" yanlıştı: UTC'de hâlâ 17 Ekim'di, gece işi 12:15 UTC'de çalışmıştı.

## 2026-10-18 (dal `claude/mcp-kapali-baslama`)

- ✅ P0-6 P0'da tutuldu: MCP ayarı boş/yetkili rolse sunucu başlamaz, sistem fonksiyonları reddedilir.
- ✅ MCP testleri 24/24, canlı salt okunur rol denetimi geçti.
- ⚠️ Gece işi: 18 Eki ml_veri görevi yok; dondurma günü olduğu için başlatma onaya bırakıldı.

## 2026-10-17 (dal `claude/komite-incelemesi`)

- ✅ Komite incelemesi `docs/denetim/2026-10-17/KOMITE_INCELEMESI.md`: 39 bulgu, jüri soruları ve cevaplar.
- ⚠️ Belgeler "ML devrede değil" diyor, canlıda 9 Eki RF aktif (C-1/C-2); kalibre_ti1 eşik hatası (C-9).
- ✅ Rehber Ders 1 backtest sayısı paketle eşitlendi (0,24 / 0,39 / 0,02).

## 2026-10-17 (dal `claude/ogrenme-rehberi`)

- ✅ Gece işi kontrolü: ml_veri tamamlandı; aday aktif modeli geçemedi (+0,003), yalnız sürüm.
- ✅ 8 derslik öğrenme rehberi `docs/ogrenme/PROJE_REHBERI.md` (kod değişikliği yok).
- ✅ Ders testleri 214/214, tarayıcı 8/8 görünür modda (geçici port, -test DB); yığın durdurulmadı.

## 2026-10-17 (dal `claude/hiz-siniri-test-kararliligi`)

- ✅ PR #76 CI test (3.12) hatası kod değil zamanlama: 429 testi dakika sınırına denk geldi; 4 test sınırdan uzaklaşıyor.

## 2026-10-17 (dal `claude/uretim-faz0`)

- ✅ Faz 0 üretim denetimi: 988 test, ruff temiz; 28 bulgu: 21 doğru, 7 kısmen, 7 yeni (`docs/denetim/2026-10-17/`).
- ⚠️ Ağa açılış için P0: kapalı başlama, CDN/CSP, yedek ayrımı, TLS vekili; Faz 1 onay bekliyor.

## 2026-10-17 (dal `claude/kacinma-baslangici`)

- ✅ Fikir 12: KAYNAK_INCELEMESI OpenSky yanıtıyla güncellendi (PR #77).
- ✅ Fikir 18: 15 vaka, 9,5 MB; riskli süre kaçınmasız 46,1 → R0 26,7 → R1 14,8 dk, süre maliyeti ~0.
- ⚠️ Fikir 18 referansı gözlem değil daha yeni GFS; R1 lehine yanlı olabilir (`docs/sonuclar/2026-10-17/`).

## 2026-10-17 (dal `claude/onbellek-hata-duzeltmeleri`)

- ✅ Proje taraması: 1019 test, ruff, CI, servisler, yedek temiz; gece işi bitti (aday aktifi geçemedi).
- ✅ Rota önbelleği geçici topluluk/kalkış penceresi hatalarını artık saklamıyor.
- ✅ Yanıtta ham hata metni yerine yalnız tür adı; uyarı dinleyicisi hatada bağlantıyı kapatıyor.
- ✅ Birleşmiş eski yerel dallar silindi. Docker önbellek temizliği yapılmadı (onay yok).

## 2026-10-17 (dal `claude/opensky-yaniti`)

- ✅ OpenSky yanıtı: bulut IP engeli Trino'yu da kapsıyor, Hetzner garantisiz; B planında OpenSky dizüstünde.
- ✅ Gece işi bugün çalışıyor (ml_veri, 12:15 UTC).

## 2026-10-16 gece (dal `claude/yapilacaklar-opensky`)

- ✅ OpenSky e-postası kullanıcı tarafından gönderildi; yanıt bekleniyor (YAPILACAKLAR).

## 2026-10-16 gece (dal `claude/demo-ekranlari-16-ekim`)

- ✅ Demo ekranları temiz klondan (5532/8100) yenilendi; sayılar aynı. Postman koleksiyonu yeni uçlarla güncellendi.
- ✅ OpenSky taslağına alıcı (contact@opensky-network.org) eklendi; gönderim sizde.

## 2026-10-16 gece (dal `claude/iz-bulutu-sac`)

- ✅ Fikir 30: M9 eşiği sabit −40 °C yerine Schmidt–Appleman T_LC(p) (250 hPa'da −46,9 °C) + ±2000 ft iz bulutu bilgisi.
- ⚠️ Fikir 26 ve 27 bilinçli olarak yapılmadı (gerekçe KAYNAK_INCELEMESI'nde).

## 2026-10-16 gece (dal `claude/cat-egilim-baglami`)

- ✅ Fikir 25: ILGILI_CALISMALAR §1'e bölgesel CAT eğilimleri (Foudad 2024, Soliva Fabrega 2025, Zhang 2025).

## 2026-10-16 gece (dal `claude/fizibilite-18-20-23`)

- ✅ Fizibilite: 18 yapılabilir (THREDDS ~8 gün); 20 mevcut günlerle 0 örtüşme (G-AIRMET 2021+); 23 Trino tablosu var, deneme gerekli.

## 2026-10-16 gece (dal `claude/dikey-kesit`)

- ✅ Fikir 17: önerilen rota boyunca FL280–400 TI1 dikey kesiti (API + web ısı şeridi), ek ~10 ms.

## 2026-10-16 gece (dal `claude/kalkis-penceresi`)

- ✅ Fikir 16: isteğe bağlı kalkış ±2 sa penceresi (yalnız bilgi), web brifing kartında tablo.

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
