"""
Lo que el banco ve sin preguntar (curva-amigos.md §4.1, fuente «Bizums que llegan»; tarea A4b).

Un Bizum o transferencia que llega de una persona en los `VENTANA_REEMBOLSO` días siguientes a un pago con tarjeta en
un sitio elegible (restaurante, bar, ocio...) y que encaja con una cuota de ese pago es una observación, HAYA CASO O
NO y también cuando todos pagaron:

- `bzp:<pago_id>:<clave>` (persona): su retraso real (días del pago al Bizum, sin que nadie se lo pidiera), su canal y
  si redondeó. No se emite si ese Bizum saldó a un deudor de un caso (lo aprende el caso, sin contar dos veces).
- `bzg:<pago_id>` (compañía): fuiste acompañado a ese comercio, tipo de sitio y franja, con quienes pagaron más los
  deudores de los casos de ese pago (en un `gasto_compartido` del motor, los que ya pagaron también son compañeros).
  Se emite cuando ya han pagado todos los que encajan con la cuota o, si no, al cerrarse la ventana. No se emite si
  un caso de ese pago ya enseñó la compañía (`acomp:<caso_id>`).

Emparejar: el pago más reciente de la ventana al que encaja el importe, con las reglas de `motor/reparto.py` (cuota
exacta a max(1 €, 3 %) del total y múltiplos de k personas), pero desde 2 personas (tú y un amigo) y desde
`PagoIndividual.IMPORTE_MIN_APRENDIDA`. Pura, en línea (solo mira el historial hasta hoy) y sin nada por nombre de
comercio. Los conceptos y notas de Bizum nunca se leen.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, timedelta
from decimal import Decimal
from typing import Iterable

from ..motor.detectores.pago_individual import tipo_del_pago
from ..motor.enriquecer import es_reembolso_entrante
from ..motor.normalizar import normalizar
from ..motor.parametros import GastoCompartido, PagoIndividual
from ..motor.reparto import clase_de_importe, cuota_de_referencia, personas_que_encajan
from ..plataforma.tipos import Caso, EventoAmigos, Movimiento, MovimientoEnriquecido

_G = GastoCompartido()
_P = PagoIndividual()
VENTANA = _G.VENTANA_REEMBOLSO              # días tras el pago en los que cuenta un Bizum (7)
DIAS_GRACIA = 2                             # la observación de compañía se emite como tarde hasta 2 días después
PARAMS_REPARTO = replace(_G, PERSONAS_MIN=2)   # tú y un amigo ya es un reparto
REDONDEO_MIN = Decimal("0.10")              # a >= 10 céntimos de la cuota exacta: redondeó
CANALES = {"bizum": "bizum", "transferencia": "transferencia"}


@dataclass(frozen=True)
class Encaje:
    reembolso: MovimientoEnriquecido
    pago: MovimientoEnriquecido
    personas: int                           # del reparto, con quien paga
    cubre: int                              # personas que cubre este envío (k en un múltiplo)
    redondeado: bool


def _enriquecido(m: Movimiento) -> MovimientoEnriquecido:
    return m if isinstance(m, MovimientoEnriquecido) and (m.comercio_normalizado or m.contraparte_normalizada) else normalizar(m)


def es_pago_elegible(m: MovimientoEnriquecido) -> bool:
    """Un pago tuyo con tarjeta en un sitio donde se suele ir con gente (los tipos del `pago_individual`)."""
    if m.canal != "tarjeta" or m.tipo_operacion != "cargo" or -m.importe < _P.IMPORTE_MIN_APRENDIDA:
        return False
    if not m.comercio_normalizado or "posible_persona" in m.etiquetas:
        return False
    tipo, _ = tipo_del_pago(m)
    return tipo in _P.TIPOS_ELEGIBLES


def _exacta(pago: MovimientoEnriquecido, importe: Decimal) -> tuple[int, int, bool] | None:
    """Paso 1 (`reparto.py`): `importe` es la cuota exacta de `pago` entre 2 y 12 personas (a max(1 €, 3 %) del total).
    `(personas, 1, redondeado)` o None."""
    total = -pago.importe
    if importe <= 0 or importe > total * _G.PARTE_MAX_PCT:
        return None
    personas = personas_que_encajan(total, importe, PARAMS_REPARTO)
    if personas is None:
        return None
    return personas, 1, abs(importe - total / personas) >= REDONDEO_MIN


def _con_referencia(pago: MovimientoEnriquecido, importe: Decimal, cuota: Decimal, personas: int
                    ) -> tuple[int, int, bool] | None:
    """Paso 2 (`reparto.py`): redondeo (a <= 1 €) o múltiplo (k x cuota) de la cuota de referencia del pago, la de los
    Bizums que encajaron exactos. Sin referencia no hay múltiplos sueltos: 7,40 € no es «3 x 1/11» de una pizza."""
    if importe <= 0 or importe > -pago.importe * _G.PARTE_MAX_PCT:
        return None
    clase = clase_de_importe(importe, cuota, _G)
    if clase is None or clase[1] > personas - 1:
        return None
    return personas, clase[1], clase[0] == "redondeo" or (clase[0] == "multiplo" and abs(importe - clase[1] * cuota) >= REDONDEO_MIN)


def emparejar(historial: Iterable[Movimiento], hoy: date) -> list[Encaje]:
    """Cada Bizum o transferencia recibidos (hasta hoy) con el pago elegible más reciente de su ventana al que encaja:
    primero por cuota exacta y, los que quedan, por redondeo o múltiplo de la cuota de referencia de ese pago.
    Determinista: el mismo historial da siempre los mismos encajes."""
    desde = hoy - timedelta(days=2 * VENTANA + DIAS_GRACIA)
    movs = [_enriquecido(m) for m in historial if desde <= m.fecha <= hoy]
    pagos = sorted((m for m in movs if es_pago_elegible(m)), key=lambda m: (m.fecha, m.id), reverse=True)
    entrantes = sorted((m for m in movs if es_reembolso_entrante(m)), key=lambda m: (m.fecha, m.id))

    def ventana(r: MovimientoEnriquecido) -> list[MovimientoEnriquecido]:
        return [p for p in pagos if 0 <= (r.fecha - p.fecha).days <= VENTANA]

    salida: list[Encaje] = []
    restantes = []
    for r in entrantes:
        encaje = next((Encaje(r, p, *e) for p in ventana(r) for e in [_exacta(p, r.importe)] if e), None)
        if encaje:
            salida.append(encaje)
        else:
            restantes.append(r)
    referencia: dict[str, tuple[Decimal, int]] = {}
    for e in salida:
        cuotas = [x.reembolso.importe for x in salida if x.pago.id == e.pago.id]
        cuota, _ = cuota_de_referencia(cuotas, _G)
        if cuota is not None:
            referencia[e.pago.id] = (cuota, max(x.personas for x in salida if x.pago.id == e.pago.id))
    for r in restantes:
        encaje = next((Encaje(r, p, *e) for p in ventana(r) if p.id in referencia
                       for e in [_con_referencia(p, r.importe, *referencia[p.id])] if e), None)
        if encaje:
            salida.append(encaje)
    return sorted(salida, key=lambda e: (e.reembolso.fecha, e.reembolso.id))


def _pago_de(caso: Caso) -> str | None:
    valor = caso.hechos.get("pago_id") or caso.hechos.get("movimiento_origen")
    return valor if isinstance(valor, str) else None


def observaciones(historial: list[Movimiento], hoy: date, casos: list[Caso], vistos: Iterable[str] = ()
                  ) -> list[EventoAmigos]:
    """Las observaciones de hoy (personas y compañía) a partir de los Bizums que han llegado. `vistos` son los ids ya
    aprendidos (`AprendizajeAmigos.eventos_vistos`); las ya vistas no se repiten."""
    vistos = set(vistos)
    encajes = emparejar(historial, hoy)
    if not encajes and not casos:
        return []
    saldaron = {d.movimiento_pago for c in casos for d in c.deudores if d.movimiento_pago}
    por_pago: dict[str, list[Caso]] = {}
    for c in casos:
        if _pago_de(c):
            por_pago.setdefault(_pago_de(c), []).append(c)
    eventos: list[EventoAmigos] = []

    # 1. Personas: el Bizum de hoy, con su retraso real y su canal.
    for e in encajes:
        clave = e.reembolso.contraparte_normalizada
        ev_id = f"bzp:{e.pago.id}:{clave}"
        if e.reembolso.fecha != hoy or ev_id in vistos or e.reembolso.id in saldaron:
            continue
        eventos.append(EventoAmigos(id=ev_id, fuente="bizum", fecha=hoy, fecha_pago=e.pago.fecha, contraparte=clave,
                                    retraso_dias=(e.reembolso.fecha - e.pago.fecha).days, tras_pedir=False,
                                    canal=CANALES.get(e.reembolso.canal or "", "bizum"), redondeado=e.redondeado))

    # 2. Compañía: una por pago, cuando ya pagaron todos o al cerrarse la ventana.
    agrupados: dict[str, list[Encaje]] = {}
    for e in encajes:
        agrupados.setdefault(e.pago.id, []).append(e)
    for pago_id, lista in agrupados.items():
        pago = lista[0].pago
        edad = (hoy - pago.fecha).days
        ev_id = f"bzg:{pago_id}"
        propios = por_pago.get(pago_id, [])
        if ev_id in vistos or any(f"acomp:{c.id}" in vistos for c in propios):
            continue
        personas = max(e.personas for e in lista)
        cubiertas = sum(e.cubre for e in lista)
        todos = cubiertas >= personas - 1
        if not (todos or VENTANA <= edad <= VENTANA + DIAS_GRACIA):
            continue
        quienes = {e.reembolso.contraparte_normalizada for e in lista}
        for c in propios:                   # deudores (los que faltan) y quien ya pagó en el caso del motor
            quienes |= {d.contraparte for d in c.deudores}
        tipo, _ = tipo_del_pago(pago)
        eventos.append(EventoAmigos(id=ev_id, fuente="bizum", fecha=hoy, fecha_pago=pago.fecha,
                                    comercio=pago.comercio_normalizado, tipo_comercio=tipo, acompanado=True,
                                    personas=sorted(q for q in quienes if q),
                                    forma="redondeo" if any(e.redondeado for e in lista) else "iguales"))
    return eventos


def sin_repetir(eventos: list[EventoAmigos], caso: Caso, vistos: Iterable[str]) -> list[EventoAmigos]:
    """Quita de lo que enseña un caso lo que ya se aprendió de los Bizums de su pago: la compañía (`bzg:<pago>`) y la
    devolución de cada persona (`bzp:<pago>:<clave>`). Así nada cuenta dos veces."""
    pago_id = _pago_de(caso)
    if not pago_id:
        return eventos
    vistos = set(vistos)
    salida = []
    for ev in eventos:
        if ev.id.startswith("acomp:") and f"bzg:{pago_id}" in vistos:
            continue
        if ev.id.startswith("pago:") and ev.contraparte and f"bzp:{pago_id}:{ev.contraparte}" in vistos:
            continue
        salida.append(ev)
    return salida
