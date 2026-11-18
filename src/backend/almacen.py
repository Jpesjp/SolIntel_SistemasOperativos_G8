"""
SolIntel - Capa de datos (sistema de archivos).

Concepto de SO aplicado:
- Sistema de archivos: los datos se guardan en JSON/CSV organizados por directorios (un directorio por hogar).
- Concurrencia y sincronizacion: el servidor (varios hilos) y el simulador IoT (otro proceso) escriben los
  mismos archivos, por eso cada escritura usa un bloqueo de archivo entre procesos (fcntl en Linux,
  msvcrt en Windows) y un bloqueo entre hilos (threading.Lock).
- Escritura atomica: se escribe en un archivo temporal y luego se reemplaza con os.replace, asi un fallo
  a mitad de escritura nunca deja un archivo corrupto.
- Permisos: en Linux los archivos sensibles quedan con permisos 600 (solo el usuario del servicio).
"""
import contextlib
import json
import os
import threading

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DIR_DATOS = os.environ.get("SOLINTEL_DATOS", os.path.join(RAIZ, "data"))

_lock_hilos = threading.RLock()

try:  # Linux / macOS
    import fcntl

    def _bloquear(f):
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)

    def _desbloquear(f):
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
except ImportError:  # Windows
    import msvcrt

    def _bloquear(f):
        f.seek(0)
        msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)

    def _desbloquear(f):
        f.seek(0)
        msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)


def ruta(*partes):
    return os.path.join(DIR_DATOS, *partes)


def dir_hogar(uid):
    d = ruta("hogares", uid)
    os.makedirs(d, exist_ok=True)
    return d


@contextlib.contextmanager
def bloqueo(nombre="global"):
    """Exclusion mutua entre hilos y entre procesos usando un archivo .lock."""
    os.makedirs(ruta("locks"), exist_ok=True)
    with _lock_hilos:
        with open(ruta("locks", nombre + ".lock"), "a+") as f:
            _bloquear(f)
            try:
                yield
            finally:
                _desbloquear(f)


def leer_json(path, defecto=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return defecto


def escribir_json(path, datos, privado=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.{os.getpid()}.{threading.get_ident()}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    if privado and os.name == "posix":
        os.chmod(path, 0o600)
