"""
Perfil de vida (`personalizacion.perfilar`, personalizacion.md §3). Sin crédito ni red: pandas y datos
sintéticos. El perfil de Lucía exacto sale de su vida sintética (`simulacion/vidas.py`), que contiene
los movimientos de `cena-lucia`; el grupo exacto, también del propio escenario.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

from backend import motor, personalizacion
from backend.escenarios.cargar import cargar
from backend.motor.normalizar import normalizar_comercio
from backend.personalizacion.perfil import es_sensible, perfilar
from backend.personalizacion.simulacion.vidas import HOY_LUCIA, vida_lucia
from backend.plataforma.tipos import (
    AccionOfrecida,
    Grupo,
    ModeloUsuario,
    Movimiento,
    PerfilUsuario,
    Propuesta,
)

HOY = date(2026, 11, 9)
GRUPO_LUCIA = Grupo(miembros=["LAURA M", "DANIEL P", "SARA L", "MARCOS R"], veces=3, retraso_p75_dias=2)
METRO = normalizar_comercio(None, "COMPRA TARJETA METRO DE MADRID")[0]   # la clave que da el motor


def perfil_lucia(hoy: date = HOY_LUCIA, anterior: PerfilUsuario | None = None) -> PerfilUsuario:
    return perfilar(motor.enriquecer(vida_lucia(hoy)), hoy, anterior)


def test_perfil_de_lucia_exacto():
    p = perfil_lucia()
    assert p.version == "perfil-v1" and p.calculado == HOY_LUCIA
    assert p.dia_cobro_nomina == 28
    assert p.ingreso_mensual_tipico == Decimal("1850")
    assert p.ticket_tipico == Decimal("9.80") and p.umbral_relevante_eur == Decimal("20")
    assert p.gasto_tipico_por_categoria == {"supermercado": Decimal("260"), "restaurantes": Decimal("140"),
                                            "ocio": Decimal("60"), "transporte": Decimal("55"),
                                            "suscripciones": Decimal("24")}
    assert list(p.gasto_tipico_por_categoria) == ["supermercado", "restaurantes", "ocio", "transporte", "suscripciones"]
    assert p.comercios_habituales == ["MERCADONA", METRO, "GLOVO", "LA TASCA", "NETFLIX", "SPOTIFY"]
    assert p.grupos == [GRUPO_LUCIA]
    assert [(s.comercio, s.importe, s.periodicidad_dias, s.proximo_cobro, s.en_prueba)
            for s in p.suscripciones_activas] == [
        ("NETFLIX", Decimal("12.99"), 30, date(2026, 12, 3), False),
        ("SPOTIFY", Decimal("10.99"), 30, date(2026, 11, 15), False),
    ]
    assert p.resumen_vida == (
        "Cobras la nómina hacia el día 28, unos 1.850 € al mes. Donde más gastas es en supermercado (260 €) "
        "y restaurantes (140 €). Sueles dividir cenas con un grupo de 4 personas a partes iguales. "
        "Tienes 2 suscripciones, Netflix y Spotify, que suman 23,98 € al mes.")


def test_grupo_exacto_sobre_cena_lucia():
    """El escenario de la demo: las 3 cenas cerradas; la del 6/11 aún está abierta y no cuenta."""
    esc = cargar("cena-lucia")
    p = perfilar(motor.enriquecer([m for m in esc.movimientos if m.fecha <= HOY]), HOY, None)
    assert p.grupos == [GRUPO_LUCIA]
    assert p.dia_cobro_nomina == 28
    # Al cerrar la cena del 6/11 (más de 7 días), cuenta una vez más y el grupo no cambia.
    hoy = date(2026, 11, 16)
    p2 = perfilar(motor.enriquecer([m for m in esc.movimientos if m.fecha <= hoy]), hoy, None)
    assert p2.grupos[0].miembros == GRUPO_LUCIA.miembros and p2.grupos[0].veces == 4


def test_menos_de_28_dias_no_hay_perfil():
    vida = vida_lucia()
    reciente = [m for m in vida if m.fecha >= HOY_LUCIA - timedelta(days=26)]
    assert perfilar(motor.enriquecer(reciente), HOY_LUCIA, None) is None
    assert perfilar([], HOY_LUCIA, None) is None
    justo = [m for m in vida if m.fecha >= HOY_LUCIA - timedelta(days=27)]
    assert min(m.fecha for m in justo) == HOY_LUCIA - timedelta(days=27)
    assert perfilar(motor.enriquecer(justo), HOY_LUCIA, None) is not None


def test_no_mira_el_futuro():
    """Con movimientos posteriores a hoy en la lista, el perfil es el mismo que sin ellos."""
    esc = cargar("cena-lucia")
    todo = motor.enriquecer(esc.movimientos)                                     # hasta el 16/11
    pasado = motor.enriquecer([m for m in esc.movimientos if m.fecha <= HOY])
    assert perfilar(todo, HOY, None) == perfilar(pasado, HOY, None)
    futuro = vida_lucia() + [Movimiento(id=f"fut{i}", fecha=HOY_LUCIA + timedelta(days=i), concepto="RECIBO NETFLIX.COM",
                                        comercio="NETFLIX", importe=Decimal("-99.00"), canal="recibo",
                                        categoria="suscripciones") for i in range(1, 4)]
    assert perfilar(motor.enriquecer(futuro), HOY_LUCIA, None) == perfil_lucia()


def test_lista_negra_no_deja_rastro():
    p = perfil_lucia()
    assert es_sensible(comercio="FARMACIA SOL") and es_sensible(categoria="Salud")
    assert es_sensible(comercio="TINDER") and es_sensible(comercio="BET365") and not es_sensible(comercio="MERCADONA")
    assert "salud" not in p.gasto_tipico_por_categoria
    assert not any("FARMACIA" in c for c in p.comercios_habituales)
    assert "armacia" not in (p.resumen_vida or "")
    # Sin la farmacia, el perfil es idéntico: no se deriva nada de ella (ni el ticket).
    sin = [m for m in vida_lucia() if "FARMACIA" not in (m.comercio or "")]
    assert perfilar(motor.enriquecer(sin), HOY_LUCIA, None) == p
    # Una suscripción sensible tampoco entra.
    citas = vida_lucia() + [Movimiento(id=f"tin{i}", fecha=date(2026, mes, 9), concepto="RECIBO TINDER",
                                       comercio="TINDER", importe=Decimal("-14.99"), canal="recibo",
                                       categoria="suscripciones") for i, mes in enumerate((8, 9, 10))]
    assert perfilar(motor.enriquecer(citas), HOY_LUCIA, None) == p


def test_umbral_sale_de_la_compra_tipica_no_de_los_ingresos():
    rica = [m.model_copy(update={"importe": Decimal("6000")}) if m.concepto.startswith("NOMINA") else m
            for m in vida_lucia()]
    p = perfilar(motor.enriquecer(rica), HOY_LUCIA, None)
    assert p.ingreso_mensual_tipico == Decimal("6000")
    assert p.ticket_tipico == Decimal("9.80") and p.umbral_relevante_eur == Decimal("20")


def test_campos_fijados_y_borrados():
    anterior = perfil_lucia().model_copy(update={
        "dia_cobro_nomina": 1, "umbral_relevante_eur": Decimal("50"), "comercios_habituales": ["MERCADONA"],
        "campos_fijados": ["dia_cobro_nomina", "umbral_relevante_eur", "comercios_habituales", "inventado"],
        "campos_borrados": ["ingreso_mensual_tipico", "grupos"],
    })
    p = perfil_lucia(anterior=anterior)
    assert p.dia_cobro_nomina == 1 and p.umbral_relevante_eur == Decimal("50")
    assert p.comercios_habituales == ["MERCADONA"]
    assert p.ingreso_mensual_tipico is None and p.grupos == []
    assert p.campos_fijados == ["dia_cobro_nomina", "umbral_relevante_eur", "comercios_habituales"]
    assert p.campos_borrados == ["ingreso_mensual_tipico", "grupos"]
    # El resumen solo usa lo que queda: ni ingresos ni grupo.
    assert p.resumen_vida.startswith("Cobras la nómina hacia el día 1.")
    assert "1.850" not in p.resumen_vida and "grupo" not in p.resumen_vida
    # Un resumen reescrito por el usuario no se pisa.
    fijo = perfil_lucia().model_copy(update={"resumen_vida": "Mi resumen.", "campos_fijados": ["resumen_vida"]})
    assert perfil_lucia(anterior=fijo).resumen_vida == "Mi resumen."


def test_streamflix_en_prueba_no_es_una_suscripcion_pagada():
    """La verificación de 0 € de Streamflix no la convierte en suscripción (el motor no la da por pagada)."""
    p = perfil_lucia()
    assert "STREAMFLIX" not in [s.comercio for s in p.suscripciones_activas]
    # Si un comercio con serie vuelve a pedir una verificación tras su último cargo: en prueba.
    vida = vida_lucia() + [Movimiento(id="nfx-v", fecha=date(2026, 11, 5), concepto="VERIFICACION TARJETA NETFLIX",
                                      comercio="NETFLIX", importe=Decimal("0.00"), canal="tarjeta",
                                      tipo_operacion="verificacion")]
    netflix = next(s for s in perfilar(motor.enriquecer(vida), HOY_LUCIA, None).suscripciones_activas
                   if s.comercio == "NETFLIX")
    assert netflix.en_prueba
    assert "Netflix" not in perfilar(motor.enriquecer(vida), HOY_LUCIA, None).resumen_vida


def _cena(modelo: ModeloUsuario) -> str:
    propuesta = Propuesta(
        id="p-cena", modulo_id="gasto_compartido", momento_id="m", usuario_id=modelo.usuario_id,
        titulo="Cena", mensaje_notificacion="Te faltan 24 €", contexto_llamada="",
        acciones_ofrecidas=[AccionOfrecida(accion_id="pedir_bizum"), AccionOfrecida(accion_id="recordar")],
        valor_estimado_eur=Decimal("24.00"), urgencia="media", tipo_momento="gasto_compartido",
        comercio="LA TASCA", contraparte="MARCOS R", confianza=0.95, creada=datetime(2026, 11, 9, 20, 30))
    return personalizacion.decidir(propuesta, modelo, datetime(2026, 11, 9, 20, 30))


def test_la_cena_avisa_con_perfil_y_sin_perfil():
    """El dinero que te deben no se diluye con el umbral personal (E <= 10 €)."""
    esc = cargar("cena-lucia")
    perfiles = {
        "sin perfil": None,
        "cena-lucia (ticket ~19 €)": perfilar(motor.enriquecer([m for m in esc.movimientos if m.fecha <= HOY]), HOY, None),
        "vida de Lucía (ticket 9,80 €)": perfil_lucia(),
    }
    for nombre, perfil in perfiles.items():
        modelo = ModeloUsuario(usuario_id="lucia", modulos_activos=["gasto_compartido"],
                               consentimientos={"copiloto": datetime(2026, 10, 1)}, perfil=perfil)
        d = _cena(modelo)
        assert d.accion == "notificar_ahora", (nombre, d)
        assert d.motivos[0] == "Es dinero que te deben: si no se reclama, se olvida."
