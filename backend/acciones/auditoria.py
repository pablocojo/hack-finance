"""Auditoría de acciones: `auditoria.jsonl` por usuario, enmascarada por almacenamiento."""

from __future__ import annotations

from typing import Any

from ..plataforma import almacenamiento


def registrar(usuario_id: str, evento: str, *, propuesta_id: str | None = None, accion_id: str | None = None,
              parametros: dict | None = None, motivo: str | None = None, canal: str = "boton",
              fecha_simulada: str | None = None, extra: dict[str, Any] | None = None) -> dict:
    """evento: preparada | ejecutada | rechazada | deshecha."""
    reg: dict[str, Any] = {"evento": evento, "origen": "acciones", "propuesta_id": propuesta_id, "accion_id": accion_id,
                           "canal": canal, "simulada": True}
    if parametros is not None:
        reg["parametros"] = {k: (str(v) if not isinstance(v, (bool, int, str)) else v) for k, v in parametros.items()}
    if motivo:
        reg["motivo"] = motivo
    if fecha_simulada:
        reg["fecha_simulada"] = fecha_simulada
    if extra:
        reg.update(extra)
    return almacenamiento.anadir_auditoria(usuario_id, reg)
