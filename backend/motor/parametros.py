"""Umbrales personales del motor. STUB de E1: `ajustar` devuelve los parámetros sin cambios."""

from __future__ import annotations

from typing import TypeVar

from ..plataforma.tipos import PerfilUsuario

Parametros = TypeVar("Parametros")


def ajustar(params: Parametros, perfil: PerfilUsuario | None) -> Parametros:
    """Única función de umbrales personales. Sin perfil, mismos valores por defecto."""
    return params
