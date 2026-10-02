#!/bin/sh
# Veritabanının günlük yedeği (docker-compose "yedek" servisi). Saatte bir bakar;
# bugünün (UTC) yedeği yoksa alır, böylece bilgisayar geç açılsa da yedek alınır.
# Yedek pg_restore ile okunabildiği doğrulanmadan yerine konmaz; en yeni
# DB_YEDEK_SAKLA_GUN dosya tutulur. Bağlantı PG* ortam değişkenlerinden okunur.
set -u
SAKLA="${DB_YEDEK_SAKLA_GUN:-7}"
while true; do
  HEDEF="/yedekler/turbulans_$(date -u +%Y%m%d).dump"
  if [ ! -s "$HEDEF" ]; then
    if pg_dump -Fc -f "$HEDEF.yaziliyor" && pg_restore -l "$HEDEF.yaziliyor" > /dev/null; then
      mv "$HEDEF.yaziliyor" "$HEDEF"
      echo "$(date -u +%FT%TZ) yedek alindi: $(basename "$HEDEF") $(du -h "$HEDEF" | cut -f1)"
      ls -1t /yedekler/turbulans_*.dump | tail -n +"$((SAKLA + 1))" | xargs -r rm -f
    else
      rm -f "$HEDEF.yaziliyor"
      echo "$(date -u +%FT%TZ) YEDEK BASARISIZ" >&2
    fi
  fi
  sleep 3600
done
