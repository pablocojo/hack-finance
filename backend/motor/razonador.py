"""
Razonador (motor.md §2.5): de hallazgos a `Momento`s. Sin Claude: todo por código y plantillas.

1. Clave estable -> `id = mom-<tipo>-<sha1(tipo|clave)[:10]>`; si ya se emitió, no se repite.
2. Filtro: `confianza >= CONFIANZA_MIN`.
3. Solapes (un movimiento en dos momentos del mismo día): gana el tipo de más prioridad y el otro
   queda marcado como emitido (no reaparece al día siguiente).
4. Orden: prioridad y luego `impacto_eur`.
5. `explicacion`: una frase por plantilla, en formato español. Nunca lleva notas de Bizum.
6. Con perfil (M9): `impacto_relativo` y `contexto_personal` (motor.md §2.5.6), por código y plantillas.
"""

from __future__ import annotations

import hashlib
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Callable

from ..plataforma.tipos import Momento, PerfilUsuario
from . import detectores
from .detectores.base import Hallazgo
from .detectores.pago_individual import TIPOS_CON_ENTRADA
from .formato import decimal, eur  # noqa: F401  (`eur` es API pública del razonador)
from .parametros import Razonador

VERSION_MOTOR = "motor-0.2"
PRIORIDAD = [
    "posible_estafa", "cargo_duplicado", "saldo_negativo_previsto", "gasto_compartido",
    "prueba_gratuita", "subida_recibo", "renovacion_proxima", "ingreso_extra", "viaje_detectado",
]
_MINUSCULAS = {"DE", "DEL", "LA", "LAS", "EL", "LOS", "Y", "EN", "A"}


# --- Formato ---------------------------------------------------------------------------------

_decimal = decimal


def nombre_visible(comercio: str | None) -> str:
    """«LA TASCA» -> «La Tasca»."""
    if not comercio:
        return ""
    palabras = comercio.split()
    return " ".join(p.lower() if i and p in _MINUSCULAS else p.capitalize() for i, p in enumerate(palabras))


def _plural(n: int, singular: str, plural: str) -> str:
    return singular if n == 1 else plural


# --- Plantillas de explicación ---------------------------------------------------------------

_DIAS_SEMANA = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")


def _explicar_pago_individual(d: dict) -> str:
    """Solo pregunta: no hay deuda calculada. El comercio es un dato y solo entra por `nombre_visible`."""
    fecha = date.fromisoformat(str(d["fecha"]))
    personas = d.get("personas_estimadas")
    cuantas = ""
    if isinstance(personas, int) and not isinstance(personas, bool) and personas >= 2:     # precio por persona (K1 d)
        unidad = "entradas" if d.get("tipo_comercio") in TIPOS_CON_ENTRADA else "personas"
        cuantas = f", unas {personas} {unidad},"
    return (f"Pagaste {eur(d['importe_total'])} en {nombre_visible(d.get('comercio'))} el "
            f"{_DIAS_SEMANA[fecha.weekday()]} {fecha.day}/{fecha.month}{cuantas} y nadie te ha enviado un Bizum: "
            f"¿fuiste con alguien?")


def _explicar_gasto_compartido(d: dict) -> str:
    if d.get("origen") == "pago_individual":
        return _explicar_pago_individual(d)
    reembolsos = d.get("reembolsos", [])
    devuelto = sum((_decimal(r["importe"]) for r in reembolsos), Decimal("0"))
    n, faltan = len(reembolsos), int(d["faltan"])
    if d.get("dudoso"):
        motivo = str(((d.get("hipotesis") or [{}])[0]).get("motivo", "no encaja del todo")).rstrip(".")
        if motivo.split(" ")[0] in ("Los", "El", "La", "Cada"):     # no es un nombre propio
            motivo = motivo[0].lower() + motivo[1:]
        return (f"Pagaste {eur(d['importe_total'])} en {nombre_visible(d.get('comercio'))} y te han devuelto "
                f"{eur(devuelto)} de {n} {_plural(n, 'persona', 'personas')}, pero no está claro si falta alguien: "
                f"{motivo}.")
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


def _explicar_prueba_gratuita(d: dict) -> str:
    """Un aviso a tiempo, sin dramatizar. Si la duración es una suposición, lo dice."""
    n = int(d["dias_hasta"])
    texto = (f"Tu prueba de {nombre_visible(d.get('comercio'))} empieza a cobrarse en {n} {_plural(n, 'día', 'días')} "
             f"(el {_dia(d['fecha_primer_cobro'])})")
    if d.get("importe_previsto") is not None:
        texto += f" por {eur(d['importe_previsto'])}"
    if d.get("fuente_duracion") == "por_defecto":
        texto += f"; he supuesto {int(d['dias_prueba'])} días de prueba"
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
    "prueba_gratuita": _explicar_prueba_gratuita,
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


# --- Contexto personal (con perfil) ----------------------------------------------------------

