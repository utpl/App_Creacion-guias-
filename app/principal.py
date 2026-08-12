"""Aplicacion FastAPI de App-EdiLoja."""

from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from app.rutas import autenticacion
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.base_datos import obtener_sesion
from app.configuracion import configuracion

app = FastAPI(
    title="App-EdiLoja",
    description="Plataforma academica digital",
    version="0.1.0",
    docs_url="/docs" if configuracion.entorno != "produccion" else None,
    redoc_url=None,
)


@app.get("/salud", tags=["sistema"])
def salud() -> dict[str, str]:
    """Vive el proceso. No consulta nada externo, a proposito."""
    return {"estado": "vivo"}


@app.get("/listo", tags=["sistema"])
def listo(bd: Session = Depends(obtener_sesion)) -> JSONResponse:
    """Puede atender trafico. Comprueba base de datos y Redis."""
    fallos: list[str] = []

    try:
        bd.execute(text("SELECT 1"))
    except Exception:
        fallos.append("base_datos")

    try:
        import redis
        cliente = redis.Redis.from_url(str(configuracion.url_redis))
        cliente.ping()
    except Exception:
        fallos.append("redis")

    if fallos:
        return JSONResponse(
            status_code=503,
            content={"estado": "no_listo", "fallos": fallos},
        )
    return JSONResponse(content={"estado": "listo"})


@app.get("/version", tags=["sistema"])
def version() -> dict[str, str]:
    return {"version": app.version, "entorno": configuracion.entorno}


app.mount("/estaticos", StaticFiles(directory="estaticos"), name="estaticos")
app.include_router(autenticacion.enrutador)