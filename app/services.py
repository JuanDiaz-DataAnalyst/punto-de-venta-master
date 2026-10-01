"""Reglas de negocio: ventas con backflush, inventario (costo promedio ponderado), turnos."""

import calendar
import math
import sqlite3
from collections import defaultdict
from datetime import date, datetime, timedelta

from .db import audit, ensure_fecha, get_config, now_str


class ErrorNegocio(Exception):
    def __init__(self, mensaje: str, status: int = 400, datos=None):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.status = status
        self.datos = datos


def r2(x: float) -> float:
    return round(float(x) + 0.0, 2)


def r4(x: float) -> float:
    return round(float(x) + 0.0, 4)


def _fid(conn, fecha_hora: str) -> int:
    return ensure_fecha(conn, datetime.strptime(fecha_hora[:10], "%Y-%m-%d").date())


def siguiente_folio(conn: sqlite3.Connection) -> str:
    """Folio único y consecutivo, compartido por cuentas abiertas y ventas directas.

    Debe llamarse dentro de una transacción de escritura (BEGIN IMMEDIATE / `with conn:`).
    Un folio nunca se reutiliza, aunque la cuenta se cancele.
    """
    row = conn.execute("SELECT valor FROM config WHERE clave='folio_consecutivo'").fetchone()
    actual = int(row["valor"]) if row else conn.execute("SELECT COALESCE(MAX(venta_id),0) FROM ventas").fetchone()[0]
    nuevo = actual + 1
    conn.execute("INSERT OR REPLACE INTO config(clave, valor) VALUES ('folio_consecutivo', ?)", (str(nuevo),))
    return f"{get_config(conn).get('folio_prefijo', 'V-')}{nuevo:06d}"


