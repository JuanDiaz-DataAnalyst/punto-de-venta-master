import { get, put } from "../api.js";
import { $, esc, formData, printHTML, toast, toastErr } from "../ui.js";
import { refreshConfig, state } from "../app.js";

export async function render(view) {
  let c;
  try { c = await get("/config"); } catch (e) { return toastErr(e); }
  const chk = (k) => (c[k] === "1" ? "checked" : "");
  view.innerHTML = `<div class="page" style="max-width:980px"><div class="page-head"><div class="grow"><h1>Configuración</h1>
    <div class="sub">Datos del negocio, ticket e inventario</div></div><button class="btn primary" id="cfg-save">Guardar cambios</button></div>
    <div class="stack" id="cfg">
      <div class="card"><div class="card-h"><h3>Datos del negocio (aparecen en el ticket)</h3></div><div class="card-b grid2">
        <label class="f">Nombre del negocio<input class="input" name="nombre_negocio" value="${esc(c.nombre_negocio)}"></label>
        <label class="f">RFC<input class="input" name="rfc" value="${esc(c.rfc)}"></label>
        <label class="f">Dirección<input class="input" name="direccion" value="${esc(c.direccion)}"></label>
        <label class="f">Teléfono<input class="input" name="telefono" value="${esc(c.telefono)}"></label>
      </div></div>
      <div class="card"><div class="card-h"><h3>Ticket e impresión</h3></div><div class="card-b grid2">
        <label class="f">Ancho de papel<select class="input" name="ancho_ticket"><option value="80" ${c.ancho_ticket === "80" ? "selected" : ""}>80 mm</option><option value="58" ${c.ancho_ticket === "58" ? "selected" : ""}>58 mm</option></select></label>
        <label class="f">Prefijo de folio<input class="input" name="folio_prefijo" value="${esc(c.folio_prefijo)}"></label>
        <label class="f" style="grid-column:span 2">Mensaje al pie del ticket<input class="input" name="mensaje_ticket" value="${esc(c.mensaje_ticket)}"></label>
        <label class="check"><input type="checkbox" name="imprimir_auto" ${chk("imprimir_auto")}> Imprimir ticket automáticamente al cobrar</label>
        <label class="check"><input type="checkbox" name="mostrar_iva" ${chk("mostrar_iva")}> Mostrar IVA incluido en el ticket</label>
        <label class="f">Tasa de IVA (%)<input class="input" type="number" min="0" max="100" name="tasa_iva" value="${esc(c.tasa_iva)}"></label>
        <div class="row" style="align-items:flex-end"><button class="btn" id="cfg-test">Imprimir ticket de prueba</button></div>
        <p class="hint" style="grid-column:span 2;margin:0">Consejo: instala tu impresora térmica en Windows, márcala como predeterminada y en el diálogo de impresión desactiva encabezados/pies de página y márgenes.</p>
      </div></div>
      <div class="card"><div class="card-h"><h3>Inventario</h3></div><div class="card-b stack">
        <label class="check"><input type="checkbox" name="permitir_stock_negativo" ${chk("permitir_stock_negativo")}> Permitir vender aunque el sistema no tenga existencia suficiente (el inventario puede quedar negativo)</label>
        <p class="hint" style="margin:0">Recomendado al inicio, mientras tus existencias se ajustan a la realidad. Desactívalo cuando tus conteos sean confiables: el sistema bloqueará ventas sin insumos.</p>
      </div></div>
      <div class="card"><div class="card-h"><h3>Datos del sistema</h3></div><div class="card-b">
        <div class="stat-line"><span>Carpeta de datos (base de datos, respaldos, exportaciones)</span><code>${esc(c._data_dir)}</code></div>
        <div class="stat-line"><span>Base de datos</span><span>SQLite (gratuita, sin servidor)</span></div>
      </div></div>
    </div></div>`;
  $("#cfg-save").onclick = async () => {
    const d = formData($("#cfg"));
    ["imprimir_auto", "mostrar_iva", "permitir_stock_negativo"].forEach((k) => d[k] = d[k] ? "1" : "0");
    try { await put("/config", d); await refreshConfig(); toast("Configuración guardada"); } catch (e) { toastErr(e); }
  };
  $("#cfg-test").onclick = () => {
    const d = formData($("#cfg"));
    const w = d.ancho_ticket === "58" ? "58mm" : "80mm";
    printHTML(`<!doctype html><html><head><meta charset=utf-8><style>@page{size:${w} auto;margin:0}body{width:${w};margin:0;padding:3mm;font:12px Consolas,monospace}
      h1{font-size:15px;text-align:center;margin:0}hr{border:0;border-top:1px dashed #000}</style></head><body>
      <h1>${esc(d.nombre_negocio)}</h1><div style="text-align:center">${esc(d.direccion)}<br>${esc(d.telefono)}</div><hr>
      TICKET DE PRUEBA<br>Ancho: ${w}<br>${new Date().toLocaleString("es-MX")}<hr>
      <div style="text-align:center">${esc(d.mensaje_ticket)}</div></body></html>`);
  };
}
