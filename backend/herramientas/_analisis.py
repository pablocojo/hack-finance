"""Utilidades compartidas por las herramientas de gastos (pandas)."""

from __future__ import annotations

import calendar

import pandas as pd

SIN_DATOS = ("No hay movimientos cargados. Pide al usuario que suba el CSV de su banco "
             "o que cargue datos de ejemplo.")


def tabla(ctx) -> pd.DataFrame:
    movimientos = getattr(ctx, "movimientos", None) or []
    if not movimientos:
        raise ValueError(SIN_DATOS)
    datos = pd.DataFrame(movimientos)
    datos["fecha"] = pd.to_datetime(datos["fecha"])
    datos["importe"] = datos["importe"].astype(float)
    if "categoria" not in datos:
        datos["categoria"] = None
    datos["categoria"] = datos["categoria"].fillna("sin categoría").astype(str)
    if "comercio" not in datos:
        datos["comercio"] = datos["concepto"]
    datos["comercio"] = datos["comercio"].fillna(datos["concepto"]).astype(str)
    datos["mes"] = datos["fecha"].dt.strftime("%Y-%m")
    return datos.sort_values("fecha", kind="stable").reset_index(drop=True)


def eur(valor) -> float:
    return round(float(valor), 2)


def inicio_periodo(datos: pd.DataFrame, meses: int) -> pd.Timestamp:
    """Primer día del mes que queda `meses` meses calendario atrás (el actual cuenta como uno)."""
    final = datos["fecha"].max()
    mes = final.month - (meses - 1)
    anio = final.year
    while mes <= 0:
        mes += 12
        anio -= 1
    return pd.Timestamp(year=anio, month=mes, day=1)


def mes_incompleto(datos: pd.DataFrame) -> str | None:
    final = datos["fecha"].max()
    if final.day < calendar.monthrange(final.year, final.month)[1]:
        return final.strftime("%Y-%m")
    return None


def _indice_mes(fecha: pd.Timestamp) -> int:
    return fecha.year * 12 + fecha.month


def detectar_recurrentes(datos: pd.DataFrame, signo: int = -1) -> list[dict]:
    """Pagos (signo=-1) o ingresos (signo=1) que se repiten cada 1, 2 o 3 meses con importe parecido."""
    filtrados = datos[datos["importe"] < 0] if signo < 0 else datos[datos["importe"] > 0]
    resultado = []
    for comercio, grupo in filtrados.groupby("comercio"):
        meses = sorted({_indice_mes(f) for f in grupo["fecha"]})
        if len(meses) < 2:
            continue
        saltos = {b - a for a, b in zip(meses, meses[1:])}
        if len(saltos) != 1:  # un recibo llega con un ritmo fijo: cada 1, 2 o 3 meses
            continue
        periodo = saltos.pop()
        if periodo not in (1, 2, 3) or (periodo == 1 and len(meses) < 3):
            continue
        if len(grupo) / len(meses) > 1.5:  # varias veces al mes: gasto variable, no recibo
            continue
        importes = grupo["importe"].abs()
        variacion = float(importes.std(ddof=0) / importes.mean()) if len(importes) > 1 else 0.0
        if variacion > 0.25 or grupo["fecha"].dt.day.std(ddof=0) > 3:
            continue
        compra_con_tarjeta = grupo["concepto"].astype(str).str.upper().str.startswith("COMPRA").all()
        if compra_con_tarjeta and (len(meses) < 4 or variacion > 0.05):
            continue  # una tienda donde se compra a menudo no es una suscripción
        mediana = float(importes.median())
        resultado.append({
            "comercio": comercio,
            "categoria": grupo["categoria"].mode().iat[0],
            "importe": eur(mediana * signo),
            "periodo_meses": periodo,
            "tipo": "fijo" if variacion <= 0.05 else "variable",
            "dia_habitual": int(grupo["fecha"].dt.day.median()),
            "ultimo": grupo["fecha"].max().date().isoformat(),
            "coste_anual": eur(mediana * 12 / periodo),
            "veces": int(len(grupo)),
        })
    return sorted(resultado, key=lambda r: -r["coste_anual"])
