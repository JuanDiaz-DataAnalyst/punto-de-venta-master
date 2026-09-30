import { api, get, post } from "../api.js";
import { $, $$, badgeEstado, confirmDialog, esc, fmtDate, formData, modal, money, printHTML, table, toast, toastErr } from "../ui.js";

const DENOMS = [1000, 500, 200, 100, 50, 20, 10, 5, 2, 1, 0.5];

export async function render(view, ctx) {
  view.innerHTML = `<div class="page"><div class="page-head"><div class="grow"><h1>Caja y turno</h1>
      <div class="sub">Apertura, entradas/salidas de efectivo y corte de caja</div></div></div>
      <div id="caja-act"></div>
      ${ctx.isAdmin ? `<h2 style="margin:28px 0 12px">Historial de cortes</h2><div id="caja-hist"></div>` : ""}</div>`;
  await pintar(ctx);
}

async function pintar(ctx) {
  const box = $("#caja-act");
  let r;
  try { r = await get("/turno/actual"); } catch (e) { return toastErr(e); }
  if (!r.turno) {
    box.innerHTML = `<div class="card card-b stack" style="max-width:460px">
      <h3>No hay turno abierto</h3><p class="ink2" style="margin:0">Abre la caja registrando el fondo inicial en efectivo.</p>
      <label class="f">Fondo inicial<input class="input lg" type="number" min="0" step="0.5" value="500" id="fondo"></label>
      <button class="btn primary lg" id="abrir">Abrir caja</button></div>`;
    $("#abrir").onclick = async () => {
      try { await post("/turno/abrir", { fondo_inicial: Number($("#fondo").value || 0) }); toast("Turno abierto"); pintar(ctx); }
      catch (e) { toastErr(e); }
    };
  } else {
    const t = r.turno;
    box.innerHTML = `
      <div class="row wrap" style="margin-bottom:14px">
        ${badgeEstado("ABIERTO")}<span class="ink2">Turno #${t.turno_id} · abierto ${esc(fmtDate(t.apertura))} por <b>${esc(t.usuario_apertura || "")}</b></span>
        <span class="spacer"></span>
        <button class="btn" data-mov="INGRESO">+ Ingreso de efectivo</button>
        <button class="btn" data-mov="RETIRO">− Retiro de efectivo</button>
        <button class="btn" id="imp">Imprimir corte parcial (X)</button>
        <button class="btn primary" id="cerrar">Cerrar turno (corte Z)</button>
      </div>
      <div class="kpis" style="grid-template-columns:repeat(4,1fr)">
        <div class="card kpi"><div class="l">Ventas del turno</div><div class="v">${money(r.total_ventas)}</div><div class="d">${r.tickets} tickets</div></div>
        <div class="card kpi"><div class="l">Efectivo esperado en caja</div><div class="v">${money(r.efectivo_esperado)}</div><div class="d">Fondo ${money(t.fondo_inicial)} + efectivo ${money(r.efectivo_ventas)}</div></div>
        <div class="card kpi"><div class="l">Entradas / salidas de caja</div><div class="v">${money(r.ingresos_caja - r.retiros_caja)}</div><div class="d">+${money(r.ingresos_caja)} / −${money(r.retiros_caja)}</div></div>
        <div class="card kpi"><div class="l">Cancelaciones</div><div class="v">${r.canceladas}</div><div class="d">${money(r.total_canceladas)}</div></div>
      </div>
      <div class="grid2" style="margin-top:14px">
        <div class="card"><div class="card-h"><h3>Por método de pago</h3></div><div class="card-b" id="c-met"></div></div>
        <div class="card"><div class="card-h"><h3>Movimientos de efectivo</h3></div><div class="card-b" id="c-mov"></div></div>
      </div>`;
    $("#c-met").appendChild(table([
      { t: "Método", k: "metodo" }, { t: "Tickets", k: "tickets", cls: "num" }, { t: "Total", k: "total", cls: "num", f: money },
    ], r.por_metodo));
    $("#c-mov").appendChild(table([
      { t: "Hora", k: "fecha_hora", f: (v) => esc(v.slice(11, 16)) }, { t: "Tipo", k: "tipo" }, { t: "Concepto", k: "concepto" },
      { t: "Usuario", k: "usuario" }, { t: "Monto", k: "monto", cls: "num", f: money },
    ], r.movimientos_caja, { empty: "Sin movimientos de efectivo" }));
    $$("[data-mov]", box).forEach((b) => b.onclick = () => movimiento(b.dataset.mov, ctx));
    $("#imp").onclick = () => imprimirCorte(t.turno_id);
    $("#cerrar").onclick = () => cerrar(r, ctx);
  }
  if (ctx.isAdmin) historial();
}

function movimiento(tipo, ctx) {
  const m = modal({
    title: tipo === "INGRESO" ? "Ingreso de efectivo" : "Retiro de efectivo", size: "w-sm",
    body: `<div class="stack"><label class="f">Monto<input class="input lg" type="number" min="0" step="0.5" name="monto"></label>
      <label class="f">Concepto<input class="input" name="concepto" placeholder="${tipo === "RETIRO" ? "Ej. pago de gas, compra de hielo" : "Ej. cambio adicional"}"></label></div>`,
    footer: `<button class="btn" data-c>Cancelar</button><button class="btn primary" data-s>Registrar</button>`,
  });
  $("[data-c]", m.el).onclick = () => m.close();
  $("[data-s]", m.el).onclick = async () => {
    const d = formData(m.body);
    try { await post("/turno/movimiento", { tipo, ...d }); m.close(); toast("Movimiento registrado"); pintar(ctx); } catch (e) { toastErr(e); }
  };
}

