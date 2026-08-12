import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.base_datos import Base
from typing import ClassVar

class Facultad(Base):
    __tablename__ = "facultad"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    nombre: Mapped[str] = mapped_column(String(200), unique=True, index=True)

    carreras: Mapped[list["Carrera"]] = relationship(back_populates="facultad")


class Carrera(Base):
    __tablename__ = "carrera"
    __table_args__ = (UniqueConstraint("facultad_id", "nombre"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    facultad_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("facultad.id"))
    nombre: Mapped[str] = mapped_column(String(200), index=True)
    departamento: Mapped[str | None] = mapped_column(String(200), default=None)

    # Dimensiones reales de ambito para el filtrado de reglas.
    nivel: Mapped[str] = mapped_column(String(30), default="GRADO")
    modalidad: Mapped[str] = mapped_column(String(30), default="EN_LINEA")

    facultad: Mapped["Facultad"] = relationship(back_populates="carreras")


class Asignatura(Base):
    __tablename__ = "asignatura"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    codigo: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    nombre: Mapped[str] = mapped_column(String(300))
    carrera_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("carrera.id"))

    creditos: Mapped[int | None] = mapped_column(Integer, default=None)
    ciclo: Mapped[str | None] = mapped_column(String(20), default=None)
    campo_formacion: Mapped[str | None] = mapped_column(String(120), default=None)
    url_canvas: Mapped[str | None] = mapped_column(String(500), default=None)
    # Horas academicas. Se usaran en el metacurso.
    horas_texto: Mapped[str | None] = mapped_column(String(200), default=None)
    horas_total: Mapped[int | None] = mapped_column(Integer, default=None)
    horas_acd: Mapped[int | None] = mapped_column(Integer, default=None)
    horas_ape: Mapped[int | None] = mapped_column(Integer, default=None)
    horas_aa: Mapped[int | None] = mapped_column(Integer, default=None)

    tipo_plantilla: Mapped[str | None] = mapped_column(String(60), default=None)
    propia_de_carrera: Mapped[str | None] = mapped_column(String(20), default=None)
    carreras_oferta: Mapped[int | None] = mapped_column(Integer, default=None)
    carrera_origen: Mapped[str | None] = mapped_column(String(200), default=None)

    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    carrera: Mapped["Carrera"] = relationship()


class PeriodoAcademico(Base):
    __tablename__ = "periodo_academico"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    nombre: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class AsignacionDocente(Base):
    __tablename__ = "asignacion_docente"
    __table_args__ = (
        UniqueConstraint("docente_id", "asignatura_id", "periodo_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    docente_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("usuario.id"), index=True
    )
    asignatura_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("asignatura.id"), index=True
    )
    periodo_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("periodo_academico.id"), index=True
    )

    # titular = autor original; colaborador = reestructurador
    rol_en_asignatura: Mapped[str] = mapped_column(String(20), default="titular")

    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    asignatura: Mapped["Asignatura"] = relationship()
    periodo: Mapped["PeriodoAcademico"] = relationship()

    # Se rellena en tiempo de ejecucion para la vista del docente.
    # No es columna y no se persiste.
    companeros: ClassVar[list[str]]