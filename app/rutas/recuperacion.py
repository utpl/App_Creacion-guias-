"""Rutas de recuperacion de contrasena."""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.base_datos import obtener_sesion
from app.configuracion import configuracion
from app.seguridad import auditoria, correo, recuperacion, sesiones
from app.seguridad.csrf import exigir_csrf
from app.seguridad.passwords import generar_hash, validar_fortaleza

enrutador = APIRouter()
plantillas = Jinja2Templates(directory="plantillas")


@enrutador.get("/recuperar", response_class=HTMLResponse)
def mostrar_solicitud(request: Request):
    return plantillas.TemplateResponse(
        request, "recuperar.html", {"enviado": False}
    )


@enrutador.post("/recuperar", dependencies=[Depends(exigir_csrf)])
def procesar_solicitud(
    request: Request,
    correo_ingresado: str = Form(..., alias="correo"),
    bd: Session = Depends(obtener_sesion),
):
    ip = request.client.host if request.client else None
    token = recuperacion.solicitar(bd, correo_ingresado, ip=ip)

    if token:
        usuario = recuperacion.validar(bd, token)
        if usuario:
            url = f"{configuracion.url_publica}/restablecer/{token}"
            asunto, cuerpo = correo.enlace_recuperacion(url, usuario.nombres)
            correo.enviar(usuario.correo, asunto, cuerpo)
            auditoria.registrar(
                bd, "recuperacion.solicitada",
                actor_id=usuario.id, request=request,
            )

    # La respuesta es identica exista o no la cuenta.
    return plantillas.TemplateResponse(
        request, "recuperar.html", {"enviado": True}
    )


@enrutador.get("/restablecer/{token}", response_class=HTMLResponse)
def mostrar_restablecer(
    request: Request, token: str, bd: Session = Depends(obtener_sesion)
):
    usuario = recuperacion.validar(bd, token)
    if usuario is None:
        return plantillas.TemplateResponse(
            request, "enlace_invalido.html", {}, status_code=400
        )
    return plantillas.TemplateResponse(
        request, "restablecer.html",
        {"token": token, "correo": usuario.correo, "error": None},
    )


@enrutador.post("/restablecer/{token}", dependencies=[Depends(exigir_csrf)])
def procesar_restablecer(
    request: Request,
    token: str,
    password: str = Form(...),
    confirmacion: str = Form(...),
    bd: Session = Depends(obtener_sesion),
):
    usuario = recuperacion.validar(bd, token)
    if usuario is None:
        return plantillas.TemplateResponse(
            request, "enlace_invalido.html", {}, status_code=400
        )

    def con_error(mensaje: str):
        return plantillas.TemplateResponse(
            request, "restablecer.html",
            {"token": token, "correo": usuario.correo, "error": mensaje},
            status_code=400,
        )

    if password != confirmacion:
        return con_error("Las contraseñas no coinciden.")

    problemas = validar_fortaleza(password)
    if problemas:
        return con_error(" ".join(problemas))

    usuario.hash_password = generar_hash(password)
    usuario.requiere_cambio_password = False
    usuario.intentos_fallidos = 0
    usuario.bloqueado_hasta = None
    bd.commit()

    recuperacion.consumir(bd, token)
    cerradas = sesiones.revocar_todas(bd, usuario.id)

    asunto, cuerpo = correo.aviso_cambio(usuario.nombres)
    correo.enviar(usuario.correo, asunto, cuerpo)

    auditoria.registrar(
        bd, "password.restablecida", actor_id=usuario.id,
        detalles={"sesiones_cerradas": cerradas}, request=request,
    )

    nuevo = sesiones.crear(
        bd, usuario,
        ip=request.client.host if request.client else None,
        agente_usuario=request.headers.get("user-agent"),
    )
    respuesta = RedirectResponse(url="/inicio", status_code=303)
    respuesta.set_cookie(
        key=sesiones.NOMBRE_COOKIE,
        value=nuevo,
        max_age=configuracion.horas_sesion * 3600,
        httponly=True,
        secure=configuracion.entorno != "desarrollo",
        samesite="lax",
        path="/",
    )
    return respuesta
