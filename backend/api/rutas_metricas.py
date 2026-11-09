"""Métricas para /jurado (tarea E9): el último JSON que escribe `evals/medir.py` en `evals/resultados/`.

Solo lee (sin clave de demo). Nombres: `motor` (alias `deteccion`) y `personalizacion` (alias
`molestias` y `aprendizaje`, que salen del mismo JSON). 404 legible si aún no hay ninguno.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException

router = APIRouter()

RESULTADOS = Path(__file__).resolve().parents[2] / "evals" / "resultados"
PARTES = {"motor": "motor", "deteccion": "motor",
          "personalizacion": "personalizacion", "molestias": "personalizacion", "aprendizaje": "personalizacion"}


def ultimo_resultado(parte: str, directorio: Path | None = None) -> Path | None:
    directorio = directorio or RESULTADOS
    if not directorio.is_dir():
        return None
    patron = re.compile(rf"^{re.escape(parte)}-\d{{4}}-\d{{2}}-\d{{2}}\.json$")
    rutas = sorted(r for r in directorio.iterdir() if patron.match(r.name))
    return rutas[-1] if rutas else None


@router.get("/metricas/{nombre}")
def metricas(nombre: str) -> dict:
    parte = PARTES.get(nombre)
    if parte is None:
        raise HTTPException(404, f"No hay métricas con ese nombre. Usa: {', '.join(PARTES)}.")
    ruta = ultimo_resultado(parte)
    if ruta is None:
        raise HTTPException(404, f"Aún no hay métricas de {parte}: ejecuta python evals/medir.py --parte {parte}.")
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise HTTPException(500, f"No se pudo leer {ruta.name}.") from error
    datos.setdefault("generado", datetime.fromtimestamp(ruta.stat().st_mtime).isoformat(timespec="seconds"))
    datos["archivo"] = ruta.name
    return datos
