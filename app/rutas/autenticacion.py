"""Rutas de ingreso y cierre de sesion."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.base_datos import obtener_sesion
from app.configuracion import configuracion
from app.modelos import Usuario
from app.seguridad import sesiones
from app.seguridad.passwords import verificar

enrutador = APIRouter()
plantillas = Jinja2Templates(directory="plantillas")

MENSAJE_CREDENCIALES = "Correo o contraseña incorrectos."

# Minutos de bloqueo segun el numero de intentos fallidos acumulados.
ESCALA_BLOQUEO = {5: 1, 6: 5, 7: 15}
BLOQUEO_MAXIMO = 30


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def _minutos_de_bloqueo(intentos: int) -> int | None:
    if intentos < 5:
        return None
    return ESCALA_BLOQUEO.get(intentos, BLOQUEO_MAXIMO)


@enrutador.get("/ingresar", response_class=HTMLResponse)
def mostrar_login(request: Request):
    return plantillas.TemplateResponse(
        request, "login.html", {"error": None, "correo": None}
    )


@enrutador.post("/ingresar")
def procesar_login(
    request: Request,
    correo: str = Form(...),
    password: str = Form(...),
    bd: Session = Depends(obtener_sesion),
):
    correo_normalizado = correo.strip().lower()

    usuario = bd.scalar(
        select(Usuario).where(Usuario.correo == correo_normalizado)
    )

    # Si esta bloqueado, no se intenta verificar.
    if usuario and usuario.bloqueado_hasta and usuario.bloqueado_hasta > _ahora():
        return plantillas.TemplateResponse(
            request, "login.html",
            {"error": MENSAJE_CREDENCIALES, "correo": correo_normalizado},
            status_code=401,
        )

    # Se verifica SIEMPRE, exista o no el usuario.
    credenciales_validas = verificar(
        password, usuario.hash_password if usuario else None
    )

    if not credenciales_validas or usuario is None:
        if usuario is not None:
            usuario.intentos_fallidos += 1
            minutos = _minutos_de_bloqueo(usuario.intentos_fallidos)
            if minutos:
                usuario.bloqueado_hasta = _ahora() + timedelta(minutes=minutos)
            bd.commit()
        return plantillas.TemplateResponse(
            request, "login.html",
            {"error": MENSAJE_CREDENCIALES, "correo": correo_normalizado},
            status_code=401,
        )

    if usuario.estado != "ACTIVO":
        return plantillas.TemplateResponse(
            request, "login.html",
            {"error": MENSAJE_CREDENCIALES, "correo": correo_normalizado},
            status_code=401,
        )

    if usuario.vigencia_hasta is not None and usuario.vigencia_hasta <= _ahora():
        return plantillas.TemplateResponse(
            request, "login.html",
            {"error": MENSAJE_CREDENCIALES, "correo": correo_normalizado},
            status_code=401,
        )

    usuario.intentos_fallidos = 0
    usuario.bloqueado_hasta = None
    usuario.ultimo_acceso = _ahora()
    bd.commit()

    token = sesiones.crear(
        bd, usuario,
        ip=request.client.host if request.client else None,
        agente_usuario=request.headers.get("user-agent"),
    )

    respuesta = RedirectResponse(url="/inicio", status_code=303)
    respuesta.set_cookie(
        key=sesiones.NOMBRE_COOKIE,
        value=token,
        max_age=configuracion.horas_sesion * 3600,
        httponly=True,
        secure=configuracion.entorno != "desarrollo",
        samesite="lax",
        path="/",
    )
    return respuesta


@enrutador.post("/salir")
def salir(request: Request, bd: Session = Depends(obtener_sesion)):
    token = request.cookies.get(sesiones.NOMBRE_COOKIE)
    if token:
        sesiones.revocar(bd, token)
    respuesta = RedirectResponse(url="/ingresar", status_code=303)
    respuesta.delete_cookie(sesiones.NOMBRE_COOKIE, path="/")
    return respuesta
