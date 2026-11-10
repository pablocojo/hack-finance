"""
Cierre de casos: un Bizum o transferencia ENTRANTE de la misma contraparte (clave normalizada, p. ej.
`MARCOS R`) por la cuota ±0,50 €, en cualquier fecha posterior al pago y con cualquier concepto, salda al
deudor. El concepto o la nota del movimiento NO se usan para decidir (son datos de un tercero).

Si todos los deudores quedan saldados, el caso pasa a `saldado` y no avisa más; si entra antes de
`avisar_desde`, se salda sin avisar. Es en línea: solo mira los movimientos que se le pasan (los del día).
"""

from __future__ import annotations

from datetime import date, datetime

from ..motor.normalizar import normalizar
from ..plataforma.reloj import ahora_por_defecto
from ..plataforma.tipos import Caso, Movimiento, MovimientoEnriquecido
from .ciclo import (CERRADOS, TOLERANCIA, _a_fecha, _anotar, _copia, nombre_visible)


def _enriquecido(m: Movimiento) -> MovimientoEnriquecido:
    if isinstance(m, MovimientoEnriquecido) and m.contraparte_normalizada:
        return m
    return normalizar(m)


def pagos_entrantes(movimientos: list[Movimiento]) -> list[MovimientoEnriquecido]:
    """Bizums y transferencias recibidos, con la clave de contraparte ya normalizada."""
    salida = []
    for m in movimientos:
        e = _enriquecido(m)
        if e.importe > 0 and e.canal in ("bizum", "transferencia") and e.contraparte_normalizada:
            salida.append(e)
    return salida


def saldar_con_movimientos(caso: Caso, movimientos: list[Movimiento], hoy: date,
                           ahora: datetime | None = None) -> Caso:
    """Devuelve el caso con los deudores que pagan saldados; si lo están todos, `saldado`. Cada movimiento
    salda como mucho a un deudor. Ignora los movimientos que ya probaban el caso y los anteriores al pago."""
    if caso.estado in CERRADOS or not caso.deudores:
        return caso
    ya_usados = {str(x) for x in caso.hechos.get("movimientos", [])}
    desde = _a_fecha(caso.hechos.get("fecha")) or caso.creado
    libres = [e for e in pagos_entrantes(movimientos) if e.id not in ya_usados and desde <= e.fecha <= hoy]
    if not libres:
        return caso

    nuevo = _copia(caso)
    cuando = ahora or ahora_por_defecto(hoy)
    for deudor in nuevo.deudores:
        if deudor.estado == "saldada":
            continue
        encajan = [e for e in libres
                   if e.contraparte_normalizada == deudor.contraparte and abs(e.importe - deudor.cuota) <= TOLERANCIA]
        if not encajan:
            continue
        pago = min(encajan, key=lambda e: (abs(e.importe - deudor.cuota), e.fecha, e.id))
        libres.remove(pago)
        deudor.estado, deudor.saldada, deudor.movimiento_pago = "saldada", pago.fecha, pago.id
        _anotar(nuevo, "codigo", f"{nombre_visible(deudor.contraparte)} pasa a saldada.", cuando)

    if all(d.estado == "saldada" for d in nuevo.deudores):
        sin_aviso = "avisado_el" not in nuevo.hechos
        nuevo.estado = "saldado"
        _anotar(nuevo, "codigo", "Caso saldado" + (" antes de avisar." if sin_aviso else "."), cuando)
    return nuevo if nuevo != caso else caso


def saldar_casos(casos: list[Caso], movimientos: list[Movimiento], hoy: date,
                 ahora: datetime | None = None) -> list[Caso]:
    """`saldar_con_movimientos` sobre una lista, en el mismo orden."""
    if not movimientos:
        return list(casos)
    return [saldar_con_movimientos(c, movimientos, hoy, ahora) for c in casos]


__all__ = ["pagos_entrantes", "saldar_con_movimientos", "saldar_casos"]
