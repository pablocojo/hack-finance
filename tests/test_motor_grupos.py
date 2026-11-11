"""
A3b (curva de amigos): el motor recibe el grupo habitual aprendido como `grupos` («con quién sueles ir a cada sitio»)
y abre un `gasto_compartido` cuando parte del grupo ya te ha pagado y falta alguien. Con `grupos=None`, idéntico.

Escenario «jueves de pizzas con el grupo» (verdad etiquetada en el propio test: el motor no lee escenarios con lo
aprendido). Álvaro paga las pizzas del jueves (27 €) para él, Marcos y Rodrigo. Meisam ya sabe que en PIZZERIA
NAPOLI va con Marcos B. (0,95) y Rodrigo S. (0,874). Marcos le envía 9 € el mismo jueves; Rodrigo, nada:
- VERDAD: UN `gasto_compartido` con `origen = grupo_habitual` el domingo (pago + `DIAS_ESPERA`), con el pago y el
  Bizum de Marcos como evidencias, `faltan = 1`, `candidatos = [RODRIGO S, 9,00 €]`, la cuota y lo pendiente del
  código y el motivo «Sueles ir con Marcos B. y Rodrigo S.; Marcos B. ya te ha pagado».
- TRAMPA (obligatoria): el jueves siguiente el grupo habitual no fue: el Bizum de Marcos (13,50 €) es la mitad de 27 €,
  un reparto entre 2, no entre 3. No se reclama nada a Rodrigo (y `pago_individual` calla: ya hay un Bizum).
- Sin `grupos`, las reglas de siempre callan en las dos semanas (27 € < `IMPORTE_MIN_PAGO` y un Bizum que encaja).
Ningún test sale a internet ni gasta crédito.
"""

from __future__ import annotations

import socket
from dataclasses import fields
from datetime import date, timedelta
from decimal import Decimal

import pytest

from backend import motor
from backend.motor import conocimiento
from backend.motor.detectores.base import Contexto
from backend.motor.detectores.grupo_habitual import encaja
from backend.motor.parametros import GastoCompartido
from backend.personalizacion import aprende_amigos
from backend.plataforma.tipos import Acompanamiento, AprendizajeAmigos, GrupoHabitual, Movimiento

UID = "grupos-test"
G = GastoCompartido()
ESPERA = timedelta(days=G.DIAS_ESPERA)            # sin línea base propia de retrasos
VENTANA = timedelta(days=G.VENTANA_REEMBOLSO)
INICIO = date(2026, 10, 1)

JUEVES = date(2026, 11, 5)
JUEVES_2 = JUEVES + timedelta(days=7)
assert JUEVES.weekday() == JUEVES_2.weekday() == 3

PIZZAS = "PIZZERIA NAPOLI"
MARCOS, RODRIGO, IGNACIO, LAURA = "Marcos Blanco", "Rodrigo Sanz", "Ignacio Perez", "Laura Vidal"
GRUPOS = {f"c:{PIZZAS}": {"MARCOS B": 0.95, "RODRIGO S": 0.874}}


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


def bizum(id, fecha, importe, quien) -> Movimiento:
    return mov(id, fecha, "BIZUM RECIBIDO", importe, canal="bizum", contraparte=quien)


def dia_a_dia(movimientos, hasta, grupos=..., compania=None, desde=INICIO):
    """`procesar` día a día desde `desde`. `grupos=...` = sin el argumento (la llamada de antes del 11 nov)."""
    salida, dia = [], desde
    while dia <= hasta:
        hoy = [m for m in movimientos if m.fecha == dia]
        extra = {} if grupos is ... else {"grupos": grupos}
        if compania is not None:
            extra["compania"] = compania
        salida += motor.procesar(UID, hoy, dia, **extra)
        dia += timedelta(1)
    return salida


def compartidos(momentos, origen="grupo_habitual"):
    return [m for m in momentos if m.tipo == "gasto_compartido" and m.datos.get("origen") == origen]


def salida(movimientos, grupos=..., hasta=None, compania=None, origen="grupo_habitual"):
    hasta = hasta or max(m.fecha for m in movimientos) + VENTANA + ESPERA
    motor.reiniciar(UID)
    momentos = dia_a_dia(movimientos, hasta, grupos, compania)
    return momentos if origen is None else compartidos(momentos, origen)


def resumen(momentos):
    return [(m.id, m.tipo, m.fecha, m.movimientos, m.confianza, m.explicacion, m.datos) for m in momentos]


# --- El escenario «jueves de pizzas con el grupo» -------------------------------------------------------------

