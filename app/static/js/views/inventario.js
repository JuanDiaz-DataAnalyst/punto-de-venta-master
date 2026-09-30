import { get, post } from "../api.js";
import { $, $$, addDays, badgeEstado, confirmDialog, debounce, esc, fmtDate, formData, modal, money, num, options, table, toast, toastErr, today } from "../ui.js";

let tab = "existencias";
let insumos = [], proveedores = [];

const TABS = [
  ["existencias", "Existencias"], ["entrada", "Entrada de material"], ["ajuste", "Ajuste manual", true],
  ["conteo", "Conteo físico", true], ["kardex", "Kardex / movimientos"], ["entradas", "Historial de entradas"],
];

export async function render(view, ctx) {
  view.innerHTML = `<div class="page"><div class="page-head"><div class="grow"><h1>Inventario</h1>
      <div class="sub">Existencias de insumos, entradas de material, ajustes y kardex. Las ventas descuentan automáticamente (backflush) según la receta.</div></div></div>
      <div id="inv-sum" class="kpis" style="grid-template-columns:repeat(4,1fr);margin-bottom:16px"></div>
      <div class="tabs" id="inv-tabs"></div><div id="inv-body"></div></div>`;
  if (!ctx.isAdmin && TABS.find((t) => t[0] === tab)?.[2]) tab = "existencias";
  $("#inv-tabs").innerHTML = TABS.filter((t) => !t[2] || ctx.isAdmin).map(([k, l]) => `<button data-t="${k}" class="${k === tab ? "active" : ""}">${l}</button>`).join("");
  $$("#inv-tabs button").forEach((b) => b.onclick = () => { tab = b.dataset.t; $$("#inv-tabs button").forEach((x) => x.classList.toggle("active", x === b)); pintarTab(ctx); });
  await recargarBase();
  pintarTab(ctx);
}

async function recargarBase() {
  try {
    [insumos, proveedores] = await Promise.all([get("/insumos"), get("/proveedores")]);
    const r = await get("/inventario/resumen");
    $("#inv-sum").innerHTML = `
      <div class="card kpi"><div class="l">Valor del inventario</div><div class="v">${money(r.valor)}</div><div class="d">a costo promedio</div></div>
      <div class="card kpi"><div class="l">Insumos activos</div><div class="v">${r.insumos}</div></div>
      <div class="card kpi"><div class="l">Bajo mínimo</div><div class="v ${r.bajos ? "warn-t" : ""}">${r.bajos || 0}</div><div class="d">▲ reordenar pronto</div></div>
      <div class="card kpi"><div class="l">Agotados</div><div class="v ${r.agotados ? "bad-t" : ""}">${r.agotados || 0}</div><div class="d">✕ sin existencia</div></div>`;
  } catch (e) { toastErr(e); }
}

function pintarTab(ctx) {
  const body = $("#inv-body");
  body.innerHTML = "";
  ({ existencias, entrada, ajuste, conteo, kardex, entradas })[tab](body, ctx);
}

// ---------------- Existencias ----------------
function existencias(body) {
  body.innerHTML = `<div class="row wrap" style="margin-bottom:12px">
    <input class="input" style="max-width:280px" placeholder="Buscar insumo…" id="ex-q">
    <div class="seg" id="ex-f"><button data-f="" class="active">Todos</button><button data-f="BAJO">Bajo mínimo</button><button data-f="AGOTADO">Agotados</button></div>
    </div><div id="ex-t"></div>`;
  let f = "", q = "";
  const pinta = () => {
    const rows = insumos.filter((i) => (!f || i.estado === f) && (!q || i.nombre.toLowerCase().includes(q) || (i.codigo || "").toLowerCase().includes(q)));
    const t = $("#ex-t"); t.innerHTML = "";
    t.appendChild(table([
      { t: "Código", k: "codigo" }, { t: "Insumo", k: "nombre" }, { t: "Unidad", k: "unidad" },
      { t: "Existencia", k: "stock_actual", cls: "num", f: (v) => `<b>${num(v)}</b>` },
      { t: "Mínimo", k: "stock_minimo", cls: "num", f: (v) => num(v) },
      { t: "Costo prom.", k: "costo_promedio", cls: "num", f: money }, { t: "Valor", k: "valor", cls: "num", f: money },
      { t: "Proveedor", k: "proveedor" }, { t: "Estado", k: "estado", f: badgeEstado },
    ], rows, { empty: "Sin insumos. Dalos de alta en «Menú y recetas → Insumos»." ,
      foot: ["", "", "", "", "", "Total", money(rows.reduce((s, r) => s + r.valor, 0)), "", ""] }));
  };
  $("#ex-q").oninput = debounce((e) => { q = e.target.value.toLowerCase(); pinta(); }, 150);
  $$("#ex-f button").forEach((b) => b.onclick = () => { f = b.dataset.f; $$("#ex-f button").forEach((x) => x.classList.toggle("active", x === b)); pinta(); });
  pinta();
}

