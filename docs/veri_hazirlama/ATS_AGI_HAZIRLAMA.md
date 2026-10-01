# AIP Türkiye'den Veri Hazırlama: ATS Ağı ve Kısıtlı Sahalar

Hoca önerisi 1 ve 2 (Doç. Dr. Fulya Aybek Çetek) için gereken gerçek veriyi elle
hazırlama rehberi. Kod hazır ve sentetik verilerle test edildi; **gerçek veri
depoda yoktur ve uydurulmamıştır.**

> Bölüm numaraları AIP Türkiye ENR 0.6'dan (AIRAC AMDT 03/26) doğrulandı:
> ENR 3.1/3.2 ATS yolları, ENR 4.4 önemli noktalar, ENR 5.1 P/R/D, ENR 5.2
> askerî sahalar, ENR 6.3 FRA haritası. AIP verisinin yeniden dağıtım izni
> doğrulanmadığı için hazırladığınız dosyalar depoya konmaz: `ats_verisi/`
> `.gitignore`'dadır.

## 0. Otomatik hazırlama (önerilen)

Doğrudan AIP Türkiye'den, her AIRAC döngüsünde (28 günde bir) tekrarlanabilir.
Her komut DHMİ'ye yalnızca bir istek atar:

```bash
pip install -r requirements-dev.txt          # pypdf
turbulans-aip-ats --indir                     # ENR 4.4 -> ats_verisi/ats_agi.json (FRA ağı)
turbulans-aip-sahalar --indir                 # ENR 5.1 -> ats_verisi/aip_enr51.geojson
turbulans-kisitli-saha ice-aktar ats_verisi/aip_enr51.geojson --kaynak aip_enr51
```

- **ENR 4.4:** Tüm önemli noktalar koordinatları ve FRA rolleriyle alınır. FRA
  noktaları arasında 200 km'ye kadar doğrudan (DCT) kenarlar kurulur; alt sınır
  FL305'tir. Bu sınırlar `--dct-km` ve `--alt-fl` ile değiştirilebilir.
- **ENR 5.1:** Yalnızca biçimi kesin olan sahalar alınır. Belirsiz olanlar
  gerekçesiyle "ATLANDI" diye listelenir; bunları aşağıdaki §2 biçimiyle elle
  ekleyin.
  - 2 Ekim 2026'da 77 saha alındı, 8'i atlandı: LTP1, LTR8, LTR9, LTR43, LTR44,
    LTD31, LTD33, LTD40.
- **Sınırlar:**
  - Klasik ve RNAV hava yolları (ENR 3.1/3.2) bu araçlarla kurulmaz. FL305
    altında ATS modu rota bulamaz ve bunu açıkça söyler.
  - "Activated by NOTAM" sahalar, NOTAM verisi olmadığı için sürekli aktif
    sayılır (güvenli taraf).

## 1. ATS yolu ağı (`ats_verisi/ats_agi.json`)

### Kaynak
- **Hava yolları:** AIP Türkiye ENR 3.1 (klasik) ve ENR 3.2 (RNAV) ATS yolları. Her yol için nokta sırası,
  alt/üst sınır (FL) ve varsa tek yön kısıtı.
- **Nokta koordinatları:** ENR 4.4 (önemli noktaların adı ve koordinatı). VOR/NDB
  gibi seyrüsefer yardımcıları ENR 4.1'de.
- **Serbest Rota Sahası (FRA):** Türkiye'de 27 Kasım 2025'ten beri FL305 ve
  üzerinde uygulanıyor. FRA rolleri ENR 4.4'te, harita ENR 6.3'te. Güncel
  uygulama saatlerini AIP'ten kontrol edin.

### Kapsam önerisi
Tüm ağ yerine, demo senaryolarının geçtiği 2–3 koridor yeterli: örneğin İstanbul
→ Ankara → Doğu Anadolu ve Malatya → güneydoğu. 20–60 nokta ve 5–15 yol, elle
hazırlanabilir bir boyuttur.

### Biçim
```json
{
  "kaynak": "AIP Türkiye, AIRAC <numara>, ENR 3/4.4 (elle hazırlandı, <tarih>)",
  "noktalar": [
    {"ad": "<NOKTA1>", "enlem": 0.0, "boylam": 0.0}
  ],
  "yollar": [
    {"ad": "<YOL>", "noktalar": ["<NOKTA1>", "<NOKTA2>", "<NOKTA3>"],
     "alt_fl": 245, "ust_fl": 460, "yon": "cift"}
  ],
  "fra": {"noktalar": ["<NOKTA1>", "<NOKTA3>"], "dct_maks_km": 400, "alt_fl": 245, "ust_fl": 660}
}
```
- **Koordinatlar** ondalık derece. AIP'teki `DDMMSS.ssN DDDMMSS.ssE` biçimini
  çevirin: derece + dakika/60 + saniye/3600; güney ve batı negatif.
