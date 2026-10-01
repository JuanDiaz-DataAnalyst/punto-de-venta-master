import { api, del, get, post, put } from "../api.js";
import { $, $$, confirmDialog, esc, modal, money, printHTML, promptDialog, toast, toastErr } from "../ui.js";

// Las cuentas (una por mesa) viven en el servidor: sobreviven si se cierra la app o se cambia de pantalla.
// Aquí solo se recuerda cuál pestaña está activa, el método de pago y los filtros del menú.
let cuentas = [];
let activaId = null;
let metodo = null;
let cat = null;
let filtroCat = "";
let busqueda = "";

// Las escrituras se hacen una tras otra para que las respuestas no lleguen desordenadas
let cola = Promise.resolve();
function enCola(fn) { const p = cola.then(fn); cola = p.catch(() => {}); return p; }

const cuenta = () => cuentas.find((c) => c.cuenta_id === activaId) || null;
const mesaTitulo = (m) => (/^\d+$/.test(m) ? `Mesa ${m}` : m);

function siguienteMesa() {
  const usadas = new Set(cuentas.map((c) => c.mesa.toLowerCase()));
  let n = 1;
  while (usadas.has(String(n))) n++;
  return String(n);
}

export async function render(view) {
  view.innerHTML = `<div class="pos-shell">
    <div class="mesa-tabs" id="pos-tabs" role="tablist" aria-label="Mesas abiertas"></div>
    <div class="pos">
      <section class="pos-left">
        <div class="pos-top">
          <input class="input grow" id="pos-search" placeholder="Buscar producto o código…  (F2)" autocomplete="off">
          <span class="badge" id="pos-turno"></span>
        </div>
        <div class="chips" id="pos-cats"></div>
        <div class="prod-grid" id="pos-grid"></div>
      </section>
      <aside class="cart">
        <div class="cart-h"><h3 class="grow" id="cart-title"></h3>
          <button class="btn sm ghost" id="pos-mesa" title="Cambiar el número o nombre de la mesa">Cambiar mesa</button>
          <button class="btn sm ghost" id="pos-cancel" title="Cancelar la cuenta abierta" style="color:var(--bad)">Cancelar</button>
          <div class="hint" id="cart-sub" style="flex-basis:100%"></div></div>
        <div class="cart-list" id="pos-cart"></div>
        <div class="cart-sum">
          <div class="sum-row"><span>Subtotal</span><span id="pos-sub" class="num"></span></div>
          <div class="sum-row"><button class="btn sm ghost" id="pos-desc" style="padding:2px 6px;margin-left:-6px">Descuento <span class="kbd">F9</span></button><span id="pos-descv" class="num"></span></div>
          <div class="sum-total"><span>Total</span><span id="pos-total" class="num"></span></div>
          <div class="pay-methods" id="pos-metodos"></div>
          <div class="row" style="gap:6px">
            <button class="btn sm grow" id="pos-pre" title="Imprimir la cuenta para que el cliente la revise antes de pagar">Pre-cuenta</button>
            <button class="btn sm grow" id="pos-split" title="Dividir la cuenta o pasar consumos a otra mesa">Dividir / mover</button></div>
          <button class="btn primary xl block" id="pos-cobrar">Cobrar <span class="kbd" style="color:#fff;border-color:#ffffff66;background:transparent">F12</span></button>
        </div>
      </aside>
    </div>
  </div>
  <div id="pos-closed"></div>`;

  await cargar();
  const search = $("#pos-search");
  search.value = busqueda;
  search.addEventListener("input", () => { busqueda = search.value; pintarProductos(); });
  search.addEventListener("keydown", (e) => {
    if (e.key !== "Enter") return;
    const q = search.value.trim().toLowerCase();
    const lista = filtrados();
    const exacto = cat.productos.find((p) => (p.codigo || "").toLowerCase() === q);
    const p = exacto || (lista.length === 1 ? lista[0] : null);
    if (p) { agregar(p); search.value = ""; busqueda = ""; pintarProductos(); }
  });
  $("#pos-mesa").onclick = cambiarMesa;
  $("#pos-cancel").onclick = cancelarCuenta;
  $("#pos-desc").onclick = pedirDescuento;
  $("#pos-pre").onclick = imprimirPrecuenta;
  $("#pos-split").onclick = dividir;
  $("#pos-cobrar").onclick = cobrar;

  const onKey = (e) => {
    if (document.querySelector(".modal-back")) return;
    if (e.key === "F2") { e.preventDefault(); search.focus(); search.select(); }
    if (e.key === "F4") { e.preventDefault(); nuevaMesa(); }
    if (e.key === "F9") { e.preventDefault(); pedirDescuento(); }
    if (e.key === "F12") { e.preventDefault(); cobrar(); }
  };
  document.addEventListener("keydown", onKey);
  // por si otra ventana abrió o cobró mesas mientras esta estaba en segundo plano
  const alVolver = () => refrescarCuentas();
  window.addEventListener("focus", alVolver);
  setTimeout(() => search.focus(), 50);
  return () => { document.removeEventListener("keydown", onKey); window.removeEventListener("focus", alVolver); };
}

