"""Formato de eventos SSE y mensajes de error legibles (sin dependencias de FastAPI, para testearlos)."""

from __future__ import annotations

import json

MENSAJES = {
    "SinClaveError": None,  # su propio mensaje ya explica qué hacer
    "AuthenticationError": "La clave de la API no es válida. Revisa ANTHROPIC_API_KEY_PRODUCTO en .env.",
    "PermissionDeniedError": "La clave no tiene permiso para este modelo o esta función.",
    "RateLimitError": "Demasiadas peticiones a la API de Claude. Espera unos segundos y vuelve a intentarlo.",
    "APIConnectionError": "No hay conexión con la API de Claude. Revisa la red.",
    "APITimeoutError": "La API de Claude ha tardado demasiado. Vuelve a intentarlo.",
    "InternalServerError": "La API de Claude está saturada. Prueba de nuevo en un momento.",
    "OverloadedError": "La API de Claude está saturada. Prueba de nuevo en un momento.",
}
ESTADOS = {
    "SinClaveError": 503, "AuthenticationError": 502, "PermissionDeniedError": 502, "RateLimitError": 429,
    "APIConnectionError": 503, "APITimeoutError": 504, "InternalServerError": 503, "OverloadedError": 503,
    "ValueError": 400, "BadRequestError": 400,
}


def evento_sse(tipo: str, datos: dict) -> str:
    return f"event: {tipo}\ndata: {json.dumps(datos, ensure_ascii=False, default=str)}\n\n"


def mensaje_error(error: Exception) -> str:
    nombre = type(error).__name__
    texto = str(error)
    if "credit balance" in texto.lower():
        return "Se ha agotado el saldo de esta clave de la API. Cambia a la clave de reserva (ver docs/PLAN.md)."
    if nombre in MENSAJES:
        return MENSAJES[nombre] or texto
    if nombre == "BadRequestError":
        return f"La petición a Claude no es válida: {texto[:300]}"
    if isinstance(error, ValueError):
        return texto
    return f"Error inesperado ({nombre}). Mira la consola del backend."


def estado_http(error: Exception) -> int:
    return ESTADOS.get(type(error).__name__, 400 if isinstance(error, ValueError) else 502)
