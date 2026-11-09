"""
`cargo_duplicado` (motor.md §3.2): el mismo comercio cobra dos veces el mismo importe en pocos días.

Par: cargo nuevo B (llega hoy) y el cargo anterior A más cercano del mismo comercio e importe al
céntimo, con `0 <= B - A <= VENTANA_DIAS`, sin un abono igual entre los dos.
No avisa: verificaciones y abonos (solo `cargo`), canales que no son tarjeta o recibo, tarjeta por
debajo de `IMPORTE_MIN_TARJETA` (el umbral que el perfil baja en M9), categorías excluidas
(`transporte`), el patrón habitual (el mismo par ya pasó antes: dos cuotas de gimnasio cada mes) y las
compras frecuentes (>= 8 en 30 días con tarjeta y < 50 €: el menú del día).
Cuándo: el día que entra B. Solo mira `ctx.historial` (fecha <= hoy).
"""

from __future__ import annotations

from datetime import timedelta

from ..enriquecer import centimos
from ..parametros import CargoDuplicado
from ...plataforma.tipos import MovimientoEnriquecido
from . import registrar
from .base import Contexto, Hallazgo


def _es_cargo(m: MovimientoEnriquecido) -> bool:
    return m.importe < 0 and m.tipo_operacion == "cargo" and bool(m.comercio_normalizado)


def _candidato(b: MovimientoEnriquecido, p: CargoDuplicado) -> bool:
    if not _es_cargo(b) or b.canal not in p.CANALES or (b.categoria or "") in p.CATEGORIAS_EXCLUIDAS:
        return False
    minimo = p.IMPORTE_MIN_RECIBO if b.canal == "recibo" else p.IMPORTE_MIN_TARJETA
    return abs(b.importe) >= minimo


def _hay_pares(cargos: list[MovimientoEnriquecido], dias: int) -> bool:
    return any((y.fecha - x.fecha).days <= dias for x, y in zip(cargos, cargos[1:]))


def _confianza(a: MovimientoEnriquecido, b: MovimientoEnriquecido, p: CargoDuplicado) -> float:
    if a.serie_id or b.serie_id:
        return p.CONFIANZA_SERIE
    if b.canal == "recibo":
        return p.CONFIANZA_RECIBO
    return p.CONFIANZA_TARJETA_MISMO_DIA if a.fecha == b.fecha else p.CONFIANZA_TARJETA_OTRO_DIA


@registrar("cargo_duplicado", version=1)
def detectar(ctx: Contexto) -> list[Hallazgo]:
    p: CargoDuplicado = ctx.params["cargo_duplicado"]
    posicion = {m.id: i for i, m in enumerate(ctx.historial)}
    hallazgos = []
    for b in ctx.nuevos:
        if not _candidato(b, p):
            continue
        mismo_comercio = [m for m in ctx.historial if m.comercio_normalizado == b.comercio_normalizado]
        iguales = [m for m in mismo_comercio if _es_cargo(m) and m.importe == b.importe
                   and posicion[m.id] < posicion[b.id]]
        if not iguales or not 0 <= (b.fecha - iguales[-1].fecha).days <= p.VENTANA_DIAS:
            continue
        a = iguales[-1]
        abono = any(m.importe == -b.importe and a.fecha <= m.fecha <= b.fecha for m in mismo_comercio)
        habitual = _hay_pares(iguales[:-1], p.VENTANA_DIAS)          # el mismo par ya pasó antes
        desde = b.fecha - timedelta(days=p.DIAS_FRECUENCIA)
        frecuente = (b.canal == "tarjeta" and abs(b.importe) < p.IMPORTE_FRECUENTE_MAX and
                     sum(1 for m in mismo_comercio if _es_cargo(m) and desde < m.fecha <= b.fecha)
                     >= p.COMPRAS_FRECUENTES)
        if abono or habitual or frecuente:
            continue
        importe = centimos(abs(b.importe))
        datos = {
            "comercio": b.comercio_normalizado,
            "importe": importe,
            "fechas": [a.fecha.isoformat(), b.fecha.isoformat()],
            "ids": [a.id, b.id],
            "id_segundo": b.id,
            "dias_entre": (b.fecha - a.fecha).days,
            "canal": b.canal,
        }
        if b.canal == "recibo":
            datos["fecha_limite_devolucion"] = (b.fecha + timedelta(weeks=p.SEMANAS_DEVOLUCION_RECIBO)).isoformat()
        if a.serie_id or b.serie_id:
            datos["serie_id"] = a.serie_id or b.serie_id
        hallazgos.append(Hallazgo(
            tipo="cargo_duplicado",
            clave=f"{a.id}|{b.id}",
            movimientos=[a.id, b.id],
            confianza=_confianza(a, b, p),
            impacto_eur=importe,
            datos=datos,
        ))
    return hallazgos
