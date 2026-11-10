"""
Orquestador: une motor, módulos, personalización y acciones. Es el ÚNICO que escribe en disco
(vía `almacenamiento`, siempre dentro del candado del usuario). Contrato: docs/ARQUITECTURA.md §3.2.

Orden de un día (CONTRATO.md, «Cambios aceptados tras los cambios de Pablo»):
    perfilar (cada 7 días) -> motor.procesar(perfil) -> modulos.proponer -> ordenar_acciones
    -> decidir -> registrar_decision -> observar -> guardar

Archivos por usuario: estado, modelo, movimientos (hasta hoy), pendientes (del escenario, aún en
el futuro), momentos, propuestas, decisiones, notificaciones, recordatorios, motor_estado.
El token de confirmación nunca se guarda en disco ni llega a un modelo.
"""

from __future__ import annotations

import importlib
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Iterator

from .. import acciones, config, modulos, motor, personalizacion
from . import almacenamiento as alm
from ..modulos.plantillas import CABECERA_DATOS, sanear_dato
from ..personalizacion import edicion
from .privacidad import enmascarar_nombre, enmascarar_texto
from .reloj import ahora_por_defecto
from .tipos import (
    Caso,
    ACCIONES,
    Decision,
    Evento,
    Feedback,
    HechoAprendido,
    ModeloUsuario,
    Momento,
    Movimiento,
    Propuesta,
    ResultadoAccion,
    TarjetaConfirmacion,
)

HORAS_IGNORADA = 48
MAX_PENDIENTES_WEB = 20
DIAS_PERFIL = 7

_motor_cargado: set[str] = set()


class NoEncontrado(ValueError):
    """404: el usuario, la propuesta o el escenario no existen."""


class Prohibido(ValueError):
    """403: acción no ofrecida en la propuesta o usuario que no corresponde."""


# --- Lectura y escritura -----------------------------------------------------------------------

def _tipo(nombre: str):
    return {"movimientos": list[Movimiento], "pendientes": list[Movimiento], "momentos": list[Momento],
            "propuestas": list[Propuesta], "decisiones": list[Decision], "modelo": ModeloUsuario,
            "casos": list[Caso]}.get(nombre)


def _leer(uid: str, nombre: str, defecto: Any = None) -> Any:
    return alm.cargar(uid, nombre, tipo=_tipo(nombre), defecto=defecto)


def _estado(uid: str) -> dict:
    estado = alm.cargar(uid, "estado")
    if estado is None:
        raise NoEncontrado(f"El usuario {uid!r} no existe. Carga un escenario con POST /demo/cargar.")
    return estado


def _hoy(estado: dict) -> date:
    return date.fromisoformat(estado["hoy"])


def existe(usuario_id: str) -> bool:
    return alm.existe(usuario_id, "estado")


def _carga_motor(uid: str) -> None:
    if uid in _motor_cargado:
        return
    guardado = alm.cargar(uid, "motor_estado")
    if guardado:
        motor.importar_estado(uid, guardado)
    _motor_cargado.add(uid)


def _guardar_motor(uid: str) -> None:
    alm.guardar(uid, "motor_estado", motor.exportar_estado(uid) or {})


def _saldo(movimientos: list[Movimiento]) -> Decimal | None:
    for m in sorted(movimientos, key=lambda x: x.fecha, reverse=True):
        if m.saldo is not None:
            return m.saldo
    return None


def _contadores(uid: str) -> dict[str, int]:
    decisiones = _leer(uid, "decisiones", [])
    return {"momentos": len(_leer(uid, "momentos", [])),
            "ahora": sum(d.accion == "notificar_ahora" for d in decisiones),
            "resumen": sum(d.accion == "resumen" for d in decisiones),
            "silenciadas": sum(d.accion == "silenciar" for d in decisiones)}


def _auditar(uid: str, evento: str, **datos: Any) -> None:
    alm.anadir_auditoria(uid, {"evento": evento, **datos})


# --- Escenarios y activación -------------------------------------------------------------------

def _modulo_escenarios():
    return importlib.import_module("backend.escenarios.cargar")


def _campo(objeto: Any, nombre: str, defecto: Any = None) -> Any:
    if isinstance(objeto, dict):
        return objeto.get(nombre, defecto)
    return getattr(objeto, nombre, defecto)


