# Proje Kuralları

- Always communicate, summarize, and ask questions in Turkish. You can write code in English, but your conversational language must be strictly Turkish.

## İzin Verilen İşlemler (Allowlist)
- Dosya okuma: Her zaman OK
- Git: Varsayılan dal `master`. İş `claude/<konu>` dalında küçük commit'lerle yapılır; testler ve lint temizse
  Claude `master`'a birleştirip push edebilir (2026-10-06 Tevfik'in kararı; GitHub'da PR şartı kaldırıldı, CI çalıştırıcı
  sorunları birleştirmeyi engellemez). Birleştirme için `gh pr merge <no> --merge` (settings.local.json izinli).
  Force-push ve geçmişi yeniden yazma (amend, rebase, filter-repo) yasak/önce sor; GitHub'da master force-push/silme kapalı.
- Dosya silme: Sadece kendi oluşturduğun dosyaları sil
- Tehlikeli komutlar `.claude/settings.json` deny listesiyle teknik olarak engellenir (rm -rf, docker compose down -v, docker volume rm, DROP/TRUNCATE, force-push).
- Diğer her şey için: Önce sor

## Mobil İzleme (telefondan takip)
- Her adım bitince tek satırlık özet ver: `✅/⚠️/❌ <adım>: <sonuç>` (en fazla ~120 karakter, önce sonuç).
- Uzun çıktı, log ve tabloyu sohbete dökme; dosyaya yaz, özette dosya yolunu ver.
- Her oturumun yaptıklarını `docs/ISLEM_GUNLUGU.md` başına tarihli kısa satırlarla ekle (en yeni üstte); pushlanınca GitHub mobil uygulamasından okunur.
- Gece işi özeti için: `turbulans-ml --gece-gecmisi` (CSV).
- Onay gerekince tek satır: `ONAY? <işlem> · etki · geri alınabilir mi (E/H)`; cevap gelene kadar o işi bekletip başka işe geçme.
- Uzun iş (>10 dk ya da >5 dosya) öncesi 3 satırlık plan + tahmini süre ver, onay al; bitince tek satır özet.
- Veritabanını etkileyen iş (migration, toplu yazma/silme) öncesi günün yedeği `db_yedekleri/` içinde var mı kontrol et; yoksa önce sor.
- Migration'lar önce `-test` veritabanında `upgrade` + `downgrade` ile denenir; geliştirme veritabanına uygulamak onaylıdır.

## Kodlama Kararları
| Durum | Karar |
|---|---|
| C ve Java Değişken İsimleri | KESİNLİKLE Türkçe kullan (node -> dugum, temp -> gecici) |
| Arayüz (Flutter) / API (FastAPI) | Tüm dosyayı baştan yazma, SADECE değişen/eklenen fonksiyonu ver |
| Açıklama (Comment) Satırları | Açıkça istenmedikçe yazma |
| Token Tasarrufu | Her zaman en kısa ve net yorumlamayı kullan |

## Örnek Kullanım (Few-Shot)
Kötü: update_node(temp)
İyi: dugum_guncelle(gecici)

## Bilimsel Dürüstlük
- Çıktılar sertifikalı EDR değildir; sistem operasyonel karar aracı değil, karar destek aracıdır. Bu ifadeleri koru.
- Olmayan veriyi/bileşeni varmış gibi varsayma; uydurma katsayı, etiket ya da sonuç üretme.
- Sırlar (şifre, token, API anahtarı) koda yazılmaz; `.env` ya da Docker secret'tan okunur.

## Mimari Özeti
- Paket: `src/turbulans_radar` (fizik, veri, depo, analiz, rota, ml, api, isci, dogrulama, arayuz, cli).
- Hava verisi ortak şema: u, v, t; `valid_time`, `pressure_level` (hPa), `latitude` (azalan), `longitude` (-180..180).
  Kaynaklar: yerel ERA5 küpleri, uçuşa özel ERA5 dilimi (CDS birincil, ARCO yedek), canlı GFS.
- Uçuş: OpenSky/Trino (OAuth) + Parquet rota önbelleği. Seviye seçimi barometrik irtifayla.
- ML: `ml_ornekleri` tablosu (seyir irtifası IEM PIREP + ERA5 özellikleri), gece işi `POST /api/v1/ml/gece-isi`,
  durum `GET /api/v1/ml/durum`, kapılı aktivasyon (TI1 referansı + aktif model), `turbulans-ml --geri-al`.
- Altyapı: WSL2 + Docker (`docker compose`: db, api, worker), PostgreSQL + Alembic, dağıtık kilit (advisory lock).
- Testler WSL'de: `~/.venvs/turbulans/bin/python -m pytest tests/`; katmanlar `-m birim|veritabani|gercek_veri|tarayici|ag`.
  Yerelde testler otomatik olarak ayrı `<POSTGRES_DB>-test` veritabanını kullanır (tests/conftest.py); CI kendi DB'sini.