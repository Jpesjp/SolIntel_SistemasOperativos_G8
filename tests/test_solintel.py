"""
Pruebas automaticas de SolIntel (unittest, libreria estandar).

Ejecutar desde la raiz del repositorio:
    python -m unittest discover -s tests -v
"""
import http.client
import json
import multiprocessing
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
TMP = tempfile.mkdtemp(prefix="solintel_test_")
os.environ["SOLINTEL_DATOS"] = TMP  # los tests nunca tocan data/ real

from src.backend import almacen, seguridad, servidor  # noqa: E402
from src.ia import motor_ia  # noqa: E402
from src.simulador import simulador_iot  # noqa: E402

servidor.CONFIG["dias_historial"] = 90


def _incrementar(n):
    """Se ejecuta en otro PROCESO: incrementa un contador compartido usando el bloqueo de archivo."""
    for _ in range(n):
        with almacen.bloqueo("contador"):
            p = almacen.ruta("contador.json")
            v = almacen.leer_json(p, {"v": 0})["v"]
            almacen.escribir_json(p, {"v": v + 1})


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = servidor.crear_servidor("127.0.0.1", 0)
        cls.puerto = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()

    def pedir(self, metodo, ruta, cuerpo=None, token=None):
        c = http.client.HTTPConnection("127.0.0.1", self.puerto, timeout=30)
        h = {"Content-Type": "application/json"}
        if token:
            h["Authorization"] = "Bearer " + token
        c.request(metodo, ruta, json.dumps(cuerpo) if cuerpo is not None else None, h)
        r = c.getresponse()
        datos = r.read()
        c.close()
        try:
            datos = json.loads(datos)
        except ValueError:
            datos = datos.decode()
        return r.status, datos, dict(r.getheaders())

    def login_demo(self):
        demo = servidor.CONFIG["usuario_demo"]
        return self.pedir("POST", "/api/login", {"correo": demo["correo"], "clave": demo["clave"]})[1]["token"]


class PruebasSeguridad(Base):
    def test_01_hash_contrasena(self):
        h1, h2 = seguridad.hash_clave("Clave1234"), seguridad.hash_clave("Clave1234")
        self.assertNotEqual(h1, h2, "la sal debe ser distinta en cada hash")
        self.assertTrue(seguridad.verificar_clave("Clave1234", h1))
        self.assertFalse(seguridad.verificar_clave("otra", h1))
        self.assertTrue(h1.startswith("pbkdf2_sha256$"))

    def test_02_politica_contrasena(self):
        self.assertFalse(seguridad.validar_clave("corta1"))
        self.assertFalse(seguridad.validar_clave("soloLetras"))
        self.assertTrue(seguridad.validar_clave("Segura2026"))

    def test_03_rutas_protegidas_sin_token(self):
        for ruta in ("/api/dashboard", "/api/consumo", "/api/dispositivos", "/api/alertas", "/api/sistema"):
            self.assertEqual(self.pedir("GET", ruta)[0], 401, ruta)

    def test_04_bloqueo_fuerza_bruta(self):
        cuerpo = {"correo": "atacante@x.co", "clave": "mala12345"}
        codigos = [self.pedir("POST", "/api/login", cuerpo)[0] for _ in range(6)]
        self.assertEqual(codigos[:5], [401] * 5)
        self.assertEqual(codigos[5], 429)

    def test_05_cabeceras_seguridad(self):
        _, _, h = self.pedir("GET", "/")
        self.assertEqual(h.get("X-Frame-Options"), "DENY")
        self.assertEqual(h.get("X-Content-Type-Options"), "nosniff")
        self.assertIn("default-src 'self'", h.get("Content-Security-Policy", ""))

    def test_06_path_traversal(self):
        _, cuerpo, _ = self.pedir("GET", "/../../config/solintel.json")
        self.assertNotIn("usuario_demo", cuerpo)

    def test_07_permisos_archivo_usuarios(self):
        if os.name != "posix":
            self.skipTest("permisos POSIX")
        modo = os.stat(almacen.ruta("usuarios.json")).st_mode & 0o777
        self.assertEqual(modo, 0o600)


