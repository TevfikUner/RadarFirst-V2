#!/usr/bin/env bash
# Canlı veriyle demo: .env (yoksa .env.canli.ornek'ten) + docker compose --profile demo up -d,
# API sağlıklı olunca SIGMET yenilemesi ve bağlantı/tazelik özeti.
#   scripts/canli_demo.sh               yığını başlatır
#   scripts/canli_demo.sh --baslatma    yalnız çalışan yığını yoklar (compose çalıştırmaz)
# Taban adres: CANLI_DEMO_URL (varsayılan http://localhost:8000), bekleme: CANLI_DEMO_BEKLEME_SANIYE (180).
set -euo pipefail
cd "$(dirname "$0")/.."

TABAN="${CANLI_DEMO_URL:-http://localhost:8000}"
BEKLEME="${CANLI_DEMO_BEKLEME_SANIYE:-180}"
BASLAT=1
for arg in "$@"; do
  case "$arg" in
    --baslatma) BASLAT=0 ;;
    -h|--help) sed -n '2,6p' "$0"; exit 0 ;;
    *) echo "Bilinmeyen seçenek: $arg" >&2; exit 2 ;;
  esac
done

if [ ! -f .env ]; then
  cp .env.canli.ornek .env
  echo "✅ .env yoktu; .env.canli.ornek kopyalandı (demo anahtarları herkesçe bilinir, yığını ağa açma)."
else
  echo "⚠️  .env zaten var, dokunulmadı. Canlı ayarlar için .env.canli.ornek ile karşılaştır."
fi

ortam() { grep -E "^$1=" .env | tail -n1 | cut -d= -f2- || true; }
[ "$(ortam CANLI_HAVA_VERISI_ETKIN)" = "false" ] && echo "⚠️  .env: CANLI_HAVA_VERISI_ETKIN=false -- canlı GFS kapalı."
[ "$(ortam SIGMET_OTOMATIK_GUNCELLEME_DAKIKA)" = "0" ] && echo "⚠️  .env: SIGMET_OTOMATIK_GUNCELLEME_DAKIKA=0 -- SIGMET otomatik yenilenmez."
ANAHTAR="$(ortam API_ANAHTARI)"
[ -n "$ANAHTAR" ] || { echo "❌ .env içinde API_ANAHTARI yok." >&2; exit 1; }

if [ "$BASLAT" = 1 ]; then
  echo "▶ docker compose --profile demo up -d (imaj yoksa derlenir: ilk derleme internetten yüzlerce MB indirir)"
  docker compose --profile demo up -d
fi

printf "▶ API bekleniyor (%s/saglik, en fazla %s sn)" "$TABAN" "$BEKLEME"
bitis=$(( $(date +%s) + BEKLEME ))
until curl -fsS -m 5 "$TABAN/saglik" >/dev/null 2>&1; do
  if [ "$(date +%s)" -ge "$bitis" ]; then
    echo; echo "❌ API $BEKLEME sn içinde sağlıklı olmadı. Bak: docker compose ps; docker compose logs api" >&2
    exit 1
  fi
  printf "."; sleep 3
done
echo " ayakta."

json_oku() {
  if command -v python3 >/dev/null 2>&1; then python3 -c "$1"; else cat; echo; fi
}

echo "▶ SIGMET yenileniyor (POST /api/v1/sigmet/guncelle, AWC)"
if YANIT="$(curl -sS -m 90 -X POST -H "X-API-Key: $ANAHTAR" -w '\n%{http_code}' "$TABAN/api/v1/sigmet/guncelle")"; then
  KOD="${YANIT##*$'\n'}"; GOVDE="${YANIT%$'\n'*}"
  if [ "$KOD" = 200 ]; then
    printf '%s' "$GOVDE" | json_oku 'import json,sys
d=json.load(sys.stdin)
print("  kaydedilen %s, sonlandırılan %s, silinen %s" % (d["kaydedilen"], d["sonlandirilan"], d["silinen"]))
for k,h in (d.get("kaynak_hatalari") or {}).items(): print("  ⚠️ %s: %s (mevcut SIGMETler korundu)" % (k, h))'
  else
    echo "  ❌ HTTP $KOD: $GOVDE"
  fi
else
  echo "  ❌ SIGMET yenileme isteği başarısız (ağ/zaman aşımı)."
fi

DURUM="$(curl -sS -m 30 -H "X-API-Key: $ANAHTAR" "$TABAN/api/v1/sistem/durum" || true)"
echo
echo "Bağlantılar"
echo "  Rota simülasyonu : $TABAN/harita/ucus_simulasyonu.html"
echo "  3B harita        : $TABAN/harita/harita3d.html"
echo "  API belgesi      : $TABAN/docs"
echo "  API anahtarı     : $ANAHTAR"
echo
echo "Tazelik"
if [ -z "$DURUM" ]; then
  echo "  ❌ /api/v1/sistem/durum okunamadı."
else
  printf '%s' "$DURUM" | json_oku 'import json,sys
from datetime import datetime,timezone
try:
    k=json.load(sys.stdin)["kontroller"]
except Exception as e:
    print("  ❌ sistem durumu çözümlenemedi: %s" % e); sys.exit(0)
def yas(z):
    if not z: return "yok"
    d=(datetime.now(timezone.utc)-datetime.fromisoformat(str(z).replace("Z","+00:00"))).total_seconds()/60
    return "%.0f dk önce" % d if d<120 else "%.1f sa önce" % (d/60)
g=k.get("canli_gfs") or {}
s=k.get("sigmet") or {}
kosu=g.get("model_calisma_zamani")
try:
    kosu_metni=datetime.fromisoformat(str(kosu).replace("Z","+00:00")).strftime("%d.%m %HZ") if kosu else "bilinmiyor"
except ValueError:
    kosu_metni=str(kosu)
hata=(" · hata: %s" % g["son_hata"]) if g.get("son_hata") else ""
print("  Canlı GFS : %s · koşu %s · son indirme %s%s" % (g.get("durum","?"), kosu_metni, yas(g.get("son_basarili_indirme")), hata))
print("  SIGMET    : %s · son güncelleme %s · otomatik %s dk" % (s.get("durum","?"), yas(s.get("son_basarili_guncelleme")), s.get("otomatik_guncelleme_dakika","?")))'
fi
echo
echo "Operasyonel değildir; karar destek aracıdır. Çıktılar sertifikalı EDR değildir."