# ============================ INVENTARIO ============================
def mover_inventario(
    conn: sqlite3.Connection,
    insumo_id: int,
    cantidad: float,
    tipo: str,
    *,
    costo_unitario: float | None = None,
    referencia_tipo: str | None = None,
    referencia_id: int | None = None,
    motivo: str | None = None,
    usuario_id: int | None = None,
    fecha_hora: str | None = None,
) -> dict:
    """Registra un movimiento de kardex y actualiza stock y costo promedio.

    cantidad > 0 entra, cantidad < 0 sale. Las entradas con costo (ENTRADA, INICIAL,
    CANCELACION) recalculan el costo promedio ponderado.
    """
    fecha_hora = fecha_hora or now_str()
    ins = conn.execute("SELECT stock_actual, costo_promedio FROM dim_insumo WHERE insumo_id=?", (insumo_id,)).fetchone()
    if not ins:
        raise ErrorNegocio(f"Insumo {insumo_id} no existe", 404)
    stock, costo_prom = ins["stock_actual"], ins["costo_promedio"]
    nuevo_costo = costo_prom
    if cantidad > 0 and costo_unitario is not None and tipo in ("ENTRADA", "INICIAL", "CANCELACION"):
        base = max(stock, 0.0)
        nuevo_costo = (
            (base * costo_prom + cantidad * costo_unitario) / (base + cantidad)
            if (base + cantidad) > 0
            else costo_unitario
        )
        cu = costo_unitario
    else:
        cu = costo_prom
    nuevo_stock = r4(stock + cantidad)
    conn.execute(
        "UPDATE dim_insumo SET stock_actual=?, costo_promedio=?, actualizado_en=? WHERE insumo_id=?",
        (nuevo_stock, r4(nuevo_costo), fecha_hora, insumo_id),
    )
    conn.execute(
        """INSERT INTO fact_movimientos_inventario(fecha_hora, fecha_id, insumo_id, tipo, cantidad,
               costo_unitario, costo_total, stock_resultante, referencia_tipo, referencia_id, motivo, usuario_id)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            fecha_hora,
            _fid(conn, fecha_hora),
            insumo_id,
            tipo,
            r4(cantidad),
            r4(cu),
            r2(cantidad * cu),
            nuevo_stock,
            referencia_tipo,
            referencia_id,
            motivo,
            usuario_id,
        ),
    )
    return {"stock": nuevo_stock, "costo_unitario": cu}


def registrar_entrada(
    conn,
    usuario_id: int,
    lineas: list[dict],
    proveedor_id=None,
    factura=None,
    notas=None,
    fecha_hora: str | None = None,
) -> int:
    if not lineas:
        raise ErrorNegocio("La entrada no tiene renglones")
    fecha_hora = fecha_hora or now_str()
    total = sum(float(ln["cantidad"]) * float(ln["costo_unitario"]) for ln in lineas)
    cur = conn.execute(
        "INSERT INTO entradas_inventario(fecha_hora, proveedor_id, factura, notas, usuario_id, total) VALUES (?,?,?,?,?,?)",
        (fecha_hora, proveedor_id, factura, notas, usuario_id, r2(total)),
    )
    entrada_id = cur.lastrowid
    for ln in lineas:
        cant = float(ln["cantidad"])
        costo = float(ln["costo_unitario"])
        if cant <= 0 or costo < 0:
            raise ErrorNegocio("Cantidades deben ser mayores a 0 y costos no negativos")
        mover_inventario(
            conn,
            int(ln["insumo_id"]),
            cant,
            "ENTRADA",
            costo_unitario=costo,
            referencia_tipo="ENTRADA",
            referencia_id=entrada_id,
            motivo=factura,
            usuario_id=usuario_id,
            fecha_hora=fecha_hora,
        )
    audit(
        conn,
        usuario_id,
        "ENTRADA_INVENTARIO",
        "entradas_inventario",
        entrada_id,
        f"{len(lineas)} renglones, total {r2(total)}",
        fecha_hora,
    )
    return entrada_id


def ajustar_inventario(
    conn, usuario_id: int, insumo_id: int, modo: str, cantidad: float, motivo: str, fecha_hora: str | None = None
) -> dict:
    """modo: CONTEO (fija el stock al conteo físico), SUMAR o RESTAR."""
    ins = conn.execute("SELECT nombre, stock_actual FROM dim_insumo WHERE insumo_id=?", (insumo_id,)).fetchone()
    if not ins:
        raise ErrorNegocio("Insumo no encontrado", 404)
    cantidad = float(cantidad)
    if modo == "CONTEO":
        if cantidad < 0:
            raise ErrorNegocio("El conteo no puede ser negativo")
        delta = cantidad - ins["stock_actual"]
    elif modo == "SUMAR":
        delta = abs(cantidad)
    elif modo == "RESTAR":
        delta = -abs(cantidad)
    else:
        raise ErrorNegocio("Modo de ajuste inválido")
    if abs(delta) < 1e-9:
        raise ErrorNegocio("El ajuste no cambia el inventario")
    res = mover_inventario(
        conn,
        insumo_id,
        delta,
        "AJUSTE",
        referencia_tipo="AJUSTE",
        motivo=f"{modo}: {motivo}",
        usuario_id=usuario_id,
        fecha_hora=fecha_hora,
    )
    audit(
        conn,
        usuario_id,
        "AJUSTE_INVENTARIO",
        "dim_insumo",
        insumo_id,
        f"{ins['nombre']}: {modo} {cantidad} (delta {r4(delta)}) - {motivo}",
        fecha_hora,
    )
    return {"delta": r4(delta), **res}


def disponibilidad_productos(conn) -> dict[int, int | None]:
    """Porciones que se pueden preparar con el inventario actual (None = sin receta)."""
    disp: dict[int, float] = {}
    for r in conn.execute(
        """SELECT r.producto_id, r.cantidad, i.stock_actual FROM dim_receta r
           JOIN dim_insumo i ON i.insumo_id = r.insumo_id"""
    ):
        porc = math.floor(max(r["stock_actual"], 0) / r["cantidad"] + 1e-9)
        disp[r["producto_id"]] = min(disp.get(r["producto_id"], porc), porc)
    return {k: int(v) for k, v in disp.items()}


# ============================ TURNOS ============================
def turno_abierto(conn):
    row = conn.execute(
        """SELECT t.*, u.nombre AS usuario_apertura FROM turnos t
           JOIN dim_usuario u ON u.usuario_id = t.usuario_apertura_id
           WHERE t.estado='ABIERTO' ORDER BY t.turno_id DESC LIMIT 1"""
    ).fetchone()
    return dict(row) if row else None


def resumen_turno(conn, turno_id: int) -> dict:
    t = conn.execute("SELECT * FROM turnos WHERE turno_id=?", (turno_id,)).fetchone()
    if not t:
        raise ErrorNegocio("Turno no encontrado", 404)
    por_metodo = [
        dict(r)
        for r in conn.execute(
            """SELECT m.nombre AS metodo, m.es_efectivo, COUNT(v.venta_id) AS tickets, COALESCE(SUM(v.total),0) AS total
           FROM dim_metodo_pago m
           LEFT JOIN ventas v ON v.metodo_pago_id = m.metodo_pago_id AND v.turno_id=? AND v.estado='PAGADA'
           GROUP BY m.metodo_pago_id ORDER BY m.metodo_pago_id""",
            (turno_id,),
        )
    ]
    tot = conn.execute(
        """SELECT COUNT(*) n, COALESCE(SUM(total),0) total, COALESCE(SUM(descuento),0) descuentos,
                  COALESCE(SUM(costo_total),0) costo
           FROM ventas WHERE turno_id=? AND estado='PAGADA'""",
        (turno_id,),
    ).fetchone()
    canc = conn.execute(
        "SELECT COUNT(*) n, COALESCE(SUM(total),0) total FROM ventas WHERE turno_id=? AND estado='CANCELADA'",
        (turno_id,),
    ).fetchone()
    movs = [
        dict(r)
        for r in conn.execute(
            """SELECT mc.*, u.nombre AS usuario FROM movimientos_caja mc JOIN dim_usuario u ON u.usuario_id=mc.usuario_id
           WHERE turno_id=? ORDER BY fecha_hora""",
            (turno_id,),
        )
    ]
    ingresos = sum(m["monto"] for m in movs if m["tipo"] == "INGRESO")
    retiros = sum(m["monto"] for m in movs if m["tipo"] == "RETIRO")
    efectivo_ventas = sum(m["total"] for m in por_metodo if m["es_efectivo"])
    esperado = t["fondo_inicial"] + efectivo_ventas + ingresos - retiros
    return {
        "turno": dict(t),
        "por_metodo": por_metodo,
        "tickets": tot["n"],
        "total_ventas": r2(tot["total"]),
        "descuentos": r2(tot["descuentos"]),
        "costo": r2(tot["costo"]),
        "canceladas": canc["n"],
        "total_canceladas": r2(canc["total"]),
        "movimientos_caja": movs,
        "ingresos_caja": r2(ingresos),
        "retiros_caja": r2(retiros),
        "efectivo_ventas": r2(efectivo_ventas),
        "efectivo_esperado": r2(esperado),
    }


# ============================ VENTAS ============================
def registrar_venta(
    conn,
    usuario_id: int,
    items: list[dict],
    metodo_pago_id: int,
    descuento: float = 0,
    pago_recibido: float | None = None,
    cliente: str | None = None,
    notas: str | None = None,
    fecha_hora: str | None = None,
    turno_id: int | None = None,
    requiere_turno: bool = True,
    folio: str | None = None,
    mesa: str | None = None,
) -> int:
    if not items:
        raise ErrorNegocio("El ticket está vacío")
    cfg = get_config(conn)
    fecha_hora = fecha_hora or now_str()

    if requiere_turno:
        t = turno_abierto(conn)
        if not t:
            raise ErrorNegocio("No hay un turno de caja abierto. Abre la caja antes de vender.", 409)
        turno_id = t["turno_id"]

    metodo = conn.execute(
        "SELECT * FROM dim_metodo_pago WHERE metodo_pago_id=? AND activo=1", (metodo_pago_id,)
    ).fetchone()
    if not metodo:
        raise ErrorNegocio("Método de pago inválido")

    # --- consolidar renglones y leer precios desde la BD (no se confía en el cliente)
    lineas = []
    for it in items:
        cant = float(it.get("cantidad", 0))
        if cant <= 0:
            raise ErrorNegocio("Cantidad inválida en el ticket")
        p = conn.execute(
            "SELECT * FROM dim_producto WHERE producto_id=? AND activo=1", (int(it["producto_id"]),)
        ).fetchone()
        if not p:
            raise ErrorNegocio(f"Producto {it['producto_id']} no disponible")
        receta = conn.execute(
            """SELECT r.insumo_id, r.cantidad, i.costo_promedio, i.stock_actual, i.nombre, i.unidad
               FROM dim_receta r JOIN dim_insumo i ON i.insumo_id=r.insumo_id WHERE r.producto_id=?""",
            (p["producto_id"],),
        ).fetchall()
        lineas.append({"p": p, "cant": cant, "receta": receta, "nota": it.get("nota")})

    # --- validar existencias (consumo agregado por insumo)
    requerido = defaultdict(float)
    info_ins = {}
    for ln in lineas:
        for r in ln["receta"]:
            requerido[r["insumo_id"]] += r["cantidad"] * ln["cant"]
            info_ins[r["insumo_id"]] = r
    faltantes = [
        {
            "insumo": info_ins[i]["nombre"],
            "unidad": info_ins[i]["unidad"],
            "requerido": r4(q),
            "disponible": r4(info_ins[i]["stock_actual"]),
        }
        for i, q in requerido.items()
        if q > info_ins[i]["stock_actual"] + 1e-9
    ]
    if faltantes and cfg.get("permitir_stock_negativo", "1") != "1":
        raise ErrorNegocio("Inventario insuficiente para completar la venta", 409, faltantes)

    subtotal = r2(sum(ln["p"]["precio_venta"] * ln["cant"] for ln in lineas))
    descuento = r2(max(0.0, min(float(descuento or 0), subtotal)))
    total = r2(subtotal - descuento)
    cambio = None
    if metodo["es_efectivo"]:
        if pago_recibido is None:
            pago_recibido = total
        if float(pago_recibido) + 1e-9 < total:
            raise ErrorNegocio("El pago recibido es menor al total")
        cambio = r2(float(pago_recibido) - total)
    else:
        pago_recibido = total
        cambio = 0.0

    fid = _fid(conn, fecha_hora)
    folio = folio or siguiente_folio(conn)  # las ventas que vienen de una cuenta conservan su folio
    cur = conn.execute(
        """INSERT INTO ventas(folio, fecha_hora, fecha_id, usuario_id, turno_id, metodo_pago_id, subtotal,
               descuento, total, pago_recibido, cambio, costo_total, estado, cliente, notas, mesa)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,0,'PAGADA',?,?,?)""",
        (
            folio,
            fecha_hora,
            fid,
            usuario_id,
            turno_id,
            metodo_pago_id,
            subtotal,
            descuento,
            total,
            r2(pago_recibido),
            cambio,
            cliente,
            notas,
            mesa,
        ),
    )
    venta_id = cur.lastrowid
    hora = int(fecha_hora[11:13])

    # --- renglones de hechos + backflush
    desc_restante = descuento
    costo_venta = 0.0
    for idx, ln in enumerate(lineas):
        p, cant = ln["p"], ln["cant"]
        bruto = r2(p["precio_venta"] * cant)
        if idx == len(lineas) - 1:
            d_linea = r2(desc_restante)
        else:
            d_linea = r2(descuento * bruto / subtotal) if subtotal else 0.0
            desc_restante = r2(desc_restante - d_linea)
        neto = r2(bruto - d_linea)
        costo_linea = 0.0
        for r in ln["receta"]:
            consumo = r["cantidad"] * cant
            mv = mover_inventario(
                conn,
                r["insumo_id"],
                -consumo,
                "BACKFLUSH",
                referencia_tipo="VENTA",
                referencia_id=venta_id,
                motivo=f"{folio} {p['nombre']}",
                usuario_id=usuario_id,
                fecha_hora=fecha_hora,
            )
            costo_linea += consumo * mv["costo_unitario"]
        costo_linea = r2(costo_linea)
        costo_venta += costo_linea
        conn.execute(
            """INSERT INTO fact_ventas(venta_id, fecha_id, fecha_hora, hora, producto_id, categoria_id, usuario_id,
                   metodo_pago_id, turno_id, cantidad, precio_unitario, importe_bruto, descuento, importe_neto,
                   costo_unitario, costo_total, margen, nota)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                venta_id,
                fid,
                fecha_hora,
                hora,
                p["producto_id"],
                p["categoria_id"],
                usuario_id,
                metodo_pago_id,
                turno_id,
                cant,
                p["precio_venta"],
                bruto,
                d_linea,
                neto,
                r4(costo_linea / cant),
                costo_linea,
                r2(neto - costo_linea),
                ln["nota"],
            ),
        )
    conn.execute("UPDATE ventas SET costo_total=? WHERE venta_id=?", (r2(costo_venta), venta_id))
    audit(conn, usuario_id, "VENTA", "ventas", venta_id, f"{folio} total {total} ({metodo['nombre']})", fecha_hora)
    return venta_id


