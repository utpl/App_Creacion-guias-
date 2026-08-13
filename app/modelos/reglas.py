"""Reglas de generacion, documentos institucionales e indicadores.

Las tres comparten el mismo patron de gobernanza:
  - Se versionan, no se sobrescriben
  - Tienen estado: BORRADOR, ACTIVA, INACTIVA, ARCHIVADA
  - Se filtran por ambito al momento de generar
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    ARRAY, Boolean, DateTime, ForeignKey, Integer, Numeric,
    String, Text, UniqueConstraint, func
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.base_datos import Base

ESTADOS = ("BORRADOR", "ACTIVA", "INACTIVA", "ARCHIVADA")
ETAPAS = ("PAR", "CALIDAD", "EDITORIAL")


class EspecificacionGeneracion(Base):
    """Una regla que se inyecta en el prompt de generacion."""

    __tablename__ = "especificacion_generacion"
    __table_args__ = (UniqueConstraint("clave", "version"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    clave: Mapped[str] = mapped_column(String(60), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)

    titulo: Mapped[str] = mapped_column(String(200))
    contenido: Mapped[str] = mapped_column(Text)

    estado: Mapped[str] = mapped_column(String(20), default="BORRADOR", index=True)
    prioridad: Mapped[int] = mapped_column(Integer, default=100)

    # Ambito. Vacio significa "aplica a todo".
    niveles: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    modalidades: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    duraciones: Mapped[list[int]] = mapped_column(ARRAY(Integer), default=list)
    tipos_asignatura: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)

    creada_por_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("usuario.id"), default=None
    )
    creada_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    activada_en: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )


class DocumentoConocimiento(Base):
    """Documento institucional que orienta la generacion.

    Si no hay ninguno activo para una clave, se usa el archivo
    de respaldo del repositorio.
    """

    __tablename__ = "documento_conocimiento"
    __table_args__ = (UniqueConstraint("clave", "version"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    clave: Mapped[str] = mapped_column(String(60), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)

    titulo: Mapped[str] = mapped_column(String(200))
    contenido: Mapped[str] = mapped_column(Text)
    nombre_archivo: Mapped[str | None] = mapped_column(String(255), default=None)

    estado: Mapped[str] = mapped_column(String(20), default="BORRADOR", index=True)
    prioridad: Mapped[int] = mapped_column(Integer, default=100)

    aplica_a_todo: Mapped[bool] = mapped_column(Boolean, default=True)
    niveles: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    modalidades: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    duraciones: Mapped[list[int]] = mapped_column(ARRAY(Integer), default=list)
    tipos_asignatura: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)

    creado_por_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("usuario.id"), default=None
    )
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    activado_en: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )


class VersionIndicadores(Base):
    """Un catalogo completo de indicadores. Se versiona entero."""

    __tablename__ = "version_indicadores"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    version: Mapped[int] = mapped_column(Integer, unique=True)
    titulo: Mapped[str] = mapped_column(String(200))
    estado: Mapped[str] = mapped_column(String(20), default="BORRADOR", index=True)

    creada_por_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("usuario.id"), default=None
    )
    creada_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    activada_en: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )

    indicadores: Mapped[list["Indicador"]] = relationship(
        back_populates="version_obj", cascade="all, delete-orphan"
    )


class Indicador(Base):
    __tablename__ = "indicador"
    __table_args__ = (UniqueConstraint("version_id", "codigo"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("version_indicadores.id"), index=True
    )

    codigo: Mapped[str] = mapped_column(String(20))
    nombre: Mapped[str] = mapped_column(String(300), default="")
    descripcion: Mapped[str] = mapped_column(Text)

    etapa: Mapped[str] = mapped_column(String(20), default="PAR")
    peso: Mapped[float] = mapped_column(Numeric(8, 4), default=0)

    obligatorio: Mapped[bool] = mapped_column(Boolean, default=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    orden: Mapped[int] = mapped_column(Integer, default=0)

    version_obj: Mapped["VersionIndicadores"] = relationship(
        back_populates="indicadores"
    )
