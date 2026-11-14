"""
Sollntel - Generador de la interfaz web (dashboard) a partir de los datos simulados.
Lee el CSV y crea web/index.html con graficos de consumo.

Uso:
    python src/generar_web.py --entrada data/consumo_simulado.csv --salida web/index.html
"""
import argparse
import csv
import os
from collections import defaultdict

TARIFA_COP_KWH = 900
COLORES = ["#1b7f5c", "#f4b400", "#e8710a", "#4285f4", "#9334e6", "#d93025", "#12b5cb", "#7b8794"]
ICONOS = {"nevera": "❄️", "iluminacion": "💡", "televisor": "📺", "computador": "💻",
          "lavadora": "🧺", "plancha": "👔", "microondas": "🍲", "cargadores": "🔌"}

PLANTILLA = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sollntel - Dashboard de consumo (simulado)</title>
<style>
  * { box-sizing: border-box; }
  body { font-family: 'Segoe UI', Arial, sans-serif; background: #eef3f1; margin: 0; color: #1f2d2a; }
  header { background: linear-gradient(135deg, #0f5e44, #1b9a6c); color: #fff; padding: 28px 36px; }
  header h1 { margin: 0; font-size: 32px; letter-spacing: .5px; }
  header p { margin: 6px 0 0; opacity: .92; }
  .badge { display: inline-block; margin-top: 10px; background: rgba(255,255,255,.2); padding: 4px 12px; border-radius: 20px; font-size: 13px; }
  main { max-width: 1000px; margin: -18px auto 30px; padding: 0 16px; }
  .kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 20px; }
  .kpi { background: #fff; border-radius: 14px; padding: 18px 20px; box-shadow: 0 4px 14px rgba(0,0,0,.08); border-top: 4px solid #1b9a6c; }
  .kpi h3 { margin: 0; font-size: 13px; color: #6b7a76; font-weight: 600; text-transform: uppercase; letter-spacing: .5px; }
  .kpi p { margin: 8px 0 0; font-size: 26px; font-weight: 700; color: #0f5e44; text-transform: capitalize; }
  .panel { background: #fff; border-radius: 14px; padding: 22px; box-shadow: 0 4px 14px rgba(0,0,0,.08); margin-bottom: 20px; }
  .panel h2 { margin: 0 0 16px; font-size: 18px; }
  .dos { display: flex; gap: 20px; flex-wrap: wrap; }
  .dos .panel { flex: 1; min-width: 300px; margin-bottom: 0; }
  .donut-box { display: flex; align-items: center; gap: 24px; flex-wrap: wrap; justify-content: center; }
  .donut { width: 180px; height: 180px; border-radius: 50%; position: relative; }
  .donut::after { content: ""; position: absolute; inset: 34px; background: #fff; border-radius: 50%; }
  .leyenda { list-style: none; padding: 0; margin: 0; font-size: 14px; }
  .leyenda li { margin: 6px 0; display: flex; align-items: center; gap: 8px; text-transform: capitalize; }
  .punto { width: 12px; height: 12px; border-radius: 50%; display: inline-block; }
  .fila { display: flex; align-items: center; gap: 10px; margin: 11px 0; }
  .nombre { width: 130px; text-transform: capitalize; font-size: 14px; }
  .barra { flex: 1; background: #e6eeeb; border-radius: 8px; height: 14px; overflow: hidden; }
  .barra div { height: 100%; border-radius: 8px; }
  .valor { width: 130px; text-align: right; font-size: 13px; color: #44534f; }
  .horas { display: flex; align-items: flex-end; gap: 4px; height: 170px; }
  .col { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: flex-end; height: 100%; }
  .b { width: 100%; background: #9fd3bf; border-radius: 4px 4px 0 0; min-height: 2px; }
  .b.pico { background: #e8710a; }
  .col span { font-size: 10px; color: #6b7a76; margin-top: 4px; }
  .nota { font-size: 13px; color: #6b7a76; margin-top: 10px; }
  .recs { list-style: none; padding: 0; margin: 0; }
  .recs li { background: #f3f8f6; border-left: 4px solid #1b9a6c; border-radius: 8px; padding: 10px 14px; margin: 10px 0; }
  footer { text-align: center; color: #6b7a76; font-size: 13px; padding: 10px 16px 28px; }
</style>
</head>
<body>
<header>
  <h1>☀️ Sollntel</h1>
  <p>Plataforma de optimizacion del consumo energetico residencial</p>
  <span class="badge">Proyecto simulado · datos de IoT generados por software</span>
</header>
<main>
  <div class="kpis">
    <div class="kpi"><h3>Consumo total</h3><p>@@TOTAL@@ kWh</p></div>
    <div class="kpi"><h3>Costo estimado</h3><p>$@@COSTO@@</p></div>
    <div class="kpi"><h3>Promedio diario</h3><p>@@PROMEDIO@@ kWh</p></div>
    <div class="kpi"><h3>Mayor consumo</h3><p>@@TOP@@</p></div>
  </div>

  <div class="dos">
    <div class="panel">
      <h2>Distribucion del consumo</h2>
      <div class="donut-box">
        <div class="donut" style="background:@@DONUT@@"></div>
        <ul class="leyenda">@@LEYENDA@@</ul>
      </div>
    </div>
    <div class="panel">
      <h2>Consumo por dispositivo</h2>
      @@FILAS@@
    </div>
  </div>

  <div class="panel" style="margin-top:20px">
    <h2>Consumo por hora del dia</h2>
    <div class="horas">@@HORAS@@</div>
    <p class="nota">En naranja: hora de mayor consumo (@@HORAPICO@@:00).</p>
  </div>

  <div class="panel">
    <h2>Recomendaciones de ahorro</h2>
    <ul class="recs">@@RECS@@</ul>
  </div>
</main>
<footer>Datos generados por simulacion · Sollntel · Sistemas Operativos, Fase II</footer>
</body>
</html>
"""


def generar(entrada, salida):
    por_disp = defaultdict(float)
    por_hora = defaultdict(float)
    dias = set()
    with open(entrada, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            k = float(r["energia_kwh"])
            por_disp[r["dispositivo"]] += k
            por_hora[int(r["timestamp"][11:13])] += k
            dias.add(r["timestamp"][:10])

    total = sum(por_disp.values())
    orden = sorted(por_disp.items(), key=lambda x: -x[1])
    maximo = orden[0][1]
    color = {d: COLORES[i % len(COLORES)] for i, (d, _) in enumerate(orden)}

    filas, leyenda, segmentos, acum = "", "", [], 0.0
    for d, k in orden:
        pct = k / total * 100
        icono = ICONOS.get(d, "⚡")
        filas += (f'<div class="fila"><span class="nombre">{icono} {d}</span>'
                  f'<div class="barra"><div style="width:{k / maximo * 100:.1f}%;background:{color[d]}"></div></div>'
                  f'<span class="valor">{k:.2f} kWh · {pct:.1f}%</span></div>\n')
        leyenda += f'<li><span class="punto" style="background:{color[d]}"></span>{d} <b>{pct:.1f}%</b></li>'
        segmentos.append(f"{color[d]} {acum:.2f}% {acum + pct:.2f}%")
        acum += pct
    donut = "conic-gradient(" + ", ".join(segmentos) + ")"

    hora_pico = max(por_hora, key=por_hora.get)
    max_h = por_hora[hora_pico]
    horas = ""
    for h in range(24):
        v = por_hora.get(h, 0)
        alto = v / max_h * 100 if max_h else 0
        pico = " pico" if h == hora_pico else ""
        horas += (f'<div class="col"><div class="b{pico}" style="height:{alto:.1f}%" '
                  f'title="{h:02d}:00 - {v:.2f} kWh"></div><span>{h}</span></div>')

    recs = ""
    for d, k in orden[:3]:
        recs += (f"<li>{ICONOS.get(d, '⚡')} El consumo de <b>{d}</b> es {k / total * 100:.1f}% del total: "
                 f"revisar su uso y horarios.</li>")
    recs += f"<li>🕖 La hora de mayor consumo es las <b>{hora_pico:02d}:00</b>: mover cargas flexibles a otras horas.</li>"
    recs += "<li>🔌 Desconectar cargadores y equipos en espera cuando no se usen.</li>"

    html = (PLANTILLA.replace("@@TOTAL@@", f"{total:.2f}")
            .replace("@@COSTO@@", f"{total * TARIFA_COP_KWH:,.0f} COP")
            .replace("@@PROMEDIO@@", f"{total / len(dias):.2f}")
            .replace("@@TOP@@", orden[0][0])
            .replace("@@DONUT@@", donut)
            .replace("@@LEYENDA@@", leyenda)
            .replace("@@FILAS@@", filas)
            .replace("@@HORAS@@", horas)
            .replace("@@HORAPICO@@", f"{hora_pico:02d}")
            .replace("@@RECS@@", recs))

    os.makedirs(os.path.dirname(salida) or ".", exist_ok=True)
    with open(salida, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Dashboard web generado en: {salida}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Generador de dashboard web - Sollntel")
    p.add_argument("--entrada", default="data/consumo_simulado.csv")
    p.add_argument("--salida", default="web/index.html")
    a = p.parse_args()
    generar(a.entrada, a.salida)