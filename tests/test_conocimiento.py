"""Conocimiento de comercios (M7) y `prueba_gratuita`: alta por verificación, duración, cuándo, cierre.

Sin internet y sin crédito: el catálogo es el del repo, la caché web va a un directorio temporal y
cualquier intento de abrir un socket falla el test.
"""

from __future__ import annotations

import hashlib
import json
import socket
from datetime import date, timedelta
from decimal import Decimal

import pytest

from backend import claude_client, motor
from backend.escenarios import cargar
from backend.motor import conocimiento, pruebas
from backend.motor.parametros import PruebaGratuita
from backend.plataforma.tipos import InfoComercio, Movimiento, PerfilUsuario, Suscripcion

P = PruebaGratuita()
TRAMPAS = ["verificacion-tienda", "ya-la-pago", "sumup-persona", "gasolinera-1eur", "cobro-antes"]


@pytest.fixture(autouse=True)
def sin_internet(monkeypatch):
    def prohibido(*args, **kwargs):
        raise AssertionError("Un test ha intentado salir a internet.")

    monkeypatch.setattr(socket.socket, "connect", prohibido)
    monkeypatch.setattr(socket, "create_connection", prohibido)
    conocimiento.limpiar_memoria()
    for uid in ("u1", "u2", "lucia"):
        motor.reiniciar(uid)
    yield
    conocimiento.limpiar_memoria()
    for uid in ("u1", "u2", "lucia"):
        motor.reiniciar(uid)


def mov(id, fecha, concepto, importe, **extra) -> Movimiento:
    return Movimiento(id=id, fecha=fecha, concepto=concepto, importe=Decimal(str(importe)), **extra)


def verificacion(id, fecha, nombre, importe="0.00") -> Movimiento:
    return mov(id, fecha, f"VERIFICACION TARJETA {nombre}", importe, canal="tarjeta")


def dia_a_dia(uid, movimientos, desde, hasta, perfil=None):
    salida, dia = [], desde
    while dia <= hasta:
        salida += motor.procesar(uid, [m for m in movimientos if m.fecha == dia], dia, perfil)
        dia += timedelta(1)
    return salida


def pruebas_de(momentos):
    return [m for m in momentos if m.tipo == "prueba_gratuita"]


def estado_final(esc) -> dict:
    """El estado del motor al terminar de reproducir el escenario sin perfil."""
    guardado = {}
    cargar.reproducir(esc, con_perfil=False, al_terminar=lambda uid: guardado.update(motor.exportar_estado(uid)))
    return guardado


def etiqueta(esc, tipo="prueba_gratuita"):
    return next(e for e in esc.esperado if e["tipo"] == tipo)


# --- Catálogo y caché ------------------------------------------------------------------------

def test_catalogo_streamflix_de_la_demo():
    info = conocimiento.info_en_cache("Streamflix")
    assert info.origen == "catalogo" and info.es_suscripcion and info.dias_prueba == 30
    assert info.precio_tras_prueba == Decimal("9.99")
    assert info.url_baja.startswith("https://") and 1 <= len(info.pasos_baja) <= 5
    assert all(len(p) <= 200 for p in info.pasos_baja)
    assert info.fuentes and "demo" in info.fuentes[0].lower()


def test_catalogo_sonora_y_fitapp_ficticios():
    assert (conocimiento.info_en_cache("SONORA MUSIC").dias_prueba, conocimiento.info_en_cache("sonora music").precio_tras_prueba) == (14, Decimal("10.99"))
    assert (conocimiento.info_en_cache("FITAPP PLUS").dias_prueba, conocimiento.info_en_cache("FITAPP PLUS").precio_tras_prueba) == (7, Decimal("4.99"))


@pytest.mark.parametrize("nombre", ["NETFLIX", "SPOTIFY", "AMAZON PRIME", "DISNEY+", "HBO MAX", "DAZN", "AUDIBLE", "YOUTUBE PREMIUM"])
def test_catalogo_marcas_reales_solo_con_tipo_y_suscripcion(nombre):
    info = conocimiento.info_en_cache(nombre)
    assert info.es_suscripcion and info.tipo and info.origen == "catalogo"
    assert (info.dias_prueba, info.precio_tras_prueba, info.url_baja, info.pasos_baja) == (None, None, None, None)


@pytest.mark.parametrize("nombre", ["ZARA", "REPSOL", "NH HOTELES", "MERCADONA"])
def test_catalogo_comercios_que_no_son_suscripcion(nombre):
    info = conocimiento.info_en_cache(nombre)
    assert info is not None and not info.es_suscripcion and info.origen == "catalogo"


