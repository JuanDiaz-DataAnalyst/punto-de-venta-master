"""Configuración inicial, inicio de sesión y contraseñas."""

from tests.conftest import login


def test_estado_indica_configuracion_pendiente(client):
    assert client.get("/api/estado").json()["requiere_configuracion"] is True


def test_setup_solo_se_permite_una_vez(client, admin):
    r = client.post(
        "/api/setup",
        json={"nombre_negocio": "X", "admin_nombre": "X", "admin_username": "otro", "admin_password": "1234"},
    )
    assert r.status_code == 400


def test_login_incorrecto(client, admin):
    assert client.post("/api/login", json={"username": "admin", "password": "mala"}).status_code == 401


def test_endpoint_protegido_sin_token(client, admin):
    assert client.get("/api/insumos").status_code == 401
    assert client.get("/api/insumos", headers={"Authorization": "Bearer inventado"}).status_code == 401


def test_usuario_desactivado_pierde_acceso(client, admin, cajero):
    uid = next(u for u in client.get("/api/usuarios", headers=admin).json() if u["username"] == "caja1")["usuario_id"]
    r = client.put(
        f"/api/usuarios/{uid}",
        json={"username": "caja1", "nombre": "Cajero", "rol": "USER", "activo": False},
        headers=admin,
    )
    assert r.status_code == 200
    assert client.get("/api/me", headers=cajero).status_code == 401
    assert client.post("/api/login", json={"username": "caja1", "password": "1234"}).status_code == 403


def test_no_se_puede_quitar_el_ultimo_admin(client, admin):
    uid = client.get("/api/me", headers=admin).json()["usuario_id"]
    r = client.put(
        f"/api/usuarios/{uid}",
        json={"username": "admin", "nombre": "Admin", "rol": "USER", "activo": True},
        headers=admin,
    )
    assert r.status_code == 400


def test_cambio_de_password(client, admin):
    r = client.post("/api/me/password", json={"actual": "admin123", "nueva": "nueva123"}, headers=admin)
    assert r.status_code == 200
    assert login(client, "admin", "nueva123")
