# Savunma hazırlığı (kurul #5, K-1)

Kurulun kabul ölçütü: danışmana beyan e-postası gönderildi; dört çekirdek için **yazarın elle
çizdiği** birer sayfa akış; "kendi kararlarım" listesi; **2 kayıtlı, notsuz prova** (her biri
≤ 10 dk). Çizim, prova ve gönderim yazarındır; bu belge yalnız çalışma iskeletidir. Kartlardaki
her adım koddan okundu (31 Ekim 2026, `master`); satır numarası yerine fonksiyon adı verildi.

Genel anlatım sırası: `PROJE_ISLEYISI.md` §13. Sık sorular: aynı belge §14.

## 1. Dört çekirdek: çizim iskeleti ve olası sorular

### 1.1 Eşleştirme: ADS-B noktası → hava hücresi

Kod: `fizik/eslestirme.py`, `rotayi_hava_durumuyla_eslestir`. Girdi: iz (zaman, enlem, boylam,
irtifa), hava küpü (u, v, t; `valid_time`, `pressure_level`, `latitude`, `longitude`). Çıktı:
izin her noktasına `basinc_hpa`, `ti1_indeksi`, `richardson_sayisi`, `birlesik_edr`.

Çizilecek kutular:
1. İrtifa seçimi: barometrik varsa o, yoksa GPS; kaynak satıra yazılır (`rota_irtifalari_ve_kaynagi`).
2. ISA ile irtifa → basınç (`irtifa_metre_to_basinc_hpa`).
3. Çevreleyen katman: p_üst ≤ p ≤ p_alt (`cevreleyen_katman_seviyeleri`; küp kenarında en yakın iki seviye).
4. Zaman: küpün gerçek en yakın `valid_time` adımı; enterpolasyon yok.
5. Kapsam dışı maskesi: yatay toleransın ya da ±3 sa'in dışındaki nokta NaN kalır, uydurma değer yok.
6. İki seviyeden en yakın ızgara hücresi; hipsometrik kalınlık Δz (iki seviyenin sıcaklığından).
7. VWS ve Ri katmandan; DEF ve DIV en yakın seviyenin yatay alanından → TI1, Ri, birleşik EDR.

Olası sorular:
- *Neden GPS değil barometrik irtifa?* Hava verisi basınç seviyelerinde; barometrik irtifa ISA
  basıncına birebir karşılık gelir (ADR 0005).
- *Zamanda neden enterpolasyon yok?* Etkisi ölçüldü (ATM-04, `SISTEM_KARTI.md` §5): saatlik
  küpte riskli noktaların %86,3'ü 3 saatlik örneklemede de riskli.
- *Küpün dışındaki nokta?* NaN; rota yanıtı "veri yok" der, tahmin edilmez.

### 1.2 TI1 ve Richardson sayısı

Kod: `fizik/turbulans_indeksleri.py`.
- VWS = √(Δu² + Δv²) / Δz (`dusey_ruzgar_kaymasi_hesapla`), s⁻¹.
- DEF = √(gerilme² + kayma²); gerilme = ∂u/∂x − ∂v/∂y − v·tanφ/a, kayma = ∂v/∂x + ∂u/∂y + u·tanφ/a
  (küresel metrik terimleriyle; `yatay_deformasyon_hesapla`), s⁻¹.
- TI1 = |VWS| · DEF (Ellrod ve Knapp, 1992; `ti1_indeksi_hesapla`), s⁻². Risk eşiği 7e-7.
- Ri = g · Δθ · Δz / (θ̄ · (Δu² + Δv²)), θ = T·(1000/p)^(R/cp) (`richardson_sayisi_hesapla`).
  Ri < 0,25: Miles–Howard ölçütü, Kelvin–Helmholtz kararsızlığı.

Büyüklük sezgisi (tahtada işe yarar, hesap bu belgenin): 1 km'lik katmanda 10 m/s rüzgâr farkı
VWS = 0,01 s⁻¹ verir; DEF = 7e-5 s⁻¹ ise TI1 = 7e-7, yani tam eşikte.

Olası sorular:
- *TI1 neden tek başına zayıf (ROC-AUC 0,673)?* ERA5 0,25° (~25–30 km) ve saatlik; uçağın
  hissettiği türbülans ~100 m – 1 km ölçeğinde. Gösterge ancak türbülansa elverişli ortamı söyler.
- *Ri ile TI1 neden birleştirilmiyor?* Keyfi katsayıyla birleştirilmez; birleşim yalnız
  Sharman ve Pearson (2017) log-normal EDR eşlemesiyle (birleşik EDR, +0,013).

### 1.3 A*: maliyet ve sezgiselin kabul edilebilirliği

Kod: `rota/a_yildiz.py` (`_a_yildiz_ile_rota_ara`), `rota/risk_katmanlari.py`.
1. Graf: büyük daire üzerinde 41 ara nokta × yanal ofsetler (bacak açısı ≤ 30°, toplam sapma
   ≤ 400 km, aralık ≤ 20 km).
2. Sert kısıt: aktif SIGMET ve kısıtlı sahanın yasak düğüm/kenarları graftan **çıkarılır**. Yol yoksa
   `None`, sessiz ihlal yok.
3. Kenar maliyeti: gerçek rüzgârla uçuş süresi. Yumuşak kısıt: TI1 riskli düğüme girişte
   `TURBULANS_CEZASI_SANIYE` = 6 sa (21.600 sn) ceza.
4. Sezgisel: h = kalan büyük daire mesafesi / (1,8 × TAS).
5. Aday seçimi A*'tan sonra: sert kısıta uyanlar arasında önce en az riskli nokta, eşitlikte en
   az yakıt (ADR 0013, `sozluksel`).