// ---------------- Entrada de material ----------------
function entrada(body) {
  const lineas = [];
  body.innerHTML = `<div class="card card-b stack">
    <div class="grid3">
      <label class="f">Proveedor<select class="input" id="en-prov">${options(proveedores.filter((p) => p.activo), "proveedor_id", "nombre", "", "— Sin proveedor —")}</select></label>
      <label class="f">Factura / nota de remisión<input class="input" id="en-fac"></label>
      <label class="f">Notas<input class="input" id="en-not"></label>
    </div>
    <div class="row wrap" style="align-items:flex-end">
      <label class="f grow">Insumo<select class="input" id="en-ins">${options(insumos, "insumo_id", (i) => `${i.nombre} (${i.unidad}) — existencia ${num(i.stock_actual)}`, "", "Selecciona un insumo…")}</select></label>
      <label class="f" style="width:130px">Cantidad<input class="input" type="number" min="0" step="0.001" id="en-cant"></label>
      <label class="f" style="width:150px">Costo unitario<input class="input" type="number" min="0" step="0.01" id="en-cost"></label>
      <button class="btn" id="en-add">Agregar renglón</button>
    </div>
    <div id="en-lin"></div>
    <div class="row"><span class="spacer"></span><span class="ink2">Total de la entrada</span><span class="big-num" id="en-tot">$0.00</span></div>
    <div class="row"><span class="hint grow">Al guardar, la existencia aumenta y el costo promedio ponderado se recalcula automáticamente.</span>
      <button class="btn primary lg" id="en-save">Registrar entrada</button></div></div>`;
  const ins = $("#en-ins"), cant = $("#en-cant"), cost = $("#en-cost");
  const provSel = $("#en-prov");
  provSel.onchange = () => {  // filtra insumos del proveedor si se eligió uno
    const pid = provSel.value;
    const lista = pid ? insumos.filter((i) => String(i.proveedor_id) === pid) : insumos;
    ins.innerHTML = options(lista.length ? lista : insumos, "insumo_id", (i) => `${i.nombre} (${i.unidad}) — existencia ${num(i.stock_actual)}`, "", "Selecciona un insumo…");
  };
  ins.onchange = () => { const i = insumos.find((x) => x.insumo_id === +ins.value); if (i) { cost.value = i.costo_promedio; cant.focus(); } };
  const pinta = () => {
    const el = $("#en-lin"); el.innerHTML = "";
    el.appendChild(table([
      { t: "Insumo", k: "nombre" }, { t: "Cantidad", k: (l) => `${num(l.cantidad)} ${esc(l.unidad)}`, cls: "num" },
      { t: "Costo unit.", k: "costo_unitario", cls: "num", f: money }, { t: "Importe", k: (l) => money(l.cantidad * l.costo_unitario), cls: "num" },
      { t: "", k: (l, i) => `<button class="btn sm ghost" data-del="${lineas.indexOf(l)}">Quitar</button>` },
    ], lineas, { empty: "Agrega los insumos que llegaron" }));
    $$("[data-del]", el).forEach((b) => b.onclick = () => { lineas.splice(+b.dataset.del, 1); pinta(); });
    $("#en-tot").textContent = money(lineas.reduce((s, l) => s + l.cantidad * l.costo_unitario, 0));
  };
  const add = () => {
    const i = insumos.find((x) => x.insumo_id === +ins.value);
    const c = Number(cant.value), p = Number(cost.value);
    if (!i) return toast("Selecciona un insumo", "warn");
    if (!(c > 0)) return toast("Captura una cantidad mayor a 0", "warn");
    if (!(p >= 0) || cost.value === "") return toast("Captura el costo unitario", "warn");
    const ex = lineas.find((l) => l.insumo_id === i.insumo_id && l.costo_unitario === p);
    if (ex) ex.cantidad += c; else lineas.push({ insumo_id: i.insumo_id, nombre: i.nombre, unidad: i.unidad, cantidad: c, costo_unitario: p });
    cant.value = ""; ins.value = ""; cost.value = ""; ins.focus(); pinta();
  };
  $("#en-add").onclick = add;
  [cant, cost].forEach((x) => x.addEventListener("keydown", (e) => e.key === "Enter" && add()));
  $("#en-save").onclick = async () => {
    if (!lineas.length) return toast("La entrada no tiene renglones", "warn");
    try {
      await post("/inventario/entradas", { proveedor_id: provSel.value ? +provSel.value : null, factura: $("#en-fac").value || null,
        notas: $("#en-not").value || null, lineas: lineas.map(({ insumo_id, cantidad, costo_unitario }) => ({ insumo_id, cantidad, costo_unitario })) });
      toast("Entrada registrada");
      await recargarBase(); tab = "entrada"; entrada(body);
    } catch (e) { toastErr(e); }
  };
  pinta();
}

