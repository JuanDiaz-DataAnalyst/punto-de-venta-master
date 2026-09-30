"""Fixtures compartidas: cada prueba corre contra una base de datos SQLite nueva y aislada."""

import pytest
from fastapi.testclient import TestClient

from app import config, db, security
from app.server import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Cliente HTTP con carpeta de datos temporal (BD, respaldos y exportaciones)."""
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "pos.db")
    monkeypatch.setattr(config, "BACKUP_DIR", tmp_path / "respaldos")
    monkeypatch.setattr(config, "EXPORT_DIR", tmp_path / "exportaciones")
    monkeypatch.setattr(config, "LOG_DIR", tmp_path / "logs")
    security._sessions.clear()
    db.init_db()
    return TestClient(app)


def login(client, username, password) -> dict:
    r = client.post("/api/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture
def admin(client) -> dict:
    """Sistema configurado con un administrador; regresa los headers de su sesión."""
    r = client.post(
        "/api/setup",
        json={
            "nombre_negocio": "Negocio de prueba",
            "admin_nombre": "Admin",
            "admin_username": "admin",
            "admin_password": "admin123",
        },
    )
    assert r.status_code == 200, r.text
    return login(client, "admin", "admin123")


@pytest.fixture
def cajero(client, admin) -> dict:
    r = client.post(
        "/api/usuarios",
        json={"username": "caja1", "nombre": "Cajero", "rol": "USER", "password": "1234"},
        headers=admin,
    )
    assert r.status_code == 200, r.text
    return login(client, "caja1", "1234")


@pytest.fixture
def catalogo(client, admin) -> dict:
    """Taco = 2 tortillas ($0.50) + 0.1 kg de carne ($150/kg) -> costo teórico $16, precio $25."""
    cat = client.post("/api/categorias", json={"nombre": "Tacos"}, headers=admin).json()["categoria_id"]

    def insumo(nombre, unidad, stock, costo, minimo=0):
        body = {
            "nombre": nombre,
            "unidad": unidad,
            "stock_inicial": stock,
            "costo_unitario": costo,
            "stock_minimo": minimo,
        }
        return client.post("/api/insumos", json=body, headers=admin).json()["insumo_id"]

    tor = insumo("Tortilla", "pz", 100, 0.5)
    car = insumo("Carne", "kg", 2, 150, minimo=1)
    refresco = insumo("Refresco", "pz", 24, 11)
    receta = [{"insumo_id": tor, "cantidad": 2}, {"insumo_id": car, "cantidad": 0.1}]
    taco = client.post(
        "/api/productos",
        json={"nombre": "Taco", "precio_venta": 25, "categoria_id": cat, "receta": receta},
        headers=admin,
    ).json()
    bebida = client.post(
        "/api/productos",
        json={
            "nombre": "Refresco",
            "precio_venta": 28,
            "categoria_id": cat,
            "receta": [{"insumo_id": refresco, "cantidad": 1}],
        },
        headers=admin,
    ).json()
    return {
        "tortilla": tor,
        "carne": car,
        "refresco": refresco,
        "taco": taco["producto_id"],
        "bebida": bebida["producto_id"],
        "categoria": cat,
    }


@pytest.fixture
def turno(client, admin) -> dict:
    r = client.post("/api/turno/abrir", json={"fondo_inicial": 500}, headers=admin)
    assert r.status_code == 200, r.text
    return r.json()["turno"]


@pytest.fixture
def stock(client, admin):
    """Función auxiliar: regresa el insumo (existencia y costo promedio) por id."""

    def _stock(insumo_id: int) -> dict:
        return next(i for i in client.get("/api/insumos", headers=admin).json() if i["insumo_id"] == insumo_id)

    return _stock


@pytest.fixture
def vender(client, admin):
    """Función auxiliar para registrar una venta y regresar la respuesta."""

    def _vender(items, metodo_pago_id=1, headers=None, **extra):
        body = {
            "items": [{"producto_id": p, "cantidad": q} for p, q in items],
            "metodo_pago_id": metodo_pago_id,
            **extra,
        }
        return client.post("/api/ventas", json=body, headers=headers or admin)

    return _vender
