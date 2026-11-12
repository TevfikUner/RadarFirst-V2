# Yapılacaklar

Açık işlerin tek listesi. **Biten madde silinir** (12 Kasım 2026, kullanıcı kararı); ne yapıldığı
`docs/ISLEM_GUNLUGU.md`'de ve git geçmişinde kalır. Yeni ertelenen iş buraya eklenir. Süreler kabadır.

## 1. Kullanıcının yapacakları

1. **İki kopya veritabanını silmek** (12 Kasım'da onaylandı; Claude'un `dropdb`'si izin denetiminde reddediliyor).
   WSL'de, depo klasöründe:
   `docker compose exec -T db sh -c 'dropdb -U $POSTGRES_USER Turbulence-db-dondurma && dropdb -U $POSTGRES_USER Turbulence-db-tatbikat'`
   Geri alınamaz; asıl veritabanı etkilenmez. Dondurma kopyası gerekirse `db_yedekleri/kalici/turbulans_20261018_dondurma.dump`
   dosyasından yeniden kurulur. (~5 dk)
2. **Savunma hazırlığı** (`docs/sunum/SAVUNMA_HAZIRLIGI.md`): 4 çekirdeğin sayfalarını elle çizmek, "kendi kararlarım"
   tablosuna gerekçe, 2 notsuz prova; danışmana YZ beyanı e-postası (taslak aynı dosyada). (6–8 sa)
3. **Bitirme raporunu okuyup onaylamak** (`docs/rapor/BITIRME_RAPORU.md` + `.pdf`, 29 sayfa). Üniversite şablonu ya da
   kapak gerekiyorsa Claude'a söylenir. (4–6 sa)
4. **Katkı cümlesi ve konumlandırma** (`docs/sunum/SUNUM_AKISI.md` §3 ve §8): taslağı onaylamak, slayta aktarmak. (0,5 sa)
5. **E7 kullanılabilirlik oturumları:** önce danışmandan etik onay, sonra 3–5 katılımcı (pilot/dispeçer/ATC öğrencisi;
   ESTÜ'den istenebilir). Paket `docs/kullanilabilirlik/OTURUM_PAKETI.md`; formları kullanıcı getirir, SUS/tabloyu Claude
   hesaplar. (4 sa + organizasyon)
6. **Dış başvurular:** MGM ve IATA Turbulence Aware (Avrupa/Türkiye nesnel etiket kaynağı, bkz.
   `docs/fizibilite/TURKIYE_ETIKET_KAYNAKLARI.md`); TUSAŞ, Boeing, Airbus, DLR, NASA e-posta taslakları masaüstünde
   (depo dışı). Danışman onayından sonra gönderilir. (1–2 sa)
7. **Kotasız internet olunca Claude'a haber vermek:** Docker derleme önbelleği 12 Kasım'da silindi (37,8 GB); sonraki
   derleme Python bağımlılıklarını ve CesiumJS'i baştan indirir (yüzlerce MB). Aşağıdaki 2.2 o zaman yapılır.
8. Her Perşembe 23:55 haftalık ilerleme raporu (danışman Fatih TİTREK).
9. İsteğe bağlı: Trino girişi için `keyring` + `keyrings.alt` (WSL venv); yeni OpenSky sorgusu gerekince sorulur.

## 2. Yarım kalanlar ve tarihli işler (Claude)

1. **~17 Kasım: #11 devamı + ATM-05** (ONAY 28 Ekim, yeni pencere 12 Kasım). 28 Ekim–4 Kasım GFS koşuları UCAR'dan
   silindi (kalıcı boşluk); 5–12 Kasım indirildi (`ciktilar/tahmin_ufku/`, 35 dosya). Eksik tek koşu 12 Kas 12Z,
   **~19 Kasım'a kadar** indirilebilir: `turbulans-tahmin-ufku --indir --baslangic 2026-11-12T12 --bitis 2026-11-12T12`.
   ERA5 12 Kasım'ı yayınlayınca (~17 Kasım) iki aralık birlikte:
   `CDSAPI_RC=<CDSAPI_RC_DOSYASI> turbulans-tahmin-ufku --era5 --baslangic 2026-10-23T00 --bitis 2026-11-12T12
   --cikti docs/sonuclar/<tarih>_tahmin_ufku` (araç üç ufku birlikte bulamadığı zamanları "eksik" sayar; ~11 gün).
   ERA5 → GFS eşik eşlemesi ~10 günle yeniden; eşik `TI1_ESIK_ORTA_SIDDETLI_GFS`'ten farklı çıkarsa `.env` değişikliği ONAY. (2–3 sa)
2. **Kotasız internette (1.7):** `docker compose build api worker migrate` ve `up -d --wait`; aynı derlemede kurul #25 /
   MİM-08 yerel Swagger (statik katman değişince CesiumJS zaten yeniden iner). (1–2 sa)
3. **Rapor tesliminden hemen önce:** `python scripts/beyan_sayimlari.py --kontrol`; farklıysa
   `docs/rapor/ARAC_KULLANIMI_BEYANI.md` paragrafı güncel sayılarla yenilenir. (0,5 sa)
4. **Türk TURB SIGMET'leri biriktikçe** (12 Kasım'da 6, kullanılabilen 4): ~15 kullanılabilir SIGMET olunca
   `turbulans-sigmet-alan` yeni bir klasörle bir kez daha (protokol §14). (0,5 sa)

## 3. Proje iyileştirme (önem sırasıyla)

1. **Demo: ABD vakası + ML modeli** (OPS-05) ve iki seçim kuralının (`sozluksel` / `maliyet`, A1) yan yana gösterimi;
   Docker'lı uçtan uca doğrulama gerekir. (6–8 sa)
2. **A2 / VER-09:** birleşik EDR ya da ML'in rota cezasına girmesi (eşik seçimi ve GFS doğrulaması önce); Fikir 10'un
   `fizik/eslestirme.py`'ye mod olarak girmesi ve eşiğin yeniden seçilmesi (ONAY). (6–10 sa)
3. **ATM-06:** GTG referans AUC'si ve NCSU1, yalnız Sharman vd. (2006) tam metni bulunursa.
4. Düşük öncelik: `gorev_olc` CLI'ına test (DB kuyruğu gerektiriyor).

## 4. Araştırma (önce `docs/deney_protokolu.md`'ye yazılarak; çoğu yeni veri ya da ONAY ister)

1. Faz 2: tırmanma/alçalma için ayrı model (400–850 hPa, CAPE, arazi; FL100–FL280 PIREP'leri konvektif / dağ dalgası /
   rüzgâr kesmesi diye ayrı etiket; Lee ve Chun 2025). Seyir modeline karıştırılmaz. (20–30 sa)
2. İndekslerin `rojak` (Imperial College) ile aynı ERA5 üzerinde kıyası. (6–8 sa)
3. GFS topluluk oranının doğrulanması (Fikir 3 devamı): günlük GFS koşu dilimi biriktirmek veri bütçesine girer (ONAY).
4. Fikir 18 devamı (MADIS/PIREP günlerinde R0/R1 deneyi), Fikir 20 (IEM G-AIRMET kıyası), Fikir 23 (tek uçuşluk
   `rollcall_replies_data4` sorgusu, OpenSky girişi kullanıcıda), Fikir 29 (OpenAP ile kanat yükü; kazanç küçük).
5. F7 rüzgâr asimilasyonu küçük deneyi (5–10 gün; `docs/fizibilite/RUZGAR_ASIMILASYONU.md`; veri bütçesi ONAY).
6. Daha fazla OpenSky uçuşu (önce kota hesabı, ONAY); F5 backtest yakıtı için kalıcı sütun (migration, önce `-test` DB).
7. Gece işinin yeniden açılması (28 Ekim'den beri kapalı; yalnız kullanıcı emriyle, `ML_GECE_ISI_SAATI`).

## 5. Koşullu

1. Kurul #30: GTG/WAFS kıyası (veri erişimi gerekir).
2. P0-7 hibrit topoloji ADR'si (yalnız B planına, sanal sunucuya geçilirse; koddan önce ONAY).
3. Eski commit mesajlarındaki YZ imzalarının temizliği (force-push gerektirir; önerilen: yapılmaması).
