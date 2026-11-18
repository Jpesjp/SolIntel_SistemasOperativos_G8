"""
SolIntel - Seguridad: contrasenas cifradas, sesiones y control de intentos fallidos.

- Contrasenas: PBKDF2-HMAC-SHA256 con sal aleatoria y 200.000 iteraciones (RNF04).
- Sesiones: token aleatorio de 32 bytes guardado en memoria RAM con fecha de expiracion.
- Fuerza bruta: 5 intentos fallidos bloquean el correo durante 5 minutos.
"""
import hashlib
import hmac
import re
import secrets
import threading
import time

ITERACIONES = 200_000
MAX_INTENTOS = 5
BLOQUEO_SEG = 300

_sesiones = {}       # token -> (uid, expira)
_intentos = {}       # correo -> (fallos, desde)
_lock = threading.Lock()

RE_CORREO = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def hash_clave(clave, sal=None):
    sal = sal or secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", clave.encode(), bytes.fromhex(sal), ITERACIONES).hex()
    return f"pbkdf2_sha256${ITERACIONES}${sal}${h}"


def verificar_clave(clave, guardado):
    try:
        _, it, sal, h = guardado.split("$")
        calc = hashlib.pbkdf2_hmac("sha256", clave.encode(), bytes.fromhex(sal), int(it)).hex()
        return hmac.compare_digest(calc, h)
    except (ValueError, AttributeError):
        return False


def validar_clave(clave):
    """Politica minima: 8 caracteres, una letra y un numero."""
    return len(clave) >= 8 and re.search(r"[A-Za-z]", clave) and re.search(r"\d", clave)


def crear_sesion(uid, horas):
    token = secrets.token_urlsafe(32)
    with _lock:
        _sesiones[token] = (uid, time.time() + horas * 3600)
    return token


def usuario_de(token):
    with _lock:
        s = _sesiones.get(token)
        if not s:
            return None
        if s[1] < time.time():
            del _sesiones[token]
            return None
        return s[0]


def cerrar_sesion(token):
    with _lock:
        _sesiones.pop(token, None)


def sesiones_activas():
    ahora = time.time()
    with _lock:
        return sum(1 for _, exp in _sesiones.values() if exp > ahora)


def bloqueado(correo):
    with _lock:
        fallos, desde = _intentos.get(correo, (0, 0))
        if fallos >= MAX_INTENTOS and time.time() - desde < BLOQUEO_SEG:
            return True
        if fallos >= MAX_INTENTOS:
            _intentos.pop(correo, None)
        return False


def registrar_intento(correo, exito):
    with _lock:
        if exito:
            _intentos.pop(correo, None)
        else:
            fallos, desde = _intentos.get(correo, (0, time.time()))
            _intentos[correo] = (fallos + 1, desde if fallos else time.time())