def test_catalogo_entero_valida_y_la_clave_es_el_nombre():
    crudo = json.loads(conocimiento.RUTA_CATALOGO.read_text(encoding="utf-8"))
    fichas = {k: v for k, v in crudo.items() if not k.startswith("_")}
    assert len(fichas) >= 15
    for clave, ficha in fichas.items():
        info = InfoComercio.model_validate(ficha)
        assert info.nombre == clave and info.origen == "catalogo"
        if info.url_baja:
            assert info.url_baja.startswith("https://")


def test_info_en_cache_desconocido_es_none_y_ignora_mayusculas_y_tildes():
    assert conocimiento.info_en_cache("COMERCIO QUE NO EXISTE") is None
    assert conocimiento.info_en_cache("") is None
    assert conocimiento.info_en_cache("  streamflix ").nombre == "STREAMFLIX"


def test_guardar_escribe_la_cache_web_y_no_el_catalogo(tmp_path):
    antes = hashlib.sha1(conocimiento.RUTA_CATALOGO.read_bytes()).hexdigest()
    info = InfoComercio(nombre="Estudio Arco", tipo="deporte", es_suscripcion=True, dias_prueba=14,
                        precio_tras_prueba=Decimal("12.00"), fuentes=["https://ejemplo.example/precios"], origen="web")
    assert conocimiento.info_en_cache("ESTUDIO ARCO") is None
    conocimiento.guardar(info)
    leida = conocimiento.info_en_cache("estudio arco")
    assert leida.origen == "web" and leida.dias_prueba == 14 and leida.precio_tras_prueba == Decimal("12.00")
    assert conocimiento.ruta_cache_web().is_file() and tmp_path in conocimiento.ruta_cache_web().parents
    assert hashlib.sha1(conocimiento.RUTA_CATALOGO.read_bytes()).hexdigest() == antes


def test_guardar_rechaza_origen_catalogo_y_el_catalogo_manda_sobre_la_web():
    with pytest.raises(ValueError):
        conocimiento.guardar(InfoComercio(nombre="X", tipo="y", origen="catalogo"))
    conocimiento.guardar(InfoComercio(nombre="STREAMFLIX", tipo="otro", es_suscripcion=False, origen="web"))
    assert conocimiento.info_en_cache("STREAMFLIX").origen == "catalogo"


def test_cache_web_estropeada_no_rompe_nada():
    ruta = conocimiento.ruta_cache_web()
    ruta.parent.mkdir(parents=True)
    ruta.write_text("{esto no es json", encoding="utf-8")
    assert conocimiento.info_en_cache("ESTUDIO ARCO") is None
    conocimiento.guardar(InfoComercio(nombre="ESTUDIO ARCO", tipo="deporte", origen="desconocido"))
    assert conocimiento.info_en_cache("ESTUDIO ARCO").origen == "desconocido"


def test_info_comercio_con_la_busqueda_apagada_no_llama_a_nadie():
    assert conocimiento.info_comercio("COMERCIO QUE NO EXISTE") is None
    assert conocimiento.info_comercio("STREAMFLIX").origen == "catalogo"
    assert claude_client.cliente().peticiones == []


# --- Nombres buscables ------------------------------------------------------------------------

@pytest.mark.parametrize("nombre, etiquetas, esperado", [
    ("ESTUDIO ARCO", (), True),
    ("SUMUP *JUAN PEREZ", ("posible_persona",), False),
    ("TIENDA 24 HORAS", (), False),
    ("UN COMERCIO CON UN NOMBRE DEMASIADO LARGO PARA BUSCAR", (), False),
    ("APPLE", ("pasarela",), False),
    ("GOOGLE", ("pasarela",), False),
    ("PAYPAL", ("pasarela",), False),
    ("SONORA MUSIC", ("pasarela",), True),
    ("", (), False),
])
def test_prueba_solo_se_busca_un_nombre_de_comercio(nombre, etiquetas, esperado):
    assert pruebas.buscable(nombre, etiquetas, P) is esperado


# --- prueba_gratuita: el escenario de la demo --------------------------------------------------

@pytest.fixture(scope="module")
def streamflix():
    return cargar.cargar("prueba-streamflix-lucia")