async function cargar() {
  try {
    [cat, cuentas] = await Promise.all([get("/pos/catalogo"), get("/cuentas")]);
  } catch (e) { toastErr(e); return; }
  if (!metodo || !cat.metodos.some((m) => m.metodo_pago_id === metodo)) metodo = cat.metodos[0]?.metodo_pago_id;
  if (!cuenta()) activaId = cuentas[0]?.cuenta_id ?? null;
  pintarTurno(); pintarCategorias(); pintarProductos(); pintarMetodos(); pintarTabs(); pintarCarrito();
}

async function refrescarCuentas() {
  try { cuentas = await get("/cuentas"); } catch { return; }
  if (!cuenta()) activaId = cuentas[0]?.cuenta_id ?? null;
  pintarTabs(); pintarCarrito();
}

// Aplica la respuesta del servidor a la lista local (una cuenta cobrada o cancelada sale de las pestañas)
function reemplazar(det) {
  const i = cuentas.findIndex((c) => c.cuenta_id === det.cuenta_id);
  if (det.estado !== "ABIERTA") { if (i >= 0) cuentas.splice(i, 1); }
  else if (i >= 0) cuentas[i] = det;
  else cuentas.push(det);
  if (!cuenta()) activaId = cuentas.at(-1)?.cuenta_id ?? null;
  pintarTabs(); pintarCarrito();
}

async function llamar(fn) {
  try { reemplazar(await enCola(fn)); return true; }
  catch (e) {
    toastErr(e);
    if (e.status === 404 || e.status === 409) await refrescarCuentas();
    return false;
  }
}

function pintarTurno() {
  const b = $("#pos-turno");
  const closed = $("#pos-closed");
  if (cat.turno) {
    b.className = "badge ok";
    b.textContent = `● Caja abierta · Turno #${cat.turno.turno_id}`;
    closed.innerHTML = "";
    return;
  }
  b.className = "badge bad"; b.textContent = "Caja cerrada";
  closed.innerHTML = `<div class="overlay-closed"><form class="card card-b stack" style="width:380px;padding:26px">
      <h2>La caja está cerrada</h2>
      <p class="ink2" style="margin:0">Para empezar a vender, abre un turno con el efectivo inicial (fondo de caja).</p>
      <label class="f">Fondo inicial en efectivo<input class="input lg" type="number" min="0" step="0.5" name="fondo" value="500"></label>
      <button class="btn primary lg block">Abrir caja</button></form></div>`;
  const f = $("form", closed);
  $("input", f).select();
  f.onsubmit = async (e) => {
    e.preventDefault();
    try {
      await post("/turno/abrir", { fondo_inicial: Number($("input", f).value || 0) });
      toast("Turno abierto. ¡Buenas ventas!");
      await cargar();
      $("#pos-search").focus();
    } catch (ex) { toastErr(ex); }
  };
}

// ---------- pestañas: una por mesa ----------
function pintarTabs() {
  const el = $("#pos-tabs");
  if (!el) return;
  el.innerHTML = cuentas.map((c) => {
    const activa = c.cuenta_id === activaId;
    return `<button class="mesa-tab ${activa ? "active" : ""}" role="tab" aria-selected="${activa}" data-id="${c.cuenta_id}" title="Folio ${esc(c.folio)}">
      <span class="mt-n">${esc(mesaTitulo(c.mesa))}</span><span class="mt-t">${c.items.length ? money(c.total) : "sin consumo"}</span></button>`;
  }).join("") + `<button class="mesa-tab new" id="pos-newtab" title="Abrir otra mesa (F4)">+ Nueva mesa <span class="kbd">F4</span></button>`;
  $$(".mesa-tab[data-id]", el).forEach((b) => b.onclick = () => {
    activaId = +b.dataset.id; pintarTabs(); pintarCarrito(); $("#pos-search")?.focus();
  });
  $("#pos-newtab").onclick = () => nuevaMesa();
}

