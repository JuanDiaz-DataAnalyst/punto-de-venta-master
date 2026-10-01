import { $, $$, esc } from "../ui.js";

// Guía de uso dentro del sistema. Al cambiar una función, actualiza también docs/manual-de-usuario.md.
const SECCIONES = [
  {
    id: "inicio", t: "Primeros pasos",
    html: `<ol>
      <li>Entra con tu usuario y contraseña. Si es la primera vez, el sistema te pide crear al <b>administrador</b>.</li>
      <li>El administrador da de alta el menú en <b>Menú y recetas</b> (categorías, insumos y productos con su receta).</li>
      <li>Captura tus <b>Gastos fijos</b> (sueldos, renta, luz, agua, gas…) para ver la utilidad real en el Dashboard.</li>
      <li>Cada día: <b>abre la caja</b>, vende, y al terminar haz el <b>corte</b> en Caja / Turno.</li></ol>
      <p class="hint">Puedes abrir esta ayuda en cualquier momento con la tecla <span class="kbd">F1</span>.</p>`,
  },
  {
    id: "vender", t: "Vender: mesas y tickets abiertos",
    html: `<ul>
      <li><b>Abrir una mesa:</b> botón <b>+ Nueva mesa</b> o <span class="kbd">F4</span>. Escribe el número de mesa (o un nombre como «Barra 2» o «Llevar»).
        Cada mesa es una <b>pestaña</b> con su propio ticket y su <b>folio único</b>.</li>
      <li><b>Agregar lo que piden:</b> elige la pestaña de la mesa y toca los productos. Puedes agregar más en cualquier momento mientras están en la mesa.</li>
      <li><b>Notas:</b> botón <b>Nota</b> en el renglón (sin cebolla, término medio…). Si hay varias piezas, la nota se aplica a una sola.</li>
      <li><b>Descuento:</b> <span class="kbd">F9</span>, en monto ($) o porcentaje (%).</li>
      <li><b>Pre-cuenta:</b> imprime la cuenta para que el cliente la revise antes de pagar. No es comprobante y no cierra la mesa.</li>
      <li><b>Dividir / mover:</b> pasa piezas a una <b>cuenta nueva</b> (para cobrar por separado, con su propio folio) o a <b>otra mesa abierta</b>.</li>
      <li><b>Cobrar:</b> <span class="kbd">F12</span> → efectivo (con cambio), tarjeta o transferencia → imprime el ticket. La mesa se libera y su número puede usarse de nuevo.</li>
      <li><b>Cambiar mesa / Cancelar:</b> corrige el número de mesa o descarta una cuenta (pide motivo si ya tenía consumos).</li></ul>
      <p class="hint">Las mesas abiertas se guardan aunque cierres el sistema. El inventario se descuenta al <b>cobrar</b>, no al agregar productos.
      No se puede cerrar el turno mientras haya mesas abiertas.</p>`,
  },
  {
    id: "atajos", t: "Atajos de teclado",
    html: `<div class="tbl-wrap"><table class="tbl"><tbody>
      <tr><td><span class="kbd">F1</span></td><td>Abrir esta ayuda</td></tr>
      <tr><td><span class="kbd">F2</span></td><td>Buscar producto o código (con Enter agrega el único resultado)</td></tr>
      <tr><td><span class="kbd">F4</span></td><td>Abrir una mesa nueva</td></tr>
      <tr><td><span class="kbd">F9</span></td><td>Descuento a la mesa activa</td></tr>
      <tr><td><span class="kbd">F12</span></td><td>Cobrar la mesa activa</td></tr>
      <tr><td><span class="kbd">Esc</span></td><td>Cerrar la ventana abierta</td></tr></tbody></table></div>`,
  },
  {
    id: "caja", t: "Caja y turno",
    html: `<ul>
      <li><b>Abrir caja:</b> captura el efectivo inicial (fondo). Sin turno abierto no se puede vender.</li>
      <li><b>Ingresos y retiros de efectivo:</b> registra cambio adicional, pago de gas, hielo o proveedores, siempre con concepto.</li>
      <li><b>Corte parcial (X):</b> imprime cómo va el turno sin cerrarlo.</li>
      <li><b>Cerrar turno (corte Z):</b> cuenta el efectivo por denominación; el sistema calcula la diferencia contra lo esperado e imprime el corte.</li></ul>`,
  },
  {
    id: "inventario", t: "Inventario",
    html: `<ul>
      <li>Cada venta descuenta automáticamente los insumos de la receta (<b>backflush</b>).</li>
      <li><b>Entrada de material:</b> cuando llega mercancía, captura insumos, cantidades y costo; el costo promedio se recalcula.</li>
      <li><b>Kardex:</b> historial de cada movimiento con la existencia resultante.</li>
      <li>Los insumos bajo su mínimo aparecen como alerta (también en el Dashboard).</li>
      <li><b>Admin:</b> ajustes manuales (merma, caducidad, daño) con motivo y conteo físico masivo.</li></ul>`,
  },
  {
    id: "ventas", t: "Historial de ventas y cancelaciones",
    html: `<ul>
      <li><b>Ventas</b> lista los tickets con folio, mesa, método de pago y total. Busca por folio, mesa o cliente.</li>
      <li>Un <b>User</b> ve solo los tickets del turno actual; el <b>Admin</b> ve todo el historial.</li>
      <li><b>Reimprimir</b> un ticket queda registrado en la auditoría.</li>
      <li><b>Admin:</b> abre el ticket y pulsa <b>Cancelar venta</b> con motivo; el inventario consumido regresa automáticamente.</li></ul>`,
  },
  {
    id: "catalogo", t: "Menú y recetas", admin: true,
    html: `<ol>
      <li>Crea <b>categorías</b> (Tacos, Bebidas…) y, si quieres, <b>proveedores</b>.</li>
      <li>Da de alta los <b>insumos</b>: unidad (kg, l, pz), stock mínimo, existencia inicial y costo unitario.</li>
      <li>Crea los <b>productos</b> con su precio y su <b>receta</b>: cuánto de cada insumo consume una unidad.
        El sistema calcula costo, margen, food cost y un precio sugerido.</li></ol>
      <p class="hint">Un producto que revendes tal cual (un refresco) lleva como receta 1 pieza de ese insumo.</p>`,
  },
  {
    id: "gastos", t: "Gastos fijos", admin: true,
    html: `<ul>
      <li>Pulsa <b>Agregar conceptos comunes</b> para cargar una lista típica de restaurante pequeño con monto $0.</li>
      <li>Escribe el <b>monto mensual</b> de cada concepto directo en la tabla. Para sueldos, agrega un renglón por empleado con <b>+ Nuevo gasto</b> (categoría Nómina).</li>
      <li>El Dashboard reparte cada gasto por día y lo resta del margen bruto para calcular la <b>utilidad operativa</b>, el <b>punto de equilibrio</b>, el <b>costo laboral</b> y el <b>prime cost</b>.</li>
      <li>Para registrar un aumento sin alterar los meses anteriores, termina el gasto en la fecha del cambio (<b>Vigente hasta</b>) y agrega uno nuevo con el monto actualizado.</li></ul>`,
  },
  {
    id: "dashboard", t: "Dashboard", admin: true,
    html: `<p>Elige el periodo (hoy, 7/30/90 días, mes o rango). Todo se compara contra el periodo anterior de la misma duración.</p>
      <ul><li><b>Margen bruto</b> = ventas − costo de insumos. <b>Food cost</b> = costo ÷ ventas.</li>
      <li><b>Utilidad operativa</b> = margen bruto − gastos fijos del periodo.</li>
      <li><b>Punto de equilibrio</b> = ventas necesarias en el periodo para cubrir los gastos fijos con tu margen actual.</li>
      <li><b>Prime cost</b> = (insumos + nómina) ÷ ventas; conviene mantenerlo cerca o por debajo de 60-65 %.</li>
      <li><b>Ingeniería de menú:</b> Estrella (protégela), Caballo de batalla (revisa costo o precio), Rompecabezas (promociónala), Perro (rediséñala o retírala).</li></ul>`,
  },
  {
    id: "usuarios", t: "Usuarios y permisos", admin: true,
    html: `<ul><li><b>User (cajero):</b> vende, maneja mesas, abre/cierra caja, registra entradas de material y consulta existencias.</li>
      <li><b>Admin:</b> además ve Dashboard, Menú, Gastos fijos, Usuarios, Reportes y Configuración, y puede cancelar ventas y ajustar inventario.</li>
      <li>Al crear un usuario elige su tipo en el menú desplegable. Siempre debe quedar al menos un administrador activo.</li>
      <li>Cada persona puede cambiar su contraseña con el botón <b>Contraseña</b> del menú lateral.</li></ul>`,
  },
  {
    id: "respaldos", t: "Respaldos y reportes", admin: true,
    html: `<ul><li>Se crea un <b>respaldo automático</b> cada vez que se abre el sistema (se guardan los últimos 20).</li>
      <li>Copia la carpeta de respaldos a una USB o a la nube con regularidad (ver «Acerca de» para su ubicación).</li>
      <li>En <b>Reportes y respaldos</b> puedes exportar a Excel/CSV (ventas, tickets, productos, inventario, kardex, recetas, cortes, gastos fijos y auditoría) y restaurar un respaldo.</li></ul>`,
  },
  {
    id: "impresora", t: "Impresora de tickets",
    html: `<p>Instala la impresora térmica en Windows y márcala como predeterminada. En el diálogo de impresión desactiva encabezados, pies de página y márgenes.
      El ancho del papel (58 u 80 mm) se elige en <b>Configuración</b>.</p>`,
  },
  {
    id: "problemas", t: "Solución de problemas",
    html: `<div class="tbl-wrap"><table class="tbl"><thead><tr><th>Síntoma</th><th>Qué hacer</th></tr></thead><tbody>
      <tr><td>«No hay un turno de caja abierto»</td><td>Abre la caja en Vender o en Caja / Turno.</td></tr>
      <tr><td>«Inventario insuficiente»</td><td>Registra la entrada de material, o pide al administrador que permita vender sin existencia (Configuración).</td></tr>
      <tr><td>No se puede cerrar el turno</td><td>Hay mesas abiertas: cóbralas o cancélalas primero.</td></tr>
      <tr><td>«La mesa ya tiene una cuenta abierta»</td><td>Usa esa pestaña o cobra/cancela la cuenta anterior.</td></tr>
      <tr><td>«Tu sesión terminó»</td><td>Vuelve a entrar; las sesiones se cierran al reiniciar el sistema.</td></tr>
      <tr><td>No imprime</td><td>Revisa que la impresora esté predeterminada y encendida; prueba imprimir desde otro programa.</td></tr>
      <tr><td>El sistema no abre su ventana</td><td>Instala <i>Microsoft Edge WebView2 Runtime</i>; mientras tanto abre en el navegador.</td></tr>
      <tr><td>Algo falla y no sabes por qué</td><td>Envía al soporte el archivo <code>pos.log</code> de la carpeta de registros (ver «Acerca de»).</td></tr></tbody></table></div>`,
  },
];

