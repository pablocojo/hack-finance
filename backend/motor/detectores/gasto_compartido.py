"""
`gasto_compartido` (motor.md §3.1): pagaste algo para varios, casi todos te han devuelto su parte
con un Bizum y falta alguien.

Cuándo: el primer `hoy` con `hoy - pago >= DIAS_ESPERA` (p75 propio + 1, entre 2 y 5; 3 sin línea base)
y al menos un día desde el último reembolso, mientras `faltan >= 1` y `hoy - pago <= VENTANA_REEMBOLSO`.
Candidatos: quienes devolvieron junto a alguno de los que ya han pagado en repartos anteriores o, con
perfil, los miembros que faltan del grupo del perfil que más coincide (y su retraso p75 fija la espera).
Las notas de los Bizums solo suben la confianza: nunca salen en `datos` ni en la explicación.

Casos dudosos (deudas-casos.md, fase 1): si la señal no es inequívoca, el momento sale con
`datos["dudoso"] = True`, `datos["hipotesis"] = [{candidatos, faltan, motivo}]` y confianza `CONFIANZA_DUDOSO`
(0,60, bajo el 0,7 del módulo): sin IA no avisa; la fase 2 elige. Son dudosos: alguien que paga k cuotas (no se
sabe a quién cubre) mientras aún falta gente, dos cuotas posibles, un envío de un candidato que no encaja
con la cuota y las cuotas desiguales. Un redondeo (<= 1 €) o un múltiplo que deja el reparto cubierto no
dudan (este último ni siquiera avisa: no falta nadie). Con la clave `dudoso` ausente, el aviso es firme.
"""

from __future__ import annotations

import re
from collections import Counter
from decimal import Decimal

from ...datos.categorias import normalizar as normalizar_texto
from ...plataforma.tipos import MovimientoEnriquecido, PerfilUsuario
from ..enriquecer import centimos
from ..formato import eur, nombre_persona
from ..parametros import GastoCompartido
from ..reparto import Reparto, es_pago, repartos
from . import grupo_habitual, registrar
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


def grupo_del_perfil(perfil: PerfilUsuario | None, pagadores: set[str]):
    """El grupo del perfil con más miembros entre los que ya pagaron (>= 2, o >= 1 si el grupo tiene <= 4)."""
    if perfil is None or "grupos" in perfil.campos_borrados:
        return None
    posibles = [(len(set(g.miembros) & pagadores), g.veces, g) for g in perfil.grupos
                if len(set(g.miembros) & pagadores) >= (1 if len(g.miembros) <= 4 else 2)]
    return max(posibles, key=lambda t: (t[0], t[1]), default=(0, 0, None))[2]


def _aprendidos(ctx: Contexto, pago: MovimientoEnriquecido | None, pagadores: set[str],
                personas: int | None) -> tuple[list[tuple[str, float]], bool, tuple[str, dict[str, float]] | None]:
    """Del grupo habitual aprendido del sitio (`grupos`, A3b), si alguno de los que ya pagaron es de él: los miembros
    que faltan (de quien más va a quien menos), si el grupo encaja con las personas del reparto y `(ámbito, grupo)`."""
    aprendido = grupo_habitual.grupo_de(ctx, pago) if pago is not None and ctx.grupos else None
    if aprendido is None or not pagadores & set(aprendido[1]):
        return [], False, None
    miembros = aprendido[1]
    faltan = [(c, miembros[c]) for c in grupo_habitual.ordenados(miembros) if c not in pagadores]
    return faltan, personas is not None and len(miembros) == personas - 1, aprendido