DIAS_ANTES_NOMINA = 5          # un cobro en los 5 días previos a la nómina se avisa como tal
TIPOS_CON_COBRO = ("prueba_gratuita", "renovacion_proxima")
CAMPOS_FECHA_COBRO = ("fecha_primer_cobro", "fecha_prevista")


def _dias_hasta_dia_del_mes(dia: int, desde: date) -> int:
    """Días desde `desde` hasta el próximo día `dia` del mes (0 si es ese día)."""
    def ultimo(anio: int, mes: int) -> int:
        return (date(anio + (mes == 12), mes % 12 + 1, 1) - date(anio, mes, 1)).days

    d = min(dia, ultimo(desde.year, desde.month))
    if desde.day <= d:
        return d - desde.day
    anio, mes = desde.year + (desde.month == 12), desde.month % 12 + 1
    return (date(anio, mes, min(dia, ultimo(anio, mes))) - desde).days


def _campo_perfil(perfil: PerfilUsuario, nombre: str) -> Any:
    return None if nombre in perfil.campos_borrados else getattr(perfil, nombre, None)


def _dias(n: int) -> str:
    return f"{n} {_plural(n, 'día', 'días')}"


def _frase_base(impacto: Decimal, perfil: PerfilUsuario, hoy: date,
                saldo_hoy: Decimal | None) -> tuple[Decimal | None, str | None]:
    """Primera regla con datos (a: saldo y nómina; b: ingreso típico; c: umbral relevante)."""
    nomina = _campo_perfil(perfil, "dia_cobro_nomina")
    dias = _dias_hasta_dia_del_mes(int(nomina), hoy) if nomina else 0
    if saldo_hoy is not None and saldo_hoy > 0 and dias >= 1:
        relativo = impacto / saldo_hoy
        if relativo >= 1:
            return _relativo(relativo), f"Es más de lo que te queda hasta la nómina ({_dias(dias)})"
        frase = (f"Te {_plural(dias, 'queda', 'quedan')} {_dias(dias)} hasta la nómina y son el "
                 f"{_pct(relativo * 100)} % de lo que te queda")
        return _relativo(relativo), frase if relativo >= Decimal("0.01") else None
    ingreso = _campo_perfil(perfil, "ingreso_mensual_tipico")
    if ingreso is not None and ingreso > 0:
        relativo = impacto / ingreso
        frase = f"Es el {_pct(relativo * 100)} % de lo que sueles ingresar al mes"
        return _relativo(relativo), frase if relativo >= Decimal("0.01") else None
    umbral = _campo_perfil(perfil, "umbral_relevante_eur")
    if umbral is not None and umbral > 0 and impacto >= umbral:
        return _relativo(impacto / umbral), (f"Está por encima de lo que para ti es un gasto importante "
                                             f"({eur(umbral).replace(',00', '')})")
    return None, None


def _relativo(valor: Decimal) -> Decimal:
    return valor.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def contexto_personal(h: Hallazgo, perfil: PerfilUsuario | None, hoy: date,
                      saldo_hoy: Decimal | None) -> tuple[Decimal | None, str | None]:
    """`(impacto_relativo, frase)` solo con perfil. Cifras del código, frases por plantilla, nada de Claude.
    Un caso dudoso no lleva contexto: sus importes son una estimación."""
    if perfil is None or h.datos.get("dudoso"):
        return None, None
    relativo, frase = (None, None)
    if h.impacto_eur is not None and h.impacto_eur > 0:
        relativo, frase = _frase_base(h.impacto_eur, perfil, hoy, saldo_hoy)
    nomina = _campo_perfil(perfil, "dia_cobro_nomina")
    if nomina and h.tipo in TIPOS_CON_COBRO:
        cobro = next((h.datos[c] for c in CAMPOS_FECHA_COBRO if h.datos.get(c)), None)
        if cobro:
            fecha = date.fromisoformat(str(cobro))
            antes = _dias_hasta_dia_del_mes(int(nomina), fecha)
            if 1 <= antes <= DIAS_ANTES_NOMINA:
                inicio = f"El cobro llega {_dias(antes)} antes de tu nómina"
                frase = f"{inicio}. {frase}" if frase else inicio
    return relativo, (frase + "." if frase else None)


def razonar(
    usuario_id: str,
    hallazgos: list[Hallazgo],
    emitidas: dict[str, str],
    hoy: date,
    fechas: dict[str, date],
    params: Razonador,
    perfil: PerfilUsuario | None = None,
    saldo_hoy: Decimal | None = None,
) -> list[Momento]:
    """Convierte hallazgos en momentos nuevos y anota sus claves en `emitidas` (lo muta).
    `saldo_hoy`: último saldo conocido (<= hoy), para el contexto personal con perfil."""
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
        relativo, contexto = contexto_personal(h, perfil, hoy, saldo_hoy)
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
            impacto_relativo=relativo,
            contexto_personal=contexto,
        ))
        emitidas[clave_completa(h)] = ident
        usados.update({i: ident for i in ids})
    return momentos
