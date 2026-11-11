"""Banco simulado: estado en `datos_usuario/<usuario>/banco.json` (vía almacenamiento). Todo es simulado.

Solicitudes de Bizum (`solicitudes_bizum`): estados `pendiente`, `aceptada`, `rechazada`, `caducada` y
`cancelada` (la anula quien pidió, mientras está pendiente). Caducan a los 7 días naturales con el reloj
simulado: una solicitud hecha el día D caduca el día D+7.

Solo para las demos (opción del escenario `amigos_pagan_tras_solicitud_dias: N`, guardada en el estado del usuario;
apagada por defecto, porque el simulador de amigos ya simula sus propios pagos): el amigo acepta la solicitud N días
después. `pagos_de_solicitudes` da, el día que toca, el Bizum RECIBIDO por ese importe (lo crea el código con los datos
de la solicitud, nunca la IA, y con la fecha de ese día: nadie mira el futuro) y `aceptar_pagadas` la pasa a `aceptada`.
"""

from __future__ import annotations

from datetime import date, timedelta

from ..plataforma import almacenamiento
from . import auditoria
from .errores import ErrorAccion

DIAS_CADUCIDAD_SOLICITUD = 7
RESPUESTAS_SOLICITUD = ("aceptada", "rechazada")
PREFIJO_PAGO_SOLICITUD = "bizum-sol-"     # id del Bizum con el que el amigo acepta una solicitud (demos)


def estado_inicial() -> dict:
    return {
        "cuentas": {"corriente": "1500.00", "ahorro": "3000.00"},
        "bloqueos": [], "solicitudes_bizum": [], "reclamaciones": [], "bajas": [], "recordatorios": [],
        "sin_bizum": [], "recibos_domiciliados": [], "canal_movimientos": {},
        "ejecuciones": {},   # clave idempotente (propuesta|accion|hash) -> resultado
        "resultados": {},    # resultado_id -> {accion_id, params, efecto, deshecho}
    }


def fecha_simulada(usuario_id: str) -> date:
    """Fecha del reloj simulado del usuario (`reloj.json`); si no hay, la del sistema."""
    try:
        r = almacenamiento.cargar(usuario_id, "reloj", defecto=None)
        if isinstance(r, dict) and r.get("hoy"):
            return date.fromisoformat(str(r["hoy"])[:10])
        if isinstance(r, str):
            return date.fromisoformat(r[:10])
    except (ValueError, TypeError):
        pass
    return date.today()


def caducidad_solicitud(fecha_solicitud: str | date) -> date:
    f = fecha_solicitud if isinstance(fecha_solicitud, date) else date.fromisoformat(str(fecha_solicitud)[:10])
    return f + timedelta(days=DIAS_CADUCIDAD_SOLICITUD)


def expirar_solicitudes(estado: dict, hoy: date) -> list[dict]:
    """Pasa a `caducada` las solicitudes pendientes que ya llegaron a su fecha. Devuelve las que cambian."""
    cambiadas = []
    for s in estado.get("solicitudes_bizum", []):
        if s.get("estado") == "pendiente" and hoy >= caducidad_solicitud(s["fecha"]):
            s["estado"] = "caducada"
            s["fecha_estado"] = caducidad_solicitud(s["fecha"]).isoformat()
            cambiadas.append(s)
    return cambiadas


def _crudo(usuario_id: str) -> dict:
    est = almacenamiento.cargar(usuario_id, "banco", defecto=None) or {}
    base = estado_inicial()
    base.update(est)
    return base


def cargar(usuario_id: str) -> dict:
    """Estado del banco al día del reloj simulado: las solicitudes vencidas ya figuran como caducadas
    (en memoria; se guardan cuando alguien guarda el estado o con `actualizar_solicitudes`)."""
    est = _crudo(usuario_id)
    expirar_solicitudes(est, fecha_simulada(usuario_id))
    return est


def guardar(usuario_id: str, estado: dict) -> None:
    almacenamiento.guardar(usuario_id, "banco", estado)


def _auditar(usuario_id: str, evento: str, s: dict, hoy: date) -> None:
    auditoria.registrar(usuario_id, evento, accion_id="pedir_bizum", fecha_simulada=hoy.isoformat(),
                        extra={"solicitud_id": s["id"], "estado": s["estado"], "contraparte": s["contraparte"],
                               "propuesta_id": s.get("propuesta_id")})