def _candidatos(ctx: Contexto, pagadores: set[str], personas: int | None,
                p: GastoCompartido, pago: MovimientoEnriquecido | None = None,
                faltan: int | None = None) -> tuple[list[tuple[str, int]], bool]:
    """`([(contraparte, peso)], fuertes)`: los miembros del grupo del perfil que faltan (por `veces`) o, sin
    perfil, los de las líneas base propias. `fuertes`: encaja el grupo con las personas o hay >= 3 coincidencias.
    Con el grupo habitual aprendido del sitio (`grupos`), sus miembros que faltan van primero; si bastan para
    `faltan`, son los únicos (aprendidos, no adivinados)."""
    aprendidos, encaja, _ = _aprendidos(ctx, pago, pagadores, personas)
    if aprendidos:
        if faltan is not None and len(aprendidos) >= faltan:
            return aprendidos, encaja
        resto, _ = _candidatos(ctx, pagadores, personas, p)
        vistos = {c for c, _ in aprendidos}
        return aprendidos + [(c, n) for c, n in resto if c not in vistos], encaja
    grupo = grupo_del_perfil(ctx.perfil, pagadores)
    if grupo is not None:
        faltan = [(m, grupo.veces) for m in sorted(set(grupo.miembros) - pagadores)]
        if faltan:
            return faltan, personas is not None and len(grupo.miembros) == personas - 1
    propios = candidatos(pagadores, ctx.lineas_base.get("repartos", []), p)
    return propios, bool(propios) and propios[0][1] >= p.COINCIDENCIAS_FUERTES


def _confianza(reparto: Reparto, fuertes: bool, p: GastoCompartido) -> float:
    confianza = p.CONFIANZA_BASE
    confianza += 0.15 if reparto.cuadra else 0
    confianza += 0.10 if len(reparto.reembolsos) >= 3 else 0
    confianza += 0.10 if any(_nota_de_plan(r.nota) for r in reparto.reembolsos) else 0
    confianza += 0.10 if fuertes else 0
    confianza -= 0.15 if reparto.personas > 8 else 0
    return round(min(confianza, p.CONFIANZA_MAX), 2)


def _entrada(r: MovimientoEnriquecido) -> dict:
    return {"contraparte": r.contraparte_normalizada, "importe": centimos(r.importe), "id": r.id}


def _hipotesis(reparto: Reparto, todos: list[str], extras: list[MovimientoEnriquecido]) -> list[dict]:
    """Hipótesis de un reparto con cuota común y alguna duda. Frases legibles, sin notas de Bizum."""
    faltan, cuota = reparto.faltan, reparto.cuota
    hipotesis = []
    for r in reparto.multiples:
        k = reparto.pesos[r.id]
        hipotesis.append({
            "candidatos": todos[: (faltan + k - 1) * 2],
            "faltan": faltan,
            "motivo": (f"{nombre_persona(r.contraparte_normalizada)} envió {eur(r.importe)}, {k} cuotas de "
                       f"{eur(cuota)}: no se sabe a quién más cubre"),
        })
    if reparto.empate:
        hipotesis.append({"candidatos": todos[: faltan * 2], "faltan": faltan,
                          "motivo": f"El reparto encaja con más de una cuota; he tomado {eur(cuota)}"})
    for e in extras:
        quien = e.contraparte_normalizada
        motivo = f"{nombre_persona(quien)} envió {eur(e.importe)}, que no encaja con la cuota de {eur(cuota)}"
        hipotesis.append({"candidatos": [c for c in todos if c != quien][: max(faltan - 1, 0) * 2],
                          "faltan": max(faltan - 1, 0), "motivo": motivo + ": puede ser su parte"})
        hipotesis.append({"candidatos": todos[: faltan * 2], "faltan": faltan,
                          "motivo": motivo + ": puede ser otra cosa y que aún deba su parte"})
    return hipotesis


def _es_recurrente(ctx: Contexto, reparto: Reparto, personas: set[str], todos: dict[str, Reparto],
                   p: GastoCompartido) -> bool:
    """¿Es un gasto fijo compartido? El pago es del mismo comercio que `MIN_OCURRENCIAS_RECURRENTE - 1` pagos anteriores
    seguidos, a ≈ un mes uno de otro (`DIAS_ENTRE_CICLOS`), y en todos esos ciclos pagaron `personas` (quienes ya han
    pagado este y los candidatos que faltan). Dos cenas en el mismo restaurante con amigos distintos no lo son.
    Solo mira el pasado: el historial ya llega cortado en `hoy`."""
    pago = reparto.pago
    if not pago.comercio_normalizado or not personas:
        return False
    previos = sorted((m for m in ctx.historial if m.fecha < pago.fecha and es_pago(m, p)
                      and m.comercio_normalizado == pago.comercio_normalizado), key=lambda m: m.fecha)
    cadena: list = []
    siguiente = pago
    for m in reversed(previos):
        dias = (siguiente.fecha - m.fecha).days
        if p.DIAS_ENTRE_CICLOS[0] <= dias <= p.DIAS_ENTRE_CICLOS[1]:
            cadena.append(m)
            siguiente = m
        elif dias > p.DIAS_ENTRE_CICLOS[1]:
            break
    if len(cadena) + 1 < p.MIN_OCURRENCIAS_RECURRENTE:
        return False
    for m in cadena:
        previo = todos.get(m.id)
        if previo is None or not previo.valido or not personas <= {r.contraparte_normalizada for r in previo.reembolsos}:
            return False
    return True