// ---------------- Ajuste manual ----------------
async function ajuste(body) {
  const motivos = await get("/inventario/motivos").catch(() => ["Otro"]);
  body.innerHTML = `<div class="card card-b stack" style="max-width:640px">
    <label class="f">Insumo<select class="input" id="aj-ins">${options(insumos, "insumo_id", (i) => `${i.nombre} (${i.unidad})`, "", "Selecciona…")}</select></label>
    <div id="aj-info" class="hint"></div>
    <div class="seg" id="aj-modo"><button data-m="RESTAR" class="active">Restar (merma, caducidad…)</button><button data-m="SUMAR">Sumar</button><button data-m="CONTEO">Fijar por conteo</button></div>
    <div class="grid2">
      <label class="f"><span id="aj-lbl">Cantidad a restar</span><input class="input lg" type="number" min="0" step="0.001" id="aj-cant"></label>
      <label class="f">Motivo<select class="input" id="aj-mot">${motivos.map((m) => `<option>${esc(m)}</option>`).join("")}</select></label>
    </div>
    <label class="f">Comentario<input class="input" id="aj-com" placeholder="Opcional"></label>
    <div id="aj-prev" class="alert info hidden"></div>
    <div class="row"><span class="spacer"></span><button class="btn primary" id="aj-save">Aplicar ajuste</button></div></div>`;
  let modo = "RESTAR";
  const ins = $("#aj-ins"), cant = $("#aj-cant");
  const prev = () => {
    const i = insumos.find((x) => x.insumo_id === +ins.value);
    $("#aj-info").textContent = i ? `Existencia actual: ${num(i.stock_actual)} ${i.unidad} · costo promedio ${money(i.costo_promedio)}` : "";
    const box = $("#aj-prev");
    if (!i || cant.value === "") { box.classList.add("hidden"); return; }
    const c = Number(cant.value);
    const nuevo = modo === "CONTEO" ? c : modo === "SUMAR" ? i.stock_actual + c : i.stock_actual - c;
    const delta = nuevo - i.stock_actual;
    box.classList.remove("hidden");
    box.innerHTML = `Quedará en <b>${num(nuevo)} ${esc(i.unidad)}</b> (${delta >= 0 ? "+" : ""}${num(delta)}) · impacto ${money(delta * i.costo_promedio)}`;
  };
  $$("#aj-modo button").forEach((b) => b.onclick = () => {
    modo = b.dataset.m; $$("#aj-modo button").forEach((x) => x.classList.toggle("active", x === b));
    $("#aj-lbl").textContent = modo === "CONTEO" ? "Cantidad contada físicamente" : modo === "SUMAR" ? "Cantidad a sumar" : "Cantidad a restar";
    if (modo === "CONTEO") $("#aj-mot").value = "Conteo físico";
    prev();
  });
  ins.onchange = prev; cant.oninput = prev;
  $("#aj-save").onclick = async () => {
    if (!ins.value || cant.value === "") return toast("Selecciona insumo y cantidad", "warn");
    try {
      const r = await post("/inventario/ajustes", { insumo_id: +ins.value, modo, cantidad: Number(cant.value), motivo: $("#aj-mot").value, comentario: $("#aj-com").value || null });
      toast(`Ajuste aplicado (${r.delta > 0 ? "+" : ""}${num(r.delta)})`);
      await recargarBase(); ajuste(body);
    } catch (e) { toastErr(e); }
  };
}

