#!/usr/bin/env bash
# SolIntel - instalacion como servicio en Linux (Ubuntu 22.04/24.04). Ejecutar con sudo.
# Crea usuario y grupos, copia a /opt/solintel, aplica permisos, instala servicios systemd,
# tareas cron, rotacion de logs y firewall.
set -euo pipefail
DEST=/opt/solintel
ORIGEN="$(cd "$(dirname "$0")/../.." && pwd)"
[[ $EUID -eq 0 ]] || { echo "Ejecuta con sudo"; exit 1; }
paso() { echo -e "\n==> $*"; }

paso "1. Paquetes del sistema"
if [[ -z "${SOLINTEL_SIN_APT:-}" ]] && command -v apt-get >/dev/null; then apt-get update -qq && apt-get install -y -qq python3 curl ufw logrotate cron >/dev/null || true; fi
python3 --version

paso "2. Usuarios y grupos"
getent group solintel >/dev/null || groupadd --system solintel
id solintel >/dev/null 2>&1 || useradd --system --gid solintel --home-dir "$DEST" --shell /usr/sbin/nologin solintel
getent group solintel-admin >/dev/null || groupadd solintel-admin   # equipo que puede leer logs y respaldos
[[ -n "${SUDO_USER:-}" ]] && usermod -aG solintel-admin "$SUDO_USER" || true
id solintel; getent group solintel-admin

paso "3. Copia de archivos a $DEST"
mkdir -p "$DEST"
cp -r "$ORIGEN"/{src,config,scripts,tests,data,README.md} "$DEST"/
mkdir -p "$DEST"/{logs,respaldos,evidencias}

paso "4. Permisos (principio de minimo privilegio)"
chown -R root:solintel "$DEST"
find "$DEST" -type d -exec chmod 750 {} +
find "$DEST" -type f -exec chmod 640 {} +
chmod 750 "$DEST"/scripts/linux/*.sh
chown -R solintel:solintel "$DEST"/data "$DEST"/logs
chown -R solintel:solintel-admin "$DEST"/respaldos "$DEST"/evidencias
find "$DEST"/data -name usuarios.json -exec chmod 600 {} +
chmod 700 "$DEST"/data; chmod 770 "$DEST"/respaldos "$DEST"/evidencias
chmod 2750 "$DEST"/logs; chgrp solintel-admin "$DEST"/logs
ls -ld "$DEST" "$DEST"/data "$DEST"/logs "$DEST"/respaldos "$DEST"/src

paso "5. Servicios systemd"
if command -v systemctl >/dev/null && [[ -d /run/systemd/system ]]; then
  cp "$DEST"/config/systemd/*.service /etc/systemd/system/
  systemctl daemon-reload
  systemctl enable --now solintel-web.service solintel-simulador.service
  systemctl --no-pager status solintel-web.service solintel-simulador.service | head -20
else
  echo "systemd no disponible en este entorno (contenedor); se omite."
fi

paso "6. Tareas programadas (cron) y rotacion de logs"
cp "$DEST"/config/cron/solintel /etc/cron.d/solintel && chmod 644 /etc/cron.d/solintel
cp "$DEST"/config/logrotate/solintel /etc/logrotate.d/solintel && chmod 644 /etc/logrotate.d/solintel
cat /etc/cron.d/solintel | grep -v '^#'

paso "7. Firewall"
if command -v ufw >/dev/null; then bash "$DEST"/config/firewall/ufw_reglas.sh; else echo "ufw no instalado; se omite."; fi

paso "Listo. Abre http://<IP-del-servidor>:8080  (demo@solintel.co / Solintel2026)"
