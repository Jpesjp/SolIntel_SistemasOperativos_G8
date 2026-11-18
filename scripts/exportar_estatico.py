"""
SolIntel - genera la version estatica para GitHub Pages.

Levanta el servidor en un directorio temporal, inicia sesion con la cuenta demo, guarda las
respuestas de la API en site/demo/datos.json y copia el frontend a site/.

Uso:  python scripts/exportar_estatico.py [--salida site]
"""
import argparse
import http.client
import json
import os
import shutil
import sys
import tempfile
import threading
from datetime import datetime

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ["SOLINTEL_DATOS"] = tempfile.mkdtemp(prefix="solintel_pages_")
sys.path.insert(0, RAIZ)
from src.backend import servidor  # noqa: E402

RUTAS = ["dashboard", "consumo?periodo=dia", "consumo?periodo=semana", "consumo?periodo=mes", "consumo?periodo=ano",
         "dispositivos", "alertas", "recomendaciones", "reportes?tipo=mensual", "reportes?tipo=trimestral",
         "reportes?tipo=anual", "plan", "perfil", "hogar", "sistema"]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--salida", default=os.path.join(RAIZ, "site"))
    a = p.parse_args()
    srv = servidor.crear_servidor("127.0.0.1", 0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    puerto = srv.server_address[1]

    def pedir(metodo, ruta, cuerpo=None, token=""):
        c = http.client.HTTPConnection("127.0.0.1", puerto, timeout=60)
        c.request(metodo, "/api/" + ruta, json.dumps(cuerpo) if cuerpo else None,
                  {"Authorization": "Bearer " + token, "Content-Type": "application/json"})
        r = c.getresponse()
        datos = json.loads(r.read())
        assert r.status == 200, (ruta, r.status, datos)
        return datos

    demo = servidor.CONFIG["usuario_demo"]
    token = pedir("POST", "login", {"correo": demo["correo"], "clave": demo["clave"]})["token"]
    respuestas = {r: pedir("GET", r, token=token) for r in RUTAS}
    respuestas["sistema"]["nota"] = "Instantánea tomada al generar el sitio estático"
    srv.shutdown()

    shutil.rmtree(a.salida, ignore_errors=True)
    shutil.copytree(os.path.join(RAIZ, "src", "frontend"), a.salida)
    os.makedirs(os.path.join(a.salida, "demo"))
    with open(os.path.join(a.salida, "demo", "datos.json"), "w", encoding="utf-8") as f:
        json.dump({"generado": datetime.now().strftime("%Y-%m-%d %H:%M"), "usuario": demo,
                   "respuestas": respuestas}, f, ensure_ascii=False)
    open(os.path.join(a.salida, ".nojekyll"), "w").close()
    print(f"Sitio estatico generado en {a.salida} ({len(respuestas)} respuestas de la API)")


if __name__ == "__main__":
    main()
