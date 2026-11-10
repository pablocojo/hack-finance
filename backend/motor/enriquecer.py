"""
Enriquecimiento (motor.md §2.2): series recurrentes con `serie_id`, etiquetas y líneas base propias.

Adapta `detectar_recurrentes` del kit a `Decimal` y Python puro (cientos de filas en milisegundos).
Todo es puro: lo que entra es el historial que ya se puede ver (fecha <= hoy); nada mira el futuro.
"""

from __future__ import annotations

import calendar
import math
import re
import statistics
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from ..plataforma.tipos import Movimiento, MovimientoEnriquecido
from . import parametros
from .normalizar import normalizar

CENTIMO = Decimal("0.01")
_MARCADOR_ANUAL = re.compile(r"ANUAL|ANNUAL|YEARLY|12 MESES")


def centimos(valor: Decimal) -> Decimal:
    return Decimal(valor).quantize(CENTIMO, rounding=ROUND_HALF_UP)


@dataclass
class Serie:
    serie_id: str
    comercio: str
    periodo_meses: int
    importe_habitual: Decimal          # mediana, en positivo
    dia_habitual: int
    variacion: float
    veces: int
    ultimo: date
    fijo: bool
    canal: str | None
    categoria: str | None
    ids: list[str] = field(default_factory=list)
    importes: list[Decimal] = field(default_factory=list)   # en positivo, por fecha
    fechas: list[date] = field(default_factory=list)

    @property
    def cargos_al_anio(self) -> int:
        return 12 // self.periodo_meses

    def a_dict(self) -> dict:
        datos = asdict(self)
        datos.update(importe_habitual=str(self.importe_habitual), ultimo=self.ultimo.isoformat(),
                     importes=[str(i) for i in self.importes], fechas=[f.isoformat() for f in self.fechas],
                     cargos_al_anio=self.cargos_al_anio)
        return datos


def _indice_mes(d: date) -> int:
    return d.year * 12 + d.month


def _es_cargo(m: MovimientoEnriquecido) -> bool:
    return m.importe < 0 and m.tipo_operacion == "cargo" and bool(m.comercio_normalizado)


def _dias_del_mes(fechas: list[date]) -> tuple[float, int]:
    """(dispersión, día habitual) del día del mes, en circular: el 30 y el 2 están a 3 días."""
    dias = [f.day for f in fechas]
    girados = [(d + 15) % 31 for d in dias]
    if len(dias) > 1 and statistics.pstdev(girados) < statistics.pstdev(dias):
        habitual = (int(statistics.median(girados)) - 15) % 31 or 31
        return statistics.pstdev(girados), habitual
    return (statistics.pstdev(dias) if len(dias) > 1 else 0.0), int(statistics.median(dias))


def _periodo(fechas: list[date], concepto: str, p: parametros.Series) -> int | None:
    """Periodo en meses (1, 2, 3, 6 o 12). Anual: saltos de 330-400 días (o un cargo con marcador).
    El resto: el salto de meses más común, con hasta `MAX_HUECOS` recibos que faltan (salto doble)."""
    if len(fechas) == 1:
        return 12 if _MARCADOR_ANUAL.search(concepto.upper()) else None
    saltos_dias = [(b - a).days for a, b in zip(fechas, fechas[1:])]
    if all(p.DIAS_ANUAL[0] <= s <= p.DIAS_ANUAL[1] for s in saltos_dias):
        return 12
    meses = sorted({_indice_mes(f) for f in fechas})
    if len(meses) < 2 or len(fechas) / len(meses) > p.MAX_CARGOS_POR_MES:
        return None
    saltos = [b - a for a, b in zip(meses, meses[1:])]
    periodo = min(set(saltos), key=lambda s: (-saltos.count(s), s))
    if periodo not in p.PERIODOS_MESES:
        return None
    huecos = sum(1 for s in saltos if s == 2 * periodo)
    if huecos > p.MAX_HUECOS or any(s not in (periodo, 2 * periodo) for s in saltos):
        return None
    if periodo == 1 and len(meses) < p.MIN_CARGOS_MENSUAL:
        return None
    return periodo


