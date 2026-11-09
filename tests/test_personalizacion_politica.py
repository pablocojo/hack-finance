"""
Política `beta-jerarquica-v2` (docs/diseno/personalizacion.md §4): ejemplos exactos, reglas duras,
motivos, aprendizaje puro y una curva mínima con usuarios simulados de preferencias ocultas.
Sin crédito y reproducible (semillas fijas).
"""

from __future__ import annotations

import random
import time
from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from backend import personalizacion
from backend.personalizacion import politica
from backend.plataforma.tipos import (
    AccionOfrecida,
    Celda,
    Feedback,
    ModeloUsuario,
    PerfilUsuario,
    Propuesta,
    Silencio,
    TIPOS_MOMENTO,
)

AHORA = datetime(2026, 11, 9, 20, 30)   # lunes de la cena
MODULO_DE = {
    "gasto_compartido": "cena_compartida", "cargo_duplicado": "cobro_duplicado",
    "renovacion_proxima": "renovacion", "prueba_gratuita": "fin_de_prueba", "subida_recibo": "recibo_al_alza",
    "posible_estafa": "estafa", "ingreso_extra": "ingreso", "saldo_negativo_previsto": "colchon",
    "viaje_detectado": "viaje",
}


def perfil(ticket: str, umbral: str, dia_cobro: int | None = None) -> PerfilUsuario:
    return PerfilUsuario(calculado=AHORA.date(), dias_historial=90, dia_cobro_nomina=dia_cobro,
                         ticket_tipico=Decimal(ticket), umbral_relevante_eur=Decimal(umbral))


LUCIA = lambda: perfil("9.80", "20", 28)            # noqa: E731
ESTUDIANTE = lambda: perfil("6", "12", 1)           # noqa: E731
HOLGADO = lambda: perfil("45", "90", 28)            # noqa: E731


def modelo(perfil_usuario: PerfilUsuario | None = None, **extra) -> ModeloUsuario:
    m = personalizacion.nuevo_modelo("lucia")
    m.modulos_activos = sorted(set(MODULO_DE.values()))
    m.consentimientos = {"copiloto": AHORA - timedelta(days=1)}
    m.perfil = perfil_usuario
    for campo, valor in extra.items():
        setattr(m, campo, valor)
    return m


def propuesta(tipo: str = "cargo_duplicado", valor: str | None = "12.99", urgencia: str = "media",
              confianza: float = 0.92, pid: str = "p1", comercio: str | None = None,
              contraparte: str | None = None, impacto: str | None = None, contexto: str | None = None,
              modulo_id: str | None = None, creada: datetime = AHORA) -> Propuesta:
    return Propuesta(
        id=pid, modulo_id=modulo_id or MODULO_DE[tipo], momento_id=f"m-{pid}", usuario_id="lucia",
        titulo="t", mensaje_notificacion="m", contexto_llamada="c",
        acciones_ofrecidas=[AccionOfrecida(accion_id="recordar"), AccionOfrecida(accion_id="reclamar_cargo")],
        valor_estimado_eur=Decimal(valor) if valor is not None else None, urgencia=urgencia,
        tipo_momento=tipo, comercio=comercio, contraparte=contraparte, confianza=confianza,
        impacto_relativo=Decimal(impacto) if impacto else None, contexto_personal=contexto, creada=creada,
    )


def feedback(pid: str, resultado: str, fecha: datetime = AHORA) -> Feedback:
    return Feedback(propuesta_id=pid, usuario_id="lucia", resultado=resultado, canal="app", fecha=fecha)


# --- Ejemplos de §4.4, exactos ----------------------------------------------------------------

