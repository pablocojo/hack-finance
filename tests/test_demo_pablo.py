"""`demo-pablo` (11 nov): la demo sencilla de /app con el historial de Pablo, día a día.

Dos notificaciones en las dos semanas: el cine de Kinepolis (pregunta de un toque, juicio de la IA desde la caché
versionada) y las pizzas de Mamma Rosa (falta el Bizum de Nacho). La cena del viernes en Taberna El Búho no avisa: la
apunta Pablo (chat o botón). Con `amigos_pagan_tras_solicitud_dias: 1`, el amigo al que se le pide el Bizum con el botón
paga al día siguiente y el caso se cierra solo. Todas las fechas salen de las etiquetas del escenario. Sin red ni gasto.
"""

from __future__ import annotations

import socket
from datetime import date, timedelta
from decimal import Decimal

import pytest

from backend import casos, motor
from backend.acciones import banco_sim
from backend.escenarios import cargar
from backend.motor import conocimiento, ocio
from backend.plataforma import chat_casos
from backend.plataforma import orquestador as orq
from backend.plataforma.tipos import ApuntarGastoEntrada

UID = "pablo"
MODULOS = ["gasto_compartido", "cobro_duplicado", "fin_de_prueba"]      # los que marca /app por defecto
TEXTO_CINE = "32,70 € en Kinepolis Ciudad de la Imagen el sábado: parecen 3 entradas. ¿Fuiste con alguien?"
FRASE_CHAT = "la cena del viernes en El Búho"     # lo que extrae el chat de «... la pagué yo, era con Sergio»


@pytest.fixture(autouse=True)
def sin_red(monkeypatch):
    conectar = socket.socket.connect

    def solo_local(sock, direccion, *args, **kwargs):   # el bucle de eventos de Windows usa un socketpair en 127.0.0.1
        if isinstance(direccion, tuple) and direccion[0] in ("127.0.0.1", "::1", "localhost"):
            return conectar(sock, direccion, *args, **kwargs)
        raise AssertionError("Un test ha intentado salir a internet.")

    def prohibido(*args, **kwargs):
        raise AssertionError("Un test ha intentado salir a internet.")

    monkeypatch.setattr(socket.socket, "connect", solo_local)
    monkeypatch.setattr(socket, "create_connection", prohibido)
    monkeypatch.delenv("OCIO_IA", raising=False)
    monkeypatch.delenv("DUDAS_IA", raising=False)
    monkeypatch.delenv("DEMO_KEY", raising=False)
    conocimiento.limpiar_memoria()
    ocio.limpiar_memoria()
    yield
    conocimiento.limpiar_memoria()
    ocio.limpiar_memoria()


@pytest.fixture(scope="module")
def demo():
    return cargar.cargar("demo-pablo")


def fecha_de(demo, pago_id: str) -> date:
    return next(e["fecha_detectable"] for e in demo.esperado if pago_id in e["ids"])


def cine(demo) -> date:
    return fecha_de(demo, "pab-d10")


def pizzas(demo) -> date:
    return fecha_de(demo, "pab-d11")


def cena(demo) -> date:
    return fecha_de(demo, "pab-d09")


def avanzar_hasta(dia: date) -> list:
    decisiones = []
    hoy = date.fromisoformat(orq.estado_usuario(UID)["hoy"])
    while hoy < dia:
        hoy += timedelta(days=1)
        decisiones += [(hoy, d) for d in orq.avanzar_dia(UID, hoy)]
    return decisiones


def preparado(falso, con_opcion: bool = True):
    cliente = falso()
    orq.cargar_escenario("demo-pablo")
    if not con_opcion:                      # como cualquier usuario: sin la opción de la demo
        estado = orq._estado(UID)
        estado.pop(orq.OPCION_PAGO_AMIGOS)
        orq.alm.guardar(UID, "estado", estado)
    orq.activar(UID, MODULOS, {"copiloto": True, "memoria": True})
    return cliente


