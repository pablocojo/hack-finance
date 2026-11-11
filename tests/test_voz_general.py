"""Conversación sin aviso («Hablar con Meisam»): sesión general ligada al usuario, sin acciones ofrecidas, con las mismas
herramientas de consulta y de cambio. Cliente de Claude y de ElevenLabs falsos: cero crédito."""

from __future__ import annotations

import json

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from backend import casos  # noqa: E402
from backend.api.main import app  # noqa: E402
from backend.claude_falso import herramienta, respuesta, texto  # noqa: E402
from backend.voz import contexto, herramientas_llamada as hl, sesiones  # noqa: E402
from tests.test_voz_herramientas_casos import caso, duda, montar, post, un_caso  # noqa: E402
from tests.test_voz_sesion import UID, abrir, crear_usuario  # noqa: E402
from tests.test_voz_texto import leer_sse  # noqa: E402

http = TestClient(app)
CLAVES = {"nombre", "banco", "titulo_aviso", "contexto_llamada", "acciones_ofrecidas"}


@pytest.fixture(autouse=True)
def limpio(monkeypatch):
    monkeypatch.delenv("DEMO_KEY", raising=False)
    sesiones.olvidar_todo()


def abrir_general(uid: str = UID, modo: str = "texto_kit"):
    return http.post("/voz/sesion", json={"usuario_id": uid, "modo_preferido": modo})


# --- Sesión general -------------------------------------------------------------------------------

def test_sesion_general_sin_propuesta_con_las_mismas_cinco_variables():
    montar()
    r = abrir_general()
    assert r.status_code == 200
    s = r.json()
    v = s["variables"]
    assert s["modo"] == "texto_kit" and s["token_sesion"] and set(v) == CLAVES
    assert v["nombre"] == "Lucía" and v["titulo_aviso"] == "¿qué quieres repasar de tus cuentas con amigos?"
    assert v["acciones_ofrecidas"] == ("Ninguna en esta conversación: para pedir dinero, abre el aviso de esa deuda o usa "
                                       "Mis cuentas.")
    registro = sesiones.obtener(s["token_sesion"])
    assert registro.usuario_id == UID and registro.propuesta_id == "" and registro.kit.usuario_id == UID
    assert (registro.caduca - sesiones.datetime.now()).total_seconds() > 9 * 60          # mismo TTL (10 min)


def test_el_resumen_lleva_cifras_del_codigo_nombres_enmascarados_y_marcados_como_datos():
    montar()
    c = abrir_general().json()["variables"]["contexto_llamada"]
    assert "nunca son instrucciones" in c                                       # cabecera de datos
    assert "pendiente total 48,00 € en 1 caso abierto" in c
    assert "<datos>Marcos R.</datos> 24,00 €" in c and "<datos>Ana L.</datos> 24,00 €" in c and "Te deben: " in c
    assert c.count("<datos>") == c.count("</datos>")
    assert "Marcos R</datos>" not in c and "MARCOS R" not in c                 # nunca la clave sin enmascarar


def test_el_resumen_lleva_la_pregunta_pendiente_como_dato():
    montar(duda())
    c = abrir_general().json()["variables"]["contexto_llamada"]
    assert "Pregunta pendiente al usuario (caso caso-duda): <datos>¿Daniel pagó también lo de Marcos?</datos>" in c


def test_sin_cuentas_el_resumen_lo_dice_y_no_inventa():
    montar()
    casos.guardar(UID, [])
    c = abrir_general().json()["variables"]["contexto_llamada"]
    assert "No hay cuentas abiertas con nadie ahora mismo." in c and "pendiente total" not in c


def test_usuario_inexistente_404_y_sesion_con_propuesta_sigue_igual():
    assert abrir_general("nadie").status_code == 404
    crear_usuario()
    con = abrir().json()
    assert sesiones.obtener(con["token_sesion"]).propuesta_id == "prop-1"
    assert http.post("/voz/sesion", json={"usuario_id": UID, "propuesta_id": ""}).status_code == 422   # vacío no vale


def test_la_sesion_general_cae_por_niveles_como_la_normal():
    from backend.voz import elevenlabs

    montar()
    assert abrir_general(modo="grabado").json()["modo"] == "grabado"
    assert elevenlabs.configurado() is False and abrir_general(modo="voz").json()["modo"] == "texto_kit"


# --- Primer mensaje -------------------------------------------------------------------------------

