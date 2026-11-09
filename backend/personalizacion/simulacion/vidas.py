"""
Vidas sintéticas con las que se prueba `perfilar` (personalizacion.md §3 y §8). Datos inventados.

`vida_lucia()`: la Lucía de la demo en Madrid, del 1/8 al 9/11/2026. Cobra 1.850 € el día 28, compra en
Mercadona, se mueve en metro, pide Glovo, tiene Netflix y Spotify y divide cenas con su grupo. Lleva
dentro los movimientos del escenario `cena-lucia` (grupo, cenas y Bizums), la verificación de 0 € de
Streamflix (14/10) y el duplicado de 9,99 € de LIBRERIA LUNA (15/10) de `demo-lucia`, y compras en
una farmacia (lista negra) que el perfil debe ignorar. Determinista: no usa azar.

Cada mes completo suma, sin contar lo que te devuelven tus amigos: supermercado 260 €, restaurantes
140 €, ocio 60 €, transporte 55 € y suscripciones 23,98 €. La mediana de sus compras con tarjeta es 9,80 €.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from ...plataforma.tipos import Movimiento

INICIO_LUCIA = date(2026, 8, 1)
HOY_LUCIA = date(2026, 11, 9)

_MERCADONA = [(2, "9.80"), (5, "9.80"), (9, "9.80"), (12, "42.30"), (16, "8.60"), (19, "48.70"),
              (23, "9.80"), (26, "52.10"), (30, "69.10")]                       # 260,00 €
_METRO = [(1, "9.80"), (7, "9.80"), (13, "7.90"), (18, "9.80"), (22, "7.90"), (27, "9.80")]   # 55,00 €
_GLOVO = [(4, "18.50"), (11, "22.40"), (20, "19.90"), (25, "24.20")]           # 85,00 €
_FARMACIA = [(6, "6.50"), (14, "6.50"), (21, "6.50")]                          # lista negra
# Lo que cambia cada mes (restaurantes y ocio), para que ningún otro comercio llegue a 3 cargos.
_EXTRAS = {
    8: [(8, "CAFE COMERCIAL", "9.80", "restaurantes"), (20, "LA TASCA", "45.20", "restaurantes"),
        (10, "CINES CALLAO", "9.80", "ocio"), (24, "SALA EL SOL", "50.20", "ocio")],
    9: [(6, "CAFETERIA EL ANDEN", "9.80", "restaurantes"), (21, "BAR EL BRILLANTE", "25.20", "restaurantes"),
        (10, "CINES IDEAL", "9.80", "ocio"), (24, "TEATRO KAPITAL", "50.20", "ocio")],
    10: [(17, "CHURRERIA SAN GINES", "8.00", "restaurantes"),
         (10, "CINESA PRINCIPE PIO", "9.80", "ocio"), (24, "BOLERA CHAMARTIN", "50.20", "ocio")],
}


def _tarjeta(i: str, dia: date, comercio: str, importe: str, categoria: str | None) -> Movimiento:
    return Movimiento(id=i, fecha=dia, concepto=f"COMPRA TARJETA {comercio}", comercio=comercio,
                      importe=-Decimal(importe), canal="tarjeta", categoria=categoria)


def _mes(anio: int, mes: int, hasta: date) -> list[Movimiento]:
    pre = f"vl-{anio}{mes:02d}"
    movs: list[Movimiento] = [
        Movimiento(id=f"{pre}-nom", fecha=date(anio, mes, 28), concepto="NOMINA ESTUDIO GRAFICO NORTE SL",
                   importe=Decimal("1850.00"), canal="transferencia", categoria="ingresos"),
        Movimiento(id=f"{pre}-nfx", fecha=date(anio, mes, 3), concepto="RECIBO NETFLIX.COM", comercio="NETFLIX",
                   importe=Decimal("-12.99"), canal="recibo", categoria="suscripciones"),
        Movimiento(id=f"{pre}-spo", fecha=date(anio, mes, 15), concepto="RECIBO SPOTIFY", comercio="SPOTIFY",
                   importe=Decimal("-10.99"), canal="recibo", categoria="suscripciones"),
    ]
    movs += [_tarjeta(f"{pre}-mer{n}", date(anio, mes, d), "MERCADONA", v, "supermercado")
             for n, (d, v) in enumerate(_MERCADONA)]
    movs += [_tarjeta(f"{pre}-met{n}", date(anio, mes, d), "METRO DE MADRID", v, "transporte")
             for n, (d, v) in enumerate(_METRO)]
    movs += [_tarjeta(f"{pre}-glo{n}", date(anio, mes, d), "GLOVO", v, "restaurantes") for n, (d, v) in enumerate(_GLOVO)]
    movs += [_tarjeta(f"{pre}-far{n}", date(anio, mes, d), "FARMACIA SOL", v, "salud") for n, (d, v) in enumerate(_FARMACIA)]
    movs += [_tarjeta(f"{pre}-ext{n}", date(anio, mes, d), c, v, cat) for n, (d, c, v, cat) in enumerate(_EXTRAS.get(mes, []))]
    return [m for m in movs if m.fecha <= hasta]


def _escenario_cena() -> list[Movimiento]:
    from ...escenarios.cargar import desde_dict, leer

    crudo = leer("cena-lucia")
    return desde_dict({"id": "vida-lucia", "usuario_id": "lucia", "activacion": crudo["activacion"],
                       "movimientos": crudo["movimientos"]}).movimientos


def _demo() -> list[Movimiento]:
    return [
        Movimiento(id="luc-v1", fecha=date(2026, 10, 14), concepto="VERIFICACION TARJETA STREAMFLIX",
                   comercio="STREAMFLIX", importe=Decimal("0.00"), canal="tarjeta", tipo_operacion="verificacion"),
        _tarjeta("luc-d1", date(2026, 10, 15), "LIBRERIA LUNA", "9.99", None),
        _tarjeta("luc-d2", date(2026, 10, 15), "LIBRERIA LUNA", "9.99", None),
    ]


def vida_lucia(hasta: date = HOY_LUCIA) -> list[Movimiento]:
    """Historial de Lucía hasta `hasta` (incluido), ordenado por fecha."""
    movs: list[Movimiento] = []
    for anio, mes in ((2026, 8), (2026, 9), (2026, 10), (2026, 11), (2026, 12)):
        if date(anio, mes, 1) <= hasta:
            movs += _mes(anio, mes, hasta)
    movs += [m for m in _escenario_cena() + _demo() if m.fecha <= hasta]
    return sorted(movs, key=lambda m: m.fecha)
