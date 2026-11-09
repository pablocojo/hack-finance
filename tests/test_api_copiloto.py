"""Tests HTTP de las rutas del Copiloto. Con stubs del orquestador salvo el de principio a fin (xfail)."""

from __future__ import annotations

import json

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from backend.api.main import app  # noqa: E402
from tests.test_orquestador import Falsos, UID  # noqa: E402

http = TestClient(app)


@pytest.fixture
def falsos(monkeypatch) -> Falsos:
    monkeypatch.delenv("DEMO_KEY", raising=False)
    return Falsos().montar(monkeypatch)


@pytest.fixture
def activo(falsos):
    assert http.post("/demo/cargar", json={"escenario_id": "demo-test"}).status_code == 200
    r = http.post(f"/usuarios/{UID}/activar", json={"modulos_activos": ["cena_compartida"],
                                                    "consentimientos": {"copiloto": True}})
    assert r.status_code == 200
    return falsos


def _avanzar(dias: int = 1):
    return http.post("/reloj/avanzar", json={"usuario_id": UID, "dias": dias})


def test_demo_cargar_activar_y_estado(falsos):
    r = http.post("/demo/cargar", json={"escenario_id": "demo-test"})
    assert r.json() == {"usuario_id": UID, "hoy": "2026-11-06", "activacion": "2026-11-06"}
    r = http.post(f"/usuarios/{UID}/activar", json={"modulos_activos": ["cena_compartida"],
                                                    "consentimientos": {"avisos": True, "memoria": True}})
    assert r.json()["modulos_activos"] == ["cena_compartida"]
    assert http.get(f"/usuarios/{UID}/estado").json()["saldo"] == "500.00"  # dinero como cadena
    assert http.get("/usuarios/nadie/estado").status_code == 404


def test_demo_key_solo_si_esta_configurada(falsos, monkeypatch):
    cuerpo = {"escenario_id": "demo-test"}
    assert http.post("/demo/cargar", json=cuerpo).status_code == 200  # sin clave: local
    monkeypatch.setenv("DEMO_KEY", "secreta")
    assert http.post("/demo/cargar", json=cuerpo).status_code == 401
    assert http.post("/demo/cargar", json=cuerpo, headers={"X-Demo-Key": "mala"}).status_code == 401
    assert http.post("/demo/cargar", json=cuerpo, headers={"X-Demo-Key": "secreta"}).status_code == 200


def test_avanzar_notificaciones_propuesta_y_feedback(activo):
    r = _avanzar(3)  # 7, 8 y 9 de noviembre
    assert r.status_code == 200 and r.json()["hoy"] == "2026-11-09"
    assert [d["accion"] for d in r.json()["decisiones"]] == ["notificar_ahora"]
    bandeja = http.get(f"/usuarios/{UID}/notificaciones", params={"bandeja": "ahora"}).json()
    assert len(bandeja) == 1 and bandeja[0]["estado"] == "nueva"
    pid = bandeja[0]["propuesta"]["id"]
    detalle = http.get(f"/usuarios/{UID}/propuestas/{pid}").json()
    assert detalle["momento"]["impacto_eur"] == "24.00" and detalle["movimientos"][0]["importe"] == "-120.00"
    assert http.get(f"/usuarios/{UID}/propuestas/no-existe").status_code == 404
    assert http.get(f"/usuarios/{UID}/notificaciones", params={"bandeja": "otra"}).status_code == 400
    r = http.post("/feedback", json={"usuario_id": UID, "propuesta_id": pid, "resultado": "no_avisar_tipo", "canal": "voz"})
    assert r.json()["ok"] and r.json()["hechos_nuevos"][0]["id"] == "h-no_avisar_tipo"
    assert http.post("/feedback", json={"usuario_id": UID, "propuesta_id": pid, "resultado": "inventado"}).status_code == 422
    assert _avanzar(0).status_code == 422


def test_avanzar_sin_activar_da_400(falsos):
    http.post("/demo/cargar", json={"escenario_id": "demo-test"})
    r = _avanzar()
    assert r.status_code == 400 and "activado" in r.json()["detail"]