def _hallazgo_cuota_comun(ctx: Contexto, reparto: Reparto, p: GastoCompartido,
                          todos_repartos: dict[str, Reparto] | None = None) -> Hallazgo:
    pago = reparto.pago
    reembolsos = reparto.reembolsos
    pagadores = {r.contraparte_normalizada for r in reembolsos}
    todos, fuertes = _candidatos(ctx, pagadores, reparto.personas, p, pago, reparto.faltan)
    elegidos = todos[: reparto.faltan * 2]
    posibles = {c for c, _ in todos}
    extras = [e for e in reparto.extras if e.contraparte_normalizada in posibles]
    hipotesis = []
    if reparto.multiples or reparto.empate or extras:
        hipotesis = _hipotesis(reparto, [c for c, _ in todos], extras)
    cuota = reparto.cuota
    pendiente = centimos(reparto.faltan * cuota)
    datos = {
        "pago_id": pago.id,
        "comercio": pago.comercio_normalizado,
        "importe_total": centimos(reparto.total),
        "fecha": pago.fecha.isoformat(),
        "reembolsos": [{**_entrada(r), **({"personas": reparto.pesos[r.id]} if reparto.pesos.get(r.id, 1) > 1 else {})}
                       for r in reembolsos],
        "personas_estimadas": reparto.personas,
        "faltan": reparto.faltan,
        "importe_pendiente": pendiente,
        "candidatos": [{"contraparte": c, "importe": cuota} for c, _ in elegidos],
        "cuota": cuota,
    }
    aprendidos, _, grupo = _aprendidos(ctx, pago, pagadores, reparto.personas)
    if aprendidos and grupo and {c for c, _ in elegidos} <= {c for c, _ in aprendidos}:   # candidatos aprendidos
        datos["ambito_aprendido"] = grupo[0]
        datos["motivo_grupo"] = grupo_habitual.motivo(grupo[1], sorted(pagadores & set(grupo[1])))
    confianza = _confianza(reparto, fuertes, p)
    if todos_repartos is not None and _es_recurrente(ctx, reparto, pagadores | {c for c, _ in elegidos[: reparto.faltan]},
                                                     todos_repartos, p):
        datos["recurrente"] = True
    if hipotesis:
        datos["dudoso"] = True
        datos["hipotesis"] = hipotesis
        if extras:
            datos["sin_encajar"] = [_entrada(e) for e in extras]
        confianza = min(confianza, p.CONFIANZA_DUDOSO)
    return Hallazgo(
        tipo="gasto_compartido", clave=pago.id,
        movimientos=[pago.id, *(r.id for r in reembolsos), *(e.id for e in extras)],
        confianza=confianza, impacto_eur=pendiente, datos=datos,
    )


