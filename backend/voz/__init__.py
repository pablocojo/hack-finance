"""
Llamada de voz y chat con ElevenLabs (tareas V1 y V2). Firma de docs/ARQUITECTURA.md §3.2.
Las claves de ElevenLabs solo viven en el backend: el navegador recibe un token de conversación o
una URL firmada, más un `token_sesion` propio que liga la llamada a un usuario y una propuesta.
"""

from __future__ import annotations

from .. import casos
from ..plataforma import almacenamiento as alm
from ..plataforma import orquestador
from ..plataforma.tipos import ModeloUsuario, Propuesta, SesionVoz
from . import contexto, elevenlabs, sesiones


def sesion(propuesta_id: str | None, usuario_id: str, modo_preferido: str, caso_id: str | None = None) -> SesionVoz:
    """modo: voz | texto_el | texto_kit | grabado. 404 si la propuesta no es de ese usuario. Sin `propuesta_id`, sesión
    general (conversación sin aviso): ligada solo al usuario, sin acciones ofrecidas, con el mismo token y TTL. Con
    `caso_id` (solo sin propuesta, «Otra respuesta» de una pregunta del Resumen) la conversación se enfoca en ese caso
    del usuario; un id que no es suyo se ignora."""
    if propuesta_id:
        detalle = orquestador.propuesta_detalle(usuario_id, propuesta_id)
        propuesta = Propuesta.model_validate(detalle["propuesta"])
        modelo = alm.cargar(usuario_id, "modelo", tipo=ModeloUsuario)
        variables = contexto.variables(propuesta, modelo, usuario_id, casos.cargar(usuario_id))
    else:
        orquestador.estado_usuario(usuario_id)       # 404 si el usuario no existe
        modelo = alm.cargar(usuario_id, "modelo", tipo=ModeloUsuario)
        caso = next((c for c in casos.cargar(usuario_id) if c.id == caso_id), None) if caso_id else None
        variables = contexto.variables_generales(usuario_id, modelo, caso)
    modo, token, url = elevenlabs.abrir(modo_preferido)
    registro = sesiones.crear(usuario_id, propuesta_id or "", modo, variables)
    return SesionVoz(modo=modo, token=token, signed_url=url, variables=variables,
                     token_sesion=registro.token_sesion, caduca=registro.caduca)
