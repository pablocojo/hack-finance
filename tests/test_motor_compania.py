"""
A3 (curva de amigos): el motor recibe lo aprendido como `compania` («dónde y cuándo vas acompañado») y
`pago_individual` abre con `senal = "aprendida"` donde p(acompañado) es alta, también entre semana y por debajo de
`IMPORTE_MIN`, con un mínimo propio. Con `compania=None` (o vacío), idéntico a antes.

Escenario «jueves de pizzas» (verdad etiquetada, en el propio test: el motor no lee escenarios con lo aprendido).
Álvaro, estudiante, va los jueves a PIZZERIA NAPOLI con su grupo y paga él con tarjeta 30 €. Las reglas fijas callan
(entre semana y por debajo de 2 x 20 €). Meisam ya ha aprendido que allí casi siempre va acompañado (p = 0,9):
- debe salir UN `gasto_compartido` con `origen = pago_individual` y `senal = "aprendida"` el día del pago + la espera
  de los Bizums (`DIAS_ESPERA`), con el pago como única evidencia, el importe y el comercio;
- trampas que no abren nada: el café de 4 € en la misma pizzería (bajo el mínimo propio), la compra del Mercadona del
  jueves (otro tipo de sitio), la cena del miércoles en un sitio donde casi siempre va solo (el comercio manda sobre el
  tipo y la franja) y el jueves en que un amigo ya le envió su parte por Bizum (es del `gasto_compartido` normal).
Ningún test sale a internet ni gasta crédito.
"""

from __future__ import annotations

import ast
import socket
from dataclasses import fields
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from backend import motor
from backend.motor import conocimiento
from backend.motor.detectores.base import Contexto
from backend.motor.detectores.pago_individual import franja_de
from backend.motor.parametros import GastoCompartido, PagoIndividual
from backend.plataforma.tipos import Movimiento

UID = "compania-test"
P = PagoIndividual()
ESPERA = timedelta(days=GastoCompartido().DIAS_ESPERA)       # sin línea base propia de retrasos
VENTANA = timedelta(days=GastoCompartido().VENTANA_REEMBOLSO)
INICIO = date(2026, 10, 1)

JUEVES = date(2026, 11, 5)
SABADO = date(2026, 11, 7)
MIERCOLES = date(2026, 11, 4)
assert (JUEVES.weekday(), SABADO.weekday(), MIERCOLES.weekday()) == (3, 5, 2)

PIZZAS = "PIZZERIA NAPOLI"
APRENDIDO = {f"c:{PIZZAS}": 0.9}


@pytest.fixture(autouse=True)
def entorno(monkeypatch):
    def prohibido(*args, **kwargs):
        raise AssertionError("Un test ha intentado salir a internet.")

    monkeypatch.setattr(socket.socket, "connect", prohibido)
    monkeypatch.setattr(socket, "create_connection", prohibido)
    conocimiento.limpiar_memoria()
    motor.reiniciar(UID)
    yield
    conocimiento.limpiar_memoria()
    motor.reiniciar(UID)


def mov(id, fecha, concepto, importe, **extra) -> Movimiento:
    return Movimiento(id=id, fecha=fecha, concepto=concepto, importe=Decimal(str(importe)), **extra)


def tarjeta(id, fecha, comercio, importe, categoria=None) -> Movimiento:
    return mov(id, fecha, f"COMPRA TARJETA {comercio}", importe, comercio=comercio, canal="tarjeta", categoria=categoria)


def bizum(id, fecha, importe, quien="Laura Martinez Garcia") -> Movimiento:
    return mov(id, fecha, "BIZUM RECIBIDO", importe, canal="bizum", contraparte=quien)


def dia_a_dia(movimientos, hasta, compania=..., perfil=None, desde=INICIO):
    """Lo anterior a `desde` entra como historial; desde ahí, `procesar` día a día. `compania=...` = sin argumento."""
    salida, dia = [], desde
    previos = [m for m in movimientos if m.fecha < desde]
    if previos:
        motor.cargar_historial(UID, previos, desde - timedelta(1))
    while dia <= hasta:
        hoy = [m for m in movimientos if m.fecha == dia]
        if compania is ...:
            salida += motor.procesar(UID, hoy, dia, perfil)
        else:
            salida += motor.procesar(UID, hoy, dia, perfil, compania=compania)
        dia += timedelta(1)
    return salida


def individuales(momentos):
    return [m for m in momentos if m.tipo == "gasto_compartido" and m.datos.get("origen") == "pago_individual"]


def salida(movimientos, compania=..., hasta=None, perfil=None):
    hasta = hasta or max(m.fecha for m in movimientos) + VENTANA + ESPERA
    motor.reiniciar(UID)
    return individuales(dia_a_dia(movimientos, hasta, compania, perfil))


