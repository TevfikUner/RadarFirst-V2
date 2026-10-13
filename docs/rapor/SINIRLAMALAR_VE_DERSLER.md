# Sınırlamalar ve öğrenilen dersler (rapor bölümü, Madde 9)

## 1. Sınırlamalar

**Sertifikasyon yok.** Sistem sertifikalı EDR üretmez ve operasyonel karar aracı
değildir; karar destek aracıdır. Birleşik EDR, reanalizden türetilmiş bir tahmindir.
Uçaktan ölçülen EDR'nin yerini tutmaz. Kabin önerisi "karar kaptanındır" ifadesiyle
verilir. Hiçbir çıktı havacılık otoritesinin onayından geçmemiştir.

**Kapsam yalnızca açık hava türbülansı (CAT).** Konvektif, bulut içi, dağ dalgası ve
iz türbülansı kapsam dışıdır. Yalnızca seyir safhası (ToC–ToD, FL280 üstü)
değerlendirilir. NTSB (2021) türbülans yaralanmalarının önemli bir kısmının alçak
irtifada ve yaklaşmada olduğunu gösterir; bu olaylar sistemin göremediği yerdedir.

**Yalnızca ABD verisi.** Eğitim etiketleri (IEM PIREP) ve nesnel doğrulama (MADIS EDR)
ABD hava sahasındandır; 80 gün, 7.815 PIREP (16 gün altın test). Türkiye ya da Avrupa
için geçerlilik gösterilmedi. Rota ve arayüz Türkiye'de çalışır ama oradaki beceri ölçülmedi.
Yerel MADIS EDR deposu bu açığı kapatmaz: 11 günde Avrupa'da (35–60°K, 10°B–30°D) FL280 üstü
21.167 gözlem var ama yalnızca 28'i hafif ve üstü (EDR ≥ 0,1); Türkiye/Doğu Akdeniz'de (34–43°K,
25–45°D) hiç yok. O günler için Avrupa ERA5 penceresi de indirilmemiştir. 28 pozitifle ROC-AUC
güven aralığı anlamlı olmayacağından Avrupa skoru raporlanmaz.
Göstergelerin log-normal eşleme klimatolojisi de ABD PIREP pencerelerinden gelir.

**Doğrulama reanalize dayalı.** Göstergeler ERA5 reanalizinden (0,25°, saatlik)
hesaplanır. Reanaliz, uçuş anında elde olmayan ve gözlemlerle düzeltilmiş bir "en iyi
tahmin"dir. Bu yüzden ölçülen beceri, gerçek zamanlı bir tahmin modelinin (GFS)
becerisinin üst sınırına yakındır; canlı GFS ile beceri ayrıca ölçülmedi. Canlı GFS
küpü 3 seviyeyle indirildiği için kayma orada 50 hPa'lık katmandan hesaplanır.
Eğitim ise 25 hPa'lık katmanla yapıldı.

**Etiket kaynaklı sınırlar.** PIREP'ler türbülansa doğru güçlü biçimde yanlıdır:
pozitif oranı %52, aynı yerlerdeki MADIS ölçümlerinde hafif ve üstü %3. Model
olasılıkları bu yüzden mutlak sıklık değildir. MADIS ölçümleri yalnız 6 gündür, kalite
kontrolsüzdür (QC "Z") ve PIREP pencerelerinin içinden gelir; sonuçlar ön sonuçtur.

**İstatistiksel sınırlar.** Birleşik EDR'nin TI1'e üstünlüğü anlamlı ama küçüktür
(altın test günlerinde +0,014 ROC-AUC); model TI1'i geçemedi (+0,008, GA 0'ı içeriyor;
`docs/sonuclar/2026-10-07/SAYILAR.md`). Altın test 16 gündür; güven aralıkları geniştir.
Sanal PIREP 16 PIREP'le ölçüldü ve eşikleri kalibre edilmedi. ATC ayırma komutu ve TCAS uyarısı ayrıca
elenmez (seviye değişimi seyir sayılmaz, düşey hız tepkisi aranır, bildirim için ≥ 2 uçak gerekir);
bildirimdeki ERA5 TI1 uyum etiketi olayı elemez ve başarımı ölçülmedi.
Kazanç raporlarken büyük daire referansı rüzgâr kazancını da içerir; kaçınma bedeli ayrıca
`referans_karsilastirmasi.kacinma_bedeli` ile rüzgâr-optimum rotaya göre verilir. TI1 risk eşiği 8 Ekim'de
eğitim günlerinden 1-SE kuralıyla 7e-7 seçildi; hafif eşiği (4e-7) hâlâ kaba bir
başlangıç değeridir.

**Çözünürlük.** ERA5'in 0,25° ızgarası ve 25 hPa'lık katmanı, uçağın algıladığı
ölçeği (yaklaşık 100 m – 1 km) çözemez; ince kararsız katmanlar (Ri < 0,25)
örneklerin yalnızca %1,4'ünde görülür.

