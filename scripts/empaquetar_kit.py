"""Arma la carpeta del kit de instalación para llevar el sistema a computadoras de clientes.

Uso (desde la raíz del repositorio):
    python scripts/empaquetar_kit.py                      # crea kit-instalacion/ y el .zip
    python scripts/empaquetar_kit.py --instalador ruta\\Instalar_PuntoDeVentaMASTER_1.0.0.exe

Contenido: guías en HTML (instalación, usuario, checklist), herramientas .bat, el código fuente en .zip y,
si se encuentra, el instalador de Windows (se busca en la carpeta «instalador» o se indica con --instalador).
El instalador .exe solo se puede compilar en Windows (scripts\\build.bat o el workflow «Build Windows»).
"""

import argparse
import html
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DIST = RAIZ / "distribucion"
SOLO_WINDOWS_CRLF = {".bat", ".cmd", ".iss", ".txt"}


def version() -> str:
    m = re.search(r'__version__\s*=\s*"([^"]+)"', (RAIZ / "app" / "__init__.py").read_text(encoding="utf-8"))
    return m.group(1) if m else "0.0.0"


# ----------------------------------------------------------------- Markdown -> HTML (lo justo para las guías)
def _inline(texto: str) -> str:
    partes = re.split(r"(`[^`]+`)", texto)
    salida = []
    for p in partes:
        if p.startswith("`") and p.endswith("`") and len(p) > 1:
            salida.append(f"<code>{html.escape(p[1:-1], quote=False)}</code>")
            continue
        p = html.escape(p, quote=False)
        p = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", p)
        p = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", p)
        p = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", r'<a href="\2">\1</a>', p)
        p = re.sub(r"&lt;(https?://[^&\s]+)&gt;", r'<a href="\1">\1</a>', p)
        salida.append(p)
    return "".join(salida)


_LISTA = re.compile(r"^(\s*)([-*]|\d+\.)\s+(.*)$")


def _lista(items: list[tuple[int, bool, str]]) -> str:
    out: list[str] = []
    pila: list[tuple[int, str]] = []
    for sangria, ordenada, texto in items:
        while pila and sangria < pila[-1][0]:
            out.append(f"</li></{pila.pop()[1]}>")
        if pila and sangria == pila[-1][0]:
            out.append("</li>")
        elif not pila or sangria > pila[-1][0]:
            etiqueta = "ol" if ordenada else "ul"
            out.append(f"<{etiqueta}>")
            pila.append((sangria, etiqueta))
        caja = ""
        if texto.startswith("[ ] "):
            caja, texto = '<input type="checkbox"> ', texto[4:]
        out.append(f"<li>{caja}{_inline(texto)}")
    while pila:
        out.append(f"</li></{pila.pop()[1]}>")
    return "".join(out)


