"""
`pago_individual` (deudas-casos.md, «Escenarios, transiciones y cuentas con personas»; motor.md §3.1 bis):
un pago con tarjeta que podría haber sido con otros y del que nadie te ha devuelto nada.

No es un detector de «te deben»: es una SEÑAL de lugar y día. Sale como un `Momento` de tipo `gasto_compartido`
con `datos["origen"] = "pago_individual"` y `datos["dudoso"] = True`; el hilo de casos lo recoge (`senal = media`
-> aviso `resumen`; `senal = debil` -> aviso `silencioso`; nunca push). El motor no calcula ni `faltan` ni
`importe_pendiente`: la cuota la fija luego el usuario.

Reglas (todas con parámetros con nombre en `parametros.PagoIndividual`, ajustados al perfil):
1. Pago de tarjeta (no de una serie, no de una persona) de >= `IMPORTE_MIN` (20 € sin perfil; con perfil
   clamp(`umbral_relevante_eur`, 20, 60)).
2. Tipo de comercio de la lista elegible (`restaurante`, `bar`, `ocio`) según `conocimiento.tipo_comercio` (catálogo,
   caché, heurística; aquí nunca hay búsqueda web) o, si el tipo es `desconocido`, la categoría del movimiento
   (`restaurantes`). Un supermercado, una gasolinera, una barbería (`servicios_personales`), un gimnasio...
   no abren nada, ningún día.
3. Día: sábado o domingo -> `senal = media` para restaurante u ocio (`debil` para un bar); viernes ("la noche")
   -> `debil`; entre semana solo cuenta un pago de >= `MULT_ENTRE_SEMANA` x el umbral y es `debil`.
4. Cuándo: el primer `hoy` con `hoy - pago >= DIAS_ESPERA` (el mismo plazo que `gasto_compartido`, para dar tiempo
   a los Bizums) y mientras `hoy - pago <= VENTANA_REEMBOLSO`, y solo si NINGÚN Bizum o transferencia recibidos en la
   ventana pudo ser la parte de alguien (si lo hay, es el `gasto_compartido` normal o una duda suya).
Confianza baja y fija (0,50): nunca llega al 0,7 del módulo, así que no avisa por sí solo.

Lo aprendido (curva de amigos, A3; `compania` en `procesar` y en `Contexto`, calculado fuera del motor):
5. Ámbito: primero el comercio (`"c:<COMERCIO>"`, comercio normalizado) y, si no está, el tipo de sitio y la franja del
   día (`"t:<tipo>|<franja>"`; franja = `laborable`, `viernes` o `finde`; un tipo `desconocido` no es ámbito). El
   comercio manda: «en la cafetería de la uni, siempre solo» pesa más que «los bares entre semana».
6. Si p(acompañado) del ámbito >= `P_ACOMPANADO_MIN` y el pago es de >= `IMPORTE_MIN_APRENDIDA` (cualquier día y
   aunque no llegue a `IMPORTE_MIN`; para el comercio, aunque su tipo no esté en la lista), abre con
   `senal = "aprendida"`, `CONFIANZA_APRENDIDA` y `datos["p_acompanado"]` y `datos["ambito_aprendido"]`. La regla 4
   (espera y Bizums) se aplica igual. Una p baja no quita nada: callar donde va solo lo decide la escalera al abrir
   el caso. Con `compania` None o vacío, todo es idéntico a las reglas 1-4.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from ...plataforma.tipos import MovimientoEnriquecido
from .. import conocimiento
from ..enriquecer import centimos, es_reembolso_entrante
from ..parametros import GastoCompartido, PagoIndividual
from .base import Contexto, Hallazgo

CATEGORIA_A_TIPO = {"restaurantes": "restaurante"}      # `ocio` no: incluye tiendas de deporte, entradas online...
TIPOS_SENAL_MEDIA = ("restaurante", "ocio")
MOTIVO_CON_ALGUIEN = "Pudo ir con alguien y nadie le ha enviado todavía su parte"
MOTIVO_SOLO = "Pudo ir solo: un pago propio sin nada que reclamar"
MOTIVO_APRENDIDA = "Sueles ir acompañado a este sitio y nadie le ha enviado todavía su parte"
CLAVE_COMERCIO, CLAVE_TIPO = "c:", "t:"
FRANJAS = {4: "viernes", 5: "finde", 6: "finde"}       # `date.weekday`; el resto, `laborable` (Franja del contrato)


def tipo_del_pago(m: MovimientoEnriquecido) -> tuple[str, str]:
    """`(tipo, fuente)` del comercio de un pago: catálogo, caché o heurística y, si sigue siendo `desconocido`, la
    categoría del movimiento. Sin red."""
    tipo, fuente = conocimiento.resolver_tipo(m.comercio_normalizado or "", buscar=False, etiquetas=m.etiquetas)
    if tipo == conocimiento.DESCONOCIDO and m.categoria in CATEGORIA_A_TIPO:
        return CATEGORIA_A_TIPO[m.categoria], "categoria"
    return tipo, fuente


def senal_de(fecha: date, tipo: str, importe: Decimal, p: PagoIndividual) -> str | None:
    """`media`, `debil` o None (no abre nada). Supone ya comprobado `importe >= IMPORTE_MIN`."""
    if tipo not in p.TIPOS_ELEGIBLES:
        return None
    dia = fecha.weekday()
    if dia in p.DIAS_FINDE:
        return "media" if tipo in TIPOS_SENAL_MEDIA else "debil"
    if dia in p.DIAS_NOCHE:
        return "debil"
    return "debil" if importe >= p.IMPORTE_MIN * p.MULT_ENTRE_SEMANA else None


def franja_de(fecha: date) -> str:
    """`laborable`, `viernes` o `finde`, solo del día de la semana (el banco no da la hora)."""
    return FRANJAS.get(fecha.weekday(), "laborable")


def _p_valida(valor: object) -> float | None:
    """Una probabilidad en [0, 1] o None (lo que no lo sea se ignora: ni bool, ni texto, ni NaN)."""
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return None
    p = float(valor)
    return p if 0.0 <= p <= 1.0 else None


def ambito_aprendido(compania: dict[str, float] | None, m: MovimientoEnriquecido, tipo: str) -> tuple[str, float] | None:
    """`(clave, p)` del ámbito más concreto con p conocida: el comercio y, si no está, el tipo de sitio y la franja."""
    if not compania:
        return None
    clave = CLAVE_COMERCIO + (m.comercio_normalizado or "")
    p = _p_valida(compania.get(clave))
    if p is not None:
        return clave, p
    if tipo == conocimiento.DESCONOCIDO:
        return None
    clave = f"{CLAVE_TIPO}{tipo}|{franja_de(m.fecha)}"
    p = _p_valida(compania.get(clave))
    return (clave, p) if p is not None else None


def _es_pago_propio(m: MovimientoEnriquecido, p: PagoIndividual, minimo: Decimal | None = None) -> bool:
    minimo = p.IMPORTE_MIN if minimo is None else minimo
    return (m.canal == "tarjeta" and m.tipo_operacion == "cargo" and -m.importe >= minimo
            and m.serie_id is None and bool(m.comercio_normalizado) and "posible_persona" not in m.etiquetas)


def _hallazgo(m: MovimientoEnriquecido, tipo: str, senal: str, p: PagoIndividual,
              aprendido: tuple[str, float] | None = None) -> Hallazgo:
    importe = centimos(-m.importe)
    datos = {
        "origen": "pago_individual",
        "dudoso": True,
        "senal": senal,
        "tipo_comercio": tipo,
        "pago_id": m.id,
        "comercio": m.comercio_normalizado,
        "importe_total": importe,
        "fecha": m.fecha.isoformat(),
        "movimientos": [m.id],
        "hipotesis": [
            {"candidatos": [], "faltan": 0, "motivo": MOTIVO_CON_ALGUIEN},
            {"candidatos": [], "faltan": 0, "motivo": MOTIVO_SOLO},
        ],
    }
    confianza = p.CONFIANZA
    if aprendido:
        datos["ambito_aprendido"], datos["p_acompanado"] = aprendido[0], round(aprendido[1], 3)
        datos["hipotesis"][0]["motivo"] = MOTIVO_APRENDIDA
        confianza = p.CONFIANZA_APRENDIDA
    return Hallazgo(tipo="gasto_compartido", clave=f"individual:{m.id}", movimientos=[m.id],
                    confianza=confianza, datos=datos, impacto_eur=None)


def _hay_bizum_que_encaja(m: MovimientoEnriquecido, entrantes: list[MovimientoEnriquecido], g: GastoCompartido) -> bool:
    """¿Algún Bizum o transferencia recibidos en la ventana del pago pudo ser la parte de alguien? Ante la duda (un
    envío de hasta `PARTE_MAX_PCT` del total), es del otro detector o de otra cosa: aquí, silencio."""
    return any(0 <= (r.fecha - m.fecha).days <= g.VENTANA_REEMBOLSO and r.importe <= -m.importe * g.PARTE_MAX_PCT
               for r in entrantes)


def detectar(ctx: Contexto) -> list[Hallazgo]:
    """No está registrado: lo llama `gasto_compartido.detectar` (mismo tipo de momento, `origen = pago_individual`)."""
    from .gasto_compartido import dias_espera

    p: PagoIndividual = ctx.params["pago_individual"]
    g: GastoCompartido = ctx.params["gasto_compartido"]
    espera = dias_espera(g, ctx.lineas_base.get("retraso_reembolso_p75"))
    desde, hasta = ctx.hoy - timedelta(days=g.VENTANA_REEMBOLSO), ctx.hoy - timedelta(days=espera)
    minimo = min(p.IMPORTE_MIN, p.IMPORTE_MIN_APRENDIDA) if ctx.compania else p.IMPORTE_MIN
    candidatos = [m for m in ctx.historial if desde <= m.fecha <= hasta and _es_pago_propio(m, p, minimo)]
    if not candidatos:
        return []
    entrantes = [r for r in ctx.historial if es_reembolso_entrante(r) and r.fecha >= desde]
    hallazgos = []
    for m in candidatos:
        if _hay_bizum_que_encaja(m, entrantes, g):
            continue
        tipo, _ = tipo_del_pago(m)
        aprendido = ambito_aprendido(ctx.compania, m, tipo)
        if aprendido and aprendido[1] >= p.P_ACOMPANADO_MIN and -m.importe >= p.IMPORTE_MIN_APRENDIDA:
            hallazgos.append(_hallazgo(m, tipo, "aprendida", p, aprendido))
            continue
        if -m.importe < p.IMPORTE_MIN:          # solo entró por el mínimo propio de lo aprendido
            continue
        senal = senal_de(m.fecha, tipo, -m.importe, p)
        if senal:
            hallazgos.append(_hallazgo(m, tipo, senal, p))
    return hallazgos


def tipos_por_buscar(ctx: Contexto) -> list[str]:
    """Nombres de comercio cuyo tipo haría falta y no se conoce: pagos de tarjeta de la ventana, plausibles por día e
    importe, cuyo tipo no está ni en el catálogo ni en la caché (la heurística es el último recurso, después de la
    búsqueda) y con nombre buscable. Solo nombres (nunca importes ni fechas). Los lee el
    orquestador fuera de `procesar` (`motor.tipos_pendientes`) y los resuelve con `conocimiento.tipo_comercio`."""
    p: PagoIndividual = ctx.params["pago_individual"]
    g: GastoCompartido = ctx.params["gasto_compartido"]
    desde = ctx.hoy - timedelta(days=g.VENTANA_REEMBOLSO)
    pendientes: dict[str, None] = {}
    for m in ctx.historial:
        if m.fecha < desde or not _es_pago_propio(m, p) or senal_de(m.fecha, p.TIPOS_ELEGIBLES[0], -m.importe, p) is None:
            continue
        if tipo_del_pago(m)[1] in ("catalogo", "cache"):       # ya está en el catálogo o en la caché: no se busca
            continue
        if conocimiento.es_buscable_tipo(m.comercio_normalizado, m.etiquetas, m.canal):
            pendientes[m.comercio_normalizado] = None
    return list(pendientes)
