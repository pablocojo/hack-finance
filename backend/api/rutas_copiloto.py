"""
Rutas del Copiloto (Meisam): escenarios, reloj, notificaciones, feedback y acciones.
Contrato: docs/ARQUITECTURA.md §4. Dinero como cadena (`model_dump(mode="json")`). Las rutas de tareas
futuras responden 501.
"""

from __future__ import annotations

import secrets
import queue
import threading
import time
from datetime import date, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import AliasChoices, BaseModel, Field

from .. import config
from ..plataforma import orquestador
from ..plataforma.reloj import ahora_por_defecto
from ..plataforma.tipos import CanalFeedback, Feedback, ResultadoFeedback
from .sse import estado_http, evento_sse, mensaje_error

router = APIRouter()


# --- Utilidades compartidas por los cuatro routers ------------------------------------------------

def exigir_demo_key(x_demo_key: str | None = Header(default=None)) -> None:
    """Si `DEMO_KEY` está configurada, la cabecera `X-Demo-Key` debe coincidir. Sin clave, se
    permite (local). No es seguridad real: solo evita abusos durante la demo."""
    esperada = config.ajustes().demo_key
    if esperada and not secrets.compare_digest((x_demo_key or "").encode(), esperada.encode()):
        raise HTTPException(401, "Falta la cabecera X-Demo-Key o no es correcta.")


def estado_de_error(error: Exception) -> int:
    if isinstance(error, orquestador.NoEncontrado):
        return 404
    if isinstance(error, (orquestador.Prohibido, PermissionError)):
        return 403
    estado = getattr(error, "http", None)  # ErrorAccion (backend/acciones/errores.py)
    if isinstance(estado, int):
        return estado
    texto = str(error).lower()
    if isinstance(error, ValueError):
        if "caduc" in texto:
            return 410
        if "ya se usó" in texto or "ya usado" in texto or "ya fue usado" in texto or "un solo uso" in texto:
            return 409
        if "no se ofrece" in texto or "límite" in texto or "limite" in texto or "no coincide" in texto:
            return 403
    return estado_http(error)


def a_http(error: Exception) -> HTTPException:
    return HTTPException(estado_de_error(error), mensaje_error(error))


def no_implementado(tarea: str) -> HTTPException:
    return HTTPException(501, f"Aún sin hacer (tarea {tarea}).")


# --- Cuerpos -------------------------------------------------------------------------------------

class PeticionCargar(BaseModel):
    escenario_id: str = Field(min_length=1, max_length=64)


class Consentimientos(BaseModel):
    # Sin marcar por defecto: el cliente los da al pulsar «Activar». La clave principal es
    # `copiloto` (CONTRATO, «Integración del esqueleto»); `avisos` se acepta como alias.
    copiloto: bool = Field(False, validation_alias=AliasChoices("copiloto", "avisos"))
    memoria: bool = False


class PeticionActivar(BaseModel):
    modulos_activos: list[str] = Field(default_factory=list, max_length=20)
    consentimientos: Consentimientos = Field(default_factory=Consentimientos)


class PeticionAvanzar(BaseModel):
    usuario_id: str
    dias: int = Field(default=1, ge=1, le=60)


class PeticionFeedback(BaseModel):
    usuario_id: str
    propuesta_id: str
    resultado: ResultadoFeedback
    canal: CanalFeedback = "app"
    nota: str | None = Field(default=None, max_length=500)


class PeticionEditarPerfil(BaseModel):
    campo: str = Field(min_length=1, max_length=64)
    valor: Any = None


class PeticionEditarHecho(BaseModel):
    activo: bool | None = None
    texto: str | None = Field(default=None, max_length=500)


class PeticionPreparar(BaseModel):
    usuario_id: str
    propuesta_id: str
    accion_id: str
    parametros: dict = Field(default_factory=dict)
    editado: bool = False   # solo el botón del usuario; el agente de voz nunca lo envía


class PeticionConfirmar(BaseModel):
    usuario_id: str
    token_confirmacion: str = Field(min_length=1, max_length=200)


# --- Hechas (E8) ---------------------------------------------------------------------------------

@router.get("/escenarios")
def escenarios() -> list[dict]:
    try:
        return orquestador.listar_escenarios()
    except Exception as error:
        raise a_http(error) from error


@router.post("/demo/cargar", dependencies=[Depends(exigir_demo_key)])
def demo_cargar(peticion: PeticionCargar) -> dict:
    try:
        return orquestador.cargar_escenario(peticion.escenario_id)
    except Exception as error:
        raise a_http(error) from error


