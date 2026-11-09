"""
Llamada de voz y chat con ElevenLabs. STUB de E1: firma de docs/ARQUITECTURA.md §3.2.
Lo sustituye el hilo `voz`. Las claves de ElevenLabs solo viven en el backend.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from ..plataforma.tipos import SesionVoz


def sesion(propuesta_id: str, usuario_id: str, modo_preferido: str) -> SesionVoz:
    """modo: voz | texto_el | texto_kit | grabado. Stub: siempre texto_kit."""
    return SesionVoz(
        modo="texto_kit",
        variables={"propuesta_id": propuesta_id},
        token_sesion="stub-sesion",
        caduca=datetime.now() + timedelta(minutes=30),
    )
