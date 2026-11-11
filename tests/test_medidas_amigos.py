"""C6: las medidas de la curva de amigos (`amigos/medidas.py`, `evals/medir_amigos.py`) y lo que añade C7
(`factor_respuesta`, procesos en paralelo, almacén en memoria). Sin Claude ni red."""

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
import medir_amigos  # noqa: E402

from backend.personalizacion.simulacion.amigos import medidas as M  # noqa: E402
from backend.personalizacion.simulacion.amigos import protocolo as P  # noqa: E402
from backend.personalizacion.simulacion.amigos.esquema import cargar_vidas  # noqa: E402
from backend.plataforma import almacenamiento  # noqa: E402

VIDAS = cargar_vidas()


def deuda(persona="LAURA M", fecha="2026-10-12", cuota="10.00", devuelto=None, reclamado=None, observable=True,
          canal_devuelto=None, declarado=None, recordado=None, destiempo=None, dias=None):
    return {"tipo": "deuda", "semana": 9, "pago_id": f"p-{persona}-{fecha}", "fecha_pago": fecha, "contraparte": persona,
            "cuota": cuota, "devuelto_el": devuelto, "reclamado_el": reclamado, "observable_21": observable,
            "canal_devuelto": canal_devuelto, "declarado": declarado, "recordado_el": recordado,
            "primer_recordatorio_a_destiempo": destiempo, "dias_hasta_cobrar": dias}


# --- dinero que se escapa ----------------------------------------------------------------------

def test_dinero_que_se_escapa_aplica_las_correcciones_de_experto_usuarios():
    nerea = VIDAS["nerea"]                       # no_recordar: DAVID S
    assert "DAVID S" in nerea.meisam.no_recordar
    eventos = [
        deuda("ANA B"),                                                              # se escapa: 10
        deuda("ANA C", reclamado="2026-10-14"),                                     # reclamada a tiempo
        deuda("ANA D", devuelto="2026-10-20", dias=8),                              # volvió
        deuda("ANA E", reclamado="2026-11-10"),                                     # reclamada tarde: se escapó a los 21 días
        deuda("DAVID S"),                                                           # no_recordar: excluido
        deuda("ANA F", fecha="2026-11-20", observable=False),                       # sin ventana: excluido
        deuda("ANA G", cuota="20.00", devuelto="2026-10-15", canal_devuelto="efectivo", declarado=False, dias=3),
    ]
    r = M.medir_corrida(eventos, nerea)
    # cierre = 12 oct + 21 = 2 nov = semana 5
    assert r["prestado_eur"]["5"] == 60.0                       # 10+10+10+10+20 (sin DAVID S ni la no observable)
    assert r["dinero_escapa_eur"]["5"] == 20.0                  # ANA B y ANA E
    assert r["dinero_escapa"]["5"] == pytest.approx(20 / 60, abs=1e-4)
    assert r["efectivo_sin_declarar_eur"]["5"] == 20.0          # cifra aparte: volvió, no es perdido
    assert r["dinero_escapa"]["4"] is None and r["dinero_escapa"]["8"] is None
    assert r["dinero_escapa"]["total"] == r["dinero_escapa"]["5"]
    assert r["dias_hasta_cobrar"]["5"] == 5.5                   # mediana de 8 y 3


def test_sin_excluir_a_nadie_la_pareja_cuenta():
    r = M.medir_corrida([deuda("DAVID S")], VIDAS["alvaro"])   # en Álvaro no es `no_recordar`
    assert r["dinero_escapa_eur"]["5"] == 10.0


# --- preguntas, acierto, casos, recordatorios, toques ------------------------------------------

