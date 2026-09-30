"""Catálogos: categorías, productos + recetas, insumos, proveedores, métodos de pago."""

import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..db import audit, get_db, now_str
from ..security import current_user, require_admin
from ..services import mover_inventario

router = APIRouter(prefix="/api", tags=["catalogo"])

UNIDADES = ["kg", "g", "l", "ml", "pz", "paq", "caja", "porción"]


def _integrity(e: sqlite3.IntegrityError):
    msg = str(e)
    if "UNIQUE" in msg:
        raise HTTPException(400, "Ya existe un registro con ese nombre o código")
    raise HTTPException(400, f"Dato inválido: {msg}")


# ------------------------------ CATEGORÍAS ------------------------------
class CategoriaIn(BaseModel):
    nombre: str = Field(min_length=1)
    color: str = "#E4572E"
    orden: int = 0
    activo: bool = True


@router.get("/categorias")
def listar_categorias(user=Depends(current_user), conn=Depends(get_db)):
    return [
        dict(r)
        for r in conn.execute(
            """SELECT c.*, (SELECT COUNT(*) FROM dim_producto p WHERE p.categoria_id=c.categoria_id AND p.activo=1) AS productos
           FROM dim_categoria c ORDER BY c.orden, c.nombre"""
        )
    ]


@router.post("/categorias")
def crear_categoria(data: CategoriaIn, user=Depends(require_admin), conn=Depends(get_db)):
    try:
        with conn:
            cur = conn.execute(
                "INSERT INTO dim_categoria(nombre, color, orden, activo) VALUES (?,?,?,?)",
                (data.nombre.strip(), data.color, data.orden, int(data.activo)),
            )
            audit(conn, user["usuario_id"], "CREAR", "dim_categoria", cur.lastrowid, data.nombre)
    except sqlite3.IntegrityError as e:
        _integrity(e)
    return {"categoria_id": cur.lastrowid}


@router.put("/categorias/{cid}")
def editar_categoria(cid: int, data: CategoriaIn, user=Depends(require_admin), conn=Depends(get_db)):
    try:
        with conn:
            conn.execute(
                "UPDATE dim_categoria SET nombre=?, color=?, orden=?, activo=? WHERE categoria_id=?",
                (data.nombre.strip(), data.color, data.orden, int(data.activo), cid),
            )
            audit(conn, user["usuario_id"], "EDITAR", "dim_categoria", cid, data.nombre)
    except sqlite3.IntegrityError as e:
        _integrity(e)
    return {"ok": True}


# ------------------------------ PRODUCTOS ------------------------------
class RecetaItem(BaseModel):
    insumo_id: int
    cantidad: float = Field(gt=0)


class ProductoIn(BaseModel):
    codigo: str | None = None
    nombre: str = Field(min_length=1)
    categoria_id: int | None = None
    precio_venta: float = Field(ge=0)
    activo: bool = True
    receta: list[RecetaItem] = []


def _productos(conn, solo_activos=False, producto_id=None):
    where, params = [], []
    if solo_activos:
        where.append("p.activo=1")
    if producto_id:
        where.append("p.producto_id=?")
        params.append(producto_id)
    sql = f"""SELECT p.*, c.nombre AS categoria, c.color AS categoria_color, vc.costo_teorico, vc.margen_teorico,
                     vc.num_insumos
              FROM dim_producto p
              LEFT JOIN dim_categoria c ON c.categoria_id=p.categoria_id
              LEFT JOIN v_costo_receta vc ON vc.producto_id=p.producto_id
              {"WHERE " + " AND ".join(where) if where else ""}
              ORDER BY c.orden, c.nombre, p.nombre"""
    rows = [dict(r) for r in conn.execute(sql, params)]
    recetas = {}
    for r in conn.execute(
        """SELECT r.producto_id, r.insumo_id, r.cantidad, i.nombre, i.unidad, i.costo_promedio,
                  ROUND(r.cantidad*i.costo_promedio, 4) AS costo
           FROM dim_receta r JOIN dim_insumo i ON i.insumo_id=r.insumo_id ORDER BY i.nombre"""
    ):
        recetas.setdefault(r["producto_id"], []).append(dict(r))
    for p in rows:
        p["receta"] = recetas.get(p["producto_id"], [])
        p["margen_teorico_pct"] = round(p["margen_teorico"] / p["precio_venta"], 4) if p["precio_venta"] else 0
    return rows


@router.get("/productos")
def listar_productos(solo_activos: bool = False, user=Depends(current_user), conn=Depends(get_db)):
    return _productos(conn, solo_activos)


def _guardar_receta(conn, producto_id: int, receta: list[RecetaItem]):
    ids = [r.insumo_id for r in receta]
    if len(ids) != len(set(ids)):
        raise HTTPException(400, "La receta tiene insumos repetidos")
    conn.execute("DELETE FROM dim_receta WHERE producto_id=?", (producto_id,))
    for r in receta:
        conn.execute(
            "INSERT INTO dim_receta(producto_id, insumo_id, cantidad) VALUES (?,?,?)",
            (producto_id, r.insumo_id, r.cantidad),
        )


