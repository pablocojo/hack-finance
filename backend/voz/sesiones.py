"""
Sesión de la llamada, propia del servidor. El `token_sesion` va ligado a usuario y propuesta y
caduca a los 10 minutos: de él sale el `usuario_id`, nunca del agente ni del cuerpo de las
herramientas. Se guarda en memoria (una instancia); si el proceso reinicia, hay que abrir otra.
"""

from __future__ import annotations

import secrets
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from ..datos.almacen import Sesion

TTL = timedelta(minutes=10)
GRACIA_CONVERSACION = timedelta(minutes=10)   # al colgar, la transcripción puede llegar tras caducar el TTL (solo esa ruta)
MAX_SESIONES = 200


class ErrorSesion(ValueError):
    """Token de sesión desconocido (401) o caducado (410). `http` lo lee `estado_de_error`."""

    def __init__(self, mensaje: str, http: int):
        super().__init__(mensaje)
        self.http = http


@dataclass
class SesionLlamada(Sesion):
    """Sesión del agente del kit para el nivel 3, con la propuesta fijada por el servidor y un
    buzón de tarjetas: la tarjeta (con su token de confirmación) va al navegador, no al modelo. `cambios` es el
    buzón de los cambios que hizo `actualizar_caso` (`{hecho, cambio_id}`, para el aviso con «Deshacer») y `deshacer`
    guarda, por `cambio_id`, el caso antes y después (se pierde con la sesión, 10 min)."""

    usuario_id: str = ""
    propuesta_id: str = ""
    tarjetas: list[dict] = field(default_factory=list)
    cambios: list[dict] = field(default_factory=list)
    deshacer: dict[str, dict] = field(default_factory=dict)


@dataclass
class RegistroSesion:
    token_sesion: str
    usuario_id: str
    propuesta_id: str
    modo: str
    caduca: datetime
    variables: dict[str, str]
    kit: SesionLlamada
    saludado: bool = False


_SESIONES: dict[str, RegistroSesion] = {}
_CERROJO = threading.Lock()


def crear(usuario_id: str, propuesta_id: str, modo: str, variables: dict[str, str],
          ahora: datetime | None = None) -> RegistroSesion:
    ahora = ahora or datetime.now()
    token = secrets.token_urlsafe(32)
    kit = SesionLlamada(id=f"llamada-{token[:8]}", usuario_id=usuario_id, propuesta_id=propuesta_id,
                        origen_datos="propuesta")
    registro = RegistroSesion(token, usuario_id, propuesta_id, modo, ahora + TTL, dict(variables), kit)
    with _CERROJO:
        for t in [t for t, r in _SESIONES.items() if r.caduca + GRACIA_CONVERSACION < ahora]:
            del _SESIONES[t]
        while len(_SESIONES) >= MAX_SESIONES:  # tope de memoria: cae la más antigua
            del _SESIONES[next(iter(_SESIONES))]
        _SESIONES[token] = registro
    return registro


def obtener(token_sesion: str | None, ahora: datetime | None = None,
            gracia: timedelta = timedelta(0)) -> RegistroSesion:
    """`gracia` solo la pide `/voz/conversacion`: la sesión sigue valiendo ese margen tras caducar (una llamada larga
    cuelga después de los 10 min). Las demás rutas la rechazan (410) en cuanto caduca, aunque la sesión siga en memoria."""
    ahora = ahora or datetime.now()
    with _CERROJO:
        registro = _SESIONES.get(token_sesion or "")
    if registro is None:
        raise ErrorSesion("Sesión de llamada desconocida. Abre la llamada otra vez.", 401)
    if registro.caduca + gracia < ahora:
        if registro.caduca + GRACIA_CONVERSACION < ahora:
            with _CERROJO:
                _SESIONES.pop(registro.token_sesion, None)
        raise ErrorSesion("La sesión de la llamada ha caducado. Abre la llamada otra vez.", 410)
    return registro


def olvidar_todo() -> None:
    with _CERROJO:
        _SESIONES.clear()
