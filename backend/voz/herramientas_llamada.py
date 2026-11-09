"""
Herramientas de la llamada. Las usan el agente del nivel 3 (grupo `llamada`, invisibles para /kit) y
los endpoints /voz/herramientas/* (que llama el navegador por el agente de ElevenLabs).

Regla de oro: el token de confirmación nunca llega a un modelo. Al agente solo vuelve
`{preparada, titulo}`; la tarjeta completa va al navegador (evento `tarjeta` o respuesta HTTP).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

from ..acciones import ErrorAccion
from ..agente.registro import herramienta
from ..plataforma import orquestador
from ..plataforma.reloj import ahora_por_defecto
from ..plataforma.tipos import ACCIONES, Feedback

AccionLlamada = Literal[ACCIONES]  # type: ignore[valid-type]
ResultadoLlamada = Literal["rechazada", "falso_positivo", "no_avisar_tipo", "no_avisar_comercio", "no_avisar_contacto"]


def construir_parametros(accion_id: str, **plano) -> dict:
    """Campos planos de la herramienta -> `parametros` de la acción (sin vacíos)."""
    p = {k: v for k, v in plano.items() if v is not None and v != ""}
    if "importe" in p:
        p["importe"] = format(Decimal(str(p["importe"])), "f")
    if accion_id != "cancelar_suscripcion":
        p.pop("bloquear_cobros", None)
    return p


def preparar(usuario_id: str, propuesta_id: str, accion_id: str, parametros: dict) -> dict:
    """`{preparada, titulo, tarjeta}` o `{preparada: False, motivo}`. La tarjeta lleva el token."""
    try:
        tarjeta = orquestador.preparar_accion(usuario_id, propuesta_id, accion_id, parametros)
    except (ErrorAccion, orquestador.Prohibido) as error:
        return {"preparada": False, "motivo": getattr(error, "mensaje", None) or str(error)}
    return {"preparada": True, "titulo": tarjeta.titulo, "tarjeta": tarjeta.model_dump(mode="json")}


def registrar(usuario_id: str, propuesta_id: str, resultado: str, canal: str = "voz") -> dict:
    hoy = date.fromisoformat(orquestador.estado_usuario(usuario_id)["hoy"])
    hechos = orquestador.registrar_feedback(Feedback(
        propuesta_id=propuesta_id, usuario_id=usuario_id, resultado=resultado, canal=canal,
        fecha=ahora_por_defecto(hoy)))
    return {"ok": True, "hechos_nuevos": [h.model_dump(mode="json") for h in hechos]}


@herramienta(grupo="llamada")
def preparar_accion(accion_id: AccionLlamada, contraparte: str | None = None, importe: float | None = None,
                    concepto: str | None = None, comercio: str | None = None, movimiento_id: str | None = None,
                    motivo: str | None = None, cuando: str | None = None, texto: str | None = None,
                    bloquear_cobros: bool | None = None, ctx=None) -> dict:
    """Prepara una acción de la lista ofrecida y muestra la tarjeta de confirmación. No ejecuta nada.

    Args:
        accion_id: Acción de la lista ofrecida.
        contraparte: Persona a quien se pide el Bizum, tal como aparece en el contexto.
        importe: Importe en euros.
        concepto: Concepto del Bizum.
        comercio: Comercio de la acción.
        movimiento_id: Identificador del movimiento a reclamar.
        motivo: Motivo de la reclamación.
        cuando: Fecha AAAA-MM-DD del recordatorio.
        texto: Texto del recordatorio.
        bloquear_cobros: Solo con cancelar_suscripcion: bloquear también los cobros.
    """
    parametros = construir_parametros(
        accion_id, contraparte=contraparte, importe=importe, concepto=concepto, comercio=comercio,
        movimiento_id=movimiento_id, motivo=motivo, cuando=cuando, texto=texto, bloquear_cobros=bloquear_cobros)
    r = preparar(ctx.usuario_id, ctx.propuesta_id, accion_id, parametros)  # usuario y propuesta: del servidor
    if not r["preparada"]:
        return r
    ctx.tarjetas.append(r["tarjeta"])  # buzón para el navegador; el modelo no lo ve
    return {"preparada": True, "titulo": r["titulo"]}


@herramienta(grupo="llamada")
def registrar_feedback(resultado: ResultadoLlamada, ctx=None) -> dict:
    """Registra que el usuario rechaza el aviso o dice que era un error.

    Args:
        resultado: rechazada, falso_positivo o no_avisar_tipo, no_avisar_comercio, no_avisar_contacto.
    """
    registrar(ctx.usuario_id, ctx.propuesta_id, resultado, canal="texto")
    return {"registrada": True}
