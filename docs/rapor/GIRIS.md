# Giriş (rapor bölümü)

## 1. Problem

Türbülans, tarifeli hava taşımacılığında yaralanmalı kazaların başlıca nedenlerindendir. ABD'de
2009–2018 arasında Part 121 (tarifeli hava yolu) kazalarının üçte birinden fazlası türbülansla
ilgiliydi; çoğunda uçak hasar görmedi ama en az bir kişi ağır yaralandı, en sık yaralananlar
kabin ekibiydi (NTSB, 2021). Aynı rapora göre bu kazaların yaklaşık yarısı alçalma ve yaklaşmada,
%60'ı 20.000 ft altında oldu; bu çalışma yalnız seyir safhasını (FL280–FL420) ele aldığı için o
kazaların hepsini hedeflemez.

Seyir irtifasındaki türbülansın önemli bir kısmı bulut dışındadır (açık hava türbülansı, CAT) ve
hava radarında görünmez. Elde iki tür bilgi vardır: sayısal hava tahmini (NWP) ve reanaliz
alanlarından türetilen teşhis indeksleri (Ellrod ve Knapp, 1992; Sharman vd., 2006) ve uçaktan
gelen gözlemler. Gözlemlerin en yaygını pilot raporudur (PIREP): gönüllü, gecikmeli, konumu ve
zamanı kabadır, şiddeti özneldir (Schwartz, 1996). Uçağın ölçtüğü EDR nesneldir ama büyük ölçüde
havayollarının kapalı verisidir; herkese açık kısmı (NOAA MADIS) seyrek ve ABD ağırlıklıdır.

Operasyonel ürünler (GTG, WAFS) türbülans alanı üretir ve yerinde EDR ile doğrulanır. Bir
dispeçerin elinde ise bu alanı belirli bir uçuşun izine bağlayan, becerisinin sınırını söyleyen
ve rota kararına bu sınırla giren açık bir araç yoktur.

## 2. Araştırma sorusu

Yalnız açık veriyle (OpenSky ADS-B, ERA5, AWC SIGMET, IEM PIREP) gerçek bir uçuş izinde seyir
türbülansı riski hangi ölçülmüş beceriyle gösterilebilir ve bu sınır rota kararına nasıl
taşınmalıdır?

Soru iki parçalıdır. Birincisi bir ölçme sorusudur: göstergenin ve modelin becerisi, modelin
görmediği günlerde, bağımsız etiketle ve belirsizliğiyle birlikte nedir? İkincisi bir tasarım
sorusudur: becerisi sınırlı bir gösterge rota kararında hangi rolü almalıdır?

## 3. Kapsam

- **Türbülans türü:** yalnız açık hava türbülansı. Konvektif, bulut içi, dağ dalgası ve iz
  türbülansı kapsam dışıdır.
- **Uçuş safhası:** yalnız seyir (ToC–ToD, FL280 üstü). Kalkış, tırmanış, alçalış, SID/STAR ve
  yaklaşma kapsam dışıdır.
- **Doğrulama bölgesi:** etiketler (IEM PIREP, MADIS EDR) ABD hava sahasındandır. Rota ve arayüz
  Türkiye'de çalışır ama oradaki beceri ölçülmedi.
- **Kullanım sınıfı:** tavsiye niteliğinde karar destek. Sistem sertifikalı değildir, EFB onayı
  yoktur; karar yetkisi pilotta ve dispeçerdedir.

## 4. Yaklaşım ve raporun düzeni

Çalışma önce ölçer, sonra karar verir. TI1 risk eşiği, model aktivasyon kapısı ve test günleri
sonuçlar görülmeden önce yazılı kurallara bağlandı (deney protokolü; ADR 0003, 0004). Sonuç ne
çıktıysa raporlandı; olumsuz ara bulgular da (örneğin 7 Ekim ön paketinde lojistik regresyonun
TI1'i geçememesi) sonuçlar bölümündedir.

Bölüm 2 ilgili çalışmaları, Bölüm 3 veri, gösterge, model, doğrulama ve rota yöntemini anlatır.
Bölüm 4 ölçülen sonuçları, Bölüm 5 katkıları ve her birinin sınırını, Bölüm 6 sınırlamaları ve
öğrenilen dersleri verir. Bölüm 7 sonucu özetler ve gelecek çalışmayı sıralar. Raporlanan her
sayı depodaki komutla yeniden üretilebilen sonuç paketlerinden (`docs/sonuclar/`) alınmıştır.

Çıktılar sertifikalı EDR değildir; sistem operasyonel karar aracı değil, karar destek aracıdır.
