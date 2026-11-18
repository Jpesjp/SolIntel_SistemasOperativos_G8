"""
SolIntel - Servidor web y API REST (capa de logica de negocio).

Solo usa la libreria estandar de Python (no requiere instalar dependencias).

Conceptos de SO aplicados:
- Hilos: ThreadingHTTPServer atiende cada solicitud en un hilo distinto (concurrencia).
- Procesos: con --con-simulador el servidor crea el proceso hijo del simulador IoT (subprocess).
- Memoria: sesiones y cache de analisis en RAM.
- Archivos y permisos: datos por hogar en data/hogares/<uid>/, usuarios.json con permisos 600.
- Seguridad y auditoria: contrasenas PBKDF2, tokens de sesion, bloqueo por intentos fallidos,
  cabeceras de seguridad HTTP y registro de eventos en logs/solintel.log.
- Monitoreo: /api/sistema expone PID, hilos, memoria, carga, disco y estado del simulador.

Uso:
    python src/backend/servidor.py [--puerto 8080] [--con-simulador]
"""
import argparse
import json
import logging
import os
import platform
import re
import secrets
import shutil
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from logging.handlers import RotatingFileHandler
from urllib.parse import parse_qs, urlparse

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, RAIZ)

from src.backend import almacen, seguridad  # noqa: E402
from src.ia import motor_ia  # noqa: E402
from src.simulador import simulador_iot  # noqa: E402

FRONTEND = os.path.join(RAIZ, "src", "frontend")
CONFIG = almacen.leer_json(os.path.join(RAIZ, "config", "solintel.json"), {})
TARIFA = float(os.environ.get("SOLINTEL_TARIFA", CONFIG.get("tarifa_cop_kwh", 900)))
INICIO = time.time()
TIPOS = {".html": "text/html; charset=utf-8", ".js": "application/javascript; charset=utf-8",
         ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml", ".png": "image/png",
         ".json": "application/json", ".ico": "image/x-icon"}
ESTADOS = {"activa", "apagada", "standby"}

os.makedirs(os.path.join(RAIZ, "logs"), exist_ok=True)
log = logging.getLogger("solintel")
log.setLevel(logging.INFO)
if not log.handlers:
    _h = RotatingFileHandler(os.path.join(RAIZ, "logs", "solintel.log"), maxBytes=1_000_000, backupCount=5,
                             encoding="utf-8")
    _h.setFormatter(logging.Formatter("%(asctime)s [%(process)d:%(threadName)s] %(levelname)s %(message)s"))
    log.addHandler(_h)


class ErrorApi(Exception):
    def __init__(self, codigo, mensaje):
        super().__init__(mensaje)
        self.codigo, self.mensaje = codigo, mensaje


# ----------------------------------------------------------------- datos de usuarios y hogares
def _usuarios():
    return almacen.leer_json(almacen.ruta("usuarios.json"), {})


def crear_usuario(nombre, correo, clave):
    correo = correo.strip().lower()
    if not seguridad.RE_CORREO.match(correo):
        raise ErrorApi(400, "Correo electrónico no válido.")
    if not seguridad.validar_clave(clave):
        raise ErrorApi(400, "La contraseña debe tener mínimo 8 caracteres, letras y números.")
    with almacen.bloqueo("usuarios"):
        usuarios = _usuarios()
        if correo in usuarios:
            raise ErrorApi(409, "Ya existe una cuenta con ese correo.")
        uid = "h" + secrets.token_hex(6)
        usuarios[correo] = {"uid": uid, "nombre": nombre.strip()[:60] or "Mi hogar", "correo": correo,
                            "clave": seguridad.hash_clave(clave), "creado": datetime.now().isoformat(timespec="seconds"),
                            "rol": "residente"}
        almacen.escribir_json(almacen.ruta("usuarios.json"), usuarios, privado=True)
    d = almacen.dir_hogar(uid)
    almacen.escribir_json(os.path.join(d, "hogar.json"), {
        "nombre": usuarios[correo]["nombre"], "tipo_vivienda": "Apartamento familiar", "ciudad": "Bogotá",
        "estrato": 3, "personas": 3, "factura_promedio": 75000, "meta_ahorro_pct": 12,
        "prioridades": ["Bajar factura", "Alertas"], "configurado": False})
    almacen.escribir_json(os.path.join(d, "dispositivos.json"), simulador_iot.dispositivos_por_defecto())
    simulador_iot.generar_historial(uid, int(CONFIG.get("dias_historial", 365)))
    simulador_iot.lectura_actual(uid)
    log.info("AUDITORIA registro correo=%s uid=%s", correo, uid)
    return usuarios[correo]


