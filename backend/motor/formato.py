"""Formato en español de cifras y nombres (sin dependencias del motor: lo usan razonador y detectores)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any


def decimal(valor: Any) -> Decimal:
    return valor if isinstance(valor, Decimal) else Decimal(str(valor))


def eur(valor: Any) -> str:
    """`Decimal("1234.5")` -> «1.234,50 €»."""
    texto = f"{decimal(valor):,.2f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".") + " €"


def nombre_persona(clave: str) -> str:
    """Clave de contraparte -> nombre legible: «DANIEL P» -> «Daniel P.»."""
    palabras = [p.capitalize() for p in clave.split()]
    if len(palabras) > 1 and len(palabras[-1]) == 1:
        palabras[-1] += "."
    return " ".join(palabras)
