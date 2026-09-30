"""Ventas: turno obligatorio, backflush, descuentos, cambio y cancelaciones."""

import pytest


def test_no_se_vende_sin_turno_abierto(catalogo, vender):
    r = vender([(catalogo["taco"], 1)])
    assert r.status_code == 409


def test_backflush_descuenta_receta_y_registra_costo(catalogo, turno, vender, stock):
    v = vender([(catalogo["taco"], 4)], pago_recibido=100).json()
    assert v["total"] == 100
    assert v["costo_total"] == pytest.approx(64.0)  # 4 x (2 x 0.50 + 0.1 x 150)
    assert stock(catalogo["tortilla"])["stock_actual"] == 92
    assert stock(catalogo["carne"])["stock_actual"] == pytest.approx(1.6)


def test_descuento_se_prorratea_entre_renglones(catalogo, turno, vender):
    v = vender([(catalogo["taco"], 2), (catalogo["bebida"], 1)], descuento=13).json()
    assert v["subtotal"] == 78 and v["total"] == 65
    assert sum(ln["descuento"] for ln in v["lineas"]) == pytest.approx(13)
    assert sum(ln["importe_neto"] for ln in v["lineas"]) == pytest.approx(v["total"])


def test_efectivo_calcula_cambio_y_rechaza_pago_insuficiente(catalogo, turno, vender):
    assert vender([(catalogo["taco"], 1)], pago_recibido=100).json()["cambio"] == 75
    assert vender([(catalogo["taco"], 1)], pago_recibido=10).status_code == 400


def test_precio_se_toma_de_la_base_no_del_cliente(client, admin, catalogo, turno):
    body = {"items": [{"producto_id": catalogo["taco"], "cantidad": 1, "precio": 1}], "metodo_pago_id": 2}
    assert client.post("/api/ventas", json=body, headers=admin).json()["total"] == 25


def test_cancelacion_regresa_inventario(client, admin, catalogo, turno, vender, stock):
    v = vender([(catalogo["taco"], 4)]).json()
    r = client.post(f"/api/ventas/{v['venta_id']}/cancelar", json={"motivo": "Error de captura"}, headers=admin)
    assert r.json()["estado"] == "CANCELADA"
    assert stock(catalogo["tortilla"])["stock_actual"] == 100
    assert stock(catalogo["carne"])["stock_actual"] == pytest.approx(2)
    # no se puede cancelar dos veces
    again = client.post(f"/api/ventas/{v['venta_id']}/cancelar", json={"motivo": "otra vez"}, headers=admin)
    assert again.status_code == 400


def test_bloqueo_por_falta_de_existencia(client, admin, catalogo, turno, vender):
    client.put("/api/config", json={"permitir_stock_negativo": "0"}, headers=admin)
    r = vender([(catalogo["taco"], 30)], metodo_pago_id=2)
    assert r.status_code == 409
    assert r.json()["datos"][0]["insumo"] == "Carne"


def test_venta_con_stock_negativo_permitido(client, admin, catalogo, turno, vender, stock):
    assert vender([(catalogo["taco"], 30)], metodo_pago_id=2).status_code == 200
    assert stock(catalogo["carne"])["stock_actual"] == pytest.approx(-1)


def test_ticket_html(client, admin, catalogo, turno, vender):
    v = vender([(catalogo["taco"], 1)]).json()
    html = client.get(f"/api/ventas/{v['venta_id']}/ticket", headers=admin).text
    assert v["folio"] in html and "TOTAL" in html
