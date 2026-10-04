#!/bin/sh
# Konteyner girişi: root olarak başlar, yalnızca yazılabilir bağlı klasörleri
# 'turbulans' (uid 1000) kullanıcısına sahiplendirir ve süreci o kullanıcıyla
# çalıştırır. Linux'ta Docker eksik bind-mount klasörlerini root olarak
# oluşturur; sahiplendirmeden uid 1000 oraya yazamaz. Windows diskinde (drvfs)
# chown etkisizdir ve sessizce geçilir.
set -e
if [ "$(id -u)" = 0 ]; then
  for klasor in ciktilar canli_veri era5_ucus_verisi era5_arco_onbellek opensky_onbellek \
    ml_ozellik_deposu madis_edr model_deposu; do
    if [ -d "/app/$klasor" ]; then
      find "/app/$klasor" ! -user turbulans -exec chown turbulans:turbulans {} + 2>/dev/null || true
    fi
  done
  exec setpriv --reuid=turbulans --regid=turbulans --init-groups "$@"
fi
exec "$@"
