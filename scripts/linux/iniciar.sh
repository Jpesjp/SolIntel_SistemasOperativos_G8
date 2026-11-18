#!/usr/bin/env bash
# Inicia servidor web y simulador IoT en segundo plano (modo desarrollo, sin systemd).
set -e
cd "$(dirname "$0")/../.."
mkdir -p logs run
PUERTO="${SOLINTEL_PUERTO:-8080}"
if [[ -f run/web.pid ]] && kill -0 "$(cat run/web.pid)" 2>/dev/null; then echo "Ya esta en ejecucion (PID $(cat run/web.pid))"; exit 0; fi
nohup python3 src/simulador/simulador_iot.py > logs/simulador.out 2>&1 & echo $! > run/simulador.pid
nohup python3 src/backend/servidor.py --puerto "$PUERTO" > logs/web.out 2>&1 & echo $! > run/web.pid
sleep 2
echo "Servidor PID $(cat run/web.pid) | Simulador PID $(cat run/simulador.pid)"
curl -fsS "http://localhost:$PUERTO/api/salud" && echo -e "\nAbre http://localhost:$PUERTO"
