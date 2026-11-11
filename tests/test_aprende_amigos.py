"""
A1 (curva de amigos): `personalizacion/aprende_amigos.py`. Funciones puras, sin red ni crédito.

Comprueba la regla de compatibilidad (vacío o `modo="reglas"` = lo de antes, 2 días), que `fijo` no aprende, la
idempotencia, el retraso por persona (persona -> grupo -> general), el canal, el decaimiento, lo que se pasa al motor,
que «nadie me debe» no cuenta como «solo», las frases neutras, borrar y editar, los eventos desde los casos y la
velocidad (< 1 ms por evento).
"""

from __future__ import annotations

import time
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from backend.casos import DIAS_ESPERA_PAGO_POR_OTRO
from backend.personalizacion import aprende_amigos as A
from backend.plataforma.tipos import (
    AprendizajeAmigos,
    Caso,
    Contacto,
    Deudor,
    EventoAmigos,
    HabitoPersona,
    ModeloUsuario,
    PerfilUsuario,
    Grupo,
    SugerenciaReparto,
)

SABADO = date(2026, 11, 14)
JUEVES = date(2026, 11, 12)


def ev(id_: str, fecha: date = SABADO, fuente: str = "respuesta", **kw) -> EventoAmigos:
    return EventoAmigos(id=id_, fuente=fuente, fecha=fecha, **kw)


def visita(id_: str, acompanado: bool, fecha: date = SABADO, comercio: str = "LA TASCA",
           personas: list[str] | None = None, forma: str | None = None, **kw) -> EventoAmigos:
    return ev(id_, fecha=fecha, fecha_pago=fecha, comercio=comercio, tipo_comercio="restaurante",
              acompanado=acompanado, personas=personas or [], forma=forma, **kw)


def devolucion(id_: str, contraparte: str, retraso: int, canal: str = "bizum", tras_pedir: bool = False,
               fecha: date = SABADO) -> EventoAmigos:
    return ev(id_, fecha=fecha, fuente="bizum" if canal == "bizum" else "cierre", contraparte=contraparte,
              retraso_dias=retraso, canal=canal, tras_pedir=tras_pedir)


def aprender(apr: AprendizajeAmigos, eventos: list[EventoAmigos]) -> AprendizajeAmigos:
    for e in eventos:
        apr = A.aprender_evento(apr, e)
    return apr


# --- Compatibilidad: vacío o reglas = lo de antes ---------------------------------------------------------------

def test_vacio_se_comporta_como_antes():
    apr = AprendizajeAmigos()
    assert A.PARAMETROS["dias_general"] == DIAS_ESPERA_PAGO_POR_OTRO == 2
    assert A.retraso_persona(apr, "RODRIGO P") == (2, "general")
    assert A.avisar_desde(apr, "RODRIGO P", SABADO - timedelta(days=3), SABADO) == SABADO + timedelta(days=2)
    assert A.compania_para_motor(apr) is None
    assert A.canal_probable(apr, "RODRIGO P") is None
    assert A.frases_amigos(apr, {}) == []


def test_vacio_ignora_el_perfil_para_ser_identico():
    perfil = PerfilUsuario(calculado=SABADO, dias_historial=60,
                           grupos=[Grupo(miembros=["RODRIGO P", "LAURA M"], veces=4, retraso_p75_dias=4)])
    assert A.retraso_persona(AprendizajeAmigos(), "RODRIGO P", perfil=perfil) == (2, "general")


def test_reglas_ni_aprende_ni_usa():
    apr = AprendizajeAmigos(modo="reglas")
    assert A.aprender_evento(apr, devolucion("b1", "RODRIGO P", 3)) is apr
    con_datos = aprender(AprendizajeAmigos(), [devolucion("b1", "RODRIGO P", 3), devolucion("b2", "RODRIGO P", 3),
                                               visita("v1", True), visita("v2", True)])
    reglas = con_datos.model_copy(update={"modo": "reglas"})
    assert A.retraso_persona(reglas, "RODRIGO P") == (2, "general")
    assert A.avisar_desde(reglas, "RODRIGO P", SABADO, SABADO) == SABADO + timedelta(days=2)
    assert A.compania_para_motor(reglas) is None
    assert A.canal_probable(reglas, "RODRIGO P") is None
    assert A.frases_amigos(reglas, {}) == []
    assert A.decaer(reglas, SABADO + timedelta(days=90)) is reglas