def _tabla(filas: list[str]) -> str:
    def celdas(linea: str) -> list[str]:
        return [c.strip() for c in linea.strip().strip("|").split("|")]

    cab = celdas(filas[0])
    cuerpo = [celdas(f) for f in filas[2:]]
    h = "".join(f"<th>{_inline(c)}</th>" for c in cab)
    b = "".join("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in f) + "</tr>" for f in cuerpo)
    return f"<table><thead><tr>{h}</tr></thead><tbody>{b}</tbody></table>"


def md_a_html(md: str) -> str:
    lineas = md.replace("\r\n", "\n").split("\n")
    out: list[str] = []
    i = 0
    while i < len(lineas):
        ln = lineas[i]
        if not ln.strip():
            i += 1
        elif ln.startswith("```"):
            i += 1
            bloque = []
            while i < len(lineas) and not lineas[i].startswith("```"):
                bloque.append(lineas[i])
                i += 1
            i += 1
            out.append("<pre><code>" + html.escape("\n".join(bloque), quote=False) + "</code></pre>")
        elif re.match(r"^#{1,4}\s", ln):
            nivel = len(ln) - len(ln.lstrip("#"))
            out.append(f"<h{nivel}>{_inline(ln[nivel:].strip())}</h{nivel}>")
            i += 1
        elif ln.strip() == "---":
            out.append("<hr>")
            i += 1
        elif ln.startswith("|"):
            filas = []
            while i < len(lineas) and lineas[i].startswith("|"):
                filas.append(lineas[i])
                i += 1
            out.append(_tabla(filas))
        elif ln.startswith(">"):
            cita = []
            while i < len(lineas) and lineas[i].startswith(">"):
                cita.append(lineas[i].lstrip(">").strip())
                i += 1
            out.append(f"<blockquote>{_inline(' '.join(cita))}</blockquote>")
        elif _LISTA.match(ln):
            items: list[list] = []
            while i < len(lineas) and lineas[i].strip():
                m = _LISTA.match(lineas[i])
                if m:
                    items.append([len(m.group(1)), m.group(2)[0].isdigit(), m.group(3)])
                elif lineas[i][:1].isspace() and items:  # continuación del renglón anterior
                    items[-1][2] += " " + lineas[i].strip()
                else:
                    break
                i += 1
            out.append(_lista([tuple(x) for x in items]))
        else:
            parrafo = []
            while (
                i < len(lineas)
                and lineas[i].strip()
                and not lineas[i].startswith(("#", "|", ">", "```"))
                and not _LISTA.match(lineas[i])
            ):
                parrafo.append(lineas[i].strip())
                i += 1
            out.append(f"<p>{_inline(' '.join(parrafo))}</p>")
    return "\n".join(out)


PLANTILLA = """<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{titulo}</title>
<style>
 body {{ font: 15px/1.6 "Segoe UI", system-ui, Arial, sans-serif; color: #1c1c1a; max-width: 880px; margin: 0 auto; padding: 24px 20px 60px; }}
 h1 {{ font-size: 26px; border-bottom: 3px solid #e4572e; padding-bottom: 8px; }}
 h2 {{ font-size: 20px; margin-top: 34px; color: #c7441f; }} h3 {{ font-size: 16px; margin-top: 22px; }}
 table {{ border-collapse: collapse; width: 100%; margin: 12px 0; }}
 th, td {{ border: 1px solid #d8d6d0; padding: 7px 10px; text-align: left; vertical-align: top; }}
 th {{ background: #f4f3f0; }} code {{ background: #f4f3f0; padding: 1px 5px; border-radius: 4px; font-family: Consolas, monospace; font-size: .92em; }}
 pre {{ background: #f4f3f0; padding: 12px; border-radius: 8px; overflow: auto; }} pre code {{ background: none; padding: 0; }}
 blockquote {{ margin: 12px 0; padding: 8px 14px; background: #fdf2d9; border-left: 4px solid #eda100; }}
 li {{ margin: 3px 0; }} li input {{ transform: scale(1.3); margin-right: 8px; }}
 footer {{ margin-top: 40px; color: #8a8984; font-size: 12px; }}
 @media print {{ body {{ max-width: none; padding: 0; font-size: 12px; }} h2 {{ break-after: avoid; }} tr, li {{ break-inside: avoid; }} }}
</style></head><body>
{cuerpo}
<footer>Punto de Venta MASTER v{version} · © 2026 Juan Díaz Vega</footer>
</body></html>
"""


def md_a_pagina(md_ruta: Path, ver: str) -> str:
    md = md_ruta.read_text(encoding="utf-8")
    titulo = next((ln.lstrip("# ").strip() for ln in md.splitlines() if ln.startswith("# ")), "Punto de Venta MASTER")
    return PLANTILLA.format(titulo=html.escape(titulo), cuerpo=md_a_html(md), version=ver)


# ----------------------------------------------------------------- armado del kit
def _escribir(destino: Path, contenido: bytes) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    if destino.suffix.lower() in SOLO_WINDOWS_CRLF:
        contenido = contenido.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    destino.write_bytes(contenido)


def _archivos_del_proyecto() -> list[Path]:
    try:
        r = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
            cwd=RAIZ,
            capture_output=True,
            text=True,
            check=True,
        )
        rutas = [RAIZ / p for p in r.stdout.splitlines() if p]
    except (OSError, subprocess.CalledProcessError):  # sin git: recorrer la carpeta
        excluir = {".git", ".venv", "dist", "build", "instalador", "kit-instalacion", "__pycache__", ".pytest_cache"}
        rutas = [p for p in RAIZ.rglob("*") if p.is_file() and not (set(p.relative_to(RAIZ).parts) & excluir)]
    return sorted(p for p in rutas if p.is_file())


