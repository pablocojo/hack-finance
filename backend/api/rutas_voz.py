"""Rutas de la llamada y el chat (tareas V1 y V2). Piden `X-Demo-Key` si hay clave.
El `usuario_id` y la `propuesta_id` de las herramientas salen del `token_sesion` del servidor."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from ..plataforma import orquestador
from ..plataforma.tipos import ACCIONES
from ..voz import consultas, herramientas_llamada, sesiones, texto
from ..voz import sesion as abrir_sesion
from .rutas_copiloto import a_http, exigir_demo_key, no_implementado
from .sse import evento_sse

router = APIRouter(prefix="/voz", dependencies=[Depends(exigir_demo_key)])
router_casos = APIRouter()   # lo guardado de las llamadas, para «Lo que he aprendido»


class PeticionSesion(BaseModel):
    usuario_id: str = Field(min_length=1, max_length=64)
    propuesta_id: str | None = Field(default=None, min_length=1, max_length=128)  # sin ella: conversación general
    modo_preferido: str = Field(default="voz", max_length=16)


class PeticionTexto(BaseModel):
    token_sesion: str = Field(min_length=1, max_length=200)
    mensaje: str | None = Field(default=None, max_length=2000)  # sin mensaje: el saludo fijo


class PeticionPreparar(BaseModel):
    token_sesion: str = Field(min_length=1, max_length=200)
    accion_id: str = Field(min_length=1, max_length=40)
    parametros: dict = Field(default_factory=dict)


class PeticionFeedback(BaseModel):
    token_sesion: str = Field(min_length=1, max_length=200)
    resultado: herramientas_llamada.ResultadoLlamada


class PeticionHerramienta(BaseModel):
    """Cuerpo de las herramientas de consulta y de cambio: solo `token_sesion` y los campos planos de cada una. Un campo
    desconocido (p. ej. `usuario_id`) se rechaza: el usuario sale siempre de la sesión del servidor."""
    model_config = ConfigDict(extra="forbid")
    token_sesion: str = Field(min_length=1, max_length=200)


class PeticionCuentas(PeticionHerramienta):
    persona: str | None = Field(default=None, max_length=60)
    estado: str | None = Field(default=None, max_length=12)


class PeticionMovimientos(PeticionHerramienta):
    texto: str | None = Field(default=None, max_length=80)
    desde: str | None = Field(default=None, max_length=10)
    hasta: str | None = Field(default=None, max_length=10)
    importe_min: float | None = None
    importe_max: float | None = None
    limite: int | None = None


class PeticionActualizarCaso(PeticionHerramienta):
    caso_id: str = Field(min_length=1, max_length=80)
    accion: str = Field(min_length=1, max_length=40)
    persona: str | None = Field(default=None, max_length=120)
    importe: float | None = None
    via: str | None = Field(default=None, max_length=12)
    motivo: str | None = Field(default=None, max_length=300)
    dias: int | None = None
    escenario: str | None = Field(default=None, max_length=30)
    respuesta: str | None = Field(default=None, max_length=4)


class PeticionDeshacer(PeticionHerramienta):
    cambio_id: str = Field(min_length=1, max_length=40)


@router.post("/sesion")
def sesion(peticion: PeticionSesion) -> dict:
    try:
        return abrir_sesion(peticion.propuesta_id, peticion.usuario_id, peticion.modo_preferido).model_dump(mode="json")
    except Exception as error:
        raise a_http(error) from error


@router.post("/texto")
def texto_sse(peticion: PeticionTexto) -> StreamingResponse:
    try:
        registro = sesiones.obtener(peticion.token_sesion)
    except Exception as error:
        raise a_http(error) from error

    def generar():
        for tipo, datos in texto.eventos(registro, peticion.mensaje):
            yield evento_sse(tipo, datos)

    return StreamingResponse(generar(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/herramientas/preparar")
def herramienta_preparar(peticion: PeticionPreparar) -> dict:
    """`{preparada, titulo, tarjeta}` para el navegador (con el token de confirmación) o
    `{preparada: false, motivo}`. El navegador devuelve al agente solo `{preparada, titulo}`."""
    try:
        registro = sesiones.obtener(peticion.token_sesion)
        if peticion.accion_id not in ACCIONES:
            return {"preparada": False, "motivo": f"Acción no permitida: {peticion.accion_id!r}."}
        try:
            parametros = herramientas_llamada.construir_parametros_dict(peticion.accion_id, peticion.parametros)
        except (ArithmeticError, ValueError, TypeError):
            return {"preparada": False, "motivo": "Los datos de la acción no son válidos (revisa el importe)."}
        return herramientas_llamada.preparar(registro.usuario_id, registro.propuesta_id, peticion.accion_id, parametros)
    except Exception as error:
        raise a_http(error) from error


@router.post("/herramientas/feedback")
def herramienta_feedback(peticion: PeticionFeedback) -> dict:
    try:
        registro = sesiones.obtener(peticion.token_sesion)
        canal = "voz" if registro.modo in ("voz", "texto_el") else "texto"
        return herramientas_llamada.registrar(registro.usuario_id, registro.propuesta_id, peticion.resultado, canal)
    except Exception as error:
        raise a_http(error) from error


@router.post("/herramientas/consultar_cuentas")
def herramienta_consultar_cuentas(peticion: PeticionCuentas) -> dict:
    """Solo lectura, del usuario de la sesión. `{ok, personas, casos, …}` o `{ok: false, error}`."""
    try:
        registro = sesiones.obtener(peticion.token_sesion)
        return consultas.cuentas(registro.usuario_id, peticion.persona, peticion.estado)
    except Exception as error:
        raise a_http(error) from error


@router.post("/herramientas/buscar_movimientos")
def herramienta_buscar_movimientos(peticion: PeticionMovimientos) -> dict:
    """Solo lectura, hasta «hoy», sin la nota de Bizum, como mucho 10 resultados."""
    try:
        registro = sesiones.obtener(peticion.token_sesion)
        return consultas.movimientos(registro.usuario_id, peticion.texto, peticion.desde, peticion.hasta,
                                     peticion.importe_min, peticion.importe_max, peticion.limite)
    except Exception as error:
        raise a_http(error) from error


@router.post("/herramientas/lo_que_sabes_de_mi")
def herramienta_lo_que_sabes_de_mi(peticion: PeticionHerramienta) -> dict:
    try:
        registro = sesiones.obtener(peticion.token_sesion)
        return consultas.aprendido(registro.usuario_id)
    except Exception as error:
        raise a_http(error) from error


@router.post("/herramientas/actualizar_caso")
def herramienta_actualizar_caso(peticion: PeticionActualizarCaso) -> dict:
    """Cambio de un caso del usuario de la sesión, validado por el servidor con las reglas de `casos/`. Devuelve
    `{ok, hecho, caso, cambio_id}` (el navegador usa `cambio_id` para «Deshacer» y no se lo pasa al agente) o
    `{ok: false, error}` con el motivo en español. Nunca mueve dinero ni marca pagos de Bizum."""
    try:
        registro = sesiones.obtener(peticion.token_sesion)
        return herramientas_llamada.actualizar(
            registro.kit, peticion.caso_id, peticion.accion, peticion.persona, peticion.importe, peticion.via,
            peticion.motivo, peticion.dias, peticion.escenario, peticion.respuesta)
    except Exception as error:
        raise a_http(error) from error


@router.post("/herramientas/deshacer")
def herramienta_deshacer(peticion: PeticionDeshacer) -> dict:
    """«Deshacer» del aviso de un cambio de esta llamada (solo si el caso no ha cambiado desde entonces)."""
    try:
        registro = sesiones.obtener(peticion.token_sesion)
        return herramientas_llamada.deshacer(registro.kit, peticion.cambio_id)
    except Exception as error:
        raise a_http(error) from error


class MensajeConversacion(BaseModel):
    rol: Literal["meisam", "usuario", "agent", "user"]
    texto: str = Field(max_length=2000)


class PeticionConversacion(BaseModel):
    """Usuario y propuesta salen de la sesión del servidor (`token_sesion`), nunca del cuerpo."""
    token_sesion: str = Field(min_length=1, max_length=200)
    mensajes: list[MensajeConversacion] = Field(max_length=120)
    canal: Literal["voz", "texto"] = "voz"


@router.post("/conversacion")
def conversacion(peticion: PeticionConversacion) -> dict:
    """Al colgar (voz o chat): el agente post-llamada lee la transcripción y aplica al caso de la propuesta cambios de
    una lista cerrada (posponer, nota, silenciar contacto, olvidar a un deudor). Nunca mueve dinero. Sin caso: `ok`.
    Exige `token_sesion` (con un margen de gracia tras caducar los 10 min) y de él salen usuario y propuesta; en una
    conversación general la propuesta es vacía y solo se revisan los cambios de tipo propuestos."""
    try:
        registro = sesiones.obtener(peticion.token_sesion, gracia=sesiones.GRACIA_CONVERSACION)
        return orquestador.registrar_conversacion(registro.usuario_id, registro.propuesta_id,
                                                  [m.model_dump() for m in peticion.mensajes], peticion.canal)
    except Exception as error:
        raise a_http(error) from error


@router_casos.get("/usuarios/{usuario_id}/casos")
def casos_ver(usuario_id: str) -> list[dict]:
    try:
        return orquestador.casos_usuario(usuario_id)
    except Exception as error:
        raise a_http(error) from error


@router_casos.delete("/usuarios/{usuario_id}/casos/{caso_id}/conversaciones", dependencies=[Depends(exigir_demo_key)])
def conversaciones_borrar(usuario_id: str, caso_id: str) -> dict:
    try:
        return orquestador.borrar_conversaciones_caso(usuario_id, caso_id)
    except Exception as error:
        raise a_http(error) from error


@router.post("/herramientas/consultar")
def herramienta_consultar() -> None:
    raise no_implementado("O3")
