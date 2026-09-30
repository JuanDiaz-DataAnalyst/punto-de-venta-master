import { get, post, session } from "../api.js";
import { $, $$, addDays, confirmDialog, esc, fmtDate, table, toast, toastErr, today } from "../ui.js";

const DESC = {
  ventas_detalle: "Cada renglón vendido (tabla de hechos) con fecha, producto, categoría, usuario, método de pago, costo y margen.",
  ventas: "Un renglón por ticket: totales, descuento, costo, margen y estado.",
  productos: "Unidades, ventas, costo y margen por producto en el periodo.",
  inventario: "Existencias actuales valorizadas a costo promedio, con estado vs. mínimo.",
  movimientos: "Kardex: entradas, backflush por ventas, ajustes y cancelaciones.",
  recetas: "Recetas de cada producto con costo teórico por insumo.",
  turnos: "Cortes de caja: fondo, esperado, contado y diferencias.",
  auditoria: "Bitácora de acciones de los usuarios.",
};

export async function render(view) {
  view.innerHTML = `<div class="page"><div class="page-head"><div class="grow"><h1>Reportes y respaldos</h1>
    <div class="sub">Exporta a Excel/CSV, respalda la base de datos y consulta la bitácora de auditoría</div></div></div>
    <div class="tabs" id="r-tabs"><button data-t="exp" class="active">Exportar</button><button data-t="resp">Respaldos</button><button data-t="aud">Auditoría</button></div>
    <div id="r-body"></div></div>`;
  $$("#r-tabs button").forEach((b) => b.onclick = () => { $$("#r-tabs button").forEach((x) => x.classList.toggle("active", x === b)); pintar(b.dataset.t); });
  pintar("exp");
}

function pintar(t) {
  const body = $("#r-body");
  body.innerHTML = "";
  ({ exp: exportar, resp: respaldos, aud: auditoria })[t](body);
}

async function exportar(body) {
  const tipos = await get("/exportar/tipos").catch(() => []);
  body.innerHTML = `<div class="row wrap" style="margin-bottom:16px;align-items:flex-end">
      <label class="f">Desde<input class="input" type="date" id="x-desde" value="${addDays(today(), -29)}"></label>
      <label class="f">Hasta<input class="input" type="date" id="x-hasta" value="${today()}"></label>
      <button class="btn primary" data-x="todo" data-f="xlsx">Exportar todo a un Excel</button>
      <button class="btn" id="x-folder">Abrir carpeta de exportaciones</button></div>
    <div class="grid3" id="x-cards"></div>
    <div class="alert info" style="margin-top:16px">Para Power BI: conecta Power BI Desktop a la base SQLite (conector ODBC de SQLite) y usa las vistas <code>v_ventas_detalle</code>, <code>v_inventario_valorizado</code>, <code>v_movimientos_inventario</code> y <code>v_costo_receta</code>, o importa el Excel exportado.</div>`;
  $("#x-cards").innerHTML = tipos.map((t) => `<div class="card card-b stack" style="gap:8px"><h3>${esc(t.nombre)}</h3>
      <p class="hint" style="margin:0;flex:1">${esc(DESC[t.clave] || "")}</p>
      <div class="row"><button class="btn sm" data-x="${t.clave}" data-f="xlsx">Excel</button><button class="btn sm" data-x="${t.clave}" data-f="csv">CSV</button></div></div>`).join("");
  $$("[data-x]", body).forEach((b) => b.onclick = async () => {
    b.disabled = true;
    try {
      const r = await post(`/exportar/${b.dataset.x}`, {}, { formato: b.dataset.f, desde: $("#x-desde").value, hasta: $("#x-hasta").value });
      if (r.abierto) toast(`Exportado (${r.filas} filas). Abriendo ${r.archivo}…`);
      else descargar(r.archivo, r.filas);
    } catch (e) { toastErr(e); }
    b.disabled = false;
  });
  $("#x-folder").onclick = abrirCarpeta("exportaciones");
}

