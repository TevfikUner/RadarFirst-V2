# Demo Senaryosu (E8)

Jüri sunumundaki canlı demo ve yedek video için adım adım akış. Demo, depodaki
demo paketiyle (THY322, 15 Ocak 2019, gerçek OpenSky izi + ERA5 dilimi) **ağ
bağlantısı ve kimlik bilgisi olmadan** çalışır. Aşağıdaki tüm sayılar bu paketle
1 Ekim 2026'da alınmış gerçek çıktılardır; ekran görüntüleri `ekranlar/`
klasöründedir ve `turbulans-demo-ekranlari` ile yeniden üretilir.

Sistem sertifikalı EDR üretmez; karar destek aracıdır. Demo boyunca bu cümle
en az bir kez söylenmelidir.

## 1. Hazırlık

### Sunumdan bir gün önce

1. Demo için geliştirme klasöründen **ayrı** bir klon kullanın (gerçek `.env`
   dosyanız ezilmesin):

   ```bash
   git clone <depo-adresi> turbulans-demo && cd turbulans-demo
   cp .env.demo .env
   ```

2. Geliştirme yığını aynı portları (8000, 5432) kullanır. Geliştirme klasöründe
   `docker compose stop` ile durdurun. Gece işi o gece çalışmaz; sunumdan
   sonra `docker compose start` ile geri açın.
3. Demo yığınını bir kez kurup deneyin (ilk derleme internet ister, sonrası istemez):

   ```bash
   docker compose --profile demo up -d --build
   docker compose logs demo          # "ÖZET: THY322 / 2019-01-15" görünmeli
   ```

4. Prova: aşağıdaki komut demo adımlarını tarayıcıda gerçekten tıklar ve ekran
   görüntülerini üretir. Hata verirse sunumdan önce düzeltilecek bir şey vardır.

   ```bash
   TURBULANS_API_ANAHTARI=demo-yerel-yonetici turbulans-demo-ekranlari --klasor /tmp/prova
   ```

5. Yedek videoyu kaydedin (bkz. §4) ve sunum bilgisayarına kopyalayın.

### Sunumdan 15 dakika önce

- Wi-Fi'yi kapatın: demonun ağsız çalıştığı jüriye bir kanıt olarak da söylenebilir.
- `docker compose --profile demo up -d` (veritabanı hacmi korunur, THY322 zaten kayıtlı).
- Tarayıcıda iki sekme açın: `http://localhost:8000/harita/harita3d.html` ve
  `http://localhost:8000/harita/ucus_simulasyonu.html`. Anahtar alanına
  `demo-yerel-yonetici` yazın.
- Ekran ölçeği %100, tarayıcı tam ekran (F11). Yedek video masaüstünde.

## 2. Canlı demo akışı (≈ 6 dakika)

| # | Süre | Ekran | Yapılacak | Söylenecek |
|---|---|---|---|---|
| 1 | 0:30 | Terminal | `docker compose ps` (db, api, worker sağlıklı); Wi-Fi kapalı | "Sistem dizüstünde, internet bağlantısı yok. Veri, depoyla gelen gerçek bir uçuş ve gerçek ERA5 dilimi." |
| 2 | 1:30 | 3B harita | Uçuş `THY322`, tarih `2019-01-15`, **Yükle**. Zaman kaydırıcısını baştan sona sürükleyin | "OpenSky'dan alınmış 1614 gerçek ADS-B noktası. Her nokta, uçağın o anki barometrik irtifasına karşılık gelen basınç seviyesinde ERA5 rüzgarıyla eşleşti ve Ellrod TI1 hesaplandı. Tırmanışın alt kısmı 150–350 hPa dışında kaldığı için 1614 noktanın 720'si hesaplandı, gerisi 'veri yok': sistem kapsamadığı yeri tahmin etmiyor. İzdeki ~1 saatlik boşlukta OpenSky'da kayıt yok; sistem bu boşluğu doldurmuyor." |
| 3 | 0:30 | 3B harita, sol panel | Model paneli ve lejanttaki TI1 notunu gösterin | "TI1'in tek başına güvenilirliği kanıtlanmadı: seyir irtifasındaki 1600 PIREP'te ROC-AUC 0,69. Bu not ekranda her zaman duruyor." |
| 4 | 1:30 | Rota simülasyonu | 41.0, 29.0 → 40.5, 43.5; 36000 ft; 15.01.2019 20:00; A320; **Simüle Et** | "Büyük daire rotasında 4 riskli TI1 noktası var. A* 53 km yanal sapmayla hepsinden kaçınıyor; bedeli 1,6 dakika ve %2 yakıt. Sistem tasarrufu değil güvenlik bedelini gösteriyor." (Ekran: `ekranlar/02_…`) |
| 5 | 1:00 | Rota simülasyonu | 38.35, 38.31 → 36.34, 43.13 (Malatya → Musul); **Simüle Et** | "Bu kez sert kısıt: normal rota örnek kısıtlı sahaya 11 noktada giriyor, önerilen rota hiç girmiyor. Bu bölge ERA5 diliminin dışında; sistem rüzgarı hesaba katamadığını açıkça söylüyor. SIGMET de aynı sert kısıt mekanizmasıyla çalışıyor." (Ekran: `ekranlar/03_…`) |
| 6 | 0:30 | Slayt | ML ve doğrulama sonuçları slaytına geçin | "Model sonuçlarını canlı değil, ölçülmüş haliyle gösteriyorum. Sistem sertifikalı EDR üretmez; karar destek aracıdır." |

