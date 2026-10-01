"""Usuarios, configuración, respaldos, auditoría y exportaciones (solo Admin)."""

import csv
import os
import sqlite3
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .. import config, db, security
from ..db import audit, get_config, get_db

router = APIRouter(prefix="/api", tags=["admin"])


# ------------------------------ USUARIOS ------------------------------
class UsuarioIn(BaseModel):
    username: str = Field(min_length=3)
    nombre: str = Field(min_length=1)
    rol: str = "USER"
    activo: bool = True
    password: str | None = None


def _admins_activos(conn, excluir: int | None = None) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM dim_usuario WHERE rol='ADMIN' AND activo=1 AND usuario_id != ?", (excluir or -1,)
    ).fetchone()[0]


@router.get("/usuarios")
def listar_usuarios(user=Depends(security.require_admin), conn=Depends(get_db)):
    return [
        dict(r)
        for r in conn.execute(
            """SELECT u.usuario_id, u.username, u.nombre, u.rol, u.activo, u.creado_en, u.ultimo_acceso,
                  (SELECT COUNT(*) FROM ventas v WHERE v.usuario_id=u.usuario_id AND v.estado='PAGADA') AS ventas
           FROM dim_usuario u ORDER BY u.activo DESC, u.nombre"""
        )
    ]


@router.post("/usuarios")
def crear_usuario(data: UsuarioIn, user=Depends(security.require_admin), conn=Depends(get_db)):
    if data.rol not in ("ADMIN", "USER"):
        raise HTTPException(400, "Rol inválido")
    if not data.password or len(data.password) < 4:
        raise HTTPException(400, "La contraseña debe tener al menos 4 caracteres")
    h, s = security.hash_password(data.password)
    try:
        with conn:
            cur = conn.execute(
                "INSERT INTO dim_usuario(username, nombre, rol, password_hash, salt, activo) VALUES (?,?,?,?,?,?)",
                (data.username.strip(), data.nombre.strip(), data.rol, h, s, int(data.activo)),
            )
            audit(
                conn, user["usuario_id"], "CREAR_USUARIO", "dim_usuario", cur.lastrowid, f"{data.username} ({data.rol})"
            )
    except sqlite3.IntegrityError as e:
        raise HTTPException(400, "Ese nombre de usuario ya existe") from e
    return {"usuario_id": cur.lastrowid}


@router.put("/usuarios/{uid}")
def editar_usuario(uid: int, data: UsuarioIn, user=Depends(security.require_admin), conn=Depends(get_db)):
    if data.rol not in ("ADMIN", "USER"):
        raise HTTPException(400, "Rol inválido")
    prev = conn.execute("SELECT * FROM dim_usuario WHERE usuario_id=?", (uid,)).fetchone()
    if not prev:
        raise HTTPException(404, "Usuario no encontrado")
    if (data.rol != "ADMIN" or not data.activo) and prev["rol"] == "ADMIN" and _admins_activos(conn, uid) == 0:
        raise HTTPException(400, "Debe existir al menos un administrador activo")
    if uid == user["usuario_id"] and not data.activo:
        raise HTTPException(400, "No puedes desactivar tu propio usuario")
    try:
        with conn:
            conn.execute(
                "UPDATE dim_usuario SET username=?, nombre=?, rol=?, activo=? WHERE usuario_id=?",
                (data.username.strip(), data.nombre.strip(), data.rol, int(data.activo), uid),
            )
            if data.password:
                if len(data.password) < 4:
                    raise HTTPException(400, "La contraseña debe tener al menos 4 caracteres")
                h, s = security.hash_password(data.password)
                conn.execute("UPDATE dim_usuario SET password_hash=?, salt=? WHERE usuario_id=?", (h, s, uid))
            audit(
                conn,
                user["usuario_id"],
                "EDITAR_USUARIO",
                "dim_usuario",
                uid,
                f"{data.username} rol={data.rol} activo={data.activo}{' + reset password' if data.password else ''}",
            )
    except sqlite3.IntegrityError as e:
        raise HTTPException(400, "Ese nombre de usuario ya existe") from e
    if not data.activo or data.password:
        security.drop_user_sessions(uid)
    return {"ok": True}


# ------------------------------ CONFIGURACIÓN ------------------------------
CLAVES_EDITABLES = set(db.DEFAULT_CONFIG.keys())


@router.get("/config")
def leer_config(user=Depends(security.current_user), conn=Depends(get_db)):
    cfg = get_config(conn)
    cfg["_data_dir"] = str(config.DATA_DIR)
    return cfg


@router.put("/config")
def guardar_config(data: dict, user=Depends(security.require_admin), conn=Depends(get_db)):
    with conn:
        for k, v in data.items():
            if k in CLAVES_EDITABLES:
                conn.execute("INSERT OR REPLACE INTO config(clave, valor) VALUES (?,?)", (k, str(v)))
        audit(conn, user["usuario_id"], "EDITAR_CONFIG", detalle=", ".join(k for k in data if k in CLAVES_EDITABLES))
    return get_config(conn)


