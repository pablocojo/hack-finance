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
2. Tipo de comercio de la lista elegible `PagoIndividual.TIPOS_ELEGIBLES` (toda actividad de ocio o social, K1 c:
   `restaurante`, `bar`, `ocio`, `cine`, `teatro`, `concierto`, `evento`, `actividad`) según `conocimiento.tipo_comercio`
   (catálogo, caché, heurística; aquí nunca hay búsqueda web) o, si el tipo es `desconocido`, la categoría del
   movimiento (`restaurantes`; la de `ocio` no, porque también es gimnasio, viajes o juegos). Un supermercado, una
   gasolinera, una barbería (`servicios_personales`), un gimnasio... no abren nada, ningún día.
3. Día: sábado o domingo -> `senal = media` (`debil` para los `TIPOS_SENAL_DEBIL`: un bar); viernes ("la noche")
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

El precio por persona (K1 d; `conocimiento.precio_persona`, del catálogo o de la caché, nunca de internet aquí):
7. Si el sitio (de un tipo elegible) tiene `precio_persona`, el código estima en local las personas = importe /
   precio: <= 1 + `TOL_PERSONAS` es 1 persona -> SILENCIO (manda sobre las reglas 1-3 y sobre lo aprendido: una sola
   entrada o un solo menú no deja nada que reclamar); >= 2 - `TOL_PERSONAS` son `max(2, redondeo)` personas (hasta
   `PERSONAS_MAX_PRECIO`) -> abre con `senal = media` cualquier día y desde `IMPORTE_MIN_PRECIO`, o refuerza lo que
   abran las reglas (`debil` pasa a `media`; `aprendida` se queda) con `datos["personas_estimadas"]`,
   `datos["precio_persona"]` y `datos["motivo_personas"]` («19,00 € en Cines Fotograma son unas 2 entradas»).
   Entre medias (o sin precio), todo como en las reglas 1-6. La regla 4 (espera y Bizums) se aplica igual.

La tabla de precios (ocio, 11 nov; `motor/ocio.py`, de la caché de la búsqueda web, nunca de internet aquí):
8. Si el sitio (cine, teatro, concierto, evento o actividad) tiene `tabla_precios`, el código aplica el día del pago y
   enumera en local las combinaciones que suman el importe (± 0,05 €): «2 entradas de sábado» o «1 entrada con dos
   palomitas pequeñas», cada una con sus personas. Manda sobre la regla 7. Solo de 1 persona -> SILENCIO; alguna de
   >= 2 -> abre con `senal = media` cualquier día desde `IMPORTE_MIN_PRECIO` (o refuerza), con `datos["ocio"]`
   (combinaciones, día, tarifa, fuentes, consulta y la pregunta sin afirmar). `personas_estimadas` solo si todas las
   combinaciones dicen lo mismo. Si ninguna encaja, la regla 7 y las de siempre. El juicio de la IA (cuál es más
   probable y p de ir acompañado) lo añade el orquestador fuera de `procesar` (`ocio.anotar_momento`).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from ...plataforma.tipos import MovimientoEnriquecido
from .. import conocimiento, ocio
from ..enriquecer import centimos, es_reembolso_entrante
from ..formato import eur
from ..parametros import GastoCompartido, PagoIndividual
from .base import Contexto, Hallazgo

CATEGORIA_A_TIPO = {"restaurantes": "restaurante"}      # `ocio` no: incluye gimnasios, viajes, juegos...
MOTIVO_CON_ALGUIEN = "Pudo ir con alguien y nadie le ha enviado todavía su parte"
MOTIVO_SOLO = "Pudo ir solo: un pago propio sin nada que reclamar"
MOTIVO_APRENDIDA = "Sueles ir acompañado a este sitio y nadie le ha enviado todavía su parte"
MOTIVO_PRECIO = "Por el importe fueron unas {n} personas y nadie le ha enviado todavía su parte"
MOTIVO_TABLA = "Por la tabla de precios del sitio pudieron ser {n} personas y nadie le ha enviado todavía su parte"
TIPOS_CON_ENTRADA = ("cine", "teatro", "concierto", "evento", "actividad")   # «son unas 2 entradas»; si no, «personas»
CLAVE_COMERCIO, CLAVE_TIPO = "c:", "t:"
FRANJAS = {4: "viernes", 5: "finde", 6: "finde"}       # `date.weekday`; el resto, `laborable` (Franja del contrato)


