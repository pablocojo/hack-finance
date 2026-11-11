"""
Cierre de casos: un Bizum o transferencia ENTRANTE de la misma contraparte (clave normalizada, p. ej.
`MARCOS R`) por la cuota ±0,50 €, en cualquier fecha posterior al pago y con cualquier concepto, salda al
deudor. El concepto o la nota del movimiento NO se usan para decidir (son datos de un tercero).

Si todos los deudores quedan saldados, el caso pasa a `saldado` y no avisa más; si entra antes de
`avisar_desde`, se salda sin avisar. Es en línea: solo mira los movimientos que se le pasan (los del día).
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from ..motor.normalizar import normalizar
from ..plataforma.reloj import ahora_por_defecto
from ..plataforma.tipos import Caso, Movimiento, MovimientoEnriquecido
from .ciclo import (ABIERTOS, CERRADOS, CLAVE_DESCARTADOS, TIPO_BIZUM_NO_ENCAJA, TOLERANCIA, _a_fecha, _anotar, _copia, _eur_corto, _nombre_comercio,
                    eur_texto, nombre_visible)

IMPORTE_MIN_PREGUNTA = Decimal("1.00")
VECES_CUOTA_MAX = Decimal("2")                # por encima de 2 cuotas ya no parece lo mismo: no se pregunta


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


def pregunta_pendiente(caso: Caso, tipo: str | None = None) -> bool:
    """¿El caso espera una respuesta del usuario sobre un Bizum (o sobre un caso dudoso, si `tipo` es None)?"""
    pregunta = caso.hechos.get("pregunta")
    return (isinstance(pregunta, dict) and pregunta.get("estado") == "pendiente"
            and (tipo is None or pregunta.get("tipo") == tipo))


def preguntar_no_encaja(caso: Caso, movimientos: list[Movimiento], hoy: date, ahora: datetime | None = None,
                        excluir: frozenset[str] | set[str] = frozenset()) -> Caso:
    """Un Bizum de alguien que DEBE en este caso y que no entra en el margen (25 € por 24 €, 10 € por 24 €) no deja la
    deuda en el aire: el caso guarda una pregunta pendiente («Marcos te ha enviado 25 €: ¿es lo de La Tasca (24 €)?»)
    con las cifras del código. Sin notificación (sale en el Resumen) y, mientras esté pendiente, el portero no recuerda
    nada a esa persona. Una sola pregunta por caso; no repite un Bizum que el usuario ya dijo que era otra cosa. El
    concepto o la nota del Bizum nunca se leen. `excluir` son los ids ya usados por otra cosa hoy."""
    if caso.estado not in ABIERTOS or caso.estado == "dudoso" or not caso.deudores or pregunta_pendiente(caso):
        return caso
    ya_usados = {str(x) for x in caso.hechos.get("movimientos", [])} | {str(x) for x in caso.hechos.get(CLAVE_DESCARTADOS, [])}
    desde = _a_fecha(caso.hechos.get("fecha")) or caso.creado
    libres = [e for e in pagos_entrantes(movimientos)
              if e.id not in ya_usados and e.id not in excluir and desde <= e.fecha <= hoy]
    for deudor in caso.deudores:
        if deudor.estado == "saldada":
            continue
        candidatos = [e for e in libres
                      if e.contraparte_normalizada == deudor.contraparte and abs(e.importe - deudor.cuota) > TOLERANCIA
                      and IMPORTE_MIN_PREGUNTA <= e.importe <= deudor.cuota * VECES_CUOTA_MAX]
        if not candidatos:
            continue
        pago = min(candidatos, key=lambda e: (abs(e.importe - deudor.cuota), e.fecha, e.id))
        nombre = nombre_visible(deudor.contraparte).split()[0]
        texto = (f"{nombre} te ha enviado {_eur_corto(pago.importe)}: "
                 f"¿es lo de {_nombre_comercio(caso.hechos.get('comercio'))} ({_eur_corto(deudor.cuota)})?")
        nuevo = _copia(caso)
        nuevo.hechos["pregunta"] = {"tipo": TIPO_BIZUM_NO_ENCAJA, "texto": texto, "candidatos": [deudor.contraparte],
                                    "preguntada": hoy.isoformat(), "estado": "pendiente", "movimiento": pago.id,
                                    "contraparte": deudor.contraparte, "importe": eur_texto(pago.importe),
                                    "fecha": pago.fecha.isoformat(), "cuota": eur_texto(deudor.cuota)}
        _anotar(nuevo, "codigo", f"Bizum de {nombre_visible(deudor.contraparte)} que no encaja con su cuota: se pregunta "
                                 "en el Resumen y no se le recuerda mientras tanto.", ahora or ahora_por_defecto(hoy))
        return nuevo
    return caso


def saldar_casos(casos: list[Caso], movimientos: list[Movimiento], hoy: date,
                 ahora: datetime | None = None) -> list[Caso]:
    """`saldar_con_movimientos` sobre una lista, en el mismo orden. Después, los Bizums de quien debe que no han saldado
    a nadie y no entran en el margen abren una pregunta (`preguntar_no_encaja`), una sola vez por Bizum."""
    if not movimientos:
        return list(casos)
    saldados = [saldar_con_movimientos(c, movimientos, hoy, ahora) for c in casos]
    usados = {d.movimiento_pago for c in saldados for d in c.deudores if d.movimiento_pago}
    salida = []
    for c in saldados:
        c = preguntar_no_encaja(c, movimientos, hoy, ahora, usados)
        pregunta = c.hechos.get("pregunta")
        if isinstance(pregunta, dict) and pregunta.get("tipo") == TIPO_BIZUM_NO_ENCAJA and pregunta.get("preguntada") == hoy.isoformat():
            usados = usados | {str(pregunta.get("movimiento"))}
        salida.append(c)
    return salida


__all__ = ["pagos_entrantes", "saldar_con_movimientos", "saldar_casos", "preguntar_no_encaja", "pregunta_pendiente",
           "TIPO_BIZUM_NO_ENCAJA", "CLAVE_DESCARTADOS"]
