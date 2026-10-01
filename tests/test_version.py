"""La versión debe ser una sola y quedar documentada en el CHANGELOG (historial de cambios)."""

import re
from pathlib import Path

from app import __version__

RAIZ = Path(__file__).resolve().parent.parent


def _leer(ruta: str) -> str:
    return (RAIZ / ruta).read_text(encoding="utf-8")


def test_la_version_es_semantica():
    assert re.fullmatch(r"\d+\.\d+\.\d+", __version__)


def test_pyproject_e_instalador_coinciden_con_el_codigo():
    assert re.search(r'^version = "([^"]+)"', _leer("pyproject.toml"), re.M).group(1) == __version__
    assert re.search(r'#define AppVersion "([^"]+)"', _leer("packaging/installer.iss")).group(1) == __version__


def test_el_changelog_documenta_la_version_actual():
    cl = _leer("CHANGELOG.md")
    assert re.search(rf"^## \[{re.escape(__version__)}\] - \d{{4}}-\d{{2}}-\d{{2}}$", cl, re.M), (
        "falta la entrada en CHANGELOG.md"
    )
    assert f"[{__version__}]: https://github.com/" in cl, "falta el enlace de la versión al final del CHANGELOG"
    # la primera versión listada debe ser la actual (las más nuevas van arriba)
    versiones = re.findall(r"^## \[(\d+\.\d+\.\d+)\]", cl, re.M)
    assert versiones[0] == __version__