@dataclass(frozen=True)
class Estimacion:
    """Cuántas personas explica el importe con el precio por persona del sitio (regla 7)."""
    personas: int
    precio: Decimal
    motivo: str


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
        return "debil" if tipo in p.TIPOS_SENAL_DEBIL else "media"
    if dia in p.DIAS_NOCHE:
        return "debil"
    return "debil" if importe >= p.IMPORTE_MIN * p.MULT_ENTRE_SEMANA else None


def franja_de(fecha: date) -> str:
    """`laborable`, `viernes` o `finde`, solo del día de la semana (el banco no da la hora)."""
    return FRANJAS.get(fecha.weekday(), "laborable")


def _nombre_visible(comercio: str | None) -> str:
    from ..razonador import nombre_visible         # aquí dentro: el razonador importa los detectores

    return nombre_visible(comercio)


def estimar_personas(importe: Decimal, tipo: str, precio: Decimal | None, comercio: str | None,
                     p: PagoIndividual) -> Estimacion | None:
    """Regla 7, en local y con `Decimal`: personas ≈ importe / precio por persona. None si no hay precio, el tipo no
    es elegible o el importe cae entre 1 y 2 personas (ambiguo) o por encima de `PERSONAS_MAX_PRECIO`."""
    if precio is None or precio <= 0 or tipo not in p.TIPOS_ELEGIBLES:
        return None
    ratio = importe / precio
    if ratio <= 1 + p.TOL_PERSONAS:
        personas = 1
    elif ratio >= 2 - p.TOL_PERSONAS:
        personas = max(2, int(ratio.quantize(Decimal("1"), rounding=ROUND_HALF_UP)))
        if personas > p.PERSONAS_MAX_PRECIO:
            return None
    else:
        return None
    sitio = _nombre_visible(comercio)
    if tipo in TIPOS_CON_ENTRADA:
        cuantas = "una entrada" if personas == 1 else f"unas {personas} entradas"
        motivo = f"{eur(importe)} en {sitio} {'es' if personas == 1 else 'son'} {cuantas}"
    else:
        cuantas = "una persona" if personas == 1 else f"unas {personas} personas"
        motivo = f"{eur(importe)} en {sitio} dan para {cuantas} (unos {eur(precio)} por persona)"
    return Estimacion(personas=personas, precio=precio, motivo=motivo)


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


def estimar_por_tabla(importe: Decimal, ocio_datos: dict, comercio: str | None) -> Estimacion | None:
    """Regla 8: `personas_estimadas` solo si todas las combinaciones de la tabla dicen el mismo número (>= 2); el
    motivo enseña las dos primeras opciones («21,80 € en Kinepolis...: 2 entradas de sábado (...) o 1 entrada...»)."""
    lista = ocio_datos.get("combinaciones", [])
    personas = {c["personas"] for c in lista}
    if len(personas) != 1 or min(personas) < 2:
        return None
    primera = lista[0]
    precio = (Decimal(str(primera["importe"])) / primera["personas"]).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return Estimacion(personas=primera["personas"], precio=precio, motivo=motivo_tabla(importe, ocio_datos, comercio))


def motivo_tabla(importe: Decimal, ocio_datos: dict, comercio: str | None) -> str:
    lista = ocio_datos.get("combinaciones", [])
    con = next((c for c in lista if c["personas"] >= 2), None)
    otra = ocio.alternativa(lista, con) if con else None
    que = " o ".join(c["descripcion"] for c in ([con, otra] if otra else lista[:2]) if c)
    return f"{eur(importe)} en {_nombre_visible(comercio)} pueden ser {que}"


