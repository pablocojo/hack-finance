"""
Repartos: empareja pagos con tarjeta y los Bizums o transferencias que los devuelven
(motor.md §3.1 y deudas-casos.md, fase 1).

Cada reembolso va al pago anterior más reciente (en `VENTANA_REEMBOLSO` días) al que encaja:
1. **Cuota exacta**: `round(total / importe)` personas entre 3 y 12 y el total cuadra a `max(1 €, 3 %)`.
2. **Redondeo o múltiplo** de la cuota de referencia del pago (la más repetida entre las exactas): a <= 1 €
   de la cuota (redondeo), o k x cuota con 2 <= k <= `MAX_MULTIPLO` (cuenta como k personas).
3. **Sin explicar** (`extras`): un envío plausible que no encaja con nada. No cuenta como pago, pero el
   detector lo usa para dudar (cuotas desiguales, alguien que paga otra cantidad).
Un gasto fijo de vivienda (`CATEGORIAS_FIJO`) también cuenta como pago.
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
    """Un pago que otros pueden devolver: de tarjeta, fuera de las series y de una categoría de gasto compartible, o
    un gasto fijo de vivienda (alquiler) aunque sea una transferencia o un recibo de una serie mensual."""
    if m.tipo_operacion != "cargo" or -m.importe < p.IMPORTE_MIN_PAGO:
        return False
    if m.canal == "tarjeta" and m.serie_id is None and m.categoria in p.CATEGORIAS_PAGO:
        return True
    return m.canal in p.CANALES_FIJO and m.categoria in p.CATEGORIAS_FIJO


def es_fijo(m: MovimientoEnriquecido, p: GastoCompartido) -> bool:
    """Un gasto fijo de vivienda: solo se le asignan cuotas exactas y entre pocas personas (`PERSONAS_MAX_FIJO`)."""
    return m.categoria in p.CATEGORIAS_FIJO


def encaja_cuota(pago: MovimientoEnriquecido, cuota: Decimal, p: GastoCompartido) -> bool:
    personas = personas_que_encajan(-pago.importe, cuota, p)
    return bool(personas) and (not es_fijo(pago, p) or personas <= p.PERSONAS_MAX_FIJO)


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


def cuota_de_referencia(importes: list[Decimal], p: GastoCompartido) -> tuple[Decimal | None, bool]:
    """`(cuota, empate)`: el grupo de importes (a <= `TOL_CUOTA`) más numeroso; `empate` si hay dos igual de grandes."""
    grupos: list[list[Decimal]] = []
    for importe in sorted(importes):
        for grupo in grupos:
            if abs(importe - grupo[0]) <= p.TOL_CUOTA:
                grupo.append(importe)
                break
        else:
            grupos.append([importe])
    if not grupos:
        return None, False
    mayor = max(len(g) for g in grupos)
    primeros = [g for g in grupos if len(g) == mayor]
    return centimos(Decimal(statistics.median(primeros[0]))), len(primeros) > 1


def clase_de_importe(importe: Decimal, cuota: Decimal, p: GastoCompartido) -> tuple[str, int] | None:
    """Cómo encaja `importe` con la cuota: `("exacto"|"redondeo", 1)`, `("multiplo", k)` o None."""
    diferencia = abs(importe - cuota)
    if diferencia <= p.TOL_CUOTA:
        return "exacto", 1
    if diferencia <= p.TOL_REDONDEO_EUR:
        return "redondeo", 1
    for k in range(2, p.MAX_MULTIPLO + 1):
        if abs(importe - k * cuota) <= k * p.TOL_REDONDEO_EUR:
            return "multiplo", k
    return None


@dataclass
class Reparto:
    pago: MovimientoEnriquecido
    reembolsos: list[MovimientoEnriquecido] = field(default_factory=list)
    extras: list[MovimientoEnriquecido] = field(default_factory=list)   # envíos sin explicar dentro de la ventana
    cuota: Decimal | None = None
    personas: int | None = None
    faltan: int | None = None
    valido: bool = False
    cuadra: bool = False              # el total cuadra a ±0,05 € por persona
    pesos: dict[str, int] = field(default_factory=dict)       # id del reembolso -> personas que cubre (k)
    redondeos: list[str] = field(default_factory=list)        # ids de reembolsos redondeados
    empate: bool = False              # dos cuotas de referencia igual de probables
    desigual: bool = False            # sin cuota común: cada uno pagó una cantidad distinta

    @property
    def total(self) -> Decimal:
        return -self.pago.importe

    @property
    def multiples(self) -> list[MovimientoEnriquecido]:
        return [r for r in self.reembolsos if self.pesos.get(r.id, 1) > 1]

    @property
    def cubiertas(self) -> int:
        """Personas que han pagado (sin quien paga): un múltiplo cuenta como k."""
        return sum(self.pesos.get(r.id, 1) for r in self.reembolsos)

    def calcular(self, p: GastoCompartido) -> "Reparto":
        ajustan = [r.importe for r in self.reembolsos if personas_que_encajan(self.total, r.importe, p)]
        cuota, empate = cuota_de_referencia(ajustan, p)
        if cuota is not None:
            conserva, sobran = [], []
            for r in self.reembolsos:
                clase = clase_de_importe(r.importe, cuota, p)
                if clase:
                    conserva.append(r)
                    self.pesos[r.id] = clase[1]
                    if clase[0] == "redondeo":
                        self.redondeos.append(r.id)
                else:
                    sobran.append(r)
            self.reembolsos, self.extras = conserva, self.extras + sobran
            self.empate = empate and not sobran
        else:
            self.reembolsos, self.extras = [], self.reembolsos + self.extras
        if len(self.reembolsos) < p.MIN_REEMBOLSOS or cuota is None:
            self.desigual = len(self.reembolsos) + len(self.extras) >= p.MIN_REEMBOLSOS
            return self
        personas = personas_que_encajan(self.total, cuota, p)
        if personas is None or personas - 1 - self.cubiertas < 0:
            return self
        self.cuota, self.personas = cuota, personas
        self.faltan = personas - 1 - self.cubiertas
        self.cuadra = abs(self.total - personas * cuota) <= Decimal("0.05") * personas
        self.valido = True
        return self


def repartos(historial: list[MovimientoEnriquecido], p: GastoCompartido) -> dict[str, Reparto]:
    """`{pago_id: Reparto}` de los pagos que han recibido al menos un reembolso (o un envío sin explicar)."""
    pagos = [(i, m) for i, m in enumerate(historial) if es_pago(m, p)]
    if not pagos:
        return {}
    orden = {m.id: i for i, m in enumerate(historial)}
    entrantes = sorted((r for r in historial if es_reembolso_entrante(r)), key=lambda m: (m.fecha, orden[m.id]))
    asignados: dict[str, Reparto] = {}

    def en_ventana(r: MovimientoEnriquecido) -> list[MovimientoEnriquecido]:
        """Pagos que pudo devolver `r`, del más reciente al más antiguo."""
        candidatos = [(pago.fecha, i, pago) for i, pago in pagos
                      if 0 <= (r.fecha - pago.fecha).days <= p.VENTANA_REEMBOLSO]
        return [pago for _, _, pago in sorted(candidatos, key=lambda c: (c[0], c[1]), reverse=True)]

    # 1. cuota exacta
    restantes = []
    for r in entrantes:
        pago = next((x for x in en_ventana(r) if encaja_cuota(x, r.importe, p)), None)
        if pago:
            asignados.setdefault(pago.id, Reparto(pago=pago)).reembolsos.append(r)
        else:
            restantes.append(r)
    # 2. redondeo o múltiplo de la cuota de referencia del pago
    referencias = {pid: cuota_de_referencia([r.importe for r in rep.reembolsos], p)[0]
                   for pid, rep in asignados.items()}
    sin_explicar = []
    for r in restantes:
        pago = next((x for x in en_ventana(r) if referencias.get(x.id) is not None
                     and clase_de_importe(r.importe, referencias[x.id], p)), None)
        if pago:
            asignados[pago.id].reembolsos.append(r)
        else:
            sin_explicar.append(r)
    # 3. envíos plausibles sin explicar: al pago más reciente de su ventana
    for r in sin_explicar:
        ventana = [x for x in en_ventana(r) if r.importe <= -x.importe * p.PARTE_MAX_PCT and not es_fijo(x, p)]
        if ventana:
            asignados.setdefault(ventana[0].id, Reparto(pago=ventana[0])).extras.append(r)
    for rep in asignados.values():
        rep.reembolsos.sort(key=lambda m: (m.fecha, orden[m.id]))
        rep.extras.sort(key=lambda m: (m.fecha, orden[m.id]))
    return {pid: rep.calcular(p) for pid, rep in asignados.items()}
