"""`demo-lucia` (M8): el escenario único de la demo. Cena el 9/11, Streamflix el 10/11, la luz el 12/11 y el
duplicado de «LIBRERIA LUNA» (solo con perfil). Las fechas salen de las etiquetas del escenario."""

from __future__ import annotations

import socket
from datetime import date
from decimal import Decimal

import pytest

from backend import motor
from backend.escenarios import cargar


@pytest.fixture(autouse=True)
def sin_internet(monkeypatch):
    def prohibido(*args, **kwargs):
        raise AssertionError("Un test ha intentado salir a internet.")

    monkeypatch.setattr(socket.socket, "connect", prohibido)
    monkeypatch.setattr(socket, "create_connection", prohibido)


@pytest.fixture(scope="module")
def demo():
    return cargar.cargar("demo-lucia")


@pytest.fixture(scope="module")
def sin_perfil(demo):
    return cargar.reproducir(demo, con_perfil=False)


@pytest.fixture(scope="module")
def con_perfil(demo):
    return cargar.reproducir(demo, con_perfil=True)


def etiqueta(demo, tipo):
    return next(e for e in demo.esperado if e["tipo"] == tipo)


def de_tipo(momentos, tipo):
    return [m for m in momentos if m.tipo == tipo]


def test_demo_lucia_existe_y_une_los_cuatro_momentos(demo):
    assert demo.id == "demo-lucia" and demo.usuario_id == "lucia" and demo.perfil == "calcular"
    assert {e["tipo"] for e in demo.esperado} == {"gasto_compartido", "prueba_gratuita", "cargo_duplicado", "subida_recibo"}
    ids = {m.id for m in demo.movimientos}
    assert {"luc-c1", "luc-v1", "luc-d1", "luc-d2", "luc-luz-11"} <= ids
    assert next(m for m in demo.movimientos if m.id == "luc-v1").importe == Decimal("0.00")


@pytest.mark.parametrize("con", [False, True])
def test_demo_lucia_emite_la_cena_el_9_de_noviembre(demo, sin_perfil, con_perfil, con):
    [m] = de_tipo(con_perfil if con else sin_perfil, "gasto_compartido")
    assert m.fecha == etiqueta(demo, "gasto_compartido")["fecha_detectable"] == date(2026, 11, 9)
    assert m.movimientos == ["luc-c1", "luc-b1", "luc-b2", "luc-b3"]
    assert m.datos["personas_estimadas"] == 5 and m.datos["faltan"] == 1
    assert m.datos["importe_pendiente"] == Decimal("24.00")
    assert [c["contraparte"] for c in m.datos["candidatos"]] == ["MARCOS R"]


@pytest.mark.parametrize("con", [False, True])
def test_demo_lucia_emite_streamflix_el_10_de_noviembre(demo, sin_perfil, con_perfil, con):
    [m] = de_tipo(con_perfil if con else sin_perfil, "prueba_gratuita")
    assert m.fecha == etiqueta(demo, "prueba_gratuita")["fecha_detectable"] == date(2026, 11, 10)
    assert m.datos["dias_hasta"] == 3 and m.datos["fuente_duracion"] == "catalogo"
    assert m.datos["fecha_primer_cobro"] == "2026-11-13" and m.datos["importe_previsto"] == Decimal("9.99")
    assert m.movimientos == ["luc-v1"]


@pytest.mark.parametrize("con", [False, True])
def test_demo_lucia_avisa_de_la_subida_de_la_luz_el_12(demo, sin_perfil, con_perfil, con):
    [m] = de_tipo(con_perfil if con else sin_perfil, "subida_recibo")
    assert m.fecha == etiqueta(demo, "subida_recibo")["fecha_detectable"] == date(2026, 11, 12)
    assert m.datos["subida_eur"] == Decimal("12.00") and m.movimientos == ["luc-luz-11"]


