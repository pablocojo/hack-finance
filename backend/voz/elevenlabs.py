"""
ElevenLabs desde el servidor (la clave nunca sale de aquí). Documentación:
- Token de conversación (WebRTC): https://elevenlabs.io/docs/api-reference/conversations/get-webrtc-token
- URL firmada (WebSocket):        https://elevenlabs.io/docs/api-reference/conversations/get-signed-url
El agente es privado: sin token o URL firmada el navegador no conecta.
"""

from __future__ import annotations

import httpx

from .. import config

BASE = "https://api.elevenlabs.io"
TIEMPO_MAX = 8.0
MODOS = ("voz", "texto_el", "texto_kit", "grabado")
_TRANSPORTE: httpx.BaseTransport | None = None  # los tests inyectan un falso


class ErrorElevenLabs(RuntimeError):
    """Sin configuración, sin red o respuesta no válida. El mensaje nunca contiene la clave."""


def configurado() -> bool:
    a = config.ajustes()
    return bool(a.elevenlabs_api_key and a.elevenlabs_agent_id)


def _pedir(ruta: str, campo: str) -> str:
    a = config.ajustes()
    if not (a.elevenlabs_api_key and a.elevenlabs_agent_id):
        raise ErrorElevenLabs("ElevenLabs no está configurado.")
    try:
        with httpx.Client(base_url=BASE, timeout=TIEMPO_MAX, transport=_TRANSPORTE) as cliente:
            r = cliente.get(ruta, params={"agent_id": a.elevenlabs_agent_id},
                            headers={"xi-api-key": a.elevenlabs_api_key})
    except httpx.HTTPError as error:
        raise ErrorElevenLabs(f"Sin conexión con ElevenLabs ({type(error).__name__}).") from None
    if r.status_code != 200:
        raise ErrorElevenLabs(f"ElevenLabs respondió {r.status_code}.")
    try:
        valor = r.json().get(campo)
    except ValueError:
        valor = None
    if not valor:
        raise ErrorElevenLabs("ElevenLabs no devolvió el dato esperado.")
    return str(valor)


def token_conversacion() -> str:
    return _pedir("/v1/convai/conversation/token", "token")


def url_firmada() -> str:
    return _pedir("/v1/convai/conversation/get-signed-url", "signed_url")


def elegir_modo(preferido: str | None) -> str:
    """Sin clave o sin agente: texto con el agente del kit (o el demo grabado si se pide)."""
    if preferido in ("grabado", "texto_kit"):  # se respeta: texto_kit no pide nada a ElevenLabs
        return preferido
    if not configurado():
        return "texto_kit"
    return preferido if preferido in ("voz", "texto_el") else "voz"


def abrir(preferido: str | None) -> tuple[str, str | None, str | None]:
    """(modo, token, signed_url). Si ElevenLabs falla, baja al nivel 3 sin romper la llamada."""
    modo = elegir_modo(preferido)
    try:
        if modo == "voz":
            return modo, token_conversacion(), None
        if modo == "texto_el":
            return modo, None, url_firmada()
    except ErrorElevenLabs:
        return "texto_kit", None, None
    return modo, None, None
