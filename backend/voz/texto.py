"""
Nivel 3 de la llamada (sin clave o sin red a ElevenLabs): el agente del kit con el contexto de la
propuesta en el sistema y solo las herramientas de la llamada. Misma tarjeta y eventos SSE:
`texto`, `herramienta_inicio`, `herramienta_fin`, `tarjeta {tarjeta}`, `fin`, `error`.
"""

from __future__ import annotations

import queue
import threading
from typing import Iterator

from ..agente import servicio
from ..agente.nucleo import Agente
from ..api.sse import mensaje_error
from . import contexto, herramientas_llamada  # noqa: F401  (importar registra las herramientas)
from .sesiones import RegistroSesion

HERRAMIENTAS = ["preparar_accion", "registrar_feedback"]


def _agente(registro: RegistroSesion) -> Agente:
    return Agente(modelo="sonnet", herramientas=HERRAMIENTAS, sistema=contexto.sistema_texto(registro.variables))


def saludo(registro: RegistroSesion) -> str:
    """Primer mensaje fijo y neutro (el aviso de IA es la insignia en pantalla). Entra en el historial sin llamar a Claude."""
    texto = contexto.primer_mensaje(registro.variables)
    with registro.kit.turno:
        if not registro.saludado:
            registro.kit.mensajes += [
                {"role": "user", "content": "(El cliente ha abierto el aviso y empieza la llamada.)"},
                {"role": "assistant", "content": [{"type": "text", "text": texto}]},
            ]
            registro.saludado = True
    return texto


def eventos(registro: RegistroSesion, mensaje: str | None) -> Iterator[tuple[str, dict]]:
    """Genera (tipo, datos). Sin mensaje: el saludo. Los errores salen como evento `error`."""
    if not (mensaje or "").strip():
        texto = saludo(registro)
        yield "texto", {"texto": texto}
        yield "fin", {"texto": texto, "modelo": "fijo", "vueltas": 0, "coste_usd": 0.0, "herramientas": []}
        return
    cola: queue.Queue = queue.Queue()
    fin = object()
    kit = registro.kit
    if not registro.saludado:
        saludo(registro)

    def emitir(tipo: str, datos: dict) -> None:
        cola.put((tipo, datos))
        if tipo == "herramienta_fin" and datos.get("nombre") == "preparar_accion":
            while kit.tarjetas:
                cola.put(("tarjeta", {"tarjeta": kit.tarjetas.pop(0)}))

    def trabajar() -> None:
        try:
            servicio.conversar(kit, mensaje, agente=_agente(registro), al_evento=emitir)
        except Exception as error:
            cola.put(("error", {"mensaje": mensaje_error(error), "tipo": type(error).__name__}))
        finally:
            cola.put(fin)

    threading.Thread(target=trabajar, daemon=True).start()
    while True:
        elemento = cola.get()
        if elemento is fin:
            return
        yield elemento
