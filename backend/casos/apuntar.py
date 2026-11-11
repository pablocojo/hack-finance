"""
Apuntar un gasto desde el chat (docs/diseno/curva-amigos.md §4.2; CONTRATO.md, «Curva de amigos»). Todo es PURO: no lee
ni guarda nada (el candado, el disco y la auditoría son de `plataforma/chat_casos.py`).

    buscar_cargos(historial, entrada, hoy) -> list[CargoCandidato]   el cargo que dice el usuario, por código
    cuotas_de(movimiento, entrada, claves) -> dict[str, Decimal]      lo que debe cada persona (ValueError si no vale)

La pista del usuario es DATO: solo se normaliza y se compara con el comercio, el concepto y la categoría del cargo; nunca
se interpreta como instrucción ni se copia a ningún sitio. Los candidatos salen enmascarados y sin la nota de Bizum.
"""

from __future__ import annotations

import difflib
import os
import re
import unicodedata
from datetime import date, timedelta
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal

from ..acciones.registro import BIZUM_IMPORTE_MAX, BIZUM_IMPORTE_MIN
from ..plataforma.tipos import ApuntarGastoEntrada, CargoCandidato, Movimiento
from .ciclo import eur_texto, nombre_visible, sanear_motivo

VENTANA_DIAS = 3             # con `fecha_aprox`: ± 3 días
SIN_FECHA_DIAS = 7           # sin `fecha_aprox`: los últimos 7 días
MAX_CANDIDATOS = 5
UMBRAL_PISTA = 0.6           # por debajo, el comercio no encaja con la pista
MARGEN = 0.15                # entre candidatos, se quedan los que están a este margen del mejor
TOLERANCIA_IMPORTE_ABS = Decimal("1.00")   # «unos 48»: se admite 1 € o el 3 %
TOLERANCIA_IMPORTE_REL = Decimal("0.03")
CENT = Decimal("0.01")

# Palabras que no distinguen un sitio de otro («las pizzas de ayer») y fechas dichas con palabras.
_VACIAS = frozenset("""el la los las un una unos unas de del al en con y e o a por para que lo le mi mis ayer hoy anoche
antes anteayer otro otra dia noche tarde manana pasado semana fin finde sabado domingo lunes martes miercoles jueves
viernes""".split())
# Lo que se suele decir y no es el nombre del comercio: se compara con la categoría y el concepto del cargo.
_SINONIMOS = {
    "pizza": ("pizza", "pizzeria", "restaurantes"), "cena": ("restaurantes", "restaurante", "bar", "cena"),
    "comida": ("restaurantes", "restaurante", "comida"), "comer": ("restaurantes", "restaurante"),
    "restaurante": ("restaurantes", "restaurante"), "copas": ("bar", "ocio", "copas", "pub"),
    "cervezas": ("bar", "ocio", "cerveceria"), "birras": ("bar", "ocio", "cerveceria"), "tapas": ("bar", "restaurantes"),
    "desayuno": ("cafeteria", "cafe", "restaurantes"), "cafe": ("cafeteria", "cafe"), "cine": ("cine", "ocio"),
    "sushi": ("sushi", "restaurantes"), "hamburguesas": ("burger", "hamburgueseria", "restaurantes"),
}


def _normal(texto: object) -> str:
    base = unicodedata.normalize("NFD", str(texto or "")).encode("ascii", "ignore").decode()
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", base.lower()).split())


def _raiz(palabra: str) -> str:
    """Quita el plural y las terminaciones más comunes para que «pizzas» encaje con «pizzeria»."""
    p = palabra
    for sufijo in ("es", "s"):
        if len(p) > 4 and p.endswith(sufijo):
            p = p[: -len(sufijo)]
            break
    return p[:5] if len(p) > 5 else p


def _tokens(texto: object) -> list[str]:
    return [t for t in _normal(texto).split() if t not in _VACIAS and len(t) > 1]