def test_cena_de_lucia():
    m = modelo(LUCIA(), estadisticas={
        "global": Celda(utiles=6, molestias=4, n=10),
        "t:gasto_compartido": Celda(utiles=2, molestias=0, n=2),
        "t:gasto_compartido|b:alto": Celda(utiles=1, molestias=0, n=1),
        "t:gasto_compartido|e:MARCOS R": Celda(utiles=1, molestias=0, n=1),
    })
    p = propuesta("gasto_compartido", "24.00", "media", 0.92, comercio="La Tasca", contraparte="MARCOS R",
                  impacto="0.02")
    cal = politica.evaluar(p, m, AHORA)
    assert [round(n.media, 3) for n in cal.niveles] == [0.571, 0.714, 0.771, 0.817]
    assert cal.tramo == "alto" and cal.E == Decimal("10")
    assert cal.q == pytest.approx(0.752, abs=5e-4)
    assert cal.B == pytest.approx(2.9) and cal.bonus_nomina == 0
    assert cal.U == pytest.approx(1.93, abs=5e-3)
    d = personalizacion.decidir(p, m, AHORA)
    assert d.accion == "notificar_ahora" and d.politica == "beta-jerarquica-v2"
    assert d.puntuacion == pytest.approx(1.93, abs=5e-3) and d.probabilidad_util == pytest.approx(0.752, abs=5e-4)
    assert "Sueles resolver los avisos de gastos compartidos (2 de 2)." in d.motivos
    assert "Para ti, 24 € es más del doble de una compra típica (9,80 €)." in d.motivos


@pytest.mark.parametrize("nombre, perfil_usuario, ahora, impacto, B, U, accion", [
    ("estudiante", ESTUDIANTE(), datetime(2026, 11, 27, 20, 30), "0.09", 3.165, 0.92, "notificar_ahora"),
    ("lucia", LUCIA(), AHORA, None, 1.799, 0.29, "resumen"),
    ("holgado", HOLGADO(), AHORA, None, 0.789, -0.18, "resumen"),
])
def test_mismo_duplicado_tres_vidas(nombre, perfil_usuario, ahora, impacto, B, U, accion):
    p = propuesta("cargo_duplicado", "12.99", "media", 0.92, comercio="Netflix", impacto=impacto)
    m = modelo(perfil_usuario)
    cal = politica.evaluar(p, m, ahora)
    assert cal.q == pytest.approx(0.46)
    assert cal.B == pytest.approx(B, abs=1e-3)
    assert cal.U == pytest.approx(U, abs=5e-3)
    d = personalizacion.decidir(p, m, ahora)
    assert d.accion == accion
    if nombre == "estudiante":
        assert cal.dias_hasta_nomina == 4 and cal.bonus_nomina == 0.5
        assert "Para ti, 12,99 € es más del doble de una compra típica (6 €)." in d.motivos


def test_sin_perfil_estudiante_y_holgado_se_tratan_igual():
    """Sin perfil (o con el perfil apagado): E = 10 €, tramos sobre 20 € y sin bonus de nómina."""
    p = propuesta("cargo_duplicado", "12.99", comercio="Netflix", impacto="0.09")
    sin = personalizacion.decidir(p, modelo(None), datetime(2026, 11, 27, 20, 30))
    apagado_est = modelo(ESTUDIANTE())
    apagado_est.preferencias.usar_perfil = False
    apagado_hol = modelo(HOLGADO())
    apagado_hol.preferencias.usar_perfil = False
    a = personalizacion.decidir(p, apagado_est, datetime(2026, 11, 27, 20, 30))
    b = personalizacion.decidir(p, apagado_hol, datetime(2026, 11, 27, 20, 30))
    assert sin.accion == a.accion == b.accion == "resumen"
    assert sin.puntuacion == a.puntuacion == b.puntuacion == pytest.approx(0.29, abs=5e-3)
    assert politica.claves(p, modelo(None))[2] == "t:cargo_duplicado|b:medio"   # 12,99 < 20 €


def test_duplicado_de_la_demo_va_al_resumen():
    p = propuesta("cargo_duplicado", "9.99", "media", 0.92, comercio="LIBRERIA LUNA")
    cal = politica.evaluar(p, modelo(LUCIA()), datetime(2026, 10, 15, 20, 30))
    assert cal.B == pytest.approx(1.499) and cal.U == pytest.approx(0.15, abs=5e-3)
    assert personalizacion.decidir(p, modelo(LUCIA()), datetime(2026, 10, 15, 20, 30)).accion == "resumen"


