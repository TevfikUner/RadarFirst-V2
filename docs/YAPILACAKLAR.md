# Yapılacaklar (ileri tarihli işler)

İleri bir tarihe ertelenen tüm işler burada tek listede tutulur. Biten madde silinmez,
`[x]` ile işaretlenir ve yanına PR/tarih yazılır. Yeni ertelenen iş buraya eklenir.

## 18 Ekim 2026 — ML veri dondurma

- [ ] Nihai sonuç paketi (şarjdayken):
  `turbulans-ml-degerlendirme --kesme 2026-10-18 --cikti docs/sonuclar/2026-10-18`,
  `turbulans-performans rota --json docs/sonuclar/2026-10-18/rota_performansi.json`,
  `turbulans-ml --dondurma-raporu docs/sonuclar/2026-10-18`. Sonuç ne çıkarsa raporlanır.
- [ ] Ön paket (2026-10-07) sayılarını nihai `SAYILAR.md` ile değiştir: SISTEM_KARTI,
  SONUCLAR §0, KATKILAR, SUNUM_AKISI §8, poster, DEMO_SENARYOSU, ILGILI_CALISMALAR,
  `TI1_GUVENILIRLIK_NOTU`, README "Kısa cevap", PROJE_ISLEYISI; `docs/sonuclar/README.md`
  tablosu; ARAC_KULLANIMI_BEYANI commit/satır sayımları güncel git'e göre.
- [ ] `esik_taramasi.bir_se.esik` 7e-7'den belirgin farklıysa `TI1_ESIK_ORTA_SIDDETLI`'yi
  güncelle; eşiğe bağlı testler, demo senaryosu ve ekranlar yeniden kontrol edilir.
- [ ] GFS eşiği: nihai ERA5 eşiğiyle `turbulans-esik-esleme --baslangic 2026-10-09T00:00Z
  --bitis 2026-10-11T18:00Z --esik <yeni> --cikti docs/sonuclar/2026-10-18` (veri önbellekte,
  indirme yok). 16 Ekim ölçümü: 7e-7 ↔ GFS 8,30e-7 [7,96; 8,67]e-7. Sonucu
  `TI1_ESIK_ORTA_SIDDETLI_GFS`'e (`.env`) yaz, API/worker'ı yeniden başlat; demo ekranları GFS
  kullanıyorsa yeniden kontrol et. Örneklemi büyütmek için `--bitis 2026-10-13T18:00Z`
  (12–13 Ekim için ~2 MB GFS + ~5 MB ERA5 ek indirme; THREDDS koşuları ~8 gün durur).
- [ ] MADIS önsel kayma gösterimi (`model_olasilik_onsel_duzeltilmis`) pakette çıkınca
  SONUCLAR §0.4'e tek satır not.
- [ ] SUNUM_AKISI §10 (F1 doğrulama karnesi) ve poster "Sonraki" satırını nihai pakete bağla.

## 18 Ekim sonrası (paket çıktıktan sonra)

- [ ] Madde 10 adım 6: SISTEM_KARTI §5/§6 ve README mimari/paket ağacının kodla çelişki
  denetimi; test sayısı CI'dan alınır.
- [ ] Yeni ML protokolü (F9 devamı): `docs/deney_protokolu.md`'ye geniş özellik setini
  (temel 8 + 5 bağlam) ve aday modelleri önceden yaz. Değerlendirme dondurmadan SONRA
  toplanan yeni günlerde yapılır; aynı 16 altın gün kullanılmaz (bkz. SONUCLAR §2.4).
- [ ] Türkiye ERA5 (7 seviye) ve daha fazla OpenSky uçuşu: önce CDS/OpenSky kotası ve
  günlük 500 MB bütçe hesabı, sonra ONAY.
- [ ] F7 rüzgâr asimilasyonu küçük deneyi (5–10 gün, 2021 sonrası MADIS günleri + AWS GFS;
  bkz. `docs/fizibilite/RUZGAR_ASIMILASYONU.md`): gece veri bütçesine eklenmeden ONAY.
- [ ] İsteğe bağlı: F5 backtest yakıtı için kalıcı veritabanı sütunu (migration; önce
  `-test` DB'de upgrade/downgrade, geliştirme DB'si için ONAY). Şu an yalnız yanıtta.

- [ ] **GFS topluluk oranının doğrulanması (Fikir 3 devamı):** THREDDS koşuları ~8 gün
  durduğu için geçmiş günlerde değerlendirme ancak veri biriktirilerek yapılabilir. Gece
  işine günlük GFS koşu dilimi eklemek veri bütçesine girer (ONAY). Ölçüt: MADIS EDR / PIREP
  günlerinde güvenilirlik diyagramı ve Brier skoru; rota kararına alınması ayrı karar.

### Kaynak incelemesinden (16 Ekim, `docs/arastirma/KAYNAK_INCELEMESI.md` §3)

Kural: her biri ÖNCE `docs/deney_protokolu.md`'ye (hipotez, metrik, karar ölçütü) yazılır,
SONRA dondurmadan sonra toplanan yeni günlerde çalıştırılır; aynı 16 altın gün yeniden
kullanılmaz. Böylece sonuç görüldükten sonra seçim (p-hacking) olmaz. Öncelik sırası
jüri sorularına doğrudan yanıt verenler önde.

- [ ] **Fikir 4 — Tabakalı doğrulama:** mevsim, 250 hPa rüzgâr sınıfı (<30 / ≥30 m/s),
  backtest için uçuş yönü; tabaka başına n, ROC-AUC, bootstrap GA. `ml/degerlendirme.py`.
- [ ] **Fikir 8 — "Hafif = negatif" duyarlılığı:** hafif raporlar negatiften çıkarılır,
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

- [ ] **25 Ekim:** sunum için Docker imajı yedeği (`docker save`).
- [ ] **29 Ekim (AIRAC bitişi, ATS ağı `airac_bitis=2026-10-29`):** ONAY ile
  `turbulans-aip-ats --indir` ve `turbulans-aip-sahalar --indir` (DHMİ'ye belge başına tek
  istek); `/saglik` `ats_agi` yeniden "tamam" olmalı.
- [ ] **5 Kasım:** E8 yedek demo videosu (3–5 dk, metin `docs/sunum/DEMO_SENARYOSU.md` §4;
  ekranlar temiz klondan).
- [ ] Sunum konuşulmaya başlanınca: E7 kullanılabilirlik oturumları (katılımcı bulmak zaman alır).

## Kullanıcı kararı bekleyenler

- [ ] OpenSky'a bulut IP / Trino sorusu (B planından önce; taslak `docs/fizibilite/OPENSKY_BULUT_ERISIMI.md`,
  gönderim kullanıcıda).
- [ ] Avrupa/Türkiye nesnel etiket kaynağı için MGM'ye ve IATA Turbulence Aware'a başvuru
  (dış iletişim; bkz. `docs/fizibilite/TURKIYE_ETIKET_KAYNAKLARI.md`).
- [ ] Eski commit mesajlarındaki yapay zekâ imzalarının temizliği (force-push gerektirir;
  önerilen: yapılmaması).
