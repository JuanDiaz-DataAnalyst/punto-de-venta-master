from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import config, security
from ..db import audit, get_config, get_db, now_str

router = APIRouter(prefix="/api", tags=["auth"])


class LoginIn(BaseModel):
    username: str
    password: str


class SetupIn(BaseModel):
    nombre_negocio: str = Field(min_length=1)
    admin_nombre: str = Field(min_length=1)
    admin_username: str = Field(min_length=3)
    admin_password: str = Field(min_length=4)
    datos_ejemplo: bool = False


class CambioPasswordIn(BaseModel):
    actual: str
    nueva: str = Field(min_length=4)


def _user_out(u) -> dict:
    return {"usuario_id": u["usuario_id"], "username": u["username"], "nombre": u["nombre"], "rol": u["rol"]}


@router.get("/estado")
def estado(conn=Depends(get_db)):
    n = conn.execute("SELECT COUNT(*) FROM dim_usuario").fetchone()[0]
    cfg = get_config(conn)
    return {
        "requiere_configuracion": n == 0,
        "app": config.APP_NAME,
        "version": config.APP_VERSION,
        "nombre_negocio": cfg.get("nombre_negocio"),
        "moneda": cfg.get("moneda", "$"),
    }


@router.post("/setup")
def setup(data: SetupIn, conn=Depends(get_db)):
    if conn.execute("SELECT COUNT(*) FROM dim_usuario").fetchone()[0] > 0:
        raise HTTPException(400, "El sistema ya está configurado")
    h, s = security.hash_password(data.admin_password)
    with conn:
        cur = conn.execute(
            "INSERT INTO dim_usuario(username, nombre, rol, password_hash, salt) VALUES (?,?,?,?,?)",
            (data.admin_username.strip(), data.admin_nombre.strip(), "ADMIN", h, s),
        )
        conn.execute("UPDATE config SET valor=? WHERE clave='nombre_negocio'", (data.nombre_negocio.strip(),))
        audit(conn, cur.lastrowid, "CONFIGURACION_INICIAL", detalle=data.nombre_negocio)
    if data.datos_ejemplo:
        from ..seed import cargar_datos_ejemplo

        cargar_datos_ejemplo(conn, admin_id=cur.lastrowid)
    return {"ok": True}


@router.post("/login")
def login(data: LoginIn, conn=Depends(get_db)):
    u = conn.execute("SELECT * FROM dim_usuario WHERE username=?", (data.username.strip(),)).fetchone()
    if not u or not security.verify_password(data.password, u["password_hash"], u["salt"]):
        with conn:
            audit(conn, u["usuario_id"] if u else None, "LOGIN_FALLIDO", detalle=data.username)
        raise HTTPException(401, "Usuario o contraseña incorrectos")
    if not u["activo"]:
        raise HTTPException(403, "El usuario está desactivado")
    token = security.create_session(dict(u))
    with conn:
        conn.execute("UPDATE dim_usuario SET ultimo_acceso=? WHERE usuario_id=?", (now_str(), u["usuario_id"]))
        audit(conn, u["usuario_id"], "LOGIN")
    return {"token": token, "usuario": _user_out(u)}


@router.post("/logout")
def logout(user=Depends(security.current_user), conn=Depends(get_db)):
    security.drop_session(user["token"])
    with conn:
        audit(conn, user["usuario_id"], "LOGOUT")
    return {"ok": True}


@router.get("/me")
def me(user=Depends(security.current_user)):
    return _user_out(user)


@router.post("/me/password")
def cambiar_password(data: CambioPasswordIn, user=Depends(security.current_user), conn=Depends(get_db)):
    u = conn.execute("SELECT * FROM dim_usuario WHERE usuario_id=?", (user["usuario_id"],)).fetchone()
    if not security.verify_password(data.actual, u["password_hash"], u["salt"]):
        raise HTTPException(400, "La contraseña actual no es correcta")
    h, s = security.hash_password(data.nueva)
    with conn:
        conn.execute("UPDATE dim_usuario SET password_hash=?, salt=? WHERE usuario_id=?", (h, s, u["usuario_id"]))
        audit(conn, u["usuario_id"], "CAMBIO_PASSWORD")
    return {"ok": True}