def test_prueba_streamflix_avisa_el_10_con_la_duracion_del_catalogo(streamflix):
    esperado = etiqueta(streamflix)
    momentos = pruebas_de(cargar.reproducir(streamflix, con_perfil=False))
    assert len(momentos) == 1
    m = momentos[0]
    assert m.fecha == esperado["fecha_detectable"] == date(2026, 11, 10)
    assert m.datos["dias_hasta"] == 3 and m.datos["fuente_duracion"] == "catalogo"
    assert m.datos["fecha_primer_cobro"] == "2026-11-13" and m.datos["fecha_alta"] == "2026-10-14"
    assert m.datos["dias_prueba"] == 30 and m.datos["comercio"] == "STREAMFLIX" and m.datos["fuente"] == "verificacion"
    assert m.datos["importe_previsto"] == Decimal("9.99") and m.impacto_eur == Decimal("9.99")
    assert m.datos["verificacion_id"] == "luc-v1" and m.movimientos == ["luc-v1"]
    assert m.datos["fuentes_info"] and m.confianza == 0.9 and m.detector == "prueba_gratuita"


def test_prueba_streamflix_explicacion_de_una_frase(streamflix):
    [m] = pruebas_de(cargar.reproducir(streamflix, con_perfil=False))
    assert m.explicacion == "Tu prueba de Streamflix empieza a cobrarse en 3 días (el 13/11) por 9,99 €."


def test_prueba_streamflix_evaluacion_perfecta(streamflix):
    momentos = cargar.reproducir(streamflix, con_perfil=False)
    r = cargar.evaluar(streamflix, momentos)
    assert (r["aciertos"], r["omitidos"], r["falsos_positivos"], r["trampas_violadas"], r["retrasos"]) == (1, 0, [], [], [0])


def test_prueba_streamflix_con_perfil_calculado_es_igual(streamflix):
    esc = cargar.cargar("prueba-streamflix-lucia")
    sin = pruebas_de(cargar.reproducir(esc, con_perfil=False))
    con = pruebas_de(cargar.reproducir(esc, con_perfil=True) if esc.perfil else
                     cargar.reproducir(cargar.desde_dict({**esc.crudo, "perfil": "calcular"}), con_perfil=True))
    assert [(m.id, m.fecha, m.datos) for m in sin] == [(m.id, m.fecha, m.datos) for m in con]


def test_prueba_ningun_dia_anterior_avisa(streamflix):
    esperado = etiqueta(streamflix)["fecha_detectable"]
    momentos = cargar.reproducir(streamflix, con_perfil=False)
    assert all(m.fecha >= esperado for m in pruebas_de(momentos))
    assert [m.fecha for m in pruebas_de(momentos)] == [esperado]       # y solo una vez, aunque siga el reloj


@pytest.mark.parametrize("escenario_id", TRAMPAS)
def test_prueba_trampas_no_disparan_nada(escenario_id):
    esc = cargar.cargar(escenario_id)
    momentos = cargar.reproducir(esc, con_perfil=False)
    r = cargar.evaluar(esc, momentos)
    assert pruebas_de(momentos) == [] and r["trampas_violadas"] == [] and r["falsos_positivos"] == []
    assert esc.trampas and all(t["tipo"] == "prueba_gratuita" for t in esc.trampas)


def test_prueba_verificacion_de_una_tienda_ni_se_pide_ni_se_abre():
    estado = estado_final(cargar.cargar("verificacion-tienda"))
    assert estado["pruebas"] == [] and estado["comercios_pendientes"] == []


def test_prueba_ya_la_pago_no_abre_ninguna_prueba():
    assert estado_final(cargar.cargar("ya-la-pago"))["pruebas"] == []


def test_prueba_sumup_persona_no_se_busca_ni_se_abre():
    estado = estado_final(cargar.cargar("sumup-persona"))
    assert estado["pruebas"] == [] and estado["comercios_pendientes"] == []


def test_prueba_gasolinera_no_abre_ninguna_prueba():
    assert estado_final(cargar.cargar("gasolinera-1eur"))["pruebas"] == []


# --- Otras altas -------------------------------------------------------------------------------

def test_prueba_de_1_euro_con_devolucion_es_prueba_y_usa_los_dos_movimientos():
    esc = cargar.cargar("prueba-1eur-sonora")
    momentos = pruebas_de(cargar.reproducir(esc, con_perfil=False))
    [m] = momentos
    assert m.fecha == etiqueta(esc)["fecha_detectable"] == date(2026, 10, 31)
    assert m.movimientos == ["son-v1", "son-d1"] and m.datos["importe_previsto"] == Decimal("10.99")
    assert m.datos["dias_prueba"] == 14 and m.datos["dias_hasta"] == 3


