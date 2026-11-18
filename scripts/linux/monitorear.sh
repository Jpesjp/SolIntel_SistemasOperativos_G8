#!/usr/bin/env bash
# Monitoreo de SolIntel: SO, CPU, memoria, disco, procesos, puertos, salud del servicio y auditoria.
# Uso: monitorear.sh [--silencioso]   (guarda el reporte en evidencias/monitoreo/)
cd "$(dirname "$0")/../.."
PUERTO="${SOLINTEL_PUERTO:-8080}"
SALIDA="evidencias/monitoreo/monitoreo_$(date +%Y%m%d_%H%M%S).txt"
mkdir -p evidencias/monitoreo
{
echo "=== SolIntel - Monitoreo $(date '+%Y-%m-%d %H:%M:%S') en $(hostname) ==="
echo -e "\n--- Sistema operativo"; uname -srmo; [[ -f /etc/os-release ]] && grep PRETTY_NAME /etc/os-release
echo -e "\n--- Tiempo activo y carga"; uptime
echo -e "\n--- CPU"; nproc | xargs echo "Nucleos:"; top -bn1 | head -5 | tail -3
echo -e "\n--- Memoria"; free -h
echo -e "\n--- Disco"; df -h . | tail -1; du -sh data logs 2>/dev/null
echo -e "\n--- Procesos SolIntel (PID, PPID, %CPU, %MEM, hilos, tiempo, comando)"
ps -eo pid,ppid,%cpu,%mem,nlwp,etime,cmd | grep -E "servidor.py|simulador_iot.py" | grep -v grep || echo "No hay procesos en ejecucion"
echo -e "\n--- Puertos en escucha"; (ss -ltnp 2>/dev/null || netstat -ltnp 2>/dev/null) | grep -E ":$PUERTO|State|Estado" || echo "ss/netstat no disponible"
echo -e "\n--- Salud del servicio"; curl -s -m 5 -w "\nHTTP %{http_code} en %{time_total}s\n" "http://localhost:$PUERTO/api/salud" || echo "Servicio no responde"
echo -e "\n--- Auditoria (logs/solintel.log)"
if [[ -f logs/solintel.log ]]; then
  echo "Inicios de sesion correctos: $(grep -c 'login_ok' logs/solintel.log)"
  echo "Intentos fallidos:           $(grep -c 'login_fallido' logs/solintel.log)"
  echo "Bloqueos por fuerza bruta:   $(grep -c 'login_bloqueado' logs/solintel.log)"
  echo "Cambios de dispositivos:     $(grep -c 'AUDITORIA dispositivo' logs/solintel.log)"
  echo "Errores:                     $(grep -c ' ERROR ' logs/solintel.log)"
fi
} > "$SALIDA"
[[ "$1" == "--silencioso" ]] || cat "$SALIDA"
echo "Reporte: $SALIDA"