def test_fijo_usa_pero_no_aprende():
    oraculo = AprendizajeAmigos(modo="fijo", personas={
        "RODRIGO P": HabitoPersona(contraparte="RODRIGO P", retrasos_dias=[2, 3, 3], retraso_p75_dias=3)})
    assert A.aprender_evento(oraculo, devolucion("b9", "RODRIGO P", 9)) is oraculo
    assert A.retraso_persona(oraculo, "RODRIGO P") == (3, "persona")
    assert A.decaer(oraculo, SABADO + timedelta(days=90)) is oraculo


# --- Aprender ------------------------------------------------------------------------------------------------------

def test_idempotente_por_id():
    e = visita("acomp:caso-1", True, personas=["LAURA M", "MARCOS R"], forma="iguales")
    una = A.aprender_evento(AprendizajeAmigos(), e)
    dos = A.aprender_evento(una, e)
    assert dos is una
    assert una.por_comercio["LA TASCA"].n == 1
    assert una.eventos_vistos == ["acomp:caso-1"]


def test_no_muta_el_original():
    modelo = ModeloUsuario(usuario_id="u1")
    nuevo = A.aprender_eventos(modelo, [visita("v1", True, personas=["LAURA M"])])
    assert modelo.aprendizaje.por_comercio == {}
    assert nuevo.aprendizaje.por_comercio["LA TASCA"].con_alguien == 1.0
    base = nuevo.aprendizaje
    otra = A.aprender_evento(base, visita("v2", True, personas=["LAURA M"]))
    assert base.por_comercio["LA TASCA"].grupos[0].veces == 1.0
    assert otra.por_comercio["LA TASCA"].grupos[0].veces == 2.0


def test_aprende_por_comercio_y_por_tipo_y_franja():
    apr = aprender(AprendizajeAmigos(), [visita("v1", True, personas=["LAURA M", "MARCOS R"], forma="iguales"),
                                         visita("v2", False, fecha=JUEVES)])
    assert set(apr.por_tipo_franja) == {"restaurante|finde", "restaurante|laborable"}
    tasca = apr.por_comercio["LA TASCA"]
    assert (tasca.con_alguien, tasca.solo, tasca.n) == (1.0, 1.0, 2)
    assert tasca.grupos[0].miembros == ["LAURA M", "MARCOS R"]
    assert tasca.grupos[0].repartos == {"iguales": 1.0}


def test_nadie_me_debe_es_acompanado_y_no_solo():
    apr = aprender(AprendizajeAmigos(), [visita(f"s{i}", True, forma="cada_uno_lo_suyo") for i in range(3)])
    a = apr.por_comercio["LA TASCA"]
    assert a.solo == 0.0 and a.con_alguien == 3.0
    assert A.sin_deuda_de(a) == 3.0
    assert A.p_acompanado_de(a) == pytest.approx(0.8)      # fue acompañado...
    assert A.p_de(a) == pytest.approx(0.2)                  # ...pero nadie le debía
    assert A.grupo_con_deuda(a) is None


def test_nadie_me_debe_con_personas_no_se_sugiere_ese_grupo():
    eventos = [visita(f"s{i}", True, personas=["MARTA G"], forma="cada_uno_lo_suyo") for i in range(3)]
    eventos += [visita(f"d{i}", True, personas=["LAURA M"], forma="iguales") for i in range(2)]
    a = aprender(AprendizajeAmigos(), eventos).por_comercio["LA TASCA"]
    assert A.grupo_con_deuda(a).miembros == ["LAURA M"]
    assert A.sin_deuda_de(a) == 3.0


def test_recortar_grupos_conserva_lo_sin_deuda():
    eventos = [visita(f"s{i}", True, personas=[f"P{i} X"], forma="cada_uno_lo_suyo") for i in range(8)]
    a = aprender(AprendizajeAmigos(), eventos).por_comercio["LA TASCA"]
    assert len([g for g in a.grupos if g.miembros]) == A.PARAMETROS["max_grupos"]
    assert A.sin_deuda_de(a) == pytest.approx(8.0)


