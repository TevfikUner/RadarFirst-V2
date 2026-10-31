# Özet (rapor bölümü)

Seyir irtifasındaki açık hava türbülansı (CAT) radarda görünmez; pilot raporu (PIREP) gönüllü,
gecikmeli ve konumu kabadır. Bu çalışma, yalnız açık veriyle (OpenSky ADS-B, Copernicus ERA5,
NOAA GFS, AWC SIGMET, IEM PIREP, NOAA MADIS) gerçek bir uçuş izinde seyir türbülansı riskinin
hangi ölçülmüş beceriyle gösterilebileceğini ve bu sınırın rota kararına nasıl taşınması
gerektiğini sorar. Türbülans Radar, ADS-B izinin her noktasını barometrik irtifasına karşılık
gelen basınç seviyesinde hava verisiyle eşleştirir, Ellrod TI1 ve birleşik EDR göstergelerini
hesaplar, PIREP'lerle eğitilen kapılı bir ML modeli çalıştırır ve aktif SIGMET'leri sert, TI1'i
yumuşak kısıt alan bir A* ile kaçınma rotası önerir.

Beceri sınırlıdır. TI1, 163 günde 15.940 seyir PIREP'inde ROC-AUC 0,673 [0,661–0,684] verir;
altın test günlerinde risk eşiğinde (7e-7) yakalama 0,50, yanlış alarm 0,25'tir. Önceden
yazılmış protokolle, modelin görmediği 79 yeni günde (7.769 PIREP) model TI1'i +0,027
[+0,018; +0,035] farkla geçer (0,685'e karşı 0,658); bu fark 18 Ekim altın günlerindeki
farka (+0,033) yakındır. Model yine de ROC-AUC 0,69 civarında kaldığı için güvenlik SIGMET sert
kısıtına dayanır; TI1 yasaklamaz, adaylar arasında seçimde yakıttan önce gelir. Bağımsız rota
backtest'inde (NE-ABD, A*'ın saptığı 908 rota) PIREP tüpündeki orta ve üstü payının oranı 0,71
[0,58; 0,90] çıkmıştır. Doğrulama ABD verisiyledir; Türkiye için beceri ölçülmemiştir.

Çıktılar sertifikalı EDR değildir; sistem operasyonel karar aracı değil, karar destek aracıdır.

**Anahtar sözcükler:** açık hava türbülansı, Ellrod TI1, ERA5, ADS-B, PIREP, rota optimizasyonu,
karar destek sistemi.
