"""
Perfil de vida (personalizacion.md §3): `perfilar(historial, hoy, perfil_anterior) -> PerfilUsuario | None`.

En una frase: «con pandas, miro tus últimos 90 días y saco cuándo cobras, cuánto entra, en qué gastas,
tu compra típica, con quién divides y qué suscripciones tienes; de tu compra típica sale qué es
"mucho" para ti». Pura y en línea: solo usa movimientos con fecha <= hoy.

- Con menos de 28 días de historial devuelve None (sin perfil: el motor usa sus umbrales por defecto).
- Lista negra (salud, citas, religión, política, sindicatos, donaciones, apuestas): esos cargos se
  descartan antes de calcular nada. Ante la duda, fuera.
- No puntúa solvencia: el umbral sale de la compra típica, nunca de los ingresos.
- `campos_fijados` (editados por el usuario) se copian del perfil anterior; `campos_borrados` vuelven
  a su valor por defecto y no se recalculan. `resumen_vida` se redacta por plantilla con lo que queda.
"""

from __future__ import annotations

import re
import statistics
import unicodedata
from calendar import monthrange
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

import pandas as pd

from ..motor.normalizar import clave_contraparte
from ..plataforma.tipos import Grupo, MovimientoEnriquecido, PerfilUsuario, Suscripcion
from .motivos import euros

VERSION = "perfil-v1"

PARAMETROS = {
    "min_dias": 28,                 # menos: sin perfil
    "ventana_dias": 90,             # V90
    "meses_gasto": 3,               # meses completos para el gasto típico y el ingreso
    "ingreso_min": Decimal("300"),
    "variacion_ingreso": 0.15,      # cada ingreso a <= 15 % de la mediana de su fuente
    "dispersion_dia": 4,            # días del mes de la nómina más separados: sin día
    "min_cargos_habitual": 3,
    "max_habituales": 8,
    "importe_min_pago": Decimal("30"),
    "ventana_reparto": 7,           # días tras el pago en los que cuenta un Bizum
    "personas_min": 3,
    "personas_max": 12,
    "tol_reparto_eur": Decimal("1"),
    "tol_reparto_pct": Decimal("0.03"),
    "min_bizums_p75": 3,
    "fusion_grupos": 0.5,           # comparten >= 50 % de miembros (del grupo menor): mismo grupo
    "umbral_factor": Decimal("2"),
    "umbral_min": Decimal("5"),
    "umbral_max": Decimal("100"),
}

# --- Lista negra (RGPD art. 9 y afines). Por categoría y por comercio --------------------------

CATEGORIAS_SENSIBLES = frozenset({
    "salud", "farmacia", "citas", "religion", "politica", "sindicatos", "donaciones", "apuestas",
})
COMERCIOS_SENSIBLES = re.compile(
    r"\b(FARMACIA|PARAFARMACIA|CLINICA|HOSPITAL|DENTAL|DENTISTA|MEDIC\w*|SANITAS|ADESLAS|DKV|ASISA|"
    r"PSICOLOG\w*|PSIQUIATR\w*|FISIOTERAP\w*|OPTICA|LABORATORIO|CENTRO DE SALUD|"
    r"TINDER|BUMBLE|MEETIC|BADOO|GRINDR|HAPPN|HINGE|"
    r"PARROQUIA|IGLESIA|DIOCESIS|ARZOBISPADO|OBISPADO|MEZQUITA|SINAGOGA|"
    r"PARTIDO|SINDICATO|CCOO|UGT|"
    r"CARITAS|CRUZ ROJA|UNICEF|ACNUR|ONG|FUNDACION|DONACION\w*|GREENPEACE|"
    r"BET365|CODERE|SPORTIUM|BWIN|POKERSTARS|WILLIAM HILL|LOTERIA\w*|APUESTA\w*|CASINO|ONCE)\b"
)
NO_CONSUMO = frozenset({"ingresos", "transferencias", "nomina"})        # no son gasto
NO_SUSCRIPCION = frozenset({                                           # recibos de casa, no cuotas
    "vivienda", "suministros", "impuestos", "seguros", "trabajo", "educacion", "ingresos", "transferencias",
})
PARTICULAS = {"de", "del", "la", "las", "los", "y", "el"}
CENTIMO = Decimal("0.01")
EURO = Decimal("1")
CAMPOS_CALCULADOS = (
    "dia_cobro_nomina", "ingreso_mensual_tipico", "gasto_tipico_por_categoria", "ticket_tipico",
    "umbral_relevante_eur", "comercios_habituales", "grupos", "suscripciones_activas", "resumen_vida",
)