def aviso_pizzas() -> dict:
    [n] = [n for n in orq.notificaciones(UID, "ahora") if n["propuesta"]["id"].startswith("prop-mom-")]
    return n


def pedir_bizum_a_nacho() -> str:
    propuesta = aviso_pizzas()["propuesta"]
    accion = next(a for a in propuesta["acciones_ofrecidas"] if a["accion_id"] == "pedir_bizum")
    tarjeta = orq.preparar_accion(UID, propuesta["id"], "pedir_bizum", accion["parametros"])
    resultado = orq.confirmar_accion(UID, tarjeta.token_confirmacion)
    assert resultado.ok
    return resultado.datos["resultado_id"]


def caso_pizzas():
    return next(c for c in casos.cargar(UID) if c.hechos.get("pago_id") == "pab-d11")


# --- El escenario ---------------------------------------------------------------------------------------------------

def test_el_escenario_tiene_historial_de_seis_semanas_amigos_y_la_opcion_de_la_demo(demo):
    assert (demo.id, demo.usuario_id, demo.perfil) == ("demo-pablo", "pablo", "calcular")
    assert demo.activacion == date(2026, 11, 1) and demo.hasta == date(2026, 11, 15)
    assert (demo.activacion - min(m.fecha for m in demo.previos())).days + 1 >= 28      # `perfilar` necesita 28 días
    assert {c.contraparte for c in demo.contactos} >= {"RODRIGO P", "IRENE C", "NACHO G", "SERGIO M"}
    assert demo.amigos_pagan_tras_solicitud_dias == 1
    assert cargar.cargar("demo-lucia").amigos_pagan_tras_solicitud_dias is None         # Lucía, como siempre


@pytest.mark.parametrize("valor", [0, 7, True, "1"])
def test_la_opcion_solo_admite_de_1_a_6_dias(valor):
    crudo = dict(cargar.leer("demo-pablo"), amigos_pagan_tras_solicitud_dias=valor)
    with pytest.raises(ValueError):
        cargar.desde_dict(crudo)


def test_el_cine_son_3_entradas_de_sabado_con_los_precios_reales_y_el_juicio_esta_en_la_cache(demo):
    pago = next(m for m in demo.movimientos if m.id == "pab-d10")
    assert pago.fecha.weekday() == 5 and pago.importe == Decimal("-32.70")
    datos = ocio.analizar_pago(Decimal("32.70"), "KINEPOLIS CIUDAD DE LA IMAGEN", "cine", pago.fecha)
    assert [(c["personas"], c["corta"]) for c in datos["combinaciones"]] == [
        (3, "3 entradas"), (2, "2 entradas con dos palomitas saladas pequeñas")]
    juicio = ocio.juzgar(Decimal("32.70"), "KINEPOLIS CIUDAD DE LA IMAGEN", "cine", datos)
    assert juicio is not None and juicio.origen == "cache" and juicio.combinacion == "c1"
    assert juicio.p_acompanado >= ocio.P_ACOMPANADO_MIN


@pytest.mark.parametrize("con", [False, True])
def test_el_motor_da_la_cena_el_cine_y_las_pizzas_en_sus_fechas_sin_trampas(demo, con):
    momentos = cargar.reproducir(demo, con_perfil=con)
    assert [(cargar.tipo_medido(m), m.fecha) for m in momentos] == [
        ("pago_individual", cena(demo)), ("pago_individual", cine(demo)), ("gasto_compartido", pizzas(demo))]
    r = cargar.evaluar(demo, momentos, con_perfil=con)
    assert r["aciertos"] == 3 and r["omitidos"] == 0
    assert r["falsos_positivos"] == [] and r["dudosos"] == [] and r["trampas_violadas"] == []
    [p] = [m for m in momentos if m.tipo == "gasto_compartido" and m.datos.get("origen") != "pago_individual"]
    assert [c["contraparte"] for c in p.datos["candidatos"]] == ["NACHO G"] and p.datos["importe_pendiente"] == Decimal("13.00")


