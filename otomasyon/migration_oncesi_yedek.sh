#!/bin/sh
# P1-2: "migrate" servisi şemayı güncellemeden önce her açılışta bir yedek (docker-compose
# "migrate_yedegi"). Yedek okunabildiği doğrulanmadan yerine konmaz; başarısızsa migration
# (ve dolayısıyla API) başlamaz. En yeni MIGRATION_YEDEK_SAKLA dosya tutulur.
set -u
SAKLA="${MIGRATION_YEDEK_SAKLA:-5}"
KLASOR=/yedekler/migration_oncesi
mkdir -p "$KLASOR"
HEDEF="$KLASOR/turbulans_$(date -u +%Y%m%dT%H%M%SZ).dump"
if pg_dump -Fc -f "$HEDEF.yaziliyor" && pg_restore -l "$HEDEF.yaziliyor" > /dev/null; then
  mv "$HEDEF.yaziliyor" "$HEDEF"
  echo "$(date -u +%FT%TZ) migration oncesi yedek: $(basename "$HEDEF") $(du -h "$HEDEF" | cut -f1)"
else
  rm -f "$HEDEF.yaziliyor"
  echo "$(date -u +%FT%TZ) MIGRATION ONCESI YEDEK BASARISIZ; migration yapilmadi" >&2
  exit 1
fi
ls -1t "$KLASOR"/turbulans_*.dump 2>/dev/null | tail -n +"$((SAKLA + 1))" | xargs -r rm -f
