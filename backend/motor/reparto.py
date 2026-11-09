"""
Repartos: empareja pagos con tarjeta y los Bizums o transferencias que los devuelven (motor.md §3.1).

Cada reembolso va al pago anterior más reciente (en `VENTANA_REEMBOLSO` días) cuya cuota encaja:
`round(total / importe)` personas entre 3 y 12 y el total cuadra a `max(1 €, 3 %)`.
Lo usan el detector `gasto_compartido` y las líneas base (retraso p75 y grupos propios).
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from ..plataforma.tipos import MovimientoEnriquecido
from .enriquecer import centimos, es_reembolso_entrante
from .parametros import GastoCompartido


def es_pago(m: MovimientoEnriquecido, p: GastoCompartido) -> bool:
    return (m.canal == "tarjeta" and m.tipo_operacion == "cargo" and -m.importe >= p.IMPORTE_MIN_PAGO
            and m.serie_id is None and m.categoria in p.CATEGORIAS_PAGO)


def personas_que_encajan(total: Decimal, cuota: Decimal, p: GastoCompartido) -> int | None:
    """Personas del reparto (incluida quien paga) si `total` se divide en cuotas de `cuota`; si no, None."""
    if cuota <= 0:
        return None
    personas = int((total / cuota).to_integral_value(rounding=ROUND_HALF_UP))
    if not p.PERSONAS_MIN <= personas <= p.PERSONAS_MAX:
        return None
    if abs(total - personas * cuota) > max(p.TOL_REPARTO_EUR, total * p.TOL_REPARTO_PCT):
        return None
    return personas


@dataclass
class Reparto:
    pago: MovimientoEnriquecido
    reembolsos: list[MovimientoEnriquecido] = field(default_factory=list)
    cuota: Decimal | None = None
    personas: int | None = None
    faltan: int | None = None
    valido: bool = False
    cuadra: bool = False              # el total cuadra a ±0,05 € por persona

    @property
    def total(self) -> Decimal:
        return -self.pago.importe

    def calcular(self, p: GastoCompartido) -> "Reparto":
        importes = [r.importe for r in self.reembolsos]
        if len(importes) < p.MIN_REEMBOLSOS:
            return self
        cuota = centimos(Decimal(statistics.median(importes)))
        if any(abs(i - cuota) > p.TOL_CUOTA for i in importes):
            return self               # cuotas desiguales: fuera del MVP, no avisa
        personas = personas_que_encajan(self.total, cuota, p)
        if personas is None or personas - 1 - len(importes) < 0:
            return self
        self.cuota, self.personas = cuota, personas
        self.faltan = personas - 1 - len(importes)
        self.cuadra = abs(self.total - personas * cuota) <= Decimal("0.05") * personas
        self.valido = True
        return self


def repartos(historial: list[MovimientoEnriquecido], p: GastoCompartido) -> dict[str, Reparto]:
    """`{pago_id: Reparto}` de los pagos que han recibido al menos un reembolso."""
    pagos = [(i, m) for i, m in enumerate(historial) if es_pago(m, p)]
    if not pagos:
        return {}
    asignados: dict[str, Reparto] = {}
    for r in sorted(historial, key=lambda m: m.fecha):
        if not es_reembolso_entrante(r):
            continue
        mejor = None
        for i, pago in pagos:
            dias = (r.fecha - pago.fecha).days
            if 0 <= dias <= p.VENTANA_REEMBOLSO and personas_que_encajan(-pago.importe, r.importe, p):
                if mejor is None or (pago.fecha, i) > mejor[0]:
                    mejor = ((pago.fecha, i), pago)
        if mejor:
            pago = mejor[1]
            asignados.setdefault(pago.id, Reparto(pago=pago)).reembolsos.append(r)
    return {pid: reparto.calcular(p) for pid, reparto in asignados.items()}
