# Türbülans Radar — Proje İlerleme Raporu

**Hazırlayan:** Tevfik Uner  
**Danışman:** ……………………  
**Son güncelleme:** 16 Ekim 2026

**Proje kısaca.** Seyir irtifasındaki açık hava türbülansı radarda görünmez. Proje, yalnız
açık verilerle (uçuş izleri, hava verisi, resmî hava uyarıları ve pilot raporları) bir
uçuşun rotası boyunca türbülans riskini gösteren ve riskli bölgelerden kaçan rota öneren
bir karar destek aracı geliştiriyor. Çıktılar sertifikalı türbülans ölçümü (EDR) değildir;
sistem operasyonel karar aracı değil, karar destek aracıdır.

> Her hafta yeni bölüm en alta eklenir; önceki bölümler silinmez. Haftalar görüşme
> düzenine göre Cuma–Perşembe aralığıyla verilmiştir.

---

## Hafta 1 — 18–24 Eylül 2026 (çalışma 21 Eylül'de başladı)

**Yapılanlar**
- Proje parçalara ayrıldı: uçuş verisi, hava verisi, hesaplama ve arayüz ayrı modüller oldu.
- Sonuçları saklamak için veritabanı, dışarıdan erişim için bir web servisi kuruldu.
- İlk web arayüzü ve 3B harita hazırlandı; hesaplanan risk resmî hava uyarılarıyla
  (SIGMET) karşılaştırılabiliyor.
- Her değişiklikte testlerin kendiliğinden çalıştığı otomatik kontrol düzeni ve temel
  güvenlik önlemleri eklendi.

**Sonuç:** Bir uçuş için türbülans riskini hesaplayıp haritada gösteren ilk çalışan sürüm.

---

## Hafta 2 — 25 Eylül – 1 Ekim 2026

**Yapılanlar**
- 3B uçuş simülasyonu ekranı eklendi.
- Rota önerisi: riskli bölgelerden kaçan alternatif rota. SIGMET bölgeleri ve yasak/kısıtlı
  hava sahaları kesin olarak dışarıda bırakılıyor.
- Canlı hava verisi (NOAA GFS) ve canlı SIGMET bağlantısı kuruldu.
- Makine öğrenmesi için veri hattı: pilot raporları ile hava verisi otomatik eşleştiriliyor;
  her gece kendiliğinden veri toplayıp modeli yeniden eğiten bir iş kuruldu.
- Gerçek uçuş izlerindeki ani irtifa sapmalarından "sanal pilot raporu" üretimi.
- Sonuçlara belirsizlik gösterimi eklendi (düşük risk / yüksek risk / belirsiz).
- Sunum paketi taslağı: demo senaryosu ve poster.

**Önceki çalışmalarda yapılan değişiklik**
- Önceki modelin yanlış veriyle eğitildiği bulundu: pilot raporlarındaki irtifa feet
  cinsindenmiş, uçuş seviyesi sanılmış. Yani seyir irtifası yerine yere yakın raporlar
  kullanılmış. İlk model ve buna dayanan kalibrasyon geçersiz sayıldı, veri hattı doğru
  filtreyle baştan kuruldu. Düzeltmeden sonra temel göstergenin (Ellrod TI1) ayırt etme
  başarısı küçük bir denemede 0,44'ten 0,71'e çıktı.

---

## Hafta 3 — 2–8 Ekim 2026

**Yapılanlar**
- Doç. Dr. Fulya Aybek Çetek'in önerileri uygulandı:
  - Türkiye AIP'sinden serbest rota (FRA) noktaları ve 85 kısıtlı/askerî saha alındı;
    sahaların aktif olduğu saatler NOTAM'larla işleniyor.
  - Rota artık yalnız bu ağ üzerinde ve FRA saatlerinde (20:00–02:00 UTC) öneriliyor.
  - Önerilen rotanın geçmiş trafikle ayırmasını gösteren bir gösterge eklendi.
- Uçuş kurallarına uyum: yasal uçuş seviyeleri (yön kuralı), SIGMET çevresine güvenlik payı.
- Hesaplama çekirdeği iyileştirildi (daha fazla atmosfer katmanı kullanılıyor).
- Nesnel doğrulama için uçakların otomatik ölçtüğü türbülans verisi (MADIS) eklendi.
- Değerlendirme kuralları donduruldu: rastgele seçilen 16 "test günü" hiçbir eğitime
  girmiyor; yeni model ancak temel göstergeyi anlamlı biçimde geçerse devreye alınıyor.
