"""
Medidas de la curva de amigos (C6; `docs/diseno/curva-amigos.md` §4.4 y §4.5).

Funciones puras sobre el registro de `protocolo.simular` (`ResultadoSimulacion.eventos`, ver su docstring):

    medir_corrida(eventos, vida)  -> {medida: {"1".."8", "total": valor | None}}     una vida × semilla × política
    agregar(corridas, vidas)      -> media e IC 95 % sobre las semillas, por usuario, global y por grado de rutina / chat

Qué es cada semana (todo se documenta también en `SUPUESTOS`, que va al JSON):
- Medidas de PREGUNTAS, ACIERTO, TOQUES y CASOS: la semana en que ocurren (el caso, por su creación).
- Medidas de DEUDA (dinero que se escapa y días hasta cobrar): la semana en que se cumple la ventana de 21 días del
  cargo (un cargo de la semana 5 se juzga en la 8). Solo cuentan los cargos con `observable_21`, así que las semanas 1-3
  quedan vacías (`None`). `semana_cargo = semana - 3`.
- Recordatorios a destiempo: la semana del primer recordatorio de cada deuda.

Correcciones de `experto-usuarios` (si no, la curva castigaría callar cuando toca):
- El dinero que se escapa EXCLUYE a las personas que el usuario no quiere que se recuerden (`meisam.no_recordar`): ni suman
  en lo prestado ni en lo que se escapa.
- El efectivo que volvió sin declararse NO es dinero perdido (volvió): va como cifra aparte
  (`efectivo_sin_declarar_eur`), porque Meisam no lo sabe.
- Nerea y Pilar (`uso: evaluacion`) salen siempre por separado en `agregar`: nunca entran en el global ni en los desgloses.

Este módulo vive en el simulador: el sistema (política, motor, casos, portero) nunca lo importa.
"""

from __future__ import annotations

import math
import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Iterable

from .esquema import Vida
from .generador import ACTIVACION

VENTANA_DIAS = 21
SEMANAS = tuple(range(1, 9))
CLAVES_SEMANA = tuple(str(s) for s in SEMANAS) + ("total",)
# Corte entre grados (sobre `vida.rutina` y `vida.meisam.usa_chat`).
RUTINA_FIJA = 0.7
RUTINA_BAJA = 0.4
CHAT_ALTO = 0.3
CHAT_BAJO = 0.1
FACTOR_SENSIBILIDAD = 0.5

CUENTAS = ("preguntas", "preguntas_inutiles", "toques", "recuperado_eur")   # sin eventos = 0
# t de Student bilateral al 95 % por grados de libertad (1..30); con más, 1,96.
_T95 = (12.706, 4.303, 3.182, 2.776, 2.571, 2.447, 2.365, 2.306, 2.262, 2.228, 2.201, 2.179, 2.160, 2.145, 2.131,
        2.120, 2.110, 2.101, 2.093, 2.086, 2.080, 2.074, 2.069, 2.064, 2.060, 2.056, 2.052, 2.048, 2.045, 2.042)