def test_preparar_y_confirmar(activo):
    _avanzar(3)
    pid = http.get(f"/usuarios/{UID}/notificaciones").json()[0]["propuesta"]["id"]
    cuerpo = {"usuario_id": UID, "propuesta_id": pid, "accion_id": "cancelar_suscripcion", "parametros": {}}
    assert http.post("/acciones/preparar", json=cuerpo).status_code == 403  # no ofrecida
    cuerpo["accion_id"] = "pedir_bizum"
    tarjeta = http.post("/acciones/preparar", json=cuerpo)
    assert tarjeta.status_code == 200 and tarjeta.json()["simulada"] is True
    token = tarjeta.json()["token_confirmacion"]
    r = http.post("/acciones/confirmar", json={"usuario_id": UID, "token_confirmacion": token})
    assert r.status_code == 200 and r.json()["ok"]
    assert http.post("/acciones/confirmar", json={"usuario_id": UID, "token_confirmacion": token}).status_code == 409
    assert http.get(f"/usuarios/{UID}/notificaciones").json()[0]["estado"] == "resuelta"


def test_reproducir_sse(activo):
    r = http.get("/reloj/reproducir", params={"usuario_id": UID, "dias": 3, "ms_por_dia": 0})
    assert r.headers["content-type"].startswith("text/event-stream")
    eventos = [linea.removeprefix("event: ") for linea in r.text.splitlines() if linea.startswith("event: ")]
    assert eventos == ["dia", "dia", "dia", "momento", "propuesta", "decision", "fin"]
    ultimo = [json.loads(linea.removeprefix("data: ")) for linea in r.text.splitlines() if linea.startswith("data: ")][-1]
    assert ultimo["hoy"] == "2026-11-09"
    r = http.get("/reloj/reproducir", params={"usuario_id": "nadie", "dias": 1})
    assert r.text.startswith("event: error")


def test_rutas_futuras_responden_501():
    for metodo, ruta in [("get", "/usuarios/u/perfil"), ("patch", "/usuarios/u/perfil"), ("delete", "/usuarios/u/perfil"),
                         ("delete", "/usuarios/u/perfil/umbral_relevante_eur"), ("get", "/usuarios/u/aprendido"),
                         ("patch", "/usuarios/u/aprendido/h1"), ("delete", "/usuarios/u/aprendido/h1"),
                         ("delete", "/usuarios/u/aprendido"), ("post", "/usuarios/u/pruebas"), ("get", "/usuarios/u/amigos"),
                         ("post", "/acciones/deshacer"), ("post", "/voz/sesion"), ("post", "/voz/texto"),
                         ("post", "/voz/herramientas/preparar"), ("post", "/voz/herramientas/feedback"),
                         ("post", "/voz/herramientas/consultar"), ("get", "/banco/modulos"),
                         ("post", "/banco/modulos/borrador"), ("post", "/banco/modulos/x/aprobar")]:
        assert getattr(http, metodo)(ruta).status_code == 501, (metodo, ruta)


def test_cors_permite_patch_y_delete():
    r = http.options("/usuarios/u/perfil", headers={"Origin": "http://localhost:3000",
                                                    "Access-Control-Request-Method": "PATCH"})
    assert r.status_code == 200 and "PATCH" in r.headers["access-control-allow-methods"]
    assert "DELETE" in r.headers["access-control-allow-methods"]