function nuevaMesa() {
  return new Promise((resolve) => {
    let listo = false;
    const m = modal({
      title: "Abrir mesa", size: "w-sm",
      body: `<div class="stack"><label class="f">Número o nombre de la mesa<input class="input lg" maxlength="30" value="${esc(siguienteMesa())}" placeholder="Ej. 5, Barra 2, Llevar" autofocus></label>
        <p class="hint" style="margin:0">Cada mesa lleva su propio ticket y folio. Puedes seguir agregando lo que pidan mientras están en la mesa y cobrar al final.</p></div>`,
      footer: `<button class="btn" data-c>Cancelar</button><button class="btn primary" data-ok>Abrir mesa</button>`,
      onClose: () => { if (!listo) resolve(null); },
    });
    const inp = $("input", m.el);
    inp.select();
    const abrir = async () => {
      const mesa = inp.value.trim();
      if (!mesa) return;
      try {
        const det = await enCola(() => post("/cuentas", { mesa }));
        listo = true; m.close();
        reemplazar(det); activaId = det.cuenta_id; pintarTabs(); pintarCarrito();
        resolve(det);
        setTimeout(() => $("#pos-search")?.focus(), 50);
      } catch (e) { toastErr(e); inp.select(); }
    };
    $("[data-c]", m.el).onclick = () => m.close();
    $("[data-ok]", m.el).onclick = abrir;
    inp.addEventListener("keydown", (e) => { if (e.key === "Enter") abrir(); });
  });
}

async function cambiarMesa() {
  const c = cuenta();
  if (!c) return;
  const nueva = await promptDialog("Número o nombre de la mesa", { title: `Cambiar ${mesaTitulo(c.mesa)}`, value: c.mesa, ok: "Guardar" });
  if (nueva === null || nueva.trim() === "" || nueva.trim() === c.mesa) return;
  await llamar(() => put(`/cuentas/${c.cuenta_id}`, { mesa: nueva.trim() }));
}

async function cancelarCuenta() {
  const c = cuenta();
  if (!c) return;
  let motivo = "";
  if (c.items.length) {
    motivo = await promptDialog("Motivo de la cancelación (no se descuenta inventario porque la cuenta aún no se cobra)", { title: `Cancelar ${mesaTitulo(c.mesa)}`, ok: "Cancelar cuenta" });
    if (!motivo) return;
  } else if (!(await confirmDialog(`¿Cerrar la ${esc(mesaTitulo(c.mesa))} sin consumo?`, { ok: "Cerrar mesa" }))) return;
  if (await llamar(() => post(`/cuentas/${c.cuenta_id}/cancelar`, { motivo }))) toast("Cuenta cancelada");
}

async function imprimirPrecuenta() {
  const c = cuenta();
  if (!c || !c.items.length) return;
  try {
    await enCola(async () => {}); // que ya estén guardados los últimos cambios
    printHTML(await api(`/cuentas/${c.cuenta_id}/precuenta`, { raw: true }));
  } catch (e) { toastErr(e); }
}

