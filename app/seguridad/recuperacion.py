"""Solicitud y uso de tokens de recuperacion de contrasena."""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.configuracion import configuracion
from app.modelos import TokenRecuperacion, Usuario

# Limites contra el uso de la funcion como herramienta de acoso.
MAXIMO_POR_CUENTA_HORA = 3
MAXIMO_POR_IP_HORA = 5


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _excede_limite(bd: Session, usuario_id, ip: str | None) -> bool:
    desde = _ahora() - timedelta(hours=1)

    por_cuenta = len(bd.scalars(
        select(TokenRecuperacion).where(
            TokenRecuperacion.usuario_id == usuario_id,
            TokenRecuperacion.creado_en >= desde,
        )
    ).all())
    if por_cuenta >= MAXIMO_POR_CUENTA_HORA:
        return True

    if ip:
        por_ip = len(bd.scalars(
            select(TokenRecuperacion).where(
                TokenRecuperacion.ip_solicitud == ip,
                TokenRecuperacion.creado_en >= desde,
            )
        ).all())
        if por_ip >= MAXIMO_POR_IP_HORA:
            return True

    return False


def solicitar(bd: Session, correo: str, ip: str | None = None) -> str | None:
    """Genera un token si procede. Devuelve None sin revelar el motivo."""
    usuario = bd.scalar(
        select(Usuario).where(Usuario.correo == correo.strip().lower())
    )
    if usuario is None or usuario.estado != "ACTIVO":
        return None

    if (usuario.vigencia_hasta is not None
            and usuario.vigencia_hasta <= _ahora()):
        return None

    if _excede_limite(bd, usuario.id, ip):
        return None

    # Un token nuevo invalida los anteriores.
    bd.execute(
        update(TokenRecuperacion)
        .where(
            TokenRecuperacion.usuario_id == usuario.id,
            TokenRecuperacion.usado_en.is_(None),
            TokenRecuperacion.invalidado_en.is_(None),
        )
        .values(invalidado_en=_ahora())
    )

    token = secrets.token_urlsafe(32)
    bd.add(TokenRecuperacion(
        usuario_id=usuario.id,
        hash_token=_hash(token),
        expira_en=_ahora() + timedelta(
            minutes=configuracion.minutos_token_recuperacion
        ),
        ip_solicitud=ip,
    ))
    bd.commit()
    return token


def validar(bd: Session, token: str) -> Usuario | None:
    """Devuelve el usuario si el token sirve. No lo consume."""
    registro = bd.scalar(
        select(TokenRecuperacion).where(
            TokenRecuperacion.hash_token == _hash(token)
        )
    )
    if registro is None:
        return None
    if registro.usado_en is not None or registro.invalidado_en is not None:
        return None
    if registro.expira_en <= _ahora():
        return None
    if registro.usuario.estado != "ACTIVO":
        return None
    return registro.usuario


def consumir(bd: Session, token: str) -> None:
    """Marca el token como usado. Un solo uso."""
    registro = bd.scalar(
        select(TokenRecuperacion).where(
            TokenRecuperacion.hash_token == _hash(token)
        )
    )
    if registro and registro.usado_en is None:
        registro.usado_en = _ahora()
        bd.commit()
