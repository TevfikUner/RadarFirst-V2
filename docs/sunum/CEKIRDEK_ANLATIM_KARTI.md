# Çekirdek anlatım kartı (tahta provası)

Savunmada jüri "bunu tahtada anlat" dediğinde kullanılacak dört modül (Madde 9, adım 7).
Her modül için: tahtaya ne çizilir, akış, formül, sayı, olası soru. Satır numaraları
2026-10-08 master'ına göredir. Sayıların kaynağı `docs/sonuclar/2026-10-07/SAYILAR.md`
(18 Ekim'de nihai paketle değişir).

**Prova yöntemi:** Kartı kapat, her modülü boş kâğıda 3 dakikada anlat, sonra karttaki
soruları sesli cevapla. Takıldığın yeri kodda aç (bağlantılar aşağıda). Dört modül
toplam 15 dakikayı geçmemeli.

---

## 1. İz–ERA5 eşleştirmesi (K1): `fizik/eslestirme.py`

**Tahtaya:** Düşey eksen basınç (hPa, yukarı azalır), üstünde 7 ERA5 seviyesi; uçak bir
nokta. Uçağın iki yanındaki seviyeler: `p_ust ≤ p ≤ p_alt`.

**Akış** ([rotayi_hava_durumuyla_eslestir](../../src/turbulans_radar/fizik/eslestirme.py#L248)):
1. İrtifa kaynağı: baro önce, yoksa geo ([L164](../../src/turbulans_radar/fizik/eslestirme.py#L164)).
   Seyirde altimetre 1013,25 hPa'da olduğu için baro irtifa doğrudan ISA basınç irtifasıdır.
2. ISA: `p = 1013,25 · (1 − 2,25577e-5 · h)^5,25588` (`fizik/birim_donusumleri.py`).
3. Kapsam maskesi ([L92](../../src/turbulans_radar/fizik/eslestirme.py#L92)): yatay ±0,125°,
   en yakın gerçek zaman adımına ≤3 saat, düşeyde küp seviyelerinden ≤50 hPa. Dışarıdakiler
   NaN kalır. Neden: xarray `sel(method="nearest")` mesafe sınırı koymaz; Teksas rotası
   Türkiye küpünün kenar hücresini sessizce alırdı.
4. Çevreleyen katman ([L197](../../src/turbulans_radar/fizik/eslestirme.py#L197)): iki seviyeyi
   tek vektörel `sel` ile al (nokta boyutu; döngü yok).
5. Katman kalınlığı hipsometrik: `Δz = R_d · T̄ / g · ln(p_alt / p_ust)`.
6. VWS, DEF, TI1, Ri hesapla (bölüm 2); kapsam dışını tekrar NaN'la.

**Sayı:** Demo THY322: 1614 noktanın 720'si 150–350 hPa içinde (kalkış/iniş TI1 almaz).

**Olası sorular:**
- *Neden GPS irtifası değil?* ERA5 seviyesi basınçtır; geo irtifa sıcaklığa göre sapar
  (THY322'de medyan 225 m). Baro irtifa ISA basıncına birebir karşılık gelir.
- *Neden enterpolasyon değil en yakın hücre?* Gerekçemiz: enterpolasyon 0,25° ve saatlik
  çözünürlüğün altındaki türbülans ölçeğini geri getirmez; en yakın hücre basit ve
  izlenebilir. Düşeyde VWS ve Ri uçağı çevreleyen katmandan, DEF en yakın seviyeden hesaplanır.
- *Uçak iki seviyenin dışındaysa?* Kenarda en yakın iki seviye; 50 hPa'dan uzaksa kapsam dışı.

---

## 2. Teşhis göstergeleri (K6'nın fiziği): `fizik/turbulans_indeksleri.py`

**Tahtaya:** Üç kutu: VWS (düşey), DEF (yatay), Ri (kararlılık) → TI1 = VWS × DEF.

**Formüller:**
- VWS = √(Δu² + Δv²) / Δz ([L103](../../src/turbulans_radar/fizik/turbulans_indeksleri.py#L103))
- DEF = √(gerilme² + kayma²), küresel metrik terimleriyle
  ([L65](../../src/turbulans_radar/fizik/turbulans_indeksleri.py#L65)):
  gerilme = ∂u/∂x − ∂v/∂y − v·tanφ/a, kayma = ∂v/∂x + ∂u/∂y + u·tanφ/a.
  Katı cisim dönmesinde DEF = 0 (testte var).
- TI1 = VWS × DEF (Ellrod ve Knapp, 1992) ([L119](../../src/turbulans_radar/fizik/turbulans_indeksleri.py#L119))
- θ = T · (1000/p)^(R/cp); Ri = g · Δθ · Δz / (θ̄ · (Δu² + Δv²))
  ([L175](../../src/turbulans_radar/fizik/turbulans_indeksleri.py#L175)); Ri < 0,25 Miles–Howard.
- Gösterge ölçeği: birleşik EDR (Sharman–Pearson log-normal eşleme), yoksa
  tanh(TI1 · 0,27 · 10⁶). Görsel ölçektir, EDR değildir.

**Sayılar:** TI1 ROC-AUC 0,680 [0,662–0,697] (7.815 PIREP, 80 gün); altın günler 0,673;
1/Ri 0,653; birleşik 0,687, TI1'den +0,014 [+0,007; +0,020]. Risk eşiği 7e-7:
POD 0,50, POFD 0,25. MADIS ölçülen EDR'de TI1 0,706 (6 gün).

**Olası sorular:**
- *0,68 iyi mi?* Rastgele 0,5. Orta düzey ayırt edicilik; tek başına güvenliğe yetmez.
  Bu yüzden SIGMET sert, TI1 yumuşak kısıt. Literatürdeki AUC'ler tam metinden
  okunamadığı için doğrudan kıyas yapılmadı (`ILGILI_CALISMALAR.md` §9).
- *Ri < 0,25 neden neredeyse hiç çıkmıyor?* 0,25° ERA5 ince katmanı çözemez; 1000
  PIREP'te en küçük Ri 0,32. Ri yine de sürekli özellik olarak ayırt edici.
- *Neden metrik terim?* Küresel koordinatta düz türev, yüksek enlemde DEF'i bozar.

---

## 3. A* maliyeti ve sezgisel (K7): `rota/rota_optimizasyonu.py`

**Tahtaya:** Büyük daire düz çizgi; her ara noktada ona dik k = −3…+3 düğüm (yanal ızgara);
bir SIGMET poligonu (düğümleri silinmiş) ve TI1 riskli bir bölge (cezalı düğümler).

**Graf** ([_YanalIzgara L316](../../src/turbulans_radar/rota/rota_optimizasyonu.py#L316)):
- Düğüm (i, k): i. büyük daire noktasından dik yönde k × aralık km. k = 0 hep aday.
- Bacak açısı ≤ 30°, ızgara aralığı ≤ 20 km, toplam sapma ≤ 400 km; uçlar sabit.
- Komşu ([L612](../../src/turbulans_radar/rota/rota_optimizasyonu.py#L612)): yalnız bir sonraki
  noktaya, seviye değişimi ≤ adım başına seviye (ani yanal sıçrama yok).

**Maliyet** ([L462](../../src/turbulans_radar/rota/rota_optimizasyonu.py#L462)):
`g(kenar) = mesafe / yer_hızı(TAS, rüzgâr, yön) + ceza(düğüm)`, birim saniye.
- Sert kısıt: SIGMET ve kısıtlı saha düğüm/kenarları grafdan silinir
  (`risk_katmanlari.py` `PoligonKisitKatmani`); varış zamanı ± belirsizlik
  (geçen sürenin %30'u + 5 dk) payıyla.
- Yumuşak kısıt: TI1 ≥ eşik düğümüne 6 saat ceza (`Ti1CezaKatmani`); Pareto seçenekleri
  için ceza 300/60/0 sn ile ayrı aramalar.
- Kapsam dışı düğüm elenir: veri yoksa "türbülans yok" varsayılmaz.

**Sezgisel** ([L470](../../src/turbulans_radar/rota/rota_optimizasyonu.py#L470)):
`h = kalan büyük daire mesafesi / (1,8 · TAS)`.
- Kabul edilebilir: hiçbir yol büyük daireden kısa değil, yer hızı TAS + kuyruk rüzgârını
  aşmaz (tipik 240 m/s TAS için 0,8 · TAS ≈ 190 m/s kuyruk rüzgârı; jet akımından büyük),
  ceza ≥ 0.
- Tutarlı: üçgen eşitsizliği; bu yüzden kapalı kümeyle optimal.

**Sonra:** Seçilen yol rüzgârla yeniden zamanlanır ve son kez sert kısıtlarla kontrol edilir;
güvenli yol yoksa öneri verilmez (`None`, sessiz ihlal yok). Seviye alternatifleri yasal FL
(yarım daire kuralı) ve tırmanma yakıt bedeliyle ayrıca karşılaştırılır.

**Sayılar:** Backtest THY322 15 Oca 2019 riskli oran gerçek 0,24 / büyük daire 0,39 / A* 0,02.
Rota yanıtı şarjda 0,03–0,45 sn.

**Olası sorular:**
- *Neden Dijkstra değil?* Aynı optimal sonuç; sezgisel aramayı hedefe yönlendirir.
- *Ceza neden 6 saat?* Hiçbir sapmanın süresi bunu aşmasın diye: riskli düğümden kaçış
  mümkünse her zaman seçilir; değilse en az riskli yol. Bu bir öncelik sırası, kalibre
  edilmiş bir maliyet değil.
- *Rüzgâr neden düğümde değil kenarda?* Kenar maliyeti varış düğümündeki rüzgârı kullanır;
  20 km'lik bacakta fark küçük, nominal zamanla tek okuma.
- *Yasak alan ızgarayı keserse?* Yol yoksa `None`; arayüz "öneri yok" der.

---

## 4. Değerlendirme istatistiği (K6): `ml/degerlendirme.py`

**Tahtaya:** Takvim; günler blok. Bootstrap: günleri iadeli seç, AUC'yi yeniden hesapla,
1000 kez; %2,5 ve %97,5 yüzdelikleri.

**Akış:**
1. Gün bloku bootstrap ([L93](../../src/turbulans_radar/ml/degerlendirme.py#L93)): aynı gündeki
   PIREP'ler bağımlı (aynı hava sistemi); satır değil gün örneklenir, GA daralmaz.
2. GA ([L117](../../src/turbulans_radar/ml/degerlendirme.py#L117)): yüzdelik yöntemi; tek
   sınıflı tekrar sayılmaz.
3. Eşleştirilmiş fark ([L138](../../src/turbulans_radar/ml/degerlendirme.py#L138)): model ve TI1
   aynı örneklemde; p = 2 · min(P(fark ≤ 0), P(fark ≥ 0)).
4. Peirce eşiği ([L173](../../src/turbulans_radar/ml/degerlendirme.py#L173)): POD − POFD en
   yüksek; yalnız eğitim günlerinde seçilir, teste olduğu gibi uygulanır.
5. 1-SE eşiği ([L185](../../src/turbulans_radar/ml/degerlendirme.py#L185)): Peirce max'ın bir
   standart hatası içindeki en tutucu eşik → 7,06e-7 (config 7e-7).

**Protokol:** 80 günden 16 altın test günü rastgele (tohum 0) donduruldu, eğitime girmez;
model gün gruplu CV ve 1-SE kuralıyla seçilir; kapı: TI1'den fark ≥ 0,02 ve GA alt > 0.

**Sayılar:** LR 0,681 vs TI1 0,673, fark +0,008 [−0,006; +0,022], p 0,27 → kapı geçilmedi,
model devreye girmez. Birleşik EDR farkı anlamlı (p < 0,001).

**Olası sorular:**
- *Neden satır bootstrap değil?* Günlük korelasyon GA'yı yapay daraltır; gün birimdir.
- *Neden altın günler rastgele, son günler değil?* Son günler tek bir mevsim dilimidir;
  rastgele günler tüm dönemi temsil eder. Hafta ve ay gruplu CV duyarlılığında AUC
  değişmedi (`docs/rapor/SONUCLAR.md` §2.3).
- *PIREP yanlılığı?* Pozitif oranı 0,52; pilotlar türbülansı daha çok raporlar. AUC sıralama
  ölçtüğü için taban orandan etkilenmez ama POD/POFD gerçek uçuştaki oranı yansıtmaz.
- *Model neden TI1'i geçemedi?* Kanıtlanmış bir neden yok. Olası açıklama (yorum):
  model aynı 0,25° ERA5 alanlarından türetilen özelliklerle öğreniyor, ölçek sınırı
  özellik eklemekle aşılmıyor. Olumsuz sonuç olduğu gibi raporlandı.
