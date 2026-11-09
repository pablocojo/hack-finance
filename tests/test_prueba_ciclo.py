"""Ciclo de vida de la prueba (M8): `registrar_prueba` (lo dice el cliente) y `cerrar_prueba`
(`cancelada`, `baja_guiada`; `cobrada` y `caducada` las deduce el motor). Las fechas salen de los escenarios."""

from __future__ import annotations

import dataclasses
from datetime import date, timedelta
from decimal import Decimal

import pytest

from backend import motor
from backend.escenarios import cargar
from backend.plataforma.tipos import Movimiento


@pytest.fixture(autouse=True)
def limpio():
    for uid in ("u1", "u2"):
        motor.reiniciar(uid)
    yield
    for uid in ("u1", "u2"):
        motor.reiniciar(uid)


def mov(id, fecha, concepto, importe, **extra) -> Movimiento:
    return Movimiento(id=id, fecha=fecha, concepto=concepto, importe=Decimal(str(importe)), **extra)


def dia_a_dia(uid, movimientos, desde, hasta):
    salida, dia = [], desde
    while dia <= hasta:
        salida += motor.procesar(uid, [m for m in movimientos if m.fecha == dia], dia)
        dia += timedelta(1)
    return [m for m in salida if m.tipo == "prueba_gratuita"]


def etiqueta(esc):
    return next(e for e in esc.esperado if e["tipo"] == "prueba_gratuita")


def estado_final(esc) -> dict:
    guardado = {}
    cargar.reproducir(esc, con_perfil=False, al_terminar=lambda uid: guardado.update(motor.exportar_estado(uid)))
    return guardado


# --- prueba-cancelada ------------------------------------------------------------------------------

def test_prueba_cancelada_no_emite_ningun_momento():
    esc = cargar.cargar("prueba-cancelada")
    momentos = cargar.reproducir(esc, con_perfil=False)
    r = cargar.evaluar(esc, momentos)
    assert momentos == [] and r["trampas_violadas"] == [] and r["falsos_positivos"] == []
    assert [p["estado"] for p in estado_final(esc)["pruebas"]] == ["cancelada"]


def test_prueba_cancelada_sin_el_evento_si_habria_avisado_el_mismo_dia():
    """Es el cierre lo que evita el aviso: con el mismo historial y sin `cerrar_prueba`, avisa el 10/11."""
    cancelada = cargar.cargar("prueba-cancelada")
    dia_del_cierre = date.fromisoformat(str(cancelada.eventos[0]["fecha"]))
    sin_evento = cargar.desde_dict({**cancelada.crudo, "eventos": []})
    [m] = [m for m in cargar.reproducir(sin_evento, con_perfil=False) if m.tipo == "prueba_gratuita"]
    assert m.fecha == dia_del_cierre == date(2026, 11, 10)


def test_prueba_cancelada_un_dia_despues_del_aviso_no_deshace_el_aviso():
    cancelada = cargar.cargar("prueba-cancelada")
    aviso = date(2026, 11, 10)
    evento = {**cancelada.eventos[0], "fecha": aviso + timedelta(1)}
    esc = cargar.desde_dict({**cancelada.crudo, "eventos": [evento]})
    momentos = cargar.reproducir(esc, con_perfil=False)
    assert [m.fecha for m in momentos] == [aviso]
    assert [p["estado"] for p in estado_final(esc)["pruebas"]] == ["cancelada"]


def test_prueba_cancelada_no_vuelve_a_abrirse_con_la_misma_verificacion():
    esc = cargar.cargar("prueba-cancelada")
    assert estado_final(dataclasses.replace(esc, hasta=esc.hasta + timedelta(60)))["pruebas"][0]["estado"] == "cancelada"
    assert len(estado_final(esc)["pruebas"]) == 1


# --- baja guiada --------------------------------------------------------------------------------------

def test_prueba_baja_guiada_el_aviso_sale_y_despues_nada():
    esc = cargar.cargar("prueba-baja-guiada")
    momentos = cargar.reproducir(esc, con_perfil=False)
    r = cargar.evaluar(esc, momentos)
    assert [m.fecha for m in momentos] == [etiqueta(esc)["fecha_detectable"]]
    assert (r["aciertos"], r["omitidos"], r["falsos_positivos"], r["trampas_violadas"]) == (1, 0, [], [])


