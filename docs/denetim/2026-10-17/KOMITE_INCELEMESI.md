# Komite incelemesi: zayıf yönler, eksikler ve olası jüri soruları

17 Ekim 2026 · depo `master` `7347dac` · kod değişikliği yok.

Okuyucu: proje sahibi (savunma hazırlığı). Bakış açısı: bitirme komitesi başkanı. Altyapı ve
güvenlik bulguları [`URETIM_HAZIRLIK.md`](URETIM_HAZIRLIK.md)'de (Faz 0, 28 + 7 bulgu) ayrıntılı
olduğu için burada yalnız özetlenir. Ağırlık bilimsel geçerlilikte ve belge–kod tutarlılığında.

**Yöntem.** Kod, sonuç paketleri (`docs/sonuclar/`), model deposu manifesti
(`model_deposu/model_versiyonlari/manifest.json`), canlı API (`GET /api/v1/ml/durum`,
`/turbulans/model-bilgisi`, salt okuma) ve belgeler karşılaştırıldı. Veritabanına yazılmadı,
geliştirme yığınına dokunulmadı, dış servise istek atılmadı.

**Önem:** **Kritik** savunmada sonucu tartışmalı hâle getirir · **Yüksek** büyük olasılıkla
sorulur, hazırlıksız cevap puan kaybettirir · **Orta** sorulabilir · **Düşük** düzeltilmesi kolay.
**⏳ dondurma:** 18 Ekim veri dondurmasından sonra değeri ya da durumu değişebilir.

**Düzeltilen iki ön varsayım.**
- "Aktif model eski fizikle seçildi" bilgisi **eskimiş**. Canlı sistemde aktif model 9 Ekim'de
  eğitilen, 8 özellikli (güncel fizik) Random Forest'tır. Altın test günlerinde TI1 kapısını
  +0,033 [+0,018; +0,048] ile geçip aktifleşmiştir (manifest, `ml/durum`). Belgelerin çoğu bunu
  hâlâ "model devrede değil" diye anlatıyor (bkz. C-1).
- İnceleme sırasında bir özet betiğinin listeleri kırpması yüzünden aktif modelde "6 özellik,
  boş güven aralığı" göründü. Manifest ve API ile kontrol edildi: ikisi de tamdır. Bu bulgu elendi.

---

## A. Bilimsel zayıflıklar

