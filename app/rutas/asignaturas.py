"""Vista del docente: sus asignaturas del periodo activo."""

"""Vista del docente: sus asignaturas del periodo activo."""

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.base_datos import obtener_sesion
from app.modelos import AsignacionDocente, PeriodoAcademico, Usuario
from app.rutas.navegacion import construir
from app.seguridad.csrf import exigir_csrf
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
            asignacion.companeros = companeros  # type: ignore[misc]
            asignaciones.append(asignacion)

        asignaciones.sort(key=lambda a: a.asignatura.codigo)

    return plantillas.TemplateResponse(request, "mis_asignaturas.html", {
        "usuario": usuario,
        "navegacion": construir(usuario, "/asignaturas"),
        "periodo": periodo,
        "asignaciones": asignaciones,
    })


def _asignacion_o_403(bd, usuario, codigo, periodo):
    """Devuelve la asignatura si el usuario tiene vinculo con ella."""
    from fastapi import HTTPException, status
    from app.modelos import Asignatura

    asignatura = bd.scalar(
        select(Asignatura).where(Asignatura.codigo == codigo)
    )
    if asignatura is None or periodo is None:
        raise HTTPException(status_code=404, detail="Asignatura no encontrada.")

    vinculo = bd.scalar(
        select(AsignacionDocente).where(
            AsignacionDocente.docente_id == usuario.id,
            AsignacionDocente.asignatura_id == asignatura.id,
            AsignacionDocente.periodo_id == periodo.id,
        )
    )
    if vinculo is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene asignada esta asignatura.",
        )
    return asignatura


def _periodo_activo(bd):
    return bd.scalar(
        select(PeriodoAcademico).where(PeriodoAcademico.activo.is_(True))
    )


@enrutador.get("/asignaturas/{codigo}/matriz", response_class=HTMLResponse)
def ver_matriz(
    request: Request,
    codigo: str,
    usuario: Usuario = Depends(exigir_roles("PROFESOR")),
    bd: Session = Depends(obtener_sesion),
):
    from app.modelos import FilaMatriz, MatrizPlanificacion

    periodo = _periodo_activo(bd)
    asignatura = _asignacion_o_403(bd, usuario, codigo, periodo)

    matriz = bd.scalar(
        select(MatrizPlanificacion).where(
            MatrizPlanificacion.asignatura_id == asignatura.id,
            MatrizPlanificacion.periodo_id == periodo.id,
        )
    )
    filas = []
    if matriz:
        filas = bd.scalars(
            select(FilaMatriz)
            .where(FilaMatriz.matriz_id == matriz.id)
            .order_by(FilaMatriz.semana)
        ).all()

    return plantillas.TemplateResponse(request, "subir_matriz.html", {
        "usuario": usuario,
        "navegacion": construir(usuario, "/asignaturas"),
        "asignatura": asignatura,
        "periodo": periodo,
        "matriz": matriz,
        "filas": filas,
        "errores": None,
        "avisos": None,
    })


@enrutador.post("/asignaturas/{codigo}/matriz", dependencies=[Depends(exigir_csrf)])
async def cargar_matriz(
    request: Request,
    codigo: str,
    semanas: int = Form(...),
    archivo: UploadFile = File(...),
    usuario: Usuario = Depends(exigir_roles("PROFESOR")),
    bd: Session = Depends(obtener_sesion),
):
    from app.modelos import FilaMatriz, MatrizPlanificacion
    from app.seguridad import auditoria
    from app.servicios.matriz import validar

    periodo = _periodo_activo(bd)
    asignatura = _asignacion_o_403(bd, usuario, codigo, periodo)

    base: dict = {
        "usuario": usuario,
        "navegacion": construir(usuario, "/asignaturas"),
        "asignatura": asignatura,
        "periodo": periodo,
        "matriz": None,
        "filas": [],
        "errores": None,
        "avisos": None,
    }

    contenido = await archivo.read()
    resultado = validar(archivo.filename or "", contenido, semanas)

    if not resultado.valida:
        base["errores"] = resultado.errores
        base["avisos"] = resultado.avisos
        return plantillas.TemplateResponse(
            request, "subir_matriz.html", base, status_code=400
        )

    existente = bd.scalar(
        select(MatrizPlanificacion).where(
            MatrizPlanificacion.asignatura_id == asignatura.id,
            MatrizPlanificacion.periodo_id == periodo.id,
        )

    )
    if existente:
        base["errores"] = [
            "Esta asignatura ya tiene matriz. Use 'Reemplazar matriz' primero."
        ]
        return plantillas.TemplateResponse(
            request, "subir_matriz.html", base, status_code=400
        )

    matriz = MatrizPlanificacion(
        asignatura_id=asignatura.id,
        periodo_id=periodo.id,
        semanas_totales=resultado.semanas_totales,
        nombre_archivo=(archivo.filename or "")[:255],
        subida_por_id=usuario.id,
    )
    bd.add(matriz)
    bd.flush()

    for fila in resultado.filas:
        bd.add(FilaMatriz(
            matriz_id=matriz.id,
            semana=fila.semana,
            resultado_aprendizaje=fila.resultado_aprendizaje or None,
            unidad_contenido=fila.unidad_contenido,
            metodologia=fila.metodologia or None,
            actividades=fila.actividades or None,
        ))

    bd.commit()

    auditoria.registrar(
        bd, "matriz.cargada", actor_id=usuario.id,
        tipo_entidad="asignatura", id_entidad=asignatura.codigo,
        detalles={"semanas": resultado.semanas_totales,
                  "archivo": archivo.filename},
        request=request,
    )

    return RedirectResponse(
        url=f"/asignaturas/{asignatura.codigo}/matriz", status_code=303
    )


