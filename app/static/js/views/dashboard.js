import { get } from "../api.js";
import { $, $$, addDays, compact, esc, fmtShortDate, money, money0, num, pct, table, toastErr, today } from "../ui.js";

// Paleta categórica validada (orden fijo, nunca ciclada) + tokens de ejes
const C = { s1: "#2a78d6", s2: "#eb6834", s3: "#1baf7a", s4: "#eda100", gray: "#9a9994", grid: "#ecebe7", ink2: "#52514e", muted: "#8a8984" };
const CLASES = { "Estrella": C.s1, "Caballo de batalla": C.s2, "Rompecabezas": C.s3, "Perro": "#4a3aa7" };
const FORMAS = { "Estrella": "circle", "Caballo de batalla": "triangle", "Rompecabezas": "rectRot", "Perro": "rect" };
const CONSEJO = {
  "Estrella": "Populares y rentables: protégelas, destácalas en el menú.",
  "Caballo de batalla": "Se venden mucho pero dejan poco: revisa porción/costo o sube precio poco a poco.",
  "Rompecabezas": "Rentables pero poco pedidas: promociónalas, cambia nombre o ubicación.",
  "Perro": "Poca venta y poco margen: considera rediseñarlas o quitarlas.",
};

let rango = { preset: "30", desde: addDays(today(), -29), hasta: today() };
let charts = [];

export async function render(view) {
  setupChartDefaults();
  view.innerHTML = `<div class="page">
    <div class="page-head" style="margin-bottom:10px"><div class="grow"><h1>Dashboard</h1><div class="sub" id="d-sub"></div></div></div>
    <div class="row wrap" style="margin-bottom:16px">
      <div class="seg" id="d-pre">
        ${[["hoy", "Hoy"], ["ayer", "Ayer"], ["7", "7 días"], ["30", "30 días"], ["mes", "Este mes"], ["mesant", "Mes anterior"], ["90", "90 días"]]
          .map(([k, l]) => `<button data-p="${k}" class="${rango.preset === k ? "active" : ""}">${l}</button>`).join("")}
      </div>
      <input class="input" type="date" id="d-desde" style="width:150px" value="${rango.desde}">
      <input class="input" type="date" id="d-hasta" style="width:150px" value="${rango.hasta}">
      <button class="btn" id="d-refresh" title="Actualizar">Actualizar</button>
    </div>
    <div id="d-body"><div class="muted">Cargando indicadores…</div></div></div>`;
  $$("#d-pre button").forEach((b) => b.onclick = () => { setPreset(b.dataset.p); cargar(); });
  ["d-desde", "d-hasta"].forEach((id) => $("#" + id).onchange = () => {
    rango = { preset: "", desde: $("#d-desde").value, hasta: $("#d-hasta").value }; cargar();
  });
  $("#d-refresh").onclick = cargar;
  await cargar();
  return () => destroyCharts();
}

function setPreset(p) {
  const t = today();
  const d = new Date(t + "T12:00:00");
  const iso = (x) => x.toISOString().slice(0, 10);
  let desde = t, hasta = t;
  if (p === "ayer") desde = hasta = addDays(t, -1);
  if (["7", "30", "90"].includes(p)) desde = addDays(t, -(+p - 1));
  if (p === "mes") desde = t.slice(0, 8) + "01";
  if (p === "mesant") { const a = new Date(d.getFullYear(), d.getMonth() - 1, 1, 12); const b = new Date(d.getFullYear(), d.getMonth(), 0, 12); desde = iso(a); hasta = iso(b); }
  rango = { preset: p, desde, hasta };
  $("#d-desde").value = desde; $("#d-hasta").value = hasta;
  $$("#d-pre button").forEach((x) => x.classList.toggle("active", x.dataset.p === p));
}

