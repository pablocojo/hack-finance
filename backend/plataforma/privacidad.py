"""Enmascarado de datos personales para auditoría, textos y todo lo que sale a un modelo."""

from __future__ import annotations

import re
from typing import Any

from ..agente.guardarrailes import enmascarar as _enmascarar_patrones

_PARTICULAS = {"de", "del", "la", "las", "los", "el", "y", "da", "di", "van", "von"}


def enmascarar_nombre(nombre: str | None) -> str:
    """«Marcos Ruiz Sanz» -> «Marcos R.». Un solo nombre queda igual; «MARCOS R» -> «Marcos R.»."""
    if not nombre:
        return ""
    partes = [p for p in re.split(r"[\s.]+", nombre.strip()) if p]
    if not partes:
        return ""
    primero = partes[0].capitalize()
    resto = [p for p in partes[1:] if p.lower() not in _PARTICULAS]
    if not resto:
        return primero
    return f"{primero} {resto[0][0].upper()}."


def enmascarar_texto(texto: str) -> str:
    """Oculta IBAN, tarjetas, DNI/NIE, correos y teléfonos (mismos patrones que el kit)."""
    limpio, _ = _enmascarar_patrones(texto)
    return limpio


def enmascarar_datos(valor: Any) -> Any:
    """Aplica `enmascarar_texto` a todas las cadenas de una estructura (para la auditoría)."""
    if isinstance(valor, str):
        return enmascarar_texto(valor)
    if isinstance(valor, dict):
        return {k: enmascarar_datos(v) for k, v in valor.items()}
    if isinstance(valor, (list, tuple)):
        return [enmascarar_datos(v) for v in valor]
    return valor
