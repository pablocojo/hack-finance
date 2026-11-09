"""
`gasto_compartido` (motor.md §3.1): pagaste algo para varios, casi todos te han devuelto su parte
con un Bizum y falta alguien.

Cuándo: el primer `hoy` con `hoy - pago >= DIAS_ESPERA` (p75 propio + 1, entre 2 y 5; 3 sin línea base)
y al menos un día desde el último reembolso, mientras `faltan >= 1` y `hoy - pago <= VENTANA_REEMBOLSO`.
Candidatos: quienes devolvieron junto a alguno de los que ya han pagado en repartos anteriores.
Las notas de los Bizums solo suben la confianza: nunca salen en `datos` ni en la explicación.
"""

from __future__ import annotations

import re
from collections import Counter

from ...datos.categorias import normalizar as normalizar_texto
from ..enriquecer import centimos
from ..parametros import GastoCompartido
from ..reparto import Reparto, repartos
from . import registrar
from .base import Contexto, Hallazgo

_PLAN = re.compile(r"\b(CENA|COMIDA|PIZZAS?|BIRRAS?|CUMPLE DE|REGALO PARA)\b")
_EMOJIS_PLAN = ("\U0001F355", "\U0001F35D", "\U0001F37B")   # pizza, espaguetis, jarras


def _nota_de_plan(nota: str | None) -> bool:
    return bool(nota) and (bool(_PLAN.search(normalizar_texto(nota))) or any(e in nota for e in _EMOJIS_PLAN))


def dias_espera(p: GastoCompartido, retraso_p75: int | None) -> int:
    if retraso_p75 is None:
        return p.DIAS_ESPERA
    return min(max(retraso_p75 + 1, p.DIAS_ESPERA_MIN), p.DIAS_ESPERA_MAX)


def candidatos(pagadores: set[str], repartos_previos: list[list[str]], p: GastoCompartido) -> list[tuple[str, int]]:
    """`[(contraparte, coincidencias)]` de quienes devolvieron con alguno de `pagadores`, de más a menos."""
    coincidencias: Counter[str] = Counter()
    for miembros in repartos_previos:
        if pagadores & set(miembros):
            coincidencias.update(set(miembros) - pagadores)
    elegidos = [(c, n) for c, n in coincidencias.items() if n >= p.MIN_COINCIDENCIAS]
    return sorted(elegidos, key=lambda par: (-par[1], par[0]))


def _confianza(reparto: Reparto, fuertes: bool, p: GastoCompartido) -> float:
    confianza = p.CONFIANZA_BASE
    confianza += 0.15 if reparto.cuadra else 0
    confianza += 0.10 if len(reparto.reembolsos) >= 3 else 0
    confianza += 0.10 if any(_nota_de_plan(r.nota) for r in reparto.reembolsos) else 0
    confianza += 0.10 if fuertes else 0
    confianza -= 0.15 if reparto.personas > 8 else 0
    return round(min(confianza, p.CONFIANZA_MAX), 2)


@registrar("gasto_compartido", version=1)
def detectar(ctx: Contexto) -> list[Hallazgo]:
    p: GastoCompartido = ctx.params["gasto_compartido"]
    espera = dias_espera(p, ctx.lineas_base.get("retraso_reembolso_p75"))
    hallazgos = []
    for reparto in repartos(ctx.historial, p).values():
        pago = reparto.pago
        dias = (ctx.hoy - pago.fecha).days
        if not reparto.valido or reparto.faltan < 1 or not espera <= dias <= p.VENTANA_REEMBOLSO:
            continue
        reembolsos = sorted(reparto.reembolsos, key=lambda r: r.fecha)
        if (ctx.hoy - reembolsos[-1].fecha).days < p.MIN_DIAS_DESDE_ULTIMO:
            continue
        pagadores = {r.contraparte_normalizada for r in reembolsos}
        elegidos = candidatos(pagadores, ctx.lineas_base.get("repartos", []), p)[: reparto.faltan * 2]
        fuertes = bool(elegidos) and elegidos[0][1] >= p.COINCIDENCIAS_FUERTES
        cuota = reparto.cuota
        pendiente = centimos(reparto.faltan * cuota)
        hallazgos.append(Hallazgo(
            tipo="gasto_compartido",
            clave=pago.id,
            movimientos=[pago.id, *(r.id for r in reembolsos)],
            confianza=_confianza(reparto, fuertes, p),
            impacto_eur=pendiente,
            datos={
                "pago_id": pago.id,
                "comercio": pago.comercio_normalizado,
                "importe_total": centimos(reparto.total),
                "fecha": pago.fecha.isoformat(),
                "reembolsos": [{"contraparte": r.contraparte_normalizada, "importe": centimos(r.importe), "id": r.id}
                               for r in reembolsos],
                "personas_estimadas": reparto.personas,
                "faltan": reparto.faltan,
                "importe_pendiente": pendiente,
                "candidatos": [{"contraparte": c, "importe": cuota} for c, _ in elegidos],
                "cuota": cuota,
            },
        ))
    return hallazgos
