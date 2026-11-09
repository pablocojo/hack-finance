"""Ningún detector mira el futuro (motor.md §6 y §8): meter movimientos posteriores a `hoy` no cambia
lo que se emite hasta `hoy`, y cortar la historia en un día da los mismos momentos que verla entera."""

from __future__ import annotations

import dataclasses
from datetime import date, timedelta
from decimal import Decimal

import pytest

from backend import motor
from backend.escenarios import cargar
from backend.plataforma.tipos import Momento, Movimiento

ESCENARIOS = ("cena-lucia", "fondo-familia")


def _firma(momentos: list[Momento]) -> list[tuple]:
    return [(m.id, m.tipo, m.fecha, tuple(m.movimientos), m.confianza, repr(sorted(m.datos.items())))
            for m in momentos]


def _reproducir_con_futuro(esc: cargar.Escenario, extra: list[Movimiento] = ()) -> list[Momento]:
    """Como `cargar.reproducir`, pero con TODOS los movimientos (y `extra`) metidos en el estado del
    motor desde el primer día: el detector los tendría delante si no respetara el corte por `hoy`."""
    uid = f"__no_futuro__:{esc.id}"
    todos = list(esc.movimientos) + list(extra)
    momentos: list[Momento] = []
    try:
        motor.cargar_historial(uid, esc.previos(), esc.activacion)
        motor._estado(uid).agregar(todos)                      # el futuro, ya dentro del estado
        dia = esc.activacion + timedelta(days=1)
        while dia <= esc.hasta:
            nuevos = [m for m in todos if m.fecha == dia]
            momentos += motor.procesar(uid, nuevos, dia)
            dia += timedelta(days=1)
    finally:
        motor.reiniciar(uid)
    return momentos


@pytest.mark.parametrize("escenario_id", ESCENARIOS)
def test_el_futuro_en_el_estado_no_cambia_nada(escenario_id):
    esc = cargar.cargar(escenario_id)
    assert _firma(_reproducir_con_futuro(esc)) == _firma(cargar.reproducir(esc, con_perfil=False))


@pytest.mark.parametrize("corte", [date(2026, 11, 6), date(2026, 11, 8), date(2026, 11, 9), date(2026, 11, 12)])
def test_cortar_la_historia_da_lo_mismo_hasta_el_corte(corte):
    esc = cargar.cargar("cena-lucia")
    entero = cargar.reproducir(esc, con_perfil=False)
    cortado = dataclasses.replace(esc, hasta=corte, movimientos=[m for m in esc.movimientos if m.fecha <= corte])
    assert _firma(cargar.reproducir(cortado, con_perfil=False)) == _firma([m for m in entero if m.fecha <= corte])


def test_el_bizum_futuro_de_marcos_no_apaga_el_aviso_del_9():
    """Si el detector viera el Bizum de Marcos del 10/11, el 9/11 no avisaría de la cena."""
    esc = cargar.cargar("cena-lucia")
    marcos = Movimiento(id="luc-futuro-marcos", fecha=date(2026, 11, 10), concepto="BIZUM RECIBIDO",
                        contraparte="Marcos Ruiz Sanz", nota="cena viernes", importe=Decimal("24.00"), canal="bizum")
    hasta_el_9 = [m for m in _reproducir_con_futuro(esc, [marcos]) if m.fecha <= date(2026, 11, 9)]
    cenas = [m for m in hasta_el_9 if m.tipo == "gasto_compartido"]
    assert [m.fecha for m in cenas] == [date(2026, 11, 9)] and "luc-futuro-marcos" not in cenas[0].movimientos
    assert cenas[0].datos["faltan"] == 1


def test_procesar_rechaza_movimientos_del_futuro():
    futuro = Movimiento(id="x-futuro", fecha=date(2026, 11, 10), concepto="BIZUM RECIBIDO",
                        importe=Decimal("10.00"), canal="bizum")
    with pytest.raises(ValueError):
        motor.procesar("__no_futuro__:rechazo", [futuro], date(2026, 11, 9))
    with pytest.raises(ValueError):
        motor.cargar_historial("__no_futuro__:rechazo", [futuro], date(2026, 11, 9))
    motor.reiniciar("__no_futuro__:rechazo")
