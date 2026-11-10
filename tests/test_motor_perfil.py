"""M9: el perfil de vida dentro del motor (motor.md §2.3 y §2.5.6): umbrales personales, grupos y contexto personal.

Sin perfil el motor es el de siempre; con perfil sube la exhaustividad (nunca baja) y el razonador añade
`impacto_relativo` y `contexto_personal` por plantilla, con cifras del código.
"""

from __future__ import annotations

import dataclasses
from datetime import date
from decimal import Decimal

import pytest

from backend.escenarios import cargar
from backend.motor import parametros, razonador
from backend.motor.detectores.base import Hallazgo
from backend.motor.detectores.gasto_compartido import grupo_del_perfil
from backend.motor.parametros import CargoDuplicado, GastoCompartido, PruebaGratuita, SubidaRecibo
from backend.plataforma.tipos import Grupo, PerfilUsuario

HOY = date(2026, 11, 9)


def perfil(**campos) -> PerfilUsuario:
    base = {"calculado": HOY, "dias_historial": 120, "ticket_tipico": Decimal("12"),
            "umbral_relevante_eur": Decimal("40")}
    return PerfilUsuario(**{**base, **campos})


def de_tipo(momentos, tipo):
    return [m for m in momentos if m.tipo == tipo]


# --- parametros.ajustar ----------------------------------------------------------------------------

def test_ajustar_sin_perfil_devuelve_el_mismo_objeto():
    for nombre, params in parametros.DEFECTO.items():
        assert parametros.ajustar(params, None) is params, nombre


def test_ajustar_con_el_perfil_de_lucia_cambia_solo_los_tres_umbrales_de_la_tabla():
    p = perfil()
    assert parametros.ajustar(GastoCompartido(), p).IMPORTE_MIN_PAGO == Decimal("24.00")       # clamp(2 x 12, 20, 60)
    assert parametros.ajustar(CargoDuplicado(), p).IMPORTE_MIN_TARJETA == Decimal("6.00")      # clamp(0,5 x 12, 5, 30)
    assert parametros.ajustar(SubidaRecibo(), p).SUBIDA_MIN_ANUAL == Decimal("12.00")          # max(12, 0,10 x 40)
    for nombre in ("series", "prueba_gratuita", "razonador"):
        assert parametros.ajustar(parametros.DEFECTO[nombre], p) is parametros.DEFECTO[nombre]
    assert parametros.ajustar(PruebaGratuita(), p) == PruebaGratuita()
    assert parametros.DEFECTO["gasto_compartido"].IMPORTE_MIN_PAGO == Decimal("30")             # el defecto no se muta


@pytest.mark.parametrize("ticket, minimo_pago, minimo_duplicado", [
    ("1", "20.00", "5.00"), ("12", "24.00", "6.00"), ("19.12", "38.24", "9.56"),
    ("45", "60.00", "22.50"), ("500", "60.00", "30.00"),
])
def test_los_umbrales_se_acotan_con_clamp(ticket, minimo_pago, minimo_duplicado):
    p = perfil(ticket_tipico=Decimal(ticket))
    assert parametros.ajustar(GastoCompartido(), p).IMPORTE_MIN_PAGO == Decimal(minimo_pago)
    assert parametros.ajustar(CargoDuplicado(), p).IMPORTE_MIN_TARJETA == Decimal(minimo_duplicado)


@pytest.mark.parametrize("umbral, esperado", [("40", "12.00"), ("100", "12.00"), ("200", "20.00"), ("500", "50.00")])
def test_la_subida_anual_minima_nunca_baja_de_12(umbral, esperado):
    p = perfil(umbral_relevante_eur=Decimal(umbral))
    assert parametros.ajustar(SubidaRecibo(), p).SUBIDA_MIN_ANUAL == Decimal(esperado)


def test_un_campo_borrado_por_el_usuario_no_cambia_nada():
    p = perfil(campos_borrados=["ticket_tipico", "umbral_relevante_eur"])
    assert parametros.ajustados(p) == parametros.DEFECTO


