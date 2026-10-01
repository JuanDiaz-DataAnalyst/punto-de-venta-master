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


# ---------------------------------------------------------------- pre-cuenta
def test_precuenta_se_imprime_sin_cerrar_ni_mover_inventario(client, admin, turno, mesa, agregar, catalogo, stock):
    c = mesa("6")
    assert client.get(f"/api/cuentas/{c['cuenta_id']}/precuenta", headers=admin).status_code == 400  # vacía
    agregar(c["cuenta_id"], catalogo["taco"], 2, nota="sin cebolla")
    r = client.get(f"/api/cuentas/{c['cuenta_id']}/precuenta", headers=admin)
    assert r.status_code == 200
    assert "PRE-CUENTA" in r.text and c["folio"] in r.text and "Mesa: <b>6</b>" in r.text
    assert "sin cebolla" in r.text and "Pago" not in r.text.replace("pago", "")
    assert stock(catalogo["tortilla"])["stock_actual"] == 100
    assert [x["mesa"] for x in client.get("/api/cuentas", headers=admin).json()] == ["6"]
    bitacora = client.get("/api/auditoria", params={"accion": "PRECUENTA"}, headers=admin).json()
    assert len(bitacora) == 1


def test_precuenta_de_cuenta_cerrada_se_rechaza(client, admin, turno, mesa, agregar, catalogo):
    c = mesa("6")
    agregar(c["cuenta_id"], catalogo["taco"], 1)
    client.post(f"/api/cuentas/{c['cuenta_id']}/cobrar", json={"metodo_pago_id": 2}, headers=admin)
    assert client.get(f"/api/cuentas/{c['cuenta_id']}/precuenta", headers=admin).status_code == 409


# ---------------------------------------------------------------- dividir / mover
def _mover(client, admin, cuenta_id, items, **destino):
    body = {"items": [{"item_id": i, "cantidad": q} for i, q in items], **destino}
    return client.post(f"/api/cuentas/{cuenta_id}/mover", json=body, headers=admin)


def test_dividir_cuenta_hacia_una_cuenta_nueva_con_su_propio_folio(
    client, admin, turno, mesa, agregar, catalogo, stock
):
    c = mesa("1")
    agregar(c["cuenta_id"], catalogo["taco"], 4)
    det = agregar(c["cuenta_id"], catalogo["bebida"], 2).json()
    taco, bebida = (i["item_id"] for i in det["items"])
    r = _mover(client, admin, c["cuenta_id"], [(taco, 1), (bebida, 2)], destino_mesa="1-B")
    assert r.status_code == 200, r.text
    origen, destino = r.json()["origen"], r.json()["destino"]
    assert [(i["nombre"], i["cantidad"]) for i in origen["items"]] == [("Taco", 3)]
    assert [(i["nombre"], i["cantidad"]) for i in destino["items"]] == [("Taco", 1), ("Refresco", 2)]
    assert destino["mesa"] == "1-B" and destino["folio"] != origen["folio"]
    assert origen["total"] + destino["total"] == 4 * 25 + 2 * 28
    # cada ticket se cobra por separado y el inventario se descuenta una sola vez por consumo
    v1 = client.post(f"/api/cuentas/{origen['cuenta_id']}/cobrar", json={"metodo_pago_id": 2}, headers=admin).json()
    v2 = client.post(f"/api/cuentas/{destino['cuenta_id']}/cobrar", json={"metodo_pago_id": 2}, headers=admin).json()
    assert (v1["folio"], v2["folio"]) == (origen["folio"], destino["folio"])
    assert v1["total"] + v2["total"] == 156
    assert stock(catalogo["tortilla"])["stock_actual"] == 100 - 2 * 4
    assert stock(catalogo["refresco"])["stock_actual"] == 24 - 2


def test_pasar_consumos_a_otra_mesa_abierta_y_sumar_renglones_iguales(client, admin, turno, mesa, agregar, catalogo):
    a, b = mesa("1"), mesa("2")
    ia = agregar(a["cuenta_id"], catalogo["taco"], 2).json()["items"][0]["item_id"]
    agregar(b["cuenta_id"], catalogo["taco"], 1)
    r = _mover(client, admin, a["cuenta_id"], [(ia, 2)], destino_cuenta_id=b["cuenta_id"]).json()
    assert r["origen"]["items"] == [] and r["origen"]["estado"] == "ABIERTA"
    assert [(i["nombre"], i["cantidad"]) for i in r["destino"]["items"]] == [("Taco", 3)]


