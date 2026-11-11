"""Ganchos de la curva de amigos (A0): `cargar_simulacion`, `anadir_movimientos`, `crear_caso_usuario(origen)` y
la compañía del motor (solo se pasa si no es None). Sin cliente real ni internet."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from backend import casos, motor
from backend.plataforma import almacenamiento as alm
from backend.plataforma import orquestador as orq
from backend.plataforma.tipos import Contacto, ModeloUsuario, Movimiento

UID = "sim-a0"
HOY = date(2026, 11, 6)


def mov(id_, dias, importe, concepto, comercio=None, **extra):
    return Movimiento(id=id_, fecha=HOY + timedelta(days=dias), concepto=concepto, comercio=comercio,
                      importe=Decimal(importe), **extra)


@pytest.fixture
def sim():
    movs = [mov("n1", -3, "1500.00", "NOMINA", "EMPRESA SL", saldo=Decimal("2000.00")),
            mov("c1", -1, "-60.00", "COMPRA TARJ RESTAURANTE LA PLAZA", "RESTAURANTE LA PLAZA", saldo=Decimal("1940.00")),
            mov("f1", 2, "-10.00", "COMPRA TARJ KIOSCO", "KIOSCO")]
    contactos = {"MARCOS R": Contacto(contraparte="MARCOS R", nombre="Marcos R.")}
    r = orq.cargar_simulacion(UID, movs, HOY, contactos=contactos)
    orq.activar(UID, ["gasto_compartido"], {"copiloto": True})
    return r


def test_cargar_simulacion_deja_el_usuario_listo(sim):
    assert sim == {"usuario_id": UID, "hoy": "2026-11-06", "activacion": "2026-11-06"}
    assert [m.id for m in alm.cargar(UID, "pendientes", tipo=list[Movimiento])] == ["f1"]
    modelo = orq._leer(UID, "modelo")
    assert modelo.usuario_id == UID and "MARCOS R" in modelo.contactos
    assert modelo.aprendizaje.modo == "aprende"


def test_cargar_simulacion_respeta_el_modelo_dado():
    base = ModeloUsuario(usuario_id="otro")
    base.aprendizaje.modo = "reglas"
    orq.cargar_simulacion(UID, [mov("a", -2, "-5.00", "X")], HOY, modelo=base)
    modelo = orq._leer(UID, "modelo")
    assert modelo.usuario_id == UID and modelo.aprendizaje.modo == "reglas"


def test_anadir_movimientos_rechaza_hoy_y_pasado(sim):
    with pytest.raises(ValueError, match="posteriores a hoy"):
        orq.anadir_movimientos(UID, [mov("p1", 0, "5.00", "BIZUM")])
    with pytest.raises(ValueError):
        orq.anadir_movimientos(UID, [mov("p2", -1, "5.00", "BIZUM")])


def test_anadir_movimientos_llegan_con_el_reloj_y_sin_duplicar(sim):
    bizum = mov("b1", 1, "20.00", "BIZUM DE MARCOS R", canal="bizum", contraparte="MARCOS R", nota="cena")
    assert orq.anadir_movimientos(UID, [bizum]) == 1
    assert orq.anadir_movimientos(UID, [bizum]) == 0           # idempotente por id
    assert [m.id for m in alm.cargar(UID, "pendientes", tipo=list[Movimiento])] == ["b1", "f1"]
    orq.avanzar_dia(UID, HOY + timedelta(days=1))
    assert "b1" in {m.id for m in orq._leer(UID, "movimientos", [])}
    assert orq.anadir_movimientos(UID, []) == 0


def test_crear_caso_usuario_rellena_origen(sim):
    orq.crear_caso_usuario(UID, "c1", [{"contraparte": "Marcos R", "importe": "20.00"}])
    assert [c.origen for c in casos.cargar(UID)] == ["boton"]


def test_crear_caso_usuario_origen_chat(sim):
    orq.crear_caso_usuario(UID, "c1", [{"contraparte": "Marcos R", "importe": "20.00"}], origen="chat")
    assert [c.origen for c in casos.cargar(UID)] == ["chat"]


def test_motor_recibe_compania_solo_si_no_es_none(sim, monkeypatch):
    llamadas = []
    real = motor.procesar

    def espia(*args, **kwargs):
        llamadas.append(kwargs)
        return real(*args, **kwargs)

    monkeypatch.setattr(motor, "procesar", espia)
    orq.avanzar_dia(UID, HOY + timedelta(days=1))
    assert llamadas == [{}]          # compania = None: la llamada es idéntica a la de antes
