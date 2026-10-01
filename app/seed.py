"""Datos de ejemplo: food truck con menú, recetas, inventario y 90 días de operación simulada.

El historial se genera con las MISMAS funciones de negocio que usa la app
(registrar_venta, registrar_entrada, ajustar_inventario, cancelar_venta), así que el
backflush, el costo promedio y el kardex quedan consistentes.
"""

import random
from datetime import date, datetime, timedelta

from . import security
from .db import audit
from .services import ajustar_inventario, cancelar_venta, registrar_entrada, registrar_venta

PROVEEDORES = [
    ("Carnicería El Toro", "Don Ramiro", "222 100 2001"),
    ("Tortillería La Güera", "Sra. Lupita", "222 100 2002"),
    ("Abarrotes Central", "Mostrador", "222 100 2003"),
    ("Refresquera del Valle", "Ruta 12", "222 100 2004"),
    ("Verdulería Doña Mary", "María", "222 100 2005"),
    ("Panadería San José", "José", "222 100 2006"),
]

# codigo, nombre, unidad, costo, stock_minimo, proveedor
INSUMOS = [
    ("TOR-M", "Tortilla de maíz", "pz", 0.60, 200, "Tortillería La Güera"),
    ("TOR-H", "Tortilla de harina", "pz", 2.20, 40, "Tortillería La Güera"),
    ("CAR-P", "Carne al pastor", "kg", 125, 4, "Carnicería El Toro"),
    ("CAR-B", "Bistec de res", "kg", 175, 3, "Carnicería El Toro"),
    ("CAR-PO", "Pollo deshebrado", "kg", 95, 3, "Carnicería El Toro"),
    ("CAR-H", "Carne para hamburguesa 150 g", "pz", 22, 20, "Carnicería El Toro"),
    ("TOC", "Tocino", "kg", 180, 1, "Carnicería El Toro"),
    ("PAN-H", "Pan de hamburguesa", "pz", 5.5, 24, "Panadería San José"),
    ("QUE", "Queso manchego", "kg", 180, 1.5, "Abarrotes Central"),
    ("PIN", "Piña", "kg", 25, 1.5, "Verdulería Doña Mary"),
    ("CEB", "Cebolla", "kg", 22, 2, "Verdulería Doña Mary"),
    ("CIL", "Cilantro", "kg", 40, 0.5, "Verdulería Doña Mary"),
    ("JIT", "Jitomate", "kg", 28, 2, "Verdulería Doña Mary"),
    ("LEC", "Lechuga", "kg", 30, 1, "Verdulería Doña Mary"),
    ("SAL-V", "Salsa verde", "l", 30, 2, "Abarrotes Central"),
    ("SAL-R", "Salsa roja", "l", 30, 2, "Abarrotes Central"),
    ("PAP", "Papas congeladas", "kg", 55, 5, "Abarrotes Central"),
    ("ACE", "Aceite vegetal", "l", 38, 4, "Abarrotes Central"),
    ("REF", "Refresco lata 355 ml", "pz", 11, 48, "Refresquera del Valle"),
    ("AGU", "Agua embotellada 600 ml", "pz", 6, 36, "Refresquera del Valle"),
    ("JAM", "Concentrado de jamaica", "l", 20, 3, "Abarrotes Central"),
    ("AZU", "Azúcar", "kg", 26, 2, "Abarrotes Central"),
    ("CAF", "Café molido", "kg", 280, 0.5, "Abarrotes Central"),
    ("LEH", "Leche entera", "l", 24, 4, "Abarrotes Central"),
    ("MAS", "Masa para churros", "kg", 30, 2, "Abarrotes Central"),
    ("CAJ", "Cajeta", "kg", 90, 0.5, "Abarrotes Central"),
    ("VAS", "Vaso desechable 12 oz", "pz", 1.2, 80, "Abarrotes Central"),
    ("CHA", "Charola desechable", "pz", 2.5, 80, "Abarrotes Central"),
]

CATEGORIAS = [
    ("Tacos", "#E4572E", 1),
    ("Hamburguesas", "#C0392B", 2),
    ("Bebidas", "#2E86AB", 3),
    ("Postres", "#8E5EA2", 4),
]