def test_prueba_de_1_euro_sin_devolucion_no_es_prueba():
    movs = [verificacion("v", date(2026, 10, 20), "SONORA MUSIC", "-1.00")]
    assert pruebas_de(dia_a_dia("u1", movs, date(2026, 10, 1), date(2026, 11, 10))) == []
    assert motor.exportar_estado("u1")["pruebas"] == []


def test_prueba_devolucion_tardia_de_1_euro_no_cuenta():
    movs = [verificacion("v", date(2026, 10, 20), "SONORA MUSIC", "-1.00"),
            mov("d", date(2026, 10, 20) + timedelta(P.VENTANA_DEVOLUCION_VERIF + 1), "DEVOLUCION SONORA MUSIC", "1.00",
                canal="tarjeta")]
    assert pruebas_de(dia_a_dia("u1", movs, date(2026, 10, 1), date(2026, 11, 10))) == []


def test_prueba_tras_paypal_se_reconoce_el_comercio():
    esc = cargar.cargar("prueba-paypal")
    [m] = pruebas_de(cargar.reproducir(esc, con_perfil=False))
    assert m.datos["comercio"] == "SONORA MUSIC" and m.fecha == etiqueta(esc)["fecha_detectable"]


def test_prueba_tras_apple_no_se_reconoce_ni_se_busca():
    movs = [mov("a", date(2026, 10, 20), "VERIFICACION TARJETA APPLE.COM/BILL", "0.00", canal="tarjeta")]
    assert pruebas_de(dia_a_dia("u1", movs, date(2026, 10, 1), date(2026, 11, 30))) == []
    assert motor.comercios_pendientes("u1") == []


def test_prueba_sin_verificacion_explicita_no_la_inventa():
    # Un cargo de 0,99 € que no se devuelve no es una verificación: es un cargo.
    movs = [mov("c", date(2026, 10, 20), "COMPRA TARJETA SONORA MUSIC", "-0.99", canal="tarjeta", categoria="suscripciones")]
    assert pruebas_de(dia_a_dia("u1", movs, date(2026, 10, 1), date(2026, 11, 30))) == []


# --- Comercio sin ficha: se pide y la respuesta llega al día siguiente ------------------------

def test_prueba_sin_ficha_se_pide_y_llega_al_dia_siguiente():
    alta = date(2026, 11, 1)
    movs = [verificacion("v", alta, "ESTUDIO ARCO")]
    assert dia_a_dia("u1", movs, date(2026, 10, 20), alta + timedelta(1)) == []
    assert motor.comercios_pendientes("u1") == ["ESTUDIO ARCO"]
    assert motor.exportar_estado("u1")["pruebas"] == []                  # sin ficha ni categoría: no se abre
    conocimiento.guardar(InfoComercio(nombre="ESTUDIO ARCO", tipo="deporte", es_suscripcion=True, dias_prueba=14,
                                      precio_tras_prueba=Decimal("12.00"), fuentes=["https://ejemplo.example/p"],
                                      origen="web"))
    momentos = pruebas_de(dia_a_dia("u1", [], alta + timedelta(2), alta + timedelta(30)))
    [m] = momentos
    assert m.fecha == alta + timedelta(14 - 3)
    assert m.datos["fuente_duracion"] == "web" and m.datos["importe_previsto"] == Decimal("12.00")
    assert m.datos["fuentes_info"] == ["https://ejemplo.example/p"] and m.confianza == 0.9
    assert motor.comercios_pendientes("u1") == []


def test_prueba_ficha_que_dice_que_no_es_suscripcion_la_descarta():
    alta = date(2026, 11, 1)
    conocimiento.guardar(InfoComercio(nombre="ESTUDIO ARCO", tipo="tienda", es_suscripcion=False, origen="web"))
    assert pruebas_de(dia_a_dia("u1", [verificacion("v", alta, "ESTUDIO ARCO")], alta, alta + timedelta(40))) == []
    assert motor.exportar_estado("u1")["pruebas"] == [] and motor.comercios_pendientes("u1") == []


def test_prueba_ficha_desconocida_no_se_vuelve_a_pedir():
    alta = date(2026, 11, 1)
    conocimiento.guardar(InfoComercio(nombre="ESTUDIO ARCO", tipo="desconocido", origen="desconocido"))
    dia_a_dia("u1", [verificacion("v", alta, "ESTUDIO ARCO")], alta, alta + timedelta(3))
    assert motor.comercios_pendientes("u1") == []


