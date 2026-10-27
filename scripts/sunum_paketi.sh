#!/usr/bin/env bash
# S-8: sunum yedeği tek komutla (WSL'de, ana depo kökünden):
#   bash scripts/sunum_paketi.sh [cikti_klasoru]
# Temiz klon (~/turbulans-demo) güncellenir, demo yığını ana yığını durdurmadan ayrı portlarla
# (5532/8100) kurulur, ekranlar ağsız provayla üretilir, imajlar `docker save` ile kaydedilir,
# her dosyanın sha256'sı SHA256SUMS'a yazılır ve demo yığını durdurulur (veri silinmez).
set -euo pipefail

ANA_DEPO="$(cd "$(dirname "$0")/.." && pwd)"
KLON="${KLON:-$HOME/turbulans-demo}"
CIKTI="${1:-$HOME/sunum_paketi_$(date -u +%Y%m%d)}"
PORTLAR="$HOME/demo_portlar.yml"
VENV="${VENV:-$HOME/.venvs/turbulans/bin}"

if [ ! -d "$KLON/.git" ]; then
  git clone "$ANA_DEPO" "$KLON"
fi
git -C "$KLON" pull --ff-only
[ -f "$KLON/.env" ] || cp "$KLON/.env.demo" "$KLON/.env"

cat > "$PORTLAR" <<'YAML'
services:
  db:
    ports: !override ["127.0.0.1:5532:5432"]
  api:
    ports: !override ["127.0.0.1:8100:8000"]
    networks: !override [default]
networks:
  vekil_agi:
    ipam: !override
      config:
        - subnet: 172.31.251.0/24
YAML

DOSYALAR=(-f docker-compose.yml)
[ -f "$KLON/docker-compose.override.yml" ] && DOSYALAR+=(-f docker-compose.override.yml)
DOSYALAR+=(-f "$PORTLAR")
compose() { (cd "$KLON" && docker compose "${DOSYALAR[@]}" --profile demo "$@"); }

GIT_SHA="$(git -C "$KLON" rev-parse HEAD)"
export GIT_SHA
mkdir -p "$CIKTI/ekranlar"
compose up -d --build --wait --wait-timeout 600
DEMO_CIKISI="$(docker wait "$(compose ps -a -q demo)")"
[ "$DEMO_CIKISI" = 0 ] || { echo "demo çıkış kodu $DEMO_CIKISI" >&2; exit 1; }
compose logs --no-color demo > "$CIKTI/demo_ozeti.log"
grep -q "ÖZET:" "$CIKTI/demo_ozeti.log" || { echo "demo özeti yok, $CIKTI/demo_ozeti.log" >&2; exit 1; }

(cd "$ANA_DEPO" && TURBULANS_API_ANAHTARI=demo-yerel-yonetici "$VENV/turbulans-demo-ekranlari" \
  --agsiz --taban-url http://localhost:8100 --klasor "$CIKTI/ekranlar") | tee "$CIKTI/ekran_provasi.log"

mapfile -t IMAJLAR < <(compose config --images | sort -u)
docker save -o "$CIKTI/imajlar.tar" "${IMAJLAR[@]}"
printf '%s\n' "commit $GIT_SHA" "imajlar ${IMAJLAR[*]}" "uretim $(date -u +%FT%TZ)" > "$CIKTI/BILGI.txt"
compose stop

(cd "$CIKTI" && find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS)
echo "Sunum paketi: $CIKTI ($(du -sh "$CIKTI" | cut -f1)); geri yükleme: docker load -i imajlar.tar"