// ---------------- Conteo físico ----------------
function conteo(body) {
  body.innerHTML = `<div class="alert info" style="margin-bottom:12px">Captura lo que contaste físicamente. Sólo se ajustan los insumos donde escribas un conteo diferente a la existencia del sistema.</div>
    <div id="co-t"></div>
    <div class="row" style="margin-top:12px"><input class="input" id="co-com" placeholder="Comentario (ej. inventario de fin de mes)" style="max-width:360px">
      <span class="spacer"></span><span class="ink2" id="co-res"></span><button class="btn primary" id="co-save">Aplicar conteo</button></div>`;
  const t = $("#co-t");
  t.appendChild(table([
    { t: "Insumo", k: "nombre" }, { t: "Unidad", k: "unidad" }, { t: "Sistema", k: "stock_actual", cls: "num", f: (v) => num(v) },
    { t: "Conteo físico", k: (i) => `<input class="input" type="number" min="0" step="0.001" data-c="${i.insumo_id}" style="width:120px;text-align:right">`, cls: "num" },
    { t: "Diferencia", k: (i) => `<span data-d="${i.insumo_id}"></span>`, cls: "num" },
    { t: "Impacto $", k: (i) => `<span data-v="${i.insumo_id}"></span>`, cls: "num" },
  ], insumos));
  const calc = () => {
    let n = 0, tot = 0;
    $$("[data-c]", t).forEach((inp) => {
      const i = insumos.find((x) => x.insumo_id === +inp.dataset.c);
      const d = inp.value === "" ? null : Number(inp.value) - i.stock_actual;
      $(`[data-d="${i.insumo_id}"]`, t).innerHTML = d === null ? "" : `<span class="${d < 0 ? "bad-t" : d > 0 ? "ok-t" : ""}">${d > 0 ? "+" : ""}${num(d)}</span>`;
      $(`[data-v="${i.insumo_id}"]`, t).textContent = d === null ? "" : money(d * i.costo_promedio);
      if (d !== null && Math.abs(d) > 1e-9) { n++; tot += d * i.costo_promedio; }
    });
    $("#co-res").textContent = n ? `${n} diferencias · impacto ${money(tot)}` : "";
  };
  t.addEventListener("input", calc);
  $("#co-save").onclick = async () => {
    const items = $$("[data-c]", t).filter((i) => i.value !== "").map((i) => ({ insumo_id: +i.dataset.c, conteo: Number(i.value) }));
    if (!items.length) return toast("No capturaste ningún conteo", "warn");
    if (!(await confirmDialog(`Se ajustarán las existencias según el conteo. ${esc($("#co-res").textContent)}`, { ok: "Aplicar" }))) return;
    try { const r = await post("/inventario/conteo", { items, comentario: $("#co-com").value || null }); toast(`${r.ajustados} insumos ajustados`); await recargarBase(); conteo(body); }
    catch (e) { toastErr(e); }
  };
}

