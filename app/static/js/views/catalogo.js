import { get, post, put } from "../api.js";
import { $, $$, badgeEstado, debounce, esc, formData, modal, money, num, options, pct, table, toast, toastErr } from "../ui.js";

let tab = "productos";
let data = { productos: [], insumos: [], categorias: [], proveedores: [], metodos: [], unidades: [] };

const TABS = [["productos", "Productos y recetas"], ["insumos", "Insumos"], ["categorias", "Categorías"],
  ["proveedores", "Proveedores"], ["metodos", "Métodos de pago"]];

export async function render(view) {
  view.innerHTML = `<div class="page"><div class="page-head"><div class="grow"><h1>Menú y recetas</h1>
    <div class="sub">Productos que vendes, su receta (insumos que consume cada uno) y catálogos relacionados</div></div>
    <button class="btn primary" id="cat-new">+ Nuevo</button></div>
    <div class="tabs" id="cat-tabs"></div><div id="cat-body"></div></div>`;
  $("#cat-tabs").innerHTML = TABS.map(([k, l]) => `<button data-t="${k}" class="${k === tab ? "active" : ""}">${l}</button>`).join("");
  $$("#cat-tabs button").forEach((b) => b.onclick = () => { tab = b.dataset.t; $$("#cat-tabs button").forEach((x) => x.classList.toggle("active", x === b)); pintar(); });
  $("#cat-new").onclick = () => editar(null);
  await cargar();
  pintar();
}

async function cargar() {
  try {
    const [productos, insumos, categorias, proveedores, metodos, unidades] = await Promise.all([
      get("/productos"), get("/insumos", { incluir_inactivos: true }), get("/categorias"), get("/proveedores"), get("/metodos-pago"), get("/unidades")]);
    data = { productos, insumos, categorias, proveedores, metodos, unidades };
  } catch (e) { toastErr(e); }
}

function editar(row) {
  ({ productos: editarProducto, insumos: editarInsumo, categorias: editarCategoria, proveedores: editarProveedor, metodos: editarMetodo })[tab](row);
}

const activoBadge = (v) => v ? `<span class="badge ok">Activo</span>` : `<span class="badge">Inactivo</span>`;

function pintar() {
  const body = $("#cat-body");
  body.innerHTML = "";
  const nuevo = { productos: "+ Nuevo producto", insumos: "+ Nuevo insumo", categorias: "+ Nueva categoría", proveedores: "+ Nuevo proveedor", metodos: "+ Nuevo método" };
  $("#cat-new").textContent = nuevo[tab];

  if (tab === "productos") {
    body.innerHTML = `<div class="row wrap" style="margin-bottom:12px"><input class="input" id="p-q" placeholder="Buscar producto…" style="max-width:280px">
      <select class="input" id="p-cat" style="max-width:220px">${options(data.categorias, "categoria_id", "nombre", "", "Todas las categorías")}</select>
      <span class="hint">El costo teórico se calcula con la receta y el costo promedio actual de cada insumo.</span></div><div id="p-t"></div>`;
    const pinta = () => {
      const q = $("#p-q").value.toLowerCase(), c = $("#p-cat").value;
      const rows = data.productos.filter((p) => (!q || p.nombre.toLowerCase().includes(q) || (p.codigo || "").toLowerCase().includes(q)) && (!c || String(p.categoria_id) === c));
      const el = $("#p-t"); el.innerHTML = "";
      el.appendChild(table([
        { t: "Código", k: "codigo" }, { t: "Producto", k: "nombre" },
        { t: "Categoría", k: (p) => p.categoria ? `<span class="row" style="gap:6px"><span class="dot" style="background:${esc(p.categoria_color)}"></span>${esc(p.categoria)}</span>` : "" },
        { t: "Precio", k: "precio_venta", cls: "num", f: money }, { t: "Costo receta", k: "costo_teorico", cls: "num", f: money },
        { t: "Margen", k: "margen_teorico", cls: "num", f: money },
        { t: "Margen %", k: (p) => { const v = p.margen_teorico_pct; return `<span class="${v < 0.5 ? "warn-t" : ""}">${pct(v)}</span>`; }, cls: "num" },
        { t: "Food cost", k: (p) => p.precio_venta ? pct(p.costo_teorico / p.precio_venta) : "", cls: "num" },
        { t: "Insumos", k: (p) => p.num_insumos ? String(p.num_insumos) : `<span class="badge warn">Sin receta</span>`, cls: "num" },
        { t: "Estado", k: "activo", f: activoBadge },
      ], rows, { onRow: editarProducto, rowClass: (p) => p.activo ? "" : "off", empty: "Aún no hay productos" }));
    };
    $("#p-q").oninput = debounce(pinta, 150); $("#p-cat").onchange = pinta; pinta();
  }
  if (tab === "insumos") {
    body.appendChild(table([
      { t: "Código", k: "codigo" }, { t: "Insumo", k: "nombre" }, { t: "Unidad", k: "unidad" },
      { t: "Existencia", k: "stock_actual", cls: "num", f: (v) => num(v) }, { t: "Mínimo", k: "stock_minimo", cls: "num", f: (v) => num(v) },
      { t: "Costo prom.", k: "costo_promedio", cls: "num", f: money }, { t: "Proveedor", k: "proveedor" },
      { t: "En recetas", k: "usado_en", cls: "num" }, { t: "Estado", k: (i) => i.activo ? badgeEstado(i.estado) : activoBadge(0) },
    ], data.insumos, { onRow: editarInsumo, rowClass: (i) => i.activo ? "" : "off" }));
  }
  if (tab === "categorias") {
    body.appendChild(table([
      { t: "Orden", k: "orden", cls: "num" }, { t: "Color", k: (c) => `<span class="dot" style="background:${esc(c.color)};width:18px;height:18px"></span>` },
      { t: "Categoría", k: "nombre" }, { t: "Productos activos", k: "productos", cls: "num" }, { t: "Estado", k: "activo", f: activoBadge },
    ], data.categorias, { onRow: editarCategoria }));
  }
  if (tab === "proveedores") {
    body.appendChild(table([
      { t: "Proveedor", k: "nombre" }, { t: "Contacto", k: "contacto" }, { t: "Teléfono", k: "telefono" }, { t: "Email", k: "email" },
      { t: "Insumos", k: "insumos", cls: "num" }, { t: "Última compra", k: "ultima_compra", f: (v) => esc((v || "").slice(0, 10)) },
      { t: "Estado", k: "activo", f: activoBadge },
    ], data.proveedores, { onRow: editarProveedor }));
  }
  if (tab === "metodos") {
    body.appendChild(table([
      { t: "Método", k: "nombre" }, { t: "¿Es efectivo?", k: (m) => m.es_efectivo ? "Sí (calcula cambio y entra al corte)" : "No" },
      { t: "Estado", k: "activo", f: activoBadge },
    ], data.metodos, { onRow: editarMetodo }));
  }
}

