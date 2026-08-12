"""Crea el primer ADMIN. Falla si ya existe uno.

No fija contrasena: la cuenta nace con requiere_cambio_password.
En produccion se enviara enlace de activacion por correo.
"""

import sys

from app.base_datos import FabricaSesion
from app.modelos import Rol, Usuario, UsuarioRol


def crear(correo: str, nombres: str, apellidos: str) -> None:
    correo = correo.strip().lower()

    with FabricaSesion() as bd:
        rol_admin = bd.query(Rol).filter_by(codigo="ADMIN").one_or_none()
        if rol_admin is None:
            sys.exit("Error: ejecute primero 'python -m app.cli.sembrar_roles'.")

        ya_existe = (
            bd.query(UsuarioRol)
            .filter_by(rol_id=rol_admin.id)
            .join(Usuario)
            .filter(Usuario.estado == "ACTIVO")
            .first()
        )
        if ya_existe:
            sys.exit("Error: ya existe un ADMIN activo. Este comando no lo reemplaza.")

        if bd.query(Usuario).filter_by(correo=correo).first():
            sys.exit(f"Error: el correo {correo} ya esta registrado.")

        usuario = Usuario(
            correo=correo,
            nombres=nombres,
            apellidos=apellidos,
            hash_password=None,
            requiere_cambio_password=True,
            origen="NOMINA",
        )
        bd.add(usuario)
        bd.commit()

        bd.add(UsuarioRol(usuario_id=usuario.id, rol_id=rol_admin.id))
        bd.commit()

        print(f"ADMIN creado: {correo}")
        print("La cuenta no tiene contrasena. Debe activarse por enlace.")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit('Uso: python -m app.cli.crear_admin "correo" "Nombres" "Apellidos"')
    crear(sys.argv[1], sys.argv[2], sys.argv[3])
