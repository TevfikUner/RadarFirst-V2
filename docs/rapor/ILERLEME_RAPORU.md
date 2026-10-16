# Türbülans Tespit ve Rota Optimizasyonu — Proje İlerleme Raporu

**Hazırlayan:** Tevfik ÜNER  
**Danışman:** Fatih TİTREK  
**Son güncelleme:** 16 Ekim 2026

**Proje kısaca.** Uçaklar yüksek irtifada, bulutsuz açık havada da türbülansa girebilir ve
bu türbülans radarda görünmez. Bu projede herkese açık verileri (uçuş kayıtları, hava durumu
verileri, resmî hava uyarıları ve pilotların verdiği raporlar) kullanarak bir uçuşun rotası
boyunca türbülans riskini gösteren ve gerektiğinde daha güvenli bir rota öneren bir yazılım
geliştiriyorum. Sistemin verdiği değerler resmî/sertifikalı türbülans ölçümü (EDR) değildir;
sistem karar vermez, karar verene yardımcı olan bir karar destek aracıdır.

---

## Hafta 1 — 18–24 Eylül 2026 (çalışma 21 Eylül'de başladı)

**Yapılanlar**
- Projenin temel iskeleti kuruldu; uçuş bilgisi, hava durumu, hesaplama ve ekran kısımları
  birbirinden ayrıldı.
- Sonuçların saklanacağı bir veritabanı ve sisteme dışarıdan ulaşılabilmesi için bir web
  servisi hazırlandı.
- Türbülans riskini harita üzerinde gösteren ilk ekran yapıldı; sonuçlar resmî hava
  uyarılarıyla karşılaştırılabiliyor.
- Yapılan her değişikliğin otomatik olarak test edilmesi sağlandı.

**Sonuç:** Bir uçuş için türbülans riskini hesaplayıp haritada gösteren ilk çalışan sürüm
ortaya çıktı.

---

## Hafta 2 — 25 Eylül – 1 Ekim 2026

**Yapılanlar**
- Uçuşu üç boyutlu izleyebilen bir simülasyon ekranı eklendi.
- Sistem artık riskli bölgelerden kaçan alternatif bir rota önerebiliyor. Resmî uyarı verilmiş
  bölgeler ve uçuşa kapalı alanlar bu rotada kesinlikle kullanılmıyor.
- Güncel hava durumu verisi ve resmî hava uyarıları sisteme bağlandı.
- Pilot raporlarını hava durumu verisiyle eşleştirip yapay zekâ modelini her gece kendiliğinden
  yeniden eğiten bir düzen kuruldu.
- Uçuş kayıtlarındaki ani irtifa değişimlerinden türbülans olabilecek anlar bulunuyor
  ("sanal pilot raporu").
- Sonuçların ne kadar kesin olduğu da gösteriliyor (düşük risk / yüksek risk / belirsiz).
- Sunum için demo senaryosu ve poster taslağı hazırlandı.

**Önceki çalışmalarda yapılan değişiklik**
- İlk yapay zekâ modelinin hatalı veriyle eğitildiği fark edildi: pilot raporlarındaki yükseklik
  bilgisi yanlış okunmuş, bu yüzden yüksek irtifa yerine yere yakın raporlar kullanılmıştı.
  İlk model geçersiz sayıldı ve veri doğru şekilde baştan hazırlandı. Düzeltmeden sonra
  tahmin başarısı belirgin biçimde arttı.

---

## Hafta 3 — 2–8 Ekim 2026

**Yapılanlar**
- Doç. Dr. Fulya Aybek Çetek'in önerileri uygulandı:
  - Türkiye'nin resmî havacılık yayınından uçuş noktaları ile 85 kısıtlı ve askerî bölge
    sisteme eklendi; bu bölgelerin hangi saatlerde kapalı olduğu da hesaba katılıyor.
  - Önerilen rotalar artık yalnızca gerçek hava yolu ağı üzerinde ve bu ağın kullanılabildiği
    saatlerde çiziliyor.
  - Önerilen rotanın diğer uçak trafiğine ne kadar yakın olduğu gösteriliyor.
- Rotalar havacılık kurallarına uygun hâle getirildi: kurallara uygun uçuş yükseklikleri
  seçiliyor, resmî uyarı bölgelerinin çevresinde güvenlik payı bırakılıyor.
- Türbülans hesabı daha fazla yükseklik katmanı kullanacak şekilde iyileştirildi.
- Sonuçları kontrol etmek için uçakların kendi ölçtüğü türbülans verisi eklendi.
- Değerlendirmenin adil olması için bazı günler yalnızca teste ayrıldı; bu günler modelin
  eğitiminde hiç kullanılmıyor. Yeni bir model, mevcut yöntemden açıkça daha iyi olmadıkça
  devreye alınmıyor.
- Güvenlik kontrolü yapıldı; verilerin her gün şifreli yedeği alınıyor.
- Tezin çerçeve bölümleri yazıldı: benzer çalışmalar, projenin katkıları ve sınırlamaları.

**Sonuçlar (7 Ekim ara sonuçları)**
- Klasik türbülans hesabı, türbülanslı ve sakin durumları ayırt etmede orta düzeyde başarılı
  (yaklaşık 7.800 pilot raporunda başarı puanı 0,68; 1 kusursuz, 0,5 rastgele tahmin demek).