def listar_escenarios() -> list[dict]:
    """`[{id, usuario_id, descripcion}]`, de `backend.escenarios.cargar.listar()` o de los YAML."""
    try:
        cargador = _modulo_escenarios()
    except ImportError:
        cargador = None
    if cargador is not None and hasattr(cargador, "listar"):
        return [{"id": _campo(e, "id"), "usuario_id": _campo(e, "usuario_id"),
                 "descripcion": _campo(e, "descripcion", "") or ""} for e in cargador.listar()]
    import yaml
    from pathlib import Path
    salida = []
    for ruta in sorted((Path(__file__).resolve().parent.parent / "escenarios").glob("*.yaml")):
        datos = yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}
        if "id" in datos:
            salida.append({"id": datos["id"], "usuario_id": datos.get("usuario_id", ""),
                           "descripcion": datos.get("descripcion", "") or ""})
    return salida


def _leer_escenario(escenario_id: str) -> Any:
    try:
        cargador = _modulo_escenarios()
    except ImportError as error:
        raise NoEncontrado("Los escenarios aún no están disponibles (backend/escenarios/cargar.py).") from error
    funcion = getattr(cargador, "cargar", None) or getattr(cargador, "cargar_escenario", None)
    if funcion is None:
        raise NoEncontrado("backend/escenarios/cargar.py no expone `cargar(escenario_id)`.")
    try:
        return funcion(escenario_id)
    except (FileNotFoundError, KeyError) as error:
        raise NoEncontrado(f"El escenario {escenario_id!r} no existe.") from error


def cargar_escenario(escenario_id: str) -> dict:
    """Reinicia al usuario del escenario y pone el reloj en la activación. Devuelve
    `{usuario_id, hoy, activacion}`. El escenario aporta `usuario_id`, `activacion` y `movimientos`."""
    escenario = _leer_escenario(escenario_id)
    uid = _campo(escenario, "usuario_id")
    activacion = _campo(escenario, "activacion")
    if isinstance(activacion, str):
        activacion = date.fromisoformat(activacion)
    movimientos = [m if isinstance(m, Movimiento) else Movimiento.model_validate(m)
                   for m in _campo(escenario, "movimientos", [])]
    if not uid or activacion is None:
        raise ValueError(f"El escenario {escenario_id!r} no tiene usuario_id o activacion.")
    with alm.candado(uid):
        alm.borrar_usuario(uid)
        motor.reiniciar(uid)
        _motor_cargado.discard(uid)
        movimientos.sort(key=lambda m: (m.fecha, m.id))
        alm.guardar(uid, "movimientos", [m for m in movimientos if m.fecha <= activacion])
        alm.guardar(uid, "pendientes", [m for m in movimientos if m.fecha > activacion])
        alm.guardar(uid, "reloj", {"hoy": activacion.isoformat()})  # lo lee acciones.banco_sim.fecha_simulada
        alm.guardar(uid, "estado", {"hoy": activacion.isoformat(), "activado": False, "activacion": activacion.isoformat(),
                                    "ultimo_perfil": None, "escenario_id": escenario_id})
        alm.guardar(uid, "modelo", personalizacion.nuevo_modelo(uid))
        for nombre in ("momentos", "propuestas", "decisiones"):
            alm.guardar(uid, nombre, [])
        alm.guardar(uid, "notificaciones", [])
        alm.guardar(uid, "recordatorios", [])
        _auditar(uid, "escenario_cargado", escenario_id=escenario_id)
    return {"usuario_id": uid, "hoy": activacion.isoformat(), "activacion": activacion.isoformat()}


def activar(usuario_id: str, modulos_activos: list[str], consentimientos: dict) -> ModeloUsuario:
    """`cargar_historial` (sin emitir) + `perfilar`. Los consentimientos marcados quedan con la hora."""
    with alm.candado(usuario_id):
        estado = _estado(usuario_id)
        hoy = _hoy(estado)
        historial = _leer(usuario_id, "movimientos", [])
        modelo = _leer(usuario_id, "modelo") or personalizacion.nuevo_modelo(usuario_id)
        _motor_cargado.add(usuario_id)
        motor.cargar_historial(usuario_id, historial, hoy)
        modelo = modelo.model_copy(deep=True)
        modelo.modulos_activos = list(modulos_activos)
        ahora = ahora_por_defecto(hoy)
        for nombre, valor in (consentimientos or {}).items():
            if valor:
                modelo.consentimientos[nombre] = ahora
            else:
                modelo.consentimientos.pop(nombre, None)
        if modelo.preferencias.usar_perfil:
            modelo.perfil = personalizacion.perfilar(motor.enriquecer(historial), hoy, modelo.perfil)
        modelo.actualizado = ahora
        estado.update(activado=True, ultimo_perfil=hoy.isoformat())
        alm.guardar(usuario_id, "modelo", modelo)
        alm.guardar(usuario_id, "estado", estado)
        _guardar_motor(usuario_id)
        _auditar(usuario_id, "activado", modulos=list(modulos_activos), consentimientos=sorted(modelo.consentimientos))
        return modelo


