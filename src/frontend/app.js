/* SolIntel - cliente web (SPA sin dependencias). Pantallas 00 a 10 del diseño en Figma. */
"use strict";

const $app = document.getElementById("app");
const NOMBRES = { nevera: "Nevera", lavadora: "Lavadora", iluminacion: "Iluminación", televisor: "TV sala",
  computador: "Computador", cargadores: "Cargadores", microondas: "Microondas", plancha: "Plancha" };
const COLORES = ["var(--verde)", "var(--teal)", "var(--amarillo)", "var(--azul)", "var(--naranja)", "var(--rojo)", "#8a63d2", "#7a8b84"];
const NIVEL = { alto: ["var(--rojo)", "var(--rojo-claro)", "Riesgo alto"], medio: ["var(--amarillo)", "var(--amarillo-claro)", "Atención"],
  info: ["var(--azul)", "var(--azul-claro)", "Información"], ok: ["var(--verde)", "var(--verde-claro)", "En meta"] };
let refresco = null;

/* ---------------- utilidades ---------------- */
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const cop = (n) => "$ " + Math.round(n || 0).toLocaleString("es-CO");
const kwh = (n, d = 1) => Number(n || 0).toLocaleString("es-CO", { minimumFractionDigits: d, maximumFractionDigits: d });
const iniciales = (s) => esc((s || "SI").split(/\s+/).map((p) => p[0]).join("").slice(0, 2).toUpperCase());
const token = { get: () => { try { return localStorage.getItem("solintel_token"); } catch { return null; } },
  set: (t) => { try { t ? localStorage.setItem("solintel_token", t) : localStorage.removeItem("solintel_token"); } catch { /* sin almacenamiento */ } } };

function toast(msg) {
  const t = document.getElementById("toast");
  t.textContent = msg; t.classList.add("ver");
  clearTimeout(toast.t); toast.t = setTimeout(() => t.classList.remove("ver"), 2600);
}

async function api(ruta, opciones = {}) {
  const r = await fetch("/api/" + ruta, { ...opciones, headers: { "Content-Type": "application/json",
    Authorization: "Bearer " + (token.get() || ""), ...(opciones.headers || {}) } });
  const datos = await r.json().catch(() => ({}));
  if (r.status === 401 && !ruta.startsWith("login")) { token.set(null); location.hash = "#/login"; throw new Error("Sesión expirada"); }
  if (!r.ok) throw new Error(datos.error || "Error de conexión");
  return datos;
}

/* ---------------- gráficas SVG ---------------- */
function barras(valores, etiquetas, { color = "var(--verde)", linea = null, alto = 180 } = {}) {
  const W = 600, H = alto, pad = 26, max = Math.max(...valores, linea || 0, 0.001) * 1.12;
  const n = valores.length, paso = (W - pad) / n, ancho = Math.min(46, paso * 0.62);
  const cada = Math.ceil(n / 12);
  let s = `<svg class="grafica" viewBox="0 0 ${W} ${H + 22}" role="img" aria-label="Gráfica de barras">`;
  for (let i = 1; i <= 3; i++) { const y = H - (H - 10) * i / 3; s += `<line x1="${pad}" x2="${W}" y1="${y}" y2="${y}" stroke="#e6eeea"/>`; }
  valores.forEach((v, i) => {
    const h = (H - 10) * v / max, x = pad + i * paso + (paso - ancho) / 2;
    s += `<rect x="${x}" y="${H - h}" width="${ancho}" height="${Math.max(h, 1)}" rx="${Math.min(8, ancho / 3)}" fill="${color}"><title>${esc(etiquetas[i])}: ${kwh(v, 2)} kWh</title></rect>`;
    if (i % cada === 0) s += `<text x="${x + ancho / 2}" y="${H + 16}" text-anchor="middle">${esc(etiquetas[i])}</text>`;
  });
  if (linea) { const y = H - (H - 10) * linea / max;
    s += `<line x1="${pad}" x2="${W}" y1="${y}" y2="${y}" stroke="var(--rojo)" stroke-dasharray="6 5"/><text x="${W - 4}" y="${y - 5}" text-anchor="end" style="fill:var(--rojo)">meta</text>`; }
  return s + "</svg>";
}