// Dividir la cuenta (hacia una cuenta nueva con su propio folio) o pasar consumos a otra mesa abierta
function dividir() {
  const c = cuenta();
  if (!c || !c.items.length) return;
  const otras = cuentas.filter((x) => x.cuenta_id !== c.cuenta_id);
  const usadas = new Set(cuentas.map((x) => x.mesa.toLowerCase()));
  const sugerida = usadas.has(`${c.mesa}-b`.toLowerCase()) ? siguienteMesa() : `${c.mesa}-B`;
  const m = modal({
    title: `Dividir o mover · ${mesaTitulo(c.mesa)}`,
    body: `<div class="stack">
      <p class="hint" style="margin:0">Indica cuántas piezas de cada producto pasan a la otra cuenta.</p>
      <div>${c.items.map((i) => `<div class="row" style="padding:7px 0;border-bottom:1px dashed var(--line)">
        <div class="grow"><b>${esc(i.nombre)}</b><div class="hint">${i.nota ? esc(i.nota) + " · " : ""}${i.cantidad} en la cuenta · ${money(i.precio)} c/u</div></div>
        <input class="input" type="number" min="0" max="${i.cantidad}" step="1" value="0" data-i="${i.item_id}" aria-label="Piezas de ${esc(i.nombre)} a mover" style="width:78px;text-align:right">
        <button class="btn sm" data-all="${i.item_id}">Todo</button></div>`).join("")}</div>
      <label class="f">Destino<select class="input" id="mv-dest">
        <option value="">Cuenta nueva (dividir la cuenta)</option>
        ${otras.map((o) => `<option value="${o.cuenta_id}">Pasar a ${esc(mesaTitulo(o.mesa))} · ${esc(o.folio)}</option>`).join("")}</select></label>
      <label class="f" id="mv-nueva">Nombre de la cuenta nueva<input class="input" id="mv-mesa" maxlength="30" value="${esc(sugerida)}"></label>
      <div class="row"><span class="grow ink2">Piezas a mover</span><b id="mv-n">0</b></div>
      <p class="hint" style="margin:0">La cuenta nueva tendrá su propio folio y se cobra por separado. El descuento se queda en la cuenta original.</p></div>`,
    footer: `<button class="btn" data-c>Cancelar</button><button class="btn primary" data-ok disabled>Mover</button>`,
  });
  const inputs = $$("[data-i]", m.el);
  const ok = $("[data-ok]", m.el);
  const dest = $("#mv-dest", m.el);
  const elegidos = () => inputs.map((i) => ({ item_id: +i.dataset.i, cantidad: Math.min(Math.max(Number(i.value || 0), 0), +i.max) })).filter((x) => x.cantidad > 0);
  const actualizar = () => {
    const n = elegidos().reduce((s, x) => s + x.cantidad, 0);
    $("#mv-n", m.el).textContent = n;
    $("#mv-nueva", m.el).classList.toggle("hidden", !!dest.value);
    ok.disabled = !n;
  };
  inputs.forEach((i) => i.addEventListener("input", actualizar));
  $$("[data-all]", m.el).forEach((b) => b.onclick = () => { const i = $(`[data-i="${b.dataset.all}"]`, m.el); i.value = i.max; actualizar(); });
  dest.onchange = actualizar;
  $("[data-c]", m.el).onclick = () => m.close();
  ok.onclick = async () => {
    ok.disabled = true;
    const body = { items: elegidos(), ...(dest.value ? { destino_cuenta_id: +dest.value } : { destino_mesa: $("#mv-mesa", m.el).value.trim() }) };
    try {
      const r = await enCola(() => post(`/cuentas/${c.cuenta_id}/mover`, body));
      m.close();
      reemplazar(r.origen); reemplazar(r.destino);
      activaId = r.destino.cuenta_id; pintarTabs(); pintarCarrito();
      toast(`Consumos pasados a ${mesaTitulo(r.destino.mesa)} (${r.destino.folio})`);
    } catch (e) {
      ok.disabled = false;
      toastErr(e);
      if (e.status === 404) { m.close(); refrescarCuentas(); }
    }
  };
}

// ---------- menú ----------
function pintarCategorias() {
  const el = $("#pos-cats");
  el.innerHTML = `<button class="chip ${filtroCat === "" ? "active" : ""}" data-c="">Todo</button>` +
    cat.categorias.map((c) => `<button class="chip ${String(filtroCat) === String(c.categoria_id) ? "active" : ""}" data-c="${c.categoria_id}">
      <span class="dot" style="background:${esc(c.color)}"></span>${esc(c.nombre)}</button>`).join("");
  $$(".chip", el).forEach((b) => b.onclick = () => { filtroCat = b.dataset.c; pintarCategorias(); pintarProductos(); });
}

function filtrados() {
  const q = busqueda.trim().toLowerCase();
  return cat.productos.filter((p) =>
    (!filtroCat || String(p.categoria_id) === String(filtroCat)) &&
    (!q || p.nombre.toLowerCase().includes(q) || (p.codigo || "").toLowerCase().includes(q)));
}

function badgeDisp(p) {
  if (p.disponibles === null || p.disponibles === undefined) return "";
  if (p.disponibles <= 0) return `<span class="badge bad av">Sin insumos</span>`;
  if (p.disponibles <= 5) return `<span class="badge warn av">Quedan ${p.disponibles}</span>`;
  return "";
}