def test_las_notas_viajan_con_el_consumo(client, admin, turno, mesa, agregar, catalogo):
    a = mesa("1")
    item = agregar(a["cuenta_id"], catalogo["taco"], 2, nota="sin salsa").json()["items"][0]["item_id"]
    r = _mover(client, admin, a["cuenta_id"], [(item, 1)], destino_mesa="2").json()
    assert r["destino"]["items"][0]["nota"] == "sin salsa"
    assert r["origen"]["items"][0]["nota"] == "sin salsa"


def test_el_descuento_se_queda_en_la_cuenta_de_origen(client, admin, turno, mesa, agregar, catalogo):
    a = mesa("1")
    item = agregar(a["cuenta_id"], catalogo["taco"], 4).json()["items"][0]["item_id"]
    client.put(f"/api/cuentas/{a['cuenta_id']}", json={"descuento_tipo": "%", "descuento_valor": 10}, headers=admin)
    r = _mover(client, admin, a["cuenta_id"], [(item, 2)], destino_mesa="2").json()
    assert r["origen"]["descuento"] == 5 and r["destino"]["descuento"] == 0


@pytest.mark.parametrize(
    ("items", "destino", "codigo"),
    [
        ([("X", 5)], {"destino_mesa": "9"}, 400),  # más piezas de las que hay
        ([("X", 0)], {"destino_mesa": "9"}, 400),  # nada que mover
        ([("X", 1)], {}, 400),  # sin destino
        ([("X", 1)], {"destino_mesa": "9", "destino_cuenta_id": 1}, 400),  # dos destinos
        ([("X", 1)], {"destino_cuenta_id": 1}, 400),  # misma cuenta
        ([("X", 1)], {"destino_cuenta_id": 999}, 404),
        ([("X", 1)], {"destino_mesa": "Ocupada"}, 409),  # la mesa ya tiene cuenta abierta
    ],
)
def test_mover_valida_los_datos(client, admin, turno, mesa, agregar, catalogo, items, destino, codigo):
    mesa("Ocupada")
    a = mesa("1")  # cuenta_id 2
    item = agregar(a["cuenta_id"], catalogo["taco"], 2).json()["items"][0]["item_id"]
    if destino.get("destino_cuenta_id") == 1:
        destino = {**destino, "destino_cuenta_id": a["cuenta_id"]}
    r = _mover(client, admin, a["cuenta_id"], [(item if i == "X" else i, q) for i, q in items], **destino)
    assert r.status_code == codigo, r.text
    # un intento fallido no deja cuentas ni renglones a medias
    assert [(x["mesa"], len(x["items"])) for x in client.get("/api/cuentas", headers=admin).json()] == [
        ("Ocupada", 0),
        ("1", 1),
    ]


def test_no_se_mueven_consumos_de_una_cuenta_cerrada_ni_a_una_cerrada(client, admin, turno, mesa, agregar, catalogo):
    a, b = mesa("1"), mesa("2")
    item = agregar(a["cuenta_id"], catalogo["taco"], 1).json()["items"][0]["item_id"]
    client.post(f"/api/cuentas/{b['cuenta_id']}/cancelar", json={}, headers=admin)
    assert _mover(client, admin, a["cuenta_id"], [(item, 1)], destino_cuenta_id=b["cuenta_id"]).status_code == 409
    client.post(f"/api/cuentas/{a['cuenta_id']}/cobrar", json={"metodo_pago_id": 2}, headers=admin)
    assert _mover(client, admin, a["cuenta_id"], [(item, 1)], destino_mesa="3").status_code == 409


def test_mover_queda_en_auditoria_y_es_para_cualquier_usuario(client, cajero, admin, turno, mesa, agregar, catalogo):
    a = mesa("1", headers=cajero)
    item = agregar(a["cuenta_id"], catalogo["taco"], 2, headers=cajero).json()["items"][0]["item_id"]
    assert _mover(client, cajero, a["cuenta_id"], [(item, 1)], destino_mesa="2").status_code == 200
    assert len(client.get("/api/auditoria", params={"accion": "MOVER_CONSUMOS"}, headers=admin).json()) == 1
