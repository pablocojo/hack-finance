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


def _dia(iso: str, con_anio: bool = False) -> str:
    """«2026-10-17» -> «17/10» (o «17/10/2026»)."""
    f = date.fromisoformat(str(iso))
    return f"{f.day}/{f.month}/{f.year}" if con_anio else f"{f.day}/{f.month}"


def _explicar_cargo_duplicado(d: dict) -> str:
    primera, segunda = d["fechas"]
    cuando = f"el {_dia(segunda)}" if primera == segunda else f"({_dia(primera)} y {_dia(segunda)})"
    comercio = nombre_visible(d.get("comercio"))
    if d.get("canal") == "recibo":
        limite = d.get("fecha_limite_devolucion")
        devolver = f" y puedes devolver el recibo hasta el {_dia(limite, True)}" if limite else ""
        return (f"Hay dos recibos iguales de {eur(d['importe'])} de {comercio} {cuando}; "
                f"puede ser un cobro duplicado{devolver}.")
    return f"Hay dos cargos iguales de {eur(d['importe'])} en {comercio} {cuando}; puede ser un cobro duplicado."


def _pct(valor: Any) -> str:
    texto = f"{_decimal(valor):.1f}".replace(".", ",")
    return texto[:-2] if texto.endswith(",0") else texto


def _explicar_subida_recibo(d: dict) -> str:
    """Dice «ha subido», nunca «te han cobrado de más» (revisión de `experto-banca`)."""
    texto = (f"El recibo de {nombre_visible(d.get('comercio'))} ha subido de {eur(d['importe_habitual'])} "
             f"a {eur(d['importe_actual'])} (+{eur(d['subida_eur'])}, un {_pct(d['subida_pct'])} %)")
    meses = str(d.get("serie_id", "")).rpartition(":")[2].removesuffix("m")
    if meses.isdigit() and int(meses) and 12 // int(meses) > 1:
        texto += f": son unos {eur(_decimal(d['subida_eur']) * (12 // int(meses)))} más al año"
    return texto + "."


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
    "cargo_duplicado": _explicar_cargo_duplicado,
    "subida_recibo": _explicar_subida_recibo,
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
