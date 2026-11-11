"""Tipos internos de los detectores: lo que ven (`Contexto`) y lo que devuelven (`Hallazgo`)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Callable

from ...plataforma.tipos import InfoComercio, MovimientoEnriquecido, PerfilUsuario


@dataclass(frozen=True)
class Contexto:
    """Solo el pasado: `historial` tiene fecha <= `hoy` (único punto de corte, en `procesar`)."""

    hoy: date
    historial: list[MovimientoEnriquecido]
    nuevos: list[MovimientoEnriquecido]
    series: dict[str, Any]
    lineas_base: dict[str, Any]
    perfil: PerfilUsuario | None
    params: dict[str, Any]                                   # ya ajustados al perfil
    conocimiento: Callable[[str], InfoComercio | None]        # solo lectura de la caché
    pruebas: tuple[dict, ...] = ()
    # Lo aprendido del usuario (curva de amigos): "c:<COMERCIO>" o "t:<tipo>|<franja>" -> p(acompañado). Lo calcula
    # la personalización fuera del motor; None = las reglas fijas de siempre.
    compania: dict[str, float] | None = None
    # El grupo habitual aprendido (A3b), mismos ámbitos que `compania` -> {contraparte: frecuencia con que va}. Lo
    # calcula la personalización fuera del motor; None = las reglas fijas de siempre.
    grupos: dict[str, dict[str, float]] | None = None


@dataclass
class Hallazgo:
    """Un momento en bruto. El razonador le pone id, fecha, explicación y versión."""

    tipo: str
    clave: str                      # estable: el mismo hecho da la misma clave cada día
    movimientos: list[str]
    confianza: float
    datos: dict[str, Any] = field(default_factory=dict)
    impacto_eur: Decimal | None = None