def zip_codigo_fuente(destino: Path, ver: str) -> None:
    base = f"PuntoDeVentaMASTER-fuente-{ver}"
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as z:
        for p in _archivos_del_proyecto():
            if p.suffix in (".db", ".pyc") or p.name.startswith("PuntoDeVentaMASTER-kit-"):
                continue
            datos = p.read_bytes()
            if p.suffix.lower() in SOLO_WINDOWS_CRLF - {".txt"}:
                datos = datos.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
            z.writestr(f"{base}/{p.relative_to(RAIZ).as_posix()}", datos)


def armar_kit(salida: Path, instalador: Path | None = None, con_zip: bool = True) -> Path:
    ver = version()
    if salida.exists():
        shutil.rmtree(salida)
    salida.mkdir(parents=True)

    leeme = (DIST / "LEEME.txt").read_text(encoding="utf-8").replace("{version}", ver)
    _escribir(salida / "LEEME.txt", leeme.encode("utf-8"))
    paginas = {
        "1-Guia-de-instalacion.html": DIST / "Guia-de-instalacion.md",
        "2-Guia-del-usuario.html": RAIZ / "docs" / "manual-de-usuario.md",
        "3-Checklist-de-entrega.html": DIST / "Checklist-de-entrega.md",
    }
    for nombre, md in paginas.items():
        _escribir(salida / nombre, md_a_pagina(md, ver).encode("utf-8"))
    for p in sorted((DIST / "herramientas").glob("*")):
        _escribir(salida / "herramientas" / p.name, p.read_bytes())
    _escribir(
        salida / "instalador" / "LEEME-instalador.txt", (DIST / "instalador" / "LEEME-instalador.txt").read_bytes()
    )

    encontrados = (
        [instalador] if instalador else sorted((RAIZ / "instalador").glob("Instalar_PuntoDeVentaMASTER_*.exe"))
    )
    encontrados += sorted(RAIZ.glob("PuntoDeVentaMASTER-*-portable.zip")) if not instalador else []
    for f in encontrados:
        if f and f.is_file():
            shutil.copy2(f, salida / "instalador" / f.name)
            print(f"  + instalador: {f.name}")
    if not any((salida / "instalador").glob("*.exe")):
        print(
            "  ! No se encontró el instalador .exe: consíguelo (ver instalador/LEEME-instalador.txt) y cópialo a esa carpeta."
        )

    (salida / "codigo-fuente").mkdir()
    zip_codigo_fuente(salida / "codigo-fuente" / f"PuntoDeVentaMASTER-fuente-{ver}.zip", ver)

    if con_zip:
        destino = salida.parent / f"PuntoDeVentaMASTER-kit-{ver}"
        shutil.make_archive(str(destino), "zip", root_dir=salida.parent, base_dir=salida.name)
        print(f"  + {destino.name}.zip")
    return salida


def main() -> int:
    ap = argparse.ArgumentParser(description="Arma el kit de instalación de Punto de Venta MASTER")
    ap.add_argument("--salida", type=Path, default=RAIZ / "kit-instalacion")
    ap.add_argument("--instalador", type=Path, help="ruta del Instalar_PuntoDeVentaMASTER_*.exe a incluir")
    ap.add_argument("--sin-zip", action="store_true", help="no crear el .zip del kit")
    a = ap.parse_args()
    print(f"Armando el kit v{version()} en {a.salida} ...")
    armar_kit(a.salida, a.instalador, not a.sin_zip)
    print("Listo.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
