"""Contraseñas (PBKDF2-SHA256, librería estándar) y sesiones por token."""

import hashlib
import hmac
import secrets
import threading
from datetime import datetime, timedelta

from fastapi import Depends, Header, HTTPException

from . import config
from .db import get_db

_ITER = 200_000
_sessions: dict[str, dict] = {}
_lock = threading.Lock()


def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    salt = salt or secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), _ITER).hex()
    return h, salt


def verify_password(password: str, password_hash: str, salt: str) -> bool:
    h, _ = hash_password(password, salt)
    return hmac.compare_digest(h, password_hash)


def create_session(user: dict) -> str:
    token = secrets.token_urlsafe(32)
    with _lock:
        _sessions[token] = {
            "usuario_id": user["usuario_id"],
            "expira": datetime.now() + timedelta(hours=config.SESSION_HOURS),
        }
    return token


def drop_session(token: str) -> None:
    with _lock:
        _sessions.pop(token, None)


def drop_user_sessions(usuario_id: int) -> None:
    with _lock:
        for t in [t for t, s in _sessions.items() if s["usuario_id"] == usuario_id]:
            _sessions.pop(t, None)


def _token_from_header(authorization: str | None) -> str | None:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None


def current_user(authorization: str | None = Header(default=None), conn=Depends(get_db)) -> dict:
    token = _token_from_header(authorization)
    if not token:
        raise HTTPException(401, "Sesión no iniciada")
    with _lock:
        s = _sessions.get(token)
        if not s or s["expira"] < datetime.now():
            _sessions.pop(token, None)
            raise HTTPException(401, "La sesión expiró, vuelve a iniciar sesión")
        s["expira"] = datetime.now() + timedelta(hours=config.SESSION_HOURS)
    row = conn.execute(
        "SELECT usuario_id, username, nombre, rol, activo FROM dim_usuario WHERE usuario_id=?",
        (s["usuario_id"],),
    ).fetchone()
    if not row or not row["activo"]:
        drop_session(token)
        raise HTTPException(401, "Usuario inactivo")
    u = dict(row)
    u["token"] = token
    return u


def require_admin(user: dict = Depends(current_user)) -> dict:
    if user["rol"] != "ADMIN":
        raise HTTPException(403, "Esta función es solo para administradores")
    return user
