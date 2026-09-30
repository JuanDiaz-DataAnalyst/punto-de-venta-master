import { api, get, post } from "../api.js";
import { $, $$, esc, modal, money, printHTML, promptDialog, toast, toastErr } from "../ui.js";

// El carrito vive a nivel de módulo: sobrevive si el cajero cambia de pantalla
const cart = { items: [], descuento: { tipo: "$", valor: 0 }, metodo: null, cliente: "" };
let cat = null;
let filtroCat = "";
let busqueda = "";

export async function render(view) {
  view.innerHTML = `<div class="pos">
    <section class="pos-left">
      <div class="pos-top">
        <input class="input grow" id="pos-search" placeholder="Buscar producto o código…  (F2)" autocomplete="off">
        <span class="badge" id="pos-turno"></span>
      </div>
      <div class="chips" id="pos-cats"></div>
      <div class="prod-grid" id="pos-grid"></div>
    </section>
    <aside class="cart">
      <div class="cart-h"><h3 class="grow">Ticket actual</h3>
        <button class="btn sm ghost" id="pos-clear" title="Vaciar ticket">Vaciar</button></div>
      <div class="cart-list" id="pos-cart"></div>
      <div class="cart-sum">
        <div class="sum-row"><span>Subtotal</span><span id="pos-sub" class="num"></span></div>
        <div class="sum-row"><button class="btn sm ghost" id="pos-desc" style="padding:2px 6px;margin-left:-6px">Descuento <span class="kbd">F9</span></button><span id="pos-descv" class="num"></span></div>
        <div class="sum-total"><span>Total</span><span id="pos-total" class="num"></span></div>
        <div class="pay-methods" id="pos-metodos"></div>
        <button class="btn primary xl block" id="pos-cobrar">Cobrar <span class="kbd" style="color:#fff;border-color:#ffffff66;background:transparent">F12</span></button>
      </div>
    </aside>
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
  $("#pos-clear").onclick = () => { if (cart.items.length) { cart.items = []; cart.descuento.valor = 0; pintarCarrito(); } };
  $("#pos-desc").onclick = pedirDescuento;
  $("#pos-cobrar").onclick = cobrar;

  const onKey = (e) => {
    if (document.querySelector(".modal-back")) return;
    if (e.key === "F2") { e.preventDefault(); search.focus(); search.select(); }
    if (e.key === "F9") { e.preventDefault(); pedirDescuento(); }
    if (e.key === "F12") { e.preventDefault(); cobrar(); }
  };
  document.addEventListener("keydown", onKey);
  setTimeout(() => search.focus(), 50);
  return () => document.removeEventListener("keydown", onKey);
}

async function cargar() {
  try { cat = await get("/pos/catalogo"); } catch (e) { toastErr(e); return; }
  if (!cart.metodo || !cat.metodos.some((m) => m.metodo_pago_id === cart.metodo)) cart.metodo = cat.metodos[0]?.metodo_pago_id;
  // refrescar precios del carrito por si cambiaron
  cart.items = cart.items.filter((it) => {
    const p = cat.productos.find((x) => x.producto_id === it.producto_id);
    if (p) { it.precio = p.precio_venta; it.nombre = p.nombre; }
    return !!p;
  });
  pintarTurno(); pintarCategorias(); pintarProductos(); pintarMetodos(); pintarCarrito();
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

function agregar(p) {
  const enCarrito = cart.items.filter((i) => i.producto_id === p.producto_id).reduce((s, i) => s + i.cantidad, 0);
  if (!cat.permitir_stock_negativo && p.disponibles !== null && enCarrito + 1 > p.disponibles) {
    toast(`No hay insumos suficientes para más «${p.nombre}»`, "warn"); return;
  }
  const it = cart.items.find((i) => i.producto_id === p.producto_id && !i.nota);
  if (it) it.cantidad += 1;
  else cart.items.push({ producto_id: p.producto_id, nombre: p.nombre, precio: p.precio_venta, cantidad: 1, nota: "" });
  pintarCarrito();
}

function totales() {
  const sub = cart.items.reduce((s, i) => s + i.precio * i.cantidad, 0);
  let d = cart.descuento.tipo === "%" ? sub * (cart.descuento.valor / 100) : cart.descuento.valor;
  d = Math.min(Math.max(0, Math.round(d * 100) / 100), sub);
  return { sub, desc: d, total: Math.round((sub - d) * 100) / 100 };
}

function pintarCarrito() {
  const list = $("#pos-cart");
  if (!list) return;
  if (!cart.items.length) {
    list.innerHTML = `<div class="empty">Toca un producto para agregarlo.<br><span class="hint">F2 buscar · F9 descuento · F12 cobrar</span></div>`;
  } else {
    list.innerHTML = cart.items.map((i, idx) => `<div class="cart-item">
        <div><div class="nm">${esc(i.nombre)}</div>${i.nota ? `<div class="nt">${esc(i.nota)}</div>` : ""}
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
  const t = totales();
  $("#pos-sub").textContent = money(t.sub);
  $("#pos-descv").textContent = t.desc ? "−" + money(t.desc) + (cart.descuento.tipo === "%" ? ` (${cart.descuento.valor}%)` : "") : money(0);
  $("#pos-total").textContent = money(t.total);
  $("#pos-cobrar").disabled = !cart.items.length;
}