SUPUESTOS = [
    "Todo es SIMULACIÓN: vidas inventadas (`amigos/vidas/*.yaml`, congeladas) sobre el sistema real con reloj simulado; "
    "no son datos de clientes.",
    "Las tasas con que el usuario contesta a Meisam son supuestos (sin datos; las notificaciones de banca se abren un "
    "7-16 %): por eso hay una medida de sensibilidad con la mitad de esas tasas.",
    f"Dinero que se escapa: deudas con `observable_21` (cargo + {VENTANA_DIAS} días dentro de las 8 semanas) que a los "
    f"{VENTANA_DIAS} días ni han vuelto ni están reclamadas (Bizum pedido o en persona), sobre el total prestado; se juzga "
    "en la semana en que se cumple la ventana (semanas 1-3 sin datos).",
    "El dinero que se escapa excluye a las personas en `meisam.no_recordar` (el usuario no quiere que se las recuerde).",
    "El efectivo que vuelve sin declararse no cuenta como perdido (volvió): va aparte en `efectivo_sin_declarar_eur`.",
    "Acierto de la sugerencia: preguntas de nivel 2 y 3 cuya sugerencia el usuario acepta sin cambios, sobre todas las "
    "propuestas mostradas (las ignoradas cuentan como no aceptadas).",
    "Casos cerrados solos: casos con deudores cerrados por un Bizum sin ningún toque del usuario, sobre los casos con "
    "deudores creados esa semana.",
    "Toques por 100 € recuperados: gestos del usuario (responder, pedir, efectivo, corregir, feedback, chat) por cada "
    "100 € devueltos esa semana (banco y efectivo).",
    "Días hasta cobrar: mediana de las deudas cobradas con ventana observable (las no cobradas no entran).",
    f"Grado de rutina: fija >= {RUTINA_FIJA}, baja < {RUTINA_BAJA}, media el resto. Uso del chat (`usa_chat`): alto >= "
    f"{CHAT_ALTO}, bajo < {CHAT_BAJO}, medio el resto.",
    "Media e IC 95 % (t de Student) sobre las semillas; en grupos, primero la media de las vidas de cada semilla.",
    "Nerea y Pilar (solo evaluación) salen aparte y solo con semillas >= 100; las semillas 0-9 y las 8 vidas de ajuste "
    "son para ajustar.",
]


@dataclass(frozen=True)
class Medida:
    nombre: str
    tipo: str          # ratio | suma | mediana
    debe: str          # bajar | subir | informa
    descripcion: str


MEDIDAS: dict[str, Medida] = {m.nombre: m for m in (
    Medida("dinero_escapa", "ratio", "bajar", "Fracción de € prestados que a los 21 días ni volvieron ni se reclamaron "
           "(sin `no_recordar`; el efectivo devuelto no cuenta)"),
    Medida("dinero_escapa_eur", "suma", "bajar", "€ que se escapan (numerador de `dinero_escapa`)"),
    Medida("prestado_eur", "suma", "informa", "€ prestados con ventana observable (denominador, sin `no_recordar`)"),
    Medida("efectivo_sin_declarar_eur", "suma", "informa", "€ que volvieron en efectivo sin que el usuario lo declarara "
           "(cifra aparte: no es dinero perdido)"),
    Medida("preguntas", "suma", "bajar", "Preguntas de Meisam («¿fuiste con alguien?») que se muestran"),
    Medida("preguntas_inutiles", "suma", "bajar", "Preguntas que acaban en «iba solo», «nadie debe», «ya pagado» o "
           "duplicada"),
    Medida("preguntas_inutiles_frac", "ratio", "bajar", "Fracción de preguntas inútiles"),
    Medida("acierto_sugerencia", "ratio", "subir", "Propuestas de nivel 2 y 3 aceptadas sin cambios, sobre las mostradas"),
    Medida("sugerencia_correcta", "ratio", "subir", "Propuestas de nivel 2 y 3 que coincidían con la verdad oculta"),
    Medida("casos_cerrados_solos", "ratio", "subir", "Casos con deudores cerrados por Bizum sin toques del usuario"),
    Medida("recordatorios_a_destiempo", "ratio", "bajar", "Primeros recordatorios antes de cuando el amigo habría pagado "
           "solo"),
    Medida("toques", "suma", "informa", "Gestos del usuario"),
    Medida("recuperado_eur", "suma", "informa", "€ devueltos (banco y efectivo)"),
    Medida("toques_por_100_eur", "ratio", "bajar", "Toques por cada 100 € recuperados"),
    Medida("dias_hasta_cobrar", "mediana", "bajar", "Mediana de días del cargo al cobro (deudas cobradas)"),
)}


# --- Una corrida -------------------------------------------------------------------------------

def _dia(texto: str | None) -> date | None:
    return date.fromisoformat(texto) if texto else None


def _semana_de(dia: date) -> int:
    return (dia - ACTIVACION).days // 7 + 1


def _num(texto: Any) -> float:
    return float(texto) if texto not in (None, "") else 0.0