# --- Un día ------------------------------------------------------------------------------------

def _procesar_dia(uid: str, hoy: date, ahora: datetime | None) -> dict:
    """Hace todo un día y guarda. Si falla a mitad, descarta el estado del motor en memoria (se
    recarga del disco en la siguiente llamada) para que no quede a medias."""
    try:
        return _procesar_dia_interno(uid, hoy, ahora)
    except Exception:
        with alm.candado(uid):
            motor.reiniciar(uid)
            _motor_cargado.discard(uid)
        raise


def _procesar_dia_interno(uid: str, hoy: date, ahora: datetime | None) -> dict:
    ahora = ahora or ahora_por_defecto(hoy)
    with alm.candado(uid):
        estado = _estado(uid)
        if not estado.get("activado"):
            raise ValueError("El usuario no está activado: llama antes a POST /usuarios/{id}/activar.")
        if hoy <= _hoy(estado):
            raise ValueError(f"El reloj simulado no retrocede: hoy es {estado['hoy']} y se pidió {hoy.isoformat()}.")
        _carga_motor(uid)
        modelo = _leer(uid, "modelo")
        historial = _leer(uid, "movimientos", [])
        pendientes = _leer(uid, "pendientes", [])
        nuevos = [m for m in pendientes if m.fecha <= hoy]
        pendientes = [m for m in pendientes if m.fecha > hoy]
        historial = historial + nuevos

        # 1. perfilar cada 7 días
        perfil_recalculado = False
        ultimo = date.fromisoformat(estado["ultimo_perfil"]) if estado.get("ultimo_perfil") else None
        if modelo.preferencias.usar_perfil and (ultimo is None or (hoy - ultimo).days >= DIAS_PERFIL):
            modelo = modelo.model_copy(deep=True)
            modelo.perfil = personalizacion.perfilar(motor.enriquecer(historial), hoy, modelo.perfil)
            estado["ultimo_perfil"] = hoy.isoformat()
            perfil_recalculado = True
        perfil = modelo.perfil if modelo.preferencias.usar_perfil else None

        # 2. momento -> propuesta -> decisión
        momentos = _leer(uid, "momentos", [])
        propuestas = _leer(uid, "propuestas", [])
        decisiones = _leer(uid, "decisiones", [])
        notificaciones = _leer(uid, "notificaciones", [])
        vistos = {m.id for m in momentos}
        items: list[tuple[Momento, Propuesta, Decision]] = []
        momentos_dia: list[Momento] = []
        for momento in motor.procesar(uid, nuevos, hoy, perfil):
            if momento.id in vistos:
                continue
            vistos.add(momento.id)
            momentos.append(momento)
            momentos_dia.append(momento)
            for propuesta in modulos.proponer(momento, modelo):
                propuesta = personalizacion.ordenar_acciones(propuesta, modelo)
                decision = personalizacion.decidir(propuesta, modelo, ahora)
                modelo = personalizacion.registrar_decision(modelo, propuesta, decision)
                propuestas.append(propuesta)
                decisiones.append(decision)
                notificaciones.append({"propuesta_id": propuesta.id, "estado": "nueva",
                                       "actualizado": ahora.isoformat(timespec="seconds")})
                items.append((momento, propuesta, decision))
                _auditar(uid, "decision", propuesta_id=propuesta.id, tipo=propuesta.tipo_momento,
                         accion=decision.accion, politica=decision.politica)

        # 3. recordatorios que vencen y avisos sin respuesta tras 48 h
        _recordatorios_vencidos(uid, hoy, ahora, propuestas, decisiones, notificaciones, items)
        modelo = _marcar_ignoradas(uid, modelo, propuestas, decisiones, notificaciones, ahora)

        # 4. observar y gancho de búsqueda web
        modelo = personalizacion.observar(modelo, nuevos, hoy)
        if config.ajustes().busqueda_web:
            _buscar_comercios(uid)

        # 5. guardar
        modelo = modelo.model_copy(update={"actualizado": ahora})
        estado["hoy"] = hoy.isoformat()
        alm.guardar(uid, "movimientos", historial)
        alm.guardar(uid, "pendientes", pendientes)
        alm.guardar(uid, "momentos", momentos)
        alm.guardar(uid, "propuestas", propuestas)
        alm.guardar(uid, "decisiones", decisiones)
        alm.guardar(uid, "notificaciones", notificaciones)
        alm.guardar(uid, "modelo", modelo)
        alm.guardar(uid, "estado", estado)
        alm.guardar(uid, "reloj", {"hoy": hoy.isoformat()})
        _guardar_motor(uid)
        return {"hoy": hoy, "movimientos": nuevos, "saldo": _saldo(historial), "perfil": modelo.perfil if perfil_recalculado else None,
                "perfil_recalculado": perfil_recalculado, "items": items, "momentos": momentos_dia,
                "contadores": _contadores(uid)}


