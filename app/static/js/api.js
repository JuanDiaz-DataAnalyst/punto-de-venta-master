// Cliente de la API local con token de sesión
const KEY = "pos_token";

export const session = {
  get token() { try { return sessionStorage.getItem(KEY); } catch { return this._t; } },
  set token(v) {
    this._t = v;
    try { v ? sessionStorage.setItem(KEY, v) : sessionStorage.removeItem(KEY); } catch { /* sin storage */ }
  },
  user: null,
  _t: null,
};

export class ApiError extends Error {
  constructor(msg, status, datos) { super(msg); this.status = status; this.datos = datos; }
}

let onUnauthorized = () => {};
export function setUnauthorizedHandler(fn) { onUnauthorized = fn; }

export async function api(path, { method = "GET", body, raw = false, query } = {}) {
  let url = "/api" + path;
  if (query) {
    const q = new URLSearchParams();
    Object.entries(query).forEach(([k, v]) => { if (v !== undefined && v !== null && v !== "") q.set(k, v); });
    const s = q.toString();
    if (s) url += (url.includes("?") ? "&" : "?") + s;
  }
  const headers = {};
  if (session.token) headers.Authorization = "Bearer " + session.token;
  if (body !== undefined) headers["Content-Type"] = "application/json";
  let res;
  try {
    res = await fetch(url, { method, headers, body: body !== undefined ? JSON.stringify(body) : undefined });
  } catch (e) {
    throw new ApiError("No hay conexión con el servidor local", 0);
  }
  if (res.status === 401 && path !== "/login") {
    session.token = null;
    onUnauthorized();
    throw new ApiError("Tu sesión terminó", 401);
  }
  if (raw) {
    if (!res.ok) throw new ApiError("Error " + res.status, res.status);
    return res.text();
  }
  let data = null;
  try { data = await res.json(); } catch { /* vacío */ }
  if (!res.ok) throw new ApiError((data && data.detail) || "Error " + res.status, res.status, data && data.datos);
  return data;
}

export const get = (p, query) => api(p, { query });
export const post = (p, body, query) => api(p, { method: "POST", body: body ?? {}, query });
export const put = (p, body) => api(p, { method: "PUT", body });
export const del = (p) => api(p, { method: "DELETE" });
