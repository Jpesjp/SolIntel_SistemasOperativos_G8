"""
Sollntel - Generador de datos simulados de consumo energetico residencial.
Proyecto simulado: los datos de IoT (medidores y sensores) los genera este software.

Uso:
    python src/generador_datos.py --dias 30 --salida data/consumo_simulado.csv
"""
import argparse
import csv
import os
import random
from datetime import datetime, timedelta

# dispositivo: (potencia en W, horas del dia en que suele usarse, probabilidad de uso en esa hora)
DISPOSITIVOS = {
    "nevera":      (150, range(0, 24),  0.40),
    "iluminacion": (120, range(18, 24), 0.85),
    "televisor":   (100, range(18, 23), 0.70),
    "computador":  (80,  range(8, 22),  0.50),
    "lavadora":    (500, range(9, 12),  0.15),
    "plancha":     (1000, range(6, 8),  0.10),
    "microondas":  (1200, [7, 12, 19],  0.25),
    "cargadores":  (20,  range(0, 24),  0.30),
}


def simular_hora(potencia, horas, prob, hora):
    """Devuelve (estado, minutos_encendido, energia_kwh) para un dispositivo en una hora."""
    if hora in horas and random.random() < prob:
        minutos = random.randint(10, 60)
        ruido = random.uniform(0.9, 1.1)  # variacion del sensor simulado
        energia = potencia * ruido * (minutos / 60) / 1000
        return 1, minutos, round(energia, 4)
    return 0, 0, 0.0


def generar(dias, salida, semilla):
    random.seed(semilla)
    os.makedirs(os.path.dirname(salida) or ".", exist_ok=True)
    inicio = datetime.now().replace(minute=0, second=0, microsecond=0) - timedelta(days=dias)
    total = 0.0

    with open(salida, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["timestamp", "dispositivo", "estado", "minutos_encendido", "energia_kwh"])
        for h in range(dias * 24):
            momento = inicio + timedelta(hours=h)
            for nombre, (pot, horas, prob) in DISPOSITIVOS.items():
                estado, minutos, kwh = simular_hora(pot, horas, prob, momento.hour)
                total += kwh
                w.writerow([momento.strftime("%Y-%m-%d %H:%M"), nombre, estado, minutos, kwh])

    print(f"Datos simulados generados en: {salida}")
    print(f"Periodo: {dias} dias | Consumo total simulado: {total:.2f} kWh")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Generador de datos simulados de consumo - Sollntel")
    p.add_argument("--dias", type=int, default=30, help="Dias a simular")
    p.add_argument("--salida", default="data/consumo_simulado.csv", help="Archivo CSV de salida")
    p.add_argument("--semilla", type=int, default=42, help="Semilla para resultados repetibles")
    a = p.parse_args()
    generar(a.dias, a.salida, a.semilla)
