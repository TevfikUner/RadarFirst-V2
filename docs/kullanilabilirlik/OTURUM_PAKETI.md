# Kullanılabilirlik Oturumu Paketi (E7)

3–5 pilot ya da uçuş harekât/dispeçer uzmanıyla yapılacak oturumlar için her şey
bu dosyada: hazırlık, onam metni, görevler, ölçekler, gözlem formu ve analiz.
Oturum başına yaklaşık 40 dakika.

Amaç sistemin doğruluğunu değil, **anlaşılırlığını** ölçmek: kullanıcı ekranı
doğru okuyor mu, önerinin bedelini görüyor mu, sistemin sınırlarını (sertifikalı
EDR değil, karar destek aracı) fark ediyor mu?

## 1. Hazırlık

- **Ortam:** Demo yığını, ağsız (`docs/sunum/DEMO_SENARYOSU.md` §1). İki sekme
  açık olsun: 3B harita ve rota simülasyonu. Anahtar alanları önceden doldurulmuş.
- **Roller:** Moderatör (yönlendirir, yardım etmez) ve not tutan (§6 formunu
  doldurur). Tek kişiyseniz ekran ve ses kaydı alın (katılımcı izin verirse).
- **Malzeme:** Bu dosyanın çıktısı, kronometre, her katılımcı için §6 formu ve §5 anketi.
- **Katılımcı kodu:** K1, K2, … İsim, havayolu ya da kişisel bilgi forma yazılmaz.
- **Pilot oturum:** İlk gerçek oturumdan önce bir arkadaşla prova yapın; görev
  metinlerinde takılan yeri düzeltin.

## 2. Onam metni (oturum başında okunur)

> Bu oturum Türbülans Radar adlı bir bitirme projesi prototipinin ne kadar
> anlaşılır olduğunu ölçmek içindir. Sizi değil sistemi değerlendiriyoruz;
> yanlış cevap yoktur. Görevler sırasında aklınızdan geçenleri sesli
> söylemenizi rica ediyoruz. Adınız ve kurumunuz kaydedilmez; notlar yalnızca
> bir katılımcı koduyla tutulur. [Ses/ekran kaydı alınacaksa: Kayıt yalnızca
> notları tamamlamak için kullanılır ve proje bitince silinir.] İstediğiniz
> anda oturumu bırakabilirsiniz. Sistem gerçek uçuşlarda kullanılmaz; çıktıları
> sertifikalı EDR değildir, karar destek amaçlı bir prototiptir.
> Katılmayı kabul ediyor musunuz? ☐ Evet

Kurumunuz (üniversite etik kurulu) yazılı onam istiyorsa bu metni imzalı forma
çevirin; danışmanınıza sorun.

## 3. Isınma soruları (3 dk)

1. Kaç yıldır uçuyorsunuz / harekâtta çalışıyorsunuz? Hangi uçak tipleri ya da görev?
2. Uçuş öncesi türbülans bilgisini bugün nereden alıyorsunuz (SIGWX, GTG, şirket
   meteorolojisi, PIREP, EFB uygulaması…)?
3. Son bir yılda rota ya da irtifa kararını türbülans yüzünden değiştirdiniz mi? Nasıl karar verdiniz?

## 4. Görevler (her biri ≤ 5 dk; sesli düşünme)

Her görevden sonra katılımcıya §5.1'deki tek soru sorulur. Moderatör ipucu
vermez; katılımcı 2 dakikadan uzun takılırsa "yardımla" diye işaretlenip bir
sonraki adıma geçilir.

