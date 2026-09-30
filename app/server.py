"""Aplicación FastAPI: API REST + archivos estáticos del frontend."""

import logging

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import config
from .routers import admin, auth, catalogo, dashboard, inventario, ventas
from .security import current_user
from .services import ErrorNegocio

log = logging.getLogger("pos")

app = FastAPI(title=config.APP_NAME, version=config.APP_VERSION, docs_url="/api/docs", redoc_url=None)
app.state.server = None  # lo asigna main.py para permitir el apagado


@app.exception_handler(ErrorNegocio)
async def _err_negocio(request: Request, exc: ErrorNegocio):
    return JSONResponse(status_code=exc.status, content={"detail": exc.mensaje, "datos": exc.datos})


@app.exception_handler(RequestValidationError)
async def _err_validacion(request: Request, exc: RequestValidationError):
    campos = []
    for e in exc.errors():
        loc = ".".join(str(x) for x in e.get("loc", []) if x not in ("body", "query"))
        campos.append(f"{loc}: {e.get('msg')}")
    return JSONResponse(status_code=422, content={"detail": "Datos inválidos — " + "; ".join(campos)})


@app.exception_handler(Exception)
async def _err_general(request: Request, exc: Exception):
    log.exception("Error no controlado en %s", request.url.path)
    return JSONResponse(status_code=500, content={"detail": f"Error interno: {exc}"})


for r in (auth, catalogo, inventario, ventas, admin, dashboard):
    app.include_router(r.router)


@app.post("/api/sistema/apagar")
def apagar(user=Depends(current_user)):
    srv = app.state.server
    if srv is not None:
        srv.should_exit = True
    return {"ok": True}


@app.middleware("http")
async def _no_cache(request: Request, call_next):
    resp = await call_next(request)
    if request.url.path.startswith("/api") or request.url.path in ("/", "/index.html"):
        resp.headers["Cache-Control"] = "no-store"
    return resp


app.mount("/static", StaticFiles(directory=str(config.STATIC_DIR)), name="static")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(config.STATIC_DIR / "index.html")
