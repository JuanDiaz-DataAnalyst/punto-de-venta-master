"""Cuentas abiertas por mesa: tickets independientes en paralelo con folio único."""

import sqlite3

import pytest

from app import config, db


@pytest.fixture
def mesa(client, admin):
    """Función auxiliar: abre una cuenta y regresa su detalle."""

    def _mesa(nombre, headers=None):
        r = client.post("/api/cuentas", json={"mesa": nombre}, headers=headers or admin)
        assert r.status_code == 200, r.text
        return r.json()

    return _mesa


@pytest.fixture
def agregar(client, admin):
    def _agregar(cuenta_id, producto_id, cantidad=1, nota=None, headers=None):
        body = {"producto_id": producto_id, "cantidad": cantidad, "nota": nota}
        return client.post(f"/api/cuentas/{cuenta_id}/items", json=body, headers=headers or admin)

    return _agregar


def test_no_se_abre_cuenta_sin_turno(client, admin):
    assert client.post("/api/cuentas", json={"mesa": "1"}, headers=admin).status_code == 409


def test_varias_mesas_abiertas_a_la_vez_con_folios_unicos(client, admin, turno, mesa, vender, catalogo):
    a, b, c = mesa("1"), mesa("2"), mesa("Barra")
    directa = vender([(catalogo["taco"], 1)]).json()
    folios = [a["folio"], b["folio"], c["folio"], directa["folio"]]
    assert len(set(folios)) == 4
    abiertas = client.get("/api/cuentas", headers=admin).json()
    assert [x["mesa"] for x in abiertas] == ["1", "2", "Barra"]


def test_una_sola_cuenta_abierta_por_mesa(client, admin, turno, mesa):
    mesa("5")
    r = client.post("/api/cuentas", json={"mesa": " 5 "}, headers=admin)
    assert r.status_code == 409 and "ya tiene una cuenta abierta" in r.json()["detail"]
    assert client.post("/api/cuentas", json={"mesa": "   "}, headers=admin).status_code in (400, 422)


def test_los_consumos_se_agregan_durante_la_estancia(client, admin, turno, mesa, agregar, catalogo):
    c = mesa("3")
    agregar(c["cuenta_id"], catalogo["taco"], 2)
    agregar(c["cuenta_id"], catalogo["taco"], 1)  # mismo producto sin nota: suma
    det = agregar(c["cuenta_id"], catalogo["bebida"]).json()
    assert [(i["nombre"], i["cantidad"]) for i in det["items"]] == [("Taco", 3), ("Refresco", 1)]
    assert det["subtotal"] == 3 * 25 + 28 and det["total"] == det["subtotal"]


def test_las_cuentas_son_independientes(client, admin, turno, mesa, agregar, catalogo):
    a, b = mesa("1"), mesa("2")
    agregar(a["cuenta_id"], catalogo["taco"], 2)
    agregar(b["cuenta_id"], catalogo["bebida"], 1)
    por_mesa = {x["mesa"]: x for x in client.get("/api/cuentas", headers=admin).json()}
    assert por_mesa["1"]["total"] == 50 and por_mesa["2"]["total"] == 28


def test_modificar_y_quitar_renglones(client, admin, turno, mesa, agregar, catalogo):
    c = mesa("4")
    det = agregar(c["cuenta_id"], catalogo["taco"], 3).json()
    item = det["items"][0]["item_id"]
    base = f"/api/cuentas/{c['cuenta_id']}/items/{item}"
    # nota solo a una pieza: se separa en un renglón nuevo
    det = client.put(base, json={"nota": "sin cebolla", "separar": True}, headers=admin).json()
    assert [(i["cantidad"], i["nota"]) for i in det["items"]] == [(2, None), (1, "sin cebolla")]
    det = client.put(base, json={"cantidad": 5}, headers=admin).json()
    assert det["items"][0]["cantidad"] == 5
    det = client.delete(base, headers=admin).json()
    assert [i["nota"] for i in det["items"]] == ["sin cebolla"]


def test_cobrar_conserva_folio_y_mesa_y_mueve_inventario_hasta_ese_momento(
    client, admin, turno, mesa, agregar, catalogo, stock
):
    c = mesa("7")
    agregar(c["cuenta_id"], catalogo["taco"], 4)
    assert stock(catalogo["tortilla"])["stock_actual"] == 100  # abrir/agregar no toca el inventario
    v = client.post(
        f"/api/cuentas/{c['cuenta_id']}/cobrar", json={"metodo_pago_id": 1, "pago_recibido": 200}, headers=admin
    ).json()
    assert v["folio"] == c["folio"] and v["mesa"] == "7" and v["total"] == 100 and v["cambio"] == 100
    assert v["costo_total"] == pytest.approx(64.0)
    assert stock(catalogo["tortilla"])["stock_actual"] == 92
    assert client.get("/api/cuentas", headers=admin).json() == []
    # ya no se puede cobrar de nuevo y la mesa queda libre
    again = client.post(f"/api/cuentas/{c['cuenta_id']}/cobrar", json={"metodo_pago_id": 1}, headers=admin)
    assert again.status_code == 409
    assert client.post("/api/cuentas", json={"mesa": "7"}, headers=admin).status_code == 200