def _similitud(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    ra, rb = _raiz(a), _raiz(b)
    if ra == rb or (min(len(ra), len(rb)) >= 4 and (ra.startswith(rb) or rb.startswith(ra))):
        return 1.0
    comun = len(os.path.commonprefix([a, b]))   # «pizzas» ~ «pizzeria»: misma raíz aunque cambie el final
    if comun >= 4 and comun >= 0.6 * min(len(a), len(b)):
        return 0.9
    return difflib.SequenceMatcher(None, a, b).ratio()


def _puntuar(pista: list[str], m: Movimiento) -> float:
    """0-1: cuánto encaja la pista con el comercio (1), el concepto o la categoría (algo menos). Sin pista útil: 0,5."""
    if not pista:
        return 0.5
    nombre = _tokens(m.comercio) or _tokens(m.concepto)
    resto = _tokens(m.concepto) + _tokens(m.categoria)
    mejor = 0.0
    for t in pista:
        directo = max((_similitud(t, c) for c in nombre), default=0.0)
        indirecto = 0.9 * max((_similitud(t, c) for c in resto), default=0.0)
        sinonimo = 0.0
        for s in _SINONIMOS.get(_raiz(t), ()):
            sinonimo = max(sinonimo, 0.7 * max((_similitud(s, c) for c in nombre + resto), default=0.0))
        mejor = max(mejor, directo, indirecto, sinonimo)
    return mejor


def _importe_encaja(m: Movimiento, buscado: Decimal) -> bool:
    total = abs(m.importe)
    return abs(total - buscado) <= max(TOLERANCIA_IMPORTE_ABS, buscado * TOLERANCIA_IMPORTE_REL)


def _visible(m: Movimiento) -> str:
    return sanear_motivo(m.comercio or m.concepto, 40)


def buscar_cargos(historial: list[Movimiento], entrada: ApuntarGastoEntrada, hoy: date) -> list[CargoCandidato]:
    """Cargos de la cuenta que encajan con lo que dice el usuario: de más a menos probable, como mucho 5.

    Ventana de fechas: `fecha_aprox` ± 3 días (nunca después de `hoy`) o, sin ella, los últimos 7 días. Solo cargos
    (importe negativo), de tarjeta o recibo: ni Bizums ni ingresos ni movimientos sensibles (RGPD). Con `importe_total` se
    descartan los que no encajan (tolerancia de 1 € o el 3 %). Con una pista útil, solo los que se parecen al comercio; si
    uno encaja claramente mejor que los demás, se queda solo con los que están a su altura. 0 candidatos = no hay cargo."""
    from ..personalizacion.perfil import es_sensible   # import tardío: evita ciclos con `personalizacion`

    if entrada.fecha_aprox is not None:
        desde, hasta = entrada.fecha_aprox - timedelta(days=VENTANA_DIAS), entrada.fecha_aprox + timedelta(days=VENTANA_DIAS)
    else:
        desde, hasta = hoy - timedelta(days=SIN_FECHA_DIAS), hoy
    hasta = min(hasta, hoy)                      # nadie mira el futuro
    pista = _tokens(entrada.pista)
    puntuados: list[tuple[float, int, date, Movimiento]] = []
    for m in historial:
        if m.importe >= 0 or m.canal in ("bizum", "transferencia", "cajero") or not desde <= m.fecha <= hasta:
            continue
        if es_sensible(m.categoria, m.comercio, m.concepto):
            continue
        if entrada.importe_total is not None and not _importe_encaja(m, abs(entrada.importe_total)):
            continue
        puntos = _puntuar(pista, m)
        if pista and puntos < UMBRAL_PISTA:
            continue
        cerca = abs((m.fecha - entrada.fecha_aprox).days) if entrada.fecha_aprox else (hoy - m.fecha).days
        puntuados.append((puntos, cerca, m.fecha, m))
    if not puntuados:
        return []
    puntuados.sort(key=lambda t: (-t[0], t[1], -t[2].toordinal(), t[3].id))
    corte = puntuados[0][0] - MARGEN
    elegidos = [t[3] for t in puntuados if t[0] >= corte][:MAX_CANDIDATOS]
    return [CargoCandidato(movimiento_id=m.id, fecha=m.fecha, comercio=_visible(m), importe=abs(m.importe)) for m in elegidos]


def _fuera_de_rango(nombre: str, cuota: Decimal) -> ValueError:
    return ValueError(f"La parte de {nombre} sería {eur_texto(cuota).replace('.', ',')} €: un Bizum admite de 0,50 € a "
                      "1.000 €.")


def cuotas_de(movimiento: Movimiento, entrada: ApuntarGastoEntrada, claves: list[str]) -> dict[str, Decimal]:
    """Lo que debe cada persona (`claves`, en el orden de `entrada.personas`). Lanza `ValueError` en español si no vale.

    - Si el usuario no dice importes: a partes iguales con el usuario incluido (`incluye_usuario`), con `Decimal`.
    - Si dice el importe de algunas: esas, tal cual; las demás (y el usuario, si va) se reparten el resto a partes iguales.
    - Cada cuota, de 0,50 € a 1.000 €, y entre todas no pueden pasar de lo que pagó el usuario."""
    if movimiento.importe >= 0:
        raise ValueError("Solo se puede repartir un cargo tuyo: ese movimiento es un ingreso.")
    if not claves:
        raise ValueError("Indica con quién fue.")
    if len(set(claves)) != len(claves):
        raise ValueError("Una persona aparece dos veces: suma sus partes en una.")
    if len(claves) != len(entrada.personas):
        raise ValueError("Las personas resueltas no coinciden con las que dijo el usuario.")
    total = abs(movimiento.importe)
    dichos: dict[str, Decimal] = {}
    for clave, persona in zip(claves, entrada.personas):
        if persona.importe is not None:
            try:  # revisor 11 nov: «1e40» o infinito no deben acabar en un 500
                dichos[clave] = Decimal(persona.importe).quantize(CENT, rounding=ROUND_HALF_UP)
            except ArithmeticError:
                raise ValueError("Ese importe no es válido: cada parte va de 0,50 € a 1.000 €.") from None
    libres = [c for c in claves if c not in dichos]
    partes = len(libres) + (1 if entrada.incluye_usuario else 0)
    cuotas = dict(dichos)
    if libres:
        resto = total - sum(dichos.values(), Decimal("0"))
        if resto <= 0:
            raise ValueError("Con esos importes no queda nada para el resto: la suma pasa de lo que pagaste "
                             f"({eur_texto(total).replace('.', ',')} €).")
        for redondeo in (ROUND_HALF_UP, ROUND_DOWN):
            cada = (resto / partes).quantize(CENT, rounding=redondeo)
            if cada * len(libres) + sum(dichos.values(), Decimal("0")) <= total:
                break
        cuotas.update({c: cada for c in libres})
    salida = {c: cuotas[c] for c in claves}      # en el orden en que habló el usuario
    for clave, cuota in salida.items():
        if not BIZUM_IMPORTE_MIN <= cuota <= BIZUM_IMPORTE_MAX:
            raise _fuera_de_rango(nombre_visible(clave), cuota)
    if sum(salida.values(), Decimal("0")) > total:
        raise ValueError(f"Entre todos no pueden deberte más de lo que pagaste ({eur_texto(total).replace('.', ',')} €).")
    return salida
