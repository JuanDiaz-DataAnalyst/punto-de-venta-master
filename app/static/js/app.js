import { api, get, post, session, setUnauthorizedHandler } from "./api.js";
import { $, $$, closeAllModals, confirmDialog, esc, formData, icon, modal, toast, toastErr } from "./ui.js";

const root = $("#root");
export const state = { estado: null, user: null, config: {} };

const ROUTES = [
  { path: "pos", label: "Vender", icon: "pos", mod: "./views/pos.js" },
  { path: "caja", label: "Caja / Turno", icon: "caja", mod: "./views/caja.js" },
  { path: "ventas", label: "Ventas", icon: "ventas", mod: "./views/ventas.js" },
  { path: "inventario", label: "Inventario", icon: "inv", mod: "./views/inventario.js" },
  { sec: "Administración", admin: true },
  { path: "dashboard", label: "Dashboard", icon: "dash", mod: "./views/dashboard.js", admin: true },
  { path: "catalogo", label: "Menú y recetas", icon: "cat", mod: "./views/catalogo.js", admin: true },
  { path: "usuarios", label: "Usuarios", icon: "users", mod: "./views/usuarios.js", admin: true },
  { path: "reportes", label: "Reportes y respaldos", icon: "rep", mod: "./views/reportes.js", admin: true },
  { path: "config", label: "Configuración", icon: "cfg", mod: "./views/config.js", admin: true },
];

export const isAdmin = () => state.user?.rol === "ADMIN";
const enVentana = () => !!window.pywebview;

setUnauthorizedHandler(() => { state.user = null; renderLogin("Tu sesión terminó, vuelve a entrar."); });

async function boot() {
  try {
    state.estado = await get("/estado");
  } catch (e) {
    root.innerHTML = `<div class="auth-wrap"><div class="auth-card"><h2>No se pudo iniciar</h2><p>${esc(e.message)}</p></div></div>`;
    return;
  }
  document.title = `${state.estado.nombre_negocio || ""} · Punto de Venta`;
  if (state.estado.requiere_configuracion) return renderSetup();
  if (session.token) {
    try { state.user = await get("/me"); return startApp(); } catch { session.token = null; }
  }
  renderLogin();
}

function brand(sub) {
  return `<div class="brand"><div class="logo">PV</div><div><h2>${esc(state.estado?.nombre_negocio || "Punto de Venta")}</h2>
          <small>${esc(sub || "Punto de Venta MASTER v" + (state.estado?.version || ""))}</small></div></div>`;
}

function renderLogin(msg) {
  root.innerHTML = `<div class="auth-wrap"><form class="auth-card stack" autocomplete="off">
      ${brand()}
      ${msg ? `<div class="alert">${esc(msg)}</div>` : ""}
      <label class="f">Usuario<input class="input" name="username" autofocus required></label>
      <label class="f">Contraseña<input class="input" name="password" type="password" required></label>
      <div class="alert bad hidden" data-err></div>
      <button class="btn primary lg block">Entrar</button>
    </form></div>`;
  const f = $("form", root);
  $("[name=username]", f).focus();
  f.onsubmit = async (e) => {
    e.preventDefault();
    const btn = $("button", f); btn.disabled = true;
    try {
      const r = await post("/login", formData(f));
      session.token = r.token;
      state.user = r.usuario;
      startApp();
    } catch (err) {
      const box = $("[data-err]", f); box.textContent = err.message; box.classList.remove("hidden");
      btn.disabled = false; $("[name=password]", f).select();
    }
  };
}

function renderSetup() {
  root.innerHTML = `<div class="auth-wrap"><form class="auth-card wide stack" autocomplete="off">
      ${brand("Configuración inicial")}
      <p class="ink2" style="margin:0">Bienvenido. Captura los datos de tu negocio y crea el usuario administrador.</p>
      <label class="f">Nombre del negocio<input class="input" name="nombre_negocio" required placeholder="Ej. Tacos Don Juan"></label>
      <div class="grid2">
        <label class="f">Tu nombre<input class="input" name="admin_nombre" required></label>
        <label class="f">Usuario administrador<input class="input" name="admin_username" required minlength="3" value="admin"></label>
        <label class="f">Contraseña<input class="input" name="admin_password" type="password" required minlength="4"></label>
        <label class="f">Repite la contraseña<input class="input" name="pw2" type="password" required minlength="4"></label>
      </div>
      <label class="check"><input type="checkbox" name="datos_ejemplo"> Cargar datos de ejemplo (menú de food truck, recetas, inventario y 90 días de ventas) — ideal para probar el sistema</label>
      <div class="alert bad hidden" data-err></div>
      <button class="btn primary lg block">Crear y comenzar</button>
    </form></div>`;
  const f = $("form", root);
  f.onsubmit = async (e) => {
    e.preventDefault();
    const d = formData(f);
    const err = $("[data-err]", f);
    if (d.admin_password !== d.pw2) { err.textContent = "Las contraseñas no coinciden"; err.classList.remove("hidden"); return; }
    delete d.pw2;
    const btn = $("button", f); btn.disabled = true; btn.textContent = d.datos_ejemplo ? "Generando datos de ejemplo…" : "Creando…";
    try {
      await post("/setup", d);
      const r = await post("/login", { username: d.admin_username, password: d.admin_password });
      session.token = r.token; state.user = r.usuario;
      state.estado = await get("/estado");
      toast("¡Listo! Sistema configurado");
      startApp();
    } catch (ex) { err.textContent = ex.message; err.classList.remove("hidden"); btn.disabled = false; btn.textContent = "Crear y comenzar"; }
  };
}