def test_descuento_de_la_cuenta_se_prorratea_al_cobrar(client, admin, turno, mesa, agregar, catalogo):
    c = mesa("8")
    agregar(c["cuenta_id"], catalogo["taco"], 2)
    agregar(c["cuenta_id"], catalogo["bebida"], 1)
    det = client.put(
        f"/api/cuentas/{c['cuenta_id']}", json={"descuento_tipo": "%", "descuento_valor": 10}, headers=admin
    ).json()
    assert det["subtotal"] == 78 and det["descuento"] == 7.8 and det["total"] == 70.2
    v = client.post(f"/api/cuentas/{c['cuenta_id']}/cobrar", json={"metodo_pago_id": 2}, headers=admin).json()
    assert v["total"] == 70.2
    assert sum(ln["importe_neto"] for ln in v["lineas"]) == pytest.approx(v["total"])


def test_no_se_cobra_una_cuenta_vacia(client, admin, turno, mesa):
    c = mesa("9")
    assert (
        client.post(f"/api/cuentas/{c['cuenta_id']}/cobrar", json={"metodo_pago_id": 1}, headers=admin).status_code
        == 400
    )


def test_cancelar_cuenta_no_toca_inventario_y_no_reutiliza_folio(
    client, admin, turno, mesa, agregar, catalogo, stock, vender
):
    c = mesa("10")
    agregar(c["cuenta_id"], catalogo["taco"], 2)
    sin_motivo = client.post(f"/api/cuentas/{c['cuenta_id']}/cancelar", json={}, headers=admin)
    assert sin_motivo.status_code == 400
    r = client.post(f"/api/cuentas/{c['cuenta_id']}/cancelar", json={"motivo": "Se fueron"}, headers=admin)
    assert r.json()["estado"] == "CANCELADA"
    assert stock(catalogo["tortilla"])["stock_actual"] == 100
    nueva = mesa("10")
    assert nueva["folio"] != c["folio"]
    assert vender([(catalogo["taco"], 1)]).json()["folio"] not in (c["folio"], nueva["folio"])


def test_cuenta_vacia_se_cancela_sin_motivo(client, admin, turno, mesa):
    c = mesa("11")
    assert client.post(f"/api/cuentas/{c['cuenta_id']}/cancelar", json={}, headers=admin).status_code == 200


def test_no_se_cierra_el_turno_con_cuentas_abiertas(client, admin, turno, mesa, agregar, catalogo):
    c = mesa("12")
    r = client.post("/api/turno/cerrar", json={"efectivo_contado": 500}, headers=admin)
    assert r.status_code == 409 and "12" in r.json()["detail"]
    client.post(f"/api/cuentas/{c['cuenta_id']}/cancelar", json={}, headers=admin)
    assert client.post("/api/turno/cerrar", json={"efectivo_contado": 500}, headers=admin).status_code == 200


def test_cualquier_usuario_maneja_cuentas(client, cajero, turno, catalogo, mesa, agregar):
    c = mesa("1", headers=cajero)
    assert agregar(c["cuenta_id"], catalogo["taco"], 1, headers=cajero).status_code == 200
    r = client.post(f"/api/cuentas/{c['cuenta_id']}/cobrar", json={"metodo_pago_id": 1}, headers=cajero)
    assert r.status_code == 200


def test_ticket_y_listado_muestran_la_mesa(client, admin, turno, mesa, agregar, catalogo):
    c = mesa("Terraza 2")
    agregar(c["cuenta_id"], catalogo["taco"], 1)
    v = client.post(f"/api/cuentas/{c['cuenta_id']}/cobrar", json={"metodo_pago_id": 2}, headers=admin).json()
    assert "Terraza 2" in client.get(f"/api/ventas/{v['venta_id']}/ticket", headers=admin).text
    fila = client.get("/api/ventas", params={"buscar": "Terraza"}, headers=admin).json()
    assert [f["folio"] for f in fila] == [c["folio"]]


def test_migracion_v1_agrega_mesa_y_continua_los_folios(tmp_path, monkeypatch):
    ruta = tmp_path / "pos.db"
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "DB_PATH", ruta)
    viejo = sqlite3.connect(ruta)  # ventas de la versión 1: sin columna `mesa`
    viejo.execute("CREATE TABLE ventas (venta_id INTEGER PRIMARY KEY, folio TEXT, fecha_id INTEGER, turno_id INTEGER)")
    viejo.execute("INSERT INTO ventas(venta_id, folio) VALUES (7, 'V-000007')")
    viejo.commit()
    viejo.close()
    db.init_db()
    db.init_db()  # idempotente
    conn = db.connect()
    try:
        assert "mesa" in {r["name"] for r in conn.execute("PRAGMA table_info(ventas)")}
        assert conn.execute("SELECT valor FROM config WHERE clave='folio_consecutivo'").fetchone()[0] == "7"
    finally:
        conn.close()
