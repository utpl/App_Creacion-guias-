from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.configuracion import configuracion

motor = create_engine(
    str(configuracion.url_base_datos),
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    echo=configuracion.entorno == "desarrollo",
)

FabricaSesion = sessionmaker(bind=motor, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    """Clase padre de todos los modelos."""


def obtener_sesion() -> Generator[Session, None, None]:
    """Entrega una sesion y garantiza que se cierre al terminar."""
    sesion = FabricaSesion()
    try:
        yield sesion
    finally:
        sesion.close()
