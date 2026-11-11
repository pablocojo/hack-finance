"""
Escalera de la pregunta (curva-amigos.md §4.1): cómo preguntar por un pago que pudo ser con otros.

En una frase: «sin saber nada pregunto como siempre; cuanto mejor te conozco en ese sitio, menos pregunto donde
nadie te debe y mejor propongo donde sí: primero en el resumen y, si estoy muy seguro y el importe importa, con una
notificación de un toque».

| Nivel | Qué hace | Cuándo |
|---|---|---|
| 0 | Silencio | Señal débil sin nada aprendido, o sitio donde casi nunca te deben (vas solo o cada uno paga lo suyo) |
| 1 | Resumen genérico: «¿Fuiste con alguien?» | Lo de antes (señal media) o p(te deben) moderada |
| 2 | Resumen con sugerencia: «¿Con Laura y Marcos?» | p(te deben) media y un grupo habitual |
| 3 | Notificación de un toque con cuotas | p(te deben) alta, propuesta probable e importe >= umbral |

Cada 2 preguntas seguidas sin respuesta en ese sitio, un nivel menos. Sin datos o con `modo = "reglas"`: exactamente
lo de antes (`senal media` -> 1, `debil` -> 0). Nada por nombre de comercio ni de vida: solo lo aprendido del usuario.
Umbrales en `aprende_amigos.PARAMETROS`. Puras y rápidas (< 1 ms). El nivel 4 (rutina aceptada) va aparte (A6).
"""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from ..plataforma.tipos import AprendizajeAmigos, AvisoCaso, DecisionPregunta, SugerenciaReparto
from .aprende_amigos import (
    PARAMETROS,
    Estimacion,
    ambitos_de,
    clave_tipo_franja,
    estimar,
    forma_con_deuda,
    franja_de,
    grupo_con_deuda,
    peso_grupo,
)

AVISO_POR_NIVEL: dict[int, AvisoCaso] = {0: "silencioso", 1: "resumen", 2: "resumen", 3: "notificar", 4: "silencioso"}
SENALES_PREGUNTA = ("media", "aprendida")   # lo que hoy pregunta en el resumen (`aprendida`: la abrió lo aprendido)
FORMAS_CON_CUOTA = ("iguales", "redondeo")  # por consumo: las cuotas las dice el usuario
_CENTIMO = Decimal("0.01")

MOTIVO_BASE_PREGUNTA = "Pudo ser con alguien y aún no conozco tus costumbres aquí: te pregunto en el resumen."
MOTIVO_BASE_SILENCIO = "Es poco probable que fuera compartido y no sé nada que diga lo contrario: no te pregunto."
MOTIVO_REGLAS = "Uso las reglas de siempre, sin lo aprendido."
MOTIVO_DUDA = "Pudo ser con alguien y todavía no lo tengo claro: te pregunto en el resumen."


def _donde(est: Estimacion) -> str:
    if est.es_comercio:
        return "Aquí"
    tipo, _, franja = est.ambito.removeprefix("tipo:").partition("|")
    cuando = {"laborable": "entre semana", "viernes": "los viernes", "finde": "los fines de semana"}.get(franja, "")
    return f"En sitios así {cuando}".rstrip()


def _cuotas(importe: Decimal, personas: list[str]) -> dict[str, Decimal]:
    """A partes iguales con el usuario incluido (como `con_personas` de la llamada): cada persona, total / (n + 1)
    redondeado al céntimo; el resto lo pone el usuario. Vacío si la cuota no cabe en un Bizum."""
    if importe is None or importe <= 0 or not personas:
        return {}
    cuota = (Decimal(importe) / (len(personas) + 1)).quantize(_CENTIMO, rounding=ROUND_HALF_UP)
    if not PARAMETROS["cuota_min"] <= cuota <= PARAMETROS["cuota_max"] or cuota * len(personas) > importe:
        return {}
    return {p: cuota for p in personas}


def sugerir(apr: AprendizajeAmigos, comercio: str | None, tipo_comercio: str | None, fecha: date,
            importe: Decimal) -> SugerenciaReparto | None:
    """Las personas del grupo con el que más te deben en ese sitio (o, si no hay, en ese tipo de sitio y franja), su
    forma de reparto y, si es a partes iguales, las cuotas con `Decimal` (usuario incluido). `confianza` = p(te deben)
    x peso del grupo: la probabilidad de que la propuesta acierte. None si no hay grupo o con `modo = "reglas"`."""
    if apr.modo == "reglas":
        return None
    est = estimar(apr, comercio, tipo_comercio, fecha)
    if est is None:
        return None
    t = clave_tipo_franja(tipo_comercio, franja_de(fecha))
    opciones = [(est.acomp, est.ambito)]
    if est.es_comercio and t and t in apr.por_tipo_franja:
        opciones.append((apr.por_tipo_franja[t], f"tipo:{t}"))
    for acomp, ambito in opciones:
        g = grupo_con_deuda(acomp)
        if g is None:
            continue
        forma = forma_con_deuda(g) or "iguales"
        cuotas = _cuotas(importe, g.miembros) if forma in FORMAS_CON_CUOTA else {}
        confianza = max(0.0, min(1.0, est.p * peso_grupo(acomp, g)))
        return SugerenciaReparto(personas=list(g.miembros), forma=forma, cuotas=cuotas,
                                 confianza=round(confianza, 3), ambito=ambito)
    return None


