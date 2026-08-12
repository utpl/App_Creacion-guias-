"""Panel de administracion. Solo rol ADMIN."""

import math

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session
from fastapi.responses import HTMLResponse, RedirectResponse
from app.seguridad.csrf import exigir_csrf
from app.base_datos import obtener_sesion
from app.modelos import Rol, Usuario, UsuarioRol
from app.rutas.navegacion import construir
from app.seguridad.dependencias import exigir_roles

enrutador = APIRouter(prefix="/admin")
plantillas = Jinja2Templates(directory="plantillas")

POR_PAGINA = 25


@enrutador.get("/usuarios", response_class=HTMLResponse)
def listar_usuarios(
    request: Request,
    busqueda: str = "",
    rol: str = "",
    pagina: int = 1,
    usuario: Usuario = Depends(exigir_roles("ADMIN")),
    bd: Session = Depends(obtener_sesion),
):
    consulta = select(Usuario)

    if busqueda:
        patron = f"%{busqueda.strip().lower()}%"
        consulta = consulta.where(or_(
            func.lower(Usuario.correo).like(patron),
            func.lower(Usuario.nombres).like(patron),
            func.lower(Usuario.apellidos).like(patron),
        ))

    if rol:
        consulta = consulta.join(UsuarioRol).join(Rol).where(Rol.codigo == rol)

    total = bd.scalar(
        select(func.count()).select_from(consulta.subquery())
    ) or 0
    paginas = max(1, math.ceil(total / POR_PAGINA))
    pagina = max(1, min(pagina, paginas))

    usuarios = bd.scalars(
        consulta.order_by(Usuario.apellidos, Usuario.nombres)
        .offset((pagina - 1) * POR_PAGINA)
        .limit(POR_PAGINA)
    ).unique().all()

    return plantillas.TemplateResponse(request, "admin_usuarios.html", {
        "usuario": usuario,
        "navegacion": construir(usuario, "/admin/usuarios"),
        "usuarios": usuarios,
        "roles": bd.scalars(select(Rol).order_by(Rol.codigo)).all(),
        "busqueda": busqueda,
        "rol": rol,
        "total": total,
        "pagina": pagina,
        "paginas": paginas,
    })
@enrutador.get("/sesiones", response_class=HTMLResponse)
def listar_sesiones(
    request: Request,
    usuario: Usuario = Depends(exigir_roles("ADMIN")),
    bd: Session = Depends(obtener_sesion),
):
    from datetime import datetime, timezone
    from app.modelos import Sesion

    ahora = datetime.now(timezone.utc)
    activas = bd.scalars(
        select(Sesion)
        .where(Sesion.revocada_en.is_(None), Sesion.expira_en > ahora)
        .order_by(Sesion.ultima_actividad.desc())
    ).all()

    return plantillas.TemplateResponse(request, "admin_sesiones.html", {
        "usuario": usuario,
        "navegacion": construir(usuario, "/admin/sesiones"),
        "sesiones": activas,
    })


@enrutador.post("/sesiones/{sesion_id}/revocar")
def revocar_sesion(
    request: Request,
    sesion_id: str,
    usuario: Usuario = Depends(exigir_roles("ADMIN")),
    bd: Session = Depends(obtener_sesion),
    _=Depends(exigir_csrf),
):
    from datetime import datetime, timezone
    from app.modelos import Sesion
    from app.seguridad import auditoria

    sesion = bd.get(Sesion, sesion_id)
    if sesion and sesion.revocada_en is None:
        sesion.revocada_en = datetime.now(timezone.utc)
        bd.commit()
        auditoria.registrar(
            bd, "sesion.revocada_por_admin", actor_id=usuario.id,
            tipo_entidad="sesion", id_entidad=str(sesion_id), request=request,
        )
    return RedirectResponse(url="/admin/sesiones", status_code=303)


@enrutador.get("/auditoria", response_class=HTMLResponse)
def ver_auditoria(
    request: Request,
    accion: str = "",
    pagina: int = 1,
    usuario: Usuario = Depends(exigir_roles("ADMIN")),
    bd: Session = Depends(obtener_sesion),
):
    from app.modelos import RegistroAuditoria

    consulta = select(RegistroAuditoria)
    if accion:
        consulta = consulta.where(RegistroAuditoria.accion == accion)

    total = bd.scalar(select(func.count()).select_from(consulta.subquery())) or 0
    paginas = max(1, math.ceil(total / POR_PAGINA))
    pagina = max(1, min(pagina, paginas))

    registros = bd.scalars(
        consulta.order_by(RegistroAuditoria.ocurrido_en.desc())
        .offset((pagina - 1) * POR_PAGINA).limit(POR_PAGINA)
    ).all()

    nombres = {
        u.id: u.nombre_completo
        for u in bd.scalars(select(Usuario)).all()
    }

    acciones = bd.scalars(
        select(RegistroAuditoria.accion).distinct().order_by(RegistroAuditoria.accion)
    ).all()

    return plantillas.TemplateResponse(request, "admin_auditoria.html", {
        "usuario": usuario,
        "navegacion": construir(usuario, "/admin/auditoria"),
        "registros": registros,
        "nombres": nombres,
        "acciones": acciones,
        "accion": accion,
        "total": total,
        "pagina": pagina,
        "paginas": paginas,
    })