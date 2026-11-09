"""Métricas para /jurado (tarea E9): servirán el último JSON de `evals/resultados/`. De momento 501."""

from __future__ import annotations

from fastapi import APIRouter

from .rutas_copiloto import no_implementado

router = APIRouter()


@router.get("/metricas/{nombre}")
def metricas(nombre: str) -> None:
    raise no_implementado("E9")
