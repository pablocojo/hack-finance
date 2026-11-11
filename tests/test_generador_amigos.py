"""Generador de vidas con amigos (curva de amigos, C4). Sin red ni crédito."""

from __future__ import annotations

import re
from datetime import date, timedelta
from decimal import Decimal

import pytest
import yaml

from backend.personalizacion.simulacion.amigos.esquema import (
    DIR_VIDAS,
    Corpus,
    cargar_vidas,
    corpus_desde_dict,
    vida_desde_dict,
)
from backend.personalizacion.simulacion.amigos.generador import (
    ACTIVACION,
    FIN,
    INICIO_HISTORIAL,
    generar,
)

ESQUEMA_MD = DIR_VIDAS.parent / "ESQUEMA.md"
SIN_CHAT = Corpus(version=1, entradas=[])


def _bloque(marca: str) -> dict:
    seccion = ESQUEMA_MD.read_text(encoding="utf-8").split(marca, 1)[1]
    return yaml.safe_load(re.search(r"```yaml\n(.*?)```", seccion, re.S).group(1))


@pytest.fixture(scope="module")
def alvaro():
    return vida_desde_dict(_bloque("### 1.8"))


@pytest.fixture(scope="module")
def corpus():
    """Las tres entradas del ejemplo de ESQUEMA.md §3.4 más dos de `cobro:` y `semana` para el generador."""
    datos = _bloque("### 3.4")
    datos["entradas"] += [
        {"id": "alvaro-04", "vida": "alvaro", "tipo": "ya_pagado", "disparador": "cobro:NACHO S",
         "retraso_dias": {1: 1.0}, "plantilla": "{persona} me dio los {cuota} en mano",
         "esperado": {"herramienta": "recordar_sobre_mi", "entrada": {"tipo": "paga_en_efectivo", "persona": "{persona}"}}},
        {"id": "alvaro-05", "vida": "alvaro", "tipo": "hecho", "disparador": "semana", "retraso_dias": {0: 1.0},
         "plantilla": "{dia_semana} cenamos en {coloquial} con {personas}",
         "esperado": {"herramienta": "recordar_sobre_mi", "entrada": {"tipo": "plan_recurrente"}}},
    ]
    return corpus_desde_dict(datos)


def _con_chat_seguro(vida):
    """Copia de la vida que siempre usa el chat (para probar el relleno)."""
    datos = vida.model_dump(mode="json")
    datos["meisam"]["usa_chat"] = 1.0
    datos["meisam"]["chat_hechos"] = 1.0
    return vida_desde_dict(datos)


def test_determinista_por_semilla_y_distinto_entre_semillas(alvaro, corpus):
    a = generar(alvaro, 1, corpus).model_dump(mode="json")
    assert a == generar(alvaro, 1, corpus).model_dump(mode="json")
    assert a != generar(alvaro, 2, corpus).model_dump(mode="json")


def test_ids_estables_y_unicos(alvaro):
    v = generar(alvaro, 3, SIN_CHAT)
    ids = [m.id for m in v.movimientos_base] + [r.id_movimiento for r in v.reacciones]
    assert len(ids) == len(set(ids))
    assert all(re.fullmatch(r"sim-alvaro-3-\d+", i) for i in ids)
    assert v.prefijo == "sim-alvaro-3" and v.usuario_id("personalizada") == "sim-alvaro-3-personalizada"
    assert set(v.verdad) <= {m.id for m in v.movimientos_base}
    fechas = [m.fecha for m in v.movimientos_base]
    assert fechas == sorted(fechas)


def test_calendario_y_dinero_exacto(alvaro):
    v = generar(alvaro, 4, SIN_CHAT)
    assert all(INICIO_HISTORIAL <= m.fecha <= FIN for m in v.movimientos_base)
    assert min(m.fecha for m in v.movimientos_base) >= INICIO_HISTORIAL
    assert any(m.fecha < ACTIVACION for m in v.movimientos_base)           # hay historial previo
    assert all(isinstance(m.importe, Decimal) and m.importe == m.importe.quantize(Decimal("0.01"))
               for m in v.movimientos_base)
    assert any(m.concepto == "TRANSFERENCIA PADRES" and m.importe == Decimal("450.00") for m in v.movimientos_base)


def test_ningun_movimiento_de_efectivo_y_los_cargos_van_en_negativo(alvaro):
    for semilla in range(1, 8):
        v = generar(alvaro, semilla, SIN_CHAT)
        assert all(m.canal in ("tarjeta", "recibo", "bizum", "transferencia") for m in v.movimientos_base)
        assert all(m.importe < 0 for m in v.movimientos_base if m.canal == "tarjeta")
        assert all(m.importe > 0 for m in v.movimientos_base if m.concepto.endswith("RECIBIDO"))
        assert all(m.importe < 0 for m in v.movimientos_base if m.concepto == "BIZUM ENVIADO")


