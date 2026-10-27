# Hızlı tarama (27 Ekim 2026)

Kapsam: statik kontroller, testler, bağımlılık açıkları, kabuk betikleri, servis günlükleri,
açık PR'lar ve kullanıcının açtığı `arayuz/web_arayuzu.py`. Ayrıntılı denetimler için
`docs/denetim/2026-10-20/DENETIM.md`.

| Kontrol | Sonuç |
|---|---|
| ruff check / format | Temiz (306 dosya) |
| mypy (`api/`, `depo/`, `fizik/`) | Temiz (35 dosya) |
| pytest (tarayıcı, ağ, gerçek veri hariç) | 1.066 geçti, kapsam %84,6 (yeni testlerden önce) |
| pip-audit `requirements.lock`, `requirements-era5.lock` | Bilinen açık yok |
| shellcheck (`scripts/`, `otomasyon/`) | 4 uyarı: 1'i düzeltildi, 3'ü zararsız (aşağıda) |
| Servis günlükleri (yeniden başlatmadan sonra) | Hata yok |
| Açık PR | Yok (#128 Dependabot'ça kapatıldı) |
| Derin sağlık | Tamam; `ats_agi` "bitiyor" (AIRAC 29–30 Ekim, beklenen) |

## Düzeltilenler

- `scripts/tam_denetim.sh`: `set -e` yok; `cd` başarısız olursa betik yanlış klasörde sürerdi →
  `cd ... || exit 1`.
- `scripts/pr_hazir_mi.sh` (yeni): push'tan hemen sonra `gh pr checks` "no checks reported"
  döner; #137 bu yüzden CI başlamadan birleşti (master CI sonradan yeşil). Betik en az bir
  kontrol raporlanmadıkça ve hepsi pass olmadıkça 0 dönmez; `--bekle` ile bitene kadar bekler.
- `arayuz/web_arayuzu.py`: uyarı "araştırma/görselleştirme amaçlıdır" diyordu; projenin
  standart ifadesine getirildi ("sertifikalı EDR değildir; ... karar destek aracıdır").
- `tests/test_kup_katalogu_sorgulari.py` (yeni): küp kataloğunun kayıt (upsert), kapsayan küp
  seçimi (en yeni çalışma, eksik dosya, hazır olmayan durum, indirme tazeliği), kesişim (3 sa
  tolerans) ve canlı küp temizliği hiç test edilmiyordu (mevcut test gerçek veri katmanında).
  `depo/kup_katalogu.py` kapsamı %48,5 → %86,4.

## Bilerek bırakılanlar

- shellcheck SC2174 (`otomasyon/db_yedekle.sh` `mkdir -p -m 700 /tmp/gnupg`): `/tmp` her zaman var,
  izin yalnız son klasöre gerekli. SC2011 (`tam_denetim.sh` `ls | xargs`): yalnız bilgi satırı.
- Sessiz `except Exception: pass` blokları (`depo/dagitik_kilit.py`, `api/api_servisi.py` WS
  kapanışı) yalnız kapatma/temizlik adımlarında; bilinçli.
- Düşük kapsamlı diğer modüller: `veri/veri_saglayicilari.py` %55,6 (ağ testleri dışarıda),
  araştırma CLI'ları (`cli/demo_ekranlari` %27, `cli/performans_olcumu` %51) YAPILACAKLAR'da düşük öncelik.

Çıktılar sertifikalı EDR değildir; sistem operasyonel karar aracı değil, karar destek aracıdır.
