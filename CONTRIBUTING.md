# Katkı Rehberi

Bu belge Türbülans Radar'da kod, commit ve sır yönetimi kurallarını toplar.
Kurulum ve testlerin ayrıntısı için README'ye ve `docs/` klasörüne bakın.

## Geliştirme ortamı

```bash
pip install -e ".[dev]"
pre-commit install          # ruff, biçim, büyük dosya ve sır taraması her commit'te
```

Windows'ta testler WSL2 içinde çalıştırılır (bkz. README "Testleri çalıştırmak").

## Kodlama kuralları

- Tanımlayıcılar, docstring'ler, log ve hata mesajları Türkçedir; kütüphane
  adları ve yerleşik teknik terimler olduğu gibi kalır.
- Lint ve biçim: `ruff check .` ve `ruff format .` (CI aynı sürümle kontrol eder).
- Yeni bir ortam değişkeni `config.py`'de varsayılanıyla tanımlanır ve
  `.env.example`'a eklenir.
- Uydurma katsayı, etiket ya da sonuç üretilmez; veri yoksa kod bunu açıkça
  söyler (NaN, `None`, "kapsam dışı").
- Çıktılar sertifikalı EDR değildir; sistem karar destek aracıdır. Kullanıcıya
  dönen metinlerde bu ifade korunur.

## Testler

| Katman | Ne zaman çalıştırılır |
|---|---|
| `birim` | Her değişiklikte (`pytest -m birim`) |
| `veritabani`, `gercek_veri` | Commit öncesi tam çalıştırmada (`pytest tests/`) |
| `tarayici` | Arayüz değişikliğinde (`pytest -m tarayici`) |
| `ag` | Gerçek CDS'e dokunan değişiklikte, elle (`pytest -m ag`; kota harcar) |

Yeni davranış testle gelir. Hata düzeltmesine, hatayı yeniden üreten bir test eşlik eder.

## Commit mesajları

- Tek satırlık Türkçe özet; önce alan, sonra ne değiştiği:
  `Alan: kısa açıklama` (örn. `Dağıtık kilit: işçi süreçleri arası ERA5 indirmelerinde tekilleştirme`).
- Hata düzeltmesi `Düzeltme:` ile başlar.
- Gerekirse boş satırdan sonra neden yapıldığını anlatan gövde.
- Bir commit tek bir mantıksal değişikliği içerir; üretilen dosyalar
  (`openapi.json`, kilit dosyaları) kaynağıyla aynı commit'e girer.

## Dal stratejisi

- `master` her zaman çalışır durumdadır: CI (lint, testler, güvenlik, Docker
  duman testi) yeşil olmadan birleştirme yapılmaz.
- Çok kişili çalışmada her iş `ozellik/<kisa-ad>` ya da `duzeltme/<kisa-ad>`
  dalında yapılır ve PR ile birleştirilir.
- `master`'a force-push yapılmaz. Geçmişi yeniden yazmak (aşağıdaki sır olayı
  dışında) yasaktır.

## Sır yönetimi

- Şifre, token ve API anahtarı koda, teste ya da belgeye yazılmaz. Değerler
  `.env` (git'e girmez) ya da Docker secret'tan okunur; şablonu `.env.example`.
- `pre-commit` ve CI, `gitleaks` ile tarar. `.gitleaks.toml` varsayılan
  kurallara Türkçe değişken adlarını (`sifre`, `parola`, `api_anahtari`, ...)
  ekler; CI ayrıca sahte bir sırrın yakalandığını doğrular.
- Yanlış pozitif olan satıra `# gitleaks:allow` eklenir. `.gitleaksignore`
  yalnızca geçmişteki bilinen bulgular içindir; yeni bulgu oraya yazılmaz.
- Bir sır commit'lenirse: (1) sır hemen sağlayıcıda değiştirilir/iptal edilir,
  (2) koddan kaldırılır, (3) depo herkese açıksa ya da açılacaksa geçmiş
  yedek alındıktan sonra temizlenir (`git filter-repo --replace-text`) ve
  bu işlem için depo sahibinin onayıyla force-push yapılır.

### Bilinen olay (2026-09-21)

`20a7b31` commit'i OpenSky şifresini `kimlik_dogrulama.py`'ye düz metin yazdı,
`b29f487` kaldırdı. Şifre geçmişte durmaktadır. Yapılması gerekenler: şifrenin
değiştirilmesi ve depo herkese açılmadan önce geçmişin temizlenmesi. Olay,
sır taramasının kişisel dikkate değil otomatik kontrole bağlanmasının gerekçesidir.

## Bağımlılıklar

`requirements.txt` değişince hash'li kilitler yeniden üretilir (README
"Bağımlılık kilidi"). CI her push'ta `pip-audit` ile bilinen açıkları tarar ve
CycloneDX SBOM'u (`sbom-cyclonedx` artifact'ı) üretir.