class PruebasFuncionales(Base):
    def test_10_registro_login_logout(self):
        s, r, _ = self.pedir("POST", "/api/registro", {"nombre": "Hogar Test", "correo": "test@solintel.co", "clave": "Prueba2026"})
        self.assertEqual(s, 201)
        self.assertEqual(self.pedir("POST", "/api/registro", {"nombre": "x", "correo": "test@solintel.co",
                                                               "clave": "Prueba2026"})[0], 409)
        s, r, _ = self.pedir("POST", "/api/login", {"correo": "test@solintel.co", "clave": "Prueba2026"})
        self.assertEqual(s, 200)
        self.assertEqual(self.pedir("POST", "/api/logout", {}, r["token"])[0], 200)
        self.assertEqual(self.pedir("GET", "/api/dashboard", token=r["token"])[0], 401)

    def test_11_endpoints_principales(self):
        t = self.login_demo()
        rutas = ["/api/dashboard", "/api/consumo?periodo=dia", "/api/consumo?periodo=semana", "/api/consumo?periodo=mes",
                 "/api/consumo?periodo=ano", "/api/dispositivos", "/api/alertas", "/api/recomendaciones",
                 "/api/reportes?tipo=mensual", "/api/reportes?tipo=trimestral", "/api/reportes?tipo=anual",
                 "/api/plan", "/api/perfil", "/api/hogar", "/api/sistema"]
        for ruta in rutas:
            s, d, _ = self.pedir("GET", ruta, token=t)
            self.assertEqual(s, 200, ruta)
            self.assertIsInstance(d, dict)
        self.assertEqual(self.pedir("GET", "/api/consumo?periodo=siglo", token=t)[0], 400)

    def test_12_dashboard_rendimiento(self):
        t = self.login_demo()
        inicio = time.perf_counter()
        s, d, _ = self.pedir("GET", "/api/dashboard", token=t)
        self.assertEqual(s, 200)
        self.assertLess(time.perf_counter() - inicio, 3.0, "RNF02: el dashboard debe cargar en menos de 3 s")
        self.assertEqual(len(d["tendencia_semanal"]), 7)

    def test_13_control_dispositivo(self):
        t = self.login_demo()
        s, d, _ = self.pedir("PUT", "/api/dispositivos/lavadora", {"estado": "apagada"}, t)
        self.assertEqual(s, 200)
        lav = next(x for x in d["dispositivos"] if x["id"] == "lavadora")
        self.assertEqual(lav["estado"], "apagada")
        self.assertEqual(lav["potencia_actual_w"], 0)
        self.assertEqual(self.pedir("PUT", "/api/dispositivos/lavadora", {"estado": "volando"}, t)[0], 400)
        self.assertEqual(self.pedir("PUT", "/api/dispositivos/nave", {"estado": "activa"}, t)[0], 404)
        self.pedir("PUT", "/api/dispositivos/lavadora", {"estado": "activa"}, t)

    def test_14_configuracion_hogar(self):
        t = self.login_demo()
        s, h, _ = self.pedir("PUT", "/api/hogar", {"factura_promedio": 90000, "meta_ahorro_pct": 10}, t)
        self.assertEqual(s, 200)
        self.assertAlmostEqual(h["meta_kwh"], 90000 / servidor.TARIFA * 0.9, places=0)
        self.assertEqual(self.pedir("PUT", "/api/hogar", {"meta_ahorro_pct": 99}, t)[0], 400)

    def test_15_plan_ahorro(self):
        t = self.login_demo()
        hab = self.pedir("GET", "/api/plan", token=t)[1]["habitos"]
        s, p, _ = self.pedir("PUT", "/api/plan", {"hechos": [hab[0]["id"], "inventado"]}, t)
        self.assertEqual(s, 200)
        self.assertEqual([h["id"] for h in p["habitos"] if h["hecho"]], [hab[0]["id"]])