def test_prueba_categoria_por_reglas_sin_ficha_avisa_con_confianza_baja():
    alta = date(2026, 11, 1)
    movs = [mov("v", alta, "VERIFICACION TARJETA RADIO BOX", "0.00", canal="tarjeta", categoria="suscripciones")]
    momentos = pruebas_de(dia_a_dia("u1", movs, alta, alta + timedelta(40)))
    [m] = momentos
    assert m.confianza == P.CONFIANZA_SIN_CATALOGO_MAX and m.datos["fuente_duracion"] == "por_defecto"
    assert m.fecha == alta + timedelta(P.DIAS_PRUEBA_POR_DEFECTO - (P.AVISO_DIAS_ANTES + P.AVISO_DIAS_EXTRA_POR_DEFECTO))
    assert "importe_previsto" not in m.datos and m.impacto_eur is None and m.datos["fuentes_info"] == []
    assert "he supuesto 30 días" in m.explicacion


# --- Perfil -------------------------------------------------------------------------------------

def _perfil(en_prueba: bool) -> PerfilUsuario:
    return PerfilUsuario(calculado=date(2026, 10, 21), dias_historial=90, suscripciones_activas=[
        Suscripcion(comercio="STREAMFLIX", importe=Decimal("9.99"), periodicidad_dias=30, en_prueba=en_prueba)])


def _reproducir_con_perfil(esc, desde, perfil_desde):
    """Día a día; `perfil_desde` pone el perfil a mano a partir de esa fecha (lo recalcula el orquestador)."""
    uid = "lucia"
    motor.cargar_historial(uid, esc.previos(), esc.activacion)
    salida, dia = [], esc.activacion + timedelta(1)
    while dia <= esc.hasta:
        salida += motor.procesar(uid, esc.del_dia(dia), dia, perfil_desde(dia))
        dia += timedelta(1)
    return pruebas_de(salida)


def test_prueba_recalcular_el_perfil_a_mitad_de_la_prueba_no_la_mata(streamflix):
    esperado = etiqueta(streamflix)["fecha_detectable"]
    desde = date(2026, 10, 21)
    momentos = _reproducir_con_perfil(streamflix, desde, lambda d: _perfil(True) if d >= desde else None)
    assert [m.fecha for m in momentos] == [esperado] and momentos[0].datos["dias_hasta"] == 3


def test_prueba_en_suscripciones_activas_ya_se_paga_y_no_abre_prueba(streamflix):
    momentos = _reproducir_con_perfil(streamflix, None, lambda d: _perfil(False))
    assert momentos == []


def test_prueba_en_prueba_en_el_perfil_desde_el_principio_se_ignora(streamflix):
    momentos = _reproducir_con_perfil(streamflix, None, lambda d: _perfil(True))
    assert [m.fecha for m in momentos] == [etiqueta(streamflix)["fecha_detectable"]]


# --- Cierre ---------------------------------------------------------------------------------------

def test_prueba_cobrada_se_cierra_y_no_avisa():
    [prueba] = estado_final(cargar.cargar("cobro-antes"))["pruebas"]
    assert prueba["estado"] == "cobrada" and prueba["cerrada"] == "2026-11-08"


def test_prueba_cobrada_dentro_del_margen_de_7_dias_tras_el_primer_cobro():
    alta = date(2026, 10, 14)
    cobro = alta + timedelta(30 + P.DIAS_GRACIA_COBRO)
    movs = [verificacion("v", alta, "STREAMFLIX"),
            mov("c", cobro, "COMPRA TARJETA STREAMFLIX", "-9.99", canal="tarjeta", categoria="suscripciones")]
    momentos = pruebas_de(dia_a_dia("u1", movs, date(2026, 10, 1), cobro + timedelta(3)))
    assert [m.fecha for m in momentos] == [alta + timedelta(27)]          # avisó antes del cobro
    assert motor.exportar_estado("u1")["pruebas"][0]["estado"] == "cobrada"


