# 0008 — Sır taraması pre-commit ve CI'da zorunlu

- Durum: Kabul edildi (2026-10-01)
- İlgili dosyalar: `.gitleaks.toml`, `.gitleaksignore`, `.pre-commit-config.yaml`, `.github/workflows/ci.yml`

## Bağlam

2026-09-21'de OpenSky şifresi Türkçe adlı bir değişkene düz metin yazılıp
commit'lendi, ertesi gün kaldırıldı ama git geçmişinde kaldı. Varsayılan sır
tarayıcı kuralları Türkçe değişken adlarını tanımaz.

## Karar

- gitleaks pre-commit kancası ve CI'da tüm geçmiş taraması.
- `.gitleaks.toml` varsayılan kurallara Türkçe/İngilizce adlı şifre ve anahtar
  atamalarını ekler.
- CI, Türkçe adlı sahte bir sırrın yakalandığını her çalıştırmada doğrular
  (yapılandırma bozulursa tarama sessizce "temiz" demesin diye).
- Geçmişteki OpenSky şifresi değiştirildi (2026-10-01) ve geçmiş temizlendi
  (2026-10-02, `git filter-repo` + depo sahibinin onayıyla force-push).
  `.gitleaksignore` yalnızca bilinen yanlış pozitifi tutar.
- CI ayrıca `pip-audit` ve CycloneDX SBOM çalıştırır.

## Sonuçlar

- Sır yönetimi kişisel dikkate değil otomatik kontrole dayanır.
- Yanlış pozitifler satır içi `gitleaks:allow` ile, görünür biçimde işaretlenir.

## Değerlendirilen alternatifler

- Yalnızca CI: sır push edildikten sonra yakalanır; yetersiz.