def test_prueba_baja_guiada_deja_la_prueba_en_ese_estado_hasta_que_llega_el_cobro():
    esc = cargar.cargar("prueba-baja-guiada")
    cobro = next(m.fecha for m in esc.movimientos if m.id == "bg-c1")
    antes = cargar.desde_dict({**esc.crudo, "hasta": cobro - timedelta(1)})
    [prueba] = estado_final(antes)["pruebas"]
    assert prueba["estado"] == "baja_guiada" and prueba["cerrada"] == "2026-11-11"
    assert [p["estado"] for p in estado_final(esc)["pruebas"]] == ["cobrada"]


def test_prueba_baja_guiada_antes_del_aviso_no_avisa():
    esc = cargar.cargar("prueba-baja-guiada")
    evento = {**esc.eventos[0], "fecha": etiqueta(esc)["fecha_detectable"] - timedelta(2)}
    nueva = cargar.desde_dict({**esc.crudo, "eventos": [evento]})
    assert cargar.reproducir(nueva, con_perfil=False) == []


# --- prueba-dicha-usuario ------------------------------------------------------------------------------

def test_prueba_dicha_por_el_usuario_avisa_5_dias_antes_con_30_dias_supuestos():
    esc = cargar.cargar("prueba-dicha-usuario")
    momentos = cargar.reproducir(esc, con_perfil=False)
    r = cargar.evaluar(esc, momentos)
    [m] = momentos
    assert (r["aciertos"], r["omitidos"], r["falsos_positivos"]) == (1, 0, [])
    assert m.fecha == etiqueta(esc)["fecha_detectable"] == date(2026, 11, 15)
    assert m.datos["fuente"] == "usuario" and m.datos["fuente_duracion"] == "por_defecto"
    assert m.datos["dias_hasta"] == 5 and m.datos["dias_prueba"] == 30
    assert m.movimientos == [] and "verificacion_id" not in m.datos and m.confianza == 0.9
    assert "importe_previsto" not in m.datos and m.impacto_eur is None


def test_prueba_dicha_con_los_dias_que_dice_el_cliente_avisa_3_dias_antes():
    esc = cargar.cargar("prueba-dicha-usuario")
    evento = {**esc.eventos[0], "dias": 14}
    nueva = cargar.desde_dict({**esc.crudo, "eventos": [evento]})
    [m] = cargar.reproducir(nueva, con_perfil=False)
    alta = date.fromisoformat(str(evento["fecha_alta"]))
    assert m.datos["fuente_duracion"] == "usuario" and m.datos["dias_prueba"] == 14
    assert m.fecha == alta + timedelta(14 - 3) and m.datos["dias_hasta"] == 3


def test_prueba_dicha_de_un_comercio_del_catalogo_usa_su_duracion():
    esc = cargar.cargar("prueba-dicha-usuario")
    evento = {**esc.eventos[0], "comercio": "FitApp Plus"}
    nueva = cargar.desde_dict({**esc.crudo, "eventos": [evento]})
    [m] = cargar.reproducir(nueva, con_perfil=False)
    assert m.datos["fuente_duracion"] == "catalogo" and m.datos["dias_prueba"] == 7
    assert m.datos["importe_previsto"] == Decimal("4.99") and m.fecha == date(2026, 10, 21) + timedelta(7 - 3)


def test_prueba_dicha_se_pide_a_la_cache_solo_por_el_nombre():
    esc = cargar.cargar("prueba-dicha-usuario")
    estado = estado_final(esc)          # termina el día del primer cobro: sigue abierta y sin ficha
    assert estado["pruebas"][0]["estado"] == "abierta" and estado["comercios_pendientes"] == ["YOGA ONLINE PLUS"]


def test_prueba_dicha_y_verificacion_a_menos_de_3_dias_son_la_misma_prueba():
    dicha = date(2026, 10, 18)
    verif = dicha + timedelta(2)
    movs = [mov("v", verif, "VERIFICACION TARJETA SONORA MUSIC", "0.00", canal="tarjeta")]
    motor.cargar_historial("u1", [], date(2026, 10, 1))
    motor.registrar_prueba("u1", "Sonora Music", dicha, None, dicha)
    momentos = dia_a_dia("u1", movs, date(2026, 10, 2), date(2026, 11, 20))
    [m] = momentos
    [prueba] = motor.exportar_estado("u1")["pruebas"]
    assert prueba["verificacion_id"] == "v" and prueba["fuente"] == "usuario" and m.movimientos == ["v"]
    assert m.datos["fecha_alta"] == dicha.isoformat() and m.datos["fuente"] == "usuario"
    assert m.datos["dias_prueba"] == 14 and m.datos["fuente_duracion"] == "catalogo"


