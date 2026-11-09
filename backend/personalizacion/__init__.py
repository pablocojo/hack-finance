"""
Personalización. STUB de E1: firmas definitivas de docs/ARQUITECTURA.md §3.2.
Lo sustituye el hilo `personalizacion`; las firmas no cambian.
"""

from __future__ import annotations

from datetime import date, datetime

from ..plataforma.tipos import (
    Decision,
    Feedback,
    ModeloUsuario,
    Movimiento,
    MovimientoEnriquecido,
    PerfilUsuario,
    Propuesta,
    ResultadoAccion,
)
from . import edicion  # noqa: F401

POLITICA = "beta-jerarquica-v2"


def nuevo_modelo(usuario_id: str) -> ModeloUsuario:
    return ModeloUsuario(usuario_id=usuario_id)


def perfilar(
    historial: list[MovimientoEnriquecido], hoy: date, perfil_anterior: PerfilUsuario | None
) -> PerfilUsuario | None:
    """Pura. Con menos de 28 días de historial devuelve None (sin perfil). Stub: None."""
    return None


def ordenar_acciones(propuesta: Propuesta, modelo: ModeloUsuario) -> Propuesta:
    """Pura; solo reordena las acciones. Stub: sin cambios."""
    return propuesta


def decidir(propuesta: Propuesta, modelo: ModeloUsuario, ahora: datetime) -> Decision:
    """Stub: avisa siempre con un motivo legible."""
    return Decision(
        propuesta_id=propuesta.id,
        accion="notificar_ahora",
        puntuacion=1.0,
        probabilidad_util=0.5,
        motivos=["Política de ejemplo (stub): avisa siempre."],
        politica=POLITICA,
    )


def aprender(feedback: Feedback, modelo: ModeloUsuario) -> ModeloUsuario:
    """Pura: no guarda. Stub: el mismo modelo."""
    return modelo


def registrar_decision(modelo: ModeloUsuario, propuesta: Propuesta, decision: Decision) -> ModeloUsuario:
    return modelo


def registrar_accion(modelo: ModeloUsuario, propuesta: Propuesta, resultado: ResultadoAccion) -> ModeloUsuario:
    """Suma a `elecciones`. Stub: sin cambios."""
    return modelo


def observar(modelo: ModeloUsuario, movimientos: list[Movimiento], hoy: date) -> ModeloUsuario:
    return modelo


def memoria_para_agente(modelo: ModeloUsuario) -> str:
    """Solo hechos operativos; nunca ingresos, importes por categoría ni resumen_vida."""
    return ""