function linea(valores, etiquetas, rango) {
  const W = 600, H = 200, pad = 26, max = Math.max(...valores, rango?.[1] || 0, 0.001) * 1.15, n = valores.length;
  const x = (i) => pad + (W - pad - 10) * (n === 1 ? 0.5 : i / (n - 1)), y = (v) => H - (H - 12) * v / max;
  let s = `<svg class="grafica" viewBox="0 0 ${W} ${H + 22}" role="img" aria-label="Gráfica de consumo">`;
  if (rango) s += `<rect x="${pad}" width="${W - pad}" y="${y(rango[1])}" height="${y(rango[0]) - y(rango[1])}" fill="var(--verde-claro)"/>`;
  for (let i = 1; i <= 3; i++) { const yy = H - (H - 12) * i / 3; s += `<line x1="${pad}" x2="${W}" y1="${yy}" y2="${yy}" stroke="#e6eeea"/>`; }
  const pts = valores.map((v, i) => `${x(i)},${y(v)}`).join(" ");
  s += `<polyline points="${pts}" fill="none" stroke="var(--teal)" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"/>`;
  const cada = Math.ceil(n / 10);
  valores.forEach((v, i) => {
    s += `<circle cx="${x(i)}" cy="${y(v)}" r="4" fill="var(--teal)"><title>${esc(etiquetas[i])}: ${kwh(v, 2)} kWh</title></circle>`;
    if (i % cada === 0) s += `<text x="${x(i)}" y="${H + 16}" text-anchor="middle">${esc(etiquetas[i])}</text>`;
  });
  return s + "</svg>";
}

function listaDispositivos(items) {
  const max = Math.max(...items.map((d) => d.kwh), 0.001);
  return `<div class="lista-disp">${items.map((d, i) => `<div class="fila"><span>${esc(NOMBRES[d.id] || d.id)}</span>
    <div class="barra"><div style="width:${d.kwh / max * 100}%;--c:${COLORES[i % COLORES.length]}"></div></div>
    <span class="num">${kwh(d.kwh, 2)} kWh</span></div>`).join("")}</div>`;
}

/* ---------------- layout ---------------- */
const NAV = [["dashboard", "Inicio"], ["consumo", "Consumo"], ["dispositivos", "Equipos"], ["recomendaciones", "IA"], ["reportes", "Reportes"]];
const NAV_LATERAL = [["dashboard", "Inicio"], ["consumo", "Consumo"], ["dispositivos", "Dispositivos"], ["alertas", "Alertas IA"],
  ["recomendaciones", "Recomendaciones"], ["reportes", "Reportes"], ["plan", "Plan de ahorro"], ["perfil", "Perfil y ajustes"]];

function layout(ruta, titulo, subtitulo, cuerpo, { atras = true } = {}) {
  const hogar = sessionStorage.getItem("solintel_hogar") || "Hogar";
  const act = (r) => (r === ruta || (r === "recomendaciones" && ruta === "alertas") ? "activo" : "");
  return `<div class="shell">
    <nav class="lateral" aria-label="Menú principal"><div class="marca"><img src="logo.svg" alt="">SolIntel</div>
      ${NAV_LATERAL.map(([r, t]) => `<a href="#/${r}" class="${r === ruta ? "activo" : ""}">${t}</a>`).join("")}
      <div class="pie">Datos simulados con fines académicos<br>UMB · Sistemas Operativos · G8</div></nav>
    <main class="principal">
      <div class="aviso-sim">Datos simulados con fines académicos · no hay sensores ni integración con empresas de energía</div>
      <header class="cabecera">${atras ? `<a class="btn-atras" href="#/dashboard" aria-label="Volver">&lt;</a>` : ""}
        <div class="titulos"><h1>${titulo}</h1><p>${subtitulo}</p></div>
        <a class="avatar" href="#/perfil" title="Perfil">${iniciales(hogar)}</a></header>
      <div class="contenido">${cuerpo}</div>
    </main>
    <nav class="nav-inferior" aria-label="Navegación">${NAV.map(([r, t]) => `<a href="#/${r}" class="${act(r)}">${t}</a>`).join("")}</nav>
  </div>`;
}

/* ---------------- 00 Inicio ---------------- */
function vInicio() {
  $app.innerHTML = `<section class="inicio"><div class="caja">
    <div class="hero"><img src="logo.svg" alt="Logo SolIntel"><h1>SolIntel</h1><p>Ahorro inteligente para hogares</p></div>
    <div style="display:grid;gap:14px">
      <div class="tarjeta barra-izq" style="--c:var(--amarillo)"><h3>Prototipo residencial</h3>
        <p>Monitorea consumo, costos y hábitos del hogar con datos simulados e inteligencia artificial.</p></div>
      <div class="tarjeta barra-izq" style="--c:var(--teal)"><h3>Pensado para usuarios de 20 a 60 años</h3>
        <p>Interfaz simple, guías visuales, alertas claras y control básico de dispositivos.</p></div>
      <a class="btn claro" href="#/login" style="margin-top:14px">Comenzar</a>
    </div></div></section>`;
}