async function startApp() {
  try { state.config = await get("/config"); } catch { state.config = {}; }
  const nav = ROUTES.filter((r) => !r.admin || isAdmin()).map((r) =>
    r.sec ? `<div class="sec">${esc(r.sec)}</div>` : `<a href="#/${r.path}" data-path="${r.path}">${icon(r.icon)}<span>${esc(r.label)}</span></a>`).join("");
  const ini = (state.user.nombre || "?").split(" ").map((x) => x[0]).slice(0, 2).join("").toUpperCase();
  root.innerHTML = `<div class="app">
    <aside class="sidebar">
      <div class="brand"><div class="logo">PV</div><div><b style="color:#fff">${esc(state.estado.nombre_negocio || "")}</b><small>Punto de Venta</small></div></div>
      <nav class="nav">${nav}</nav>
      <div class="side-foot">
        <div class="user-chip"><div class="avatar">${esc(ini)}</div><div><b>${esc(state.user.nombre)}</b><small>${state.user.rol === "ADMIN" ? "Administrador" : "Cajero"}</small></div></div>
        <div class="row" style="gap:6px">
          <button class="btn sm grow" data-pw>Contraseña</button>
          <button class="btn sm grow" data-out>${icon("out")} Salir</button>
        </div>
        ${enVentana() ? "" : `<button class="btn sm block" style="margin-top:6px" data-off>${icon("power")} Cerrar sistema</button>`}
      </div>
    </aside>
    <main class="main" id="view"></main>
  </div>`;
  $("[data-out]").onclick = logout;
  $("[data-pw]").onclick = cambiarPassword;
  const off = $("[data-off]");
  if (off) off.onclick = apagar;
  window.onhashchange = route;
  if (!location.hash || location.hash === "#/") location.hash = "#/pos";
  route();
}

let cleanup = null;
let routeSeq = 0;
async function route() {
  const path = (location.hash.replace(/^#\//, "") || "pos").split("?")[0];
  let r = ROUTES.find((x) => x.path === path && (!x.admin || isAdmin()));
  if (!r) { location.hash = "#/pos"; return; }
  $$(".nav a").forEach((a) => a.classList.toggle("active", a.dataset.path === path));
  closeAllModals();
  if (cleanup) { try { cleanup(); } catch { /* */ } cleanup = null; }
  const view = $("#view");
  const seq = ++routeSeq;
  view.innerHTML = `<div class="page"><div class="muted">Cargando…</div></div>`;
  try {
    const mod = await import(r.mod);
    if (seq !== routeSeq) return;
    view.innerHTML = "";
    view.scrollTop = 0;
    cleanup = (await mod.render(view, { state, isAdmin: isAdmin() })) || null;
  } catch (e) {
    console.error(e);
    view.innerHTML = `<div class="page"><div class="alert bad">${esc(e.message)}</div></div>`;
  }
}

async function logout() {
  try { await post("/logout"); } catch { /* */ }
  session.token = null; state.user = null;
  if (cleanup) { try { cleanup(); } catch { /* */ } cleanup = null; }
  location.hash = "";
  renderLogin();
}

function cambiarPassword() {
  const m = modal({
    title: "Cambiar mi contraseña", size: "w-sm",
    body: `<div class="stack"><label class="f">Contraseña actual<input class="input" type="password" name="actual"></label>
           <label class="f">Nueva contraseña<input class="input" type="password" name="nueva" minlength="4"></label>
           <label class="f">Repetir nueva<input class="input" type="password" name="rep"></label></div>`,
    footer: `<button class="btn" data-c>Cancelar</button><button class="btn primary" data-s>Guardar</button>`,
  });
  $("[data-c]", m.el).onclick = () => m.close();
  $("[data-s]", m.el).onclick = async () => {
    const d = formData(m.body);
    if (d.nueva !== d.rep) return toast("Las contraseñas no coinciden", "err");
    try { await post("/me/password", { actual: d.actual, nueva: d.nueva }); m.close(); toast("Contraseña actualizada"); }
    catch (e) { toastErr(e); }
  };
}

async function apagar() {
  if (!(await confirmDialog("Se cerrará el servidor del punto de venta. ¿Continuar?", { ok: "Cerrar sistema", danger: true }))) return;
  try { await post("/sistema/apagar"); } catch { /* */ }
  root.innerHTML = `<div class="auth-wrap"><div class="auth-card"><h2>Sistema cerrado</h2><p class="ink2">Ya puedes cerrar esta pestaña.</p></div></div>`;
}

export function refreshConfig() { return get("/config").then((c) => (state.config = c)); }
export { api };

boot();
