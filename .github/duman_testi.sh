#!/usr/bin/env bash
# docker compose yığınının (db + api + worker) uçtan uca duman testi -- CI'daki
# 'docker' işi çalıştırır. Yığın ayakta ve .env'de API_ANAHTARI /
# API_PILOT_ANAHTARI tanımlı olmalı.
set -euo pipefail

TABAN="${TABAN:-http://localhost:8000}"
YONETICI="$(grep '^API_ANAHTARI=' .env | cut -d= -f2-)"
PILOT="$(grep '^API_PILOT_ANAHTARI=' .env | cut -d= -f2-)"

json_alan() { python3 -c "import json,sys; print(json.load(sys.stdin)$1)"; }
kod() { curl -s -o /dev/null -w '%{http_code}' "$@"; }

echo "1) Derin sağlık: veritabanı erişilebilir"
curl -fsS "$TABAN/saglik?derin=true" | json_alan '["veritabani"]' | grep -qx erisilebilir

echo "2) Pilot anahtarı rota hesaplar (A*, yerel/canlı veri yoksa dürüst geri düşüş)"
ROTA='{"baslangic_enlem":41.0,"baslangic_boylam":28.9,"bitis_enlem":39.9,"bitis_boylam":32.8,"irtifa_ft":34000,"zaman":"2019-01-15T10:00:00","ucak_modeli":"A320"}'
test "$(kod -X POST "$TABAN/api/v1/simulasyon/rota" -H "X-API-Key: $PILOT" -H 'Content-Type: application/json' -d "$ROTA")" = 200

echo "3) Pilot anahtarı yönetici işlemine 403 alır"
test "$(kod -X DELETE "$TABAN/api/v1/kisitli-sahalar/olmayan" -H "X-API-Key: $PILOT")" = 403

echo "4) Kuyruğa giren görevi ayrı worker konteyneri tamamlar"
GOREV="$(curl -fsS -X POST "$TABAN/api/v1/backtest/toplu?limit=1" -H "X-API-Key: $YONETICI" | json_alan '["gorev_id"]')"
for _ in $(seq 1 60); do
  DURUM="$(curl -fsS "$TABAN/api/v1/analiz/durum/$GOREV" -H "X-API-Key: $YONETICI" | json_alan '["durum"]')"
  case "$DURUM" in kuyrukta|calisiyor) sleep 1 ;; *) break ;; esac
done
echo "   görev durumu: $DURUM"
test "$DURUM" = tamamlandi

echo "5) Volume'lar: model deposu var, ERA5 klasörü salt okunur, .env ve kod konteynerden erişilemez"
docker compose exec -T api test -d /app/model_deposu
docker compose exec -T api sh -c 'test -d /veri/era5_egitim_verisi && ! touch /veri/era5_egitim_verisi/.yazma_denemesi 2>/dev/null'
docker compose exec -T api sh -c '! test -e /veri/.env && ! test -e /veri/docker-compose.yml'
docker compose exec -T -u turbulans api sh -c '! test -w /app/src/turbulans_radar/api/api_servisi.py'

echo "Duman testi başarılı."