def actualizar_solicitudes(usuario_id: str) -> list[dict]:
    """Persiste y audita las caducidades que ya tocan según el reloj simulado. Idempotente.
    Lo llama el orquestador al avanzar el día; devuelve las solicitudes que acaban de caducar."""
    hoy = fecha_simulada(usuario_id)
    with almacenamiento.candado(usuario_id):
        est = _crudo(usuario_id)
        cambiadas = expirar_solicitudes(est, hoy)
        if cambiadas:
            guardar(usuario_id, est)
            for s in cambiadas:
                _auditar(usuario_id, "solicitud_caducada", s, hoy)
        return [dict(s) for s in cambiadas]


def solicitudes(usuario_id: str, estado: str | None = None) -> list[dict]:
    """Solicitudes de Bizum del usuario con su estado al día del reloj simulado."""
    return [dict(s) for s in cargar(usuario_id)["solicitudes_bizum"] if estado in (None, s["estado"])]


def pagos_de_solicitudes(usuario_id: str, hoy: date, dias: int) -> list[dict]:
    """Demos (`amigos_pagan_tras_solicitud_dias`): las solicitudes pendientes a las que el amigo responde hoy (hechas
    hace >= `dias` días y aún sin caducar) y, de cada una, el Bizum recibido por su importe, con la fecha de hoy y el
    id `bizum-sol-<solicitud>`. Solo lee: no cambia nada hasta `aceptar_pagadas`."""
    if isinstance(dias, bool) or not isinstance(dias, int) or dias < 1:
        return []
    salida = []
    for s in _crudo(usuario_id).get("solicitudes_bizum", []):
        if s.get("estado") != "pendiente":
            continue
        fecha = date.fromisoformat(str(s["fecha"])[:10])
        if not fecha + timedelta(days=dias) <= hoy < caducidad_solicitud(fecha):
            continue
        salida.append({"id": f"{PREFIJO_PAGO_SOLICITUD}{s['id']}", "fecha": hoy, "concepto": "BIZUM RECIBIDO",
                       "contraparte": s["contraparte"], "importe": str(s["importe"]), "canal": "bizum",
                       "nota": s.get("concepto") or None})
    return salida


def aceptar_pagadas(usuario_id: str, ids_movimientos: list[str], hoy: date) -> list[dict]:
    """Las solicitudes cuyo Bizum (`pagos_de_solicitudes`) ya ha entrado pasan a `aceptada` con la fecha de hoy
    (auditado). Idempotente: una solicitud que ya no está pendiente no cambia."""
    ids = {i[len(PREFIJO_PAGO_SOLICITUD):] for i in ids_movimientos if i.startswith(PREFIJO_PAGO_SOLICITUD)}
    if not ids:
        return []
    with almacenamiento.candado(usuario_id):
        est = _crudo(usuario_id)
        cambiadas = []
        for s in est["solicitudes_bizum"]:
            if s["id"] in ids and s.get("estado") == "pendiente":
                s["estado"], s["fecha_estado"] = "aceptada", hoy.isoformat()
                cambiadas.append(s)
        if cambiadas:
            guardar(usuario_id, est)
            for s in cambiadas:
                _auditar(usuario_id, "solicitud_aceptada", s, hoy)
        return [dict(s) for s in cambiadas]


def resolver_solicitud(usuario_id: str, solicitud_id: str, resultado: str) -> dict:
    """Simula la respuesta de la otra persona: `aceptada` o `rechazada`. Solo si sigue pendiente."""
    if resultado not in RESPUESTAS_SOLICITUD:
        raise ErrorAccion("parametros_invalidos", f"La respuesta debe ser una de: {', '.join(RESPUESTAS_SOLICITUD)}.")
    hoy = fecha_simulada(usuario_id)
    with almacenamiento.candado(usuario_id):
        est = cargar(usuario_id)
        for s in est["solicitudes_bizum"]:
            if s["id"] == solicitud_id:
                if s["estado"] != "pendiente":
                    raise ErrorAccion("no_se_puede", f"La solicitud ya no está pendiente (estado: {s['estado']}).")
                s["estado"], s["fecha_estado"] = resultado, hoy.isoformat()
                guardar(usuario_id, est)
                _auditar(usuario_id, f"solicitud_{resultado}", s, hoy)
                return dict(s)
    raise ErrorAccion("no_se_puede", "No se encuentra la solicitud.")