# --- Regresión: sin perfil (o con un perfil sin nada que usar) todo es igual ------------------------------

def firma(momentos):
    return [(m.id, m.tipo, m.fecha, m.confianza, m.movimientos, m.datos, m.impacto_eur) for m in momentos]


@pytest.mark.parametrize("id_", ["cena-lucia", "demo-lucia", "tpv-doble", "luz-sube"])
def test_sin_perfil_no_hay_contexto_personal_y_un_perfil_vacio_no_cambia_nada(id_):
    esc = cargar.cargar(id_)
    sin = cargar.reproducir(esc, con_perfil=False)
    assert all(m.impacto_relativo is None and m.contexto_personal is None for m in sin)
    vacio = {"calculado": esc.activacion, "dias_historial": 120,
             "campos_borrados": ["ticket_tipico", "umbral_relevante_eur", "grupos", "dia_cobro_nomina",
                                 "ingreso_mensual_tipico"]}
    con = cargar.reproducir(dataclasses.replace(esc, perfil=vacio), con_perfil=True)
    assert firma(con) == firma(sin)
    assert all(m.contexto_personal is None for m in con)


# --- Exhaustividad con perfil >= sin perfil ------------------------------------------------------------

def test_con_perfil_aciertan_al_menos_los_mismos_momentos_y_no_aparecen_falsos():
    from evals.medir_motor import _con_perfil

    for ficha in cargar.listar():
        esc = cargar.cargar(ficha["id"])
        sin = cargar.evaluar(esc, cargar.reproducir(esc, con_perfil=False), con_perfil=False)
        con_esc = _con_perfil(esc)
        con = cargar.evaluar(con_esc, cargar.reproducir(con_esc, con_perfil=True), con_perfil=True)
        assert con["aciertos"] >= sin["aciertos"], ficha["id"]
        assert con["omitidos"] == 0 or esc.id.startswith("fondo-"), (ficha["id"], con["detalle_omitidos"])
        assert con["trampas_violadas"] == [] and con["falsos_positivos"] == [], (ficha["id"], con)


# --- Escenarios que solo salen con perfil ----------------------------------------------------------------

def test_libreria_doble_solo_avisa_con_perfil_y_el_mismo_dia():
    esc = cargar.cargar("libreria-doble-perfil")
    assert de_tipo(cargar.reproducir(esc, con_perfil=False), "cargo_duplicado") == []
    [m] = de_tipo(cargar.reproducir(esc, con_perfil=True), "cargo_duplicado")
    assert m.fecha == date(2026, 10, 15) and m.movimientos == ["lib-d1", "lib-d2"]
    assert m.datos["importe"] == Decimal("9.90") and m.confianza == 0.70


def test_la_cena_pequena_solo_sale_con_perfil_y_pide_a_quien_falta_del_grupo():
    esc = cargar.cargar("cena-pequena-perfil")
    assert de_tipo(cargar.reproducir(esc, con_perfil=False), "gasto_compartido") == []
    [m] = de_tipo(cargar.reproducir(esc, con_perfil=True), "gasto_compartido")
    assert m.fecha == date(2026, 11, 9) and m.datos["personas_estimadas"] == 4 and m.datos["faltan"] == 1
    assert m.datos["importe_pendiente"] == Decimal("7.00")
    assert [c["contraparte"] for c in m.datos["candidatos"]] == ["SARA L"]
    assert not m.datos.get("dudoso")


@pytest.mark.parametrize("con", [False, True])
def test_la_cena_de_lucia_sale_el_9_de_noviembre_con_y_sin_perfil(con):
    esc = cargar.cargar("cena-lucia")
    esc = dataclasses.replace(esc, perfil="calcular") if con else esc
    [m] = de_tipo(cargar.reproducir(esc, con_perfil=con), "gasto_compartido")
    assert m.fecha == date(2026, 11, 9) and m.datos["faltan"] == 1
    assert [c["contraparte"] for c in m.datos["candidatos"]] == ["MARCOS R"]