def test_decaimiento_por_vida_media():
    apr = aprender(AprendizajeAmigos(), [visita("v1", True, personas=["LAURA M"]), visita("v2", False)])
    despues = A.decaer(apr, SABADO + timedelta(days=A.PARAMETROS["vida_media_dias"]))
    a = despues.por_comercio["LA TASCA"]
    assert a.con_alguien == pytest.approx(0.5) and a.solo == pytest.approx(0.5)
    assert a.grupos[0].veces == pytest.approx(0.5)
    assert a.n == 2                                          # las observaciones reales no se olvidan
    assert apr.por_comercio["LA TASCA"].con_alguien == 1.0   # pura
    assert A.decaer(despues, SABADO) is despues              # hacia atrás no hace nada


def test_aprender_decae_hasta_la_fecha_del_evento():
    apr = aprender(AprendizajeAmigos(), [visita("v1", False),
                                         visita("v2", False, fecha=SABADO + timedelta(days=60))])
    assert apr.por_comercio["LA TASCA"].solo == pytest.approx(1.5)


# --- Retraso por persona y avisar_desde -----------------------------------------------------------------------------

def test_retraso_persona_con_dos_observaciones():
    apr = aprender(AprendizajeAmigos(), [devolucion("b1", "RODRIGO P", 2)])
    assert A.retraso_persona(apr, "RODRIGO P") == (2, "general")     # con una sola, todavía no
    apr = aprender(apr, [devolucion("b2", "RODRIGO P", 3)])
    assert apr.personas["RODRIGO P"].retraso_p75_dias == 3
    assert A.retraso_persona(apr, "RODRIGO P") == (3, "persona")


def test_retraso_del_grupo_y_del_perfil():
    apr = aprender(AprendizajeAmigos(), [devolucion("b1", "LAURA M", 1), devolucion("b2", "LAURA M", 4)])
    assert A.retraso_persona(apr, "MARCOS R", grupo=["LAURA M", "MARCOS R"]) == (4, "grupo")
    assert A.retraso_persona(apr, "MARCOS R") == (2, "general")
    perfil = PerfilUsuario(calculado=SABADO, dias_historial=60,
                           grupos=[Grupo(miembros=["MARCOS R", "ANA L"], veces=3, retraso_p75_dias=5)])
    assert A.retraso_persona(apr, "MARCOS R", perfil=perfil) == (5, "grupo")


def test_retraso_tras_pedir_no_cuenta_para_el_primer_recordatorio():
    apr = aprender(AprendizajeAmigos(), [devolucion("b1", "SARA T", 1, tras_pedir=True),
                                         devolucion("b2", "SARA T", 0, tras_pedir=True)])
    h = apr.personas["SARA T"]
    assert h.retrasos_tras_pedir == [1, 0] and h.retrasos_dias == []
    assert h.paga_tras_pedir == 2 and h.retraso_p75_dias is None
    assert A.retraso_persona(apr, "SARA T") == (2, "general")


def test_avisar_desde_respeta_el_retraso_de_cada_uno():
    """Un amigo con p75 = 3 no recibe recordatorio antes del día 3 (se recuerda el día siguiente si no ha pagado)."""
    apr = aprender(AprendizajeAmigos(), [devolucion("b1", "RODRIGO P", 2), devolucion("b2", "RODRIGO P", 3)])
    pago = JUEVES
    assert A.avisar_desde(apr, "RODRIGO P", pago, hoy=pago) == pago + timedelta(days=4)
    # caso apuntado tarde: nunca antes de mañana
    assert A.avisar_desde(apr, "RODRIGO P", pago, hoy=pago + timedelta(days=6)) == pago + timedelta(days=7)
    # alguien desconocido: lo de siempre, 2 días desde que se apunta
    assert A.avisar_desde(apr, "ANA L", pago, hoy=pago + timedelta(days=1)) == pago + timedelta(days=3)


def test_retraso_con_tope():
    apr = aprender(AprendizajeAmigos(), [devolucion("b1", "LENTO X", 20), devolucion("b2", "LENTO X", 25)])
    assert A.retraso_persona(apr, "LENTO X") == (A.PARAMETROS["dias_max_persona"], "persona")


# --- Canal ---------------------------------------------------------------------------------------------------------

