"""Series completas (1, 2, 3, 6 y 12 meses) y `subida_recibo` (M4, motor.md §2.2 y §3.4)."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from backend import motor
from backend.escenarios import cargar
from backend.motor.enriquecer import calcular_series, serie_previa
from backend.motor.normalizar import normalizar
from backend.plataforma.tipos import Momento, Movimiento


def _mov(i, fecha, importe, concepto="RECIBO ENERGIA NORTE LUZ", canal="recibo", categoria="suministros"):
    return Movimiento(id=i, fecha=fecha, concepto=concepto, importe=Decimal(importe), canal=canal,
                      categoria=categoria)


def _mensuales(importes, desde=date(2026, 1, 12), concepto="RECIBO ENERGIA NORTE LUZ", prefijo="m"):
    salida = []
    for n, importe in enumerate(importes):
        mes = desde.month - 1 + n
        fecha = date(desde.year + mes // 12, mes % 12 + 1, desde.day)
        salida.append(_mov(f"{prefijo}{n}", fecha, importe, concepto))
    return salida


def _series(movs):
    return calcular_series([normalizar(m) for m in movs])


# --- Series completas -------------------------------------------------------------------------

@pytest.mark.parametrize("meses, periodo", [(1, 1), (2, 2), (3, 3), (6, 6), (12, 12)])
def test_series_de_cada_periodo(meses, periodo):
    fechas = [date(2023 + (1 + k * meses - 1) // 12, (k * meses) % 12 + 1, 10) for k in range(4)]
    movs = [_mov(f"p{k}", f, "-30.00", "RECIBO SEGUROS ATLAS") for k, f in enumerate(fechas)]
    [serie] = _series(movs).values()
    assert serie.serie_id == f"SEGUROS ATLAS:{periodo}m" and serie.periodo_meses == periodo
    assert serie.cargos_al_anio == 12 // periodo and serie.veces == 4 and serie.fijo


def test_serie_mensual_con_un_recibo_que_falta():
    movs = [m for m in _mensuales(["-45.00"] * 7) if m.id != "m3"]
    [serie] = _series(movs).values()
    assert serie.periodo_meses == 1 and serie.veces == 6


def test_serie_anual_de_tres_cargos_que_se_mueven_de_mes():
    movs = [_mov("a1", date(2023, 10, 28), "-210.00", "RECIBO MAPFRE SEGURO HOGAR"),
            _mov("a2", date(2024, 11, 2), "-215.00", "RECIBO MAPFRE SEGURO HOGAR"),
            _mov("a3", date(2025, 10, 30), "-220.00", "RECIBO MAPFRE SEGURO HOGAR")]
    [serie] = _series(movs).values()
    assert serie.periodo_meses == 12 and serie.cargos_al_anio == 1


def test_compras_sueltas_no_son_serie():
    movs = [_mov(f"z{k}", date(2026, 3 + k, d), imp, "COMPRA TARJETA ZARA", "tarjeta", "compras")
            for k, (d, imp) in enumerate([(3, "-25.00"), (19, "-60.00"), (8, "-41.50"), (27, "-33.00")])]
    assert _series(movs) == {}


def test_serie_previa_no_incluye_el_cargo_nuevo():
    movs = _mensuales(["-45.00"] * 5 + ["-90.00"])
    norm = [normalizar(m) for m in movs]
    previa = serie_previa(norm, norm[-1])
    assert previa is not None and previa.veces == 5 and previa.importe_habitual == Decimal("45.00")
    assert norm[-1].id not in previa.ids


# --- subida_recibo: escenarios ----------------------------------------------------------------

@pytest.fixture(scope="module")
def luz():
    return cargar.reproducir(cargar.cargar("luz-sube"), con_perfil=False)


def _subidas(momentos: list[Momento]) -> list[Momento]:
    return [m for m in momentos if m.tipo == "subida_recibo"]


def test_luz_sube_evaluacion(luz):
    r = cargar.evaluar(cargar.cargar("luz-sube"), luz)
    assert r["aciertos"] == 1 and r["omitidos"] == 0 and r["retrasos"] == [0]
    assert r["falsos_positivos"] == [] and r["trampas_violadas"] == []


def test_luz_sube_datos_y_texto(luz):
    [m] = _subidas(luz)
    assert m.fecha == date(2026, 11, 12) and m.movimientos == ["luz-11"]
    d = m.datos
    assert d["comercio"] == "ENERGIA NORTE" and d["serie_id"] == "ENERGIA NORTE:1m"
    assert d["importe_actual"] == Decimal("57.00") and d["importe_habitual"] == Decimal("45.00")
    assert d["subida_eur"] == Decimal("12.00") and d["subida_pct"] == Decimal("26.7")
    assert m.impacto_eur == Decimal("144.00")                     # 12 € x 12 recibos al año
    assert m.confianza == 0.80                                    # 5 recibos previos
    assert "ha subido" in m.explicacion
    assert "de más" not in m.explicacion and "cobrado" not in m.explicacion
    assert m.explicacion == ("El recibo de Energia Norte ha subido de 45,00 € a 57,00 € (+12,00 €, un 26,7 %): "
                             "son unos 144,00 € más al año.")


def test_subida_centimos_y_luz_variable_no_avisan():
    esc = cargar.cargar("subida-centimos")
    momentos = cargar.reproducir(esc, con_perfil=False)
    r = cargar.evaluar(esc, momentos)
    assert _subidas(momentos) == [] and r["trampas_violadas"] == [] and r["falsos_positivos"] == []


# --- subida_recibo: reglas sueltas ------------------------------------------------------------

def _dia_a_dia(movs, uid="__subida__"):
    salida: list[Momento] = []
    motor.reiniciar(uid)
    try:
        dia, fin = min(m.fecha for m in movs), max(m.fecha for m in movs)
        while dia <= fin:
            salida += motor.procesar(uid, [m for m in movs if m.fecha == dia], dia)
            dia += timedelta(days=1)
    finally:
        motor.reiniciar(uid)
    return _subidas(salida)


@pytest.mark.parametrize("nuevo, sale", [("-57.00", True), ("-47.00", False), ("-48.50", False), ("-45.00", False)])
def test_umbral_de_subida_fija(nuevo, sale):
    """+12 € avisa; +2 € no; +3,50 € (7,8 %) no llega al 8 %; igual, nada."""
    assert bool(_dia_a_dia(_mensuales(["-45.00"] * 4 + [nuevo]))) is sale


def test_hace_falta_historia_de_tres_recibos():
    assert _dia_a_dia(_mensuales(["-45.00"] * 2 + ["-90.00"])) == []


def test_subida_pequena_que_suma_al_ano():
    """Suscripción de 5,99 € que pasa a 8,49 €: +2,50 € al mes son 30 € al año (>= 12 €): avisa.
    Un recibo semestral que sube 3 € (6 € al año) no."""
    mensual = _mensuales(["-5.99"] * 4 + ["-8.49"], concepto="RECIBO STREAMFLIX")
    [m] = _dia_a_dia(mensual)
    assert m.impacto_eur == Decimal("30.00")
    semestral = [_mov(f"s{k}", date(2024 + k // 2, 1 + 6 * (k % 2), 3), "-24.00", "RECIBO SEGURO MOVIL")
                 for k in range(4)]
    semestral.append(_mov("s4", date(2026, 1, 3), "-27.00", "RECIBO SEGURO MOVIL"))
    assert _dia_a_dia(semestral) == []


def test_cargo_fuera_de_fecha_no_es_de_la_serie():
    """Un cargo del mismo comercio a mitad de mes (p. ej. un alta) no es el recibo de la serie."""
    movs = _mensuales(["-45.00"] * 5)
    movs.append(_mov("extra", date(2026, 5, 27), "-80.00"))
    assert _dia_a_dia(movs) == []


def test_no_repite_el_nuevo_nivel():
    assert len(_dia_a_dia(_mensuales(["-45.00"] * 4 + ["-57.00", "-57.00", "-57.20"]))) == 1


# --- No mira el futuro ------------------------------------------------------------------------

def test_no_mira_el_futuro(luz):
    esc = cargar.cargar("luz-sube")
    uid = "__subida_futuro__"
    momentos: list[Momento] = []
    try:
        motor.cargar_historial(uid, esc.previos(), esc.activacion)
        motor._estado(uid).agregar(list(esc.movimientos))           # el futuro, ya dentro del estado
        dia = esc.activacion + timedelta(days=1)
        while dia <= esc.hasta:
            momentos += motor.procesar(uid, esc.del_dia(dia), dia)
            dia += timedelta(days=1)
    finally:
        motor.reiniciar(uid)
    firma = lambda ms: [(m.id, m.fecha, tuple(m.movimientos), m.confianza, repr(sorted(m.datos.items())))  # noqa: E731
                        for m in ms]
    assert firma(momentos) == firma(luz)
