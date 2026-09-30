# -*- mode: python ; coding: utf-8 -*-
# Especificación de PyInstaller. Desde la raíz del repo:
#     pyinstaller packaging/PuntoDeVenta.spec --noconfirm --clean
import os

from PyInstaller.utils.hooks import collect_submodules

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))  # noqa: F821 - SPECPATH lo define PyInstaller

hidden = collect_submodules("app") + collect_submodules("uvicorn") + ["openpyxl", "anyio._backends._asyncio"]

a = Analysis(
    [os.path.join(SPECPATH, "launcher.py")],  # noqa: F821
    pathex=[ROOT],
    binaries=[],
    datas=[(os.path.join(ROOT, "app", "static"), os.path.join("app", "static"))],
    hiddenimports=hidden,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "numpy", "pandas", "PyQt5", "PyQt6", "PySide2", "PySide6"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PuntoDeVentaMASTER",
    debug=False,
    strip=False,
    upx=False,
    console=False,  # aplicación de ventana, sin consola
    icon=os.path.join(SPECPATH, "icono.ico"),  # noqa: F821
)

coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="PuntoDeVentaMASTER")