def _hallazgo_desigual(ctx: Contexto, reparto: Reparto, p: GastoCompartido,
                       todos_repartos: dict[str, Reparto] | None = None) -> Hallazgo | None:
    """Cada uno pagó una cantidad distinta: siempre dudoso (lo valora la fase 2 con el contexto)."""
    pago = reparto.pago
    recibidos = sorted([*reparto.reembolsos, *reparto.extras], key=lambda m: m.fecha)
    pagadores = {r.contraparte_normalizada for r in recibidos}
    previos = ctx.lineas_base.get("repartos", [])
    conocidos = {m for grupo in previos for m in grupo}
    if ctx.perfil is not None and "grupos" not in ctx.perfil.campos_borrados:
        conocidos |= {m for g in ctx.perfil.grupos for m in g.miembros}
    cubierto = sum((r.importe for r in recibidos), Decimal("0"))
    if len(pagadores & conocidos) < p.MIN_CONOCIDOS_DESIGUAL or cubierto >= reparto.total * p.CUBIERTO_MAX_PCT:
        return None
    todos, _ = _candidatos(ctx, pagadores, None, p, pago)
    elegidos = [c for c, _ in todos][: max(p.PERSONAS_MAX - 1 - len(pagadores), 0)]
    if not elegidos:
        return None
    faltan = len(elegidos)
    cuota = centimos((reparto.total - cubierto) / (faltan + 1))
    if cuota <= 0:
        return None
    pendiente = centimos(faltan * cuota)
    importes = [r.importe for r in recibidos]
    motivo = (f"Los envíos son distintos (de {eur(min(importes))} a {eur(max(importes))}): puede que cada uno "
              f"pague lo suyo y no se sabe cuánto falta")
    datos = {
        "pago_id": pago.id,
        "comercio": pago.comercio_normalizado,
        "importe_total": centimos(reparto.total),
        "fecha": pago.fecha.isoformat(),
        "reembolsos": [_entrada(r) for r in recibidos],
        "personas_estimadas": len(pagadores) + 1 + faltan,
        "faltan": faltan,
        "importe_pendiente": pendiente,
        "candidatos": [{"contraparte": c, "importe": cuota} for c in elegidos],
        "cuota": cuota,
        "cuota_estimada": True,
        "dudoso": True,
        "hipotesis": [
            {"candidatos": elegidos, "faltan": faltan, "motivo": motivo},
            {"candidatos": [], "faltan": 0, "motivo": "Cada uno pudo pagar su parte y la cuenta estar cerrada"},
        ],
    }
    return Hallazgo(tipo="gasto_compartido", clave=pago.id, movimientos=[pago.id, *(r.id for r in recibidos)],
                    confianza=p.CONFIANZA_DUDOSO, impacto_eur=pendiente, datos=datos)


@registrar("gasto_compartido", version=3)
def detectar(ctx: Contexto) -> list[Hallazgo]:
    """Los repartos con falta, el grupo habitual aprendido (`origen = grupo_habitual`, solo con `grupos`) y la señal de
    lugar y día (`origen = pago_individual`): el mismo tipo de momento."""
    from . import pago_individual

    todos = repartos(ctx.historial, ctx.params["gasto_compartido"])
    return _repartos_con_falta(ctx, todos) + grupo_habitual.detectar(ctx, todos) + pago_individual.detectar(ctx)


def _repartos_con_falta(ctx: Contexto, todos: dict[str, Reparto] | None = None) -> list[Hallazgo]:
    p: GastoCompartido = ctx.params["gasto_compartido"]
    propio = ctx.lineas_base.get("retraso_reembolso_p75")
    hallazgos = []
    todos = repartos(ctx.historial, p) if todos is None else todos
    for reparto in todos.values():
        dias = (ctx.hoy - reparto.pago.fecha).days
        grupo = grupo_del_perfil(ctx.perfil, {r.contraparte_normalizada for r in [*reparto.reembolsos, *reparto.extras]})
        espera = dias_espera(p, grupo.retraso_p75_dias if grupo is not None and grupo.retraso_p75_dias is not None
                             else propio)
        if not espera <= dias <= p.VENTANA_REEMBOLSO:
            continue
        if reparto.valido and reparto.faltan >= 1:
            ultimo, construir = max(r.fecha for r in reparto.reembolsos), _hallazgo_cuota_comun
        elif reparto.desigual:
            ultimo = max(r.fecha for r in [*reparto.reembolsos, *reparto.extras])
            construir = _hallazgo_desigual
        else:
            continue
        if (ctx.hoy - ultimo).days < p.MIN_DIAS_DESDE_ULTIMO:
            continue
        hallazgo = construir(ctx, reparto, p, todos)
        if hallazgo:
            hallazgos.append(hallazgo)
    return hallazgos
