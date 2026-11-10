"""Tests HTTP de las rutas del Copiloto. Con stubs del orquestador salvo el de principio a fin (xfail)."""

from __future__ import annotations

import json
from decimal import Decimal
from urllib.parse import quote

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from backend.api.main import app  # noqa: E402
from backend.plataforma import almacenamiento as alm  # noqa: E402
from backend.plataforma import orquestador as orq  # noqa: E402
from backend.plataforma.tipos import ModeloUsuario  # noqa: E402
from tests.test_orquestador import Falsos, UID  # noqa: E402

http = TestClient(app)


@pytest.fixture
def falsos(monkeypatch) -> Falsos:
    monkeypatch.delenv("DEMO_KEY", raising=False)
    return Falsos().montar(monkeypatch)


@pytest.fixture
def activo(falsos):
    assert http.post("/demo/cargar", json={"escenario_id": "demo-test"}).status_code == 200
    r = http.post(f"/usuarios/{UID}/activar", json={"modulos_activos": ["gasto_compartido"],
                                                    "consentimientos": {"copiloto": True}})
    assert r.status_code == 200
    return falsos


def _avanzar(dias: int = 1):
    return http.post("/reloj/avanzar", json={"usuario_id": UID, "dias": dias})


def test_demo_cargar_activar_y_estado(falsos):
    r = http.post("/demo/cargar", json={"escenario_id": "demo-test"})
    assert r.json() == {"usuario_id": UID, "hoy": "2026-11-06", "activacion": "2026-11-06"}
    r = http.post(f"/usuarios/{UID}/activar", json={"modulos_activos": ["gasto_compartido"],
                                                    "consentimientos": {"avisos": True, "memoria": True}})
    assert r.json()["modulos_activos"] == ["gasto_compartido"]
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
    for metodo, ruta in [("post", "/usuarios/u/pruebas"),
                         ("post", "/acciones/deshacer"),
                         ("post", "/voz/herramientas/consultar"), ("get", "/banco/modulos"),
                         ("post", "/banco/modulos/borrador"), ("post", "/banco/modulos/x/aprobar")]:
        assert getattr(http, metodo)(ruta).status_code == 501, (metodo, ruta)


def test_rutas_de_lo_aprendido_ya_no_son_501(falsos):
    """U2: sin usuario, 404; con usuario, existen y responden JSON."""
    for metodo, ruta in [("get", "/usuarios/u/perfil"), ("delete", "/usuarios/u/perfil"),
                         ("delete", "/usuarios/u/perfil/umbral_relevante_eur"), ("get", "/usuarios/u/aprendido"),
                         ("delete", "/usuarios/u/aprendido/h1"), ("delete", "/usuarios/u/aprendido")]:
        assert getattr(http, metodo)(ruta).status_code == 404, (metodo, ruta)
    assert http.patch("/usuarios/u/perfil", json={"campo": "dia_cobro_nomina", "valor": 5}).status_code == 404
    assert http.patch("/usuarios/u/aprendido/h1", json={"activo": False}).status_code == 404


def test_cors_permite_patch_y_delete():
    r = http.options("/usuarios/u/perfil", headers={"Origin": "http://localhost:3000",
                                                    "Access-Control-Request-Method": "PATCH"})
    assert r.status_code == 200 and "PATCH" in r.headers["access-control-allow-methods"]
    assert "DELETE" in r.headers["access-control-allow-methods"]


