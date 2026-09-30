"""Control de acceso por nivel: User vs Admin."""

from datetime import date

import pytest

HOY = date.today().isoformat()

SOLO_ADMIN = [
    ("get", f"/api/dashboard?desde={HOY}&hasta={HOY}", None),
    ("get", "/api/usuarios", None),
    ("get", "/api/turnos", None),
    ("post", "/api/productos", {"nombre": "X", "precio_venta": 1}),
    ("post", "/api/insumos", {"nombre": "X", "unidad": "kg"}),
    ("post", "/api/inventario/ajustes", {"insumo_id": 1, "modo": "SUMAR", "cantidad": 1, "motivo": "x"}),
    ("post", "/api/ventas/1/cancelar", {"motivo": "prueba"}),
    ("put", "/api/config", {"nombre_negocio": "X"}),
    ("post", "/api/respaldos", None),
    ("post", "/api/exportar/inventario", None),
]


@pytest.mark.parametrize(("metodo", "ruta", "body"), SOLO_ADMIN)
def test_user_no_accede_a_funciones_de_admin(client, cajero, metodo, ruta, body):
    kwargs = {"headers": cajero}
    if body is not None:
        kwargs["json"] = body
    assert getattr(client, metodo)(ruta, **kwargs).status_code == 403


def test_user_si_vende_y_registra_entradas(client, cajero, catalogo, turno, vender):
    assert vender([(catalogo["taco"], 1)], headers=cajero).status_code == 200
    body = {"lineas": [{"insumo_id": catalogo["tortilla"], "cantidad": 10, "costo_unitario": 0.5}]}
    assert client.post("/api/inventario/entradas", json=body, headers=cajero).status_code == 200


def test_user_solo_ve_ventas_del_turno_actual(client, admin, cajero, catalogo, turno, vender):
    vender([(catalogo["taco"], 1)])
    client.post("/api/turno/cerrar", json={"efectivo_contado": 525}, headers=admin)
    assert client.get("/api/ventas", headers=cajero).json() == []
    assert len(client.get("/api/ventas", headers=admin).json()) == 1
