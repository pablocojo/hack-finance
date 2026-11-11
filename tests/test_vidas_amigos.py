"""Esquema de las vidas ocultas y del corpus del chat (curva de amigos, C3). Sin red ni crédito."""

from __future__ import annotations

import copy
import re
from decimal import Decimal

import pytest
import yaml

from backend.personalizacion.simulacion.amigos import esquema
from backend.personalizacion.simulacion.amigos.esquema import (
    DIR_VIDAS,
    RUTA_CORPUS,
    cargar_corpus,
    cargar_vidas,
    corpus_desde_dict,
    validar_corpus_con_vidas,
    vida_desde_dict,
)

ESQUEMA_MD = DIR_VIDAS.parent / "ESQUEMA.md"


def _ejemplo_alvaro() -> dict:
    """El YAML de §1.8 de ESQUEMA.md (el ejemplo ilustrativo de Álvaro)."""
    texto = ESQUEMA_MD.read_text(encoding="utf-8")
    seccion = texto.split("### 1.8", 1)[1]
    bloque = re.search(r"```yaml\n(.*?)```", seccion, re.S).group(1)
    return yaml.safe_load(bloque)


def _ejemplo_corpus() -> dict:
    texto = ESQUEMA_MD.read_text(encoding="utf-8")
    seccion = texto.split("### 3.4", 1)[1]
    bloque = re.search(r"```yaml\n(.*?)```", seccion, re.S).group(1)
    return yaml.safe_load(bloque)


def test_carga_el_ejemplo_de_alvaro():
    vida = vida_desde_dict(_ejemplo_alvaro())
    assert vida.id == "alvaro" and vida.uso == "ajuste"
    assert set(vida.amigos) == {"RODRIGO P", "MARCOS L", "NACHO S"}
    assert vida.amigos["RODRIGO P"].retraso_dias == {2: 0.55, 3: 0.35, 5: 0.10}
    assert vida.amigos["NACHO S"].paga_por_dos.con == "MARCOS L"
    assert vida.visible.saldo_inicial == Decimal("620.00")
    assert [p.id for p in vida.planes] == ["pizzas_piso", "sabado_tasca", "cumple_rodrigo"]
    assert vida.planes_esporadicos[0].cuando[0].semana == 5
    assert vida.planes_recurrentes[0].importe_por_persona.max == Decimal("10.00")


def test_falla_con_clave_de_amigo_inexistente():
    datos = _ejemplo_alvaro()
    datos["planes_recurrentes"][0]["grupo"]["fijos"].append("FANTASMA X")
    with pytest.raises(ValueError, match="FANTASMA X"):
        vida_desde_dict(datos)


@pytest.mark.parametrize("donde", ["paga", "paga_por_dos", "no_recordar"])
def test_falla_con_otras_referencias_rotas(donde):
    datos = _ejemplo_alvaro()
    if donde == "paga":
        datos["planes_recurrentes"][0]["paga"] = {"NADIE Z": 1.0}
    elif donde == "paga_por_dos":
        datos["amigos"]["NACHO S"]["paga_por_dos"]["con"] = "NADIE Z"
    else:
        datos["meisam"]["no_recordar"] = ["NADIE Z"]
    with pytest.raises(ValueError, match="NADIE Z"):
        vida_desde_dict(datos)


def test_falla_con_probabilidad_mayor_que_uno():
    datos = _ejemplo_alvaro()
    datos["planes_recurrentes"][0]["prob_semanal"] = 1.2
    with pytest.raises(ValueError):
        vida_desde_dict(datos)
    datos = _ejemplo_alvaro()
    datos["amigos"]["RODRIGO P"]["prob_paga_solo"] = 1.5
    with pytest.raises(ValueError):
        vida_desde_dict(datos)


def test_falla_con_errata_de_campo_y_con_distribucion_invalida():
    datos = _ejemplo_alvaro()
    datos["amigos"]["RODRIGO P"]["retrasso_dias"] = {1: 1.0}
    with pytest.raises(ValueError):
        vida_desde_dict(datos)
    datos = _ejemplo_alvaro()
    datos["amigos"]["RODRIGO P"]["retraso_dias"] = {2: 0.0}
    with pytest.raises(ValueError, match="sumar"):
        vida_desde_dict(datos)
    datos = _ejemplo_alvaro()
    datos["amigos"]["RODRIGO P"]["retraso_tras_pedir_dias"] = {9: 1.0}
    with pytest.raises(ValueError, match="fuera de"):
        vida_desde_dict(datos)


