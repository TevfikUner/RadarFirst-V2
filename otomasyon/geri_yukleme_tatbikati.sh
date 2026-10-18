#!/bin/sh
# Geri yükleme tatbikatı (P0-8): son veritabanı yedeğini yedek konteynerinin içinde
# geçici bir PostgreSQL sunucusuna (yalnız unix soketi, ağ yok) yükler; tablo listesini,
# alembic sürümünü ve satır sayılarını canlı veritabanıyla karşılaştırır, süreyi ölçer
# ve raporu /yedekler/tatbikat/ altına yazar. Canlı veritabanına yalnız okuma sorgusu
# gider. Kullanım (yedek servisi haftada bir kendisi çalıştırır):
#   docker compose exec yedek sh /geri_yukleme_tatbikati.sh [/yedekler/turbulans_YYYYAAGG.dump]
set -u
export LC_ALL=C
DUMP="${1:-$(ls -1t /yedekler/turbulans_*.dump 2>/dev/null | head -n 1)}"
RAPOR_KLASORU=/yedekler/tatbikat
[ -s "$DUMP" ] || { echo "tatbikat: yedek bulunamadi" >&2; exit 2; }
mkdir -p "$RAPOR_KLASORU"

GECICI="$(mktemp -d)"
chown postgres "$GECICI"
temizle() {
  gosu postgres pg_ctl -D "$GECICI/veri" -m immediate stop > /dev/null 2>&1
  rm -rf "$GECICI"
}
trap temizle EXIT

sorgu_sayimlari() {
  psql -X -At -h "$1" -U "$2" -d "$3" -c "
    SELECT format('SELECT %L || ''|'' || count(*) FROM %I.%I;', table_name, table_schema, table_name)
    FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
    ORDER BY table_name" | psql -X -At -h "$1" -U "$2" -d "$3" | sort -t'|' -k1,1
}

BASLANGIC=$(date +%s)
gosu postgres initdb -D "$GECICI/veri" -A trust -U postgres > /dev/null || exit 3
gosu postgres pg_ctl -D "$GECICI/veri" -o "-k $GECICI -c listen_addresses=''" -w start > /dev/null || exit 3
createdb -h "$GECICI" -U postgres tatbikat || exit 3
pg_restore -h "$GECICI" -U postgres -d tatbikat --no-owner --no-acl --exit-on-error "$DUMP" 2> "$GECICI/restore.log"
RESTORE_KODU=$?
SURE=$(( $(date +%s) - BASLANGIC ))

sorgu_sayimlari "$GECICI" postgres tatbikat > "$GECICI/yedek.txt"
sorgu_sayimlari "$PGHOST" "$PGUSER" "$PGDATABASE" > "$GECICI/canli.txt"
YEDEK_ALEMBIC=$(psql -X -At -h "$GECICI" -U postgres -d tatbikat -c "SELECT version_num FROM alembic_version" 2>/dev/null)
CANLI_ALEMBIC=$(psql -X -At -c "SELECT version_num FROM alembic_version" 2>/dev/null)

SONUC=GECTI
NEDEN=""
[ -s "$GECICI/yedek.txt" ] && [ -s "$GECICI/canli.txt" ] || { SONUC=KALDI; NEDEN="$NEDEN satir_sayimi_bos"; }
[ "$RESTORE_KODU" -eq 0 ] || { SONUC=KALDI; NEDEN="$NEDEN pg_restore=$RESTORE_KODU"; }
[ -n "$YEDEK_ALEMBIC" ] && [ "$YEDEK_ALEMBIC" = "$CANLI_ALEMBIC" ] || { SONUC=KALDI; NEDEN="$NEDEN alembic($YEDEK_ALEMBIC/$CANLI_ALEMBIC)"; }
EKSIK=$(cut -d'|' -f1 "$GECICI/canli.txt" | while read -r tablo; do grep -q "^$tablo|" "$GECICI/yedek.txt" || echo "$tablo"; done)
[ -z "$EKSIK" ] || { SONUC=KALDI; NEDEN="$NEDEN eksik_tablo($(echo $EKSIK | tr ' ' ','))"; }
# Canlı veri yedekten sonra büyüyebilir; yarıdan fazla eksik satır yedeğin bozuk olduğunu gösterir.
DUSUK=$(join -t'|' "$GECICI/yedek.txt" "$GECICI/canli.txt" | awk -F'|' '$3 > 100 && $2 * 2 < $3 {print $1}')
[ -z "$DUSUK" ] || { SONUC=KALDI; NEDEN="$NEDEN az_satir($(echo $DUSUK | tr ' ' ','))"; }

GUN="$(date -u +%Y%m%d)"
RAPOR="$RAPOR_KLASORU/tatbikat_$GUN.txt"
{
  echo "tarih: $(date -u +%FT%TZ)"
  echo "yedek: $(basename "$DUMP") ($(du -h "$DUMP" | cut -f1), $(date -u -r "$DUMP" +%FT%TZ))"
  echo "sonuc: $SONUC${NEDEN:+ -$NEDEN}"
  echo "geri_yukleme_suresi_sn: $SURE"
  echo "alembic: yedek=$YEDEK_ALEMBIC canli=$CANLI_ALEMBIC"
  echo "tablo|yedek_satir|canli_satir"
  join -t'|' -a 2 -e '-' -o '0,1.2,2.2' "$GECICI/yedek.txt" "$GECICI/canli.txt"
  [ "$RESTORE_KODU" -eq 0 ] || { echo "pg_restore hatasi:"; tail -n 5 "$GECICI/restore.log"; }
} > "$RAPOR.yaziliyor" && mv "$RAPOR.yaziliyor" "$RAPOR"
ls -1t "$RAPOR_KLASORU"/tatbikat_*.txt 2>/dev/null | tail -n +13 | xargs -r rm -f
echo "$(date -u +%FT%TZ) geri yukleme tatbikati: $SONUC (${SURE} sn) -> $(basename "$RAPOR")"
[ "$SONUC" = GECTI ]
