"""
Razonador (motor.md §2.5): de hallazgos a `Momento`s. Sin Claude: todo por código y plantillas.

1. Clave estable -> `id = mom-<tipo>-<sha1(tipo|clave)[:10]>`; si ya se emitió, no se repite.
2. Filtro: `confianza >= CONFIANZA_MIN`.
3. Solapes (un movimiento en dos momentos del mismo día): gana el tipo de más prioridad y el otro
   queda marcado como emitido (no reaparece al día siguiente).
4. Orden: prioridad y luego `impacto_eur`.
5. `explicacion`: una frase por plantilla, en formato español. Nunca lleva notas de Bizum.
M9 añadirá `impacto_relativo` y `contexto_personal` con el perfil.
"""

from __future__ import annotations

import hashlib
from datetime import date
from decimal import Decimal
from typing import Any, Callable

from ..plataforma.tipos import Momento, PerfilUsuario
from . import detectores
from .detectores.base import Hallazgo
from .parametros import Razonador

VERSION_MOTOR = "motor-0.2"
PRIORIDAD = [
    "posible_estafa", "cargo_duplicado", "saldo_negativo_previsto", "gasto_compartido",
    "prueba_gratuita", "subida_recibo", "renovacion_proxima", "ingreso_extra", "viaje_detectado",
]
_MINUSCULAS = {"DE", "DEL", "LA", "LAS", "EL", "LOS", "Y", "EN", "A"}


# --- Formato ---------------------------------------------------------------------------------

def _decimal(valor: Any) -> Decimal:
    return valor if isinstance(valor, Decimal) else Decimal(str(valor))


def eur(valor: Any) -> str:
    """`Decimal("1234.5")` -> «1.234,50 €»."""
    texto = f"{_decimal(valor):,.2f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".") + " €"


def nombre_visible(comercio: str | None) -> str:
    """«LA TASCA» -> «La Tasca»."""
    if not comercio:
        return ""
    palabras = comercio.split()
    return " ".join(p.lower() if i and p in _MINUSCULAS else p.capitalize() for i, p in enumerate(palabras))


def _plural(n: int, singular: str, plural: str) -> str:
    return singular if n == 1 else plural


# --- Plantillas de explicación ---------------------------------------------------------------

def _explicar_gasto_compartido(d: dict) -> str:
    reembolsos = d.get("reembolsos", [])
    devuelto = sum((_decimal(r["importe"]) for r in reembolsos), Decimal("0"))
    n, faltan = len(reembolsos), int(d["faltan"])
    return (f"Pagaste {eur(d['importe_total'])} en {nombre_visible(d.get('comercio'))} y te han devuelto "
            f"{eur(devuelto)} de {n} {_plural(n, 'persona', 'personas')}; "
            f"{_plural(faltan, 'falta', 'faltan')} {faltan} ({eur(d['importe_pendiente'])}).")


_TITULOS = {
    "cargo_duplicado": "Posible cargo duplicado",
    "renovacion_proxima": "Se renueva pronto una suscripción",
    "subida_recibo": "Un recibo ha subido",
    "saldo_negativo_previsto": "Tu saldo podría quedar en negativo",
    "posible_estafa": "Movimiento con señales de posible estafa",
    "gasto_compartido": "Gasto compartido pendiente",
    "ingreso_extra": "Ingreso extra",
    "viaje_detectado": "Parece que vas de viaje",
    "prueba_gratuita": "Una prueba gratuita está a punto de cobrarse",
}

PLANTILLAS: dict[str, Callable[[dict], str]] = {
    "gasto_compartido": _explicar_gasto_compartido,
}


def explicar(tipo: str, datos: dict) -> str:
    plantilla = PLANTILLAS.get(tipo)
    if plantilla:
        try:
            return plantilla(datos)
        except (KeyError, TypeError, ValueError, ArithmeticError):
            pass
    comercio = nombre_visible(datos.get("comercio"))
    return f"{_TITULOS.get(tipo, tipo)}{' en ' + comercio if comercio else ''}."


# --- Razonar ---------------------------------------------------------------------------------

def clave_completa(h: Hallazgo) -> str:
    return f"{h.tipo}|{h.clave}"


def momento_id(tipo: str, clave: str) -> str:
    return f"mom-{tipo}-{hashlib.sha1(f'{tipo}|{clave}'.encode()).hexdigest()[:10]}"


def _prioridad(tipo: str) -> int:
    return PRIORIDAD.index(tipo) if tipo in PRIORIDAD else len(PRIORIDAD)


def razonar(
    usuario_id: str,
    hallazgos: list[Hallazgo],
    emitidas: dict[str, str],
    hoy: date,
    fechas: dict[str, date],
    params: Razonador,
    perfil: PerfilUsuario | None = None,
) -> list[Momento]:
    """Convierte hallazgos en momentos nuevos y anota sus claves en `emitidas` (lo muta)."""
    vivos = [h for h in hallazgos if h.confianza >= params.CONFIANZA_MIN and clave_completa(h) not in emitidas]
    vivos.sort(key=lambda h: (_prioridad(h.tipo), -(h.impacto_eur or Decimal("0"))))
    usados: dict[str, str] = {}
    momentos: list[Momento] = []
    for h in vivos:
        ident = momento_id(h.tipo, h.clave)
        solape = next((usados[i] for i in h.movimientos if i in usados), None)
        if solape:
            emitidas[clave_completa(h)] = f"solapado:{solape}"
            continue
        ids = sorted(dict.fromkeys(h.movimientos), key=lambda i: (fechas.get(i, hoy), h.movimientos.index(i)))
        momentos.append(Momento(
            id=ident,
            tipo=h.tipo,
            usuario_id=usuario_id,
            fecha=hoy,
            movimientos=ids,
            datos=h.datos,
            confianza=round(h.confianza, 2),
            impacto_eur=h.impacto_eur,
            explicacion=explicar(h.tipo, h.datos),
            detector=h.tipo,
            version=f"{VERSION_MOTOR}/{h.tipo}-{detectores.version(h.tipo)}",
        ))
        emitidas[clave_completa(h)] = ident
        usados.update({i: ident for i in ids})
    return momentos
