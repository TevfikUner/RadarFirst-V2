# İşlem Günlüğü

Her oturumun kısa özeti, en yeni üstte. Telefondan (GitHub mobil) okunmak için kısa tutulur.

## 2026-10-04

- ✅ Git kuralları: master'a doğrudan push yasak (.githooks/pre-push), iş claude/<konu> dalında, birleştirme PR ile.
- ✅ `alembic downgrade` (Bash) artık yasak değil, "önce sor"da; PowerShell karşılığını yasaktan çıkarmak kullanıcıda.

- ⚠️ Disk dışı yedek: yedekler OneDrive\TurbulansRadar_Yedekleri'ne de kopyalanıyor; OneDrive'a giriş yapılana dek buluta gitmez.
- ✅ OpenSky önbelleği günlük dosya arşivine eklendi.

- ✅ Güvenlik: `.claude/settings.json` deny listesi (rm -rf, docker compose down -v, DROP/TRUNCATE, force-push); test edildi, engelliyor.
- ✅ CLAUDE.md: dal `master`, mobil izleme kuralları eklendi.
- ✅ V1 (RadarFirst) şifre temizliği: commit yeniden yazıldı (5decb4a), kullanıcı force-push etti; GitHub'da eski commit'e işaret eden dal/PR yok.
- ✅ Yedek: günlük pg_dump + dosya arşivi zaten çalışıyor (`db_yedekleri/`).
- ✅ API yalnızca 127.0.0.1:8000; DB yalnızca localhost.
- ✅ Docker giriş betiği: süreçler uid 1000, Linux'ta yazma izni sorunu çözüldü (ca393f8).
- ✅ Denetim: yüksek/orta/düşük öncelikli maddeler kapandı; 750 test geçti.
- ✅ DB şifresi döndürüldü (43 karakter), MCP salt okunur rolle Docker DB'yi okuyor.
