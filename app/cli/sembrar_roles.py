"""Crea los seis roles del sistema. Es idempotente: se puede repetir."""

from app.base_datos import FabricaSesion
from app.modelos import Rol

ROLES = [
    ("ADMIN", "Administrador de plataforma",
     "Cuentas, roles, integraciones y monitoreo. No toca contenido academico."),
    ("ADMIN_VRA", "Administrador del Vicerrectorado Academico",
     "Reglas institucionales, catalogo academico e indicadores."),
    ("ADMIN_EDILOJA", "Administrador de EdiLoja",
     "Plantillas, vocabulario visual y publicacion en Canvas."),
    ("QA", "Aseguramiento de calidad",
     "Revision de guias contra los indicadores de su etapa."),
    ("OPERATIVO", "Operacion academica",
     "Nominas, asignaciones, desbloqueos y reprocesos."),
    ("PROFESOR", "Docente",
     "Genera, edita y aprueba sus propias guias."),
]


def sembrar() -> None:
    with FabricaSesion() as sesion:
        for codigo, nombre, descripcion in ROLES:
            existente = sesion.query(Rol).filter_by(codigo=codigo).one_or_none()
            if existente:
                print(f"  ya existe: {codigo}")
                continue
            sesion.add(Rol(codigo=codigo, nombre=nombre,
                           descripcion=descripcion, es_sistema=True))
            print(f"  creado:    {codigo}")
        sesion.commit()


if __name__ == "__main__":
    sembrar()