- **Uçuş seviyesi** alanları FL cinsindendir (245 = FL245). Sınır yoksa `null`.
- **`yon`** üç değer alır:
  - `cift`: iki yön
  - `ileri`: listedeki sıra yönünde
  - `geri`: ters yönde

### Doğrulama ve kullanma
```bash
python -c "from turbulans_radar.rota.hava_yolu_agi import agi_yukle; a = agi_yukle(); print(a.kaynak, len(a.noktalar))"
```
- Hatalı bir dosya hangi satırda ne sorun olduğunu söyler; örneğin `yollar[3] (UL333): tanımsız nokta(lar): XXXXX`.
- Docker'da `./ats_verisi` klasörü konteynere salt okunur bağlanır; dosyayı
  değiştirince API'yi yeniden başlatmak gerekmez.
- Arayüzde "Arama uzayı → ATS yolları / FRA" seçilir. API'de
  `"arama_uzayi": "ats"` kullanılır.

### Sistem bu veriyi nasıl kullanır
- ToC ve ToD, ağdaki en yakın `ATS_AGI_BAGLANTI_SAYISI` (3) noktaya, en fazla
  `ATS_AGI_BAGLANTI_KM` (150 km) mesafeyle doğrudan (DCT) bağlanır.
- Seyir irtifasının `alt_fl`–`ust_fl` dışında kalan segmentler kullanılmaz.
- Risk kontrolünün segment ortasındaki bir SIGMET'i ya da türbülansı atlamaması
  için uzun segmentler 60 km'lik parçalara bölünür (`ATS_AGI_ARA_NOKTA_KM`).
- Normal rota, ağdaki en hızlı yoldur (rüzgar dahil). Optimize rota, aynı ağda
  SIGMET, kısıtlı saha ve TI1 kısıtlarıyla bulunan yoldur. Yanıttaki `ats`
  alanı, rotayı uçuş planı biçimine yakın verir: `ToC DCT ABCDE UL123 FGHIJ DCT ToD`.
- Yanıttaki `buyuk_daire_km` ile ATS rotasının mesafesi karşılaştırılarak
  "ATS yolu kısıtının bedeli" raporlanabilir.

## 2. Yasak, tahditli ve askerî sahalar (GeoJSON)

### Kaynak
- **ENR 5.1:** Yasak (P), tahditli (R) ve tehlikeli (D) sahalar.
- **ENR 5.2:** Askerî tatbikat ve eğitim sahaları.
- **Aktivasyonlar:** NOTAM ile duyurulur.

### Biçim
`turbulans-kisitli-saha ice-aktar sahalar.geojson --kaynak aip` ya da
`POST /api/v1/kisitli-sahalar?kaynak=aip`.
```json
{"type": "FeatureCollection", "features": [{
  "type": "Feature",
  "properties": {
    "kimlik": "<AIP-kimliği>", "ad": "<saha adı>", "tur": "KISITLI",
    "taban_ft": 0, "tavan_ft": 24500,
    "haftalik_takvim": [{"gunler": ["PZT", "SAL", "CAR", "PER", "CUM"], "baslangic": "06:00", "bitis": "15:00"}],
    "aciklama": "AIP ENR 5.1, AIRAC <numara>"
  },
  "geometry": {"type": "Polygon", "coordinates": [[[0.0, 0.0], [0.0, 0.0], [0.0, 0.0], [0.0, 0.0]]]}
}]}
```
- **`tur`:** `YASAK` (P), `KISITLI` (R), `TEHLIKELI` (D), `GECICI` (TRA/TSA,
  NOTAM'lı) ya da `CATISMA`.
- **Sınırlar:** feet cinsinden. AIP'te FL verilmişse FL × 100. AGL referanslı
  sınırlar için arazi yüksekliğini ekleyin ya da muhafazakâr bir pay bırakın.
- **Aktif zamanlar** üç şekilde verilir:
  - AIP'teki "MON-FRI 0600-1500" türü saatler `haftalik_takvim` alanına (UTC) girer.
  - NOTAM ile duyurulan aktivasyonlar `aktif_araliklar` alanına girer:
    `[{"baslangic": "2026-10-05T08:00Z", "bitis": "2026-10-05T12:00Z"}]`.
  - "BY NOTAM" sahalarında NOTAM bilinmiyorsa iki alanı da boş bırakın; saha
    her zaman aktif sayılır (muhafazakâr).
- **Önce test:** Gerçek veriyi yüklemeden önce `.env`'de
  `KISITLI_SAHA_ORNEK_VERI_YUKLE=false` yapın ve örnek Suriye/Irak verisini silin:
  `DELETE /api/v1/kisitli-sahalar/ornek:ornek-suriye` ve `.../ornek:ornek-irak`.
