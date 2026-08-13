"""Panel del Vicerrectorado Academico. Solo rol ADMIN_VRA."""

import math

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.base_datos import obtener_sesion
from app.modelos import (
    AsignacionDocente,
    Asignatura,
    Carrera,
    Facultad,
    Guia,
    MatrizPlanificacion,
    PeriodoAcademico,
    Usuario,
)
from app.rutas.navegacion import construir
from app.seguridad.csrf import exigir_csrf
from app.seguridad.dependencias import exigir_roles

enrutador = APIRouter(prefix="/vra")
plantillas = Jinja2Templates(directory="plantillas")

POR_PAGINA = 30


def _periodo_activo(bd: Session):
    return bd.scalar(
        select(PeriodoAcademico).where(PeriodoAcademico.activo.is_(True))
    )


@enrutador.get("/catalogo", response_class=HTMLResponse)
def catalogo(
    request: Request,
    busqueda: str = "",
    carrera: str = "",
    pagina: int = 1,
    usuario: Usuario = Depends(exigir_roles("ADMIN_VRA")),
    bd: Session = Depends(obtener_sesion),
):
    consulta = select(Asignatura)

    if busqueda:
        patron = f"%{busqueda.strip().lower()}%"
        consulta = consulta.where(or_(
            func.lower(Asignatura.codigo).like(patron),
            func.lower(Asignatura.nombre).like(patron),
        ))

    if carrera:
        consulta = consulta.where(Asignatura.carrera_id == carrera)

    total = bd.scalar(select(func.count()).select_from(consulta.subquery())) or 0
    paginas = max(1, math.ceil(total / POR_PAGINA))
    pagina = max(1, min(pagina, paginas))

    asignaturas = bd.scalars(
        consulta.order_by(Asignatura.codigo)
        .offset((pagina - 1) * POR_PAGINA).limit(POR_PAGINA)
    ).unique().all()

    periodo = _periodo_activo(bd)
    docentes: dict = {}
    if periodo:
        filas = bd.execute(
            select(AsignacionDocente.asignatura_id, func.count())
            .where(AsignacionDocente.periodo_id == periodo.id)
            .group_by(AsignacionDocente.asignatura_id)
        ).all()
        docentes = {fila[0]: fila[1] for fila in filas}

    resumen = [
        ("Facultades", bd.scalar(select(func.count()).select_from(Facultad)) or 0),
        ("Carreras", bd.scalar(select(func.count()).select_from(Carrera)) or 0),
        ("Asignaturas", bd.scalar(select(func.count()).select_from(Asignatura)) or 0),
    ]

    return plantillas.TemplateResponse(request, "vra_catalogo.html", {
        "usuario": usuario,
        "navegacion": construir(usuario, "/vra/catalogo"),
        "asignaturas": asignaturas,
        "carreras": bd.scalars(select(Carrera).order_by(Carrera.nombre)).all(),
        "docentes": docentes,
        "resumen": resumen,
        "busqueda": busqueda,
        "carrera": carrera,
        "total": total,
        "pagina": pagina,
        "paginas": paginas,
    })


@enrutador.get("/periodos", response_class=HTMLResponse)
def periodos(
    request: Request,
    usuario: Usuario = Depends(exigir_roles("ADMIN_VRA")),
    bd: Session = Depends(obtener_sesion),
):
    return _vista_periodos(request, usuario, bd)


def _vista_periodos(request, usuario, bd, error=None, codigo=200):
    lista = bd.scalars(
        select(PeriodoAcademico).order_by(PeriodoAcademico.creado_en.desc())
    ).all()

    conteo_asig = {
        fila[0]: fila[1]
        for fila in bd.execute(
            select(AsignacionDocente.periodo_id, func.count())
            .group_by(AsignacionDocente.periodo_id)
        ).all()
    }
    conteo_guias = {
        fila[0]: fila[1]
        for fila in bd.execute(
            select(Guia.periodo_id, func.count()).group_by(Guia.periodo_id)
        ).all()
    }

    return plantillas.TemplateResponse(request, "vra_periodos.html", {
        "usuario": usuario,
        "navegacion": construir(usuario, "/vra/periodos"),
        "periodos": lista,
        "asignaciones": conteo_asig,
        "guias": conteo_guias,
        "error": error,
    }, status_code=codigo)


