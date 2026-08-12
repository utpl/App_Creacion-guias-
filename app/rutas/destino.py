"""Decide a donde entra cada usuario segun su rol."""

from app.modelos import Usuario

# El orden importa: si alguien tiene varios roles, gana el primero.
DESTINOS = [
    ("ADMIN",         "/admin/usuarios"),
    ("ADMIN_VRA",     "/inicio"),
    ("ADMIN_EDILOJA", "/inicio"),
    ("OPERATIVO",     "/inicio"),
    ("QA",            "/inicio"),
    ("PROFESOR",      "/asignaturas"),
]


def para(usuario: Usuario) -> str:
    roles = {vinculo.rol.codigo for vinculo in usuario.roles}
    for codigo, url in DESTINOS:
        if codigo in roles:
            return url
    return "/inicio"
