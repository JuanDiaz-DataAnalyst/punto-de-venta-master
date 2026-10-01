"""Punto de venta, historial de ventas, cancelaciones, tickets y turnos de caja."""

from html import escape

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from ..db import audit, get_config, get_db, now_str
from ..security import current_user, require_admin
from ..services import (
    ErrorNegocio,
    cancelar_venta,
    detalle_venta,
    disponibilidad_productos,
    registrar_venta,
    resumen_turno,
    turno_abierto,
)
from ..ticket import render_ticket

router = APIRouter(prefix="/api", tags=["ventas"])


class ItemIn(BaseModel):
    producto_id: int
    cantidad: float = Field(gt=0)
    nota: str | None = None


class VentaIn(BaseModel):
    items: list[ItemIn]
    metodo_pago_id: int
    descuento: float = Field(ge=0, default=0)
    pago_recibido: float | None = None
    cliente: str | None = None
    notas: str | None = None


class CancelIn(BaseModel):
    motivo: str = Field(min_length=3)


# ------------------------------ POS ------------------------------
@router.get("/pos/catalogo")
def catalogo_pos(user=Depends(current_user), conn=Depends(get_db)):
    disp = disponibilidad_productos(conn)
    productos = [
        dict(r)
        for r in conn.execute(
            """SELECT p.producto_id, p.codigo, p.nombre, p.precio_venta, p.categoria_id, c.nombre AS categoria,
                  c.color FROM dim_producto p LEFT JOIN dim_categoria c ON c.categoria_id=p.categoria_id
           WHERE p.activo=1 AND (c.activo IS NULL OR c.activo=1)
           ORDER BY c.orden, c.nombre, p.nombre"""
        )
    ]
    for p in productos:
        p["disponibles"] = disp.get(p["producto_id"])
    categorias = [
        dict(r)
        for r in conn.execute(
            "SELECT categoria_id, nombre, color FROM dim_categoria WHERE activo=1 ORDER BY orden, nombre"
        )
    ]
    metodos = [dict(r) for r in conn.execute("SELECT * FROM dim_metodo_pago WHERE activo=1 ORDER BY metodo_pago_id")]
    cfg = get_config(conn)
    return {
        "productos": productos,
        "categorias": categorias,
        "metodos": metodos,
        "turno": turno_abierto(conn),
        "permitir_stock_negativo": cfg.get("permitir_stock_negativo") == "1",
        "imprimir_auto": cfg.get("imprimir_auto") == "1",
    }