class _Acum:
    """Celdas por medida y semana: ratio (num, den), suma (valor) o mediana (valores)."""

    def __init__(self) -> None:
        self.c: dict[str, dict[int, list[float]]] = {m: defaultdict(list) for m in MEDIDAS}

    def ratio(self, medida: str, semana: int, num: float, den: float) -> None:
        if semana in SEMANAS:
            cel = self.c[medida].setdefault(semana, [0.0, 0.0])
            cel[0] += num
            cel[1] += den

    def suma(self, medida: str, semana: int, valor: float) -> None:
        if semana in SEMANAS:
            cel = self.c[medida].setdefault(semana, [0.0])
            cel[0] += valor

    def valor_(self, medida: str, semana: int, valor: float) -> None:
        if semana in SEMANAS:
            self.c[medida][semana].append(valor)

    def resultado(self) -> dict[str, dict[str, float | None]]:
        salida: dict[str, dict[str, float | None]] = {}
        for nombre, m in MEDIDAS.items():
            celdas = self.c[nombre]
            fila: dict[str, float | None] = {}
            for s in SEMANAS:
                celda = celdas.get(s)
                if celda is None and nombre in CUENTAS:
                    celda = [0.0]            # una semana sin preguntas ni toques cuenta 0, no «sin dato»
                fila[str(s)] = _valor(m.tipo, celda)
            total = _combinar(m.tipo, celdas.values())
            fila["total"] = _valor(m.tipo, total if total is not None or nombre not in CUENTAS else [0.0])
            salida[nombre] = fila
        return salida


def _combinar(tipo: str, celdas: Iterable[list[float]]) -> list[float] | None:
    celdas = [c for c in celdas if c]
    if not celdas:
        return None
    if tipo == "ratio":
        return [sum(c[0] for c in celdas), sum(c[1] for c in celdas)]
    if tipo == "suma":
        return [sum(c[0] for c in celdas)]
    return [v for c in celdas for v in c]


def _valor(tipo: str, celda: list[float] | None) -> float | None:
    if not celda:
        return None
    if tipo == "ratio":
        return round(celda[0] / celda[1], 4) if celda[1] > 0 else None
    if tipo == "suma":
        return round(celda[0], 2)
    return round(float(statistics.median(celda)), 2)


def medir_corrida(eventos: list[dict], vida: Vida) -> dict[str, dict[str, float | None]]:
    """Las 7 medidas de §4.4 (y sus numeradores) por semana y en total para una vida × semilla × política."""
    a = _Acum()
    excluidos = set(vida.meisam.no_recordar)
    respuestas = {e["caso_id"]: e for e in eventos if e["tipo"] == "respuesta"}

    for e in eventos:
        t = e["tipo"]
        if t == "pregunta":
            sem = e["semana"]
            a.suma("preguntas", sem, 1)
            a.suma("preguntas_inutiles", sem, 1 if e["inutil"] else 0)
            a.ratio("preguntas_inutiles_frac", sem, 1 if e["inutil"] else 0, 1)
            if e["nivel"] in (2, 3) and e.get("sugerencia"):
                r = respuestas.get(e["caso_id"])
                a.ratio("acierto_sugerencia", sem, 1 if r and r.get("sugerencia_aceptada") is True else 0, 1)
                if e.get("sugerencia_correcta") is not None:
                    a.ratio("sugerencia_correcta", sem, 1 if e["sugerencia_correcta"] else 0, 1)
        elif t == "toque":
            a.suma("toques", e["semana"], 1)
        elif t == "cobro":
            a.suma("recuperado_eur", e["semana"], _num(e["importe"]))
        elif t == "caso_final":
            creado = _dia(e.get("creado"))
            if creado and e.get("deudores"):
                a.ratio("casos_cerrados_solos", _semana_de(creado), 1 if e.get("cerrado_solo") else 0, 1)
        elif t == "deuda":
            _deuda(a, e, excluidos)

    # toques por 100 € se calcula con las celdas de toques y de recuperado de cada semana
    for s in SEMANAS:
        toques = a.c["toques"].get(s, [0.0])[0]
        euros = a.c["recuperado_eur"].get(s, [0.0])[0]
        if euros > 0:
            a.ratio("toques_por_100_eur", s, toques, euros / 100)
    return a.resultado()