@enrutador.post("/periodos", dependencies=[Depends(exigir_csrf)])
def crear_periodo(
    request: Request,
    nombre: str = Form(...),
    usuario: Usuario = Depends(exigir_roles("ADMIN_VRA")),
    bd: Session = Depends(obtener_sesion),
):
    from app.seguridad import auditoria

    limpio = nombre.strip()
    if not limpio:
        return _vista_periodos(request, usuario, bd,
                               "El nombre no puede estar vacío.", 400)

    if bd.scalar(select(PeriodoAcademico).where(PeriodoAcademico.nombre == limpio)):
        return _vista_periodos(request, usuario, bd,
                               f"Ya existe un periodo llamado «{limpio}».", 400)

    bd.add(PeriodoAcademico(nombre=limpio, activo=False))
    bd.commit()

    auditoria.registrar(
        bd, "periodo.creado", actor_id=usuario.id,
        tipo_entidad="periodo", id_entidad=limpio, request=request,
    )
    return RedirectResponse(url="/vra/periodos", status_code=303)


@enrutador.post("/periodos/{periodo_id}/activar",
                dependencies=[Depends(exigir_csrf)])
def activar_periodo(
    request: Request,
    periodo_id: str,
    usuario: Usuario = Depends(exigir_roles("ADMIN_VRA")),
    bd: Session = Depends(obtener_sesion),
):
    from sqlalchemy import update
    from app.seguridad import auditoria

    periodo = bd.get(PeriodoAcademico, periodo_id)
    if periodo is None:
        return _vista_periodos(request, usuario, bd, "Periodo no encontrado.", 404)

    # Solo uno activo a la vez.
    bd.execute(update(PeriodoAcademico).values(activo=False))
    periodo.activo = True
    bd.commit()

    auditoria.registrar(
        bd, "periodo.activado", actor_id=usuario.id,
        tipo_entidad="periodo", id_entidad=periodo.nombre, request=request,
    )
    return RedirectResponse(url="/vra/periodos", status_code=303)


@enrutador.get("/avance", response_class=HTMLResponse)
def avance(
    request: Request,
    usuario: Usuario = Depends(exigir_roles("ADMIN_VRA")),
    bd: Session = Depends(obtener_sesion),
):
    periodo = _periodo_activo(bd)

    total_asignaturas = bd.scalar(
        select(func.count()).select_from(Asignatura)
    ) or 0

    con_matriz = set()
    con_guia = set()
    con_titular = set()

    if periodo:
        con_matriz = {
            f[0] for f in bd.execute(
                select(MatrizPlanificacion.asignatura_id)
                .where(MatrizPlanificacion.periodo_id == periodo.id)
            ).all()
        }
        con_guia = {
            f[0] for f in bd.execute(
                select(Guia.asignatura_id).where(Guia.periodo_id == periodo.id)
            ).all()
        }
        con_titular = {
            f[0] for f in bd.execute(
                select(AsignacionDocente.asignatura_id).where(
                    AsignacionDocente.periodo_id == periodo.id,
                    AsignacionDocente.rol_en_asignatura == "titular",
                )
            ).all()
        }

    todas = bd.scalars(select(Asignatura)).unique().all()
    bloqueadas = [a for a in todas if a.id not in con_titular]

    tarjetas = [
        ("Asignaturas", total_asignaturas, "var(--ed-primary)"),
        ("Con matriz", len(con_matriz), "var(--ed-primary)"),
        ("Con guía", len(con_guia), "var(--ed-success)"),
        ("Sin docente", len(bloqueadas),
         "var(--ed-danger)" if bloqueadas else "var(--ed-text-muted)"),
    ]

    facultades = bd.scalars(select(Facultad).order_by(Facultad.nombre)).all()
    por_facultad = []
    for facultad in facultades:
        ids = {
            a.id for a in todas
            if a.carrera and a.carrera.facultad_id == facultad.id
        }
        por_facultad.append({
            "nombre": facultad.nombre,
            "asignaturas": len(ids),
            "con_matriz": len(ids & con_matriz),
            "con_guia": len(ids & con_guia),
            "sin_docente": len(ids - con_titular),
        })

    return plantillas.TemplateResponse(request, "vra_avance.html", {
        "usuario": usuario,
        "navegacion": construir(usuario, "/vra/avance"),
        "periodo": periodo,
        "tarjetas": tarjetas,
        "por_facultad": por_facultad,
        "bloqueadas": sorted(bloqueadas, key=lambda a: a.codigo),
    })


def _lista_ambito(texto: str) -> list[str]:
    """Convierte 'GRADO, POSGRADO' en ['GRADO', 'POSGRADO']."""
    return [p.strip().upper() for p in texto.split(",") if p.strip()]


def _lista_numeros(texto: str) -> list[int]:
    numeros = []
    for parte in texto.split(","):
        limpio = parte.strip()
        if limpio.isdigit():
            numeros.append(int(limpio))
    return numeros


@enrutador.get("/reglas", response_class=HTMLResponse)
def reglas(
    request: Request,
    usuario: Usuario = Depends(exigir_roles("ADMIN_VRA")),
    bd: Session = Depends(obtener_sesion),
):
    return _vista_reglas(request, usuario, bd)


