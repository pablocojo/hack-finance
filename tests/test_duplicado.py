"""`cargo_duplicado` (M1, motor.md §3.2): escenarios etiquetados, trampas, umbral como parámetro y
que el detector no mira el futuro."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal

import pytest

from backend import motor
from backend.escenarios import cargar
from backend.motor import parametros
from backend.plataforma.tipos import Momento, Movimiento

POSITIVOS = ("tpv-doble", "gimnasio-doble")
TRAMPAS = ("dos-cafes", "cuotas-gimnasio", "compra-devolucion-compra")


@pytest.fixture(scope="module")
def reproducidos():
    return {e: cargar.reproducir(cargar.cargar(e), con_perfil=False) for e in POSITIVOS + TRAMPAS}


def _dup(momentos: list[Momento]) -> list[Momento]:
    return [m for m in momentos if m.tipo == "cargo_duplicado"]


@pytest.mark.parametrize("escenario_id", POSITIVOS + TRAMPAS)
def test_escenarios_sin_omitidos_falsos_ni_trampas(escenario_id, reproducidos):
    esc = cargar.cargar(escenario_id)
    r = cargar.evaluar(esc, reproducidos[escenario_id])
    assert r["omitidos"] == 0, r["detalle_omitidos"]
    assert r["falsos_positivos"] == [] and r["trampas_violadas"] == []
    assert all(d == 0 for d in r["retrasos"])


@pytest.mark.parametrize("escenario_id", TRAMPAS)
def test_trampas_no_dan_ningun_duplicado(escenario_id, reproducidos):
    assert _dup(reproducidos[escenario_id]) == []


def test_tpv_doble(reproducidos):
    [m] = _dup(reproducidos["tpv-doble"])
    assert m.fecha == date(2026, 10, 17) and m.movimientos == ["tpv-z1", "tpv-z2"]
    d = m.datos
    assert d["comercio"] == "ZARA" and d["importe"] == Decimal("59.95") and d["canal"] == "tarjeta"
    assert d["ids"] == ["tpv-z1", "tpv-z2"] and d["id_segundo"] == "tpv-z2" and d["dias_entre"] == 0
    assert d["fechas"] == ["2026-10-17", "2026-10-17"]
    assert "fecha_limite_devolucion" not in d
    assert m.impacto_eur == Decimal("59.95") and m.confianza == 0.70
    assert m.explicacion == "Hay dos cargos iguales de 59,95 € en Zara el 17/10; puede ser un cobro duplicado."


def test_gimnasio_doble_recibo(reproducidos):
    [m] = _dup(reproducidos["gimnasio-doble"])
    assert m.fecha == date(2026, 11, 6) and m.movimientos == ["gim-11a", "gim-11b"]
    d = m.datos
    assert d["canal"] == "recibo" and d["dias_entre"] == 1 and d["fecha_limite_devolucion"] == "2027-01-01"
    assert d["serie_id"] == "GIMNASIO VITAL SPORT:1m" and m.confianza == 0.90
    assert "puedes devolver" in m.explicacion and "1/1/2027" in m.explicacion
    leido = json.loads(m.model_dump_json())
    assert leido["datos"]["importe"] == "39.90" and leido["impacto_eur"] == "39.90"


# --- Reglas sueltas, con `procesar` día a día -------------------------------------------------

def _mov(i, fecha, concepto, importe, canal="tarjeta", categoria="compras", comercio=None):
    return Movimiento(id=i, fecha=fecha, concepto=concepto, comercio=comercio, importe=Decimal(importe),
                      canal=canal, categoria=categoria)


def _dia_a_dia(movs: list[Movimiento], desde: date, hasta: date, uid: str = "__dup__") -> list[Momento]:
    salida: list[Momento] = []
    motor.reiniciar(uid)
    try:
        dia = desde
        while dia <= hasta:
            salida += motor.procesar(uid, [m for m in movs if m.fecha == dia], dia)
            dia += timedelta(days=1)
    finally:
        motor.reiniciar(uid)
    return salida


D = date(2026, 10, 10)


def test_umbral_de_tarjeta_es_un_parametro(monkeypatch):
    """El duplicado de la demo (9,99 €) no sale con 15 €; con el umbral personal de Lucía (6 €), sí."""
    movs = [_mov("l1", D, "COMPRA TARJETA LIBRERIA LUNA", "-9.99"), _mov("l2", D, "COMPRA TARJETA LIBRERIA LUNA", "-9.99")]
    assert _dup(_dia_a_dia(movs, D, D)) == []
    defecto = parametros.DEFECTO["cargo_duplicado"]
    assert defecto.IMPORTE_MIN_TARJETA == Decimal("15")
    monkeypatch.setitem(parametros.DEFECTO, "cargo_duplicado", replace(defecto, IMPORTE_MIN_TARJETA=Decimal("6")))
    [m] = _dup(_dia_a_dia(movs, D, D))
    assert m.datos["comercio"] == "LIBRERIA LUNA" and m.datos["id_segundo"] == "l2"


@pytest.mark.parametrize("segundo, sale", [
    (_mov("b", D + timedelta(days=3), "COMPRA TARJETA MEDIA MARKT", "-89.00"), True),    # 3 días: aún cuenta
    (_mov("b", D + timedelta(days=4), "COMPRA TARJETA MEDIA MARKT", "-89.00"), False),   # 4 días: no
    (_mov("b", D, "COMPRA TARJETA MEDIA MARKT", "-89.01"), False),                       # un céntimo distinto
    (_mov("b", D, "COMPRA TARJETA DECATHLON", "-89.00"), False),                         # otro comercio
    (_mov("b", D, "COMPRA TARJETA MEDIA MARKT", "89.00"), False),                        # abono, no cargo
])
def test_par_mismo_comercio_importe_y_ventana(segundo, sale):
    primero = _mov("a", D, "COMPRA TARJETA MEDIA MARKT", "-89.00")
    momentos = _dup(_dia_a_dia([primero, segundo], D, D + timedelta(days=5)))
    assert bool(momentos) is sale
    if sale:
        assert momentos[0].fecha == segundo.fecha and momentos[0].confianza == 0.55
        assert momentos[0].datos["dias_entre"] == 3


def test_transporte_y_verificaciones_no_son_duplicados():
    movs = [
        _mov("t1", D, "RECARGA ABONO METRO", "-20.00", categoria="transporte", comercio="METRO DE MADRID"),
        _mov("t2", D, "RECARGA ABONO METRO", "-20.00", categoria="transporte", comercio="METRO DE MADRID"),
        _mov("v1", D, "VERIFICACION TARJETA STREAMFLIX", "0.00", comercio="STREAMFLIX"),
        _mov("v2", D, "VERIFICACION TARJETA STREAMFLIX", "0.00", comercio="STREAMFLIX"),
    ]
    assert _dup(_dia_a_dia(movs, D, D)) == []


def test_no_se_repite_en_dias_siguientes():
    """Tres cargos iguales el mismo día: un solo aviso (el razonador no pone un movimiento en dos
    momentos) y no reaparece los días siguientes."""
    movs = [_mov(f"x{i}", D, "COMPRA TARJETA FNAC", "-30.00") for i in range(3)]
    momentos = _dup(_dia_a_dia(movs, D, D + timedelta(days=4)))
    assert [m.movimientos for m in momentos] == [["x0", "x1"]]


# --- No mira el futuro ------------------------------------------------------------------------

def _con_futuro(esc: cargar.Escenario) -> list[Momento]:
    """Todos los movimientos en el estado desde el primer día: si el detector no cortara por `hoy`,
    los vería antes de tiempo."""
    uid = f"__dup_futuro__:{esc.id}"
    momentos: list[Momento] = []
    try:
        motor.cargar_historial(uid, esc.previos(), esc.activacion)
        motor._estado(uid).agregar(list(esc.movimientos))
        dia = esc.activacion + timedelta(days=1)
        while dia <= esc.hasta:
            momentos += motor.procesar(uid, esc.del_dia(dia), dia)
            dia += timedelta(days=1)
    finally:
        motor.reiniciar(uid)
    return momentos


@pytest.mark.parametrize("escenario_id", ("tpv-doble", "gimnasio-doble", "compra-devolucion-compra"))
def test_no_mira_el_futuro(escenario_id, reproducidos):
    esc = cargar.cargar(escenario_id)
    firma = lambda ms: [(m.id, m.fecha, tuple(m.movimientos), m.confianza) for m in ms]  # noqa: E731
    assert firma(_con_futuro(esc)) == firma(reproducidos[escenario_id])


def test_el_segundo_cargo_no_se_ve_antes_de_su_dia():
    """Con el segundo recibo ya dentro del estado, el 5/11 no hay duplicado: sale el 6/11."""
    esc = cargar.cargar("gimnasio-doble")
    hasta_el_5 = [m for m in _con_futuro(esc) if m.fecha <= date(2026, 11, 5)]
    assert _dup(hasta_el_5) == []
