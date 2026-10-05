# Güvenlik taraması — 2026-10-05

Dış rapordaki 11 madde projeye karşı doğrulandı; hepsi geçerliydi. Durum:

| Risk | Madde | Durum |
|---|---|---|
| 🟠 | API/işçi `postgres` süper kullanıcısıyla bağlanıyor | ✅ `turbulans_uygulama` (süper değil, yalnızca kendi DB'sinin sahibi); `pg_read_file` reddediliyor |
| 🟠 | Windows'ta eski PostgreSQL 17 (Özel ağ duvar kuralı açık) | ⏳ `otomasyon/windows_eski_postgresql_kapat.ps1` — yönetici PowerShell'de kullanıcı çalıştıracak |
| 🟠 | Yedekler şifresiz, aynı diskte | ✅ OneDrive kopyası gpg AES256 (`*.gpg`), şifresiz kopyalar silindi, çözme doğrulandı. Yerel kopya bilinçli olarak şifresiz; disk için Cihaz Şifrelemesi önerilir |
| 🟠 | Eski OpenSky şifresi bundle'larda ve PR #1'de | ⏳ Şifre geçersiz. Bundle'lar kullanıcı kararıyla kaldı; depo herkese açılmadan önce aşağıdaki Destek talebi |
| 🟡 | `/docs`, `/openapi.json` anahtarsız | ✅ API ağa açılınca (`API_YAYIN_ADRESI` yerel değilse) kapanır; `API_BELGELERI_ACIK` ile zorlanır. `/harita` statik, veri anahtarla gelir |
| 🟡 | WS `?api_key=` | ✅ Kaldırıldı; yalnızca bilet |
| 🟡 | Pilot anahtarı yok | ✅ `API_PILOT_ANAHTARI` üretildi (`.env`); silme 403 doğrulandı |
| 🟡 | Tüm `.env` konteynerlere gidiyor | ✅ API/işçi/demo'da süper kullanıcı ve MCP şifreleri boşaltıldı (env_file diğer ayarlar için korunur) |
| 🟡 | TLS yok | ℹ️ Yerelde gereksiz; ağa açılınca açılış uyarısı + README'de ters vekil önerisi |
| 🟡 | Hız sınırı DB yokken kapalı; bilet 60 sn tekrar kullanılabilir | ✅ DB yokken süreç içi sayaç; bilet tek kullanımlık + rastgele ek |
| 🟡 | `docker exec` root | ℹ️ README: `docker compose exec -u turbulans ...` |

Doğrulama: birim + veritabanı katmanı 764 test geçti; veritabanı katmanı uygulama rolüyle de
geçti (229). `-test` veritabanında alembic downgrade/upgrade uygulama rolüyle çalıştı.
Değişiklik öncesi yedek: `db_yedekleri/turbulans_20261005_rol_oncesi.dump`.

## Kullanıcının yapacakları

1. Yönetici PowerShell: `powershell -ExecutionPolicy Bypass -File otomasyon\windows_eski_postgresql_kapat.ps1`
2. Yedek parolası `C:\Users\VICTUS\.turbulans_yedek_parolasi` içinde: bir parola yöneticisine kaydet.
3. Ayarlar > Gizlilik ve güvenlik > Cihaz şifrelemesi: açık mı kontrol et (yerel yedekler için).
4. RadarFirst-V2 herkese açılacaksa önce aşağıdaki talebi gönder.

## GitHub Destek talebi (PR #1)

https://support.github.com/contact → "Removing sensitive data"

> Repository: TevfikUner/RadarFirst-V2
> I rewrote the history of this repository with git filter-repo to remove a leaked credential
> (already rotated) and force-pushed. Pull request #1 still references the old commits via
> refs/pull/1/head, so the credential remains reachable. Please remove the cached views/refs of
> the old commits for PR #1 (or the PR itself) and run garbage collection. No other forks exist.