def _decision(nivel: int, motivos: list[str], p: float, n: int,
              sugerencia: SugerenciaReparto | None = None) -> DecisionPregunta:
    if nivel == 2 and sugerencia is not None:
        sugerencia = sugerencia.model_copy(update={"cuotas": {}})   # en el resumen solo se proponen las personas
    elif nivel not in (2, 3):
        sugerencia = None
    return DecisionPregunta(nivel=nivel, aviso=AVISO_POR_NIVEL[nivel], sugerencia=sugerencia,
                            p_acompanado=round(max(0.0, min(1.0, p)), 3), n=n, motivos=motivos)


def nivel_pregunta(apr: AprendizajeAmigos, *, comercio: str | None, tipo_comercio: str | None, fecha: date,
                   importe: Decimal, senal: str | None, umbral: Decimal) -> DecisionPregunta:
    """Decide el nivel (0-3) con sus motivos legibles. `senal` es la del motor (`media`, `debil`, `aprendida` o None);
    `umbral` es el importe relevante del usuario (20 € sin perfil). `p_acompanado` sale como la probabilidad de que
    alguien te deba (la que decide)."""
    P = PARAMETROS
    base = 1 if senal in SENALES_PREGUNTA else 0
    motivo_base = MOTIVO_BASE_PREGUNTA if base else MOTIVO_BASE_SILENCIO
    prior = P["prior_con"] / (P["prior_con"] + P["prior_solo"])
    if apr.modo == "reglas":
        return _decision(base, [motivo_base, MOTIVO_REGLAS], prior, 0)

    est = estimar(apr, comercio, tipo_comercio, fecha)
    sugerencia = None
    if est is None:
        nivel, motivos, p, n = base, [motivo_base], prior, 0
    else:
        p, n, donde = est.p, est.n, _donde(est)
        if p <= P["p_solo_max"] and est.evidencia >= P["min_evidencia_silencio"]:
            nivel = 0
            motivos = [f"{donde} cada uno suele pagar lo suyo: no te pregunto." if est.sin_deuda > est.solo else
                       f"{donde} sueles ir solo: no te pregunto."]
        else:
            sugerencia = sugerir(apr, comercio, tipo_comercio, fecha, importe)
            confianza = sugerencia.confianza if sugerencia is not None else 0.0
            alta = (p >= P["p_alta"] and est.evidencia >= P["min_evidencia_alta"]
                    and confianza >= P["confianza_alta"] and bool(sugerencia and sugerencia.cuotas))
            media = p >= P["p_media"] and est.evidencia >= P["min_evidencia_media"] and confianza >= P["confianza_media"]
            if alta and importe >= umbral:
                nivel = 3
                motivos = [f"{donde} sueles pagar tú por el grupo y casi siempre con las mismas personas.",
                           "El importe es relevante para ti: te lo pregunto con una notificación de un toque."]
            elif alta or media:
                nivel = 2
                motivos = [f"{donde} sueles pagar tú por más gente: te sugiero con quién en el resumen."]
                if alta:
                    motivos.append("El importe está por debajo de lo que para ti es relevante: no te mando "
                                   "notificación.")
            elif base or (p >= P["p_preguntar"] and est.evidencia >= P["min_evidencia_preguntar"]):
                nivel = 1
                motivos = [f"{donde} a veces te deben algo: te pregunto en el resumen."
                           if p >= P["p_preguntar"] else MOTIVO_DUDA]
            else:
                nivel = 0
                motivos = [MOTIVO_BASE_SILENCIO]

    ignoradas = max((a.ignoradas for a in ambitos_de(apr, comercio, tipo_comercio, fecha)), default=0)
    bajar = ignoradas // P["ignoradas_bajan"] if P["ignoradas_bajan"] > 0 else 0
    if bajar and nivel > 0:
        nivel = max(nivel - bajar, 0)
        motivos = [motivos[0], "Las últimas preguntas parecidas se quedaron sin respuesta: pregunto menos."]
    return _decision(nivel, motivos, p, n, sugerencia)
