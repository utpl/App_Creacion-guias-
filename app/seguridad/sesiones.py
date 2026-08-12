"""Creacion, validacion y revocacion de sesiones."""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session as SesionBD

from app.configuracion import configuracion
from app.modelos import Sesion, Usuario

# El prefijo __Host- exige el atributo Secure, que no existe sin HTTPS.
NOMBRE_COOKIE = (
    "ediloja_sesion"
    if configuracion.entorno == "desarrollo"
    else "__Host-ediloja_sesion"
)


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def crear(
    bd: SesionBD,
    usuario: Usuario,
    ip: str | None = None,
    agente_usuario: str | None = None,
) -> str:
    """Crea una sesion y devuelve el token en claro. Solo se ve aqui."""
    token = secrets.token_urlsafe(32)
    bd.add(Sesion(
        usuario_id=usuario.id,
        hash_token=_hash(token),
        expira_en=_ahora() + timedelta(hours=configuracion.horas_sesion),
        ip=ip,
        agente_usuario=(agente_usuario or "")[:255] or None,
    ))
    bd.commit()
    return token


def obtener_usuario(bd: SesionBD, token: str | None) -> Usuario | None:
    """Devuelve el usuario si la sesion es valida, y renueva la actividad."""
    if not token:
        return None

    sesion = bd.scalar(
        select(Sesion).where(Sesion.hash_token == _hash(token))
    )
    if sesion is None or sesion.revocada_en is not None:
        return None

    ahora = _ahora()

    if sesion.expira_en <= ahora:
        return None

    limite_inactividad = timedelta(minutes=configuracion.minutos_inactividad)
    if ahora - sesion.ultima_actividad > limite_inactividad:
        sesion.revocada_en = ahora
        bd.commit()
        return None

    if sesion.usuario.estado != "ACTIVO":
        return None

    if (sesion.usuario.vigencia_hasta is not None
            and sesion.usuario.vigencia_hasta <= ahora):
        return None

    sesion.ultima_actividad = ahora
    bd.commit()
    return sesion.usuario


def revocar(bd: SesionBD, token: str) -> None:
    """Cierra una sesion concreta."""
    sesion = bd.scalar(select(Sesion).where(Sesion.hash_token == _hash(token)))
    if sesion and sesion.revocada_en is None:
        sesion.revocada_en = _ahora()
        bd.commit()


def revocar_todas(bd: SesionBD, usuario_id) -> int:
    """Cierra todas las sesiones de un usuario. Devuelve cuantas cerro."""
    resultado = bd.execute(
        update(Sesion)
        .where(Sesion.usuario_id == usuario_id, Sesion.revocada_en.is_(None))
        .values(revocada_en=_ahora())
    )
    bd.commit()
    return resultado.rowcount