def test_reglas_de_planes_y_rangos():
    datos = _ejemplo_alvaro()
    datos["planes_recurrentes"][0]["importe_por_persona"] = {"min": "12.00", "max": "9.00"}
    with pytest.raises(ValueError, match="min"):
        vida_desde_dict(datos)
    datos = _ejemplo_alvaro()
    datos["planes_recurrentes"][0]["importe_por_persona"] = {"min": "100.00", "max": "300.00"}
    with pytest.raises(ValueError, match="tope"):
        vida_desde_dict(datos)
    datos = _ejemplo_alvaro()
    datos["planes_recurrentes"][0]["cuando"] = [{"semana": 1, "dia": 0}]     # recurrente con `cuando`
    with pytest.raises(ValueError):
        vida_desde_dict(datos)
    datos = _ejemplo_alvaro()
    del datos["planes_esporadicos"][0]["cuando"]                              # esporádico sin `cuando`
    with pytest.raises(ValueError):
        vida_desde_dict(datos)
    datos = _ejemplo_alvaro()
    datos["planes_esporadicos"][0]["id"] = "pizzas_piso"
    with pytest.raises(ValueError, match="repetido"):
        vida_desde_dict(datos)
    datos = _ejemplo_alvaro()
    datos["cambios_rutina"][0]["planes"] = {"no_existe": 0.5}
    with pytest.raises(ValueError, match="no_existe"):
        vida_desde_dict(datos)


def test_corpus_de_ejemplo_valida_y_detecta_errores():
    corpus = corpus_desde_dict(_ejemplo_corpus())
    assert [e.id for e in corpus.entradas] == ["alvaro-01", "alvaro-02", "alvaro-03"]
    vidas = {"alvaro": vida_desde_dict(_ejemplo_alvaro())}
    assert validar_corpus_con_vidas(corpus, vidas) == []

    datos = _ejemplo_corpus()
    datos["entradas"][0]["disparador"] = "plan:no_existe"
    errores = validar_corpus_con_vidas(corpus_desde_dict(datos), vidas)
    assert errores and "no_existe" in errores[0]

    datos = copy.deepcopy(_ejemplo_corpus())
    datos["entradas"][1]["plantilla"] = "apuntame {inventado}"
    with pytest.raises(ValueError, match="inventado"):
        corpus_desde_dict(datos)

    datos = copy.deepcopy(_ejemplo_corpus())
    datos["entradas"][2]["id"] = "alvaro-01"
    with pytest.raises(ValueError, match="repetidos"):
        corpus_desde_dict(datos)


def test_disparador_semana_no_admite_huecos_de_pago():
    datos = _ejemplo_corpus()
    datos["entradas"][1]["plantilla"] = "oye me costo {total}"
    with pytest.raises(ValueError, match="semana"):
        corpus_desde_dict(datos)


def test_vidas_del_repositorio_validan():
    if not any(DIR_VIDAS.glob("*.yaml")):
        pytest.skip("todavía no hay vidas en amigos/vidas/")
    vidas = cargar_vidas()          # falla con el nombre del archivo y el error si alguna no valida
    assert vidas
    for vida in vidas.values():
        assert vida.amigos, f"{vida.id}: sin amigos"


def test_corpus_del_repositorio_valida():
    if not RUTA_CORPUS.exists():
        pytest.skip("todavía no existe evals/datos/chat_amigos.yaml")
    corpus = cargar_corpus()
    assert corpus.entradas
    if any(DIR_VIDAS.glob("*.yaml")):
        assert validar_corpus_con_vidas(corpus, cargar_vidas()) == []


def test_modulo_expone_las_rutas():
    assert esquema.DIR_VIDAS.name == "vidas" and esquema.RUTA_CORPUS.name == "chat_amigos.yaml"