def _deuda(a: _Acum, e: dict, excluidos: set[str]) -> None:
    fecha = _dia(e["fecha_pago"])
    recordado = _dia(e.get("recordado_el"))
    if recordado is not None and e.get("primer_recordatorio_a_destiempo") is not None:
        a.ratio("recordatorios_a_destiempo", _semana_de(recordado), 1 if e["primer_recordatorio_a_destiempo"] else 0, 1)
    if not e.get("observable_21") or e["contraparte"] in excluidos:
        return
    cierre = fecha + timedelta(days=VENTANA_DIAS)
    sem = _semana_de(cierre)
    cuota = _num(e["cuota"])
    devuelto = _dia(e.get("devuelto_el"))
    reclamado = _dia(e.get("reclamado_el"))
    vuelto = devuelto is not None and devuelto <= cierre
    reclamada = reclamado is not None and reclamado <= cierre
    a.suma("prestado_eur", sem, cuota)
    escapa = not vuelto and not reclamada
    a.suma("dinero_escapa_eur", sem, cuota if escapa else 0.0)
    a.ratio("dinero_escapa", sem, cuota if escapa else 0.0, cuota)
    if vuelto and e.get("canal_devuelto") == "efectivo" and e.get("declarado") is not True:
        a.suma("efectivo_sin_declarar_eur", sem, cuota)
    if e.get("dias_hasta_cobrar") is not None:
        a.valor_("dias_hasta_cobrar", sem, float(e["dias_hasta_cobrar"]))


# --- Agregar sobre semillas, vidas y grupos ----------------------------------------------------

def intervalo(valores: list[float]) -> dict[str, Any]:
    """Media e IC 95 % (t de Student) de los valores de las semillas; `None` si no hay ninguno."""
    n = len(valores)
    if n == 0:
        return {"media": None, "ic95": None, "n": 0}
    media = statistics.fmean(valores)
    if n == 1:
        return {"media": round(media, 4), "ic95": None, "n": 1}
    t = _T95[n - 2] if n - 1 <= len(_T95) else 1.96
    mitad = t * statistics.stdev(valores) / math.sqrt(n)
    return {"media": round(media, 4), "ic95": [round(media - mitad, 4), round(media + mitad, 4)], "n": n}


def grado_rutina(vida: Vida) -> str:
    return "fija" if vida.rutina >= RUTINA_FIJA else "baja" if vida.rutina < RUTINA_BAJA else "media"


def grado_chat(vida: Vida) -> str:
    u = vida.meisam.usa_chat
    return "alto" if u >= CHAT_ALTO else "bajo" if u < CHAT_BAJO else "medio"


def _por_semillas(filas: dict[int, dict[str, dict[str, float | None]]]) -> dict[str, dict[str, dict]]:
    """`filas`: semilla -> medidas de una corrida (o ya promediadas). -> medida -> semana -> intervalo."""
    salida: dict[str, dict[str, dict]] = {}
    for nombre in MEDIDAS:
        salida[nombre] = {}
        for clave in CLAVES_SEMANA:
            valores = [f[nombre][clave] for f in filas.values() if f[nombre][clave] is not None]
            salida[nombre][clave] = intervalo(valores)
    return salida


def _media_de_vidas(por_vida: dict[str, dict[int, dict]]) -> dict[int, dict[str, dict[str, float | None]]]:
    """Por semilla, la media de las vidas (las que tienen valor) de cada medida y semana."""
    semillas = sorted({s for v in por_vida.values() for s in v})
    salida: dict[int, dict[str, dict[str, float | None]]] = {}
    for semilla in semillas:
        fila: dict[str, dict[str, float | None]] = {}
        for nombre in MEDIDAS:
            fila[nombre] = {}
            for clave in CLAVES_SEMANA:
                vals = [v[semilla][nombre][clave] for v in por_vida.values()
                        if semilla in v and v[semilla][nombre][clave] is not None]
                fila[nombre][clave] = statistics.fmean(vals) if vals else None
        salida[semilla] = fila
    return salida


