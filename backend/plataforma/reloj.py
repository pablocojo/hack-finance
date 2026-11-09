"""Reloj simulado: el motor solo ve el pasado y la demo avanza día a día."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

HORA_DECISION = time(20, 30)


def ahora_por_defecto(hoy: date) -> datetime:
    """Hora a la que se decide por defecto un día simulado: hoy a las 20:30."""
    return datetime.combine(hoy, HORA_DECISION)


class Reloj:
    """Fecha simulada de un usuario. `avanzar` nunca retrocede."""

    def __init__(self, hoy: date):
        self.hoy = hoy

    def ahora(self) -> datetime:
        return ahora_por_defecto(self.hoy)

    def avanzar(self, dias: int = 1) -> date:
        if dias < 0:
            raise ValueError("El reloj simulado no retrocede: reinicia el usuario para volver atrás.")
        self.hoy = self.hoy + timedelta(days=dias)
        return self.hoy