def test_online_hasta_la_vispera_no_hay_nada_y_el_dia_esperado_aparece(demo):
    uid = "__test_demo_pablo__"
    motor.reiniciar(uid)
    try:
        motor.cargar_historial(uid, demo.previos(), demo.activacion)
        emitidos: dict[str, date] = {}
        dia = demo.activacion + timedelta(1)
        while dia <= demo.hasta:
            for m in motor.procesar(uid, demo.del_dia(dia), dia):
                emitidos[m.movimientos[0]] = m.fecha
            dia += timedelta(1)
        assert emitidos == {"pab-d09": cena(demo), "pab-d10": cine(demo), "pab-d11": pizzas(demo)}
    finally:
        motor.reiniciar(uid)


# --- La regla 4 de `pago_individual`: las cuotas de otro pago no callan la pregunta ------------------------------------

def _cine_con(movimientos: list[dict]) -> list:
    base = {"id": "cine-y-pizzas", "usuario_id": "u", "activacion": "2026-11-01", "hasta": "2026-11-14",
            "movimientos": [{"id": "k", "fecha": "2026-11-07", "concepto": "COMPRA TARJETA KINEPOLIS",
                             "comercio": "KINEPOLIS CIUDAD DE LA IMAGEN", "importe": -32.70, "canal": "tarjeta",
                             "categoria": "ocio"}, *movimientos]}
    return [m for m in cargar.reproducir(cargar.desde_dict(base), con_perfil=False)
            if m.datos.get("origen") == "pago_individual"]


def test_los_bizums_de_las_pizzas_del_domingo_no_callan_la_pregunta_del_cine():
    pizzas_y_bizums = [
        {"id": "p", "fecha": "2026-11-08", "concepto": "COMPRA TARJETA PIZZERIA MAMMA ROSA", "comercio": "PIZZERIA MAMMA ROSA",
         "importe": -52.00, "canal": "tarjeta", "categoria": "restaurantes"},
        {"id": "b1", "fecha": "2026-11-08", "concepto": "BIZUM RECIBIDO", "contraparte": "RODRIGO P", "importe": 13.00,
         "canal": "bizum"},
        {"id": "b2", "fecha": "2026-11-08", "concepto": "BIZUM RECIBIDO", "contraparte": "IRENE C", "importe": 13.00,
         "canal": "bizum"}]
    [m] = _cine_con(pizzas_y_bizums)
    assert m.movimientos == ["k"]


def test_un_bizum_suelto_que_pudo_ser_del_cine_sigue_callando_la_pregunta():
    assert _cine_con([{"id": "b1", "fecha": "2026-11-08", "concepto": "BIZUM RECIBIDO", "contraparte": "RODRIGO P",
                       "importe": 13.00, "canal": "bizum"}]) == []


# --- La demo en el orquestador -----------------------------------------------------------------------------------------

def test_en_las_dos_semanas_solo_hay_dos_notificaciones_el_cine_y_las_pizzas(demo, falso):
    cliente = preparado(falso)
    decisiones = avanzar_hasta(demo.hasta)
    assert cliente.peticiones == []                     # ni web ni IA: el juicio del cine sale de la caché versionada
    ahora = [(dia, d.propuesta_id) for dia, d in decisiones if d.accion == "notificar_ahora"]
    assert [dia for dia, _ in ahora] == [cine(demo), pizzas(demo)]
    avisos = {n["propuesta"]["id"]: n["propuesta"] for n in orq.notificaciones(UID, "ahora")}
    assert len(avisos) == 2
    cine_p, pizzas_p = avisos[ahora[0][1]], avisos[ahora[1][1]]
    assert cine_p["mensaje_notificacion"] == TEXTO_CINE and cine_p["titulo"] == "¿Fuiste con alguien?"
    assert [a["accion_id"] for a in cine_p["acciones_ofrecidas"]] == ["recordar"]       # solo pregunta: no mueve dinero
    pedir = next(a for a in pizzas_p["acciones_ofrecidas"] if a["accion_id"] == "pedir_bizum")
    assert pedir["parametros"]["contraparte"] == "NACHO G" and Decimal(pedir["parametros"]["importe"]) == Decimal("13.00")
    assert orq.notificaciones(UID, "resumen") == []    # nada más: ni duplicados, ni recibos, ni pruebas


