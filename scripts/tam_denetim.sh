#!/usr/bin/env bash
# Türbülans Radar tam denetimi (Faz 0-5). WSL'de proje kökünden çalıştırılır:
#   bash scripts/tam_denetim.sh [--hizli] [--tarayicisiz] [--build-zorla]
#     --hizli        yalnız birim testleri + duman testi (statik kontroller dahil)
#     --tarayicisiz  tarayıcı testleri ve Playwright ekran/video adımı atlanır
#     --build-zorla  gece işi (ml_veri) çalışıyor olsa bile imajları yeniden derler
# Çıktı: test_raporu/<YYYY-MM-DD>/ (junit, log, api, ekran, kapsam); RAPOR_KLASORU ile değiştirilebilir.
# Yasaklar: volume silme, `down -v`, DROP, git push/reset, `-m ag` testleri,
# CDS/ERA5 indirmesi ve POST /api/v1/ml/gece-isi bu betikte YOKTUR.
set -uo pipefail
exec < /dev/null

HIZLI=0; TARAYICISIZ=0; BUILD_ZORLA=0
for arguman in "$@"; do
  case "$arguman" in
    --hizli) HIZLI=1 ;;
    --tarayicisiz) TARAYICISIZ=1 ;;
    --build-zorla) BUILD_ZORLA=1 ;;
    -h|--help) sed -n 2,9p "$0"; exit 0 ;;
    *) echo "Bilinmeyen bayrak: $arguman"; exit 2 ;;
  esac
done

cd "$(dirname "$0")/.."
KOK="$(pwd)"
TARIH="$(date +%F)"
R="${RAPOR_KLASORU:-test_raporu/$TARIH}"
VENV="${VENV:-$HOME/.venvs/turbulans}"
PY="$VENV/bin/python"
TABAN="${TABAN:-http://localhost:8000}"
mkdir -p "$R"/{log,api,ekran,statik,openapi}
DURUM="$R/log/adim_durumlari.tsv"
: > "$DURUM"