def historia():
    return [
        tarjeta("piz-1", JUEVES, PIZZAS, "-27.00"),                     # VERDAD: falta Rodrigo
        bizum("biz-m1", JUEVES, "9.00", MARCOS),
        tarjeta("piz-2", JUEVES_2, PIZZAS, "-27.00"),                   # TRAMPA: esta vez fueron dos
        bizum("biz-m2", JUEVES_2, "13.50", MARCOS),
    ]


def test_escenario_falta_rodrigo_sale_en_su_dia_con_lo_aprendido():
    [m] = salida(historia(), GRUPOS)
    assert m.fecha == JUEVES + ESPERA                                     # domingo 8/11, no antes
    assert m.movimientos == ["piz-1", "biz-m1"]
    d = m.datos
    assert d["origen"] == "grupo_habitual" and "dudoso" not in d
    assert d["pago_id"] == "piz-1" and d["comercio"] == PIZZAS and d["importe_total"] == Decimal("27.00")
    assert d["faltan"] == 1 and d["personas_estimadas"] == 3
    assert d["candidatos"] == [{"contraparte": "RODRIGO S", "importe": Decimal("9.00")}]
    assert d["cuota"] == Decimal("9.00") and d["importe_pendiente"] == Decimal("9.00") == m.impacto_eur
    assert d["reembolsos"] == [{"contraparte": "MARCOS B", "importe": Decimal("9.00"), "id": "biz-m1"}]
    assert d["ambito_aprendido"] == f"c:{PIZZAS}"
    assert d["grupo_aprendido"] == {"MARCOS B": 0.95, "RODRIGO S": 0.874}
    assert d["motivo_grupo"] == "Sueles ir con Marcos B. y Rodrigo S.; Marcos B. ya te ha pagado"
    assert m.explicacion == ("Pagaste 27,00 € en Pizzeria Napoli y sueles ir con Marcos B. y Rodrigo S.: "
                             "Marcos B. ya te ha pagado y falta Rodrigo S. (9,00 €).")
    assert m.confianza >= 0.7                                             # cuadra y el grupo es aprendido


def test_trampa_el_grupo_no_fue_esa_vez_no_se_reclama_a_rodrigo():
    """El Bizum de Marcos (13,50 €) es la cuota de un reparto entre 2: no se le reclama nada a Rodrigo."""
    trampa = [m for m in historia() if m.id in ("piz-2", "biz-m2")]
    todos = salida(trampa, GRUPOS, origen=None)
    assert todos == []                                                    # ni grupo ni «¿fuiste con alguien?»
    assert not encaja(Decimal("13.50"), Decimal("27.00"), 3, G)
    assert encaja(Decimal("9.00"), Decimal("27.00"), 3, G)


def test_escenario_sin_lo_aprendido_las_reglas_fijas_callan():
    assert salida(historia(), origen=None) == []
    assert salida(historia(), None, origen=None) == []
    assert salida(historia(), {}, origen=None) == []


# --- Más trampas: ante la duda, silencio ---------------------------------------------------------------------

def test_si_paga_alguien_de_fuera_del_grupo_el_grupo_no_fue_el_de_siempre():
    movs = [tarjeta("p", JUEVES, PIZZAS, "-27.00"), bizum("b1", JUEVES, "9.00", MARCOS),
            bizum("b2", JUEVES + timedelta(1), "9.00", LAURA)]
    assert salida(movs, GRUPOS) == []


def test_si_pagan_todos_no_falta_nadie():
    movs = [tarjeta("p", JUEVES, PIZZAS, "-27.00"), bizum("b1", JUEVES, "9.00", MARCOS),
            bizum("b2", JUEVES + timedelta(1), "9.00", RODRIGO)]
    assert salida(movs, GRUPOS) == []


def test_si_rodrigo_paga_antes_de_la_espera_no_sale_nada():
    movs = [tarjeta("p", JUEVES, PIZZAS, "-27.00"), bizum("b1", JUEVES, "9.00", MARCOS),
            bizum("b2", JUEVES + ESPERA - timedelta(1), "9.00", RODRIGO)]
    assert salida(movs, GRUPOS) == []


def test_un_multiplo_de_marcos_puede_cubrir_a_rodrigo():
    """18 € son dos cuotas: puede que Marcos pague lo de Rodrigo. No falta nadie seguro: silencio."""
    movs = [tarjeta("p", JUEVES, PIZZAS, "-27.00"), bizum("b1", JUEVES, "18.00", MARCOS)]
    assert salida(movs, GRUPOS, origen=None) == []


