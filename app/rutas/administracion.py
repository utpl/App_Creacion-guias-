"""Panel de administracion. Solo rol ADMIN."""

import math

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

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
