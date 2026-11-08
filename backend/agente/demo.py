"""
Modo demo: graba respuestas reales y las reproduce sin llamar a la API (plan B de la demo).

    MODO_DEMO=grabar      cada pregunta se responde en directo y se guarda en demo/grabaciones/
    MODO_DEMO=reproducir  si la pregunta está grabada, se reproduce con el mismo streaming;
                          si no, se responde en directo (o con un aviso si no hay clave)
    MODO_DEMO=off         normal

Las preguntas se comparan sin mayúsculas, tildes ni signos de puntuación.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import datetime

from .. import config
from ..datos.categorias import normalizar

CARPETA = config.RAIZ / "demo" / "grabaciones"


def clave(mensaje: str) -> str:
    texto = re.sub(r"[^A-Z0-9 ]", " ", normalizar(mensaje))
    return re.sub(r"\s+", " ", texto).strip()


def _ruta(mensaje: str):
    return CARPETA / f"{hashlib.sha1(clave(mensaje).encode()).hexdigest()[:12]}.json"


def guardar(mensaje: str, eventos: list[list]) -> None:
    CARPETA.mkdir(parents=True, exist_ok=True)
    contenido = {"mensaje": mensaje, "clave": clave(mensaje),
                 "grabado": datetime.now().isoformat(timespec="seconds"), "eventos": eventos}
    _ruta(mensaje).write_text(json.dumps(contenido, ensure_ascii=False, indent=1), encoding="utf-8")


def buscar(mensaje: str) -> list[list] | None:
    try:
        return json.loads(_ruta(mensaje).read_text(encoding="utf-8"))["eventos"]
    except (OSError, ValueError, KeyError):
        return None


def grabadas() -> list[str]:
    if not CARPETA.exists():
        return []
    preguntas = []
    for ruta in sorted(CARPETA.glob("*.json")):
        try:
            preguntas.append(json.loads(ruta.read_text(encoding="utf-8"))["mensaje"])
        except (OSError, ValueError, KeyError):
            continue
    return preguntas


def reproducir(eventos: list[list], al_evento=None, pausa: float = 0.015) -> dict:
    """Reemite los eventos grabados. Devuelve los datos del evento 'fin'."""
    final = {}
    for tipo, datos in eventos:
        if tipo == "fin":
            final = {**datos, "reproducido": True, "coste_usd": 0.0}
            datos = final
        if al_evento:
            al_evento(tipo, datos)
            if tipo == "texto" and pausa:
                time.sleep(pausa)
    return final
