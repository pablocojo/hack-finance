"""Tests de la API HTTP. Necesitan fastapi y httpx (pip install -r requirements.txt)."""

import json

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from backend.api.main import app  # noqa: E402
from backend.claude_falso import herramienta, respuesta, texto  # noqa: E402

cliente_http = TestClient(app)


def _sesion_con_datos() -> str:
    r = cliente_http.post("/datos/ejemplo", json={"perfil": "familia"})
    assert r.status_code == 200
    return r.json()["sesion_id"]


def test_salud():
    r = cliente_http.get("/salud")
    assert r.status_code == 200 and "resumen_gastos" in r.json()["herramientas"]


def test_datos_resumen_y_movimientos():
    sesion_id = _sesion_con_datos()
    resumen = cliente_http.get("/movimientos/resumen", params={"sesion_id": sesion_id}).json()
    assert resumen["gastos"] > 0 and resumen["por_categoria"]
    movimientos = cliente_http.get("/movimientos", params={"sesion_id": sesion_id, "limite": 5}).json()
    assert len(movimientos["movimientos"]) == 5
    assert cliente_http.get("/movimientos/resumen", params={"sesion_id": "no-existe"}).status_code == 404


def test_subir_csv():
    csv = "Fecha;Concepto;Importe;Saldo\n05/11/2026;COMPRA TARJETA MERCADONA;-23,40;1.200,00\n"
    r = cliente_http.post("/movimientos", files={"archivo": ("extracto.csv", csv.encode(), "text/csv")})
    assert r.status_code == 200 and r.json()["movimientos"] == 1
    malo = cliente_http.post("/movimientos", files={"archivo": ("x.csv", b"a,b\n1,2\n", "text/csv")})
    assert malo.status_code == 400


def test_chat(falso):
    falso([respuesta(herramienta("resumen_gastos", {"meses": 1})), respuesta(texto("Gastas en vivienda."))])
    sesion_id = _sesion_con_datos()
    r = cliente_http.post("/chat", json={"mensaje": "¿En qué gasto?", "sesion_id": sesion_id})
    assert r.status_code == 200
    assert r.json()["texto"] == "Gastas en vivienda." and r.json()["herramientas"] == ["resumen_gastos"]


def test_chat_stream_sse(falso):
    falso([respuesta(texto("Hola desde el streaming."))])
    sesion_id = _sesion_con_datos()
    with cliente_http.stream("POST", "/chat/stream", json={"mensaje": "Hola", "sesion_id": sesion_id}) as r:
        cuerpo = "".join(r.iter_text())
    eventos = [b for b in cuerpo.split("\n\n") if b.strip()]
    tipos = [b.split("\n")[0].removeprefix("event: ") for b in eventos]
    assert tipos[0] == "sesion" and tipos[-1] == "fin" and "texto" in tipos
    final = json.loads(eventos[-1].split("data: ", 1)[1])
    assert final["texto"] == "Hola desde el streaming."


def test_chat_stream_error_sin_clave(monkeypatch):
    from backend import claude_client

    claude_client.olvidar_clientes()
    for nombre in ("ANTHROPIC_API_KEY_PRODUCTO", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(nombre, raising=False)
    with cliente_http.stream("POST", "/chat/stream", json={"mensaje": "Hola"}) as r:
        cuerpo = "".join(r.iter_text())
    assert "event: error" in cuerpo and "ANTHROPIC_API_KEY_PRODUCTO" in cuerpo