def test_canal_probable():
    apr = aprender(AprendizajeAmigos(), [devolucion("c1", "PILAR R", 0, "efectivo")])
    assert A.canal_probable(apr, "PILAR R") is None                     # una vez no basta
    apr = aprender(apr, [devolucion("c2", "PILAR R", 1, "efectivo"), devolucion("c3", "PILAR R", 1, "bizum")])
    assert A.canal_probable(apr, "PILAR R") == "efectivo"
    empate = aprender(AprendizajeAmigos(), [devolucion("d1", "LUIS P", 0, "efectivo"),
                                            devolucion("d2", "LUIS P", 0, "bizum")])
    assert A.canal_probable(empate, "LUIS P") is None                   # ante la duda, nada


# --- Lo que se pasa al motor -----------------------------------------------------------------------------------------

def test_compania_para_motor():
    apr = aprender(AprendizajeAmigos(), [visita(f"v{i}", True, personas=["LAURA M"], forma="iguales")
                                         for i in range(3)])
    compania = A.compania_para_motor(apr)
    assert compania == {"c:LA TASCA": 0.8, "t:restaurante|finde": 0.8}
    poco = aprender(AprendizajeAmigos(), [visita("v1", True)])
    assert A.compania_para_motor(poco) is None                          # sin evidencia suficiente, como antes
    sin_deuda = aprender(AprendizajeAmigos(), [visita(f"s{i}", True, forma="cada_uno_lo_suyo") for i in range(3)])
    assert A.compania_para_motor(sin_deuda)["c:LA TASCA"] == 0.2        # acompañado, pero nadie le debe


# --- Lo que he aprendido de ti --------------------------------------------------------------------------------------

PALABRAS_DE_JUICIO = ("moros", "fiar", "fiable", "tarde", "olvid", "mal pagador", "deudor", "puntua", "nunca paga",
                      "jeta", "cara", "gorr", "tacañ", "irresponsable", "malo", "mala")


def test_frases_neutras_por_persona_y_por_sitio():
    contactos = {"RODRIGO P": Contacto(contraparte="RODRIGO P", nombre="Rodrigo P.")}
    apr = aprender(AprendizajeAmigos(), [
        devolucion("b1", "RODRIGO P", 2), devolucion("b2", "RODRIGO P", 3),
        devolucion("c1", "PILAR R", 0, "efectivo"), devolucion("c2", "PILAR R", 1, "efectivo"),
        *[visita(f"v{i}", True, personas=["LAURA M", "MARCOS R"], forma="iguales") for i in range(3)],
        *[visita(f"s{i}", False, comercio="CAFETERIA UNI", fecha=JUEVES) for i in range(3)],
    ])
    frases = {f.campo: f.texto for f in A.frases_amigos(apr, contactos)}
    assert frases["amigos:RODRIGO P"].startswith("Rodrigo P. suele devolvértelo a los 2 o 3 días.")
    assert frases["amigos:PILAR R"] == ("Pilar R. suele pagarte en efectivo, el mismo día o al siguiente. "
                                        "No te lo recuerdo antes de ese plazo.")
    assert frases["sitios:comercio:LA TASCA"] == ("En La Tasca sueles pagar tú por más gente, casi siempre con "
                                                  "Laura M. y Marcos R., y repartís a partes iguales.")
    assert frases["sitios:comercio:CAFETERIA UNI"] == "En Cafeteria Uni sueles ir solo: no te pregunto."
    for texto in frases.values():
        assert not any(p in texto.lower() for p in PALABRAS_DE_JUICIO), texto


def test_frase_de_sitio_donde_cada_uno_paga_lo_suyo():
    apr = aprender(AprendizajeAmigos(), [visita(f"s{i}", True, forma="cada_uno_lo_suyo") for i in range(3)])
    frases = {f.campo: f.texto for f in A.frases_amigos(apr, {})}
    assert frases["sitios:comercio:LA TASCA"] == "En La Tasca cada uno suele pagar lo suyo: no te pregunto."


