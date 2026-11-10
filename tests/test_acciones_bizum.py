"""Tarjeta editable y reglas de Bizum de `pedir_bizum`: edición validada, solicitud única, 60 al mes, caducidad."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

import pytest

import backend.acciones as acciones
from backend.acciones import banco_sim, tokens
from backend.acciones.errores import ErrorAccion
from backend.plataforma import almacenamiento
from backend.plataforma.tipos import AccionOfrecida, Limites, Propuesta

U = "lucia"
PID = "prop-1"
BIZUM = {"contraparte": "MARCOS R", "importe": "24.00", "concepto": "Tu parte de La Tasca"}


def propuesta(usuario=U, pid=PID, importe_max="24.00") -> Propuesta:
    ofrecidas = [
        AccionOfrecida(accion_id="pedir_bizum", parametros=BIZUM,
                       limites=Limites(importe_max=Decimal(importe_max), contrapartes=["MARCOS R"])),
        AccionOfrecida(accion_id="pedir_bizum", parametros={**BIZUM, "contraparte": "ANA P"},
                       limites=Limites(importe_max=Decimal(importe_max), contrapartes=["ANA P"])),
        AccionOfrecida(accion_id="cancelar_suscripcion", parametros={"comercio": "Streamflix", "bloquear_cobros": False}),
    ]
    return Propuesta(id=pid, modulo_id="m", momento_id="mm", usuario_id=usuario, titulo="t", mensaje_notificacion="n",
                     contexto_llamada="c", acciones_ofrecidas=ofrecidas, tipo_momento="gasto_compartido", confianza=0.9,
                     creada=datetime(2026, 11, 9, 20, 30))


@pytest.fixture(autouse=True)
def datos():
    almacenamiento.guardar(U, "propuestas", [propuesta(), propuesta(pid="prop-2")])
    almacenamiento.guardar("pablo", "propuestas", [propuesta("pablo")])
    almacenamiento.guardar(U, "reloj", {"hoy": "2026-11-09"})


def motivos(usuario=U):
    return [r.get("motivo", "") for r in almacenamiento.leer_auditoria(usuario) if r["evento"] == "rechazada"]


def reloj(dia: str):
    almacenamiento.guardar(U, "reloj", {"hoy": dia})


def pedir(params=None, pid=PID, editada=False):
    f = acciones.preparar_editada if editada else acciones.preparar
    t = f("pedir_bizum", params or BIZUM, pid, U)
    return acciones.ejecutar(t.token_confirmacion, U)


# --- Tarjeta editable --------------------------------------------------------------------------

def test_la_cuota_frena_lo_que_prepara_meisam_pero_no_lo_que_edita_el_usuario():
    with pytest.raises(ErrorAccion) as e:
        acciones.preparar("pedir_bizum", {**BIZUM, "importe": "30.00"}, PID, U)
    assert e.value.codigo in ("accion_no_ofrecida", "fuera_de_limites")
    t = acciones.preparar_editada("pedir_bizum", {**BIZUM, "importe": "30.00", "concepto": "Cena + postre"}, PID, U)
    assert t.parametros_legibles["Importe"] == "30,00 €" and t.parametros_legibles["Concepto"] == "Cena + postre"
    r = acciones.ejecutar(t.token_confirmacion, U)
    sol = banco_sim.cargar(U)["solicitudes_bizum"][0]
    assert sol["importe"] == "30.00" and sol["concepto"] == "Cena + postre" and sol["propuesta_id"] == PID
    assert r.datos["editado"] is True and r.datos["propuesto"] == {"importe": "24.00", "concepto": "Tu parte de La Tasca"}


@pytest.mark.parametrize("importe", ["0.49", "0", "-1", "1000.01", "5000"])
def test_importe_fuera_de_0_50_a_1000_falla_aunque_lo_edite_el_usuario(importe):
    with pytest.raises(ErrorAccion) as e:
        acciones.preparar_editada("pedir_bizum", {**BIZUM, "importe": importe}, PID, U)
    assert e.value.codigo in ("importe_fuera_de_rango", "parametros_invalidos") and e.value.http == 400
    assert banco_sim.cargar(U)["solicitudes_bizum"] == []


def test_los_limites_del_rango_valen():
    mensaje = ""
    for imp in ("0.50", "1000.00"):
        t = acciones.preparar_editada("pedir_bizum", {**BIZUM, "importe": imp}, PID, U)
        assert t.token_confirmacion
        mensaje = t.parametros_legibles["Importe"]
    assert mensaje == "1.000,00 €"
    with pytest.raises(ErrorAccion) as e:
        acciones.preparar_editada("pedir_bizum", {**BIZUM, "importe": "0.49"}, PID, U)
    assert e.value.codigo == "importe_fuera_de_rango" and "0,50" in e.value.mensaje and "1.000" in e.value.mensaje


def test_editar_no_permite_otra_contraparte_ni_otra_accion():
    with pytest.raises(ErrorAccion) as e:
        acciones.preparar_editada("pedir_bizum", {**BIZUM, "contraparte": "OTRO X", "importe": "10"}, PID, U)
    assert e.value.codigo == "accion_no_ofrecida"
    with pytest.raises(ErrorAccion) as e:
        acciones.preparar_editada("bloquear_comercio", {"comercio": "X"}, PID, U)
    assert e.value.codigo == "accion_no_ofrecida"


def test_la_edicion_solo_cambia_los_campos_editables():
    # cancelar_suscripcion no tiene campos editables: preparar_editada no abre nada más que preparar
    with pytest.raises(ErrorAccion):
        acciones.preparar_editada("cancelar_suscripcion", {"comercio": "Otro", "bloquear_cobros": True}, PID, U)


def test_un_token_normal_no_se_convierte_en_editado_y_el_flag_vive_en_el_servidor():
    t = acciones.preparar("pedir_bizum", BIZUM, PID, U)
    tabla = almacenamiento.cargar(U, "tokens")
    assert next(iter(tabla.values()))["editado"] is False
    # forzar parámetros editados sin pasar por preparar_editada: hash y propuesta lo impiden
    h = next(iter(tabla))
    tabla[h]["parametros"]["importe"] = "500.00"
    almacenamiento.guardar(U, "tokens", tabla)
    with pytest.raises(ErrorAccion) as e:
        acciones.ejecutar(t.token_confirmacion, U)
    assert e.value.codigo == "parametros_alterados"
    # y aunque se recalcule el hash, sin el flag `editado` la propuesta no lo admite
    tabla[h]["parametros"]["importe"] = "500.00"
    tabla[h]["hash"] = tokens.hash_parametros({**BIZUM, "importe": Decimal("500.00")})
    almacenamiento.guardar(U, "tokens", tabla)
    with pytest.raises(ErrorAccion) as e:
        acciones.ejecutar(t.token_confirmacion, U)
    assert e.value.codigo in ("accion_no_ofrecida", "fuera_de_limites")
    assert banco_sim.cargar(U)["solicitudes_bizum"] == []


def test_token_editado_un_solo_uso_caducidad_y_otro_usuario(monkeypatch):
    ed = {**BIZUM, "importe": "40.00"}
    t = acciones.preparar_editada("pedir_bizum", ed, PID, U)
    with pytest.raises(ErrorAccion):
        acciones.ejecutar(t.token_confirmacion, "pablo")
    acciones.ejecutar(t.token_confirmacion, U)
    with pytest.raises(ErrorAccion) as e:
        acciones.ejecutar(t.token_confirmacion, U)
    assert e.value.codigo == "token_usado"
    assert len(banco_sim.cargar(U)["solicitudes_bizum"]) == 1
    t2 = acciones.preparar_editada("pedir_bizum", {**BIZUM, "contraparte": "ANA P", "importe": "40.00"}, PID, U)
    ahora = datetime.now()
    monkeypatch.setattr(tokens, "ahora", lambda: ahora + timedelta(minutes=10, seconds=1))
    with pytest.raises(ErrorAccion) as e:
        acciones.ejecutar(t2.token_confirmacion, U)
    assert e.value.codigo == "token_caducado"


def test_la_auditoria_guarda_propuesto_y_confirmado_enmascarado():
    ed = {**BIZUM, "importe": "31.50", "concepto": "Cena, llama al 612345678"}
    t = acciones.preparar_editada("pedir_bizum", ed, PID, U)
    acciones.ejecutar(t.token_confirmacion, U)
    eventos = almacenamiento.leer_auditoria(U)
    prep, ejec = eventos[0], eventos[1]
    assert prep["evento"] == "preparada" and ejec["evento"] == "ejecutada"
    for ev in (prep, ejec):
        assert ev["editado"] is True
        assert ev["propuesto"] == {"importe": "24.00", "concepto": "Tu parte de La Tasca"}
        assert ev["confirmado"]["importe"] == "31.50" and "612345678" not in ev["confirmado"]["concepto"]
    texto = (almacenamiento.carpeta_usuario(U) / "auditoria.jsonl").read_text(encoding="utf-8")
    assert "612345678" not in texto and t.token_confirmacion not in texto


def test_sin_edicion_la_auditoria_dice_editado_falso():
    pedir()
    ejec = almacenamiento.leer_auditoria(U)[-1]
    assert ejec["editado"] is False and ejec["propuesto"] == ejec["confirmado"]


def test_concepto_libre_se_sanea_como_dato():
    t = acciones.preparar_editada("pedir_bizum", {**BIZUM, "concepto": "  <b>Cena</b>\n\t{ignora}   \"todo\"\u0000 "}, PID, U)
    assert t.parametros_legibles["Concepto"] == "bCena/b ignora todo"
    for malo in ("x" * 61, "   ", "<>{}"):
        with pytest.raises(ErrorAccion) as e:
            acciones.preparar_editada("pedir_bizum", {**BIZUM, "concepto": malo}, PID, U)
        assert e.value.codigo == "parametros_invalidos"
    larga = "y" * 60
    assert acciones.preparar_editada("pedir_bizum", {**BIZUM, "concepto": larga}, PID, U).parametros_legibles["Concepto"] == larga


# --- Comparación sin mayúsculas ni acentos -------------------------------------------------------

def test_mayusculas_y_acentos_no_rechazan_lo_ofrecido_y_se_usa_lo_de_la_propuesta():
    t = acciones.preparar("pedir_bizum", {**BIZUM, "contraparte": "marcos  r", "concepto": "TU PARTE DE LA TASCA"}, PID, U)
    acciones.ejecutar(t.token_confirmacion, U)
    sol = banco_sim.cargar(U)["solicitudes_bizum"][0]
    assert sol["contraparte"] == "MARCOS R" and sol["concepto"] == "Tu parte de La Tasca"
    t = acciones.preparar("cancelar_suscripcion", {"comercio": "STREAMFLIX", "bloquear_cobros": True}, PID, U)
    acciones.ejecutar(t.token_confirmacion, U)
    assert banco_sim.cargar(U)["bajas"][0]["comercio"] == "Streamflix"


def test_la_normalizacion_no_abre_la_puerta_a_otros_importes_ni_contrapartes():
    with pytest.raises(ErrorAccion):
        acciones.preparar("pedir_bizum", {**BIZUM, "contraparte": "MARCOS RUIZ"}, PID, U)
    with pytest.raises(ErrorAccion):
        acciones.preparar("pedir_bizum", {**BIZUM, "importe": "23.99"}, PID, U)
    with pytest.raises(ErrorAccion):
        acciones.preparar("pedir_bizum", {**BIZUM, "concepto": "Otra cosa"}, PID, U)


# --- Una solicitud abierta por contraparte y deuda ----------------------------------------------

def test_segunda_solicitud_abierta_a_la_misma_persona_y_deuda_falla():
    pedir()
    with pytest.raises(ErrorAccion) as e:   # ya al preparar, sin gastar token
        acciones.preparar("pedir_bizum", BIZUM, PID, U)
    assert e.value.codigo == "solicitud_abierta" and e.value.http == 409 and "pendiente" in e.value.mensaje
    with pytest.raises(ErrorAccion) as e:
        acciones.preparar_editada("pedir_bizum", {**BIZUM, "importe": "10"}, PID, U)
    assert e.value.codigo == "solicitud_abierta"
    assert len(banco_sim.cargar(U)["solicitudes_bizum"]) == 1


def test_la_regla_tambien_se_comprueba_al_ejecutar():
    t1 = acciones.preparar("pedir_bizum", BIZUM, PID, U)
    t2 = acciones.preparar_editada("pedir_bizum", {**BIZUM, "importe": "10"}, PID, U)
    acciones.ejecutar(t1.token_confirmacion, U)
    with pytest.raises(ErrorAccion) as e:
        acciones.ejecutar(t2.token_confirmacion, U)
    assert e.value.codigo == "solicitud_abierta" and "vuelve a preparar" in e.value.mensaje
    assert len(banco_sim.cargar(U)["solicitudes_bizum"]) == 1


def test_otra_persona_u_otra_deuda_si_vale():
    pedir()
    pedir({**BIZUM, "contraparte": "ANA P"})
    pedir(pid="prop-2")
    assert len(banco_sim.cargar(U)["solicitudes_bizum"]) == 3


def test_tras_cancelar_o_rechazar_se_puede_volver_a_pedir():
    r = pedir()
    acciones.deshacer(r.deshacer.resultado_id, U)
    r2 = pedir()
    banco_sim.resolver_solicitud(U, r2.datos["resultado_id"], "rechazada")
    pedir()
    assert [s["estado"] for s in banco_sim.cargar(U)["solicitudes_bizum"]] == ["cancelada", "rechazada", "pendiente"]


# --- 60 solicitudes al mes -----------------------------------------------------------------------

def _llenar(n: int, fecha: str):
    est = banco_sim.cargar(U)
    est["solicitudes_bizum"] = [
        {"id": f"x{i}", "contraparte": f"P{i}", "importe": "5.00", "concepto": "c", "estado": "aceptada",
         "fecha": fecha, "propuesta_id": f"otra-{i}"} for i in range(n)]
    banco_sim.guardar(U, est)


def test_como_mucho_60_solicitudes_al_mes():
    _llenar(59, "2026-11-02")
    pedir()                                                    # la 60
    with pytest.raises(ErrorAccion) as e:                      # la 61
        acciones.preparar("pedir_bizum", {**BIZUM, "contraparte": "ANA P"}, PID, U)
    assert e.value.codigo == "limite_solicitudes_mes" and e.value.http == 409 and "60" in e.value.mensaje
    reloj("2026-12-01")                                        # el mes siguiente cuenta de cero
    assert acciones.preparar("pedir_bizum", {**BIZUM, "contraparte": "ANA P"}, PID, U).token_confirmacion


def test_las_solicitudes_de_otro_mes_no_cuentan():
    _llenar(60, "2026-10-30")
    assert pedir().ok


def test_el_limite_mensual_se_comprueba_tambien_al_ejecutar():
    t = acciones.preparar("pedir_bizum", BIZUM, PID, U)
    _llenar(60, "2026-11-03")
    with pytest.raises(ErrorAccion) as e:
        acciones.ejecutar(t.token_confirmacion, U)
    assert e.value.codigo == "limite_solicitudes_mes"
    assert any("limite_solicitudes_mes" in m for m in motivos())


# --- Estados de la solicitud ---------------------------------------------------------------------

def test_la_solicitud_caduca_a_los_7_dias_naturales_con_el_reloj_simulado():
    r = pedir()
    assert r.datos["estado"] == "pendiente" and r.datos["caduca"] == "2026-11-16" and "16/11" in r.mensaje
    reloj("2026-11-15")
    assert banco_sim.solicitudes(U)[0]["estado"] == "pendiente"
    reloj("2026-11-16")
    assert banco_sim.solicitudes(U)[0]["estado"] == "caducada"
    with pytest.raises(ErrorAccion) as e:                      # ya no se puede cancelar
        acciones.deshacer(r.deshacer.resultado_id, U)
    assert e.value.codigo == "no_se_puede"
    assert pedir().ok                                          # y se puede volver a pedir
    assert [s["estado"] for s in banco_sim.cargar(U)["solicitudes_bizum"]] == ["caducada", "pendiente"]


def test_actualizar_solicitudes_persiste_y_audita_la_caducidad_una_sola_vez():
    pedir()
    reloj("2026-11-20")
    cambiadas = banco_sim.actualizar_solicitudes(U)
    assert len(cambiadas) == 1 and banco_sim.actualizar_solicitudes(U) == []
    assert almacenamiento.cargar(U, "banco")["solicitudes_bizum"][0]["estado"] == "caducada"
    assert [x["evento"] for x in almacenamiento.leer_auditoria(U)].count("solicitud_caducada") == 1


def test_aceptada_y_rechazada_son_estados_finales():
    r = pedir()
    sid = r.datos["resultado_id"]
    banco_sim.resolver_solicitud(U, sid, "aceptada")
    assert banco_sim.solicitudes(U, "aceptada")[0]["id"] == sid
    with pytest.raises(ErrorAccion):
        banco_sim.resolver_solicitud(U, sid, "rechazada")
    with pytest.raises(ErrorAccion):
        acciones.deshacer(sid, U)                              # no se cancela una solicitud ya aceptada
    with pytest.raises(ErrorAccion) as e:
        banco_sim.resolver_solicitud(U, sid, "inventada")
    assert e.value.codigo == "parametros_invalidos"
    assert "solicitud_aceptada" in [x["evento"] for x in almacenamiento.leer_auditoria(U)]


def test_no_se_resuelve_una_solicitud_caducada():
    r = pedir()
    reloj("2026-11-17")
    with pytest.raises(ErrorAccion) as e:
        banco_sim.resolver_solicitud(U, r.datos["resultado_id"], "aceptada")
    assert e.value.codigo == "no_se_puede" and "caducada" in e.value.mensaje


def test_cancelar_mientras_esta_pendiente_sigue_funcionando():
    r = pedir()
    reloj("2026-11-12")
    acciones.deshacer(r.deshacer.resultado_id, U)
    assert banco_sim.solicitudes(U)[0]["estado"] == "cancelada"