async function guardar(m, promesa, msg) {
  try { await promesa; m.close(); toast(msg); await cargar(); pintar(); } catch (e) { toastErr(e); }
}

// ---------------- Producto + receta ----------------
function editarProducto(p) {
  const nuevo = !p;
  p = p || { nombre: "", codigo: "", categoria_id: data.categorias[0]?.categoria_id, precio_venta: 0, activo: 1, receta: [] };
  const receta = p.receta.map((r) => ({ insumo_id: r.insumo_id, cantidad: r.cantidad }));
  const insAct = data.insumos.filter((i) => i.activo);
  const m = modal({
    title: nuevo ? "Nuevo producto" : `Editar: ${p.nombre}`, size: "w-xl",
    body: `<div class="grid2" style="grid-template-columns:1fr 1.35fr;align-items:start;gap:22px">
      <div class="stack">
        <label class="f">Nombre<input class="input" name="nombre" value="${esc(p.nombre)}" autofocus></label>
        <div class="grid2"><label class="f">Código<input class="input" name="codigo" value="${esc(p.codigo || "")}"></label>
          <label class="f">Precio de venta<input class="input" type="number" min="0" step="0.5" name="precio_venta" value="${p.precio_venta}"></label></div>
        <label class="f">Categoría<select class="input" name="categoria_id">${options(data.categorias, "categoria_id", "nombre", p.categoria_id, "Sin categoría")}</select></label>
        <label class="check"><input type="checkbox" name="activo" ${p.activo ? "checked" : ""}> Activo (visible en el punto de venta)</label>
        <div class="card card-b stack" style="gap:4px;background:var(--surface-2)">
          <div class="stat-line"><span>Costo de receta</span><b id="pr-costo"></b></div>
          <div class="stat-line"><span>Margen bruto</span><b id="pr-mg"></b></div>
          <div class="stat-line"><span>Food cost</span><b id="pr-fc"></b></div>
          <div class="stat-line"><span>Precio sugerido (food cost 30%)</span><span id="pr-sug"></span></div>
        </div>
      </div>
      <div class="stack">
        <h3>Receta — consumo por 1 unidad vendida</h3>
        <p class="hint" style="margin:0">Estos insumos se descuentan automáticamente del inventario cada vez que se vende el producto (backflush). Si revendes algo tal cual (ej. un refresco), su receta es 1 pieza de ese insumo.</p>
        <div id="pr-rec"></div>
        <div class="row"><select class="input grow" id="pr-ins">${options(insAct, "insumo_id", (i) => `${i.nombre} (${i.unidad}) · ${money(i.costo_promedio)}/${i.unidad}`, "", "Agregar insumo…")}</select>
          <input class="input" type="number" min="0" step="0.001" id="pr-cant" placeholder="Cantidad" style="width:110px">
          <button class="btn" id="pr-add">Agregar</button></div>
      </div></div>`,
    footer: `<button class="btn" data-c>Cancelar</button><button class="btn primary" data-s>Guardar</button>`,
  });
  const precio = $("[name=precio_venta]", m.el);
  const pinta = () => {
    const el = $("#pr-rec", m.el); el.innerHTML = "";
    const filas = receta.map((r) => { const i = data.insumos.find((x) => x.insumo_id === r.insumo_id) || {}; return { ...r, nombre: i.nombre, unidad: i.unidad, costo: r.cantidad * (i.costo_promedio || 0) }; });
    el.appendChild(table([
      { t: "Insumo", k: "nombre" },
      { t: "Cantidad", k: (r) => `<input class="input" type="number" min="0" step="0.001" value="${r.cantidad}" data-q="${r.insumo_id}" style="width:100px;text-align:right"> ${esc(r.unidad)}`, cls: "num" },
      { t: "Costo", k: "costo", cls: "num", f: money },
      { t: "", k: (r) => `<button class="btn sm ghost" data-del="${r.insumo_id}">Quitar</button>` },
    ], filas, { empty: "Sin insumos. El producto no descontará inventario." }));
    $$("[data-q]", el).forEach((i) => i.oninput = () => { const r = receta.find((x) => x.insumo_id === +i.dataset.q); r.cantidad = Number(i.value || 0); calc(); });
    $$("[data-del]", el).forEach((b) => b.onclick = () => { receta.splice(receta.findIndex((x) => x.insumo_id === +b.dataset.del), 1); pinta(); });
    calc();
  };
  const calc = () => {
    const costo = receta.reduce((s, r) => s + r.cantidad * (data.insumos.find((x) => x.insumo_id === r.insumo_id)?.costo_promedio || 0), 0);
    const pv = Number(precio.value || 0);
    $("#pr-costo", m.el).textContent = money(costo);
    $("#pr-mg", m.el).textContent = `${money(pv - costo)} (${pv ? pct((pv - costo) / pv) : "—"})`;
    $("#pr-fc", m.el).textContent = pv ? pct(costo / pv) : "—";
    $("#pr-sug", m.el).textContent = money(Math.ceil(costo / 0.3));
  };
  precio.oninput = calc;
  const add = () => {
    const id = +$("#pr-ins", m.el).value, q = Number($("#pr-cant", m.el).value);
    if (!id || !(q > 0)) return toast("Elige insumo y cantidad mayor a 0", "warn");
    const ex = receta.find((r) => r.insumo_id === id);
    if (ex) ex.cantidad = q; else receta.push({ insumo_id: id, cantidad: q });
    $("#pr-cant", m.el).value = ""; $("#pr-ins", m.el).value = ""; pinta();
  };
  $("#pr-add", m.el).onclick = add;
  $("#pr-cant", m.el).addEventListener("keydown", (e) => e.key === "Enter" && add());
  $("[data-c]", m.el).onclick = () => m.close();
  $("[data-s]", m.el).onclick = () => {
    const d = formData(m.el.querySelector(".modal-b > .grid2 > .stack"));
    const body = { ...d, categoria_id: d.categoria_id ? +d.categoria_id : null, precio_venta: Number(precio.value || 0),
      receta: receta.filter((r) => r.cantidad > 0) };
    guardar(m, nuevo ? post("/productos", body) : put(`/productos/${p.producto_id}`, body), "Producto guardado");
  };
  pinta();
}