class PruebasSO(Base):
    def test_20_simulador_respeta_estado(self):
        import random
        rng = random.Random(1)
        self.assertEqual(simulador_iot.simular_hora(rng, "nevera", 12, "apagada"), (0, 0, 0.0))
        self.assertEqual(simulador_iot.simular_hora(rng, "televisor", 3, "standby")[2], 0.005)

    def test_21_rellenar_horas_faltantes(self):
        uid = "htestrellenar"
        os.makedirs(almacen.dir_hogar(uid), exist_ok=True)
        almacen.escribir_json(os.path.join(almacen.dir_hogar(uid), "dispositivos.json"),
                              simulador_iot.dispositivos_por_defecto())
        path = simulador_iot.generar_historial(uid, 3)
        with open(path) as f:
            lineas = f.read().splitlines()
        with open(path, "w") as f:
            f.write("\n".join(lineas[:-5 * 8]) + "\n")  # se borran las ultimas 5 horas
        self.assertEqual(simulador_iot.rellenar(uid), 5)
        self.assertEqual(simulador_iot.rellenar(uid), 0)

    def test_22_exclusion_mutua_entre_procesos(self):
        almacen.escribir_json(almacen.ruta("contador.json"), {"v": 0})
        ctx = multiprocessing.get_context("spawn" if os.name == "nt" else "fork")
        procesos = [ctx.Process(target=_incrementar, args=(50,)) for _ in range(4)]
        [p.start() for p in procesos]
        [p.join() for p in procesos]
        self.assertEqual(almacen.leer_json(almacen.ruta("contador.json"))["v"], 200,
                         "sin perdida de actualizaciones con 4 procesos concurrentes")

    def test_23_concurrencia_hilos_api(self):
        t = self.login_demo()
        errores = []

        def trabajo(i):
            try:
                estado = ("activa", "apagada", "standby")[i % 3]
                s = self.pedir("PUT", "/api/dispositivos/televisor", {"estado": estado}, t)[0]
                s2 = self.pedir("GET", "/api/dashboard", token=t)[0]
                if (s, s2) != (200, 200):
                    errores.append((s, s2))
            except Exception as e:  # noqa: BLE001
                errores.append(e)
        hilos = [threading.Thread(target=trabajo, args=(i,)) for i in range(20)]
        [h.start() for h in hilos]
        [h.join() for h in hilos]
        self.assertEqual(errores, [])
        disp = almacen.leer_json(os.path.join(almacen.dir_hogar(servidor._usuarios()["demo@solintel.co"]["uid"]),
                                              "dispositivos.json"))
        self.assertEqual(len(disp), 8, "el archivo sigue integro despues de 20 escrituras concurrentes")

    def test_24_cache_en_memoria(self):
        uid = servidor._usuarios()["demo@solintel.co"]["uid"]
        path = os.path.join(almacen.dir_hogar(uid), "consumo.csv")
        a1, a2 = motor_ia.analizar(path), motor_ia.analizar(path)
        self.assertIs(a1, a2, "la segunda lectura debe salir de la cache en RAM")

    def test_25_monitoreo_sistema(self):
        s, d, _ = self.pedir("GET", "/api/sistema", token=self.login_demo())
        self.assertEqual(s, 200)
        self.assertEqual(d["pid"], os.getpid())
        self.assertGreaterEqual(d["hilos_activos"], 2)
        self.assertIn("simulador", d)


class PruebasIA(unittest.TestCase):
    def test_30_regresion_lineal(self):
        m, b = motor_ia.regresion([1, 3, 5, 7])
        self.assertAlmostEqual(m, 2)
        self.assertAlmostEqual(b, 1)

    def test_31_meta(self):
        self.assertAlmostEqual(motor_ia.meta_kwh({"factura_promedio": 90000, "meta_ahorro_pct": 10}, 900), 90.0)


def tearDownModule():
    shutil.rmtree(TMP, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