/* ---------------- 01 Login / Registro ---------------- */
function vLogin(modo = "login") {
  const reg = modo === "registro";
  $app.innerHTML = `<section class="acceso">
    <div class="lado"><div><img src="logo.svg" alt=""><h2 style="font-size:2rem;margin-top:16px">SolIntel</h2>
      <p style="color:#cdeadf">Entiende tu factura de energía en lenguaje sencillo.</p></div></div>
    <div><header class="cabecera"><div class="titulos"><h1>${reg ? "Crea tu cuenta" : "Bienvenido"}</h1>
      <p>Ingresa o crea una cuenta residencial</p></div></header>
    <form class="panel" id="f" novalidate>
      <div class="marca-txt">SolIntel</div>
      <p style="text-align:center;color:var(--suave);margin:0 0 8px">Gestiona la energía de tu casa o apartamento con recomendaciones claras y datos fáciles de entender.</p>
      ${reg ? `<div class="campo"><label for="nombre">Nombre del hogar</label><input id="nombre" required placeholder="Ej: Hogar Prieto" maxlength="60"></div>` : ""}
      <div class="campo"><label for="correo">Correo electrónico</label><input id="correo" type="email" required autocomplete="email" placeholder="tu@correo.com"></div>
      <div class="campo"><label for="clave">Contraseña</label><input id="clave" type="password" required autocomplete="${reg ? "new-password" : "current-password"}" placeholder="${reg ? "Mínimo 8 caracteres, letras y números" : "••••••••"}"></div>
      <div class="error" id="err"></div>
      <button class="btn" type="submit">${reg ? "Crear cuenta y configurar hogar" : "Iniciar sesión"}</button>
      <a class="btn sec" href="#/${reg ? "login" : "registro"}">${reg ? "Ya tengo cuenta" : "Crear cuenta y configurar hogar"}</a>
      <div class="tarjeta barra-izq" style="--c:var(--amarillo);background:var(--amarillo-claro);margin-top:10px"><h3>Nota de alcance</h3>
        <p>Este prototipo usa estadísticas simuladas. No requiere sensores físicos ni integración real con empresas de energía.
        Cuenta demo: <b>demo@solintel.co</b> / <b>Solintel2026</b></p></div>
    </form></div></section>`;
  document.getElementById("f").onsubmit = async (e) => {
    e.preventDefault();
    const b = e.target.querySelector("button"), err = document.getElementById("err");
    const cuerpo = { correo: correo.value, clave: clave.value };
    if (reg) cuerpo.nombre = nombre.value;
    b.disabled = true; err.textContent = "";
    try {
      const r = await api(reg ? "registro" : "login", { method: "POST", body: JSON.stringify(cuerpo) });
      token.set(r.token); sessionStorage.setItem("solintel_hogar", r.nombre);
      location.hash = r.configurado ? "#/dashboard" : "#/configuracion";
    } catch (x) { err.textContent = x.message; } finally { b.disabled = false; }
  };
}

/* ---------------- 02 Configuración residencial ---------------- */
const PRIORIDADES = [["Bajar factura", "var(--verde)", "var(--verde-claro)"], ["Alertas", "var(--rojo)", "var(--rojo-claro)"],
  ["Fácil de usar", "var(--azul)", "var(--azul-claro)"], ["Sostenible", "var(--teal)", "var(--teal-claro)"], ["Control hogar", "var(--naranja)", "var(--amarillo-claro)"]];

