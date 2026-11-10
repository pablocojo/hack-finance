"""Rutas de la llamada y el chat (tareas V1 y V2). Piden `X-Demo-Key` si hay clave.
El `usuario_id` y la `propuesta_id` de las herramientas salen del `token_sesion` del servidor."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ..plataforma import orquestador
from ..plataforma.tipos import ACCIONES
from ..voz import herramientas_llamada, sesiones, texto
from ..voz import sesion as abrir_sesion
from .rutas_copiloto import a_http, exigir_demo_key, no_implementado
from .sse import evento_sse

router = APIRouter(prefix="/voz", dependencies=[Depends(exigir_demo_key)])
router_casos = APIRouter()   # lo guardado de las llamadas, para «Lo que he aprendido»


class PeticionSesion(BaseModel):
    usuario_id: str = Field(min_length=1, max_length=64)
    propuesta_id: str = Field(min_length=1, max_length=128)
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
    resultado: str = Field(min_length=1, max_length=40)


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
        parametros = herramientas_llamada.construir_parametros(peticion.accion_id, **peticion.parametros)
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


class MensajeConversacion(BaseModel):
    rol: Literal["meisam", "usuario", "agent", "user"]
    texto: str = Field(max_length=2000)


class PeticionConversacion(BaseModel):
    usuario_id: str = Field(min_length=1, max_length=64)
    propuesta_id: str = Field(min_length=1, max_length=128)
    mensajes: list[MensajeConversacion] = Field(max_length=120)
    canal: Literal["voz", "texto"] = "voz"


@router.post("/conversacion")
def conversacion(peticion: PeticionConversacion) -> dict:
    """Al colgar (voz o chat): el agente post-llamada lee la transcripción y aplica al caso de la propuesta cambios de
    una lista cerrada (posponer, nota, silenciar contacto, olvidar a un deudor). Nunca mueve dinero. Sin caso: `ok`."""
    try:
        return orquestador.registrar_conversacion(peticion.usuario_id, peticion.propuesta_id,
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
