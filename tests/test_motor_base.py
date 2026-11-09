"""Motor base (E2): normalización, enriquecimiento, estado, procesar en línea, parámetros y razonador."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal

import pytest

from backend import motor
from backend.datos.sinteticos import generar_movimientos
from backend.motor import detectores, parametros, razonador
from backend.motor.detectores.base import Hallazgo
from backend.motor.normalizar import clave_contraparte, normalizar
from backend.plataforma.tipos import Momento, Movimiento, PerfilUsuario

HOY = date(2026, 11, 9)


@pytest.fixture(autouse=True)
def limpio():
    for uid in ("u1", "u2", "lucia"):
        motor.reiniciar(uid)
    yield
    for uid in ("u1", "u2", "lucia"):
        motor.reiniciar(uid)


def mov(id, fecha, concepto, importe, **extra) -> Movimiento:
    return Movimiento(id=id, fecha=fecha, concepto=concepto, importe=Decimal(str(importe)), **extra)


def cena(dia=date(2026, 11, 6)) -> list[Movimiento]:
    return [
        mov("c1", dia, "COMPRA TARJETA LA TASCA MADRID", "-120.00", comercio="LA TASCA", canal="tarjeta"),
        mov("b1", dia, "BIZUM RECIBIDO", "24.00", contraparte="Laura Martinez Garcia", canal="bizum", nota="cena"),
        mov("b2", dia + timedelta(1), "BIZUM RECIBIDO", "24.00", contraparte="Daniel Perez Ruiz", canal="bizum"),
        mov("b3", dia + timedelta(2), "BIZUM RECIBIDO", "24.00", contraparte="Sara Lopez Gil", canal="bizum"),
    ]


def dia_a_dia(uid, movimientos, desde, hasta, perfil=None) -> list[Momento]:
    salida, dia = [], desde
    while dia <= hasta:
        salida += motor.procesar(uid, [m for m in movimientos if m.fecha == dia], dia, perfil)
        dia += timedelta(1)
    return salida


# --- Normalización ---------------------------------------------------------------------------

@pytest.mark.parametrize("nombre, clave", [
    ("Laura Martinez G", "LAURA M"),
    ("LAURA MARTINEZ GARCIA", "LAURA M"),
    ("Laura Martínez García", "LAURA M"),
    ("Marcos Ruiz Sanz", "MARCOS R"),
    ("MARCOS R", "MARCOS R"),
    ("Sara de la Fuente", "SARA F"),
    ("Daniel", "DANIEL"),
    (None, None),
    ("  ", None),
])
def test_clave_contraparte(nombre, clave):
    assert clave_contraparte(nombre) == clave


def test_verificacion_de_cero_euros():
    m = normalizar(mov("v1", HOY, "VERIFICACION TARJETA STREAMFLIX", "0.00", comercio="STREAMFLIX"))
    assert m.tipo_operacion == "verificacion" and "verificacion" in m.etiquetas
    assert m.canal == "tarjeta" and m.comercio_normalizado == "STREAMFLIX"
    autorizacion = normalizar(mov("v2", HOY, "AUTORIZACION SONORA MUSIC", "-1.00"))
    assert autorizacion.tipo_operacion == "verificacion"
    assert normalizar(mov("v3", HOY, "AUTORIZACION HOTEL", "-150.00")).tipo_operacion == "cargo"


def test_tipo_operacion_y_canal_deducidos():
    assert normalizar(mov("d1", HOY, "DEVOLUCION COMPRA ZARA", "59.95")).tipo_operacion == "devolucion"
    assert normalizar(mov("r1", HOY, "RECIBO IBERDROLA CLIENTES", "-60")).canal == "recibo"
    assert normalizar(mov("b1", HOY, "BIZUM RECIBIDO", "10")).canal == "bizum"
    assert normalizar(mov("t1", HOY, "TRANSFERENCIA EMITIDA ALQUILER", "-380")).canal == "transferencia"
    assert normalizar(mov("k1", HOY, "RETIRADA CAJERO", "-20")).canal == "cajero"
    # lo que trae el banco no se toca
    assert normalizar(mov("x1", HOY, "COMPRA", "0", tipo_operacion="cargo")).tipo_operacion == "cargo"


@pytest.mark.parametrize("concepto, comercio, esperado, etiqueta", [
    ("COMPRA TARJETA LA TASCA MADRID", None, "LA TASCA", None),
    ("COMPRA TARJETA X", "La Tasca", "LA TASCA", None),
    ("RECIBO NETFLIX.COM", None, "NETFLIX", None),
    ("COMPRA ONLINE AMZN MKTP ES*1234", None, "AMAZON", None),
    ("COMPRA TARJETA PAYPAL *STREAMFLIX", None, "STREAMFLIX", "pasarela"),
    ("COMPRA TARJETA APPLE.COM/BILL", None, "APPLE", "pasarela"),
    ("COMPRA TARJETA SUMUP *JUAN PEREZ", None, "SUMUP *JUAN PEREZ", "posible_persona"),
    ("COMPRA TARJETA CAFETERÍA FACULTAD", None, "CAFETERIA FACULTAD", None),
])
def test_comercio_normalizado(concepto, comercio, esperado, etiqueta):
    m = normalizar(mov("m", HOY, concepto, "-10", comercio=comercio))
    assert m.comercio_normalizado == esperado
    if etiqueta:
        assert etiqueta in m.etiquetas


def test_bizum_lleva_contraparte_normalizada_y_categoria():
    b = normalizar(mov("b", HOY, "BIZUM RECIBIDO", "24", contraparte="Laura Martinez G", nota="cena"))
    assert b.contraparte_normalizada == "LAURA M" and b.comercio_normalizado is None
    tasca = normalizar(mov("c", HOY, "COMPRA TARJETA LA TASCA MADRID", "-120"))
    assert tasca.categoria == "restaurantes"


# --- Enriquecimiento -------------------------------------------------------------------------

def test_enriquecer_es_pura_y_marca_series():
    movs = [mov(f"n{i}", date(2026, 6 + i, 15), "RECIBO NETFLIX.COM", "-7.99") for i in range(4)]
    movs.append(mov("z1", date(2026, 9, 20), "COMPRA TARJETA ZARA", "-30"))
    copia = [m.model_copy() for m in movs]
    enr = motor.enriquecer(movs)
    assert [m.model_dump() for m in movs] == [m.model_dump() for m in copia]   # no muta la entrada
    assert [e.id for e in enr] == [m.id for m in movs]
    assert {e.serie_id for e in enr[:4]} == {"NETFLIX:1m"}
    assert all("cargo_serie" in e.etiquetas for e in enr[:4])
    assert enr[4].serie_id is None and "comercio_nuevo" in enr[4].etiquetas
    assert "comercio_nuevo" in enr[0].etiquetas and "comercio_nuevo" not in enr[1].etiquetas
    assert motor.enriquecer(movs) == enr                                     # determinista


def test_series_del_fondo_sintetico():
    crudos = generar_movimientos("estudiante", meses=6, semilla=7, hasta=date(2026, 11, 16), anomalias=False)
    enr = motor.enriquecer([Movimiento.model_validate(m) for m in crudos])
    series = {e.serie_id for e in enr if e.serie_id}
    for esperada in ("NETFLIX:1m", "SPOTIFY:1m", "GIMNASIO FITUP:1m", "DIGI:1m"):
        assert esperada in series
    assert not any(s.startswith(("MERCADONA", "GLOVO", "BAR LA PLAZA")) for s in series)


def test_sinteticos_sin_anomalias_y_por_defecto_igual():
    hasta = date(2026, 11, 7)
    por_defecto = generar_movimientos("familia", meses=6, semilla=42, hasta=hasta)
    assert por_defecto == generar_movimientos("familia", meses=6, semilla=42, hasta=hasta, anomalias=True)
    assert any(m["comercio"] == "TECHSHOP-EU" for m in por_defecto)
    limpios = generar_movimientos("familia", meses=6, semilla=42, hasta=hasta, anomalias=False)
    assert not any(m["comercio"] in ("TECHSHOP-EU", "TALLER AUTOFIX") for m in limpios)


# --- procesar, estado y razonador ------------------------------------------------------------

def test_procesar_rechaza_el_futuro():
    with pytest.raises(ValueError):
        motor.procesar("u1", [mov("f", HOY + timedelta(1), "COMPRA", "-5")], HOY)
    with pytest.raises(ValueError):
        motor.cargar_historial("u1", [mov("f", HOY + timedelta(1), "COMPRA", "-5")], HOY)


def test_procesar_sin_perfil_detecta_la_cena_y_es_idempotente():
    movs = cena()
    momentos = dia_a_dia("u1", movs, date(2026, 11, 6), date(2026, 11, 16))
    assert [(m.tipo, m.fecha) for m in momentos] == [("gasto_compartido", date(2026, 11, 9))]
    momento = momentos[0]
    assert momento.movimientos == ["c1", "b1", "b2", "b3"]
    assert momento.id.startswith("mom-gasto_compartido-") and len(momento.id) == len("mom-gasto_compartido-") + 10
    assert momento.detector == "gasto_compartido" and momento.version.startswith("motor-0.2/gasto_compartido-")
    assert momento.explicacion == (
        "Pagaste 120,00 € en La Tasca y te han devuelto 72,00 € de 3 personas; falta 1 (24,00 €).")
    # reprocesar el mismo día con los mismos movimientos no repite nada ni duplica el historial
    assert motor.procesar("u1", movs, date(2026, 11, 9)) == []
    estado = motor.exportar_estado("u1")
    assert len(estado["movimientos"]) == 4


def test_ningun_movimiento_futuro_cambia_lo_emitido():
    movs = cena()
    a = dia_a_dia("u1", movs, date(2026, 11, 6), date(2026, 11, 9))
    # Marcos paga el 10 y ese Bizum ya está en el estado (entra por detrás): lo emitido hasta el 9 no cambia
    futuro = mov("b4", date(2026, 11, 10), "BIZUM RECIBIDO", "24", contraparte="Marcos Ruiz Sanz", canal="bizum")
    motor.importar_estado("u2", {"movimientos": [futuro.model_dump(mode="json")]})
    b = dia_a_dia("u2", movs, date(2026, 11, 6), date(2026, 11, 9))
    assert [m.model_dump(exclude={"usuario_id"}) for m in a] == [m.model_dump(exclude={"usuario_id"}) for m in b]
    assert motor.procesar("u2", [], date(2026, 11, 10)) == []          # el 10 ya no falta nadie


def test_exportar_importar_y_reiniciar():
    movs = cena()
    dia_a_dia("u1", movs, date(2026, 11, 6), date(2026, 11, 8))
    motor.registrar_prueba("u1", "Streamflix", date(2026, 10, 14), 30, date(2026, 11, 8))
    estado = motor.exportar_estado("u1")
    texto = json.dumps(estado)                       # JSON puro (Decimal y fechas como cadena)
    motor.reiniciar("u1")
    assert motor.exportar_estado("u1") == {}
    motor.importar_estado("u2", json.loads(texto))
    assert motor.exportar_estado("u2")["pruebas"][0]["comercio"] == "STREAMFLIX"
    assert [m.tipo for m in motor.procesar("u2", [], date(2026, 11, 9))] == ["gasto_compartido"]
    motor.importar_estado("u2", {})
    assert motor.exportar_estado("u2") == {}


def test_registrar_y_cerrar_prueba():
    with pytest.raises(ValueError):
        motor.registrar_prueba("u1", "STREAMFLIX", HOY + timedelta(1), None, HOY)
    motor.registrar_prueba("u1", "Streamflix", date(2026, 10, 14), None, HOY)
    motor.cerrar_prueba("u1", "STREAMFLIX", "baja_guiada", HOY)
    prueba = motor.exportar_estado("u1")["pruebas"][0]
    assert prueba["estado"] == "baja_guiada" and prueba["fuente"] == "usuario" and prueba["cerrada"] == HOY.isoformat()
    assert motor.comercios_pendientes("u1") == []


def test_cargar_historial_no_emite():
    motor.cargar_historial("u1", cena(), date(2026, 11, 9))
    assert motor.exportar_estado("u1")["claves_emitidas"] == {}
    assert len(motor.exportar_estado("u1")["movimientos"]) == 4


def test_parametros_sin_perfil_son_los_de_defecto():
    for nombre, params in parametros.DEFECTO.items():
        assert parametros.ajustar(params, None) is params, nombre
    assert parametros.ajustar({"x": 1}, None) == {"x": 1}
    assert parametros.DEFECTO["gasto_compartido"].IMPORTE_MIN_PAGO == Decimal("30")
    assert parametros.ajustados(None) == parametros.DEFECTO


def test_registro_de_detectores():
    assert "gasto_compartido" in detectores.REGISTRO
    assert set(detectores.REGISTRO) <= set(__import__("backend.plataforma.tipos", fromlist=["x"]).TIPOS_MOMENTO)


def _hallazgo(tipo="gasto_compartido", clave="p1", confianza=0.9, ids=("c1",), impacto="24.00"):
    return Hallazgo(tipo=tipo, clave=clave, movimientos=list(ids), confianza=confianza,
                    impacto_eur=Decimal(impacto) if impacto else None,
                    datos={"comercio": "LA TASCA", "importe_total": Decimal("120.00"), "reembolsos": [{}, {}, {}],
                           "faltan": 1, "importe_pendiente": Decimal("24.00")})


def test_razonador_clave_estable_filtro_y_solapes():
    fechas = {"c1": date(2026, 11, 6), "c2": date(2026, 11, 7)}
    emitidas: dict[str, str] = {}
    params = parametros.DEFECTO["razonador"]
    flojo = _hallazgo(clave="p2", confianza=0.4, ids=("c2",))
    momentos = razonador.razonar("u1", [_hallazgo(), flojo], emitidas, HOY, fechas, params)
    assert len(momentos) == 1 and momentos[0].confianza == 0.9
    otra_vez = razonador.razonar("u1", [_hallazgo()], dict(emitidas), HOY, fechas, params)
    assert otra_vez == []                                        # misma clave: no se repite
    nuevo = razonador.razonar("u2", [_hallazgo()], {}, HOY, fechas, params)
    assert nuevo[0].id == momentos[0].id                          # id estable para la misma clave
    # solape: el mismo movimiento en dos momentos -> gana el de más prioridad
    duplicado = _hallazgo(tipo="cargo_duplicado", clave="d1", ids=("c1",), confianza=0.7)
    duplicado.datos = {"comercio": "LA TASCA", "importe": Decimal("120.00")}
    ambos = razonador.razonar("u3", [_hallazgo(), duplicado], {}, HOY, fechas, params)
    assert [m.tipo for m in ambos] == ["cargo_duplicado"]
    # el filtro se puede cambiar por parámetro
    laxo = replace(params, CONFIANZA_MIN=0.3)
    assert len(razonador.razonar("u4", [flojo], {}, HOY, fechas, laxo)) == 1


def test_formato_euros():
    assert razonador.eur(Decimal("1234.5")) == "1.234,50 €"
    assert razonador.eur(Decimal("24")) == "24,00 €"


def test_rendimiento_seis_meses_dia_a_dia():
    import time

    crudos = generar_movimientos("familia", meses=6, semilla=42, hasta=date(2026, 11, 7), anomalias=False)
    movs = [Movimiento.model_validate(m) for m in crudos]
    inicio = time.perf_counter()
    dia_a_dia("u1", movs, movs[0].fecha, movs[-1].fecha)
    assert time.perf_counter() - inicio < 2.0


def test_perfil_no_rompe_procesar():
    perfil = PerfilUsuario(calculado=HOY, dias_historial=90)
    momentos = dia_a_dia("u1", cena(), date(2026, 11, 6), date(2026, 11, 12), perfil)
    assert [m.fecha for m in momentos] == [date(2026, 11, 9)]
