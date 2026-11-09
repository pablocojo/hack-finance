"""«Lo que he aprendido de ti»: ver, editar y borrar el perfil. STUB de E1."""

from __future__ import annotations

from typing import Any

from ..plataforma.tipos import FrasePerfil, ModeloUsuario, PerfilUsuario


def frases_perfil(perfil: PerfilUsuario | None) -> list[FrasePerfil]:
    return []


def editar_perfil(modelo: ModeloUsuario, campo: str, valor: Any) -> ModeloUsuario:
    """Va a `campos_fijados`. Stub: sin cambios."""
    return modelo


def borrar_campo_perfil(modelo: ModeloUsuario, campo: str) -> ModeloUsuario:
    """Valor por defecto y `campos_borrados`. Stub: sin cambios."""
    return modelo


def borrar_perfil(modelo: ModeloUsuario) -> ModeloUsuario:
    """`perfil = None` y `usar_perfil = False`."""
    modelo = modelo.model_copy(deep=True)
    modelo.perfil = None
    modelo.preferencias.usar_perfil = False
    return modelo