# codigo, nombre, categoría, precio, peso de popularidad, receta {codigo_insumo: cantidad}
PRODUCTOS = [
    (
        "T01",
        "Taco al pastor",
        "Tacos",
        25,
        30,
        {"TOR-M": 2, "CAR-P": 0.06, "PIN": 0.01, "CEB": 0.008, "CIL": 0.003, "SAL-V": 0.015},
    ),
    (
        "T02",
        "Taco de bistec",
        "Tacos",
        30,
        16,
        {"TOR-M": 2, "CAR-B": 0.065, "CEB": 0.008, "CIL": 0.003, "SAL-R": 0.015},
    ),
    ("T03", "Taco de pollo", "Tacos", 24, 9, {"TOR-M": 2, "CAR-PO": 0.065, "CEB": 0.008, "CIL": 0.003, "SAL-V": 0.015}),
    ("T04", "Gringa al pastor", "Tacos", 68, 8, {"TOR-H": 2, "CAR-P": 0.09, "QUE": 0.05, "PIN": 0.015, "SAL-V": 0.02}),
    (
        "T05",
        "Orden 5 tacos pastor",
        "Tacos",
        115,
        7,
        {"TOR-M": 10, "CAR-P": 0.3, "PIN": 0.05, "CEB": 0.04, "CIL": 0.015, "SAL-V": 0.075, "CHA": 1},
    ),
    (
        "H01",
        "Hamburguesa clásica",
        "Hamburguesas",
        98,
        10,
        {"PAN-H": 1, "CAR-H": 1, "QUE": 0.03, "JIT": 0.03, "LEC": 0.02, "CEB": 0.015, "CHA": 1},
    ),
    (
        "H02",
        "Hamburguesa doble con tocino",
        "Hamburguesas",
        149,
        5,
        {"PAN-H": 1, "CAR-H": 2, "QUE": 0.06, "TOC": 0.04, "JIT": 0.03, "LEC": 0.02, "CHA": 1},
    ),
    ("H03", "Papas a la francesa", "Hamburguesas", 52, 9, {"PAP": 0.2, "ACE": 0.03, "CHA": 1}),
    (
        "H04",
        "Combo clásico (hamburguesa + papas + refresco)",
        "Hamburguesas",
        155,
        6,
        {
            "PAN-H": 1,
            "CAR-H": 1,
            "QUE": 0.03,
            "JIT": 0.03,
            "LEC": 0.02,
            "CEB": 0.015,
            "PAP": 0.2,
            "ACE": 0.03,
            "REF": 1,
            "CHA": 1,
        },
    ),
    ("B01", "Refresco de lata", "Bebidas", 28, 18, {"REF": 1}),
    ("B02", "Agua embotellada", "Bebidas", 20, 7, {"AGU": 1}),
    ("B03", "Agua de jamaica", "Bebidas", 32, 10, {"JAM": 0.35, "AZU": 0.03, "VAS": 1}),
    ("B04", "Café americano", "Bebidas", 30, 3, {"CAF": 0.015, "AZU": 0.01, "VAS": 1}),
    ("B05", "Café con leche", "Bebidas", 38, 2, {"CAF": 0.015, "LEH": 0.2, "AZU": 0.01, "VAS": 1}),
    ("P01", "Churros (3 pz)", "Postres", 45, 5, {"MAS": 0.15, "ACE": 0.03, "AZU": 0.02}),
    ("P02", "Churros con cajeta", "Postres", 58, 3, {"MAS": 0.15, "ACE": 0.03, "AZU": 0.02, "CAJ": 0.05}),
    ("P03", "Pay de queso (rebanada)", "Postres", 55, 1, {"QUE": 0.02, "AZU": 0.02, "LEH": 0.05}),
]

# concepto, categoría, monto mensual (food truck con 3 personas en nómina)
GASTOS_FIJOS = [
    ("Salarios de cocina", "Nómina", 18000),
    ("Salarios de meseros / servicio", "Nómina", 14000),
    ("Salario del encargado o administrador", "Nómina", 9000),
    ("Cargas sociales (IMSS, INFONAVIT, SAR)", "Nómina", 6500),
    ("Renta del local", "Renta", 9000),
    ("Electricidad", "Servicios", 1800),
    ("Agua", "Servicios", 900),
    ("Gas", "Servicios", 4200),
    ("Internet y teléfono", "Servicios", 700),
    ("Mantenimiento de equipo y local", "Mantenimiento", 1500),
    ("Publicidad y redes sociales", "Marketing", 2500),
    ("Contador", "Administrativos", 1800),
    ("Licencias y permisos", "Impuestos y permisos", 900),
]

