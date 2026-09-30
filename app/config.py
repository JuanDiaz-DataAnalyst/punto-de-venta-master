"""Rutas y parámetros globales de la aplicación.

Los datos (base de datos, respaldos, exportaciones, logs) se guardan en
%LOCALAPPDATA%\\PuntoDeVentaMASTER en Windows, para que el programa pueda
instalarse en "Archivos de programa" sin problemas de permisos.
Se puede cambiar con la variable de entorno POS_DATA_DIR.
"""

import os
import sys
from pathlib import Path

from . import __version__

APP_NAME = "Punto de Venta MASTER"
APP_VERSION = __version__  # versión única, definida en app/__init__.py
HOST = "127.0.0.1"
PORT = int(os.environ.get("POS_PORT", "8765"))


def _base_resource_dir() -> Path:
    # Cuando está empaquetado con PyInstaller los recursos viven en sys._MEIPASS
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "app"
    return Path(__file__).resolve().parent


def _data_dir() -> Path:
    custom = os.environ.get("POS_DATA_DIR")
    if custom:
        return Path(custom)
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "PuntoDeVentaMASTER"
    return Path.home() / ".punto_de_venta_master"


RESOURCE_DIR = _base_resource_dir()
STATIC_DIR = RESOURCE_DIR / "static"

DATA_DIR = _data_dir()
DB_PATH = DATA_DIR / "pos.db"
BACKUP_DIR = DATA_DIR / "respaldos"
EXPORT_DIR = DATA_DIR / "exportaciones"
LOG_DIR = DATA_DIR / "logs"

MAX_BACKUPS = 20
SESSION_HOURS = 14


def ensure_dirs() -> None:
    for d in (DATA_DIR, BACKUP_DIR, EXPORT_DIR, LOG_DIR):
        d.mkdir(parents=True, exist_ok=True)