def cancelar_venta(conn, venta_id: int, usuario_id: int, motivo: str, fecha_hora: str | None = None) -> None:
    v = conn.execute("SELECT * FROM ventas WHERE venta_id=?", (venta_id,)).fetchone()
    if not v:
        raise ErrorNegocio("Venta no encontrada", 404)
    if v["estado"] == "CANCELADA":
        raise ErrorNegocio("La venta ya estaba cancelada")
    if not motivo or not motivo.strip():
        raise ErrorNegocio("Indica el motivo de la cancelación")
    ahora = fecha_hora or now_str()
    # Regresar al inventario exactamente lo que consumió, a su costo original
    for m in conn.execute(
        """SELECT insumo_id, cantidad, costo_unitario FROM fact_movimientos_inventario
           WHERE referencia_tipo='VENTA' AND referencia_id=? AND tipo='BACKFLUSH'""",
        (venta_id,),
    ).fetchall():
        mover_inventario(
            conn,
            m["insumo_id"],
            -m["cantidad"],
            "CANCELACION",
            costo_unitario=m["costo_unitario"],
            referencia_tipo="VENTA",
            referencia_id=venta_id,
            motivo=f"Cancelación {v['folio']}",
            usuario_id=usuario_id,
            fecha_hora=ahora,
        )
    conn.execute(
        """UPDATE ventas SET estado='CANCELADA', cancelada_en=?, cancelada_por=?, motivo_cancelacion=?
                    WHERE venta_id=?""",
        (ahora, usuario_id, motivo.strip(), venta_id),
    )
    audit(conn, usuario_id, "CANCELAR_VENTA", "ventas", venta_id, f"{v['folio']} - {motivo}", ahora)


