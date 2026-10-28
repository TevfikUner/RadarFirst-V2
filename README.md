# Türbülans Radar

**Problem.** Seyir irtifasındaki açık hava türbülansı (CAT) radarda görünmez; pilot
raporu (PIREP) gönüllü, gecikmeli ve konumu kabadır; operasyonel ürünler (GTG, WAFS)
NWP alanı üretir ve yerinde EDR ile doğrulanır.

**Araştırma sorusu.** Yalnız açık veriyle (OpenSky ADS-B, ERA5, AWC SIGMET, IEM PIREP)
gerçek bir uçuş izinde seyir türbülansı riski hangi ölçülmüş beceriyle gösterilebilir
ve bu sınır rota kararına nasıl taşınmalıdır?

**Kısa cevap** (nihai paket [2026-10-18](docs/sonuclar/2026-10-18/SAYILAR.md)). Becerisi
sınırlı: Ellrod TI1, 163 günde 15.940 seyir PIREP'inde ROC-AUC 0,673 [0,661–0,684]; altın
test günlerinde risk eşiğinde (7e-7) yakalama 0,50, yanlış alarm 0,25. Birleşik gösterge
TI1'i az ama anlamlı geçiyor (+0,013 [+0,007; +0,020]). ML modeli altın günlerde TI1'i
geçiyor (protokol modeli Random Forest +0,033 [+0,018; +0,049]; canlıdaki 9 Ekim Random
Forest da +0,033), ama ROC-AUC 0,71'de kalıyor. Bu yüzden güvenlik SIGMET'e (sert kısıt)
dayanır. TI1 yumuşak kısıttır: yasaklamaz (riskten kaçınan aday yoksa riskli rota yine önerilir),
ama adaylar arasında seçimde yakıttan önce gelir (en az riskli noktalı aday, eşitlikte en az yakıt).

