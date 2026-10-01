"""Base de datos SQLite (gratuita, embebida, sin servidor).

Modelo en estrella:
  * fact_ventas                  -> tabla de hechos principal (una fila por renglón vendido)
  * fact_movimientos_inventario  -> hechos de inventario (entradas, backflush, ajustes)
  * dim_*                        -> dimensiones (fecha, usuario, producto, categoría,
                                     insumo, receta, proveedor, método de pago)
  * ventas / turnos / entradas   -> encabezados transaccionales
  * log_auditoria                -> registro de todo lo que hacen los usuarios
"""

import contextlib
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

from . import config

SCHEMA_VERSION = 2

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS config (
    clave TEXT PRIMARY KEY,
    valor TEXT
);

-- ======================= DIMENSIONES =======================
CREATE TABLE IF NOT EXISTS dim_fecha (
    fecha_id      INTEGER PRIMARY KEY,          -- AAAAMMDD
    fecha         TEXT NOT NULL UNIQUE,         -- AAAA-MM-DD
    anio          INTEGER NOT NULL,
    trimestre     INTEGER NOT NULL,
    mes           INTEGER NOT NULL,
    nombre_mes    TEXT NOT NULL,
    semana_iso    INTEGER NOT NULL,
    dia           INTEGER NOT NULL,
    dia_semana    INTEGER NOT NULL,             -- 1=lunes ... 7=domingo
    nombre_dia    TEXT NOT NULL,
    es_fin_semana INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_usuario (
    usuario_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE COLLATE NOCASE,
    nombre        TEXT NOT NULL,
    rol           TEXT NOT NULL CHECK (rol IN ('ADMIN','USER')),
    password_hash TEXT NOT NULL,
    salt          TEXT NOT NULL,
    activo        INTEGER NOT NULL DEFAULT 1,
    creado_en     TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    ultimo_acceso TEXT
);

CREATE TABLE IF NOT EXISTS dim_categoria (
    categoria_id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre       TEXT NOT NULL UNIQUE COLLATE NOCASE,
    color        TEXT NOT NULL DEFAULT '#E4572E',
    orden        INTEGER NOT NULL DEFAULT 0,
    activo       INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS dim_producto (
    producto_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo         TEXT UNIQUE COLLATE NOCASE,
    nombre         TEXT NOT NULL,
    categoria_id   INTEGER REFERENCES dim_categoria(categoria_id),
    precio_venta   REAL NOT NULL CHECK (precio_venta >= 0),
    activo         INTEGER NOT NULL DEFAULT 1,
    creado_en      TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    actualizado_en TEXT
);

CREATE TABLE IF NOT EXISTS dim_proveedor (
    proveedor_id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre       TEXT NOT NULL UNIQUE COLLATE NOCASE,
    contacto     TEXT,
    telefono     TEXT,
    email        TEXT,
    activo       INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS dim_insumo (
    insumo_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo         TEXT UNIQUE COLLATE NOCASE,
    nombre         TEXT NOT NULL UNIQUE COLLATE NOCASE,
    unidad         TEXT NOT NULL,                 -- kg, g, l, ml, pz
    costo_promedio REAL NOT NULL DEFAULT 0,       -- costo promedio ponderado por unidad
    stock_actual   REAL NOT NULL DEFAULT 0,
    stock_minimo   REAL NOT NULL DEFAULT 0,
    proveedor_id   INTEGER REFERENCES dim_proveedor(proveedor_id),
    activo         INTEGER NOT NULL DEFAULT 1,
    creado_en      TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    actualizado_en TEXT
);

-- Receta / lista de materiales: cuánto de cada insumo consume 1 unidad de producto
CREATE TABLE IF NOT EXISTS dim_receta (
    producto_id INTEGER NOT NULL REFERENCES dim_producto(producto_id) ON DELETE CASCADE,
    insumo_id   INTEGER NOT NULL REFERENCES dim_insumo(insumo_id),
    cantidad    REAL NOT NULL CHECK (cantidad > 0),
    PRIMARY KEY (producto_id, insumo_id)
);

CREATE TABLE IF NOT EXISTS dim_metodo_pago (
    metodo_pago_id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre         TEXT NOT NULL UNIQUE,
    es_efectivo    INTEGER NOT NULL DEFAULT 0,
    activo         INTEGER NOT NULL DEFAULT 1
);

-- ======================= CAJA =======================
CREATE TABLE IF NOT EXISTS turnos (
    turno_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_apertura_id INTEGER NOT NULL REFERENCES dim_usuario(usuario_id),
    usuario_cierre_id  INTEGER REFERENCES dim_usuario(usuario_id),
    apertura           TEXT NOT NULL,
    cierre             TEXT,
    fondo_inicial      REAL NOT NULL DEFAULT 0,
    efectivo_esperado  REAL,
    efectivo_contado   REAL,
    diferencia         REAL,
    notas              TEXT,
    estado             TEXT NOT NULL CHECK (estado IN ('ABIERTO','CERRADO'))
);

CREATE TABLE IF NOT EXISTS movimientos_caja (
    mov_caja_id INTEGER PRIMARY KEY AUTOINCREMENT,
    turno_id    INTEGER NOT NULL REFERENCES turnos(turno_id),
    fecha_hora  TEXT NOT NULL,
    tipo        TEXT NOT NULL CHECK (tipo IN ('INGRESO','RETIRO')),
    monto       REAL NOT NULL CHECK (monto > 0),
    concepto    TEXT NOT NULL,
    usuario_id  INTEGER NOT NULL REFERENCES dim_usuario(usuario_id)
);

-- ======================= VENTAS =======================
CREATE TABLE IF NOT EXISTS ventas (
    venta_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    folio              TEXT NOT NULL UNIQUE,
    fecha_hora         TEXT NOT NULL,
    fecha_id           INTEGER NOT NULL REFERENCES dim_fecha(fecha_id),
    usuario_id         INTEGER NOT NULL REFERENCES dim_usuario(usuario_id),
    turno_id           INTEGER REFERENCES turnos(turno_id),
    metodo_pago_id     INTEGER NOT NULL REFERENCES dim_metodo_pago(metodo_pago_id),
    subtotal           REAL NOT NULL,
    descuento          REAL NOT NULL DEFAULT 0,
    total              REAL NOT NULL,
    pago_recibido      REAL,
    cambio             REAL,
    costo_total        REAL NOT NULL DEFAULT 0,
    estado             TEXT NOT NULL DEFAULT 'PAGADA' CHECK (estado IN ('PAGADA','CANCELADA')),
    cancelada_en       TEXT,
    cancelada_por      INTEGER REFERENCES dim_usuario(usuario_id),
    motivo_cancelacion TEXT,
    cliente            TEXT,
    notas              TEXT,
    mesa               TEXT                          -- mesa / cuenta de origen (NULL en ventas directas)
);

-- TABLA DE HECHOS PRINCIPAL: grano = un renglón de producto vendido
CREATE TABLE IF NOT EXISTS fact_ventas (
    linea_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    venta_id        INTEGER NOT NULL REFERENCES ventas(venta_id),
    fecha_id        INTEGER NOT NULL REFERENCES dim_fecha(fecha_id),
    fecha_hora      TEXT NOT NULL,
    hora            INTEGER NOT NULL,
    producto_id     INTEGER NOT NULL REFERENCES dim_producto(producto_id),
    categoria_id    INTEGER REFERENCES dim_categoria(categoria_id),
    usuario_id      INTEGER NOT NULL REFERENCES dim_usuario(usuario_id),
    metodo_pago_id  INTEGER NOT NULL REFERENCES dim_metodo_pago(metodo_pago_id),
    turno_id        INTEGER REFERENCES turnos(turno_id),
    cantidad        REAL NOT NULL,
    precio_unitario REAL NOT NULL,
    importe_bruto   REAL NOT NULL,
    descuento       REAL NOT NULL DEFAULT 0,
    importe_neto    REAL NOT NULL,
    costo_unitario  REAL NOT NULL DEFAULT 0,
    costo_total     REAL NOT NULL DEFAULT 0,
    margen          REAL NOT NULL DEFAULT 0,
    nota            TEXT
);
CREATE INDEX IF NOT EXISTS ix_fv_fecha    ON fact_ventas(fecha_id);
CREATE INDEX IF NOT EXISTS ix_fv_producto ON fact_ventas(producto_id);
CREATE INDEX IF NOT EXISTS ix_fv_venta    ON fact_ventas(venta_id);
CREATE INDEX IF NOT EXISTS ix_v_fecha     ON ventas(fecha_id);
CREATE INDEX IF NOT EXISTS ix_v_turno     ON ventas(turno_id);

-- ======================= CUENTAS ABIERTAS (MESAS) =======================
-- Una cuenta es un ticket abierto por mesa. El folio se asigna al abrirla y es el mismo
-- con el que se registra la venta al cobrar. El inventario NO se mueve hasta el cobro.
CREATE TABLE IF NOT EXISTS cuentas (
    cuenta_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    folio           TEXT NOT NULL UNIQUE,
    mesa            TEXT NOT NULL,
    estado          TEXT NOT NULL DEFAULT 'ABIERTA' CHECK (estado IN ('ABIERTA','COBRADA','CANCELADA')),
    abierta_en      TEXT NOT NULL,
    usuario_id      INTEGER NOT NULL REFERENCES dim_usuario(usuario_id),
    descuento_tipo  TEXT NOT NULL DEFAULT '$' CHECK (descuento_tipo IN ('$','%')),
    descuento_valor REAL NOT NULL DEFAULT 0 CHECK (descuento_valor >= 0),
    cerrada_en      TEXT,
    venta_id        INTEGER REFERENCES ventas(venta_id),
    motivo_cancelacion TEXT
);
-- una sola cuenta abierta por mesa
CREATE UNIQUE INDEX IF NOT EXISTS ux_cuentas_mesa_abierta ON cuentas(mesa COLLATE NOCASE) WHERE estado = 'ABIERTA';

CREATE TABLE IF NOT EXISTS cuenta_items (
    item_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    cuenta_id   INTEGER NOT NULL REFERENCES cuentas(cuenta_id) ON DELETE CASCADE,
    producto_id INTEGER NOT NULL REFERENCES dim_producto(producto_id),
    cantidad    REAL NOT NULL CHECK (cantidad > 0),
    nota        TEXT,
    agregado_en TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_ci_cuenta ON cuenta_items(cuenta_id);

-- ======================= GASTOS FIJOS MENSUALES =======================
-- Monto mensual de cada gasto con su vigencia; el dashboard lo prorratea por día.
CREATE TABLE IF NOT EXISTS gastos_fijos (
    gasto_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    concepto       TEXT NOT NULL,
    categoria      TEXT NOT NULL,
    monto_mensual  REAL NOT NULL DEFAULT 0 CHECK (monto_mensual >= 0),
    vigente_desde  TEXT NOT NULL,                 -- AAAA-MM-DD
    vigente_hasta  TEXT,                          -- NULL = sigue vigente
    notas          TEXT,
    creado_en      TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    actualizado_en TEXT
);

-- ======================= INVENTARIO =======================
CREATE TABLE IF NOT EXISTS entradas_inventario (
    entrada_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha_hora   TEXT NOT NULL,
    proveedor_id INTEGER REFERENCES dim_proveedor(proveedor_id),
    factura      TEXT,
    notas        TEXT,
    usuario_id   INTEGER NOT NULL REFERENCES dim_usuario(usuario_id),
    total        REAL NOT NULL DEFAULT 0
);

-- Kardex: cada movimiento de cada insumo (cantidad con signo)
CREATE TABLE IF NOT EXISTS fact_movimientos_inventario (
    movimiento_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha_hora       TEXT NOT NULL,
    fecha_id         INTEGER NOT NULL REFERENCES dim_fecha(fecha_id),
    insumo_id        INTEGER NOT NULL REFERENCES dim_insumo(insumo_id),
    tipo             TEXT NOT NULL CHECK (tipo IN ('INICIAL','ENTRADA','BACKFLUSH','AJUSTE','CANCELACION')),
    cantidad         REAL NOT NULL,
    costo_unitario   REAL NOT NULL DEFAULT 0,
    costo_total      REAL NOT NULL DEFAULT 0,
    stock_resultante REAL NOT NULL,
    referencia_tipo  TEXT,          -- VENTA, ENTRADA, AJUSTE
    referencia_id    INTEGER,
    motivo           TEXT,
    usuario_id       INTEGER REFERENCES dim_usuario(usuario_id)
);
CREATE INDEX IF NOT EXISTS ix_mi_insumo ON fact_movimientos_inventario(insumo_id, fecha_hora);
CREATE INDEX IF NOT EXISTS ix_mi_fecha  ON fact_movimientos_inventario(fecha_id);
CREATE INDEX IF NOT EXISTS ix_mi_ref    ON fact_movimientos_inventario(referencia_tipo, referencia_id);

-- ======================= AUDITORÍA =======================
CREATE TABLE IF NOT EXISTS log_auditoria (
    log_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha_hora TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    usuario_id INTEGER REFERENCES dim_usuario(usuario_id),
    accion     TEXT NOT NULL,
    entidad    TEXT,
    entidad_id INTEGER,
    detalle    TEXT
);
CREATE INDEX IF NOT EXISTS ix_log_fecha ON log_auditoria(fecha_hora);

-- ======================= VISTAS ANALÍTICAS (listas para Power BI / Excel) =======================
DROP VIEW IF EXISTS v_ventas_detalle;
CREATE VIEW v_ventas_detalle AS
SELECT f.linea_id, v.folio, v.mesa, f.venta_id, f.fecha_hora, d.fecha, d.anio, d.mes, d.nombre_mes,
       d.semana_iso, d.nombre_dia, d.dia_semana, f.hora,
       p.codigo AS producto_codigo, p.nombre AS producto, c.nombre AS categoria,
       u.nombre AS usuario, m.nombre AS metodo_pago, f.turno_id,
       f.cantidad, f.precio_unitario, f.importe_bruto, f.descuento, f.importe_neto,
       f.costo_unitario, f.costo_total, f.margen,
       CASE WHEN f.importe_neto > 0 THEN ROUND(f.margen / f.importe_neto, 4) ELSE 0 END AS margen_pct
FROM fact_ventas f
JOIN ventas v          ON v.venta_id = f.venta_id
JOIN dim_fecha d       ON d.fecha_id = f.fecha_id
JOIN dim_producto p    ON p.producto_id = f.producto_id
LEFT JOIN dim_categoria c ON c.categoria_id = f.categoria_id
JOIN dim_usuario u     ON u.usuario_id = f.usuario_id
JOIN dim_metodo_pago m ON m.metodo_pago_id = f.metodo_pago_id
WHERE v.estado = 'PAGADA';

DROP VIEW IF EXISTS v_inventario_valorizado;
CREATE VIEW v_inventario_valorizado AS
SELECT i.insumo_id, i.codigo, i.nombre, i.unidad, i.stock_actual, i.stock_minimo,
       i.costo_promedio, ROUND(i.stock_actual * i.costo_promedio, 2) AS valor_inventario,
       pr.nombre AS proveedor,
       CASE WHEN i.stock_actual <= 0 THEN 'AGOTADO'
            WHEN i.stock_actual <= i.stock_minimo THEN 'BAJO'
            ELSE 'OK' END AS estado
FROM dim_insumo i
LEFT JOIN dim_proveedor pr ON pr.proveedor_id = i.proveedor_id
WHERE i.activo = 1;

DROP VIEW IF EXISTS v_costo_receta;
CREATE VIEW v_costo_receta AS
SELECT p.producto_id, p.codigo, p.nombre, c.nombre AS categoria, p.precio_venta,
       ROUND(COALESCE(SUM(r.cantidad * i.costo_promedio), 0), 4) AS costo_teorico,
       ROUND(p.precio_venta - COALESCE(SUM(r.cantidad * i.costo_promedio), 0), 2) AS margen_teorico,
       COUNT(r.insumo_id) AS num_insumos
FROM dim_producto p
LEFT JOIN dim_categoria c ON c.categoria_id = p.categoria_id
LEFT JOIN dim_receta r ON r.producto_id = p.producto_id
LEFT JOIN dim_insumo i ON i.insumo_id = r.insumo_id
GROUP BY p.producto_id;

DROP VIEW IF EXISTS v_movimientos_inventario;
CREATE VIEW v_movimientos_inventario AS
SELECT m.movimiento_id, m.fecha_hora, d.fecha, i.codigo AS insumo_codigo, i.nombre AS insumo,
       i.unidad, m.tipo, m.cantidad, m.costo_unitario, m.costo_total, m.stock_resultante,
       m.referencia_tipo, m.referencia_id, m.motivo, u.nombre AS usuario
FROM fact_movimientos_inventario m
JOIN dim_fecha d  ON d.fecha_id = m.fecha_id
JOIN dim_insumo i ON i.insumo_id = m.insumo_id
LEFT JOIN dim_usuario u ON u.usuario_id = m.usuario_id;
"""

DEFAULT_CONFIG = {
    "nombre_negocio": "Mi Negocio",
    "direccion": "",
    "telefono": "",
    "rfc": "",
    "mensaje_ticket": "¡Gracias por su compra!",
    "ancho_ticket": "80",
    "imprimir_auto": "0",
    "permitir_stock_negativo": "1",
    "mostrar_iva": "1",
    "tasa_iva": "16",
    "moneda": "$",
    "folio_prefijo": "V-",
}

METODOS_PAGO = [("Efectivo", 1), ("Tarjeta", 0), ("Transferencia", 0)]

MESES = [
    "Enero",
    "Febrero",
    "Marzo",
    "Abril",
    "Mayo",
    "Junio",
    "Julio",
    "Agosto",
    "Septiembre",
    "Octubre",
    "Noviembre",
    "Diciembre",
]
DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]


def connect(path: Path | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path or config.DB_PATH), timeout=15, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn


def get_db():
    """Dependencia de FastAPI: una conexión por petición."""
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def fecha_id_de(ts: str | datetime | date) -> int:
    if isinstance(ts, str):
        return int(ts[:10].replace("-", ""))
    return int(ts.strftime("%Y%m%d"))


def ensure_fecha(conn: sqlite3.Connection, d: date) -> int:
    fid = int(d.strftime("%Y%m%d"))
    conn.execute(
        """INSERT OR IGNORE INTO dim_fecha VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (
            fid,
            d.isoformat(),
            d.year,
            (d.month - 1) // 3 + 1,
            d.month,
            MESES[d.month - 1],
            d.isocalendar()[1],
            d.day,
            d.isoweekday(),
            DIAS[d.weekday()],
            1 if d.weekday() >= 5 else 0,
        ),
    )
    return fid


def _poblar_dim_fecha(conn: sqlite3.Connection, inicio: date, fin: date) -> None:
    rows = []
    d = inicio
    while d <= fin:
        rows.append(
            (
                int(d.strftime("%Y%m%d")),
                d.isoformat(),
                d.year,
                (d.month - 1) // 3 + 1,
                d.month,
                MESES[d.month - 1],
                d.isocalendar()[1],
                d.day,
                d.isoweekday(),
                DIAS[d.weekday()],
                1 if d.weekday() >= 5 else 0,
            )
        )
        d += timedelta(days=1)
    conn.executemany("INSERT OR IGNORE INTO dim_fecha VALUES (?,?,?,?,?,?,?,?,?,?,?)", rows)


def _columnas(conn: sqlite3.Connection, tabla: str) -> set[str]:
    return {r["name"] for r in conn.execute(f"PRAGMA table_info({tabla})")}


def _migrar_antes(conn: sqlite3.Connection) -> None:
    """Migraciones idempotentes que deben correr antes de crear vistas e índices nuevos."""
    cols = _columnas(conn, "ventas")
    if cols and "mesa" not in cols:  # v1 -> v2: la tabla existe pero aún no tiene la columna
        conn.execute("ALTER TABLE ventas ADD COLUMN mesa TEXT")


def init_db(path: Path | None = None) -> None:
    config.ensure_dirs()
    conn = connect(path)
    try:
        _migrar_antes(conn)
        conn.executescript(SCHEMA)
        with conn:
            # El consecutivo de folios es compartido por cuentas abiertas y ventas directas.
            # En bases anteriores arranca en el último venta_id para no repetir folios existentes.
            conn.execute(
                "INSERT OR IGNORE INTO config(clave, valor) "
                "SELECT 'folio_consecutivo', CAST(COALESCE(MAX(venta_id), 0) AS TEXT) FROM ventas"
            )
            for k, v in DEFAULT_CONFIG.items():
                conn.execute("INSERT OR IGNORE INTO config(clave, valor) VALUES (?,?)", (k, v))
            conn.execute(
                "INSERT OR REPLACE INTO config(clave, valor) VALUES ('schema_version', ?)", (str(SCHEMA_VERSION),)
            )
            for nombre, ef in METODOS_PAGO:
                conn.execute("INSERT OR IGNORE INTO dim_metodo_pago(nombre, es_efectivo) VALUES (?,?)", (nombre, ef))
            hoy = date.today()
            _poblar_dim_fecha(conn, date(hoy.year - 2, 1, 1), date(hoy.year + 5, 12, 31))
    finally:
        conn.close()


def get_config(conn: sqlite3.Connection) -> dict:
    return {r["clave"]: r["valor"] for r in conn.execute("SELECT clave, valor FROM config")}


def audit(
    conn: sqlite3.Connection,
    usuario_id,
    accion: str,
    entidad: str | None = None,
    entidad_id=None,
    detalle: str | None = None,
    fecha_hora: str | None = None,
) -> None:
    conn.execute(
        "INSERT INTO log_auditoria(fecha_hora, usuario_id, accion, entidad, entidad_id, detalle) VALUES (?,?,?,?,?,?)",
        (fecha_hora or now_str(), usuario_id, accion, entidad, entidad_id, detalle),
    )


def backup(etiqueta: str = "manual") -> Path:
    """Respaldo en caliente con la API de backup de SQLite; conserva los últimos N."""
    config.ensure_dirs()
    destino = config.BACKUP_DIR / f"pos_{datetime.now():%Y%m%d_%H%M%S}_{etiqueta}.db"
    src = connect()
    dst = sqlite3.connect(str(destino))
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    respaldos = sorted(config.BACKUP_DIR.glob("pos_*.db"))
    for viejo in respaldos[: -config.MAX_BACKUPS]:
        with contextlib.suppress(OSError):
            viejo.unlink()
    return destino


def restore(origen: Path) -> None:
    """Restaura un respaldo (se hace un respaldo previo de seguridad)."""
    backup("antes_de_restaurar")
    src = sqlite3.connect(str(origen))
    dst = connect()
    try:
        src.backup(dst)
    finally:
        src.close()
        dst.close()


__all__ = [
    "connect",
    "get_db",
    "init_db",
    "now_str",
    "fecha_id_de",
    "ensure_fecha",
    "get_config",
    "audit",
    "backup",
    "restore",
]