def detalle_venta(conn, venta_id: int) -> dict:
    v = conn.execute(
        """SELECT v.*, u.nombre AS usuario, m.nombre AS metodo_pago, m.es_efectivo, uc.nombre AS cancelada_por_nombre
           FROM ventas v JOIN dim_usuario u ON u.usuario_id=v.usuario_id
           JOIN dim_metodo_pago m ON m.metodo_pago_id=v.metodo_pago_id
           LEFT JOIN dim_usuario uc ON uc.usuario_id=v.cancelada_por
           WHERE v.venta_id=?""",
        (venta_id,),
    ).fetchone()
    if not v:
        raise ErrorNegocio("Venta no encontrada", 404)
    lineas = [
        dict(r)
        for r in conn.execute(
            """SELECT f.*, p.nombre AS producto FROM fact_ventas f JOIN dim_producto p ON p.producto_id=f.producto_id
           WHERE f.venta_id=? ORDER BY f.linea_id""",
            (venta_id,),
        )
    ]
    return {**dict(v), "lineas": lineas}


# ============================ CUENTAS ABIERTAS (MESAS) ============================
def _descuento_cuenta(tipo: str, valor: float, subtotal: float) -> float:
    d = subtotal * valor / 100 if tipo == "%" else valor
    return r2(max(0.0, min(d, subtotal)))