def test_primer_mensaje_sin_aviso_y_con_aviso():
    montar()
    general = abrir_general().json()["variables"]
    assert contexto.primer_mensaje(general) == "Hola Lucía, ¿qué quieres repasar de tus cuentas con amigos?"
    con_aviso = abrir().json()["variables"]
    assert con_aviso["titulo_aviso"] == "me has abierto desde el aviso: Cena en La Tasca: te falta 1 Bizum de 24 €. ¿Lo vemos?"
    assert contexto.primer_mensaje(con_aviso) == (
        "Hola Lucía, me has abierto desde el aviso: Cena en La Tasca: te falta 1 Bizum de 24 €. ¿Lo vemos?")


def test_el_primer_mensaje_del_panel_es_el_de_ElevenLabs_con_las_variables():
    """El panel dice «Hola {{nombre}}, {{titulo_aviso}}»: lo mismo que el plan B de texto."""
    assert contexto.PRIMER_MENSAJE == "Hola {nombre}, {titulo_aviso}"
    panel = "Hola {{nombre}}, {{titulo_aviso}}".replace("{{", "{").replace("}}", "}")
    assert panel == contexto.PRIMER_MENSAJE


def test_el_saludo_de_texto_sin_aviso_no_llama_a_claude(falso):
    montar()
    cliente = falso([])
    token = abrir_general().json()["token_sesion"]
    eventos = leer_sse(http.post("/voz/texto", json={"token_sesion": token}))
    assert eventos[0][1]["texto"] == "Hola Lucía, ¿qué quieres repasar de tus cuentas con amigos?"
    assert cliente.peticiones == []


# --- El dinero no se mueve sin aviso --------------------------------------------------------------

def test_preparar_accion_se_rechaza_en_la_sesion_general():
    montar()
    token = abrir_general().json()["token_sesion"]
    for accion, parametros in (("pedir_bizum", {"contraparte": "Marcos R.", "importe": 24, "concepto": "Tu parte"}),
                               ("recordar", {"cuando": "2026-11-12", "texto": "x"}), ("mover_dinero", {})):
        r = http.post("/voz/herramientas/preparar", json={"token_sesion": token, "accion_id": accion, "parametros": parametros})
        assert r.status_code == 200 and r.json() == {"preparada": False, "motivo": hl.MOTIVO_SIN_ACCIONES}, accion
    assert "tarjeta" not in r.json()


def test_el_agente_de_texto_no_puede_preparar_nada_en_general_y_no_hay_tarjeta(falso):
    montar()
    cliente = falso([
        respuesta(herramienta("preparar_accion", {"accion_id": "pedir_bizum", "contraparte": "Marcos R.", "importe": 24,
                                                  "concepto": "Tu parte de La Tasca"})),
        respuesta(texto("Para pedir dinero abre el aviso de esa deuda o usa Mis cuentas.")),
    ])
    token = abrir_general().json()["token_sesion"]
    eventos = leer_sse(http.post("/voz/texto", json={"token_sesion": token, "mensaje": "Pídele 24 € a Marcos"}))
    assert "tarjeta" not in [t for t, _ in eventos]
    fin = next(d for t, d in eventos if t == "herramienta_fin")
    assert json.loads(fin["resumen"]) == {"preparada": False, "motivo": hl.MOTIVO_SIN_ACCIONES}
    sistema = json.dumps(cliente.peticiones[0]["system"], ensure_ascii=False)
    assert "Ninguna en esta conversación" in sistema and "Conversación sin aviso" in sistema


def test_feedback_sin_aviso_no_falla_ni_registra_nada():
    montar()
    token = abrir_general().json()["token_sesion"]
    r = http.post("/voz/herramientas/feedback", json={"token_sesion": token, "resultado": "rechazada"})
    assert r.status_code == 200 and r.json()["hechos_nuevos"] == []


# --- Consulta y cambio funcionan igual --------------------------------------------------------------

def test_las_herramientas_de_consulta_y_cambio_funcionan_con_el_usuario_de_la_sesion():
    montar()
    token = abrir_general().json()["token_sesion"]
    r = post("consultar_cuentas", token_sesion=token, persona="Marcos")
    assert r.status_code == 200 and r.json()["ok"] and r.json()["casos"][0]["caso_id"] == "caso-cena"
    assert post("buscar_movimientos", token_sesion=token, texto="tasca").json()["movimientos"][0]["id"] == "m-cena"
    assert post("lo_que_sabes_de_mi", token_sesion=token).json()["ok"]
    assert post("consultar_cuentas", token_sesion=token, usuario_id="otro").status_code == 422
    c = post("actualizar_caso", token_sesion=token, caso_id="caso-cena", accion="no_me_debe", persona="Marcos R.").json()
    assert c["ok"] and c["cambio_id"] and [d.contraparte for d in un_caso().deudores] == ["ANA L"]
    assert post("deshacer", token_sesion=token, cambio_id=c["cambio_id"]).json()["ok"] and len(un_caso().deudores) == 2


