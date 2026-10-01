"""Kit de instalación: guías en HTML, herramientas .bat y código fuente empaquetados."""

import importlib.util
import zipfile
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("empaquetar_kit", RAIZ / "scripts" / "empaquetar_kit.py")
kit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kit)


def test_markdown_a_html_cubre_lo_que_usan_las_guias():
    md = "# Título\n\nTexto con **negrita**, `código <x>` y [liga](http://a.b).\n\n- [ ] uno\n- dos\n\n1. a\n   1. sub\n2. b\n\n| A | B |\n|---|---|\n| 1 | 2 |\n"
    h = kit.md_a_html(md)
    assert "<h1>Título</h1>" in h and "<strong>negrita</strong>" in h and "<code>código &lt;x&gt;</code>" in h
    assert '<a href="http://a.b">liga</a>' in h and '<input type="checkbox"> uno' in h
    assert "<ol><li>a<ol><li>sub</li></ol></li><li>b</li></ol>" in h
    assert (
        "<table><thead><tr><th>A</th><th>B</th></tr></thead><tbody><tr><td>1</td><td>2</td></tr></tbody></table>" in h
    )


@pytest.fixture(scope="module")
def kit_armado(tmp_path_factory):
    salida = tmp_path_factory.mktemp("kit") / "kit-instalacion"
    kit.armar_kit(salida, con_zip=True)
    return salida


def test_kit_trae_guias_herramientas_y_codigo_fuente(kit_armado):
    for nombre in (
        "LEEME.txt",
        "1-Guia-de-instalacion.html",
        "2-Guia-del-usuario.html",
        "3-Checklist-de-entrega.html",
        "herramientas/Verificar-equipo.bat",
        "herramientas/Respaldar-datos.bat",
        "instalador/LEEME-instalador.txt",
    ):
        assert (kit_armado / nombre).is_file(), nombre
    assert "Guía de instalación" in (kit_armado / "1-Guia-de-instalacion.html").read_text(encoding="utf-8")
    assert (kit_armado.parent / f"PuntoDeVentaMASTER-kit-{kit.version()}.zip").is_file()


def test_los_bat_usan_saltos_de_linea_de_windows(kit_armado):
    for bat in (kit_armado / "herramientas").glob("*.bat"):
        datos = bat.read_bytes()
        assert b"\r\n" in datos and b"\n" not in datos.replace(b"\r\n", b""), bat.name


def test_zip_de_codigo_fuente_es_utilizable(kit_armado):
    z = next((kit_armado / "codigo-fuente").glob("*.zip"))
    with zipfile.ZipFile(z) as zf:
        nombres = {n.split("/", 1)[1] for n in zf.namelist()}
        assert {"app/main.py", "requirements.txt", "scripts/build.bat", "scripts/instalar-desde-codigo.bat"} <= nombres
        assert not any(n.startswith((".git/", ".venv/")) or n.endswith(".db") for n in nombres)
        bat = zf.read(next(n for n in zf.namelist() if n.endswith("instalar-desde-codigo.bat")))
        assert b"\r\n" in bat


def test_incluye_el_instalador_si_se_indica(tmp_path):
    exe = tmp_path / "Instalar_PuntoDeVentaMASTER_9.9.9.exe"
    exe.write_bytes(b"MZ")
    kit.armar_kit(tmp_path / "k", instalador=exe, con_zip=False)
    assert (tmp_path / "k" / "instalador" / exe.name).read_bytes() == b"MZ"
