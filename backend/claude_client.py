"""
Punto único de acceso a la API de Claude para el producto: agente, revisor, categorizador y evals.

Uso rápido:
    from backend.claude_client import preguntar, preguntar_json

    texto = preguntar("Explica qué es la TAE en dos frases", modelo="haiku")
    datos = preguntar_json("Clasifica: 'MERCADONA 23,40'", esquema={...})

Notas para el SDK 2.x (API 2026-10-21):
- temperature, top_p y top_k ya no existen: devuelven un error 400.
- Los documentos (PDF) van siempre en mensajes del usuario.
- La caché automática (cache_control en la raíz) y output_config (esfuerzo y JSON
  estructurado) se envían en extra_body, que funciona con cualquier versión del SDK.
"""

from __future__ import annotations

import copy
import json
import threading
from typing import Any

from . import config

MODELOS = {
    "haiku": "claude-haiku-5-5",
    "sonnet": "claude-sonnet-5-5",
    "opus": "claude-opus-5-5",
}

# USD por millón de tokens: (entrada, salida, lectura de caché, escritura de caché de 5 min).
# Haiku: precio para prompts de hasta 100.000 tokens.
# Fuente: https://platform.claude.com/docs/en/about-claude/pricing
PRECIOS = {
    "claude-haiku-5-5": (0.10, 0.50, 0.01, 0.125),
    "claude-sonnet-5-5": (2.00, 10.00, 0.10, 2.50),
    "claude-opus-5-5": (4.00, 20.00, 0.20, 5.00),
}
PRECIO_BUSQUEDA_WEB = 0.01  # 10 $ por cada 1.000 búsquedas

_clientes: dict[str, Any] = {}
_cerrojo = threading.Lock()
_coste_total = 0.0


class SinClaveError(RuntimeError):
    """No hay clave de la API configurada para este uso."""


def modelo_id(alias_o_id: str) -> str:
    return MODELOS.get(alias_o_id, alias_o_id)


def cliente(uso: str = "producto"):
    """Cliente de Anthropic para un uso ("producto" o "evals"). Se crea la primera vez."""
    with _cerrojo:
        if uso not in _clientes:
            clave, _ = config.clave_api(uso)
            if not clave:
                raise SinClaveError(
                    "Falta la clave de la API. Añade ANTHROPIC_API_KEY_PRODUCTO a .env "
                    "(y ANTHROPIC_API_KEY_EVALS para las evals)."
                )
            import anthropic

            _clientes[uso] = anthropic.Anthropic(api_key=clave, max_retries=3, timeout=120.0)
        return _clientes[uso]


def usar_cliente(falso, uso: str | None = None) -> None:
    """Sustituye el cliente real (tests, evals simuladas). Sin `uso`, para todos los usos."""
    with _cerrojo:
        if uso is None:
            _clientes.clear()
            _clientes["producto"] = falso
            _clientes["evals"] = falso
        else:
            _clientes[uso] = falso


def olvidar_clientes() -> None:
    with _cerrojo:
        _clientes.clear()


def _valor(objeto, nombre: str, defecto=0):
    if objeto is None:
        return defecto
    if isinstance(objeto, dict):
        return objeto.get(nombre, defecto) or defecto
    return getattr(objeto, nombre, defecto) or defecto


def tokens(usage) -> dict:
    return {
        "entrada": _valor(usage, "input_tokens"),
        "salida": _valor(usage, "output_tokens"),
        "cache_lectura": _valor(usage, "cache_read_input_tokens"),
        "cache_escritura": _valor(usage, "cache_creation_input_tokens"),
    }


def coste(modelo: str, usage) -> float:
    """Coste estimado en USD de una respuesta, a precio de lista."""
    precios = PRECIOS.get(modelo_id(modelo))
    if not precios or usage is None:
        return 0.0
    entrada, salida, lectura, escritura = precios
    t = tokens(usage)
    total = (
        t["entrada"] * entrada
        + t["salida"] * salida
        + t["cache_lectura"] * lectura
        + t["cache_escritura"] * escritura
    ) / 1_000_000
    busquedas = _valor(_valor(usage, "server_tool_use", None), "web_search_requests")
    return total + busquedas * PRECIO_BUSQUEDA_WEB


def registrar_coste(importe: float) -> None:
    global _coste_total
    with _cerrojo:
        _coste_total += importe


def coste_acumulado() -> float:
    """USD estimados gastados por este proceso."""
    return _coste_total