function setupChartDefaults() {
  if (!window.Chart) return;
  const D = Chart.defaults;
  D.font.family = getComputedStyle(document.body).fontFamily;
  D.font.size = 12;
  D.color = C.ink2;
  D.borderColor = C.grid;
  D.animation = { duration: 250 };
  D.maintainAspectRatio = false;
  D.plugins.legend.display = false;
  const tt = D.plugins.tooltip;
  Object.assign(tt, { backgroundColor: "#1f2230", titleColor: "#fff", bodyColor: "#e8e8ee", padding: 10, cornerRadius: 8,
    boxPadding: 4, usePointStyle: true, titleFont: { weight: "600" } });
}

function destroyCharts() { charts.forEach((c) => c.destroy()); charts = []; }

function delta(act, ant, { inverso = false, esPct = false } = {}) {
  if (!ant) return `<span class="muted">sin periodo previo</span>`;
  const d = esPct ? act - ant : (act - ant) / Math.abs(ant);
  if (!isFinite(d)) return "";
  const bueno = inverso ? d < 0 : d > 0;
  const txt = esPct ? `${d >= 0 ? "+" : ""}${(d * 100).toFixed(1)} pts` : `${d >= 0 ? "+" : ""}${(d * 100).toFixed(1)}%`;
  return `<span class="${Math.abs(d) < 0.0005 ? "" : bueno ? "up" : "down"}">${d >= 0 ? "▲" : "▼"} ${txt}</span> vs periodo anterior`;
}