| # | Görev metni (katılımcıya okunur) | Ekran | Başarı ölçütü |
|---|---|---|---|
| G1 | "THY322 uçuşunun 15 Ocak 2019 izini açın ve uçuşun türbülans riskinin en yüksek olduğu bölümü gösterin." | 3B harita | Uçuşu yükler, renk lejantını kullanarak doğru bölümü gösterir |
| G2 | "Gri noktalar ne anlama geliyor? Sistem orada ne biliyor?" | 3B harita | "Veri yok / kapsam dışı" anlamını kendi sözleriyle söyler |
| G3 | "41,0 / 29,0'dan 40,5 / 43,5'e, 36.000 ft, 15.01.2019 20:00 UTC, A320 için rota isteyin. Önerilen rota neden farklı ve bunun bedeli ne?" | Rota simülasyonu | Riskli bölümden (~198 NM, 23 dk) kaçınıldığını ve bedelin (~+6 dk, +%7,7 seyir yakıtı) farkına varır |
| G4 | "Malatya'dan (38,35 / 38,31) Musul'a (36,34 / 43,13) aynı ayarlarla rota isteyin. Bu sonuca ne kadar güvenirdiniz?" | Rota simülasyonu | Kısıtlı sahadan kaçınıldığını ve "rüzgar hesaba katılamadı / kapsam dışı" uyarısını fark eder |
| G5 | "Ekranda gördüklerinize göre bu sistemin türbülans değerlerini gerçek bir uçuşta nasıl kullanırdınız?" | Her ikisi | Sertifikalı EDR olmadığını / karar destek amaçlı olduğunu ya da TI1 güvenilirlik notunu kendiliğinden anar |

G5'te katılımcı sınırı kendiliğinden anmazsa "Ekranda bununla ilgili bir uyarı
gördünüz mü?" diye **bir kez** sorun ve yanıtı ayrıca not edin. Bu soru, sistemin
dürüstlük mesajlarının görülüp görülmediğini ölçer; projenin en önemli
bulgularından biridir.

## 5. Ölçekler

### 5.1 Görev sonrası tek soru (SEQ)

"Bu görev genel olarak ne kadar zor ya da kolaydı?"
1 (çok zor) – 2 – 3 – 4 – 5 – 6 – 7 (çok kolay)

### 5.2 Oturum sonu: Sistem Kullanılabilirlik Ölçeği (SUS)

Kaynak: Brooke, J. (1996). SUS: A "quick and dirty" usability scale. Aşağıdaki
Türkçe metin bu proje için yapılmış bir çeviridir, geçerlilik çalışması yapılmış
bir uyarlama değildir; raporda böyle belirtin (yayımlanmış bir Türkçe uyarlama
bulursanız onu kullanın ve atıf verin).

1 = Kesinlikle katılmıyorum … 5 = Kesinlikle katılıyorum

| # | İfade | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|---|
| 1 | Bu sistemi sık sık kullanmak isterdim. | ☐ | ☐ | ☐ | ☐ | ☐ |
| 2 | Sistemi gereksiz derecede karmaşık buldum. | ☐ | ☐ | ☐ | ☐ | ☐ |
| 3 | Sistemin kullanımının kolay olduğunu düşündüm. | ☐ | ☐ | ☐ | ☐ | ☐ |
| 4 | Bu sistemi kullanabilmek için teknik bir kişinin desteğine ihtiyaç duyacağımı düşünüyorum. | ☐ | ☐ | ☐ | ☐ | ☐ |
| 5 | Sistemin çeşitli işlevlerinin iyi bütünleştirildiğini düşündüm. | ☐ | ☐ | ☐ | ☐ | ☐ |
| 6 | Sistemde çok fazla tutarsızlık olduğunu düşündüm. | ☐ | ☐ | ☐ | ☐ | ☐ |
| 7 | Çoğu kişinin bu sistemi çok çabuk öğreneceğini tahmin ediyorum. | ☐ | ☐ | ☐ | ☐ | ☐ |
| 8 | Sistemi kullanmayı çok zahmetli buldum. | ☐ | ☐ | ☐ | ☐ | ☐ |
| 9 | Sistemi kullanırken kendimden emin hissettim. | ☐ | ☐ | ☐ | ☐ | ☐ |
| 10 | Bu sistemi kullanmaya başlamadan önce birçok şey öğrenmem gerekti. | ☐ | ☐ | ☐ | ☐ | ☐ |