def test_streamflix_es_proteccion_respeta_franja_y_no_cuenta_para_el_tope():
    p = propuesta("prueba_gratuita", "9.99", "alta", 0.85, comercio="Streamflix")
    ahora = datetime(2026, 11, 10, 20, 30)
    cal = politica.evaluar(p, modelo(LUCIA()), ahora)
    assert cal.q == pytest.approx(0.425) and cal.B == pytest.approx(2.999)
    assert cal.U == pytest.approx(0.70, abs=5e-3)
    assert personalizacion.decidir(p, modelo(LUCIA()), ahora).accion == "notificar_ahora"
    lleno = modelo(LUCIA(), ultimos_avisos=[ahora.replace(hour=10), ahora.replace(hour=12)])
    d = personalizacion.decidir(p, lleno, ahora)
    assert d.accion == "notificar_ahora" and d.motivos[0].startswith("Es urgente")
    noche = personalizacion.decidir(p, modelo(LUCIA()), ahora.replace(hour=23, minute=10))
    assert noche.accion == "resumen" and "fuera de tu horario" in noche.motivos[0]


# --- Reglas duras -----------------------------------------------------------------------------

def test_reglas_duras():
    p = propuesta("cargo_duplicado", "50", comercio="Netflix")
    assert personalizacion.decidir(p, modelo(LUCIA()), AHORA).accion == "notificar_ahora"
    # 1. módulo no activo o sin consentimiento
    sin_modulo = modelo(LUCIA(), modulos_activos=["cena_compartida"])
    assert personalizacion.decidir(p, sin_modulo, AHORA).accion == "silenciar"
    sin_permiso = modelo(LUCIA(), consentimientos={})
    d = personalizacion.decidir(p, sin_permiso, AHORA)
    assert d.accion == "silenciar" and "permiso" in d.motivos[0]
    assert personalizacion.decidir(p, modelo(LUCIA(), consentimientos={"avisos": AHORA}), AHORA).accion != "silenciar"
    # 2. no ahorra ni protege
    for valor in ("0", None):
        d = personalizacion.decidir(propuesta("ingreso_extra", valor), modelo(LUCIA()), AHORA)
        assert d.accion == "silenciar" and d.motivos == ["No te ahorra dinero ni te protege, así que no te interrumpo."]
    # 3. silencios explícitos
    for ambito, valor in (("tipo", "cargo_duplicado"), ("comercio", "netflix")):
        m = modelo(LUCIA())
        m.preferencias.silencios = [Silencio(ambito=ambito, valor=valor, desde=AHORA.date(), origen="x")]
        d = personalizacion.decidir(p, m, AHORA)
        assert d.accion == "silenciar" and d.motivos[0].startswith("Me pediste no avisarte de")
    m = modelo(LUCIA())
    m.preferencias.silencios = [Silencio(ambito="contacto", valor="HERMANO", desde=AHORA.date(), origen="x")]
    d = personalizacion.decidir(propuesta("gasto_compartido", "30", contraparte="Hermano"), m, AHORA)
    assert d.accion == "silenciar" and "Hermano" in d.motivos[0]
    m.preferencias.silencios.append(Silencio(ambito="tipo", valor="posible_estafa", desde=AHORA.date(), origen="x"))
    estafa = personalizacion.decidir(propuesta("posible_estafa", "200", "alta"), m, AHORA)
    assert estafa.accion == "resumen"
    # 4. tope diario (2) y franja
    lleno = modelo(LUCIA(), ultimos_avisos=[AHORA.replace(hour=10), AHORA.replace(hour=11)])
    d = personalizacion.decidir(p, lleno, AHORA)
    assert d.accion == "resumen" and d.motivos[0] == "Hoy ya te he avisado 2 veces; lo dejo en el resumen."
    ayer = modelo(LUCIA(), ultimos_avisos=[AHORA - timedelta(days=1)] * 3)
    assert personalizacion.decidir(p, ayer, AHORA).accion == "notificar_ahora"
    assert personalizacion.decidir(p, modelo(LUCIA()), AHORA.replace(hour=7)).accion == "resumen"


