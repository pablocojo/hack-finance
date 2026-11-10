"""
Curva de aprendizaje (U3, docs/diseno/personalizacion.md §8): usuarios simulados con preferencias ocultas,
6 semanas y cinco políticas, con la política, el perfil y el aprendizaje reales. Sin crédito, sin Claude y
reproducible (semillas fijas).

Los objetivos se comprueban con las semillas 0-9 juntas: con una sola (semilla 0) cada semana trae unos 20
avisos que interrumpen y la precisión baila ±0,1. La semilla 0 sola se usa con más margen.

Hipótesis medida (0-9): con el perfil, la precisión de la semana 1 sube de 0,61 (`fija`) a 0,67; aprender
quita ~80 % de las molestias frente a `reglas` y la primera acción ofrecida pasa de 0,39 a 0,72. NO sale
el objetivo de 0,80 en la semana 6 (0,74): `saturable` ignora desde el 4.º aviso de la semana y la política
no lo capta (xfail estricto abajo; cuando se arregle, el test avisará).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ / "evals") not in sys.path:
    sys.path.insert(0, str(RAIZ / "evals"))

from backend.personalizacion.simulacion import generador, perfiles, protocolo as P  # noqa: E402

SEMILLAS = tuple(range(10))
S1, S6 = 0, 5


def _f(regs, politica, semana=None, usuario=None):
    return P.fila([r for r in regs if r["politica"] == politica and (semana is None or r["semana"] == semana)
                   and (usuario is None or r["usuario"] == usuario)])


@pytest.fixture(scope="module")
def regs():
    return P.simular_todo(SEMILLAS)


@pytest.fixture(scope="module")
def regs0():
    return P.simular_todo((0,))


# --- Reproducible y aislado ------------------------------------------------------------------------

def test_misma_semilla_mismos_resultados():
    quitar = lambda rs: [{k: v for k, v in r.items() if k != "ms"} for r in rs]    # noqa: E731
    a = P.simular_todo((3,), ("personalizada",), ("social", "saturable"))
    b = P.simular_todo((3,), ("personalizada",), ("social", "saturable"))
    assert quitar(a) == quitar(b)
    otra = P.simular_todo((4,), ("personalizada",), ("social", "saturable"))
    assert quitar(a) != quitar(otra)


def test_las_politicas_ven_las_mismas_propuestas(regs0):
    por_pol = {pol: [r["id"] for r in regs0 if r["politica"] == pol and r["usuario"] == "social"]
               for pol in P.POLITICAS}
    assert all(ids == por_pol["fija"] for ids in por_pol.values()) and len(por_pol["fija"]) == 60


def test_la_politica_no_importa_la_simulacion():
    assert P.verificar_aislamiento() == []


def test_datos_de_los_usuarios_son_coherentes():
    for u in perfiles.USUARIOS.values():
        for tipo, accion in u.favorita.items():
            assert accion in generador.ACCIONES_OFRECIDAS[tipo], (u.nombre, tipo)
        p = u.perfil
        assert p.umbral_relevante_eur == min(max(2 * p.ticket_tipico, 5), 100)    # lo que daría `perfilar`
    assert set(perfiles.USUARIOS) == {"estudiante", "holgado", "social", "saturable"}


# --- Objetivos (semillas 0-9) ----------------------------------------------------------------------

def test_el_perfil_sube_la_precision_de_la_semana_1(regs):
    fija, perfil = _f(regs, "fija", S1)["precision_ahora"], _f(regs, "perfil", S1)["precision_ahora"]
    assert perfil >= 0.65 and perfil > fija + 0.03
    assert _f(regs, "reglas", S1)["precision_ahora"] < fija          # y ambas mejoran a «avisar todo»


def test_la_curva_sube_aprendiendo(regs):
    sem = [_f(regs, "personalizada", w)["precision_ahora"] for w in range(6)]
    assert sum(sem[3:]) / 3 > sem[0] + 0.05                              # las últimas semanas, mejor que la primera
    assert _f(regs, "personalizada", S6)["precision_ahora"] >= _f(regs, "perfil", S6)["precision_ahora"] + 0.08
    assert _f(regs, "personalizada", S6)["precision_ahora"] >= 0.70
    for u in ("estudiante", "holgado", "social"):                       # donde el modelo puede aprender, llega a ~0,8
        assert _f(regs, "personalizada", S6, u)["precision_ahora"] >= 0.75, u


@pytest.mark.xfail(strict=True, reason="No sale: saturable ignora desde el 4.º aviso de la semana y la política "
                                       "no capta esa fatiga (semana 6: 0,74 con 10 semillas)")
def test_objetivo_de_precision_080_en_la_semana_6(regs):
    assert _f(regs, "personalizada", S6)["precision_ahora"] >= 0.80


def test_molestias_evitadas_frente_a_reglas(regs):
    reglas, pers = _f(regs, "reglas", S6)["molestias"], _f(regs, "personalizada", S6)["molestias"]
    assert 1 - pers / reglas >= 0.65


def test_la_primera_accion_ofrecida_acierta(regs):
    s1, s6 = (_f(regs, "personalizada", w)["primera_accion"] for w in (S1, S6))
    assert s6 >= 0.70 and s6 > s1 + 0.2
    assert _f(regs, "fija", S6)["primera_accion"] < 0.55                 # sin aprender, el orden del módulo


def test_no_se_pierde_lo_util(regs):
    pers = _f(regs, "personalizada")
    assert pers["arrepentimiento"] <= 0.05
    assert _f(regs, "personalizada", usuario="estudiante")["arrepentimiento"] <= 0.05
    assert _f(regs, "personalizada", S6)["cobertura_total"] >= 0.90
    assert _f(regs, "personalizada", S6)["cobertura_ahora"] >= 0.75


def test_proteccion_nunca_silenciada_ni_avisos_tras_un_no_avisar(regs):
    for pol in ("fija", "perfil", "aprendida", "personalizada"):
        rs = [r for r in regs if r["politica"] == pol]
        assert not [r for r in rs if r["proteccion"] and r["accion"] == "silenciar"], pol
        assert not [r for r in rs if r["tras_silencio"] and r["accion"] == "notificar_ahora"], pol


def test_toda_decision_lleva_motivo_y_tarda_menos_de_5_ms(regs):
    rs = [r for r in regs if r["politica"] != "reglas"]
    assert all(1 <= r["motivos"] <= 3 for r in rs)
    ms = sorted(r["ms"] for r in rs)
    assert ms[int(0.99 * len(ms))] < 5          # el máximo puede subir por el recolector de basura o el sistema


def test_mismo_duplicado_estudiante_notifica_y_holgado_no():
    d = P.duplicado()
    assert d["estudiante"]["perfil"]["accion"] == "notificar_ahora"
    assert d["holgado"]["perfil"]["accion"] != "notificar_ahora"
    assert d["estudiante"]["perfil"]["U"] == pytest.approx(0.9159, abs=1e-3)       # §4.4 (3,17 de B)
    assert all(v["fija"]["accion"] == "resumen" for v in d.values())                # sin perfil, igual para todos


def test_un_modulo_nuevo_hereda_lo_aprendido():
    nuevos = {t: f"modulo_nuevo_{i}" for i, t in enumerate(generador.MODULO_DE)}
    clave = lambda rs: [(r["id"], r["accion"], r["resultado"], r["primera"], r["elegida"]) for r in rs]   # noqa: E731
    base = P.simular_todo((0,), ("personalizada",))
    assert clave(base) == clave(P.simular_todo((0,), ("personalizada",), modulos=nuevos))


# --- Semilla 0 sola (con margen) -------------------------------------------------------------------

def test_semilla_0_con_margen(regs0):
    reglas, pers = _f(regs0, "reglas", S6)["molestias"], _f(regs0, "personalizada", S6)["molestias"]
    assert 1 - pers / reglas >= 0.65
    assert _f(regs0, "personalizada", S6)["precision_ahora"] >= _f(regs0, "perfil", S6)["precision_ahora"] + 0.05
    assert _f(regs0, "personalizada", S6)["primera_accion"] >= 0.60
    assert _f(regs0, "personalizada")["arrepentimiento"] <= 0.05


# --- Lo que escribe /medir -------------------------------------------------------------------------

def test_medir_escribe_el_json_y_compara(tmp_path):
    import medir

    from datetime import date

    primera, _ = medir.medir_parte("personalizacion", tmp_path, date(2026, 11, 9))
    segunda, resultado = medir.medir_parte("personalizacion", tmp_path, date(2026, 11, 10))
    assert segunda.name == "personalizacion-2026-11-10.json"
    datos = json.loads(segunda.read_text(encoding="utf-8"))
    assert datos["parte"] == "personalizacion" and datos["total_criterios"] == len(datos["criterios"]) == 15
    assert set(datos["curva"]) == set(P.POLITICAS) and len(datos["curva"]["personalizada"]) == 6
    comp = resultado["comparacion"]
    assert comp["contra"] == primera.name and comp["empeora"] == []              # idéntico: determinista
    ids = {c["id"]: c for c in datos["criterios"]}
    assert ids["molestias_evitadas"]["cumple"] and ids["p1_perfil"]["cumple"] and ids["modulo_nuevo"]["cumple"]
    assert ids["p6_personalizada"]["cumple"] is False                            # honesto: hoy no sale
    import medir_personalizacion

    texto = medir_personalizacion.resumen(resultado)
    assert "Criterios:" in texto and "FALLA p6_personalizada" in texto and "Frente a personalizacion-2026-11-09" in texto


def test_medir_no_llama_a_claude(tmp_path, falso):
    import medir

    from datetime import date

    cliente = falso()
    medir.medir_parte("personalizacion", tmp_path, date(2026, 11, 9))
    assert cliente.peticiones == []
