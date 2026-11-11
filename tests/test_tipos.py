"""Contrato en código: tipos, dinero exacto por JSON, lista cerrada de acciones y stubs de los paquetes."""

from __future__ import annotations

import importlib
import json
from datetime import date, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from backend import acciones, modulos, motor, personalizacion, voz
from backend.plataforma import privacidad
from backend.plataforma.reloj import Reloj, ahora_por_defecto
from backend.plataforma.tipos import (
    ACCIONES,
    TIPOS_MOMENTO,
    AccionOfrecida,
    Amigo,
    Decision,
    Feedback,
    Grupo,
    InfoComercio,
    ModeloUsuario,
    Momento,
    Movimiento,
    PerfilUsuario,
    Propuesta,
    ResultadoAccion,
    Suscripcion,
    TarjetaConfirmacion,
)

AHORA = datetime(2026, 11, 9, 20, 30)


def ida_y_vuelta(modelo):
    texto = modelo.model_dump_json()
    return type(modelo).model_validate_json(texto), json.loads(texto)


def perfil_lucia() -> PerfilUsuario:
    """Perfil de Lucía de personalizacion.md §3."""
    return PerfilUsuario(
        calculado=date(2026, 11, 9),
        dias_historial=90,
        dia_cobro_nomina=28,
        ingreso_mensual_tipico=Decimal("1850"),
        gasto_tipico_por_categoria={
            "supermercado": Decimal("260"), "restaurantes": Decimal("140"),
            "ocio": Decimal("60"), "transporte": Decimal("55"), "suscripciones": Decimal("24"),
        },
        ticket_tipico=Decimal("9.80"),
        umbral_relevante_eur=Decimal("20"),
        comercios_habituales=["Mercadona", "Metro de Madrid", "Glovo", "La Tasca", "Netflix", "Spotify"],
        grupos=[Grupo(miembros=["LAURA M", "DANIEL P", "SARA L", "MARCOS R"], veces=3, retraso_p75_dias=2)],
        suscripciones_activas=[
            Suscripcion(comercio="Netflix", importe=Decimal("12.99"), periodicidad_dias=30, proximo_cobro=date(2026, 12, 3)),
            Suscripcion(comercio="Spotify", importe=Decimal("10.99"), periodicidad_dias=30, proximo_cobro=date(2026, 11, 15)),
        ],
        resumen_vida="Cobras la nómina hacia el día 28, unos 1.850 € al mes.",
    )


def momento_cena() -> Momento:
    """Momento de la demo (motor.md §3.1 y §5): cena en La Tasca, falta Marcos."""
    return Momento(
        id="mom-gasto_compartido-1234567890",
        tipo="gasto_compartido",
        usuario_id="lucia",
        fecha=date(2026, 11, 9),
        movimientos=["luc-c1", "luc-b1", "luc-b2", "luc-b3"],
        datos={
            "pago_id": "luc-c1", "comercio": "LA TASCA", "importe_total": Decimal("120.00"),
            "fecha": "2026-11-06", "personas_estimadas": 5, "faltan": 1,
            "importe_pendiente": Decimal("24.00"), "cuota": Decimal("24.00"),
            "reembolsos": [{"contraparte": "LAURA M", "importe": Decimal("24.00"), "id": "luc-b1"}],
            "candidatos": [{"contraparte": "MARCOS R", "importe": Decimal("24.00")}],
        },
        confianza=0.9,
        impacto_eur=Decimal("24.00"),
        explicacion="Pagaste 120,00 € en La Tasca y te han devuelto 72,00 € de 3 personas; falta 1 (24,00 €).",
        detector="gasto_compartido",
        version="motor-0.2/gasto_compartido-1",
        impacto_relativo=Decimal("0.10"),
        contexto_personal="Te quedan 19 días hasta la nómina y son el 10 % de lo que te queda.",
    )


def propuesta_cena() -> Propuesta:
    return Propuesta(
        id="prop-1", modulo_id="gasto_compartido", momento_id="mom-gasto_compartido-1234567890",
        usuario_id="lucia", titulo="Falta Marcos R. por pagar la cena",
        mensaje_notificacion="Te faltan 24,00 € de la cena en La Tasca.",
        contexto_llamada="Cena en <datos>LA TASCA</datos>: falta 1 persona.",
        acciones_ofrecidas=[
            AccionOfrecida(
                accion_id="pedir_bizum",
                parametros={"contraparte": "MARCOS R", "importe": Decimal("24.00"), "concepto": "Tu parte de La Tasca"},
                limites={"importe_max": Decimal("24.00"), "contrapartes": ["MARCOS R"]},
            ),
            AccionOfrecida(accion_id="recordar", parametros={"cuando": "+3d", "texto": "Cobrar la cena"}),
        ],
        valor_estimado_eur=Decimal("24.00"), urgencia="media", tipo_momento="gasto_compartido",
        contraparte="MARCOS R", confianza=0.9, impacto_relativo=Decimal("0.10"),
        contexto_personal="Son el 10 % de lo que te queda.", creada=AHORA,
    )


