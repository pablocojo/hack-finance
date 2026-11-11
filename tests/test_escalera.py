"""
A2 (curva de amigos): `personalizacion/escalera.py`. Puras, sin red ni crédito.

Sin datos o con `modo="reglas"`, lo de antes (señal media -> 1, débil -> 0); «iba solo» y «nadie me debe» repetidos
-> 0 con motivos distintos; dos ignoradas bajan un nivel; nivel 3 solo con confianza alta e importe >= umbral; cuotas
con `Decimal` y el usuario incluido; nada por nombre de comercio; < 1 ms. Al final, un usuario simulado con
preferencias ocultas y semilla fija: la hipótesis medible de la escalera.
"""

from __future__ import annotations

import random
import time
from datetime import date, timedelta
from decimal import Decimal

import pytest

from backend.personalizacion import aprende_amigos as A
from backend.personalizacion.escalera import nivel_pregunta, sugerir
from backend.plataforma.tipos import AprendizajeAmigos, EventoAmigos

SABADO = date(2026, 11, 14)
JUEVES = date(2026, 11, 12)
UMBRAL = Decimal("20")
GRUPO = ["LAURA M", "MARCOS R"]


def visita(id_: str, acompanado: bool | None, fecha: date = SABADO, comercio: str = "LA TASCA",
           tipo: str = "restaurante", personas: list[str] | None = None, forma: str | None = None,
           fuente: str = "respuesta", **kw) -> EventoAmigos:
    return EventoAmigos(id=id_, fuente=fuente, fecha=fecha, fecha_pago=fecha, comercio=comercio, tipo_comercio=tipo,
                        acompanado=acompanado, personas=personas or [], forma=forma, **kw)


def aprender(eventos: list[EventoAmigos], apr: AprendizajeAmigos | None = None) -> AprendizajeAmigos:
    apr = apr or AprendizajeAmigos()
    for e in eventos:
        apr = A.aprender_evento(apr, e)
    return apr


def decidir(apr: AprendizajeAmigos, senal: str | None = "media", importe: str = "48", comercio: str = "LA TASCA",
            tipo: str = "restaurante", fecha: date = SABADO, umbral: Decimal = UMBRAL):
    return nivel_pregunta(apr, comercio=comercio, tipo_comercio=tipo, fecha=fecha, importe=Decimal(importe),
                          senal=senal, umbral=umbral)


def con_grupo(n: int, comercio: str = "LA TASCA", prefijo: str = "v") -> list[EventoAmigos]:
    return [visita(f"{prefijo}{i}", True, comercio=comercio, personas=GRUPO, forma="iguales",
                   fecha=SABADO - timedelta(days=7 * (n - i))) for i in range(n)]


# --- Lo de antes -------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("senal,nivel,aviso", [("media", 1, "resumen"), ("debil", 0, "silencioso"),
                                                ("aprendida", 1, "resumen"), (None, 0, "silencioso")])
def test_sin_datos_como_hoy(senal, nivel, aviso):
    d = decidir(AprendizajeAmigos(), senal)
    assert (d.nivel, d.aviso, d.sugerencia, d.n) == (nivel, aviso, None, 0)
    assert d.motivos


def test_reglas_ignora_lo_aprendido():
    apr = aprender(con_grupo(6) + [visita("i1", None, fuente="ignorada"), visita("i2", None, fuente="ignorada")])
    reglas = apr.model_copy(update={"modo": "reglas"})
    for senal, nivel in (("media", 1), ("debil", 0)):
        d = decidir(reglas, senal)
        assert (d.nivel, d.sugerencia) == (nivel, None)
    assert sugerir(reglas, "LA TASCA", "restaurante", SABADO, Decimal("48")) is None


# --- Bajar: solo, nadie me debe, ignoradas --------------------------------------------------------------------------------

def test_iba_solo_repetido_calla():
    apr = aprender([visita(f"s{i}", False, fecha=SABADO - timedelta(days=7 * (3 - i))) for i in range(3)])
    d = decidir(apr, "media")
    assert (d.nivel, d.aviso) == (0, "silencioso")
    assert d.motivos == ["Aquí sueles ir solo: no te pregunto."]
    assert decidir(aprender([visita("s0", False), visita("s1", False)]), "media").nivel == 1   # dos aún no bastan