@router.post("/usuarios/{usuario_id}/activar", dependencies=[Depends(exigir_demo_key)])
def activar(usuario_id: str, peticion: PeticionActivar) -> dict:
    try:
        modelo = orquestador.activar(usuario_id, peticion.modulos_activos, peticion.consentimientos.model_dump())
    except Exception as error:
        raise a_http(error) from error
    return modelo.model_dump(mode="json")


@router.get("/usuarios/{usuario_id}/estado")
def estado(usuario_id: str) -> dict:
    try:
        return orquestador.estado_usuario(usuario_id)
    except Exception as error:
        raise a_http(error) from error


@router.post("/reloj/avanzar", dependencies=[Depends(exigir_demo_key)])
def reloj_avanzar(peticion: PeticionAvanzar) -> dict:
    decisiones = []
    try:
        for _ in range(peticion.dias):
            hoy = date.fromisoformat(orquestador.estado_usuario(peticion.usuario_id)["hoy"])
            decisiones += orquestador.avanzar_dia(peticion.usuario_id, hoy + timedelta(days=1))
        hoy = orquestador.estado_usuario(peticion.usuario_id)["hoy"]
    except Exception as error:
        raise a_http(error) from error
    return {"hoy": hoy, "decisiones": [d.model_dump(mode="json") for d in decisiones]}