def test_la_proteccion_nunca_se_silencia_por_aprendizaje():
    m = modelo(LUCIA(), falsos_positivos={"prueba_gratuita": 5, "posible_estafa": 5})
    for tipo in ("prueba_gratuita", "posible_estafa"):
        m.estadisticas["global"] = Celda(utiles=0, molestias=30, n=30)
        m.estadisticas[f"t:{tipo}"] = Celda(utiles=0, molestias=20, n=20)
    casos = [propuesta("prueba_gratuita", v, u, 0.3, comercio="Streamflix") for v in ("0", "9.99", None)
             for u in ("alta", "media", "baja")]
    casos += [propuesta("posible_estafa", "200", "alta", 0.3), propuesta("posible_estafa", None, "media", 0.3),
              propuesta("cargo_duplicado", "3", "alta", 0.3)]
    for p in casos:
        d = personalizacion.decidir(p, m, AHORA)
        assert d.accion != "silenciar", (p.tipo_momento, p.valor_estimado_eur, p.urgencia)
        assert d.motivos


def test_exploracion_prudente_y_despues_silencio():
    p = propuesta("renovacion_proxima", "1", "baja", comercio="Spotify")
    m = modelo(LUCIA())
    d = personalizacion.decidir(p, m, AHORA)
    assert d.puntuacion < -0.3 and d.accion == "resumen" and d.motivos[0].startswith("Aún sé poco")
    for i in range(3):
        q = propuesta("renovacion_proxima", "1", "baja", pid=f"r{i}", comercio="Spotify")
        m = personalizacion.registrar_decision(m, q, personalizacion.decidir(q, m, AHORA))
        m = personalizacion.aprender(feedback(f"r{i}", "rechazada"), m)
    d = personalizacion.decidir(p, m, AHORA)
    assert d.accion == "silenciar" and any("Pocas veces te sirven" in x for x in d.motivos)


def test_toda_decision_lleva_motivos_y_tarda_menos_de_5_ms():
    rng = random.Random(0)
    m = modelo(LUCIA(), estadisticas={"global": Celda(utiles=3, molestias=5, n=8),
                                      "t:renovacion_proxima": Celda(utiles=0, molestias=4, n=4)})
    tiempos = []
    for i in range(400):
        tipo = rng.choice(TIPOS_MOMENTO)
        p = propuesta(tipo, rng.choice([None, "0", "2.5", "9.99", "24", "130"]), rng.choice(["alta", "media", "baja"]),
                      rng.random(), pid=f"x{i}", comercio=rng.choice([None, "Netflix"]),
                      contraparte=rng.choice([None, "MARCOS R"]))
        ahora = AHORA.replace(hour=rng.randint(0, 23))
        t0 = time.perf_counter()
        d = personalizacion.decidir(p, m, ahora)
        tiempos.append(time.perf_counter() - t0)
        assert 1 <= len(d.motivos) <= 3 and all(isinstance(x, str) and x for x in d.motivos)
    assert max(tiempos) < 0.005


# --- Aprender (pura) --------------------------------------------------------------------------

def _con_aviso(accion="notificar_ahora", **kw):
    p = propuesta("gasto_compartido", "24", comercio="La Tasca", contraparte="MARCOS R", **kw)
    m = modelo(LUCIA())
    d = personalizacion.decidir(p, m, AHORA).model_copy(update={"accion": accion})
    return p, personalizacion.registrar_decision(m, p, d)


def test_aprender_es_pura_y_suma_a_todas_las_claves():
    p, m = _con_aviso()
    copia = m.model_dump()
    nuevo = personalizacion.aprender(feedback("p1", "resuelta"), m)
    assert m.model_dump() == copia                     # no toca el original
    for clave in ("global", "t:gasto_compartido", "t:gasto_compartido|b:alto", "t:gasto_compartido|e:MARCOS R"):
        assert nuevo.estadisticas[clave] == Celda(utiles=1, molestias=0, n=1, ultima=AHORA.date())
    assert "p1" not in nuevo.avisos_abiertos           # una respuesta por aviso
    assert personalizacion.aprender(feedback("p1", "resuelta"), nuevo) == nuevo
    assert personalizacion.aprender(feedback("otra", "resuelta"), m) == m


