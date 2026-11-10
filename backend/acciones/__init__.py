"""
Acciones de la lista cerrada con banco simulado (modulos.md §6).
`preparar` no tiene efectos; `ejecutar` valida token, usuario, propuesta, acción y límites en el
servidor, ejecuta en `banco_sim` y audita. Todo es simulado y queda auditado.

Tarjeta editable: `preparar_editada` es el único camino por el que el usuario cambia los campos
`editables` de una acción (en `pedir_bizum`, importe y concepto). Se valida con las reglas de la acción
(Bizum: 0,50 a 1.000 €), no con la cuota de los `limites`, que solo frena lo que prepara Meisam. Emite un
token nuevo, ligado al usuario, la propuesta y los parámetros editados, y marcado como `editado` en el
servidor para que `ejecutar` lo revalide igual. El agente de voz solo usa `preparar`.
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
from .registro import REGISTRO, normalizar, obtener

__all__ = ["preparar", "preparar_editada", "ejecutar", "deshacer", "ErrorAccion"]

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


def _comparables(params: dict, libres: tuple[str, ...]) -> dict:
    """Parámetros que deben coincidir con los de la propuesta: sin los libres y sin mayúsculas ni acentos
    en los textos («La Tasca» == «LA TASCA»). El dinero y los booleanos se comparan exactos."""
    return {k: (normalizar(v) if isinstance(v, str) else v) for k, v in params.items() if k not in libres}


def _validar_contra_propuesta(prop: Propuesta, accion_id: str, params: dict, editado: bool = False) -> tuple[dict, dict]:
    """La acción debe estar ofrecida con esos parámetros y respetar sus límites (en el servidor).

    Devuelve `(canonicos, ofrecidos)`: los parámetros con los campos fijos tomados de la propuesta
    (así «LA TASCA» se convierte en «La Tasca») y los parámetros ofrecidos ya validados. Con `editado`,
    los campos `editables` de la acción son libres y se saltan `limites.importe_max`; el resto, la
    contraparte incluida, tiene que coincidir con una acción ofrecida.
    """
    defn = obtener(accion_id)
    ofrecidas = [o for o in prop.acciones_ofrecidas if o.accion_id == accion_id]
    if not ofrecidas:
        raise ErrorAccion("accion_no_ofrecida", f"La acción {accion_id!r} no está entre las ofrecidas por esta propuesta.")
    libres = tuple(defn.variables) + (tuple(defn.editables) if editado else ())
    mis = _comparables(params, libres)
    coincide, base = None, None
    for o in ofrecidas:
        try:
            ofrecidos = defn.validar(o.parametros)
        except ErrorAccion:
            continue
        if _comparables(ofrecidos, libres) == mis:
            coincide, base = o, ofrecidos
            break
    if coincide is None:
        raise ErrorAccion("accion_no_ofrecida", "Los parámetros no coinciden con ninguna acción ofrecida por la propuesta.")
    canonicos = {**params, **{k: v for k, v in base.items() if k not in libres}}
    lim = coincide.limites
    edita_importe = editado and "importe" in defn.editables
    if not edita_importe and lim.importe_max is not None and "importe" in params and _dec(params["importe"]) > _dec(lim.importe_max):
        raise ErrorAccion("fuera_de_limites", f"El importe supera el máximo permitido ({lim.importe_max}).")
    if lim.contrapartes is not None and normalizar(canonicos.get("contraparte")) not in {normalizar(c) for c in lim.contrapartes}:
        raise ErrorAccion("fuera_de_limites", "La contraparte no está entre las permitidas.")
    return canonicos, base


def _campos_editables(defn, params: dict) -> dict[str, str]:
    return {k: str(params[k]) for k in defn.editables if k in params}


def _preparar(accion_id: str, parametros: dict, propuesta_id: str, usuario_id: str, editado: bool) -> TarjetaConfirmacion:
    sim = banco_sim.fecha_simulada(usuario_id)
    try:
        defn = obtener(accion_id)
        prop = _propuesta(usuario_id, propuesta_id)
        params = defn.validar(parametros)
        params, ofrecidos = _validar_contra_propuesta(prop, accion_id, params, editado)
        if defn.precondiciones is not None:
            defn.precondiciones(banco_sim.cargar(usuario_id), params, sim, propuesta_id)
    except ErrorAccion as e:
        auditoria.registrar(usuario_id, "rechazada", propuesta_id=propuesta_id, accion_id=accion_id,
                            parametros=parametros if isinstance(parametros, dict) else None, motivo=f"{e.codigo}: {e.mensaje}",
                            fecha_simulada=sim.isoformat(), extra={"fase": "preparar", "editado": editado})
        raise
    token, caduca = tokens.emitir(usuario_id, propuesta_id, accion_id, params, editado=editado)
    detalle = None
    if accion_id == "cancelar_suscripcion":
        detalle = DetalleBaja(bloquea_cobros=params["bloquear_cobros"], canal="tarjeta")
    extra: dict[str, Any] = {}
    if defn.editables:
        propuesto, confirmado = _campos_editables(defn, ofrecidos), _campos_editables(defn, params)
        extra = {"editado": propuesto != confirmado, "propuesto": propuesto, "confirmado": confirmado}
    auditoria.registrar(usuario_id, "preparada", propuesta_id=propuesta_id, accion_id=accion_id, parametros=params,
                        fecha_simulada=sim.isoformat(), extra=extra or None)
    return TarjetaConfirmacion(
        accion_id=accion_id, propuesta_id=propuesta_id, titulo=defn.titulo,
        parametros_legibles=defn.legible(params), simulada=True, token_confirmacion=token, caduca=caduca,
        detalle_baja=detalle,
    )


def preparar(accion_id: str, parametros: dict, propuesta_id: str, usuario_id: str) -> TarjetaConfirmacion:
    """Sin efectos. Valida y emite un token de un solo uso (10 min) ligado a usuario, propuesta y parámetros.
    Lo que prepara Meisam (y el agente de voz) debe coincidir con lo ofrecido y respetar `limites`."""
    return _preparar(accion_id, parametros, propuesta_id, usuario_id, editado=False)


def preparar_editada(accion_id: str, parametros: dict, propuesta_id: str, usuario_id: str) -> TarjetaConfirmacion:
    """Como `preparar`, pero el usuario ha cambiado campos editables de la tarjeta (importe y concepto de
    `pedir_bizum`). Los valida con las reglas de la acción, no con la cuota. Solo lo llama el botón del usuario."""
    return _preparar(accion_id, parametros, propuesta_id, usuario_id, editado=True)


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
            _, ofrecidos = _validar_contra_propuesta(_propuesta(usuario_id, propuesta_id), accion_id, params,
                                                     editado=bool(ent.get("editado")))
        except ErrorAccion as e:
            _rechazo(usuario_id, ent, e.codigo, e.mensaje, sim)
        tokens.marcar_usado(usuario_id, token_confirmacion)  # antes de ejecutar

        estado = banco_sim.cargar(usuario_id)
        clave = f"{propuesta_id}|{accion_id}|{ent['hash']}"
        previo = estado["ejecuciones"].get(clave)
        if previo is not None and defn.vigente is not None and not defn.vigente(estado, previo):
            previo = None  # la solicitud ya no está pendiente (rechazada, caducada...): esto es otra petición
        if previo is not None:  # idempotencia: no repite el efecto
            auditoria.registrar(usuario_id, "ejecutada", propuesta_id=propuesta_id, accion_id=accion_id, parametros=params,
                                fecha_simulada=sim, extra={"idempotente": True})
            return ResultadoAccion.model_validate(previo)

        rid = "res-" + uuid.uuid4().hex[:12]
        try:
            mensaje, efecto = defn.simular(estado, params, banco_sim.fecha_simulada(usuario_id), rid, propuesta_id)
        except ErrorAccion as e:  # el token ya se marcó como usado
            _rechazo(usuario_id, ent, e.codigo, f"{e.mensaje} El token ya se usó: vuelve a preparar la acción.", sim)
        hasta = tokens.ahora() + DISPONIBLE_DESHACER
        propuesto, confirmado = _campos_editables(defn, ofrecidos), _campos_editables(defn, params)
        edicion = {"propuesto": propuesto, "editado": propuesto != confirmado} if defn.editables else {}
        resultado = ResultadoAccion(accion_id=accion_id, ok=True, mensaje=mensaje, datos={**efecto, "resultado_id": rid, "propuesta_id": propuesta_id,
                                                        "parametros": {k: str(v) if isinstance(v, Decimal) else v for k, v in params.items()},
                                                        **edicion},
                                    simulada=True, deshacer=Deshacer(resultado_id=rid, disponible_hasta=hasta))
        estado["resultados"][rid] = {"accion_id": accion_id, "efecto": efecto, "deshecho": False, "hasta": hasta.isoformat()}
        estado["ejecuciones"][clave] = resultado.model_dump(mode="json")
        banco_sim.guardar(usuario_id, estado)
        extra: dict[str, Any] = {"resultado_id": rid}
        if defn.editables:
            extra.update({"editado": propuesto != confirmado, "propuesto": propuesto, "confirmado": confirmado})
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
