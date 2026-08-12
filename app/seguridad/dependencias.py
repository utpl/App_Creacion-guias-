"""Dependencias de FastAPI para exigir sesion y permisos."""

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.base_datos import obtener_sesion
from app.modelos import Usuario
from app.seguridad import sesiones


class RedireccionAlLogin(Exception):
    """Se lanza cuando no hay sesion valida en una vista HTML."""


def usuario_actual(
    request: Request,
    bd: Session = Depends(obtener_sesion),
) -> Usuario:
    """Exige sesion valida. Redirige al login si no la hay."""
    token = request.cookies.get(sesiones.NOMBRE_COOKIE)
    usuario = sesiones.obtener_usuario(bd, token)
    if usuario is None:
        raise RedireccionAlLogin()
    return usuario


def usuario_opcional(
    request: Request,
    bd: Session = Depends(obtener_sesion),
) -> Usuario | None:
    """Devuelve el usuario si hay sesion, sin exigirla."""
    token = request.cookies.get(sesiones.NOMBRE_COOKIE)
    return sesiones.obtener_usuario(bd, token)


def exigir_roles(*codigos: str):
    """Genera una dependencia que exige al menos uno de los roles indicados."""

    def verificador(usuario: Usuario = Depends(usuario_actual)) -> Usuario:
        roles = {vinculo.rol.codigo for vinculo in usuario.roles}
        if not roles.intersection(codigos):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tiene permiso para acceder a esta seccion.",
            )
        return usuario

    return verificador