async function accionItem(a, idx) {
  const it = cart.items[idx];
  if (a === "mas") {
    const p = cat.productos.find((x) => x.producto_id === it.producto_id);
    const enCarrito = cart.items.filter((i) => i.producto_id === it.producto_id).reduce((s, i) => s + i.cantidad, 0);
    if (!cat.permitir_stock_negativo && p.disponibles !== null && enCarrito + 1 > p.disponibles) return toast("No hay insumos suficientes", "warn");
    it.cantidad += 1;
  }
  if (a === "menos") { it.cantidad -= 1; if (it.cantidad <= 0) cart.items.splice(idx, 1); }
  if (a === "del") cart.items.splice(idx, 1);
  if (a === "nota") {
    const n = await promptDialog("Nota para cocina / ticket", { title: it.nombre, value: it.nota, placeholder: "Ej. sin cebolla" });
    if (n === null) return;
    if (it.cantidad > 1 && n) { it.cantidad -= 1; cart.items.splice(idx + 1, 0, { ...it, cantidad: 1, nota: n }); }
    else it.nota = n;
  }
  pintarCarrito();
}

function pintarMetodos() {
  const el = $("#pos-metodos");
  el.style.gridTemplateColumns = `repeat(${Math.min(cat.metodos.length, 3)}, 1fr)`;
  el.innerHTML = cat.metodos.map((m) => `<button class="${m.metodo_pago_id === cart.metodo ? "active" : ""}" data-m="${m.metodo_pago_id}">${esc(m.nombre)}</button>`).join("");
  $$("button", el).forEach((b) => b.onclick = () => { cart.metodo = +b.dataset.m; pintarMetodos(); });
}

function pedirDescuento() {
  if (!cart.items.length) return;
  const m = modal({
    title: "Descuento", size: "w-sm",
    body: `<div class="stack"><div class="seg"><button data-t="$" class="${cart.descuento.tipo === "$" ? "active" : ""}">Monto $</button><button data-t="%" class="${cart.descuento.tipo === "%" ? "active" : ""}">Porcentaje %</button></div>
      <input class="input lg" type="number" min="0" step="0.5" value="${cart.descuento.valor || ""}" autofocus>
      <div class="row wrap">${[5, 10, 15, 20].map((v) => `<button class="btn sm" data-q="${v}">${v}</button>`).join("")}</div></div>`,
    footer: `<button class="btn" data-quitar>Quitar descuento</button><button class="btn primary" data-ok>Aplicar</button>`,
  });
  let tipo = cart.descuento.tipo;
  const inp = $("input", m.el);
  $$("[data-t]", m.el).forEach((b) => b.onclick = () => { tipo = b.dataset.t; $$("[data-t]", m.el).forEach((x) => x.classList.toggle("active", x === b)); inp.focus(); });
  $$("[data-q]", m.el).forEach((b) => b.onclick = () => { inp.value = b.dataset.q; inp.focus(); });
  const apply = () => {
    let v = Math.max(0, Number(inp.value || 0));
    if (tipo === "%") v = Math.min(v, 100);
    cart.descuento = { tipo, valor: v }; m.close(); pintarCarrito();
  };
  $("[data-ok]", m.el).onclick = apply;
  inp.addEventListener("keydown", (e) => e.key === "Enter" && apply());
  $("[data-quitar]", m.el).onclick = () => { cart.descuento = { tipo: "$", valor: 0 }; m.close(); pintarCarrito(); };
}

