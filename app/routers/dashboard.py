"""Indicadores para el dashboard de administración."""

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException

from ..db import get_db
from ..security import require_admin

router = APIRouter(prefix="/api", tags=["dashboard"])


def _kpis(conn, desde: str, hasta: str) -> dict:
    v = conn.execute(
        """SELECT COUNT(*) tickets, COALESCE(SUM(total),0) ventas, COALESCE(SUM(costo_total),0) costo,
                  COALESCE(SUM(descuento),0) descuentos
           FROM ventas WHERE estado='PAGADA' AND date(fecha_hora) BETWEEN ? AND ?""",
        (desde, hasta),
    ).fetchone()
    u = conn.execute(
        """SELECT COALESCE(SUM(f.cantidad),0) FROM fact_ventas f JOIN ventas v ON v.venta_id=f.venta_id
           WHERE v.estado='PAGADA' AND f.fecha_hora BETWEEN ? AND ?""",
        (desde, hasta + " 23:59:59"),
    ).fetchone()[0]
    c = conn.execute(
        """SELECT COUNT(*) n, COALESCE(SUM(total),0) monto FROM ventas
           WHERE estado='CANCELADA' AND date(fecha_hora) BETWEEN ? AND ?""",
        (desde, hasta),
    ).fetchone()
    ventas, costo = v["ventas"], v["costo"]
    return {
        "ventas": round(ventas, 2),
        "tickets": v["tickets"],
        "costo": round(costo, 2),
        "margen": round(ventas - costo, 2),
        "margen_pct": round((ventas - costo) / ventas, 4) if ventas else 0,
        "ticket_promedio": round(ventas / v["tickets"], 2) if v["tickets"] else 0,
        "unidades": u,
        "descuentos": round(v["descuentos"], 2),
        "canceladas": c["n"],
        "monto_cancelado": round(c["monto"], 2),
    }