| No | Bulgu | Önem | Kanıt | Jüri sorusu | Önerilen kısa cevap |
|---|---|---|---|---|---|
| B-1 | TI1'in ayırt ediciliği orta: altın günlerde ROC-AUC 0,673 [0,639–0,704], 80 günde 0,680. 7e-7 eşiğinde POD 0,50, POFD 0,25. | Kritik ⏳ | `docs/sonuclar/2026-10-07/SAYILAR.md` | "Türbülansların yarısını kaçırıyorsunuz. Sistem neye yarıyor?" | "Evet, TI1 tek başına orta düzeyde. Bunu ölçtük ve ürüne yansıttık: güvenliği SIGMET duvarı sağlıyor, TI1 yalnız yumuşak ceza. Katkımız yüksek beceri değil, becerinin dürüstçe ölçülüp karar mantığına taşınması." |
| B-2 | Gerçek taban oranda yanlış alarm çok yüksek. PIREP pozitif oranı %52, MADIS'te hafif+ %3. POD 0,50 / POFD 0,25 ve %3 taban oranla kaba hesap: uyarıların ~%94'ü yanlış alarm olur. Bu bir **hesaptır**: MADIS etiketi "hafif ve üstü", PIREP etiketi "orta ve üstü"; yalnız büyüklük fikri verir. THY322 demosunda hesaplanan noktaların %49'u (351/720) kırmızı. | Kritik | `SONUCLAR.md` §0.4, §4; MADIS Brier becerisi −8,36 (`SAYILAR.md`); THY322 sayımı bu oturumda | "Haritada uçuşun yarısı kırmızı. Pilot buna nasıl güvensin?" | "Eşik, türbülansa doğru yanlı PIREP örnekleminde seçildi; gerçek sıklıkta çoğu uyarı yanlış alarm olur. Bu yüzden kırmızı 'kesin türbülans' değil, 'risk göstergesi'. Rota kararında ağırlığı sınırlı, olasılık mutlak sıklık olarak gösterilmiyor." |
| B-3 | Eğitim–kullanım uyuşmazlığı. Model ve 7e-7 eşiği 7 basınç seviyesiyle (25 hPa katman) hesaplanan özelliklerle seçildi. Türkiye ERA5 küpü (`ocak_2019_turbulans.nc`), demo küpü ve canlı GFS ise yalnız 3 seviye (300/250/200; 50 hPa katman). 5 Ekim karşılaştırması 3 seviyeli "eski fizikte" TI1 dağılımının belirgin farklı olduğunu gösteriyor. | Kritik | `config.py:112-113` (7 seviye), `config.py:472-473` (GFS 3 seviye); küp boyutları bu oturumda; `SONUCLAR.md` §1.1; `SINIRLAMALAR_VE_DERSLER.md` "Doğrulama reanalize dayalı" | "Eşiği bir veri düzeninde seçip demoyu başka bir düzende gösteriyorsunuz. Demodaki kırmızılar ne kadar anlamlı?" | "Doğru, Türkiye ve canlı GFS 3 seviyeli; katman kalınlığı farklı, eşik oraya doğrulanmadan aktarıldı. GFS için ayrı eşik ölçümü var (7e-7 ↔ 8,3e-7), dondurmadan sonra uygulanacak. Türkiye küpü 7 seviyeyle yeniden indirilmeli." |
| B-4 | Doğrulama yalnız ABD'de; demo ve rotalar Türkiye'de. Türkiye/Doğu Akdeniz'de MADIS gözlemi yok, IEM'in Türkiye kutusundaki PIREP'ler yanlış konumlu ABD raporları. Türkiye verisi tek ay (Ocak 2019, 744 saat). | Kritik | `SINIRLAMALAR_VE_DERSLER.md` §1; README "2019 Türkiye uçuşları için hiçbir kaynak kapsama sağlamıyor"; küp boyutu | "Türkiye'de işe yaradığını nereden biliyorsunuz?" | "Bilmiyoruz; Türkiye'de beceri ölçülmedi ve bunu sistem kartında yazıyoruz. Fizik bölgeden bağımsız, ama doğrulaması ABD'de. Türkiye için nesnel etiket (MGM, IATA Turbulence Aware) gelecek iş." |
| B-5 | PIREP etiketi yanlı ve gürültülü: gönüllü, konumu kaba, %52 pozitif. "Orta ve üstü" LGT-MOD'u da kapsıyor. Negatif raporlar rastgele nokta değil. | Yüksek | `SONUCLAR.md` §4; `bagimsiz_kanit.py:52-61` (`pirep_siddet_sinifi`) | "Etiketiniz pilotların keyfine bağlı. Model neyi öğreniyor?" | "Sıralama becerisi (ROC-AUC) taban orandan bağımsız olduğu için anlamlı; olasılık ise 'PIREP verilmiş bir noktada' koşullu. Bunu MADIS ölçümüyle çapraz kontrol ettik; sıralama orada da korunuyor (TI1 0,706), olasılık kalibre değil." |
| B-6 | MADIS nesnel etiketi zayıf: 6 gün, QC'siz ("Z"), PIREP pencerelerinden seçilmiş. Orta ve üstü ölçüm **0**; yalnız "hafif ve üstü" ölçülebiliyor (etiket tanımı PIREP'ten farklı). | Yüksek ⏳ | `SAYILAR.md` "MADIS orta ve üstü ölçüm 0"; `SONUCLAR.md` §0.4 | "Nesnel doğrulamanız 6 gün ve hiç orta türbülans içermiyor mu?" | "Evet, ön sonuç olarak raporlanıyor. Asıl doğrulama PIREP; MADIS yalnız sıralamanın kendi etiketimize özgü olmadığını gösteriyor." |
| B-7 | ML modelinin katkısı küçük ve model türüne bağlı. 1-SE kuralı Lojistik Regresyon seçtiğinde aday TI1'i geçemiyor (+0,007 civarı); Random Forest/GB seçtiğinde geçiyor (+0,033). Gece gece seçim LR, RF ve GB arasında değişiyor. Aktif RF de 10–17 Ekim adaylarına karşı fark yaratmıyor (+0,000…+0,003). | Yüksek ⏳ | manifest: 10, 11, 12 Ekim LR → TI1 farkı GA 0'ı içeriyor; 9, 13–17 Ekim RF/GB → alt sınır ~+0,018 | "ML gerçekten bir şey katıyor mu, yoksa model seçimine mi bağlı?" | "Katkı küçük: +0,03 ROC-AUC, o da doğrusal olmayan modellerde. Doğrusal model fizik göstergesinin ötesine geçemiyor; bu, bilginin büyük kısmının TI1'de olduğunu söylüyor." |
| B-8 | Aynı 16 altın test günü her gece kapı olarak kullanılıyor: 19 sürüm, 9 Ekim'de biri geçip aktifleşti. Seçim CV ile yapılsa da aynı test setine tekrar tekrar bakmak "şans eseri geçme" olasılığını artırır (çoklu karşılaştırma). Belgelerde açık değil. | Yüksek ⏳ | manifest (19 kayıt); `ml_otomatik_egitim.py:156-173` (`terfi_karari`); `YAPILACAKLAR.md` "aynı 16 altın gün kullanılmaz" yalnız gelecek deneyler için | "Test günlerine 19 kez baktınız. Bu artık test seti mi?" | "Haklı bir eleştiri. Model seçimi test günlerine bakılmadan yapıldı, ama kapı aynı günlerde tekrarlandı. Bu yüzden nihai iddiayı dondurma sonrası toplanan yeni günlerle doğrulamayı planladık." |
| B-9 | Eşik 7e-7 ERA5'te seçildi, canlı GFS'te aynen kullanılıyor; GFS'te noktaların daha büyük kısmı riskli çıkıyor (%11,1 / %8,5; eşdeğer 8,30e-7). Ayrı GFS eşiği boş. Eşik mevsime ve seviyeye göre ayrılmadı; 350 hPa'da seviye eşiği 1,1e-6. Hafif eşiği 4e-7 hâlâ kaba başlangıç değeri. | Yüksek ⏳ | `config.py:281-283`; `SISTEM_KARTI.md` §3; `SAYILAR.md` seviye satırları | "Gelecek için tahmin yaparken geçmiş veriyle ayarlanmış eşiği mi kullanıyorsunuz?" | "Evet, şu an öyle. Eşdeğer GFS eşiğini ölçtük (8,3e-7) ve dondurma sonrası nihai ERA5 eşiğiyle yeniden hesaplayıp uygulayacağız." |
| B-10 | Backtest döngüsel ve küçük: A* TI1'i düşürecek şekilde seçiliyor, başarı yine TI1'le ölçülüyor. Veritabanında yalnız 2 uçuş (THY322 1 ve 15 Ocak). Bağımsız kanıtlı tek uçuş (PUE502) veritabanında yok; o uçuşta TI1 SIGMET'in gösterdiği türbülansı hiç görmedi. | Yüksek | `SONUCLAR.md` §0.5; README "Bağımsız kanıt" | "Rotanızın daha güvenli olduğunu nasıl kanıtladınız?" | "Kanıtlamadık. Backtest yalnız tutarlılık gösteriyor ve döngüsel olduğunu yazıyoruz. Bağımsız kanıt modülü var, ama Türkiye uçuşları için kanıt kaynağı yok." |
| B-11 | Küçük örneklemli deneyler: Fikir 18 15 vaka ve referansı gözlem değil daha yeni GFS (R1 lehine yanlı). Sanal PIREP POD 1/8, POFD 0/8 (16 PIREP), eşikler kalibre değil. Altın test 16 gün. | Orta | `docs/sonuclar/2026-10-17/README.md`; `SONUCLAR.md` §5 | "Bu sayılarla genelleme yapılabilir mi?" | "Hayır; ikisini de gösterim/ön sonuç olarak etiketledik ve istatistiksel iddia kurmadık." |
| B-12 | Kalibre edilmemiş varsayımlar rota sonucunu etkiliyor: seyir kütlesi MTOW × 0,85; 48 sa güvenilir öngörü sınırı (Lee 2025, 4 vaka); tip başına sabit TAS (A320 230 m/s, seviyeden bağımsız); sabit manyetik sapma +5°E (ABD'de ve izi 0°/180° civarı rotalarda FL paritesini yanlış seçebilir); 6 saatlik TI1 cezası; varış zamanında %30 + 5 dk belirsizlik payı. | Orta | `config.py:366, 376, 477, 358-359`; `rota_optimizasyonu.py:118-145`; `risk_katmanlari.py:41` | "Yakıt tasarrufu yüzdeniz hangi varsayımlara dayanıyor?" | "Kütleye duyarlılığı yanıtta bant olarak veriyoruz (%70–90 MTOW). Diğerleri belgelenmiş varsayım; özellikle seviye değişiminde sonuç kütleye duyarlı, yanal sapmada değil." |
| B-13 | Çözünürlük sınırı: 0,25° (~25–30 km) ve 25–50 hPa katman, uçağın hissettiği 100 m–1 km ölçeği çözemez; Ri < 0,25 örneklerin yalnız %1,4'ünde görülüyor, THY322'de 0 nokta. | Orta | `SINIRLAMALAR_VE_DERSLER.md` "Çözünürlük"; THY322 sayımı | "Bu çözünürlükte CAT görülebilir mi?" | "Doğrudan görülemez; ancak onu üreten büyük ölçekli koşullar (kayma, deformasyon) görülebilir. GTG gibi operasyonel ürünler de aynı mantıkla çalışır, ama daha ince NWP verisiyle." |
| B-14 | Operasyonel ürünlerle karşılaştırma yok (GTG, WAFS). Sistemin onlardan iyi ya da kötü olduğu söylenemez. | Orta | `SINIRLAMALAR_VE_DERSLER.md` "Operasyonel karşılaştırma yok" | "GTG zaten varken bunu neden yaptınız?" | "GTG ABD'ye, WAFS kaba ızgaraya odaklı ve açık veriyle iz bazlı ölçüm yapmıyor. Biz yalnız açık veriyle ne yapılabileceğini ölçtük; karşılaştırma yapılmadı ve iddia etmiyoruz." |
| B-15 | Model olasılıkları kalibre değil: MADIS'te ortalama tahmin %51, gözlenen %3. Konformal çıktı aktif modelde örneklerin %59'unda "belirsiz" diyor. | Orta | `SAYILAR.md` MADIS; `turbulans_ml_modeli_bilgisi.json` `konformal.holdout_dogrulamasi.belirsiz_orani` 0,587 | "Modeliniz çoğu zaman 'bilmiyorum' diyorsa ne işe yarar?" | "Belirsizliği gizlemek yerine gösteriyoruz; ayırt gücü orta olan bir göstergede bu beklenen bir sonuç." |
| B-16 | Kapsam dar: yalnız CAT ve seyir (FL280 üstü). NTSB'ye göre yaralanmaların önemli kısmı alçak irtifa/yaklaşmada. Konvektif türbülans (en sık neden) kapsam dışı. | Düşük | `SINIRLAMALAR_VE_DERSLER.md` §1 | "En tehlikeli türbülansları kapsam dışı mı bıraktınız?" | "Bilinçli kapsam kararı; konvektif ve alçak irtifa türbülansı farklı veri (radar, uydu) gerektiriyor." |

## B. Belge–kod çelişkileri ve eski sayılar

| No | Bulgu | Önem | Kanıt | Jüri sorusu | Önerilen kısa cevap |
|---|---|---|---|---|---|
| C-1 | **"ML modeli devrede değil" iddiası canlı sistemle çelişiyor.** README "Kısa cevap", PROJE_ISLEYISI ve SISTEM_KARTI modelin kapıdan geçemediğini ya da aktif modelin "5 Ekim, eski fizik" olduğunu söylüyor. Gerçekte 9 Ekim RF aktif, 8 güncel özellikli; `/turbulans/tahmin` ve model bilgisi uçlarında kullanılıyor. | Kritik ⏳ | `README.md:15`; `docs/sunum/PROJE_ISLEYISI.md:243, 300`; `SISTEM_KARTI.md:245-250`; `SONUCLAR.md:246`; `ml/durum` `aktif_model`; `turbulans_ml_modeli.py:213-223` | Demo sırasında: "Ekranda model bilgisi var, ama raporunuz model devrede değil diyor?" | "Rapordaki satır 7 Ekim protokol modeline (LR) ait. Gece kapısı 9 Ekim'de RF'yi altın günlerde TI1'i geçtiği için aktifleştirdi; belgeleri nihai pakette tek anlatıya bağlıyoruz." (Bunu söylemek zorunda kalmamak için belgeler düzeltilmeli.) |
| C-2 | İki ayrı "nihai model" anlatısı oluşacak. Dondurma paketi (`turbulans-ml-degerlendirme`, `sonuc_disa_aktarimi.py`) protokol modelini, yani 1-SE ile büyük olasılıkla LR'yi raporlayacak. Canlı sistem RF sunuyor. `sonuc_paketi.py` ise "aktif modelle aynı tür" kullanıyor. | Kritik ⏳ | `ml/sonuc_disa_aktarimi.py` docstring; `ml/sonuc_paketi.py` docstring; `YAPILACAKLAR.md` 18 Ekim listesinde bu çelişki yok | "Raporladığınız model ile çalışan model aynı mı?" | "Hayır; raporlanan protokol modeli, çalışan model kapıdan geçen sürüm. İkisinin skorlarını aynı altın günlerde yan yana veriyoruz." (Tablo eklenmeli.) |
| C-3 | `docs/mimari.md` §5 kapıyı "aktif modeli F1'de geçiyor mu" diye çiziyor; kod ROC-AUC farkı + GA alt sınırı kullanıyor. | Orta | `docs/mimari.md:160`; `ml_otomatik_egitim.py:141-173` | "Kapı ölçütünüz F1 mi ROC-AUC mi?" | "ROC-AUC; diyagram eski sürümden kalmış." |
| C-4 | SISTEM_KARTI aktif modelin "eğitim gün listesi olmadığı için karşılaştırmada yok sayıldığını" söylüyor. Aktif modelin 79 günlük listesi var; 10 Ekim'den beri her aday ona karşı ölçülüyor. | Orta | `SISTEM_KARTI.md:247-248`; manifest `aday_eksi_aktif_model_roc_auc` (10–17 Ekim dolu) | — | Belge düzeltmesi. |
| C-5 | THY322 backtest sayısı belgeler arasında farklı: README 0,19 / 0,32 / 0,00 (6 Ekim, 116 km bölüm), SAYILAR/SONUCLAR/poster 0,24 / 0,39 / 0,02 (7e-7 eşiği). Öğrenme rehberi Ders 1 README'deki eski değeri almıştı; bu incelemede düzeltildi. | Orta | `README.md:769`; `SAYILAR.md:72` | "Posterde bir sayı, raporda başka bir sayı var." | "README satırı eşik değişmeden önceki ölçüm; güncel değer sonuç paketindeki." |
| C-6 | Aynı paket için iki farklı commit kimliği: SONUCLAR "commit `34c6f93`", SAYILAR "commit `d7858e8`". | Düşük | `SONUCLAR.md` §0; `SAYILAR.md` başlık | "Hangi kodla üretildi?" | Belge düzeltmesi; SAYILAR otomatik üretildiği için doğru kaynak odur. |
| C-7 | Koda gömülü eski sayılar: `TI1_GUVENILIRLIK_NOTU` her API yanıtında "7815 PIREP [80 gün]" diyor; veritabanında şu an 15.942 eşleşmiş örnek, 163 gün. | Orta ⏳ | `fizik/turbulans_indeksleri.py:126, 139`; `ml/durum` | — | Dondurma sonrası güncellenecek listede var (`YAPILACAKLAR.md`). |
| C-8 | `fizik/kalibrasyon.py` docstring'i katsayının "varsayılan 1.5, tamamen keyfi" olduğunu söylüyor; kodda 0,27 ve "PIREP'le kalibre edildi" bayrağı `True`. | Düşük | `fizik/kalibrasyon.py:4-6`; `config.py:304, 307` | — | Docstring düzeltmesi. |
| C-9 | **Raporlama hatası:** `kalibre_ti1` holdout metrikleri olasılık çıktısına TI1 birimindeki eşiği (5,3e-7) uyguluyor. Sonuç: her sürümde POD = POFD = 1, Peirce 0. Brier değeri doğru, ikili metrikler anlamsız. | Orta | `ml_otomatik_egitim.py:293-297`; aktif modelin `holdout.kalibre_ti1` alanı | "Bu tabloda kalibre TI1 her şeyi pozitif sayıyor?" | "İkili metrikleri yanlış eşikle hesaplanmış bir raporlama hatası; karar kapısını etkilemiyor, kapı ROC-AUC kullanıyor." (Dondurmadan önce düzeltilmesi önerilir.) |
| C-10 | Belge yükü ve sayı dağınıklığı: `docs/` altında 51 Markdown dosyası (6.864 satır), README 1.672 satır. Dondurma sonrası 12'den fazla dosyada sayı elle değişecek; tutarlılık betiği yok. | Orta ⏳ | `YAPILACAKLAR.md` 18 Ekim maddesi; Faz 0 S-6 | "Belgelerinizde hangi sayı doğru?" | "Tek kaynak `SAYILAR.md`; diğerleri ondan alıntılanıyor." (Betik yazılmadıkça bu cevap riskli.) |

## C. Yapay zekâ kullanımı ve sahiplik

| No | Bulgu | Önem | Kanıt | Jüri sorusu | Önerilen kısa cevap |
|---|---|---|---|---|---|
| Y-1 | Beyan eskimiş ve yöntemi artık çalışmıyor. Beyan "202 commit'in 200'ü asistan işaretli" diyor (8 Ekim). Bugün 282 commit, 208'i işaretli. 8 Ekim'den sonraki 72 commit'in yalnız 6'sı işaretli, çünkü imza bırakıldı; bunlar da asistanla yazıldı. `Co-Authored-By` sayımı artık asistan payını **eksik gösterir**. Beyan "908 test" diyor; bugün 1.035. | Kritik | `docs/rapor/ARAC_KULLANIMI_BEYANI.md`; `git rev-list --count --no-merges HEAD` = 282; Co-Authored-By = 208 | "Bu kodu kim yazdı?" | "Kodun neredeyse tamamı Claude Code ile birlikte yazıldı. Araştırma sorusu, kapsam, veri seçimi, kabul kriterleri ve yorum benim. Beyandaki sayıları güncel git'le ve imza bırakıldıktan sonraki dönemi açıkça yazarak güncelledim." |
| Y-2 | Ölçek ve süre uyumsuzluğu: 26.325 satır kaynak + 14.434 satır test, yaklaşık 4 haftada (21 Eylül–17 Ekim). Komite tek öğrencinin bunu anlayıp anlamadığını sınayacaktır. | Kritik | `src/` ve `tests/` satır sayımı; ilk commit tarihi | "Rastgele bir dosya açalım: bu fonksiyon ne yapıyor?" | Beyandaki 4 çekirdek modülü (`eslestirme.py`, `turbulans_indeksleri.py`, A* maliyet ve sezgiseli, `degerlendirme.py`) satır satır anlatabilmek. Ekler (sanal PIREP, IWXXM, MCP, n8n) için "mühendislik eki, tez iddiası değil" demek. |
| Y-3 | Kapsam şişmesi: çekirdek 4 katkının yanında çok sayıda ek (sanal PIREP, contrail, IWXXM, FPL, GFS topluluğu, MCP, n8n, 3B simülasyon, Pareto, kalkış penceresi). Her biri yeni sınırlama ve soru kapısı açıyor; bir kısmı kalibre değil ya da gösterim amaçlı. | Yüksek | README "Çekirdek ve ekler"; SISTEM_KARTI §3 | "Bu kadar özellikten hangisi tezin katkısı?" | "Dört katkı: K1, K2, K6, K7. Diğerleri ürünleştirme denemesi ve tez iddiası taşımıyor." |
| Y-4 | Asistan kararlarının izlenebilirliği: beyan, asistana bırakılan kararların "önceden yazılı kurala bağlandığını" söylüyor. Bu en çok eşik seçiminde belgeli; model türü, ceza değerleri ve tampon gibi diğer seçimler için aynı izlenebilirlik yok. | Orta | `ARAC_KULLANIMI_BEYANI.md`; `deney_protokolu.md` | "6 saatlik ceza değerini kim, neye göre seçti?" | "Kalibre edilmemiş bir tasarım varsayımı; Pareto seçenekleri (300/60/0 sn) bu yüzden kullanıcıya gösteriliyor." |

## D. Yazılım, test ve yeniden üretilebilirlik

| No | Bulgu | Önem | Kanıt | Jüri sorusu | Önerilen kısa cevap |
|---|---|---|---|---|---|
| T-1 | Sonuçlar üçüncü kişi tarafından yeniden üretilemiyor. ML sayıları veritabanına ve 222 MB'lık pencere deposuna dayanıyor; ikisi de depoda yok. Yeniden toplamak CDS hesabı, kota ve günler süren gece işi istiyor. Depoda yalnız tek demo uçuşu var. | Yüksek ⏳ | `git ls-files` (yalnız `demo/` verisi); `ml_ozellik_deposu` 222 MB; `db_yedekleri` 1,4 GB | "Sonuçlarınızı ben nasıl tekrarlarım?" | "Dondurma anının veritabanı yedeği ve sha256'sı paketle birlikte arşivleniyor; komutlar belgeli." (Yedeğin teslim/arşiv biçimi henüz belirlenmedi.) |
| T-2 | Kapsama ölçülüyor ama alt sınır yok. CI `--cov` çalıştırıyor, `fail_under` tanımlı değil; oranı bu incelemede ölçmedim. | Düşük | `.github/workflows/ci.yml:111`; `pyproject.toml` | "Test kapsamanız yüzde kaç?" | CI özetinden güncel oran bilinmeli. |
| T-3 | Zamana bağlı kararsız testler görüldü: hız sınırı testleri saate hizalı pencere sınırına denk gelince düştü (PR #81 ile düzeltildi). Benzer zamana bağlı testler başka yerde de olabilir; taranmadı. | Düşük | `ISLEM_GUNLUGU.md` 17 Ekim | — | — |
| T-4 | Testlerin çoğu davranışı ve uç durumları sınıyor; bilimsel doğruluğu sınayan sabit referans testleri az. Örnekler: THY322 "altın değerleri" ve analitik deformasyon testleri. Bunlar regresyonu yakalar, doğruluğu kanıtlamaz. | Orta | `tests/test_demo.py:46-62`; `tests/test_turbulans_indeksleri.py` | "TI1 hesabınızın doğru olduğunu nasıl test ettiniz?" | "Analitik alanlarda (doğrusal, katı dönme, saf gerilme) beklenen değerlerle; ayrıca yayımlanmış bir TI1 değeriyle karşılaştırma yapılmadı." (Literatürdeki bir vaka ile çapraz kontrol eklenebilir.) |

## E. Altyapı ve güvenlik (Faz 0'dan, açık olanlar)

Ayrıntı ve kanıt [`URETIM_HAZIRLIK.md`](URETIM_HAZIRLIK.md)'de. Komite için önemli olanlar:

| No | Bulgu | Önem | Jüri sorusu | Önerilen kısa cevap |
|---|---|---|---|---|
| O-1 | Ağa açılış için 9 P0 açık: TLS vekili yok, kapalı başlama yok, CSP/güvenlik başlıkları yok, yedekler API konteynerinde görünüyor, geri yükleme tatbikatı yok. | Yüksek | "Bu sistem internete açılabilir mi?" | "Hayır, bugün yalnız yerelde (127.0.0.1) çalışıyor. Ağa açılış öncesi eksikler listelendi ve sıralandı." |
| O-2 | Tek dizüstüne bağımlılık: gece işi bilgisayarın açılmasına bağlı, WSL uykudan çıkınca DNS hataları görülüyor. Sunucu B planı yalnız öneri. | Orta | "Gece işi kaçarsa ne olur?" | "Bir sonraki açılışta çalışıyor ve günlük bütçe korunuyor; sürekli çalışma için sunucu gerekir." |
| O-3 | Kısıtlı saha verisi: AIRAC 29 Ekim'de bitiyor, yani savunmada (Kasım) AIP verisi süresi geçmiş olacak. Paketle gelen Suriye/Irak sahaları resmî değil (Natural Earth ülke sınırı). | Orta | "Yasak saha veriniz güncel mi?" | "Hayır; AIRAC döngüsüne bağlı ve elle yenileniyor. Örnek veri arayüzde 'örnek' diye işaretli." |
| O-4 | Önerilen rota dosyalanabilir bir uçuş planı değil. Koridor modu ATS yollarına bağlı değil; FRA ağı yalnız DCT kenarları ve 20:00–02:00 UTC. Diğer trafikle ayırma yok. FPL dizgisi NON-OPERATIONAL. | Orta | "ATC bu rotayı kabul eder mi?" | "Hayır, bu bir planlama önerisi; ATS yolu ve ayırma kapsam dışı ve yanıtta `kapsam` alanında yazıyor." |
| O-5 | Lisans: OpenSky verisi yalnız araştırma/ticari olmayan kullanım; Esri karoları koda gömülü. Ürünleşme iddiası bu şartlarla çelişebilir. | Düşük | "Bunu satabilir misiniz?" | "Bu verilerle hayır; veri lisansları ticari kullanıma izin vermiyor." |

## F. İleride karşına çıkacak engeller (takvim)

| Tarih | Engel | Etki |
|---|---|---|
| 18 Ekim | Nihai paket ön paketteki sayıları değiştirecek (veri 80 → ~163 gün). | B-1, B-6, B-7, B-9, C-1, C-2, C-7, C-10 yeniden yazılır. 12+ belge, poster, sunum ve koda gömülü not elle güncellenir. |
| 18 Ekim | 1-SE kuralı LR seçerse paket "model geçemedi", canlı sistem "RF aktif" diyecek. | C-2 çelişkisi kalıcı olur; yan yana tablo şart. |
| 18 Ekim sonrası | GFS eşiği uygulanınca demo ve ekranlardaki riskli sayılar değişebilir. | Demo videosu ve ekran görüntüleri yeniden üretilir. |
| 29 Ekim | AIRAC bitişi. | Savunmada kısıtlı saha verisi süresi geçmiş olur (O-3). |
| 5 Kasım | Demo videosu. | C-1/C-2 çözülmeden çekilirse ekrandaki model bilgisi rapora ters düşer. |
| Savunma | Beyan güncellenmezse (Y-1) sayılar git'le doğrulanabilir biçimde tutmaz. | Akademik dürüstlük sorusu. |

---

## En zayıf 5 nokta ve sunumda nasıl savunulur

1. **TI1'in becerisi orta ve gerçek taban oranda çoğu uyarı yanlış alarm (B-1, B-2).**
   *Savunma:* Bunu saklamayın, sunumun ana bulgusu yapın. "Açık veriyle ulaşılabilen beceri
   bu kadar; biz bu sınırı ölçtük ve ürünü ona göre tasarladık: güvenlik SIGMET duvarından,
   TI1 yalnız yumuşak ceza, olasılık mutlak sıklık olarak gösterilmiyor." Bir slaytta
   POD/POFD ile taban oran etkisini birlikte gösterin.

2. **Türkiye'de doğrulama yok ve Türkiye/GFS verisi eğitimden farklı katman düzeninde (B-3, B-4).**
   *Savunma:* "Doğrulama ABD'de, demo Türkiye'de; Türkiye'deki beceri ölçülmedi." Eğitim–kullanım
   farkını kendiniz söyleyin ve planı verin: Türkiye küpünü 7 seviyeyle indirmek, GFS eşiğini
   uygulamak, nesnel etiket kaynağı aramak. Jüri bunu sizden önce bulursa zarar büyük olur.

3. **ML anlatısı belgelerle canlı sistem arasında çelişkili (C-1, C-2, B-7, B-8).**
   *Savunma:* Dondurmadan sonra tek tablo hazırlayın: protokol modeli (LR) ve aktif model (RF),
   aynı altın günlerde, TI1 farkıyla yan yana. Ana mesaj: "ML'in katkısı küçük (+0,03) ve
   doğrusal olmayan modele bağlı; altın günler tekrar kullanıldığı için bu sonucu yeni günlerle
   doğrulamayı planladık." Bu, çelişkiyi bir bulguya çevirir.

4. **Yapay zekâ ile yazılmış büyük bir kod tabanı (Y-1, Y-2, Y-3).**
   *Savunma:* Beyanı güncel sayılarla ve imza bırakılan dönemi açıkça yazarak yenileyin. Dört
   çekirdek modülü kâğıtsız anlatabilecek kadar çalışın: eşleştirme, TI1, A* maliyet/sezgisel,
   değerlendirme. Ekleri "mühendislik eki" diye baştan ayırın. "Sen ne yaptın?" sorusunun
   cevabı: soru, kapsam, veri seçimi, kabul kriterleri, hataların bulunması (FL feet, /OV UNK)
   ve sonuçların dürüst yorumu.

5. **Rota faydası kanıtlanmadı: backtest döngüsel, 2 uçuş, varsayımlar kalibre değil (B-10, B-12).**
   *Savunma:* Rota bölümünü "fayda kanıtı" değil, "kısıtlı karar mantığının doğru çalıştığı"
   olarak sunun: duvarlara hiç girmiyor, risk yoksa rotayı değiştirmiyor, güvenli yol yoksa
   "ÖNERİ YOK" diyor. Bunlar testlerle kanıtlı. Yakıt yüzdelerini kütle bandıyla verin, tek
   sayı olarak değil.

## Dondurmadan önce yapılması önerilen küçük işler (onaya sunulur, bu incelemede yapılmadı)

- C-9 raporlama hatası (`kalibre_ti1` eşiği): tek satır; düzeltilmezse nihai pakete anlamsız
  POD/POFD girer.
- C-2 için paket betiğine "aktif model" satırı eklenmesi ya da en azından SONUCLAR'a not.
- Y-1 beyan sayımlarının dondurma günü güncel git'ten yeniden alınması.

## 18 Ekim durumu (nihai paket sonrası)

- **C-9 kapandı** (PR #86): kalibre TI1'in ikili metrikleri artık TI1 eşiğinin olasılık
  karşılığıyla hesaplanıyor; nihai pakette POD/POFD TI1 referansıyla aynı (0,622 / 0,373).
- **C-1, C-2 kapandı:** nihai pakette protokol modeli Random Forest, altın günlerde TI1'i
  +0,033 [+0,018; +0,049] ile geçti. Canlıdaki 9 Ekim RF (+0,033) ile yan yana SONUCLAR §0.1,
  SISTEM_KARTI, README "Kısa cevap", PROJE_ISLEYISI ve SUNUM_AKISI §8'de anlatılıyor. Dondurma
  raporunda aday aktif modeli geçemedi (+0,003), saklandı.
- **C-7 kapandı:** `TI1_GUVENILIRLIK_NOTU` 15.940 PIREP / 163 güne güncellendi.
- **B-6 değişti:** MADIS 14 gün, 45.075 ölçüm; orta ve üstü yalnız 1 ölçüm (hâlâ fiilen hafif sınıf).
- **B-7 değişti:** 1-SE kuralı 163 günde ağaç modeli seçti (RF ve GB berabere) ve model geçti; 80 günde LR seçip geçememişti.
  Sonucun veri hacmine duyarlılığı belgelerde açıkça yazıyor.
- **B-8 belgelendi:** 7–18 Ekim arasında 12 sürümün aynı altın günlerde kapıya girdiği SONUCLAR
  §0.1 ve SISTEM_KARTI'nda not edildi.
- **Yeni bulgu:** kesme `olusturulma_zamani`'na göre; gece işi eski satırları güncellediği için
  kesme canlı veride dondurmuyor. Paket ancak `turbulans_20261018.dump` yedeğiyle aynen yeniden
  üretilir (`docs/sonuclar/README.md`, SONUCLAR §6).
- **Yeni bulgu kapandı (PR #89):** eğitim sorgusu sırasızdı; dondurma yedeğinden yeniden
  üretimde RF/GB seçimi değişti (CV'de berabere). Sorgular sıralandı; nihai paket yedekten ve
  canlıdan birebir aynı üretildi (RF +0,033). İlk üretim (GB +0,036) `ilk_uretim_sirasiz/`'da.
  T-1 (yeniden üretilebilirlik) bu yedek ve tatbikatla kısmen kapandı; yedek depoda değil.
- Y-1 beyan sayımları güncellendi (284 commit, %1,6 kalan satır, 1.051 test).

## 19 Ekim durumu

- **B-8 için yol önceden kayıtlı:** `deney_protokolu.md` §10. Sonraki değerlendirme
  dondurmanın görmediği günlerde (`ml/dondurma_gunleri.json` dışı, ≥ 30 gün) bir kez yapılır;
  16 altın gün artık test sayılmaz.
- **B-9 kapandı (18 Ekim):** GFS eşiği `TI1_ESIK_ORTA_SIDDETLI_GFS=8,3e-7` (`.env`).
- **C-3 kapandı:** `mimari.md` kapı diyagramı ROC-AUC farkı + GA alt sınırına göre.
- **C-5 kapandı:** README THY322 satırının 6 Ekim ölçümü olduğu ve güncel değerin
  (0,24 / 0,39 / 0,02) yeri yazıldı.
- **C-8 kapandı:** `fizik/kalibrasyon.py` docstring'i güncel katsayıya (0,27) bağlandı.
- **O-3:** `/saglik` AIRAC bitişine 7 gün kala `ats_agi: bitiyor` uyarısı veriyor; yenileme
  29 Ekim'de (ONAY).
- **T-1 kapandı (biçim):** yedek açık yayımlanmaz (OpenSky lisansı), komite isterse özel
  bağlantıyla verilir; sha256 ve adımlar `docs/sonuclar/README.md` "Üçüncü kişi için". Başka
  makinede uçtan uca denenmedi.
- **C-10 kapandı:** `tests/test_sayi_tutarliligi.py` (CI): 7 Ekim ön paketinin GA'lı ve binlik
  sayıları güncel belgelerde yalnız tarihçe bağlamında geçebilir; `TI1_GUVENILIRLIK_NOTU` ve
  paket commit'i nihai paketle aynı olmalı.
- **T-4 kapandı:** deformasyon ve diverjans, gerçek ERA5 alanında (THY322 demo küpü) MetPy
  `total_deformation`/`divergence` ile aynı (iç noktalarda fark alan ölçeğinin ~1e-6'sı;
  küresel metrik terimi kaldırılınca %2,6). Jüri cevabı: "Analitik alanlara ek olarak bağımsız
  bir kütüphaneyle gerçek veride çapraz kontrol var; yayımlanmış bir vaka değeriyle karşılaştırma yok."
- **T-2 kapandı:** `fail_under = 80` (CI kapsamı %84,5).
- **B-3 ertelendi (ONAY alındı):** 19 Ekim veri bütçesi dolu olduğu için 7 seviyeli Türkiye küpü
  20 Ekim'de indirilecek (`scripts/turkiye_kupu_7seviye.py`, YAPILACAKLAR). Ayrı dosya;
  varsayılan küp ve demo sayıları değişmez, fark raporlanır.
- Açık kalanlar: B-3 (20 Ekim), Y-1 (beyan sayımları teslimden hemen önce), O-3 (29 Ekim AIRAC).
