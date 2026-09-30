"""Entradas (costo promedio ponderado), ajustes, conteo físico y kardex."""

import pytest


def test_entrada_recalcula_costo_promedio(client, admin, catalogo, stock):
    # 2 kg a $150 + 2 kg a $170 => $160
    lineas = [{"insumo_id": catalogo["carne"], "cantidad": 2, "costo_unitario": 170}]
    assert client.post("/api/inventario/entradas", json={"lineas": lineas}, headers=admin).status_code == 200
    carne = stock(catalogo["carne"])
    assert carne["stock_actual"] == pytest.approx(4)
    assert carne["costo_promedio"] == pytest.approx(160)


@pytest.mark.parametrize(("modo", "cantidad", "esperado"), [("SUMAR", 5, 105), ("RESTAR", 5, 95), ("CONTEO", 80, 80)])
def test_ajustes_manuales(client, admin, catalogo, stock, modo, cantidad, esperado):
    body = {"insumo_id": catalogo["tortilla"], "modo": modo, "cantidad": cantidad, "motivo": "Merma"}
    assert client.post("/api/inventario/ajustes", json=body, headers=admin).status_code == 200
    assert stock(catalogo["tortilla"])["stock_actual"] == esperado


def test_conteo_masivo_solo_ajusta_diferencias(client, admin, catalogo):
    items = [{"insumo_id": catalogo["tortilla"], "conteo": 100}, {"insumo_id": catalogo["carne"], "conteo": 1.5}]
    r = client.post("/api/inventario/conteo", json={"items": items}, headers=admin).json()
    assert r["ajustados"] == 1


def test_kardex_cuadra_con_existencia(client, admin, catalogo, turno, vender, stock):
    vender([(catalogo["taco"], 3)])
    client.post(
        "/api/inventario/ajustes",
        json={"insumo_id": catalogo["tortilla"], "modo": "RESTAR", "cantidad": 4, "motivo": "Merma"},
        headers=admin,
    )
    movs = client.get("/api/inventario/movimientos", params={"insumo_id": catalogo["tortilla"]}, headers=admin).json()
    assert {m["tipo"] for m in movs} == {"INICIAL", "BACKFLUSH", "AJUSTE"}
    assert sum(m["cantidad"] for m in movs) == pytest.approx(stock(catalogo["tortilla"])["stock_actual"])


def test_no_se_desactiva_insumo_usado_en_receta(client, admin, catalogo):
    body = {"nombre": "Carne", "unidad": "kg", "activo": False}
    assert client.put(f"/api/insumos/{catalogo['carne']}", json=body, headers=admin).status_code == 400


def test_costo_teorico_de_receta(client, admin, catalogo):
    taco = next(p for p in client.get("/api/productos", headers=admin).json() if p["producto_id"] == catalogo["taco"])
    assert taco["costo_teorico"] == pytest.approx(16)
    assert taco["margen_teorico"] == pytest.approx(9)