def test_dinero_ida_y_vuelta_exacta_en_json():
    m = Movimiento(id="a", fecha=date(2026, 11, 6), concepto="COMPRA TARJETA", comercio="LA TASCA",
                   importe=Decimal("-120.00"), saldo=Decimal("1234.50"), canal="tarjeta",
                   tipo_operacion="cargo")
    vuelta, crudo = ida_y_vuelta(m)
    assert crudo["importe"] == "-120.00" and crudo["saldo"] == "1234.50"
    assert crudo["fecha"] == "2026-11-06"
    assert vuelta == m and vuelta.importe == Decimal("-120.00")
    # Enteros y un decimal salen con 2 decimales; más precisión no se recorta
    assert json.loads(Movimiento(id="b", fecha=date(2026, 1, 1), concepto="x", importe=Decimal("5")).model_dump_json())["importe"] == "5.00"
    assert json.loads(Movimiento(id="b", fecha=date(2026, 1, 1), concepto="x", importe=Decimal("0.5")).model_dump_json())["importe"] == "0.50"
    raro = Movimiento(id="c", fecha=date(2026, 1, 1), concepto="x", importe=Decimal("0.1234"))
    assert ida_y_vuelta(raro)[0].importe == Decimal("0.1234")


def test_momento_demo_valida_y_conserva_decimales_en_datos():
    momento = momento_cena()
    vuelta, crudo = ida_y_vuelta(momento)
    assert crudo["impacto_eur"] == "24.00" and crudo["impacto_relativo"] == "0.10"
    assert crudo["datos"]["importe_pendiente"] == "24.00"  # Decimal dentro de dict[str, Any]
    assert Decimal(vuelta.datos["importe_total"]) == Decimal("120.00")
    assert vuelta.tipo == "gasto_compartido" and vuelta.contexto_personal


def test_perfil_de_lucia_ida_y_vuelta():
    perfil = perfil_lucia()
    vuelta, crudo = ida_y_vuelta(perfil)
    assert vuelta == perfil
    assert crudo["ingreso_mensual_tipico"] == "1850.00" and crudo["ticket_tipico"] == "9.80"
    assert crudo["suscripciones_activas"][0]["importe"] == "12.99"
    assert vuelta.grupos[0].retraso_p75_dias == 2
    assert PerfilUsuario(calculado=date(2026, 1, 1), dias_historial=30).umbral_relevante_eur == Decimal("20")


def test_modelo_usuario_v2():
    modelo = ModeloUsuario(
        usuario_id="lucia", perfil=perfil_lucia(), elecciones={"t:gasto_compartido|a:pedir_bizum": 2},
        amigos=[Amigo(contraparte="Marcos R.", saldo=Decimal("24"), propuesta_origen="prop-1",
                      estado="detectado", creado=date(2026, 11, 9))],
    )
    vuelta, crudo = ida_y_vuelta(modelo)
    assert vuelta == modelo
    assert crudo["politica"] == "beta-jerarquica-v2"
    assert "series" not in crudo and "lineas_base" not in crudo
    assert crudo["preferencias"]["usar_perfil"] is True
    assert crudo["preferencias"]["euros_por_molestia"] is None
    assert "concepto" not in crudo["amigos"][0]


def test_propuesta_valida_y_acciones_ofrecidas():
    propuesta = propuesta_cena()
    vuelta, crudo = ida_y_vuelta(propuesta)
    # Los Decimal dentro de `parametros` (dict libre) viajan como cadena exacta y vuelven como cadena
    assert vuelta.acciones_ofrecidas[0].parametros["importe"] == "24.00"
    assert vuelta.acciones_ofrecidas[0].limites == propuesta.acciones_ofrecidas[0].limites
    assert vuelta.model_dump(exclude={"acciones_ofrecidas"}) == propuesta.model_dump(exclude={"acciones_ofrecidas"})
    assert crudo["acciones_ofrecidas"][0]["limites"]["importe_max"] == "24.00"
    assert crudo["impacto_relativo"] == "0.10"
    muchas = [AccionOfrecida(accion_id="recordar") for _ in range(4)]
    with pytest.raises(ValidationError):
        propuesta.model_copy(update={"acciones_ofrecidas": muchas}).model_validate(
            {**propuesta.model_dump(), "acciones_ofrecidas": [a.model_dump() for a in muchas]}
        )