async function cargar() {
  let d;
  try { d = await get("/dashboard", { desde: rango.desde, hasta: rango.hasta }); } catch (e) { return toastErr(e); }
  destroyCharts();
  const k = d.kpis, p = d.kpis_anterior, inv = d.inventario;
  const foodCost = k.ventas ? k.costo / k.ventas : 0, foodCostAnt = p.ventas ? p.costo / p.ventas : 0;
  $("#d-sub").textContent = `${fmtShortDate(d.rango.desde)} – ${fmtShortDate(d.rango.hasta)} (${d.rango.dias} días) · comparado con ${fmtShortDate(d.rango.anterior_desde)} – ${fmtShortDate(d.rango.anterior_hasta)}`;
  const body = $("#d-body");
  body.innerHTML = `
    <div class="kpis">
      <div class="card kpi hero"><div class="l">Ventas netas</div><div class="v">${money0(k.ventas)}</div><div class="d">${delta(k.ventas, p.ventas)}</div></div>
      <div class="card kpi"><div class="l">Margen bruto</div><div class="v">${money0(k.margen)}</div><div class="d">${pct(k.margen_pct)} · ${delta(k.margen_pct, p.margen_pct, { esPct: true })}</div></div>
      <div class="card kpi"><div class="l">Tickets</div><div class="v">${num(k.tickets, 0)}</div><div class="d">${delta(k.tickets, p.tickets)}</div></div>
      <div class="card kpi"><div class="l">Ticket promedio</div><div class="v">${money(k.ticket_promedio)}</div><div class="d">${delta(k.ticket_promedio, p.ticket_promedio)}</div></div>
      <div class="card kpi"><div class="l">Food cost (costo / venta)</div><div class="v">${pct(foodCost)}</div><div class="d">${delta(foodCost, foodCostAnt, { inverso: true, esPct: true })}</div></div>
      <div class="card kpi"><div class="l">Unidades vendidas</div><div class="v">${num(k.unidades, 0)}</div><div class="d">${delta(k.unidades, p.unidades)}</div></div>
    </div>
    <div class="kpis" style="margin-top:12px">
      <div class="card kpi"><div class="l">Costo de ventas</div><div class="v" style="font-size:20px">${money0(k.costo)}</div><div class="d">consumo real vía backflush</div></div>
      <div class="card kpi"><div class="l">Compras de insumos</div><div class="v" style="font-size:20px">${money0(inv.compras_periodo)}</div><div class="d">entradas de material</div></div>
      <div class="card kpi"><div class="l">Merma registrada</div><div class="v" style="font-size:20px">${money0(inv.merma_periodo)}</div><div class="d">${k.costo ? pct(inv.merma_periodo / k.costo) + " del costo de ventas" : ""}</div></div>
      <div class="card kpi"><div class="l">Valor del inventario</div><div class="v" style="font-size:20px">${money0(inv.valor)}</div><div class="d">${inv.bajos + inv.agotados ? `<span class="down">▲ ${inv.bajos + inv.agotados} insumos bajo mínimo</span>` : "todo en nivel"}</div></div>
      <div class="card kpi"><div class="l">Descuentos</div><div class="v" style="font-size:20px">${money0(k.descuentos)}</div><div class="d">${k.ventas ? pct(k.descuentos / (k.ventas + k.descuentos)) + " de la venta bruta" : ""}</div></div>
      <div class="card kpi"><div class="l">Cancelaciones</div><div class="v" style="font-size:20px">${k.canceladas}</div><div class="d">${money0(k.monto_cancelado)}</div></div>
    </div>
    <div class="dash-grid">
      <div class="card c8"><div class="card-h"><h3>Ventas y margen bruto ${d.rango.agrupar === "semana" ? "por semana" : "por día"}</h3>
        <div class="legend"><span><i style="background:${C.s1}"></i>Ventas</span><span><i style="background:${C.s2}"></i>Margen bruto</span></div></div>
        <div class="card-b"><div class="chart-box"><canvas id="ch-serie"></canvas></div></div></div>
      <div class="card c4"><div class="card-h"><h3>Métodos de pago</h3></div><div class="card-b" id="t-met"></div></div>
      <div class="card c6"><div class="card-h"><h3>Ventas por hora del día</h3><span class="hint">total del periodo</span></div>
        <div class="card-b"><div class="chart-box"><canvas id="ch-hora"></canvas></div></div></div>
      <div class="card c6"><div class="card-h"><h3>Venta promedio por día de la semana</h3></div>
        <div class="card-b"><div class="chart-box"><canvas id="ch-dow"></canvas></div></div></div>
      <div class="card c7"><div class="card-h"><h3>Top 10 productos por ventas</h3></div>
        <div class="card-b"><div class="chart-box tall"><canvas id="ch-top"></canvas></div></div></div>
      <div class="card c5"><div class="card-h"><h3>Ventas y margen por categoría</h3></div><div class="card-b" id="t-cat"></div></div>
      <div class="card c7"><div class="card-h"><h3>Ingeniería de menú</h3>
        <div class="legend">${Object.entries(CLASES).map(([n, c]) => `<span><i class="sq" style="background:${c}"></i>${n}</span>`).join("")}</div></div>
        <div class="card-b"><div class="chart-box tall"><canvas id="ch-menu"></canvas></div>
        <div class="hint" style="margin-top:6px">Eje X: unidades vendidas (popularidad). Eje Y: margen por unidad. Líneas: umbral de popularidad (70% del promedio) y margen promedio ponderado.</div></div></div>
      <div class="card c5"><div class="card-h"><h3>Qué hacer con cada grupo</h3></div><div class="card-b" id="t-menu"></div></div>
      <div class="card c12"><div class="card-h"><h3>Rentabilidad por producto</h3><span class="hint">${d.sin_venta.length ? `${d.sin_venta.length} productos activos sin ventas en el periodo: ${esc(d.sin_venta.map((x) => x.producto).join(", "))}` : ""}</span></div><div class="card-b" id="t-prod"></div></div>
      <div class="card c6"><div class="card-h"><h3>Alertas de inventario</h3></div><div class="card-b" id="t-alert"></div></div>
      <div class="card c6"><div class="card-h"><h3>Días de cobertura (menor a mayor)</h3><span class="hint">existencia ÷ consumo diario de los últimos 28 días</span></div><div class="card-b" id="t-cob"></div></div>
      <div class="card c6"><div class="card-h"><h3>Insumos con mayor consumo ($)</h3></div><div class="card-b" id="t-cons"></div></div>
      <div class="card c6"><div class="card-h"><h3>Merma por insumo</h3></div><div class="card-b" id="t-merma"></div></div>
      <div class="card c12"><div class="card-h"><h3>Desempeño por usuario</h3></div><div class="card-b" id="t-usr"></div></div>
    </div>`;

  // --- Serie de ventas y margen
  const labels = d.serie.map((s) => fmtShortDate(s.periodo));
  charts.push(new Chart($("#ch-serie"), {
    type: "line",
    data: { labels, datasets: [
      { label: "Ventas", data: d.serie.map((s) => s.ventas), borderColor: C.s1, backgroundColor: C.s1 + "1a", fill: true, borderWidth: 2, pointRadius: 0, pointHoverRadius: 5, pointHoverBorderColor: "#fff", pointHoverBorderWidth: 2, tension: 0.25 },
      { label: "Margen bruto", data: d.serie.map((s) => s.margen), borderColor: C.s2, backgroundColor: C.s2, borderWidth: 2, pointRadius: 0, pointHoverRadius: 5, pointHoverBorderColor: "#fff", pointHoverBorderWidth: 2, tension: 0.25 },
    ] },
    options: {
      interaction: { mode: "index", intersect: false },
      scales: { x: { grid: { display: false }, ticks: { maxTicksLimit: 10, maxRotation: 0 } },
        y: { beginAtZero: true, border: { display: false }, ticks: { callback: (v) => compact(v) } } },
      plugins: { tooltip: { callbacks: { label: (c) => ` ${c.dataset.label}: ${money(c.parsed.y)}`,
        afterBody: (items) => { const s = d.serie[items[0].dataIndex]; return [`Tickets: ${s.tickets}`, s.ventas ? `Margen: ${pct(s.margen / s.ventas)}` : ""]; } } } },
    },
  }));

  // --- Métodos de pago (barras HTML con % directo)
  const totMet = d.metodos.reduce((s, m) => s + m.ventas, 0) || 1;
  $("#t-met").innerHTML = d.metodos.length ? d.metodos.map((m) => `<div style="margin-bottom:14px">
      <div class="row"><b class="grow">${esc(m.metodo)}</b><span class="num">${money0(m.ventas)}</span><span class="num muted" style="width:52px">${pct(m.ventas / totMet, 0)}</span></div>
      <div class="bar-mini" style="margin-top:6px;height:8px"><i style="width:${(m.ventas / totMet) * 100}%"></i></div>
      <div class="hint" style="margin-top:3px">${m.tickets} tickets · promedio ${money(m.ventas / (m.tickets || 1))}</div></div>`).join("") : `<div class="empty">Sin ventas</div>`;

  // --- Por hora
  const horas = [];
  const hmin = Math.min(...d.por_hora.map((h) => h.hora), 12), hmax = Math.max(...d.por_hora.map((h) => h.hora), 22);
  for (let h = hmin; h <= hmax; h++) horas.push(d.por_hora.find((x) => x.hora === h) || { hora: h, ventas: 0, tickets: 0 });
  charts.push(barChart("#ch-hora", horas.map((h) => `${h.hora}:00`), horas.map((h) => h.ventas), {
    tip: (i) => [`Ventas: ${money(horas[i].ventas)}`, `Tickets: ${horas[i].tickets}`],
  }));

  // --- Día de la semana (promedio)
  charts.push(barChart("#ch-dow", d.por_dia_semana.map((x) => x.nombre_dia.slice(0, 3)), d.por_dia_semana.map((x) => x.promedio), {
    tip: (i) => { const x = d.por_dia_semana[i]; return [`Promedio: ${money(x.promedio)}`, `Días en el periodo: ${x.dias}`, `Total: ${money(x.ventas)}`]; },
  }));

  // --- Top productos (horizontal)
  const top = d.productos.slice(0, 10);
  charts.push(barChart("#ch-top", top.map((x) => x.producto.length > 30 ? x.producto.slice(0, 29) + "…" : x.producto), top.map((x) => x.ventas), {
    horizontal: true, tip: (i) => [`Ventas: ${money(top[i].ventas)}`, `Unidades: ${num(top[i].unidades, 0)}`, `Margen: ${money(top[i].margen)} (${pct(top[i].margen_pct)})`],
  }));

  // --- Categorías (tabla con barra)
  const maxCat = Math.max(...d.categorias.map((c) => c.ventas), 1);
  $("#t-cat").appendChild(table([
    { t: "Categoría", k: (c) => `<span class="row" style="gap:6px"><span class="dot" style="background:${esc(c.color || C.gray)}"></span>${esc(c.categoria)}</span>` },
    { t: "Ventas", k: (c) => `<div class="row" style="gap:8px;justify-content:flex-end"><span class="bar-mini" style="width:48px;min-width:48px"><i style="width:${(c.ventas / maxCat) * 100}%"></i></span>${money0(c.ventas)}</div>`, cls: "num" },
    { t: "Margen", k: "margen", cls: "num", f: money0 },
    { t: "Margen %", k: (c) => pct(c.margen / (c.ventas || 1)), cls: "num" },
  ], d.categorias, { empty: "Sin ventas" }));

  // --- Ingeniería de menú (dispersión)
  const ref = d.menu_ref;
  const refLines = {
    id: "refLines",
    afterDatasetsDraw(chart) {
      const { ctx, chartArea: a, scales: { x, y } } = chart;
      ctx.save(); ctx.strokeStyle = "#b9b7b0"; ctx.lineWidth = 1;
      const px = x.getPixelForValue(ref.umbral_popularidad), py = y.getPixelForValue(ref.margen_unitario_promedio);
      if (px >= a.left && px <= a.right) { ctx.beginPath(); ctx.moveTo(px, a.top); ctx.lineTo(px, a.bottom); ctx.stroke(); }
      if (py >= a.top && py <= a.bottom) { ctx.beginPath(); ctx.moveTo(a.left, py); ctx.lineTo(a.right, py); ctx.stroke(); }
      ctx.restore();
    },
  };
  charts.push(new Chart($("#ch-menu"), {
    type: "scatter",
    data: { datasets: Object.entries(CLASES).map(([clase, color]) => ({
      label: clase, backgroundColor: color, borderColor: "#fff", borderWidth: 2, pointStyle: FORMAS[clase], pointRadius: 7, pointHoverRadius: 9, pointHitRadius: 10,
      data: d.productos.filter((x) => x.clase_menu === clase).map((x) => ({ x: x.unidades, y: x.margen_unitario, n: x.producto, m: x.margen })),
    })) },
    options: {
      scales: { x: { beginAtZero: true, title: { display: true, text: "Unidades vendidas" }, grid: { color: C.grid } },
        y: { beginAtZero: true, title: { display: true, text: "Margen por unidad" }, border: { display: false }, ticks: { callback: (v) => money0(v) } } },
      plugins: { tooltip: { callbacks: { label: (c) => ` ${c.raw.n}: ${num(c.raw.x, 0)} u · ${money(c.raw.y)}/u · ${c.dataset.label}` } } },
    },
    plugins: [refLines],
  }));
  const conteo = Object.keys(CLASES).map((c) => ({ clase: c, n: d.productos.filter((x) => x.clase_menu === c).length,
    ventas: d.productos.filter((x) => x.clase_menu === c).reduce((s, x) => s + x.ventas, 0) }));
  $("#t-menu").innerHTML = conteo.map((c) => `<div style="padding:10px 0;border-bottom:1px solid var(--line)">
      <div class="row"><span class="dot" style="background:${CLASES[c.clase]}"></span><b class="grow">${c.clase}</b><span class="badge">${c.n} productos</span><span class="num" style="width:90px">${money0(c.ventas)}</span></div>
      <div class="hint" style="margin-top:4px">${CONSEJO[c.clase]}</div></div>`).join("");

  // --- Rentabilidad por producto
  $("#t-prod").appendChild(table([
    { t: "Producto", k: "producto" }, { t: "Categoría", k: "categoria" },
    { t: "Unidades", k: "unidades", cls: "num", f: (v) => num(v, 0) }, { t: "Ventas", k: "ventas", cls: "num", f: money },
    { t: "Costo", k: "costo", cls: "num", f: money }, { t: "Margen", k: "margen", cls: "num", f: money },
    { t: "Margen %", k: "margen_pct", cls: "num", f: (v) => pct(v) }, { t: "Margen/u", k: "margen_unitario", cls: "num", f: money },
    { t: "Participación", k: (x) => pct(x.ventas / (k.ventas || 1)), cls: "num" },
    { t: "Clasificación", k: (x) => `<span class="row" style="gap:6px"><span class="dot" style="background:${CLASES[x.clase_menu]}"></span>${esc(x.clase_menu)}</span>` },
  ], d.productos, { empty: "Sin ventas en el periodo",
    foot: ["Total", "", num(k.unidades, 0), money(k.ventas), money(k.costo), money(k.margen), pct(k.margen_pct), "", "100%", ""] }));

  // --- Inventario
  $("#t-alert").appendChild(table([
    { t: "Insumo", k: "nombre" }, { t: "Existencia", k: (r) => `${num(r.stock_actual)} ${esc(r.unidad)}`, cls: "num" },
    { t: "Mínimo", k: "stock_minimo", cls: "num", f: (v) => num(v) }, { t: "Proveedor", k: "proveedor" },
    { t: "Estado", k: "estado", f: (v) => `<span class="badge ${v === "AGOTADO" ? "bad" : "warn"}">${v === "AGOTADO" ? "✕" : "▲"} ${esc(v)}</span>` },
  ], inv.alertas, { empty: "✓ Todos los insumos están arriba del mínimo" }));
  $("#t-cob").appendChild(table([
    { t: "Insumo", k: "insumo" }, { t: "Existencia", k: (r) => `${num(r.stock_actual)} ${esc(r.unidad)}`, cls: "num" },
    { t: "Consumo diario", k: (r) => `${num(r.consumo_diario)} ${esc(r.unidad)}`, cls: "num" },
    { t: "Días", k: "dias_cobertura", cls: "num", f: (v) => `<b class="${v < 2 ? "bad-t" : v < 4 ? "warn-t" : ""}">${num(v, 1)}</b>` },
  ], inv.cobertura, { empty: "Sin consumo reciente" }));
  $("#t-cons").appendChild(table([
    { t: "Insumo", k: "insumo" }, { t: "Cantidad", k: (r) => `${num(r.cantidad)} ${esc(r.unidad)}`, cls: "num" },
    { t: "Costo", k: "costo", cls: "num", f: money },
  ], inv.consumo, { empty: "Sin consumo" }));
  $("#t-merma").appendChild(table([
    { t: "Insumo", k: "insumo" }, { t: "Cantidad", k: (r) => `${num(r.cantidad)} ${esc(r.unidad)}`, cls: "num" },
    { t: "Costo", k: "costo", cls: "num", f: money },
  ], inv.mermas, { empty: "Sin mermas registradas en el periodo" }));

  // --- Usuarios
  $("#t-usr").appendChild(table([
    { t: "Usuario", k: "usuario" }, { t: "Tickets", k: "tickets", cls: "num" }, { t: "Ventas", k: "ventas", cls: "num", f: money },
    { t: "Ticket promedio", k: "ticket_promedio", cls: "num", f: money }, { t: "Participación", k: (u) => pct(u.ventas / (k.ventas || 1)), cls: "num" },
    { t: "Cancelaciones", k: "canceladas", cls: "num" },
  ], d.usuarios, { empty: "Sin ventas" }));
}

function barChart(sel, labels, values, { horizontal = false, tip } = {}) {
  const valueAxis = { beginAtZero: true, border: { display: false }, ticks: { callback: (v) => compact(v) } };
  const catAxis = { grid: { display: false }, ticks: { autoSkip: !horizontal } };
  return new Chart($(sel), {
    type: "bar",
    data: { labels, datasets: [{ data: values, backgroundColor: C.s1, hoverBackgroundColor: "#256abf", borderRadius: 4, borderSkipped: "start", maxBarThickness: 24 }] },
    options: {
      indexAxis: horizontal ? "y" : "x",
      scales: horizontal ? { x: valueAxis, y: catAxis } : { x: catAxis, y: valueAxis },
      plugins: { tooltip: { displayColors: false, callbacks: { label: (c) => tip ? tip(c.dataIndex) : money(c.parsed[horizontal ? "x" : "y"]) } } },
    },
  });
}