- Gerçek türbülansların yaklaşık yarısını yakalıyor; verdiği dört uyarıdan biri yanlış alarm.
- Yapay zekâ modeli klasik hesaptan açıkça daha iyi olmadığı için devreye alınmadı.
- Bu yüzden sistem güvenlik için resmî hava uyarılarını esas alıyor; kendi türbülans hesabını
  yalnızca yardımcı bilgi olarak kullanıyor.

**Önceki çalışmalarda yapılan değişiklikler**
- Türbülans değerini ölçeklemek için kullanılan katsayı, düzeltilmiş veriyle yeniden belirlendi.
- Ekranda "EDR" olarak gösterilen değerin gerçek bir ölçüm sanılabileceği fark edildi; adı
  "gösterge" olarak değiştirildi.
- Rota hesaplama süresi için daha önce yazılan değer ölçümle tutmadı; program hızlandırıldı
  ve belgeler gerçek ölçüme göre düzeltildi.
- Hangi değerden sonra "riskli" deneceği daha sağlam bir yöntemle yeniden belirlendi.
- Bir örnek rotada kullanılan noktanın resmî yayına göre yanlış olduğu görüldü ve düzeltildi.

---

## Hafta 4 — 9–16 Ekim 2026

**Yapılanlar**
- Önerilen rotanın yanında yalnızca rüzgâra göre en uygun rota da gösteriliyor; böylece
  türbülanstan kaçmanın ne kadar zaman ve yakıta mal olduğu görülebiliyor.
- Yakıt tüketimi ve egzoz salımı, uçağın ağırlığı ve uçtuğu yükseklik hesaba katılarak
  tahmin ediliyor.
- Yolcu kabini için uyarı tek bir saat yerine ±15 dakikalık bir zaman aralığı olarak
  veriliyor; uçuşu planlayan kişi için 3 satırlık kısa bir özet eklendi.
- Sistem daha güvenilir hâle getirildi: hava durumu verisi alınamazsa "risk yok" değil
  "veri alınamadı" diyor; her sonucun hangi veriyle üretildiği kaydediliyor.
- Yeni gelen verinin eski veriden farklılaşıp farklılaşmadığı izleniyor; şu an bir
  farklılaşma yok.
- Demo, internete bağlı olmayan temiz bir bilgisayarda çalıştırılarak denendi.
- Kısa denemeler yapıldı:
  - Modelin ayarlarını değiştirmek ve ona ek bilgi vermek sonucu çok az iyileştirdi.
  - Büyük ve küçük uçaklar arasında türbülans riski açısından anlamlı bir fark bulunmadı.
  - Uçuş kayıtlarından türbülans bulma yöntemi belirgin irtifa değişimlerini neredeyse her
    zaman yakalıyor, küçük dalgalanmalarda yanlış alarm vermiyor.

**Sonuçlar**
- Demo uçuşunda riskli bölgeden tamamen kaçan rota yaklaşık 8 dakika daha uzun sürüyor ve
  %9,5 daha fazla yakıt harcıyor. Daha yüksekten uçma seçeneği %2 daha az yakıt harcıyor ama
  rotada küçük bir riskli kısım kalıyor; hangisinin seçileceği uçuşu planlayan kişiye bırakılıyor.
- Her gece çalışan veri toplama işi düzenli ilerliyor: şu ana kadar 148 güne ait yaklaşık
  14.500 örnek toplandı. 15 Ekim'de eğitilen yeni model, mevcut modelden daha iyi olmadığı
  için devreye alınmadı.

> ⚠️ Hocam, burada küçük bir açıklama yapmak istiyorum. (Verileri Copernicus (Avrupa'nın hava
> durumu arşivi), Iowa Environmental Mesonet (pilot raporları) ve NOAA MADIS (uçakların
> ölçtüğü türbülans) gibi herkese ücretsiz hizmet veren kurumlardan alıyorum. Bu kurumların
> sunucuları herkesin ortak kullanımında olduğu için, kısa sürede çok fazla veri isteyenlerin
> erişimi kısıtlanabiliyor. Ben de verinin hepsini bir anda indirmek yerine her gece
> kendiliğinden çalışan bir otomasyon kurdum. Sistem günde en fazla 500 MB olacak şekilde,
> istekler arasında bekleyerek az az veri topluyor. Veri bu yüzden yavaş ama düzenli
> birikiyor.)

**Önceki çalışmalarda yapılan değişiklikler**
- Demo örneklerinden birinin sayıları kendi bilgisayarımdaki farklı veriden alınmıştı; temiz
  kurulumda farklı sonuç çıktı. Belgeler, poster ve ekran görüntüleri düzeltildi.
- Otomatik test sistemi, kullandığım platformun ücret sınırı yüzünden durdu; proje herkese
  açık yapılarak sorun giderildi.
- Geçmiş bir uçuş üzerinde yapılan yakıt karşılaştırması, uçak o sırada yükseldiği için
  anlamlı sonuç vermedi; bu sonuç "karşılaştırılamaz" olarak işaretlendi.
- Yöntemi Avrupa'da denemek için yeterli ölçüm bulunamadı; bu durum bir sınırlama olarak
  not edildi.