Kabul edilebilirlik: kalan gerçek süre ≥ kalan mesafe / en büyük yer hızı. h, yer hızının 1,8 × TAS'ı
(TAS 230 m/s için ~185 m/s kuyruk rüzgârı) aşmayacağını varsayar; ceza negatif değildir ve h onu
saymaz. Böylece h gerçek kalan maliyeti aşmaz, A* bulduğu yolun en düşük maliyetli olduğunu garanti eder.

"Neden 6 saat?" (kurulun beklediği soru; aşağıdaki türetme bu belgenin, kalibrasyon değildir):
bacak açısı ≤ 30° olduğu için koridordaki her yol büyük dairenin en fazla 1/cos 30° ≈ 1,155 katıdır;
rüzgâr farkı ihmal edilirse en uzun sapma rota süresine ~%15,5 ekler. 6 saatlik cezayı tek bir
sapmanın "geri kazanması" için rotanın ~39 saat sürmesi gerekir. Yani 6 sa, "riskli bir düğümden
kaçınmak her sapmaya değer" kuralının büyük-M kodlamasıdır; yakıt–risk takası değildir. Takas
isteyen için ayrı kural vardır: `maliyet` (riskli dakika × 5 dk bedel, kalibre edilmedi).

### 1.4 Gün bloklu bootstrap ve eşleştirilmiş AUC farkı

Kod: `ml/degerlendirme.py` (`_bootstrap_ornekleri`, `bootstrap_guven_araligi`, `eslestirilmis_auc_farki`).
1. Örnekler gün bloklarına ayrılır.
2. 1000 tekrar: gün sayısı kadar gün **iadeli** çekilir; seçilen günün bütün PIREP'leri birlikte gelir.
3. Her tekrarda metrik; tek sınıflı tekrar (AUC tanımsız) atılır, geçerli tekrar sayısı yazılır.
4. %95 GA: %2,5 ve %97,5 yüzdelikleri.
5. Eşleştirilmiş fark: aynı tekrarda AUC(model) − AUC(TI1); p = 2 · min(P(fark ≤ 0), P(fark ≥ 0)).
6. Kapı (ADR 0004): fark ≥ 0,02 **ve** GA alt sınırı > 0.

Olası sorular:
- *Neden gün?* Aynı günün raporları aynı hava sistemini görür; satır satır örnekleme belirsizliği
  olduğundan dar gösterir (ADR 0003). Ölçüldü: rastgele 70/30 bölme ortalama AUC'yi değiştirmedi
  (−0,001, protokol §10.7); grupla bölmenin asıl işi güven aralığını dürüst tutmaktır.
- *Neden DeLong değil?* DeLong örneklerin bağımsızlığını varsayar; gün içi bağımlılık var.

## 2. Kendi kararlarım (taslak: kayıttaki iz; gerekçeyi kendi cümlenle yaz)

| Karar | Kayıttaki iz | Senin gerekçen |
|---|---|---|
| Araştırma sorusu: "ölçülmüş beceri + rota kararına taşıma" | README, `GIRIS.md` | |
| Kapsam yalnız CAT ve seyir safhası | `SINIRLAMALAR_VE_DERSLER.md` §1, NTSB (2021) | |
| TI1 eşiğinin veriden, önceden yazılmış kuralla seçilmesi (1-SE) | `ISLEM_GUNLUGU.md` 8 Ekim; `SONUCLAR.md` §0.2 | |
| PIREP `FL` alanının feet olduğunun tespiti ve etiket hattının yeniden kurulması | `SINIRLAMALAR_VE_DERSLER.md` §2.2 (1 Ekim) | |
| Güvenliğin SIGMET'e, TI1'in yumuşak kısıta verilmesi | PUE502 bulgusu, `KATKILAR.md` K6–K7 | |
| `sozluksel` seçim kuralının varsayılan kalması | ADR 0013 (28 Ekim) | |
| MADIS public veriyle devam (resmî başvuru yanıtsız) | ADR 0012, 5 Ekim | |
| Gece veri işinin durdurulması, sağlayıcı sınırlarına uyum | 28 Ekim; `VERI_KAYNAKLARI_VE_LISANSLAR.md` | |

Tespitin kimden geldiğini kayıt söylemiyorsa "birlikte" de; jüri dürüstlüğü ölçer.

## 3. Prova planı

- 2 prova, notsuz, kayıtlı (telefon yeterli), her biri ≤ 10 dk; sıra `PROJE_ISLEYISI.md` §13.
- Her provada 4 karttan biri tahtada çizilir (rastgele seç); "neden 6 saat?" ve "şu fonksiyonu anlat"
  sorusu mutlaka sorulsun (28 Ekim kurul raporundaki olası jüri soruları, 4. soru).
- Prova sonunda takılınan soruları bu belgeye ekle.

## 4. Danışmana e-posta taslağı (K-1; gönderim yazarda)

**Konu:** Bitirme projesi: yapay zekâ araç kullanımı beyanı

Sayın Dr. Titrek,

Bitirme raporumun Yöntem bölümünün sonuna aşağıdaki araç kullanımı beyanını koymayı planlıyorum.
Biçim (Yöntem sonunda tek paragraf mı, ayrı bölüm mü) ve içerik için görüşünüzü rica ederim.

[`docs/rapor/ARAC_KULLANIMI_BEYANI.md` "Paragraf" bölümünü buraya olduğu gibi yapıştırın; sayılar
göndermeden önce `python scripts/beyan_sayimlari.py --kontrol` ile güncellenir.]

Savunmada çekirdek modüllerin (eşleştirme, TI1/Ri, A* maliyet ve sezgiseli, gün bloklu bootstrap)
tasarımını ve doğrulamasını kendim anlatacağım.

Saygılarımla,
Tevfik Uner
