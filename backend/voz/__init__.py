"""
Llamada de voz y chat con ElevenLabs (tareas V1 y V2). Firma de docs/ARQUITECTURA.md §3.2.
Las claves de ElevenLabs solo viven en el backend: el navegador recibe un token de conversación o
una URL firmada, más un `token_sesion` propio que liga la llamada a un usuario y una propuesta.
"""

from __future__ import annotations

from ..plataforma import almacenamiento as alm
from ..plataforma import orquestador
from ..plataforma.tipos import ModeloUsuario, Propuesta, SesionVoz
from . import contexto, elevenlabs, sesiones


def sesion(propuesta_id: str, usuario_id: str, modo_preferido: str) -> SesionVoz:
    """modo: voz | texto_el | texto_kit | grabado. 404 si la propuesta no es de ese usuario."""
    detalle = orquestador.propuesta_detalle(usuario_id, propuesta_id)
    propuesta = Propuesta.model_validate(detalle["propuesta"])
    modelo = alm.cargar(usuario_id, "modelo", tipo=ModeloUsuario)
    variables = contexto.variables(propuesta, modelo, usuario_id)
    modo, token, url = elevenlabs.abrir(modo_preferido)
    registro = sesiones.crear(usuario_id, propuesta_id, modo, variables)
    return SesionVoz(modo=modo, token=token, signed_url=url, variables=variables,
                     token_sesion=registro.token_sesion, caduca=registro.caduca)