def _vista_reglas(request, usuario, bd, error=None, codigo=200):
    from app.modelos import EspecificacionGeneracion

    lista = bd.scalars(
        select(EspecificacionGeneracion)
        .order_by(
            EspecificacionGeneracion.clave,
            EspecificacionGeneracion.version.desc(),
        )
    ).all()

    return plantillas.TemplateResponse(request, "vra_reglas.html", {
        "usuario": usuario,
        "navegacion": construir(usuario, "/vra/reglas"),
        "reglas": lista,
        "error": error,
    }, status_code=codigo)


@enrutador.post("/reglas", dependencies=[Depends(exigir_csrf)])
def crear_regla(
    request: Request,
    clave: str = Form(...),
    titulo: str = Form(...),
    contenido: str = Form(...),
    prioridad: int = Form(100),
    niveles: str = Form(""),
    modalidades: str = Form(""),
    duraciones: str = Form(""),
    tipos: str = Form(""),
    usuario: Usuario = Depends(exigir_roles("ADMIN_VRA")),
    bd: Session = Depends(obtener_sesion),
):
    from app.modelos import EspecificacionGeneracion
    from app.seguridad import auditoria

    clave_limpia = clave.strip().lower().replace(" ", "-")
    if not clave_limpia:
        return _vista_reglas(request, usuario, bd,
                             "La clave no puede estar vacía.", 400)

    # Si la clave ya existe, se crea la version siguiente.
    ultima = bd.scalar(
        select(func.max(EspecificacionGeneracion.version))
        .where(EspecificacionGeneracion.clave == clave_limpia)
    )
    version = (ultima or 0) + 1

    regla = EspecificacionGeneracion(
        clave=clave_limpia,
        version=version,
        titulo=titulo.strip(),
        contenido=contenido.strip(),
        prioridad=prioridad,
        estado="BORRADOR",
        niveles=_lista_ambito(niveles),
        modalidades=_lista_ambito(modalidades),
        duraciones=_lista_numeros(duraciones),
        tipos_asignatura=_lista_ambito(tipos),
        creada_por_id=usuario.id,
    )
    bd.add(regla)
    bd.commit()

    auditoria.registrar(
        bd, "regla.creada", actor_id=usuario.id,
        tipo_entidad="especificacion", id_entidad=f"{clave_limpia}-v{version}",
        detalles={"titulo": titulo.strip(), "prioridad": prioridad},
        request=request,
    )
    return RedirectResponse(url="/vra/reglas", status_code=303)


@enrutador.post("/reglas/{regla_id}/activar", dependencies=[Depends(exigir_csrf)])
def activar_regla(
    request: Request,
    regla_id: str,
    usuario: Usuario = Depends(exigir_roles("ADMIN_VRA")),
    bd: Session = Depends(obtener_sesion),
):
    from datetime import datetime, timezone
    from sqlalchemy import update
    from app.modelos import EspecificacionGeneracion
    from app.seguridad import auditoria

    regla = bd.get(EspecificacionGeneracion, regla_id)
    if regla is None:
        return _vista_reglas(request, usuario, bd, "Regla no encontrada.", 404)

    # Solo una version activa por clave: las anteriores se archivan.
    bd.execute(
        update(EspecificacionGeneracion)
        .where(
            EspecificacionGeneracion.clave == regla.clave,
            EspecificacionGeneracion.estado == "ACTIVA",
        )
        .values(estado="ARCHIVADA")
    )
    regla.estado = "ACTIVA"
    regla.activada_en = datetime.now(timezone.utc)
    bd.commit()

    auditoria.registrar(
        bd, "regla.activada", actor_id=usuario.id,
        tipo_entidad="especificacion",
        id_entidad=f"{regla.clave}-v{regla.version}", request=request,
    )
    return RedirectResponse(url="/vra/reglas", status_code=303)


@enrutador.post("/reglas/{regla_id}/desactivar",
                dependencies=[Depends(exigir_csrf)])
def desactivar_regla(
    request: Request,
    regla_id: str,
    usuario: Usuario = Depends(exigir_roles("ADMIN_VRA")),
    bd: Session = Depends(obtener_sesion),
):
    from app.modelos import EspecificacionGeneracion
    from app.seguridad import auditoria

    regla = bd.get(EspecificacionGeneracion, regla_id)
    if regla is None:
        return _vista_reglas(request, usuario, bd, "Regla no encontrada.", 404)

    regla.estado = "INACTIVA"
    bd.commit()

    auditoria.registrar(
        bd, "regla.desactivada", actor_id=usuario.id,
        tipo_entidad="especificacion",
        id_entidad=f"{regla.clave}-v{regla.version}", request=request,
    )
    return RedirectResponse(url="/vra/reglas", status_code=303)
