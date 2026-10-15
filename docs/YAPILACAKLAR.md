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

## Tarihli hatırlatmalar

- [ ] **25 Ekim:** sunum için Docker imajı yedeği (`docker save`).
- [ ] **29 Ekim (AIRAC bitişi, ATS ağı `airac_bitis=2026-10-29`):** ONAY ile
  `turbulans-aip-ats --indir` ve `turbulans-aip-sahalar --indir` (DHMİ'ye belge başına tek
  istek); `/saglik` `ats_agi` yeniden "tamam" olmalı.
- [ ] **5 Kasım:** E8 yedek demo videosu (3–5 dk, metin `docs/sunum/DEMO_SENARYOSU.md` §4;
  ekranlar temiz klondan).
- [ ] Sunum konuşulmaya başlanınca: E7 kullanılabilirlik oturumları (katılımcı bulmak zaman alır).

## Kullanıcı kararı bekleyenler

- [ ] Avrupa/Türkiye nesnel etiket kaynağı için MGM'ye ve IATA Turbulence Aware'a başvuru
  (dış iletişim; bkz. `docs/fizibilite/TURKIYE_ETIKET_KAYNAKLARI.md`).
- [ ] Eski commit mesajlarındaki yapay zekâ imzalarının temizliği (force-push gerektirir;
  önerilen: yapılmaması).