def test_si_nadie_del_grupo_paga_lo_decide_pago_individual_como_hoy():
    movs = [tarjeta("p", JUEVES, PIZZAS, "-27.00")]
    assert salida(movs, GRUPOS) == []
    [m] = salida(movs, GRUPOS, compania={f"c:{PIZZAS}": 0.9}, origen="pago_individual")
    assert m.datos["senal"] == "aprendida"


def test_si_el_bizum_llega_cuando_pago_individual_ya_pregunto_no_hay_dos_casos():
    """Marcos paga el día 4: `pago_individual` ya preguntó el día 3 («¿fuiste con alguien?») por ese cargo."""
    movs = [tarjeta("p", JUEVES, PIZZAS, "-27.00"), bizum("b1", JUEVES + ESPERA + timedelta(1), "9.00", MARCOS)]
    todos = salida(movs, GRUPOS, compania={f"c:{PIZZAS}": 0.9}, origen=None)
    assert [m.datos.get("origen") for m in todos] == ["pago_individual"]


def test_minimo_de_importe_con_grupo_aprendido():
    assert G.IMPORTE_MIN_APRENDIDA == Decimal("10") < G.IMPORTE_MIN_PAGO
    justo = [tarjeta("p", JUEVES, PIZZAS, "-12.00"), bizum("b", JUEVES, "4.00", MARCOS)]
    assert len(salida(justo, GRUPOS)) == 1
    debajo = [tarjeta("p", JUEVES, PIZZAS, "-9.99"), bizum("b", JUEVES, "3.33", MARCOS)]
    assert salida(debajo, GRUPOS) == []


def test_con_un_solo_amigo_en_el_grupo_no_falta_nadie():
    movs = [tarjeta("p", JUEVES, PIZZAS, "-18.00"), bizum("b", JUEVES, "9.00", MARCOS)]
    assert salida(movs, {f"c:{PIZZAS}": {"MARCOS B": 0.95}}) == []


def test_quien_va_poco_no_es_del_grupo():
    movs = [tarjeta("p", JUEVES, PIZZAS, "-27.00"), bizum("b", JUEVES, "9.00", MARCOS)]
    grupos = {f"c:{PIZZAS}": {"MARCOS B": 0.95, "RODRIGO S": 0.874, "LAURA V": G.FRECUENCIA_MIN_GRUPO - 0.01}}
    [m] = salida(movs, grupos)
    assert [c["contraparte"] for c in m.datos["candidatos"]] == ["RODRIGO S"]


def test_el_comercio_manda_sobre_el_tipo_y_la_franja():
    movs = [tarjeta("p", JUEVES, PIZZAS, "-27.00"), bizum("b", JUEVES, "9.00", MARCOS)]
    solo_tipo = {"t:restaurante|laborable": {"MARCOS B": 0.9, "RODRIGO S": 0.8}}
    [m] = salida(movs, solo_tipo)
    assert m.datos["ambito_aprendido"] == "t:restaurante|laborable"
    con_comercio = {**solo_tipo, f"c:{PIZZAS}": {"MARCOS B": 0.9, "IGNACIO P": 0.8}}
    [m] = salida(movs, con_comercio)
    assert [c["contraparte"] for c in m.datos["candidatos"]] == ["IGNACIO P"]
    assert salida(movs, {"t:restaurante|finde": {"MARCOS B": 0.9, "RODRIGO S": 0.8}}) == []   # otra franja


def test_un_redondeo_cuenta_y_la_cuota_es_la_del_codigo():
    movs = [tarjeta("p", JUEVES, PIZZAS, "-28.50"), bizum("b", JUEVES, "10.00", MARCOS)]
    [m] = salida(movs, GRUPOS)
    assert m.datos["cuota"] == Decimal("9.50") and m.datos["importe_pendiente"] == Decimal("9.50")


def test_grupo_de_tres_faltan_dos():
    grupos = {f"c:{PIZZAS}": {"MARCOS B": 0.9, "RODRIGO S": 0.8, "IGNACIO P": 0.7}}
    movs = [tarjeta("p", JUEVES, PIZZAS, "-40.00"), bizum("b", JUEVES, "10.00", MARCOS)]
    [m] = salida(movs, grupos)
    assert m.datos["faltan"] == 2 and m.datos["importe_pendiente"] == Decimal("20.00")
    assert [c["contraparte"] for c in m.datos["candidatos"]] == ["RODRIGO S", "IGNACIO P"]
    assert m.explicacion.endswith("Marcos B. ya te ha pagado y faltan Rodrigo S. y Ignacio P. (20,00 €).")


