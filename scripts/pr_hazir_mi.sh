#!/usr/bin/env bash
# Birleştirmeden önce: bash scripts/pr_hazir_mi.sh <pr_no> [--bekle]
# En az bir CI kontrolü raporlanmış ve hepsi pass/skipping ise 0 döner. Push'tan hemen sonra
# "no checks reported" yanıtı geçti sayılmaz (27 Ekim #137). --bekle kontroller bitene kadar bekler.
set -euo pipefail

PR="${1:?PR numarası gerekli}"
BEKLE="${2:-}"

for _ in $(seq 1 60); do
  durum="$(gh pr checks "$PR" --json bucket --jq '[.[].bucket] | group_by(.) | map("\(.[0])=\(length)") | join(" ")' 2>/dev/null || true)"
  if [ -z "$durum" ]; then
    echo "#$PR: henüz kontrol raporlanmadı"
  elif [[ "$durum" == *pending* ]]; then
    echo "#$PR: sürüyor ($durum)"
  elif [[ "$durum" == *fail* || "$durum" == *cancel* ]]; then
    echo "#$PR: HAZIR DEĞİL ($durum)"
    exit 1
  else
    echo "#$PR: hazır ($durum)"
    exit 0
  fi
  [ "$BEKLE" = "--bekle" ] || exit 1
  sleep 30
done
echo "#$PR: 30 dk içinde bitmedi"
exit 1
