"""A4b: lo que el banco ve sin preguntar (`casos/observar.py`). Un Bizum que devuelve parte de un pago con tarjeta en
un sitio elegible enseña con quién fuiste, el retraso real y el canal de cada persona, haya caso o no. Sin red ni
crédito; con `reglas` no se aprende nada."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from backend import casos, personalizacion
from backend.personalizacion import aprende_amigos as A
from backend.plataforma import orquestador as orq
from backend.plataforma.tipos import AprendizajeAmigos, Caso, Deudor, EventoAmigos, Movimiento

UID = "bizums-test"
D = date(2026, 10, 15)          # jueves de pizzas
PIZZERIA = A.clave_comercio("Pizzeria Vesubio")


def _pago(id_="p1", dia=D, importe="-27.03", comercio="Pizzeria Vesubio", categoria="restaurantes") -> Movimiento:
    return Movimiento(id=id_, fecha=dia, concepto=comercio.upper(), comercio=comercio, importe=Decimal(importe),
                      canal="tarjeta", categoria=categoria, tipo_operacion="cargo")


def _bizum(id_: str, dia: date, importe: str, quien: str) -> Movimiento:
    return Movimiento(id=id_, fecha=dia, concepto="BIZUM RECIBIDO", importe=Decimal(importe), canal="bizum",
                      contraparte=quien)


MARCOS = _bizum("b1", D, "9.01", "Marcos Bravo")
RODRIGO = _bizum("b2", D + timedelta(days=5), "10.00", "Rodrigo Sanz")


def _hasta(movs: list[Movimiento], dia: date) -> list[Movimiento]:
    return [m for m in movs if m.fecha <= dia]


def test_cada_bizum_que_encaja_es_una_observacion_de_la_persona_sin_caso():
    movs = [_pago(), MARCOS, RODRIGO]
    hoy = D
    evs = casos.observaciones(_hasta(movs, hoy), hoy, [])
    marcos = next(e for e in evs if e.id == "bzp:p1:MARCOS B")
    assert (marcos.retraso_dias, marcos.canal, marcos.tras_pedir, marcos.redondeado) == (0, "bizum", False, False)
    assert not any(e.id.startswith("bzg:") for e in evs)                 # aún falta uno: la compañía espera
    hoy = D + timedelta(days=5)
    evs = casos.observaciones(_hasta(movs, hoy), hoy, [], {"bzp:p1:MARCOS B"})
    rodrigo = next(e for e in evs if e.id == "bzp:p1:RODRIGO S")
    assert rodrigo.retraso_dias == 5 and rodrigo.redondeado                # 10 € en vez de 9,01: redondeó (cuota de referencia)
    grupo = next(e for e in evs if e.id == "bzg:p1")                       # ya pagaron todos: fuiste con ellos
    assert (grupo.acompanado, grupo.personas, grupo.comercio, grupo.tipo_comercio) == (
        True, ["MARCOS B", "RODRIGO S"], PIZZERIA, "restaurante")
    assert grupo.fecha_pago == D and grupo.forma == "redondeo"


def test_si_no_pagan_todos_la_compania_se_aprende_al_cerrar_la_ventana_con_los_deudores_del_caso():
    movs = [_pago(), MARCOS]
    caso_motor = Caso(id="caso-m", usuario_id=UID, escenario="gasto_compartido", creado=D + timedelta(days=3),
                      hechos={"pago_id": "p1"}, deudores=[Deudor(contraparte="RODRIGO S", cuota=Decimal("9.01"))])
    for n in range(1, 7):
        assert not any(e.id == "bzg:p1" for e in casos.observaciones(movs, D + timedelta(days=n), [caso_motor]))
    grupo = next(e for e in casos.observaciones(movs, D + timedelta(days=7), [caso_motor]) if e.id == "bzg:p1")
    assert grupo.personas == ["MARCOS B", "RODRIGO S"]                     # quien pagó y quien falta: compañeros


def test_no_cuenta_dos_veces_lo_que_ya_aprende_un_caso():
    movs = [_pago(), MARCOS]
    caso = Caso(id="caso-u-p1", usuario_id=UID, escenario="pago_por_otro", creado=D, hechos={"pago_id": "p1"},
                deudores=[Deudor(contraparte="MARCOS B", cuota=Decimal("9.01"), estado="saldada", saldada=D,
                                 movimiento_pago="b1")])
    assert casos.observaciones(movs, D, [caso]) == []                        # el Bizum saldó al deudor: lo aprende el caso
    assert casos.observaciones(movs, D + timedelta(days=7), [caso], {"acomp:caso-u-p1"}) == []   # su compañía, también
    pago = EventoAmigos(id="pago:caso-u-p1:MARCOS B", fuente="bizum", fecha=D, contraparte="MARCOS B", retraso_dias=0)
    acomp = EventoAmigos(id="acomp:caso-u-p1", fuente="boton", fecha=D, acompanado=True, personas=["MARCOS B"])
    assert casos.sin_repetir([pago, acomp], caso, {"bzp:p1:MARCOS B", "bzg:p1"}) == []
    assert casos.sin_repetir([pago, acomp], caso, set()) == [pago, acomp]


@pytest.mark.parametrize("pago, bizum", [
    (_pago(comercio="Mercadona", categoria="supermercado", importe="-30.00"), _bizum("b", D, "15.00", "Marcos Bravo")),
    (_pago(), _bizum("b", D, "20.00", "Marcos Bravo")),                       # más del 60 %: no es la parte de nadie
    (_pago(), _bizum("b", D, "7.40", "Marcos Bravo")),                        # no encaja con ninguna cuota
    (_pago(), _bizum("b", D + timedelta(days=8), "9.01", "Marcos Bravo")),    # fuera de la ventana
    (_pago(), _bizum("b", D - timedelta(days=1), "9.01", "Marcos Bravo")),    # antes del pago
])
def test_lo_que_no_encaja_no_ensena_nada(pago, bizum):
    for n in range(-1, 10):
        assert casos.observaciones([pago, bizum], D + timedelta(days=n), []) == []


def test_un_multiplo_cuenta_como_dos_personas():
    movs = [_pago(importe="-48.00", comercio="La Tasca"), _bizum("b", D + timedelta(days=1), "24.00", "Laura Vega")]
    evs = casos.observaciones(movs, D + timedelta(days=1), [])
    assert {e.id for e in evs} == {"bzp:p1:LAURA V", "bzg:p1"}           # 24 de 48: o eran dos, o pagó por dos


# --- Con el orquestador ---------------------------------------------------------------------------

@pytest.fixture
def usuario(monkeypatch):
    monkeypatch.setattr(orq.motor, "procesar", lambda uid, nuevos, hoy, perfil=None, **kw: [])

    def preparar(modo: str):
        modelo = personalizacion.nuevo_modelo(UID)
        modelo.aprendizaje = AprendizajeAmigos(modo=modo)
        base = [Movimiento(id="h1", fecha=D - timedelta(days=5), concepto="MERCADONA", importe=Decimal("-12.00"),
                           canal="tarjeta", saldo=Decimal("500.00")), _pago(), MARCOS, RODRIGO]
        orq.cargar_simulacion(UID, base, D - timedelta(days=1), modelo=modelo)
        orq.activar(UID, ["gasto_compartido"], {"copiloto": True})

    return preparar


def _avanzar(hasta: date) -> None:
    hoy = date.fromisoformat(orq.estado_usuario(UID)["hoy"])
    while hoy < hasta:
        hoy += timedelta(days=1)
        orq.avanzar_dia(UID, hoy)


def test_sin_preguntar_meisam_aprende_con_quien_fuiste_y_cuando_paga_cada_uno(usuario):
    usuario("aprende")
    _avanzar(D + timedelta(days=5))
    apr = orq._leer(UID, "modelo").aprendizaje
    assert casos.cargar(UID) == []                                           # sin ningún caso
    assert apr.personas["MARCOS B"].retrasos_dias == [0] and apr.personas["RODRIGO S"].retrasos_dias == [5]
    assert apr.por_comercio[PIZZERIA].con_alguien == 1
    assert apr.por_comercio[PIZZERIA].grupos[0].miembros == ["MARCOS B", "RODRIGO S"]
    assert apr.por_tipo_franja["restaurante|laborable"].con_alguien == 1
    vistos = list(apr.eventos_vistos)
    _avanzar(D + timedelta(days=9))
    assert orq._leer(UID, "modelo").aprendizaje.eventos_vistos == vistos     # idempotente: nada se repite


@pytest.mark.parametrize("modo", ["reglas", "fijo"])
def test_con_reglas_o_fijo_no_aprende_de_los_bizums(usuario, modo):
    usuario(modo)
    _avanzar(D + timedelta(days=9))
    assert orq._leer(UID, "modelo").aprendizaje == AprendizajeAmigos(modo=modo)