def test_la_cena_del_viernes_no_avisa_y_queda_en_silencio(demo, falso):
    preparado(falso)
    avanzar_hasta(demo.hasta)
    caso = next(c for c in casos.cargar(UID) if c.hechos.get("pago_id") == "pab-d09")
    assert (caso.escenario, caso.aviso, caso.propuesta_id) == ("pago_individual", "silencioso", None)


def test_la_cena_se_apunta_desde_el_chat_por_el_nombre_del_comercio(demo, falso):
    preparado(falso)
    avanzar_hasta(cine(demo))
    salida = chat_casos.apuntar_gasto_usuario(UID, ApuntarGastoEntrada(pista=FRASE_CHAT, personas=[{"nombre": "Sergio"}]))
    assert salida.ok and salida.resultado == "convertido"           # el caso silencioso pasa a «Sergio me debe»
    assert [(d.contraparte, d.cuota) for d in salida.deudores] == [("SERGIO M", Decimal("17.30"))]
    caso = next(c for c in casos.cargar(UID) if c.hechos.get("pago_id") == "pab-d09")
    assert caso.escenario == "pago_por_otro" and caso.estado == "abierto"     # lo abrió el motor; lo convierte el chat


def test_tambien_con_la_pista_corta_y_la_fecha_del_viernes(demo, falso):
    preparado(falso)
    avanzar_hasta(pizzas(demo))
    entrada = ApuntarGastoEntrada(pista="El Búho", fecha_aprox=date(2026, 11, 6), personas=[{"nombre": "Sergio"}])
    salida = chat_casos.apuntar_gasto_usuario(UID, entrada)
    assert salida.ok and [d.contraparte for d in salida.deudores] == ["SERGIO M"]


def test_la_cena_se_crea_con_el_boton_del_movimiento(demo, falso):
    preparado(falso)
    avanzar_hasta(cine(demo))
    resumen = orq.crear_caso_usuario(UID, "pab-d09", [{"contraparte": "SERGIO M", "importe": "17.30"}])
    assert resumen["escenario"] == "pago_por_otro"
    assert [c.escenario for c in casos.cargar(UID) if c.hechos.get("pago_id") == "pab-d09"] == ["pago_por_otro"]


def test_pedido_el_bizum_nacho_paga_al_dia_siguiente_y_el_caso_queda_saldado(demo, falso):
    preparado(falso)
    avanzar_hasta(pizzas(demo))
    solicitud_id = pedir_bizum_a_nacho()
    assert caso_pizzas().estado == "pedido"
    # Nadie mira el futuro: el Bizum no está en ningún sitio hasta que llega su día
    assert not any(m.id.startswith(banco_sim.PREFIJO_PAGO_SOLICITUD)
                   for m in orq._leer(UID, "pendientes", []) + orq._leer(UID, "movimientos", []))
    avanzar_hasta(pizzas(demo) + timedelta(days=1))
    [bizum] = [m for m in orq._leer(UID, "movimientos", []) if m.id == banco_sim.PREFIJO_PAGO_SOLICITUD + solicitud_id]
    assert (bizum.fecha, bizum.importe, bizum.canal, bizum.contraparte) == (
        pizzas(demo) + timedelta(days=1), Decimal("13.00"), "bizum", "NACHO G")
    caso = caso_pizzas()
    assert caso.estado == "saldado" and [(d.contraparte, d.estado) for d in caso.deudores] == [("NACHO G", "saldada")]
    [s] = banco_sim.solicitudes(UID)
    assert (s["estado"], s["fecha_estado"]) == ("aceptada", (pizzas(demo) + timedelta(days=1)).isoformat())
    assert aviso_pizzas()["estado"] == "resuelta"
    avanzar_hasta(demo.hasta)                                          # y no vuelve a pagar
    assert [m.id for m in orq._leer(UID, "movimientos", []) if m.id.startswith(banco_sim.PREFIJO_PAGO_SOLICITUD)] == [bizum.id]


