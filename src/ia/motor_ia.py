"""
SolIntel - Modulo de IA (motor de reglas + algoritmo predictivo simple).

- Deteccion de patrones: franjas de alto consumo, dispositivos criticos, habitos repetidos
  (iluminacion encendida muchas horas seguidas), standby nocturno y anomalias (puntaje z).
- Prediccion: regresion lineal por minimos cuadrados sobre el consumo diario de los ultimos 28 dias
  para proyectar el cierre del mes y los proximos 7 dias.
- Recomendaciones: cada regla calcula un ahorro estimado en COP/mes a partir de los datos simulados.

Gestion de memoria: el analisis de cada CSV se guarda en una cache en RAM y solo se recalcula cuando
cambia la fecha de modificacion del archivo (os.stat().st_mtime).
"""
import csv
import os
import statistics
import threading
from collections import defaultdict
from datetime import date, datetime, timedelta

DIAS_SEMANA = ["L", "M", "M", "J", "V", "S", "D"]
MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]

_cache = {}
_cache_lock = threading.Lock()
estadisticas_cache = {"aciertos": 0, "fallos": 0}


class Analisis:
    def __init__(self, path):
        self.dia = defaultdict(float)                              # 'YYYY-MM-DD' -> kWh
        self.dia_disp = defaultdict(lambda: defaultdict(float))    # dia -> disp -> kWh
        self.hora = defaultdict(lambda: [0.0] * 24)                # dia -> [kWh por hora]
        self.encendido = defaultdict(dict)                         # disp -> {datetime: minutos}
        self.ts_disp = defaultdict(dict)                           # 'YYYY-MM-DD HH:MM' -> disp -> kWh
        self.ultimo = None
        with open(path, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                ts, d, k, m = r["timestamp"], r["dispositivo"], float(r["energia_kwh"]), int(r["minutos_encendido"])
                dia, h = ts[:10], int(ts[11:13])
                self.dia[dia] += k
                self.dia_disp[dia][d] += k
                self.hora[dia][h] += k
                self.ts_disp[ts][d] = k
                if d in ("iluminacion", "cargadores") and m > 0:
                    self.encendido[d][ts] = m
                self.ultimo = ts
        self.hoy = self.ultimo[:10] if self.ultimo else date.today().isoformat()
        self.hora_corte = int(self.ultimo[11:13]) if self.ultimo else 0

    def dias(self, n, hasta=None):
        fin = date.fromisoformat(hasta or self.hoy)
        return [(fin - timedelta(days=i)).isoformat() for i in range(n - 1, -1, -1)]

    def ultimas_horas(self, n=24, desde_atras=0):
        """Lista de (etiqueta, kWh) de las ultimas n horas completas (ventana movil)."""
        if not self.ultimo:
            return []
        fin = datetime.strptime(self.ultimo, "%Y-%m-%d %H:%M") - timedelta(hours=desde_atras)
        out = []
        for i in range(n - 1, -1, -1):
            t = fin - timedelta(hours=i)
            out.append((f"{t.hour:02d}h", self.hora.get(t.strftime("%Y-%m-%d"), [0] * 24)[t.hour]))
        return out

    def disp_ultimas(self, n=24):
        acc = defaultdict(float)
        if self.ultimo:
            fin = datetime.strptime(self.ultimo, "%Y-%m-%d %H:%M")
            for i in range(n):
                for d, k in self.ts_disp.get((fin - timedelta(hours=i)).strftime("%Y-%m-%d %H:%M"), {}).items():
                    acc[d] += k
        return acc

    def mes(self, ym):
        return sum(v for k, v in self.dia.items() if k.startswith(ym))

    def disp_rango(self, dias):
        acc = defaultdict(float)
        for d in dias:
            for k, v in self.dia_disp.get(d, {}).items():
                acc[k] += v
        return acc


def analizar(path):
    mtime = os.stat(path).st_mtime
    with _cache_lock:
        c = _cache.get(path)
        if c and c[0] == mtime:
            estadisticas_cache["aciertos"] += 1
            return c[1]
        estadisticas_cache["fallos"] += 1
    a = Analisis(path)
    with _cache_lock:
        _cache[path] = (mtime, a)
    return a


def meta_kwh(hogar, tarifa):
    base = hogar.get("factura_promedio", 75000) / tarifa
    return round(base * (1 - hogar.get("meta_ahorro_pct", 12) / 100), 1)


def regresion(valores):
    """Minimos cuadrados: devuelve (pendiente, intercepto)."""
    n = len(valores)
    if n < 2:
        return 0.0, (valores[0] if valores else 0.0)
    xs = range(n)
    mx, my = (n - 1) / 2, sum(valores) / n
    den = sum((x - mx) ** 2 for x in xs)
    m = sum((x - mx) * (y - my) for x, y in zip(xs, valores)) / den
    return m, my - m * mx


def prediccion(a):
    hist = [a.dia.get(d, 0) for d in a.dias(29)[:-1]]  # 28 dias completos antes de hoy
    m, b = regresion(hist)
    n = len(hist)
    prox = [max(0.0, m * (n + i) + b) for i in range(7)]
    hoy = date.fromisoformat(a.hoy)
    fin_mes = (hoy.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    restantes = (fin_mes - hoy).days
    resto_hoy = max(0.0, m * n + b - a.dia.get(a.hoy, 0)) if a.hora_corte < 23 else 0
    proy = a.mes(a.hoy[:7]) + resto_hoy + sum(max(0.0, m * (n + i) + b) for i in range(1, restantes + 1))
    return {"pendiente_kwh_dia": round(m, 4), "proximos_7_dias": [round(x, 2) for x in prox],
            "proyeccion_mes_kwh": round(proy, 2), "dias_restantes_mes": restantes}


def resumen(a, hogar, tarifa):
    hoy_kwh = sum(v for _, v in a.ultimas_horas(24))
    ayer_igual = sum(v for _, v in a.ultimas_horas(24, 24))
    var = (hoy_kwh - ayer_igual) / ayer_igual * 100 if ayer_igual else 0
    mes_kwh = a.mes(a.hoy[:7])
    meta = meta_kwh(hogar, tarifa)
    pred = prediccion(a)
    semana = a.dias(7)
    return {
        "consumo_hoy_kwh": round(hoy_kwh, 2), "variacion_ayer_pct": round(var, 1),
        "hasta_hora": f"{a.hora_corte:02d}:59", "costo_hoy_cop": round(hoy_kwh * tarifa),
        "mes_kwh": round(mes_kwh, 2), "meta_kwh": meta, "meta_pct": round(mes_kwh / meta * 100, 1) if meta else 0,
        "costo_mes_cop": round(mes_kwh * tarifa), "proyeccion": pred,
        "factura_proyectada_cop": round(pred["proyeccion_mes_kwh"] * tarifa),
        "ahorro_ia_cop": sum(r["ahorro_cop_mes"] for r in recomendaciones(a, tarifa)),
        "tendencia_semanal": [{"etiqueta": DIAS_SEMANA[date.fromisoformat(d).weekday()], "fecha": d,
                               "kwh": round(a.dia.get(d, 0), 2)} for d in semana],
        "ultimo_registro": a.ultimo,
    }


def consumo(a, periodo):
    if periodo == "dia":
        ult = a.ultimas_horas(24)
        etiquetas, valores = [e for e, _ in ult], [v for _, v in ult]
        hist = [v for d in a.dias(31)[:-1] for v in a.hora.get(d, [])]
        unidad = "kWh/h"
    elif periodo in ("semana", "mes"):
        dias = a.dias(7 if periodo == "semana" else 30)
        valores = [a.dia.get(d, 0) for d in dias]
        etiquetas = [(DIAS_SEMANA[date.fromisoformat(d).weekday()] if periodo == "semana" else d[8:]) for d in dias]
        hist = [a.dia.get(d, 0) for d in a.dias(90)]
        unidad = "kWh/día"
    else:  # ano
        hoy = date.fromisoformat(a.hoy)
        yms = []
        y, m = hoy.year, hoy.month
        for _ in range(12):
            yms.append(f"{y}-{m:02d}")
            y, m = (y, m - 1) if m > 1 else (y - 1, 12)
        yms.reverse()
        valores = [a.mes(ym) for ym in yms]
        etiquetas = [MESES[int(ym[5:]) - 1] for ym in yms]
        hist = valores[:-1]
        unidad = "kWh/mes"
    i_pico = max(range(len(valores)), key=lambda i: valores[i]) if valores else 0
    media = statistics.mean(hist) if hist else 0
    desv = statistics.pstdev(hist) if len(hist) > 1 else 0
    por_disp = a.disp_ultimas(24) if periodo == "dia" else a.disp_rango(a.dias({"semana": 7, "mes": 30}.get(periodo, 365)))
    total_d = sum(por_disp.values()) or 1
    return {
        "periodo": periodo, "unidad": unidad, "etiquetas": etiquetas, "valores": [round(v, 3) for v in valores],
        "total_kwh": round(sum(valores), 2), "pico": {"etiqueta": etiquetas[i_pico] if etiquetas else "-",
                                                        "kwh": round(valores[i_pico], 3) if valores else 0},
        "promedio": round(sum(valores) / len(valores), 3) if valores else 0,
        "rango_normal": [round(max(0, media - desv), 3), round(media + desv, 3)],
        "por_dispositivo": sorted(({"id": k, "kwh": round(v, 2), "pct": round(v / total_d * 100, 1)}
                                   for k, v in por_disp.items()), key=lambda x: -x["kwh"]),
    }


def _racha_nocturna(a, disp):
    """Maximo de horas consecutivas encendido entre 18:00 y 06:00 de la ultima noche."""
    hoy = date.fromisoformat(a.hoy)
    inicio = datetime.combine(hoy - timedelta(days=1), datetime.min.time()) + timedelta(hours=18)
    racha = mejor = 0
    for i in range(13):
        ts = (inicio + timedelta(hours=i)).strftime("%Y-%m-%d %H:%M")
        racha = racha + 1 if ts in a.encendido[disp] else 0
        mejor = max(mejor, racha)
    return mejor


def alertas(a, hogar, tarifa):
    out = []
    ult7, prev = a.dias(8)[:-1], a.dias(38)[:30]
    franja = lambda dias: statistics.mean(sum(a.hora.get(d, [0] * 24)[18:23]) for d in dias)  # noqa: E731
    f7, fprev = franja(ult7), franja(prev)
    if fprev and (f7 - fprev) / fprev > 0.10:
        out.append({"nivel": "alto", "titulo": "Riesgo alto en la noche",
                    "mensaje": f"El consumo entre 6:00 p.m. y 11:00 p.m. está {round((f7 - fprev) / fprev * 100)}% "
                               f"por encima del promedio del hogar en los últimos 7 días."})
    hoy_d = a.dia_disp.get(a.hoy, {})
    tot = sum(hoy_d.values())
    if tot:
        top = sorted(hoy_d.items(), key=lambda x: -x[1])[:2]
        pct = sum(v for _, v in top) / tot * 100
        if pct >= 40:
            out.append({"nivel": "medio", "titulo": "Dispositivo crítico",
                        "mensaje": f"{top[0][0].capitalize()} y {top[1][0]} concentran {pct:.0f}% del consumo de hoy."})
    racha = _racha_nocturna(a, "iluminacion")
    if racha >= 4:
        out.append({"nivel": "medio", "titulo": "Hábito repetido",
                    "mensaje": f"La iluminación estuvo activa {racha} horas seguidas anoche."})
    noche = _racha_nocturna(a, "cargadores")
    if noche >= 2:
        out.append({"nivel": "info", "titulo": "Standby nocturno",
                    "mensaje": f"Los cargadores consumieron energía durante {noche} horas seguidas en la noche."})
    hist = [a.dia.get(d, 0) for d in a.dias(31)[:-2]]
    ayer = a.dia.get(a.dias(2)[0], 0)
    if len(hist) > 5 and statistics.pstdev(hist):
        z = (ayer - statistics.mean(hist)) / statistics.pstdev(hist)
        if z > 1.3:
            out.append({"nivel": "medio", "titulo": "Consumo inusual ayer",
                        "mensaje": f"Ayer se consumieron {ayer:.2f} kWh, muy por encima de lo normal (z = {z:.1f})."})
    meta = meta_kwh(hogar, tarifa)
    proy = prediccion(a)["proyeccion_mes_kwh"]
    if proy > meta:
        out.append({"nivel": "alto", "titulo": "Meta mensual en riesgo",
                    "mensaje": "Al ritmo actual, la factura podría superar la meta por COP "
                               + f"{round((proy - meta) * tarifa):,}.".replace(",", ".")})
    else:
        out.append({"nivel": "ok", "titulo": "Meta mensual",
                    "mensaje": f"Vas bien: la proyección ({proy:.1f} kWh) está por debajo de la meta ({meta:.1f} kWh)."})
    return out


def recomendaciones(a, tarifa):
    d30 = a.disp_rango(a.dias(30))
    total = sum(d30.values()) or 1
    reglas = [
        ("lavadora", 0.15, "Usa la lavadora con carga completa",
         "Lava con carga completa y agua fría, preferiblemente fuera de la franja 6:00–10:00 p.m."),
        ("cargadores", 0.60, "Apaga el standby nocturno",
         "Desconecta cargadores, TV y computador cuando no se usen; usa una regleta con interruptor."),
        ("iluminacion", 0.25, "Limita la iluminación",
         "Apaga luces en habitaciones vacías y cambia a bombillos LED."),
        ("nevera", 0.10, "Revisa la nevera",
         "Revisa los sellos de la puerta, ajusta la temperatura a 3–5 °C y no la abras seguido."),
        ("microondas", 0.15, "Usa el microondas solo lo necesario",
         "Calienta porciones pequeñas y evita usarlo para descongelar."),
        ("plancha", 0.20, "Agrupa el planchado",
         "Plancha varias prendas en una sola sesión para no recalentar la plancha."),
        ("computador", 0.15, "Activa el ahorro de energía del computador",
         "Configura suspensión automática a los 10 minutos sin uso."),
    ]
    out = []
    for disp, frac, titulo, detalle in reglas:
        kwh = d30.get(disp, 0)
        if disp == "cargadores":
            kwh += 0.005 * 10 * 30  # standby estimado de TV (5 W x 10 h x 30 dias)
        ahorro = round(kwh * frac * tarifa / 100) * 100
        if ahorro >= 300:
            out.append({"id": disp, "titulo": titulo, "detalle": detalle,
                        "participacion_pct": round(d30.get(disp, 0) / total * 100, 1),
                        "ahorro_kwh_mes": round(kwh * frac, 2), "ahorro_cop_mes": ahorro})
    out.sort(key=lambda r: -r["ahorro_cop_mes"])
    horas = [0.0] * 24
    for d in a.dias(7):
        for h, v in enumerate(a.hora.get(d, [0] * 24)):
            horas[h] += v
    pico = max(range(24), key=lambda h: horas[h])
    out.append({"id": "picos", "titulo": "Revisa los picos semanales",
                "detalle": f"Tu hora de mayor consumo es {pico:02d}:00. Evita encender varios equipos grandes a la vez.",
                "participacion_pct": None, "ahorro_kwh_mes": 0, "ahorro_cop_mes": 0})
    return out


def reporte(a, hogar, tarifa, tipo):
    hoy = date.fromisoformat(a.hoy)
    if tipo == "mensual":
        dias = [d for d in a.dias(hoy.day)]
        etiquetas, valores = [d[8:] for d in dias], [a.dia.get(d, 0) for d in dias]
    elif tipo == "trimestral":
        semanas = [a.dias(7, (hoy - timedelta(weeks=i)).isoformat()) for i in range(12, -1, -1)]
        etiquetas = [f"S{i + 1}" for i in range(13)]
        valores = [sum(a.dia.get(d, 0) for d in s) for s in semanas]
    else:
        c = consumo(a, "ano")
        etiquetas, valores = c["etiquetas"], c["valores"]
    mes_act = a.mes(a.hoy[:7])
    ant = (hoy.replace(day=1) - timedelta(days=1))
    mes_ant_igual = sum(a.dia.get(f"{ant:%Y-%m}-{i:02d}", 0) for i in range(1, hoy.day + 1))
    pred = prediccion(a)
    return {
        "tipo": tipo, "etiquetas": etiquetas, "valores": [round(v, 2) for v in valores],
        "mes_actual_kwh": round(mes_act, 2), "meta_kwh": meta_kwh(hogar, tarifa),
        "factura_parcial_cop": round(mes_act * tarifa), "factura_proyectada_cop": round(pred["proyeccion_mes_kwh"] * tarifa),
        "vs_mes_anterior_pct": round((mes_act - mes_ant_igual) / mes_ant_igual * 100, 1) if mes_ant_igual else 0,
        "por_dispositivo": consumo(a, "mes")["por_dispositivo"], "tarifa_cop_kwh": tarifa,
    }


def avance_plan(a, hogar, tarifa):
    """Porcentaje de dias del mes en que el consumo estuvo dentro de la meta diaria."""
    hoy = date.fromisoformat(a.hoy)
    meta_dia = meta_kwh(hogar, tarifa) / 30
    dias = [d for d in a.dias(hoy.day)][:-1] or [a.hoy]
    ok = sum(1 for d in dias if a.dia.get(d, 0) <= meta_dia)
    return {"meta_diaria_kwh": round(meta_dia, 2), "dias_cumplidos": ok, "dias_evaluados": len(dias),
            "avance_pct": round(ok / len(dias) * 100)}
