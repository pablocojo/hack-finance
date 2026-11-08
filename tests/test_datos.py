from datetime import date

import pytest

from backend.datos.categorias import categorizar_por_reglas, normalizar
from backend.datos.importar_csv import extraer_comercio, importar_csv, numero
from backend.datos.sinteticos import PERFILES, a_csv_banco, generar_movimientos

HOY = date(2026, 11, 7)


@pytest.mark.parametrize("perfil", sorted(PERFILES))
def test_sinteticos_deterministas_y_coherentes(perfil):
    a = generar_movimientos(perfil, meses=6, semilla=1, hasta=HOY)
    b = generar_movimientos(perfil, meses=6, semilla=1, hasta=HOY)
    assert a == b and len(a) > 100
    assert all(m["fecha"] <= HOY.isoformat() for m in a)
    assert [m["fecha"] for m in a] == sorted(m["fecha"] for m in a)
    assert any(m["categoria"] is None for m in a)  # hay trabajo para categorizar_movimientos
    assert len({m["id"] for m in a}) == len(a)


def test_csv_ida_y_vuelta():
    originales = generar_movimientos("autonomo", meses=3, hasta=HOY)
    importados, informe = importar_csv(a_csv_banco(originales).encode("cp1252"))
    assert informe["importadas"] == len(originales) and informe["descartadas"] == 0
    assert [m["importe"] for m in importados] == [m["importe"] for m in originales]
    assert importados[-1]["saldo"] == originales[-1]["saldo"]


def test_csv_con_cabecera_previa_y_cargo_abono():
    csv = ("Movimientos de la cuenta\nTitular: Ejemplo\n\n"
           "F. Operación;Concepto;Cargo;Abono;Saldo\n"
           "05/11/2026;COMPRA TARJETA MERCADONA;23,40;;1.200,00\n"
           "06/11/2026;NOMINA EMPRESA SL;;1.500,00;2.700,00\n"
           "07/11/2026;TRANSFERENCIA A ES91 2100 0418 4502 0005 1332;50,00;;2.650,00\n")
    movimientos, informe = importar_csv(csv)
    assert [m["importe"] for m in movimientos] == [-23.4, 1500.0, -50.0]
    assert movimientos[0]["categoria"] == "supermercado" and movimientos[1]["categoria"] == "ingresos"
    assert "[IBAN]" in movimientos[2]["concepto"] and informe["datos_personales_ocultados"] == 1


def test_csv_sin_columnas_da_error_claro():
    with pytest.raises(ValueError, match="columnas"):
        importar_csv("a,b,c\n1,2,3\n")


@pytest.mark.parametrize("texto,esperado", [
    ("1.234,56", 1234.56), ("-45,20", -45.2), ("45,20-", -45.2), ("(45,20)", -45.2),
    ("1,234.56", 1234.56), ("1.234", 1234.0), ("€ -3,00", -3.0), ("", None), ("abc", None),
])
def test_numeros_de_bancos(texto, esperado):
    assert numero(texto) == esperado


def test_comercio_y_categorias():
    assert extraer_comercio("COMPRA TARJ. 5402XXXXXXXX1234 MERCADONA VALENCIA") == "MERCADONA VALENCIA"
    assert normalizar("  Fármacia   López ") == "FARMACIA LOPEZ"
    assert categorizar_por_reglas("RECIBO AMAZON PRIME", -4.99) == "suscripciones"
    assert categorizar_por_reglas("COMPRA AMAZON.ES", -20) == "compras"
    assert categorizar_por_reglas("RECIBO TGSS CUOTA AUTONOMOS", -310) == "impuestos"
    assert categorizar_por_reglas("CUALQUIER COSA", 100) == "ingresos"
    assert categorizar_por_reglas("XYZ 123", -5) is None
