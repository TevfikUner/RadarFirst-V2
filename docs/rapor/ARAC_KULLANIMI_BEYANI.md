# Araç kullanımı beyanı (rapor taslağı)

**Biçim (2026-10-08 kararı):** Yöntem bölümünün sonunda tek paragraf (uzman kurulunda
YZL önerisi). Danışman ayrı bölüm isterse paragraf olduğu gibi kendi başlığına taşınır;
metin değişmez. Danışmana teyit e-postası henüz gönderilmedi.

## Paragraf

Bu projede yazılım geliştirme aracı olarak Anthropic'in Claude Code yapay zekâ
asistanı (Claude Sonnet 5 ve Claude Opus 5.5 modelleri) kullanıldı. Depodaki
birleştirme dışı 284 commit'in 208'inde asistan ortak yazar olarak işaretlidir
(`Co-Authored-By`; 2026-10-18 itibarıyla). 8 Ekim'e kadar 202 commit'in 200'ü işaretliydi;
yazar o tarihten sonra işareti eklememeye karar verdi, bu dönemde de asistan aynı şekilde
kullanıldı (oturum kayıtları `docs/ISLEM_GUNLUGU.md`). İşaret taşımayan ilk iki commit'ten
(21–22 Eylül 2026) bugüne kalan kod, Python satırlarının yaklaşık %1,6'sıdır (40.869
satırın 669'u; `git blame -w`); kodun geri kalanı asistanla birlikte yazıldı. Asistan şu
aşamalarda kullanıldı: kod ve test yazımı, hata ayıklama, belge ve rapor taslakları,
literatür künyelerinin yayıncı/Crossref kayıtlarından doğrulanması ve dış inceleme
maddelerinin uygulanması. Araştırma sorusu, kapsam (yalnız CAT, seyir safhası), veri
kaynakları ve sağlayıcı sınırları, kabul kriterleri ve sonuçların yorumu yazara aittir;
yazarın asistana bıraktığı kararlar önceden yazılı bir kurala bağlandı ve belgelendi
(örnek: TI1 risk eşiği, eğitim günlerinde Peirce maksimumunun bir standart hatası
içindeki en tutucu eşik; `docs/rapor/SONUCLAR.md`). Asistan çıktısı üç yolla denetlendi:
otomatik testler (2026-10-18'de 1.051 test) ve sürekli entegrasyon her değişikliği
sınar, ana dala birleştirme testlerin ve statik denetimin temiz olmasına bağlıdır; raporlanan her sayı depodaki komutla yeniden üretilebilen sonuç
paketinden (`docs/sonuclar/`) alındı; tasarım, dış bir inceleme raporunun maddelerine
göre kabul kriterleriyle izlendi. Çekirdek modüllerin (`fizik/eslestirme.py`,
`fizik/turbulans_indeksleri.py`, A* maliyet fonksiyonu ve sezgiseli,
`ml/degerlendirme.py`) tasarımı ve doğrulanması savunmada yazar tarafından anlatılır
(proje işleyişi: `docs/sunum/PROJE_ISLEYISI.md`).

## Kaynak

- Commit sayımı: `git rev-list --count --no-merges HEAD` ve
  `git log --no-merges --format=%B | grep -ci "Co-Authored-By: Claude"`.
- Model dağılımı (işaretli commit'ler, 2026-10-18): Claude Opus 5.5 174, Claude Sonnet 5 28,
  Claude Sonnet 5.5 6. 8 Ekim sonrası işaretsiz commit'ler bu dağılıma girmez.
- Kalan satır oranı: `src/` ve `tests/` altındaki `.py` dosyalarında `git blame -w`,
  `8bbdaa5` ve `aa1e7d9` commit'lerine düşen satırlar. Bu iki commit'in başka bir araçla
  yazılıp yazılmadığı depodan bilinemez; bu yüzden "asistansız" değil "işaret taşımayan"
  denir.
- Rapor teslim edilmeden önce sayımları yeniden çalıştırıp güncelleyin.
