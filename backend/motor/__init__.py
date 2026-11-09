"""
Motor de momentos. STUB de E1: firmas definitivas de docs/ARQUITECTURA.md §3.2.
Lo sustituye el hilo `motor` (ingeniero-deteccion); las firmas no cambian.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from ..plataforma.tipos import Momento, Movimiento, MovimientoEnriquecido, PerfilUsuario
from . import conocimiento, parametros  # noqa: F401


def procesar(
    usuario_id: str, nuevos: list[Movimiento], hoy: date, perfil: PerfilUsuario | None = None
) -> list[Momento]:
    """Detecta momentos con los movimientos de `nuevos` (todos con fecha <= hoy). Stub: ninguno."""
    return []


def enriquecer(movimientos: list[Movimiento]) -> list[MovimientoEnriquecido]:
    """Pura: normaliza y enriquece. Stub: copia con el comercio en mayúsculas."""
    salida = []
    for m in movimientos:
        base = (m.comercio or m.concepto or "").strip().upper()
        salida.append(MovimientoEnriquecido(**m.model_dump(), comercio_normalizado=base or None))
    return salida


def cargar_historial(usuario_id: str, historial: list[Movimiento], hoy: date) -> None:
    """Al activar: aprende series sin emitir momentos. Stub: no hace nada."""


def exportar_estado(usuario_id: str) -> dict:
    return {}


def importar_estado(usuario_id: str, estado: dict) -> None:
    return None


def reiniciar(usuario_id: str) -> None:
    return None


def registrar_prueba(usuario_id: str, comercio: str, fecha_alta: date, dias: int | None, hoy: date) -> None:
    return None


def cerrar_prueba(
    usuario_id: str,
    comercio: str,
    motivo: Literal["cancelada", "cobrada", "caducada", "baja_guiada"],
    hoy: date,
) -> None:
    return None


def comercios_pendientes(usuario_id: str) -> list[str]:
    return []
