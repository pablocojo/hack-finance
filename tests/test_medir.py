"""`/medir` (E9): la línea base del motor, la parte de personalización pendiente y `GET /metricas/{nombre}`."""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ / "evals") not in sys.path:
    sys.path.insert(0, str(RAIZ / "evals"))

import medir  # noqa: E402



@pytest.fixture(scope="module")
def dos_ejecuciones(tmp_path_factory):
    """Dos ejecuciones de la parte motor en días distintos (la segunda se compara con la primera)."""
    directorio = tmp_path_factory.mktemp("resultados")
    primera, _ = medir.medir_parte("motor", directorio, date(2026, 11, 9))
    segunda, resultado = medir.medir_parte("motor", directorio, date(2026, 11, 10))
    return directorio, primera, segunda, resultado


def test_escribe_el_json_del_motor_con_fecha(dos_ejecuciones):
    directorio, primera, segunda, resultado = dos_ejecuciones
    assert primera.name == "motor-2026-11-09.json" and segunda.name == "motor-2026-11-10.json"
    assert json.loads(segunda.read_text(encoding="utf-8")) == json.loads(json.dumps(resultado, default=str))
    assert medir.ultimo("motor", directorio) == segunda
    assert resultado["parte"] == "motor" and "cena-lucia" in resultado["escenarios"]["etiquetados"]
    assert {"fondo-estudiante", "fondo-familia", "fondo-autonomo"} <= set(resultado["escenarios"]["fondo"])


def test_gasto_compartido_en_la_linea_base(dos_ejecuciones):
    sin = dos_ejecuciones[3]["sin_perfil"]
    fila = sin["por_detector"]["gasto_compartido"]
    assert fila["precision"] == 1.0 and fila["exhaustividad"] == 1.0
    assert fila["retraso_medio"] == 0 and fila["trampas_violadas"] == 0 and fila["cumple"] is True
    cena = next(f for f in sin["por_escenario"] if f["escenario"] == "cena-lucia")
    assert cena["aciertos"] == 1 and cena["omitidos"] == 0 and cena["falsos_positivos"] == []
    assert cena["retrasos"] == {"gasto_compartido": [0]} and cena["trampas_violadas"] == []


def test_ruido_de_fondo_y_tiempo(dos_ejecuciones):
    sin = dos_ejecuciones[3]["sin_perfil"]
    ruido = sin["ruido_fondo"]
    assert len(ruido["usuarios"]) >= 3 and ruido["cumple"] is True
    assert ruido["max_por_usuario_mes"] <= 1.0
    assert all(u["meses"] >= 3 for u in ruido["usuarios"])
    assert sin["ms_max_por_escenario"] < 2000          # 3,5 meses día a día en < 2 s por usuario


def test_con_perfil_se_mide_o_se_explica(dos_ejecuciones):
    con = dos_ejecuciones[3]["con_perfil"]
    if con["disponible"]:
        assert con["por_detector"]["gasto_compartido"]["exhaustividad"] == 1.0
        assert con["ruido_fondo"]["cumple"] is True
    else:
        assert "perfilar" in con["motivo"]


def test_compara_con_la_ejecucion_anterior(dos_ejecuciones):
    directorio, primera, _, resultado = dos_ejecuciones
    comp = resultado["comparacion"]
    assert comp["contra"] == primera.name and comp["empeora"] == []


def test_comparar_marca_lo_que_empeora():
    from medir_motor import comparar

    def pasada(precision, ruido):
        return {"disponible": True, "ruido_fondo": {"max_por_usuario_mes": ruido},
                "por_detector": {"gasto_compartido": {"precision": precision, "exhaustividad": 1.0,
                                                      "retraso_medio": 0, "trampas_violadas": 0}}}

    antes = {"sin_perfil": pasada(1.0, 0.2), "con_perfil": {"disponible": False}}
    ahora = {"sin_perfil": pasada(0.5, 0.1), "con_perfil": {"disponible": False}}
    comp = comparar(ahora, antes, "motor-2026-11-09.json")
    assert [(c["detector"], c["campo"]) for c in comp["empeora"]] == [("gasto_compartido", "precision")]
    assert [(c["detector"], c["campo"]) for c in comp["mejora"]] == [("ruido_fondo", "max_por_usuario_mes")]
    assert comparar(ahora, None) is None


def test_personalizacion_pendiente_no_falla(tmp_path, monkeypatch):
    monkeypatch.setitem(medir.MODULOS, "personalizacion", "medir_que_no_existe")
    monkeypatch.setitem(medir.PENDIENTE_SI_FALTA, "personalizacion", ("medir_que_no_existe",))
    ruta, resultado = medir.medir_parte("personalizacion", tmp_path, date(2026, 11, 9))
    assert ruta.name == "personalizacion-2026-11-09.json"
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    assert datos["estado"] == "pendiente" and "U3" in datos["motivo"]


def test_parte_desconocida(tmp_path):
    with pytest.raises(ValueError):
        medir.medir_parte("otra", tmp_path)


def test_medir_no_llama_a_claude(tmp_path, falso):
    cliente = falso()
    medir.medir_parte("motor", tmp_path, date(2026, 11, 9))
    assert cliente.peticiones == []


# --- GET /metricas/{nombre} ------------------------------------------------------------------------

@pytest.fixture
def http():
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from backend.api.main import app

    return TestClient(app)


def test_metricas_devuelve_el_ultimo_json(http, tmp_path, monkeypatch):
    from backend.api import rutas_metricas

    monkeypatch.setattr(rutas_metricas, "RESULTADOS", tmp_path)
    (tmp_path / "motor-2026-11-09.json").write_text(json.dumps({"parte": "motor", "n": 1}), encoding="utf-8")
    (tmp_path / "motor-2026-11-10.json").write_text(json.dumps({"parte": "motor", "n": 2}), encoding="utf-8")
    (tmp_path / "20261110-101010.json").write_text("{}", encoding="utf-8")          # evals del kit: se ignora
    for nombre in ("motor", "deteccion"):
        r = http.get(f"/metricas/{nombre}")
        assert r.status_code == 200
        assert r.json()["n"] == 2 and r.json()["archivo"] == "motor-2026-11-10.json" and r.json()["generado"]


def test_metricas_404_legible(http, tmp_path, monkeypatch):
    from backend.api import rutas_metricas

    monkeypatch.setattr(rutas_metricas, "RESULTADOS", tmp_path)
    r = http.get("/metricas/motor")
    assert r.status_code == 404 and "evals/medir.py" in r.json()["detail"]
    assert http.get("/metricas/aprendizaje").status_code == 404
    r = http.get("/metricas/otra")
    assert r.status_code == 404 and "motor" in r.json()["detail"]


def test_la_linea_base_esta_versionada(http):
    """Render tiene disco efímero: `/jurado` lee el JSON versionado en `evals/resultados/`."""
    r = http.get("/metricas/motor")
    assert r.status_code == 200
    assert r.json()["sin_perfil"]["por_detector"]["gasto_compartido"]["precision"] == 1.0
