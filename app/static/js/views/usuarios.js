import { get, post, put } from "../api.js";
import { $, esc, fmtDate, formData, modal, table, toast, toastErr } from "../ui.js";
import { state } from "../app.js";

export async function render(view) {
  view.innerHTML = `<div class="page"><div class="page-head"><div class="grow"><h1>Usuarios</h1>
    <div class="sub">Niveles de acceso: <b>Admin</b> (todo el sistema) y <b>User</b> (vender, caja, entradas de material y consulta de inventario)</div></div>
    <button class="btn primary" id="u-new">+ Nuevo usuario</button></div><div id="u-t"></div>
    <div class="card card-b" style="margin-top:18px"><h3 style="margin-bottom:8px">Permisos por nivel</h3><div id="u-perm"></div></div></div>`;
  $("#u-new").onclick = () => editar(null);
  $("#u-perm").appendChild(table([{ t: "Función", k: "f" }, { t: "User", k: "u", f: (v) => v ? "✓" : "—" }, { t: "Admin", k: "a", f: (v) => v ? "✓" : "—" }], [
    { f: "Vender, cobrar, imprimir tickets", u: 1, a: 1 }, { f: "Abrir / cerrar caja, retiros e ingresos de efectivo", u: 1, a: 1 },
    { f: "Registrar entradas de material", u: 1, a: 1 }, { f: "Consultar existencias y kardex", u: 1, a: 1 },
    { f: "Ver ventas del turno actual", u: 1, a: 1 }, { f: "Historial completo de ventas y cancelaciones", u: 0, a: 1 },
    { f: "Ajustes manuales y conteo físico de inventario", u: 0, a: 1 }, { f: "Menú, precios, recetas, insumos, proveedores", u: 0, a: 1 },
    { f: "Dashboard, reportes, exportación y respaldos", u: 0, a: 1 }, { f: "Usuarios y configuración", u: 0, a: 1 },
  ]));
  await cargar();
}

async function cargar() {
  try {
    const rows = await get("/usuarios");
    const el = $("#u-t"); el.innerHTML = "";
    el.appendChild(table([
      { t: "Nombre", k: "nombre" }, { t: "Usuario", k: "username" },
      { t: "Nivel", k: "rol", f: (v) => v === "ADMIN" ? `<span class="badge acc">Admin</span>` : `<span class="badge info">User</span>` },
      { t: "Ventas", k: "ventas", cls: "num" }, { t: "Último acceso", k: "ultimo_acceso", f: (v) => esc(fmtDate(v)) },
      { t: "Estado", k: "activo", f: (v) => v ? `<span class="badge ok">Activo</span>` : `<span class="badge">Inactivo</span>` },
    ], rows, { onRow: editar, rowClass: (u) => u.activo ? "" : "off" }));
  } catch (e) { toastErr(e); }
}

function editar(u) {
  const nuevo = !u;
  u = u || { nombre: "", username: "", rol: "USER", activo: 1 };
  const yo = u.usuario_id === state.user.usuario_id;
  const m = modal({
    title: nuevo ? "Nuevo usuario" : `Editar: ${u.nombre}`, size: "w-sm",
    body: `<div class="stack">
      <label class="f">Nombre completo<input class="input" name="nombre" value="${esc(u.nombre)}"></label>
      <label class="f">Usuario (para iniciar sesión)<input class="input" name="username" value="${esc(u.username)}"></label>
      <label class="f">Nivel<select class="input" name="rol"><option value="USER" ${u.rol === "USER" ? "selected" : ""}>User — cajero</option>
        <option value="ADMIN" ${u.rol === "ADMIN" ? "selected" : ""}>Admin — administrador</option></select></label>
      <label class="f">${nuevo ? "Contraseña" : "Nueva contraseña (dejar vacío para no cambiar)"}<input class="input" type="password" name="password"></label>
      <label class="check"><input type="checkbox" name="activo" ${u.activo ? "checked" : ""} ${yo ? "disabled" : ""}> Activo</label></div>`,
    footer: `<button class="btn" data-c>Cancelar</button><button class="btn primary" data-s>Guardar</button>`,
  });
  $("[data-c]", m.el).onclick = () => m.close();
  $("[data-s]", m.el).onclick = async () => {
    const d = formData(m.body);
    if (yo) d.activo = true;
    if (!d.password) d.password = null;
    try { nuevo ? await post("/usuarios", d) : await put(`/usuarios/${u.usuario_id}`, d); m.close(); toast("Usuario guardado"); cargar(); }
    catch (e) { toastErr(e); }
  };
}