def test_efectivo_no_deja_rastro():
    """Si todos los amigos devuelven en efectivo, no hay ningún cobro en el banco ni reacción con movimiento."""
    datos = _bloque("### 1.8")
    for a in datos["amigos"].values():
        a["canal"] = {"efectivo": 1.0}
    vida = vida_desde_dict(datos)
    v = generar(vida, 5, SIN_CHAT)
    assert not [m for m in v.movimientos_base if m.concepto in ("BIZUM RECIBIDO", "TRANSFERENCIA RECIBIDA")]
    assert v.reacciones and all(r.canal == "efectivo" and r.movimiento(date(2026, 10, 20)) is None
                                for r in v.reacciones)
    pagos_efectivo = [p for p in v.verdad.values() if p.por_persona]
    assert pagos_efectivo and all(pp.canal == "efectivo" for p in pagos_efectivo for pp in p.por_persona.values())


def test_bizums_de_amigos_con_su_retraso_y_sus_cuotas(alvaro):
    """Marcos (retraso 0-1, paga solo 0.95) devuelve su cuota por Bizum 0 o 1 días después del cargo."""
    comprobados = 0
    for semilla in range(1, 6):
        v = generar(alvaro, semilla, SIN_CHAT)
        cobros = {(m.contraparte, m.fecha, m.importe) for m in v.movimientos_base if m.concepto == "BIZUM RECIBIDO"}
        for pago in v.verdad.values():
            persona = pago.por_persona.get("MARCOS L")
            if persona is None or persona.dia_pagaria_solo is None or persona.canal != "bizum":
                continue
            assert persona.retraso_dias in (0, 1)
            assert persona.dia_pagaria_solo == pago.fecha + timedelta(days=persona.retraso_dias)
            if persona.dia_pagaria_solo <= FIN and persona.pagado_por is None:
                assert ("MARCOS L", persona.dia_pagaria_solo, persona.importe_pago) in cobros
                assert persona.importe_pago == pago.cuotas["MARCOS L"]       # Marcos no redondea
                comprobados += 1
    assert comprobados > 10


def test_verdad_de_pagos_compartidos(alvaro):
    v = generar(alvaro, 6, SIN_CHAT)
    compartidos = [p for p in v.verdad.values() if p.acompanado and p.cuotas]
    assert compartidos
    for p in compartidos:
        assert set(p.cuotas) <= set(p.personas) and p.forma in ("iguales", "por_consumo")
        # el total es lo que paga el usuario y las cuotas de los amigos son parte de él
        assert sum(p.cuotas.values()) < p.importe
        assert p.n_personas >= 1 + len(p.personas)
        for clave, pp in p.por_persona.items():
            assert pp.cuota == p.cuotas[clave]
    solitarios = [p for p in v.verdad.values() if not p.acompanado]
    assert solitarios and all(not p.cuotas and p.forma is None for p in solitarios)
    assert any(p.gasto_solo_id == "cafeteria_uni" for p in solitarios)


def test_las_reacciones_son_de_pagos_que_existen_y_se_crean_sin_azar_nuevo(alvaro):
    v = generar(alvaro, 7, SIN_CHAT)
    assert v.reacciones
    for r in v.reacciones:
        assert r.pago_id in v.verdad and r.persona in v.verdad[r.pago_id].por_persona
        pp = v.verdad[r.pago_id].por_persona[r.persona]
        assert not pp.paga_solo and not pp.no_paga and pp.dia_pagaria_solo is None
        assert r.tras_pedir_dias == pp.retraso_tras_pedir_dias and r.importe == pp.importe_pago
        assert v.verdad[r.pago_id].fecha >= ACTIVACION            # en el historial nadie usa Meisam
        mov = r.movimiento(date(2026, 11, 2))
        if r.canal == "bizum":
            assert mov and mov.id == r.id_movimiento and mov.importe == r.importe and mov.contraparte == r.persona
    assert [r.model_dump() for r in v.reacciones] == [r.model_dump() for r in generar(alvaro, 7, SIN_CHAT).reacciones]


def test_el_azar_comun_no_depende_del_orden_de_las_consultas(alvaro):
    v = generar(alvaro, 8, SIN_CHAT)
    pago = next(iter(v.verdad))
    primero = v.azar(f"pregunta:{pago}:0")
    v.azar("otro:evento")
    assert v.azar(f"pregunta:{pago}:0") == primero and len(primero) == 4
    assert generar(alvaro, 8, SIN_CHAT).azar(f"pregunta:{pago}:0") == primero
    assert generar(alvaro, 9, SIN_CHAT).azar(f"pregunta:{pago}:0") != primero