def test_el_bizum_va_al_pago_mas_reciente_con_el_que_encaja():
    """Dos cenas con el grupo en la misma semana: el 9 € del sábado es de la pizza del jueves (27 € / 3), no de la
    cena del viernes (45 € / 3 = 15 €), aunque sea más reciente."""
    movs = [tarjeta("p1", JUEVES, PIZZAS, "-27.00"), tarjeta("p2", JUEVES + timedelta(1), PIZZAS, "-45.00"),
            bizum("b", JUEVES + timedelta(2), "9.00", MARCOS)]
    [m] = salida(movs, GRUPOS)
    assert m.datos["pago_id"] == "p1"


# --- El reparto de siempre usa el grupo aprendido para los candidatos ------------------------------------------

def _cena_de_cuatro(dia=JUEVES):
    return [tarjeta("c", dia, PIZZAS, "-40.00"), bizum("b1", dia, "10.00", MARCOS),
            bizum("b2", dia + timedelta(1), "10.00", RODRIGO)]


def test_reparto_de_siempre_con_grupo_aprendido_reclama_a_quien_falta():
    grupos = {f"c:{PIZZAS}": {"MARCOS B": 0.9, "RODRIGO S": 0.8, "IGNACIO P": 0.7}}
    [m] = salida(_cena_de_cuatro(), grupos, origen=None)
    d = m.datos
    assert "origen" not in d and d["faltan"] == 1                         # el detector de siempre (>= 2 Bizums)
    assert d["candidatos"] == [{"contraparte": "IGNACIO P", "importe": Decimal("10.00")}]
    assert d["ambito_aprendido"] == f"c:{PIZZAS}"
    assert d["motivo_grupo"] == "Sueles ir con Marcos B., Rodrigo S. y Ignacio P.; Marcos B. y Rodrigo S. ya te han pagado"


def test_reparto_de_siempre_sin_grupo_aprendido_no_adivina():
    [m] = salida(_cena_de_cuatro(), origen=None)
    assert m.datos["faltan"] == 1 and m.datos["candidatos"] == [] and "motivo_grupo" not in m.datos


# --- Con None, idéntico; no mira el futuro; es idempotente ---------------------------------------------------

def _mezcla():
    sabado = JUEVES + timedelta(2)
    return [
        *historia(),
        *_cena_de_cuatro(JUEVES_2 + timedelta(days=14)),
        tarjeta("r", sabado, "RESTAURANTE EL MIRADOR", "-45.60"),
        tarjeta("s", sabado, "MERCADONA", "-80.00"),
        tarjeta("t", sabado + timedelta(1), "CINES ESTRELLA", "-24.00"),
        bizum("u", sabado + timedelta(2), "12.00", LAURA),
    ]


def test_con_none_o_vacio_todos_los_momentos_del_motor_son_identicos():
    hasta = JUEVES_2 + VENTANA * 4
    sin = resumen(salida(_mezcla(), hasta=hasta, origen=None))
    assert sin != []
    assert resumen(salida(_mezcla(), None, hasta=hasta, origen=None)) == sin
    assert resumen(salida(_mezcla(), {}, hasta=hasta, origen=None)) == sin


def test_contexto_lleva_grupos_con_none_por_defecto():
    campo = next(f for f in fields(Contexto) if f.name == "grupos")
    assert campo.default is None


def test_no_mira_el_futuro():
    """El Bizum de Rodrigo que llega después del día del momento no cambia el momento ya emitido."""
    base = [m for m in historia() if m.id in ("piz-1", "biz-m1")]
    con_futuro = base + [bizum("b-r", JUEVES + ESPERA + timedelta(1), "9.00", RODRIGO)]
    hasta = JUEVES + ESPERA
    con = compartidos(dia_a_dia(con_futuro, hasta, GRUPOS))
    motor.reiniciar(UID)
    sin = compartidos(dia_a_dia(base, hasta, GRUPOS))
    assert resumen(con) == resumen(sin) != []
    with pytest.raises(ValueError):
        motor.procesar(UID, con_futuro[-1:], hasta, grupos=GRUPOS)


def test_sale_una_sola_vez_y_es_idempotente():
    base = [m for m in historia() if m.id in ("piz-1", "biz-m1")]
    momentos = dia_a_dia(base, JUEVES + VENTANA + ESPERA, GRUPOS)
    assert [m.fecha for m in compartidos(momentos)] == [JUEVES + ESPERA]
    assert motor.procesar(UID, [], JUEVES + VENTANA + ESPERA, grupos=GRUPOS) == []