def test_preguntas_acierto_casos_recordatorios_y_toques():
    sug = {"personas": ["LAURA M"], "cuotas": {"LAURA M": "5.00"}}
    eventos = [
        {"tipo": "pregunta", "semana": 2, "caso_id": "c1", "nivel": 3, "inutil": None, "sugerencia": sug,
         "sugerencia_correcta": True},
        {"tipo": "pregunta", "semana": 2, "caso_id": "c2", "nivel": 2, "inutil": "iba_solo", "sugerencia": sug,
         "sugerencia_correcta": False},
        {"tipo": "pregunta", "semana": 3, "caso_id": "c3", "nivel": 1, "inutil": "ya_pagado", "sugerencia": None,
         "sugerencia_correcta": None},
        {"tipo": "respuesta", "semana": 2, "caso_id": "c1", "sugerencia_aceptada": True},
        {"tipo": "respuesta", "semana": 2, "caso_id": "c2", "sugerencia_aceptada": False},
        {"tipo": "toque", "semana": 2}, {"tipo": "toque", "semana": 2}, {"tipo": "toque", "semana": 3},
        {"tipo": "cobro", "semana": 2, "importe": "50.00"},
        {"tipo": "caso_final", "creado": "2026-10-13", "deudores": [{"clave": "A"}], "cerrado_solo": True},
        {"tipo": "caso_final", "creado": "2026-10-14", "deudores": [{"clave": "A"}], "cerrado_solo": False},
        {"tipo": "caso_final", "creado": "2026-10-14", "deudores": [], "cerrado_solo": False},    # sin deudores: no cuenta
        deuda("ANA B", recordado="2026-10-14", destiempo=True),
        deuda("ANA C", recordado="2026-10-15", destiempo=False),
    ]
    r = M.medir_corrida(eventos, VIDAS["alvaro"])
    assert (r["preguntas"]["2"], r["preguntas"]["3"], r["preguntas"]["1"], r["preguntas"]["total"]) == (2, 1, 0, 3)
    assert r["preguntas_inutiles"]["total"] == 2
    assert r["preguntas_inutiles_frac"]["2"] == 0.5
    assert r["acierto_sugerencia"]["2"] == 0.5 and r["acierto_sugerencia"]["3"] is None
    assert r["sugerencia_correcta"]["2"] == 0.5
    assert r["casos_cerrados_solos"]["2"] == 0.5                  # la semana 2 empieza el 12 oct
    assert r["recordatorios_a_destiempo"]["2"] == 0.5
    assert r["toques_por_100_eur"]["2"] == pytest.approx(4.0)     # 2 toques por 0,5 centenas de euros
    assert r["toques_por_100_eur"]["3"] is None                   # sin dinero recuperado


def test_cada_medida_tiene_su_descripcion_y_sentido():
    r = M.medir_corrida([], VIDAS["alvaro"])
    assert set(r) == set(M.MEDIDAS)
    assert all(set(fila) == set(M.CLAVES_SEMANA) for fila in r.values())
    assert {m.debe for m in M.MEDIDAS.values()} <= {"bajar", "subir", "informa"}


# --- agregar -----------------------------------------------------------------------------------

def test_intervalo_media_y_t_de_student():
    assert M.intervalo([]) == {"media": None, "ic95": None, "n": 0}
    assert M.intervalo([2.0]) == {"media": 2.0, "ic95": None, "n": 1}
    i = M.intervalo([1.0, 2.0, 3.0])
    assert i["media"] == 2.0 and i["n"] == 3
    assert i["ic95"][0] == pytest.approx(2 - 4.303 / 3 ** 0.5, abs=1e-3)


def test_agregar_separa_evaluacion_y_desglosa():
    def corrida(vida, semilla, valor):
        medidas = M.medir_corrida([], VIDAS[vida])
        medidas["dinero_escapa"]["8"] = valor
        return {"vida": vida, "semilla": semilla, "politica": "reglas", "medidas": medidas}

    corridas = [corrida("alvaro", 0, 0.2), corrida("alvaro", 1, 0.4), corrida("irene", 0, 0.6),
                corrida("irene", 1, 0.6), corrida("nerea", 100, 0.9)]
    r = M.agregar(corridas, VIDAS)["reglas"]
    assert r["ajuste"]["vidas"] == ["alvaro", "irene"]
    assert r["ajuste"]["global"]["dinero_escapa"]["8"]["media"] == pytest.approx(0.45)   # semilla 0: .4, semilla 1: .5
    assert r["evaluacion"]["vidas"] == ["nerea"]
    assert r["evaluacion"]["global"]["dinero_escapa"]["8"]["media"] == 0.9
    assert r["ajuste"]["por_rutina"]["fija"]["vidas"] == ["alvaro"]
    assert r["ajuste"]["por_rutina"]["baja"]["vidas"] == ["irene"]
    assert r["ajuste"]["por_chat"]["alto"]["vidas"] == ["alvaro", "irene"]       # usa_chat 0,3 y 0,6
    assert set(r["por_vida"]) == {"alvaro", "irene", "nerea"}


# --- medir_amigos ------------------------------------------------------------------------------

def test_parse_semillas_y_separacion_ajuste_evaluacion():
    assert medir_amigos.parse_semillas("0-2") == (0, 1, 2)
    assert medir_amigos.parse_semillas("5,0,2-3") == (0, 2, 3, 5)
    with pytest.raises(ValueError, match="Semillas no válidas"):
        medir_amigos.parse_semillas("a-b")
    ids = medir_amigos.elegir_vidas(None, VIDAS)
    assert len(ids) == 8 and "nerea" not in ids and "pilar" not in ids
    assert set(medir_amigos.elegir_vidas("evaluacion", VIDAS)) == {"nerea", "pilar"}
    with pytest.raises(ValueError, match="Vida desconocida"):
        medir_amigos.elegir_vidas("nadie", VIDAS)
    with pytest.raises(ValueError, match="solo de evaluación"):
        medir_amigos.comprobar_separacion(VIDAS, ("nerea",), (0, 1))
    medir_amigos.comprobar_separacion(VIDAS, ("nerea", "pilar"), (100, 101))