async function vConfiguracion() {
  const h = await api("hogar");
  const sel = new Set(h.prioridades || []);
  const opt = (v, actual) => `<option ${v === actual ? "selected" : ""}>${v}</option>`;
  $app.innerHTML = layout("perfil", "Configura tu hogar", "Datos básicos para personalizar el ahorro", `
    <form id="f" class="dos-col"><div style="display:grid;gap:12px">
      <div class="tarjeta barra-izq" style="--c:var(--verde)"><h3>Tipo de vivienda</h3><div class="grid-2" style="margin-top:8px">
        <div class="campo"><label>Vivienda</label><select id="tipo">${["Apartamento familiar", "Casa", "Apartaestudio", "Habitación"].map((v) => opt(v, h.tipo_vivienda)).join("")}</select></div>
        <div class="campo"><label>Ciudad</label><input id="ciudad" value="${esc(h.ciudad)}" maxlength="40"></div>
        <div class="campo"><label>Estrato</label><select id="estrato">${[1, 2, 3, 4, 5, 6].map((v) => `<option ${v === h.estrato ? "selected" : ""}>${v}</option>`).join("")}</select></div>
        <div class="campo"><label>Personas</label><input id="personas" type="number" min="1" max="15" value="${h.personas}"></div></div></div>
      <div class="tarjeta barra-izq" style="--c:var(--teal)"><h3>Factura promedio</h3><div class="grid-2" style="margin-top:8px">
        <div class="campo"><label>COP al mes</label><input id="factura" type="number" min="1000" step="1000" value="${h.factura_promedio}"></div>
        <div class="campo"><label>Meta de ahorro (%)</label><input id="meta" type="number" min="1" max="50" value="${h.meta_ahorro_pct}"></div></div>
        <p style="margin-top:8px">Tarifa de referencia: ${cop(h.tarifa_cop_kwh)} por kWh · meta actual: <b>${kwh(h.meta_kwh)} kWh/mes</b></p></div>
      <div class="tarjeta barra-izq" style="--c:var(--azul)"><h3>Dispositivos frecuentes</h3>
        <p>Nevera, lavadora, iluminación, TV, computador, microondas, plancha y cargadores (simulados).</p></div>
    </div><div style="display:grid;gap:14px;align-content:start">
      <h2 style="font-size:1.05rem">Prioridades del usuario</h2>
      <div class="chips">${PRIORIDADES.map(([t, c, bg]) => `<button type="button" class="chip ${sel.has(t) ? "sel" : ""}" data-p="${t}" style="--c:${c};--bg:${bg}" aria-pressed="${sel.has(t)}">${t}</button>`).join("")}</div>
      <div class="error" id="err"></div>
      <button class="btn" type="submit">Generar dashboard</button></div></form>`, { atras: !!h.configurado });
  document.querySelectorAll(".chip").forEach((c) => (c.onclick = () => {
    sel.has(c.dataset.p) ? sel.delete(c.dataset.p) : sel.add(c.dataset.p);
    c.classList.toggle("sel"); c.setAttribute("aria-pressed", sel.has(c.dataset.p));
  }));
  document.getElementById("f").onsubmit = async (e) => {
    e.preventDefault();
    try {
      await api("hogar", { method: "PUT", body: JSON.stringify({ tipo_vivienda: tipo.value, ciudad: ciudad.value, estrato: +estrato.value,
        personas: +personas.value, factura_promedio: +factura.value, meta_ahorro_pct: +meta.value, prioridades: [...sel] }) });
      toast("Hogar configurado"); location.hash = "#/dashboard";
    } catch (x) { document.getElementById("err").textContent = x.message; }
  };
}

/* ---------------- 03 Dashboard ---------------- */
async function vDashboard() {
  const d = await api("dashboard");
  sessionStorage.setItem("solintel_hogar", d.hogar);
  const a = d.alertas[0];
  const [c, bg] = NIVEL[a?.nivel || "ok"];
  const var_ = d.variacion_ayer_pct;
  $app.innerHTML = layout("dashboard", `Hola, ${esc(d.hogar.toLowerCase().startsWith("hogar") ? d.hogar.replace(/^Hogar/i, "hogar") : d.hogar)}`,
    "Resumen de consumo de las últimas 24 horas", `
    <div class="grid-4">
      <div class="tarjeta kpi" style="--c:var(--verde-oscuro)"><div class="etq"><span class="punto" style="--c:var(--verde)"></span>Consumo 24 h</div>
        <div class="valor">${kwh(d.consumo_hoy_kwh)} kWh</div><small>${Math.abs(var_)}% ${var_ >= 0 ? "más" : "menos"} que el día anterior</small></div>
      <div class="tarjeta kpi" style="--c:var(--naranja)"><div class="etq"><span class="punto"></span>Costo estimado</div>
        <div class="valor">${cop(d.costo_hoy_cop)}</div><small>COP acumulado 24 h</small></div>
      <div class="tarjeta kpi" style="--c:var(--azul)"><div class="etq"><span class="punto"></span>Meta mensual</div>
        <div class="valor">${Math.round(d.meta_pct)}%</div><small>${kwh(d.mes_kwh, 0)} de ${kwh(d.meta_kwh, 0)} kWh</small></div>
      <div class="tarjeta kpi" style="--c:var(--teal)"><div class="etq"><span class="punto"></span>Ahorro IA</div>
        <div class="valor">${cop(d.ahorro_ia_cop)}</div><small>Posible este mes</small></div>
    </div>
    <div class="dos-col">
      <div class="tarjeta"><div class="seccion-tit"><h2>Tendencia semanal</h2><a class="btn peq claro" href="#/consumo">Ver detalle</a></div>
        ${barras(d.tendencia_semanal.map((t) => t.kwh), d.tendencia_semanal.map((t) => t.etiqueta))}</div>
      <div style="display:grid;gap:12px">
        <div class="tarjeta"><div class="seccion-tit"><h3>Potencia actual</h3><span class="en-vivo">simulador</span></div>
          <div class="kpi" style="--c:var(--verde-oscuro)"><div class="valor">${d.lectura.total_w ?? 0} W</div>
          <small>Lectura simulada ${esc(d.lectura.momento || "sin datos")}</small></div></div>
        <div class="tarjeta"><h3>Proyección de factura</h3><div class="kpi" style="--c:var(--naranja)"><div class="valor">${cop(d.factura_proyectada_cop)}</div>
          <small>${kwh(d.proyeccion.proyeccion_mes_kwh)} kWh estimados al cierre del mes (regresión lineal)</small></div></div>
      </div>
    </div>
    ${a ? `<div class="alerta" style="--c:${c};--bg:${bg}"><h3>Alerta preventiva · ${esc(a.titulo)}</h3><p>${esc(a.mensaje)}</p></div>` : ""}
    <div class="acciones"><a class="btn oscuro" href="#/recomendaciones">Aplicar recomendación IA</a>
      <a class="btn sec" href="#/alertas">Ver todas las alertas</a></div>`, { atras: false });
  refresco = setTimeout(() => location.hash === "#/dashboard" && render(), 30000);
}