def _buscar_comercios(uid: str) -> None:
    """Gancho (solo con BUSQUEDA_WEB=on): pide a la caché los comercios que el motor no conoce."""
    try:
        from ..motor import conocimiento
        for comercio in motor.comercios_pendientes(uid)[:MAX_PENDIENTES_WEB]:
            conocimiento.info_comercio(comercio)
    except Exception as error:  # la búsqueda nunca rompe el día
        _auditar(uid, "busqueda_web_fallida", error=type(error).__name__)


def _marcar_ignoradas(uid, modelo, propuestas, decisiones, notificaciones, ahora) -> ModeloUsuario:
    por_id = {p.id: p for p in propuestas}
    ahora_decision = {d.propuesta_id: d for d in decisiones}
    for n in notificaciones:
        d = ahora_decision.get(n["propuesta_id"])
        if n["estado"] not in ("nueva", "vista") or d is None or d.accion != "notificar_ahora":
            continue
        if ahora - datetime.fromisoformat(n["actualizado"]) >= timedelta(hours=HORAS_IGNORADA):
            n.update(estado="ignorada", actualizado=ahora.isoformat(timespec="seconds"))
            p = por_id[n["propuesta_id"]]
            modelo = personalizacion.aprender(
                Feedback(propuesta_id=p.id, usuario_id=uid, resultado="ignorada", canal="app", fecha=ahora), modelo)
    return modelo


def _recordatorios_vencidos(uid, hoy, ahora, propuestas, decisiones, notificaciones, items) -> list:
    """Recordatorios de `baja_guiada` cuyo día ha llegado: se avisan como propuesta de `recordar`."""
    recordatorios = alm.cargar(uid, "recordatorios", defecto=[])
    emitidos = []
    for r in recordatorios:
        if r.get("emitido") or date.fromisoformat(r["fecha"]) > hoy:
            continue
        r["emitido"] = True
        nombre = sanear_dato(r["comercio"])  # dato de un tercero: nunca crudo en textos ni prompts
        texto = f"¿Pudiste darte de baja de {nombre}? Mañana es el cobro."
        contexto = f"{CABECERA_DATOS} ¿Pudiste darte de baja de <datos>{nombre}</datos>? Mañana es el cobro."
        propuesta = Propuesta(
            id=f"rec-{r['propuesta_id']}", modulo_id="recordatorio", momento_id=r["momento_id"], usuario_id=uid,
            titulo=f"Recordatorio: {nombre}", mensaje_notificacion=texto, contexto_llamada=contexto,
            acciones_ofrecidas=[{"accion_id": "cancelar_suscripcion", "parametros": {"comercio": r["comercio"]}},
                                {"accion_id": "recordar", "parametros": {"texto": texto}}],
            urgencia="alta", tipo_momento="prueba_gratuita", comercio=r["comercio"], confianza=1.0, creada=ahora)
        decision = Decision(propuesta_id=propuesta.id, accion="notificar_ahora", puntuacion=1.0, probabilidad_util=1.0,
                            motivos=["Es un recordatorio que pediste al dar de baja la prueba."], politica="recordatorio")
        propuestas.append(propuesta)
        decisiones.append(decision)
        notificaciones.append({"propuesta_id": propuesta.id, "estado": "nueva", "actualizado": ahora.isoformat(timespec="seconds")})
        items.append((None, propuesta, decision))
        emitidos.append(propuesta)
    alm.guardar(uid, "recordatorios", recordatorios)
    return emitidos