def _cuenta(conn, cuenta_id: int, *, abierta: bool = True):
    c = conn.execute("SELECT * FROM cuentas WHERE cuenta_id=?", (cuenta_id,)).fetchone()
    if not c:
        raise ErrorNegocio("Cuenta no encontrada", 404)
    if abierta and c["estado"] != "ABIERTA":
        raise ErrorNegocio("Esa cuenta ya no está abierta", 409)
    return c


def detalle_cuenta(conn, cuenta_id: int) -> dict:
    c = _cuenta(conn, cuenta_id, abierta=False)
    items = [
        dict(r)
        for r in conn.execute(
            """SELECT i.item_id, i.producto_id, p.nombre, p.precio_venta AS precio, p.activo,
                      i.cantidad, i.nota, i.agregado_en
               FROM cuenta_items i JOIN dim_producto p ON p.producto_id = i.producto_id
               WHERE i.cuenta_id=? ORDER BY i.item_id""",
            (cuenta_id,),
        )
    ]
    subtotal = r2(sum(i["precio"] * i["cantidad"] for i in items))
    descuento = _descuento_cuenta(c["descuento_tipo"], c["descuento_valor"], subtotal)
    usuario = conn.execute("SELECT nombre FROM dim_usuario WHERE usuario_id=?", (c["usuario_id"],)).fetchone()
    return {
        **dict(c),
        "usuario": usuario["nombre"] if usuario else "",
        "items": items,
        "articulos": sum(i["cantidad"] for i in items),
        "subtotal": subtotal,
        "descuento": descuento,
        "total": r2(subtotal - descuento),
    }


def listar_cuentas_abiertas(conn) -> list[dict]:
    ids = [r[0] for r in conn.execute("SELECT cuenta_id FROM cuentas WHERE estado='ABIERTA' ORDER BY cuenta_id")]
    return [detalle_cuenta(conn, i) for i in ids]


def _validar_mesa(conn, mesa: str | None, excluir: int | None = None) -> str:
    mesa = (mesa or "").strip()
    if not mesa:
        raise ErrorNegocio("Indica el número o nombre de la mesa")
    if len(mesa) > 30:
        raise ErrorNegocio("El nombre de la mesa es demasiado largo (máximo 30 caracteres)")
    dup = conn.execute(
        "SELECT folio FROM cuentas WHERE estado='ABIERTA' AND mesa=? COLLATE NOCASE AND cuenta_id != ?",
        (mesa, excluir or -1),
    ).fetchone()
    if dup:
        raise ErrorNegocio(f"La mesa «{mesa}» ya tiene una cuenta abierta ({dup['folio']})", 409)
    return mesa


