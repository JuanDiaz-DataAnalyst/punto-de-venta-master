import { del, get, post, put } from "../api.js";
import { $, $$, confirmDialog, esc, fmtDate, formData, modal, money, pct, toast, toastErr, today } from "../ui.js";

let datos = { gastos: [], categorias: [] };

const diasDelMes = () => { const h = new Date(); return new Date(h.getFullYear(), h.getMonth() + 1, 0).getDate(); };

export async function render(view) {
  view.innerHTML = `<div class="page">
    <div class="page-head"><div class="grow"><h1>Gastos fijos</h1>
      <div class="sub">Gastos mensuales del negocio. Se reparten por día y alimentan la utilidad, el punto de equilibrio y el dashboard.</div></div>
      <button class="btn" id="g-plantilla" title="Agrega nómina, renta, luz, agua, gas… con monto $0 para que solo captures los importes">Agregar conceptos comunes</button>
      <button class="btn primary" id="g-new">+ Nuevo gasto</button></div>
    <div class="kpis" id="g-kpis" style="grid-template-columns:repeat(4,1fr)"></div>
    <div id="g-aviso" style="margin-top:12px"></div>
    <div id="g-tabla" style="margin-top:14px"></div></div>`;
  $("#g-new").onclick = () => editar(null);
  $("#g-plantilla").onclick = plantilla;
  await cargar();
}

async function cargar() {
  try { datos = await get("/gastos-fijos"); } catch (e) { return toastErr(e); }
  datos.gastos.sort((a, b) => datos.categorias.indexOf(a.categoria) - datos.categorias.indexOf(b.categoria) || a.concepto.localeCompare(b.concepto, "es"));
  pintarTabla();
  pintarResumen();
}

function estado(g) {
  const hoy = today();
  if (g.vigente_hasta && g.vigente_hasta < hoy) return `<span class="badge">Terminado</span>`;
  if (g.vigente_desde > hoy) return `<span class="badge info">Inicia ${esc(fmtDate(g.vigente_desde))}</span>`;
  if (!g.monto_mensual) return `<span class="badge warn">Sin monto</span>`;
  return `<span class="badge ok">Vigente</span>`;
}

// Totales con los gastos vigentes hoy; se recalculan en el navegador para no perder el foco al capturar montos
function pintarResumen() {
  const vig = datos.gastos.filter((g) => g.vigente);
  const total = vig.reduce((s, g) => s + g.monto_mensual, 0);
  const nomina = vig.filter((g) => g.categoria === "Nómina").reduce((s, g) => s + g.monto_mensual, 0);
  const sinMonto = datos.gastos.filter((g) => g.vigente && !g.monto_mensual).length;
  $("#g-kpis").innerHTML = `
    <div class="card kpi hero"><div class="l">Gastos fijos al mes</div><div class="v">${money(total)}</div><div class="d">${vig.length} conceptos vigentes</div></div>
    <div class="card kpi"><div class="l">Nómina</div><div class="v">${money(nomina)}</div><div class="d">${total ? pct(nomina / total, 0) + " de los gastos fijos" : "—"}</div></div>
    <div class="card kpi"><div class="l">Equivale por día</div><div class="v">${money(total / diasDelMes())}</div><div class="d">gasto fijo diario promedio de este mes</div></div>
    <div class="card kpi"><div class="l">Servicios y renta</div><div class="v">${money(vig.filter((g) => ["Servicios", "Renta"].includes(g.categoria)).reduce((s, g) => s + g.monto_mensual, 0))}</div><div class="d">luz, agua, gas, internet y local</div></div>`;
  $("#g-aviso").innerHTML = !datos.gastos.length
    ? `<div class="alert info">Aún no hay gastos capturados. Usa <b>Agregar conceptos comunes</b> para empezar con una lista típica de restaurante pequeño y solo captura los importes.</div>`
    : sinMonto ? `<div class="alert">${sinMonto} concepto${sinMonto > 1 ? "s" : ""} sin monto. Escribe el importe mensual directamente en la tabla; los que están en $0 no afectan los cálculos.</div>` : "";
  const foot = $("#g-total");
  if (foot) foot.textContent = money(total);
  const diario = $("#g-total-dia");
  if (diario) diario.textContent = money(total / diasDelMes());
}

