"""`ordenar_acciones` y `registrar_accion` (personalizacion.md §5). Puras y sin crédito."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest

from backend import personalizacion
from backend.personalizacion.orden_acciones import puntuaciones
from backend.plataforma.tipos import AccionOfrecida, Limites, ModeloUsuario, Propuesta, ResultadoAccion


def renovacion(acciones=("cancelar_suscripcion", "bloquear_comercio", "recordar"), tipo="renovacion_proxima"):
    return Propuesta(
        id="p1", modulo_id="renovacion", momento_id="m1", usuario_id="lucia", titulo="Spotify se renueva",
        mensaje_notificacion="Spotify se renueva el 15/11", contexto_llamada="Renovación de Spotify.",
        acciones_ofrecidas=[AccionOfrecida(accion_id=a, parametros={"comercio": "SPOTIFY"},
                                           limites=Limites(importe_max=Decimal("10.99"), contrapartes=["SPOTIFY"]))
                            for a in acciones],
        valor_estimado_eur=Decimal("10.99"), tipo_momento=tipo, comercio="SPOTIFY", confianza=0.9,
        creada=datetime(2026, 11, 12, 20, 30))


def lucia() -> ModeloUsuario:
    """4 renovaciones: 3 veces recordar y 1 cancelar; además, 2 pedir_bizum (N = 6)."""
    return ModeloUsuario(usuario_id="lucia", elecciones={
        "t:renovacion_proxima|a:recordar": 3, "t:renovacion_proxima|a:cancelar_suscripcion": 1,
        "t:gasto_compartido|a:pedir_bizum": 2,
        "a:recordar": 3, "a:cancelar_suscripcion": 1, "a:pedir_bizum": 2,
    })


def test_ejemplo_del_diseno_exacto():
    p, m = renovacion(), lucia()
    s = puntuaciones(p, m)
    assert round(s["cancelar_suscripcion"], 3) == 0.241
    assert round(s["bloquear_comercio"], 3) == 0.037
    assert round(s["recordar"], 3) == 0.648
    ordenada = personalizacion.ordenar_acciones(p, m)
    assert [a.accion_id for a in ordenada.acciones_ofrecidas] == ["recordar", "cancelar_suscripcion", "bloquear_comercio"]
    assert "Sueles elegir recordar en las renovaciones (3 de 4)." in ordenada.contexto_llamada
    assert ordenada.contexto_llamada.startswith("Renovación de Spotify.")


def test_nunca_anade_quita_ni_cambia_acciones_ni_limites():
    p, m = renovacion(), lucia()
    ordenada = personalizacion.ordenar_acciones(p, m)
    clave = lambda a: a.model_dump_json()  # noqa: E731
    assert sorted(map(clave, ordenada.acciones_ofrecidas)) == sorted(map(clave, p.acciones_ofrecidas))
    assert ordenada.model_dump(exclude={"acciones_ofrecidas", "contexto_llamada"}) == \
        p.model_dump(exclude={"acciones_ofrecidas", "contexto_llamada"})
    # Pura: la propuesta de entrada no cambia y repetir no duplica la frase.
    assert [a.accion_id for a in p.acciones_ofrecidas] == ["cancelar_suscripcion", "bloquear_comercio", "recordar"]
    otra = personalizacion.ordenar_acciones(ordenada, m)
    assert otra.contexto_llamada.count("Sueles elegir") == 1


def test_en_frio_y_empates_mantienen_el_orden_del_modulo():
    p = renovacion()
    frio = personalizacion.ordenar_acciones(p, ModeloUsuario(usuario_id="u"))
    assert [a.accion_id for a in frio.acciones_ofrecidas] == ["cancelar_suscripcion", "bloquear_comercio", "recordar"]
    assert frio.contexto_llamada == p.contexto_llamada
    # Con una sola elección del tipo, sube pero sin frase (hace falta >= 2).
    m = ModeloUsuario(usuario_id="u", elecciones={"t:renovacion_proxima|a:recordar": 1, "a:recordar": 1})
    una = personalizacion.ordenar_acciones(p, m)
    assert una.acciones_ofrecidas[0].accion_id == "recordar" and "Sueles" not in una.contexto_llamada


def test_un_tipo_nuevo_usa_lo_que_eliges_en_general():
    """Un módulo o tipo sin historia hereda la preferencia global (se aprende por acción, no por módulo)."""
    p = renovacion(acciones=("cancelar_suscripcion", "recordar"), tipo="prueba_gratuita")
    ordenada = personalizacion.ordenar_acciones(p, lucia())
    assert [a.accion_id for a in ordenada.acciones_ofrecidas] == ["recordar", "cancelar_suscripcion"]


@pytest.mark.parametrize("ok, esperado", [(True, 1), (False, 0)])
def test_registrar_accion_suma_a_elecciones(ok, esperado):
    m = ModeloUsuario(usuario_id="u")
    r = ResultadoAccion(accion_id="recordar", ok=ok, mensaje="hecho")
    nuevo = personalizacion.registrar_accion(m, renovacion(), r)
    assert nuevo.elecciones.get("t:renovacion_proxima|a:recordar", 0) == esperado
    assert nuevo.elecciones.get("a:recordar", 0) == esperado
    assert m.elecciones == {}


def test_tras_elegir_dos_veces_la_propone_primero():
    m = ModeloUsuario(usuario_id="u")
    p = renovacion()
    for _ in range(2):
        m = personalizacion.registrar_accion(m, p, ResultadoAccion(accion_id="bloquear_comercio", ok=True, mensaje="ok"))
    ordenada = personalizacion.ordenar_acciones(p, m)
    assert ordenada.acciones_ofrecidas[0].accion_id == "bloquear_comercio"
    assert "Sueles elegir bloquear el comercio en las renovaciones (2 de 2)." in ordenada.contexto_llamada