def usuario_por_uid(uid):
    return next((u for u in _usuarios().values() if u["uid"] == uid), None)


def asegurar_demo():
    demo = CONFIG.get("usuario_demo")
    if demo and demo["correo"] not in _usuarios():
        crear_usuario(demo["nombre"], demo["correo"], demo["clave"])
        print(f"Usuario demo creado: {demo['correo']} / {demo['clave']}")


def archivo(uid, nombre):
    return os.path.join(almacen.dir_hogar(uid), nombre)


def analisis(uid):
    simulador_iot.rellenar(uid)  # sincroniza horas faltantes si el simulador no esta corriendo
    return motor_ia.analizar(archivo(uid, "consumo.csv"))


def hogar(uid):
    return almacen.leer_json(archivo(uid, "hogar.json"), {})


def estado_simulador():
    try:
        pid = int(open(almacen.ruta("simulador.pid")).read().strip())
        os.kill(pid, 0)
        return {"activo": True, "pid": pid}
    except (OSError, ValueError):
        return {"activo": False, "pid": None}


# ----------------------------------------------------------------- manejadores de la API
def api_registro(_, cuerpo, __):
    u = crear_usuario(cuerpo.get("nombre", ""), cuerpo.get("correo", ""), cuerpo.get("clave", ""))
    return 201, {"token": seguridad.crear_sesion(u["uid"], CONFIG.get("sesion_horas", 8)), "nombre": u["nombre"],
                 "configurado": False}


def api_login(_, cuerpo, h):
    correo = str(cuerpo.get("correo", "")).strip().lower()
    if seguridad.bloqueado(correo):
        log.warning("AUDITORIA login_bloqueado correo=%s ip=%s", correo, h.client_address[0])
        raise ErrorApi(429, "Demasiados intentos fallidos. Espera 5 minutos.")
    u = _usuarios().get(correo)
    ok = bool(u) and seguridad.verificar_clave(str(cuerpo.get("clave", "")), u["clave"])
    seguridad.registrar_intento(correo, ok)
    log.info("AUDITORIA login_%s correo=%s ip=%s", "ok" if ok else "fallido", correo, h.client_address[0])
    if not ok:
        raise ErrorApi(401, "Correo o contraseña incorrectos.")
    return 200, {"token": seguridad.crear_sesion(u["uid"], CONFIG.get("sesion_horas", 8)), "nombre": u["nombre"],
                 "configurado": hogar(u["uid"]).get("configurado", True)}


def api_logout(uid, _, h):
    seguridad.cerrar_sesion(h.token)
    log.info("AUDITORIA logout uid=%s", uid)
    return 200, {"ok": True}


def api_perfil(uid, cuerpo, h):
    u = usuario_por_uid(uid)
    if h.command == "PUT":
        with almacen.bloqueo("usuarios"):
            usuarios = _usuarios()
            if cuerpo.get("clave_nueva"):
                if not seguridad.verificar_clave(cuerpo.get("clave_actual", ""), usuarios[u["correo"]]["clave"]):
                    raise ErrorApi(400, "La contraseña actual no es correcta.")
                if not seguridad.validar_clave(cuerpo["clave_nueva"]):
                    raise ErrorApi(400, "La nueva contraseña debe tener mínimo 8 caracteres, letras y números.")
                usuarios[u["correo"]]["clave"] = seguridad.hash_clave(cuerpo["clave_nueva"])
                log.info("AUDITORIA cambio_clave uid=%s", uid)
            if cuerpo.get("nombre"):
                usuarios[u["correo"]]["nombre"] = cuerpo["nombre"].strip()[:60]
            almacen.escribir_json(almacen.ruta("usuarios.json"), usuarios, privado=True)
            u = usuarios[u["correo"]]
    return 200, {k: u[k] for k in ("nombre", "correo", "creado", "rol")}