@pytest.mark.parametrize("resultado, accion, utiles, molestias", [
    ("vista_sin_accion", "notificar_ahora", 0.5, 0.5), ("rechazada", "notificar_ahora", 0, 1),
    ("ignorada", "notificar_ahora", 0, 1), ("ignorada", "resumen", 0, 0.25),
])
def test_cada_feedback(resultado, accion, utiles, molestias):
    _, m = _con_aviso(accion)
    celda = personalizacion.aprender(feedback("p1", resultado), m).estadisticas["t:gasto_compartido"]
    assert (celda.utiles, celda.molestias, celda.n) == (utiles, molestias, 1)


def test_falso_positivo_solo_baja_la_confianza():
    _, m = _con_aviso()
    nuevo = personalizacion.aprender(feedback("p1", "falso_positivo"), m)
    assert nuevo.falsos_positivos == {"gasto_compartido": 1} and nuevo.estadisticas == {}
    p = propuesta("gasto_compartido", "24", pid="p2", contraparte="MARCOS R")
    assert politica.evaluar(p, nuevo, AHORA).c == pytest.approx(0.92 * 0.8)


def test_no_avisar_contacto_crea_silencio_y_hecho_visible():
    _, m = _con_aviso()
    nuevo = personalizacion.aprender(feedback("p1", "no_avisar_contacto"), m)
    assert [(s.ambito, s.valor) for s in nuevo.preferencias.silencios] == [("contacto", "MARCOS R")]
    hecho = nuevo.hechos_aprendidos[0]
    assert hecho.origen == "preferencia" and hecho.texto == "No quieres avisos de gastos con Marcos R."
    assert nuevo.estadisticas["t:gasto_compartido"].molestias == 1
    otra = propuesta("gasto_compartido", "40", pid="p2", comercio="Bar Pepe", contraparte="MARCOS R")
    assert personalizacion.decidir(otra, nuevo, AHORA).accion == "silenciar"
    # no_avisar_comercio silencia el comercio, no el contacto
    _, m = _con_aviso()
    nuevo = personalizacion.aprender(feedback("p1", "no_avisar_comercio"), m)
    assert [(s.ambito, s.valor) for s in nuevo.preferencias.silencios] == [("comercio", "LA TASCA")]


def test_hechos_derivados_y_memoria_operativa():
    m = modelo(LUCIA())
    m.perfil.ingreso_mensual_tipico = Decimal("1850")
    m.perfil.resumen_vida = "Cobras la nómina hacia el día 28, unos 1.850 € al mes."
    for i in range(3):
        p = propuesta("gasto_compartido", "24", pid=f"g{i}", contraparte="MARCOS R")
        m = personalizacion.registrar_decision(m, p, personalizacion.decidir(p, m, AHORA))
        m = personalizacion.aprender(feedback(f"g{i}", "resuelta"), m)
    textos = [h.texto for h in m.hechos_aprendidos]
    assert "Sueles resolver los avisos de gastos compartidos." in textos
    memoria = personalizacion.memoria_para_agente(m)
    assert memoria.startswith("<datos>") and memoria.endswith("</datos>") and len(memoria) <= 600
    assert "1.850" not in memoria and "nómina" not in memoria


def test_un_modulo_nuevo_hereda_lo_aprendido():
    _, m = _con_aviso()
    m = personalizacion.aprender(feedback("p1", "resuelta"), m)
    a = propuesta("gasto_compartido", "24", pid="a", contraparte="MARCOS R")
    b = propuesta("gasto_compartido", "24", pid="b", contraparte="MARCOS R", modulo_id="nuevo_del_banco")
    m.modulos_activos.append("nuevo_del_banco")
    assert politica.evaluar(a, m, AHORA).U == politica.evaluar(b, m, AHORA).U


