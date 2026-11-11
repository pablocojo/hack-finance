"""
`gasto_compartido` por el grupo habitual aprendido (curva de amigos A3b; motor.md §8 septies).

Pagaste algo en un sitio donde Meisam ya sabe con quién sueles ir (`grupos` en `procesar`, calculado fuera del
motor), parte del grupo te ha devuelto su cuota y falta alguien. Las reglas de siempre callan aquí: el
`gasto_compartido` de siempre pide >= 2 Bizums y >= `IMPORTE_MIN_PAGO`, y `pago_individual` calla en cuanto hay un
Bizum que pudo ser la parte de alguien. Sale como el `gasto_compartido` de siempre (cuota común, `faltan`,
`candidatos`), con `datos["origen"] = "grupo_habitual"`, `datos["ambito_aprendido"]` y `datos["motivo_grupo"]`.

Reglas (parámetros con nombre en `parametros.GastoCompartido`):
1. Pago propio con tarjeta (no de una serie ni de una persona) de >= `IMPORTE_MIN_APRENDIDA`, en la ventana, y sin
   reparto propio (válido o desigual) en `reparto.repartos`: ese lo sigue decidiendo el detector de siempre.
2. Ámbito, como `pago_individual`: el comercio (`"c:<COMERCIO>"`) y, si no tiene grupo, el tipo de sitio y la franja
   (`"t:<tipo>|<franja>"`; un tipo `desconocido` no es ámbito). El grupo: los miembros con frecuencia >=
   `FRECUENCIA_MIN_GRUPO`; hacen falta >= `MIN_MIEMBROS_GRUPO` (con un solo amigo, si paga, no falta nadie).
3. Reparto a partes iguales entre el grupo y el usuario (n = miembros + 1). Un Bizum encaja si es la cuota de n con el
   redondeo de `reparto.clase_de_importe` (<= `TOL_REDONDEO_EUR`) y ningún otro número de personas (2 a
   `PERSONAS_MAX`) lo explica igual de bien. Cada Bizum va al pago más reciente de su ventana con el que encaja o, si
   no encaja con ninguno, al más reciente en cuyo grupo está quien lo envía; nunca uno que ya es la parte de otro pago.
4. Abre si al menos un miembro ha enviado su cuota (una sola vez), ningún miembro ha enviado algo que no encaja (un
   múltiplo, o la cuota de otro número de personas: «esta vez fuimos dos»), nadie de fuera del grupo ha enviado una
   cuota (el grupo no fue el de siempre) y falta >= 1 miembro. Ante cualquier duda, silencio.
5. Cuándo: como el `gasto_compartido` de siempre (espera = p75 propio + 1, entre 2 y 5; al menos
   `MIN_DIAS_DESDE_ULTIMO` desde el último Bizum; hasta `VENTANA_REEMBOLSO`). Y solo si algún Bizum llegó antes de
   que `pago_individual` decidiera (su misma espera): si no, ese pago ya pudo abrir «¿fuiste con alguien?» y no se
   abre un segundo caso sobre el mismo cargo.
`faltan` y `candidatos` son los miembros que faltan (aprendidos, no adivinados), con la cuota del código (la de los
Bizums que cuadran con el total, como en `reparto.py`, o total / n, al céntimo). Solo mira el pasado: el historial llega cortado en `hoy`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal

from ...plataforma.tipos import MovimientoEnriquecido
from .. import conocimiento
from ..enriquecer import centimos, es_reembolso_entrante
from ..formato import eur, nombre_persona
from ..parametros import GastoCompartido
from ..reparto import Reparto, clase_de_importe, cuota_de_referencia, personas_que_encajan
from .base import Contexto, Hallazgo
from .pago_individual import CLAVE_COMERCIO, CLAVE_TIPO, franja_de, tipo_del_pago

ORIGEN = "grupo_habitual"


@dataclass
class _Candidato:
    pago: MovimientoEnriquecido
    orden: int
    ambito: str
    miembros: dict[str, float]
    recibidos: list[MovimientoEnriquecido] = field(default_factory=list)

    @property
    def total(self) -> Decimal:
        return -self.pago.importe

    @property
    def personas(self) -> int:
        return len(self.miembros) + 1


def _miembros(valor: dict[str, float] | None, g: GastoCompartido) -> dict[str, float]:
    return {c: f for c, f in (valor or {}).items() if f >= g.FRECUENCIA_MIN_GRUPO}


def grupo_de(ctx: Contexto, m: MovimientoEnriquecido) -> tuple[str, dict[str, float]] | None:
    """`(ámbito, {miembro: frecuencia})` del grupo habitual del pago: el del comercio y, si no hay, el del tipo de sitio
    y la franja. Solo miembros con frecuencia >= `FRECUENCIA_MIN_GRUPO`. None sin `grupos` o sin grupo para el pago."""
    if not ctx.grupos:
        return None
    g: GastoCompartido = ctx.params["gasto_compartido"]
    clave = CLAVE_COMERCIO + (m.comercio_normalizado or "")
    miembros = _miembros(ctx.grupos.get(clave), g)
    if miembros:
        return clave, miembros
    tipo, _ = tipo_del_pago(m)
    if tipo == conocimiento.DESCONOCIDO:
        return None
    clave = f"{CLAVE_TIPO}{tipo}|{franja_de(m.fecha)}"
    miembros = _miembros(ctx.grupos.get(clave), g)
    return (clave, miembros) if miembros else None


def ordenados(miembros: dict[str, float]) -> list[str]:
    """De quien más va a quien menos (y por clave, para que el orden sea estable)."""
    return sorted(miembros, key=lambda c: (-miembros[c], c))


def encaja(importe: Decimal, total: Decimal, personas: int, g: GastoCompartido) -> bool:
    """¿`importe` es la cuota de un reparto a partes iguales de `total` entre `personas` (con el redondeo de
    `reparto.clase_de_importe`) y ningún otro número de personas lo explica igual de bien?"""
    if personas < 2:
        return False
    cuota = total / personas
    clase = clase_de_importe(importe, centimos(cuota), g)
    if clase is None or clase[1] != 1:
        return False
    distancia = abs(importe - cuota)
    return all(abs(importe - total / otro) > distancia for otro in range(2, g.PERSONAS_MAX + 1) if otro != personas)


def _unir(nombres: list[str]) -> str:
    return nombres[0] if len(nombres) == 1 else ", ".join(nombres[:-1]) + " y " + nombres[-1]


def motivo(miembros: dict[str, float], pagadores: list[str]) -> str:
    """«Sueles ir con Marcos B. y Rodrigo S.; Marcos B. ya te ha pagado» (frase del código, sin notas de Bizum)."""
    quienes = _unir([nombre_persona(c) for c in pagadores])
    verbo = "ha" if len(pagadores) == 1 else "han"
    return f"Sueles ir con {_unir([nombre_persona(c) for c in ordenados(miembros)])}; {quienes} ya te {verbo} pagado"


def _es_pago_propio(m: MovimientoEnriquecido, g: GastoCompartido) -> bool:
    return (m.canal == "tarjeta" and m.tipo_operacion == "cargo" and -m.importe >= g.IMPORTE_MIN_APRENDIDA
            and m.serie_id is None and bool(m.comercio_normalizado) and "posible_persona" not in m.etiquetas)


def _asignar(candidatos: list[_Candidato], entrantes: list[MovimientoEnriquecido], g: GastoCompartido) -> None:
    """Cada Bizum al pago más reciente de su ventana con el que encaja o, si no, al más reciente en cuyo grupo está
    quien lo envía (para que un envío que no encaja deje ese pago en silencio). El resto no es de ninguno."""
    for r in entrantes:
        en_ventana = sorted((c for c in candidatos if 0 <= (r.fecha - c.pago.fecha).days <= g.VENTANA_REEMBOLSO),
                            key=lambda c: (c.pago.fecha, c.orden), reverse=True)
        destino = next((c for c in en_ventana if encaja(r.importe, c.total, c.personas, g)), None)
        if destino is None:
            destino = next((c for c in en_ventana if r.contraparte_normalizada in c.miembros), None)
        if destino is not None:
            destino.recibidos.append(r)


def detectar(ctx: Contexto, todos: dict[str, Reparto]) -> list[Hallazgo]:
    """Lo llama `gasto_compartido.detectar` con sus repartos (mismo tipo de momento). Sin `grupos`, nada."""
    if not ctx.grupos:
        return []
    from .gasto_compartido import dias_espera        # aquí dentro: gasto_compartido importa este módulo

    g: GastoCompartido = ctx.params["gasto_compartido"]
    espera = dias_espera(g, ctx.lineas_base.get("retraso_reembolso_p75"))
    desde, hasta = ctx.hoy - timedelta(days=g.VENTANA_REEMBOLSO), ctx.hoy - timedelta(days=espera)
    con_reparto = {pid for pid, rep in todos.items() if rep.valido or rep.desigual}
    candidatos: list[_Candidato] = []
    for i, m in enumerate(ctx.historial):
        if not desde <= m.fecha <= hasta or m.id in con_reparto or not _es_pago_propio(m, g):
            continue
        grupo = grupo_de(ctx, m)
        if grupo is not None and len(grupo[1]) >= g.MIN_MIEMBROS_GRUPO:
            candidatos.append(_Candidato(pago=m, orden=i, ambito=grupo[0], miembros=grupo[1]))
    if not candidatos:
        return []
    propios = {c.pago.id for c in candidatos}
    ocupados = {r.id for pid, rep in todos.items() if pid not in propios for r in rep.reembolsos}
    entrantes = [r for r in ctx.historial if es_reembolso_entrante(r) and r.fecha >= desde]
    _asignar(candidatos, [r for r in entrantes if r.id not in ocupados], g)
    hallazgos = []
    for c in candidatos:
        hallazgo = _hallazgo(ctx, c, entrantes, espera, g)
        if hallazgo is not None:
            hallazgos.append(hallazgo)
    return hallazgos


def _hallazgo(ctx: Contexto, c: _Candidato, entrantes: list[MovimientoEnriquecido], espera: int,
              g: GastoCompartido) -> Hallazgo | None:
    from .gasto_compartido import _confianza, _entrada

    if not c.recibidos:
        return None
    pagan = [r for r in c.recibidos if r.contraparte_normalizada in c.miembros]
    if len(pagan) < len(c.recibidos):                                # alguien de fuera pagó una cuota: otro grupo
        return None
    if not all(encaja(r.importe, c.total, c.personas, g) for r in pagan):
        return None                                                  # un múltiplo o el reparto de otro número
    pagadores = [r.contraparte_normalizada for r in pagan]
    if len(set(pagadores)) < len(pagadores):                         # dos envíos de la misma persona: ¿cubre a otro?
        return None
    faltan = [m for m in ordenados(c.miembros) if m not in pagadores]
    if not faltan:
        return None
    if (ctx.hoy - max(r.fecha for r in pagan)).days < g.MIN_DIAS_DESDE_ULTIMO:
        return None
    decide_individual = c.pago.fecha + timedelta(days=espera)       # el día en que `pago_individual` decidió
    if not any(c.pago.fecha <= r.fecha <= decide_individual and r.importe <= c.total * g.PARTE_MAX_PCT
               for r in entrantes):
        return None
    exactos = [r.importe for r in pagan if personas_que_encajan(c.total, r.importe, g) == c.personas]
    cuota = cuota_de_referencia(exactos, g)[0] if exactos else centimos(c.total / c.personas)
    pendiente = centimos(len(faltan) * cuota)
    reparto = Reparto(pago=c.pago, reembolsos=pagan, cuota=cuota, personas=c.personas, faltan=len(faltan),
                      valido=True, cuadra=abs(c.total - c.personas * cuota) <= Decimal("0.05") * c.personas)
    datos = {
        "origen": ORIGEN,
        "pago_id": c.pago.id,
        "comercio": c.pago.comercio_normalizado,
        "importe_total": centimos(c.total),
        "fecha": c.pago.fecha.isoformat(),
        "reembolsos": [_entrada(r) for r in pagan],
        "personas_estimadas": c.personas,
        "faltan": len(faltan),
        "importe_pendiente": pendiente,
        "candidatos": [{"contraparte": m, "importe": cuota} for m in faltan],
        "cuota": cuota,
        "ambito_aprendido": c.ambito,
        "grupo_aprendido": {m: round(c.miembros[m], 3) for m in ordenados(c.miembros)},
        "motivo_grupo": motivo(c.miembros, pagadores),
    }
    return Hallazgo(tipo="gasto_compartido", clave=c.pago.id, movimientos=[c.pago.id, *(r.id for r in pagan)],
                    confianza=_confianza(reparto, True, g), impacto_eur=pendiente, datos=datos)


def frase_explicacion(d: dict) -> str:
    """La explicación de una frase (la usa el razonador): «Pagaste 27,00 € en Pizzeria Napoli y sueles ir con Marcos
    B. y Rodrigo S.: Marcos B. ya te ha pagado y falta Rodrigo S. (9,00 €)»."""
    from ..razonador import nombre_visible          # aquí dentro: el razonador importa los detectores

    miembros = d.get("grupo_aprendido") or {}
    pagadores = [r["contraparte"] for r in d.get("reembolsos", [])]
    faltan = [x["contraparte"] for x in d.get("candidatos", [])]
    verbo = "ha" if len(pagadores) == 1 else "han"
    return (f"Pagaste {eur(d['importe_total'])} en {nombre_visible(d.get('comercio'))} y sueles ir con "
            f"{_unir([nombre_persona(c) for c in ordenados(miembros)])}: "
            f"{_unir([nombre_persona(c) for c in pagadores])} ya te {verbo} pagado y "
            f"{'falta' if len(faltan) == 1 else 'faltan'} {_unir([nombre_persona(c) for c in faltan])} "
            f"({eur(d['importe_pendiente'])}).")