def avanzar_dia(usuario_id: str, hoy: date, ahora: datetime | None = None) -> list[Decision]:
    """Procesa un día simulado. `ahora` por defecto: `hoy` a las 20:30."""
    return [decision for _, _, decision in _procesar_dia(usuario_id, hoy, ahora)["items"]]


def reproducir(usuario_id: str, dias: int, pausar_en: str | None = None) -> Iterator[Evento]:
    """Avanza `dias` días emitiendo `dia`, `perfil`, `momento`, `propuesta` y `decision`, y termina en
    `fin`. Con `pausar_en` (tipo de momento) se detiene al terminar el día en que aparece ese momento."""
    if not 1 <= dias <= 60:
        raise ValueError("`dias` debe estar entre 1 y 60.")
    pausado = False
    for _ in range(dias):
        hoy = _hoy(_estado(usuario_id)) + timedelta(days=1)
        r = _procesar_dia(usuario_id, hoy, None)
        yield Evento(tipo="dia", datos={"fecha": hoy.isoformat(), "saldo": None if r["saldo"] is None else format(r["saldo"], "f"),
                                        "movimientos": [m.model_dump(mode="json") for m in r["movimientos"]]})
        if r["perfil_recalculado"] and r["perfil"] is not None:
            yield Evento(tipo="perfil", datos={"calculado": r["perfil"].calculado.isoformat(),
                                               "umbral_relevante_eur": format(r["perfil"].umbral_relevante_eur, "f")})
        emitido: set[str] = set()
        for momento, propuesta, decision in r["items"]:
            if momento is not None and momento.id not in emitido:
                emitido.add(momento.id)
                yield Evento(tipo="momento", datos=momento.model_dump(mode="json"))
            yield Evento(tipo="propuesta", datos=propuesta.model_dump(mode="json"))
            yield Evento(tipo="decision", datos=decision.model_dump(mode="json"))
        if pausar_en and any(m.tipo == pausar_en for m in r["momentos"]):
            pausado = True
            break
    estado = _estado(usuario_id)
    yield Evento(tipo="fin", datos={"hoy": estado["hoy"], "contadores": _contadores(usuario_id), "pausado": pausado})


# --- Consultas (solo lectura) ------------------------------------------------------------------

def estado_usuario(usuario_id: str) -> dict:
    with alm.candado(usuario_id):
        estado = _estado(usuario_id)
        saldo = _saldo(_leer(usuario_id, "movimientos", []))
        return {"hoy": estado["hoy"], "activado": bool(estado.get("activado")),
                "saldo": None if saldo is None else format(saldo, "f"), "contadores": _contadores(usuario_id)}


def notificaciones(usuario_id: str, bandeja: str | None = None) -> list[dict]:
    """`[{propuesta, decision, estado}]`, la más reciente primero."""
    if bandeja not in (None, "ahora", "resumen", "silenciadas"):
        raise ValueError("`bandeja` debe ser ahora, resumen o silenciadas.")
    objetivo = {"ahora": "notificar_ahora", "resumen": "resumen", "silenciadas": "silenciar"}.get(bandeja)
    with alm.candado(usuario_id):
        _estado(usuario_id)
        propuestas = {p.id: p for p in _leer(usuario_id, "propuestas", [])}
        decisiones = {d.propuesta_id: d for d in _leer(usuario_id, "decisiones", [])}
        estados = {n["propuesta_id"]: n["estado"] for n in _leer(usuario_id, "notificaciones", [])}
    salida = []
    for pid, propuesta in propuestas.items():
        decision = decisiones.get(pid)
        if decision is None or (objetivo and decision.accion != objetivo):
            continue
        salida.append({"propuesta": propuesta.model_dump(mode="json"), "decision": decision.model_dump(mode="json"),
                       "estado": estados.get(pid, "nueva")})
    salida.sort(key=lambda x: x["propuesta"]["creada"], reverse=True)
    return salida


def _movimiento_publico(m: Movimiento) -> dict:
    datos = m.model_dump(mode="json")
    datos.pop("nota", None)  # las notas de Bizum no salen del motor
    datos["concepto"] = enmascarar_texto(m.concepto)
    if m.contraparte:
        datos["contraparte"] = enmascarar_nombre(m.contraparte)
    return datos


