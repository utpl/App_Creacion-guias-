"""Proteccion contra falsificacion de solicitudes entre sitios."""

import hmac
import secrets
from hashlib import sha256

from fastapi import HTTPException, Request, status

from app.configuracion import configuracion

NOMBRE_COOKIE_CSRF = "ediloja_csrf"
NOMBRE_CAMPO = "csrf_token"
NOMBRE_CABECERA = "X-CSRF-Token"

_CLAVE = configuracion.clave_secreta.get_secret_value().encode()


def generar() -> str:
    """Genera un token nuevo, firmado con la clave del servidor."""
    aleatorio = secrets.token_urlsafe(24)
    firma = hmac.new(_CLAVE, aleatorio.encode(), sha256).hexdigest()[:32]
    return f"{aleatorio}.{firma}"


def es_valido(token: str | None) -> bool:
    """Comprueba que el token lo emitio este servidor."""
    if not token or "." not in token:
        return False
    aleatorio, firma = token.rsplit(".", 1)
    esperada = hmac.new(_CLAVE, aleatorio.encode(), sha256).hexdigest()[:32]
    return hmac.compare_digest(firma, esperada)


async def exigir_csrf(request: Request) -> None:
    """Dependencia para toda ruta que modifique estado."""
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return

    de_cookie = request.cookies.get(NOMBRE_COOKIE_CSRF)

    enviado = request.headers.get(NOMBRE_CABECERA)
    if enviado is None:
        formulario = await request.form()
        valor = formulario.get(NOMBRE_CAMPO)
        enviado = valor if isinstance(valor, str) else None

    if not de_cookie or not enviado:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solicitud sin token de seguridad.",
        )

    if not hmac.compare_digest(de_cookie, enviado) or not es_valido(enviado):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token de seguridad invalido.",
        )
