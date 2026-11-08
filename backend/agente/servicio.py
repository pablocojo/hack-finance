"""
Capa de servicio que usan la API, el panel y las evals: aplica el modo demo y llama al agente.
"""

from __future__ import annotations

from .. import claude_client, config
from ..datos.almacen import Sesion
from . import demo
from .nucleo import Agente, AlEvento

SIN_GRABACION = ("Estoy en modo demo y no tengo grabada esta pregunta. "
                 "Prueba con una de las preguntas del guion.")


def conversar(sesion: Sesion, mensaje: str, *, adjunto: dict | None = None,
              preferencia: str | None = "auto", al_evento: AlEvento | None = None,
              agente: Agente | None = None) -> dict:
    """Responde un mensaje y devuelve el resultado como dict (texto, coste, trazas...)."""
    modo = config.ajustes().modo_demo

    if modo == "reproducir" and not adjunto:
        eventos = demo.buscar(mensaje)
        if eventos is not None:
            final = demo.reproducir(eventos, al_evento)
            with sesion.turno:
                sesion.mensajes.append({"role": "user", "content": mensaje})
                sesion.mensajes.append({"role": "assistant",
                                        "content": [{"type": "text", "text": final.get("texto", "")}]})
            return final
        if config.clave_api("producto")[0] is None:
            final = {"texto": SIN_GRABACION, "modelo": "demo", "vueltas": 0, "coste_usd": 0.0,
                     "coste_sesion_usd": sesion.coste_usd, "herramientas": [], "trazas": [],
                     "revision": None, "avisos": [], "tokens": {}}
            if al_evento:
                al_evento("texto", {"texto": SIN_GRABACION})
                al_evento("fin", final)
            return final

    eventos: list[list] = []

    def registrar(tipo: str, datos: dict) -> None:
        eventos.append([tipo, datos])
        if al_evento:
            al_evento(tipo, datos)

    grabar = modo == "grabar" and not adjunto
    resultado = (agente or Agente()).responder(
        sesion, mensaje, adjunto=adjunto, preferencia=preferencia,
        al_evento=registrar if (al_evento or grabar) else None,
    )
    if grabar:
        demo.guardar(mensaje, eventos)
    return resultado.a_dict()


def estado() -> dict:
    clave, origen = config.clave_api("producto")
    return {"clave_configurada": bool(clave), "origen_clave": origen,
            "coste_proceso_usd": round(claude_client.coste_acumulado(), 4),
            "preguntas_grabadas": len(demo.grabadas())}