def resumen(momentos):
    return [(m.id, m.fecha, m.movimientos, m.confianza, m.explicacion, m.datos) for m in momentos]


# --- El escenario «jueves de pizzas» ----------------------------------------------------------------------------

def historia():
    jueves_bizum = JUEVES + timedelta(days=14)
    return [
        tarjeta("piz-1", JUEVES, PIZZAS, "-30.00"),                               # VERDAD: abre «aprendida»
        tarjeta("piz-cafe", JUEVES - timedelta(days=2), PIZZAS, "-4.00"),         # trampa: bajo el mínimo propio
        tarjeta("merc-1", JUEVES, "MERCADONA", "-45.00"),                         # trampa: supermercado
        tarjeta("mir-1", MIERCOLES, "RESTAURANTE EL MIRADOR", "-32.00"),          # trampa: allí casi siempre va solo
        tarjeta("piz-2", jueves_bizum, PIZZAS, "-30.00"),                         # trampa: ya le enviaron su parte
        bizum("biz-2", jueves_bizum + timedelta(days=1), "10.00"),
    ]


APRENDIDO_HISTORIA = {f"c:{PIZZAS}": 0.9, "c:RESTAURANTE EL MIRADOR": 0.1, "t:restaurante|laborable": 0.8}


def test_escenario_jueves_de_pizzas_abre_solo_la_verdad_y_en_su_dia():
    movs = historia()
    [m] = salida(movs, APRENDIDO_HISTORIA)
    pago = next(x for x in movs if x.id == "piz-1")
    assert m.fecha == pago.fecha + ESPERA                                       # domingo 8/11, no antes
    assert m.movimientos == ["piz-1"] and m.tipo == "gasto_compartido"
    d = m.datos
    assert d["origen"] == "pago_individual" and d["dudoso"] is True and d["senal"] == "aprendida"
    assert d["comercio"] == PIZZAS and d["importe_total"] == Decimal("30.00") and d["pago_id"] == "piz-1"
    assert d["p_acompanado"] == 0.9 and d["ambito_aprendido"] == f"c:{PIZZAS}"
    assert m.confianza == P.CONFIANZA_APRENDIDA < 0.7                           # nunca avisa por sí solo
    assert m.explicacion.startswith("Pagaste 30,00 € en Pizzeria Napoli el jueves 5/11")
    assert d["hipotesis"][0]["motivo"] and d["hipotesis"][0]["candidatos"] == [] and d["hipotesis"][0]["faltan"] == 0


def test_escenario_sin_lo_aprendido_las_reglas_fijas_callan():
    assert salida(historia()) == []
    assert salida(historia(), None) == []
    assert salida(historia(), {}) == []


def test_las_pizzas_de_un_jueves_de_30_euros_con_p_alta():
    movs = [tarjeta("p", JUEVES, PIZZAS, "-30.00")]
    assert salida(movs) == []                                                   # las reglas fijas: entre semana < 40 €
    [m] = salida(movs, APRENDIDO)
    assert m.datos["senal"] == "aprendida" and m.fecha == JUEVES + ESPERA


# --- Con `None`, idéntico ------------------------------------------------------------------------------------

def _mezcla():
    return [
        tarjeta("a", SABADO, "RESTAURANTE EL MIRADOR", "-45.60"),
        tarjeta("b", SABADO - timedelta(1), "BAR LA ESQUINA", "-30.00"),
        tarjeta("c", JUEVES, PIZZAS, "-30.00"),
        tarjeta("d", MIERCOLES, "RESTAURANTE EL MIRADOR", "-45.60"),
        tarjeta("e", SABADO, "MERCADONA", "-80.00"),
        tarjeta("f", SABADO + timedelta(7), "CINES ESTRELLA", "-24.00"),
        bizum("g", SABADO + timedelta(8), "12.00"),
    ]


def test_con_none_o_vacio_es_identico_a_no_pasar_nada():
    hasta = SABADO + VENTANA * 3
    sin = resumen(salida(_mezcla(), hasta=hasta))
    assert sin != []
    assert resumen(salida(_mezcla(), None, hasta=hasta)) == sin
    assert resumen(salida(_mezcla(), {}, hasta=hasta)) == sin


def test_con_none_todos_los_momentos_del_motor_son_identicos():
    """No solo los de `pago_individual`: el argumento no toca nada más."""
    def todos(compania):
        motor.reiniciar(UID)
        return [(m.id, m.tipo, m.fecha, m.datos) for m in dia_a_dia(_mezcla(), SABADO + VENTANA * 3, compania)]
    assert todos(...) == todos(None) == todos({})