def test_cena_lucia_de_principio_a_fin_por_http(monkeypatch):
    """Sin stubs: motor, módulos, personalización y acciones reales sobre `cena-lucia`."""
    assert http.post("/demo/cargar", json={"escenario_id": "cena-lucia"}).status_code == 200
    usuario = http.post("/demo/cargar", json={"escenario_id": "cena-lucia"}).json()["usuario_id"]
    r = http.post(f"/usuarios/{usuario}/activar", json={"modulos_activos": ["cena_compartida"],
                                                        "consentimientos": {"avisos": True, "memoria": True}})
    assert r.status_code == 200
    avisos, dia_aviso = [], None
    for _ in range(60):  # la activación es el 1/10 y la cena, el 6/11
        http.post("/reloj/avanzar", json={"usuario_id": usuario, "dias": 1})
        estado = http.get(f"/usuarios/{usuario}/estado").json()
        avisos = http.get(f"/usuarios/{usuario}/notificaciones", params={"bandeja": "ahora"}).json()
        if avisos or estado["hoy"] >= "2026-11-12":
            dia_aviso = estado["hoy"]
            break
    assert avisos, "la cena de Lucía debe producir una notificación"
    assert dia_aviso == "2026-11-09", "el aviso de la cena sale el lunes 9/11"
    propuesta = avisos[0]["propuesta"]
    assert propuesta["tipo_momento"] == "gasto_compartido"
    assert propuesta["contraparte"] == "MARCOS R" and propuesta["valor_estimado_eur"] == "24.00"
    oferta = next(a for a in propuesta["acciones_ofrecidas"] if a["accion_id"] == "pedir_bizum")
    tarjeta = http.post("/acciones/preparar", json={"usuario_id": usuario, "propuesta_id": propuesta["id"],
                                                    "accion_id": "pedir_bizum", "parametros": oferta["parametros"]})
    assert tarjeta.status_code == 200
    token = tarjeta.json()["token_confirmacion"]
    resultado = http.post("/acciones/confirmar", json={"usuario_id": usuario, "token_confirmacion": token})
    assert resultado.status_code == 200 and resultado.json()["ok"] and resultado.json()["simulada"]
    otro = http.post("/acciones/confirmar", json={"usuario_id": "otro", "token_confirmacion": token})
    assert otro.status_code in (403, 404, 409)
    repetido = http.post("/acciones/confirmar", json={"usuario_id": usuario, "token_confirmacion": token})
    assert repetido.status_code in (403, 404, 409, 410), "el token es de un solo uso"


def test_demo_key_en_todas_las_rutas_que_cambian_estado(activo, monkeypatch):
    peticiones = [("post", f"/usuarios/{UID}/activar", {"modulos_activos": []}),
                  ("post", "/reloj/avanzar", {"usuario_id": UID, "dias": 1}),
                  ("get", f"/reloj/reproducir?usuario_id={UID}&dias=1&ms_por_dia=0", None),
                  ("post", "/feedback", {"usuario_id": UID, "propuesta_id": "x", "resultado": "resuelta"}),
                  ("post", "/acciones/preparar", {"usuario_id": UID, "propuesta_id": "x", "accion_id": "recordar"}),
                  ("post", "/acciones/confirmar", {"usuario_id": UID, "token_confirmacion": "t"}),
                  ("post", "/acciones/deshacer", {}),
                  ("post", "/voz/sesion", {}), ("get", "/banco/modulos", None)]
    monkeypatch.setenv("DEMO_KEY", "secreta")

    def llamar(metodo, ruta, cuerpo, cabeceras):
        extra = {"json": cuerpo} if cuerpo is not None else {}
        return getattr(http, metodo)(ruta, headers=cabeceras, **extra)

    for metodo, ruta, cuerpo in peticiones:
        assert llamar(metodo, ruta, cuerpo, {}).status_code == 401, ruta
        assert llamar(metodo, ruta, cuerpo, {"X-Demo-Key": "mala"}).status_code == 401, ruta
        assert llamar(metodo, ruta, cuerpo, {"X-Demo-Key": "secreta"}).status_code != 401, ruta
    monkeypatch.delenv("DEMO_KEY")
    assert http.post("/reloj/avanzar", json={"usuario_id": UID, "dias": 1}).status_code == 200


def test_consentimiento_sin_marcar_por_defecto(falsos):
    """RGPD: si el cliente no marca nada, no hay consentimiento; `avisos` es alias de `copiloto`."""
    assert http.post("/demo/cargar", json={"escenario_id": "demo-test"}).status_code == 200
    r = http.post(f"/usuarios/{UID}/activar", json={"modulos_activos": ["cena_compartida"]})
    assert r.status_code == 200 and r.json()["consentimientos"] == {}
    r = http.post(f"/usuarios/{UID}/activar", json={"modulos_activos": ["cena_compartida"],
                                                    "consentimientos": {"avisos": True}})
    assert list(r.json()["consentimientos"]) == ["copiloto"]
