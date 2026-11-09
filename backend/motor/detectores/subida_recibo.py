"""
`subida_recibo` (motor.md §3.4): un recibo de una serie llega más caro que de costumbre.

Lo habitual sale de la serie calculada **sin** el cargo nuevo (`serie_previa`), con al menos
`MIN_CARGOS_PREVIOS` recibos (2 si es anual), y el cargo tiene que caer en su fecha (`encaja_en_serie`).
Avisa si el importe supera lo habitual en más de `SUBIDA_MIN_EUR` y en más del 8 % (serie fija) o del
25 % (serie variable, como la luz o el agua); si además supera en más de `SUBIDA_MIN_EUR` el último
recibo (serie fija) o el máximo de siempre (variable), para no repetir el aviso con el nivel nuevo; y
si `subida_eur x cargos al año >= SUBIDA_MIN_ANUAL`. Cuándo: el día del cargo. Clave: id del cargo.
El texto dice «ha subido», nunca «te han cobrado de más».
"""

from __future__ import annotations

from decimal import Decimal

from ..enriquecer import centimos, encaja_en_serie, serie_previa
from ..parametros import SubidaRecibo
from . import registrar
from .base import Contexto, Hallazgo


@registrar("subida_recibo", version=1)
def detectar(ctx: Contexto) -> list[Hallazgo]:
    p: SubidaRecibo = ctx.params["subida_recibo"]
    ps = ctx.params["series"]
    hallazgos = []
    for cargo in ctx.nuevos:
        if not (cargo.importe < 0 and cargo.tipo_operacion == "cargo" and cargo.comercio_normalizado):
            continue
        serie = serie_previa(ctx.historial, cargo, ps)
        if serie is None:
            continue
        minimo = p.MIN_CARGOS_PREVIOS_ANUAL if serie.periodo_meses == 12 else p.MIN_CARGOS_PREVIOS
        if serie.veces < minimo or not encaja_en_serie(serie, cargo.fecha, ps):
            continue
        actual, habitual = centimos(abs(cargo.importe)), serie.importe_habitual
        subida = actual - habitual
        pct_min = p.PCT_MIN_FIJO if serie.fijo else p.PCT_MIN_VARIABLE
        referencia = serie.importes[-1] if serie.fijo else max(serie.importes)
        anual = centimos(subida * serie.cargos_al_anio)
        if (subida <= p.SUBIDA_MIN_EUR or actual <= habitual * (1 + pct_min)
                or actual - referencia <= p.SUBIDA_MIN_EUR or anual < p.SUBIDA_MIN_ANUAL):
            continue
        confianza = min(p.CONFIANZA_BASE + 0.10 * max(0, serie.veces - 3), p.CONFIANZA_MAX)
        hallazgos.append(Hallazgo(
            tipo="subida_recibo",
            clave=cargo.id,
            movimientos=[cargo.id],
            confianza=round(confianza, 2),
            impacto_eur=anual,
            datos={
                "comercio": cargo.comercio_normalizado,
                "importe_actual": actual,
                "importe_habitual": habitual,
                "subida_eur": centimos(subida),
                "subida_pct": (subida / habitual * 100).quantize(Decimal("0.1")),
                "serie_id": serie.serie_id,
            },
        ))
    return hallazgos
