"""
Sollntel - Analizador de consumo y generador de recomendaciones de ahorro.
Lee el CSV simulado, calcula metricas y propone acciones (motor de reglas).

Uso:
    python src/analizador.py --entrada data/consumo_simulado.csv --salida data/reporte.txt
"""
import argparse
import csv
import os
from collections import defaultdict

TARIFA_COP_KWH = 900  # valor de referencia simulado (COP por kWh)


def leer(entrada):
    filas = []
    with open(entrada, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            filas.append({
                "hora": int(r["timestamp"][11:13]),
                "dia": r["timestamp"][:10],
                "dispositivo": r["dispositivo"],
                "kwh": float(r["energia_kwh"]),
            })
    return filas


def analizar(filas):
    por_disp = defaultdict(float)
    por_hora = defaultdict(float)
    dias = set()
    for r in filas:
        por_disp[r["dispositivo"]] += r["kwh"]
        por_hora[r["hora"]] += r["kwh"]
        dias.add(r["dia"])
    total = sum(por_disp.values())
    return por_disp, por_hora, total, len(dias)


def recomendaciones(por_disp, por_hora, total):
    recs = []
    if total == 0:
        return ["No hay consumo registrado."]
    for disp, kwh in sorted(por_disp.items(), key=lambda x: -x[1]):
        pct = kwh / total * 100
        if disp == "plancha" and pct > 10:
            recs.append(f"La plancha pesa {pct:.1f}% del consumo: planchar varias prendas juntas y evitar horas pico.")
        if disp == "microondas" and pct > 10:
            recs.append(f"El microondas pesa {pct:.1f}% del consumo: usarlo solo para porciones necesarias.")
        if disp == "lavadora" and pct > 8:
            recs.append(f"La lavadora pesa {pct:.1f}% del consumo: lavar con carga completa.")
        if disp == "iluminacion" and pct > 10:
            recs.append(f"La iluminacion pesa {pct:.1f}% del consumo: cambiar a LED y apagar zonas sin uso.")
        if disp == "nevera" and pct > 25:
            recs.append(f"La nevera pesa {pct:.1f}% del consumo: revisar sellos y temperatura.")
    hora_pico = max(por_hora, key=por_hora.get)
    recs.append(f"Hora de mayor consumo: {hora_pico:02d}:00. Mover cargas flexibles a otras horas.")
    recs.append("Desconectar cargadores y equipos en espera cuando no se usen.")
    return recs


def reporte(entrada, salida):
    filas = leer(entrada)
    por_disp, por_hora, total, n_dias = analizar(filas)
    lineas = ["=== SOLLNTEL - REPORTE DE CONSUMO (DATOS SIMULADOS) ===",
              f"Dias analizados: {n_dias}",
              f"Consumo total: {total:.2f} kWh",
              f"Promedio diario: {total / max(n_dias, 1):.2f} kWh",
              f"Costo estimado: ${total * TARIFA_COP_KWH:,.0f} COP (tarifa {TARIFA_COP_KWH} COP/kWh)",
              "", "Consumo por dispositivo:"]
    for disp, kwh in sorted(por_disp.items(), key=lambda x: -x[1]):
        lineas.append(f"  - {disp:<12} {kwh:8.2f} kWh  ({kwh / total * 100:5.1f}%)")
    lineas += ["", "Recomendaciones de ahorro:"]
    lineas += [f"  {i}. {r}" for i, r in enumerate(recomendaciones(por_disp, por_hora, total), 1)]
    texto = "\n".join(lineas)

    os.makedirs(os.path.dirname(salida) or ".", exist_ok=True)
    with open(salida, "w", encoding="utf-8") as f:
        f.write(texto)
    print(texto)
    print(f"\nReporte guardado en: {salida}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Analizador de consumo - Sollntel")
    p.add_argument("--entrada", default="data/consumo_simulado.csv")
    p.add_argument("--salida", default="data/reporte.txt")
    a = p.parse_args()
    reporte(a.entrada, a.salida)