HORAS_PESO = {13: 6, 14: 12, 15: 11, 16: 6, 17: 5, 18: 7, 19: 10, 20: 14, 21: 13, 22: 8}
DIA_FACTOR = {0: 0.75, 1: 0.8, 2: 0.9, 3: 0.95, 4: 1.3, 5: 1.55, 6: 1.35}  # lunes..domingo


def _catalogo(conn, admin_id: int) -> dict:
    ids = {"prov": {}, "ins": {}, "cat": {}, "prod": {}}
    for nombre, contacto, tel in PROVEEDORES:
        cur = conn.execute(
            "INSERT INTO dim_proveedor(nombre, contacto, telefono) VALUES (?,?,?)", (nombre, contacto, tel)
        )
        ids["prov"][nombre] = cur.lastrowid
    for cod, nombre, unidad, costo, minimo, prov in INSUMOS:
        cur = conn.execute(
            """INSERT INTO dim_insumo(codigo, nombre, unidad, costo_promedio, stock_minimo, proveedor_id)
               VALUES (?,?,?,?,?,?)""",
            (cod, nombre, unidad, costo, minimo, ids["prov"][prov]),
        )
        ids["ins"][cod] = cur.lastrowid
    for nombre, color, orden in CATEGORIAS:
        cur = conn.execute("INSERT INTO dim_categoria(nombre, color, orden) VALUES (?,?,?)", (nombre, color, orden))
        ids["cat"][nombre] = cur.lastrowid
    for cod, nombre, cat, precio, _peso, receta in PRODUCTOS:
        cur = conn.execute(
            "INSERT INTO dim_producto(codigo, nombre, categoria_id, precio_venta) VALUES (?,?,?,?)",
            (cod, nombre, ids["cat"][cat], precio),
        )
        ids["prod"][cod] = cur.lastrowid
        for ic, q in receta.items():
            conn.execute(
                "INSERT INTO dim_receta(producto_id, insumo_id, cantidad) VALUES (?,?,?)",
                (cur.lastrowid, ids["ins"][ic], q),
            )
    conn.execute("UPDATE config SET valor=? WHERE clave='direccion'", ("Av. Juárez 2915, Puebla, Pue.",))
    conn.execute("UPDATE config SET valor=? WHERE clave='telefono'", ("Tel. 222 000 0000",))
    audit(conn, admin_id, "DATOS_EJEMPLO", detalle="Catálogo de ejemplo cargado")
    return ids


def _uso_diario_esperado(tickets_dia: float, items_por_ticket: float) -> dict[str, float]:
    total_peso = sum(p[4] for p in PRODUCTOS)
    uso: dict[str, float] = {}
    for _c, _n, _cat, _pr, peso, receta in PRODUCTOS:
        unidades = tickets_dia * items_por_ticket * peso / total_peso
        for ic, q in receta.items():
            uso[ic] = uso.get(ic, 0) + unidades * q
    return uso


def _ts(d: date, h: int, m: int, s: int = 0) -> str:
    return datetime(d.year, d.month, d.day, h, m, s).strftime("%Y-%m-%d %H:%M:%S")