def test_demo_lucia_sin_perfil_son_exactamente_tres_momentos_en_orden(sin_perfil):
    assert [(m.tipo, m.fecha.isoformat()) for m in sin_perfil] == [
        ("gasto_compartido", "2026-11-09"), ("prueba_gratuita", "2026-11-10"), ("subida_recibo", "2026-11-12")]


def test_demo_lucia_el_duplicado_de_la_libreria_no_sale_sin_perfil(sin_perfil):
    assert de_tipo(sin_perfil, "cargo_duplicado") == []


def test_demo_lucia_el_duplicado_de_la_libreria_sale_con_perfil_el_15_de_octubre(demo, con_perfil):
    [m] = de_tipo(con_perfil, "cargo_duplicado")
    assert m.fecha == etiqueta(demo, "cargo_duplicado")["fecha_detectable"] == date(2026, 10, 15)
    assert m.movimientos == ["luc-d1", "luc-d2"] and m.datos["importe"] == Decimal("9.99")


@pytest.mark.parametrize("con", [False, True])
def test_demo_lucia_no_dispara_ninguna_trampa_ni_falsos_positivos(demo, sin_perfil, con_perfil, con):
    r = cargar.evaluar(demo, con_perfil if con else sin_perfil, con_perfil=con)
    assert r["trampas_violadas"] == [] and r["falsos_positivos"] == []
    assert r["omitidos"] == 0 and r["detalle_omitidos"] == []        # con perfil, además, el duplicado (M9)
    assert r["aciertos"] == (4 if con else 3)


def test_demo_lucia_cada_momento_lleva_evidencias_confianza_y_explicacion(sin_perfil):
    for m in sin_perfil:
        assert m.movimientos and 0.5 <= m.confianza <= 0.95 and m.explicacion.endswith(".")
        assert m.usuario_id == "lucia" and m.id.startswith(f"mom-{m.tipo}-")


def test_demo_lucia_la_cena_y_la_prueba_se_explican_en_una_frase(sin_perfil):
    por_tipo = {m.tipo: m.explicacion for m in sin_perfil}
    assert "24,00 €" in por_tipo["gasto_compartido"]
    assert por_tipo["prueba_gratuita"] == "Tu prueba de Streamflix empieza a cobrarse en 3 días (el 13/11) por 9,99 €."


def test_demo_lucia_unitarios_dan_lo_mismo_que_su_parte_del_escenario_unico(demo, sin_perfil):
    unitaria = cargar.reproducir(cargar.cargar("prueba-streamflix-lucia"), con_perfil=False)
    [grande] = de_tipo(sin_perfil, "prueba_gratuita")
    [pequena] = unitaria
    assert (grande.id, grande.fecha, grande.datos) == (pequena.id, pequena.fecha, pequena.datos)
    cena = cargar.reproducir(cargar.cargar("cena-lucia"), con_perfil=False)
    [c1], [c2] = de_tipo(cena, "gasto_compartido"), de_tipo(sin_perfil, "gasto_compartido")
    assert (c1.id, c1.fecha, c1.datos) == (c2.id, c2.fecha, c2.datos)


def test_demo_lucia_avanzando_el_reloj_hasta_cada_fecha_esperada_ya_esta_emitido(demo):
    """Online: hasta la víspera no hay nada y el propio día aparece. Las fechas salen de las etiquetas."""
    from datetime import timedelta

    uid = "__test_demo_lucia__"
    motor.reiniciar(uid)
    try:
        motor.cargar_historial(uid, demo.previos(), demo.activacion)
        emitidos: dict[str, date] = {}
        dia = demo.activacion + timedelta(1)
        while dia <= demo.hasta:
            for m in motor.procesar(uid, demo.del_dia(dia), dia):
                emitidos[m.tipo] = m.fecha
            dia += timedelta(1)
        for tipo in ("gasto_compartido", "prueba_gratuita", "subida_recibo"):
            assert emitidos[tipo] == etiqueta(demo, tipo)["fecha_detectable"], tipo
    finally:
        motor.reiniciar(uid)