def api_hogar(uid, cuerpo, h):
    datos = hogar(uid)
    if h.command == "PUT":
        for k, tipo in (("nombre", str), ("tipo_vivienda", str), ("ciudad", str), ("estrato", int),
                        ("personas", int), ("factura_promedio", int), ("meta_ahorro_pct", int), ("prioridades", list)):
            if k in cuerpo:
                try:
                    datos[k] = tipo(cuerpo[k])
                except (TypeError, ValueError):
                    raise ErrorApi(400, f"Valor no válido para {k}.")
        if not (1000 <= datos["factura_promedio"] <= 5_000_000) or not (1 <= datos["meta_ahorro_pct"] <= 50):
            raise ErrorApi(400, "Factura o meta fuera de rango.")
        datos["configurado"] = True
        almacen.escribir_json(archivo(uid, "hogar.json"), datos)
    datos["meta_kwh"] = motor_ia.meta_kwh(datos, TARIFA)
    datos["tarifa_cop_kwh"] = TARIFA
    return 200, datos


def api_dashboard(uid, _, __):
    a = analisis(uid)
    r = motor_ia.resumen(a, hogar(uid), TARIFA)
    r["alertas"] = motor_ia.alertas(a, hogar(uid), TARIFA)[:2]
    r["lectura"] = almacen.leer_json(archivo(uid, "lectura.json"), {})
    r["hogar"] = hogar(uid).get("nombre")
    return 200, r


def api_consumo(uid, _, h):
    periodo = h.query.get("periodo", ["dia"])[0]
    if periodo not in ("dia", "semana", "mes", "ano"):
        raise ErrorApi(400, "Periodo no válido.")
    return 200, motor_ia.consumo(analisis(uid), periodo)


def api_dispositivos(uid, cuerpo, h):
    path = archivo(uid, "dispositivos.json")
    m = re.match(r"^/api/dispositivos/([a-z]+)$", h.ruta)
    if h.command == "PUT" and m:
        if cuerpo.get("estado") not in ESTADOS:
            raise ErrorApi(400, "Estado no válido.")
        with almacen.bloqueo(f"dispositivos_{uid}"):
            disp = almacen.leer_json(path, [])
            item = next((d for d in disp if d["id"] == m.group(1)), None)
            if not item:
                raise ErrorApi(404, "Dispositivo no encontrado.")
            item["estado"] = cuerpo["estado"]
            item["actualizado"] = datetime.now().isoformat(timespec="seconds")
            almacen.escribir_json(path, disp)
        simulador_iot.lectura_actual(uid)
        log.info("AUDITORIA dispositivo uid=%s id=%s estado=%s", uid, item["id"], item["estado"])
    a = analisis(uid)
    hoy = a.disp_ultimas(24)
    lect = almacen.leer_json(archivo(uid, "lectura.json"), {}).get("potencia_w", {})
    disp = almacen.leer_json(path, [])
    for d in disp:
        d["kwh_hoy"] = round(hoy.get(d["id"], 0), 2)
        d["potencia_actual_w"] = lect.get(d["id"], 0)
    return 200, {"dispositivos": disp, "sugerencia": motor_ia.recomendaciones(a, TARIFA)[0]}


def api_alertas(uid, _, __):
    return 200, {"alertas": motor_ia.alertas(analisis(uid), hogar(uid), TARIFA)}


def api_recomendaciones(uid, _, __):
    recs = motor_ia.recomendaciones(analisis(uid), TARIFA)
    return 200, {"recomendaciones": recs, "ahorro_total_cop_mes": sum(r["ahorro_cop_mes"] for r in recs)}


