"""Gastos fijos mensuales (nómina, renta, servicios…) para costos, márgenes y dashboard (solo Admin)."""

from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ..db import audit, get_db
from ..security import require_admin
from ..services import (
    CATEGORIAS_GASTO,
    GASTOS_COMUNES,
    ErrorNegocio,
    resumen_gastos_fijos,
    validar_gasto,
)

router = APIRouter(prefix="/api/gastos-fijos", tags=["gastos"])


class GastoIn(BaseModel):
    concepto: str = Field(min_length=1, max_length=120)
    categoria: str
    monto_mensual: float = Field(ge=0)
    vigente_desde: str
    vigente_hasta: str | None = None
    notas: str | None = None


def _inicio_de_mes() -> str:
    return date.today().replace(day=1).isoformat()


@router.get("")
def listar_gastos(user=Depends(require_admin), conn=Depends(get_db)):
    hoy = date.today().isoformat()
    gastos = [
        {**dict(r), "vigente": r["vigente_desde"] <= hoy and (r["vigente_hasta"] is None or r["vigente_hasta"] >= hoy)}
        for r in conn.execute("SELECT * FROM gastos_fijos ORDER BY categoria, concepto")
    ]
    return {"gastos": gastos, "categorias": CATEGORIAS_GASTO, "resumen": resumen_gastos_fijos(conn)}


@router.post("")
def crear_gasto(data: GastoIn, user=Depends(require_admin), conn=Depends(get_db)):
    concepto, categoria, desde, hasta = validar_gasto(
        data.concepto, data.categoria, data.vigente_desde, data.vigente_hasta
    )
    with conn:
        cur = conn.execute(
            """INSERT INTO gastos_fijos(concepto, categoria, monto_mensual, vigente_desde, vigente_hasta, notas)
               VALUES (?,?,?,?,?,?)""",
            (concepto, categoria, data.monto_mensual, desde, hasta, (data.notas or "").strip() or None),
        )
        audit(
            conn,
            user["usuario_id"],
            "CREAR_GASTO_FIJO",
            "gastos_fijos",
            cur.lastrowid,
            f"{concepto} {data.monto_mensual}",
        )
    return {"gasto_id": cur.lastrowid}


@router.put("/{gid}")
def editar_gasto(gid: int, data: GastoIn, user=Depends(require_admin), conn=Depends(get_db)):
    prev = conn.execute("SELECT * FROM gastos_fijos WHERE gasto_id=?", (gid,)).fetchone()
    if not prev:
        raise ErrorNegocio("Gasto no encontrado", 404)
    concepto, categoria, desde, hasta = validar_gasto(
        data.concepto, data.categoria, data.vigente_desde, data.vigente_hasta
    )
    with conn:
        conn.execute(
            """UPDATE gastos_fijos SET concepto=?, categoria=?, monto_mensual=?, vigente_desde=?, vigente_hasta=?,
                   notas=?, actualizado_en=datetime('now','localtime') WHERE gasto_id=?""",
            (concepto, categoria, data.monto_mensual, desde, hasta, (data.notas or "").strip() or None, gid),
        )
        audit(
            conn,
            user["usuario_id"],
            "EDITAR_GASTO_FIJO",
            "gastos_fijos",
            gid,
            f"{concepto}: {prev['monto_mensual']} -> {data.monto_mensual}",
        )
    return {"ok": True}


@router.delete("/{gid}")
def borrar_gasto(gid: int, user=Depends(require_admin), conn=Depends(get_db)):
    prev = conn.execute("SELECT * FROM gastos_fijos WHERE gasto_id=?", (gid,)).fetchone()
    if not prev:
        raise ErrorNegocio("Gasto no encontrado", 404)
    with conn:
        conn.execute("DELETE FROM gastos_fijos WHERE gasto_id=?", (gid,))
        audit(
            conn,
            user["usuario_id"],
            "BORRAR_GASTO_FIJO",
            "gastos_fijos",
            gid,
            f"{prev['concepto']} {prev['monto_mensual']}",
        )
    return {"ok": True}


@router.post("/plantilla")
def cargar_plantilla(user=Depends(require_admin), conn=Depends(get_db)):
    """Agrega los conceptos comunes de un restaurante pequeño (con $0) que aún no existan."""
    existentes = {r[0].lower() for r in conn.execute("SELECT concepto FROM gastos_fijos")}
    nuevos = [(c, cat) for c, cat in GASTOS_COMUNES if c.lower() not in existentes]
    with conn:
        conn.executemany(
            "INSERT INTO gastos_fijos(concepto, categoria, monto_mensual, vigente_desde) VALUES (?,?,0,?)",
            [(c, cat, _inicio_de_mes()) for c, cat in nuevos],
        )
        if nuevos:
            audit(
                conn, user["usuario_id"], "PLANTILLA_GASTOS_FIJOS", "gastos_fijos", detalle=f"{len(nuevos)} conceptos"
            )
    return {"agregados": len(nuevos)}
