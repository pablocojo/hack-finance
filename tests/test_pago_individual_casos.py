"""Pago individual de punta a punta: el motor lo detecta, el caso nace silencioso o en el Resumen y no hay push."""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.api.main import app

http = TestClient(app)


def _recorrer(escenario: str, dias: int = 40):
    usuario = http.post("/demo/cargar", json={"escenario_id": escenario}).json()["usuario_id"]
    http.post(f"/usuarios/{usuario}/activar", json={"modulos_activos": ["gasto_compartido"],
                                                    "consentimientos": {"copiloto": True, "memoria": True}})
    for _ in range(dias):
        http.post("/reloj/avanzar", json={"usuario_id": usuario, "dias": 1})
    return usuario


def test_restaurante_en_fin_de_semana_abre_caso_en_el_resumen_sin_push():
    usuario = _recorrer("restaurante-fin-de-semana-solo")
    casos = http.get(f"/usuarios/{usuario}/casos").json()
    individuales = [c for c in casos if c["escenario"] == "pago_individual"]
    assert individuales, "el restaurante del sábado debe abrir un caso pago_individual"
    caso = individuales[0]
    assert caso["aviso"] == "resumen" and caso["deudores"] == []
    avisos = http.get(f"/usuarios/{usuario}/notificaciones", params={"bandeja": "ahora"}).json()
    assert not [a for a in avisos if a["propuesta"]["tipo_momento"] == "gasto_compartido"], "nunca hace push"


def test_mercadona_entre_semana_no_abre_nada():
    usuario = _recorrer("mercadona-entre-semana")
    casos = http.get(f"/usuarios/{usuario}/casos").json()
    assert not [c for c in casos if c["escenario"] == "pago_individual"]
