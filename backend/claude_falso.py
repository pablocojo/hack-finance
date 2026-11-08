"""
Cliente de Anthropic simulado para tests, evals --simulado y ensayos sin gastar crédito.

    from backend import claude_client
    from backend.claude_falso import ClienteFalso, respuesta, texto, herramienta

    falso = ClienteFalso([
        respuesta(herramienta("resumen_gastos", {"meses": 3})),
        respuesta(texto("Este trimestre has gastado 1.234,56 €.")),
    ])
    claude_client.usar_cliente(falso)

Cada elemento del guion es una respuesta o una función f(peticion) -> respuesta.
Se consumen en orden; cuando se acaban, se responde con `por_defecto`.
"""

from __future__ import annotations

import copy
import itertools
import json
import threading
from types import SimpleNamespace

_ids = itertools.count(1)


def texto(contenido: str):
    return SimpleNamespace(type="text", text=contenido)


def herramienta(nombre: str, entrada: dict | None = None, id: str | None = None):
    return SimpleNamespace(
        type="tool_use", id=id or f"toolu_falso_{next(_ids)}", name=nombre, input=entrada or {}
    )


def pensamiento(contenido: str = "Pensando…"):
    return SimpleNamespace(type="thinking", thinking=contenido, signature="firma-simulada")


def uso(entrada: int = 120, salida: int = 60, lectura: int = 0, escritura: int = 0):
    return SimpleNamespace(
        input_tokens=entrada,
        output_tokens=salida,
        cache_read_input_tokens=lectura,
        cache_creation_input_tokens=escritura,
        server_tool_use=None,
    )


def respuesta(*bloques, stop_reason: str | None = None, usage=None, modelo: str = "simulado"):
    if stop_reason is None:
        hay_herramientas = any(getattr(b, "type", "") == "tool_use" for b in bloques)
        stop_reason = "tool_use" if hay_herramientas else "end_turn"
    return SimpleNamespace(
        content=list(bloques), stop_reason=stop_reason, usage=usage or uso(), model=modelo
    )


def respuesta_json(datos: dict):
    """Respuesta de salida estructurada: un único bloque de texto con JSON."""
    return respuesta(texto(json.dumps(datos, ensure_ascii=False)))


def _trocear(contenido: str, tamano: int = 12):
    for inicio in range(0, len(contenido), tamano):
        yield contenido[inicio:inicio + tamano]


class _Stream:
    def __init__(self, resp):
        self._respuesta = resp

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    @property
    def text_stream(self):
        for bloque in self._respuesta.content:
            if getattr(bloque, "type", "") == "text":
                yield from _trocear(bloque.text)

    def get_final_message(self):
        return self._respuesta


class _Mensajes:
    def __init__(self, cliente: "ClienteFalso"):
        self._cliente = cliente

    def create(self, **peticion):
        return self._cliente._responder(peticion)

    def stream(self, **peticion):
        return _Stream(self._cliente._responder(peticion))


class ClienteFalso:
    def __init__(self, guion=None, por_defecto: str = "Respuesta simulada."):
        self.guion = list(guion or [])
        self.por_defecto = por_defecto
        self.peticiones: list[dict] = []
        self.messages = _Mensajes(self)
        self._cerrojo = threading.Lock()

    def _responder(self, peticion: dict):
        with self._cerrojo:
            self.peticiones.append(copy.deepcopy(peticion))
            siguiente = self.guion.pop(0) if self.guion else None
        if siguiente is None:
            return respuesta(texto(self.por_defecto))
        if callable(siguiente):
            return siguiente(peticion)
        return siguiente
