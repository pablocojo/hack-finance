"""
Acciones de la lista cerrada con banco simulado. STUB de E1: firmas de docs/ARQUITECTURA.md §3.2.
Lo sustituye el hilo `modulos`; las firmas no cambian.
`preparar` no tiene efectos; `ejecutar` valida token, usuario, propuesta, acción y límites.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from ..plataforma.tipos import ACCIONES, ResultadoAccion, TarjetaConfirmacion


def preparar(accion_id: str, parametros: dict, propuesta_id: str, usuario_id: str) -> TarjetaConfirmacion:
    """Stub: tarjeta válida con token de ejemplo. Una acción fuera de la lista lanza error."""
    if accion_id not in ACCIONES:
        raise ValueError(f"Acción no permitida: {accion_id!r}. Las válidas son: {', '.join(ACCIONES)}.")
    return TarjetaConfirmacion(
        accion_id=accion_id,
        propuesta_id=propuesta_id,
        titulo=f"Acción simulada: {accion_id}",
        parametros_legibles={k: str(v) for k, v in parametros.items()},
        token_confirmacion="stub-token",
        caduca=datetime.now() + timedelta(minutes=10),
    )


def ejecutar(token_confirmacion: str, usuario_id: str) -> ResultadoAccion:
    """Stub: resultado simulado correcto."""
    return ResultadoAccion(accion_id="recordar", ok=True, mensaje="Acción simulada (stub).")


def deshacer(resultado_id: str, usuario_id: str) -> ResultadoAccion:
    """Opcional (O4). Stub: resultado simulado."""
    return ResultadoAccion(accion_id="recordar", ok=True, mensaje="Deshecho (stub).")