// ---------------- Insumo ----------------
function editarInsumo(i) {
  const nuevo = !i;
  i = i || { nombre: "", codigo: "", unidad: "kg", stock_minimo: 0, proveedor_id: "", activo: 1 };
  const m = modal({
    title: nuevo ? "Nuevo insumo" : `Editar: ${i.nombre}`,
    body: `<div class="stack">
      <label class="f">Nombre<input class="input" name="nombre" value="${esc(i.nombre)}"></label>
      <div class="grid2"><label class="f">Código<input class="input" name="codigo" value="${esc(i.codigo || "")}"></label>
        <label class="f">Unidad de medida<select class="input" name="unidad">${data.unidades.map((u) => `<option ${u === i.unidad ? "selected" : ""}>${u}</option>`).join("")}</select></label>
        <label class="f">Stock mínimo (alerta)<input class="input" type="number" min="0" step="0.001" name="stock_minimo" value="${i.stock_minimo}"></label>
        <label class="f">Proveedor<select class="input" name="proveedor_id">${options(data.proveedores, "proveedor_id", "nombre", i.proveedor_id, "—")}</select></label>
        ${nuevo ? `<label class="f">Existencia inicial<input class="input" type="number" min="0" step="0.001" name="stock_inicial" value="0"></label>
        <label class="f">Costo unitario<input class="input" type="number" min="0" step="0.01" name="costo_unitario" value="0"></label>` : ""}
      </div>
      ${nuevo ? "" : `<div class="alert info">Existencia ${num(i.stock_actual)} ${esc(i.unidad)} · costo promedio ${money(i.costo_promedio)}. Para cambiar existencias usa Inventario → Entrada o Ajuste (quedan en el kardex).</div>`}
      <label class="check"><input type="checkbox" name="activo" ${i.activo ? "checked" : ""}> Activo</label></div>`,
    footer: `<button class="btn" data-c>Cancelar</button><button class="btn primary" data-s>Guardar</button>`,
  });
  $("[data-c]", m.el).onclick = () => m.close();
  $("[data-s]", m.el).onclick = () => {
    const d = formData(m.body);
    d.proveedor_id = d.proveedor_id ? +d.proveedor_id : null;
    d.stock_minimo = d.stock_minimo || 0;
    guardar(m, nuevo ? post("/insumos", d) : put(`/insumos/${i.insumo_id}`, d), "Insumo guardado");
  };
}