def api_reportes(uid, _, h):
    tipo = h.query.get("tipo", ["mensual"])[0]
    if tipo not in ("mensual", "trimestral", "anual"):
        raise ErrorApi(400, "Tipo de reporte no válido.")
    return 200, motor_ia.reporte(analisis(uid), hogar(uid), TARIFA, tipo)


def api_plan(uid, cuerpo, h):
    path = archivo(uid, "plan.json")
    a = analisis(uid)
    recs = motor_ia.recomendaciones(a, TARIFA)
    plan = almacen.leer_json(path, {"hechos": []})
    if h.command == "PUT":
        validos = {r["id"] for r in recs}
        plan = {"hechos": [x for x in cuerpo.get("hechos", []) if x in validos],
                "actualizado": datetime.now().isoformat(timespec="seconds")}
        almacen.escribir_json(path, plan)
    habitos = [{"id": r["id"], "titulo": r["titulo"], "ahorro_cop_mes": r["ahorro_cop_mes"],
                "hecho": r["id"] in plan["hechos"]} for r in recs]
    return 200, {"meta_ahorro_pct": hogar(uid).get("meta_ahorro_pct", 12), "habitos": habitos,
                 **motor_ia.avance_plan(a, hogar(uid), TARIFA)}


def api_sistema(_, __, ___):
    try:
        import resource
        mem_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    except ImportError:
        mem_kb = None
    try:
        carga = [round(x, 2) for x in os.getloadavg()]
    except (AttributeError, OSError):
        carga = None
    disco = shutil.disk_usage(almacen.DIR_DATOS)
    tam = sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(almacen.DIR_DATOS) for f in fs)
    return 200, {
        "sistema_operativo": platform.platform(), "python": platform.python_version(), "equipo": platform.node(),
        "pid": os.getpid(), "ppid": os.getppid(), "hilos_activos": threading.active_count(),
        "uptime_seg": round(time.time() - INICIO), "memoria_max_kb": mem_kb, "carga_promedio": carga,
        "disco": {"total_gb": round(disco.total / 1e9, 1), "libre_gb": round(disco.free / 1e9, 1),
                  "uso_pct": round(disco.used / disco.total * 100, 1)},
        "datos_mb": round(tam / 1e6, 2), "usuarios": len(_usuarios()), "sesiones_activas": seguridad.sesiones_activas(),
        "cache_ia": dict(motor_ia.estadisticas_cache), "simulador": estado_simulador(),
    }


RUTAS = [  # (metodo, patron, manejador, requiere_sesion)
    ("POST", r"^/api/registro$", api_registro, False),
    ("POST", r"^/api/login$", api_login, False),
    ("POST", r"^/api/logout$", api_logout, True),
    ("GET|PUT", r"^/api/perfil$", api_perfil, True),
    ("GET|PUT", r"^/api/hogar$", api_hogar, True),
    ("GET", r"^/api/dashboard$", api_dashboard, True),
    ("GET", r"^/api/consumo$", api_consumo, True),
    ("GET", r"^/api/dispositivos$", api_dispositivos, True),
    ("PUT", r"^/api/dispositivos/[a-z]+$", api_dispositivos, True),
    ("GET", r"^/api/alertas$", api_alertas, True),
    ("GET", r"^/api/recomendaciones$", api_recomendaciones, True),
    ("GET", r"^/api/reportes$", api_reportes, True),
    ("GET|PUT", r"^/api/plan$", api_plan, True),
    ("GET", r"^/api/sistema$", api_sistema, True),
]