def test_hash_de_vidas_es_estable():
    h = medir_amigos.hash_vidas()
    assert h == medir_amigos.hash_vidas()
    assert len(h["hash_vidas"]) == 64 and "alvaro.yaml" in h["archivos"] and "chat_amigos.yaml" in h["archivos"]


def test_medir_parte_amigos_escribe_el_json(tmp_path):
    opciones = {"semillas": (0,), "vidas": "diego", "politicas": ("reglas", "personalizada"), "procesos": 1,
                "sensibilidad": True}
    ruta, r = medir.medir_parte("amigos", tmp_path, date(2026, 11, 11), opciones)
    assert ruta.name == "amigos-2026-11-11.json"
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    assert datos["semillas"] == [0] and datos["fase"] == "ajuste" and datos["simulacion"] is True
    assert len(datos["hash_vidas"]) == 64 and datos["supuestos"] and datos["politicas"] == ["reglas", "personalizada"]
    assert set(datos["resultados"]) == {"reglas", "personalizada"}
    assert datos["comprobaciones"]["errores_del_sistema"] == {"reglas": 0, "personalizada": 0}
    assert datos["sensibilidad"]["factor_respuesta"] == 0.5
    assert "ajuste" in datos["sensibilidad"]["resultados"]["reglas"]
    assert "dinero_escapa" in datos["resultados"]["reglas"]["ajuste"]["global"]
    assert "SIMULACIÓN" in medir_amigos.resumen(r)


def test_amigos_no_entra_en_todo_y_nerea_pide_semillas_de_evaluacion(tmp_path):
    assert "amigos" not in medir.PARTES
    with pytest.raises(ValueError, match="solo de evaluación"):
        medir.medir_parte("amigos", tmp_path, opciones={"semillas": (0,), "vidas": "nerea"})


# --- C7: factor_respuesta, paralelo, memoria ---------------------------------------------------

def test_factor_respuesta_cero_el_usuario_no_contesta_nunca():
    a = P.simular(VIDAS["alvaro"], 0, "reglas")
    b = P.simular(VIDAS["alvaro"], 0, "reglas", factor_respuesta=0.0)
    assert a.de_tipo("respuesta") or a.de_tipo("accion_aviso")          # con 1,0 contesta
    assert not b.de_tipo("respuesta") and not b.de_tipo("accion_aviso") and not b.de_tipo("solicitud")
    assert {e["motivo"] for e in b.de_tipo("ignorada")} <= {"no_contesta", "harto", "duplicada", "tolerancia"}


def _sin_tiempos(resultados):
    return [[{k: v for k, v in e.items() if k != "duracion_s"} for e in r.eventos] for r in resultados]


def test_en_paralelo_da_lo_mismo_que_en_serie_y_en_el_mismo_orden():
    tareas = [("diego", 0, ("reglas",), 1.0), ("sergio", 0, ("reglas", "personalizada"), 1.0)]
    serie = P.simular_en_paralelo(tareas, procesos=1)
    paralelo = P.simular_en_paralelo(tareas, procesos=2)
    assert [(r.vida_id, r.politica) for r in paralelo] == [("diego", "reglas"), ("sergio", "reglas"),
                                                           ("sergio", "personalizada")]
    assert _sin_tiempos(serie) == _sin_tiempos(paralelo)


def test_almacen_en_memoria_solo_si_se_pide(tmp_path, monkeypatch):
    monkeypatch.setenv("DATOS_USUARIO_DIR", str(tmp_path))
    monkeypatch.delenv("ALMACEN_EN_MEMORIA", raising=False)
    assert not almacenamiento.en_memoria()
    almacenamiento.guardar("usuario_x", "cosa", {"a": 1})
    assert (tmp_path / "usuario_x" / "cosa.json").exists()            # por defecto: disco

    monkeypatch.setenv("ALMACEN_EN_MEMORIA", "on")
    try:
        almacenamiento.guardar("usuario_y", "cosa", {"a": 2})
        almacenamiento.anadir_auditoria("usuario_y", {"que": "x"})
        assert not (tmp_path / "usuario_y").exists()                  # nada en disco
        assert almacenamiento.cargar("usuario_y", "cosa") == {"a": 2}
        assert almacenamiento.existe("usuario_y", "cosa") and not almacenamiento.existe("usuario_y", "otra")
        assert almacenamiento.leer_auditoria("usuario_y")[0]["que"] == "x"
        assert almacenamiento.cargar("usuario_x", "cosa") is None     # lo de disco no se ve
        almacenamiento.borrar_usuario("usuario_y")
        assert almacenamiento.cargar("usuario_y", "cosa", defecto="vacío") == "vacío"
        with pytest.raises(ValueError):
            almacenamiento.guardar("../malo", "cosa", {})
    finally:
        almacenamiento.vaciar_memoria()
