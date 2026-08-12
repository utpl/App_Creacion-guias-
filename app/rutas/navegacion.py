"""Construye el menu lateral segun los roles del usuario."""

from app.modelos import Usuario

# (texto, url, roles que lo ven)
ELEMENTOS = [
    ("Inicio",         "/inicio",             None),
    ("Mis asignaturas", "/asignaturas",       {"PROFESOR"}),
    ("Usuarios",       "/admin/usuarios",     {"ADMIN"}),
    ("Sesiones",       "/admin/sesiones",     {"ADMIN"}),
    ("Auditoría",      "/admin/auditoria",    {"ADMIN"}),
]


def construir(usuario: Usuario, ruta_actual: str) -> list[dict]:
    roles = {vinculo.rol.codigo for vinculo in usuario.roles}
    menu = []
    for texto, url, requeridos in ELEMENTOS:
        if requeridos is not None and not roles.intersection(requeridos):
            continue
        menu.append({
            "texto": texto,
            "url": url,
            "activo": ruta_actual.startswith(url),
        })
    return menu