def test_el_retraso_p75_del_grupo_del_perfil_manda_sobre_el_propio():
    esc = cargar.cargar("cena-lucia")
    lento = perfil(grupos=[Grupo(miembros=["LAURA M", "DANIEL P", "SARA L", "MARCOS R"], veces=3, retraso_p75_dias=4)])
    [m] = de_tipo(cargar.reproducir(dataclasses.replace(esc, perfil=lento.model_dump(mode="json")), con_perfil=True),
                  "gasto_compartido")
    assert m.fecha == date(2026, 11, 11)                    # clamp(4 + 1, 2, 5) = 5 días desde el 6/11


def test_grupo_del_perfil_elige_el_que_mas_coincide():
    familia = Grupo(miembros=["ANA T", "LUIS T"], veces=9)
    amigos = Grupo(miembros=["LAURA M", "DANIEL P", "SARA L", "MARCOS R"], veces=2)
    p = perfil(grupos=[familia, amigos])
    assert grupo_del_perfil(p, {"LAURA M", "DANIEL P"}) is amigos
    assert grupo_del_perfil(p, {"LAURA M"}) is amigos                 # grupo de <= 4: basta 1 miembro
    assert grupo_del_perfil(p, {"PEPE X"}) is None
    grande = Grupo(miembros=[f"P{i} X" for i in range(6)], veces=1)
    assert grupo_del_perfil(perfil(grupos=[grande]), {"P0 X"}) is None   # grupo de > 4: hacen falta 2
    assert grupo_del_perfil(perfil(grupos=[grande], campos_borrados=["grupos"]), {"P0 X", "P1 X"}) is None
    assert grupo_del_perfil(None, {"LAURA M"}) is None


def test_recalcular_el_perfil_a_mitad_de_streamflix_no_mata_la_prueba():
    esc = cargar.cargar("prueba-streamflix-lucia")
    sin = de_tipo(cargar.reproducir(esc, con_perfil=False), "prueba_gratuita")
    con = de_tipo(cargar.reproducir(dataclasses.replace(esc, perfil="calcular"), con_perfil=True), "prueba_gratuita")
    assert [m.fecha for m in con] == [m.fecha for m in sin] and len(sin) == 1


# --- Contexto personal -------------------------------------------------------------------------------------

def hallazgo(impacto="24.00", tipo="gasto_compartido", **datos) -> Hallazgo:
    return Hallazgo(tipo=tipo, clave="c", movimientos=["x"], confianza=0.9,
                    impacto_eur=Decimal(impacto) if impacto is not None else None, datos=datos)


def test_regla_a_saldo_y_nomina():
    p = perfil(dia_cobro_nomina=28, ingreso_mensual_tipico=Decimal("850"))
    relativo, frase = razonador.contexto_personal(hallazgo("24.00"), p, HOY, Decimal("240.00"))
    assert relativo == Decimal("0.10")
    assert frase == "Te quedan 19 días hasta la nómina y son el 10 % de lo que te queda."
    relativo, frase = razonador.contexto_personal(hallazgo("300.00"), p, HOY, Decimal("240.00"))
    assert relativo == Decimal("1.25") and frase == "Es más de lo que te queda hasta la nómina (19 días)."
    relativo, frase = razonador.contexto_personal(hallazgo("5.00"), p, date(2026, 11, 27), Decimal("500.00"))
    assert relativo == Decimal("0.01") and frase == "Te queda 1 día hasta la nómina y son el 1 % de lo que te queda."


def test_menos_del_uno_por_ciento_no_lleva_frase():
    p = perfil(dia_cobro_nomina=28)
    relativo, frase = razonador.contexto_personal(hallazgo("2.00"), p, HOY, Decimal("1000.00"))
    assert relativo == Decimal("0.00") and frase is None


