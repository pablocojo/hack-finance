"""Tests del orquestador con motor, módulos, personalización y acciones SUSTITUIDOS por stubs
(no dependen de lo que hagan los otros hilos)."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest

from backend.plataforma import almacenamiento as alm
from backend.plataforma import orquestador as orq
from backend.plataforma.tipos import (
    Decision,
    Feedback,
    HechoAprendido,
    ModeloUsuario,
    Momento,
    Movimiento,
    PerfilUsuario,
    Propuesta,
    ResultadoAccion,
    TarjetaConfirmacion,
)

UID = "lucia"
ACTIVACION = date(2026, 11, 6)


def _mov(id_: str, fecha: date, importe: str, saldo: str | None = None, **extra) -> Movimiento:
    return Movimiento(id=id_, fecha=fecha, concepto=f"CONCEPTO {id_}", importe=Decimal(importe),
                      saldo=Decimal(saldo) if saldo else None, **extra)


class Falsos:
    """Registra las llamadas y devuelve datos fijos."""

    def __init__(self) -> None:
        self.llamadas: list[str] = []
        self.cerradas: list[tuple] = []
        self.tokens: dict[str, str] = {}
        self.usados: set[str] = set()
        self.decision = "notificar_ahora"

    def montar(self, monkeypatch) -> "Falsos":
        f = self

        def procesar(uid, nuevos, hoy, perfil=None):
            f.llamadas.append("procesar")
            momentos = []
            for m in nuevos:
                if m.id.startswith("c"):
                    momentos.append(Momento(id=f"mom-{m.id}", tipo="gasto_compartido", usuario_id=uid, fecha=hoy,
                                            movimientos=[m.id], datos={"importe_pendiente": "24.00"}, confianza=0.9,
                                            impacto_eur=Decimal("24"), explicacion="Falta 1 Bizum.", detector="g", version="1"))
                if m.id.startswith("v"):
                    momentos.append(Momento(id=f"mom-{m.id}", tipo="prueba_gratuita", usuario_id=uid, fecha=hoy,
                                            movimientos=[m.id], datos={"fecha_primer_cobro": "2026-11-13"}, confianza=0.9,
                                            explicacion="Acaba la prueba.", detector="p", version="1"))
            return momentos

        def proponer(momento, modelo):
            f.llamadas.append("proponer")
            acciones_ = ([{"accion_id": "pedir_bizum", "parametros": {"importe": "24.00"}}, {"accion_id": "recordar"}]
                         if momento.tipo == "gasto_compartido"
                         else [{"accion_id": "cancelar_suscripcion", "parametros": {"comercio": "STREAMFLIX"}},
                               {"accion_id": "recordar"}])
            return [Propuesta(id=f"prop-{momento.id}", modulo_id="m", momento_id=momento.id, usuario_id=momento.usuario_id,
                              titulo="Titulo", mensaje_notificacion="Msg", contexto_llamada="Ctx",
                              acciones_ofrecidas=acciones_, tipo_momento=momento.tipo,
                              comercio="STREAMFLIX" if momento.tipo == "prueba_gratuita" else None,
                              confianza=0.9, creada=datetime(2026, 11, 9, 20, 30))]

        def ordenar(propuesta, modelo):
            f.llamadas.append("ordenar_acciones")
            return propuesta

        def decidir(propuesta, modelo, ahora):
            f.llamadas.append("decidir")
            f.ahora = ahora
            return Decision(propuesta_id=propuesta.id, accion=f.decision, puntuacion=1.0, probabilidad_util=0.8,
                            motivos=["Ahorra 24 EUR."], politica="stub")

        def registrar_decision(modelo, propuesta, decision):
            f.llamadas.append("registrar_decision")
            return modelo

        def observar(modelo, movimientos, hoy):
            f.llamadas.append("observar")
            return modelo

        def perfilar(historial, hoy, anterior):
            f.llamadas.append("perfilar")
            return PerfilUsuario(calculado=hoy, dias_historial=len(historial))

        def aprender(feedback, modelo):
            f.llamadas.append("aprender")
            nuevo = modelo.model_copy(deep=True)
            nuevo.hechos_aprendidos.append(HechoAprendido(id=f"h-{feedback.resultado}", texto="Aprendido",
                                                          creado=feedback.fecha.date(), origen="feedback"))
            return nuevo

        def registrar_accion(modelo, propuesta, resultado):
            f.llamadas.append("registrar_accion")
            nuevo = modelo.model_copy(deep=True)
            nuevo.elecciones[resultado.accion_id] = nuevo.elecciones.get(resultado.accion_id, 0) + 1
            return nuevo

        def preparar(accion_id, parametros, propuesta_id, usuario_id):
            token = f"tok-{len(f.tokens) + 1}"
            f.tokens[token] = accion_id
            return TarjetaConfirmacion(accion_id=accion_id, propuesta_id=propuesta_id, titulo="Tarjeta",
                                       token_confirmacion=token, caduca=datetime(2026, 11, 20),
                                       parametros_legibles={k: str(v) for k, v in parametros.items()})

        def ejecutar(token, usuario_id):
            if token in f.usados:
                raise ValueError("El token ya se usó.")
            if token not in f.tokens:
                raise ValueError("Token no válido.")
            f.usados.add(token)
            return ResultadoAccion(accion_id=f.tokens[token], ok=True, mensaje="Hecho (simulado).")

        monkeypatch.setattr(orq, "motor", SimpleNamespace(
            procesar=procesar, enriquecer=lambda movs: list(movs), cargar_historial=lambda *a: f.llamadas.append("cargar_historial"),
            exportar_estado=lambda uid: {"x": 1}, importar_estado=lambda uid, e: None, reiniciar=lambda uid: None,
            cerrar_prueba=lambda uid, comercio, motivo, hoy: f.cerradas.append((comercio, motivo, hoy)),
            comercios_pendientes=lambda uid: []))
        monkeypatch.setattr(orq, "modulos", SimpleNamespace(proponer=proponer))
        monkeypatch.setattr(orq, "personalizacion", SimpleNamespace(
            nuevo_modelo=lambda uid: ModeloUsuario(usuario_id=uid), perfilar=perfilar, ordenar_acciones=ordenar,
            decidir=decidir, registrar_decision=registrar_decision, observar=observar, aprender=aprender,
            registrar_accion=registrar_accion))
        monkeypatch.setattr(orq, "acciones", SimpleNamespace(preparar=preparar, ejecutar=ejecutar))
        escenario = {"id": "demo-test", "usuario_id": UID, "activacion": ACTIVACION, "movimientos": [
            _mov("h1", date(2026, 11, 5), "-10.00", "500.00"),
            _mov("c1", date(2026, 11, 9), "-120.00", "380.00"),
            _mov("v1", date(2026, 11, 10), "0.00", "380.00"),
        ]}
        monkeypatch.setattr(orq, "_leer_escenario", lambda escenario_id: escenario)
        return f


@pytest.fixture
def falsos(monkeypatch) -> Falsos:
    return Falsos().montar(monkeypatch)


@pytest.fixture
def activo(falsos):
    orq.cargar_escenario("demo-test")
    orq.activar(UID, ["cena_compartida"], {"avisos": True, "memoria": True})
    return falsos


def _avanzar_hasta(dia: date) -> list[Decision]:
    decisiones: list[Decision] = []
    hoy = date.fromisoformat(orq.estado_usuario(UID)["hoy"])
    while hoy < dia:
        hoy += timedelta(days=1)
        decisiones += orq.avanzar_dia(UID, hoy)
    return decisiones


def test_cargar_y_activar(falsos):
    r = orq.cargar_escenario("demo-test")
    assert r == {"usuario_id": UID, "hoy": "2026-11-06", "activacion": "2026-11-06"}
    assert orq.estado_usuario(UID)["activado"] is False
    modelo = orq.activar(UID, ["cena_compartida"], {"avisos": True, "memoria": False})
    assert falsos.llamadas == ["cargar_historial", "perfilar"]
    assert modelo.modulos_activos == ["cena_compartida"] and "avisos" in modelo.consentimientos
    assert "memoria" not in modelo.consentimientos
    estado = orq.estado_usuario(UID)
    assert estado["activado"] and estado["saldo"] == "500.00"


def test_avanzar_sin_activar_o_hacia_atras_falla(falsos):
    orq.cargar_escenario("demo-test")
    with pytest.raises(ValueError, match="activado"):
        orq.avanzar_dia(UID, date(2026, 11, 7))
    orq.activar(UID, [], {})
    with pytest.raises(ValueError, match="no retrocede"):
        orq.avanzar_dia(UID, date(2026, 11, 6))
    with pytest.raises(orq.NoEncontrado):
        orq.estado_usuario("nadie")


def test_orden_de_llamadas_de_un_dia(activo):
    _avanzar_hasta(date(2026, 11, 8))
    activo.llamadas.clear()
    decisiones = orq.avanzar_dia(UID, date(2026, 11, 9))
    assert activo.llamadas == ["procesar", "proponer", "ordenar_acciones", "decidir", "registrar_decision", "observar"]
    assert len(decisiones) == 1
    assert activo.ahora == datetime(2026, 11, 9, 20, 30)  # hora por defecto


def test_ahora_explicito(activo):
    _avanzar_hasta(date(2026, 11, 8))
    orq.avanzar_dia(UID, date(2026, 11, 9), ahora=datetime(2026, 11, 9, 8, 0))
    assert activo.ahora == datetime(2026, 11, 9, 8, 0)


def test_perfilar_cada_siete_dias(activo):
    _avanzar_hasta(date(2026, 11, 12))
    activo.llamadas.clear()
    orq.avanzar_dia(UID, date(2026, 11, 13))  # 7 días desde la activación
    assert activo.llamadas[:2] == ["perfilar", "procesar"]
    activo.llamadas.clear()
    orq.avanzar_dia(UID, date(2026, 11, 14))
    assert "perfilar" not in activo.llamadas


def test_un_dia_produce_momento_propuesta_decision_y_se_guarda(activo):
    decisiones = _avanzar_hasta(date(2026, 11, 9))
    assert [d.accion for d in decisiones] == ["notificar_ahora"]
    assert [m.id for m in alm.cargar(UID, "momentos", list[Momento])] == ["mom-c1"]
    assert [p.id for p in alm.cargar(UID, "propuestas", list[Propuesta])] == ["prop-mom-c1"]
    assert len(alm.cargar(UID, "decisiones", list[Decision])) == 1
    assert orq.estado_usuario(UID) == {"hoy": "2026-11-09", "activado": True, "saldo": "380.00",
                                       "contadores": {"momentos": 1, "ahora": 1, "resumen": 0, "silenciadas": 0}}
    bandeja = orq.notificaciones(UID, "ahora")
    assert bandeja[0]["estado"] == "nueva" and bandeja[0]["propuesta"]["valor_estimado_eur"] is None
    assert orq.notificaciones(UID, "resumen") == []
    detalle = orq.propuesta_detalle(UID, "prop-mom-c1")
    assert detalle["momento"]["id"] == "mom-c1" and [m["id"] for m in detalle["movimientos"]] == ["c1"]
    assert detalle["momento"]["impacto_eur"] == "24.00"
    assert orq.notificaciones(UID)[0]["estado"] == "vista"
    with pytest.raises(orq.NoEncontrado):
        orq.propuesta_detalle(UID, "no-existe")


def test_reproducir_emite_en_orden_y_pausa(activo):
    eventos = list(orq.reproducir(UID, 4))
    tipos = [e.tipo for e in eventos]
    assert tipos == ["dia", "dia", "dia", "momento", "propuesta", "decision", "dia", "momento", "propuesta", "decision", "fin"]
    assert eventos[-1].datos["hoy"] == "2026-11-10" and eventos[-1].datos["contadores"]["ahora"] == 2
    assert eventos[3].datos["tipo"] == "gasto_compartido"

    orq.cargar_escenario("demo-test")
    orq.activar(UID, [], {})
    eventos = list(orq.reproducir(UID, 10, pausar_en="gasto_compartido"))
    assert eventos[-1].tipo == "fin" and eventos[-1].datos["hoy"] == "2026-11-09" and eventos[-1].datos["pausado"]
    with pytest.raises(ValueError):
        list(orq.reproducir(UID, 0))


def test_feedback_guarda_y_devuelve_hechos(activo):
    _avanzar_hasta(date(2026, 11, 9))
    hechos = orq.registrar_feedback(Feedback(propuesta_id="prop-mom-c1", usuario_id=UID, resultado="rechazada",
                                             canal="app", fecha=datetime(2026, 11, 9, 21, 0)))
    assert [h.id for h in hechos] == ["h-rechazada"]
    assert alm.cargar(UID, "modelo", ModeloUsuario).hechos_aprendidos[0].id == "h-rechazada"
    assert orq.notificaciones(UID)[0]["estado"] == "rechazada"
    with pytest.raises(orq.NoEncontrado):
        orq.registrar_feedback(Feedback(propuesta_id="x", usuario_id=UID, resultado="resuelta", canal="app",
                                        fecha=datetime(2026, 11, 9)))


def test_preparar_exige_accion_ofrecida(activo):
    _avanzar_hasta(date(2026, 11, 9))
    with pytest.raises(orq.Prohibido):
        orq.preparar_accion(UID, "prop-mom-c1", "cancelar_suscripcion", {})
    with pytest.raises(orq.Prohibido):
        orq.preparar_accion(UID, "prop-mom-c1", "inventada", {})
    tarjeta = orq.preparar_accion(UID, "prop-mom-c1", "pedir_bizum", {"importe": "24.00"})
    assert tarjeta.token_confirmacion == "tok-1"


def test_confirmar_registra_accion_token_unico_y_sin_token_en_disco(activo, tmp_path):
    _avanzar_hasta(date(2026, 11, 9))
    tarjeta = orq.preparar_accion(UID, "prop-mom-c1", "pedir_bizum", {"importe": "24.00"})
    resultado = orq.confirmar_accion(UID, tarjeta.token_confirmacion)
    assert resultado.ok and "registrar_accion" in activo.llamadas
    assert alm.cargar(UID, "modelo", ModeloUsuario).elecciones == {"pedir_bizum": 1}
    assert orq.notificaciones(UID)[0]["estado"] == "resuelta"
    with pytest.raises(ValueError, match="ya se usó"):
        orq.confirmar_accion(UID, tarjeta.token_confirmacion)
    for ruta in alm.carpeta_usuario(UID).rglob("*"):
        if ruta.is_file():
            assert tarjeta.token_confirmacion not in ruta.read_text(encoding="utf-8")


def _preparar_cancelacion(bloquear: bool):
    _avanzar_hasta(date(2026, 11, 10))
    tarjeta = orq.preparar_accion(UID, "prop-mom-v1", "cancelar_suscripcion",
                                  {"comercio": "STREAMFLIX", "bloquear_cobros": bloquear})
    return orq.confirmar_accion(UID, tarjeta.token_confirmacion)


def test_cancelar_con_bloqueo_cierra_la_prueba(activo):
    _preparar_cancelacion(True)
    assert activo.cerradas == [("STREAMFLIX", "cancelada", date(2026, 11, 10))]
    assert alm.cargar(UID, "recordatorios") == []


def test_cancelar_sin_bloqueo_deja_baja_guiada_y_crea_recordatorio(activo):
    _preparar_cancelacion(False)
    assert activo.cerradas == [("STREAMFLIX", "baja_guiada", date(2026, 11, 10))]
    (recordatorio,) = alm.cargar(UID, "recordatorios")
    assert recordatorio["fecha"] == "2026-11-12"  # el día antes del cobro (13/11)
    _avanzar_hasta(date(2026, 11, 11))
    assert not any(n["propuesta"]["id"].startswith("rec-") for n in orq.notificaciones(UID))
    _avanzar_hasta(date(2026, 11, 12))
    aviso = [n for n in orq.notificaciones(UID, "ahora") if n["propuesta"]["id"].startswith("rec-")]
    assert len(aviso) == 1 and "darte de baja de STREAMFLIX" in aviso[0]["propuesta"]["mensaje_notificacion"]


def test_aviso_sin_respuesta_pasa_a_ignorado_a_las_48h(activo):
    _avanzar_hasta(date(2026, 11, 9))
    activo.llamadas.clear()
    orq.avanzar_dia(UID, date(2026, 11, 10), ahora=datetime(2026, 11, 11, 21, 0))
    assert "aprender" in activo.llamadas
    assert [n["estado"] for n in orq.notificaciones(UID) if n["propuesta"]["id"] == "prop-mom-c1"] == ["ignorada"]


def test_busqueda_web_solo_si_esta_activa(activo, monkeypatch):
    llamadas = []
    monkeypatch.setattr(orq.motor, "comercios_pendientes", lambda uid: llamadas.append(uid) or [])
    orq.avanzar_dia(UID, date(2026, 11, 7))
    assert llamadas == []
    monkeypatch.setenv("BUSQUEDA_WEB", "on")
    orq.avanzar_dia(UID, date(2026, 11, 8))
    assert llamadas == [UID]