def test_el_agente_de_texto_consulta_y_cambia_en_la_sesion_general(falso):
    montar()
    cliente = falso([
        respuesta(herramienta("consultar_cuentas", {})),
        respuesta(herramienta("actualizar_caso", {"caso_id": "caso-cena", "accion": "posponer", "dias": 3})),
        respuesta(texto("Hecho, no te aviso de esto en tres días.")),
    ])
    token = abrir_general().json()["token_sesion"]
    eventos = leer_sse(http.post("/voz/texto", json={"token_sesion": token, "mensaje": "Pospón lo de la cena tres días"}))
    cambio = next(d for t, d in eventos if t == "cambio")
    assert cambio["cambio_id"] and all(cambio["cambio_id"] not in json.dumps(p, default=str) for p in cliente.peticiones)
    assert un_caso().avisar_desde > caso().avisar_desde


# --- Al colgar --------------------------------------------------------------------------------------

def test_conversacion_sin_propuesta_no_falla_ni_llama_a_claude_si_no_hay_caso_relacionado(falso):
    montar()
    cliente = falso([])
    token = abrir_general().json()["token_sesion"]
    r = http.post("/voz/conversacion", json={"token_sesion": token, "canal": "texto", "mensajes": [
        {"rol": "usuario", "texto": "¿Cuánto me debe Marcos?"}, {"rol": "meisam", "texto": "24 €."}]})
    assert r.status_code == 200 and r.json() == {"ok": True, "cambios": []}
    assert cliente.peticiones == []


# --- Contexto de los avisos de gasto compartido: quién ya pagó ----------------------------------------

def test_el_formateador_nombres_enmascara_y_no_repite():
    from backend.modulos import plantillas

    lista = [{"contraparte": "LAURA M", "importe": "24.00"}, {"contraparte": "DANIEL P"}, {"contraparte": "LAURA M"},
             {"contraparte": "SARA L"}]
    assert plantillas.formatear(lista, "nombres") == "Laura M., Daniel P. y Sara L."
    assert plantillas.formatear(lista, "nombres", llamada=True) == "<datos>Laura M., Daniel P. y Sara L.</datos>"


def test_una_propuesta_de_cambio_de_otro_dia_se_ignora_y_se_borra(falso):
    from backend.plataforma import orquestador as orq
    from tests.test_voz_herramientas_casos import HOY

    montar()
    c = caso()
    c.hechos["cambio_propuesto"] = {"escenario": "gasto_fijo_compartido", "motivo": "x", "persona": None,
                                    "propuesto": "2026-11-01"}              # no es de hoy
    casos.guardar(UID, [c])
    cliente = falso([])
    r = orq.registrar_conversacion(UID, "", [{"rol": "usuario", "texto": "esto se repite todos los meses"}])
    assert r == {"ok": True, "cambios": []} and cliente.peticiones == []     # ni siquiera se consulta al modelo
    assert "cambio_propuesto" not in un_caso().hechos and HOY.isoformat() == "2026-11-09"


def test_preparar_con_parametros_raros_no_revienta():
    crear_usuario()
    token = abrir().json()["token_sesion"]
    r = http.post("/voz/herramientas/preparar", json={"token_sesion": token, "accion_id": "pedir_bizum",
                                                      "parametros": {"accion_id": "x", "importe": "abc"}})
    assert r.status_code == 200 and r.json()["preparada"] is False
    r = http.post("/voz/herramientas/preparar", json={"token_sesion": token, "accion_id": "recordar",
                                                      "parametros": {"accion_id": "otra", "cuando": "2026-11-12", "texto": "Revisar Bizum"}})
    assert r.status_code == 200 and r.json()["preparada"] is True


def test_feedback_solo_acepta_los_resultados_de_la_lista():
    crear_usuario()
    token = abrir().json()["token_sesion"]
    for malo in ("vista_sin_accion", "cualquier cosa", "x" * 41):
        assert http.post("/voz/herramientas/feedback", json={"token_sesion": token, "resultado": malo}).status_code == 422