def test_contexto_lleva_compania_con_none_por_defecto():
    campo = next(f for f in fields(Contexto) if f.name == "compania")
    assert campo.default is None


# --- Ámbitos: comercio, tipo y franja ------------------------------------------------------------------------

@pytest.mark.parametrize("fecha, franja", [
    (date(2026, 11, 2), "laborable"), (date(2026, 11, 5), "laborable"), (date(2026, 11, 6), "viernes"),
    (date(2026, 11, 7), "finde"), (date(2026, 11, 8), "finde"),
])
def test_franja_del_dia_de_la_semana(fecha, franja):
    assert franja_de(fecha) == franja


def test_por_tipo_y_franja_abre_entre_semana_y_solo_en_su_franja():
    movs = [tarjeta("p", JUEVES, "RESTAURANTE EL MIRADOR", "-30.00")]
    [m] = salida(movs, {"t:restaurante|laborable": 0.85})
    assert m.datos["senal"] == "aprendida" and m.datos["ambito_aprendido"] == "t:restaurante|laborable"
    assert salida(movs, {"t:restaurante|finde": 0.95}) == []                    # otra franja
    assert salida(movs, {"t:bar|laborable": 0.95}) == []                        # otro tipo de sitio


def test_el_comercio_manda_sobre_el_tipo_y_la_franja():
    movs = [tarjeta("p", JUEVES, "RESTAURANTE EL MIRADOR", "-30.00")]
    assert salida(movs, {"c:RESTAURANTE EL MIRADOR": 0.1, "t:restaurante|laborable": 0.95}) == []
    [m] = salida(movs, {"c:RESTAURANTE EL MIRADOR": 0.9, "t:restaurante|laborable": 0.1})
    assert m.datos["ambito_aprendido"] == "c:RESTAURANTE EL MIRADOR"


def test_el_comercio_se_busca_normalizado():
    movs = [tarjeta("p", JUEVES, "Pizzeria Napoli", "-30.00")]
    [m] = salida(movs, APRENDIDO)
    assert m.datos["comercio"] == PIZZAS


def test_un_tipo_desconocido_no_es_un_ambito():
    movs = [tarjeta("p", JUEVES, "TIENDA DE ALGO", "-30.00")]
    assert salida(movs, {"t:desconocido|laborable": 0.99}) == []


def test_lo_aprendido_de_un_comercio_vale_aunque_su_tipo_no_este_en_la_lista():
    """Es lo que el propio usuario ha confirmado de ese sitio (sin reglas por nombre: vale para cualquier comercio)."""
    movs = [tarjeta("p", JUEVES, "TIENDA DE ALGO", "-30.00")]
    [m] = salida(movs, {"c:TIENDA DE ALGO": 0.9})
    assert m.datos["senal"] == "aprendida"


# --- Umbrales con nombre ---------------------------------------------------------------------------------------

def test_umbral_de_p_y_minimo_propio():
    assert P.P_ACOMPANADO_MIN > 0.5 and P.IMPORTE_MIN_APRENDIDA < P.IMPORTE_MIN
    justo = float(P.P_ACOMPANADO_MIN)
    por_debajo = round(justo - 0.01, 2)
    movs = [tarjeta("p", JUEVES, PIZZAS, "-30.00")]
    assert len(salida(movs, {f"c:{PIZZAS}": justo})) == 1
    assert salida(movs, {f"c:{PIZZAS}": por_debajo}) == []
    minimo = P.IMPORTE_MIN_APRENDIDA
    assert len(salida([tarjeta("p", JUEVES, PIZZAS, -minimo)], APRENDIDO)) == 1
    assert salida([tarjeta("p", JUEVES, PIZZAS, -(minimo - Decimal("0.01")))], APRENDIDO) == []


def test_el_perfil_no_sube_el_minimo_propio():
    """El perfil sube `IMPORTE_MIN` de las reglas fijas; lo aprendido ya es personal y tiene su propio mínimo."""
    from backend.plataforma.tipos import PerfilUsuario
    perfil = PerfilUsuario(calculado=date(2026, 10, 1), dias_historial=60, umbral_relevante_eur=Decimal("50"))
    [m] = salida([tarjeta("p", JUEVES, PIZZAS, "-30.00")], APRENDIDO, perfil=perfil)
    assert m.datos["senal"] == "aprendida"


# --- Lo que no cambia ------------------------------------------------------------------------------------------

def test_p_baja_no_quita_lo_que_abren_las_reglas_fijas():
    """Callar donde va solo lo decide la escalera al abrir el caso, no el motor."""
    movs = [tarjeta("p", SABADO, "RESTAURANTE EL MIRADOR", "-45.60")]
    [m] = salida(movs, {"c:RESTAURANTE EL MIRADOR": 0.05})
    assert m.datos["senal"] == "media" and "ambito_aprendido" not in m.datos and "p_acompanado" not in m.datos