def _texto(valor: str | None) -> str:
    sin_tildes = unicodedata.normalize("NFKD", valor or "").encode("ascii", "ignore").decode()
    return sin_tildes.upper().strip()


def es_sensible(categoria: str | None = None, comercio: str | None = None, concepto: str | None = None) -> bool:
    """¿Cae en la lista negra? Por categoría o por nombre de comercio. Ante la duda, sí."""
    if _texto(categoria).lower() in CATEGORIAS_SENSIBLES:
        return True
    return any(COMERCIOS_SENSIBLES.search(_texto(t)) for t in (comercio, concepto) if t)


def nombre_visible(comercio: str) -> str:
    """«METRO DE MADRID» -> «Metro de Madrid» (para el resumen; el perfil guarda la clave del motor)."""
    palabras = comercio.lower().split()
    return " ".join(p if (i and p in PARTICULAS) else p.capitalize() for i, p in enumerate(palabras))


# --- Utilidades ------------------------------------------------------------------------------

def _euros(centimos: float) -> Decimal:
    return (Decimal(str(centimos)) / 100).quantize(CENTIMO, rounding=ROUND_HALF_UP)


def _al_euro(valor: Decimal) -> Decimal:
    return valor.quantize(EURO, rounding=ROUND_HALF_UP)


def _sumar_meses(d: date, meses: int) -> date:
    indice = d.year * 12 + d.month - 1 + meses
    anio, mes = divmod(indice, 12)
    return date(anio, mes + 1, min(d.day, monthrange(anio, mes + 1)[1]))


