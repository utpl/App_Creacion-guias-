"""Panel de administracion. Solo rol ADMIN."""

import json
import math

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session
from app.modelos import AsignacionDocente, Asignatura, PeriodoAcademico
from app.base_datos import obtener_sesion
from app.configuracion import configuracion
from app.modelos import Rol, Usuario, UsuarioRol
from app.rutas.navegacion import construir
from app.seguridad.csrf import exigir_csrf
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
# Asignaturas del periodo activo que quedaron sin titular.
   

    periodo_activo = bd.scalar(
        select(PeriodoAcademico).where(PeriodoAcademico.activo.is_(True))
    )
    sin_titular = []
    if periodo_activo:
        con_titular = select(AsignacionDocente.asignatura_id).where(
            AsignacionDocente.periodo_id == periodo_activo.id,
            AsignacionDocente.rol_en_asignatura == "titular",
        )
        sin_titular = bd.scalars(
            select(Asignatura)
            .where(Asignatura.id.not_in(con_titular))
            .order_by(Asignatura.codigo)
        ).all()
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
        "sin_titular": sin_titular,
        "periodo_activo": periodo_activo,
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

@enrutador.get("/usuarios/importar", response_class=HTMLResponse)
def mostrar_importar(
    request: Request,
    usuario: Usuario = Depends(exigir_roles("ADMIN")),
):
    return plantillas.TemplateResponse(request, "admin_importar.html", {
        "usuario": usuario,
        "navegacion": construir(usuario, "/admin/usuarios"),
        "filas": None,
        "error_global": None,
        "resumen": None,
    })


@enrutador.post("/usuarios/importar", dependencies=[Depends(exigir_csrf)])
async def analizar_importacion(
    request: Request,
    archivo: UploadFile = File(...),
    usuario: Usuario = Depends(exigir_roles("ADMIN")),
    bd: Session = Depends(obtener_sesion),
):
    from app.servicios.importador import leer_archivo, validar_usuarios

    base: dict = {
        "usuario": usuario,
        "navegacion": construir(usuario, "/admin/usuarios"),
        "filas": None,
        "error_global": None,
        "resumen": None,
    }

    try:
        contenido = await archivo.read()
        crudas = leer_archivo(archivo.filename or "", contenido)
    except ValueError as error:
        base["error_global"] = str(error)
        return plantillas.TemplateResponse(request, "admin_importar.html", base)
    except Exception:
        base["error_global"] = "No fue posible leer el archivo."
        return plantillas.TemplateResponse(request, "admin_importar.html", base)

    roles_validos = {r.codigo for r in bd.scalars(select(Rol)).all()}
    correos = {c for c in bd.scalars(select(Usuario.correo)).all()}

    resultado = validar_usuarios(crudas, roles_validos, correos)

    if resultado.error_global:
        base["error_global"] = resultado.error_global
        return plantillas.TemplateResponse(request, "admin_importar.html", base)

    payload = [
        {
            "correo": f.datos["correo"],
            "nombres": f.datos["nombres"],
            "apellidos": f.datos["apellidos"],
            "roles": f.datos["roles_procesados"],
        }
        for f in resultado.validas
    ]

    base.update({
        "filas": resultado.filas,
        "validas": len(resultado.validas),
        "invalidas": len(resultado.invalidas),
        "datos_serializados": json.dumps(payload),
    })
    return plantillas.TemplateResponse(request, "admin_importar.html", base)


@enrutador.post("/usuarios/importar/confirmar", dependencies=[Depends(exigir_csrf)])
def confirmar_importacion(
    request: Request,
    datos: str = Form(...),
    usuario: Usuario = Depends(exigir_roles("ADMIN")),
    bd: Session = Depends(obtener_sesion),
):
    from app.modelos import UsuarioRol
    from app.seguridad import auditoria, correo as servicio_correo, recuperacion

    base: dict = {
        "usuario": usuario,
        "navegacion": construir(usuario, "/admin/usuarios"),
        "filas": None,
        "error_global": None,
        "resumen": None,
    }

    try:
        registros = json.loads(datos)
    except Exception:
        base["error_global"] = "Los datos de la importación no son válidos."
        return plantillas.TemplateResponse(request, "admin_importar.html", base)

    mapa_roles = {r.codigo: r.id for r in bd.scalars(select(Rol)).all()}
    existentes = {c for c in bd.scalars(select(Usuario.correo)).all()}

    creados = 0
    omitidos = 0

    for registro in registros:
        correo_nuevo = registro["correo"].strip().lower()

        # Se revalida: entre el analisis y la confirmacion pudo cambiar algo.
        if correo_nuevo in existentes or not correo_nuevo.endswith("@utpl.edu.ec"):
            omitidos += 1
            continue

        nuevo = Usuario(
            correo=correo_nuevo,
            nombres=registro["nombres"].strip(),
            apellidos=registro["apellidos"].strip(),
            hash_password=None,
            requiere_cambio_password=True,
            origen="NOMINA",
        )
        bd.add(nuevo)
        bd.flush()

        for codigo in registro["roles"].split(","):
            if codigo in mapa_roles:
                bd.add(UsuarioRol(usuario_id=nuevo.id, rol_id=mapa_roles[codigo]))

        existentes.add(correo_nuevo)
        creados += 1

    bd.commit()

    # Enlace de activacion para cada cuenta nueva.
    enviados = 0
    for registro in registros:
        token = recuperacion.solicitar(bd, registro["correo"])
        if token:
            destinatario = bd.scalar(
                select(Usuario).where(Usuario.correo == registro["correo"].lower())
            )
            if destinatario:
                url = f"{configuracion.url_publica}/restablecer/{token}"
                asunto, cuerpo = servicio_correo.enlace_recuperacion(
                    url, destinatario.nombres
                )
                servicio_correo.enviar(destinatario.correo, asunto, cuerpo)
                enviados += 1

    auditoria.registrar(
        bd, "usuarios.importados", actor_id=usuario.id,
        detalles={"creados": creados, "omitidos": omitidos, "correos": enviados},
        request=request,
    )

    base["resumen"] = (
        f"{creados} usuario(s) creado(s), {omitidos} omitido(s). "
        f"Se enviaron {enviados} enlace(s) de activación."
    )
    return plantillas.TemplateResponse(request, "admin_importar.html", base)
