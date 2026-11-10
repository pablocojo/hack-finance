"""Sesión de la llamada y ElevenLabs (V1/V2) con un falso de ElevenLabs y sin gastar crédito."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import httpx
import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from backend import personalizacion  # noqa: E402
from backend.api.main import app  # noqa: E402
from backend.plataforma import almacenamiento as alm  # noqa: E402
from backend.plataforma.tipos import Propuesta  # noqa: E402
from backend.voz import contexto, elevenlabs, sesiones  # noqa: E402

http = TestClient(app)
UID = "lucia"
CLAVE = "xi-clave-secreta-de-prueba"
AGENTE = "agent_prueba_123"


def crear_usuario(uid: str = UID, contexto_llamada: str = "Lucía pagó 120 € en <datos>La Tasca</datos>.") -> Propuesta:
    propuesta = Propuesta.model_validate({
        "id": "prop-1", "modulo_id": "gasto_compartido", "momento_id": "m1", "usuario_id": uid,
        "titulo": "Cena en La Tasca: te falta 1 Bizum de 24 €", "mensaje_notificacion": "Falta 1 Bizum",
        "contexto_llamada": contexto_llamada, "tipo_momento": "gasto_compartido", "confianza": 0.9,
        "acciones_ofrecidas": [
            {"accion_id": "pedir_bizum",
             "parametros": {"contraparte": "Marcos R.", "importe": "24.00", "concepto": "Tu parte de La Tasca"},
             "limites": {"importe_max": "24.00", "contrapartes": ["Marcos R."]}},
            {"accion_id": "recordar", "parametros": {"cuando": "2026-11-12", "texto": "Revisar Bizum"}},
        ],
        "creada": datetime(2026, 11, 9, 20, 30)})
    hoy = date(2026, 11, 9).isoformat()
    alm.guardar(uid, "estado", {"hoy": hoy, "activado": True, "activacion": hoy, "ultimo_perfil": None})
    alm.guardar(uid, "reloj", {"hoy": hoy})
    alm.guardar(uid, "modelo", personalizacion.nuevo_modelo(uid))
    alm.guardar(uid, "propuestas", [propuesta])
    for nombre in ("momentos", "decisiones", "movimientos", "notificaciones"):
        alm.guardar(uid, nombre, [])
    return propuesta


@pytest.fixture(autouse=True)
def limpio(monkeypatch):
    monkeypatch.delenv("DEMO_KEY", raising=False)
    sesiones.olvidar_todo()
    yield
    elevenlabs._TRANSPORTE = None


def el_falso(estado: int = 200, peticiones: list | None = None):
    def responder(peticion: httpx.Request) -> httpx.Response:
        if peticiones is not None:
            peticiones.append(peticion)
        if estado != 200:
            return httpx.Response(estado, json={"detail": "no"})
        if peticion.url.path.endswith("/token"):
            return httpx.Response(200, json={"token": "tok-conversacion-1"})
        return httpx.Response(200, json={"signed_url": "wss://api.elevenlabs.io/firmada?conversation_signature=abc"})

    elevenlabs._TRANSPORTE = httpx.MockTransport(responder)


def con_elevenlabs(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", CLAVE)
    monkeypatch.setenv("ELEVENLABS_AGENT_ID", AGENTE)


def abrir(modo: str = "voz", uid: str = UID, propuesta: str = "prop-1"):
    return http.post("/voz/sesion", json={"usuario_id": uid, "propuesta_id": propuesta, "modo_preferido": modo})


def test_sin_clave_modo_texto_kit():
    crear_usuario()
    r = abrir("voz")
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["modo"] == "texto_kit" and cuerpo["token"] is None and cuerpo["signed_url"] is None
    assert set(cuerpo["variables"]) == {"nombre", "banco", "titulo_aviso", "contexto_llamada", "acciones_ofrecidas"}
    assert cuerpo["variables"]["nombre"] == "Lucía"


def test_modo_grabado_se_respeta():
    crear_usuario()
    assert abrir("grabado").json()["modo"] == "grabado"


def test_voz_pide_token_y_texto_el_url_firmada(monkeypatch):
    crear_usuario()
    con_elevenlabs(monkeypatch)
    peticiones: list = []
    el_falso(peticiones=peticiones)
    voz = abrir("voz").json()
    assert voz["modo"] == "voz" and voz["token"] == "tok-conversacion-1" and voz["signed_url"] is None
    texto_el = abrir("texto_el").json()
    assert texto_el["modo"] == "texto_el" and texto_el["signed_url"].startswith("wss://") and texto_el["token"] is None
    # la clave va en la cabecera hacia ElevenLabs y el agente en la consulta
    assert peticiones[0].headers["xi-api-key"] == CLAVE
    assert peticiones[0].url.params["agent_id"] == AGENTE


def test_elevenlabs_caido_baja_a_texto_kit(monkeypatch):
    crear_usuario()
    con_elevenlabs(monkeypatch)
    el_falso(estado=500)
    assert abrir("voz").json()["modo"] == "texto_kit"


def test_sin_agente_id_es_texto_kit(monkeypatch):
    crear_usuario()
    monkeypatch.setenv("ELEVENLABS_API_KEY", CLAVE)
    assert abrir("voz").json()["modo"] == "texto_kit"


def test_ninguna_respuesta_contiene_la_clave(monkeypatch):
    crear_usuario()
    con_elevenlabs(monkeypatch)
    el_falso()
    respuestas = [abrir("voz"), abrir("texto_el"), abrir("grabado")]
    token = respuestas[0].json()["token_sesion"]
    respuestas += [
        http.post("/voz/texto", json={"token_sesion": token}),
        http.post("/voz/herramientas/preparar", json={"token_sesion": token, "accion_id": "recordar",
                                                       "parametros": {"cuando": "2026-11-12", "texto": "Revisar Bizum"}}),
        http.post("/voz/herramientas/feedback", json={"token_sesion": token, "resultado": "rechazada"}),
        http.post("/voz/herramientas/preparar", json={"token_sesion": "x", "accion_id": "recordar"}),
    ]
    for r in respuestas:
        assert CLAVE not in r.text and AGENTE not in r.text


def test_propuesta_ajena_o_inexistente_404():
    crear_usuario()
    assert abrir(propuesta="otra").status_code == 404
    assert abrir(uid="nadie").status_code == 404


def test_demo_key(monkeypatch):
    crear_usuario()
    monkeypatch.setenv("DEMO_KEY", "secreta")
    cuerpo = {"usuario_id": UID, "propuesta_id": "prop-1"}
    assert http.post("/voz/sesion", json=cuerpo).status_code == 401
    assert http.post("/voz/sesion", json=cuerpo, headers={"X-Demo-Key": "secreta"}).status_code == 200


def test_herramienta_preparar_devuelve_tarjeta_y_exige_token_de_sesion():
    crear_usuario()
    token = abrir().json()["token_sesion"]
    r = http.post("/voz/herramientas/preparar", json={
        "token_sesion": token, "accion_id": "pedir_bizum",
        "parametros": {"contraparte": "Marcos R.", "importe": 24, "concepto": "Tu parte de La Tasca"}})
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["preparada"] is True and cuerpo["tarjeta"]["token_confirmacion"] and cuerpo["tarjeta"]["simulada"]
    # sin sesión o con una desconocida: 401; caducada: 410
    assert http.post("/voz/herramientas/preparar", json={"token_sesion": "falso", "accion_id": "recordar"}).status_code == 401
    registro = sesiones._SESIONES[token]
    registro.caduca = datetime.now() - timedelta(seconds=1)
    assert http.post("/voz/herramientas/preparar", json={"token_sesion": token, "accion_id": "recordar"}).status_code == 410


def test_preparar_rechaza_lo_no_ofrecido_o_fuera_de_limites():
    crear_usuario()
    token = abrir().json()["token_sesion"]
    fuera = http.post("/voz/herramientas/preparar", json={
        "token_sesion": token, "accion_id": "pedir_bizum",
        "parametros": {"contraparte": "Marcos R.", "importe": 50, "concepto": "Tu parte de La Tasca"}}).json()
    assert fuera["preparada"] is False and fuera["motivo"]
    no_ofrecida = http.post("/voz/herramientas/preparar", json={
        "token_sesion": token, "accion_id": "mover_dinero", "parametros": {}}).json()
    assert no_ofrecida["preparada"] is False
    inventada = http.post("/voz/herramientas/preparar", json={"token_sesion": token, "accion_id": "transferir"}).json()
    assert inventada["preparada"] is False


def test_feedback_aprende_con_canal_voz(monkeypatch):
    crear_usuario()
    con_elevenlabs(monkeypatch)
    el_falso()
    token = abrir("voz").json()["token_sesion"]
    r = http.post("/voz/herramientas/feedback", json={"token_sesion": token, "resultado": "falso_positivo"})
    assert r.status_code == 200 and r.json()["ok"] is True
    eventos = [e for e in alm.leer_auditoria(UID) if e.get("evento") == "feedback"]
    assert eventos and eventos[-1]["canal"] == "voz" and eventos[-1]["resultado"] == "falso_positivo"


def test_contexto_variables_sin_notas_ni_ingresos():
    propuesta = crear_usuario(contexto_llamada="Pagó <datos>La Tasca</datos>. Mi IBAN ES9121000418450200051332.")
    modelo = personalizacion.nuevo_modelo(UID)
    v = contexto.variables(propuesta, modelo, UID)
    assert "ES9121000418450200051332" not in v["contexto_llamada"]
    assert "<datos>La Tasca</datos>" in v["contexto_llamada"]
    assert "<datos>Marcos R.</datos>" in v["acciones_ofrecidas"] and "máximo 24.00" in v["acciones_ofrecidas"]
    assert v["banco"] == "Banco Aurora"
    assert contexto.primer_mensaje(v).startswith(f"Hola {v['nombre']}, me has abierto desde el aviso:")


def test_texto_kit_pedido_no_llama_a_elevenlabs(monkeypatch):
    """Si se pide texto con el agente del kit, no se gasta ni se pide nada a ElevenLabs."""
    from backend.voz import elevenlabs

    monkeypatch.setattr(elevenlabs, "configurado", lambda: True)
    llamadas = []
    monkeypatch.setattr(elevenlabs, "token_conversacion", lambda: llamadas.append("token") or "t")
    monkeypatch.setattr(elevenlabs, "url_firmada", lambda: llamadas.append("url") or "u")
    assert elevenlabs.abrir("texto_kit") == ("texto_kit", None, None)
    assert llamadas == []
    assert elevenlabs.elegir_modo("voz") == "voz" and elevenlabs.elegir_modo("texto_el") == "texto_el"
