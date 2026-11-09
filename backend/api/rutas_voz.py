"""Rutas de la llamada y el chat (tarea V1): de momento responden 501. Piden `X-Demo-Key` si hay clave."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from .rutas_copiloto import exigir_demo_key, no_implementado

router = APIRouter(prefix="/voz", dependencies=[Depends(exigir_demo_key)])


@router.post("/sesion")
def sesion() -> None:
    raise no_implementado("V1")


@router.post("/texto")
def texto() -> None:
    raise no_implementado("V1")


@router.post("/herramientas/preparar")
def herramienta_preparar() -> None:
    raise no_implementado("V1")


@router.post("/herramientas/feedback")
def herramienta_feedback() -> None:
    raise no_implementado("V1")


@router.post("/herramientas/consultar")
def herramienta_consultar() -> None:
    raise no_implementado("O3")
