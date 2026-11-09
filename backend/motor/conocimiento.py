"""Conocimiento de comercios. STUB de E1 (firmas de ARQUITECTURA §3.2)."""

from __future__ import annotations

from ..plataforma.tipos import InfoComercio


def info_en_cache(nombre: str) -> InfoComercio | None:
    """Sin red: catálogo + _cache/comercios_web.json. Stub: desconocido."""
    return None


def info_comercio(nombre: str) -> InfoComercio | None:
    """Caché y, con BUSQUEDA_WEB=on, búsqueda web (opcional). Stub: desconocido."""
    return None


def guardar(info: InfoComercio) -> None:
    """Solo en datos_usuario/_cache/comercios_web.json. Stub: no hace nada."""
    return None
