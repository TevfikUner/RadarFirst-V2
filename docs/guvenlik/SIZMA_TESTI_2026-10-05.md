# Sızma testi ve kod denetimi — 2026-10-05

Kapsam: kaynak kod (API, web, MCP, betikler), Docker imajı ve bağlanan klasörler, çalışan yığına
zararsız canlı denemeler (127.0.0.1), Windows dinleyen portlar, GitHub deposu/CI. Veri silen ya da
servisi yoran deneme yapılmadı.

## Bulgular (önem sırasıyla)

> **Durum (2026-10-05):** 1 ve 2 düzeltildi ve canlıda doğrulandı. 3–10, proje yalnızca
> yerelde, depo gizli ve öncelik veri kaybı olduğu için kullanıcı kararıyla ertelendi; API ağa
> açılırsa ya da depo herkese açılırsa yeniden ele alınmalı.

### 🔴 1. Proje kökünün tamamı API ve işçi konteynerine bağlı (`/veri`) — ✅ düzeltildi
`/veri`'ye artık yalnızca ana küp, `era5_egitim_verisi/` ve `pirep_ham/` bağlı; `.env`, yedekler,
`.git` konteynerden görünmüyor (api ve worker'da doğrulandı).
`docker-compose.yml`: `${YEREL_VERI_KOKU:-.}:/veri:ro`. Uygulama kullanıcısı (uid 1000) konteyner
içinden `.env` (postgres süper kullanıcı şifresi, yönetici API anahtarı, MCP şifresi), tüm DB
dump'ları, `.git`, `turbulans_projesi.zip`, `.claude/` okuyabiliyor (doğrulandı). `db:5432`
konteynerden erişilebilir.
**Saldırı zinciri:** API'de herhangi bir dosya okuma/RCE → `/veri/.env` → süper kullanıcı →
`COPY ... PROGRAM` ile db konteynerinde komut çalıştırma + tüm veriyi silme. Bugünkü uygulama
rolü ve ortam değişkeni boşaltma bu yolla tamamen aşılıyor.
**Çözüm:** `/veri`'ye yalnızca ERA5 küpleri ve PIREP arşivi bağlanmalı (ayrı salt okunur bağlar).

### 🔴 2. Uygulama kodu konteyner içinde yazılabilir — ✅ düzeltildi
`COPY --chmod=755`: kod root'a ait, uid 1000 yazamıyor; yazılabilir kalanlar yalnızca bağlanan
veri klasörleri. CI duman testi her iki maddeyi de denetliyor.
`/app` altındaki tüm dosyalar 777 (WSL `/mnt/c` NTFS izinleri `COPY . .` ile imaja geçiyor).
uid 1000 `api_servisi.py`'yi değiştirebiliyor (doğrulandı). Dockerfile'daki "kod salt okunur"
varsayımı geçersiz. Saldırgan kalıcı arka kapı bırakır; konteyner yeniden başlatılsa da kalır.
**Çözüm:** Dockerfile'da `/app` root sahipliğine alınıp `chmod -R a-w,u+w` (yazılan klasörler hariç).

### 🟠 3. API'ye tüm DB dump'ları bağlı (`./db_yedekleri:/app/db_yedekleri:ro`)
Sağlık raporu yalnızca yedeğin tarihini okuyor, ama konteyner tüm veritabanının dökümünü görüyor.
**Çözüm:** Yedek servisi tazelik bilgisini küçük bir durum dosyasına yazsın, API sadece onu okusun.

### 🟠 4. İmaja gereksiz/iç dosyalar giriyor
`.dockerignore` eksik: `.claude/`, `.mcp.json`, `docker-compose.override.yml` (OneDrive yolu),
`CLAUDE.md`, `.coverage`, `pirep_ham/`, `era5_egitim_verisi/`, CSV'ler imajda. Şu an sır yok, ama
imaj paylaşılırsa iç yapı sızar ve imaj gereksiz büyür.

### 🟠 5. Tarayıcı güvenlik başlıkları yok
CSP, `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy` yok. API anahtarı
`sessionStorage`'da: ileride çıkacak tek bir XSS anahtarı çalar; `/harita` başka sitede
iframe'e gömülebilir (tıklama kaçırma). Yerel kütüphane eksikse jsdelivr yedeği `document.write`
ile **bütünlük (SRI) kontrolsüz** yükleniyor.

### 🟡 6. MCP sorgu filtresi aşılabilir
Regex filtresi `SELECT set_config('default_transaction_read_only','off',false)`'ı geçiriyor
(doğrulandı). Asıl koruma (okuyucu rolün yetkisi) tuttu: tabloya yazma reddedildi. Ancak
`MCP_POSTGRES_*` boşsa sunucu `.env`'deki süper kullanıcıya düşüyor; o zaman filtre tek engel olur.
**Çözüm:** MCP_* tanımlı değilse başlamayı reddet.

### 🟡 7. Dış kaynaklı metin Claude'a ulaşıyor (prompt injection)
SIGMET/PIREP ham metinleri (AWC, IEM) veritabanında; MCP ile Claude Code'a gidiyor. Claude bu
makinede docker/wsl çalıştırabildiği için kötü niyetli bir rapor metni talimat gibi davranabilir.
Olasılık düşük; MCP yalnızca gerektiğinde açılmalı.

### 🟡 8. GitHub token'ı geniş kapsamlı
Windows Kimlik Yöneticisi'ndeki token `repo, workflow, gist` kapsamlı; oturumdaki her süreç
`git credential fill` ile alabilir (PR açarken bu şekilde kullanıldı). Yalnızca bu depoya yetkili
ince taneli (fine-grained) token önerilir. `master` dal koruması açık (PR incelemesi zorunlu).

### 🟡 9. Diskte kalan eski izler
Eski PG17 veri klasörü (eski veri + zayıf şifre hash'i; servis kapalı) ve `Desktop\yedekler`
bundle'ları (eski, döndürülmüş OpenSky şifresi).

### 🟡 10. Küçük maddeler
- `.env.demo` herkesçe bilinen anahtarlar içeriyor; demo yığını ağa açılırsa herkes yönetici olur.
- `server: uvicorn` başlığı; `/saglik?derin=true` anahtarsız iç durum bilgisi verir (önbellekli).
- `postgres:16` etiketle (digest değil), GitHub Actions etiketle sabit.
- WS bileti tek kullanımlığı süreç başına (`WEB_CONCURRENCY>1` iken süreç sayısı kadar).
- Kapsam dışı: Windows SMB (139/445) ağa açık — Windows varsayılanı.

## Sağlam bulunanlar (canlı denendi)
- Anahtarsız erişim: tüm `/api/v1/*` ve `/metrics` 401. Boş/boşluklu/Bearer anahtar 401.
- Pilot anahtarıyla 7 yönetici ucu: hepsi 403.
- `/harita` yol geçişi (`../`, `%2e%2e`, `..%2f`): 404.
- CORS: yabancı origin'e izin yok. `TRACE` 405. 1 GB gövde beyanı 413.
- Proje portları (8000/5432/5433) yalnızca 127.0.0.1'de.
- SQL: tüm sorgular parametreli; model geri dönüşü yalnızca manifest kimliği kabul ediyor.
- Webhook SSRF: IP sabitleme, DNS rebinding koruması, yönlendirme takip edilmiyor.
- Web: dış veri `textContent` ile basılıyor (XSS bulunamadı). Bağımlılıklar güncel.
- CI: sır yok, `pull_request_target` yok.