def test_cambio_de_rutina_reduce_los_planes_en_examenes(alvaro):
    """Con `sabado_tasca` x0.3 y `pizzas_piso` x0.7 en las semanas 7 y 8 hay menos cargos que en 5 y 6 (de media)."""
    def cargos(semanas: tuple[int, ...]) -> int:
        total = 0
        for semilla in range(1, 25):
            v = generar(alvaro, semilla, SIN_CHAT)
            total += sum(1 for p in v.verdad.values() if p.plan_id in ("pizzas_piso", "sabado_tasca")
                         and ACTIVACION + timedelta(days=7 * (semanas[0] - 1)) <= p.fecha
                         < ACTIVACION + timedelta(days=7 * semanas[1]))
        return total
    assert cargos((7, 8)) < cargos((5, 6))


def test_el_chat_se_rellena_con_cargos_que_existen(alvaro, corpus):
    vida = _con_chat_seguro(alvaro)
    total = 0
    for semilla in range(1, 6):
        v = generar(vida, semilla, corpus)
        for m in v.chat:
            total += 1
            assert ACTIVACION <= m.fecha <= FIN
            assert not re.search(r"\{[a-z_]+\}", m.texto), m.texto
            assert not re.search(r"\{[a-z_]+\}", str(m.esperado)), m.esperado
            if m.pago_id is not None:
                pago = v.verdad[pago_id := m.pago_id]
                assert pago.pago_id == pago_id and pago.fecha <= m.fecha
                assert m.esperado["cargo"] == pago_id or m.esperado["cargo"] is None
                assert m.clave == f"{m.entrada_id}|alvaro|{semilla}|{pago_id}"
        assert [m.fecha for m in v.chat] == sorted(m.fecha for m in v.chat)
    assert total > 20


def test_chat_expande_personas_y_usa_formato_de_maquina_en_la_etiqueta(alvaro, corpus):
    vida = _con_chat_seguro(alvaro)
    visto = False
    for semilla in range(1, 15):
        for m in generar(vida, semilla, corpus).chat:
            if m.entrada_id == "alvaro-03":                    # inyección tras el sábado de la tasca
                visto = True
                pago = generar(vida, semilla, corpus).verdad[m.pago_id]
                entrada = m.esperado["entrada"]
                assert entrada["importe_total"] == f"{pago.importe:.2f}"
                assert entrada["fecha_aprox"] == pago.fecha.isoformat()
                nombres = [p["nombre"] for p in entrada["personas"]]
                assert nombres and all(n in ("Rodrigo", "Marcos", "Nacho") for n in nombres)
                assert m.esperado["deudores"] == {c: f"{v:.2f}" for c, v in pago.cuotas.items()}
                assert "900" in m.texto                          # el texto malicioso va tal cual: es un dato
                break
        if visto:
            break
    assert visto


def test_cobro_en_efectivo_dispara_chat_sin_movimiento(alvaro, corpus):
    datos = alvaro.model_dump(mode="json")
    datos["meisam"]["usa_chat"] = datos["meisam"]["chat_hechos"] = 1.0
    datos["amigos"]["NACHO S"].update(canal={"efectivo": 1.0}, prob_paga_solo=1.0, no_paga=0.0)
    vida = vida_desde_dict(datos)
    for semilla in range(1, 12):
        v = generar(vida, semilla, corpus)
        mensajes = [m for m in v.chat if m.entrada_id == "alvaro-04"]
        if mensajes:
            assert mensajes[0].pago_id in v.verdad and mensajes[0].persona == "NACHO S"
            assert not [m for m in v.movimientos_base if m.contraparte == "NACHO S" and m.concepto.endswith("RECIBIDO")]
            return
    pytest.fail("ninguna semilla produjo el mensaje de cobro en efectivo")


def test_sin_corpus_o_sin_entradas_no_hay_chat(alvaro):
    assert generar(alvaro, 1, SIN_CHAT).chat == []


def test_todas_las_vidas_del_repositorio_se_generan():
    if not any(DIR_VIDAS.glob("*.yaml")):
        pytest.skip("todavía no hay vidas en amigos/vidas/")
    for vida in cargar_vidas().values():
        a, b = generar(vida, 1, SIN_CHAT), generar(vida, 1, SIN_CHAT)
        assert a.model_dump() == b.model_dump(), vida.id
        assert a.movimientos_base, vida.id
        assert all(m.canal != "efectivo" for m in a.movimientos_base)
        assert all(p.acompanado is False or p.plan_id for p in a.verdad.values())
        assert all(r.pago_id in a.verdad for r in a.reacciones)
        assert all(sum(p.cuotas.values(), Decimal("0")) <= p.importe for p in a.verdad.values()), vida.id
