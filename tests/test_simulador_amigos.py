"""Simulador de vidas con amigos sobre el sistema real (C5, `amigos/protocolo.py`). Sin red ni crédito: DUDAS_IA y la
búsqueda web van apagadas y los datos de usuario viven en una carpeta temporal."""

from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path

import pytest

from backend.personalizacion.simulacion.amigos import protocolo
from backend.personalizacion.simulacion.amigos.esquema import cargar_vidas
from backend.personalizacion.simulacion.amigos.generador import generar

COMUNES = {"tipo", "dia", "semana", "vida", "semilla", "politica"}
TIPOS = {"pago", "caso", "silencio", "pregunta", "respuesta", "ignorada", "aviso", "accion_aviso", "solicitud",
         "reclamo", "reaccion", "cobro", "efectivo", "correccion", "feedback", "silencia", "chat", "cierre", "toque",
         "error", "saltado", "deuda", "caso_final", "fin"}
VIDA = "alvaro"
SEMILLA = 0


@pytest.fixture(scope="module")
def vida():
    return cargar_vidas()[VIDA]


@pytest.fixture(scope="module")
def tres(vida, tmp_path_factory):
    """Una vida × una semilla × las 3 políticas (una sola vez para todo el módulo)."""
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("DATOS_USUARIO_DIR", str(tmp_path_factory.mktemp("datos_previos")))
        return protocolo.simular_politicas(vida, SEMILLA)


def test_tres_politicas_corren_sin_errores(tres):
    assert set(tres) == set(protocolo.POLITICAS)
    for politica, r in tres.items():
        assert r.de_tipo("error") == [], r.de_tipo("error")
        assert r.de_tipo("fin"), politica
        assert r.usuario_id == f"sim-{VIDA}-{SEMILLA}-{politica}"


def test_el_registro_tiene_el_formato_documentado(tres):
    for r in tres.values():
        for e in r.eventos:
            assert COMUNES <= set(e), e
            assert e["tipo"] in TIPOS, e["tipo"]
            assert 1 <= e["semana"] <= protocolo.SEMANA_FINAL
        for p in r.de_tipo("pregunta"):
            assert {"caso_id", "pago_id", "nivel", "canal", "inutil", "sugerencia"} <= set(p)
        for d in r.de_tipo("deuda"):
            assert {"cuota", "devuelto_el", "reclamado_el", "en_caso_el", "observable_21", "dia_pagaria_solo"} <= set(d)
        assert r.eventos[-1]["tipo"] == "fin" and "duracion_s" in r.eventos[-1]


def test_todas_las_politicas_ven_la_misma_vida(tres):
    """Misma suerte: los pagos (verdad) y las deudas de la verdad son idénticos en las 3 políticas."""
    def pagos(r):
        return [(e["dia"], e["pago_id"], e["importe"], e["deudores"]) for e in r.de_tipo("pago")]
    base = pagos(tres["reglas"])
    assert base and all(pagos(r) == base for r in tres.values())
    claves = {(d["pago_id"], d["contraparte"], d["cuota"]) for d in tres["reglas"].de_tipo("deuda")}
    assert all({(d["pago_id"], d["contraparte"], d["cuota"]) for d in r.de_tipo("deuda")} == claves
               for r in tres.values())


def test_con_reglas_no_aprende_nada(tres):
    fin = tres["reglas"].aprendizaje_final
    assert fin["modo"] == "reglas" and fin["vacio"] is True
    assert tres["personalizada"].aprendizaje_final["modo"] == "aprende"


def test_sin_chat_no_hay_mensajes(tres, vida):
    assert tres["personalizada_sin_chat"].de_tipo("chat") == []
    if generar(vida, SEMILLA).chat:
        assert tres["personalizada"].de_tipo("chat")


def _hechos(r):
    return [e for e in r.de_tipo("chat") if e["herramienta"] == "recordar_sobre_mi"]


@pytest.fixture(scope="module")
def con_hechos(tmp_path_factory):
    """Irene, semilla 0: su chat trae hechos (`recordar_sobre_mi`)."""
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("DATOS_USUARIO_DIR", str(tmp_path_factory.mktemp("datos_previos_irene")))
        return protocolo.simular_politicas(cargar_vidas()["irene"], 0)


