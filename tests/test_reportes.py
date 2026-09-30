"""Dashboard, exportaciones, respaldos y datos de ejemplo."""

from datetime import date, timedelta

import pytest

from app import db
from app.seed import crear_demo_completa


def test_dashboard_kpis(client, admin, catalogo, turno, vender):
    vender([(catalogo["taco"], 2)])
    v = vender([(catalogo["bebida"], 1)]).json()
    client.post(f"/api/ventas/{v['venta_id']}/cancelar", json={"motivo": "prueba"}, headers=admin)
    hoy = date.today()
    d = client.get("/api/dashboard", params={"desde": hoy - timedelta(days=6), "hasta": hoy}, headers=admin).json()
    assert d["kpis"]["ventas"] == 50
    assert d["kpis"]["tickets"] == 1
    assert d["kpis"]["canceladas"] == 1
    assert d["kpis"]["costo"] == pytest.approx(32)
    assert d["productos"][0]["clase_menu"] in {"Estrella", "Caballo de batalla", "Rompecabezas", "Perro"}


def test_exportar_excel_y_csv(client, admin, catalogo):
    xlsx = client.post("/api/exportar/todo", params={"abrir": False}, headers=admin).json()
    assert xlsx["archivo"].endswith(".xlsx")
    csv = client.post("/api/exportar/inventario", params={"abrir": False, "formato": "csv"}, headers=admin).json()
    assert csv["archivo"].endswith(".csv") and csv["filas"] == 3


def test_respaldo(client, admin):
    r = client.post("/api/respaldos", headers=admin).json()
    assert r["archivo"].startswith("pos_")
    assert len(client.get("/api/respaldos", headers=admin).json()) == 1


def test_datos_de_ejemplo_son_consistentes(client):
    conn = db.connect()
    try:
        crear_demo_completa(conn)
        descuadres = conn.execute(
            """SELECT i.nombre FROM dim_insumo i JOIN fact_movimientos_inventario m USING (insumo_id)
               GROUP BY i.insumo_id HAVING abs(i.stock_actual - SUM(m.cantidad)) > 0.01"""
        ).fetchall()
        assert descuadres == []
        assert conn.execute("SELECT COUNT(*) FROM ventas").fetchone()[0] > 1000
        negativos = conn.execute("SELECT COUNT(*) FROM fact_movimientos_inventario WHERE stock_resultante < 0")
        assert negativos.fetchone()[0] == 0
    finally:
        conn.close()