def _serie_de(comercio: str, grupo: list[MovimientoEnriquecido], p: parametros.Series) -> Serie | None:
    importes = [abs(m.importe) for m in grupo]
    fechas = [m.fecha for m in grupo]
    periodo = _periodo(fechas, grupo[0].concepto, p)
    if periodo is None:
        return None
    media = sum(importes) / len(importes)
    variacion = float(Decimal(statistics.pstdev([float(i) for i in importes])) / media) if media else 0.0
    if variacion > p.VARIACION_MAX:
        return None
    dispersion, dia_habitual = _dias_del_mes(fechas)
    if periodo < 12 and dispersion > p.DISPERSION_DIA_MAX:
        return None
    con_tarjeta = all(m.canal == "tarjeta" for m in grupo)
    if con_tarjeta and (variacion > p.VARIACION_FIJO or (periodo < 6 and len(grupo) < p.MIN_CARGOS_TARJETA)):
        return None  # una tienda donde se compra a menudo no es una suscripción
    categorias = [m.categoria for m in grupo if m.categoria]
    return Serie(
        serie_id=f"{comercio}:{periodo}m",
        comercio=comercio,
        periodo_meses=periodo,
        importe_habitual=centimos(Decimal(statistics.median(importes))),
        dia_habitual=dia_habitual,
        variacion=round(variacion, 4),
        veces=len(grupo),
        ultimo=max(fechas),
        fijo=variacion <= p.VARIACION_FIJO,
        canal=grupo[-1].canal,
        categoria=max(set(categorias), key=categorias.count) if categorias else None,
        ids=[m.id for m in grupo],
        importes=[centimos(i) for i in importes],
        fechas=fechas,
    )


def serie_previa(historial: list[MovimientoEnriquecido], cargo: MovimientoEnriquecido,
                 p: parametros.Series | None = None) -> Serie | None:
    """La serie del comercio de `cargo` calculada solo con los cargos anteriores a él (sin él ni lo que
    llegó después). Es «lo habitual» con lo que se compara un recibo nuevo."""
    p = p or parametros.DEFECTO["series"]
    previos = []
    for m in historial:
        if m.id == cargo.id:
            break
        if _es_cargo(m) and m.comercio_normalizado == cargo.comercio_normalizado:
            previos.append(m)
    return _serie_de(cargo.comercio_normalizado, previos, p) if previos else None


def encaja_en_serie(serie: Serie, fecha: date, p: parametros.Series | None = None) -> bool:
    """¿Un cargo en `fecha` es el siguiente de la serie? Un periodo después del último (o dos, si faltó
    uno) y a ±`DIAS_TOLERANCIA_CARGO` de su día; las anuales, a 330-400 días."""
    p = p or parametros.DEFECTO["series"]
    dias = (fecha - serie.ultimo).days
    if serie.periodo_meses == 12:
        return p.DIAS_ANUAL[0] <= dias <= p.DIAS_ANUAL[1]
    for saltos in range(1, p.MAX_HUECOS + 2):
        mes = serie.ultimo.month - 1 + saltos * serie.periodo_meses
        anio, mes = serie.ultimo.year + mes // 12, mes % 12 + 1
        dia = min(serie.dia_habitual, calendar.monthrange(anio, mes)[1])
        if abs((fecha - date(anio, mes, dia)).days) <= p.DIAS_TOLERANCIA_CARGO:
            return True
    return False


