#!/usr/bin/env bash
# Detiene los procesos enviando SIGTERM (cierre ordenado).
cd "$(dirname "$0")/../.."
for p in web simulador; do
  if [[ -f run/$p.pid ]]; then kill -TERM "$(cat run/$p.pid)" 2>/dev/null && echo "$p detenido (PID $(cat run/$p.pid))"; rm -f run/$p.pid; fi
done