export async function render(view, ctx) {
  const visibles = SECCIONES.filter((s) => !s.admin || ctx.isAdmin);
  const est = ctx.state.estado || {};
  const dir = ctx.state.config?._data_dir || "";
  view.innerHTML = `<div class="page" style="max-width:900px">
    <div class="page-head"><div class="grow"><h1>Ayuda</h1>
      <div class="sub">Guía de uso y operación del sistema${ctx.isAdmin ? "" : " para cajeros"}.</div></div>
      <input class="input" id="ay-q" type="search" placeholder="Buscar en la ayuda…" style="max-width:260px" autocomplete="off"></div>
    <div class="row wrap" id="ay-idx" style="margin-bottom:14px">${visibles.map((s) => `<button class="chip" data-go="${s.id}">${esc(s.t)}</button>`).join("")}</div>
    <div class="stack" id="ay-sec">${visibles.map((s, i) => `<details class="card" id="ay-${s.id}" ${i === 0 ? "open" : ""}>
      <summary style="cursor:pointer;padding:14px 16px;font-weight:650;font-size:15px">${esc(s.t)}${s.admin ? ` <span class="badge acc">Admin</span>` : ""}</summary>
      <div class="card-b" style="padding-top:0;line-height:1.55">${s.html}</div></details>`).join("")}</div>
    <div class="empty hidden" id="ay-none">Sin resultados para esa búsqueda.</div>
    <div class="card card-b" style="margin-top:18px"><h3 style="margin-bottom:8px">Acerca de</h3>
      <div class="stat-line"><span>Sistema</span><b>${esc(est.app || "Punto de Venta MASTER")} v${esc(est.version || "")}</b></div>
      ${dir ? `<div class="stat-line"><span>Carpeta de datos</span><code>${esc(dir)}</code></div>
      <div class="stat-line"><span>Respaldos</span><code>${esc(dir)}${dir.includes("\\") ? "\\" : "/"}respaldos</code></div>
      <div class="stat-line"><span>Registros (soporte)</span><code>${esc(dir)}${dir.includes("\\") ? "\\" : "/"}logs</code></div>` : ""}
      <div class="stat-line"><span>Funciona sin internet</span><b>Sí</b></div></div></div>`;

  $$("[data-go]", view).forEach((a) => a.onclick = (e) => {
    e.preventDefault();
    const d = $(`#ay-${a.dataset.go}`, view);
    d.open = true; d.scrollIntoView({ behavior: "smooth", block: "start" });
  });
  $("#ay-q", view).addEventListener("input", (e) => {
    const q = e.target.value.trim().toLowerCase();
    let n = 0;
    $$("#ay-sec details", view).forEach((d) => {
      const ok = !q || d.textContent.toLowerCase().includes(q);
      d.classList.toggle("hidden", !ok);
      if (q && ok) d.open = true;
      n += ok ? 1 : 0;
    });
    $("#ay-none", view).classList.toggle("hidden", n > 0);
  });
}