@router.post("/productos")
def crear_producto(data: ProductoIn, user=Depends(require_admin), conn=Depends(get_db)):
    try:
        with conn:
            cur = conn.execute(
                "INSERT INTO dim_producto(codigo, nombre, categoria_id, precio_venta, activo, actualizado_en) VALUES (?,?,?,?,?,?)",
                (
                    (data.codigo or "").strip() or None,
                    data.nombre.strip(),
                    data.categoria_id,
                    data.precio_venta,
                    int(data.activo),
                    now_str(),
                ),
            )
            _guardar_receta(conn, cur.lastrowid, data.receta)
            audit(
                conn, user["usuario_id"], "CREAR", "dim_producto", cur.lastrowid, f"{data.nombre} ${data.precio_venta}"
            )
    except sqlite3.IntegrityError as e:
        _integrity(e)
    return _productos(conn, producto_id=cur.lastrowid)[0]


@router.put("/productos/{pid}")
def editar_producto(pid: int, data: ProductoIn, user=Depends(require_admin), conn=Depends(get_db)):
    prev = conn.execute("SELECT * FROM dim_producto WHERE producto_id=?", (pid,)).fetchone()
    if not prev:
        raise HTTPException(404, "Producto no encontrado")
    try:
        with conn:
            conn.execute(
                """UPDATE dim_producto SET codigo=?, nombre=?, categoria_id=?, precio_venta=?, activo=?, actualizado_en=?
                   WHERE producto_id=?""",
                (
                    (data.codigo or "").strip() or None,
                    data.nombre.strip(),
                    data.categoria_id,
                    data.precio_venta,
                    int(data.activo),
                    now_str(),
                    pid,
                ),
            )
            _guardar_receta(conn, pid, data.receta)
            cambio_precio = (
                f" precio {prev['precio_venta']} -> {data.precio_venta}"
                if prev["precio_venta"] != data.precio_venta
                else ""
            )
            audit(conn, user["usuario_id"], "EDITAR", "dim_producto", pid, f"{data.nombre}{cambio_precio}")
    except sqlite3.IntegrityError as e:
        _integrity(e)
    return _productos(conn, producto_id=pid)[0]


# ------------------------------ INSUMOS ------------------------------
class InsumoIn(BaseModel):
    codigo: str | None = None
    nombre: str = Field(min_length=1)
    unidad: str = Field(min_length=1)
    stock_minimo: float = Field(ge=0, default=0)
    proveedor_id: int | None = None
    activo: bool = True
    stock_inicial: float = Field(ge=0, default=0)  # solo al crear
    costo_unitario: float = Field(ge=0, default=0)  # solo al crear


@router.get("/unidades")
def unidades(user=Depends(current_user)):
    return UNIDADES


@router.get("/insumos")
def listar_insumos(incluir_inactivos: bool = False, user=Depends(current_user), conn=Depends(get_db)):
    return [
        dict(r)
        for r in conn.execute(
            f"""SELECT i.*, pr.nombre AS proveedor, ROUND(i.stock_actual*i.costo_promedio,2) AS valor,
                  CASE WHEN i.stock_actual <= 0 THEN 'AGOTADO' WHEN i.stock_actual <= i.stock_minimo THEN 'BAJO'
                       ELSE 'OK' END AS estado,
                  (SELECT COUNT(*) FROM dim_receta r WHERE r.insumo_id=i.insumo_id) AS usado_en
           FROM dim_insumo i LEFT JOIN dim_proveedor pr ON pr.proveedor_id=i.proveedor_id
           {"" if incluir_inactivos else "WHERE i.activo=1"}
           ORDER BY i.nombre"""
        )
    ]


