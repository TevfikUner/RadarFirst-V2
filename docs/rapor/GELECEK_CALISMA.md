# Sonuç ve gelecek çalışma (rapor bölümü)

## 1. Sonuç

Araştırma sorusunun ölçme kısmına cevap şudur: yalnız açık veriyle, gerçek uçuş izinin
barometrik seviyesinde hesaplanan TI1 seyir türbülansını sınırlı bir beceriyle ayırt eder
(15.940 PIREP'te ROC-AUC 0,673). PIREP'lerle eğitilen model bu sınırı küçük ama tutarlı bir
farkla aşar: önceden yazılmış protokolle, modelin görmediği 79 yeni günde +0,027
[+0,018; +0,035]; 18 Ekim altın günlerinde +0,033 [+0,018; +0,049]. Fark iki bağımsız ölçümde
benzerdir, ama mutlak beceri ROC-AUC 0,69 civarındadır.

Tasarım kısmına cevap bu ölçümden çıkar: becerisi bu düzeyde olan bir gösterge rota kararında
güvenlik garantisi veremez. Bu yüzden güvenlik SIGMET ve kısıtlı saha sert kısıtına dayanır; TI1
yumuşak kısıttır, yasaklamaz ama adaylar arasında seçimde yakıttan önce gelir. Bu ayrım ürünün
davranışına taşındı: her yanıt güvenilirlik notu, üretim bilgisi ve gerektiğinde "belirsiz" ya da
"kapsam dışı" durumu taşır. Bağımsız rota backtest'i (NE-ABD) önerilen rotaların PIREP tüpündeki
orta ve üstü payını 0,71 [0,58; 0,90] oranına indirdiğini gösterir; tek bölge ve simüle rota
olduğu için bu bir operasyonel kazanç iddiası değildir.

Çıktılar sertifikalı EDR değildir; sistem operasyonel karar aracı değil, karar destek aracıdır.

## 2. Gelecek çalışma

Ürün yönü: önce ölçmek, sonra tahmin etmek. Doğrulama karnesi olmayan bir tahmin ürünü eklenmez.

1. **Türkiye ve Avrupa için nesnel etiket.** Bugünkü beceri yalnız ABD verisiyle ölçüldü; MADIS'te
   Türkiye için ölçüm yok. Aday yollar MGM ve IATA Turbulence Aware'dır
   (`docs/fizibilite/TURKIYE_ETIKET_KAYNAKLARI.md`). Etiket gelene kadar Türkiye TURB SIGMET'leri
   ile TI1'in küçük örneklemli kıyası ilk kanıt olabilir. Transfer öğrenme (Zhu vd., 2026) etiket
   yokluğu için bir yoldur.
2. **Doğrulama karnesi.** Kaynak başına (PIREP, MADIS EDR) dönemsel ROC-AUC, PR-AUC, POD/POFD;
   dondurmadan sonra toplanan yeni günlerde düzenli üretim.
3. **Birleşik EDR ya da ML'in rota cezasına girmesi.** Birleşik EDR, ızgara düzeyinde de TI1'den iyi
   (POD–alan AUC +0,024 [+0,013; +0,037], protokol §13.5); eşik seçimi ve GFS doğrulaması önce
   yapılır.
4. **Tahmin ufku ve topluluk.** GFS TI1'inin riskli alanları 24 saatte bile yarı yarıya kayıyor
   (f000'da riskli olanların f024'te %57'si riskli); ERA5'e karşı kıyas ve GEFS topluluk olasılığı
   48 saatlik `ongoru_belirsiz` sınırının kalibrasyonu için gereklidir.
5. **Tırmanma ve alçalma.** Kazaların yarısı alçak irtifada; 400–850 hPa, CAPE ve arazi bilgisiyle
   seyir modelinden ayrı bir model ve ayrı etiketler (konvektif, dağ dalgası, rüzgâr kesmesi).
6. **Kullanılabilirlik.** Dispeçer ve pilotlarla kullanılabilirlik oturumları; geri bildirim kaydı
   bugün yalnız kullanıcı algısını ölçer.