def agregar(corridas: list[dict], vidas: dict[str, Vida]) -> dict[str, dict]:
    """`corridas`: `{"vida", "semilla", "politica", "medidas"}` (de `medir_corrida`). Por política:

        {"ajuste":     {"vidas": [...], "global": {medida: {semana: {media, ic95, n}}},
                        "por_rutina": {fija|media|baja: {...}}, "por_chat": {alto|medio|bajo: {...}}},
         "evaluacion": {"vidas": [...], "global": {...}},       # solo si hay (Nerea, Pilar)
         "por_vida":   {vida_id: {medida: {semana: {...}}}}}    # cada usuario, incluidas las de evaluación
    """
    por_politica: dict[str, dict[str, dict[int, dict]]] = defaultdict(lambda: defaultdict(dict))
    for c in corridas:
        por_politica[c["politica"]][c["vida"]][c["semilla"]] = c["medidas"]
    salida: dict[str, dict] = {}
    for politica, por_vida in por_politica.items():
        ajuste = {v: s for v, s in por_vida.items() if vidas[v].uso == "ajuste"}
        evaluacion = {v: s for v, s in por_vida.items() if vidas[v].uso == "evaluacion"}
        bloque: dict[str, Any] = {}
        if ajuste:
            def grupo(clave) -> dict:
                grupos: dict[str, dict] = defaultdict(dict)
                for v, s in ajuste.items():
                    grupos[clave(vidas[v])][v] = s
                return {g: {"vidas": sorted(vs), **{"medidas": _por_semillas(_media_de_vidas(vs))}}
                        for g, vs in sorted(grupos.items())}
            bloque["ajuste"] = {"vidas": sorted(ajuste), "global": _por_semillas(_media_de_vidas(ajuste)),
                                "por_rutina": grupo(grado_rutina), "por_chat": grupo(grado_chat)}
        if evaluacion:
            bloque["evaluacion"] = {"vidas": sorted(evaluacion), "nota": "solo evaluación: por separado, nunca para ajustar",
                                    "global": _por_semillas(_media_de_vidas(evaluacion))}
        bloque["por_vida"] = {v: _por_semillas(s) for v, s in sorted(por_vida.items())}
        salida[politica] = bloque
    return salida


# --- Objetivos (§4.4) --------------------------------------------------------------------------

def _media(bloque: dict, medida: str, semana: str) -> float | None:
    return bloque[medida][semana]["media"]


def objetivos(resultados: dict[str, dict], base: str = "reglas", nueva: str = "personalizada") -> dict | None:
    """`nueva` frente a `base` con el valor real, la semana 8 y el total de las 8 semanas (se informa aunque no se llegue)."""
    if base not in resultados or nueva not in resultados:
        return None
    ra, rn = resultados[base].get("ajuste"), resultados[nueva].get("ajuste")
    if not ra or not rn:
        return None
    salida: dict[str, Any] = {"base": base, "nueva": nueva}

    def razon(medida: str, semana: str, tope: float) -> dict:
        b, n = _media(ra["global"], medida, semana), _media(rn["global"], medida, semana)
        r = None if b in (None, 0) or n is None else round(n / b, 3)
        return {"base": b, "nueva": n, "razon": r, "objetivo_razon_max": tope,
                "cumple": None if r is None else r <= tope}

    for semana in ("8", "total"):
        fija_b = ra["por_rutina"].get("fija", {}).get("medidas")
        fija_n = rn["por_rutina"].get("fija", {}).get("medidas")
        acierto = _media(fija_n, "acierto_sugerencia", semana) if fija_n else None
        salida[f"semana_{semana}" if semana == "8" else "total_8_semanas"] = {
            "dinero_escapa": razon("dinero_escapa", semana, 0.5),
            "preguntas_inutiles": razon("preguntas_inutiles", semana, 0.5),
            "recordatorios_a_destiempo": razon("recordatorios_a_destiempo", semana, 0.5),
            "acierto_sugerencia_rutina_fija": {"base": _media(fija_b, "acierto_sugerencia", semana) if fija_b else None,
                                               "nueva": acierto, "objetivo_min": 0.7,
                                               "cumple": None if acierto is None else acierto >= 0.7}}
    return salida