/* ---------------- 04 Consumo por periodo ---------------- */
async function vConsumo(periodo = "dia") {
  const c = await api("consumo?periodo=" + periodo);
  const tabs = [["dia", "Día"], ["semana", "Semana"], ["mes", "Mes"], ["ano", "Año"]];
  const enRango = c.promedio <= c.rango_normal[1];
  $app.innerHTML = layout("consumo", "Consumo", "Consulta por día, semana, mes o año", `
    <div class="tabs">${tabs.map(([p, t]) => `<button class="tab ${p === periodo ? "activo" : ""}" data-p="${p}">${t}</button>`).join("")}</div>
    <div class="dos-col">
      <div class="tarjeta"><div class="seccion-tit"><h3>${periodo === "dia" ? "Últimas 24 horas" : "Total " + kwh(c.total_kwh) + " kWh"}</h3>
        <small style="color:var(--suave)">${c.unidad} · franja verde = rango normal</small></div>
        ${periodo === "ano" ? barras(c.valores, c.etiquetas, { color: "var(--teal)" }) : linea(c.valores, c.etiquetas, c.rango_normal)}</div>
      <div style="display:grid;gap:12px">
        <div class="grid-2">
          <div class="tarjeta kpi" style="--c:var(--rojo)"><div class="etq"><span class="punto"></span>Pico</div>
            <div class="valor">${esc(c.pico.etiqueta)}</div><small>Mayor carga: ${kwh(c.pico.kwh, 2)} kWh</small></div>
          <div class="tarjeta kpi" style="--c:var(--verde-oscuro)"><div class="etq"><span class="punto" style="--c:var(--verde)"></span>Promedio</div>
            <div class="valor">${kwh(c.promedio, 2)}</div><small>${c.unidad} · normal: ${kwh(c.rango_normal[0], 2)}–${kwh(c.rango_normal[1], 2)}</small></div>
        </div>
        <div class="tarjeta"><h3>Por dispositivo</h3>${listaDispositivos(c.por_dispositivo)}</div>
      </div>
    </div>
    <div class="tarjeta barra-izq" style="--c:var(--teal)"><h3>Lectura sencilla</h3>
      <p>${enRango ? "Tu consumo promedio está dentro del rango normal del hogar." : "Tu consumo promedio está por encima del rango normal del hogar."}
      El mayor aporte viene de <b>${esc(NOMBRES[c.por_dispositivo[0]?.id] || "-")}</b> (${c.por_dispositivo[0]?.pct ?? 0}%).
      Cuando la curva sube, SolIntel identifica patrones y explica qué hábito o dispositivo puede estar causando el aumento.</p></div>
    <div class="acciones"><a class="btn" href="#/alertas">Ver alertas detectadas</a></div>`);
  document.querySelectorAll(".tab").forEach((t) => (t.onclick = () => vConsumo(t.dataset.p)));
}