Kapsam yalnız CAT ve seyir safhası, doğrulama ABD verisiyle; çıktılar sertifikalı EDR
değildir, sistem karar destek aracıdır. TI1 ve 0–1 gösterge ölçeği (API alanı `edr_proxy`)
EDR değildir; ayrıntı [Sistem Kartı](docs/SISTEM_KARTI.md) ve
[Sınırlamalar](docs/KILAVUZ.md#bilinmesi-gerekenler--sınırlamalar). Doğruluk sayılarının
tek kaynağı [`docs/sonuclar/`](docs/sonuclar/README.md) paketleridir.

## Çekirdek ve ekler

Tezin çekirdeği dört katkıdır ([Katkılar](docs/rapor/KATKILAR.md)):

| Katkı | Ne | Kod |
|---|---|---|
| K1 | Barometrik irtifayla gerçek ADS-B izi – ERA5 eşleştirmesi; kapsam dışı "veri yok" | `fizik/eslestirme.py` |
| K2 | Seyir irtifası PIREP etiket hattı; IEM FL alanının feet olduğu hatanın tespiti | `ml/ml_veri_hatti.py`, `dogrulama/bagimsiz_kanit.py` |
| K6 | TI1'in sınırının bağımsız etiketle (PIREP, MADIS EDR) ölçülüp ürüne yansıtılması | `fizik/turbulans_indeksleri.py`, `ml/degerlendirme.py` |
| K7 | SIGMET sert / TI1 yumuşak kısıtlı A* rota, yakıt bedeliyle | `rota/rota_optimizasyonu.py` |

Sanal PIREP, contrail, IWXXM, n8n, MCP, 3B simülasyon ve CLI araçlarının çoğu mühendislik
ekidir; tezin iddiasını taşımaz.

## Beş dakikada çalıştır

Kimlik bilgisi (OpenSky, Copernicus) gerektirmez; ilk derleme internet ister (PyPI, npm,
GitHub); çalışma anında dış veri kaynağı yok. Depoyla gelen gerçek veri paketi
([demo/](demo/README.md)): THY322'nin 15 Ocak 2019 rotası ve onu kapsayan ERA5 dilimi
(toplam ~300 KB).

```bash
git clone <depo-adresi> && cd <depo>
cp .env.demo .env
docker compose --profile demo up -d --build
```

Temiz CI makinesinde derleme + demo analizi 80 sn; geliştirici dizüstünde önbelleksiz
derleme ~6,5 dk. `docker compose logs demo` özeti gösterir. Sonra tarayıcıda:

- 3B harita: <http://localhost:8000/harita/harita3d.html> -- API anahtarı
  `demo-yerel-yonetici`, listeden THY322'yi seç.
- Rota simülasyonu: <http://localhost:8000/harita/ucus_simulasyonu.html>
  (örn. 41.0, 29.0 → 40.5, 43.5; FL350; 2019-01-15 20:00).
- API belgesi: <http://localhost:8000/docs>

Docker olmadan (yalnız analiz ve harita):

```bash
pip install -e .
turbulans-demo        # ciktilar/turbulans_haritasi_THY322_2019-01-15.html
```

Demo anahtarları herkesçe bilinir; bu yığını ağa açmayın. Gerçek kurulum (OpenSky, CDS,
PostgreSQL, Alembic): [Kılavuz → Kurulum](docs/KILAVUZ.md#kurulum). Jüri demo akışı:
[DEMO_SENARYOSU](docs/sunum/DEMO_SENARYOSU.md).

## Nasıl çalışır

```
OpenSky / ADS-B izi ──► eşleştirme (baro irtifa → ISA basınç, ERA5/GFS küpü)
                          └► Ellrod TI1, Richardson, birleşik EDR ──► PostgreSQL ──► FastAPI + WebSocket
AWC SIGMET + kısıtlı sahalar (sert) ─┐                                                  ├► 3B harita (MapLibre)
TI1 cezası (yumuşak), OpenAP yakıt ──┴► A* rota (yanal + ±1 FL) ─────────────────────────┴► rota simülasyonu (CesiumJS)
IEM PIREP (FL280–420) ──► gece veri hattı ──► kapılı ML (TI1'i geçmezse aktifleşmez)
```

Uzun işler PostgreSQL kuyruğunda (`FOR UPDATE SKIP LOCKED`) ayrı işçide çalışır; ayrıntılı
diyagramlar [docs/mimari.md](docs/mimari.md), tasarım kararları [docs/adr/](docs/adr/).

## Belgeler

| Belge | İçerik |
|---|---|
| [Kılavuz](docs/KILAVUZ.md) | Kurulum, kullanım, API uç noktaları, güvenlik, rota, SIGMET, GFS, backtest, ML, izleme, yedek, testler, sınırlamalar |
| [Sistem Kartı](docs/SISTEM_KARTI.md) | Kullanım sınıfı, veri kaynakları, karar mantığı, hata durumları, bilinen sınırlar, doğrulama durumu |
| [Sonuç paketleri](docs/sonuclar/README.md) | Her doğruluk sayısının kaynağı (18 Ekim nihai paket ve ek analizler) |
| [Deney protokolü](docs/deney_protokolu.md) | Bölme, metrikler, karar kuralı, dondurma sonrası protokol |
| [Rapor bölümleri](docs/rapor/) | Katkılar, ilgili çalışmalar, sonuçlar, sınırlamalar ve dersler |
| [İşletim kılavuzu](docs/ISLETIM_KILAVUZU.md) | Günlük işletim adımları |
| [Performans raporu](docs/PERFORMANS_RAPORU.md) | Ölçülmüş süreler ve bellek |
| [Veri kaynakları ve lisanslar](docs/VERI_KAYNAKLARI_VE_LISANSLAR.md) | Sağlayıcı şartları ve atıflar |
| [CHANGELOG](CHANGELOG.md) · [CONTRIBUTING](CONTRIBUTING.md) | Değişiklik geçmişi, katkı kuralları |

## Geliştirme

```bash
pip install -e ".[dev]"
cp .env.example .env          # OpenSky + PostgreSQL + API_ANAHTARI
alembic upgrade head
pytest tests/                 # katmanlar: -m birim|veritabani|gercek_veri|tarayici|ag
```

Yerelde testler otomatik olarak ayrı `<POSTGRES_DB>-test` veritabanını kullanır. Ayrıntı:
[Kılavuz → Testleri çalıştırmak](docs/KILAVUZ.md#testleri-çalıştırmak).

## Lisans

Kaynak kodu: [MIT](LICENSE). Dış verilerin lisansları ve atıf metinleri:
[docs/VERI_KAYNAKLARI_VE_LISANSLAR.md](docs/VERI_KAYNAKLARI_VE_LISANSLAR.md).