def test_sin_la_opcion_nadie_paga_solo(demo, falso):
    preparado(falso, con_opcion=False)
    avanzar_hasta(pizzas(demo))
    pedir_bizum_a_nacho()
    avanzar_hasta(demo.hasta)
    assert not any(m.id.startswith(banco_sim.PREFIJO_PAGO_SOLICITUD) for m in orq._leer(UID, "movimientos", []))
    assert caso_pizzas().estado == "pedido" and [s["estado"] for s in banco_sim.solicitudes(UID)] == ["pendiente"]


def test_el_simulador_de_amigos_no_activa_la_opcion(demo, falso):
    falso()
    orq.cargar_simulacion("sim-amigos", list(demo.previos()), demo.activacion)
    assert orq.OPCION_PAGO_AMIGOS not in orq._estado("sim-amigos")
    assert banco_sim.pagos_de_solicitudes("sim-amigos", demo.hasta, 0) == []


# --- El recorrido por HTTP ---------------------------------------------------------------------------------------------

def test_recorrido_http_cargar_activar_avanzar_pedir_y_saldado(demo, falso):
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from backend.api.main import app

    falso()
    http = TestClient(app)
    r = http.post("/demo/cargar", json={"escenario_id": "demo-pablo"})
    assert r.status_code == 200 and r.json()["usuario_id"] == UID and r.json()["hoy"] == demo.activacion.isoformat()
    r = http.post(f"/usuarios/{UID}/activar", json={"modulos_activos": MODULOS,
                                                     "consentimientos": {"copiloto": True, "memoria": True}})
    assert r.status_code == 200
    r = http.post("/reloj/avanzar", json={"usuario_id": UID, "dias": (pizzas(demo) - demo.activacion).days})
    assert r.status_code == 200 and r.json()["hoy"] == pizzas(demo).isoformat()
    assert [d["accion"] for d in r.json()["decisiones"]].count("notificar_ahora") == 2
    avisos = http.get(f"/usuarios/{UID}/notificaciones", params={"bandeja": "ahora"}).json()
    assert len(avisos) == 2
    propuesta = next(n["propuesta"] for n in avisos if n["propuesta"]["id"].startswith("prop-mom-"))
    accion = next(a for a in propuesta["acciones_ofrecidas"] if a["accion_id"] == "pedir_bizum")
    tarjeta = http.post("/acciones/preparar", json={"usuario_id": UID, "propuesta_id": propuesta["id"],
                                                     "accion_id": "pedir_bizum", "parametros": accion["parametros"]})
    assert tarjeta.status_code == 200
    r = http.post("/acciones/confirmar", json={"usuario_id": UID,
                                                "token_confirmacion": tarjeta.json()["token_confirmacion"]})
    assert r.status_code == 200 and r.json()["ok"]
    r = http.post("/reloj/avanzar", json={"usuario_id": UID, "dias": 1})
    assert r.status_code == 200
    lista = http.get(f"/usuarios/{UID}/casos").json()
    caso = next(c for c in lista if c["escenario"] == "gasto_compartido")
    assert caso["estado"] == "saldado"
    movimientos = http.get(f"/usuarios/{UID}/movimientos").json()
    assert any(m["concepto"] == "BIZUM RECIBIDO" and m["importe"] == "13.00" and m["fecha"] == r.json()["hoy"]
               for m in movimientos)