function pintarProductos() {
  const grid = $("#pos-grid");
  const lista = filtrados();
  if (!lista.length) { grid.innerHTML = `<div class="empty" style="grid-column:1/-1">No hay productos${cat.productos.length ? " con ese filtro" : ". Da de alta tu menú en «Menú y recetas»"}.</div>`; return; }
  grid.innerHTML = lista.map((p) => `<button class="prod ${p.disponibles === 0 ? "agotado" : ""}" data-id="${p.producto_id}" style="--c:${esc(p.color || "#e4572e")}">
      <span class="flash"></span>${badgeDisp(p)}
      <span class="n">${esc(p.nombre)}</span>
      <span class="muted" style="font-size:12px">${esc(p.codigo || "")}</span>
      <span class="p">${money(p.precio_venta)}</span></button>`).join("");
  $$(".prod", grid).forEach((b) => b.onclick = () => {
    agregar(cat.productos.find((p) => p.producto_id === +b.dataset.id));
    b.classList.remove("hit"); void b.offsetWidth; b.classList.add("hit");
  });
}

// Piezas del producto en todas las cuentas abiertas (para respetar "no permitir stock negativo")
function enCuentas(productoId) {
  return cuentas.flatMap((c) => c.items).filter((i) => i.producto_id === productoId).reduce((s, i) => s + i.cantidad, 0);
}

function hayInsumos(productoId, nombre) {
  const p = cat.productos.find((x) => x.producto_id === productoId);
  if (!cat.permitir_stock_negativo && p && p.disponibles !== null && enCuentas(productoId) + 1 > p.disponibles) {
    toast(`No hay insumos suficientes para más «${nombre || p.nombre}»`, "warn");
    return false;
  }
  return true;
}

async function asegurarCuenta() { return cuenta() || (await nuevaMesa()); }

async function agregar(p) {
  const c = await asegurarCuenta();
  if (!c || !hayInsumos(p.producto_id, p.nombre)) return;
  llamar(() => post(`/cuentas/${c.cuenta_id}/items`, { producto_id: p.producto_id, cantidad: 1 }));
}

// ---------- ticket de la mesa activa ----------
function pintarCarrito() {
  const list = $("#pos-cart");
  if (!list) return;
  const c = cuenta();
  $("#cart-title").textContent = c ? mesaTitulo(c.mesa) : "Sin mesa abierta";
  $("#cart-sub").textContent = c ? `Folio ${c.folio} · abierta ${c.abierta_en.slice(11, 16)} · ${c.usuario}` : "";
  $("#pos-mesa").classList.toggle("hidden", !c);
  $("#pos-cancel").classList.toggle("hidden", !c);
  if (!c) {
    list.innerHTML = `<div class="empty">No hay mesas abiertas.<br><br><button class="btn primary" id="pos-empty-new">Abrir mesa <span class="kbd" style="color:#fff;border-color:#ffffff66;background:transparent">F4</span></button></div>`;
    $("#pos-empty-new").onclick = () => nuevaMesa();
  } else if (!c.items.length) {
    list.innerHTML = `<div class="empty">Toca un producto para agregarlo a esta mesa.<br><span class="hint">F2 buscar · F4 nueva mesa · F9 descuento · F12 cobrar</span></div>`;
  } else {
    list.innerHTML = c.items.map((i, idx) => `<div class="cart-item">
        <div><div class="nm">${esc(i.nombre)} ${i.activo ? "" : `<span class="badge bad">No disponible</span>`}</div>${i.nota ? `<div class="nt">${esc(i.nota)}</div>` : ""}
          <div class="muted" style="font-size:12px">${money(i.precio)} c/u</div></div>
        <div class="pr">${money(i.precio * i.cantidad)}</div>
        <div class="row" style="gap:6px">
          <span class="qty"><button data-a="menos" data-i="${idx}">−</button><span>${i.cantidad}</span><button data-a="mas" data-i="${idx}">+</button></span>
          <button class="btn sm ghost" data-a="nota" data-i="${idx}" title="Agregar nota (sin cebolla, etc.)">Nota</button>
        </div>
        <div style="text-align:right"><button class="btn sm ghost" data-a="del" data-i="${idx}" title="Quitar" style="color:var(--bad)">Quitar</button></div>
      </div>`).join("");
    $$("button[data-a]", list).forEach((b) => b.onclick = () => accionItem(b.dataset.a, +b.dataset.i));
  }
  $("#pos-sub").textContent = money(c?.subtotal);
  $("#pos-descv").textContent = c?.descuento ? "−" + money(c.descuento) + (c.descuento_tipo === "%" ? ` (${c.descuento_valor}%)` : "") : money(0);
  $("#pos-total").textContent = money(c?.total);
  $("#pos-cobrar").disabled = !c || !c.items.length;
  $("#pos-desc").disabled = !c || !c.items.length;
  $("#pos-pre").disabled = !c || !c.items.length;
  $("#pos-split").disabled = !c || !c.items.length;
}

