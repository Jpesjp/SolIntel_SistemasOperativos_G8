#!/usr/bin/env bash
# Respaldo de los datos (tar.gz + suma SHA-256). Conserva los ultimos 7.
# Uso: respaldo.sh            -> crea respaldo
#      respaldo.sh --restaurar respaldos/solintel_datos_XXXX.tar.gz
set -euo pipefail
cd "$(dirname "$0")/../.."
mkdir -p respaldos
if [[ "${1:-}" == "--restaurar" ]]; then
  sha256sum -c "$2.sha256" && tar -xzf "$2" -C . && echo "Datos restaurados desde $2"; exit 0
fi
ARCH="respaldos/solintel_datos_$(date +%Y%m%d_%H%M%S).tar.gz"
tar --exclude='data/locks' -czf "$ARCH" data config
sha256sum "$ARCH" > "$ARCH.sha256"
chmod 640 "$ARCH" "$ARCH.sha256"
ls -1t respaldos/*.tar.gz | tail -n +8 | while read -r v; do rm -f "$v" "$v.sha256"; done
echo "Respaldo creado: $ARCH ($(du -h "$ARCH" | cut -f1))"; cat "$ARCH.sha256"