def preparar_peticion(
    *,
    modelo: str,
    messages: list,
    system: str | list | None = None,
    tools: list | None = None,
    max_tokens: int = 4000,
    esfuerzo: str | None = None,
    formato: dict | None = None,
    cache: bool = True,
) -> dict:
    """Construye los argumentos de messages.create / messages.stream."""
    peticion: dict[str, Any] = {
        "model": modelo_id(modelo),
        "max_tokens": max_tokens,
        "messages": messages,
    }
    if system:
        peticion["system"] = system
    if tools:
        peticion["tools"] = tools
    extra: dict[str, Any] = {}
    if cache:
        # Caché automática: tools, system e historial repetidos salen al 5-10 % del precio.
        extra["cache_control"] = {"type": "ephemeral"}
    output_config: dict[str, Any] = {}
    if esfuerzo:
        output_config["effort"] = esfuerzo
    if formato:
        output_config["format"] = formato
    if output_config:
        extra["output_config"] = output_config
    if extra:
        peticion["extra_body"] = extra
    return peticion


def texto_de(respuesta) -> str:
    """Junta los bloques de texto (ignora thinking, tool_use y otros bloques)."""
    partes = []
    for bloque in getattr(respuesta, "content", []) or []:
        tipo = bloque.get("type") if isinstance(bloque, dict) else getattr(bloque, "type", "")
        if tipo == "text":
            partes.append(bloque.get("text") if isinstance(bloque, dict) else bloque.text)
    return "".join(partes).strip()


def _llamar(prompt, *, system, modelo, esfuerzo, max_tokens, historial, formato, uso):
    mensajes = list(historial or []) + [{"role": "user", "content": prompt}]
    peticion = preparar_peticion(
        modelo=modelo, messages=mensajes, system=system,
        max_tokens=max_tokens, esfuerzo=esfuerzo, formato=formato,
    )
    respuesta = cliente(uso).messages.create(**peticion)
    importe = coste(peticion["model"], getattr(respuesta, "usage", None))
    registrar_coste(importe)
    if getattr(respuesta, "stop_reason", None) == "refusal":
        raise RuntimeError("Claude ha rechazado la petición.")
    return respuesta, importe


def preguntar(
    prompt: str | list,
    *,
    system: str | None = None,
    modelo: str = "haiku",
    esfuerzo: str | None = None,
    max_tokens: int = 2000,
    historial: list[dict] | None = None,
    uso: str = "producto",
) -> str:
    """Pregunta a Claude y devuelve solo el texto. modelo: haiku, sonnet, opus o un ID."""
    respuesta, _ = _llamar(
        prompt, system=system, modelo=modelo, esfuerzo=esfuerzo, max_tokens=max_tokens,
        historial=historial, formato=None, uso=uso,
    )
    return texto_de(respuesta)


def cerrar_objetos(esquema: dict) -> dict:
    """Añade additionalProperties: false a cada objeto del esquema (lo pide la salida estructurada)."""
    esquema = copy.deepcopy(esquema)

    def visitar(nodo):
        if isinstance(nodo, dict):
            if nodo.get("type") == "object":
                nodo.setdefault("additionalProperties", False)
            for valor in nodo.values():
                visitar(valor)
        elif isinstance(nodo, list):
            for valor in nodo:
                visitar(valor)

    visitar(esquema)
    return esquema


def preguntar_json_con_coste(
    prompt: str | list,
    esquema: dict,
    *,
    system: str | None = None,
    modelo: str = "haiku",
    esfuerzo: str | None = "low",
    max_tokens: int = 2000,
    uso: str = "producto",
) -> tuple[dict, float]:
    """Como preguntar_json, pero devuelve también el coste en USD."""
    formato = {"type": "json_schema", "schema": cerrar_objetos(esquema)}
    respuesta, importe = _llamar(
        prompt, system=system, modelo=modelo, esfuerzo=esfuerzo, max_tokens=max_tokens,
        historial=None, formato=formato, uso=uso,
    )
    if getattr(respuesta, "stop_reason", None) == "max_tokens":
        raise RuntimeError("La respuesta JSON se ha cortado: sube max_tokens.")
    return json.loads(texto_de(respuesta)), importe


def preguntar_json(prompt: str | list, esquema: dict, **opciones) -> dict:
    """Devuelve un dict que cumple el JSON Schema `esquema` (salida estructurada)."""
    datos, _ = preguntar_json_con_coste(prompt, esquema, **opciones)
    return datos