**Aktarım ve kapsam dışı bırakılanlar.** Eşikler, birleşik EDR katsayıları ve model
ERA5 ile seçildi; canlı GFS'ye doğrulanmadan aktarılır. Eşikler mevsime göre ayrılmadı.
Türbülans riski uçak tipinden, yakıt akışı irtifa ve kütleden bağımsızdır. Sanal PIREP
seviye değişikliğini olay saymaz. ICAO uçuş planı (Item 15/EET) üretilmez; ATFCM/CTOT ve
sektör kapasitesi kapsam dışıdır. Backtest FRA modunu ölçmez. Bunlar bilinçli kapsam
kararlarıdır; ayrıntı `docs/SISTEM_KARTI.md` §5'te.

**Operasyonel karşılaştırma yok.** GTG ve WAFS ürünleriyle aynı veride doğruluk
karşılaştırması yapılmadı (M3). Sistemin operasyonel ürünlerden iyi ya da kötü olduğu
söylenemez.

## 2. Öğrenilen dersler

Her olay için ne olduğu (tespit), neye yol açtığı (etki) ve tekrarını önlemek için ne
yapıldığı (önlem) yazılıdır.

### 2.1 Git geçmişinde şifre sızıntısı

- **Tespit:** 21 Eylül 2026'da OpenSky şifresi Türkçe adlı bir değişkene düz metin
  yazılıp `kimlik_dogrulama.py` içinde commit'lendi. Ertesi gün koddan kaldırıldı ama
  git geçmişinde kaldı. Varsayılan sır tarayıcı kuralları Türkçe değişken adlarını
  tanımadığı için otomatik olarak yakalanmadı. Önceki sürümün (V1) ayrı deposunda da
  Trino bağlantı dosyasında düz metin kullanıcı adı ve şifre vardı.
- **Etki:** Şifre GitHub'daki geçmişte okunabilir durumdaydı. Hesabın kendisi, veri
  kotası ve kullanım şartları risk altındaydı.
- **Önlem:** Şifre 1 Ekim'de değiştirildi. Geçmiş 2 Ekim'de `git filter-repo` ile
  yalnızca ilgili blob'daki değer silinerek temizlendi; V1 deposu 4 Ekim'de düzeltildi.
  Sırlar artık yalnız `.env` ya da Docker secret'tan okunuyor. Her commit'te ve CI'da
  Türkçe değişken adlarını da tanıyan gitleaks taraması çalışıyor; CI, Türkçe adlı
  sahte bir sırrın yakalandığını her çalıştırmada doğruluyor (ADR 0008). Kalan iz: GitHub'daki PR #1 eski
  commit'leri tutuyor; depo herkese açılmadan önce GitHub'dan "sensitive data removal"
  istenecek.

### 2.2 FL alanının feet sanılması

- **Tespit:** 30 Eylül 2026'da, ML veri hattı yeniden kurulurken ham IEM PIREP arşivi
  eski eğitim CSV'siyle karşılaştırıldı. Eşleşen 1.754 kaydın medyan "FL" değeri 300–400
  çıktı. IEM'in `FL` sütununun uçuş seviyesi değil **feet** olduğu anlaşıldı
  (FL360 → 36000).
- **Etki:** Eski veri seti "FL 300–400" filtresiyle seyir yerine 300–400 ft'teki (pist,
  yaklaşma, rüzgâr kesmesi) raporları seçmişti; bunlar 200–300 hPa ERA5'le
  eşleştirilmişti. O veriyle TI1'in ROC-AUC'si 0,44 ölçülmüş (rastgeleden kötü), 167
  örnekli ilk model ve EDR ölçek katsayısı bu hatalı veriye dayanmıştı.
- **Önlem:** Etiket hattı ham arşivden doğru birimle (FL280–FL420) yeniden kuruldu. Aynı
  ölçüm doğru veride 0,71 verdi (tarihçe: 1 Ekim, 1.000 PIREP; güncel değer
  `docs/sonuclar/` paketinde). Eski model kullanım dışı bırakıldı, eski hat açık bir
  hata mesajıyla kapatıldı (`ESKI_VERI_HATTI_MESAJI`). Ders: dış veri kaynağının
  birimini belgesine güvenmeden ham değerin dağılımıyla doğrula.

### 2.3 Konumu bilinmeyen PIREP'ler (/OV UNK)

- **Tespit:** 3 Ekim 2026'da PIREP konumları incelenirken IEM'in konumu bilinmeyen
  raporları (`/OV UNK`) UNK istasyonuna (Unalakleet, Alaska) yerleştirdiği görüldü.
- **Etki:** Arşivde seyir irtifasında 145 rapor yanlış konumla eğitim ve doğrulama
  verisine girebiliyordu; veritabanında 40 kayıt etkilenmişti. Bu raporlar Alaska'daki
  ERA5 hücreleriyle eşleşip gerçek konumlarından bağımsız etiket üretiyordu.
- **Önlem:** Ayrıştırmada `/OV UNK` raporları atılıyor ve bunun için test var
  (`dogrulama/bagimsiz_kanit.py`, commit 9a19e07); etkilenen 40 kayıt kapsam dışı
  bırakıldı. Ders: "bilinmiyor" değeri sessizce varsayılan bir değere dönüştürülmemeli,
  açıkça reddedilmelidir. Aynı ilke eşleştirmede de uygulanır: kapsam dışı nokta "0
  risk" değil "hesaplanmadı" olarak raporlanır.
