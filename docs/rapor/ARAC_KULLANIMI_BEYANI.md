# Araç kullanımı beyanı (rapor taslağı)

Biçim açık karardır: ayrı bölüm mü, yöntem bölümünde tek paragraf mı, danışmana
sorulacak (Arş. Gör. Dr. Fatih Titrek). Aşağıdaki paragraf iki biçime de uyar.
`[YAZAR]` ile işaretli yerleri yalnız yazar doldurur; depodan doğrulanamaz.

## Paragraf

Bu projede yazılım geliştirme aracı olarak Anthropic'in Claude Code yapay zekâ
asistanı (Claude Sonnet 5 ve Claude Opus 5.5 modelleri) kullanıldı. Depodaki
birleştirme dışı 202 commit'in 200'ünde asistan ortak yazar olarak işaretlidir
(`Co-Authored-By`; 2026-10-08, `f1ea79a` itibarıyla); ilk iki commit (21–22 Eylül 2026)
asistansızdır. Asistan şu aşamalarda kullanıldı: kod ve test yazımı, hata ayıklama,
belge ve rapor taslakları, literatür künyelerinin yayıncı/Crossref kayıtlarından
doğrulanması ve dış inceleme maddelerinin uygulanması. Araştırma sorusu, kapsam (yalnız
CAT, seyir safhası), veri kaynakları ve sağlayıcı sınırları, kabul kriterleri ve
sonuçların yorumu yazara aittir; yazarın asistana bıraktığı kararlar önceden yazılı bir
kurala bağlandı ve belgelendi (örnek: TI1 risk eşiği, eğitim günlerinde Peirce
maksimumunun bir standart hatası içindeki en tutucu eşik; `docs/rapor/SONUCLAR.md`).
Asistanın ürettiği her sayı, depodaki komutla yeniden üretilebilen sonuç paketinden
(`docs/sonuclar/`) alınır ve otomatik testlerle denetlenir. [YAZAR: hangi modülleri ya
da bölümleri kendiniz yazdığınız/yeniden yazdığınız, asistan çıktısını nasıl gözden
geçirdiğiniz.] Çekirdek modüllerin (`fizik/eslestirme.py`, `fizik/turbulans_indeksleri.py`,
A* maliyet fonksiyonu ve sezgiseli, `ml/degerlendirme.py`) tasarımı ve doğrulanması
savunmada yazar tarafından anlatılır.

## Kaynak

- Commit sayımı: `git rev-list --count --no-merges HEAD` ve
  `git log --no-merges --format=%B | grep -ci "Co-Authored-By: Claude"`.
- Model dağılımı (aynı tarih): Claude Opus 5.5 172, Claude Sonnet 5 28 commit.
- Rapor teslim edilmeden önce sayımı yeniden çalıştırıp güncelleyin.