@enrutador.post("/asignaturas/{codigo}/matriz/eliminar",
                dependencies=[Depends(exigir_csrf)])
def eliminar_matriz(
    request: Request,
    codigo: str,
    usuario: Usuario = Depends(exigir_roles("PROFESOR")),
    bd: Session = Depends(obtener_sesion),
):
    from fastapi import HTTPException
    from app.modelos import Guia, MatrizPlanificacion
    from app.seguridad import auditoria

    periodo = _periodo_activo(bd)
    asignatura = _asignacion_o_403(bd, usuario, codigo, periodo)

    # Si ya hay guia generada, la matriz no se toca.
    guia = bd.scalar(
        select(Guia).where(
            Guia.asignatura_id == asignatura.id,
            Guia.periodo_id == periodo.id,
        )
    )
    if guia is not None:
        raise HTTPException(
            status_code=409,
            detail="No se puede reemplazar la matriz: ya existe una guía "
                   "basada en ella.",
        )

    matriz = bd.scalar(
        select(MatrizPlanificacion).where(
            MatrizPlanificacion.asignatura_id == asignatura.id,
            MatrizPlanificacion.periodo_id == periodo.id,
        )
    )
    if matriz:
        bd.delete(matriz)
        bd.commit()
        auditoria.registrar(
            bd, "matriz.eliminada", actor_id=usuario.id,
            tipo_entidad="asignatura", id_entidad=asignatura.codigo,
            request=request,
        )

    return RedirectResponse(
        url=f"/asignaturas/{asignatura.codigo}/matriz", status_code=303
    )


@enrutador.post("/asignaturas/{codigo}/guia/iniciar",
                dependencies=[Depends(exigir_csrf)])
def iniciar_guia(
    request: Request,
    codigo: str,
    usuario: Usuario = Depends(exigir_roles("PROFESOR")),
    bd: Session = Depends(obtener_sesion),
):
    from fastapi import HTTPException
    from app.modelos import Guia, MatrizPlanificacion, SemanaGuia
    from app.seguridad import auditoria

    periodo = _periodo_activo(bd)
    asignatura = _asignacion_o_403(bd, usuario, codigo, periodo)

    matriz = bd.scalar(
        select(MatrizPlanificacion).where(
            MatrizPlanificacion.asignatura_id == asignatura.id,
            MatrizPlanificacion.periodo_id == periodo.id,
        )
    )
    if matriz is None:
        raise HTTPException(
            status_code=400,
            detail="No se puede iniciar la guía sin matriz de planificación.",
        )

    existente = bd.scalar(
        select(Guia).where(
            Guia.asignatura_id == asignatura.id,
            Guia.periodo_id == periodo.id,
        )
    )
    if existente is None:
        guia = Guia(
            asignatura_id=asignatura.id,
            periodo_id=periodo.id,
            matriz_id=matriz.id,
            semanas_totales=matriz.semanas_totales,
            estado="EN_EDICION",
            creada_por_id=usuario.id,
        )
        bd.add(guia)
        bd.flush()

        for numero in range(1, matriz.semanas_totales + 1):
            bd.add(SemanaGuia(guia_id=guia.id, numero=numero, estado="PENDIENTE"))

        bd.commit()
        auditoria.registrar(
            bd, "guia.iniciada", actor_id=usuario.id,
            tipo_entidad="asignatura", id_entidad=asignatura.codigo,
            detalles={"semanas": matriz.semanas_totales}, request=request,
        )

    return RedirectResponse(
        url=f"/asignaturas/{asignatura.codigo}/guia", status_code=303
    )


@enrutador.get("/asignaturas/{codigo}/guia", response_class=HTMLResponse)
def ver_guia(
    request: Request,
    codigo: str,
    usuario: Usuario = Depends(exigir_roles("PROFESOR")),
    bd: Session = Depends(obtener_sesion),
):
    from app.modelos import FilaMatriz, Guia, SemanaGuia

    periodo = _periodo_activo(bd)
    asignatura = _asignacion_o_403(bd, usuario, codigo, periodo)

    guia = bd.scalar(
        select(Guia).where(
            Guia.asignatura_id == asignatura.id,
            Guia.periodo_id == periodo.id,
        )
    )
    if guia is None:
        return RedirectResponse(
            url=f"/asignaturas/{asignatura.codigo}/matriz", status_code=303
        )

    semanas = bd.scalars(
        select(SemanaGuia)
        .where(SemanaGuia.guia_id == guia.id)
        .order_by(SemanaGuia.numero)
    ).all()

    filas = bd.scalars(
        select(FilaMatriz).where(FilaMatriz.matriz_id == guia.matriz_id)
    ).all()
    temas = {f.semana: f.unidad_contenido for f in filas}

    aprobadas = sum(1 for s in semanas if s.estado == "APROBADA")
    porcentaje = round(aprobadas / guia.semanas_totales * 100) if guia.semanas_totales else 0

    return plantillas.TemplateResponse(request, "guia.html", {
        "usuario": usuario,
        "navegacion": construir(usuario, "/asignaturas"),
        "asignatura": asignatura,
        "periodo": periodo,
        "guia": guia,
        "semanas": semanas,
        "temas": temas,
        "aprobadas": aprobadas,
        "porcentaje": porcentaje,
    })
