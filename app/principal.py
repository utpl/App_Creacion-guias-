"""Aplicacion FastAPI de App-EdiLoja."""

from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from app.rutas import autenticacion
from sqlalchemy import text
from sqlalchemy.orm import Session
from fastapi.responses import RedirectResponse
from app.seguridad.dependencias import RedireccionAlLogin
from starlette.middleware.base import BaseHTTPMiddleware
from app.seguridad import csrf
from app.rutas import administracion, autenticacion, recuperacion

from app.rutas import autenticacion, recuperacion

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

@app.exception_handler(RedireccionAlLogin)
def manejar_sin_sesion(request, exc):
    return RedirectResponse(url="/ingresar", status_code=303) 


class MiddlewareCSRF(BaseHTTPMiddleware):
    """Emite el token CSRF en cada respuesta y lo deja disponible en la plantilla."""

    async def dispatch(self, request, call_next):
        token = request.cookies.get(csrf.NOMBRE_COOKIE_CSRF)
        if not token or not csrf.es_valido(token):
            token = csrf.generar()
            nuevo = True
        else:
            nuevo = False

        request.state.csrf_token = token
        respuesta = await call_next(request)

        if nuevo:
            respuesta.set_cookie(
                key=csrf.NOMBRE_COOKIE_CSRF,
                value=token,
                httponly=False,          # htmx debe poder leerlo
                secure=configuracion.entorno != "desarrollo",
                samesite="lax",
                path="/",
            )
        return respuesta


app.add_middleware(MiddlewareCSRF)

app.mount("/estaticos", StaticFiles(directory="estaticos"), name="estaticos")
app.include_router(autenticacion.enrutador)
app.include_router(recuperacion.enrutador)
app.include_router(administracion.enrutador)