def test_borrar_persona_y_sitio():
    apr = aprender(AprendizajeAmigos(), [
        devolucion("b1", "RODRIGO P", 2), devolucion("b2", "RODRIGO P", 3),
        *[visita(f"v{i}", True, personas=["RODRIGO P", "LAURA M"], forma="iguales") for i in range(2)],
    ])
    sin = A.borrar_persona(apr, "RODRIGO P")
    assert "RODRIGO P" not in sin.personas
    assert all("RODRIGO P" not in g.miembros for a in sin.por_comercio.values() for g in a.grupos)
    assert sin.por_comercio["LA TASCA"].grupos[0].miembros == ["LAURA M"]
    assert "RODRIGO P" in apr.personas                                  # pura
    assert A.retraso_persona(sin, "RODRIGO P") == (2, "general")
    otra = A.borrar_sitio(apr, "comercio:LA TASCA")
    assert "LA TASCA" not in otra.por_comercio and "restaurante|finde" in otra.por_tipo_franja
    otra = A.borrar_sitio(otra, "sitios:tipo:restaurante|finde")
    assert otra.por_tipo_franja == {}
    with pytest.raises(KeyError):
        A.borrar_sitio(otra, "comercio:NO EXISTE")


def test_editar_persona_lo_fija():
    apr = A.editar_persona(AprendizajeAmigos(), "RODRIGO P", "retraso_dias", 5)
    assert A.retraso_persona(apr, "RODRIGO P") == (5, "persona")
    apr = aprender(apr, [devolucion("b1", "RODRIGO P", 1), devolucion("b2", "RODRIGO P", 1)])
    assert A.retraso_persona(apr, "RODRIGO P") == (5, "persona")      # el código no pisa lo que dijo el usuario
    apr = A.editar_persona(apr, "RODRIGO P", "canal", "efectivo")
    assert A.canal_probable(apr, "RODRIGO P") == "efectivo"
    apr = aprender(apr, [devolucion("b3", "RODRIGO P", 1), devolucion("b4", "RODRIGO P", 1)])
    assert A.canal_probable(apr, "RODRIGO P") == "efectivo"
    assert "me lo dijiste tú" in {f.campo: f.texto for f in A.frases_amigos(apr, {})}["amigos:RODRIGO P"]
    for campo, valor in (("retraso_dias", -1), ("retraso_dias", "tres"), ("retraso_dias", True),
                         ("canal", "paypal"), ("puntuacion", 3)):
        with pytest.raises(ValueError):
            A.editar_persona(apr, "RODRIGO P", campo, valor)


# --- Eventos desde los casos -------------------------------------------------------------------------------------------

def caso_individual(**kw) -> Caso:
    datos = {"id": "caso-1", "usuario_id": "u1", "escenario": "pago_individual", "estado": "abierto",
             "creado": SABADO + timedelta(days=3), "aviso": "resumen",
             "hechos": {"comercio": "La Tasca", "tipo_comercio": "restaurante", "fecha": SABADO.isoformat(),
                        "importe_total": "48.00"}}
    datos.update(kw)
    return Caso(**datos)


def test_eventos_iba_solo_y_nadie_me_debe():
    antes = caso_individual(pregunta_nivel=1)
    solo = caso_individual(estado="descartado")
    [e] = A.eventos_de_caso(antes, solo, "respuesta", SABADO + timedelta(days=4))
    assert (e.acompanado, e.comercio, e.franja, e.tipo_comercio, e.nivel) == (False, "LA TASCA", "finde",
                                                                              "restaurante", 1)
    sin_deuda = caso_individual(estado="descartado", hechos={**solo.hechos, "sin_deuda": True})
    [e] = A.eventos_de_caso(antes, sin_deuda, "llamada", SABADO + timedelta(days=4))
    assert e.acompanado is True and e.forma == "cada_uno_lo_suyo" and e.personas == []


def test_eventos_con_personas_y_sugerencia_aceptada():
    sug = SugerenciaReparto(personas=["LAURA M", "MARCOS R"], forma="iguales",
                            cuotas={"LAURA M": Decimal("16.00"), "MARCOS R": Decimal("16.00")}, confianza=0.8)
    antes = caso_individual(pregunta_nivel=3, sugerencia=sug)
    despues = caso_individual(escenario="gasto_compartido", deudores=[
        Deudor(contraparte="LAURA M", cuota=Decimal("16.00")), Deudor(contraparte="MARCOS R", cuota=Decimal("16.00"))])
    [e] = A.eventos_de_caso(antes, despues, "respuesta", SABADO + timedelta(days=3))
    assert e.id == "acomp:caso-1" and e.acompanado is True
    assert e.personas == ["LAURA M", "MARCOS R"] and e.forma == "iguales"
    assert e.nivel == 3 and e.sugerencia_aceptada is True
    otro = caso_individual(escenario="pago_por_otro", deudores=[Deudor(contraparte="LAURA M", cuota=Decimal("24"))])
    [e] = A.eventos_de_caso(antes, otro, "respuesta", SABADO + timedelta(days=3))
    assert e.sugerencia_aceptada is False