async function accionItem(a, idx) {
  const c = cuenta();
  const it = c?.items[idx];
  if (!it) return;
  const base = `/cuentas/${c.cuenta_id}/items/${it.item_id}`;
  if (a === "mas") { if (hayInsumos(it.producto_id, it.nombre)) llamar(() => put(base, { cantidad: it.cantidad + 1 })); }
  if (a === "menos") llamar(() => put(base, { cantidad: it.cantidad - 1 }));
  if (a === "del") llamar(() => del(base));
  if (a === "nota") {
    const n = await promptDialog("Nota para cocina / ticket", { title: it.nombre, value: it.nota || "", placeholder: "Ej. sin cebolla" });
    if (n === null) return;
    llamar(() => put(base, { nota: n, separar: true }));
  }
}

function pintarMetodos() {
  const el = $("#pos-metodos");
  el.style.gridTemplateColumns = `repeat(${Math.min(cat.metodos.length, 3)}, 1fr)`;
  el.innerHTML = cat.metodos.map((m) => `<button class="${m.metodo_pago_id === metodo ? "active" : ""}" data-m="${m.metodo_pago_id}">${esc(m.nombre)}</button>`).join("");
  $$("button", el).forEach((b) => b.onclick = () => { metodo = +b.dataset.m; pintarMetodos(); });
}

function pedirDescuento() {
  const c = cuenta();
  if (!c || !c.items.length) return;
  const m = modal({
    title: "Descuento", size: "w-sm",
    body: `<div class="stack"><div class="seg"><button data-t="$" class="${c.descuento_tipo === "$" ? "active" : ""}">Monto $</button><button data-t="%" class="${c.descuento_tipo === "%" ? "active" : ""}">Porcentaje %</button></div>
      <input class="input lg" type="number" min="0" step="0.5" value="${c.descuento_valor || ""}" autofocus>
      <div class="row wrap">${[5, 10, 15, 20].map((v) => `<button class="btn sm" data-q="${v}">${v}</button>`).join("")}</div></div>`,
    footer: `<button class="btn" data-quitar>Quitar descuento</button><button class="btn primary" data-ok>Aplicar</button>`,
  });
  let tipo = c.descuento_tipo;
  const inp = $("input", m.el);
  $$("[data-t]", m.el).forEach((b) => b.onclick = () => { tipo = b.dataset.t; $$("[data-t]", m.el).forEach((x) => x.classList.toggle("active", x === b)); inp.focus(); });
  $$("[data-q]", m.el).forEach((b) => b.onclick = () => { inp.value = b.dataset.q; inp.focus(); });
  const guardar = (t, v) => { m.close(); llamar(() => put(`/cuentas/${c.cuenta_id}`, { descuento_tipo: t, descuento_valor: v })); };
  const apply = () => {
    let v = Math.max(0, Number(inp.value || 0));
    if (tipo === "%") v = Math.min(v, 100);
    guardar(tipo, v);
  };
  $("[data-ok]", m.el).onclick = apply;
  inp.addEventListener("keydown", (e) => e.key === "Enter" && apply());
  $("[data-quitar]", m.el).onclick = () => guardar("$", 0);
}

