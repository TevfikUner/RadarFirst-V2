#!/bin/sh
# API/işçi için süper kullanıcı olmayan veritabanı rolünü oluşturur ya da günceller
# ve veritabanı nesnelerinin sahipliğini ona devreder (bkz. otomasyon/uygulama_rolu.sql).
# Proje kökünde, WSL'den: sh otomasyon/uygulama_rolu_olustur.sh [veritabani]
# Varsayılan veritabanı .env'deki POSTGRES_DB'dir; önce '<POSTGRES_DB>-test' ile denenir.
# Şifre .env'deki UYGULAMA_POSTGRES_PASSWORD'dür; komut satırına/loga yazılmaz.
set -eu
cd "$(dirname "$0")/.."

env_oku() {
  grep -E "^$1=" .env | tail -n 1 | cut -d= -f2-
}

SUPER="$(env_oku POSTGRES_USER)"
ROL="$(env_oku UYGULAMA_POSTGRES_USER)"
SIFRE="$(env_oku UYGULAMA_POSTGRES_PASSWORD)"
VERITABANI="${1:-$(env_oku POSTGRES_DB)}"

if [ -z "$ROL" ] || [ -z "$SIFRE" ]; then
  echo ".env'de UYGULAMA_POSTGRES_USER ve UYGULAMA_POSTGRES_PASSWORD tanımlı olmalı." >&2
  exit 1
fi
case "$SIFRE" in
  *"'"* | *"\\"*) echo "UYGULAMA_POSTGRES_PASSWORD tek tırnak ya da ters bölü içeremez." >&2; exit 1 ;;
esac

{
  printf "\\set rol '%s'\n\\set sifre '%s'\n" "$ROL" "$SIFRE"
  cat otomasyon/uygulama_rolu.sql
} | docker compose exec -T db psql -X -q -U "${SUPER:-postgres}" -d "$VERITABANI"
echo "Rol hazır: $ROL -> $VERITABANI"