def test_lista_cerrada_de_acciones():
    assert set(ACCIONES) == {
        "pedir_bizum", "cancelar_suscripcion", "bloquear_comercio",
        "reclamar_cargo", "mover_dinero", "recordar",
    }
    assert "preparar_baja" not in ACCIONES
    for mala in ("preparar_baja", "transferir_todo", ""):
        with pytest.raises(ValidationError):
            AccionOfrecida(accion_id=mala)
        with pytest.raises(ValidationError):
            ResultadoAccion(accion_id=mala, ok=True, mensaje="x")
    with pytest.raises(ValueError):
        acciones.preparar("preparar_baja", {}, "prop-1", "lucia")


def test_tipo_momento_incluye_prueba_gratuita():
    assert "prueba_gratuita" in TIPOS_MOMENTO
    with pytest.raises(ValidationError):
        Momento(id="x", tipo="inventado", usuario_id="u", fecha=date(2026, 1, 1), confianza=0.5,
                explicacion="x", detector="x", version="x")
    with pytest.raises(ValidationError):
        Momento(id="x", tipo="prueba_gratuita", usuario_id="u", fecha=date(2026, 1, 1), confianza=1.5,
                explicacion="x", detector="x", version="x")


def test_tarjeta_con_detalle_de_baja_e_info_comercio():
    tarjeta = TarjetaConfirmacion(
        accion_id="cancelar_suscripcion", propuesta_id="p", titulo="Baja de STREAMFLIX",
        token_confirmacion="t", caduca=AHORA,
        detalle_baja={"url_baja": "https://streamflix.example/baja", "url_es_enlace": True,
                      "pasos": ["Entra en tu cuenta"], "bloquea_cobros": True, "canal": "tarjeta",
                      "fuente": "catalogo"},
    )
    vuelta, crudo = ida_y_vuelta(tarjeta)
    assert vuelta.detalle_baja.url_es_enlace is True and crudo["simulada"] is True
    sin_baja = TarjetaConfirmacion(accion_id="recordar", propuesta_id="p", titulo="t",
                                   token_confirmacion="t", caduca=AHORA)
    assert sin_baja.detalle_baja is None
    info = InfoComercio(nombre="STREAMFLIX", tipo="streaming", es_suscripcion=True, dias_prueba=30,
                        precio_tras_prueba=Decimal("9.99"), origen="catalogo")
    assert ida_y_vuelta(info)[1]["precio_tras_prueba"] == "9.99"
    with pytest.raises(ValidationError):
        InfoComercio(nombre="x", tipo="x", origen="inventado")


def test_decision_y_feedback():
    d = Decision(propuesta_id="p", accion="resumen", puntuacion=0.2, probabilidad_util=0.4,
                 motivos=["Poco importe"], politica="beta-jerarquica-v2")
    assert ida_y_vuelta(d)[0] == d
    f = Feedback(propuesta_id="p", usuario_id="lucia", resultado="no_avisar_contacto", canal="app", fecha=AHORA)
    assert ida_y_vuelta(f)[0] == f
    with pytest.raises(ValidationError):
        Feedback(propuesta_id="p", usuario_id="u", resultado="enfadado", canal="app", fecha=AHORA)


def test_reloj_simulado():
    assert ahora_por_defecto(date(2026, 11, 9)) == datetime(2026, 11, 9, 20, 30)
    r = Reloj(date(2026, 11, 9))
    assert r.avanzar() == date(2026, 11, 10) and r.ahora() == datetime(2026, 11, 10, 20, 30)
    with pytest.raises(ValueError):
        r.avanzar(-1)


def test_privacidad():
    assert privacidad.enmascarar_nombre("Marcos Ruiz Sanz") == "Marcos R."
    assert privacidad.enmascarar_nombre("LAURA MARTINEZ GARCIA") == "Laura M."
    assert privacidad.enmascarar_nombre("Sara de la Fuente") == "Sara F."
    assert privacidad.enmascarar_nombre("Daniel") == "Daniel"
    assert privacidad.enmascarar_nombre("MARCOS R") == "Marcos R."
    assert privacidad.enmascarar_nombre(None) == ""
    texto = privacidad.enmascarar_texto(
        "IBAN ES9121000418450200051332, tel 612 345 678, correo ana@example.com"
    )
    assert "ES9121000418450200051332" not in texto
    assert "612 345 678" not in texto and "ana@example.com" not in texto
    assert privacidad.enmascarar_datos({"a": ["ana@example.com"], "n": 3}) == {"a": ["[EMAIL]"], "n": 3}


@pytest.mark.parametrize(
    "paquete", ["motor", "motor.conocimiento", "motor.parametros", "escenarios", "personalizacion",
                "personalizacion.edicion", "modulos", "acciones", "voz", "plataforma"],
)
def test_paquetes_importan(paquete):
    importlib.import_module(f"backend.{paquete}")