def abrir_cuenta(conn, usuario_id: int, mesa: str, fecha_hora: str | None = None) -> int:
    """Abre un ticket independiente para una mesa y le asigna su folio único."""
    if not turno_abierto(conn):
        raise ErrorNegocio("No hay un turno de caja abierto. Abre la caja antes de abrir cuentas.", 409)
    mesa = _validar_mesa(conn, mesa)
    fecha_hora = fecha_hora or now_str()
    folio = siguiente_folio(conn)
    cur = conn.execute(
        "INSERT INTO cuentas(folio, mesa, abierta_en, usuario_id) VALUES (?,?,?,?)",
        (folio, mesa, fecha_hora, usuario_id),
    )
    audit(conn, usuario_id, "ABRIR_CUENTA", "cuentas", cur.lastrowid, f"{folio} mesa {mesa}", fecha_hora)
    return cur.lastrowid


def agregar_item(
    conn, cuenta_id: int, producto_id: int, cantidad: float = 1, nota: str | None = None, fecha_hora: str | None = None
) -> None:
    """Suma un producto a la cuenta (si ya hay uno igual y con la misma nota, aumenta la cantidad)."""
    _cuenta(conn, cuenta_id)
    if cantidad <= 0:
        raise ErrorNegocio("Cantidad inválida")
    if not conn.execute("SELECT 1 FROM dim_producto WHERE producto_id=? AND activo=1", (producto_id,)).fetchone():
        raise ErrorNegocio(f"Producto {producto_id} no disponible")
    nota = (nota or "").strip() or None
    existente = conn.execute(
        "SELECT item_id FROM cuenta_items WHERE cuenta_id=? AND producto_id=? AND COALESCE(nota,'')=COALESCE(?,'')",
        (cuenta_id, producto_id, nota),
    ).fetchone()
    if existente:
        conn.execute(
            "UPDATE cuenta_items SET cantidad = cantidad + ? WHERE item_id=?", (cantidad, existente["item_id"])
        )
    else:
        conn.execute(
            "INSERT INTO cuenta_items(cuenta_id, producto_id, cantidad, nota, agregado_en) VALUES (?,?,?,?,?)",
            (cuenta_id, producto_id, cantidad, nota, fecha_hora or now_str()),
        )


def modificar_item(
    conn,
    cuenta_id: int,
    item_id: int,
    cantidad: float | None = None,
    nota: str | None = None,
    separar: bool = False,
) -> None:
    """Cambia cantidad y/o nota de un renglón. cantidad <= 0 lo quita.

    nota: None = sin cambio, "" = borrar nota. Con separar=True y varias piezas, la nota
    se aplica solo a una pieza (que pasa a un renglón nuevo).
    """
    _cuenta(conn, cuenta_id)
    it = conn.execute("SELECT * FROM cuenta_items WHERE item_id=? AND cuenta_id=?", (item_id, cuenta_id)).fetchone()
    if not it:
        raise ErrorNegocio("Renglón no encontrado", 404)
    cant = it["cantidad"] if cantidad is None else float(cantidad)
    if cant <= 0:
        conn.execute("DELETE FROM cuenta_items WHERE item_id=?", (item_id,))
        return
    if nota is not None:
        nota = nota.strip() or None
        if separar and cant > 1 and nota and nota != it["nota"]:
            conn.execute("UPDATE cuenta_items SET cantidad=? WHERE item_id=?", (cant - 1, item_id))
            conn.execute(
                "INSERT INTO cuenta_items(cuenta_id, producto_id, cantidad, nota, agregado_en) VALUES (?,?,?,?,?)",
                (cuenta_id, it["producto_id"], 1, nota, now_str()),
            )
            return
        conn.execute("UPDATE cuenta_items SET nota=? WHERE item_id=?", (nota, item_id))
    conn.execute("UPDATE cuenta_items SET cantidad=? WHERE item_id=?", (cant, item_id))


