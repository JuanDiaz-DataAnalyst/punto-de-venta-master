"""Cuentas abiertas por mesa: varios tickets independientes en paralelo, cada uno con su folio."""

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from ..db import audit, get_config, get_db, now_str
from ..security import current_user
from ..services import (
    ErrorNegocio,
    abrir_cuenta,
    actualizar_cuenta,
    agregar_item,
    cancelar_cuenta,
    cobrar_cuenta,
    detalle_cuenta,
    detalle_venta,
    listar_cuentas_abiertas,
    modificar_item,
    mover_consumos,
)
from ..ticket import render_ticket

router = APIRouter(prefix="/api/cuentas", tags=["cuentas"])


class CuentaIn(BaseModel):
    mesa: str = Field(min_length=1, max_length=30)


class CuentaEditIn(BaseModel):
    mesa: str | None = Field(default=None, max_length=30)
    descuento_tipo: str | None = None
    descuento_valor: float | None = Field(default=None, ge=0)


class ItemIn(BaseModel):
    producto_id: int
    cantidad: float = Field(gt=0, default=1)
    nota: str | None = None


class ItemEditIn(BaseModel):
    cantidad: float | None = None
    nota: str | None = None  # None = sin cambio, "" = borrar la nota
    separar: bool = False


class CobroIn(BaseModel):
    metodo_pago_id: int
    pago_recibido: float | None = None
    cliente: str | None = None
    notas: str | None = None


class MoverItemIn(BaseModel):
    item_id: int
    cantidad: float = Field(ge=0)


class MoverIn(BaseModel):
    items: list[MoverItemIn]
    destino_cuenta_id: int | None = None  # pasar a otra mesa abierta…
    destino_mesa: str | None = Field(default=None, max_length=30)  # …o dividir hacia una cuenta nueva


class CancelCuentaIn(BaseModel):
    motivo: str | None = None


def _transaccion(conn, fn):
    """Ejecuta fn(conn) en una sola transacción de escritura."""
    try:
        conn.execute("BEGIN IMMEDIATE")
        res = fn(conn)
        conn.commit()
        return res
    except Exception:
        conn.rollback()
        raise


@router.get("")
def cuentas_abiertas(user=Depends(current_user), conn=Depends(get_db)):
    return listar_cuentas_abiertas(conn)


@router.post("")
def nueva_cuenta(data: CuentaIn, user=Depends(current_user), conn=Depends(get_db)):
    cid = _transaccion(conn, lambda c: abrir_cuenta(c, user["usuario_id"], data.mesa))
    return detalle_cuenta(conn, cid)


@router.put("/{cid}")
def editar_cuenta(cid: int, data: CuentaEditIn, user=Depends(current_user), conn=Depends(get_db)):
    _transaccion(
        conn,
        lambda c: actualizar_cuenta(c, cid, user["usuario_id"], data.mesa, data.descuento_tipo, data.descuento_valor),
    )
    return detalle_cuenta(conn, cid)


@router.post("/{cid}/items")
def agregar(cid: int, data: ItemIn, user=Depends(current_user), conn=Depends(get_db)):
    _transaccion(conn, lambda c: agregar_item(c, cid, data.producto_id, data.cantidad, data.nota))
    return detalle_cuenta(conn, cid)


@router.put("/{cid}/items/{item_id}")
def modificar(cid: int, item_id: int, data: ItemEditIn, user=Depends(current_user), conn=Depends(get_db)):
    _transaccion(conn, lambda c: modificar_item(c, cid, item_id, data.cantidad, data.nota, data.separar))
    return detalle_cuenta(conn, cid)


@router.delete("/{cid}/items/{item_id}")
def quitar(cid: int, item_id: int, user=Depends(current_user), conn=Depends(get_db)):
    _transaccion(conn, lambda c: modificar_item(c, cid, item_id, cantidad=0))
    return detalle_cuenta(conn, cid)


@router.post("/{cid}/cobrar")
def cobrar(cid: int, data: CobroIn, user=Depends(current_user), conn=Depends(get_db)):
    vid = _transaccion(
        conn,
        lambda c: cobrar_cuenta(
            c, cid, user["usuario_id"], data.metodo_pago_id, data.pago_recibido, data.cliente, data.notas
        ),
    )
    return detalle_venta(conn, vid)


@router.post("/{cid}/cancelar")
def cancelar(cid: int, data: CancelCuentaIn, user=Depends(current_user), conn=Depends(get_db)):
    _transaccion(conn, lambda c: cancelar_cuenta(c, cid, user["usuario_id"], data.motivo))
    return detalle_cuenta(conn, cid)


@router.post("/{cid}/mover")
def mover(cid: int, data: MoverIn, user=Depends(current_user), conn=Depends(get_db)):
    """Dividir la cuenta (hacia una cuenta nueva) o pasar consumos a otra mesa abierta."""
    origen, destino = _transaccion(
        conn,
        lambda c: mover_consumos(
            c,
            cid,
            user["usuario_id"],
            [i.model_dump() for i in data.items],
            data.destino_cuenta_id,
            data.destino_mesa,
        ),
    )
    return {"origen": detalle_cuenta(conn, origen), "destino": detalle_cuenta(conn, destino)}


@router.get("/{cid}/precuenta", response_class=HTMLResponse)
def precuenta(cid: int, user=Depends(current_user), conn=Depends(get_db)):
    """Cuenta imprimible de una mesa abierta para que el cliente la revise antes de pagar."""
    c = detalle_cuenta(conn, cid)
    if c["estado"] != "ABIERTA":
        raise ErrorNegocio("Esa cuenta ya no está abierta", 409)
    if not c["items"]:
        raise ErrorNegocio("La cuenta no tiene consumos")
    with conn:
        audit(conn, user["usuario_id"], "IMPRIMIR_PRECUENTA", "cuentas", cid, f"{c['folio']} mesa {c['mesa']}")
    venta = {
        **c,
        "fecha_hora": now_str(),
        "lineas": [{**i, "producto": i["nombre"], "importe_bruto": i["precio"] * i["cantidad"]} for i in c["items"]],
        "metodo_pago": "",
        "cliente": None,
    }
    return HTMLResponse(render_ticket(venta, get_config(conn), precuenta=True))


__all__ = ["router"]
