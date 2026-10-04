#!/bin/sh
# Günlük yedek (docker-compose "yedek" servisi): veritabanı (pg_dump) ve
# veritabanında olmayan, yeniden indirmesi pahalı dosyalar (ERA5 pencere deposu,
# MADIS EDR, model sürümleri; /kaynak altına salt okunur bağlanır).
# Bugünün (UTC) yedeği eksikse alınır; başarısız olursa (ör. açılışta veritabanı
# henüz hazır değil) YEDEK_YENIDEN_DENEME_SANIYE sonra yeniden denenir, böylece
# bilgisayar kısa süre açık kalsa da yedek alınır. Yedek okunabildiği doğrulanmadan
# yerine konmaz; her türden en yeni DB_YEDEK_SAKLA_GUN dosya tutulur.
set -u
SAKLA="${DB_YEDEK_SAKLA_GUN:-7}"
YENIDEN="${YEDEK_YENIDEN_DENEME_SANIYE:-60}"

eskileri_sil() {
  ls -1t /yedekler/$1_*.$2 2>/dev/null | tail -n +"$((SAKLA + 1))" | xargs -r rm -f
}

veritabani_yedegi() {
  HEDEF="/yedekler/turbulans_$1.dump"
  [ -s "$HEDEF" ] && return 0
  if pg_dump -Fc -f "$HEDEF.yaziliyor" && pg_restore -l "$HEDEF.yaziliyor" > /dev/null; then
    mv "$HEDEF.yaziliyor" "$HEDEF"
    echo "$(date -u +%FT%TZ) yedek alindi: $(basename "$HEDEF") $(du -h "$HEDEF" | cut -f1)"
    eskileri_sil turbulans dump
    return 0
  fi
  rm -f "$HEDEF.yaziliyor"
  echo "$(date -u +%FT%TZ) YEDEK BASARISIZ (veritabani), ${YENIDEN} sn sonra yeniden denenecek" >&2
  return 1
}

dosya_yedegi() {
  HEDEF="/yedekler/dosyalar_$1.tar.gz"
  [ -s "$HEDEF" ] && return 0
  [ -d /kaynak ] || return 0
  # tar 1: okunurken değişen dosya (gece işi yazıyor olabilir); arşiv yine tutarlı okunabiliyorsa kabul.
  tar -czf "$HEDEF.yaziliyor" -C /kaynak .
  if [ $? -le 1 ] && tar -tzf "$HEDEF.yaziliyor" > /dev/null; then
    mv "$HEDEF.yaziliyor" "$HEDEF"
    echo "$(date -u +%FT%TZ) yedek alindi: $(basename "$HEDEF") $(du -h "$HEDEF" | cut -f1)"
    eskileri_sil dosyalar tar.gz
    return 0
  fi
  rm -f "$HEDEF.yaziliyor"
  echo "$(date -u +%FT%TZ) YEDEK BASARISIZ (dosyalar), ${YENIDEN} sn sonra yeniden denenecek" >&2
  return 1
}

while true; do
  GUN="$(date -u +%Y%m%d)"
  if veritabani_yedegi "$GUN" && dosya_yedegi "$GUN"; then
    sleep 3600
  else
    sleep "$YENIDEN"
  fi
done