def test_cena_lucia_de_principio_a_fin_por_http(monkeypatch):
    """Sin stubs: motor, módulos, personalización y acciones reales sobre `cena-lucia`."""
    assert http.post("/demo/cargar", json={"escenario_id": "cena-lucia"}).status_code == 200
    usuario = http.post("/demo/cargar", json={"escenario_id": "cena-lucia"}).json()["usuario_id"]
    r = http.post(f"/usuarios/{usuario}/activar", json={"modulos_activos": ["gasto_compartido"],
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
                  ("patch", f"/usuarios/{UID}/perfil", {"campo": "dia_cobro_nomina", "valor": 5}),
                  ("delete", f"/usuarios/{UID}/perfil/umbral_relevante_eur", None),
                  ("delete", f"/usuarios/{UID}/perfil", None),
                  ("patch", f"/usuarios/{UID}/aprendido/h1", {"activo": False}),
                  ("delete", f"/usuarios/{UID}/aprendido/h1", None),
                  ("delete", f"/usuarios/{UID}/aprendido", None),
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
    r = http.post(f"/usuarios/{UID}/activar", json={"modulos_activos": ["gasto_compartido"]})
    assert r.status_code == 200 and r.json()["consentimientos"] == {}
    r = http.post(f"/usuarios/{UID}/activar", json={"modulos_activos": ["gasto_compartido"],
                                                    "consentimientos": {"avisos": True}})
    assert list(r.json()["consentimientos"]) == ["copiloto"]


# --- Lo que he aprendido de ti (U2) ----------------------------------------------------------------

def _perfil() -> str:
    return f"/usuarios/{UID}/perfil"


def _aprendido(*resto: str) -> str:
    return "/".join([f"/usuarios/{UID}/aprendido", *[quote(r, safe="") for r in resto]])


def test_perfil_ver_editar_y_borrar_un_campo(activo):
    r = http.get(_perfil()).json()
    assert r["usar_perfil"] is True and r["perfil"]["umbral_relevante_eur"] == "20.00"   # dinero como cadena
    assert {f["campo"] for f in r["frases"]} == {"ticket_tipico", "umbral_relevante_eur"}
    r = http.patch(_perfil(), json={"campo": "umbral_relevante_eur", "valor": "35"})
    assert r.status_code == 200 and r.json()["perfil"]["umbral_relevante_eur"] == "35.00"
    assert "umbral_relevante_eur" in r.json()["perfil"]["campos_fijados"]
    assert alm.cargar(UID, "modelo", ModeloUsuario).perfil.umbral_relevante_eur == 35
    r = http.delete(f"{_perfil()}/umbral_relevante_eur")
    assert r.status_code == 200 and Decimal(r.json()["perfil"]["umbral_relevante_eur"]) == 20
    assert r.json()["perfil"]["campos_borrados"] == ["umbral_relevante_eur"]
    # Errores: valor malo 400, campo que no existe 404, campo que solo se borra 400.
    assert http.patch(_perfil(), json={"campo": "umbral_relevante_eur", "valor": "mucho"}).status_code == 400
    assert http.patch(_perfil(), json={"campo": "saldo", "valor": 1}).status_code == 404
    assert http.patch(_perfil(), json={"campo": "ticket_tipico", "valor": 5}).status_code == 400
    assert http.delete(f"{_perfil()}/saldo").status_code == 404
    # La auditoría dice qué se tocó, no el valor.
    eventos = [e for e in alm.leer_auditoria(UID) if e["evento"].startswith("perfil_")]
    assert [e["evento"] for e in eventos] == ["perfil_editado", "perfil_campo_borrado"]
    assert all("valor" not in e and "35" not in json.dumps(e) for e in eventos)


def test_borrar_el_perfil_deja_motor_y_politica_en_frio_y_se_puede_reactivar(activo, monkeypatch):
    vistos: list = []
    original = orq.motor.procesar
    monkeypatch.setattr(orq.motor, "procesar", lambda uid, nuevos, hoy, perfil=None: (
        vistos.append(perfil), original(uid, nuevos, hoy, perfil))[1])
    _avanzar(1)
    assert vistos[-1] is not None                                                        # con perfil
    r = http.delete(_perfil())
    assert r.status_code == 200 and r.json() == {"usar_perfil": False, "perfil": None, "frases": []}
    activo.llamadas.clear()
    _avanzar(9)                                                                          # pasa más de una semana
    assert vistos[1:] == [None] * 9 and "perfilar" not in activo.llamadas               # en frío, y sin recalcular
    assert alm.cargar(UID, "modelo", ModeloUsuario).perfil is None
    r = http.patch(_perfil(), json={"campo": "usar_perfil", "valor": True})              # lo vuelve a querer
    assert r.status_code == 200 and r.json()["usar_perfil"] and r.json()["perfil"] is not None
    _avanzar(1)
    assert vistos[-1] is not None
    assert http.patch(_perfil(), json={"campo": "usar_perfil", "valor": "si"}).status_code == 400


def test_aprendido_apagar_editar_borrar_y_olvidar_todo(activo):
    _avanzar(3)
    pid = http.get(f"/usuarios/{UID}/notificaciones").json()[0]["propuesta"]["id"]
    http.post("/feedback", json={"usuario_id": UID, "propuesta_id": pid, "resultado": "rechazada"})
    visto = http.get(_aprendido()).json()
    assert [h["id"] for h in visto["hechos"]] == ["h-rechazada"] and visto["silencios"] == [] and visto["usar_perfil"]
    r = http.patch(_aprendido("h-rechazada"), json={"activo": False})
    assert r.status_code == 200 and r.json()["hechos"][0]["activo"] is False
    assert http.patch(_aprendido("h-rechazada"), json={"activo": True}).status_code == 400   # lo de feedback no se resucita
    assert http.patch(_aprendido("h-rechazada"), json={"texto": "Otra cosa"}).status_code == 400
    assert http.patch(_aprendido("h-rechazada"), json={}).status_code == 400
    assert http.patch(_aprendido("nada"), json={"activo": False}).status_code == 404
    assert http.delete(_aprendido("nada")).status_code == 404
    assert http.delete(_aprendido("h-rechazada")).json()["hechos"] == []
    http.post("/feedback", json={"usuario_id": UID, "propuesta_id": pid, "resultado": "vista_sin_accion"})
    assert [h["id"] for h in http.get(_aprendido()).json()["hechos"]] == ["h-vista_sin_accion"]
    antes = alm.cargar(UID, "modelo", ModeloUsuario)
    r = http.delete(_aprendido())
    assert r.status_code == 200 and r.json()["hechos"] == []
    despues = alm.cargar(UID, "modelo", ModeloUsuario)
    assert despues.consentimientos == antes.consentimientos and despues.modulos_activos == ["gasto_compartido"]
    assert despues.perfil is None and despues.estadisticas == {} and despues.avisos_abiertos == {}


def test_cena_lucia_un_silencio_se_ve_y_se_borra_por_http():
    """Sin stubs: «no avisar de Marcos» aparece en lo aprendido (enmascarado) y al borrarlo desaparece."""
    assert http.post("/demo/cargar", json={"escenario_id": "cena-lucia"}).status_code == 200
    usuario = "lucia"
    assert http.post(f"/usuarios/{usuario}/activar", json={"modulos_activos": ["gasto_compartido"],
                                                           "consentimientos": {"copiloto": True}}).status_code == 200
    perfil = http.get(f"/usuarios/{usuario}/perfil").json()
    assert perfil["perfil"]["dia_cobro_nomina"] == 28 and "Tu nómina suele llegar el día 28." in {
        f["texto"] for f in perfil["frases"]}
    avisos = []
    for _ in range(60):
        http.post("/reloj/avanzar", json={"usuario_id": usuario, "dias": 1})
        avisos = http.get(f"/usuarios/{usuario}/notificaciones", params={"bandeja": "ahora"}).json()
        if avisos:
            break
    pid = avisos[0]["propuesta"]["id"]
    r = http.post("/feedback", json={"usuario_id": usuario, "propuesta_id": pid, "resultado": "no_avisar_contacto"})
    hecho = r.json()["hechos_nuevos"][0]
    visto = http.get(f"/usuarios/{usuario}/aprendido").json()
    assert visto["silencios"] == [{"ambito": "contacto", "desde": "2026-11-09", "valor": "Marcos R."}]
    assert "MARCOS R" not in json.dumps(visto["silencios"])
    borrado = http.delete(f"/usuarios/{usuario}/aprendido/{quote(hecho['id'], safe='')}")
    assert borrado.status_code == 200 and borrado.json()["silencios"] == [] and borrado.json()["hechos"] == []
    assert alm.cargar(usuario, "modelo", ModeloUsuario).preferencias.silencios == []


def test_tarjeta_editable_por_http_sin_stubs():
    """Con `editado: true` el importe del usuario (mayor que la cuota) se valida con las reglas de Bizum y el
    token lo respeta; sin `editado`, el servidor rechaza un importe distinto del ofrecido."""
    usuario = http.post("/demo/cargar", json={"escenario_id": "cena-lucia"}).json()["usuario_id"]
    http.post(f"/usuarios/{usuario}/activar", json={"modulos_activos": ["gasto_compartido"],
                                                    "consentimientos": {"avisos": True, "memoria": True}})
    avisos = []
    for _ in range(60):
        http.post("/reloj/avanzar", json={"usuario_id": usuario, "dias": 1})
        avisos = http.get(f"/usuarios/{usuario}/notificaciones", params={"bandeja": "ahora"}).json()
        if avisos:
            break
    propuesta = avisos[0]["propuesta"]
    oferta = next(a for a in propuesta["acciones_ofrecidas"] if a["accion_id"] == "pedir_bizum")
    editados = {**oferta["parametros"], "importe": "30.00", "concepto": "Cena del viernes"}
    cuerpo = {"usuario_id": usuario, "propuesta_id": propuesta["id"], "accion_id": "pedir_bizum", "parametros": editados}
    assert http.post("/acciones/preparar", json=cuerpo).status_code in (400, 403)
    assert http.post("/acciones/preparar", json={**cuerpo, "editado": True,
                                                 "parametros": {**editados, "importe": "1000.01"}}).status_code == 400
    tarjeta = http.post("/acciones/preparar", json={**cuerpo, "editado": True})
    assert tarjeta.status_code == 200, tarjeta.text
    r = http.post("/acciones/confirmar", json={"usuario_id": usuario,
                                               "token_confirmacion": tarjeta.json()["token_confirmacion"]})
    assert r.status_code == 200 and r.json()["ok"] and r.json()["datos"]["editado"] is True
