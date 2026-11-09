"""
Movimientos bancarios sintéticos y realistas para la demo y los tests.

Tres perfiles: estudiante, familia y autónomo. Cada uno trae a propósito un cargo
duplicado, un gasto inusual, un comercio nuevo con un importe alto y algunos
movimientos sin categoría, para que las herramientas tengan algo que encontrar.

    from backend.datos.sinteticos import generar_movimientos
    movimientos = generar_movimientos("familia", meses=6, semilla=42)

Los datos son inventados. Nunca uses datos personales reales en la demo.
"""

from __future__ import annotations

import calendar
import random
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

PERFILES = {
    "estudiante": {
        "descripcion": "Estudiante universitaria en Valencia con un trabajo a tiempo parcial",
        "saldo_inicial": 850,
        "fijos": [
            (1, "TRANSFERENCIA EMITIDA ALQUILER HABITACION", "ALQUILER HABITACION", -380.00, "vivienda"),
            (1, "TRANSFERENCIA RECIBIDA DE PADRES", "TRANSFERENCIA PADRES", 350.00, "ingresos"),
            (3, "RECIBO CONSORCIO TRANSPORTES ABONO JOVEN", "CONSORCIO TRANSPORTES", -20.00, "transporte"),
            (5, "RECIBO GIMNASIO FITUP", "GIMNASIO FITUP", -24.90, "ocio"),
            (8, "RECIBO SPOTIFY ESTUDIANTES", "SPOTIFY", -5.99, "suscripciones"),
            (10, "RECIBO DIGI MOBIL", "DIGI", -15.00, "suministros"),
            (15, "RECIBO NETFLIX.COM", "NETFLIX", -7.99, "suscripciones"),
            (28, "NOMINA CAFETERIA CAMPUS SL", "CAFETERIA CAMPUS SL", (480.00, 560.00), "ingresos"),
        ],
        "variables": [
            (1.5, "supermercado", [("COMPRA TARJETA MERCADONA VALENCIA", "MERCADONA", 18, 55),
                                   ("COMPRA TARJETA LIDL BENIMACLET", "LIDL", 12, 40)]),
            (2.0, "restaurantes", [("COMPRA TARJETA BAR LA PLAZA", "BAR LA PLAZA", 3, 12),
                                   ("COMPRA TARJETA GLOVO", "GLOVO", 12, 24),
                                   ("COMPRA TARJETA CAFETERIA FACULTAD", "CAFETERIA FACULTAD", 2, 6)]),
            (0.5, "ocio", [("COMPRA TARJETA CINES YELMO", "CINES YELMO", 7, 9),
                           ("COMPRA TARJETA TICKETMASTER ENTRADAS", "TICKETMASTER", 20, 45)]),
            (0.4, "compras", [("COMPRA TARJETA AMAZON.ES", "AMAZON", 9, 45),
                              ("COMPRA TARJETA PRIMARK VALENCIA", "PRIMARK", 10, 35)]),
            (0.3, "transporte", [("COMPRA TARJETA CABIFY", "CABIFY", 7, 14),
                                 ("COMPRA TARJETA RENFE CERCANIAS", "RENFE", 2, 8)]),
            (0.15, "educacion", [("COMPRA TARJETA LIBRERIA PARIS VALENCIA", "LIBRERIA PARIS", 8, 30)]),
            (0.1, "salud", [("COMPRA TARJETA FARMACIA AVDA PUERTO", "FARMACIA AVDA PUERTO", 4, 18)]),
            (0.3, "transferencias", [("BIZUM ENVIADO COMPAÑERA PISO", "BIZUM", 5, 30)]),
        ],
        "periodicos": [],
        "anomalias": {
            "duplicado": ("RECIBO GIMNASIO FITUP", "GIMNASIO FITUP", -24.90, "ocio"),
            "inusual": ("COMPRA TARJETA MEDIAMARKT VALENCIA", "MEDIAMARKT", -389.00, "compras"),
        },
    },
    "familia": {
        "descripcion": "Pareja con dos hijos en Madrid, con dos nóminas e hipoteca",
        "saldo_inicial": 4200,
        "fijos": [
            (2, "RECIBO PRESTAMO HIPOTECARIO", "HIPOTECA", -780.00, "vivienda"),
            (4, "RECIBO COMUNIDAD PROPIETARIOS", "COMUNIDAD PROPIETARIOS", -65.00, "vivienda"),
            (5, "RECIBO COLEGIO SAN JORGE COMEDOR", "COLEGIO SAN JORGE", -160.00, "educacion"),
            (6, "RECIBO NETFLIX.COM", "NETFLIX", -13.99, "suscripciones"),
            (8, "RECIBO MOVISTAR FIBRA Y MOVIL", "MOVISTAR", -85.00, "suministros"),
            (9, "RECIBO DISNEY PLUS", "DISNEY PLUS", -9.99, "suscripciones"),
            (11, "RECIBO SPOTIFY FAMILIAR", "SPOTIFY", -17.99, "suscripciones"),
            (12, "RECIBO IBERDROLA CLIENTES", "IBERDROLA", (-115.00, -70.00), "suministros"),
            (15, "RECIBO MAPFRE SEGURO HOGAR", "MAPFRE", -32.40, "seguros"),
            (15, "RECIBO LINEA DIRECTA SEGURO COCHE", "LINEA DIRECTA", -48.20, "seguros"),
            (20, "RECIBO AMPA EXTRAESCOLARES", "AMPA EXTRAESCOLARES", -60.00, "educacion"),
            (27, "NOMINA ACME LOGISTICA SA", "ACME LOGISTICA SA", 2150.00, "ingresos"),
            (28, "NOMINA HOSPITAL SAN RAFAEL", "HOSPITAL SAN RAFAEL", 1680.00, "ingresos"),
        ],
        "variables": [
            (2.0, "supermercado", [("COMPRA TARJETA MERCADONA MADRID", "MERCADONA", 45, 140),
                                   ("COMPRA TARJETA CARREFOUR MARKET", "CARREFOUR", 35, 120),
                                   ("COMPRA TARJETA FRUTERIA EL HUERTO", "FRUTERIA EL HUERTO", 8, 22)]),
            (1.2, "restaurantes", [("COMPRA TARJETA RESTAURANTE CASA PEPE", "RESTAURANTE CASA PEPE", 35, 75),
                                   ("COMPRA TARJETA TELEPIZZA", "TELEPIZZA", 18, 32),
                                   ("COMPRA TARJETA CAFETERIA LA ESQUINA", "CAFETERIA LA ESQUINA", 4, 12)]),
            (0.6, "transporte", [("COMPRA TARJETA REPSOL ESTACION SERVICIO", "REPSOL", 45, 70),
                                 ("COMPRA TARJETA PARKING CENTRO", "PARKING CENTRO", 3, 9)]),
            (0.4, "ocio", [("COMPRA TARJETA CINES KINEPOLIS", "CINES KINEPOLIS", 25, 40),
                           ("COMPRA TARJETA DECATHLON", "DECATHLON", 15, 60)]),
            (0.5, "compras", [("COMPRA TARJETA AMAZON.ES", "AMAZON", 12, 80),
                              ("COMPRA TARJETA ZARA", "ZARA", 25, 90),
                              ("COMPRA TARJETA IKEA SAN SEBASTIAN", "IKEA", 20, 120)]),
            (0.3, "salud", [("COMPRA TARJETA FARMACIA LDO GARCIA", "FARMACIA LDO GARCIA", 5, 30)]),
            (0.2, "transferencias", [("BIZUM ENVIADO", "BIZUM", 10, 40)]),
            (0.15, "efectivo", [("RETIRADA CAJERO", "CAJERO", 20, 60)]),
        ],
        "periodicos": [
            # (meses, día, concepto, comercio, (mínimo, máximo), categoría)
            ((1, 3, 5, 7, 9, 11), 18, "RECIBO CANAL DE ISABEL II AGUA", "CANAL DE ISABEL II",
             (-55.00, -38.00), "suministros"),
            ((10,), 10, "RECIBO IBI AYUNTAMIENTO", "IBI AYUNTAMIENTO", (-420.00, -420.00), "impuestos"),
        ],
        "anomalias": {
            "duplicado": ("RECIBO NETFLIX.COM", "NETFLIX", -13.99, "suscripciones"),
            "inusual": ("COMPRA TARJETA TALLER MECANICO AUTOFIX", "TALLER AUTOFIX", -640.00, "transporte"),
        },
    },
    "autonomo": {
        "descripcion": "Diseñador gráfico autónomo en Sevilla con ingresos variables",
        "saldo_inicial": 6500,
        "fijos": [
            (1, "TRANSFERENCIA EMITIDA ALQUILER VIVIENDA", "ALQUILER VIVIENDA", -850.00, "vivienda"),
            (3, "RECIBO COWORKING LA NAVE", "COWORKING LA NAVE", -180.00, "trabajo"),
            (5, "RECIBO GOOGLE WORKSPACE", "GOOGLE WORKSPACE", -6.80, "suscripciones"),
            (7, "RECIBO ADOBE CREATIVE CLOUD", "ADOBE", -66.54, "suscripciones"),
            (10, "RECIBO GESTORIA PEREZ ASESORES", "GESTORIA PEREZ", -60.50, "trabajo"),
            (12, "RECIBO ENDESA ENERGIA", "ENDESA", (-80.00, -45.00), "suministros"),
            (14, "RECIBO VODAFONE FIBRA", "VODAFONE", -42.00, "suministros"),
            (20, "RECIBO SEGURO RC PROFESIONAL", "SEGURO RC PROFESIONAL", -25.00, "seguros"),
            (28, "RECIBO TGSS CUOTA AUTONOMOS", "TGSS", -310.00, "impuestos"),
        ],
        "variables": [
            (1.3, "supermercado", [("COMPRA TARJETA MERCADONA SEVILLA", "MERCADONA", 25, 80),
                                   ("COMPRA TARJETA SUPERMERCADO DIA", "DIA", 10, 35)]),
            (1.5, "restaurantes", [("COMPRA TARJETA RESTAURANTE LA ALAMEDA", "RESTAURANTE LA ALAMEDA", 12, 40),
                                   ("COMPRA TARJETA CAFETERIA TRIANA", "CAFETERIA TRIANA", 2, 6),
                                   ("COMPRA TARJETA GLOVO", "GLOVO", 14, 26)]),
            (0.5, "transporte", [("COMPRA TARJETA CABIFY", "CABIFY", 8, 16),
                                 ("COMPRA TARJETA GASOLINERA CEPSA", "CEPSA", 40, 60),
                                 ("COMPRA TARJETA RENFE AVE", "RENFE", 35, 80)]),
            (0.4, "compras", [("COMPRA TARJETA AMAZON.ES", "AMAZON", 15, 120)]),
            (0.3, "ocio", [("COMPRA TARJETA CINES NERVION", "CINES NERVION", 7, 10),
                           ("COMPRA TARJETA DECATHLON", "DECATHLON", 15, 50)]),
            (0.1, "salud", [("COMPRA TARJETA FARMACIA TRIANA", "FARMACIA TRIANA", 5, 25)]),
        ],
        "ingresos_variables": {
            "por_mes": (2, 4),
            "clientes": ["ESTUDIO NORTE SL", "BODEGAS RIBERA SA", "APP SALUD SL",
                         "TIENDA VERDE SL", "AGENCIA SUR SL"],
            "importe": (650, 2400),
        },
        "periodicos": [
            ((1, 4, 7, 10), 20, "AEAT MODELO 303 IVA", "AEAT MODELO 303", (-1400.00, -700.00), "impuestos"),
            ((1, 4, 7, 10), 20, "AEAT MODELO 130 IRPF", "AEAT MODELO 130", (-650.00, -300.00), "impuestos"),
        ],
        "anomalias": {
            "duplicado": ("RECIBO GOOGLE WORKSPACE", "GOOGLE WORKSPACE", -6.80, "suscripciones"),
            "inusual": ("COMPRA TARJETA PCCOMPONENTES", "PCCOMPONENTES", -899.00, "compras"),
        },
    },
}

