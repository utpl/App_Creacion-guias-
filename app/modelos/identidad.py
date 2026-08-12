import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.base_datos import Base


class Usuario(Base):
    __tablename__ = "usuario"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    correo: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    nombres: Mapped[str] = mapped_column(String(150))
    apellidos: Mapped[str] = mapped_column(String(150))

    hash_password: Mapped[str | None] = mapped_column(String(255), default=None)
    requiere_cambio_password: Mapped[bool] = mapped_column(Boolean, default=True)

    estado: Mapped[str] = mapped_column(String(20), default="ACTIVO")
    origen: Mapped[str] = mapped_column(String(20), default="NOMINA")
    vigencia_hasta: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )

    intentos_fallidos: Mapped[int] = mapped_column(default=0)
    bloqueado_hasta: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    ultimo_acceso: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )

    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    roles: Mapped[list["UsuarioRol"]] = relationship(back_populates="usuario")

    @property
    def nombre_completo(self) -> str:
        return f"{self.nombres} {self.apellidos}"


class Rol(Base):
    __tablename__ = "rol"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    codigo: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    nombre: Mapped[str] = mapped_column(String(120))
    descripcion: Mapped[str] = mapped_column(String(255), default="")
    es_sistema: Mapped[bool] = mapped_column(Boolean, default=True)


class UsuarioRol(Base):
    __tablename__ = "usuario_rol"
    __table_args__ = (UniqueConstraint("usuario_id", "rol_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    usuario_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuario.id"))
    rol_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("rol.id"))
    asignado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    usuario: Mapped["Usuario"] = relationship(back_populates="roles")
    rol: Mapped["Rol"] = relationship()