def test_nadie_me_debe_repetido_calla_con_su_motivo():
    apr = aprender([visita(f"s{i}", True, forma="cada_uno_lo_suyo", fecha=SABADO - timedelta(days=7 * (3 - i)))
                    for i in range(3)])
    d = decidir(apr, "media")
    assert d.nivel == 0
    assert d.motivos == ["Aquí cada uno suele pagar lo suyo: no te pregunto."]


def test_dos_ignoradas_bajan_un_nivel():
    ign = [visita(f"i{i}", None, fuente="ignorada") for i in range(2)]
    d = decidir(aprender(ign), "media")
    assert d.nivel == 0
    assert "sin respuesta" in d.motivos[-1]
    d = decidir(aprender(con_grupo(2) + ign), "media")
    assert d.nivel == 1 and d.sugerencia is None
    assert decidir(aprender(ign[:1]), "media").nivel == 1                # una sola no baja


# --- Subir: sugerencia y notificación -------------------------------------------------------------------------------------

def test_nivel_2_con_el_grupo_habitual():
    d = decidir(aprender(con_grupo(2)), "media")
    assert (d.nivel, d.aviso) == (2, "resumen")
    assert d.sugerencia.personas == GRUPO and d.sugerencia.cuotas == {}
    assert d.n == 2 and 0.7 < d.p_acompanado < 0.8          # Beta(1, 1) con 2 observaciones (y su decaimiento)


def test_nivel_3_notificacion_de_un_toque():
    d = decidir(aprender(con_grupo(3)), "media", importe="48")
    assert (d.nivel, d.aviso) == (3, "notificar")
    assert d.sugerencia.cuotas == {"LAURA M": Decimal("16.00"), "MARCOS R": Decimal("16.00")}
    assert d.sugerencia.forma == "iguales" and d.sugerencia.ambito == "comercio:LA TASCA"
    assert any("notificación" in m for m in d.motivos)


def test_nivel_3_solo_con_importe_relevante():
    d = decidir(aprender(con_grupo(4)), "media", importe="48", umbral=Decimal("60"))
    assert d.nivel == 2 and d.sugerencia.cuotas == {}
    assert any("por debajo" in m for m in d.motivos)


def test_nivel_3_solo_con_confianza_alta():
    mezcla = [visita(f"g{i}", True, personas=[f"AMIGO{i % 3} X", "ANA L"], forma="iguales",
                     fecha=SABADO - timedelta(days=7 * (6 - i))) for i in range(6)]
    d = decidir(aprender(mezcla), "media")
    assert d.nivel < 3                                                   # grupos que cambian: no hay propuesta segura


def test_una_senal_debil_sube_si_sueles_pagar_por_otros():
    """Las pizzas del jueves: entre semana es señal débil, pero si siempre te deben, se pregunta."""
    eventos = con_grupo(3, comercio="PIZZERIA PISO")
    eventos = [e.model_copy(update={"fecha": e.fecha - timedelta(days=2), "fecha_pago": e.fecha - timedelta(days=2),
                                    "tipo_comercio": "restaurante"}) for e in eventos]
    d = decidir(aprender(eventos), "debil", comercio="PIZZERIA PISO", fecha=JUEVES, importe="30")
    assert d.nivel == 3


def test_tipo_y_franja_para_un_sitio_nuevo():
    apr = aprender([visita(f"s{i}", False, comercio=f"CAFE {i}", fecha=SABADO - timedelta(days=7 * i))
                    for i in range(4)])
    d = decidir(apr, "media", comercio="CAFE NUEVO")
    assert d.nivel == 0
    assert d.motivos == ["En sitios así los fines de semana sueles ir solo: no te pregunto."]


# --- Sugerencia -------------------------------------------------------------------------------------------------------------

def test_sugerir_cuotas_decimal_con_el_usuario():
    s = sugerir(aprender(con_grupo(3)), "LA TASCA", "restaurante", SABADO, Decimal("50"))
    assert s.cuotas == {"LAURA M": Decimal("16.67"), "MARCOS R": Decimal("16.67")}
    assert all(isinstance(v, Decimal) for v in s.cuotas.values())
    assert sum(s.cuotas.values()) <= Decimal("50")
    assert 0 < s.confianza <= 1


