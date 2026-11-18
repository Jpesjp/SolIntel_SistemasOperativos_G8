#!/usr/bin/env bash
# Ejecuta las pruebas automaticas y pruebas de humo de la API; guarda resultados en evidencias/pruebas/.
cd "$(dirname "$0")/../.."
mkdir -p evidencias/pruebas
PUERTO="${SOLINTEL_PUERTO:-8080}"; URL="http://localhost:$PUERTO/api"
python3 -m unittest discover -s tests -v 2>&1 | tee evidencias/pruebas/pruebas_unitarias.txt | tail -4
{
echo "=== Pruebas de humo API $(date '+%F %T') ==="
echo "-- Salud"; curl -s "$URL/salud"; echo
echo "-- Login demo"; TOKEN=$(curl -s -XPOST "$URL/login" -d '{"correo":"demo@solintel.co","clave":"Solintel2026"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['token'])")
echo "token recibido: ${TOKEN:0:8}..."
echo "-- Acceso sin token (debe ser 401)"; curl -s -o /dev/null -w "%{http_code}\n" "$URL/dashboard"
for r in dashboard "consumo?periodo=semana" alertas recomendaciones "reportes?tipo=mensual" sistema; do
  echo "-- GET /api/$r"; curl -s -w "\n[HTTP %{http_code} en %{time_total}s]\n" -H "Authorization: Bearer $TOKEN" "$URL/$r" | cut -c1-600
done
echo "-- Apagar TV (control simulado)"; curl -s -XPUT -H "Authorization: Bearer $TOKEN" "$URL/dispositivos/televisor" -d '{"estado":"apagada"}' | cut -c1-200; echo
curl -s -o /dev/null -XPUT -H "Authorization: Bearer $TOKEN" "$URL/dispositivos/televisor" -d '{"estado":"activa"}'
} | tee evidencias/pruebas/pruebas_api.txt | tail -3