# ------------------------------ RESPALDOS ------------------------------
@router.get("/respaldos")
def listar_respaldos(user=Depends(security.require_admin)):
    config.ensure_dirs()
    return [
        {
            "archivo": p.name,
            "tamano_kb": round(p.stat().st_size / 1024, 1),
            "fecha": datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
        }
        for p in sorted(config.BACKUP_DIR.glob("pos_*.db"), reverse=True)
    ]


@router.post("/respaldos")
def crear_respaldo(user=Depends(security.require_admin), conn=Depends(get_db)):
    destino = db.backup("manual")
    with conn:
        audit(conn, user["usuario_id"], "RESPALDO", detalle=destino.name)
    return {"archivo": destino.name, "ruta": str(destino)}


@router.post("/respaldos/{archivo}/restaurar")
def restaurar_respaldo(archivo: str, user=Depends(security.require_admin)):
    ruta = (config.BACKUP_DIR / archivo).resolve()
    if ruta.parent != config.BACKUP_DIR.resolve() or not ruta.exists():
        raise HTTPException(404, "Respaldo no encontrado")
    db.restore(ruta)
    conn = db.connect()
    try:
        with conn:
            audit(conn, user["usuario_id"], "RESTAURAR_RESPALDO", detalle=archivo)
    finally:
        conn.close()
    return {"ok": True}


# ------------------------------ AUDITORÍA ------------------------------
@router.get("/auditoria")
def auditoria(
    desde: str | None = None,
    hasta: str | None = None,
    usuario_id: int | None = None,
    accion: str | None = None,
    user=Depends(security.require_admin),
    conn=Depends(get_db),
):
    where, params = [], []
    if desde:
        where.append("date(l.fecha_hora) >= ?")
        params.append(desde)
    if hasta:
        where.append("date(l.fecha_hora) <= ?")
        params.append(hasta)
    if usuario_id:
        where.append("l.usuario_id=?")
        params.append(usuario_id)
    if accion:
        where.append("l.accion LIKE ?")
        params.append(f"%{accion}%")
    return [
        dict(r)
        for r in conn.execute(
            f"""SELECT l.*, u.nombre AS usuario FROM log_auditoria l LEFT JOIN dim_usuario u ON u.usuario_id=l.usuario_id
            {"WHERE " + " AND ".join(where) if where else ""} ORDER BY l.log_id DESC LIMIT 1000""",
            params,
        )
    ]


# ------------------------------ EXPORTACIONES ------------------------------
EXPORTS = {
    "ventas_detalle": (
        "Ventas detalle",
        "SELECT * FROM v_ventas_detalle WHERE fecha BETWEEN :desde AND :hasta ORDER BY fecha_hora",
    ),
    "ventas": (
        "Tickets",
        """SELECT v.folio, v.fecha_hora, u.nombre AS usuario, m.nombre AS metodo_pago, v.subtotal,
                    v.descuento, v.total, v.costo_total, ROUND(v.total - v.costo_total, 2) AS margen, v.estado,
                    v.motivo_cancelacion, v.turno_id, v.cliente, v.mesa
                 FROM ventas v JOIN dim_usuario u ON u.usuario_id=v.usuario_id
                 JOIN dim_metodo_pago m ON m.metodo_pago_id=v.metodo_pago_id
                 WHERE date(v.fecha_hora) BETWEEN :desde AND :hasta ORDER BY v.fecha_hora""",
    ),
    "productos": (
        "Ventas por producto",
        """SELECT producto, categoria, SUM(cantidad) AS unidades,
                    ROUND(SUM(importe_neto),2) AS ventas, ROUND(SUM(costo_total),2) AS costo,
                    ROUND(SUM(margen),2) AS margen, ROUND(SUM(margen)/NULLIF(SUM(importe_neto),0),4) AS margen_pct
                 FROM v_ventas_detalle WHERE fecha BETWEEN :desde AND :hasta
                 GROUP BY producto, categoria ORDER BY ventas DESC""",
    ),
    "inventario": ("Inventario", "SELECT * FROM v_inventario_valorizado ORDER BY nombre"),
    "movimientos": (
        "Kardex",
        "SELECT * FROM v_movimientos_inventario WHERE fecha BETWEEN :desde AND :hasta ORDER BY fecha_hora",
    ),
    "recetas": (
        "Recetas y costos",
        """SELECT vc.codigo, vc.nombre AS producto, vc.categoria, vc.precio_venta, vc.costo_teorico,
                    vc.margen_teorico, i.nombre AS insumo, r.cantidad, i.unidad, i.costo_promedio,
                    ROUND(r.cantidad*i.costo_promedio,4) AS costo_insumo
                 FROM v_costo_receta vc LEFT JOIN dim_receta r ON r.producto_id=vc.producto_id
                 LEFT JOIN dim_insumo i ON i.insumo_id=r.insumo_id ORDER BY vc.nombre, i.nombre""",
    ),
    "turnos": (
        "Cortes de caja",
        """SELECT t.turno_id, t.apertura, t.cierre, ua.nombre AS abrio, uc.nombre AS cerro,
                    t.fondo_inicial, t.efectivo_esperado, t.efectivo_contado, t.diferencia, t.estado, t.notas
                 FROM turnos t JOIN dim_usuario ua ON ua.usuario_id=t.usuario_apertura_id
                 LEFT JOIN dim_usuario uc ON uc.usuario_id=t.usuario_cierre_id
                 WHERE date(t.apertura) BETWEEN :desde AND :hasta ORDER BY t.turno_id""",
    ),
    "gastos_fijos": (
        "Gastos fijos",
        """SELECT concepto, categoria, monto_mensual, vigente_desde, vigente_hasta, notas
                 FROM gastos_fijos ORDER BY categoria, concepto""",
    ),
    "auditoria": (
        "Auditoría",
        """SELECT l.fecha_hora, u.nombre AS usuario, l.accion, l.entidad, l.entidad_id, l.detalle
                 FROM log_auditoria l LEFT JOIN dim_usuario u ON u.usuario_id=l.usuario_id
                 WHERE date(l.fecha_hora) BETWEEN :desde AND :hasta ORDER BY l.log_id""",
    ),
}


