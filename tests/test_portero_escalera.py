"""Curva de amigos, A4 (docs/diseno/curva-amigos.md §4.1): lo aprendido llega a los casos y al portero.

- la escalera decide `aviso`, `pregunta_nivel` y `sugerencia` al abrir un `pago_individual`; el nivel 3 sale como
  propuesta de solo preguntar que pasa por `decidir` («48 € en La Tasca: ¿con Laura y Marcos, 16 € cada uno?»);
- `Deudor.avisar_desde` por persona: un amigo con p75 = 3 no recibe recordatorio antes del día 3;
- Meisam aprende de las respuestas, el botón, el chat, los Bizums y las preguntas ignoradas; con `reglas`, nada cambia;
- no se abre un `pago_individual` sobre un cargo que ya tiene caso; `responder_duda` cierra `hechos["pregunta"]`.
Motor simulado (sin red ni crédito) y el resto del sistema real (casos, módulos, política y portero)."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest

from backend import casos, personalizacion
from backend.personalizacion import aprende_amigos as A
from backend.personalizacion import escalera
from backend.plataforma import orquestador as orq
from backend.plataforma.tipos import (Acompanamiento, AprendizajeAmigos, Caso, Contacto, Deudor, GrupoHabitual,
                                      HabitoPersona, Momento, Movimiento, SugerenciaReparto)

UID = "amigos-test"
D = date(2026, 11, 7)            # sábado: el día del pago
ACTIVACION = date(2026, 11, 5)
AHORA = datetime(2026, 11, 9, 20, 30)
TASCA = A.clave_comercio("La Tasca")
CONTACTOS = {c: Contacto(contraparte=c, nombre=n) for c, n in
             (("LAURA M", "Laura M."), ("MARCOS R", "Marcos R."), ("RODRIGO P", "Rodrigo P."))}
TEXTO_NIVEL_3 = "48 € en La Tasca: ¿con Laura y Marcos, 16 € cada uno?"


def _pago(id_: str = "p1", dia: date = D, importe: str = "-48.00") -> Movimiento:
    return Movimiento(id=id_, fecha=dia, concepto="LA TASCA MADRID", comercio="La Tasca", importe=Decimal(importe),
                      canal="tarjeta", categoria="restaurantes", tipo_operacion="cargo")


def _bizum(id_: str, dia: date, importe: str, quien: str) -> Movimiento:
    return Movimiento(id=id_, fecha=dia, concepto="BIZUM RECIBIDO", importe=Decimal(importe), canal="bizum",
                      contraparte=quien)


def _momento_individual(senal: str, pago_id: str = "p1", importe: str = "48.00") -> Momento:
    datos = {"origen": "pago_individual", "dudoso": True, "senal": senal, "tipo_comercio": "restaurante",
             "pago_id": pago_id, "comercio": TASCA, "importe_total": Decimal(importe), "fecha": D.isoformat(),
             "movimientos": [pago_id],
             "hipotesis": [{"candidatos": [], "faltan": 0, "motivo": "Pudo ir con alguien"},
                           {"candidatos": [], "faltan": 0, "motivo": "Pudo ir solo"}]}
    return Momento(id=f"mom-ind-{pago_id}", tipo="gasto_compartido", usuario_id=UID, fecha=D + timedelta(days=2),
                   movimientos=[pago_id], datos=datos, confianza=0.5, impacto_eur=None,
                   explicacion="Pago que pudo ser con alguien.", detector="pago_individual", version="1")


def _tasca_aprendida(veces: float = 4.0) -> AprendizajeAmigos:
    """«En La Tasca, casi siempre con Laura y Marcos, a partes iguales» (4 veces, sin decaimiento)."""
    grupo = GrupoHabitual(miembros=["LAURA M", "MARCOS R"], veces=veces, ultima=D - timedelta(days=7),
                          repartos={"iguales": veces})
    return AprendizajeAmigos(por_comercio={TASCA: Acompanamiento(con_alguien=veces, solo=0.0, n=int(veces),
                                                                  grupos=[grupo])})


def _rodrigo_tarda_3() -> AprendizajeAmigos:
    return AprendizajeAmigos(personas={"RODRIGO P": HabitoPersona(contraparte="RODRIGO P", retrasos_dias=[2, 3, 3],
                                                                   retraso_p75_dias=3, paga_solo=3)})


@pytest.fixture
def usuario(monkeypatch):
    """`preparar(modo, aprendizaje, momentos={día: [Momento]})` carga un usuario de simulación con el motor simulado.
    `llamadas` guarda los argumentos con que el orquestador llama al motor (para ver `compania`)."""
    estado: dict = {"momentos": {}, "llamadas": []}

    def procesar(uid, nuevos, hoy, perfil=None, **kwargs):
        estado["llamadas"].append(kwargs)
        return [m.model_copy(update={"fecha": hoy}) for m in estado["momentos"].get(hoy, [])]

    monkeypatch.setattr(orq.motor, "procesar", procesar)

    def preparar(modo: str = "aprende", aprendizaje: AprendizajeAmigos | None = None,
                 momentos: dict[date, list[Momento]] | None = None, movimientos: list[Movimiento] | None = None):
        estado["momentos"] = momentos or {}
        modelo = personalizacion.nuevo_modelo(UID)
        modelo.aprendizaje = (aprendizaje or AprendizajeAmigos()).model_copy(update={"modo": modo})
        base = [Movimiento(id="h1", fecha=date(2026, 11, 2), concepto="MERCADONA", comercio="Mercadona",
                           importe=Decimal("-12.00"), canal="tarjeta", saldo=Decimal("500.00")),
                _pago(), *(movimientos or [])]
        orq.cargar_simulacion(UID, base, ACTIVACION, contactos=dict(CONTACTOS), modelo=modelo)
        orq.activar(UID, ["gasto_compartido"], {"copiloto": True, "memoria": True})
        return estado

    return preparar


def _avanzar_hasta(dia: date) -> None:
    hoy = date.fromisoformat(orq.estado_usuario(UID)["hoy"])
    while hoy < dia:
        hoy += timedelta(days=1)
        orq.avanzar_dia(UID, hoy)


def _modelo():
    return orq._leer(UID, "modelo")


def _caso(caso_id: str) -> Caso:
    return next(c for c in casos.cargar(UID) if c.id == caso_id)


# --- Piezas puras -------------------------------------------------------------------------------

@pytest.mark.parametrize("senal, aviso", [("media", "resumen"), ("debil", "silencioso")])
def test_con_reglas_la_escalera_deja_el_aviso_de_siempre(senal, aviso):
    momento = _momento_individual(senal)
    antes = casos.crear_desde_momento(momento, D)
    for apr in (AprendizajeAmigos(modo="reglas"), AprendizajeAmigos(), _tasca_aprendida().model_copy(update={"modo": "reglas"})):
        pregunta = escalera.nivel_pregunta(apr, comercio=TASCA, tipo_comercio="restaurante", fecha=D,
                                           importe=Decimal("48"), senal=senal, umbral=Decimal("20"))
        caso = casos.crear_desde_momento(momento, D, pregunta=pregunta)
        assert (caso.aviso, caso.escenario, caso.deudores) == (antes.aviso, "pago_individual", []) == (aviso, "pago_individual", [])
        assert caso.sugerencia is None and caso.pregunta_nivel == (1 if senal == "media" else 0)


def test_la_escalera_manda_y_sus_motivos_van_al_historial():
    pregunta = escalera.nivel_pregunta(_tasca_aprendida(), comercio=TASCA, tipo_comercio="restaurante", fecha=D,
                                       importe=Decimal("48"), senal="aprendida", umbral=Decimal("20"))
    caso = casos.crear_desde_momento(_momento_individual("aprendida"), D, pregunta=pregunta)
    assert (caso.pregunta_nivel, caso.aviso) == (3, "notificar")
    assert caso.sugerencia.personas == ["LAURA M", "MARCOS R"]
    assert caso.sugerencia.cuotas == {"LAURA M": Decimal("16.00"), "MARCOS R": Decimal("16.00")}
    assert any("Escalera de la pregunta, nivel 3" in h.cambio for h in caso.historial)


def test_texto_de_la_pregunta_de_un_toque_con_cifras_del_codigo():
    caso = Caso(id="c", usuario_id=UID, escenario="pago_individual", creado=D, aviso="notificar",
                hechos={"importe_total": "48.00", "comercio": TASCA},
                sugerencia=SugerenciaReparto(personas=["LAURA M", "MARCOS R"],
                                             cuotas={"LAURA M": Decimal("16"), "MARCOS R": Decimal("16")}, confianza=0.8))
    nombres = {"LAURA M": "Laura M.", "MARCOS R": "Marcos R."}
    assert casos.texto_pregunta(caso, nombres) == TEXTO_NIVEL_3
    propuesta = casos.propuesta_pregunta(caso, AHORA, nombres)
    assert propuesta.id == "prop-preg-c" and propuesta.mensaje_notificacion == TEXTO_NIVEL_3
    assert [a.accion_id for a in propuesta.acciones_ofrecidas] == ["recordar"]       # solo preguntar: no mueve dinero
    assert propuesta.valor_estimado_eur == Decimal("32") and "<datos>" in propuesta.contexto_llamada
    sin_cuotas = caso.model_copy(update={"sugerencia": caso.sugerencia.model_copy(update={"cuotas": {}})})
    assert casos.texto_pregunta(sin_cuotas, nombres) == "48 € en La Tasca: ¿con Laura y Marcos?"


def test_las_personas_estimadas_del_motor_pasan_a_los_hechos_y_al_historial():
    momento = _momento_individual("media", importe="19.00")
    momento = momento.model_copy(update={"datos": {**momento.datos, "personas_estimadas": 2,
                                                   "precio_persona": Decimal("9.50"),
                                                   "motivo_personas": "19,00 € en Cines Fotograma son unas 2 entradas"}})
    caso = casos.crear_desde_momento(momento, D)
    assert (caso.hechos["personas_estimadas"], caso.hechos["precio_persona"]) == (2, "9.50")
    assert caso.hechos["motivo_personas"] == "19,00 € en Cines Fotograma son unas 2 entradas"
    assert any("unas 2 entradas" in h.cambio for h in caso.historial)
    assert casos.texto_pregunta(caso).endswith("¿fuiste con alguien? (unas 2 personas)")
    assert "personas_estimadas" not in casos.crear_desde_momento(_momento_individual("media"), D).hechos


def test_listo_para_avisar_respeta_el_plazo_de_cada_persona():
    caso = Caso(id="c", usuario_id=UID, escenario="gasto_compartido", creado=D, avisar_desde=D + timedelta(days=2),
                hechos={"fecha": D.isoformat()},
                deudores=[Deudor(contraparte="LAURA M", cuota=Decimal("16")),
                          Deudor(contraparte="RODRIGO P", cuota=Decimal("16"), avisar_desde=D + timedelta(days=4))])
    assert [casos.listo_para_avisar(caso, D + timedelta(days=n)) for n in range(2, 6)] == [False, False, True, True]
    pagado = caso.model_copy(update={"deudores": [caso.deudores[0], caso.deudores[1].model_copy(
        update={"estado": "saldada", "saldada": D + timedelta(days=1)})]})
    assert casos.listo_para_avisar(pagado, D + timedelta(days=2))   # quien ya pagó no retrasa a los demás
    pospuesto = casos.posponer(caso, D + timedelta(days=4), dias=3)  # «ahora no» sigue mandando
    assert not casos.listo_para_avisar(pospuesto, D + timedelta(days=5))


def test_no_se_abre_un_pago_individual_sobre_un_cargo_que_ya_tiene_caso():
    momento = _momento_individual("media")
    del_chat = Caso(id="caso-u-p1", usuario_id=UID, escenario="gasto_compartido", creado=D, origen="chat",
                    hechos={"movimiento_origen": "p1", "pago_id": "p1"})
    assert casos.abre_caso([], momento)
    assert not casos.abre_caso([del_chat], momento)
    assert not casos.abre_caso([del_chat.model_copy(update={"estado": "saldado"})], momento)   # aunque ya se cerró
    assert not casos.abre_caso([casos.crear_desde_momento(momento, D)], momento)               # ni repetido


def test_nadie_me_debe_deja_sin_deuda_en_los_hechos():
    from backend.casos import llamada
    caso = casos.crear_desde_momento(_momento_individual("media"), D)
    cambio = llamada.aplicar(caso, "nadie_me_debe", D)
    assert cambio.caso.estado == "descartado" and cambio.caso.hechos[casos.CLAVE_SIN_DEUDA] is True
    evento = A.eventos_de_caso(caso, cambio.caso, "respuesta", D)[0]
    assert (evento.acompanado, evento.forma) == (True, "cada_uno_lo_suyo")    # acompañado, sin deuda: no es «iba solo»


def test_responder_duda_cierra_la_pregunta():
    caso = Caso(id="c", usuario_id=UID, estado="dudoso", creado=D,
                hechos={"pregunta": {"texto": "¿Daniel pagó lo de Marcos?", "candidatos": ["MARCOS R"],
                                     "estado": "pendiente"}},
                deudores=[Deudor(contraparte="MARCOS R", cuota=Decimal("10")), Deudor(contraparte="ANA L", cuota=Decimal("10"))])
    from backend.casos import llamada
    nuevo = llamada.aplicar(caso, "responder_duda", D, respuesta="sí").caso
    assert nuevo.hechos["pregunta"]["estado"] == "respondida" and nuevo.estado == "abierto"
    with pytest.raises(ValueError, match="pregunta pendiente"):
        llamada.aplicar(nuevo, "responder_duda", D, respuesta="no")


# --- Con el orquestador ---------------------------------------------------------------------------

def test_un_amigo_con_p75_3_no_recibe_recordatorio_antes_del_dia_3(usuario):
    usuario(aprendizaje=_rodrigo_tarda_3())
    _avanzar_hasta(D)
    r = orq.crear_caso_usuario(UID, "p1", [{"contraparte": "Rodrigo P.", "importe": "16.00"}])
    caso = _caso(r["id"])
    assert caso.deudores[0].avisar_desde == D + timedelta(days=4)            # pago + p75 (3) + 1
    for n in range(1, 4):
        _avanzar_hasta(D + timedelta(days=n))
        assert _caso(r["id"]).propuesta_id is None, f"recordatorio a destiempo el día {n}"
    _avanzar_hasta(D + timedelta(days=4))
    propuesta = _caso(r["id"]).propuesta_id
    assert propuesta, "el día 4 sí toca recordárselo"
    acciones = next(n for n in orq.notificaciones(UID) if n["propuesta"]["id"] == propuesta)["propuesta"]["acciones_ofrecidas"]
    assert any(a["accion_id"] == "pedir_bizum" and a["parametros"].get("contraparte") == "RODRIGO P" for a in acciones)


def test_con_reglas_el_mismo_amigo_se_recuerda_a_los_2_dias_como_siempre(usuario):
    usuario(modo="reglas", aprendizaje=_rodrigo_tarda_3())
    _avanzar_hasta(D)
    r = orq.crear_caso_usuario(UID, "p1", [{"contraparte": "Rodrigo P.", "importe": "16.00"}])
    assert _caso(r["id"]).deudores[0].avisar_desde is None
    _avanzar_hasta(D + timedelta(days=2))
    assert _caso(r["id"]).propuesta_id


def test_nivel_3_genera_la_notificacion_de_un_toque(usuario):
    estado = usuario(aprendizaje=_tasca_aprendida(), momentos={D + timedelta(days=2): [_momento_individual("aprendida")]})
    _avanzar_hasta(D + timedelta(days=2))
    assert estado["llamadas"][-1]["compania"] == {f"c:{TASCA}": pytest.approx(0.833, abs=0.001)}
    caso = _caso("caso-mom-ind-p1")
    assert (caso.pregunta_nivel, caso.aviso, caso.propuesta_id) == (3, "notificar", "prop-preg-caso-mom-ind-p1")
    assert "avisado_el" in caso.hechos                                       # el portero no la repite
    avisos = orq.notificaciones(UID, "ahora")
    assert [a["propuesta"]["mensaje_notificacion"] for a in avisos] == [TEXTO_NIVEL_3]
    assert avisos[0]["decision"]["motivos"][0].startswith("Aquí sueles pagar tú por el grupo")
    resumen = next(c for c in orq.casos_usuario(UID) if c["id"] == caso.id)
    assert (resumen["pregunta_nivel"], resumen["origen"]) == (3, "motor")
    assert resumen["sugerencia"]["cuotas"] == {"LAURA M": "16.00", "MARCOS R": "16.00"}
    # Aceptar la sugerencia (con las mismas personas) convierte el caso y lo aprende como aceptada.
    orq.actualizar_caso_llamada(UID, caso.id, "con_personas", persona="Laura M., Marcos R.")
    assert _caso(caso.id).escenario == "gasto_compartido"
    assert _modelo().aprendizaje.por_comercio[TASCA].aceptadas_seguidas == 1
    estados = {n["propuesta_id"]: n["estado"] for n in orq._leer(UID, "notificaciones", [])}
    assert estados["prop-preg-caso-mom-ind-p1"] == "resuelta"


def test_el_nivel_3_pasa_por_decidir_y_respeta_el_silencio_del_usuario(usuario):
    from backend.plataforma.tipos import Silencio
    usuario(aprendizaje=_tasca_aprendida(), momentos={D + timedelta(days=2): [_momento_individual("aprendida")]})
    modelo = _modelo()
    modelo.preferencias.silencios.append(Silencio(ambito="comercio", valor=TASCA, desde=D, origen="feedback"))
    orq.alm.guardar(UID, "modelo", modelo)
    _avanzar_hasta(D + timedelta(days=2))
    caso = _caso("caso-mom-ind-p1")
    assert caso.pregunta_nivel == 3 and caso.aviso == "silencioso" and not orq.notificaciones(UID, "ahora")


def test_las_respuestas_el_boton_y_los_bizums_ensenan(usuario):
    otro = _pago("p2", D + timedelta(days=7))
    usuario(momentos={D + timedelta(days=2): [_momento_individual("media")]}, movimientos=[
        otro, _bizum("b1", D + timedelta(days=3), "16.00", "Laura Martin")])
    _avanzar_hasta(D + timedelta(days=2))
    caso = _caso("caso-mom-ind-p1")
    assert (caso.pregunta_nivel, caso.aviso) == (1, "resumen")              # sin datos: lo de siempre
    orq.actualizar_caso_llamada(UID, caso.id, "con_personas", persona="Laura M., Marcos R.")
    apr = _modelo().aprendizaje
    assert apr.por_comercio[TASCA].con_alguien == 1 and apr.por_tipo_franja["restaurante|finde"].con_alguien == 1
    assert apr.por_comercio[TASCA].grupos[0].miembros == ["LAURA M", "MARCOS R"]
    _avanzar_hasta(D + timedelta(days=3))                                    # Laura paga sola a los 3 días
    laura = _modelo().aprendizaje.personas["LAURA M"]
    assert laura.retrasos_dias == [3] and laura.canales == {"bizum": 1}
    _avanzar_hasta(D + timedelta(days=7))
    orq.crear_caso_usuario(UID, "p2", [{"contraparte": "Marcos R.", "importe": "24.00"}])   # el botón también enseña
    assert _modelo().aprendizaje.por_comercio[TASCA].n == 2


def test_el_chat_crea_el_caso_y_el_motor_ya_no_abre_un_pago_individual(usuario):
    usuario(momentos={D + timedelta(days=2): [_momento_individual("media")]})
    _avanzar_hasta(D)
    orq.crear_caso_usuario(UID, "p1", [{"contraparte": "Laura M.", "importe": "16.00"},
                                       {"contraparte": "Marcos R.", "importe": "16.00"}], origen="chat")
    assert _modelo().aprendizaje.por_comercio[TASCA].con_alguien == 1
    _avanzar_hasta(D + timedelta(days=2))
    assert [c.escenario for c in casos.cargar(UID)] == ["gasto_compartido"]   # ningún pago_individual repetido


def test_las_preguntas_sin_respuesta_cuentan_como_ignoradas(usuario):
    usuario(momentos={D + timedelta(days=2): [_momento_individual("media")]})
    _avanzar_hasta(D + timedelta(days=4))
    assert TASCA not in _modelo().aprendizaje.por_comercio
    _avanzar_hasta(D + timedelta(days=5))                                    # 3 días en el Resumen sin respuesta
    assert _modelo().aprendizaje.por_comercio[TASCA].ignoradas == 1
    _avanzar_hasta(D + timedelta(days=8))
    assert _modelo().aprendizaje.por_comercio[TASCA].ignoradas == 1          # una sola vez por pregunta


def test_con_reglas_no_aprende_ni_pasa_compania_al_motor(usuario):
    estado = usuario(modo="reglas", aprendizaje=_tasca_aprendida(),
                     momentos={D + timedelta(days=2): [_momento_individual("media")]},
                     movimientos=[_bizum("b1", D + timedelta(days=3), "16.00", "Laura Martin")])
    _avanzar_hasta(D + timedelta(days=2))
    assert all("compania" not in kw for kw in estado["llamadas"])
    caso = _caso("caso-mom-ind-p1")
    assert (caso.aviso, caso.sugerencia, caso.propuesta_id) == ("resumen", None, None) and not orq.notificaciones(UID, "ahora")
    orq.actualizar_caso_llamada(UID, caso.id, "con_personas", persona="Laura M., Marcos R.")
    _avanzar_hasta(D + timedelta(days=6))
    assert _modelo().aprendizaje == _tasca_aprendida().model_copy(update={"modo": "reglas"})