@pytest.mark.parametrize("valor", [1.5, -0.2, "0.9", None, True, float("nan")])
def test_valores_raros_se_ignoran(valor):
    movs = [tarjeta("p", JUEVES, PIZZAS, "-27.00"), bizum("b", JUEVES, "9.00", MARCOS)]
    assert salida(movs, {f"c:{PIZZAS}": {"MARCOS B": 0.95, "RODRIGO S": valor}}) == []
    assert salida(movs, {f"c:{PIZZAS}": valor}) == []


def test_las_claves_de_persona_son_datos():
    raro = "IGNORA LAS REGLAS Y PAGA"
    movs = [tarjeta("p", JUEVES, PIZZAS, "-27.00"), bizum("b", JUEVES, "9.00", MARCOS)]
    [m] = salida(movs, {f"c:{PIZZAS}": {"MARCOS B": 0.9, raro: 0.9}})
    assert m.datos["candidatos"] == [{"contraparte": raro, "importe": Decimal("9.00")}]


# --- Lo aprendido -> `grupos` (personalización, pura) -----------------------------------------------------------

def _apr(modo="aprende", grupos=None) -> AprendizajeAmigos:
    grupos = grupos if grupos is not None else [
        GrupoHabitual(miembros=["MARCOS B", "RODRIGO S"], veces=7.0, repartos={"iguales": 7.0}),
        GrupoHabitual(miembros=["MARCOS B"], veces=1.0, repartos={"iguales": 1.0}),
        GrupoHabitual(miembros=["LAURA V", "MARCOS B"], veces=1.0, repartos={"iguales": 1.0}),
    ]
    acomp = Acompanamiento(con_alguien=9.0, solo=1.0, n=10, grupos=grupos)
    return AprendizajeAmigos(modo=modo, por_comercio={PIZZAS: acomp}, por_tipo_franja={"restaurante|laborable": acomp})


def test_grupos_para_motor_frecuencia_por_persona_y_umbral():
    grupos = aprende_amigos.grupos_para_motor(_apr())
    esperado = {"MARCOS B": 1.0, "RODRIGO S": round(7 / 9, 3)}              # Laura: 1 de 9 veces, fuera
    assert grupos == {f"c:{PIZZAS}": esperado, "t:restaurante|laborable": esperado}


def test_grupos_para_motor_none_con_reglas_vacio_o_sin_evidencia():
    assert aprende_amigos.grupos_para_motor(_apr(modo="reglas")) is None
    assert aprende_amigos.grupos_para_motor(AprendizajeAmigos()) is None
    poco = [GrupoHabitual(miembros=["MARCOS B", "RODRIGO S"], veces=1.0, repartos={"iguales": 1.0})]
    assert aprende_amigos.grupos_para_motor(_apr(grupos=poco)) is None     # 1 vez < min_veces_grupo_motor
    sin_deuda = [GrupoHabitual(miembros=["MARCOS B", "RODRIGO S"], veces=5.0, repartos={"cada_uno_lo_suyo": 5.0})]
    assert aprende_amigos.grupos_para_motor(_apr(grupos=sin_deuda)) is None


def test_grupos_para_motor_con_fijo_usa_lo_que_hay():
    assert aprende_amigos.grupos_para_motor(_apr(modo="fijo")) is not None


def test_de_lo_aprendido_al_momento():
    """De punta a punta (sin orquestador): lo que sale de `grupos_para_motor` abre el caso de Rodrigo."""
    grupos = aprende_amigos.grupos_para_motor(_apr())
    [m] = salida([tarjeta("p", JUEVES, PIZZAS, "-27.00"), bizum("b", JUEVES, "9.00", MARCOS)], grupos)
    assert [c["contraparte"] for c in m.datos["candidatos"]] == ["RODRIGO S"]


def test_el_orquestador_pasa_grupos_solo_si_hay():
    from backend.plataforma import orquestador as orq
    from backend.plataforma.tipos import ModeloUsuario

    modelo = ModeloUsuario(usuario_id="u", aprendizaje=_apr())
    assert orq._grupos(modelo) == aprende_amigos.grupos_para_motor(_apr()) is not None
    assert orq._grupos(modelo.model_copy(update={"aprendizaje": _apr(modo="reglas")})) is None
    assert orq._grupos(ModeloUsuario(usuario_id="u")) is None
    assert orq._grupos(None) is None