### 5.2a Her rota görevinden sonra iki evet/hayır sorusu

NTDA saha gösteriminde (Craig vd., ~2008) pilotlara sorulan iki soruya benzer; yanıtlar
`POST /api/v1/geri-bildirim` ile kaydedilir (`hedef_turu: "rota"`, `hedef_kimligi`: görev
kodu, ör. `E7-K03-G2`). Kayıt kişisel veri içermez; katılımcı kodu not alanına yazılmaz.

1. "Bu öneri gerçek bir uçuş hazırlığında işinize yarar mıydı?" → `yararli_mi`
2. "Gördüğünüz risk bilgisi size doğru/makul göründü mü?" → `dogru_mu`

Toplamlar `GET /api/v1/geri-bildirim/ozet` (yönetici anahtarı) ile alınır. Bu bir doğruluk
ölçümü değildir; kullanıcının algısıdır.

### 5.3 Açık uçlu sorular (5 dk)

1. Bu ekranlarda gördüğünüz bilgilerden hangisi gerçek bir uçuş hazırlığında işinize yarardı?
2. Neyi yanlış anlama riskiniz oldu ya da hangi ifade kafanızı karıştırdı?
3. Bu sistemin önerisine ne zaman güvenmezdiniz?
4. Eksik olan ve olsa kullanacağınız tek bir şey söyleyin.

## 6. Gözlem formu (her katılımcı için bir kopya)

Katılımcı kodu: ____ Rol: ☐ Pilot ☐ Dispeçer/harekât Deneyim (yıl): ____ Tarih: ____

| Görev | Süre (sn) | Sonuç (B / Y / X) | SEQ (1–7) | Hata / takılma | Sesli düşünmeden alıntı |
|---|---|---|---|---|---|
| G1 | | | | | |
| G2 | | | | | |
| G3 | | | | | |
| G4 | | | | | |
| G5 | | | | | |

B = başarılı, Y = yardımla, X = başarısız. G5 notu: sınırı kendiliğinden andı mı? ☐ Evet ☐ Soru sonrası ☐ Hayır

Bulgular (her biri bir satır): ekran, ne oldu, kaç katılımcıda, önem (0–4, aşağıda).

## 7. Analiz

- **SUS puanı:** Tek numaralı maddelerde (puan − 1), çift numaralılarda (5 − puan);
  toplam × 2,5 → 0–100. Her katılımcının puanını ve ortalamayı verin. n ≤ 5 olduğu
  için güven aralığı geniş olur; genelleme yapmayın. Sonucu "bu katılımcılarda" diye
  yazın.
- **SEQ ve süre:** Görev başına medyan ve en düşük–en yüksek.
- **Başarı:** Görev başına B/Y/X sayısı.
- **Bulgular:** Aynı sorunu yaşayan katılımcı sayısı ve önem derecesi (Nielsen
  ölçeği: 0 sorun değil, 1 kozmetik, 2 küçük, 3 büyük, 4 felaket). Önem 3–4 olan
  bulgular raporda düzeltme önerisiyle birlikte verilir; düzeltilenler için önce/sonra
  ekran görüntüsü eklenir.
- **G5 özel bulgusu:** Kaç katılımcının sistemin sınırını kendiliğinden fark ettiği.
  Bu sayı düşükse uyarı metinlerinin yeri ya da biçimi değiştirilmelidir.

## 8. Rapora girecek tablo şablonu

| Katılımcı | Rol | Deneyim | G1 | G2 | G3 | G4 | G5 | SUS |
|---|---|---|---|---|---|---|---|---|
| K1 | | | B/Y/X | | | | | |
| … | | | | | | | | |
| **Özet** | | | x/n B | | | | x/n kendiliğinden | ort. (min–maks) |

Değerler oturumlardan sonra doldurulur; boş kalan hücre "ölçülmedi" diye yazılır.