function editarCategoria(c) {
  const nuevo = !c;
  c = c || { nombre: "", color: "#2a78d6", orden: data.categorias.length + 1, activo: 1 };
  const m = modal({
    title: nuevo ? "Nueva categoría" : "Editar categoría", size: "w-sm",
    body: `<div class="stack"><label class="f">Nombre<input class="input" name="nombre" value="${esc(c.nombre)}"></label>
      <div class="grid2"><label class="f">Color<input class="input" type="color" name="color" value="${esc(c.color)}" style="height:40px;padding:3px"></label>
      <label class="f">Orden<input class="input" type="number" name="orden" value="${c.orden}"></label></div>
      <label class="check"><input type="checkbox" name="activo" ${c.activo ? "checked" : ""}> Activa</label></div>`,
    footer: `<button class="btn" data-c>Cancelar</button><button class="btn primary" data-s>Guardar</button>`,
  });
  $("[data-c]", m.el).onclick = () => m.close();
  $("[data-s]", m.el).onclick = () => { const d = formData(m.body); d.orden = d.orden || 0; guardar(m, nuevo ? post("/categorias", d) : put(`/categorias/${c.categoria_id}`, d), "Categoría guardada"); };
}

function editarProveedor(p) {
  const nuevo = !p;
  p = p || { nombre: "", contacto: "", telefono: "", email: "", activo: 1 };
  const m = modal({
    title: nuevo ? "Nuevo proveedor" : "Editar proveedor",
    body: `<div class="stack"><label class="f">Nombre<input class="input" name="nombre" value="${esc(p.nombre)}"></label>
      <div class="grid2"><label class="f">Contacto<input class="input" name="contacto" value="${esc(p.contacto || "")}"></label>
      <label class="f">Teléfono<input class="input" name="telefono" value="${esc(p.telefono || "")}"></label></div>
      <label class="f">Email<input class="input" name="email" value="${esc(p.email || "")}"></label>
      <label class="check"><input type="checkbox" name="activo" ${p.activo ? "checked" : ""}> Activo</label></div>`,
    footer: `<button class="btn" data-c>Cancelar</button><button class="btn primary" data-s>Guardar</button>`,
  });
  $("[data-c]", m.el).onclick = () => m.close();
  $("[data-s]", m.el).onclick = () => { const d = formData(m.body); guardar(m, nuevo ? post("/proveedores", d) : put(`/proveedores/${p.proveedor_id}`, d), "Proveedor guardado"); };
}

function editarMetodo(x) {
  const nuevo = !x;
  x = x || { nombre: "", es_efectivo: 0, activo: 1 };
  const m = modal({
    title: nuevo ? "Nuevo método de pago" : "Editar método de pago", size: "w-sm",
    body: `<div class="stack"><label class="f">Nombre<input class="input" name="nombre" value="${esc(x.nombre)}"></label>
      <label class="check"><input type="checkbox" name="es_efectivo" ${x.es_efectivo ? "checked" : ""}> Es efectivo (calcula cambio y suma al corte de caja)</label>
      <label class="check"><input type="checkbox" name="activo" ${x.activo ? "checked" : ""}> Activo</label></div>`,
    footer: `<button class="btn" data-c>Cancelar</button><button class="btn primary" data-s>Guardar</button>`,
  });
  $("[data-c]", m.el).onclick = () => m.close();
  $("[data-s]", m.el).onclick = () => { const d = formData(m.body); guardar(m, nuevo ? post("/metodos-pago", d) : put(`/metodos-pago/${x.metodo_pago_id}`, d), "Método guardado"); };
}
