"""Hash y verificacion de contrasenas con Argon2id."""

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

# Parametros conforme a la recomendacion vigente de OWASP.
_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=65536,   # 64 MB
    parallelism=4,
    hash_len=32,
    salt_len=16,
)

# Hash de referencia. Se verifica contra el cuando el usuario no existe,
# para que el tiempo de respuesta sea el mismo y no se pueda enumerar cuentas.
_HASH_SENUELO = _hasher.hash("contrasena-inexistente-para-comparacion")

LONGITUD_MINIMA = 12


def generar_hash(password: str) -> str:
    return _hasher.hash(password)


def verificar(password: str, hash_almacenado: str | None) -> bool:
    """Verifica la contrasena. Consume el mismo tiempo exista o no el usuario."""
    objetivo = hash_almacenado or _HASH_SENUELO
    try:
        _hasher.verify(objetivo, password)
    except (VerifyMismatchError, InvalidHashError):
        return False
    return hash_almacenado is not None


def necesita_rehash(hash_almacenado: str) -> bool:
    """True si el hash se creo con parametros antiguos."""
    return _hasher.check_needs_rehash(hash_almacenado)


def validar_fortaleza(password: str) -> list[str]:
    """Devuelve la lista de problemas. Vacia significa que es aceptable."""
    problemas: list[str] = []
    if len(password) < LONGITUD_MINIMA:
        problemas.append(
            f"Debe tener al menos {LONGITUD_MINIMA} caracteres."
        )
    if password.lower() in {
        "contrasena123", "password1234", "utpl20262026",
        "administrador", "123456789012",
    }:
        problemas.append("Es una contrasena demasiado comun.")
    return problemas
