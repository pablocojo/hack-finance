"""Minilenguaje de condiciones: gramática, rutas permitidas, falla cerrada y seguridad."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from backend.modulos import condiciones as c
from backend.plataforma.tipos import ModeloUsuario, Momento, PerfilUsuario


def momento(**datos) -> Momento:
    return Momento(id="m1", tipo="subida_recibo", usuario_id="lucia", fecha=date(2026, 11, 9), datos=datos,
                   confianza=0.9, impacto_eur=Decimal("12.00"), explicacion="x", detector="d", version="1")


def ev(texto, m=None, modelo=None):
    return c.evaluar(c.compilar(texto), c.contexto(m or momento(subida_eur=Decimal("12.00")), modelo))


def test_comparaciones_y_decimales():
    assert ev("momento.datos.subida_eur > 8")
    assert ev("momento.datos.subida_eur > 8 y momento.confianza >= 0.8")
    assert not ev("momento.datos.subida_eur > 12")
    assert ev("momento.datos.subida_eur == 12")
    assert ev("momento.datos.subida_eur * 2 + 1 == 25")


def test_importes_como_cadena_se_comparan_como_numero():
    assert ev("momento.datos.subida_eur >= 8", momento(subida_eur="12.00"))


def test_logica_listas_y_funciones():
    m = momento(comercio="Netflix", subida_eur=Decimal("3"))
    assert ev('momento.datos.comercio en ["Netflix", "HBO"]', m)
    assert ev('momento.datos.comercio no en ["HBO"]', m)
    assert ev("no (momento.datos.subida_eur > 8) y verdadero", m)
    assert ev("max(1, momento.datos.subida_eur) == 3 o falso", m)
    assert ev("largo([1, 2]) == 2", m)


@pytest.mark.parametrize("texto", [
    '__import__("os").system("x")',
    "momento.__class__",
    "momento.datos.__class__",
    "momento.datos.x.upper()",
    "open('f')",
    "eval('1')",
    "modelo.perfil.resumen_vida == 'x'",
    "modelo.perfil.grupos",
    "momento.contexto_personal",
    "momento.movimientos",
    "modelo.otra",
    "momento",
    "1 / 2 > 0",
    "2 ** 3 > 0",
    "momento.datos.a.b(",
    "",
    "a y b",
])
def test_la_gramatica_rechaza(texto):
    with pytest.raises(c.ErrorCondicion):
        c.compilar(texto)


def test_limites_de_tamano():
    with pytest.raises(c.ErrorCondicion):
        c.compilar("verdadero " + "y verdadero " * 30)
    with pytest.raises(c.ErrorCondicion):
        c.compilar("(" * 20 + "verdadero" + ")" * 20)
    with pytest.raises(c.ErrorCondicion):
        c.compilar("verdadero o " * 40 + "falso")


def test_sin_perfil_la_comparacion_es_falsa_y_o_sigue_funcionando():
    m = momento(subida_eur=Decimal("5"))
    informe: list[str] = []
    arbol = c.compilar("momento.datos.subida_eur >= modelo.perfil.umbral_relevante_eur")
    assert not c.evaluar(arbol, c.contexto(m, ModeloUsuario(usuario_id="lucia")), informe)
    assert informe
    assert not c.evaluar(arbol, c.contexto(m, None))
    combinada = "momento.datos.subida_eur > 8 o momento.datos.subida_eur >= modelo.perfil.umbral_relevante_eur"
    assert not ev(combinada, m, ModeloUsuario(usuario_id="lucia"))
    assert ev(combinada, momento(subida_eur=Decimal("9")), ModeloUsuario(usuario_id="lucia"))


def test_con_perfil_se_usa_el_umbral_personal():
    modelo = ModeloUsuario(usuario_id="lucia", perfil=PerfilUsuario(calculado=date(2026, 11, 9), dias_historial=90,
                                                                   umbral_relevante_eur=Decimal("4")))
    assert ev("momento.datos.subida_eur >= modelo.perfil.umbral_relevante_eur", momento(subida_eur=Decimal("5")), modelo)


def test_dato_ausente_falla_cerrado():
    assert not ev("momento.datos.no_existe > 1")
    assert not ev("momento.datos.no_existe == 1")
    assert not ev("momento.datos.no_existe no en [1]")
