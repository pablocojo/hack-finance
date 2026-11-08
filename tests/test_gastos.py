import pytest

from backend.datos.almacen import Sesion
from backend.herramientas import gastos


def test_resumen_cuadra(sesion_familia):
    r = gastos.resumen_gastos(meses=3, ctx=sesion_familia)
    assert r["ahorro"] == pytest.approx(r["ingresos"] - r["gastos"], abs=0.01)
    assert sum(c["importe"] for c in r["por_categoria"]) == pytest.approx(r["gastos"], abs=0.05)
    assert r["por_categoria"][0]["categoria"] == "vivienda"
    assert len(r["por_mes"]) == 3 and "nota" in r  # noviembre está incompleto


def test_buscar_movimientos(sesion_familia):
    r = gastos.buscar_movimientos(texto="mercadona", solo_gastos=True, ctx=sesion_familia)
    assert r["encontrados"] > 0
    assert all("MERCADONA" in m["concepto"] for m in r["movimientos"])
    filtrado = gastos.buscar_movimientos(categoria="Educación", importe_min=100, ctx=sesion_familia)
    assert all(abs(m["importe"]) >= 100 and m["categoria"] == "educacion" for m in filtrado["movimientos"])


def test_anomalias_encuentran_lo_sembrado(sesion_familia):
    r = gastos.detectar_anomalias(meses=3, ctx=sesion_familia)
    assert any(d["comercio"] == "NETFLIX" for d in r["posibles_duplicados"])
    sospechosos = {m["concepto"] for m in r["importes_inusuales"] + r["comercios_nuevos_con_importe_alto"]}
    assert any("TALLER" in c for c in sospechosos)
    assert any("TECHSHOP" in c for c in sospechosos)
    assert not any("IBI" in c or "HIPOTECA" in c for c in sospechosos)


def test_recurrentes(sesion_familia):
    r = gastos.gastos_recurrentes(ctx=sesion_familia)
    comercios = {x["comercio"] for x in r["recurrentes"]}
    assert {"HIPOTECA", "NETFLIX", "SPOTIFY", "IBERDROLA"} <= comercios
    assert not comercios & {"MERCADONA", "CARREFOUR", "AMAZON"}
    agua = next(x for x in r["recurrentes"] if x["comercio"] == "CANAL DE ISABEL II")
    assert agua["periodo_meses"] == 2
    assert r["suscripciones"]["cantidad"] == 3


def test_prevision_saldo(sesion_familia):
    r = gastos.prevision_saldo(dias=30, ctx=sesion_familia)
    assert r["saldo_actual"] == sesion_familia.movimientos[-1]["saldo"]
    assert any(e["comercio"] == "HIPOTECA" for e in r["proximos_movimientos_fijos"])
    assert r["saldo_minimo_estimado"] <= r["saldo_actual"]


def test_prevision_sin_saldo_pide_el_dato():
    sesion = Sesion(id="x")
    sesion.movimientos = [{"id": "1", "fecha": "2026-11-01", "concepto": "COMPRA", "importe": -10.0,
                           "categoria": "otros"}]
    with pytest.raises(ValueError, match="saldo"):
        gastos.prevision_saldo(ctx=sesion)
    assert gastos.prevision_saldo(dias=10, saldo_actual=500, ctx=sesion)["saldo_actual"] == 500


def test_sin_movimientos_explica_que_hacer():
    with pytest.raises(ValueError, match="CSV"):
        gastos.resumen_gastos(ctx=Sesion(id="vacia"))


def test_categorizar_usa_reglas_y_luego_haiku(sesion_familia, falso):
    from backend.claude_falso import respuesta_json

    pendientes = [m for m in sesion_familia.movimientos if not m["categoria"]]
    assert pendientes
    sesion_familia.movimientos.append({"id": "raro-1", "fecha": "2026-11-06", "concepto": "PAGO XJ-9 SERVICIOS",
                                       "comercio": "XJ-9", "importe": -15.0, "categoria": None})
    cliente = falso([respuesta_json({"clasificacion": [{"id": "raro-1", "categoria": "otros"}]})])
    r = gastos.categorizar_movimientos(ctx=sesion_familia)
    assert r["clasificados_por_reglas"] >= len(pendientes) - 1
    assert r["clasificados_por_ia"] == 1 and r["siguen_sin_categoria"] == 0
    peticion = cliente.peticiones[0]
    assert peticion["model"] == "claude-haiku-5-5"
    assert peticion["extra_body"]["output_config"]["format"]["type"] == "json_schema"