def actualizar_cuenta(
    conn,
    cuenta_id: int,
    usuario_id: int,
    mesa: str | None = None,
    descuento_tipo: str | None = None,
    descuento_valor: float | None = None,
) -> None:
    c = _cuenta(conn, cuenta_id)
    if mesa is not None:
        nueva = _validar_mesa(conn, mesa, excluir=cuenta_id)
        if nueva != c["mesa"]:
            conn.execute("UPDATE cuentas SET mesa=? WHERE cuenta_id=?", (nueva, cuenta_id))
            audit(conn, usuario_id, "CAMBIAR_MESA", "cuentas", cuenta_id, f"{c['folio']}: {c['mesa']} -> {nueva}")
    if descuento_tipo is not None or descuento_valor is not None:
        tipo = descuento_tipo or c["descuento_tipo"]
        valor = c["descuento_valor"] if descuento_valor is None else float(descuento_valor)
        if tipo not in ("$", "%") or valor < 0 or (tipo == "%" and valor > 100):
            raise ErrorNegocio("Descuento inválido")
        conn.execute(
            "UPDATE cuentas SET descuento_tipo=?, descuento_valor=? WHERE cuenta_id=?", (tipo, valor, cuenta_id)
        )
        if valor != c["descuento_valor"] or tipo != c["descuento_tipo"]:
            audit(conn, usuario_id, "DESCUENTO_CUENTA", "cuentas", cuenta_id, f"{c['folio']}: {valor}{tipo}")


def cobrar_cuenta(
    conn,
    cuenta_id: int,
    usuario_id: int,
    metodo_pago_id: int,
    pago_recibido: float | None = None,
    cliente: str | None = None,
    notas: str | None = None,
    fecha_hora: str | None = None,
) -> int:
    """Convierte la cuenta en una venta (con el mismo folio): aquí se hace el backflush de inventario."""
    c = _cuenta(conn, cuenta_id)
    det = detalle_cuenta(conn, cuenta_id)
    if not det["items"]:
        raise ErrorNegocio("La cuenta está vacía; agrega productos o cancélala")
    fecha_hora = fecha_hora or now_str()
    venta_id = registrar_venta(
        conn,
        usuario_id,
        [{"producto_id": i["producto_id"], "cantidad": i["cantidad"], "nota": i["nota"]} for i in det["items"]],
        metodo_pago_id,
        det["descuento"],
        pago_recibido,
        cliente,
        notas,
        fecha_hora,
        folio=c["folio"],
        mesa=c["mesa"],
    )
    conn.execute(
        "UPDATE cuentas SET estado='COBRADA', cerrada_en=?, venta_id=? WHERE cuenta_id=?",
        (fecha_hora, venta_id, cuenta_id),
    )
    return venta_id


def cancelar_cuenta(conn, cuenta_id: int, usuario_id: int, motivo: str | None, fecha_hora: str | None = None) -> None:
    """Cancela una cuenta abierta (no hay venta ni movimiento de inventario que revertir)."""
    c = _cuenta(conn, cuenta_id)
    det = detalle_cuenta(conn, cuenta_id)
    motivo = (motivo or "").strip()
    if det["items"] and len(motivo) < 3:
        raise ErrorNegocio("Indica el motivo de la cancelación")
    ahora = fecha_hora or now_str()
    conn.execute(
        "UPDATE cuentas SET estado='CANCELADA', cerrada_en=?, motivo_cancelacion=? WHERE cuenta_id=?",
        (ahora, motivo or None, cuenta_id),
    )
    audit(
        conn,
        usuario_id,
        "CANCELAR_CUENTA",
        "cuentas",
        cuenta_id,
        f"{c['folio']} mesa {c['mesa']}: {det['articulos']:g} artículos, {det['total']} - {motivo or 'sin consumo'}",
        ahora,
    )


# ============================ GASTOS FIJOS ============================
CATEGORIA_NOMINA = "Nómina"
CATEGORIAS_GASTO = [
    CATEGORIA_NOMINA,
    "Renta",
    "Servicios",
    "Mantenimiento",
    "Marketing",
    "Administrativos",
    "Impuestos y permisos",
    "Otros",
]

# Conceptos comunes de un restaurante pequeño (se cargan con monto $0 para que el dueño los capture)
GASTOS_COMUNES = [
    ("Salarios de cocina", CATEGORIA_NOMINA),
    ("Salarios de meseros / servicio", CATEGORIA_NOMINA),
    ("Salario del encargado o administrador", CATEGORIA_NOMINA),
    ("Cargas sociales (IMSS, INFONAVIT, SAR)", CATEGORIA_NOMINA),
    ("Aguinaldo y prestaciones (provisión mensual)", CATEGORIA_NOMINA),
    ("Renta del local", "Renta"),
    ("Electricidad", "Servicios"),
    ("Agua", "Servicios"),
    ("Gas", "Servicios"),
    ("Internet y teléfono", "Servicios"),
    ("Recolección de basura", "Servicios"),
    ("Mantenimiento de equipo y local", "Mantenimiento"),
    ("Limpieza y control de plagas", "Mantenimiento"),
    ("Publicidad y redes sociales", "Marketing"),
    ("Contador", "Administrativos"),
    ("Software y sistemas", "Administrativos"),
    ("Seguros", "Administrativos"),
    ("Licencias y permisos", "Impuestos y permisos"),
    ("Impuestos (predial, ISR)", "Impuestos y permisos"),
]