async function descargar(archivo, filas) {
  // Modo navegador: descarga el archivo generado
  try {
    const res = await fetch(`/api/exportar/descargar/${encodeURIComponent(archivo)}`, { headers: { Authorization: "Bearer " + session.token } });
    const blob = await res.blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob); a.download = archivo; document.body.appendChild(a); a.click(); a.remove();
    toast(`Exportado: ${archivo} (${filas} filas)`);
  } catch (e) { toastErr(e); }
}

const abrirCarpeta = (cual) => async () => {
  try { const r = await post(`/abrir-carpeta/${cual}`); if (!r.abierto) toast(`Carpeta: ${r.ruta}`, "ok", 7000); } catch (e) { toastErr(e); }
};

async function respaldos(body) {
  body.innerHTML = `<div class="row wrap" style="margin-bottom:14px"><button class="btn primary" id="b-new">Crear respaldo ahora</button>
    <button class="btn" id="b-folder">Abrir carpeta de respaldos</button>
    <span class="hint">Se crea un respaldo automático cada vez que se abre el sistema; se conservan los últimos 20. Copia periódicamente la carpeta a una USB o a la nube.</span></div><div id="b-t"></div>`;
  const load = async () => {
    const rows = await get("/respaldos").catch((e) => { toastErr(e); return []; });
    const el = $("#b-t"); el.innerHTML = "";
    el.appendChild(table([
      { t: "Archivo", k: "archivo" }, { t: "Fecha", k: "fecha", f: (v) => esc(fmtDate(v)) }, { t: "Tamaño", k: "tamano_kb", cls: "num", f: (v) => `${v} KB` },
      { t: "", k: (r) => `<button class="btn sm danger" data-r="${esc(r.archivo)}">Restaurar</button>` },
    ], rows, { empty: "Aún no hay respaldos" }));
    $$("[data-r]", el).forEach((b) => b.onclick = async () => {
      if (!(await confirmDialog(`Se reemplazarán TODOS los datos actuales por el respaldo <b>${esc(b.dataset.r)}</b>. Antes se guardará un respaldo de seguridad del estado actual. ¿Continuar?`, { ok: "Restaurar", danger: true }))) return;
      try { await post(`/respaldos/${encodeURIComponent(b.dataset.r)}/restaurar`); toast("Respaldo restaurado. Recargando…"); setTimeout(() => location.reload(), 1200); }
      catch (e) { toastErr(e); }
    });
  };
  $("#b-new").onclick = async () => { try { const r = await post("/respaldos"); toast("Respaldo creado: " + r.archivo); load(); } catch (e) { toastErr(e); } };
  $("#b-folder").onclick = abrirCarpeta("respaldos");
  load();
}

async function auditoria(body) {
  body.innerHTML = `<div class="row wrap" style="margin-bottom:12px">
    <label class="f">Desde<input class="input" type="date" id="a-desde" value="${addDays(today(), -2)}"></label>
    <label class="f">Hasta<input class="input" type="date" id="a-hasta" value="${today()}"></label>
    <label class="f">Acción<input class="input" id="a-acc" placeholder="Ej. CANCELAR, AJUSTE, LOGIN"></label></div><div id="a-t"></div>`;
  const load = async () => {
    try {
      const rows = await get("/auditoria", { desde: $("#a-desde").value, hasta: $("#a-hasta").value, accion: $("#a-acc").value });
      const el = $("#a-t"); el.innerHTML = "";
      el.appendChild(table([
        { t: "Fecha", k: "fecha_hora", f: (v) => esc(fmtDate(v)) }, { t: "Usuario", k: "usuario" },
        { t: "Acción", k: "accion", f: (v) => `<span class="badge ${/CANCEL|FALLIDO|RESTAUR/.test(v) ? "bad" : /AJUSTE|EDITAR/.test(v) ? "warn" : ""}">${esc(v)}</span>` },
        { t: "Detalle", k: "detalle" },
      ], rows, { empty: "Sin registros" }));
    } catch (e) { toastErr(e); }
  };
  ["a-desde", "a-hasta"].forEach((id) => $("#" + id).onchange = load);
  $("#a-acc").oninput = () => { clearTimeout(load.t); load.t = setTimeout(load, 300); };
  load();
}