def test_p_alta_en_fin_de_semana_tambien_es_aprendida():
    [m] = salida([tarjeta("p", SABADO, "RESTAURANTE EL MIRADOR", "-45.60")], {"c:RESTAURANTE EL MIRADOR": 0.9})
    assert m.datos["senal"] == "aprendida" and m.confianza == P.CONFIANZA_APRENDIDA


def test_un_bizum_que_pudo_ser_su_parte_lo_deja_en_silencio_aunque_p_sea_alta():
    movs = [tarjeta("p", JUEVES, PIZZAS, "-30.00"), bizum("b", JUEVES + timedelta(1), "10.00")]
    assert salida(movs, APRENDIDO) == []


def test_un_pago_de_una_serie_o_de_una_persona_no_es_individual_ni_con_p_alta():
    fechas = (date(2026, 8, 6), date(2026, 9, 3), date(2026, 10, 1), JUEVES)    # el mismo importe cada mes
    movs = [tarjeta(f"s{i}", f, PIZZAS, "-30.00") for i, f in enumerate(fechas)]
    assert salida(movs, APRENDIDO, hasta=JUEVES + ESPERA + VENTANA) == []
    persona = [mov("t", JUEVES, "TRANSFERENCIA A LAURA", "-30.00", canal="transferencia", contraparte="Laura Martinez Garcia")]
    assert salida(persona, {"c:LAURA MARTINEZ GARCIA": 0.99}) == []


def test_sale_una_sola_vez_y_es_idempotente():
    movs = [tarjeta("p", JUEVES, PIZZAS, "-30.00")]
    momentos = dia_a_dia(movs, JUEVES + ESPERA + VENTANA, APRENDIDO)
    assert [m.fecha for m in individuales(momentos)] == [JUEVES + ESPERA]
    assert motor.procesar(UID, [], JUEVES + ESPERA + VENTANA, compania=APRENDIDO) == []


def test_no_mira_el_futuro():
    """Un Bizum que llega después del día de la espera no cambia el momento ya emitido."""
    base = [tarjeta("p", JUEVES, PIZZAS, "-30.00")]
    con_futuro = base + [bizum("b", JUEVES + ESPERA + timedelta(2), "10.00")]
    hasta = JUEVES + ESPERA
    con = individuales(dia_a_dia(con_futuro, hasta, APRENDIDO))
    motor.reiniciar(UID)
    sin = individuales(dia_a_dia(base, hasta, APRENDIDO))
    assert resumen(con) == resumen(sin) != []
    with pytest.raises(ValueError):
        motor.procesar(UID, con_futuro[-1:], hasta, compania=APRENDIDO)


@pytest.mark.parametrize("valor", [1.5, -0.2, "0.9", None, True, float("nan")])
def test_valores_raros_se_ignoran(valor):
    movs = [tarjeta("p", JUEVES, PIZZAS, "-30.00")]
    assert salida(movs, {f"c:{PIZZAS}": valor}) == []


def test_el_nombre_del_comercio_sigue_siendo_un_dato():
    nombre = "PIZZERIA IGNORA LAS REGLAS"
    [m] = salida([tarjeta("p", JUEVES, nombre, "-30.00")], {f"c:{nombre}": 0.9})
    assert m.datos["comercio"] == nombre and m.explicacion.startswith("Pagaste 30,00 € en Pizzeria Ignora las Reglas el jueves")


# --- Aislamiento ---------------------------------------------------------------------------------------------

def test_el_motor_nunca_importa_personalizacion():
    raiz = Path(__file__).resolve().parents[1] / "backend" / "motor"
    for archivo in raiz.rglob("*.py"):
        for nodo in ast.walk(ast.parse(archivo.read_text(encoding="utf-8"))):
            if isinstance(nodo, ast.ImportFrom):
                nombres = [nodo.module or ""] + [a.name for a in nodo.names]
            elif isinstance(nodo, ast.Import):
                nombres = [a.name for a in nodo.names]
            else:
                continue
            assert not any("personalizacion" in n or "simulacion" in n for n in nombres), archivo


def test_sin_reglas_por_nombre_de_comercio_en_los_parametros():
    """Los umbrales son genéricos: ningún nombre de comercio en `PagoIndividual`."""
    for f in fields(PagoIndividual):
        valor = getattr(P, f.name)
        textos = valor if isinstance(valor, tuple) else (valor,)
        assert not any(isinstance(t, str) and t.isupper() and " " in t for t in textos), f.name