def test_eventos_de_devolucion_sin_contar_dos_veces():
    abierto = caso_individual(escenario="gasto_compartido", deudores=[
        Deudor(contraparte="PILAR R", cuota=Decimal("12")), Deudor(contraparte="RODRIGO P", cuota=Decimal("12"))])
    en_efectivo = abierto.model_copy(deep=True)
    en_efectivo.deudores[0].estado, en_efectivo.deudores[0].saldada = "saldada", SABADO + timedelta(days=2)
    en_efectivo.deudores[0].via_saldado = "efectivo"
    eventos = A.eventos_de_caso(abierto, en_efectivo, "cierre", SABADO + timedelta(days=2))
    [e] = [x for x in eventos if x.contraparte]
    assert (e.canal, e.retraso_dias, e.tras_pedir, e.fuente) == ("efectivo", 2, False, "cierre")

    pedido = abierto.deudores[1].model_copy(update={"estado": "pedida", "pedida": SABADO + timedelta(days=4)})
    pagado = pedido.model_copy(update={"estado": "saldada", "saldada": SABADO + timedelta(days=5),
                                       "movimiento_pago": "m-9"})
    [b] = A.eventos_de_bizum(abierto, pedido, pagado, SABADO + timedelta(days=5))
    assert (b.canal, b.retraso_dias, b.tras_pedir, b.id) == ("bizum", 1, True, "pago:caso-1:RODRIGO P")
    assert A.eventos_de_bizum(abierto, pagado, pagado, SABADO + timedelta(days=6)) == []
    apr = aprender(AprendizajeAmigos(), [b, b])
    assert apr.personas["RODRIGO P"].paga_tras_pedir == 1


def test_ignorada():
    [e] = A.eventos_de_caso(None, caso_individual(pregunta_nivel=1), "ignorada", SABADO + timedelta(days=5))
    assert e.fuente == "ignorada" and e.acompanado is None and e.nivel == 1
    apr = aprender(AprendizajeAmigos(), [e])
    assert apr.por_comercio["LA TASCA"].ignoradas == 1 and apr.por_comercio["LA TASCA"].n == 0
    apr = aprender(apr, [visita("v1", False)])
    assert apr.por_comercio["LA TASCA"].ignoradas == 0                  # contestar reinicia la cuenta


# --- Generales -------------------------------------------------------------------------------------------------------

def test_franja_de():
    assert [A.franja_de(date(2026, 11, d)) for d in range(9, 16)] == [
        "laborable", "laborable", "laborable", "laborable", "viernes", "finde", "finde"]


def test_menos_de_un_milisegundo_por_evento():
    apr = AprendizajeAmigos()
    eventos = []
    for i in range(600):
        dia = SABADO + timedelta(days=i // 3)
        if i % 3 == 2:
            eventos.append(devolucion(f"b{i}", f"AMIGO{i % 7} X", i % 5, fecha=dia))
        else:
            eventos.append(visita(f"v{i}", i % 4 != 0, fecha=dia, comercio=f"SITIO {i % 25}",
                                  personas=[f"AMIGO{i % 7} X", f"AMIGO{(i + 1) % 7} X"], forma="iguales"))
    inicio = time.perf_counter()
    for e in eventos:
        apr = A.aprender_evento(apr, e)
    media_ms = (time.perf_counter() - inicio) * 1000 / len(eventos)
    assert media_ms < 1.0, f"{media_ms:.3f} ms por evento"
    assert len(apr.eventos_vistos) == A.PARAMETROS["max_eventos_vistos"]


def test_no_importa_el_simulador():
    raiz = Path(__file__).resolve().parents[1] / "backend" / "personalizacion"
    for nombre in ("aprende_amigos.py", "escalera.py"):
        lineas = (raiz / nombre).read_text(encoding="utf-8").splitlines()
        assert not any("simulacion" in l for l in lineas if l.lstrip().startswith(("import", "from"))), nombre