class Manejador(BaseHTTPRequestHandler):
    server_version = "SolIntel/1.0"
    sys_version = ""

    def log_message(self, fmt, *args):
        log.info("ACCESO %s %s", self.client_address[0], fmt % args)

    def _cabeceras(self, codigo, tipo, largo):
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(largo))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy",
                         "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:")
        self.end_headers()

    def _json(self, codigo, datos):
        b = json.dumps(datos, ensure_ascii=False).encode()
        self._cabeceras(codigo, "application/json; charset=utf-8", len(b))
        self.wfile.write(b)

    def _api(self):
        u = urlparse(self.path)
        self.ruta, self.query = u.path.rstrip("/") or "/", parse_qs(u.query)
        if self.ruta == "/api/salud":
            return self._json(200, {"estado": "ok", "pid": os.getpid(), "simulador": estado_simulador()})
        for metodo, patron, fn, auth in RUTAS:
            if self.command in metodo.split("|") and re.match(patron, self.ruta):
                break
        else:
            return self._json(404, {"error": "Ruta no encontrada."})
        try:
            uid = None
            if auth:
                self.token = self.headers.get("Authorization", "").removeprefix("Bearer ").strip()
                uid = seguridad.usuario_de(self.token)
                if not uid:
                    raise ErrorApi(401, "Sesión no válida o expirada.")
            cuerpo = {}
            largo = int(self.headers.get("Content-Length", 0) or 0)
            if largo > CONFIG.get("max_cuerpo_bytes", 65536):
                raise ErrorApi(413, "Solicitud demasiado grande.")
            if largo:
                try:
                    cuerpo = json.loads(self.rfile.read(largo))
                except json.JSONDecodeError:
                    raise ErrorApi(400, "JSON no válido.")
            codigo, datos = fn(uid, cuerpo, self)
            self._json(codigo, datos)
        except ErrorApi as e:
            self._json(e.codigo, {"error": e.mensaje})
        except Exception:  # noqa: BLE001
            log.exception("Error interno en %s", self.ruta)
            self._json(500, {"error": "Error interno del servidor."})

    def _estatico(self):
        rel = urlparse(self.path).path.lstrip("/") or "index.html"
        path = os.path.normpath(os.path.join(FRONTEND, rel))
        if not path.startswith(FRONTEND) or not os.path.isfile(path):
            path = os.path.join(FRONTEND, "index.html")  # SPA: rutas desconocidas cargan la app
        with open(path, "rb") as f:
            b = f.read()
        self._cabeceras(200, TIPOS.get(os.path.splitext(path)[1], "application/octet-stream"), len(b))
        self.wfile.write(b)

    def do_GET(self):
        self._api() if self.path.startswith("/api/") else self._estatico()

    def do_POST(self):
        self._api()

    def do_PUT(self):
        self._api()


def crear_servidor(host, puerto):
    asegurar_demo()
    srv = ThreadingHTTPServer((host, puerto), Manejador)
    srv.daemon_threads = True
    return srv


def main():
    p = argparse.ArgumentParser(description="Servidor web SolIntel")
    p.add_argument("--host", default=os.environ.get("SOLINTEL_HOST", CONFIG.get("host", "0.0.0.0")))
    p.add_argument("--puerto", type=int, default=int(os.environ.get("SOLINTEL_PUERTO", CONFIG.get("puerto", 8080))))
    p.add_argument("--con-simulador", action="store_true", help="Inicia el simulador IoT como proceso hijo")
    a = p.parse_args()
    srv = crear_servidor(a.host, a.puerto)
    hijo = None
    if a.con_simulador and not estado_simulador()["activo"]:
        hijo = subprocess.Popen([sys.executable, os.path.join(RAIZ, "src", "simulador", "simulador_iot.py"),
                                 "--intervalo", str(CONFIG.get("intervalo_simulador_seg", 30))])
        print(f"Simulador IoT iniciado como proceso hijo (PID {hijo.pid})")
    signal.signal(signal.SIGTERM, lambda *_: threading.Thread(target=srv.shutdown).start())
    log.info("Servidor iniciado pid=%s en %s:%s", os.getpid(), a.host, a.puerto)
    print(f"SolIntel en http://localhost:{a.puerto}  (PID {os.getpid()})  Ctrl+C para detener")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
        if hijo:
            hijo.terminate()
            hijo.wait(5)
        log.info("Servidor detenido")


if __name__ == "__main__":
    main()