def test_regla_b_ingreso_tipico_si_no_hay_saldo():
    p = perfil(dia_cobro_nomina=28, ingreso_mensual_tipico=Decimal("850"))
    relativo, frase = razonador.contexto_personal(hallazgo("85.00"), p, HOY, None)
    assert relativo == Decimal("0.10") and frase == "Es el 10 % de lo que sueles ingresar al mes."


def test_regla_c_umbral_relevante_solo_si_lo_supera():
    p = perfil()
    relativo, frase = razonador.contexto_personal(hallazgo("60.00"), p, HOY, None)
    assert relativo == Decimal("1.50")
    assert frase == "Está por encima de lo que para ti es un gasto importante (40 €)."
    assert razonador.contexto_personal(hallazgo("30.00"), p, HOY, None) == (None, None)


def test_el_cobro_cercano_a_la_nomina_se_antepone_en_pruebas_y_renovaciones():
    p = perfil(dia_cobro_nomina=28, ingreso_mensual_tipico=Decimal("850"))
    h = hallazgo("9.99", tipo="prueba_gratuita", fecha_primer_cobro="2026-11-25")
    relativo, frase = razonador.contexto_personal(h, p, HOY, None)
    assert frase == "El cobro llega 3 días antes de tu nómina. Es el 1,2 % de lo que sueles ingresar al mes."
    lejos = hallazgo("9.99", tipo="prueba_gratuita", fecha_primer_cobro="2026-11-13")
    assert "antes de tu nómina" not in razonador.contexto_personal(lejos, p, HOY, None)[1]
    sin_importe = hallazgo(None, tipo="renovacion_proxima", fecha_prevista="2026-11-27")
    assert razonador.contexto_personal(sin_importe, p, HOY, None) == (None, "El cobro llega 1 día antes de tu nómina.")
    otro_tipo = hallazgo("9.99", tipo="subida_recibo", fecha_primer_cobro="2026-11-25")
    assert "antes de tu nómina" not in (razonador.contexto_personal(otro_tipo, p, HOY, None)[1] or "")


def test_sin_perfil_dudoso_o_campo_borrado_no_hay_contexto():
    assert razonador.contexto_personal(hallazgo("24.00"), None, HOY, Decimal("240")) == (None, None)
    assert razonador.contexto_personal(hallazgo("24.00", dudoso=True), perfil(dia_cobro_nomina=28), HOY,
                                       Decimal("240")) == (None, None)
    borrado = perfil(dia_cobro_nomina=28, campos_borrados=["dia_cobro_nomina", "umbral_relevante_eur"])
    assert razonador.contexto_personal(hallazgo("24.00"), borrado, HOY, Decimal("240")) == (None, None)


def test_nomina_a_final_de_mes_corto_usa_el_ultimo_dia():
    assert razonador._dias_hasta_dia_del_mes(31, date(2026, 2, 10)) == 18        # 28 de febrero
    assert razonador._dias_hasta_dia_del_mes(15, date(2026, 12, 20)) == 26       # 15 de enero


def test_demo_lucia_con_perfil_lleva_contexto_calculado_por_el_codigo():
    esc = cargar.cargar("demo-lucia")
    momentos = cargar.reproducir(esc, con_perfil=True)
    assert len(momentos) == 4
    for m in momentos:
        assert m.impacto_relativo is not None and m.contexto_personal and m.contexto_personal.endswith(".")
        assert "hasta la nómina" in m.contexto_personal
    luz = de_tipo(momentos, "subida_recibo")[0]
    assert "%" in luz.contexto_personal and luz.impacto_relativo >= Decimal("0.05")
    sin = cargar.reproducir(esc, con_perfil=False)
    assert all(m.contexto_personal is None for m in sin)
    # las notas de Bizum nunca llegan al contexto
    assert not any("cena viernes" in (m.contexto_personal or "") for m in momentos)
