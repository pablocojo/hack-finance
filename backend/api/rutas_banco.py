"""Consola del banco (tarea D2): módulos, borrador y aprobación. De momento responden 501."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from .rutas_copiloto import exigir_demo_key, no_implementado

router = APIRouter(prefix="/banco/modulos", dependencies=[Depends(exigir_demo_key)])


@router.get("")
def modulos() -> None:
    raise no_implementado("D2")


@router.post("/borrador")
def borrador() -> None:
    raise no_implementado("D2")


@router.post("/{modulo_id}/aprobar")
def aprobar(modulo_id: str) -> None:
    raise no_implementado("D2")
