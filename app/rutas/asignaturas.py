"""Vista del docente: sus asignaturas del periodo activo."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.base_datos import obtener_sesion
from app.modelos import AsignacionDocente, PeriodoAcademico, Usuario
from app.rutas.navegacion import construir
from app.seguridad.dependencias import exigir_roles

enrutador = APIRouter()
plantillas = Jinja2Templates(directory="plantillas")


@enrutador.get("/asignaturas", response_class=HTMLResponse)
def mis_asignaturas(
    request: Request,
    usuario: Usuario = Depends(exigir_roles("PROFESOR")),
    bd: Session = Depends(obtener_sesion),
):
    periodo = bd.scalar(
        select(PeriodoAcademico).where(PeriodoAcademico.activo.is_(True))
    )

    asignaciones = []
    if periodo:
        # Solo las asignaciones donde ESTE usuario tiene vinculo.
        propias = bd.scalars(
            select(AsignacionDocente).where(
                AsignacionDocente.docente_id == usuario.id,
                AsignacionDocente.periodo_id == periodo.id,
            )
        ).all()

        for asignacion in propias:
            otros = bd.scalars(
                select(AsignacionDocente).where(
                    AsignacionDocente.asignatura_id == asignacion.asignatura_id,
                    AsignacionDocente.periodo_id == periodo.id,
                    AsignacionDocente.docente_id != usuario.id,
                )
            ).all()
            companeros = []
            for otro in otros:
                persona = bd.get(Usuario, otro.docente_id)
                if persona:
                    companeros.append(persona.nombre_completo)
            asignacion.companeros = companeros
            asignaciones.append(asignacion)

        asignaciones.sort(key=lambda a: a.asignatura.codigo)

    return plantillas.TemplateResponse(request, "mis_asignaturas.html", {
        "usuario": usuario,
        "navegacion": construir(usuario, "/asignaturas"),
        "periodo": periodo,
        "asignaciones": asignaciones,
    })
