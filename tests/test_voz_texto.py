"""Nivel 3 de la llamada (texto con el agente del kit) con el cliente falso de Claude."""

from __future__ import annotations

import json

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from backend.agente import registro  # noqa: E402
from backend.api.main import app  # noqa: E402
from backend.claude_falso import herramienta, respuesta, texto  # noqa: E402
from backend.voz import sesiones  # noqa: E402
from tests.test_voz_sesion import UID, abrir, crear_usuario  # noqa: E402

http = TestClient(app)


@pytest.fixture(autouse=True)
def limpio(monkeypatch):
    monkeypatch.delenv("DEMO_KEY", raising=False)
    sesiones.olvidar_todo()


def leer_sse(r) -> list[tuple[str, dict]]:
    salida = []
    for bloque in r.text.strip().split("\n\n"):
        lineas = dict(linea.split(": ", 1) for linea in bloque.splitlines() if ": " in linea)
        salida.append((lineas["event"], json.loads(lineas["data"])))
    return salida


def test_saludo_fijo_dice_que_es_ia_y_no_llama_a_claude(falso):
    crear_usuario()
    cliente = falso([])
    token = abrir().json()["token_sesion"]
    eventos = leer_sse(http.post("/voz/texto", json={"token_sesion": token}))
    assert eventos[0][0] == "texto"
    assert eventos[0][1]["texto"].startswith("Hola Lucía, me has abierto desde el aviso:")  # neutro; la insignia «IA» va en pantalla
    assert cliente.peticiones == []


def test_preparar_pedir_bizum_emite_tarjeta_y_el_modelo_no_ve_el_token(falso):
    crear_usuario()
    cliente = falso([
        respuesta(herramienta("preparar_accion", {"accion_id": "pedir_bizum", "contraparte": "Marcos R.",
                                                  "importe": 24, "concepto": "Tu parte de La Tasca"})),
        respuesta(texto("Te la dejo en pantalla, pulsa Confirmar.")),
    ])
    token = abrir().json()["token_sesion"]
    eventos = leer_sse(http.post("/voz/texto", json={"token_sesion": token, "mensaje": "Sí, pídeselo a Marcos"}))
    tipos = [t for t, _ in eventos]
    assert "tarjeta" in tipos and tipos.index("tarjeta") > tipos.index("herramienta_fin") and tipos[-1] == "fin"
    tarjeta = next(d for t, d in eventos if t == "tarjeta")["tarjeta"]
    assert tarjeta["accion_id"] == "pedir_bizum" and tarjeta["token_confirmacion"] and tarjeta["simulada"]
    # el token no aparece en ninguna petición a Claude ni en ningún otro evento
    secreto = tarjeta["token_confirmacion"]
    assert all(secreto not in json.dumps(p, default=str) for p in cliente.peticiones)
    assert all(secreto not in json.dumps(d) for t, d in eventos if t != "tarjeta")
    resultado = next(d for t, d in eventos if t == "herramienta_fin")
    assert json.loads(resultado["resumen"]) == {"preparada": True, "titulo": tarjeta["titulo"]}
    # el sistema lleva el contexto de la propuesta y las herramientas son solo las de la llamada
    primera = cliente.peticiones[0]
    assert "La Tasca" in json.dumps(primera["system"]) and "Marcos R." in json.dumps(primera["system"])
    assert {t["name"] for t in primera["tools"]} == {"preparar_accion", "registrar_feedback"}


def test_accion_fuera_de_la_propuesta_no_emite_tarjeta(falso):
    crear_usuario()
    falso([respuesta(herramienta("preparar_accion", {"accion_id": "mover_dinero", "importe": 500})),
           respuesta(texto("No puedo hacer eso."))])
    token = abrir().json()["token_sesion"]
    eventos = leer_sse(http.post("/voz/texto", json={"token_sesion": token, "mensaje": "Mueve 500 euros"}))
    assert "tarjeta" not in [t for t, _ in eventos]
    fin = next(d for t, d in eventos if t == "herramienta_fin")
    assert json.loads(fin["resumen"])["preparada"] is False


def test_registrar_feedback_por_herramienta(falso):
    crear_usuario()
    falso([respuesta(herramienta("registrar_feedback", {"resultado": "falso_positivo"})),
           respuesta(texto("Entendido, no te avisaré. Hasta luego."))])
    token = abrir().json()["token_sesion"]
    eventos = leer_sse(http.post("/voz/texto", json={"token_sesion": token, "mensaje": "Era un error"}))
    assert eventos[-1][0] == "fin"
    from backend.plataforma import almacenamiento as alm
    assert any(e.get("evento") == "feedback" and e.get("canal") == "texto" for e in alm.leer_auditoria(UID))


def test_texto_sin_sesion_valida():
    assert http.post("/voz/texto", json={"token_sesion": "nope", "mensaje": "hola"}).status_code == 401


def test_kit_no_ve_las_herramientas_de_la_llamada():
    from backend.agente.nucleo import Agente
    import backend.voz.herramientas_llamada  # noqa: F401  (las registra)
    assert "preparar_accion" in registro.REGISTRO
    visibles = {h.nombre for h in registro.disponibles()}
    assert "preparar_accion" not in visibles and "registrar_feedback" not in visibles
    assert not {"preparar_accion", "registrar_feedback"} & {h["name"] for h in Agente().herramientas_api()}
    texto_error, es_error, _ = registro.ejecutar("preparar_accion", {"accion_id": "recordar"}, ctx=None,
                                                 permitidas={h.nombre for h in registro.disponibles()})
    assert es_error
