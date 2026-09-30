"""Turnos y corte de caja."""


def test_solo_un_turno_abierto(client, admin, turno):
    assert client.post("/api/turno/abrir", json={"fondo_inicial": 100}, headers=admin).status_code == 400


def test_corte_calcula_efectivo_esperado(client, admin, catalogo, turno, vender):
    vender([(catalogo["taco"], 2)], metodo_pago_id=1)  # $50 efectivo
    vender([(catalogo["taco"], 1)], metodo_pago_id=2)  # $25 tarjeta (no suma al efectivo)
    client.post("/api/turno/movimiento", json={"tipo": "RETIRO", "monto": 30, "concepto": "Gas"}, headers=admin)
    client.post("/api/turno/movimiento", json={"tipo": "INGRESO", "monto": 10, "concepto": "Cambio"}, headers=admin)
    actual = client.get("/api/turno/actual", headers=admin).json()
    assert actual["efectivo_esperado"] == 500 + 50 - 30 + 10
    assert actual["total_ventas"] == 75

    cierre = client.post("/api/turno/cerrar", json={"efectivo_contado": 520}, headers=admin).json()
    assert cierre["turno"]["estado"] == "CERRADO"
    assert cierre["turno"]["diferencia"] == -10


def test_corte_imprimible(client, admin, turno):
    r = client.get(f"/api/turnos/{turno['turno_id']}/corte", headers=admin)
    assert r.status_code == 200 and "CORTE DE CAJA" in r.text