# Las firmas de ARQUITECTURA §3.2 son el contrato entre zonas: si un hilo las cambia, salta este test.
FIRMAS = {
    "motor.procesar": ["usuario_id", "nuevos", "hoy", "perfil", "compania"],
    "motor.enriquecer": ["movimientos"],
    "motor.exportar_estado": ["usuario_id"],
    "motor.importar_estado": ["usuario_id", "estado"],
    "motor.reiniciar": ["usuario_id"],
    "motor.cargar_historial": ["usuario_id", "historial", "hoy"],
    "motor.comercios_pendientes": ["usuario_id"],
    "motor.registrar_prueba": ["usuario_id", "comercio", "fecha_alta", "dias", "hoy"],
    "motor.cerrar_prueba": ["usuario_id", "comercio", "motivo", "hoy"],
    "motor.conocimiento.info_comercio": ["nombre"],
    "motor.conocimiento.info_en_cache": ["nombre"],
    "motor.conocimiento.guardar": ["info"],
    "motor.parametros.ajustar": ["params", "perfil"],
    "personalizacion.nuevo_modelo": ["usuario_id"],
    "personalizacion.perfilar": ["historial", "hoy", "perfil_anterior"],
    "personalizacion.ordenar_acciones": ["propuesta", "modelo"],
    "personalizacion.decidir": ["propuesta", "modelo", "ahora"],
    "personalizacion.aprender": ["feedback", "modelo"],
    "personalizacion.registrar_decision": ["modelo", "propuesta", "decision"],
    "personalizacion.observar": ["modelo", "movimientos", "hoy"],
    "personalizacion.registrar_accion": ["modelo", "propuesta", "resultado"],
    "personalizacion.memoria_para_agente": ["modelo"],
    "personalizacion.edicion.borrar_perfil": ["modelo"],
    "modulos.proponer": ["momento", "modelo"],
    "modulos.crear_borrador": ["descripcion"],
    "modulos.probar_en_seco": ["borrador", "usuario_id"],
    "modulos.aprobar": ["modulo_id", "aprobado_por"],
    "acciones.preparar": ["accion_id", "parametros", "propuesta_id", "usuario_id"],
    "acciones.ejecutar": ["token_confirmacion", "usuario_id"],
    "acciones.deshacer": ["resultado_id", "usuario_id"],
    "voz.sesion": ["propuesta_id", "usuario_id", "modo_preferido", "caso_id"],
}


@pytest.mark.parametrize("ruta,parametros", sorted(FIRMAS.items()))
def test_firmas_del_contrato(ruta, parametros):
    import importlib
    import inspect

    *paquete, funcion = ruta.split(".")
    modulo = importlib.import_module("backend." + ".".join(paquete))
    assert list(inspect.signature(getattr(modulo, funcion)).parameters) == parametros


def test_procesar_y_decidir_devuelven_tipos_del_contrato():
    movimiento = Movimiento(id="m1", fecha=date(2026, 11, 6), concepto="COMPRA", comercio="La Tasca",
                            importe=Decimal("-120"))
    hoy = date(2026, 11, 9)
    assert all(isinstance(m, Momento) for m in motor.procesar("t-firmas", [movimiento], hoy))
    assert isinstance(motor.exportar_estado("t-firmas"), dict)
    motor.reiniciar("t-firmas")
    modelo = personalizacion.nuevo_modelo("lucia")
    decision = personalizacion.decidir(propuesta_cena(), modelo, AHORA)
    assert isinstance(decision, Decision) and decision.motivos


def test_caso_ida_y_vuelta_con_dinero_exacto():
    from backend.plataforma.tipos import Caso, Deudor, Hipotesis

    caso = Caso(
        id="caso-1", usuario_id="lucia", estado="dudoso", creado=date(2026, 11, 9),
        hechos={"total": "120.00"},
        hipotesis=[Hipotesis(escenario="gasto_compartido", confianza=0.6, deudores=["MARCOS R"])],
        deudores=[Deudor(contraparte="MARCOS R", cuota=Decimal("24.00"))],
    )
    de_vuelta, crudo = ida_y_vuelta(caso)
    assert crudo["deudores"][0]["cuota"] == "24.00"
    assert de_vuelta == caso
    assert de_vuelta.escenario is None and de_vuelta.deudores[0].estado == "detectada"


def test_caso_rechaza_estado_fuera_de_lista():
    from backend.plataforma.tipos import Caso

    with pytest.raises(ValidationError):
        Caso(id="c", usuario_id="u", creado=date(2026, 11, 9), estado="inventado")
