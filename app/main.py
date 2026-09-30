"""Punto de entrada: levanta el servidor local y abre la ventana de escritorio.

Uso:
    python -m app.main              -> abre la app en ventana (pywebview) o en el navegador
    python -m app.main --server     -> sólo servidor (desarrollo), http://127.0.0.1:8765
    python -m app.main --demo       -> crea una base nueva con datos de ejemplo si está vacía
"""

import argparse
import contextlib
import json
import logging
import os
import socket
import sys
import threading
import time
import urllib.request
import webbrowser
from logging.handlers import RotatingFileHandler


def _setup_logging(config):
    config.ensure_dirs()
    handlers = [RotatingFileHandler(config.LOG_DIR / "pos.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8")]
    if sys.stdout is not None:
        handlers.append(logging.StreamHandler(sys.stdout))
    else:  # ejecutable sin consola: evitar que uvicorn escriba en stdout inexistente
        sys.stdout = open(os.devnull, "w")  # noqa: SIM115 - vive todo el proceso
        sys.stderr = open(config.LOG_DIR / "stderr.log", "a", encoding="utf-8")  # noqa: SIM115
    logging.basicConfig(level=logging.INFO, handlers=handlers, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def _puerto_libre(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def _es_nuestra_app(url: str) -> bool:
    try:
        with urllib.request.urlopen(url + "/api/estado", timeout=2) as r:
            return "requiere_configuracion" in json.loads(r.read().decode())
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser(description="Punto de Venta MASTER")
    parser.add_argument("--server", action="store_true", help="solo servidor, sin ventana")
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--demo", action="store_true", help="cargar datos de ejemplo si la base está vacía")
    parser.add_argument("--browser", action="store_true", help="abrir en el navegador en lugar de ventana")
    args = parser.parse_args()

    from app import config

    if args.port:
        config.PORT = args.port
    _setup_logging(config)
    log = logging.getLogger("pos")

    url = f"http://{config.HOST}:{config.PORT}"
    ya_corriendo = not _puerto_libre(config.PORT) and _es_nuestra_app(url)
    server = None

    if not ya_corriendo:
        if not _puerto_libre(config.PORT):  # puerto ocupado por otro programa: buscar otro
            for p in range(config.PORT + 1, config.PORT + 50):
                if _puerto_libre(p):
                    config.PORT = p
                    break
            url = f"http://{config.HOST}:{config.PORT}"

        from app import db

        db.init_db()
        conn = db.connect()
        try:
            hay_usuarios = conn.execute("SELECT COUNT(*) FROM dim_usuario").fetchone()[0] > 0
            if args.demo and not hay_usuarios:
                from app.seed import crear_demo_completa

                crear_demo_completa(conn)
                hay_usuarios = True
        finally:
            conn.close()
        if hay_usuarios:
            try:
                db.backup("inicio")
            except Exception:
                log.exception("No se pudo crear el respaldo de inicio")

        import uvicorn

        from app.server import app

        server = uvicorn.Server(
            uvicorn.Config(
                app, host=config.HOST, port=config.PORT, log_config=None, log_level="warning", access_log=False
            )
        )
        app.state.server = server

        if args.server:
            log.info("Servidor en %s (datos en %s)", url, config.DATA_DIR)
            server.run()
            return

        hilo = threading.Thread(target=server.run, daemon=True)
        hilo.start()
        for _ in range(100):
            if server.started:
                break
            time.sleep(0.1)
        log.info("Servidor iniciado en %s (datos en %s)", url, config.DATA_DIR)

    usar_ventana = not args.browser
    if usar_ventana:
        try:
            import webview

            with contextlib.suppress(Exception):  # la opción no existe en versiones antiguas
                webview.settings["ALLOW_DOWNLOADS"] = True
            webview.create_window(
                config.APP_NAME,
                url,
                width=1400,
                height=860,
                min_size=(1100, 700),
                text_select=True,
                confirm_close=False,
            )
            webview.start(private_mode=False)
            if server:
                server.should_exit = True
            return
        except Exception:
            log.exception("No se pudo abrir la ventana nativa; se usará el navegador")

    webbrowser.open(url)
    if server:
        try:
            while not server.should_exit:
                time.sleep(0.5)
        except KeyboardInterrupt:
            server.should_exit = True


if __name__ == "__main__":
    # Permite `python app/main.py` además de `python -m app.main`
    if __package__ in (None, ""):
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    main()
