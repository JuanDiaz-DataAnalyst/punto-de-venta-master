"""Entradas de material, ajustes manuales/conteo físico y kardex."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..db import get_db
from ..security import current_user, require_admin
from ..services import ajustar_inventario, registrar_entrada

router = APIRouter(prefix="/api/inventario", tags=["inventario"])

MOTIVOS_AJUSTE = [
    "Conteo físico",
    "Merma",
    "Caducidad",
    "Daño / derrame",
    "Consumo interno / personal",
    "Error de captura",
    "Devolución a proveedor",
    "Otro",
]


class LineaEntrada(BaseModel):
    insumo_id: int
    cantidad: float = Field(gt=0)
    costo_unitario: float = Field(ge=0)


class EntradaIn(BaseModel):
    proveedor_id: int | None = None
    factura: str | None = None
    notas: str | None = None
    lineas: list[LineaEntrada]


class AjusteIn(BaseModel):
    insumo_id: int
    modo: str  # CONTEO | SUMAR | RESTAR
    cantidad: float
    motivo: str = Field(min_length=1)
    comentario: str | None = None


class ConteoItem(BaseModel):
    insumo_id: int
    conteo: float = Field(ge=0)


class ConteoMasivoIn(BaseModel):
    items: list[ConteoItem]
    comentario: str | None = None


@router.get("/motivos")
def motivos(user=Depends(current_user)):
    return MOTIVOS_AJUSTE


@router.get("/resumen")
def resumen(user=Depends(current_user), conn=Depends(get_db)):
    r = conn.execute(
        """SELECT COUNT(*) insumos, COALESCE(SUM(valor_inventario),0) valor,
                  SUM(estado='BAJO') bajos, SUM(estado='AGOTADO') agotados FROM v_inventario_valorizado"""
    ).fetchone()
    return dict(r)


@router.post("/entradas")
def nueva_entrada(data: EntradaIn, user=Depends(current_user), conn=Depends(get_db)):
    with conn:
        eid = registrar_entrada(
            conn,
            user["usuario_id"],
            [ln.model_dump() for ln in data.lineas],
            data.proveedor_id,
            data.factura,
            data.notas,
        )
    return {"entrada_id": eid}


@router.get("/entradas")
def listar_entradas(
    desde: str | None = None, hasta: str | None = None, user=Depends(current_user), conn=Depends(get_db)
):
    where, params = [], []
    if desde:
        where.append("date(e.fecha_hora) >= ?")
        params.append(desde)
    if hasta:
        where.append("date(e.fecha_hora) <= ?")
        params.append(hasta)
    return [
        dict(r)
        for r in conn.execute(
            f"""SELECT e.*, pr.nombre AS proveedor, u.nombre AS usuario,
                   (SELECT COUNT(*) FROM fact_movimientos_inventario m WHERE m.referencia_tipo='ENTRADA'
                     AND m.referencia_id=e.entrada_id) AS renglones
            FROM entradas_inventario e LEFT JOIN dim_proveedor pr ON pr.proveedor_id=e.proveedor_id
            JOIN dim_usuario u ON u.usuario_id=e.usuario_id
            {"WHERE " + " AND ".join(where) if where else ""}
            ORDER BY e.fecha_hora DESC LIMIT 500""",
            params,
        )
    ]


@router.get("/entradas/{eid}")
def detalle_entrada(eid: int, user=Depends(current_user), conn=Depends(get_db)):
    e = conn.execute(
        """SELECT e.*, pr.nombre AS proveedor, u.nombre AS usuario FROM entradas_inventario e
           LEFT JOIN dim_proveedor pr ON pr.proveedor_id=e.proveedor_id JOIN dim_usuario u ON u.usuario_id=e.usuario_id
           WHERE entrada_id=?""",
        (eid,),
    ).fetchone()
    if not e:
        raise HTTPException(404, "Entrada no encontrada")
    lineas = [
        dict(r)
        for r in conn.execute(
            """SELECT m.insumo_id, i.nombre, i.unidad, m.cantidad, m.costo_unitario, m.costo_total
           FROM fact_movimientos_inventario m JOIN dim_insumo i ON i.insumo_id=m.insumo_id
           WHERE m.referencia_tipo='ENTRADA' AND m.referencia_id=?""",
            (eid,),
        )
    ]
    return {**dict(e), "lineas": lineas}


@router.post("/ajustes")
def nuevo_ajuste(data: AjusteIn, user=Depends(require_admin), conn=Depends(get_db)):
    motivo = data.motivo + (f" - {data.comentario}" if data.comentario else "")
    with conn:
        return ajustar_inventario(conn, user["usuario_id"], data.insumo_id, data.modo.upper(), data.cantidad, motivo)


@router.post("/conteo")
def conteo_masivo(data: ConteoMasivoIn, user=Depends(require_admin), conn=Depends(get_db)):
    """Aplica un conteo físico completo: sólo ajusta los insumos con diferencia."""
    ajustados = []
    with conn:
        for it in data.items:
            actual = conn.execute("SELECT stock_actual FROM dim_insumo WHERE insumo_id=?", (it.insumo_id,)).fetchone()
            if actual is None or abs(actual[0] - it.conteo) < 1e-9:
                continue
            r = ajustar_inventario(
                conn,
                user["usuario_id"],
                it.insumo_id,
                "CONTEO",
                it.conteo,
                "Conteo físico" + (f" - {data.comentario}" if data.comentario else ""),
            )
            ajustados.append({"insumo_id": it.insumo_id, **r})
    return {"ajustados": len(ajustados), "detalle": ajustados}


@router.get("/movimientos")
def kardex(
    insumo_id: int | None = None,
    tipo: str | None = None,
    desde: str | None = None,
    hasta: str | None = None,
    limite: int = 500,
    user=Depends(current_user),
    conn=Depends(get_db),
):
    where, params = [], []
    if insumo_id:
        where.append("m.insumo_id=?")
        params.append(insumo_id)
    if tipo:
        where.append("m.tipo=?")
        params.append(tipo)
    if desde:
        where.append("date(m.fecha_hora) >= ?")
        params.append(desde)
    if hasta:
        where.append("date(m.fecha_hora) <= ?")
        params.append(hasta)
    params.append(min(max(limite, 1), 5000))
    return [
        dict(r)
        for r in conn.execute(
            f"""SELECT m.*, i.nombre AS insumo, i.unidad, u.nombre AS usuario
            FROM fact_movimientos_inventario m JOIN dim_insumo i ON i.insumo_id=m.insumo_id
            LEFT JOIN dim_usuario u ON u.usuario_id=m.usuario_id
            {"WHERE " + " AND ".join(where) if where else ""}
            ORDER BY m.movimiento_id DESC LIMIT ?""",
            params,
        )
    ]
