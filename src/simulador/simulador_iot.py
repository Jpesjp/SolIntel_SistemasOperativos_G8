"""
SolIntel - Simulador IoT (proceso independiente).

Concepto de SO aplicado:
- Proceso independiente: se ejecuta aparte del servidor web (servicio systemd / tarea programada) y
  escribe su PID en data/simulador.pid para poder monitorearlo y detenerlo.
- Planificacion: cada N segundos revisa todos los hogares y completa las horas faltantes del historial
  (catch-up), igual que una tarea cron.
- Senales: atiende SIGTERM/SIGINT para terminar de forma ordenada y borrar su PID.
- Dispositivos como perifericos virtuales: respeta el estado (activa / apagada / standby) que el usuario
  cambia desde la web.

Uso:
    python src/simulador/simulador_iot.py              # bucle continuo (intervalo de config)
    python src/simulador/simulador_iot.py --una-vez    # una sola pasada (cron)
"""
import argparse
import csv
import hashlib
import logging
import os
import random
import signal
import sys
import time
from datetime import datetime, timedelta

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, RAIZ)

from src.backend import almacen  # noqa: E402
from src.simulador.generador_datos import DISPOSITIVOS  # noqa: E402

CATALOGO = {  # id: (nombre visible, ubicacion, consumo en standby W)
    "nevera": ("Nevera", "Cocina", 0),
    "lavadora": ("Lavadora", "Patio de ropas", 3),
    "iluminacion": ("Iluminación", "Toda la casa", 0),
    "televisor": ("TV sala", "Sala", 5),
    "computador": ("Computador", "Estudio", 4),
    "cargadores": ("Cargadores", "Habitaciones", 2),
    "microondas": ("Microondas", "Cocina", 3),
    "plancha": ("Plancha", "Habitación", 0),
}
COLUMNAS = ["timestamp", "dispositivo", "estado", "minutos_encendido", "energia_kwh"]
FMT = "%Y-%m-%d %H:%M"
_activo = True


def dispositivos_por_defecto():
    return [{"id": d, "nombre": n, "ubicacion": u, "potencia_w": DISPOSITIVOS[d][0], "estado": "activa"}
            for d, (n, u, _) in CATALOGO.items()]


def _rng(uid, extra=""):
    return random.Random(int(hashlib.sha256(f"{uid}{extra}".encode()).hexdigest()[:12], 16))


def simular_hora(rng, dispositivo, hora, estado="activa"):
    """Devuelve (estado, minutos, kwh) de un dispositivo en una hora segun su estado."""
    pot, horas, prob = DISPOSITIVOS[dispositivo]
    if estado == "apagada":
        return 0, 0, 0.0
    if estado == "standby":
        return 0, 60, round(CATALOGO[dispositivo][2] / 1000, 4)
    if hora in horas and rng.random() < prob:
        minutos = rng.randint(10, 60)
        return 1, minutos, round(pot * rng.uniform(0.9, 1.1) * minutos / 60 / 1000, 4)
    return 0, 0, 0.0


def ultima_hora_completa():
    return datetime.now().replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)


def generar_historial(uid, dias=365):
    """Crea el historial inicial del hogar (datos simulados reproducibles por hogar)."""
    rng = _rng(uid)
    fin = ultima_hora_completa()
    momento = fin - timedelta(days=dias) + timedelta(hours=1)
    path = os.path.join(almacen.dir_hogar(uid), "consumo.csv")
    with almacen.bloqueo(f"consumo_{uid}"):
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(COLUMNAS)
            while momento <= fin:
                # variacion estacional suave: mas consumo en meses de lluvia/frio
                factor = 1 + 0.12 * (momento.month in (4, 5, 10, 11)) + (0.08 if momento.weekday() >= 4 else 0)
                for d in DISPOSITIVOS:
                    e, m, k = simular_hora(rng, d, momento.hour)
                    w.writerow([momento.strftime(FMT), d, e, m, round(k * factor, 4)])
                momento += timedelta(hours=1)
    return path


def _ultimo_timestamp(path):
    with open(path, "rb") as f:
        f.seek(0, os.SEEK_END)
        f.seek(max(0, f.tell() - 400))
        ultima = f.read().decode("utf-8").strip().splitlines()[-1]
    return datetime.strptime(ultima.split(",")[0], FMT)


