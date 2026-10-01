# CLAUDE.md — guía del proyecto para Claude Code

Punto de venta de escritorio (Windows) para micro/pequeños negocios de comida. Todo el texto de la UI,
mensajes de error, comentarios y documentación va **en español (México)**; nombres de tablas/columnas
también en español.

## Stack
- Python 3.11+ · FastAPI + Uvicorn (API local en `127.0.0.1:8765`) · SQLite (módulo `sqlite3`, sin ORM)
- Frontend: HTML/CSS/JS con módulos ES **sin build ni framework**; Chart.js vendorizado en `app/static/vendor/`
- Ventana de escritorio con pywebview (WebView2). Empaquetado con PyInstaller + Inno Setup.
- La app debe funcionar **100 % offline**: no agregar CDNs, fuentes web ni llamadas a internet.

## Comandos
```bash
python -m pip install -r requirements-dev.txt     # dependencias (usar .venv)
python -m pytest                                  # pruebas (BD temporal por prueba)
ruff check . && ruff format --check .             # lint/formato (obligatorio antes de commit)
python -m app.main --server                       # solo API; docs en /api/docs
python -m app.main --browser --demo               # app en navegador con datos de ejemplo (BD vacía)
POS_DATA_DIR=/tmp/pos python -m app.main --server # usar otra carpeta de datos
pyinstaller packaging/PuntoDeVenta.spec --noconfirm   # ejecutable (solo en Windows)
python scripts/empaquetar_kit.py                  # kit de instalación para clientes (kit-instalacion/ + .zip)
```
En Windows: `scripts\build.bat` (lint + pruebas + exe + instalador) y `scripts\dev.bat`.

## Mapa del código
- `app/main.py` arranque (servidor en hilo + ventana), respaldo automático al iniciar
- `app/server.py` app FastAPI, manejadores de error, monta `/static`
- `app/db.py` **esquema completo, vistas analíticas**, `init_db`, `audit`, respaldos
- `app/services.py` **reglas de negocio**: `registrar_venta` (backflush), `cancelar_venta`,
  `mover_inventario` (costo promedio ponderado), `registrar_entrada`, `ajustar_inventario`, `resumen_turno`,
  cuentas por mesa (`abrir_cuenta`, `agregar_item`, `cobrar_cuenta`, `cancelar_cuenta`, `mover_consumos`), `siguiente_folio`,
  `prorratear_gastos` (gastos fijos por día para el dashboard)
- `app/routers/*.py` endpoints delgados; validan con Pydantic y llaman a `services`
- `app/security.py` PBKDF2 + sesiones en memoria; dependencias `current_user` / `require_admin`
- `app/static/js/app.js` router por hash y layout; `js/views/*.js` una pantalla por archivo; `js/ui.js` helpers
- `app/static/js/views/ayuda.js` ayuda para el usuario final (F1); al cambiar una función, actualizarla junto con `docs/manual-de-usuario.md`
- `distribucion/` fuentes del kit de instalación (guías .md, `.bat`); `scripts/empaquetar_kit.py` lo arma y lo convierte a HTML
- `app/routers/cuentas.py` mesas abiertas · `app/routers/gastos.py` gastos fijos (solo Admin)
- `tests/conftest.py` fixtures: `client`, `admin`, `cajero`, `catalogo`, `turno`, `vender`, `stock`

## Reglas de negocio que no se deben romper
1. Toda modificación de existencias pasa por `services.mover_inventario` (deja rastro en el kardex
   `fact_movimientos_inventario`). Nunca hacer `UPDATE dim_insumo SET stock_actual` directo.
2. Invariante: `dim_insumo.stock_actual == SUM(fact_movimientos_inventario.cantidad)` por insumo.
3. Los precios se leen de la BD en el servidor; nunca confiar en precios enviados por el cliente.
4. Una venta solo se registra con turno abierto; cancelar revierte exactamente el backflush original.
5. Los descuentos se prorratean por renglón para que `SUM(fact_ventas.importe_neto) == ventas.total`.
6. Operaciones con varias escrituras van en una transacción (`with conn:` o `BEGIN IMMEDIATE`).
7. Acciones relevantes se registran con `db.audit(...)`.
8. Endpoints de administración usan `Depends(require_admin)`; agregar la prueba en `tests/test_permisos.py`.
9. Todo folio sale de `services.siguiente_folio` (consecutivo único, nunca se reutiliza). Una cuenta abierta no mueve
   inventario; el backflush ocurre solo en `cobrar_cuenta` → `registrar_venta`, que conserva el folio de la cuenta.
10. Los gastos fijos no se guardan por periodo: se prorratean por día con `prorratear_gastos` según su vigencia.

## Convenciones
- Commits: Conventional Commits en español (`feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `build:`, `ci:`).
- Ramas: `feat/…`, `fix/…`; PR a `main` con CI en verde. Versiones con tags `vX.Y.Z` (dispara el build del .exe).
- Cambios de esquema: agregar migración idempotente en `db.init_db` y subir `SCHEMA_VERSION`; nunca borrar
  columnas con datos. Documentar en `docs/modelo-de-datos.md` y `CHANGELOG.md`.
- Cada bug corregido lleva una prueba que lo reproduce.
- Frontend: escapar todo texto de usuario con `esc()` antes de meterlo a `innerHTML`.
- Colores de gráficas: usar la paleta validada definida en `js/views/dashboard.js` (no inventar colores).

## Limitaciones conocidas
- Un solo equipo (SQLite). Varias terminales requeriría migrar a PostgreSQL.
- Las sesiones viven en memoria: reiniciar la app cierra sesiones (intencional).
- La impresión usa el diálogo de Windows (`window.print()` en un iframe); no hay ESC/POS directo.