def propuesta_detalle(usuario_id: str, propuesta_id: str) -> dict:
    """`{propuesta, decision, momento, movimientos}` con los movimientos enmascarados. Marca la
    notificación como vista si era nueva."""
    with alm.candado(usuario_id):
        _estado(usuario_id)
        propuesta = _propuesta(usuario_id, propuesta_id)
        decision = next((d for d in _leer(usuario_id, "decisiones", []) if d.propuesta_id == propuesta_id), None)
        momento = next((m for m in _leer(usuario_id, "momentos", []) if m.id == propuesta.momento_id), None)
        ids = set(momento.movimientos) if momento else set()
        movimientos = [_movimiento_publico(m) for m in _leer(usuario_id, "movimientos", []) if m.id in ids]
        notificaciones_ = _leer(usuario_id, "notificaciones", [])
        for n in notificaciones_:
            if n["propuesta_id"] == propuesta_id and n["estado"] == "nueva":
                n["estado"] = "vista"
                alm.guardar(usuario_id, "notificaciones", notificaciones_)
                break
    return {"propuesta": propuesta.model_dump(mode="json"),
            "decision": decision.model_dump(mode="json") if decision else None,
            "momento": momento.model_dump(mode="json") if momento else None, "movimientos": movimientos}


def _propuesta(uid: str, propuesta_id: str) -> Propuesta:
    for p in _leer(uid, "propuestas", []):
        if p.id == propuesta_id:
            return p
    raise NoEncontrado(f"La propuesta {propuesta_id!r} no existe para este usuario.")


# --- Feedback y acciones -----------------------------------------------------------------------

_ESTADO_TRAS_FEEDBACK = {"resuelta": "resuelta", "rechazada": "rechazada", "falso_positivo": "rechazada",
                         "ignorada": "ignorada"}


def _estado_notificacion(uid: str, propuesta_id: str, estado: str) -> None:
    notificaciones_ = _leer(uid, "notificaciones", [])
    ahora = ahora_por_defecto(_hoy(_estado(uid)))  # hora simulada, no la del sistema
    for n in notificaciones_:
        if n["propuesta_id"] == propuesta_id:
            n["estado"] = estado
            n["actualizado"] = ahora.isoformat(timespec="seconds")
    alm.guardar(uid, "notificaciones", notificaciones_)


def registrar_feedback(feedback: Feedback) -> list[HechoAprendido]:
    """Aprende (`personalizacion.aprender`, pura), guarda y devuelve los hechos nuevos."""
    uid = feedback.usuario_id
    with alm.candado(uid):
        _estado(uid)
        _propuesta(uid, feedback.propuesta_id)
        modelo = _leer(uid, "modelo")
        antes = {h.id for h in modelo.hechos_aprendidos}
        nuevo = personalizacion.aprender(feedback, modelo)
        alm.guardar(uid, "modelo", nuevo)
        _estado_notificacion(uid, feedback.propuesta_id, _ESTADO_TRAS_FEEDBACK.get(feedback.resultado, "vista"))
        _auditar(uid, "feedback", propuesta_id=feedback.propuesta_id, resultado=feedback.resultado, canal=feedback.canal)
        return [h for h in nuevo.hechos_aprendidos if h.id not in antes]


def preparar_accion(usuario_id: str, propuesta_id: str, accion_id: str, parametros: dict) -> TarjetaConfirmacion:
    """Sin efectos. La acción debe estar en `acciones_ofrecidas` de esa propuesta (si no, 403)."""
    if accion_id not in ACCIONES:
        raise Prohibido(f"Acción no permitida: {accion_id!r}. Las válidas son: {', '.join(ACCIONES)}.")
    with alm.candado(usuario_id):
        _estado(usuario_id)
        propuesta = _propuesta(usuario_id, propuesta_id)
        if accion_id not in {a.accion_id for a in propuesta.acciones_ofrecidas}:
            raise Prohibido(f"La acción {accion_id!r} no se ofrece en esta propuesta.")
        tarjeta = acciones.preparar(accion_id, dict(parametros or {}), propuesta_id, usuario_id)
        _auditar(usuario_id, "accion_preparada", propuesta_id=propuesta_id, accion_id=accion_id)
        return tarjeta


