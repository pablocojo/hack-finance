"""
Tokens de confirmación: 10 minutos, un solo uso, ligados al usuario, a la propuesta y al hash de los
parámetros. Se guardan solo como hash SHA-256 en `tokens.json`. Nunca llegan a un modelo.
"""

from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime, timedelta
from decimal import Decimal

from ..plataforma import almacenamiento

VIGENCIA = timedelta(minutes=10)


def ahora() -> datetime:  # punto único de reloj (los tests lo sustituyen)
    return datetime.now()


def hash_parametros(parametros: dict) -> str:
    canon = {k: (format(v, "f") if isinstance(v, Decimal) else v) for k, v in sorted(parametros.items())}
    return hashlib.sha256(json.dumps(canon, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _huella(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def emitir(usuario_id: str, propuesta_id: str, accion_id: str, parametros: dict) -> tuple[str, datetime]:
    token = secrets.token_urlsafe(24)
    caduca = ahora() + VIGENCIA
    with almacenamiento.candado(usuario_id):
        tabla = almacenamiento.cargar(usuario_id, "tokens", defecto={}) or {}
        tabla = {h: t for h, t in tabla.items() if not t.get("usado") or t["caduca"] > (ahora() - timedelta(hours=1)).isoformat()}
        tabla[_huella(token)] = {
            "usuario_id": usuario_id, "propuesta_id": propuesta_id, "accion_id": accion_id,
            "hash": hash_parametros(parametros), "parametros": json.loads(json.dumps(parametros, default=str)),
            "caduca": caduca.isoformat(), "usado": False,
        }
        almacenamiento.guardar(usuario_id, "tokens", tabla)
    return token, caduca


def buscar(usuario_id: str, token: str) -> dict | None:
    tabla = almacenamiento.cargar(usuario_id, "tokens", defecto={}) or {}
    return tabla.get(_huella(token))


def marcar_usado(usuario_id: str, token: str) -> None:
    with almacenamiento.candado(usuario_id):
        tabla = almacenamiento.cargar(usuario_id, "tokens", defecto={}) or {}
        if _huella(token) in tabla:
            tabla[_huella(token)]["usado"] = True
            almacenamiento.guardar(usuario_id, "tokens", tabla)
