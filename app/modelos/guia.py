import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.base_datos import Base


class MatrizPlanificacion(Base):
    """La sube el docente. Pertenece a la asignatura y el periodo,
    no a la guia ni al docente: dos docentes de la misma asignatura
    parten de la misma matriz."""

    __tablename__ = "matriz_planificacion"
    __table_args__ = (UniqueConstraint("asignatura_id", "periodo_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    asignatura_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("asignatura.id"), index=True
    )
    periodo_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("periodo_academico.id"), index=True
    )

    semanas_totales: Mapped[int] = mapped_column(Integer)
    nombre_archivo: Mapped[str] = mapped_column(String(255))

    subida_por_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuario.id"))
    subida_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    filas: Mapped[list["FilaMatriz"]] = relationship(
        back_populates="matriz", cascade="all, delete-orphan"
    )


class FilaMatriz(Base):
    """Una fila por semana. La columna unidad_contenido es la unica
    fuente autorizada para crear encabezados tematicos."""

    __tablename__ = "fila_matriz"
    __table_args__ = (UniqueConstraint("matriz_id", "semana"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    matriz_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("matriz_planificacion.id"), index=True
    )

    semana: Mapped[int] = mapped_column(Integer)
    resultado_aprendizaje: Mapped[str | None] = mapped_column(Text, default=None)
    unidad_contenido: Mapped[str] = mapped_column(Text)
    metodologia: Mapped[str | None] = mapped_column(Text, default=None)
    actividades: Mapped[str | None] = mapped_column(Text, default=None)

    matriz: Mapped["MatrizPlanificacion"] = relationship(back_populates="filas")


class Guia(Base):
    """Una guia por asignatura y periodo. Todos los docentes vinculados
    trabajan sobre la misma."""

    __tablename__ = "guia"
    __table_args__ = (UniqueConstraint("asignatura_id", "periodo_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    asignatura_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("asignatura.id"), index=True
    )
    periodo_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("periodo_academico.id"), index=True
    )
    matriz_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("matriz_planificacion.id"), default=None
    )

    semanas_totales: Mapped[int] = mapped_column(Integer)
    estado: Mapped[str] = mapped_column(String(30), default="EN_EDICION", index=True)

    creada_por_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuario.id"))
    creada_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    semanas: Mapped[list["SemanaGuia"]] = relationship(
        back_populates="guia", cascade="all, delete-orphan"
    )


class SemanaGuia(Base):
    __tablename__ = "semana_guia"
    __table_args__ = (UniqueConstraint("guia_id", "numero"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    guia_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("guia.id"), index=True)

    numero: Mapped[int] = mapped_column(Integer)
    estado: Mapped[str] = mapped_column(String(30), default="PENDIENTE")

    bloques: Mapped[dict | None] = mapped_column(JSONB, default=None)

    # Cuota de generacion: tres intentos por semana.
    intentos_usados: Mapped[int] = mapped_column(Integer, default=0)
    intentos_concedidos: Mapped[int] = mapped_column(Integer, default=3)

    aprobada_por_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("usuario.id"), default=None
    )
    aprobada_en: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )

    actualizada_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    guia: Mapped["Guia"] = relationship(back_populates="semanas")