@router.post("/insumos")
def crear_insumo(data: InsumoIn, user=Depends(require_admin), conn=Depends(get_db)):
    try:
        with conn:
            cur = conn.execute(
                """INSERT INTO dim_insumo(codigo, nombre, unidad, stock_minimo, proveedor_id, activo, costo_promedio, actualizado_en)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (
                    (data.codigo or "").strip() or None,
                    data.nombre.strip(),
                    data.unidad,
                    data.stock_minimo,
                    data.proveedor_id,
                    int(data.activo),
                    data.costo_unitario,
                    now_str(),
                ),
            )
            iid = cur.lastrowid
            if data.stock_inicial > 0:
                mover_inventario(
                    conn,
                    iid,
                    data.stock_inicial,
                    "INICIAL",
                    costo_unitario=data.costo_unitario,
                    referencia_tipo="ALTA",
                    motivo="Inventario inicial",
                    usuario_id=user["usuario_id"],
                )
            audit(conn, user["usuario_id"], "CREAR", "dim_insumo", iid, data.nombre)
    except sqlite3.IntegrityError as e:
        _integrity(e)
    return {"insumo_id": iid}


@router.put("/insumos/{iid}")
def editar_insumo(iid: int, data: InsumoIn, user=Depends(require_admin), conn=Depends(get_db)):
    if not data.activo:
        usado = conn.execute(
            """SELECT p.nombre FROM dim_receta r JOIN dim_producto p ON p.producto_id=r.producto_id
               WHERE r.insumo_id=? AND p.activo=1 LIMIT 3""",
            (iid,),
        ).fetchall()
        if usado:
            raise HTTPException(400, "No se puede desactivar: se usa en " + ", ".join(u["nombre"] for u in usado))
    try:
        with conn:
            conn.execute(
                """UPDATE dim_insumo SET codigo=?, nombre=?, unidad=?, stock_minimo=?, proveedor_id=?, activo=?,
                   actualizado_en=? WHERE insumo_id=?""",
                (
                    (data.codigo or "").strip() or None,
                    data.nombre.strip(),
                    data.unidad,
                    data.stock_minimo,
                    data.proveedor_id,
                    int(data.activo),
                    now_str(),
                    iid,
                ),
            )
            audit(conn, user["usuario_id"], "EDITAR", "dim_insumo", iid, data.nombre)
    except sqlite3.IntegrityError as e:
        _integrity(e)
    return {"ok": True}


# ------------------------------ PROVEEDORES ------------------------------
class ProveedorIn(BaseModel):
    nombre: str = Field(min_length=1)
    contacto: str | None = None
    telefono: str | None = None
    email: str | None = None
    activo: bool = True


@router.get("/proveedores")
def listar_proveedores(user=Depends(current_user), conn=Depends(get_db)):
    return [
        dict(r)
        for r in conn.execute(
            """SELECT pr.*, (SELECT COUNT(*) FROM dim_insumo i WHERE i.proveedor_id=pr.proveedor_id AND i.activo=1) AS insumos,
                  (SELECT MAX(fecha_hora) FROM entradas_inventario e WHERE e.proveedor_id=pr.proveedor_id) AS ultima_compra
           FROM dim_proveedor pr ORDER BY pr.nombre"""
        )
    ]


@router.post("/proveedores")
def crear_proveedor(data: ProveedorIn, user=Depends(require_admin), conn=Depends(get_db)):
    try:
        with conn:
            cur = conn.execute(
                "INSERT INTO dim_proveedor(nombre, contacto, telefono, email, activo) VALUES (?,?,?,?,?)",
                (data.nombre.strip(), data.contacto, data.telefono, data.email, int(data.activo)),
            )
            audit(conn, user["usuario_id"], "CREAR", "dim_proveedor", cur.lastrowid, data.nombre)
    except sqlite3.IntegrityError as e:
        _integrity(e)
    return {"proveedor_id": cur.lastrowid}


@router.put("/proveedores/{pid}")
def editar_proveedor(pid: int, data: ProveedorIn, user=Depends(require_admin), conn=Depends(get_db)):
    try:
        with conn:
            conn.execute(
                "UPDATE dim_proveedor SET nombre=?, contacto=?, telefono=?, email=?, activo=? WHERE proveedor_id=?",
                (data.nombre.strip(), data.contacto, data.telefono, data.email, int(data.activo), pid),
            )
            audit(conn, user["usuario_id"], "EDITAR", "dim_proveedor", pid, data.nombre)
    except sqlite3.IntegrityError as e:
        _integrity(e)
    return {"ok": True}


# ------------------------------ MÉTODOS DE PAGO ------------------------------
class MetodoIn(BaseModel):
    nombre: str = Field(min_length=1)
    es_efectivo: bool = False
    activo: bool = True


@router.get("/metodos-pago")
def listar_metodos(user=Depends(current_user), conn=Depends(get_db)):
    return [dict(r) for r in conn.execute("SELECT * FROM dim_metodo_pago ORDER BY metodo_pago_id")]


@router.post("/metodos-pago")
def crear_metodo(data: MetodoIn, user=Depends(require_admin), conn=Depends(get_db)):
    try:
        with conn:
            cur = conn.execute(
                "INSERT INTO dim_metodo_pago(nombre, es_efectivo, activo) VALUES (?,?,?)",
                (data.nombre.strip(), int(data.es_efectivo), int(data.activo)),
            )
            audit(conn, user["usuario_id"], "CREAR", "dim_metodo_pago", cur.lastrowid, data.nombre)
    except sqlite3.IntegrityError as e:
        _integrity(e)
    return {"metodo_pago_id": cur.lastrowid}


@router.put("/metodos-pago/{mid}")
def editar_metodo(mid: int, data: MetodoIn, user=Depends(require_admin), conn=Depends(get_db)):
    try:
        with conn:
            conn.execute(
                "UPDATE dim_metodo_pago SET nombre=?, es_efectivo=?, activo=? WHERE metodo_pago_id=?",
                (data.nombre.strip(), int(data.es_efectivo), int(data.activo), mid),
            )
            audit(conn, user["usuario_id"], "EDITAR", "dim_metodo_pago", mid, data.nombre)
    except sqlite3.IntegrityError as e:
        _integrity(e)
    return {"ok": True}