def confirmar_accion(usuario_id: str, token_confirmacion: str) -> ResultadoAccion:
    """Ejecuta (simulada) con el token de un solo uso, registra la elección y, en
    `cancelar_suscripcion`, cierra la prueba o la deja en `baja_guiada` con un recordatorio."""
    with alm.candado(usuario_id):
        estado = _estado(usuario_id)
        hoy = _hoy(estado)
        resultado = acciones.ejecutar(token_confirmacion, usuario_id)
        propuestas = _leer(usuario_id, "propuestas", [])
        # `acciones.ejecutar` devuelve propuesta_id y parametros de la entrada del token ya validada.
        propuesta_id = resultado.datos.get("propuesta_id")
        parametros = resultado.datos.get("parametros") or {}
        propuesta = next((p for p in propuestas if p.id == propuesta_id), None)
        if propuesta is None:
            propuesta = next((p for p in reversed(propuestas)
                              if resultado.accion_id in {a.accion_id for a in p.acciones_ofrecidas}), None)
        _auditar(usuario_id, "accion_ejecutada", accion_id=resultado.accion_id, ok=resultado.ok,
                 propuesta_id=propuesta.id if propuesta else None)
        if not resultado.ok or propuesta is None:
            return resultado
        modelo = personalizacion.registrar_accion(_leer(usuario_id, "modelo"), propuesta, resultado)
        alm.guardar(usuario_id, "modelo", modelo)
        _estado_notificacion(usuario_id, propuesta.id, "resuelta")
        if resultado.accion_id == "cancelar_suscripcion":
            _tras_cancelar(usuario_id, hoy, propuesta, parametros, resultado)
        return resultado


def _tras_cancelar(uid: str, hoy: date, propuesta: Propuesta, parametros: dict, resultado: ResultadoAccion) -> None:
    comercio = parametros.get("comercio") or resultado.datos.get("comercio") or propuesta.comercio
    if not comercio:
        return
    bloquear = resultado.datos.get("bloqueado", False)
    if bloquear:
        motor.cerrar_prueba(uid, comercio, "cancelada", hoy)
        _guardar_motor(uid)
        return
    motor.cerrar_prueba(uid, comercio, "baja_guiada", hoy)
    _guardar_motor(uid)
    momento = next((m for m in _leer(uid, "momentos", []) if m.id == propuesta.momento_id), None)
    cobro = (momento.datos.get("fecha_primer_cobro") if momento else None) or resultado.datos.get("fecha_cobro")
    if isinstance(cobro, str):
        cobro = date.fromisoformat(cobro)
    if not isinstance(cobro, date):
        return
    recordatorios = alm.cargar(uid, "recordatorios", defecto=[])
    recordatorios.append({"propuesta_id": propuesta.id, "momento_id": propuesta.momento_id, "comercio": comercio,
                          "fecha": (cobro - timedelta(days=1)).isoformat(), "emitido": False,
                          "texto": f"¿Pudiste darte de baja de {sanear_dato(comercio)}? Mañana es el cobro."})
    alm.guardar(uid, "recordatorios", recordatorios)


# --- Lo aprendido (U2): ver, editar y borrar ---------------------------------------------------
# La edición es de `personalizacion.edicion` (pura); aquí solo se carga, se guarda y se audita. La
# auditoría guarda qué campo o hecho se tocó, nunca el valor (el ingreso, por ejemplo, es del cliente).

def _cambiar_modelo(uid: str, cambio, evento: str, **datos: Any) -> ModeloUsuario:
    with alm.candado(uid):
        estado = _estado(uid)
        modelo = _leer(uid, "modelo")
        if modelo is None:
            raise NoEncontrado(f"El usuario {uid!r} aún no tiene modelo.")
        try:
            nuevo = cambio(modelo, estado)
        except edicion.NoExiste as error:
            raise NoEncontrado(str(error)) from error
        nuevo = nuevo.model_copy(update={"actualizado": ahora_por_defecto(_hoy(estado))})
        alm.guardar(uid, "modelo", nuevo)
        alm.guardar(uid, "estado", estado)
        _auditar(uid, evento, **datos)
        return nuevo


def _modelo_de(uid: str) -> ModeloUsuario:
    with alm.candado(uid):
        _estado(uid)
        modelo = _leer(uid, "modelo")
    if modelo is None:
        raise NoEncontrado(f"El usuario {uid!r} aún no tiene modelo.")
    return modelo