function cobrar() {
  const c = cuenta();
  if (!c || !c.items.length) return;
  if (!cat.turno) return toast("Abre la caja antes de vender", "warn");
  const total = c.total;
  const forma = cat.metodos.find((m) => m.metodo_pago_id === metodo);
  const efectivo = !!forma?.es_efectivo;
  const billetes = [...new Set([total, Math.ceil(total / 50) * 50, Math.ceil(total / 100) * 100, 200, 500, 1000]
    .filter((b) => b >= total))].slice(0, 4);
  const m = modal({
    title: `Cobrar ${mesaTitulo(c.mesa)} · ${forma?.nombre || ""}`, size: "w-sm",
    body: `<div class="stack">
      <div class="row"><span class="grow ink2">Total a cobrar<br><span class="hint">Folio ${esc(c.folio)}</span></span><span class="big-num">${money(total)}</span></div>
      ${efectivo ? `<label class="f">Efectivo recibido<input class="input lg" type="number" min="0" step="0.5" id="rec" value="${total}" autofocus></label>
      <div class="cash-quick">${billetes.map((b) => `<button class="btn" data-b="${b}">${b === total ? "Exacto" : money(b).replace(".00", "")}</button>`).join("")}</div>
      <div class="change-box" id="chg"><span>Cambio</span><b>${money(0)}</b></div>` :
      `<p class="ink2" style="margin:0">Confirma que el pago con <b>${esc(forma?.nombre || "")}</b> fue aprobado.</p>`}
      <label class="f">Cliente / referencia (opcional)<input class="input" id="cli" placeholder="Nombre, # de orden…"></label>
    </div>`,
    footer: `<button class="btn" data-c>Cancelar</button><button class="btn primary lg" data-ok>Confirmar venta</button>`,
  });
  const rec = $("#rec", m.el);
  const ok = $("[data-ok]", m.el);
  const upd = () => {
    if (!rec) return;
    const dif = Number(rec.value || 0) - total;
    const box = $("#chg", m.el);
    box.classList.toggle("neg", dif < 0);
    box.innerHTML = dif < 0 ? `<span>Faltan</span><b>${money(-dif)}</b>` : `<span>Cambio</span><b>${money(dif)}</b>`;
    ok.disabled = dif < -0.001;
  };
  if (rec) { rec.addEventListener("input", upd); rec.select(); upd(); }
  $$("[data-b]", m.el).forEach((b) => b.onclick = () => { rec.value = b.dataset.b; upd(); ok.focus(); });
  $("[data-c]", m.el).onclick = () => m.close();
  const enviar = async () => {
    if (ok.disabled) return;
    ok.disabled = true;
    try {
      const venta = await enCola(() => post(`/cuentas/${c.cuenta_id}/cobrar`, {
        metodo_pago_id: metodo, pago_recibido: rec ? Number(rec.value || 0) : null, cliente: $("#cli", m.el).value.trim() || null,
      }));
      m.close();
      reemplazar({ ...c, estado: "COBRADA" });
      exito(venta);
      cargar();
    } catch (e) {
      ok.disabled = false;
      if (e.datos && Array.isArray(e.datos)) {
        modal({ title: "Inventario insuficiente", body: `<p>${esc(e.message)}:</p><ul>${e.datos.map((f) =>
          `<li><b>${esc(f.insumo)}</b>: se requieren ${f.requerido} ${esc(f.unidad)}, hay ${f.disponible}</li>`).join("")}</ul>
          <p class="hint">Registra una entrada de material o pide a un administrador un ajuste de inventario.</p>`, footer: null });
      } else {
        toastErr(e);
        if (e.status === 404 || e.status === 409) { m.close(); refrescarCuentas(); }
      }
    }
  };
  ok.onclick = enviar;
  m.el.addEventListener("keydown", (e) => { if (e.key === "Enter" && e.target.id !== "cli") { e.preventDefault(); enviar(); } });
}

function exito(v) {
  const m = modal({
    title: "Venta registrada", size: "w-sm",
    body: `<div class="stack" style="text-align:center">
      <div class="muted">${v.mesa ? esc(mesaTitulo(v.mesa)) + " · " : ""}Folio <b>${esc(v.folio)}</b> · ${esc(v.metodo_pago)}</div>
      <div class="big-num">${money(v.total)}</div>
      ${v.es_efectivo ? `<div class="change-box"><span>Cambio a entregar</span><b>${money(v.cambio)}</b></div>` : ""}
    </div>`,
    footer: `<button class="btn" data-p>Imprimir ticket</button><button class="btn primary" data-n autofocus>Listo (Enter)</button>`,
  });
  const imprimir = async () => { try { printHTML(await api(`/ventas/${v.venta_id}/ticket`, { raw: true })); } catch (e) { toastErr(e); } };
  $("[data-p]", m.el).onclick = imprimir;
  $("[data-n]", m.el).onclick = () => { m.close(); $("#pos-search")?.focus(); };
  setTimeout(() => $("[data-n]", m.el).focus(), 40);
  if (cat.imprimir_auto) imprimir();
}