def calcular_series(historial: list[MovimientoEnriquecido], p: parametros.Series | None = None) -> dict[str, Serie]:
    """Series recurrentes de cargos, por `comercio_normalizado`."""
    p = p or parametros.DEFECTO["series"]
    grupos: dict[str, list[MovimientoEnriquecido]] = {}
    for m in historial:
        if _es_cargo(m):
            grupos.setdefault(m.comercio_normalizado, []).append(m)
    series = {}
    for comercio, grupo in grupos.items():
        grupo.sort(key=lambda m: m.fecha)
        serie = _serie_de(comercio, grupo, p)
        if serie:
            series[serie.serie_id] = serie
    return series


def es_reembolso_entrante(m: MovimientoEnriquecido) -> bool:
    """Bizum o transferencia recibidos de una persona (no nóminas ni devoluciones)."""
    return (m.importe > 0 and m.canal in ("bizum", "transferencia") and m.tipo_operacion == "cargo"
            and m.contraparte_normalizada is not None and "NOMINA" not in m.concepto.upper())


def enriquecer_normalizados(
    normalizados: list[MovimientoEnriquecido], p: parametros.Series | None = None
) -> tuple[list[MovimientoEnriquecido], dict[str, Serie]]:
    """Pone `serie_id` y etiquetas a movimientos ya normalizados. Devuelve copias y las series."""
    p = p or parametros.DEFECTO["series"]
    series = calcular_series(normalizados, p)
    serie_de_id = {i: s.serie_id for s in series.values() for i in s.ids}
    visto: dict[str, date] = {}
    orden = sorted(range(len(normalizados)), key=lambda i: normalizados[i].fecha)
    nuevo: set[int] = set()
    for i in orden:
        m = normalizados[i]
        if not _es_cargo(m):
            continue
        anterior = visto.get(m.comercio_normalizado)
        if anterior is None or (m.fecha - anterior).days > p.DIAS_COMERCIO_NUEVO:
            nuevo.add(i)
        visto[m.comercio_normalizado] = m.fecha
    salida = []
    for i, m in enumerate(normalizados):
        etiquetas = list(m.etiquetas)
        serie_id = serie_de_id.get(m.id)
        if serie_id:
            etiquetas.append("cargo_serie")
        if i in nuevo:
            etiquetas.append("comercio_nuevo")
        if es_reembolso_entrante(m):
            etiquetas.append("reembolso_entrante")
        salida.append(m.model_copy(update={"serie_id": serie_id, "etiquetas": etiquetas}))
    return salida, series


def enriquecer(movimientos: list[Movimiento]) -> list[MovimientoEnriquecido]:
    """Pura: normaliza y enriquece, en el mismo orden. Las series salen de los propios movimientos."""
    return enriquecer_normalizados([normalizar(m) for m in movimientos])[0]


# --- Líneas base propias (respaldo sin perfil) -----------------------------------------------

def percentil_75(valores: list[int]) -> int | None:
    """Percentil 75 por rango más cercano (entero, sin interpolar)."""
    if not valores:
        return None
    ordenados = sorted(valores)
    return ordenados[max(0, math.ceil(0.75 * len(ordenados)) - 1)]


def lineas_base(historial: list[MovimientoEnriquecido], hoy: date,
                p: parametros.GastoCompartido | None = None) -> dict:
    """`retraso_reembolso_p75` y `repartos` (contrapartes que devolvieron juntas) de los repartos ya cerrados."""
    from .reparto import repartos

    p = p or parametros.DEFECTO["gasto_compartido"]
    cerrados = [r for r in repartos(historial, p).values()
                if r.valido and not r.multiples and not r.empate
                and hoy - r.pago.fecha > timedelta(days=p.VENTANA_REEMBOLSO)]
    retrasos = [(b.fecha - r.pago.fecha).days for r in cerrados for b in r.reembolsos]
    return {
        "retraso_reembolso_p75": percentil_75(retrasos) if len(retrasos) >= p.MIN_RETRASOS_P75 else None,
        "repartos": [sorted({b.contraparte_normalizada for b in r.reembolsos}) for r in cerrados],
    }
