# Faz 0 temel ölçüm (17 Ekim 2026)

Depo `master` `486a153`; WSL2 (Ubuntu) + Docker. Kod değişikliği yapılmadı.

## Lint ve testler

| Komut | Sonuç |
|---|---|
| `ruff check .` (ruff 0.16.8) | Temiz ("All checks passed!") |
| `ruff format --check .` | Temiz (275 dosya) |
| `pytest tests/ -m "birim or veritabani"` | **988 geçti**, 0 başarısız, 47 seçilmedi (4 dk 11 sn); testler ayrı `-test` veritabanında |

Katman başına toplanan test sayısı (`--co -m`): birim 741, veritabani 247, gercek_veri 72,
tarayici 8, ag 2 (toplam 1035 test; katmanlar kesişebilir). `gercek_veri`, `tarayici` ve `ag`
bu ölçümde çalıştırılmadı. GitHub CI'ın son koşuları (6 iş: lint, guvenlik, test, tarayici,
docker, demo) 17 Ekim'de yeşil.

## Çalışan yığında gözlemler

| Kontrol | Sonuç |
|---|---|
| `curl -I /saglik` ve `/harita/ucus_simulasyonu.html` başlıkları | Yalnız `server: uvicorn`; CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, HSTS **yok** |
| API imajında `/app` altında | **Var:** `CLAUDE.md`, `.mcp.json`, `docs/`, `scripts/`, `.githooks/`, `.env.demo`, `.env.uretim.example`, `otomasyon/`, `demo/`, Postman koleksiyonu. `web/vendor/` (Cesium, MapLibre) imajda var |
| API konteynerinden `db_yedekleri` | 14 dosya görünüyor (`.dump` ve `dosyalar_*.tar.gz`), salt okunur |
| API konteynerinde `.env` | Yok (yalnız `env_file` ile ortam değişkeni olarak geliyor) |
| API süreç kullanıcısı | PID 1 `Uid: 1000` (root değil); `docker compose exec` varsayılanı root |
| Tanımlı compose profilleri | Yalnız `demo`; `uretim` ve `izleme` yok |

## `docker compose config`

Ham çıktı dosyaya ya da sohbete yazılmadı. Çıktı bir betikle okunup yalnız yapı (servis,
port, bağlama hedefi, ortam değişkeni **adları**, secret adları) çıkarıldı; makineye özgü yollar
`<DEPO>` / `<KULLANICI>` ile maskelendi. Özet tablo: [`URETIM_HAZIRLIK.md`](URETIM_HAZIRLIK.md)
"Ağa açılan yüzey".