def test_prueba_caducada_pasado_el_margen_sin_cobro():
    alta = date(2026, 10, 14)
    ultimo = alta + timedelta(30 + P.DIAS_GRACIA_COBRO)
    dia_a_dia("u1", [verificacion("v", alta, "STREAMFLIX")], date(2026, 10, 1), ultimo)
    assert motor.exportar_estado("u1")["pruebas"][0]["estado"] == "abierta"
    dia_a_dia("u1", [], ultimo + timedelta(1), ultimo + timedelta(1))
    prueba = motor.exportar_estado("u1")["pruebas"][0]
    assert prueba["estado"] == "caducada" and prueba["cerrada"] == (ultimo + timedelta(1)).isoformat()
    assert dia_a_dia("u1", [], ultimo + timedelta(2), ultimo + timedelta(60)) == []


def test_prueba_cargo_de_1_euro_o_menos_no_cierra_la_prueba():
    alta = date(2026, 10, 14)
    movs = [verificacion("v", alta, "STREAMFLIX"),
            mov("c", alta + timedelta(5), "COMPRA TARJETA STREAMFLIX", "-1.00", canal="tarjeta", tipo_operacion="cargo")]
    dia_a_dia("u1", movs, date(2026, 10, 1), alta + timedelta(10))
    assert motor.exportar_estado("u1")["pruebas"][0]["estado"] == "abierta"


def test_prueba_cobro_posterior_a_la_baja_guiada_la_pasa_a_cobrada():
    esc = cargar.cargar("prueba-baja-guiada")
    assert len(pruebas_de(cargar.reproducir(esc, con_perfil=False))) == 1       # el aviso del 10/11 salió
    assert [p["estado"] for p in estado_final(esc)["pruebas"]] == ["cobrada"]


# --- Estado, idempotencia y futuro ----------------------------------------------------------------

def test_prueba_el_estado_sobrevive_a_exportar_e_importar_a_mitad(streamflix):
    esperado = etiqueta(streamflix)["fecha_detectable"]
    motor.cargar_historial("u1", streamflix.previos(), streamflix.activacion)
    dia = streamflix.activacion + timedelta(1)
    while dia < esperado - timedelta(5):
        assert motor.procesar("u1", streamflix.del_dia(dia), dia) == []
        dia += timedelta(1)
    texto = json.dumps(motor.exportar_estado("u1"))
    motor.reiniciar("u1")
    motor.importar_estado("u2", json.loads(texto))
    salida = []
    while dia <= streamflix.hasta:
        salida += motor.procesar("u2", streamflix.del_dia(dia), dia)
        dia += timedelta(1)
    assert [m.fecha for m in pruebas_de(salida)] == [esperado]


def test_prueba_reprocesar_el_mismo_dia_no_repite_el_aviso(streamflix):
    esperado = etiqueta(streamflix)["fecha_detectable"]
    motor.cargar_historial("u1", streamflix.previos(), streamflix.activacion)
    dia = streamflix.activacion + timedelta(1)
    while dia < esperado:
        motor.procesar("u1", streamflix.del_dia(dia), dia)
        dia += timedelta(1)
    assert len(pruebas_de(motor.procesar("u1", [], esperado))) == 1
    assert motor.procesar("u1", [], esperado) == []


def test_prueba_no_mira_el_futuro(streamflix):
    """Con el cobro del 13/11 ya en el sistema, el 10/11 sale igual: el motor solo ve fecha <= hoy."""
    esperado = etiqueta(streamflix)["fecha_detectable"]
    cobro = mov("fut", date(2026, 11, 13), "COMPRA TARJETA STREAMFLIX", "-9.99", canal="tarjeta", categoria="suscripciones")
    con_futuro = cargar.desde_dict({**streamflix.crudo, "movimientos": streamflix.crudo["movimientos"] + [
        {"id": "fut", "fecha": date(2026, 11, 13), "concepto": cobro.concepto, "comercio": "STREAMFLIX",
         "importe": "-9.99", "canal": "tarjeta", "categoria": "suscripciones"}]})
    [m] = pruebas_de(cargar.reproducir(con_futuro, con_perfil=False))
    assert m.fecha == esperado and m.datos["dias_hasta"] == 3


def test_prueba_el_estado_exportado_es_json_puro(streamflix):
    assert json.loads(json.dumps(estado_final(streamflix)))["pruebas"][0]["comercio"] == "STREAMFLIX"


# --- Sin internet ---------------------------------------------------------------------------------

def test_prueba_ninguna_ruta_del_motor_llama_a_claude():
    for escenario_id in ("prueba-streamflix-lucia", "prueba-dicha-usuario", "prueba-1eur-sonora"):
        cargar.reproducir(cargar.cargar(escenario_id), con_perfil=False)
    assert claude_client.cliente().peticiones == []