def test_sugerir_por_consumo_sin_cuotas_y_cuota_fuera_de_bizum():
    por_consumo = [visita(f"c{i}", True, personas=GRUPO, forma="por_consumo") for i in range(3)]
    assert sugerir(aprender(por_consumo), "LA TASCA", "restaurante", SABADO, Decimal("48")).cuotas == {}
    assert sugerir(aprender(con_grupo(3)), "LA TASCA", "restaurante", SABADO, Decimal("1.20")).cuotas == {}


def test_sugerir_no_propone_donde_nadie_debe():
    sin = [visita(f"s{i}", True, personas=GRUPO, forma="cada_uno_lo_suyo") for i in range(3)]
    assert sugerir(aprender(sin), "LA TASCA", "restaurante", SABADO, Decimal("48")) is None


# --- Nada por nombre, motivos legibles y rápido -----------------------------------------------------------------------------

@pytest.mark.parametrize("historia", ["solo", "grupo", "ignoradas"])
def test_nada_por_nombre_de_comercio(historia):
    def eventos(comercio: str) -> list[EventoAmigos]:
        if historia == "solo":
            return [visita(f"s{i}", False, comercio=comercio) for i in range(3)]
        if historia == "grupo":
            return con_grupo(3, comercio=comercio)
        return [visita(f"i{i}", None, comercio=comercio, fuente="ignorada") for i in range(2)]

    a = decidir(aprender(eventos("LA TASCA")), comercio="LA TASCA")
    b = decidir(aprender(eventos("BAR CUALQUIERA 7")), comercio="BAR CUALQUIERA 7")
    assert (a.nivel, a.motivos, a.p_acompanado) == (b.nivel, b.motivos, b.p_acompanado)
    for m in a.motivos + b.motivos:
        assert "TASCA" not in m.upper() and "CUALQUIERA" not in m.upper()


def test_rapido():
    apr = aprender(con_grupo(5) + [visita(f"s{i}", False, comercio=f"SITIO {i}") for i in range(40)])
    inicio = time.perf_counter()
    for _ in range(300):
        decidir(apr, "media")
    assert (time.perf_counter() - inicio) * 1000 / 300 < 1.0


# --- Usuario simulado con preferencias ocultas (semilla fija) ---------------------------------------------------------------
#
# Hipótesis: con lo aprendido, en 8 semanas y sobre 20 semillas, las preguntas inútiles (las que acaban en «iba solo» o
# «nadie me debe») de las semanas 7-8 bajan al menos un 70 % frente a las reglas, el acierto de la sugerencia en las
# semanas 4-8 es >= 70 % (con las reglas no hay sugerencia) y se escapa al menos un 20 % menos de dinero (las pizzas del
# jueves, que las reglas nunca preguntan). Medido el 11 nov: inútiles 77 -> 15, acierto 132/163 = 81 %, deudas que se
# escapan 85 -> 56 de 305; la semana 1, idéntica.

SITIOS = [
    # (comercio, tipo, día desde el sábado, importe, señal de las reglas, p oculta de ir con el grupo, forma oculta)
    ("LA TASCA", "restaurante", 0, "48", "media", 0.9, "iguales"),           # sábados con Laura y Marcos
    ("CASA PACO", "restaurante", 1, "26", "media", 0.1, "iguales"),          # domingos casi siempre solo
    ("TABERNA SUR", "restaurante", 1, "35", "media", 0.85, "cada_uno_lo_suyo"),  # con gente, pero cada uno lo suyo
    ("PIZZERIA PISO", "restaurante", 5, "30", None, 0.95, "iguales"),        # jueves: entre semana y < 40 €
]