def test_registrar_decision_cuenta_el_tope_salvo_urgencia_alta():
    m = modelo(LUCIA())
    for i, urg in enumerate(("alta", "media", "media")):
        p = propuesta("cargo_duplicado", "60", urg, pid=f"d{i}", comercio="Netflix")
        d = personalizacion.decidir(p, m, AHORA)
        assert d.accion == "notificar_ahora"
        m = personalizacion.registrar_decision(m, p, d)
    p = propuesta("cargo_duplicado", "60", pid="d9", comercio="Netflix")
    assert len(m.ultimos_avisos) == 2 and personalizacion.decidir(p, m, AHORA).accion == "resumen"


# --- Curva mínima: usuarios simulados con preferencias ocultas (semilla fija) -----------------

OCULTAS = {   # la política no ve esto: solo las respuestas
    "social": lambda tipo, v: tipo in ("gasto_compartido", "prueba_gratuita") or (tipo == "cargo_duplicado" and v >= 10),
    "holgado": lambda tipo, v: tipo == "prueba_gratuita" or v >= 60,
}
TIPOS_SIM = ("gasto_compartido", "cargo_duplicado", "renovacion_proxima", "subida_recibo", "prueba_gratuita")


def simular(nombre: str, perfil_usuario: PerfilUsuario, semilla: int, aprende: bool) -> list[tuple[int, int]]:
    """6 semanas × 10 propuestas. Devuelve por semana (avisos ahora útiles, avisos ahora)."""
    rng = random.Random(semilla)
    m = modelo(perfil_usuario)
    m.preferencias.max_avisos_dia = 10
    semanas = []
    for semana in range(6):
        utiles = total = 0
        for i in range(10):
            tipo = rng.choice(TIPOS_SIM)
            valor = Decimal(rng.choice(["4", "9.99", "15", "24", "45", "80"]))
            ahora = AHORA + timedelta(days=7 * semana + i // 2)
            pid = f"{semana}-{i}"
            p = propuesta(tipo, str(valor), "alta" if tipo == "prueba_gratuita" else "media", 0.9, pid=pid,
                          comercio=rng.choice(["Netflix", "Spotify", "Iberdrola"]), creada=ahora)
            d = personalizacion.decidir(p, m, ahora)
            util = OCULTAS[nombre](tipo, valor)
            if d.accion == "notificar_ahora":
                total += 1
                utiles += util
            if not aprende or d.accion == "silenciar":
                continue
            m = personalizacion.registrar_decision(m, p, d)
            if d.accion == "notificar_ahora":
                r = "resuelta" if util else "rechazada"
            else:
                r = ("resuelta" if util else "ignorada") if rng.random() < 0.6 else "ignorada"
            m = personalizacion.aprender(feedback(pid, r, ahora + timedelta(hours=1)), m)
        semanas.append((utiles, total))
    return semanas


def test_curva_minima_aprender_sube_la_precision():
    """Hipótesis (semillas 0-9): en `social`, aprender sube la precisión de `notificar_ahora` de la
    semana 6 en ≥ 15 puntos frente a no aprender (medido: 0,76 → 0,98) y quita ≥ 65 % de las
    molestias (14 → 1). En `holgado`, el perfil ya acierta; aprender no baja la precisión de 0,8 y
    sube los avisos útiles que interrumpen (13 → 23)."""
    def sumar(runs, w):
        utiles = sum(r[w][0] for r in runs)
        total = sum(r[w][1] for r in runs)
        return utiles / max(1, total), utiles, total - utiles

    fija = [simular("social", LUCIA(), s, aprende=False) for s in range(10)]
    pers = [simular("social", LUCIA(), s, aprende=True) for s in range(10)]
    (pf, _, mf), (pp, _, mp) = sumar(fija, 5), sumar(pers, 5)
    assert pp >= pf + 0.15 and pp >= 0.8
    assert mp <= 0.35 * mf
    fija = [simular("holgado", HOLGADO(), s, aprende=False) for s in range(10)]
    pers = [simular("holgado", HOLGADO(), s, aprende=True) for s in range(10)]
    (pf, uf, _), (pp, up, _) = sumar(fija, 5), sumar(pers, 5)
    assert pp >= 0.8 and up > uf
