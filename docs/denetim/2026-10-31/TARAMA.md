# Proje taraması — 31 Ekim 2026

Master `58f58df` (PR #155 sonrası). Salt okuma taraması: depo ve CI, çalışan yığın, testler ve kapsam,
bağımlılık ve sır taraması, belge–kod tutarlılığı, tarihli işler, kurul raporu (28 Ekim) açık maddeleri.

## 1. Sağlam olanlar (kanıtla)

| Alan | Durum |
|---|---|
| CI (master) | Son 5 birleştirme yeşil; PR #155'te 7/7 kontrol geçti |
| Testler | 1.242 test; yerelde (ağ/tarayıcı hariç) 1.229 geçti, 0 hata |
| Kapsam | %84,6 (14.473 satırın 2.223'ü kapsanmıyor; 28 Ekim %86,3, düşüş yeni araştırma CLI'larından) |
| Lint / tip | ruff temiz; mypy 142 dosya temiz |
| Bağımlılık | `pip-audit -r requirements.lock`: bilinen açık yok; haftalık tarama iş akışı tanımlı (Pazartesi 06:00) |
| Sır taraması | Kodda sabit sır yok; `.env`, anahtar dosyası izlenmiyor; TODO/FIXME yok |
| Eski sır izi (kurul #21, MİM-06) | **Kapandı:** GitHub'da şifreli commit artık 422 "No commit found", PR #1 404 |
| Yığın | db, api, worker sağlıklı; `/saglik?derin=true` tüm bileşenler "tamam", gece işi "kapalı" (bilinçli) |
| Yedek | Günlük dump 31 Ekim 05:07; OneDrive'da `.gpg` kopyası 31 Ekim |
| AIRAC | 11/26 geçerli (bitiş 26 Kasım); günlük görev 30 Ekim "guncel" |
| SIGMET birikimi | 13.410 kayıt; LTAA/LTBB 156 (5'i TURB), 30 Eylül'den beri |
| Disk | WSL %5, C: %23 dolu; Docker'da ~65 GB geri kazanılabilir (acil değil) |

## 2. Şu an yapılması gerekenler (öncelik sırası)

### A. Takvime bağlı (bu hafta)

1. **3 Kasım: #11 devamı GFS indirmesi (ONAY 28 Ekim, ~15 MB).** UCAR koşuları ~7,5 gün tutuyor; 28 Ekim 12Z
   koşusu 4–5 Kasım'da silinir, 3 Kasım kaçırılırsa aralık kısalır. ERA5 kıyas aracı `tahmin_ufku.py`'de **henüz
   yazılmadı**; ERA5 ~5 gün gecikmeli yayınlandığı için 3 Kasım'da yalnız ~29 Ekim'e kadarki zamanlar kıyaslanabilir.
   ATM-05 (eşik eşlemesi ~10 günle) aynı veriyle. Mobil kota: GFS + küçük CDS kutusu.
2. **5 Kasım öncesi: demo ekranları ve sunum paketi eski.** `docs/sunum/ekranlar/` 19 Ekim, sunum paketi
   (`sunum_paketi_20261027`) commit `e73fdd8`; o tarihten bu yana arayüze giren S-3 seçici, S-4 arıza tatbikatı,
   OOD kapısı, model paneli (ROC-AUC), `katman_cevrelenmiyor` uyarısı ve Ri notu ekranlarda/pakette yok.
   Temiz klondan (5532/8100) ekranlar + `scripts/sunum_paketi.sh` yeniden; çalışan imaj zaten #153 sonrası
   derlendiği için CesiumJS önbellekte (derlemeden önce `docker builder prune` **yapılmamalı**).
3. **5 Kasım: E8 yedek video ve soğuk açılış provası** (kurul §8 #8). 2. madde bitmeden çekilmemeli.
4. **5 Kasım Perşembe 23:55: Hafta 6 ilerleme raporu.** Hafta aralığı kullanıcıya sorulacak (30 Ekim–5 Kasım
   önerisi). Ayrıca Hafta 5'in 29 Ekim e-posta gönderimi YAPILACAKLAR'da hâlâ açık: gönderildi mi?

### B. Kısa düzeltmeler (Claude, risksiz, belge)

**Durum:** 5–9 aynı gün yapıldı (kullanıcı onayı; ayrı PR). Hafta 5 e-postası doğrulanmadı.

5. **YAPILACAKLAR'da bitmiş ama açık görünenler:** Fikir 4 ve Fikir 8 (§10'da 27 Ekim'de yapıldı), "29–30 Ekim
   AIRAC kontrolü" ve "29 Ekim haftalık rapor" hatırlatmaları, GitHub Destek doğrulaması (madde 1).
6. **Test sayısı belgelerde eski:** SISTEM_KARTI §6 ve SUNUM_AKISI "1.182 test" (bugün 1.242). Kurul #2'nin
   "tek kaynak" önerisine uygun olarak tek yerde, CI özetine bağlı yazılmalı.
7. **Beyan sayımları güncel değil** (`scripts/beyan_sayimlari.py --kontrol`): commit 308 → 423, test 1.099 → 1.242,
   satır 41.808 → 47.829, işaretsiz 669 → 665. Kural "rapor tesliminden hemen önce"; danışmana beyan e-postası
   (K-1) gönderilmeden önce de güncellenmeli.
8. **SONUCLAR'da §13 yok:** 31 Ekim keşifsel sonuçları (Fikir 9, 10, 11, 15, 19, 24) `docs/rapor/SONUCLAR.md`'ye
   §2.10 olarak; Fikir 10 bulgusu (nokta eşleştirme konum/zaman hatası ayırma kaybettiriyor, +0,027) SINIRLAMALAR'a.
9. **ILGILI_CALISMALAR eksik (YAPILACAKLAR #31):** Zhu vd. 2026, He vd. 2026 ve iki derleme yok (Gökdeniz ve Ülkü
   var). Komite sunumunda (30 Ekim) anıldıkları için rapor belgesinde de olmalı.

### C. Kullanıcı kararı bekleyenler

10. **Masaüstündeki eski şifreli yedekler:** `Desktop/yedekler/RadarFirst-V2_2026-10-02b_*` ve 2026-10-01 bundle'ı
    hâlâ eski OpenSky şifresini içeriyor (şifre değişti). GitHub tarafı kapandığına göre silinmeleri önerilir;
    geri alınamaz.
11. **Herkese açık depoda `CLAUDE.md` ve `.claude/settings.json`** (kurul JRİ-01). YZ kullanımı beyanda açık;
    kaldırmak ya da bırakmak kullanıcı kararı. Kaldırılırsa geçmişte kalır (geçmiş yeniden yazılmaz).
12. **Gece işi kapalı (28 Ekim'den beri).** Yeni veri zorunlu değil; Fikir 18/20 ve GFS topluluk doğrulaması
    yeni veri ister. Kotasız internette düşük bütçeyle (CDS 10, MADIS kapalı, ~130 MB) açılabilir.
13. **Eski dallar:** uzakta 49, yerelde 57 `claude/*` dalı (çoğu birleşmiş). Temizlik düşük öncelik; uzak dal
    silmek paylaşılan durumu değiştirir.

### D. Komite hazırlığı (kurul §8; kullanıcı açınca)

14. **Bütünleşik bitirme raporu (#6) — en büyük eksik teslimat.** `docs/rapor/` yalnız bölüm taslakları
    (SONUCLAR, ILGILI_CALISMALAR, KATKILAR, SINIRLAMALAR); tek belge (Giriş, Literatür, Yöntem, Sonuç, Sınırlılık,
    Gelecek) yok.
15. **Savunma hazırlığı (#5) ve danışmana YZ beyanı e-postası (K-1):** 4 çekirdek akış sayfası, "kendi
    kararlarım" listesi, 2 prova.
16. **Demo: ABD vakası + ML modeli (#17)** ve iki seçim kuralının yan yana gösterimi (A1).
17. **Sunum: §10'u birincil kanıt yap (#14), katkı cümlesi (#15):** 30 Ekim komite sunumunda (18 slayt) altın gün
    sonucu (+0,033) var; §10'un 79 yeni günlük sonucu ve tek cümlelik katkı/konumlandırma slaytı **yok**.
18. **E7 kullanılabilirlik oturumları (#13):** katılımcı bulmak zaman alır.

### E. Sunum sonrası (bilinçli ertelenmiş)

19. MİM-02 (`rota_simulasyonu_olustur` ~460 satır bölme; `rota_optimizasyonu.py` 1.244, `api_servisi.py` 1.355 satır).
20. A2 / VER-09: birleşik EDR ya da ML'in rota cezasına girmesi. 31 Ekim bulgusuyla birleşik EDR, ızgara düzeyinde de
    TI1'den iyi (POD–alan +0,024); A2 için ilk aday o.
21. Fikir 10'un `eslestirme.py`'ye mod olarak girmesi + eşiğin yeniden seçilmesi (ONAY).
22. Türkiye TURB SIGMET ↔ TI1 kıyası (#29): 5 TURB SIGMET'in zamanında GFS arşivi yok (UCAR 7,5 gün); ERA5 küçük
    kutu gerekir (ONAY, birkaç MB).
23. Faz 2 tırmanma/alçalma modeli (#30), `rojak` kıyası (#31), Fikir 29, NCSU1 (Sharman 2006 bulunursa).
24. `Turbulence-db-dondurma` DROP ve `docker builder prune` (~65 GB): sunum paketi yeniden üretildikten sonra, ONAY.
25. #25 yerel Swagger (kotasız internet).

## 3. Kod kalitesi notları

- Kapsamı %60'ın altındaki modüller (hepsi araştırma/ölçüm CLI'ı, karar yolunda değil): `ekonomik_deger` %47,5,
  `performans_olcumu` %51, `birlesik_esik` %51, `gosterge_degerlendirme` %52,5, `sonuc_paketi` %54,8, `esik_esleme` %55,
  `uyari_alani` %56, `rf_deneyi` %58, `tip_analizi` %58, `birlesik_klimatoloji_duyarliligi` %58, `kesifsel_gostergeler` %60.
  Eksik kısım çoğunlukla `calistir`/`ana` (veritabanı ve dosya okuyan uçlar); YAPILACAKLAR'daki "araştırma CLI'larına test"
  maddesi düşük öncelikli kalabilir.
- En büyük dosyalar: `api_servisi.py` 1.355, `rota_optimizasyonu.py` 1.244, `api/semalar.py` 776, `config.py` 697 satır.
- Çalışan api/worker imajı `0bf061d` (#153); #154–#155 yalnız belge ve analiz CLI'ı, çalışma zamanını etkilemiyor.
- Aktif model 9 Ekim RF (7.759 örnek); veritabanında 243 eşleşmiş gün, 23.891 örnek. Yuvarlanan kapı (ADR 0014)
  gece işi kapalı olduğu için çalışmıyor.

Çıktılar sertifikalı EDR değildir; sistem operasyonel karar aracı değil, karar destek aracıdır.
