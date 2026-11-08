"""
Calculadoras financieras: préstamos (sistema francés y TAE), interés compuesto, plan de ahorro y 50/30/20.

Regla del kit: dinero exacto con Decimal (cuotas, intereses, totales); análisis con float redondeado.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from ..agente.registro import herramienta
from ..datos.categorias import grupo_50_30_20
from ._analisis import eur, inicio_periodo, mes_incompleto, tabla

CENTIMO = Decimal("0.01")


def _d(valor) -> Decimal:
    return Decimal(str(valor))


def _redondear(valor: Decimal) -> Decimal:
    return valor.quantize(CENTIMO, rounding=ROUND_HALF_UP)


def _tir_mensual(neto_recibido: float, cuotas: list[float]) -> float:
    """Tipo mensual r que iguala lo recibido con el valor actual de las cuotas (bisección)."""
    bajo, alto = 0.0, 1.0
    for _ in range(200):
        medio = (bajo + alto) / 2
        valor = sum(c / (1 + medio) ** k for k, c in enumerate(cuotas, start=1))
        if valor > neto_recibido:
            bajo = medio
        else:
            alto = medio
    return (bajo + alto) / 2


@herramienta
def calcular_prestamo(importe: float, tin_anual: float, plazo_meses: int,
                      comision_apertura_pct: float = 0.0) -> dict:
    """Calcula la cuota mensual de un préstamo (sistema francés), los intereses, el coste total y la TAE.

    Úsala para préstamos personales, coches, hipotecas o para comparar ofertas.
    La TAE incluye la comisión de apertura, como exige la normativa de transparencia.

    Args:
        importe: Capital prestado en euros.
        tin_anual: Tipo de interés nominal anual en porcentaje, por ejemplo 6.5.
        plazo_meses: Número de cuotas mensuales (1-480).
        comision_apertura_pct: Comisión de apertura en porcentaje del capital, por ejemplo 1.5.
    """
    if importe <= 0:
        raise ValueError("El importe debe ser mayor que cero.")
    if not 1 <= int(plazo_meses) <= 480:
        raise ValueError("El plazo debe estar entre 1 y 480 meses.")
    if not 0 <= tin_anual <= 50:
        raise ValueError("El TIN debe estar entre 0 y 50 %.")
    capital, n = _d(importe), int(plazo_meses)
    tipo = _d(tin_anual) / Decimal(1200)
    cuota = capital / n if tipo == 0 else capital * tipo / (1 - (1 + tipo) ** -n)
    cuota = _redondear(cuota)

    pendiente, cuotas, intereses_totales = capital, [], Decimal(0)
    primer_anio = {"intereses": Decimal(0), "capital_amortizado": Decimal(0)}
    for mes in range(1, n + 1):
        interes = _redondear(pendiente * tipo)
        amortizado = cuota - interes if mes < n else pendiente
        pago = amortizado + interes
        pendiente -= amortizado
        intereses_totales += interes
        cuotas.append(float(pago))
        if mes <= 12:
            primer_anio["intereses"] += interes
            primer_anio["capital_amortizado"] += amortizado

    comision = _redondear(capital * _d(comision_apertura_pct) / 100)
    tir = _tir_mensual(float(capital - comision), cuotas)
    tae = ((1 + tir) ** 12 - 1) * 100
    return {
        "cuota_mensual": cuota,
        "ultima_cuota": _d(cuotas[-1]),
        "plazo_meses": n,
        "tin_pct": tin_anual,
        "tae_pct": round(tae, 2),
        "total_intereses": intereses_totales,
        "comision_apertura": comision,
        "total_pagado": _redondear(sum(_d(c) for c in cuotas) + comision),
        "coste_total_credito": intereses_totales + comision,
        "primer_anio": {k: _redondear(v) for k, v in primer_anio.items()},
        "nota": "Cálculo orientativo con cuota constante. La TAE de una oferta real puede incluir otros "
                "gastos (seguros vinculados, comisiones) que aquí no están.",
    }


@herramienta
def interes_compuesto(capital_inicial: float = 0.0, aportacion_mensual: float = 0.0,
                      rentabilidad_anual_pct: float = 3.0, anios: int = 10,
                      inflacion_anual_pct: float = 2.0) -> dict:
    """Proyecta el valor de un ahorro con interés compuesto y aportaciones mensuales, en euros nominales y en euros de hoy.

    Úsala para enseñar el efecto del interés compuesto o comparar escenarios. La rentabilidad es un
    supuesto que da el usuario o un ejemplo explícito, nunca una promesa.

    Args:
        capital_inicial: Dinero que se invierte o ahorra al principio, en euros.
        aportacion_mensual: Aportación al final de cada mes, en euros.
        rentabilidad_anual_pct: Rentabilidad anual supuesta en porcentaje (puede ser 0 o negativa).
        anios: Años de la proyección (1-60).
        inflacion_anual_pct: Inflación anual supuesta para expresar el resultado en euros de hoy.
    """
    if not 1 <= int(anios) <= 60:
        raise ValueError("Los años deben estar entre 1 y 60.")
    if not -50 < rentabilidad_anual_pct <= 50:
        raise ValueError("La rentabilidad anual debe estar entre -50 % y 50 %.")
    tipo_mensual = (1 + rentabilidad_anual_pct / 100) ** (1 / 12) - 1

    def valor(meses: int) -> float:
        if tipo_mensual == 0:
            return capital_inicial + aportacion_mensual * meses
        factor = (1 + tipo_mensual) ** meses
        return capital_inicial * factor + aportacion_mensual * (factor - 1) / tipo_mensual

    anios = int(anios)
    final = valor(anios * 12)
    aportado = capital_inicial + aportacion_mensual * anios * 12
    deflactor = (1 + inflacion_anual_pct / 100) ** anios
    paso = 1 if anios <= 15 else 5
    evolucion = [{"anio": a, "valor": eur(valor(a * 12)), "aportado": eur(capital_inicial + aportacion_mensual * a * 12)}
                 for a in range(paso, anios + 1, paso)]
    if evolucion[-1]["anio"] != anios:
        evolucion.append({"anio": anios, "valor": eur(final), "aportado": eur(aportado)})
    return {
        "valor_final_nominal": eur(final),
        "valor_final_en_euros_de_hoy": eur(final / deflactor),
        "total_aportado": eur(aportado),
        "intereses_generados": eur(final - aportado),
        "supuestos": {"rentabilidad_anual_pct": rentabilidad_anual_pct, "inflacion_anual_pct": inflacion_anual_pct,
                      "capitalizacion": "mensual", "aportaciones": "al final de cada mes"},
        "evolucion": evolucion,
        "nota": "Proyección con una rentabilidad constante supuesta; los resultados reales varían y "
                "pueden ser negativos. No incluye impuestos ni comisiones.",
    }


def _ahorro_mensual_actual(ctx) -> float | None:
    try:
        datos = tabla(ctx)
    except ValueError:
        return None
    datos = datos[datos["fecha"] >= inicio_periodo(datos, 4)]
    incompleto = mes_incompleto(datos)
    if incompleto and datos["mes"].nunique() > 1:
        datos = datos[datos["mes"] != incompleto]
    meses = max(1, datos["mes"].nunique())
    return float(datos["importe"].sum()) / meses


@herramienta
def plan_ahorro(objetivo: float, meses: int, ya_ahorrado: float = 0.0,
                rentabilidad_anual_pct: float = 0.0, ctx=None) -> dict:
    """Calcula cuánto hay que ahorrar cada mes para llegar a un objetivo en un plazo y lo compara con lo que el usuario ahorra ahora.

    Úsala para "quiero juntar 6.000 € para junio", el fondo de emergencia o la entrada de un piso.

    Args:
        objetivo: Cantidad que se quiere tener al final, en euros.
        meses: Plazo en meses (1-600).
        ya_ahorrado: Lo que ya tiene ahorrado para ese objetivo, en euros.
        rentabilidad_anual_pct: Rentabilidad anual supuesta del ahorro en porcentaje (0 si es una cuenta sin interés).
    """
    if objetivo <= 0 or not 1 <= int(meses) <= 600:
        raise ValueError("El objetivo debe ser positivo y el plazo estar entre 1 y 600 meses.")
    meses = int(meses)
    tipo = (1 + rentabilidad_anual_pct / 100) ** (1 / 12) - 1
    if tipo == 0:
        necesaria = (objetivo - ya_ahorrado) / meses
    else:
        factor = (1 + tipo) ** meses
        necesaria = (objetivo - ya_ahorrado * factor) * tipo / (factor - 1)
    necesaria = max(0.0, necesaria)
    resultado = {
        "aportacion_mensual_necesaria": eur(necesaria),
        "objetivo": eur(objetivo),
        "meses": meses,
        "ya_ahorrado": eur(ya_ahorrado),
        "total_que_aportar": eur(necesaria * meses),
    }
    capacidad = _ahorro_mensual_actual(ctx)
    if capacidad is not None:
        resultado["ahorro_mensual_actual"] = eur(capacidad)
        resultado["es_viable_con_el_ritmo_actual"] = capacidad >= necesaria
        resultado["diferencia_mensual"] = eur(capacidad - necesaria)
    if necesaria == 0:
        resultado["nota"] = "Con lo ya ahorrado (y la rentabilidad supuesta) se alcanza el objetivo."
    return resultado


@herramienta
def regla_50_30_20(ingresos_mensuales: float | None = None, meses: int = 3, ctx=None) -> dict:
    """Compara el reparto de gastos del usuario con la regla orientativa 50/30/20: 50 % necesidades, 30 % deseos y 20 % ahorro.

    Úsala para "¿cómo debería repartir mi sueldo?" o "¿gasto demasiado en caprichos?".

    Args:
        ingresos_mensuales: Ingresos netos al mes en euros. Si no se indica, se calculan con los movimientos.
        meses: Meses naturales analizados, contando el actual (1-12).
    """
    real = None
    try:
        datos = tabla(ctx)
    except ValueError:
        datos = None
    if datos is not None:
        datos = datos[datos["fecha"] >= inicio_periodo(datos, max(1, min(int(meses), 12)))]
        incompleto = mes_incompleto(datos)
        if incompleto and datos["mes"].nunique() > 1:
            datos = datos[datos["mes"] != incompleto]
        numero_meses = max(1, datos["mes"].nunique())
        gastos = datos[datos["importe"] < 0]
        grupos = {"necesidades": 0.0, "deseos": 0.0, "otros": 0.0}
        detalle = {"necesidades": set(), "deseos": set(), "otros": set()}
        for categoria, importe in (-gastos.groupby("categoria")["importe"].sum()).items():
            grupo = grupo_50_30_20(categoria) or "otros"
            grupos[grupo] += float(importe) / numero_meses
            detalle[grupo].add(categoria)
        if ingresos_mensuales is None:
            ingresos_mensuales = float(datos.loc[datos["importe"] > 0, "importe"].sum()) / numero_meses
        gasto_total = sum(grupos.values())
        real = {**{k: eur(v) for k, v in grupos.items()}, "ahorro": eur(ingresos_mensuales - gasto_total)}
        categorias = {k: sorted(v) for k, v in detalle.items()}
    if not ingresos_mensuales:
        raise ValueError("Necesito los ingresos mensuales netos: pregúntaselos al usuario.")

    objetivo = {"necesidades": eur(ingresos_mensuales * 0.5), "deseos": eur(ingresos_mensuales * 0.3),
                "ahorro": eur(ingresos_mensuales * 0.2)}
    resultado = {"ingresos_mensuales": eur(ingresos_mensuales), "objetivo": objetivo}
    if real:
        resultado["real_mensual"] = real
        resultado["real_pct"] = {k: round(100 * v / ingresos_mensuales, 1) for k, v in real.items()}
        resultado["categorias_por_grupo"] = categorias
    resultado["nota"] = ("Regla orientativa, no una norma. 'Otros' son transferencias, efectivo y gastos sin "
                         "categoría. Con alquileres altos es normal que las necesidades pasen del 50 %.")
    return resultado