def _p75(valores: list[int]) -> int | None:
    """Percentil 75 por rango más cercano, como el motor (entero, sin interpolar)."""
    if not valores:
        return None
    ordenados = sorted(valores)
    return ordenados[max(0, -(-3 * len(ordenados) // 4) - 1)]


def _meses_completos(primera: date, hoy: date, n: int) -> list[int]:
    """Índices (año·12 + mes) de los `n` últimos meses completos ya vistos enteros."""
    actual = hoy.year * 12 + hoy.month
    inicio = primera.year * 12 + primera.month + (0 if primera.day == 1 else 1)
    return [m for m in range(actual - n, actual) if m >= inicio]


def _tabla(historial: list[MovimientoEnriquecido]) -> pd.DataFrame:
    filas = [{
        "orden": i,
        "id": m.id,
        "fecha": m.fecha,
        "centimos": int((m.importe * 100).to_integral_value(rounding=ROUND_HALF_UP)),
        "canal": m.canal,
        "tipo": m.tipo_operacion or "cargo",
        "categoria": (m.categoria or None),
        "comercio": m.comercio_normalizado,
        "contraparte": m.contraparte_normalizada or (
            clave_contraparte(m.contraparte) if m.canal in ("bizum", "transferencia") else None),
        "concepto": m.concepto,
        "serie_id": m.serie_id,
        "posible_persona": "posible_persona" in m.etiquetas,
        "sensible": es_sensible(m.categoria, m.comercio_normalizado or m.comercio, m.concepto),
    } for i, m in enumerate(historial)]
    df = pd.DataFrame(filas)
    df["mes"] = df["fecha"].map(lambda d: d.year * 12 + d.month)
    return df.sort_values(["fecha", "orden"], kind="stable").reset_index(drop=True)


# --- Ingresos --------------------------------------------------------------------------------

def _dia_tipico(dias: list[int]) -> int | None:
    """Mediana del día del mes; el 30 y el 1 están cerca (cambio de mes). Separados > 4 días: None."""
    tope = PARAMETROS["dispersion_dia"]
    for candidatos in (dias, [d + 31 if d <= 10 else d for d in dias]):
        if max(candidatos) - min(candidatos) <= tope:
            dia = int(round(statistics.median(candidatos)))
            return dia - 31 if dia > 31 else dia
    return None


def _ingresos(df: pd.DataFrame, meses: list[int], desde: date) -> tuple[int | None, Decimal | None]:
    p = PARAMETROS
    entradas = df[(df.centimos >= int(p["ingreso_min"] * 100)) & (df.tipo == "cargo")
                  & (df.canal != "bizum") & (df.fecha >= desde)].copy()   # sin Bizums de contactos
    if entradas.empty:
        return None, None
    entradas["fuente"] = entradas.contraparte.fillna(entradas.comercio).fillna(entradas.concepto.map(_texto))
    fuentes = []
    for fuente, filas in entradas.groupby("fuente", sort=True):
        mediana = filas.centimos.median()
        if filas.mes.nunique() < 2 or ((filas.centimos - mediana).abs() > p["variacion_ingreso"] * mediana).any():
            continue
        es_nomina = filas.concepto.map(_texto).str.contains("NOMINA").any() or (filas.categoria == "nomina").any()
        fuentes.append((es_nomina, mediana, fuente, filas))
    if not fuentes:
        return None, None
    principal = max(fuentes, key=lambda f: (f[0], f[1]))[3]
    dia = _dia_tipico([d.day for d in principal.fecha])
    recurrentes = pd.concat([f[3] for f in fuentes])
    if meses:
        por_mes = recurrentes.groupby("mes").centimos.sum().reindex(meses, fill_value=0)
        ingreso = _euros(por_mes.median())
    else:
        ingreso = _euros(sum(f[1] for f in fuentes))
    return dia, (_al_euro(ingreso) if ingreso > 0 else None)


# --- Repartos y grupos -----------------------------------------------------------------------

def _cuadra(total: int, cuota: int) -> bool:
    """`total` se divide en cuotas de `cuota` entre 3 y 12 personas (a max(1 €, 3 %))."""
    p = PARAMETROS
    if cuota <= 0:
        return False
    personas = int(Decimal(total / cuota).to_integral_value(rounding=ROUND_HALF_UP))
    tolerancia = max(p["tol_reparto_eur"] * 100, Decimal(total) * p["tol_reparto_pct"])
    return p["personas_min"] <= personas <= p["personas_max"] and abs(total - personas * cuota) <= tolerancia


def _repartos(df: pd.DataFrame) -> list[dict]:
    """Pago con tarjeta seguido en <= 7 días de >= 2 Bizums entrantes de contrapartes distintas cuyas
    cuotas cuadran con el total. Cada Bizum va al pago anterior más reciente que encaja."""
    p = PARAMETROS
    pagos = df[(df.canal == "tarjeta") & (df.tipo == "cargo") & (df.serie_id.isna())
               & (df.centimos <= -int(p["importe_min_pago"] * 100))]
    bizums = df[(df.canal == "bizum") & (df.tipo == "cargo") & (df.centimos > 0) & df.contraparte.notna()]
    asignados: dict[int, dict] = {}
    for b in bizums.itertuples():
        mejor = None
        for pago in pagos.itertuples():
            dias = (b.fecha - pago.fecha).days
            if 0 <= dias <= p["ventana_reparto"] and _cuadra(-pago.centimos, b.centimos):
                mejor = pago if mejor is None or (pago.fecha, pago.Index) > (mejor.fecha, mejor.Index) else mejor
        if mejor is not None:
            reparto = asignados.setdefault(mejor.Index, {"pago_id": mejor.id, "fecha": mejor.fecha, "mes": mejor.mes,
                                                         "total": -mejor.centimos, "categoria": mejor.categoria,
                                                         "bizums": []})
            reparto["bizums"].append((b.contraparte, (b.fecha - mejor.fecha).days, b.centimos))
    return [r for _, r in sorted(asignados.items())
            if len({c for c, _, _ in r["bizums"]}) >= 2]


def _grupos(repartos: list[dict], hoy: date) -> tuple[list[Grupo], bool]:
    """Solo repartos cerrados (más de 7 días): los que comparten >= 50 % de miembros, un grupo.
    `retraso_p75_dias` es del grupo (nunca por persona). Devuelve también si suelen ser cenas."""
    p = PARAMETROS
    grupos: list[dict] = []
    for r in repartos:
        if (hoy - r["fecha"]).days <= p["ventana_reparto"]:
            continue
        miembros = list(dict.fromkeys(c for c, _, _ in r["bizums"]))
        destino = next((g for g in grupos if len(set(g["miembros"]) & set(miembros))
                        >= p["fusion_grupos"] * min(len(g["miembros"]), len(miembros))), None)
        if destino is None:
            destino = {"miembros": [], "veces": 0, "retrasos": [], "cenas": 0}
            grupos.append(destino)
        destino["miembros"] += [m for m in miembros if m not in destino["miembros"]]
        destino["veces"] += 1
        destino["retrasos"] += [dias for _, dias, _ in r["bizums"]]
        destino["cenas"] += r["categoria"] == "restaurantes"
    grupos.sort(key=lambda g: -g["veces"])
    salida = [Grupo(miembros=g["miembros"], veces=g["veces"],
                    retraso_p75_dias=_p75(g["retrasos"]) if len(g["retrasos"]) >= p["min_bizums_p75"] else None)
              for g in grupos]
    cenas = bool(grupos) and all(2 * g["cenas"] > g["veces"] for g in grupos)
    return salida, cenas


# --- Gasto, ticket, comercios y suscripciones ------------------------------------------------

def _gasto_por_categoria(df: pd.DataFrame, repartos: list[dict], meses: list[int], hoy: date) -> dict[str, Decimal]:
    """Mediana del gasto mensual por categoría (meses completos; un mes sin gasto cuenta 0). De los pagos
    compartidos cuenta solo tu parte: lo que pagaste menos lo que te han devuelto."""
    gastos = df[(df.centimos < 0) & (df.tipo == "cargo") & df.categoria.notna() & ~df.sensible
                & ~df.categoria.isin(NO_CONSUMO)].copy()
    if gastos.empty:
        return {}
    devuelto = {r["pago_id"]: sum(c for _, _, c in r["bizums"]) for r in repartos}
    gastos["gasto"] = -gastos.centimos - gastos.id.map(devuelto).fillna(0)
    if not meses:     # sin un mes completo: los últimos 30 días cuentan como un mes
        gastos = gastos[gastos.fecha > hoy - timedelta(days=30)].assign(mes=0)
        meses = [0]
    tabla = (gastos[gastos.mes.isin(meses)].pivot_table(index="categoria", columns="mes", values="gasto",
                                                         aggfunc="sum", fill_value=0)
             .reindex(columns=meses, fill_value=0))
    medianas = tabla.median(axis=1).sort_values(ascending=False, kind="stable")
    salida = {}
    for categoria, valor in medianas.items():
        euros_mes = _al_euro(_euros(valor))
        if euros_mes > 0:
            salida[str(categoria)] = euros_mes
    return salida


def _ticket(v90: pd.DataFrame) -> Decimal | None:
    compras = v90[(v90.canal == "tarjeta") & (v90.tipo == "cargo") & (v90.centimos < 0) & ~v90.sensible]
    return _euros((-compras.centimos).median()) if not compras.empty else None


def _habituales(v90: pd.DataFrame) -> list[str]:
    p = PARAMETROS
    cargos = v90[(v90.centimos < 0) & (v90.tipo == "cargo") & v90.comercio.notna() & ~v90.sensible
                 & ~v90.posible_persona & v90.canal.isin(["tarjeta", "recibo"])]   # comercios, no personas
    cuenta = cargos.groupby("comercio").size().reset_index(name="n")
    cuenta = cuenta[cuenta.n >= p["min_cargos_habitual"]].sort_values(["n", "comercio"], ascending=[False, True])
    return cuenta.comercio.head(p["max_habituales"]).tolist()


_PERIODO = re.compile(r":(\d+)m$")


def _suscripciones(df: pd.DataFrame, hoy: date) -> list[Suscripcion]:
    """Series mensuales o anuales (tarjeta o recibo, no recibos de casa) con el último cargo dentro de
    periodo y medio. `en_prueba`: hay una verificación del comercio posterior al último cargo."""
    cargos = df[df.serie_id.notna() & (df.centimos < 0) & (df.tipo == "cargo") & df.canal.isin(["tarjeta", "recibo"])
                & ~df.sensible & ~df.categoria.fillna("").isin(NO_SUSCRIPCION)]
    verificaciones = df[df.tipo == "verificacion"]
    salida = []
    for serie_id, filas in cargos.groupby("serie_id", sort=False):
        periodo = _PERIODO.search(str(serie_id))
        meses = int(periodo.group(1)) if periodo else None
        if meses not in (1, 12):
            continue
        dias = 30 if meses == 1 else 365
        ultimo = filas.iloc[-1]
        if (hoy - ultimo.fecha).days > 1.5 * dias:
            continue
        en_prueba = bool(((verificaciones.comercio == ultimo.comercio) & (verificaciones.fecha > ultimo.fecha)).any())
        salida.append(Suscripcion(comercio=ultimo.comercio, serie_id=str(serie_id), importe=_euros(-ultimo.centimos),
                                  periodicidad_dias=dias, proximo_cobro=_sumar_meses(ultimo.fecha, meses),
                                  en_prueba=en_prueba))
    return sorted(salida, key=lambda s: s.comercio)


# --- Resumen por plantilla -------------------------------------------------------------------

def resumen_plantilla(perfil: PerfilUsuario, cenas: bool = False) -> str | None:
    """3-4 frases neutras en segunda persona, solo con las cifras del perfil (ya sin la lista negra)."""
    frases = []
    if perfil.dia_cobro_nomina and perfil.ingreso_mensual_tipico:
        frases.append(f"Cobras la nómina hacia el día {perfil.dia_cobro_nomina}, "
                      f"unos {euros(perfil.ingreso_mensual_tipico)} al mes.")
    elif perfil.dia_cobro_nomina:
        frases.append(f"Cobras la nómina hacia el día {perfil.dia_cobro_nomina}.")
    elif perfil.ingreso_mensual_tipico:
        frases.append(f"Te entran unos {euros(perfil.ingreso_mensual_tipico)} al mes.")
    top = list(perfil.gasto_tipico_por_categoria.items())[:2]
    if top:
        partes = [f"{c} ({euros(v)})" for c, v in top]
        frases.append(f"Donde más gastas es en {' y '.join(partes)}.")
    if len(perfil.grupos) == 1:
        que = "cenas" if cenas else "gastos"
        frases.append(f"Sueles dividir {que} con un grupo de {len(perfil.grupos[0].miembros)} personas a partes iguales.")
    elif perfil.grupos:
        frases.append(f"Sueles dividir gastos con {len(perfil.grupos)} grupos de personas a partes iguales.")
    activas = [s for s in perfil.suscripciones_activas if not s.en_prueba]
    if activas:
        al_mes = sum((s.importe if s.periodicidad_dias <= 31 else (s.importe / 12).quantize(CENTIMO)) for s in activas)
        nombres = [nombre_visible(s.comercio) for s in activas]
        if len(activas) == 1:
            frases.append(f"Tienes 1 suscripción, {nombres[0]}, de {euros(al_mes)} al mes.")
        elif len(activas) <= 3:
            lista = ", ".join(nombres[:-1]) + f" y {nombres[-1]}"
            frases.append(f"Tienes {len(activas)} suscripciones, {lista}, que suman {euros(al_mes)} al mes.")
        else:
            frases.append(f"Tienes {len(activas)} suscripciones que suman {euros(al_mes)} al mes.")
    return " ".join(frases[:4]) or None


# --- perfilar --------------------------------------------------------------------------------

def _sin_futuro(historial: list[MovimientoEnriquecido], hoy: date) -> list[MovimientoEnriquecido]:
    """Solo fecha <= hoy. Si llegaba algo del futuro, las series se recalculan sin ello."""
    pasado = [m for m in historial if m.fecha <= hoy]
    if len(pasado) != len(historial):
        from ..motor.enriquecer import enriquecer_normalizados

        pasado = enriquecer_normalizados(pasado)[0]
    return pasado


def perfilar(historial: list[MovimientoEnriquecido], hoy: date,
             perfil_anterior: PerfilUsuario | None = None) -> PerfilUsuario | None:
    """Pura. None con menos de 28 días de historial. Respeta `campos_fijados` y `campos_borrados`."""
    p = PARAMETROS
    pasado = _sin_futuro(historial, hoy)
    if not pasado:
        return None
    primera = min(m.fecha for m in pasado)
    dias_historial = (hoy - primera).days + 1
    if dias_historial < p["min_dias"]:
        return None

    df = _tabla(pasado)
    v90 = df[df.fecha > hoy - timedelta(days=p["ventana_dias"])]
    meses = _meses_completos(primera, hoy, p["meses_gasto"])
    desde_meses = _sumar_meses(date(hoy.year, hoy.month, 1), -p["meses_gasto"])
    repartos = _repartos(df)
    dia, ingreso = _ingresos(df, meses, max(desde_meses, hoy - timedelta(days=p["ventana_dias"] + 31)))
    grupos, cenas = _grupos(repartos, hoy)
    ticket = _ticket(v90)

    calculado: dict = {
        "dia_cobro_nomina": dia,
        "ingreso_mensual_tipico": ingreso,
        "gasto_tipico_por_categoria": _gasto_por_categoria(df, repartos, meses, hoy),
        "comercios_habituales": _habituales(v90),
        "grupos": grupos,
        "suscripciones_activas": _suscripciones(df, hoy),
    }
    if ticket is not None:
        calculado["ticket_tipico"] = ticket

    fijados = [c for c in (perfil_anterior.campos_fijados if perfil_anterior else []) if c in CAMPOS_CALCULADOS]
    borrados = [c for c in (perfil_anterior.campos_borrados if perfil_anterior else []) if c in CAMPOS_CALCULADOS]
    campos = PerfilUsuario.model_fields
    for campo in borrados:
        calculado[campo] = campos[campo].get_default(call_default_factory=True)
    for campo in fijados:
        if campo not in borrados:
            calculado[campo] = getattr(perfil_anterior, campo)

    perfil = PerfilUsuario(version=VERSION, calculado=hoy, dias_historial=dias_historial,
                           campos_fijados=fijados, campos_borrados=borrados, **calculado)
    if "umbral_relevante_eur" not in fijados and "umbral_relevante_eur" not in borrados:
        perfil.umbral_relevante_eur = _al_euro(min(p["umbral_max"], max(p["umbral_min"],
                                                                        p["umbral_factor"] * perfil.ticket_tipico)))
    if "resumen_vida" not in fijados and "resumen_vida" not in borrados:
        perfil.resumen_vida = resumen_plantilla(perfil, cenas)
    return perfil