def _hallazgo(m: MovimientoEnriquecido, tipo: str, senal: str, p: PagoIndividual,
              aprendido: tuple[str, float] | None = None, estimacion: Estimacion | None = None,
              ocio_datos: dict | None = None) -> Hallazgo:
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
    if estimacion:                              # siempre de >= 2 personas: con 1 no se abre nada
        datos["personas_estimadas"] = estimacion.personas
        datos["precio_persona"] = estimacion.precio
        datos["motivo_personas"] = estimacion.motivo
        if not aprendido:
            datos["hipotesis"][0]["motivo"] = MOTIVO_PRECIO.format(n=estimacion.personas)
        confianza = max(confianza, p.CONFIANZA_PRECIO)
    if ocio_datos:                              # regla 8: siempre con alguna combinación de >= 2 personas
        datos["ocio"] = ocio_datos
        datos.setdefault("motivo_personas", motivo_tabla(importe, ocio_datos, m.comercio_normalizado))
        if not aprendido:
            n = next(c["personas"] for c in ocio_datos["combinaciones"] if c["personas"] >= 2)
            datos["hipotesis"][0]["motivo"] = MOTIVO_TABLA.format(n=n)
        confianza = max(confianza, p.CONFIANZA_PRECIO)
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
    minimos = [p.IMPORTE_MIN, p.IMPORTE_MIN_PRECIO] + ([p.IMPORTE_MIN_APRENDIDA] if ctx.compania else [])
    candidatos = [m for m in ctx.historial if desde <= m.fecha <= hasta and _es_pago_propio(m, p, min(minimos))]
    if not candidatos:
        return []
    entrantes = [r for r in ctx.historial if es_reembolso_entrante(r) and r.fecha >= desde]
    hallazgos = []
    for m in candidatos:
        if _hay_bizum_que_encaja(m, entrantes, g):
            continue
        importe = -m.importe
        tipo, _ = tipo_del_pago(m)
        estimacion, ocio_datos = None, None
        if tipo in p.TIPOS_ELEGIBLES:
            # regla 8: la tabla de precios del sitio (caché de la búsqueda web, sin red) con el día del pago
            ocio_datos = ocio.analizar_pago(importe, m.comercio_normalizado, tipo, m.fecha)
            if ocio_datos is not None:
                if max(ocio_datos["personas_posibles"]) < 2:
                    continue                    # todas las combinaciones son de una persona: nada que reclamar
                estimacion = estimar_por_tabla(importe, ocio_datos, m.comercio_normalizado)
            else:                               # regla 7: precio por persona del catálogo o la caché, sin red
                estimacion = estimar_personas(importe, tipo, conocimiento.precio_persona(m.comercio_normalizado or ""),
                                              m.comercio_normalizado, p)
                if estimacion and estimacion.personas == 1:
                    continue                    # una entrada o un menú: nada que reclamar
        aprendido = ambito_aprendido(ctx.compania, m, tipo)
        if aprendido and aprendido[1] >= p.P_ACOMPANADO_MIN and importe >= p.IMPORTE_MIN_APRENDIDA:
            hallazgos.append(_hallazgo(m, tipo, "aprendida", p, aprendido, estimacion, ocio_datos))
            continue
        senal = senal_de(m.fecha, tipo, importe, p) if importe >= p.IMPORTE_MIN else None
        if (estimacion or ocio_datos) and importe >= p.IMPORTE_MIN_PRECIO:
            senal = "media"                     # >= 2 personas: abre cualquier día o refuerza un `debil`
        if senal:
            hallazgos.append(_hallazgo(m, tipo, senal, p, None, estimacion, ocio_datos))
    return hallazgos


def precios_por_buscar(ctx: Contexto) -> list[str]:
    """Nombres de sitios con entrada (cine, teatro...) de pagos propios de la ventana cuyo tipo ya se conoce y que aún
    no tienen tabla de precios. Solo nombres: el orquestador, fuera de `procesar`, llama a `ocio.buscar_tabla`."""
    p: PagoIndividual = ctx.params["pago_individual"]
    g: GastoCompartido = ctx.params["gasto_compartido"]
    desde = ctx.hoy - timedelta(days=g.VENTANA_REEMBOLSO)
    pendientes: dict[str, None] = {}
    for m in ctx.historial:
        if m.fecha < desde or not _es_pago_propio(m, p, p.IMPORTE_MIN_PRECIO) or m.comercio_normalizado in pendientes:
            continue
        sin_tabla = tipo_del_pago(m)[0] in ocio.TIPOS_CON_TABLA and ocio.tabla_de(m.comercio_normalizado) is None
        if sin_tabla and conocimiento.es_buscable_tipo(m.comercio_normalizado, m.etiquetas, m.canal):
            pendientes[m.comercio_normalizado] = None
    return list(pendientes)


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
