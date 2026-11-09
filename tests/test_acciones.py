"""Registro cerrado de acciones: token, límites, idempotencia, banco simulado y auditoría."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

import pytest

import backend.acciones as acciones
from backend.acciones import banco_sim, tokens
from backend.acciones.errores import ErrorAccion
from backend.acciones.registro import REGISTRO
from backend.plataforma import almacenamiento
from backend.plataforma.tipos import ACCIONES, AccionOfrecida, Limites, Propuesta

U = "lucia"
PID = "prop-1"


def propuesta(usuario=U, pid=PID, ofrecidas=None) -> Propuesta:
    ofrecidas = ofrecidas or [
        AccionOfrecida(accion_id="pedir_bizum",
                       parametros={"contraparte": "MARCOS R", "importe": "24.00", "concepto": "Tu parte de La Tasca"},
                       limites=Limites(importe_max=Decimal("24.00"), contrapartes=["MARCOS R"])),
        AccionOfrecida(accion_id="recordar", parametros={"cuando": "+3d", "texto": "Mirar lo de La Tasca"}),
        AccionOfrecida(accion_id="cancelar_suscripcion", parametros={"comercio": "Streamflix", "bloquear_cobros": False}),
    ]
    return Propuesta(id=pid, modulo_id="m", momento_id="mm", usuario_id=usuario, titulo="t", mensaje_notificacion="n",
                     contexto_llamada="c", acciones_ofrecidas=ofrecidas, tipo_momento="gasto_compartido", confianza=0.9,
                     creada=datetime(2026, 11, 9, 20, 30))


@pytest.fixture(autouse=True)
def con_propuesta():
    almacenamiento.guardar(U, "propuestas", [propuesta()])
    almacenamiento.guardar("pablo", "propuestas", [propuesta("pablo")])


BIZUM = {"contraparte": "MARCOS R", "importe": "24.00", "concepto": "Tu parte de La Tasca"}


def codigos(usuario=U):
    return [r.get("motivo", "") for r in almacenamiento.leer_auditoria(usuario) if r["evento"] == "rechazada"]


def test_el_registro_tiene_exactamente_las_seis_del_contrato():
    assert set(REGISTRO) == set(ACCIONES) and len(ACCIONES) == 6
    assert "preparar_baja" not in REGISTRO


def test_preparar_no_tiene_efectos_y_ejecutar_pide_bizum():
    t = acciones.preparar("pedir_bizum", BIZUM, PID, U)
    assert t.simulada and t.token_confirmacion and t.parametros_legibles["Importe"] == "24,00 €"
    assert banco_sim.cargar(U)["solicitudes_bizum"] == []
    r = acciones.ejecutar(t.token_confirmacion, U)
    assert r.ok and r.simulada and r.deshacer is not None
    sol = banco_sim.cargar(U)["solicitudes_bizum"]
    assert len(sol) == 1 and sol[0]["estado"] == "pendiente" and sol[0]["importe"] == "24.00"
    eventos = [x["evento"] for x in almacenamiento.leer_auditoria(U)]
    assert eventos == ["preparada", "ejecutada"]


def test_accion_fuera_de_la_lista_o_de_la_propuesta():
    with pytest.raises(ErrorAccion) as e:
        acciones.preparar("transferir_todo", {}, PID, U)
    assert e.value.codigo == "accion_no_ofrecida" and e.value.http == 403
    with pytest.raises(ErrorAccion) as e:
        acciones.preparar("bloquear_comercio", {"comercio": "X"}, PID, U)   # válida pero no ofrecida
    assert e.value.codigo == "accion_no_ofrecida"
    with pytest.raises(ErrorAccion) as e:
        acciones.preparar("recordar", {"cuando": "+3d", "texto": "otro texto"}, PID, U)
    assert e.value.codigo == "accion_no_ofrecida"
    with pytest.raises(ErrorAccion) as e:
        acciones.preparar("recordar", {"cuando": "+3d", "texto": "Mirar lo de La Tasca"}, "no-existe", U)
    assert e.value.codigo == "propuesta_desconocida"
    assert len(codigos()) == 4


def test_importe_sobre_el_limite_o_contraparte_ajena():
    with pytest.raises(ErrorAccion) as e:
        acciones.preparar("pedir_bizum", {**BIZUM, "importe": "24.01"}, PID, U)
    assert e.value.codigo in ("accion_no_ofrecida", "fuera_de_limites")
    with pytest.raises(ErrorAccion):
        acciones.preparar("pedir_bizum", {**BIZUM, "contraparte": "OTRO X"}, PID, U)
    assert banco_sim.cargar(U)["solicitudes_bizum"] == []


def test_limites_se_comprueban_aunque_los_parametros_coincidan():
    # propuesta cuya acción ofrecida tiene un límite menor que su propio importe
    almacenamiento.guardar(U, "propuestas", [propuesta(ofrecidas=[AccionOfrecida(
        accion_id="pedir_bizum", parametros=BIZUM, limites=Limites(importe_max=Decimal("10.00"), contrapartes=["MARCOS R"]))])])
    with pytest.raises(ErrorAccion) as e:
        acciones.preparar("pedir_bizum", BIZUM, PID, U)
    assert e.value.codigo == "fuera_de_limites"


def test_parametros_no_validos():
    for malo in ({**BIZUM, "importe": "-5"}, {**BIZUM, "importe": "abc"}, {**BIZUM, "extra": 1},
                 {**BIZUM, "concepto": "x" * 61}):
        with pytest.raises(ErrorAccion) as e:
            acciones.preparar("pedir_bizum", malo, PID, U)
        assert e.value.codigo == "parametros_invalidos"


def test_token_de_un_solo_uso():
    t = acciones.preparar("recordar", {"cuando": "+3d", "texto": "Mirar lo de La Tasca"}, PID, U)
    acciones.ejecutar(t.token_confirmacion, U)
    with pytest.raises(ErrorAccion) as e:
        acciones.ejecutar(t.token_confirmacion, U)
    assert e.value.codigo == "token_usado" and e.value.http == 409
    assert len(banco_sim.cargar(U)["recordatorios"]) == 1
    assert any("token_usado" in m for m in codigos())


def test_token_caducado(monkeypatch):
    t = acciones.preparar("pedir_bizum", BIZUM, PID, U)
    ahora = datetime.now()
    monkeypatch.setattr(tokens, "ahora", lambda: ahora + timedelta(minutes=10, seconds=1))
    with pytest.raises(ErrorAccion) as e:
        acciones.ejecutar(t.token_confirmacion, U)
    assert e.value.codigo == "token_caducado" and e.value.http == 410
    assert banco_sim.cargar(U)["solicitudes_bizum"] == []
    assert t.caduca - datetime.now() <= timedelta(minutes=10)


def test_token_de_otro_usuario():
    t = acciones.preparar("pedir_bizum", BIZUM, PID, U)
    with pytest.raises(ErrorAccion):
        acciones.ejecutar(t.token_confirmacion, "pablo")
    assert banco_sim.cargar(U)["solicitudes_bizum"] == [] and codigos("pablo")


def test_token_de_otra_propuesta_o_usuario_alterado_en_la_entrada():
    t = acciones.preparar("pedir_bizum", BIZUM, PID, U)
    tabla = almacenamiento.cargar(U, "tokens")
    h = next(iter(tabla))
    tabla[h]["usuario_id"] = "pablo"
    almacenamiento.guardar(U, "tokens", tabla)
    with pytest.raises(ErrorAccion) as e:
        acciones.ejecutar(t.token_confirmacion, U)
    assert e.value.codigo == "token_otro_usuario"
    tabla[h]["usuario_id"] = U
    tabla[h]["propuesta_id"] = "prop-otra"
    almacenamiento.guardar(U, "tokens", tabla)
    with pytest.raises(ErrorAccion) as e:
        acciones.ejecutar(t.token_confirmacion, U)
    assert e.value.codigo == "propuesta_desconocida"


def test_parametros_alterados_tras_preparar():
    t = acciones.preparar("pedir_bizum", BIZUM, PID, U)
    tabla = almacenamiento.cargar(U, "tokens")
    h = next(iter(tabla))
    tabla[h]["parametros"]["importe"] = "99.00"
    almacenamiento.guardar(U, "tokens", tabla)
    with pytest.raises(ErrorAccion) as e:
        acciones.ejecutar(t.token_confirmacion, U)
    assert e.value.codigo == "parametros_alterados"
    assert banco_sim.cargar(U)["solicitudes_bizum"] == []


def test_la_propuesta_cambia_entre_preparar_y_ejecutar():
    t = acciones.preparar("pedir_bizum", BIZUM, PID, U)
    almacenamiento.guardar(U, "propuestas", [propuesta(ofrecidas=[AccionOfrecida(accion_id="recordar", parametros={"cuando": "+1d", "texto": "x"})])])
    with pytest.raises(ErrorAccion) as e:
        acciones.ejecutar(t.token_confirmacion, U)
    assert e.value.codigo == "accion_no_ofrecida"


def test_token_inexistente():
    with pytest.raises(ErrorAccion) as e:
        acciones.ejecutar("inventado", U)
    assert e.value.codigo == "token_desconocido"


def test_idempotencia_un_token_nuevo_no_repite_el_efecto():
    p = {"comercio": "Streamflix", "bloquear_cobros": False}
    r1 = acciones.ejecutar(acciones.preparar("cancelar_suscripcion", p, PID, U).token_confirmacion, U)
    r2 = acciones.ejecutar(acciones.preparar("cancelar_suscripcion", p, PID, U).token_confirmacion, U)
    assert r1.datos["resultado_id"] == r2.datos["resultado_id"]
    assert len(banco_sim.cargar(U)["bajas"]) == 1


def test_cancelar_suscripcion_con_bloqueo_y_deshacer():
    p = {"comercio": "Streamflix", "bloquear_cobros": True}
    t = acciones.preparar("cancelar_suscripcion", p, PID, U)
    assert t.detalle_baja is not None and t.detalle_baja.bloquea_cobros
    assert "no vale para recibos domiciliados" in t.parametros_legibles["Aviso"]
    r = acciones.ejecutar(t.token_confirmacion, U)
    est = banco_sim.cargar(U)
    assert est["bajas"][0]["estado"] == "guiada" and est["bloqueos"][0]["tipo"] == "recurrente"
    acciones.deshacer(r.deshacer.resultado_id, U)
    est = banco_sim.cargar(U)
    assert est["bloqueos"] == [] and len(est["bajas"]) == 1     # la baja en el servicio no se deshace
    with pytest.raises(ErrorAccion):
        acciones.deshacer(r.deshacer.resultado_id, U)
    assert almacenamiento.leer_auditoria(U)[-1]["evento"] == "rechazada"


def test_bloquear_cobros_no_vale_para_recibos_domiciliados():
    est = banco_sim.cargar(U)
    est["recibos_domiciliados"] = ["Streamflix"]
    banco_sim.guardar(U, est)
    t = acciones.preparar("cancelar_suscripcion", {"comercio": "Streamflix", "bloquear_cobros": True}, PID, U)
    # el único parámetro que el cliente puede cambiar en la tarjeta es bloquear_cobros
    acciones.ejecutar(t.token_confirmacion, U)
    assert banco_sim.cargar(U)["bloqueos"] == []


def test_cambiar_bloquear_cobros_en_la_tarjeta_vale_pero_otro_parametro_no():
    acciones.preparar("cancelar_suscripcion", {"comercio": "Streamflix", "bloquear_cobros": True}, PID, U)
    with pytest.raises(ErrorAccion):
        acciones.preparar("cancelar_suscripcion", {"comercio": "Otro", "bloquear_cobros": False}, PID, U)


def test_recordar_limite_de_90_dias_y_fecha():
    almacenamiento.guardar(U, "propuestas", [propuesta(ofrecidas=[
        AccionOfrecida(accion_id="recordar", parametros={"cuando": "+120d", "texto": "x"})])])
    with pytest.raises(ErrorAccion) as e:
        acciones.preparar("recordar", {"cuando": "+120d", "texto": "x"}, PID, U)
    assert e.value.codigo == "parametros_invalidos"


def test_mover_dinero_con_saldo_y_traspaso_inverso():
    p = {"origen": "ahorro", "destino": "cuenta", "importe": "100.00"}
    almacenamiento.guardar(U, "propuestas", [propuesta(ofrecidas=[
        AccionOfrecida(accion_id="mover_dinero", parametros=p, limites=Limites(importe_max=Decimal("100.00")))])])
    r = acciones.ejecutar(acciones.preparar("mover_dinero", p, PID, U).token_confirmacion, U)
    c = banco_sim.cargar(U)["cuentas"]
    assert Decimal(c["ahorro"]) == Decimal("2900.00") and Decimal(c["corriente"]) == Decimal("1600.00")
    acciones.deshacer(r.deshacer.resultado_id, U)
    assert Decimal(banco_sim.cargar(U)["cuentas"]["ahorro"]) == Decimal("3000.00")


def test_reclamar_cargo_y_pedir_bizum_sin_bizum():
    p = {"movimiento_id": "mov-2", "motivo": "Cargo duplicado"}
    almacenamiento.guardar(U, "propuestas", [propuesta(ofrecidas=[
        AccionOfrecida(accion_id="reclamar_cargo", parametros=p, limites=Limites(importe_max=Decimal("9.99"))),
        AccionOfrecida(accion_id="pedir_bizum", parametros=BIZUM, limites=Limites(importe_max=Decimal("24"), contrapartes=["MARCOS R"]))])])
    r = acciones.ejecutar(acciones.preparar("reclamar_cargo", p, PID, U).token_confirmacion, U)
    assert "plazo garantizado" in r.mensaje
    est = banco_sim.cargar(U)
    est["sin_bizum"] = ["MARCOS R"]
    banco_sim.guardar(U, est)
    with pytest.raises(ErrorAccion) as e:
        acciones.ejecutar(acciones.preparar("pedir_bizum", BIZUM, PID, U).token_confirmacion, U)
    assert e.value.codigo == "no_se_puede"


def test_auditoria_enmascarada_y_sin_el_token():
    p = {"cuando": "+3d", "texto": "Mirar lo de La Tasca"}
    almacenamiento.guardar(U, "propuestas", [propuesta(ofrecidas=[AccionOfrecida(
        accion_id="recordar", parametros={"cuando": "+3d", "texto": "Llamar al 612345678 o ES9121000418450200051332"})])])
    pp = {"cuando": "+3d", "texto": "Llamar al 612345678 o ES9121000418450200051332"}
    t = acciones.preparar("recordar", pp, PID, U)
    acciones.ejecutar(t.token_confirmacion, U)
    texto = (almacenamiento.carpeta_usuario(U) / "auditoria.jsonl").read_text(encoding="utf-8")
    assert "612345678" not in texto and "ES9121000418450200051332" not in texto
    assert t.token_confirmacion not in texto


def test_ejecutar_devuelve_propuesta_y_parametros_del_token():
    t = acciones.preparar("recordar", {"cuando": "+3d", "texto": "Mirar lo de La Tasca"}, PID, U)
    r = acciones.ejecutar(t.token_confirmacion, U)
    assert r.datos["propuesta_id"] == PID and r.datos["parametros"]["cuando"] == "+3d"


def test_repetir_tras_deshacer_si_tiene_efecto():
    p = {"cuando": "+3d", "texto": "Mirar lo de La Tasca"}
    r1 = acciones.ejecutar(acciones.preparar("recordar", p, PID, U).token_confirmacion, U)
    acciones.deshacer(r1.deshacer.resultado_id, U)
    assert banco_sim.cargar(U)["recordatorios"] == []
    r2 = acciones.ejecutar(acciones.preparar("recordar", p, PID, U).token_confirmacion, U)
    assert r2.datos["resultado_id"] != r1.datos["resultado_id"]
    assert len(banco_sim.cargar(U)["recordatorios"]) == 1


def test_recordar_y_auditoria_usan_el_reloj_simulado():
    almacenamiento.guardar(U, "reloj", {"hoy": "2026-03-01"})
    t = acciones.preparar("recordar", {"cuando": "+3d", "texto": "Mirar lo de La Tasca"}, PID, U)
    r = acciones.ejecutar(t.token_confirmacion, U)
    assert r.datos["fecha"] == "2026-03-04"
    assert {a["fecha_simulada"] for a in almacenamiento.leer_auditoria(U)} == {"2026-03-01"}
