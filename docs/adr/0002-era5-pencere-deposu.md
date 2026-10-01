# 0002 — ML için indirilen ERA5'in silinmesi yerine pencere deposu

- Durum: Kabul edildi (2026-10-01)
- İlgili kod: `ml/ml_veri_hatti.py`, `ml/ozellik_deposu.py`, migration `d1f8a2c6e4b7`

## Bağlam

Gece işi, PIREP'leri gün/bölge gruplarıyla CDS'ten indirilen ERA5 dilimleriyle
eşleştirip özellikleri çıkarıyor ve dilimi siliyordu. 812 günlük arşivin tamamı
bu şekilde dolarsa, ileride eklenecek her yeni özellik (ince katman Richardson,
bağıl nem, frontogenez) tüm CDS indirmelerinin tekrarlanmasını gerektirir. Dilimler
ayrıca yalnızca 3 basınç seviyesi (300/250/200 hPa, ~1,3–1,6 km aralık) içeriyordu;
bu aralıkta Richardson sayısı hiç 0,25'in altına inmiyor.

## Karar

1. Depo açıkken (`ML_DEPO_KLASORU`) ML veri hattı CDS'ten 7 seviye (350, 300, 250,
   225, 200, 175, 150 hPa) ve bağıl nem dahil indirir (`ML_DEPO_BASINC_SEVIYELERI_HPA`,
   `ML_DEPO_EK_DEGISKENLER`). CDS isteği gün başına olduğu için istek sayısı değişmez;
   yalnızca istek boyutu büyür. İstek, pencereler tam olsun diye aynı gün içinde
   ±`ML_DEPO_PENCERE_SAAT` genişletilir.
2. Her PIREP'in çevresindeki pencere (±1°, ±1 saat, tüm seviyeler ve değişkenler)
   sıkıştırılmış NetCDF olarak gün bölümlemeli depoya (`YYYY/MM/DD/grup_<imza>.nc`)
   yazılır. PostgreSQL yalnızca katalogdur: `ml_ornekleri.pencere_dosyasi`.
3. Mevcut özellikler, kalibrasyonun (EDR katsayısı 0,40, TI1 eşikleri) geçerli
   kalması için yine yalnızca 300/250/200 hPa ve u/v/t alt kümesinden hesaplanır
   (`ozellik_deposu.ozellik_kupu`).
4. Depo yazılamazsa (disk, izin) özellikler yine kaydedilir; örnek penceresiz kalır
   ve `--eksikleri-kuyruga-al` ile sonradan yeniden indirilebilir.

## Doğrulama

- Gerçek THY322 ERA5 diliminde, depodan geri kurulan pencereden hesaplanan
  özellikler tam dilimden hesaplananlarla birebir aynı (`tests/test_ozellik_deposu.py`).
- Gerçek CDS'e 7 seviye + bağıl nem isteği denendi; `r` değişkeni ve 7 seviye
  ortak şemaya normalize ediliyor (`tests/test_era5_gercek_ag.py`, `-m ag`).
- Operasyonda: `turbulans-ml-depo --dogrula N` rastgele N örneği depodan yeniden
  hesaplayıp veritabanındaki değerlerle kıyaslar.

## Sonuçlar

- Yeni bir özellik CDS'e gitmeden depodan, gece işiyle aynı kodla hesaplanabilir.
- Disk: örnek başına sıkıştırmasız üst sınır ~27 KB (3 saat × 7 seviye × 9×9 hücre
  × 4 değişken × 4 bayt); zlib ile daha az. 80 bin örnekte en fazla ~2 GB.
  Docker'da `./ml_ozellik_deposu` bağlanır.
- Depo öncesi eşleşmiş örneklerin (ilk 16 gün) penceresi yoktur; isteğe bağlı olarak
  yeniden kuyruğa alınabilir (yaklaşık bir gecelik CDS bütçesi).
- 7 seviyeli fizik katmanına geçiş (ince katman Richardson, birleşik EDR) ayrı bir
  karardır; önce depodaki veriyle yeniden kalibrasyon gerekir.

## Değerlendirilen alternatifler

- Grup dilimlerinin tamamını saklamak: pencerelerden çok daha büyük; reddedildi.
- Özellik setini şimdi 7 seviyeye geçirmek: EDR katsayısı ve eşikler 3 seviyeyle
  kalibre edildi, karışık veri oluşurdu; ertelendi.
- Zarr: tek dosyada çok yazıcı ve kilit yönetimi gerektirirdi; grup başına küçük
  NetCDF dosyaları işçi süreçleriyle çakışmadan atomik yazılır.