def test_los_hechos_del_chat_se_envian_y_no_se_saltan(con_hechos):
    """Ningún hecho queda `saltado`: con `personalizada` se guardan, con `reglas` el sistema los rechaza por
    `aprendizaje_apagado` y sin chat no se envía nada."""
    for r in con_hechos.values():
        assert "recordar_sobre_mi" not in r.saltado
        assert r.de_tipo("error") == []
    hechos = {p: _hechos(r) for p, r in con_hechos.items()}
    assert hechos["personalizada_sin_chat"] == []
    assert hechos["personalizada"] and len(hechos["reglas"]) == len(hechos["personalizada"])
    assert {e["resultado"] for e in hechos["reglas"]} == {"aprendizaje_apagado"}
    assert {e["resultado"] for e in hechos["personalizada"]} <= {"guardado", "repetido"}
    assert all({"reintento", "extraccion", "esperado_resultado"} <= set(e) for e in hechos["personalizada"])


def test_persona_desconocida_se_repite_confirmando(tmp_path, monkeypatch):
    """Si el sistema pide confirmar una persona nueva y lo esperado era guardar, se repite una vez confirmando."""
    from backend.plataforma import chat_casos
    llamadas = []
    real = chat_casos.recordar_sobre_mi_usuario

    def falsa(uid, entrada, confirmar_personas_nuevas=False):
        llamadas.append(confirmar_personas_nuevas)
        if not confirmar_personas_nuevas:
            return {"ok": False, "resultado": "persona_desconocida", "error": "no conozco a esa persona"}
        return real(uid, entrada, confirmar_personas_nuevas)

    monkeypatch.setattr(chat_casos, "recordar_sobre_mi_usuario", falsa)
    r = protocolo.simular(cargar_vidas()["irene"], 0, "personalizada", dir_datos=tmp_path / "d")
    hechos = _hechos(r)
    assert hechos and llamadas.count(False) == len(hechos) == llamadas.count(True)
    assert all(e["reintento"] for e in hechos)
    assert r.de_tipo("error") == []


def _sistema(r, hasta):
    """Lo que hizo el sistema y el usuario hasta `hasta` (sin los eventos finales ni la marca de ventana)."""
    salida = []
    for e in r.eventos:
        if e["tipo"] in protocolo.FINALES or e["dia"] > hasta:
            continue
        salida.append({k: v for k, v in e.items() if k != "fuera_de_ventana"})
    return salida


def test_ninguna_decision_ve_el_futuro(tres, vida):
    """Si se borra todo lo que pasa después de un día, lo que el sistema decidió hasta ese día no cambia."""
    gen = generar(vida, SEMILLA)
    corte = gen.activacion + timedelta(days=20)
    cortada = protocolo.simular(vida, SEMILLA, "reglas", generada=gen, corte=corte)
    assert cortada.de_tipo("error") == []
    hasta = corte.isoformat()
    assert _sistema(cortada, hasta) == _sistema(tres["reglas"], hasta)


def test_respeta_el_entorno_y_no_toca_datos_usuario(vida, tmp_path, monkeypatch):
    monkeypatch.setenv("DATOS_USUARIO_DIR", str(tmp_path / "previo"))
    monkeypatch.setenv("DUDAS_IA", "on")
    vistos = {}

    def espiar(*args, **kwargs):
        vistos.update(dir=os.environ["DATOS_USUARIO_DIR"], dudas=os.environ["DUDAS_IA"],
                      web=os.environ["BUSQUEDA_WEB"])
        raise RuntimeError("parada")

    monkeypatch.setattr(protocolo._Simulacion, "correr", espiar)
    with pytest.raises(RuntimeError):
        protocolo.simular(vida, SEMILLA, "reglas")
    assert vistos["dudas"] == "off" and vistos["web"] == "off"
    assert Path(vistos["dir"]) != tmp_path / "previo" and not Path(vistos["dir"]).exists()   # temporal y borrada
    assert os.environ["DATOS_USUARIO_DIR"] == str(tmp_path / "previo") and os.environ["DUDAS_IA"] == "on"


def test_elegir_usa_el_numero_sorteado():
    dist = {1: 0.5, 6: 0.3, 60: 0.2}
    assert protocolo._elegir(dist, 0.0) == 1
    assert protocolo._elegir(dist, 0.6) == 6
    assert protocolo._elegir(dist, 0.99) == 60


def test_politica_desconocida_falla(vida):
    with pytest.raises(ValueError):
        protocolo.simular(vida, SEMILLA, "oraculo")
