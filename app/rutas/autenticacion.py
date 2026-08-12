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
from app.seguridad.csrf import exigir_csrf
from app.seguridad import auditoria

from app.seguridad.dependencias import usuario_actual

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


@enrutador.post("/ingresar", dependencies=[Depends(exigir_csrf)])
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
        auditoria.registrar(
            bd, "ingreso.bloqueado", actor_id=usuario.id,
            detalles={"correo": correo_normalizado}, request=request,
        )
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
        auditoria.registrar(
            bd, "ingreso.fallido",
            actor_id=usuario.id if usuario else None,
            detalles={"correo": correo_normalizado}, request=request,
        )
        return plantillas.TemplateResponse(
            request, "login.html",
            {"error": MENSAJE_CREDENCIALES, "correo": correo_normalizado},
            status_code=401,
        )

    if usuario.estado != "ACTIVO":
        auditoria.registrar(
            bd, "ingreso.rechazado", actor_id=usuario.id,
            detalles={"motivo": "cuenta no activa"}, request=request,
        )
        return plantillas.TemplateResponse(
            request, "login.html",
            {"error": MENSAJE_CREDENCIALES, "correo": correo_normalizado},
            status_code=401,
        )

    if usuario.vigencia_hasta is not None and usuario.vigencia_hasta <= _ahora():
        auditoria.registrar(
            bd, "ingreso.rechazado", actor_id=usuario.id,
            detalles={"motivo": "vigencia vencida"}, request=request,
        )
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
    auditoria.registrar(
        bd, "ingreso.exitoso", actor_id=usuario.id, request=request,
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


@enrutador.post("/salir", dependencies=[Depends(exigir_csrf)])
def salir(request: Request, bd: Session = Depends(obtener_sesion)):
    token = request.cookies.get(sesiones.NOMBRE_COOKIE)
    if token:
        usuario = sesiones.obtener_usuario(bd, token)
        sesiones.revocar(bd, token)
        if usuario:
            auditoria.registrar(
                bd, "sesion.cerrada", actor_id=usuario.id, request=request
            )
    respuesta = RedirectResponse(url="/ingresar", status_code=303)
    respuesta.delete_cookie(sesiones.NOMBRE_COOKIE, path="/")
    return respuesta

@enrutador.get("/inicio", response_class=HTMLResponse)
def inicio(request: Request, usuario: Usuario = Depends(usuario_actual)):
    return plantillas.TemplateResponse(request, "inicio.html", {"usuario": usuario})