adim() { printf '\n\033[1;36m== %s\033[0m\n' "$1"; }
kaydet() { printf '%s\t%s\t%s\n' "$1" "$2" "$3" >> "$DURUM"; printf '%s %s: %s\n' "$2" "$1" "$3"; }
env_degeri() { grep -E "^$1=" .env 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"'"'"; }

adim "Faz 0 - Envanter"
{
  echo "dal: $(git rev-parse --abbrev-ref HEAD)"
  git log --oneline -10
  echo "-- commit'lenmemiş (autocrlf=true ile):"; git -c core.autocrlf=true status --short
  GIT_TERMINAL_PROMPT=0 timeout 20 git fetch -q origin 2>/dev/null || echo "(git fetch yapılamadı; son bilinen origin/master ile karşılaştırılıyor)"
  echo "origin/master farkı (önde/geride): $(git rev-list --left-right --count HEAD...origin/master 2>/dev/null)"
  echo "-- sürümler"; "$PY" --version; docker --version; docker compose version
  echo "-- .env anahtarları (değer yazılmaz)"
  for k in POSTGRES_USER POSTGRES_PASSWORD POSTGRES_DB POSTGRES_HOST POSTGRES_PORT API_ANAHTARI API_PILOT_ANAHTARI CDSAPI_RC_DOSYASI; do
    [ -n "$(env_degeri "$k")" ] && echo "$k: tanımlı" || echo "$k: EKSİK"
  done
  for k in $(grep -oE '^OPENSKY_[A-Z_]+=' .env | tr -d '='); do [ -n "$(env_degeri "$k")" ] && echo "$k: tanımlı" || echo "$k: EKSİK"; done
  echo "-- veri varlıkları"
  du -sh ocak_2019_turbulans.nc era5_egitim_verisi era5_ucus_verisi opensky_onbellek pirep_ham model_deposu web/vendor veri_dosyalari ciktilar 2>&1
  echo "opensky_onbellek uçuşları: $(ls opensky_onbellek/*.parquet 2>/dev/null | xargs -n1 basename 2>/dev/null | tr '\n' ' ')"
} > "$R/envanter.txt" 2>&1
kaydet "Envanter" "✅" "$R/envanter.txt"

adim "Faz 1 - Statik kontroller"
"$VENV/bin/ruff" check . > "$R/statik/ruff_check.txt" 2>&1 && kaydet "ruff check" "✅" "temiz" || kaydet "ruff check" "❌" "$R/statik/ruff_check.txt"
"$VENV/bin/ruff" format --check . > "$R/statik/ruff_format.txt" 2>&1 && kaydet "ruff format" "✅" "$(tail -1 "$R/statik/ruff_format.txt")" || kaydet "ruff format" "❌" "$R/statik/ruff_format.txt"
"$VENV/bin/mypy" > "$R/statik/mypy.txt" 2>&1 && kaydet "mypy" "✅" "$(tail -1 "$R/statik/mypy.txt")" || kaydet "mypy" "❌" "$R/statik/mypy.txt"
timeout 600 "$PY" -m pytest tests/test_bagimlilik_kilidi.py -q -p no:cacheprovider > "$R/statik/bagimlilik_kilidi.txt" 2>&1 \
  && kaydet "bağımlılık kilidi" "✅" "$(tail -1 "$R/statik/bagimlilik_kilidi.txt")" || kaydet "bağımlılık kilidi" "❌" "$R/statik/bagimlilik_kilidi.txt"
{ echo "heads:"; timeout 120 "$VENV/bin/alembic" heads; echo "current:"; timeout 120 "$VENV/bin/alembic" current 2>&1 | grep -v INFO; } > "$R/statik/alembic.txt" 2>&1
if [ "$(grep -c '(head)' "$R/statik/alembic.txt")" -ge 2 ]; then kaydet "alembic" "✅" "current = head"; else kaydet "alembic" "⚠️" "$R/statik/alembic.txt"; fi
PYTHONPATH=src timeout 300 "$PY" - "$R/openapi/openapi.json" > "$R/statik/openapi.txt" 2>&1 <<'PY'
import json, sys
from turbulans_radar.cli.openapi_disa_aktar import openapi_semasini_al
s = openapi_semasini_al()
json.dump(s, open(sys.argv[1], "w"), ensure_ascii=False, indent=2)
n = sum(1 for p in s["paths"].values() for m in p if m in ("get", "post", "put", "patch", "delete"))
print(f"{len(s['paths'])} yol, {n} uç nokta; depodaki openapi.json ile aynı: {s == json.load(open('openapi.json'))}")
PY
kaydet "OpenAPI" "$([ $? -eq 0 ] && echo ✅ || echo ❌)" "$(tail -1 "$R/statik/openapi.txt")"

adim "Faz 2 - Test paketi"
docker compose ps --status running db 2>/dev/null | grep -q db || docker compose up -d --wait db
if [ "$HIZLI" = 1 ]; then KATMANLAR="birim"; else KATMANLAR="birim veritabani gercek_veri"; [ "$TARAYICISIZ" = 0 ] && KATMANLAR="$KATMANLAR tarayici"; fi
for katman in $KATMANLAR; do
  baslangic=$(date +%s)
  timeout 2700 "$PY" -m pytest -m "$katman" -p no:cacheprovider -q -rfEs --junitxml="$R/junit_$katman.xml" --durations=15 > "$R/log/pytest_$katman.txt" 2>&1
  cikis=$?
  ozet="$(grep -E '^[0-9]+ (passed|failed)|passed|failed' "$R/log/pytest_$katman.txt" | tail -1) ($(( $(date +%s) - baslangic )) sn)"
  kaydet "pytest -m $katman" "$([ $cikis -eq 0 ] && echo ✅ || echo ❌)" "$ozet"
done
if [ "$HIZLI" = 0 ]; then
  timeout 3600 "$PY" -m pytest -p no:cacheprovider -q --cov --cov-report=term-missing --cov-report=html:"$R/kapsam" > "$R/log/pytest_kapsam.txt" 2>&1
  kaydet "kapsam" "$([ $? -eq 0 ] && echo ✅ || echo ⚠️)" "$(grep -E '^TOTAL' "$R/log/pytest_kapsam.txt") $(tail -1 "$R/log/pytest_kapsam.txt")"
fi

adim "Faz 3 - Docker yığını"
GECE_ISI=$(curl -fsS -H "X-API-Key: $(env_degeri API_ANAHTARI)" "$TABAN/api/v1/ml/durum" 2>/dev/null \
  | "$PY" -c "import json,sys; d=json.load(sys.stdin); print(any(g['tur']=='ml_veri' and g['durum'] in ('kuyrukta','calisiyor') for g in d.get('son_gorevler',[])))" 2>/dev/null)
if [ "$GECE_ISI" = "True" ] && [ "$BUILD_ZORLA" = 0 ]; then
  timeout 400 docker compose up -d --wait --wait-timeout 300 > "$R/log/docker_up.txt" 2>&1
  kaydet "docker compose up" "⚠️" "gece işi çalışıyor: imajlar YENİDEN DERLENMEDİ (--build-zorla ile zorlanır)"
else
  timeout 1500 docker compose up -d --build --wait --wait-timeout 300 > "$R/log/docker_up.txt" 2>&1
  kaydet "docker compose up --build" "$([ $? -eq 0 ] && echo ✅ || echo ❌)" "$R/log/docker_up.txt"
fi
tr -d '\r' < .github/duman_testi.sh > /tmp/duman_testi_$$.sh
timeout 300 bash /tmp/duman_testi_$$.sh > "$R/log/duman_testi.txt" 2>&1
kaydet "duman testi" "$([ $? -eq 0 ] && echo ✅ || echo ❌)" "$(tail -1 "$R/log/duman_testi.txt")"
rm -f /tmp/duman_testi_$$.sh
docker compose ps > "$R/log/docker_ps.txt" 2>&1
for servis in api worker; do docker compose logs --tail 100 "$servis" 2>&1 | grep -nE 'ERROR|Traceback|CRITICAL' > "$R/log/${servis}_hatalari.txt"; done
kaydet "konteyner logları" "$([ -s "$R/log/api_hatalari.txt" ] || [ -s "$R/log/worker_hatalari.txt" ] && echo ⚠️ || echo ✅)" \
  "api: $(wc -l < "$R/log/api_hatalari.txt") satır, worker: $(wc -l < "$R/log/worker_hatalari.txt") satır ERROR/Traceback (son 100 satırda)"

if [ "$HIZLI" = 1 ]; then
  echo; column -t -s $'\t' "$DURUM"; exit 0
fi

adim "Faz 4 - Fonksiyonel senaryolar"
"$PY" scripts/demo_goster.py --kaydet "$R/api" --renksiz > "$R/log/demo_goster.txt" 2>&1
kaydet "API senaryoları" "$([ $? -eq 0 ] && echo ✅ || echo ❌)" "$R/log/demo_goster.txt"
UCUS="${UCUS:-THY322}"; UCUS_TARIHI="${UCUS_TARIHI:-2019-01-15}"
if [ -f "opensky_onbellek/${UCUS}_${UCUS_TARIHI}.parquet" ]; then
  PYTHONPATH=src timeout 900 "$PY" -m turbulans_radar.analiz.ucus_analizi "$UCUS" "$UCUS_TARIHI" > "$R/log/turbulans_analiz.txt" 2>&1
  kaydet "turbulans-analiz $UCUS" "$([ $? -eq 0 ] && echo ✅ || echo ❌)" "ciktilar/turbulans_haritasi_${UCUS}_${UCUS_TARIHI}.html"
else
  kaydet "turbulans-analiz $UCUS" "⏭️" "OpenSky önbelleği yok (tarayıcı girişi/OAuth gerekir)"
fi
PYTHONPATH=src timeout 300 "$PY" -m turbulans_radar.cli.veri_kontrol "$UCUS" "$UCUS_TARIHI" > "$R/log/veri_kontrol.txt" 2>&1
kaydet "veri_kontrol" "$([ $? -eq 0 ] && echo ✅ || echo ❌)" "$R/log/veri_kontrol.txt"
curl -fsS -X POST -H "X-API-Key: $(env_degeri API_ANAHTARI)" "$TABAN/api/v1/backtest/ucuslar/$UCUS/$UCUS_TARIHI" -o "$R/api/backtest_yeniden_$UCUS.json" -w '%{http_code}\n' > "$R/log/backtest_yeniden.txt" 2>&1
kaydet "backtest $UCUS (yeniden)" "$(grep -q '^20' "$R/log/backtest_yeniden.txt" && echo ✅ || echo ❌)" "$R/api/backtest_yeniden_$UCUS.json"
for komut in "ml_otomatik_egitim --listele" "degerlendirme" "edr_kalibrasyonu"; do
  ad="${komut%% *}"
  PYTHONPATH=src timeout 1200 "$PY" -m "turbulans_radar.ml.$ad" ${komut#"$ad"} > "$R/log/ml_$ad.txt" 2>&1
  kaydet "ML: $ad" "$([ $? -eq 0 ] && echo ✅ || echo ❌)" "$R/log/ml_$ad.txt"
done

if [ "$TARAYICISIZ" = 0 ]; then
  adim "Faz 5 - Ekran görüntüleri ve video (Playwright)"
  if ! curl -fsS -o /dev/null http://localhost:8501/; then
    PYTHONPATH=src setsid nohup "$VENV/bin/streamlit" run src/turbulans_radar/arayuz/web_arayuzu.py --server.headless true \
      --server.port 8501 --browser.gatherUsageStats false > "$R/log/streamlit.log" 2>&1 < /dev/null &
    for _ in $(seq 1 30); do curl -fsS -o /dev/null http://localhost:8501/ && break; sleep 1; done
  fi
  timeout 900 "$PY" - "$TABAN" "$KOK/$R/ekran" "http://localhost:8501" "$KOK" "$UCUS" "$UCUS_TARIHI" > "$R/log/ekran.txt" 2>&1 <<'PY'
import json, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright

TABAN, KLASOR, STREAMLIT, KOK, UCUS, UCUS_TARIHI = sys.argv[1], Path(sys.argv[2]), sys.argv[3], Path(sys.argv[4]), sys.argv[5], sys.argv[6]
FOLIUM = KOK / f"ciktilar/turbulans_haritasi_{UCUS}_{UCUS_TARIHI}.html"
KLASOR.mkdir(parents=True, exist_ok=True)
env = dict(s.split("=", 1) for s in (KOK / ".env").read_text().splitlines() if "=" in s and not s.lstrip().startswith("#"))
ANAHTAR = env["API_ANAHTARI"].strip().strip('"').strip("'")
DEMO = {"#baslangic-enlem": 41.0, "#baslangic-boylam": 29.0, "#bitis-enlem": 40.5, "#bitis-boylam": 43.5, "#irtifa-ft": 35000}
hatalar, sonuc = [], {}

def izle(sayfa, ad):
    sayfa.on("console", lambda m: m.type == "error" and hatalar.append({"sayfa": ad, "tur": "console", "metin": m.text[:300]}))
    sayfa.on("pageerror", lambda e: hatalar.append({"sayfa": ad, "tur": "pageerror", "metin": str(e)[:300]}))

def adim(ad, fonk):
    t = time.perf_counter()
    try:
        sonuc[ad] = {"durum": "tamam", "bilgi": fonk(), "sure_sn": round(time.perf_counter() - t, 1)}
    except Exception as hata:
        sonuc[ad] = {"durum": "hata", "bilgi": str(hata)[:400], "sure_sn": round(time.perf_counter() - t, 1)}
    print(ad, sonuc[ad]["durum"], sonuc[ad]["sure_sn"], flush=True)

def simulasyon(sayfa, goruntu=True):
    sayfa.goto(f"{TABAN}/harita/ucus_simulasyonu.html")
    sayfa.fill("#giris-anahtar", ANAHTAR)
    sayfa.dispatch_event("#giris-anahtar", "change")
    sayfa.wait_for_function("document.querySelectorAll('#ucak-modeli option[value=\"A320\"]').length > 0", timeout=30_000)
    sayfa.select_option("#ucak-modeli", "A320")
    for kimlik, deger in DEMO.items():
        sayfa.fill(kimlik, str(deger))
    sayfa.fill("#zaman", "2019-01-15T20:00")
    sayfa.click("#simule-et-buton")
    sayfa.wait_for_function("document.getElementById('s-optimize-sure').innerText.trim().length > 0", timeout=120_000)
    sayfa.wait_for_timeout(6000)
    bilgi = {"strateji": sayfa.inner_text("#strateji-satiri"), "tasarruf": sayfa.inner_text("#tasarruf-satiri")}
    if goruntu:
        sayfa.screenshot(path=str(KLASOR / "01_simulasyon_sonuc.png"), full_page=True)
    sayfa.evaluate("""() => { const c = viewer.clock; const d = Cesium.JulianDate.secondsDifference(c.stopTime, c.startTime);
        c.currentTime = Cesium.JulianDate.addSeconds(c.startTime, d * 0.45, new Cesium.JulianDate()); }""")
    sayfa.wait_for_timeout(3000)
    if goruntu:
        sayfa.screenshot(path=str(KLASOR / "02_simulasyon_animasyon_ortasi.png"), full_page=True)
    sayfa.click("#yeniden-hesapla-buton")
    sayfa.wait_for_function("(() => { const t = document.getElementById('durum').innerText; return t.includes('yeniden hesaplandı') || t.includes('hatası'); })", timeout=120_000)
    sayfa.wait_for_timeout(5000)
    bilgi["yeniden_hesap"] = sayfa.inner_text("#durum")
    if goruntu:
        sayfa.screenshot(path=str(KLASOR / "03_simulasyon_yeniden_hesap.png"), full_page=True)
    return bilgi

def harita3d(sayfa):
    sayfa.goto(f"{TABAN}/harita/harita3d.html")
    sayfa.wait_for_selector("#harita")
    sayfa.fill("#giris-ucus", UCUS)
    sayfa.fill("#giris-tarih", UCUS_TARIHI)
    sayfa.fill("#giris-anahtar", ANAHTAR)
    sayfa.click("#yukle-buton")
    sayfa.wait_for_function("document.getElementById('durum').innerText.includes('nokta yüklendi')", timeout=60_000)
    sayfa.wait_for_timeout(5000)
    sayfa.screenshot(path=str(KLASOR / "04_harita3d.png"))
    sayfa.evaluate("""() => { const k = document.getElementById('zaman-kaydirici');
        k.value = Math.round((+k.min + +k.max) * 0.6); k.dispatchEvent(new Event('input', {bubbles: true})); }""")
    sayfa.wait_for_timeout(2500)
    sayfa.screenshot(path=str(KLASOR / "05_harita3d_zaman_kaydirici.png"))
    return {"durum": sayfa.inner_text("#durum")}

def swagger(sayfa):
    sayfa.goto(f"{TABAN}/docs")
    sayfa.wait_for_selector(".swagger-ui .opblock", timeout=60_000)
    sayfa.wait_for_timeout(1500)
    sayfa.screenshot(path=str(KLASOR / "06_swagger.png"))
    return {"uc_nokta_blogu": sayfa.locator(".opblock").count()}

def streamlit(sayfa):
    sayfa.goto(STREAMLIT)
    sayfa.wait_for_selector("[data-testid='stApp']", timeout=60_000)
    sayfa.wait_for_timeout(8000)
    sayfa.screenshot(path=str(KLASOR / "07_streamlit.png"), full_page=True)
    return {"hata_kutusu": sayfa.locator("[data-testid='stException']").count()}

def folium(sayfa):
    sayfa.goto(FOLIUM.as_uri())
    sayfa.wait_for_timeout(9000)
    sayfa.screenshot(path=str(KLASOR / "08_folium.png"))
    return {"dosya": str(FOLIUM)}

with sync_playwright() as p:
    tarayici = p.chromium.launch(args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
    baglam = tarayici.new_context(viewport={"width": 1600, "height": 950})
    for ad, fonk in (("simulasyon", simulasyon), ("harita3d", harita3d), ("swagger", swagger), ("streamlit", streamlit), ("folium", folium)):
        sayfa = baglam.new_page()
        izle(sayfa, ad)
        adim(ad, lambda f=fonk, s=sayfa: f(s))
        sayfa.close()
    baglam.close()
    gecici = KLASOR / "_video_gecici"
    vbaglam = tarayici.new_context(viewport={"width": 1280, "height": 720}, record_video_dir=str(gecici), record_video_size={"width": 1280, "height": 720})
    vsayfa = vbaglam.new_page()
    izle(vsayfa, "video")
    adim("video", lambda: simulasyon(vsayfa, goruntu=False))
    vsayfa.wait_for_timeout(4000)
    video = vsayfa.video.path()
    vbaglam.close()
    Path(video).replace(KLASOR / "simulasyon_akisi.webm")
    gecici.rmdir()
    tarayici.close()
(KLASOR / "konsol_hatalari.json").write_text(json.dumps(hatalar, ensure_ascii=False, indent=1))
(KLASOR / "ekran_sonuclari.json").write_text(json.dumps(sonuc, ensure_ascii=False, indent=1))
print("konsol hatası:", len(hatalar))
sys.exit(0 if all(v["durum"] == "tamam" for v in sonuc.values()) else 1)
PY
  kaydet "Playwright ekran/video" "$([ $? -eq 0 ] && echo ✅ || echo ⚠️)" "$R/ekran ($(tail -1 "$R/log/ekran.txt"))"
else
  kaydet "Playwright ekran/video" "⏭️" "--tarayicisiz"
fi

adim "Özet"
column -t -s $'\t' "$DURUM"
echo
echo "Rapor klasörü: $KOK/$R"
echo "Yığın ve Streamlit açık bırakıldı. Kapatma: docker compose stop ; pkill -f 'streamlit run'"
