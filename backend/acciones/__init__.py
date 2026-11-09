"""
Acciones de la lista cerrada con banco simulado (modulos.md §6).
`preparar` no tiene efectos; `ejecutar` valida token, usuario, propuesta, acción y límites en el
servidor, ejecuta en `banco_sim` y audita. Todo es simulado y queda auditado.
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from decimal import Decimal
from typing import Any

from ..plataforma import almacenamiento
from ..plataforma.tipos import DetalleBaja, Propuesta, ResultadoAccion, TarjetaConfirmacion, Deshacer
from . import auditoria, banco_sim, tokens
from .errores import ErrorAccion
from .registro import REGISTRO, obtener

__all__ = ["preparar", "ejecutar", "deshacer", "ErrorAccion"]

DISPONIBLE_DESHACER = timedelta(hours=24)


def _propuesta(usuario_id: str, propuesta_id: str) -> Propuesta:
    datos = almacenamiento.cargar(usuario_id, "propuestas", defecto=None)
    items = list(datos.values()) if isinstance(datos, dict) else (datos or [])
    for it in items:
        if isinstance(it, dict) and it.get("id") == propuesta_id:
            return Propuesta.model_validate(it)
    raise ErrorAccion("propuesta_desconocida", f"No existe la propuesta {propuesta_id!r}.")


def _dec(v: Any) -> Decimal:
    return v if isinstance(v, Decimal) else Decimal(str(v))


def _comparables(defn, params: dict) -> dict:
    """Parámetros normalizados sin los que el cliente puede cambiar en la tarjeta."""
    return {k: v for k, v in params.items() if k not in defn.variables}


def _validar_contra_propuesta(prop: Propuesta, accion_id: str, params: dict) -> None:
    """La acción debe estar ofrecida con esos parámetros y respetar sus límites (en el servidor)."""
    defn = obtener(accion_id)
    ofrecidas = [o for o in prop.acciones_ofrecidas if o.accion_id == accion_id]
    if not ofrecidas:
        raise ErrorAccion("accion_no_ofrecida", f"La acción {accion_id!r} no está entre las ofrecidas por esta propuesta.")
    mis = _comparables(defn, params)
    coincide = None
    for o in ofrecidas:
        try:
            if _comparables(defn, defn.validar(o.parametros)) == mis:
                coincide = o
                break
        except ErrorAccion:
            continue
    if coincide is None:
        raise ErrorAccion("accion_no_ofrecida", "Los parámetros no coinciden con ninguna acción ofrecida por la propuesta.")
    lim = coincide.limites
    if lim.importe_max is not None and "importe" in params and _dec(params["importe"]) > _dec(lim.importe_max):
        raise ErrorAccion("fuera_de_limites", f"El importe supera el máximo permitido ({lim.importe_max}).")
    if lim.contrapartes is not None and params.get("contraparte") not in lim.contrapartes:
        raise ErrorAccion("fuera_de_limites", "La contraparte no está entre las permitidas.")


def preparar(accion_id: str, parametros: dict, propuesta_id: str, usuario_id: str) -> TarjetaConfirmacion:
    """Sin efectos. Valida y emite un token de un solo uso (10 min) ligado a usuario, propuesta y parámetros."""
    sim = banco_sim.fecha_simulada(usuario_id).isoformat()
    try:
        defn = obtener(accion_id)
        prop = _propuesta(usuario_id, propuesta_id)
        params = defn.validar(parametros)
        _validar_contra_propuesta(prop, accion_id, params)
    except ErrorAccion as e:
        auditoria.registrar(usuario_id, "rechazada", propuesta_id=propuesta_id, accion_id=accion_id,
                            parametros=parametros if isinstance(parametros, dict) else None, motivo=f"{e.codigo}: {e.mensaje}",
                            fecha_simulada=sim, extra={"fase": "preparar"})
        raise
    token, caduca = tokens.emitir(usuario_id, propuesta_id, accion_id, params)
    detalle = None
    if accion_id == "cancelar_suscripcion":
        detalle = DetalleBaja(bloquea_cobros=params["bloquear_cobros"], canal="tarjeta")
    auditoria.registrar(usuario_id, "preparada", propuesta_id=propuesta_id, accion_id=accion_id, parametros=params,
                        fecha_simulada=sim)
    return TarjetaConfirmacion(
        accion_id=accion_id, propuesta_id=propuesta_id, titulo=defn.titulo,
        parametros_legibles=defn.legible(params), simulada=True, token_confirmacion=token, caduca=caduca,
        detalle_baja=detalle,
    )


def _rechazo(usuario_id, entrada, codigo, mensaje, sim):
    auditoria.registrar(usuario_id, "rechazada", propuesta_id=(entrada or {}).get("propuesta_id"),
                        accion_id=(entrada or {}).get("accion_id"), motivo=f"{codigo}: {mensaje}",
                        fecha_simulada=sim, extra={"fase": "ejecutar"})
    raise ErrorAccion(codigo, mensaje)


def ejecutar(token_confirmacion: str, usuario_id: str) -> ResultadoAccion:
    """Valida token (existe, no usado, no caducado, mismo usuario), revalida contra la propuesta y ejecuta."""
    sim = banco_sim.fecha_simulada(usuario_id).isoformat()
    with almacenamiento.candado(usuario_id):
        ent = tokens.buscar(usuario_id, token_confirmacion) if isinstance(token_confirmacion, str) else None
        if ent is None:
            _rechazo(usuario_id, None, "token_desconocido", "El token no existe.", sim)
        if ent["usuario_id"] != usuario_id:
            _rechazo(usuario_id, ent, "token_otro_usuario", "El token pertenece a otro usuario.", sim)
        if ent["usado"]:
            _rechazo(usuario_id, ent, "token_usado", "El token ya se usó.", sim)
        if tokens.ahora().isoformat() > ent["caduca"]:
            _rechazo(usuario_id, ent, "token_caducado", "El token ha caducado (10 minutos).", sim)
        accion_id, propuesta_id = ent["accion_id"], ent["propuesta_id"]
        try:
            defn = obtener(accion_id)
            params = defn.validar(ent["parametros"])
            if tokens.hash_parametros(params) != ent["hash"]:
                raise ErrorAccion("parametros_alterados", "Los parámetros no coinciden con los que se confirmaron.")
            _validar_contra_propuesta(_propuesta(usuario_id, propuesta_id), accion_id, params)
        except ErrorAccion as e:
            _rechazo(usuario_id, ent, e.codigo, e.mensaje, sim)
        tokens.marcar_usado(usuario_id, token_confirmacion)  # antes de ejecutar

        estado = banco_sim.cargar(usuario_id)
        clave = f"{propuesta_id}|{accion_id}|{ent['hash']}"
        previo = estado["ejecuciones"].get(clave)
        if previo is not None:  # idempotencia: no repite el efecto
            auditoria.registrar(usuario_id, "ejecutada", propuesta_id=propuesta_id, accion_id=accion_id, parametros=params,
                                fecha_simulada=sim, extra={"idempotente": True})
            return ResultadoAccion.model_validate(previo)

        rid = "res-" + uuid.uuid4().hex[:12]
        try:
            mensaje, efecto = defn.simular(estado, params, banco_sim.fecha_simulada(usuario_id), rid)
        except ErrorAccion as e:  # el token ya se marcó como usado
            _rechazo(usuario_id, ent, e.codigo, f"{e.mensaje} El token ya se usó: vuelve a preparar la acción.", sim)
        hasta = tokens.ahora() + DISPONIBLE_DESHACER
        resultado = ResultadoAccion(accion_id=accion_id, ok=True, mensaje=mensaje, datos={**efecto, "resultado_id": rid, "propuesta_id": propuesta_id,
                                                        "parametros": {k: str(v) if isinstance(v, Decimal) else v for k, v in params.items()}},
                                    simulada=True, deshacer=Deshacer(resultado_id=rid, disponible_hasta=hasta))
        estado["resultados"][rid] = {"accion_id": accion_id, "efecto": efecto, "deshecho": False, "hasta": hasta.isoformat()}
        estado["ejecuciones"][clave] = resultado.model_dump(mode="json")
        banco_sim.guardar(usuario_id, estado)
        extra: dict[str, Any] = {"resultado_id": rid}
        if accion_id == "cancelar_suscripcion":
            extra.update({"canal_pago": "tarjeta", "bloquear_cobros": params["bloquear_cobros"], "pasos_mostrados": False})
        auditoria.registrar(usuario_id, "ejecutada", propuesta_id=propuesta_id, accion_id=accion_id, parametros=params,
                            fecha_simulada=sim, extra=extra)
        return resultado


def deshacer(resultado_id: str, usuario_id: str) -> ResultadoAccion:
    """Revierte el efecto si sigue vigente (24 h). Auditado."""
    sim = banco_sim.fecha_simulada(usuario_id).isoformat()
    with almacenamiento.candado(usuario_id):
        estado = banco_sim.cargar(usuario_id)
        r = estado["resultados"].get(resultado_id)
        if r is None or r["deshecho"]:
            _rechazo(usuario_id, {"accion_id": r["accion_id"]} if r else None, "no_se_puede",
                     "No hay nada que deshacer con ese identificador.", sim)
        if tokens.ahora().isoformat() > r["hasta"]:
            _rechazo(usuario_id, {"accion_id": r["accion_id"]}, "no_se_puede", "Ha pasado el plazo para deshacer.", sim)
        try:
            msg = obtener(r["accion_id"]).deshacer(estado, r["efecto"], resultado_id)
        except ErrorAccion as e:
            _rechazo(usuario_id, {"accion_id": r["accion_id"]}, e.codigo, e.mensaje, sim)
        r["deshecho"] = True
        # Sin esto, repetir la misma acción devolvería el resultado ya deshecho sin efecto.
        for clave in [k for k, v in estado["ejecuciones"].items() if (v.get("datos") or {}).get("resultado_id") == resultado_id]:
            del estado["ejecuciones"][clave]
        banco_sim.guardar(usuario_id, estado)
        auditoria.registrar(usuario_id, "deshecha", accion_id=r["accion_id"], fecha_simulada=sim,
                            extra={"resultado_id": resultado_id})
        return ResultadoAccion(accion_id=r["accion_id"], ok=True, mensaje=msg, simulada=True)
