"""El frontend se sirve con rutas versionadas para que la caché de la ventana no mezcle versiones."""

import re

from app import server


def test_index_apunta_a_rutas_versionadas_y_no_se_cachea(client):
    r = client.get("/")
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store"
    rutas = re.findall(r'(?:src|href)="(/static/[^"]+)"', r.text)
    assert rutas and all(x.startswith(f"/static/{server.STATIC_TOKEN}/") for x in rutas)
    for ruta in rutas:
        assert client.get(ruta).status_code == 200, ruta


def test_modulos_relativos_se_resuelven_bajo_la_misma_huella(client):
    base = f"/static/{server.STATIC_TOKEN}/js"
    assert "export const del" in client.get(f"{base}/api.js").text
    assert client.get(f"{base}/views/pos.js").status_code == 200


def test_la_huella_cambia_si_cambia_un_archivo(monkeypatch, tmp_path):
    (tmp_path / "a.js").write_text("uno")
    monkeypatch.setattr(server.config, "STATIC_DIR", tmp_path)
    antes = server._token_estaticos()
    (tmp_path / "a.js").write_text("dos")
    assert server._token_estaticos() != antes


def test_rutas_antiguas_sin_huella_siguen_funcionando(client):
    assert client.get("/static/css/styles.css").status_code == 200