- Güvenlik denetimi yapıldı, günlük şifreli yedek kuruldu.
- Tez çerçevesi belgeleri yazıldı: ilgili çalışmalar, katkılar, sınırlamalar.

**Sonuçlar (7 Ekim ön paketi)**
- Temel gösterge (TI1) 80 günde 7.815 pilot raporunda ayırt etme başarısı 0,680 (1 = kusursuz,
  0,5 = rastgele).
- Risk eşiğinde türbülansın yarısını yakalıyor, yanlış alarm oranı %25.
- Makine öğrenmesi modeli TI1'i anlamlı geçemedi, bu yüzden devreye alınmadı. Birkaç
  göstergenin birleşimi az ama anlamlı bir iyileşme verdi.
- Bu nedenle güvenlik resmî uyarılara (SIGMET) dayanıyor; türbülans göstergesi rotada
  yalnız yumuşak bir ceza olarak kullanılıyor.

**Önceki çalışmalarda yapılan değişiklikler**
- Kalibrasyon katsayısı doğru veriyle ve yeni hesaplamayla yeniden belirlendi (0,40 → 0,27).
- "EDR" adıyla gösterilen değer yanıltıcı bulundu, adı "gösterge" olarak değiştirildi.
- Rota hesaplama süresi için daha önce yazılan süre ölçümle doğrulanmadı; kod hızlandırıldı
  ve belgedeki sayı ölçülen değerle düzeltildi.
- Risk eşiği istatistiksel bir kuralla yeniden seçildi.
- Bir rota örneğinde kullanılan bağlantı noktasının AIP'e göre yanlış olduğu görüldü, düzeltildi.

---

## Hafta 4 — 9–15 Ekim 2026

**Yapılanlar**
- Önerilen rotanın yanında "yalnız rüzgâra göre en iyi rota" da gösteriliyor; böylece
  türbülanstan kaçınmanın bedeli ayrıca görülebiliyor.
- Yakıt ve emisyon tahmini açık kaynak bir uçak performans modeliyle (OpenAP) yapılıyor.
- Kabin uyarısı tek bir saat yerine ±15 dakikalık zaman aralığı olarak veriliyor; dispeçer
  için 3 satırlık özet brifing kartı eklendi.
- Güvenilirlik iyileştirmeleri: canlı hava verisi alınamazsa sistem "risk yok" değil
  "veri alınamadı" diyor; her sonuçta hangi veri ve model sürümüyle üretildiği yazıyor.
- Gelen yeni verinin eğitim verisinden sapıp sapmadığı izleniyor; şu an sapma yok.
- Demo, temiz bir bilgisayarda internet olmadan çalıştırılarak denendi.
- Kısa deneyler:
  - Model ayarı ve ek özellikler çok küçük kazanç getirdi.
  - Ağır ve hafif uçaklar arasında anlamlı fark bulunmadı.
  - Sanal pilot raporu yöntemi 120 ft ve üstü irtifa sapmalarını neredeyse her zaman
    yakalıyor, küçük gürültüde yanlış alarm vermiyor.

**Sonuçlar**
- Demo uçuşunda riskli bölümü tamamen atlatan rota 7,8 dakika ve %9,5 yakıt fazlasına
  mal oluyor. Bir üst seviye (FL370) seçeneği %2 daha az yakıt harcıyor ama bir riskli
  nokta bırakıyor; seçim dispeçere bırakılıyor.
- Gece veri işi düzenli çalışıyor: 148 günlük eşleşmiş veri, 14.536 örnek. 15 Ekim'de
  eğitilen yeni model mevcut modeli geçemediği için devreye alınmadı.

**Önceki çalışmalarda yapılan değişiklikler**
- Demo senaryolarından birinin sayıları kendi bilgisayarımdaki farklı veriden alınmıştı;
  temiz kurulumda farklı çıktı. Belge, poster ve ekran görüntüleri düzeltildi.
- Otomatik test sistemi bir ücret sınırı nedeniyle durdu; depo herkese açık yapılarak çözüldü.
- Bir geçmiş uçuşta yakıt karşılaştırması uçuşun tırmanış bölümleri yüzünden anlamlı
  yapılamadı; sonuç "karşılaştırılamaz" olarak işaretlendi.
- Avrupa'ya genelleme denemesinde yeterli ölçüm bulunamadı; skor verilmedi, sınırlama
  olarak yazıldı.

**Gelecek hafta planı (16–22 Ekim)**
- 18 Ekim'de veri dondurulup nihai sonuç paketi üretilecek; belgelerdeki ön sayılar
  güncellenecek.
- Türkiye için daha geniş hava verisi ve daha fazla uçuş örneği (veri kotası hesabından sonra).