function pintarTabla() {
  const el = $("#g-tabla");
  if (!datos.gastos.length) { el.innerHTML = `<div class="tbl-wrap"><div class="empty">Sin gastos fijos registrados</div></div>`; return; }
  el.innerHTML = `<div class="tbl-wrap"><table class="tbl"><thead><tr>
      <th>Concepto</th><th>Categoría</th><th class="num">Monto mensual</th><th class="num">Por día</th><th>Vigencia</th><th>Estado</th><th></th></tr></thead>
    <tbody>${datos.gastos.map((g) => `<tr data-id="${g.gasto_id}" class="${g.vigente ? "" : "off"}">
      <td><b>${esc(g.concepto)}</b>${g.notas ? `<div class="hint">${esc(g.notas)}</div>` : ""}</td>
      <td>${esc(g.categoria)}</td>
      <td class="num"><input class="input g-monto" type="number" min="0" step="50" value="${g.monto_mensual || ""}" placeholder="0.00" aria-label="Monto mensual de ${esc(g.concepto)}" style="width:130px;text-align:right"></td>
      <td class="num" data-dia>${money(g.monto_mensual / diasDelMes())}</td>
      <td class="nowrap">${esc(fmtDate(g.vigente_desde))} → ${g.vigente_hasta ? esc(fmtDate(g.vigente_hasta)) : "sin fin"}</td>
      <td>${estado(g)}</td>
      <td><button class="btn sm" data-edit>Editar</button></td></tr>`).join("")}</tbody>
    <tfoot><tr><td colspan="2">Total mensual vigente</td><td class="num" id="g-total"></td><td class="num" id="g-total-dia"></td><td colspan="3"></td></tr></tfoot></table></div>
    <p class="hint" style="margin-top:8px">Escribir un monto en la tabla corrige ese gasto en todo su periodo de vigencia. Para registrar un aumento sin cambiar los meses anteriores, termina el gasto en la fecha del cambio (Editar → «Vigente hasta») y agrega uno nuevo con el monto actualizado.</p>`;
  $$("tbody tr", el).forEach((tr) => {
    const g = datos.gastos.find((x) => x.gasto_id === +tr.dataset.id);
    $("[data-edit]", tr).onclick = () => editar(g);
    const inp = $(".g-monto", tr);
    inp.addEventListener("keydown", (e) => { if (e.key === "Enter") inp.blur(); });
    inp.addEventListener("change", async () => {
      const v = Math.max(0, Number(inp.value || 0));
      if (v === g.monto_mensual) return;
      try {
        await put(`/gastos-fijos/${g.gasto_id}`, cuerpo({ ...g, monto_mensual: v }));
        g.monto_mensual = v;
        $("[data-dia]", tr).textContent = money(v / diasDelMes());
        $("td:nth-child(6)", tr).innerHTML = estado(g);
        pintarResumen();
        toast("Guardado");
      } catch (e) { inp.value = g.monto_mensual || ""; toastErr(e); }
    });
  });
}

const cuerpo = (g) => ({ concepto: g.concepto, categoria: g.categoria, monto_mensual: g.monto_mensual, vigente_desde: g.vigente_desde, vigente_hasta: g.vigente_hasta || null, notas: g.notas || null });

async function plantilla() {
  try {
    const r = await post("/gastos-fijos/plantilla");
    toast(r.agregados ? `Se agregaron ${r.agregados} conceptos. Captura el monto de cada uno.` : "Ya tienes todos los conceptos comunes");
    cargar();
  } catch (e) { toastErr(e); }
}

function editar(g) {
  const nuevo = !g;
  g = g || { concepto: "", categoria: datos.categorias[0], monto_mensual: "", vigente_desde: today().slice(0, 8) + "01", vigente_hasta: "", notas: "" };
  const m = modal({
    title: nuevo ? "Nuevo gasto fijo" : `Editar: ${g.concepto}`, size: "w-sm",
    body: `<div class="stack">
      <label class="f">Concepto<input class="input" name="concepto" maxlength="120" value="${esc(g.concepto)}" placeholder="Ej. Salario de Juan (cocinero)"></label>
      <label class="f">Categoría<select class="input" name="categoria">${datos.categorias.map((c) => `<option ${c === g.categoria ? "selected" : ""}>${esc(c)}</option>`).join("")}</select></label>
      <label class="f">Monto mensual<input class="input lg" type="number" min="0" step="50" name="monto_mensual" value="${g.monto_mensual ?? ""}"></label>
      <div class="grid2">
        <label class="f">Vigente desde<input class="input" type="date" name="vigente_desde" value="${esc(g.vigente_desde)}"></label>
        <label class="f">Vigente hasta<input class="input" type="date" name="vigente_hasta" value="${esc(g.vigente_hasta || "")}"></label>
      </div>
      <label class="f">Notas (opcional)<input class="input" name="notas" value="${esc(g.notas || "")}"></label>
      <div class="hint">Deja «Vigente hasta» vacío mientras el gasto siga aplicando. Cada día cuenta una parte proporcional del mes.</div></div>`,
    footer: `${nuevo ? "" : `<button class="btn danger" data-del>Eliminar</button><span class="spacer"></span>`}<button class="btn" data-c>Cancelar</button><button class="btn primary" data-s>Guardar</button>`,
  });
  $("[data-c]", m.el).onclick = () => m.close();
  const borrar = $("[data-del]", m.el);
  if (borrar) borrar.onclick = async () => {
    if (!(await confirmDialog(`¿Eliminar «${esc(g.concepto)}»? Dejará de contarse en todos los periodos. Si solo terminó, mejor ponle fecha en «Vigente hasta».`, { ok: "Eliminar", danger: true }))) return;
    try { await del(`/gastos-fijos/${g.gasto_id}`); m.close(); toast("Gasto eliminado"); cargar(); } catch (e) { toastErr(e); }
  };
  $("[data-s]", m.el).onclick = async () => {
    const d = formData(m.body);
    d.monto_mensual = d.monto_mensual ?? 0;
    d.vigente_hasta = d.vigente_hasta || null;
    d.notas = d.notas || null;
    try { nuevo ? await post("/gastos-fijos", d) : await put(`/gastos-fijos/${g.gasto_id}`, d); m.close(); toast("Gasto guardado"); cargar(); }
    catch (e) { toastErr(e); }
  };
}
