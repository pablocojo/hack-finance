from decimal import Decimal

import pytest

from backend.herramientas.calculos import calcular_prestamo, interes_compuesto, plan_ahorro, regla_50_30_20


def test_prestamo_sistema_frances():
    r = calcular_prestamo(10_000, 6, 36)
    assert r["cuota_mensual"] == Decimal("304.22")
    assert r["tae_pct"] == pytest.approx(6.17, abs=0.01)  # (1 + 0,005)^12 - 1
    assert r["total_intereses"] == Decimal("951.88")
    assert r["coste_total_credito"] == r["total_intereses"]


def test_prestamo_comision_sube_la_tae():
    sin = calcular_prestamo(10_000, 6, 36)
    con = calcular_prestamo(10_000, 6, 36, comision_apertura_pct=2)
    assert con["comision_apertura"] == Decimal("200.00")
    assert con["tae_pct"] > sin["tae_pct"]
    assert con["coste_total_credito"] == con["total_intereses"] + Decimal("200.00")


def test_hipoteca_y_tipo_cero():
    assert calcular_prestamo(150_000, 3.2, 360)["cuota_mensual"] == Decimal("648.70")
    cero = calcular_prestamo(1_200, 0, 12)
    assert cero["cuota_mensual"] == Decimal("100.00") and cero["total_intereses"] == 0


@pytest.mark.parametrize("argumentos", [
    {"importe": 0, "tin_anual": 5, "plazo_meses": 12},
    {"importe": 1000, "tin_anual": 5, "plazo_meses": 0},
    {"importe": 1000, "tin_anual": 80, "plazo_meses": 12},
])
def test_prestamo_valida_entradas(argumentos):
    with pytest.raises(ValueError):
        calcular_prestamo(**argumentos)


def test_interes_compuesto():
    sin_interes = interes_compuesto(0, 100, 0, 1, inflacion_anual_pct=0)
    assert sin_interes["valor_final_nominal"] == 1200
    r = interes_compuesto(1000, 100, 5, 20, 2)
    assert r["total_aportado"] == 25_000
    assert r["valor_final_nominal"] > r["total_aportado"] > 0
    assert r["valor_final_en_euros_de_hoy"] < r["valor_final_nominal"]
    assert r["evolucion"][-1]["anio"] == 20


def test_plan_ahorro_con_y_sin_datos(sesion_familia):
    sin_datos = plan_ahorro(6_000, 12)
    assert sin_datos["aportacion_mensual_necesaria"] == 500 and "ahorro_mensual_actual" not in sin_datos
    con_datos = plan_ahorro(6_000, 12, ctx=sesion_familia)
    assert "es_viable_con_el_ritmo_actual" in con_datos
    assert plan_ahorro(1_000, 10, ya_ahorrado=2_000)["aportacion_mensual_necesaria"] == 0


def test_regla_50_30_20(sesion_familia):
    r = regla_50_30_20(ctx=sesion_familia)
    assert r["objetivo"]["necesidades"] == pytest.approx(r["ingresos_mensuales"] * 0.5, abs=0.01)
    assert set(r["real_mensual"]) == {"necesidades", "deseos", "otros", "ahorro"}
    assert regla_50_30_20(ingresos_mensuales=2_000)["objetivo"]["ahorro"] == 400
    with pytest.raises(ValueError):
        regla_50_30_20()