Demo paketinde olmayanlar, slaytla gösterilir:

- **ML modeli:** Demo yığınında model yok; panel "Model henüz eğitilmedi" der
  (doğru davranış). Eğitim sonuçları (güven aralıkları, konformal kapsama)
  geliştirme yığınından slayta konur.
- **Canlı SIGMET:** AWC'den çekilir, ağ ister. Ağ varsa
  `POST /api/v1/sigmet/guncelle` sonrası aynı simülasyonda gösterilebilir.
- **Swagger (`/docs`):** Arayüz dosyaları CDN'den yüklendiği için ağ ister.
  Ağsız demoda `openapi.json` ya da Postman koleksiyonu gösterilir.
- **Sanal PIREP (M6):** Demo izi tırmanış ağırlıklı olduğu için olay üretmez (doğru
  davranış). Yöntem ve doğrulama durumu slaytla anlatılır.

## 3. Bir şey ters giderse

| Belirti | Hızlı çözüm | Olmazsa |
|---|---|---|
| Harita boş, "API anahtarı" hatası | Anahtar alanına `demo-yerel-yonetici` yazıp tekrar **Yükle** | Yedek videoya geç |
| "Uçuş bulunamadı" | `docker compose run --rm demo` (analizi yeniden yazar, ~5 sn) | Yedek video |
| Simülasyon dönmüyor | Sayfayı yenile, anahtar alanından **Tab** ile çık (uçak listesi yüklenir) | `ekranlar/` görüntüleri |
| API açılmıyor | `docker compose --profile demo up -d`; `docker compose logs api` | Yedek video |
| 3B görüntü takılıyor | Tarayıcıda donanım hızlandırma açık mı; sekmeyi kapatıp aç | `ekranlar/` görüntüleri |

## 4. Yedek video (3–5 dakika)

Kayıt: ekran kaydedici (ör. OBS ya da Windows `Win+Alt+R`), 1920×1080, mikrofonla.
Her sahne yukarıdaki canlı akışla aynıdır; anlatım metni:

1. **(0:00–0:20) Giriş.** "Türbülans Radar; gerçek uçuş izlerini ERA5 rüzgarıyla
   eşleştirip türbülans riskini hesaplayan ve kaçınan rotayı öneren bir karar destek
   sistemi. Bu kayıt internet bağlantısı olmadan, depoyla gelen veriyle alındı."
2. **(0:20–1:30) Uçuş analizi.** 3B harita, THY322 yükleme, zaman kaydırıcısı;
   §2 adım 2–3 metni.
3. **(1:30–2:40) Türbülanstan kaçınma.** §2 adım 4.
4. **(2:40–3:30) Sert kısıt.** §2 adım 5.
5. **(3:30–4:10) Mimari ve kapanış.** `docs/mimari.md` konteyner diyagramı ekranda:
   "API, işçi ve PostgreSQL ayrı servisler; uzun işler kuyrukta, gece ML veri hattı
   kendiliğinden çalışıyor. Sistem sertifikalı EDR üretmez; karar destek aracıdır."

Videoyu sunum bilgisayarına ve bir USB belleğe koyun.

## 5. Kabul kontrolü (geliştirme planı E8)

- [ ] Ağ kapalıyken §2 adım 1–5 baştan sona hatasız (prova komutu §1.4 geçti).
- [ ] Yedek video kaydedildi, 3–5 dakika.
- [ ] Poster (`poster.html`) yazdırıldı ya da PDF'e çevrildi.
- [ ] Sunum akışı (`SUNUM_AKISI.md`) slaytlara aktarıldı; ML sonuç slaytı ilk gerçek
      eğitimden sonra dolduruldu.
