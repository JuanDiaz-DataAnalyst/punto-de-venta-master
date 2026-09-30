import { api, get, post } from "../api.js";
import { $, addDays, badgeEstado, debounce, esc, fmtDate, modal, money, printHTML, table, toast, toastErr, today } from "../ui.js";

const filtros = { desde: addDays(today(), -6), hasta: today(), estado: "", buscar: "" };

export async function render(view, ctx) {
  view.innerHTML = `<div class="page">
    <div class="page-head"><div class="grow"><h1>Ventas</h1>
      <div class="sub">${ctx.isAdmin ? "Historial de tickets, reimpresión y cancelaciones" : "Tickets del turno actual"}</div></div></div>
    <div class="row wrap" style="margin-bottom:14px">
      ${ctx.isAdmin ? `<label class="f">Desde<input class="input" type="date" id="f-desde" value="${filtros.desde}"></label>
      <label class="f">Hasta<input class="input" type="date" id="f-hasta" value="${filtros.hasta}"></label>` : ""}
      <label class="f">Estado<select class="input" id="f-estado">
        <option value="">Todas</option><option value="PAGADA">Pagadas</option><option value="CANCELADA">Canceladas</option></select></label>
      <label class="f grow" style="max-width:280px">Buscar<input class="input" id="f-buscar" placeholder="Folio o cliente" value="${esc(filtros.buscar)}"></label>
    </div>
    <div id="v-res" class="row wrap" style="margin-bottom:10px"></div>
    <div id="v-tabla"></div></div>`;
  $("#f-estado").value = filtros.estado;
  const recargar = () => cargar(ctx);
  ["f-desde", "f-hasta", "f-estado"].forEach((id) => { const el = $("#" + id); if (el) el.onchange = () => { filtros[id.slice(2)] = el.value; recargar(); }; });
  $("#f-buscar").oninput = debounce(() => { filtros.buscar = $("#f-buscar").value; recargar(); });
  await recargar();
}

async function cargar(ctx) {
  let rows;
  try {
    rows = await get("/ventas", ctx.isAdmin ? filtros : { estado: filtros.estado, buscar: filtros.buscar });
  } catch (e) { return toastErr(e); }
  const pag = rows.filter((r) => r.estado === "PAGADA");
  const total = pag.reduce((s, r) => s + r.total, 0);
  $("#v-res").innerHTML = `<span class="badge info">${pag.length} tickets pagados</span><span class="badge ok">Total ${money(total)}</span>
     ${pag.length ? `<span class="badge">Ticket promedio ${money(total / pag.length)}</span>` : ""}
     ${rows.length - pag.length ? `<span class="badge bad">${rows.length - pag.length} canceladas</span>` : ""}`;
  const el = $("#v-tabla"); el.innerHTML = "";
  el.appendChild(table([
    { t: "Folio", k: "folio" }, { t: "Fecha", k: "fecha_hora", f: (v) => esc(fmtDate(v)) },
    { t: "Atendió", k: "usuario" }, { t: "Pago", k: "metodo_pago" }, { t: "Cliente", k: "cliente" },
    { t: "Artículos", k: "articulos", cls: "num" }, { t: "Descuento", k: "descuento", cls: "num", f: (v) => v ? money(v) : "" },
    { t: "Total", k: "total", cls: "num", f: (v) => `<b>${money(v)}</b>` },
    ...(ctx.isAdmin ? [{ t: "Margen", k: (r) => money(r.total - r.costo_total), cls: "num" }] : []),
    { t: "Estado", k: "estado", f: badgeEstado },
  ], rows, { onRow: (r) => detalle(r.venta_id, ctx), rowClass: (r) => r.estado === "CANCELADA" ? "off" : "", empty: "No hay ventas con estos filtros" }));
}

async function detalle(id, ctx) {
  let v;
  try { v = await get(`/ventas/${id}`); } catch (e) { return toastErr(e); }
  const m = modal({
    title: `Ticket ${v.folio}`, size: "w-lg",
    body: `<div class="row wrap" style="margin-bottom:12px">${badgeEstado(v.estado)}<span class="ink2">${esc(fmtDate(v.fecha_hora))} · ${esc(v.usuario)} · ${esc(v.metodo_pago)} · Turno #${v.turno_id ?? "-"}</span></div>
      ${v.estado === "CANCELADA" ? `<div class="alert bad" style="margin-bottom:12px">Cancelada el ${esc(fmtDate(v.cancelada_en))} por ${esc(v.cancelada_por_nombre || "")}: ${esc(v.motivo_cancelacion || "")}</div>` : ""}
      <div id="d-lin"></div>
      <div class="grid2" style="margin-top:14px"><div class="ink2">${v.cliente ? "Cliente: " + esc(v.cliente) : ""}</div>
        <div class="stack" style="gap:4px">
          <div class="stat-line"><span>Subtotal</span><b>${money(v.subtotal)}</b></div>
          ${v.descuento ? `<div class="stat-line"><span>Descuento</span><b>−${money(v.descuento)}</b></div>` : ""}
          <div class="stat-line"><span>Total</span><b style="font-size:18px">${money(v.total)}</b></div>
          ${v.es_efectivo ? `<div class="stat-line"><span>Recibido / cambio</span><span>${money(v.pago_recibido)} / ${money(v.cambio)}</span></div>` : ""}
          ${ctx.isAdmin ? `<div class="stat-line"><span>Costo (backflush)</span><span>${money(v.costo_total)}</span></div>
          <div class="stat-line"><span>Margen bruto</span><b class="ok-t">${money(v.total - v.costo_total)}</b></div>` : ""}
        </div></div>`,
    footer: `${ctx.isAdmin && v.estado === "PAGADA" ? `<button class="btn danger" data-cancel>Cancelar venta</button><span class="spacer"></span>` : ""}
      <button class="btn" data-print>Reimprimir ticket</button><button class="btn primary" data-close>Cerrar</button>`,
  });
  $("#d-lin", m.el).appendChild(table([
    { t: "Cant.", k: "cantidad", cls: "num" }, { t: "Producto", k: (l) => esc(l.producto) + (l.nota ? `<div class="hint">${esc(l.nota)}</div>` : "") },
    { t: "Precio", k: "precio_unitario", cls: "num", f: money }, { t: "Importe", k: "importe_neto", cls: "num", f: money },
    ...(ctx.isAdmin ? [{ t: "Costo", k: "costo_total", cls: "num", f: money }, { t: "Margen", k: "margen", cls: "num", f: money }] : []),
  ], v.lineas));
  $("[data-close]", m.el).onclick = () => m.close();
  $("[data-print]", m.el).onclick = async () => { try { printHTML(await api(`/ventas/${id}/ticket?reimpresion=true`, { raw: true })); } catch (e) { toastErr(e); } };
  const c = $("[data-cancel]", m.el);
  if (c) c.onclick = async () => {
    const { promptDialog } = await import("../ui.js");
    const motivo = await promptDialog("Motivo de la cancelación (el inventario consumido se regresará automáticamente)", { title: "Cancelar " + v.folio, ok: "Cancelar venta" });
    if (!motivo) return;
    try { await post(`/ventas/${id}/cancelar`, { motivo }); toast("Venta cancelada y inventario devuelto"); m.close(); cargar(ctx); }
    catch (e) { toastErr(e); }
  };
}