def perfil_usuario(usuario_id: str) -> dict:
    """`{usar_perfil, perfil, frases}`: lo que se enseña en «Cómo es tu mes» (es del propio cliente)."""
    modelo = _modelo_de(usuario_id)
    perfil = modelo.perfil if modelo.preferencias.usar_perfil else None
    return {"usar_perfil": modelo.preferencias.usar_perfil,
            "perfil": perfil.model_dump(mode="json") if perfil else None,
            "frases": [f.model_dump(mode="json") for f in edicion.frases_perfil(perfil)]}


def editar_perfil_usuario(usuario_id: str, campo: str, valor: Any) -> dict:
    _cambiar_modelo(usuario_id, lambda m, e: edicion.editar_perfil(m, campo, valor), "perfil_editado", campo=campo)
    return perfil_usuario(usuario_id)


def borrar_campo_perfil_usuario(usuario_id: str, campo: str) -> dict:
    _cambiar_modelo(usuario_id, lambda m, e: edicion.borrar_campo_perfil(m, campo), "perfil_campo_borrado", campo=campo)
    return perfil_usuario(usuario_id)


def borrar_perfil_usuario(usuario_id: str) -> dict:
    """Perfil fuera y `usar_perfil = False`: desde el siguiente día, el motor y la política van en frío."""
    _cambiar_modelo(usuario_id, lambda m, e: edicion.borrar_perfil(m), "perfil_borrado")
    return perfil_usuario(usuario_id)


def reactivar_perfil_usuario(usuario_id: str) -> dict:
    """Vuelve a usar el perfil: lo recalcula ya con el historial hasta hoy (si hay 28 días)."""
    def cambio(modelo: ModeloUsuario, estado: dict) -> ModeloUsuario:
        nuevo = edicion.usar_perfil(modelo, True)
        hoy = _hoy(estado)
        nuevo.perfil = personalizacion.perfilar(motor.enriquecer(_leer(usuario_id, "movimientos", [])), hoy, nuevo.perfil)
        estado["ultimo_perfil"] = hoy.isoformat()
        return nuevo

    _cambiar_modelo(usuario_id, cambio, "perfil_reactivado")
    return perfil_usuario(usuario_id)


def aprendido_usuario(usuario_id: str) -> dict:
    """`{hechos, silencios, amigos, usar_perfil}`: todo lo que el sistema ha aprendido y se puede tocar."""
    modelo = _modelo_de(usuario_id)
    return {
        "hechos": [h.model_dump(mode="json") for h in modelo.hechos_aprendidos],
        "silencios": [{"ambito": s.ambito, "desde": s.desde.isoformat(),
                       "valor": enmascarar_nombre(s.valor) if s.ambito == "contacto" else s.valor}
                      for s in modelo.preferencias.silencios],
        "amigos": [{"contraparte": a.contraparte, "saldo": format(a.saldo, "f"), "estado": a.estado,
                    "creado": a.creado.isoformat()} for a in modelo.amigos],
        "usar_perfil": modelo.preferencias.usar_perfil,
    }


def editar_hecho_usuario(usuario_id: str, hecho_id: str, activo: bool | None = None, texto: str | None = None) -> dict:
    """Apaga o reactiva un hecho (`activo`) y/o reescribe uno de voz (`texto`)."""
    if activo is None and texto is None:
        raise ValueError("Indica `activo` o `texto`.")

    def cambio(modelo: ModeloUsuario, estado: dict) -> ModeloUsuario:
        if texto is not None:
            modelo = edicion.editar_hecho(modelo, hecho_id, texto)
        if activo is not None:
            modelo = edicion.activar_hecho(modelo, hecho_id) if activo else edicion.apagar_hecho(modelo, hecho_id)
        return modelo

    _cambiar_modelo(usuario_id, cambio, "hecho_editado", hecho_id=hecho_id)
    return aprendido_usuario(usuario_id)


def borrar_hecho_usuario(usuario_id: str, hecho_id: str) -> dict:
    _cambiar_modelo(usuario_id, lambda m, e: edicion.borrar_hecho(m, hecho_id), "hecho_borrado", hecho_id=hecho_id)
    return aprendido_usuario(usuario_id)


def olvidar_todo_usuario(usuario_id: str) -> dict:
    """Deja solo los consentimientos y los módulos activos."""
    _cambiar_modelo(usuario_id, lambda m, e: edicion.olvidar_todo(m), "olvidar_todo")
    return aprendido_usuario(usuario_id)