def rellenar(uid):
    """Agrega las horas que faltan hasta la ultima hora completa. Devuelve cuantas horas agrego."""
    path = os.path.join(almacen.dir_hogar(uid), "consumo.csv")
    if not os.path.exists(path):
        generar_historial(uid)
        return -1
    estados = {d["id"]: d["estado"] for d in
               almacen.leer_json(os.path.join(almacen.dir_hogar(uid), "dispositivos.json"), [])}
    fin = ultima_hora_completa()
    with almacen.bloqueo(f"consumo_{uid}"):
        momento = _ultimo_timestamp(path) + timedelta(hours=1)
        rng = _rng(uid, momento.isoformat())
        n = 0
        with open(path, "a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            while momento <= fin:
                for d in DISPOSITIVOS:
                    e, m, k = simular_hora(rng, d, momento.hour, estados.get(d, "activa"))
                    w.writerow([momento.strftime(FMT), d, e, m, k])
                momento += timedelta(hours=1)
                n += 1
    return n


def lectura_actual(uid):
    """Potencia instantanea simulada (W) por dispositivo; la usa el dashboard en vivo."""
    rng = random.Random()
    hora = datetime.now().hour
    disp = almacen.leer_json(os.path.join(almacen.dir_hogar(uid), "dispositivos.json"), [])
    lect = {}
    for d in disp:
        pot, horas, prob = DISPOSITIVOS[d["id"]]
        if d["estado"] == "apagada":
            w = 0
        elif d["estado"] == "standby":
            w = CATALOGO[d["id"]][2]
        else:
            w = round(pot * rng.uniform(0.85, 1.1)) if (hora in horas and rng.random() < prob) else 0
        lect[d["id"]] = w
    datos = {"momento": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "potencia_w": lect,
             "total_w": sum(lect.values()), "pid_simulador": os.getpid()}
    almacen.escribir_json(os.path.join(almacen.dir_hogar(uid), "lectura.json"), datos)
    return datos


def pasada(log):
    hogares_dir = almacen.ruta("hogares")
    uids = sorted(os.listdir(hogares_dir)) if os.path.isdir(hogares_dir) else []
    for uid in uids:
        n = rellenar(uid)
        lectura_actual(uid)
        if n:
            log.info("hogar=%s horas_agregadas=%s", uid, n)
    return len(uids)


def _detener(*_):
    global _activo
    _activo = False


def main():
    p = argparse.ArgumentParser(description="Simulador IoT SolIntel")
    p.add_argument("--intervalo", type=int, default=int(os.environ.get("SOLINTEL_INTERVALO", 30)))
    p.add_argument("--una-vez", action="store_true")
    a = p.parse_args()
    if hasattr(os, "umask"):
        os.umask(0o027)  # archivos nuevos: rw para el dueno, r para el grupo, nada para otros

    os.makedirs(os.path.join(RAIZ, "logs"), exist_ok=True)
    logging.basicConfig(filename=os.path.join(RAIZ, "logs", "simulador.log"), level=logging.INFO,
                        format="%(asctime)s [%(process)d] %(levelname)s %(message)s")
    log = logging.getLogger("simulador")
    if a.una_vez:
        print(f"Hogares procesados: {pasada(log)}")
        return

    pid_file = almacen.ruta("simulador.pid")
    with open(pid_file, "w") as f:
        f.write(str(os.getpid()))
    signal.signal(signal.SIGTERM, _detener)
    signal.signal(signal.SIGINT, _detener)
    log.info("Simulador iniciado pid=%s intervalo=%ss", os.getpid(), a.intervalo)
    print(f"Simulador IoT en ejecucion (PID {os.getpid()}), intervalo {a.intervalo}s. Ctrl+C para salir.")
    try:
        while _activo:
            pasada(log)
            for _ in range(a.intervalo):
                if not _activo:
                    break
                time.sleep(1)
    finally:
        if os.path.exists(pid_file):
            os.remove(pid_file)
        log.info("Simulador detenido")


if __name__ == "__main__":
    main()