// ---------------- Kardex ----------------
function kardex(body) {
  body.innerHTML = `<div class="row wrap" style="margin-bottom:12px">
    <label class="f">Insumo<select class="input" id="k-ins">${options(insumos, "insumo_id", "nombre", "", "Todos")}</select></label>
    <label class="f">Tipo<select class="input" id="k-tipo"><option value="">Todos</option><option>ENTRADA</option><option>BACKFLUSH</option><option>AJUSTE</option><option>CANCELACION</option><option>INICIAL</option></select></label>
    <label class="f">Desde<input class="input" type="date" id="k-desde" value="${addDays(today(), -7)}"></label>
    <label class="f">Hasta<input class="input" type="date" id="k-hasta" value="${today()}"></label></div><div id="k-t"></div>`;
  const load = async () => {
    try {
      const rows = await get("/inventario/movimientos", { insumo_id: $("#k-ins").value, tipo: $("#k-tipo").value, desde: $("#k-desde").value, hasta: $("#k-hasta").value, limite: 2000 });
      const el = $("#k-t"); el.innerHTML = "";
      const cls = { ENTRADA: "ok", BACKFLUSH: "info", AJUSTE: "warn", CANCELACION: "acc", INICIAL: "" };
      el.appendChild(table([
        { t: "Fecha", k: "fecha_hora", f: (v) => esc(fmtDate(v)) }, { t: "Insumo", k: "insumo" },
        { t: "Tipo", k: "tipo", f: (v) => `<span class="badge ${cls[v] || ""}">${esc(v)}</span>` },
        { t: "Cantidad", k: (r) => `<span class="${r.cantidad < 0 ? "bad-t" : "ok-t"}">${r.cantidad > 0 ? "+" : ""}${num(r.cantidad)}</span> ${esc(r.unidad)}`, cls: "num" },
        { t: "Costo unit.", k: "costo_unitario", cls: "num", f: money }, { t: "Importe", k: "costo_total", cls: "num", f: money },
        { t: "Existencia", k: "stock_resultante", cls: "num", f: (v) => num(v) }, { t: "Referencia / motivo", k: "motivo" }, { t: "Usuario", k: "usuario" },
      ], rows, { empty: "Sin movimientos en el periodo" }));
    } catch (e) { toastErr(e); }
  };
  ["k-ins", "k-tipo", "k-desde", "k-hasta"].forEach((id) => $("#" + id).onchange = load);
  load();
}

// ---------------- Historial de entradas ----------------
function entradas(body) {
  body.innerHTML = `<div class="row wrap" style="margin-bottom:12px">
    <label class="f">Desde<input class="input" type="date" id="e-desde" value="${addDays(today(), -30)}"></label>
    <label class="f">Hasta<input class="input" type="date" id="e-hasta" value="${today()}"></label></div><div id="e-t"></div>`;
  const load = async () => {
    try {
      const rows = await get("/inventario/entradas", { desde: $("#e-desde").value, hasta: $("#e-hasta").value });
      const el = $("#e-t"); el.innerHTML = "";
      el.appendChild(table([
        { t: "#", k: "entrada_id" }, { t: "Fecha", k: "fecha_hora", f: (v) => esc(fmtDate(v)) }, { t: "Proveedor", k: "proveedor" },
        { t: "Factura", k: "factura" }, { t: "Renglones", k: "renglones", cls: "num" }, { t: "Registró", k: "usuario" },
        { t: "Total", k: "total", cls: "num", f: money },
      ], rows, { onRow: (r) => verEntrada(r.entrada_id), foot: ["", "", "", "", "", "Total", money(rows.reduce((s, r) => s + r.total, 0))] }));
    } catch (e) { toastErr(e); }
  };
  ["e-desde", "e-hasta"].forEach((id) => $("#" + id).onchange = load);
  load();
}

async function verEntrada(id) {
  try {
    const e = await get(`/inventario/entradas/${id}`);
    const m = modal({ title: `Entrada #${id}`, size: "w-lg", footer: null,
      body: `<p class="ink2" style="margin-top:0">${esc(fmtDate(e.fecha_hora))} · ${esc(e.proveedor || "Sin proveedor")} · Factura ${esc(e.factura || "-")} · ${esc(e.usuario)}</p>` });
    m.body.appendChild(table([
      { t: "Insumo", k: "nombre" }, { t: "Cantidad", k: (l) => `${num(l.cantidad)} ${esc(l.unidad)}`, cls: "num" },
      { t: "Costo unit.", k: "costo_unitario", cls: "num", f: money }, { t: "Importe", k: "costo_total", cls: "num", f: money },
    ], e.lineas, { foot: ["", "", "Total", money(e.total)] }));
  } catch (err) { toastErr(err); }
}