def simular(modo: str, semanas: int = 8, semilla: int = 11) -> list[dict]:
    rng = random.Random(semilla)
    azar = [[(rng.random(), rng.random(), rng.random()) for _ in SITIOS] for _ in range(semanas)]   # común a los modos
    apr = AprendizajeAmigos(modo=modo)
    inicio = date(2026, 9, 5)                                            # sábado
    semanas_out = []
    for s in range(semanas):
        cuenta = {"preguntas": 0, "inutiles": 0, "sugeridas": 0, "aceptadas": 0, "escapadas": 0, "deudas": 0}
        for j, (comercio, tipo, dia, importe, senal, p_grupo, forma) in enumerate(SITIOS):
            u_con, u_responde, u_boton = azar[s][j]
            fecha = inicio + timedelta(weeks=s, days=dia)
            con = u_con < p_grupo
            debe = con and forma != "cada_uno_lo_suyo"
            cuenta["deudas"] += debe
            compania = A.compania_para_motor(apr) or {}
            senal_hoy = senal or ("aprendida" if compania.get(f"c:{comercio}", 0) >= 0.7 else None)
            caso = f"{s}-{j}"
            if senal_hoy is None:                                        # el motor no abre nada: solo el botón
                if debe and u_boton < 0.5:
                    apr = A.aprender_evento(apr, visita(f"acomp:{caso}", True, fecha=fecha, comercio=comercio,
                                                        tipo=tipo, personas=GRUPO, forma=forma, fuente="boton"))
                elif debe:
                    cuenta["escapadas"] += 1
                continue
            d = decidir(apr, senal_hoy, importe=importe, comercio=comercio, tipo=tipo, fecha=fecha)
            if d.nivel == 0:
                if debe and u_boton < 0.5:
                    apr = A.aprender_evento(apr, visita(f"acomp:{caso}", True, fecha=fecha, comercio=comercio,
                                                        tipo=tipo, personas=GRUPO, forma=forma, fuente="boton"))
                elif debe:
                    cuenta["escapadas"] += 1
                continue
            cuenta["preguntas"] += 1
            cuenta["inutiles"] += not debe
            sugerida = d.sugerencia is not None
            cuenta["sugeridas"] += sugerida
            if u_responde >= 0.9:                                        # 1 de cada 10 se queda sin contestar
                apr = A.aprender_evento(apr, visita(f"ign:{caso}", None, fecha=fecha, comercio=comercio, tipo=tipo,
                                                    fuente="ignorada"))
                cuenta["escapadas"] += debe
                continue
            aceptada = sugerida and debe and d.sugerencia.personas == GRUPO
            cuenta["aceptadas"] += aceptada
            apr = A.aprender_evento(apr, visita(f"acomp:{caso}", con, fecha=fecha, comercio=comercio, tipo=tipo,
                                                personas=GRUPO if con else [], forma=forma if con else None,
                                                nivel=d.nivel, sugerencia_aceptada=aceptada if sugerida else None))
        semanas_out.append(cuenta)
    return semanas_out


def _suma(semanas: list[dict], clave: str, desde: int, hasta: int) -> int:
    return sum(s[clave] for s in semanas[desde:hasta])


SEMILLAS = range(20)


def _total(modo: str, clave: str, desde: int, hasta: int) -> int:
    return sum(_suma(simular(modo, semilla=s), clave, desde, hasta) for s in SEMILLAS)


def test_usuario_simulado_aprende_y_molesta_menos():
    assert simular("aprende", semilla=3) == simular("aprende", semilla=3)            # reproducible
    # Semana 1: sin datos, los dos modos preguntan exactamente lo mismo
    assert _total("aprende", "preguntas", 0, 1) == _total("reglas", "preguntas", 0, 1)
    assert _total("aprende", "inutiles", 0, 1) == _total("reglas", "inutiles", 0, 1)
    # Semanas 7-8: muchas menos preguntas inútiles
    assert _total("aprende", "inutiles", 6, 8) <= 0.3 * _total("reglas", "inutiles", 6, 8)
    # Acierto de la sugerencia (semanas 4-8)
    assert _total("reglas", "sugeridas", 0, 8) == 0
    sugeridas = _total("aprende", "sugeridas", 3, 8)
    assert sugeridas > 0 and _total("aprende", "aceptadas", 3, 8) / sugeridas >= 0.7
    # Se escapa menos dinero
    assert _total("aprende", "escapadas", 0, 8) <= 0.8 * _total("reglas", "escapadas", 0, 8)