def _validar_fecha(valor: str | None, campo: str) -> str | None:
    if not valor:
        return None
    try:
        return date.fromisoformat(valor).isoformat()
    except ValueError as e:
        raise ErrorNegocio(f"{campo}: fecha inválida (usa AAAA-MM-DD)") from e


def validar_gasto(
    concepto: str, categoria: str, vigente_desde: str, vigente_hasta: str | None
) -> tuple[str, str, str, str | None]:
    concepto = (concepto or "").strip()
    if not concepto:
        raise ErrorNegocio("Indica el concepto del gasto")
    if categoria not in CATEGORIAS_GASTO:
        raise ErrorNegocio("Categoría de gasto inválida")
    desde = _validar_fecha(vigente_desde, "Vigente desde")
    if not desde:
        raise ErrorNegocio("Indica desde cuándo aplica el gasto")
    hasta = _validar_fecha(vigente_hasta, "Vigente hasta")
    if hasta and hasta < desde:
        raise ErrorNegocio("«Vigente hasta» no puede ser anterior a «Vigente desde»")
    return concepto, categoria, desde, hasta


def prorratear_gastos(conn, desde: date, hasta: date) -> dict:
    """Gastos fijos que corresponden al rango [desde, hasta].

    Cada gasto mensual se reparte en partes iguales entre los días de su mes y se suman solo
    los días en que estuvo vigente; así un rango de 7 días o de 3 meses recibe lo justo.
    """
    gastos = conn.execute("SELECT * FROM gastos_fijos WHERE monto_mensual > 0 ORDER BY categoria, concepto").fetchall()
    dias_mes: dict[tuple[int, int], int] = {}
    diario: dict[str, float] = defaultdict(float)
    detalle = []
    for g in gastos:
        ini = max(desde, date.fromisoformat(g["vigente_desde"]))
        fin = min(hasta, date.fromisoformat(g["vigente_hasta"])) if g["vigente_hasta"] else hasta
        monto = 0.0
        d = ini
        while d <= fin:
            n = dias_mes.setdefault((d.year, d.month), calendar.monthrange(d.year, d.month)[1])
            parte = g["monto_mensual"] / n
            diario[d.isoformat()] += parte
            monto += parte
            d += timedelta(days=1)
        if monto > 0:
            detalle.append(
                {
                    "gasto_id": g["gasto_id"],
                    "concepto": g["concepto"],
                    "categoria": g["categoria"],
                    "monto_mensual": g["monto_mensual"],
                    "monto": r2(monto),
                }
            )
    por_cat: dict[str, float] = defaultdict(float)
    for x in detalle:
        por_cat[x["categoria"]] += x["monto"]
    por_categoria = sorted(({"categoria": c, "monto": r2(m)} for c, m in por_cat.items()), key=lambda x: -x["monto"])
    return {
        "total": r2(sum(por_cat.values())),
        "por_categoria": por_categoria,
        "detalle": sorted(detalle, key=lambda x: -x["monto"]),
        "diario": dict(diario),
        "configurado": bool(gastos),
    }


def resumen_gastos_fijos(conn, hoy: date | None = None) -> dict:
    """Lo que cuesta mantener el negocio abierto un mes, con los gastos vigentes a la fecha."""
    hoy = hoy or date.today()
    vigentes = conn.execute(
        """SELECT categoria, SUM(monto_mensual) AS monto FROM gastos_fijos
           WHERE vigente_desde <= ? AND (vigente_hasta IS NULL OR vigente_hasta >= ?) GROUP BY categoria""",
        (hoy.isoformat(), hoy.isoformat()),
    ).fetchall()
    por_categoria = sorted(
        ({"categoria": r["categoria"], "monto": r2(r["monto"])} for r in vigentes), key=lambda x: -x["monto"]
    )
    total = r2(sum(c["monto"] for c in por_categoria))
    return {
        "total_mensual": total,
        "total_diario": r2(total / calendar.monthrange(hoy.year, hoy.month)[1]),
        "por_categoria": por_categoria,
        "nomina_mensual": next((c["monto"] for c in por_categoria if c["categoria"] == CATEGORIA_NOMINA), 0.0),
    }
