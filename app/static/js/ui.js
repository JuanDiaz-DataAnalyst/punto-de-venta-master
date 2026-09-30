// Utilidades de interfaz: formato, modales, toasts, tablas, impresión
export const $ = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

export function esc(v) {
  return String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

const fmtMoney = new Intl.NumberFormat("es-MX", { style: "currency", currency: "MXN", minimumFractionDigits: 2 });
const fmtMoney0 = new Intl.NumberFormat("es-MX", { style: "currency", currency: "MXN", maximumFractionDigits: 0 });
const fmtNum = new Intl.NumberFormat("es-MX", { maximumFractionDigits: 3 });
export const money = (v) => fmtMoney.format(+v || 0);
export const money0 = (v) => fmtMoney0.format(+v || 0);
export const num = (v, d = 3) => new Intl.NumberFormat("es-MX", { maximumFractionDigits: d }).format(+v || 0);
export const pct = (v, d = 1) => `${((+v || 0) * 100).toFixed(d)}%`;
export const compact = (v) => {
  const a = Math.abs(v);
  if (a >= 1e6) return "$" + (v / 1e6).toFixed(2) + "M";
  if (a >= 1e4) return "$" + (v / 1e3).toFixed(1) + "K";
  return money0(v);
};
export { fmtNum };

export function today() { return isoDate(new Date()); }
export function isoDate(d) {
  const z = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${z(d.getMonth() + 1)}-${z(d.getDate())}`;
}
export function addDays(iso, n) { const d = new Date(iso + "T12:00:00"); d.setDate(d.getDate() + n); return isoDate(d); }
export function fmtDate(s) {
  if (!s) return "";
  const d = new Date(s.replace(" ", "T"));
  if (isNaN(d)) return s;
  return (d.toLocaleDateString("es-MX", { day: "2-digit", month: "short", year: "numeric" }) +
    (s.length > 10 ? " " + d.toLocaleTimeString("es-MX", { hour: "2-digit", minute: "2-digit", hour12: false }) : "")).replace(/\s/g, "\u00a0");
}
export function fmtShortDate(s) {
  const d = new Date(s + "T12:00:00");
  return d.toLocaleDateString("es-MX", { day: "2-digit", month: "short" });
}

// ---------- toasts ----------
export function toast(msg, type = "ok", ms = 3200) {
  const el = document.createElement("div");
  el.className = "toast " + (type === "ok" ? "" : type);
  el.textContent = msg;
  $("#toasts").appendChild(el);
  setTimeout(() => el.remove(), ms);
}
export function toastErr(e) { toast(e?.message || String(e), "err", 5000); }

// ---------- modales ----------
let modalStack = [];
export function modal({ title, body = "", footer = "", size = "", onClose } = {}) {
  const back = document.createElement("div");
  back.className = "modal-back";
  back.innerHTML = `<div class="modal ${size}" role="dialog" aria-modal="true">
      <div class="modal-h"><h2>${esc(title)}</h2><button class="btn ghost icon" data-x aria-label="Cerrar">✕</button></div>
      <div class="modal-b"></div>${footer !== null ? `<div class="modal-f"></div>` : ""}</div>`;
  const m = {
    el: back,
    body: $(".modal-b", back),
    foot: $(".modal-f", back),
    close() {
      back.remove();
      modalStack = modalStack.filter((x) => x !== m);
      onClose && onClose();
    },
  };
  if (typeof body === "string") m.body.innerHTML = body; else if (body) m.body.appendChild(body);
  if (m.foot) { if (typeof footer === "string") m.foot.innerHTML = footer; else if (footer) m.foot.appendChild(footer); }
  $("[data-x]", back).onclick = () => m.close();
  back.addEventListener("mousedown", (e) => { if (e.target === back) m.close(); });
  document.body.appendChild(back);
  modalStack.push(m);
  setTimeout(() => { const f = $("[autofocus], .modal-b input:not([type=checkbox]), .modal-b select", back); f && f.focus(); }, 30);
  return m;
}
export function topModal() { return modalStack[modalStack.length - 1]; }
export function closeAllModals() { [...modalStack].reverse().forEach((m) => m.close()); }
document.addEventListener("keydown", (e) => { if (e.key === "Escape" && modalStack.length) { topModal().close(); e.stopPropagation(); } }, true);

export function confirmDialog(msg, { title = "Confirmar", ok = "Aceptar", danger = false } = {}) {
  return new Promise((resolve) => {
    let done = false;
    const m = modal({
      title, size: "w-sm", body: `<p style="margin:0;line-height:1.5">${msg}</p>`,
      footer: `<button class="btn" data-no>Cancelar</button><button class="btn ${danger ? "danger" : "primary"}" data-ok>${esc(ok)}</button>`,
      onClose: () => { if (!done) resolve(false); },
    });
    $("[data-no]", m.el).onclick = () => m.close();
    $("[data-ok]", m.el).onclick = () => { done = true; m.close(); resolve(true); };
    $("[data-ok]", m.el).focus();
  });
}

export function promptDialog(msg, { title = "Captura", value = "", placeholder = "", ok = "Aceptar", type = "text" } = {}) {
  return new Promise((resolve) => {
    let done = false;
    const m = modal({
      title, size: "w-sm",
      body: `<label class="f">${esc(msg)}<input class="input" type="${type}" value="${esc(value)}" placeholder="${esc(placeholder)}" autofocus></label>`,
      footer: `<button class="btn" data-no>Cancelar</button><button class="btn primary" data-ok>${esc(ok)}</button>`,
      onClose: () => { if (!done) resolve(null); },
    });
    const inp = $("input", m.el);
    const accept = () => { done = true; const v = inp.value; m.close(); resolve(v); };
    $("[data-no]", m.el).onclick = () => m.close();
    $("[data-ok]", m.el).onclick = accept;
    inp.addEventListener("keydown", (e) => { if (e.key === "Enter") accept(); });
  });
}

// ---------- formularios ----------
export function formData(root) {
  const out = {};
  $$("[name]", root).forEach((el) => {
    if (el.type === "checkbox") out[el.name] = el.checked;
    else if (el.type === "number") out[el.name] = el.value === "" ? null : Number(el.value);
    else out[el.name] = el.value.trim();
  });
  return out;
}

export function options(list, valKey, labelKey, selected, empty) {
  return (empty !== undefined ? `<option value="">${esc(empty)}</option>` : "") +
    list.map((o) => `<option value="${esc(o[valKey])}" ${String(o[valKey]) === String(selected) ? "selected" : ""}>${esc(typeof labelKey === "function" ? labelKey(o) : o[labelKey])}</option>`).join("");
}

// ---------- tablas ----------
// cols: [{ t: "Título", k: "campo" | fn(row), cls: "num", f: formatter }]
export function table(cols, rows, { onRow, empty = "Sin registros", rowClass, foot } = {}) {
  const wrap = document.createElement("div");
  wrap.className = "tbl-wrap";
  if (!rows.length) { wrap.innerHTML = `<div class="empty">${esc(empty)}</div>`; return wrap; }
  const head = cols.map((c) => `<th class="${c.cls || ""}">${esc(c.t)}</th>`).join("");
  const body = rows.map((r, i) => {
    const tds = cols.map((c) => {
      let v = typeof c.k === "function" ? c.k(r) : r[c.k];
      if (c.f) v = c.f(v, r);
      else if (typeof c.k !== "function" && !c.html) v = esc(v);
      return `<td class="${c.cls || ""}">${v ?? ""}</td>`;
    }).join("");
    return `<tr data-i="${i}" class="${onRow ? "click " : ""}${rowClass ? rowClass(r) : ""}">${tds}</tr>`;
  }).join("");
  const tfoot = foot ? `<tfoot><tr>${cols.map((c, i) => `<td class="${c.cls || ""}">${foot[i] ?? ""}</td>`).join("")}</tr></tfoot>` : "";
  wrap.innerHTML = `<table class="tbl"><thead><tr>${head}</tr></thead><tbody>${body}</tbody>${tfoot}</table>`;
  if (onRow) $$("tbody tr", wrap).forEach((tr) => tr.addEventListener("click", (e) => {
    if (e.target.closest("button")) return;
    onRow(rows[+tr.dataset.i], e);
  }));
  return wrap;
}

export function badgeEstado(e) {
  const map = { OK: "ok", BAJO: "warn", AGOTADO: "bad", PAGADA: "ok", CANCELADA: "bad", ABIERTO: "info", CERRADO: "" };
  const icon = { OK: "●", BAJO: "▲", AGOTADO: "✕", PAGADA: "✓", CANCELADA: "✕", ABIERTO: "●", CERRADO: "■" };
  return `<span class="badge ${map[e] ?? ""}">${icon[e] || ""} ${esc(e)}</span>`;
}

// ---------- impresión (ticket térmico) ----------
export function printHTML(html) {
  const fr = $("#print-frame");
  fr.onload = () => {
    try { fr.contentWindow.focus(); fr.contentWindow.print(); } catch (e) { toastErr(e); }
    fr.onload = null;
  };
  fr.srcdoc = html;
}

export function debounce(fn, ms = 250) {
  let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
}

// ---------- íconos (trazos simples) ----------
const P = {
  pos: '<path d="M3 4h18v12H3z"/><path d="M8 20h8M12 16v4"/>',
  caja: '<rect x="3" y="7" width="18" height="13" rx="2"/><path d="M7 7V4h10v3M3 12h18"/>',
  ventas: '<path d="M6 3h12v18l-3-2-3 2-3-2-3 2z"/><path d="M9 8h6M9 12h6"/>',
  inv: '<path d="M3 7l9-4 9 4-9 4z"/><path d="M3 7v10l9 4 9-4V7"/><path d="M12 11v10"/>',
  cat: '<path d="M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z"/>',
  users: '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c.8-3.5 3.4-5.5 6.5-5.5s5.7 2 6.5 5.5"/><path d="M16 4.5a3.5 3.5 0 010 7M18 14.5c1.9.7 3 2.6 3.5 5.5"/>',
  dash: '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
  rep: '<path d="M14 3H6a2 2 0 00-2 2v14a2 2 0 002 2h12a2 2 0 002-2V9z"/><path d="M14 3v6h6M8 13h8M8 17h5"/>',
  cfg: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 00.3 1.8l.1.1a2 2 0 11-2.8 2.8l-.1-.1a1.7 1.7 0 00-1.8-.3 1.7 1.7 0 00-1 1.5V21a2 2 0 11-4 0v-.1a1.7 1.7 0 00-1.1-1.5 1.7 1.7 0 00-1.8.3l-.1.1a2 2 0 11-2.8-2.8l.1-.1a1.7 1.7 0 00.3-1.8 1.7 1.7 0 00-1.5-1H3a2 2 0 110-4h.1a1.7 1.7 0 001.5-1.1 1.7 1.7 0 00-.3-1.8l-.1-.1a2 2 0 112.8-2.8l.1.1a1.7 1.7 0 001.8.3H9a1.7 1.7 0 001-1.5V3a2 2 0 114 0v.1a1.7 1.7 0 001 1.5 1.7 1.7 0 001.8-.3l.1-.1a2 2 0 112.8 2.8l-.1.1a1.7 1.7 0 00-.3 1.8V9a1.7 1.7 0 001.5 1H21a2 2 0 110 4h-.1a1.7 1.7 0 00-1.5 1z"/>',
  out: '<path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4M16 17l5-5-5-5M21 12H9"/>',
  power: '<path d="M12 2v10M18.4 6.6a9 9 0 11-12.8 0"/>',
};
export const icon = (n) => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${P[n] || ""}</svg>`;