def test_prueba_dicha_con_verificacion_lejana_no_se_fusiona_y_no_duplica():
    dicha = date(2026, 10, 1)
    movs = [mov("v", dicha + timedelta(20), "VERIFICACION TARJETA SONORA MUSIC", "0.00", canal="tarjeta")]
    motor.registrar_prueba("u1", "Sonora Music", dicha, None, dicha)
    dia_a_dia("u1", movs, dicha + timedelta(1), dicha + timedelta(40))
    pruebas = motor.exportar_estado("u1")["pruebas"]
    assert len(pruebas) == 1 and pruebas[0]["verificacion_id"] is None       # ya había una prueba de ese comercio


def test_prueba_la_verificacion_primero_y_el_cliente_despues_pone_los_dias():
    alta = date(2026, 10, 14)
    movs = [mov("v", alta, "VERIFICACION TARJETA STREAMFLIX", "0.00", canal="tarjeta")]
    dia_a_dia("u1", movs, date(2026, 10, 1), alta + timedelta(2))
    motor.registrar_prueba("u1", "streamflix", alta, 7, alta + timedelta(2))
    [prueba] = motor.exportar_estado("u1")["pruebas"]
    assert prueba["fuente"] == "usuario" and prueba["dias"] == 7 and prueba["verificacion_id"] == "v"
    [m] = dia_a_dia("u1", [], alta + timedelta(3), alta + timedelta(20))
    assert m.datos["dias_prueba"] == 7 and m.datos["fuente_duracion"] == "usuario" and m.fecha == alta + timedelta(4)


# --- Validación y casos límite ------------------------------------------------------------------------------

def test_prueba_registrar_valida_sus_argumentos():
    hoy = date(2026, 11, 9)
    with pytest.raises(ValueError):
        motor.registrar_prueba("u1", "X", hoy + timedelta(1), None, hoy)
    for dias in (0, -3, 366):
        with pytest.raises(ValueError):
            motor.registrar_prueba("u1", "X", hoy, dias, hoy)
    with pytest.raises(ValueError):
        motor.registrar_prueba("u1", "   ", hoy, None, hoy)
    assert motor.exportar_estado("u1") == {}


def test_prueba_registrar_dos_veces_no_duplica():
    hoy = date(2026, 11, 9)
    motor.registrar_prueba("u1", "Yoga Online Plus", hoy, None, hoy)
    motor.registrar_prueba("u1", "YOGA ONLINE PLUS", hoy, 14, hoy)
    [prueba] = motor.exportar_estado("u1")["pruebas"]
    assert prueba["dias"] == 14 and prueba["comercio"] == "YOGA ONLINE PLUS"


@pytest.mark.parametrize("motivo", ["cancelada", "baja_guiada", "cobrada", "caducada"])
def test_prueba_cerrar_admite_los_cuatro_motivos(motivo):
    hoy = date(2026, 11, 9)
    motor.registrar_prueba("u1", "Yoga Online Plus", hoy, None, hoy)
    motor.cerrar_prueba("u1", "yoga online plus", motivo, hoy)
    assert motor.exportar_estado("u1")["pruebas"][0]["estado"] == motivo


def test_prueba_cerrar_con_un_motivo_raro_falla_y_sin_prueba_no_hace_nada():
    hoy = date(2026, 11, 9)
    with pytest.raises(ValueError):
        motor.cerrar_prueba("u1", "X", "descartada", hoy)          # no está en la lista cerrada
    motor.cerrar_prueba("u1", "COMERCIO SIN PRUEBA", "cancelada", hoy)
    assert motor.exportar_estado("u1") == {}


def test_prueba_cerrar_dos_veces_no_pisa_el_primer_motivo():
    hoy = date(2026, 11, 9)
    motor.registrar_prueba("u1", "Yoga Online Plus", hoy, None, hoy)
    motor.cerrar_prueba("u1", "Yoga Online Plus", "cancelada", hoy)
    motor.cerrar_prueba("u1", "Yoga Online Plus", "caducada", hoy + timedelta(1))
    assert motor.exportar_estado("u1")["pruebas"][0]["estado"] == "cancelada"


def test_prueba_cerrada_puede_registrarse_otra_nueva_del_mismo_comercio():
    hoy = date(2026, 11, 9)
    motor.registrar_prueba("u1", "Yoga Online Plus", hoy, None, hoy)
    motor.cerrar_prueba("u1", "Yoga Online Plus", "cancelada", hoy)
    motor.registrar_prueba("u1", "Yoga Online Plus", hoy + timedelta(40), None, hoy + timedelta(40))
    assert [p["estado"] for p in motor.exportar_estado("u1")["pruebas"]] == ["cancelada", "abierta"]
