"""Gastos fijos mensuales y su efecto en utilidad, punto de equilibrio y dashboard."""

from datetime import date, timedelta

import pytest

from app import db
from app.services import prorratear_gastos

HOY = date.today()
INICIO_MES = HOY.replace(day=1).isoformat()
DIAS_MES = (date(HOY.year + (HOY.month == 12), HOY.month % 12 + 1, 1) - HOY.replace(day=1)).days


def gasto(**extra):
    return {
        "concepto": "Renta del local",
        "categoria": "Renta",
        "monto_mensual": 3000,
        "vigente_desde": INICIO_MES,
        **extra,
    }


def test_alta_edicion_y_baja(client, admin):
    gid = client.post("/api/gastos-fijos", json=gasto(), headers=admin).json()["gasto_id"]
    d = client.get("/api/gastos-fijos", headers=admin).json()
    assert d["gastos"][0]["concepto"] == "Renta del local" and d["gastos"][0]["vigente"] is True
    assert d["resumen"]["total_mensual"] == 3000 and "Nómina" in d["categorias"]
    assert client.put(f"/api/gastos-fijos/{gid}", json=gasto(monto_mensual=3500), headers=admin).status_code == 200
    assert client.get("/api/gastos-fijos", headers=admin).json()["resumen"]["total_mensual"] == 3500
    assert client.delete(f"/api/gastos-fijos/{gid}", headers=admin).status_code == 200
    assert client.get("/api/gastos-fijos", headers=admin).json()["gastos"] == []
    assert client.delete(f"/api/gastos-fijos/{gid}", headers=admin).status_code == 404


@pytest.mark.parametrize(
    "extra",
    [
        {"categoria": "Inventada"},
        {"concepto": "  "},
        {"monto_mensual": -1},
        {"vigente_desde": "31/12/2026"},
        {"vigente_hasta": "2000-01-01"},
    ],
)
def test_validaciones(client, admin, extra):
    assert client.post("/api/gastos-fijos", json=gasto(**extra), headers=admin).status_code in (400, 422)


def test_plantilla_de_gastos_comunes_es_idempotente(client, admin):
    n = client.post("/api/gastos-fijos/plantilla", headers=admin).json()["agregados"]
    assert n > 10
    assert client.post("/api/gastos-fijos/plantilla", headers=admin).json()["agregados"] == 0
    d = client.get("/api/gastos-fijos", headers=admin).json()
    conceptos = {g["concepto"] for g in d["gastos"]}
    assert {"Electricidad", "Agua", "Gas", "Renta del local"} <= conceptos
    assert d["resumen"]["total_mensual"] == 0


def test_prorrateo_por_dia_y_por_vigencia(client, admin):
    client.post(
        "/api/gastos-fijos",
        json=gasto(monto_mensual=3100, vigente_desde="2026-10-01", vigente_hasta="2026-11-10"),
        headers=admin,
    )
    conn = db.connect()
    try:
        assert prorratear_gastos(conn, date(2026, 10, 1), date(2026, 10, 31))["total"] == 3100
        assert prorratear_gastos(conn, date(2026, 10, 1), date(2026, 10, 10))["total"] == 1000
        # 7 días de octubre (31 días) + 5 de noviembre (30 días)
        assert prorratear_gastos(conn, date(2026, 10, 25), date(2026, 11, 5))["total"] == pytest.approx(
            7 * 3100 / 31 + 5 * 3100 / 30, abs=0.01
        )
        # termina el 10 de noviembre: lo que sigue ya no se cobra
        assert prorratear_gastos(conn, date(2026, 11, 1), date(2026, 11, 30))["total"] == pytest.approx(
            10 * 3100 / 30, abs=0.01
        )
        assert prorratear_gastos(conn, date(2026, 9, 1), date(2026, 9, 30))["total"] == 0
    finally:
        conn.close()


def test_dashboard_calcula_utilidad_y_equilibrio(client, admin, catalogo, turno, vender):
    vender([(catalogo["taco"], 4)])  # venta $100, costo $64, margen $36
    client.post("/api/gastos-fijos", json=gasto(monto_mensual=DIAS_MES * 10), headers=admin)  # $10 por día
    client.post(
        "/api/gastos-fijos",
        json=gasto(concepto="Salarios de cocina", categoria="Nómina", monto_mensual=DIAS_MES * 5),
        headers=admin,
    )
    d = client.get("/api/dashboard", params={"desde": HOY, "hasta": HOY}, headers=admin).json()
    k = d["kpis"]
    assert k["gastos_fijos"] == pytest.approx(15) and k["nomina"] == pytest.approx(5)
    assert k["utilidad"] == pytest.approx(36 - 15)
    assert k["nomina_pct"] == pytest.approx(0.05) and k["prime_cost_pct"] == pytest.approx((64 + 5) / 100)
    assert k["punto_equilibrio"] == pytest.approx(15 / 0.36, abs=0.01)
    assert d["gastos_fijos"]["configurado"] is True
    assert {c["categoria"] for c in d["gastos_fijos"]["por_categoria"]} == {"Renta", "Nómina"}
    assert d["serie"][-1]["gastos"] == pytest.approx(15) and d["serie"][-1]["utilidad"] == pytest.approx(21)


def test_dashboard_sin_gastos_configurados(client, admin, catalogo, turno, vender):
    vender([(catalogo["taco"], 1)])
    d = client.get("/api/dashboard", params={"desde": HOY, "hasta": HOY}, headers=admin).json()
    assert d["gastos_fijos"]["configurado"] is False
    assert d["kpis"]["gastos_fijos"] == 0 and d["kpis"]["punto_equilibrio"] is None


def test_dashboard_agrupa_por_semana_con_gastos(client, admin, catalogo, turno, vender):
    vender([(catalogo["taco"], 1)])
    client.post("/api/gastos-fijos", json=gasto(vigente_desde=(HOY - timedelta(days=400)).isoformat()), headers=admin)
    desde = HOY - timedelta(days=200)
    d = client.get("/api/dashboard", params={"desde": desde, "hasta": HOY}, headers=admin).json()
    assert d["rango"]["agrupar"] == "semana"
    assert sum(s["gastos"] for s in d["serie"]) == pytest.approx(d["kpis"]["gastos_fijos"], abs=0.1 * len(d["serie"]))