function cobrar() {
  if (!cart.items.length) return;
  if (!cat.turno) return toast("Abre la caja antes de vender", "warn");
  const t = totales();
  const metodo = cat.metodos.find((m) => m.metodo_pago_id === cart.metodo);
  const efectivo = !!metodo?.es_efectivo;
  const billetes = [...new Set([t.total, Math.ceil(t.total / 50) * 50, Math.ceil(t.total / 100) * 100, 200, 500, 1000]
    .filter((b) => b >= t.total))].slice(0, 4);
  const m = modal({
    title: `Cobrar · ${metodo?.nombre || ""}`, size: "w-sm",
    body: `<div class="stack">
      <div class="row"><span class="grow ink2">Total a cobrar</span><span class="big-num">${money(t.total)}</span></div>
      ${efectivo ? `<label class="f">Efectivo recibido<input class="input lg" type="number" min="0" step="0.5" id="rec" value="${t.total}" autofocus></label>
      <div class="cash-quick">${billetes.map((b) => `<button class="btn" data-b="${b}">${b === t.total ? "Exacto" : money(b).replace(".00", "")}</button>`).join("")}</div>
      <div class="change-box" id="chg"><span>Cambio</span><b>${money(0)}</b></div>` :
      `<p class="ink2" style="margin:0">Confirma que el pago con <b>${esc(metodo?.nombre || "")}</b> fue aprobado.</p>`}
      <label class="f">Cliente / referencia (opcional)<input class="input" id="cli" value="${esc(cart.cliente)}" placeholder="Nombre, mesa, # de orden…"></label>
    </div>`,
    footer: `<button class="btn" data-c>Cancelar</button><button class="btn primary lg" data-ok>Confirmar venta</button>`,
  });
  const rec = $("#rec", m.el);
  const ok = $("[data-ok]", m.el);
  const upd = () => {
    if (!rec) return;
    const c = Number(rec.value || 0) - t.total;
    const box = $("#chg", m.el);
    box.classList.toggle("neg", c < 0);
    box.innerHTML = c < 0 ? `<span>Faltan</span><b>${money(-c)}</b>` : `<span>Cambio</span><b>${money(c)}</b>`;
    ok.disabled = c < -0.001;
  };
  if (rec) { rec.addEventListener("input", upd); rec.select(); upd(); }
  $$("[data-b]", m.el).forEach((b) => b.onclick = () => { rec.value = b.dataset.b; upd(); ok.focus(); });
  $("[data-c]", m.el).onclick = () => m.close();
  const enviar = async () => {
    if (ok.disabled) return;
    ok.disabled = true;
    try {
      const venta = await post("/ventas", {
        items: cart.items.map((i) => ({ producto_id: i.producto_id, cantidad: i.cantidad, nota: i.nota || null })),
        metodo_pago_id: cart.metodo, descuento: t.desc,
        pago_recibido: rec ? Number(rec.value || 0) : null, cliente: $("#cli", m.el).value.trim() || null,
      });
      m.close();
      cart.items = []; cart.descuento = { tipo: "$", valor: 0 }; cart.cliente = "";
      exito(venta);
      cargar();
    } catch (e) {
      ok.disabled = false;
      if (e.datos && Array.isArray(e.datos)) {
        modal({ title: "Inventario insuficiente", body: `<p>${esc(e.message)}:</p><ul>${e.datos.map((f) =>
          `<li><b>${esc(f.insumo)}</b>: se requieren ${f.requerido} ${esc(f.unidad)}, hay ${f.disponible}</li>`).join("")}</ul>
          <p class="hint">Registra una entrada de material o pide a un administrador un ajuste de inventario.</p>`, footer: null });
      } else toastErr(e);
    }
  };
  ok.onclick = enviar;
  m.el.addEventListener("keydown", (e) => { if (e.key === "Enter" && e.target.id !== "cli") { e.preventDefault(); enviar(); } });
}

function exito(v) {
  const m = modal({
    title: "Venta registrada", size: "w-sm",
    body: `<div class="stack" style="text-align:center">
      <div class="muted">Folio <b>${esc(v.folio)}</b> · ${esc(v.metodo_pago)}</div>
      <div class="big-num">${money(v.total)}</div>
      ${v.es_efectivo ? `<div class="change-box"><span>Cambio a entregar</span><b>${money(v.cambio)}</b></div>` : ""}
    </div>`,
    footer: `<button class="btn" data-p>Imprimir ticket</button><button class="btn primary" data-n autofocus>Nueva venta (Enter)</button>`,
  });
  const imprimir = async () => { try { printHTML(await api(`/ventas/${v.venta_id}/ticket`, { raw: true })); } catch (e) { toastErr(e); } };
  $("[data-p]", m.el).onclick = imprimir;
  $("[data-n]", m.el).onclick = () => { m.close(); $("#pos-search")?.focus(); };
  setTimeout(() => $("[data-n]", m.el).focus(), 40);
  if (cat.imprimir_auto) imprimir();
}
