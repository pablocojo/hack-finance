"""
Registro de detectores (motor.md §2.4). Cada uno: `detectar(ctx: Contexto) -> list[Hallazgo]`.
Tipo de momento nuevo = un archivo aquí con `@registrar("<tipo>", version=n)` (skill `/detector`).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .base import Contexto, Hallazgo


@dataclass(frozen=True)
class Detector:
    tipo: str
    version: int
    detectar: Callable[[Contexto], list[Hallazgo]]


REGISTRO: dict[str, Detector] = {}


def registrar(tipo: str, version: int = 1):
    def decorar(funcion: Callable[[Contexto], list[Hallazgo]]):
        REGISTRO[tipo] = Detector(tipo=tipo, version=version, detectar=funcion)
        return funcion

    return decorar


def version(tipo: str) -> int:
    return REGISTRO[tipo].version if tipo in REGISTRO else 1


from . import cargo_duplicado, gasto_compartido, prueba_gratuita, subida_recibo  # noqa: E402,F401  (se registran al importar)