/* ---------------- 05 Control de dispositivos ---------------- */
async function vDispositivos(datos) {
  const r = datos || (await api("dispositivos"));
  const txt = { activa: ["Activa", "var(--verde-oscuro)"], apagada: ["Apagada", "var(--suave)"], standby: ["Standby", "var(--teal)"] };
  $app.innerHTML = layout("dispositivos", "Dispositivos", "Control básico simulado del hogar", `
    <div class="grid-2 grid-disp">${r.dispositivos.map((d) => `<div class="tarjeta disp">
      <h3>${esc(d.nombre)}</h3><p>${kwh(d.kwh_hoy, 2)} kWh en 24 h</p>
      <p style="font-size:.76rem">${esc(d.ubicacion)} · ${d.potencia_w} W · ahora ${d.potencia_actual_w} W</p>
      <div class="fila"><div><span class="estado" style="color:${txt[d.estado][1]}">${txt[d.estado][0]}</span><br>
        ${d.estado !== "standby" ? `<button class="mini" data-id="${d.id}" data-e="standby">Poner en standby</button>` : `<button class="mini" data-id="${d.id}" data-e="activa">Activar</button>`}</div>
        <button class="switch ${d.estado !== "apagada" ? "on" : ""}" data-id="${d.id}" data-e="${d.estado === "apagada" ? "activa" : "apagada"}"
          role="switch" aria-checked="${d.estado !== "apagada"}" aria-label="Encender o apagar ${esc(d.nombre)}"></button></div></div>`).join("")}</div>
    <div class="tarjeta barra-izq" style="--c:var(--amarillo);background:var(--amarillo-claro)"><h3>Sugerencia de control</h3>
      <p>${esc(r.sugerencia.titulo)}: ${esc(r.sugerencia.detalle)}</p></div>
    <div class="acciones"><a class="btn" href="#/recomendaciones">Ver recomendación IA</a></div>`);
  document.querySelectorAll("[data-id]").forEach((b) => (b.onclick = async () => {
    b.disabled = true;
    try {
      const nuevo = await api("dispositivos/" + b.dataset.id, { method: "PUT", body: JSON.stringify({ estado: b.dataset.e }) });
      toast(`${NOMBRES[b.dataset.id]}: ${b.dataset.e} (simulado)`); vDispositivos(nuevo);
    } catch (x) { toast(x.message); b.disabled = false; }
  }));
}