@router.post("/ventas")
def nueva_venta(data: VentaIn, user=Depends(current_user), conn=Depends(get_db)):
    try:
        conn.execute("BEGIN IMMEDIATE")
        vid = registrar_venta(
            conn,
            user["usuario_id"],
            [i.model_dump() for i in data.items],
            data.metodo_pago_id,
            data.descuento,
            data.pago_recibido,
            data.cliente,
            data.notas,
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return detalle_venta(conn, vid)


@router.get("/ventas")
def listar_ventas(
    desde: str | None = None,
    hasta: str | None = None,
    estado: str | None = None,
    usuario_id: int | None = None,
    turno_id: int | None = None,
    buscar: str | None = None,
    user=Depends(current_user),
    conn=Depends(get_db),
):
    where, params = [], []
    if user["rol"] != "ADMIN":  # un cajero sólo ve el turno actual
        t = turno_abierto(conn)
        where.append("v.turno_id=?")
        params.append(t["turno_id"] if t else -1)
    if desde:
        where.append("date(v.fecha_hora) >= ?")
        params.append(desde)
    if hasta:
        where.append("date(v.fecha_hora) <= ?")
        params.append(hasta)
    if estado:
        where.append("v.estado=?")
        params.append(estado)
    if usuario_id:
        where.append("v.usuario_id=?")
        params.append(usuario_id)
    if turno_id:
        where.append("v.turno_id=?")
        params.append(turno_id)
    if buscar:
        where.append("(v.folio LIKE ? OR v.cliente LIKE ? OR v.mesa LIKE ?)")
        params += [f"%{buscar}%"] * 3
    rows = [
        dict(r)
        for r in conn.execute(
            f"""SELECT v.venta_id, v.folio, v.mesa, v.fecha_hora, v.total, v.descuento, v.costo_total, v.estado, v.cliente,
                   v.turno_id, u.nombre AS usuario, m.nombre AS metodo_pago,
                   (SELECT SUM(cantidad) FROM fact_ventas f WHERE f.venta_id=v.venta_id) AS articulos
            FROM ventas v JOIN dim_usuario u ON u.usuario_id=v.usuario_id
            JOIN dim_metodo_pago m ON m.metodo_pago_id=v.metodo_pago_id
            {"WHERE " + " AND ".join(where) if where else ""}
            ORDER BY v.venta_id DESC LIMIT 1000""",
            params,
        )
    ]
    return rows


@router.get("/ventas/{vid}")
def ver_venta(vid: int, user=Depends(current_user), conn=Depends(get_db)):
    return detalle_venta(conn, vid)


@router.post("/ventas/{vid}/cancelar")
def cancelar(vid: int, data: CancelIn, user=Depends(require_admin), conn=Depends(get_db)):
    try:
        conn.execute("BEGIN IMMEDIATE")
        cancelar_venta(conn, vid, user["usuario_id"], data.motivo)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return detalle_venta(conn, vid)


@router.get("/ventas/{vid}/ticket", response_class=HTMLResponse)
def ticket(vid: int, reimpresion: bool = False, user=Depends(current_user), conn=Depends(get_db)):
    v = detalle_venta(conn, vid)
    if reimpresion:
        with conn:
            audit(conn, user["usuario_id"], "REIMPRESION_TICKET", "ventas", vid, v["folio"])
    return HTMLResponse(render_ticket(v, get_config(conn), reimpresion))


# ------------------------------ TURNOS / CORTE DE CAJA ------------------------------
class AbrirTurnoIn(BaseModel):
    fondo_inicial: float = Field(ge=0, default=0)
    notas: str | None = None


class MovCajaIn(BaseModel):
    tipo: str  # INGRESO | RETIRO
    monto: float = Field(gt=0)
    concepto: str = Field(min_length=2)


class CerrarTurnoIn(BaseModel):
    efectivo_contado: float = Field(ge=0)
    notas: str | None = None


@router.get("/turno/actual")
def turno_actual(user=Depends(current_user), conn=Depends(get_db)):
    t = turno_abierto(conn)
    if not t:
        return {"turno": None}
    return resumen_turno(conn, t["turno_id"])


@router.post("/turno/abrir")
def abrir_turno(data: AbrirTurnoIn, user=Depends(current_user), conn=Depends(get_db)):
    if turno_abierto(conn):
        raise ErrorNegocio("Ya hay un turno abierto")
    with conn:
        cur = conn.execute(
            "INSERT INTO turnos(usuario_apertura_id, apertura, fondo_inicial, notas, estado) VALUES (?,?,?,?,'ABIERTO')",
            (user["usuario_id"], now_str(), data.fondo_inicial, data.notas),
        )
        audit(conn, user["usuario_id"], "ABRIR_TURNO", "turnos", cur.lastrowid, f"Fondo {data.fondo_inicial}")
    return resumen_turno(conn, cur.lastrowid)


@router.post("/turno/movimiento")
def movimiento_caja(data: MovCajaIn, user=Depends(current_user), conn=Depends(get_db)):
    t = turno_abierto(conn)
    if not t:
        raise ErrorNegocio("No hay turno abierto")
    tipo = data.tipo.upper()
    if tipo not in ("INGRESO", "RETIRO"):
        raise ErrorNegocio("Tipo inválido")
    with conn:
        conn.execute(
            "INSERT INTO movimientos_caja(turno_id, fecha_hora, tipo, monto, concepto, usuario_id) VALUES (?,?,?,?,?,?)",
            (t["turno_id"], now_str(), tipo, data.monto, data.concepto, user["usuario_id"]),
        )
        audit(conn, user["usuario_id"], f"CAJA_{tipo}", "turnos", t["turno_id"], f"{data.monto} {data.concepto}")
    return resumen_turno(conn, t["turno_id"])


@router.post("/turno/cerrar")
def cerrar_turno(data: CerrarTurnoIn, user=Depends(current_user), conn=Depends(get_db)):
    t = turno_abierto(conn)
    if not t:
        raise ErrorNegocio("No hay turno abierto")
    abiertas = [r["mesa"] for r in conn.execute("SELECT mesa FROM cuentas WHERE estado='ABIERTA' ORDER BY cuenta_id")]
    if abiertas:
        raise ErrorNegocio(
            f"Hay {len(abiertas)} cuenta(s) abierta(s): {', '.join(f'«{m}»' for m in abiertas)}. "
            "Cóbralas o cancélalas antes de cerrar el turno.",
            409,
        )
    res = resumen_turno(conn, t["turno_id"])
    esperado = res["efectivo_esperado"]
    dif = round(data.efectivo_contado - esperado, 2)
    with conn:
        conn.execute(
            """UPDATE turnos SET estado='CERRADO', cierre=?, usuario_cierre_id=?, efectivo_esperado=?, efectivo_contado=?,
                   diferencia=?, notas=COALESCE(notas,'') || ? WHERE turno_id=?""",
            (
                now_str(),
                user["usuario_id"],
                esperado,
                data.efectivo_contado,
                dif,
                (" | Cierre: " + data.notas) if data.notas else "",
                t["turno_id"],
            ),
        )
        audit(
            conn,
            user["usuario_id"],
            "CERRAR_TURNO",
            "turnos",
            t["turno_id"],
            f"Esperado {esperado}, contado {data.efectivo_contado}, diferencia {dif}",
        )
    return resumen_turno(conn, t["turno_id"])


@router.get("/turnos")
def listar_turnos(user=Depends(require_admin), conn=Depends(get_db)):
    return [
        dict(r)
        for r in conn.execute(
            """SELECT t.*, ua.nombre AS usuario_apertura, uc.nombre AS usuario_cierre,
                  (SELECT COUNT(*) FROM ventas v WHERE v.turno_id=t.turno_id AND v.estado='PAGADA') AS tickets,
                  (SELECT COALESCE(SUM(total),0) FROM ventas v WHERE v.turno_id=t.turno_id AND v.estado='PAGADA') AS total_ventas
           FROM turnos t JOIN dim_usuario ua ON ua.usuario_id=t.usuario_apertura_id
           LEFT JOIN dim_usuario uc ON uc.usuario_id=t.usuario_cierre_id
           ORDER BY t.turno_id DESC LIMIT 300"""
        )
    ]


@router.get("/turnos/{tid}")
def ver_turno(tid: int, user=Depends(require_admin), conn=Depends(get_db)):
    return resumen_turno(conn, tid)


@router.get("/turnos/{tid}/corte", response_class=HTMLResponse)
def imprimir_corte(tid: int, user=Depends(current_user), conn=Depends(get_db)):
    r = resumen_turno(conn, tid)
    cfg = get_config(conn)
    t = r["turno"]
    ancho = "58mm" if cfg.get("ancho_ticket") == "58" else "80mm"
    usuarios = {u["usuario_id"]: u["nombre"] for u in conn.execute("SELECT usuario_id, nombre FROM dim_usuario")}

    def m(x):
        return f"${(x or 0):,.2f}"

    metodos = "".join(
        f"<tr><td>{x['metodo']} ({x['tickets']})</td><td class=r>{m(x['total'])}</td></tr>" for x in r["por_metodo"]
    )
    movs = "".join(
        f"<tr><td>{x['tipo'].title()}: {escape(x['concepto'])}</td><td class=r>{m(x['monto'])}</td></tr>"
        for x in r["movimientos_caja"]
    )
    html = f"""<!doctype html><html><head><meta charset=utf-8><style>
    @page {{ size:{ancho} auto; margin:0 }} body{{width:{ancho};margin:0;padding:3mm;font:12px Consolas,monospace}}
    table{{width:100%;border-collapse:collapse}} .r{{text-align:right}} hr{{border:0;border-top:1px dashed #000}}
    h1{{font-size:15px;text-align:center;margin:0}} b{{font-size:13px}}</style></head><body>
    <h1>{escape(cfg.get("nombre_negocio", ""))}</h1><div style="text-align:center">CORTE DE CAJA · Turno #{t["turno_id"]}</div><hr>
    Apertura: {t["apertura"]} ({usuarios.get(t["usuario_apertura_id"], "")})<br>
    Cierre: {t["cierre"] or "ABIERTO"} {("(" + usuarios.get(t["usuario_cierre_id"], "") + ")") if t["usuario_cierre_id"] else ""}<hr>
    <table><tr><td>Tickets</td><td class=r>{r["tickets"]}</td></tr>
    <tr><td><b>Total ventas</b></td><td class=r><b>{m(r["total_ventas"])}</b></td></tr>
    <tr><td>Descuentos</td><td class=r>{m(r["descuentos"])}</td></tr>
    <tr><td>Canceladas ({r["canceladas"]})</td><td class=r>{m(r["total_canceladas"])}</td></tr></table><hr>
    <table>{metodos}</table><hr><table>
    <tr><td>Fondo inicial</td><td class=r>{m(t["fondo_inicial"])}</td></tr>
    <tr><td>+ Ventas efectivo</td><td class=r>{m(r["efectivo_ventas"])}</td></tr>
    <tr><td>+ Ingresos caja</td><td class=r>{m(r["ingresos_caja"])}</td></tr>
    <tr><td>- Retiros caja</td><td class=r>{m(r["retiros_caja"])}</td></tr>
    <tr><td><b>Efectivo esperado</b></td><td class=r><b>{m(r["efectivo_esperado"])}</b></td></tr>
    <tr><td>Efectivo contado</td><td class=r>{m(t["efectivo_contado"]) if t["efectivo_contado"] is not None else "-"}</td></tr>
    <tr><td><b>Diferencia</b></td><td class=r><b>{m(t["diferencia"]) if t["diferencia"] is not None else "-"}</b></td></tr>
    </table>{("<hr><table>" + movs + "</table>") if movs else ""}<hr><br><br>
    Firma: ______________________</body></html>"""
    return HTMLResponse(html)
