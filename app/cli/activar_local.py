"""Fija una contrasena directamente. SOLO para desarrollo.

En produccion la activacion se hace por enlace enviado al correo.
Este comando se niega a ejecutarse fuera de desarrollo.
"""

import sys

from app.base_datos import FabricaSesion
from app.configuracion import configuracion
from app.modelos import Usuario
from app.seguridad.passwords import generar_hash, validar_fortaleza


def activar(correo: str, password: str) -> None:
    if configuracion.entorno != "desarrollo":
        sys.exit("Error: este comando solo funciona en entorno de desarrollo.")

    problemas = validar_fortaleza(password)
    if problemas:
        sys.exit("Error: " + " ".join(problemas))

    with FabricaSesion() as bd:
        usuario = bd.query(Usuario).filter_by(correo=correo.strip().lower()).one_or_none()
        if usuario is None:
            sys.exit(f"Error: no existe el usuario {correo}.")

        usuario.hash_password = generar_hash(password)
        usuario.requiere_cambio_password = False
        usuario.intentos_fallidos = 0
        usuario.bloqueado_hasta = None
        bd.commit()
        print(f"Contrasena establecida para {usuario.correo}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit('Uso: python -m app.cli.activar_local "correo" "contrasena"')
    activar(sys.argv[1], sys.argv[2])