/* ---------------- 06 Alertas inteligentes ---------------- */
async function vAlertas() {
  const { alertas } = await api("alertas");
  $app.innerHTML = layout("alertas", "Alertas IA", "Avisos preventivos antes de gastar más", `
    <div style="display:grid;gap:12px">${alertas.map((a) => { const [c, bg, etq] = NIVEL[a.nivel];
      return `<div class="alerta" style="--c:${c};--bg:${a.nivel === "ok" ? "#fff" : bg}"><h3>${esc(a.titulo)} <small style="color:${c};font-weight:600">· ${etq}</small></h3><p>${esc(a.mensaje)}</p></div>`; }).join("")}</div>
    <div class="acciones"><a class="btn" href="#/recomendaciones">Resolver con recomendaciones</a><a class="btn sec" href="#/dashboard">Volver al dashboard</a></div>`);
}

/* ---------------- 07 Recomendaciones IA ---------------- */
async function vRecomendaciones() {
  const r = await api("recomendaciones");
  $app.innerHTML = layout("recomendaciones", "Recomendaciones", "Acciones simples para reducir la factura", `
    <div class="dos-col"><div style="display:grid;gap:12px">${r.recomendaciones.map((x, i) => `
      <div class="tarjeta barra-izq" style="--c:${COLORES[i % COLORES.length]}"><h3>${i + 1}. ${esc(x.titulo)}</h3>
        <p>${esc(x.detalle)} ${x.ahorro_cop_mes ? `Ahorro estimado: <b>COP ${cop(x.ahorro_cop_mes).slice(2)}/mes</b>` : ""}
        ${x.participacion_pct != null ? ` · ${x.participacion_pct}% del consumo` : ""}</p></div>`).join("")}</div>
      <div style="display:grid;gap:12px"><div class="destacado"><p>Ahorro proyectado total</p><div class="grande">${cop(r.ahorro_total_cop_mes)} COP/mes</div>
        <p>Calculado por el motor de reglas a partir de los últimos 30 días simulados.</p></div>
        <a class="btn" href="#/plan">Crear plan de ahorro</a></div></div>`);
}

/* ---------------- 08 Reportes históricos ---------------- */
async function vReportes(tipo = "mensual") {
  const r = await api("reportes?tipo=" + tipo);
  const tabs = [["mensual", "Mensual"], ["trimestral", "Trimestral"], ["anual", "Anual"]];
  $app.innerHTML = layout("reportes", "Reportes", "Históricos de consumo y costo", `
    <div class="tabs">${tabs.map(([p, t]) => `<button class="tab ${p === tipo ? "activo" : ""}" data-p="${p}">${t}</button>`).join("")}</div>
    <div class="dos-col">
      <div class="tarjeta"><h3>${{ mensual: "Consumo diario del mes", trimestral: "Consumo semanal (13 semanas)", anual: "Consumo mensual (12 meses)" }[tipo]}</h3>
        ${barras(r.valores, r.etiquetas, { color: "var(--azul)", linea: tipo === "anual" ? r.meta_kwh : tipo === "mensual" ? r.meta_kwh / 30 : null })}</div>
      <div style="display:grid;gap:12px"><div class="grid-2">
        <div class="tarjeta kpi" style="--c:var(--azul)"><div class="etq"><span class="punto"></span>Mes actual</div>
          <div class="valor">${kwh(r.mes_actual_kwh, 0)} kWh</div><small>Meta: ${kwh(r.meta_kwh, 0)} kWh</small></div>
        <div class="tarjeta kpi" style="--c:var(--verde-oscuro)"><div class="etq"><span class="punto" style="--c:var(--verde)"></span>Factura</div>
          <div class="valor">${cop(r.factura_proyectada_cop)}</div><small>Proyección · parcial ${cop(r.factura_parcial_cop)}</small></div></div>
        <div class="tarjeta"><h3>Comparación</h3><p>${r.vs_mes_anterior_pct >= 0 ? "Subió" : "Bajó"} <b>${Math.abs(r.vs_mes_anterior_pct)}%</b> frente a los mismos días del mes anterior.</p>
          <table class="tabla" style="margin-top:8px">${r.por_dispositivo.slice(0, 5).map((d) => `<tr><td>${esc(NOMBRES[d.id])}</td><td>${kwh(d.kwh, 1)} kWh · ${d.pct}%</td></tr>`).join("")}</table></div>
      </div></div>
    <div class="tarjeta barra-izq" style="--c:var(--teal)"><h3>Reporte para el usuario</h3>
      <p>El resumen ayuda a entender costos elevados, comparar periodos y explicar en lenguaje claro qué cambió. Tarifa de referencia ${cop(r.tarifa_cop_kwh)}/kWh.</p></div>
    <div class="acciones"><button class="btn sec" id="exp">Exportar reporte simulado (CSV)</button><button class="btn sec" id="imp">Imprimir / PDF</button></div>`);
  document.querySelectorAll(".tab").forEach((t) => (t.onclick = () => vReportes(t.dataset.p)));
  document.getElementById("imp").onclick = () => window.print();
  document.getElementById("exp").onclick = () => {
    const filas = [["periodo", "kwh", "costo_cop"], ...r.etiquetas.map((e, i) => [e, r.valores[i], Math.round(r.valores[i] * r.tarifa_cop_kwh)])];
    const blob = new Blob(["# SolIntel - reporte " + tipo + " (datos simulados)\n" + filas.map((f) => f.join(",")).join("\n")], { type: "text/csv" });
    const a = Object.assign(document.createElement("a"), { href: URL.createObjectURL(blob), download: `solintel_reporte_${tipo}.csv` });
    a.click(); URL.revokeObjectURL(a.href); toast("Reporte exportado");
  };
}

/* ---------------- 09 Plan de ahorro ---------------- */
async function vPlan(datos) {
  const p = datos || (await api("plan"));
  const hechos = p.habitos.filter((h) => h.hecho).length;
  $app.innerHTML = layout("plan", "Plan de ahorro", "Seguimiento semanal de hábitos", `
    <div class="dos-col"><div style="display:grid;gap:14px">
      <div class="destacado"><p>Meta personalizada</p><div class="grande">Ahorrar ${p.meta_ahorro_pct}% este mes</div>
        <div class="progreso"><div style="width:${p.avance_pct}%"></div></div>
        <p style="margin-top:8px">${p.avance_pct}% de avance: ${p.dias_cumplidos} de ${p.dias_evaluados} días dentro de la meta diaria (${kwh(p.meta_diaria_kwh, 2)} kWh) con datos simulados</p></div>
      <div class="tarjeta"><h3>Hábitos recomendados · ${hechos}/${p.habitos.length}</h3>
        ${p.habitos.map((h) => `<label class="habito"><input type="checkbox" value="${h.id}" ${h.hecho ? "checked" : ""}>${esc(h.titulo)}
          <small>${h.ahorro_cop_mes ? cop(h.ahorro_cop_mes) + "/mes" : ""}</small></label>`).join("")}</div></div>
      <div style="display:grid;gap:12px"><div class="tarjeta barra-izq" style="--c:var(--azul)"><h3>Guía visual</h3>
        <p>Cada acción aceptada se convierte en una tarea simple para usuarios con habilidades tecnológicas básicas-medias. Marca el círculo cuando la cumplas.</p></div>
        <a class="btn" href="#/dashboard">Ir al dashboard</a></div></div>`);
  document.querySelectorAll(".habito input").forEach((c) => (c.onchange = async () => {
    const sel = [...document.querySelectorAll(".habito input:checked")].map((x) => x.value);
    vPlan(await api("plan", { method: "PUT", body: JSON.stringify({ hechos: sel }) })); toast("Plan actualizado");
  }));
}

/* ---------------- 10 Perfil y ajustes ---------------- */
async function vPerfil() {
  const [u, h, s] = await Promise.all([api("perfil"), api("hogar"), api("sistema")]);
  const up = s.uptime_seg, t = `${Math.floor(up / 3600)} h ${Math.floor((up % 3600) / 60)} min`;
  $app.innerHTML = layout("perfil", "Perfil y ajustes", "Cuenta, hogar y estado del sistema", `
    <div class="dos-col"><div style="display:grid;gap:12px">
      <form class="tarjeta" id="fp" style="display:grid;gap:10px"><h3>Cuenta</h3>
        <div class="campo"><label>Nombre del hogar</label><input id="nom" value="${esc(u.nombre)}" maxlength="60"></div>
        <div class="campo"><label>Correo</label><input value="${esc(u.correo)}" disabled></div>
        <div class="grid-2"><div class="campo"><label>Contraseña actual</label><input id="ca" type="password" autocomplete="current-password"></div>
          <div class="campo"><label>Nueva contraseña</label><input id="cn" type="password" autocomplete="new-password"></div></div>
        <div class="error" id="err"></div><button class="btn peq" type="submit">Guardar cambios</button></form>
      <div class="tarjeta barra-izq" style="--c:var(--teal)"><h3>Hogar</h3>
        <p>${esc(h.tipo_vivienda)} · ${esc(h.ciudad)} · estrato ${h.estrato} · ${h.personas} personas<br>
        Factura promedio ${cop(h.factura_promedio)} · meta ${h.meta_ahorro_pct}% (${kwh(h.meta_kwh)} kWh/mes)</p>
        <a class="btn peq claro" href="#/configuracion" style="margin-top:10px">Editar configuración</a></div>
    </div>
    <div class="tarjeta sistema"><div class="seccion-tit"><h3>Estado del sistema</h3><span class="en-vivo">${s.simulador.activo ? "simulador activo" : "simulador detenido"}</span></div>
      <dl style="margin-top:10px"><dt>Sistema operativo</dt><dd>${esc(s.sistema_operativo)}</dd><dt>Equipo</dt><dd>${esc(s.equipo)}</dd>
        <dt>Python</dt><dd>${esc(s.python)}</dd><dt>PID servidor</dt><dd>${s.pid} (padre ${s.ppid})</dd>
        <dt>Hilos activos</dt><dd>${s.hilos_activos}</dd><dt>Tiempo activo</dt><dd>${t}</dd>
        <dt>Memoria máx.</dt><dd>${s.memoria_max_kb ? (s.memoria_max_kb / 1024).toFixed(1) + " MB" : "n/d"}</dd>
        <dt>Carga (1/5/15)</dt><dd>${s.carga_promedio ? s.carga_promedio.join(" / ") : "n/d"}</dd>
        <dt>Disco</dt><dd>${s.disco.uso_pct}% usado · ${s.disco.libre_gb} GB libres</dd><dt>Datos</dt><dd>${s.datos_mb} MB</dd>
        <dt>Simulador IoT</dt><dd>${s.simulador.activo ? "PID " + s.simulador.pid : "no está en ejecución"}</dd>
        <dt>Usuarios / sesiones</dt><dd>${s.usuarios} / ${s.sesiones_activas}</dd>
        <dt>Caché IA</dt><dd>${s.cache_ia.aciertos} aciertos · ${s.cache_ia.fallos} fallos</dd></dl>
      <button class="btn sec" id="salir" style="margin-top:16px">Cerrar sesión</button></div></div>`);
  document.getElementById("fp").onsubmit = async (e) => {
    e.preventDefault();
    try {
      const r = await api("perfil", { method: "PUT", body: JSON.stringify({ nombre: nom.value, clave_actual: ca.value, clave_nueva: cn.value }) });
      sessionStorage.setItem("solintel_hogar", r.nombre); toast("Cambios guardados"); vPerfil();
    } catch (x) { document.getElementById("err").textContent = x.message; }
  };
  document.getElementById("salir").onclick = async () => {
    await api("logout", { method: "POST" }).catch(() => {}); token.set(null); location.hash = "#/inicio";
  };
}

/* ---------------- enrutador ---------------- */
const RUTAS = { inicio: vInicio, login: () => vLogin("login"), registro: () => vLogin("registro"), configuracion: vConfiguracion,
  dashboard: vDashboard, consumo: () => vConsumo(), dispositivos: () => vDispositivos(), alertas: vAlertas,
  recomendaciones: vRecomendaciones, reportes: () => vReportes(), plan: () => vPlan(), perfil: vPerfil };
const PUBLICAS = new Set(["inicio", "login", "registro"]);

async function render() {
  clearTimeout(refresco);
  let ruta = location.hash.replace(/^#\/?/, "") || (token.get() ? "dashboard" : "inicio");
  if (!RUTAS[ruta]) ruta = "inicio";
  if (!PUBLICAS.has(ruta) && !token.get()) { location.hash = "#/login"; return; }
  if (!$app.innerHTML) $app.innerHTML = `<div class="cargando">Cargando…</div>`;
  try { await RUTAS[ruta](); window.scrollTo(0, 0); } catch (x) { if (x.message !== "Sesión expirada") toast(x.message); }
}
window.addEventListener("hashchange", render);
render();