COMERCIO_NUEVO = ("COMPRA ONLINE TECHSHOP-EU", "TECHSHOP-EU", -249.99, "compras")
PROPORCION_SIN_CATEGORIA = 0.12


def _centimos(valor: float) -> float:
    return float(Decimal(str(valor)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _restar_meses(dia: date, meses: int) -> date:
    mes = dia.month - meses
    anio = dia.year
    while mes <= 0:
        mes += 12
        anio -= 1
    return date(anio, mes, 1)


def _importe(rng: random.Random, valor) -> float:
    if isinstance(valor, tuple):
        return _centimos(rng.uniform(*valor))
    return _centimos(valor)


def _anadir_anomalias(crudos: list[tuple], anomalias: dict, rng: random.Random, inicio: date, hasta: date) -> None:
    """Duplicado, gasto inusual y comercio nuevo, siempre dentro del último mes."""
    concepto, comercio, importe, categoria = anomalias["duplicado"]
    previos = [m for m in crudos if m[2] == comercio and m[0] >= hasta - timedelta(days=40)]
    if previos:  # el mismo recibo cobrado dos veces el mismo día
        crudos.append(max(previos, key=lambda m: m[0]))
    else:
        fecha_duplicado = max(inicio, hasta - timedelta(days=rng.randint(12, 25)))
        crudos.append((fecha_duplicado, concepto, comercio, importe, categoria))
        crudos.append((fecha_duplicado, concepto, comercio, importe, categoria))
    concepto, comercio, importe, categoria = anomalias["inusual"]
    crudos.append((max(inicio, hasta - timedelta(days=rng.randint(6, 18))), concepto, comercio, importe, categoria))
    concepto, comercio, importe, categoria = COMERCIO_NUEVO
    crudos.append((max(inicio, hasta - timedelta(days=rng.randint(1, 5))), concepto, comercio, importe, categoria))


def generar_movimientos(
    perfil: str = "familia",
    meses: int = 6,
    semilla: int = 42,
    hasta: date | None = None,
    anomalias: bool = True,
) -> list[dict]:
    """Genera movimientos ordenados por fecha, con saldo acumulado.

    Con `anomalias=False` no añade el duplicado, el gasto inusual ni el comercio nuevo: es el
    «fondo» limpio de los escenarios del motor (ruido de fondo).
    """
    if perfil not in PERFILES:
        raise ValueError(f"Perfil desconocido: {perfil}. Elige uno de {sorted(PERFILES)}.")
    datos = PERFILES[perfil]
    rng = random.Random(semilla + sum(ord(c) for c in perfil))
    hasta = hasta or date.today()
    inicio = _restar_meses(hasta.replace(day=1), max(1, meses) - 1)
    crudos: list[tuple] = []  # (fecha, concepto, comercio, importe, categoria)

    dia = inicio
    while dia <= hasta:
        ultimo_dia_mes = calendar.monthrange(dia.year, dia.month)[1]
        for dia_fijo, concepto, comercio, valor, categoria in datos["fijos"]:
            if dia.day == min(dia_fijo, ultimo_dia_mes):
                crudos.append((dia, concepto, comercio, _importe(rng, valor), categoria))
        for meses_periodo, dia_fijo, concepto, comercio, valor, categoria in datos["periodicos"]:
            if dia.month in meses_periodo and dia.day == dia_fijo:
                crudos.append((dia, concepto, comercio, _importe(rng, valor), categoria))
        for veces_semana, categoria, comercios in datos["variables"]:
            if rng.random() < veces_semana / 7:
                concepto, comercio, minimo, maximo = rng.choice(comercios)
                crudos.append((dia, concepto, comercio, -_centimos(rng.uniform(minimo, maximo)), categoria))
        dia += timedelta(days=1)

    ingresos = datos.get("ingresos_variables")
    if ingresos:
        mes = inicio
        numero_factura = 1
        while mes <= hasta:
            ultimo = calendar.monthrange(mes.year, mes.month)[1]
            for _ in range(rng.randint(*ingresos["por_mes"])):
                fecha = mes.replace(day=rng.randint(1, ultimo))
                if fecha > hasta:
                    continue
                cliente = rng.choice(ingresos["clientes"])
                concepto = f"TRANSFERENCIA RECIBIDA {cliente} FRA {fecha.year}-{numero_factura:03d}"
                numero_factura += 1
                crudos.append((fecha, concepto, cliente, _centimos(rng.uniform(*ingresos["importe"])), "ingresos"))
            mes = (mes.replace(day=28) + timedelta(days=4)).replace(day=1)

    # Anomalías a propósito, siempre dentro del último mes.
    if anomalias:
        _anadir_anomalias(crudos, datos["anomalias"], rng, inicio, hasta)

    crudos.sort(key=lambda m: (m[0], -m[3]))  # ingresos primero dentro del mismo día
    saldo = Decimal(str(datos["saldo_inicial"]))
    prefijo = perfil[:3]
    movimientos = []
    for numero, (fecha, concepto, comercio, importe, categoria) in enumerate(crudos, start=1):
        saldo += Decimal(str(importe))
        sin_categoria = importe < 0 and categoria not in ("vivienda", "impuestos") and (
            rng.random() < PROPORCION_SIN_CATEGORIA
        )
        movimientos.append({
            "id": f"{prefijo}-{numero:05d}",
            "fecha": fecha.isoformat(),
            "concepto": concepto,
            "comercio": comercio,
            "importe": importe,
            "categoria": None if sin_categoria else categoria,
            "saldo": float(saldo.quantize(Decimal("0.01"))),
        })
    return movimientos


def descripcion_perfil(perfil: str) -> str:
    return PERFILES[perfil]["descripcion"]


def a_csv_banco(movimientos: list[dict]) -> str:
    """Exporta en el formato típico de un banco español: punto y coma, coma decimal y dd/mm/aaaa."""

    def numero(valor: float) -> str:
        texto = f"{valor:,.2f}"  # 1,234.56
        return texto.replace(",", "X").replace(".", ",").replace("X", ".")

    lineas = ["Fecha;Concepto;Importe;Saldo"]
    for m in movimientos:
        anio, mes, dia = m["fecha"].split("-")
        lineas.append(f"{dia}/{mes}/{anio};{m['concepto']};{numero(m['importe'])};{numero(m['saldo'])}")
    return "\n".join(lineas) + "\n"