@router.get("/reloj/reproducir", dependencies=[Depends(exigir_demo_key)])
def reloj_reproducir(usuario_id: str, dias: int = Query(1, ge=1, le=60), ms_por_dia: int = Query(1500, ge=0, le=10000),
                     pausar_en: str | None = None) -> StreamingResponse:
    """SSE: `dia`, `perfil`, `momento`, `propuesta`, `decision` y `fin` (o `error`)."""
    cola: queue.Queue = queue.Queue()
    terminado = object()

    def trabajar() -> None:
        try:
            primero = True
            for evento in orquestador.reproducir(usuario_id, dias, pausar_en):
                if evento.tipo == "dia":
                    if not primero and ms_por_dia:
                        time.sleep(ms_por_dia / 1000)
                    primero = False
                cola.put(evento_sse(evento.tipo, evento.datos))
        except Exception as error:
            cola.put(evento_sse("error", {"mensaje": mensaje_error(error), "tipo": type(error).__name__}))
        finally:
            cola.put(terminado)

    threading.Thread(target=trabajar, daemon=True).start()

    def generar():
        while True:
            elemento = cola.get()
            if elemento is terminado:
                break
            yield elemento

    return StreamingResponse(generar(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/usuarios/{usuario_id}/notificaciones")
def notificaciones(usuario_id: str, bandeja: str | None = None) -> list[dict]:
    try:
        return orquestador.notificaciones(usuario_id, bandeja)
    except Exception as error:
        raise a_http(error) from error


@router.get("/usuarios/{usuario_id}/propuestas/{propuesta_id}")
def propuesta(usuario_id: str, propuesta_id: str) -> dict:
    try:
        return orquestador.propuesta_detalle(usuario_id, propuesta_id)
    except Exception as error:
        raise a_http(error) from error


@router.post("/feedback", dependencies=[Depends(exigir_demo_key)])
def feedback(peticion: PeticionFeedback) -> dict:
    try:
        hoy = date.fromisoformat(orquestador.estado_usuario(peticion.usuario_id)["hoy"])
        fecha = ahora_por_defecto(hoy)  # hora simulada
        hechos = orquestador.registrar_feedback(Feedback(
            propuesta_id=peticion.propuesta_id, usuario_id=peticion.usuario_id, resultado=peticion.resultado,
            canal=peticion.canal, fecha=fecha, nota=peticion.nota))
    except Exception as error:
        raise a_http(error) from error
    return {"ok": True, "hechos_nuevos": [h.model_dump(mode="json") for h in hechos]}


@router.post("/acciones/preparar", dependencies=[Depends(exigir_demo_key)])
def acciones_preparar(peticion: PeticionPreparar) -> dict:
    try:
        tarjeta = orquestador.preparar_accion(peticion.usuario_id, peticion.propuesta_id, peticion.accion_id,
                                              peticion.parametros, editado=peticion.editado)
    except Exception as error:
        raise a_http(error) from error
    return tarjeta.model_dump(mode="json")


@router.post("/acciones/confirmar", dependencies=[Depends(exigir_demo_key)])
def acciones_confirmar(peticion: PeticionConfirmar) -> dict:
    """El `usuario_id` del cuerpo debe ser el dueño del token: lo comprueba `acciones.ejecutar`."""
    try:
        resultado = orquestador.confirmar_accion(peticion.usuario_id, peticion.token_confirmacion)
    except Exception as error:
        raise a_http(error) from error
    return resultado.model_dump(mode="json")


# --- Futuras (501) -------------------------------------------------------------------------------

@router.post("/acciones/deshacer", dependencies=[Depends(exigir_demo_key)])
def acciones_deshacer() -> None:
    raise no_implementado("O4")


# --- Lo que he aprendido de ti (U2): ver, editar y borrar ----------------------------------------

@router.get("/usuarios/{usuario_id}/perfil")
def perfil_ver(usuario_id: str) -> dict:
    try:
        return orquestador.perfil_usuario(usuario_id)
    except Exception as error:
        raise a_http(error) from error


@router.patch("/usuarios/{usuario_id}/perfil", dependencies=[Depends(exigir_demo_key)])
def perfil_editar(usuario_id: str, peticion: PeticionEditarPerfil) -> dict:
    """`{campo, valor}`. El campo especial `usar_perfil` (true/false) lo enciende o lo apaga."""
    try:
        if peticion.campo == "usar_perfil":
            if not isinstance(peticion.valor, bool):
                raise ValueError("`usar_perfil` es verdadero o falso.")
            if peticion.valor:
                return orquestador.reactivar_perfil_usuario(usuario_id)
            return orquestador.borrar_perfil_usuario(usuario_id)
        return orquestador.editar_perfil_usuario(usuario_id, peticion.campo, peticion.valor)
    except Exception as error:
        raise a_http(error) from error


@router.delete("/usuarios/{usuario_id}/perfil", dependencies=[Depends(exigir_demo_key)])
def perfil_borrar(usuario_id: str) -> dict:
    try:
        return orquestador.borrar_perfil_usuario(usuario_id)
    except Exception as error:
        raise a_http(error) from error


@router.delete("/usuarios/{usuario_id}/perfil/{campo}", dependencies=[Depends(exigir_demo_key)])
def perfil_borrar_campo(usuario_id: str, campo: str) -> dict:
    try:
        return orquestador.borrar_campo_perfil_usuario(usuario_id, campo)
    except Exception as error:
        raise a_http(error) from error


@router.get("/usuarios/{usuario_id}/aprendido")
def aprendido_ver(usuario_id: str) -> dict:
    try:
        return orquestador.aprendido_usuario(usuario_id)
    except Exception as error:
        raise a_http(error) from error


@router.delete("/usuarios/{usuario_id}/aprendido", dependencies=[Depends(exigir_demo_key)])
def aprendido_olvidar_todo(usuario_id: str) -> dict:
    try:
        return orquestador.olvidar_todo_usuario(usuario_id)
    except Exception as error:
        raise a_http(error) from error


@router.patch("/usuarios/{usuario_id}/aprendido/{hecho_id}", dependencies=[Depends(exigir_demo_key)])
def aprendido_editar(usuario_id: str, hecho_id: str, peticion: PeticionEditarHecho) -> dict:
    try:
        return orquestador.editar_hecho_usuario(usuario_id, hecho_id, peticion.activo, peticion.texto)
    except Exception as error:
        raise a_http(error) from error


@router.delete("/usuarios/{usuario_id}/aprendido/{hecho_id}", dependencies=[Depends(exigir_demo_key)])
def aprendido_borrar(usuario_id: str, hecho_id: str) -> dict:
    try:
        return orquestador.borrar_hecho_usuario(usuario_id, hecho_id)
    except Exception as error:
        raise a_http(error) from error


@router.post("/usuarios/{usuario_id}/pruebas")
def pruebas(usuario_id: str) -> None:
    raise no_implementado("O8")


@router.get("/usuarios/{usuario_id}/amigos")
def amigos(usuario_id: str) -> list[dict]:
    """O7, saldo con cada amigo: `list[Amigo]` calculada desde los casos (contraparte enmascarada, saldo
    y estado; sin conceptos). Se borran al saldarse o a los 90 días."""
    try:
        return orquestador.amigos_usuario(usuario_id)
    except Exception as error:
        raise a_http(error) from error


@router.delete("/usuarios/{usuario_id}/amigos/{contraparte}", dependencies=[Depends(exigir_demo_key)])
def amigo_borrar(usuario_id: str, contraparte: str) -> list[dict]:
    """Borra a un amigo de «Lo que he aprendido» (por su nombre enmascarado, p. ej. `Marcos R.`)."""
    try:
        return orquestador.borrar_amigo_usuario(usuario_id, contraparte)
    except Exception as error:
        raise a_http(error) from error
