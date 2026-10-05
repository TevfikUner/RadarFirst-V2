#!/bin/sh
# Günlük yedek (docker-compose "yedek" servisi): veritabanı (pg_dump) ve
# veritabanında olmayan, yeniden indirmesi pahalı dosyalar (ERA5 pencere deposu,
# MADIS EDR, OpenSky rota önbelleği, model sürümleri; /kaynak altına salt okunur bağlanır).
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

# İsteğe bağlı disk dışı kopya: /dis_yedek bağlıysa (docker-compose.override.yml,
# örn. OneDrive klasörü) yeni yedekler oraya da kopyalanır. Parola secret'ı
# (YEDEK_PAROLA_DOSYASI) doluysa kopya gpg AES256 ile şifrelenir (*.gpg) ve aynı
# yedeğin şifresiz eski kopyası silinir. Başarısızlık yerel yedeği etkilemez; bir
# sonraki turda yeniden denenir. Yedek dosyaları adlandıktan sonra değişmez.
PAROLA=/run/secrets/yedek_parolasi

sifreli_mi() {
  [ -s "$PAROLA" ]
}

dis_kopyala() {
  [ -d /dis_yedek ] || return 0
  sifreli_mi || echo "$(date -u +%FT%TZ) UYARI: yedek parolasi yok, dis kopya SIFRESIZ" >&2
  for kaynak in /yedekler/turbulans_*.dump /yedekler/dosyalar_*.tar.gz; do
    [ -s "$kaynak" ] || continue
    hedef="/dis_yedek/$(basename "$kaynak")"
    if sifreli_mi; then
      if [ -s "$hedef.gpg" ]; then
        rm -f "$hedef"
        continue
      fi
      mkdir -p -m 700 /tmp/gnupg
      if gpg --homedir /tmp/gnupg --batch --yes --pinentry-mode loopback --passphrase-file "$PAROLA" \
          --symmetric --cipher-algo AES256 --compress-algo none -o "$hedef.gpg.yaziliyor" "$kaynak" \
          && mv "$hedef.gpg.yaziliyor" "$hedef.gpg"; then
        rm -f "$hedef"
        echo "$(date -u +%FT%TZ) dis kopya (sifreli): $(basename "$hedef").gpg"
      else
        rm -f "$hedef.gpg.yaziliyor"
        echo "$(date -u +%FT%TZ) DIS KOPYA BASARISIZ: $(basename "$hedef").gpg" >&2
      fi
      continue
    fi
    if [ -s "$hedef" ] && cmp -s "$kaynak" "$hedef"; then
      continue
    fi
    if cp "$kaynak" "$hedef.yaziliyor" && mv "$hedef.yaziliyor" "$hedef"; then
      echo "$(date -u +%FT%TZ) dis kopya: $(basename "$hedef")"
    else
      rm -f "$hedef.yaziliyor"
      echo "$(date -u +%FT%TZ) DIS KOPYA BASARISIZ: $(basename "$hedef")" >&2
    fi
  done
  for desen in 'turbulans_*.dump' 'dosyalar_*.tar.gz' 'turbulans_*.dump.gpg' 'dosyalar_*.tar.gz.gpg'; do
    ls -1t /dis_yedek/$desen 2>/dev/null | tail -n +"$((SAKLA + 1))" | xargs -r rm -f
  done
}

while true; do
  GUN="$(date -u +%Y%m%d)"
  dis_kopyala
  if veritabani_yedegi "$GUN" && dosya_yedegi "$GUN"; then
    dis_kopyala
    sleep 3600
  else
    sleep "$YENIDEN"
  fi
done