function cerrar(r, ctx) {
  const m = modal({
    title: "Corte de caja — cerrar turno", size: "w-lg",
    body: `<div class="grid2" style="align-items:start">
      <div><h3 style="margin-bottom:8px">Conteo de efectivo</h3>
        <div class="tbl-wrap"><table class="tbl"><thead><tr><th>Denominación</th><th class="num">Cantidad</th><th class="num">Importe</th></tr></thead><tbody>
        ${DENOMS.map((d) => `<tr><td>${money(d)}</td><td class="num"><input class="input" style="width:80px;text-align:right" type="number" min="0" data-d="${d}"></td><td class="num" data-imp="${d}">$0.00</td></tr>`).join("")}
        </tbody></table></div></div>
      <div class="stack">
        <div class="card card-b stack" style="gap:6px">
          <div class="stat-line"><span>Fondo inicial</span><b>${money(r.turno.fondo_inicial)}</b></div>
          <div class="stat-line"><span>+ Ventas en efectivo</span><b>${money(r.efectivo_ventas)}</b></div>
          <div class="stat-line"><span>+ Ingresos</span><b>${money(r.ingresos_caja)}</b></div>
          <div class="stat-line"><span>− Retiros</span><b>${money(r.retiros_caja)}</b></div>
          <div class="stat-line"><span><b>Efectivo esperado</b></span><b>${money(r.efectivo_esperado)}</b></div>
        </div>
        <label class="f">Efectivo contado<input class="input lg" type="number" min="0" step="0.5" id="contado" value=""></label>
        <div class="change-box" id="dif"><span>Diferencia</span><b>$0.00</b></div>
        <label class="f">Notas del cierre<input class="input" id="notas" placeholder="Opcional"></label>
      </div></div>`,
    footer: `<button class="btn" data-c>Cancelar</button><button class="btn primary" data-s>Cerrar turno</button>`,
  });
  const contado = $("#contado", m.el);
  const upd = () => {
    const d = Number(contado.value || 0) - r.efectivo_esperado;
    const box = $("#dif", m.el);
    box.classList.toggle("neg", Math.abs(d) > 0.009);
    box.innerHTML = `<span>${d > 0.009 ? "Sobrante" : d < -0.009 ? "Faltante" : "Cuadra exacto"}</span><b>${money(d)}</b>`;
  };
  $$("[data-d]", m.el).forEach((i) => i.addEventListener("input", () => {
    let tot = 0;
    $$("[data-d]", m.el).forEach((x) => { const v = Number(x.value || 0) * Number(x.dataset.d); tot += v; $(`[data-imp="${x.dataset.d}"]`, m.el).textContent = money(v); });
    contado.value = tot.toFixed(2); upd();
  }));
  contado.addEventListener("input", upd); upd();
  $("[data-c]", m.el).onclick = () => m.close();
  $("[data-s]", m.el).onclick = async () => {
    if (contado.value === "") return toast("Captura el efectivo contado", "warn");
    if (!(await confirmDialog("¿Cerrar el turno? Ya no se podrán registrar ventas en él.", { ok: "Cerrar turno" }))) return;
    try {
      const res = await post("/turno/cerrar", { efectivo_contado: Number(contado.value), notas: $("#notas", m.el).value || null });
      m.close();
      toast(`Turno cerrado. Diferencia: ${money(res.turno.diferencia)}`, Math.abs(res.turno.diferencia) > 0.009 ? "warn" : "ok", 6000);
      imprimirCorte(res.turno.turno_id);
      pintar(ctx);
    } catch (e) { toastErr(e); }
  };
}

async function imprimirCorte(id) {
  try { printHTML(await api(`/turnos/${id}/corte`, { raw: true })); } catch (e) { toastErr(e); }
}

async function historial() {
  const el = $("#caja-hist");
  if (!el) return;
  let rows;
  try { rows = await get("/turnos"); } catch (e) { return toastErr(e); }
  el.innerHTML = "";
  el.appendChild(table([
    { t: "#", k: "turno_id" }, { t: "Apertura", k: "apertura", f: (v) => esc(fmtDate(v)) },
    { t: "Cierre", k: "cierre", f: (v) => esc(fmtDate(v)) }, { t: "Abrió", k: "usuario_apertura" },
    { t: "Estado", k: "estado", f: badgeEstado }, { t: "Tickets", k: "tickets", cls: "num" },
    { t: "Ventas", k: "total_ventas", cls: "num", f: money }, { t: "Esperado", k: "efectivo_esperado", cls: "num", f: (v) => v == null ? "" : money(v) },
    { t: "Contado", k: "efectivo_contado", cls: "num", f: (v) => v == null ? "" : money(v) },
    { t: "Diferencia", k: "diferencia", cls: "num", f: (v) => v == null ? "" : `<span class="${v < 0 ? "bad-t" : v > 0 ? "warn-t" : "ok-t"}">${money(v)}</span>` },
    { t: "", k: (r) => `<button class="btn sm" data-p="${r.turno_id}">Imprimir</button>` },
  ], rows));
  $$("[data-p]", el).forEach((b) => b.onclick = () => imprimirCorte(b.dataset.p));
}