@router.get("/dashboard")
def dashboard(desde: str, hasta: str, user=Depends(require_admin), conn=Depends(get_db)):
    try:
        d0, d1 = date.fromisoformat(desde), date.fromisoformat(hasta)
    except ValueError as e:
        raise HTTPException(400, "Fechas inválidas") from e
    if d1 < d0:
        d0, d1 = d1, d0
    desde, hasta = d0.isoformat(), d1.isoformat()
    dias = (d1 - d0).days + 1
    p1 = d0 - timedelta(days=1)
    p0 = p1 - timedelta(days=dias - 1)
    rango = (desde, hasta)
    hasta_ts = hasta + " 23:59:59"

    actual = _kpis(conn, desde, hasta)
    anterior = _kpis(conn, p0.isoformat(), p1.isoformat())

    # agrupar por semana si el rango es largo
    agrupar = "semana" if dias > 120 else "dia"
    if agrupar == "dia":
        serie = [
            dict(r)
            for r in conn.execute(
                """SELECT d.fecha AS periodo, d.nombre_dia,
                      COALESCE(SUM(v.total),0) AS ventas, COALESCE(SUM(v.costo_total),0) AS costo,
                      COUNT(v.venta_id) AS tickets
               FROM dim_fecha d LEFT JOIN ventas v ON v.fecha_id=d.fecha_id AND v.estado='PAGADA'
               WHERE d.fecha BETWEEN ? AND ? GROUP BY d.fecha ORDER BY d.fecha""",
                rango,
            )
        ]
    else:
        serie = [
            dict(r)
            for r in conn.execute(
                """SELECT MIN(d.fecha) AS periodo, '' AS nombre_dia,
                      COALESCE(SUM(v.total),0) AS ventas, COALESCE(SUM(v.costo_total),0) AS costo,
                      COUNT(v.venta_id) AS tickets
               FROM dim_fecha d LEFT JOIN ventas v ON v.fecha_id=d.fecha_id AND v.estado='PAGADA'
               WHERE d.fecha BETWEEN ? AND ? GROUP BY d.anio, d.semana_iso ORDER BY MIN(d.fecha)""",
                rango,
            )
        ]
    for s in serie:
        s["margen"] = round(s["ventas"] - s["costo"], 2)

    por_hora = [
        dict(r)
        for r in conn.execute(
            """SELECT CAST(strftime('%H', fecha_hora) AS INTEGER) AS hora, COUNT(*) tickets, ROUND(SUM(total),2) ventas
           FROM ventas WHERE estado='PAGADA' AND date(fecha_hora) BETWEEN ? AND ?
           GROUP BY hora ORDER BY hora""",
            rango,
        )
    ]

    por_dia_semana = [
        dict(r)
        for r in conn.execute(
            """SELECT d.dia_semana, d.nombre_dia, COUNT(DISTINCT d.fecha) AS dias,
                  COALESCE(SUM(v.total),0) AS ventas, COUNT(v.venta_id) AS tickets
           FROM dim_fecha d LEFT JOIN ventas v ON v.fecha_id=d.fecha_id AND v.estado='PAGADA'
           WHERE d.fecha BETWEEN ? AND ? GROUP BY d.dia_semana ORDER BY d.dia_semana""",
            rango,
        )
    ]
    for r in por_dia_semana:
        r["promedio"] = round(r["ventas"] / r["dias"], 2) if r["dias"] else 0

    productos = [
        dict(r)
        for r in conn.execute(
            """SELECT p.producto_id, p.nombre AS producto, COALESCE(c.nombre,'Sin categoría') AS categoria,
                  SUM(f.cantidad) unidades, ROUND(SUM(f.importe_neto),2) ventas, ROUND(SUM(f.costo_total),2) costo,
                  ROUND(SUM(f.margen),2) margen
           FROM fact_ventas f JOIN ventas v ON v.venta_id=f.venta_id AND v.estado='PAGADA'
           JOIN dim_producto p ON p.producto_id=f.producto_id LEFT JOIN dim_categoria c ON c.categoria_id=f.categoria_id
           WHERE f.fecha_hora BETWEEN ? AND ?
           GROUP BY p.producto_id ORDER BY ventas DESC""",
            (desde, hasta_ts),
        )
    ]
    for p in productos:
        p["margen_pct"] = round(p["margen"] / p["ventas"], 4) if p["ventas"] else 0
        p["margen_unitario"] = round(p["margen"] / p["unidades"], 2) if p["unidades"] else 0

    # Ingeniería de menú (Kasavana & Smith): popularidad vs. margen unitario
    if productos:
        total_u = sum(p["unidades"] for p in productos)
        umbral_pop = (total_u / len(productos)) * 0.7
        margen_prom = sum(p["margen"] for p in productos) / total_u if total_u else 0
        for p in productos:
            alta_pop = p["unidades"] >= umbral_pop
            alto_mg = p["margen_unitario"] >= margen_prom
            p["clase_menu"] = (
                "Estrella"
                if alta_pop and alto_mg
                else "Caballo de batalla"
                if alta_pop
                else "Rompecabezas"
                if alto_mg
                else "Perro"
            )
        menu_ref = {"umbral_popularidad": round(umbral_pop, 1), "margen_unitario_promedio": round(margen_prom, 2)}
    else:
        menu_ref = {"umbral_popularidad": 0, "margen_unitario_promedio": 0}

    sin_venta = [
        dict(r)
        for r in conn.execute(
            """SELECT p.nombre AS producto, c.nombre AS categoria FROM dim_producto p
           LEFT JOIN dim_categoria c ON c.categoria_id=p.categoria_id
           WHERE p.activo=1 AND p.producto_id NOT IN (
               SELECT f.producto_id FROM fact_ventas f JOIN ventas v ON v.venta_id=f.venta_id AND v.estado='PAGADA'
               WHERE f.fecha_hora BETWEEN ? AND ?)""",
            (desde, hasta_ts),
        )
    ]

    categorias = [
        dict(r)
        for r in conn.execute(
            """SELECT COALESCE(c.nombre,'Sin categoría') AS categoria, c.color, ROUND(SUM(f.importe_neto),2) ventas,
                  ROUND(SUM(f.margen),2) margen, SUM(f.cantidad) unidades
           FROM fact_ventas f JOIN ventas v ON v.venta_id=f.venta_id AND v.estado='PAGADA'
           LEFT JOIN dim_categoria c ON c.categoria_id=f.categoria_id
           WHERE f.fecha_hora BETWEEN ? AND ? GROUP BY f.categoria_id ORDER BY ventas DESC""",
            (desde, hasta_ts),
        )
    ]

    metodos = [
        dict(r)
        for r in conn.execute(
            """SELECT m.nombre AS metodo, COUNT(v.venta_id) tickets, ROUND(COALESCE(SUM(v.total),0),2) ventas
           FROM ventas v JOIN dim_metodo_pago m ON m.metodo_pago_id=v.metodo_pago_id
           WHERE v.estado='PAGADA' AND date(v.fecha_hora) BETWEEN ? AND ?
           GROUP BY m.metodo_pago_id ORDER BY ventas DESC""",
            rango,
        )
    ]

    usuarios = [
        dict(r)
        for r in conn.execute(
            """SELECT u.nombre AS usuario, COUNT(v.venta_id) tickets, ROUND(SUM(v.total),2) ventas,
                  ROUND(AVG(v.total),2) ticket_promedio,
                  (SELECT COUNT(*) FROM ventas x WHERE x.usuario_id=u.usuario_id AND x.estado='CANCELADA'
                     AND date(x.fecha_hora) BETWEEN ? AND ?) AS canceladas
           FROM ventas v JOIN dim_usuario u ON u.usuario_id=v.usuario_id
           WHERE v.estado='PAGADA' AND date(v.fecha_hora) BETWEEN ? AND ?
           GROUP BY u.usuario_id ORDER BY ventas DESC""",
            rango + rango,
        )
    ]

    inv = conn.execute(
        """SELECT COALESCE(SUM(valor_inventario),0) valor, COUNT(*) insumos,
                  SUM(estado='BAJO') bajos, SUM(estado='AGOTADO') agotados FROM v_inventario_valorizado"""
    ).fetchone()
    alertas = [
        dict(r)
        for r in conn.execute(
            """SELECT nombre, unidad, stock_actual, stock_minimo, estado, proveedor FROM v_inventario_valorizado
           WHERE estado != 'OK' ORDER BY estado, nombre"""
        )
    ]
    compras = conn.execute(
        "SELECT COALESCE(SUM(total),0) FROM entradas_inventario WHERE date(fecha_hora) BETWEEN ? AND ?", rango
    ).fetchone()[0]
    mermas = [
        dict(r)
        for r in conn.execute(
            """SELECT i.nombre AS insumo, i.unidad, ROUND(SUM(-m.cantidad),3) cantidad, ROUND(SUM(-m.costo_total),2) costo
           FROM fact_movimientos_inventario m JOIN dim_insumo i ON i.insumo_id=m.insumo_id
           WHERE m.tipo='AJUSTE' AND m.cantidad < 0 AND date(m.fecha_hora) BETWEEN ? AND ?
           GROUP BY m.insumo_id ORDER BY costo DESC LIMIT 10""",
            rango,
        )
    ]
    consumo = [
        dict(r)
        for r in conn.execute(
            """SELECT i.nombre AS insumo, i.unidad, ROUND(SUM(-m.cantidad),3) cantidad, ROUND(SUM(-m.costo_total),2) costo
           FROM fact_movimientos_inventario m JOIN dim_insumo i ON i.insumo_id=m.insumo_id
           WHERE m.tipo='BACKFLUSH' AND date(m.fecha_hora) BETWEEN ? AND ?
           GROUP BY m.insumo_id ORDER BY costo DESC LIMIT 10""",
            rango,
        )
    ]
    # días de cobertura: stock / consumo diario promedio de los últimos 28 días
    cobertura = [
        dict(r)
        for r in conn.execute(
            """WITH c AS (SELECT insumo_id, SUM(-cantidad)/28.0 diario FROM fact_movimientos_inventario
                      WHERE tipo='BACKFLUSH' AND fecha_hora >= datetime('now','localtime','-28 days') GROUP BY insumo_id)
           SELECT i.nombre AS insumo, i.unidad, i.stock_actual, ROUND(c.diario,3) consumo_diario,
                  ROUND(i.stock_actual / c.diario, 1) dias_cobertura
           FROM dim_insumo i JOIN c ON c.insumo_id=i.insumo_id
           WHERE i.activo=1 AND c.diario > 0 ORDER BY dias_cobertura LIMIT 10"""
        )
    ]

    return {
        "rango": {
            "desde": desde,
            "hasta": hasta,
            "dias": dias,
            "agrupar": agrupar,
            "anterior_desde": p0.isoformat(),
            "anterior_hasta": p1.isoformat(),
        },
        "kpis": actual,
        "kpis_anterior": anterior,
        "serie": serie,
        "por_hora": por_hora,
        "por_dia_semana": por_dia_semana,
        "productos": productos,
        "menu_ref": menu_ref,
        "sin_venta": sin_venta,
        "categorias": categorias,
        "metodos": metodos,
        "usuarios": usuarios,
        "inventario": {
            "valor": round(inv["valor"], 2),
            "insumos": inv["insumos"],
            "bajos": inv["bajos"] or 0,
            "agotados": inv["agotados"] or 0,
            "compras_periodo": round(compras, 2),
            "merma_periodo": round(sum(m["costo"] for m in mermas), 2),
            "alertas": alertas,
            "mermas": mermas,
            "consumo": consumo,
            "cobertura": cobertura,
        },
    }