def _abrir(path: Path) -> bool:
    try:
        if os.name == "nt":
            os.startfile(str(path))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            return False
        return True
    except Exception:
        return False


def _escribir_xlsx(ruta: Path, hojas: list[tuple[str, list[str], list]]):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    wb.remove(wb.active)
    for titulo, cols, rows in hojas:
        ws = wb.create_sheet(titulo[:31])
        ws.append(cols)
        for c in ws[1]:
            c.font = Font(bold=True, color="FFFFFF")
            c.fill = PatternFill("solid", fgColor="2B2D42")
            c.alignment = Alignment(horizontal="center")
        for r in rows:
            ws.append(list(r))
        ws.freeze_panes = "A2"
        if rows:
            ws.auto_filter.ref = ws.dimensions
        for i, col in enumerate(cols, 1):
            largo = max([len(str(col))] + [len(str(r[i - 1])) for r in rows[:300] if r[i - 1] is not None])
            ws.column_dimensions[get_column_letter(i)].width = min(max(10, largo + 2), 45)
    wb.save(ruta)


@router.get("/exportar/tipos")
def tipos_export(user=Depends(security.require_admin)):
    return [{"clave": k, "nombre": v[0]} for k, v in EXPORTS.items()]


@router.post("/exportar/{tipo}")
def exportar(
    tipo: str,
    formato: str = "xlsx",
    desde: str | None = None,
    hasta: str | None = None,
    abrir: bool = True,
    user=Depends(security.require_admin),
    conn=Depends(get_db),
):
    tipos = list(EXPORTS) if tipo == "todo" else [tipo]
    if any(t not in EXPORTS for t in tipos):
        raise HTTPException(404, "Tipo de exportación desconocido")
    params = {"desde": desde or "2000-01-01", "hasta": hasta or date.today().isoformat()}
    hojas = []
    for t in tipos:
        cur = conn.execute(EXPORTS[t][1], params)
        cols = [d[0] for d in cur.description]
        hojas.append((EXPORTS[t][0], cols, [tuple(r) for r in cur.fetchall()]))
    config.ensure_dirs()
    sello = datetime.now().strftime("%Y%m%d_%H%M%S")
    if formato == "csv" and len(hojas) == 1:
        ruta = config.EXPORT_DIR / f"{tipo}_{params['desde']}_{params['hasta']}_{sello}.csv"
        with open(ruta, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(hojas[0][1])
            w.writerows(hojas[0][2])
    else:
        ruta = config.EXPORT_DIR / f"{tipo}_{params['desde']}_{params['hasta']}_{sello}.xlsx"
        _escribir_xlsx(ruta, hojas)
    with conn:
        audit(conn, user["usuario_id"], "EXPORTAR", detalle=ruta.name)
    abierto = _abrir(ruta) if abrir else False
    return {"archivo": ruta.name, "ruta": str(ruta), "abierto": abierto, "filas": sum(len(h[2]) for h in hojas)}


@router.get("/exportar/descargar/{archivo}")
def descargar(archivo: str, user=Depends(security.require_admin)):
    ruta = (config.EXPORT_DIR / archivo).resolve()
    if ruta.parent != config.EXPORT_DIR.resolve() or not ruta.exists():
        raise HTTPException(404, "Archivo no encontrado")
    return FileResponse(ruta, filename=archivo)


@router.post("/abrir-carpeta/{cual}")
def abrir_carpeta(cual: str, user=Depends(security.require_admin)):
    carpetas = {"exportaciones": config.EXPORT_DIR, "respaldos": config.BACKUP_DIR, "datos": config.DATA_DIR}
    if cual not in carpetas:
        raise HTTPException(404, "Carpeta desconocida")
    config.ensure_dirs()
    return {"abierto": _abrir(carpetas[cual]), "ruta": str(carpetas[cual])}
