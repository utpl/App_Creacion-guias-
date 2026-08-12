"""Registro de auditoria. Nunca almacena datos sensibles."""

from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from app.modelos import RegistroAuditoria

# Claves que jamas se escriben, aunque lleguen por error.
_PROHIBIDAS = {
    "password", "contrasena", "token", "hash_password",
    "csrf_token", "cookie", "authorization",
}


def _limpiar(detalles: dict[str, Any] | None) -> dict[str, Any] | None:
    if not detalles:
        return None
    return {
        clave: valor
        for clave, valor in detalles.items()
        if clave.lower() not in _PROHIBIDAS
    }


def registrar(
    bd: Session,
    accion: str,
    actor_id=None,
    tipo_entidad: str | None = None,
    id_entidad: str | None = None,
    detalles: dict[str, Any] | None = None,
    request: Request | None = None,
) -> None:
    bd.add(RegistroAuditoria(
        actor_id=actor_id,
        accion=accion,
        tipo_entidad=tipo_entidad,
        id_entidad=id_entidad,
        detalles=_limpiar(detalles),
        ip=request.client.host if request and request.client else None,
        agente_usuario=(request.headers.get("user-agent") or "")[:255]
                       if request else None,
    ))
    bd.commit()