def cargar_datos_ejemplo(conn, admin_id: int, dias: int = 90, semilla: int = 7) -> None:
    rnd = random.Random(semilla)
    conn.execute("BEGIN")
    try:
        ids = _catalogo(conn, admin_id)
        # cajeros de ejemplo (contraseña 1234)
        cajeros = []
        for user, nombre in (("carla", "Carla Méndez"), ("luis", "Luis Ramírez")):
            h, s = security.hash_password("1234")
            conn.execute(
                "INSERT OR IGNORE INTO dim_usuario(username, nombre, rol, password_hash, salt) VALUES (?,?,?,?,?)",
                (user, nombre, "USER", h, s),
            )
            cajeros.append(conn.execute("SELECT usuario_id FROM dim_usuario WHERE username=?", (user,)).fetchone()[0])

        metodos = {r["nombre"]: r["metodo_pago_id"] for r in conn.execute("SELECT * FROM dim_metodo_pago")}
        costo_base = {c[0]: c[3] for c in INSUMOS}
        prov_ins = {c[0]: ids["prov"][c[5]] for c in INSUMOS}
        minimos = {c[0]: c[4] for c in INSUMOS}
        uso = _uso_diario_esperado(62, 2.8)
        productos = [(ids["prod"][p[0]], p[4]) for p in PRODUCTOS]
        pids, pesos = [p[0] for p in productos], [p[1] for p in productos]
        horas, hpesos = list(HORAS_PESO), list(HORAS_PESO.values())

        inicio = date.today() - timedelta(days=dias)
        # inventario inicial: ~6 días de consumo
        for cod, iid in ids["ins"].items():
            q = round(uso.get(cod, 0) * 6 + minimos[cod] * 1.5, 2)
            registrar_entrada(
                conn,
                admin_id,
                [{"insumo_id": iid, "cantidad": q, "costo_unitario": costo_base[cod]}],
                prov_ins[cod],
                "INV-INICIAL",
                "Inventario inicial",
                _ts(inicio - timedelta(days=1), 10, 0),
            )

        for n in range(dias):
            d = inicio + timedelta(days=n)
            inflacion = 1 + 0.06 * n / dias  # costos suben ~6% en el periodo

            # compras lunes y jueves: reponer a 5 días de consumo + mínimo
            if d.weekday() in (0, 3) or n == 0:
                por_prov: dict[int, list] = {}
                for cod, iid in ids["ins"].items():
                    stock = conn.execute("SELECT stock_actual FROM dim_insumo WHERE insumo_id=?", (iid,)).fetchone()[0]
                    objetivo = uso.get(cod, 0) * 5.5 + minimos[cod] * 1.3
                    if stock < objetivo * 0.8:
                        costo = round(costo_base[cod] * inflacion * rnd.uniform(0.96, 1.05), 2)
                        por_prov.setdefault(prov_ins[cod], []).append(
                            {"insumo_id": iid, "cantidad": round(objetivo - stock, 2), "costo_unitario": costo}
                        )
                for prov, lineas in por_prov.items():
                    registrar_entrada(
                        conn, admin_id, lineas, prov, f"F-{d:%m%d}-{prov}", None, _ts(d, 10, rnd.randint(0, 50))
                    )

            # turno del día
            cajero = cajeros[n % 2] if d.weekday() < 5 else cajeros[(n + 1) % 2]
            fondo = 500.0
            cur = conn.execute(
                "INSERT INTO turnos(usuario_apertura_id, apertura, fondo_inicial, estado) VALUES (?,?,?,'ABIERTO')",
                (cajero, _ts(d, 12, 45), fondo),
            )
            turno_id = cur.lastrowid

            crecimiento = 1 + 0.18 * n / dias
            tickets = max(8, int(rnd.gauss(46 * DIA_FACTOR[d.weekday()] * crecimiento, 6)))
            tiempos = sorted(
                (rnd.choices(horas, hpesos)[0], rnd.randint(0, 59), rnd.randint(0, 59)) for _ in range(tickets)
            )
            ventas_dia = []
            for h, m, s in tiempos:
                n_items = rnd.choices([1, 2, 3, 4], [35, 38, 19, 8])[0]
                elegidos = {}
                for pid in rnd.choices(pids, pesos, k=n_items):
                    elegidos[pid] = elegidos.get(pid, 0) + rnd.choices([1, 2, 3], [70, 22, 8])[0]
                metodo = rnd.choices(["Efectivo", "Tarjeta", "Transferencia"], [55, 35, 10])[0]
                items = [{"producto_id": k, "cantidad": v} for k, v in elegidos.items()]
                descuento = 0.0
                if rnd.random() < 0.04:
                    descuento = 10.0
                vendedor = cajero if rnd.random() < 0.85 else admin_id
                vid = registrar_venta(
                    conn,
                    vendedor,
                    items,
                    metodos[metodo],
                    descuento,
                    None,
                    fecha_hora=_ts(d, h, m, s),
                    turno_id=turno_id,
                    requiere_turno=False,
                )
                ventas_dia.append(vid)
                if metodo == "Efectivo":  # simular billete recibido
                    total = conn.execute("SELECT total FROM ventas WHERE venta_id=?", (vid,)).fetchone()[0]
                    billete = next(b for b in (total, 50, 100, 200, 500, 1000, 10000) if b >= total)
                    if rnd.random() < 0.6:
                        conn.execute(
                            "UPDATE ventas SET pago_recibido=?, cambio=? WHERE venta_id=?",
                            (billete, round(billete - total, 2), vid),
                        )
            # ~1% cancelaciones
            for vid in ventas_dia:
                if rnd.random() < 0.012:
                    cancelar_venta(
                        conn,
                        vid,
                        admin_id,
                        rnd.choice(["Error de captura", "Cliente se retiró", "Producto equivocado"]),
                        fecha_hora=_ts(d, 22, 50),
                    )
            # retiro de caja ocasional
            if rnd.random() < 0.3:
                conn.execute(
                    "INSERT INTO movimientos_caja(turno_id, fecha_hora, tipo, monto, concepto, usuario_id) VALUES (?,?,?,?,?,?)",
                    (turno_id, _ts(d, 18, 5), "RETIRO", 300.0, "Pago de hielo y gas", cajero),
                )
            # cierre de turno
            efectivo = conn.execute(
                """SELECT COALESCE(SUM(v.total),0) FROM ventas v JOIN dim_metodo_pago m
                                       ON m.metodo_pago_id=v.metodo_pago_id WHERE v.turno_id=? AND v.estado='PAGADA'
                                       AND m.es_efectivo=1""",
                (turno_id,),
            ).fetchone()[0]
            retiros = conn.execute(
                "SELECT COALESCE(SUM(monto),0) FROM movimientos_caja WHERE turno_id=? AND tipo='RETIRO'", (turno_id,)
            ).fetchone()[0]
            esperado = round(fondo + efectivo - retiros, 2)
            dif = rnd.choice([0, 0, 0, 0, 0, -10, -20, 5, 10, -50])
            conn.execute(
                """UPDATE turnos SET estado='CERRADO', cierre=?, usuario_cierre_id=?, efectivo_esperado=?,
                            efectivo_contado=?, diferencia=? WHERE turno_id=?""",
                (_ts(d, 23, 15), cajero, esperado, esperado + dif, dif, turno_id),
            )

            # mermas los domingos
            if d.weekday() == 6:
                for cod in rnd.sample(["CIL", "JIT", "LEC", "PIN", "CEB", "PAN-H", "TOR-M"], 3):
                    iid = ids["ins"][cod]
                    stock = conn.execute("SELECT stock_actual FROM dim_insumo WHERE insumo_id=?", (iid,)).fetchone()[0]
                    q = round(max(stock, 0) * rnd.uniform(0.03, 0.08), 3)
                    if q > 0:
                        ajustar_inventario(
                            conn,
                            admin_id,
                            iid,
                            "RESTAR",
                            q,
                            rnd.choice(["Merma", "Caducidad", "Daño / derrame"]),
                            _ts(d, 23, 30),
                        )
        for concepto, categoria, monto in GASTOS_FIJOS:
            conn.execute(
                "INSERT INTO gastos_fijos(concepto, categoria, monto_mensual, vigente_desde) VALUES (?,?,?,?)",
                (concepto, categoria, monto, inicio.isoformat()),
            )
        # dejar algunos insumos en nivel bajo para ver alertas
        for cod in ("CIL", "TOC", "CAJ"):
            iid = ids["ins"][cod]
            stock = conn.execute("SELECT stock_actual FROM dim_insumo WHERE insumo_id=?", (iid,)).fetchone()[0]
            if stock > minimos[cod] * 0.8:
                ajustar_inventario(
                    conn,
                    admin_id,
                    iid,
                    "CONTEO",
                    round(minimos[cod] * 0.7, 3),
                    "Conteo físico",
                    _ts(date.today() - timedelta(days=1), 23, 40),
                )
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def crear_demo_completa(conn) -> None:
    """Crea usuario admin/admin123 + datos de ejemplo (para --demo)."""
    h, s = security.hash_password("admin123")
    with conn:
        cur = conn.execute(
            "INSERT INTO dim_usuario(username, nombre, rol, password_hash, salt) VALUES (?,?,?,?,?)",
            ("admin", "Administrador", "ADMIN", h, s),
        )
        conn.execute("UPDATE config SET valor='Food Truck La Esquina' WHERE clave='nombre_negocio'")
    cargar_datos_ejemplo(conn, cur.lastrowid)
