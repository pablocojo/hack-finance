"""
API HTTP del producto.

    uvicorn backend.api.main:app --reload          (http://localhost:8000/docs)

Endpoints:
    GET  /salud                  estado, clave configurada, herramientas y perfiles de ejemplo
    POST /datos/ejemplo          carga datos sintéticos en una sesión (la crea si hace falta)
    GET  /movimientos            lista de movimientos de la sesión
    POST /movimientos            sube un CSV del banco (multipart, campo "archivo")
    GET  /movimientos/resumen    resumen para el panel de gastos (sin IA, gratis)
    POST /chat                   pregunta al agente y devuelve la respuesta completa
    POST /chat/stream            igual, en streaming SSE (eventos del núcleo + "sesion" y "error")
"""

from __future__ import annotations

import asyncio
import queue
import threading

from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from .. import config
from ..agente import registro, servicio
from ..agente.guardarrailes import AVISO_IA
from ..datos.almacen import ALMACEN, Sesion
from ..datos.importar_csv import importar_csv
from ..datos.sinteticos import PERFILES
from ..herramientas.gastos import resumen_gastos
from . import rutas_banco, rutas_copiloto, rutas_metricas, rutas_voz
from .rutas_copiloto import exigir_demo_key
from .sse import estado_http, evento_sse, mensaje_error

AJUSTES = config.ajustes()
MAX_ARCHIVO = 5_000_000

app = FastAPI(title=f"{AJUSTES.nombre_producto} API", version="1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(AJUSTES.origenes_cors),
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["*"],
)
for _router in (rutas_copiloto.router, rutas_voz.router, rutas_voz.router_casos, rutas_banco.router, rutas_metricas.router):
    app.include_router(_router)


class Adjunto(BaseModel):
    tipo: str = Field(description="image/png, image/jpeg, image/gif, image/webp o application/pdf")
    datos_base64: str = Field(max_length=7_000_000)


class PeticionChat(BaseModel):
    mensaje: str = Field(min_length=1, max_length=4000)
    sesion_id: str | None = Field(default=None, max_length=64)
    modelo: str = Field(default="auto", description="auto, rapido, normal, profundo o un alias")
    adjunto: Adjunto | None = None


class PeticionEjemplo(BaseModel):
    perfil: str = "familia"
    sesion_id: str | None = Field(default=None, max_length=64)
    meses: int = Field(default=6, ge=1, le=24)


def _sesion(sesion_id: str) -> Sesion:
    try:
        return ALMACEN.obtener(sesion_id, crear=False)
    except KeyError as error:
        raise HTTPException(404, "La sesión no existe (¿se ha reiniciado el servidor?). Carga datos de nuevo.") from error


def _adjunto(peticion: PeticionChat) -> dict | None:
    return peticion.adjunto.model_dump() if peticion.adjunto else None


@app.get("/salud")
def salud() -> dict:
    clave, origen = config.clave_api("producto")
    aviso = None
    if not clave:
        aviso = "No hay clave: añade ANTHROPIC_API_KEY_PRODUCTO a .env o usa MODO_DEMO=reproducir."
    elif origen == "ANTHROPIC_API_KEY":
        aviso = "El producto usa ANTHROPIC_API_KEY (suele ser la de Claude Code). Define ANTHROPIC_API_KEY_PRODUCTO."
    ajustes = config.ajustes()
    return {
        "ok": True,
        "producto": ajustes.nombre_producto,
        "aviso_ia": AVISO_IA,
        "aviso_configuracion": aviso,
        "modelo_chat": ajustes.modelo_chat,
        "modo_demo": ajustes.modo_demo,
        "revisor_cumplimiento": ajustes.revisor_cumplimiento,
        "herramientas": [h.nombre for h in registro.disponibles()],
        "perfiles_ejemplo": {nombre: datos["descripcion"] for nombre, datos in PERFILES.items()},
        **servicio.estado(),
    }


@app.post("/datos/ejemplo", dependencies=[Depends(exigir_demo_key)])  # gasta o cambia estado
def datos_ejemplo(peticion: PeticionEjemplo) -> dict:
    sesion = ALMACEN.obtener(peticion.sesion_id)
    try:
        ALMACEN.cargar_ejemplo(sesion, peticion.perfil, meses=peticion.meses)
    except ValueError as error:
        raise HTTPException(400, str(error)) from error
    with sesion.turno:
        sesion.mensajes = []  # datos nuevos, conversación nueva
    return {"sesion_id": sesion.id, **sesion.resumen_datos()}


@app.get("/movimientos")
def listar_movimientos(sesion_id: str, limite: int = Query(200, ge=1, le=5000),
                       categoria: str | None = None) -> dict:
    sesion = _sesion(sesion_id)
    movimientos = sesion.movimientos
    if categoria:
        movimientos = [m for m in movimientos if m.get("categoria") == categoria]
    return {"sesion_id": sesion.id, "total": len(movimientos),
            "movimientos": list(reversed(movimientos))[:limite]}


@app.post("/movimientos", dependencies=[Depends(exigir_demo_key)])  # gasta o cambia estado
async def subir_movimientos(archivo: UploadFile = File(...), sesion_id: str | None = Query(None)) -> dict:
    contenido = await archivo.read()
    if len(contenido) > MAX_ARCHIVO:
        raise HTTPException(413, "El archivo supera 5 MB.")
    try:
        movimientos, informe = importar_csv(contenido)
    except ValueError as error:
        raise HTTPException(400, str(error)) from error
    sesion = ALMACEN.obtener(sesion_id)
    ALMACEN.cargar_movimientos(sesion, movimientos, origen=f"CSV del usuario ({archivo.filename})")
    with sesion.turno:
        sesion.mensajes = []
    return {"sesion_id": sesion.id, "informe": informe, **sesion.resumen_datos()}


@app.get("/movimientos/resumen")
def resumen_movimientos(sesion_id: str, meses: int = Query(3, ge=1, le=24)) -> dict:
    sesion = _sesion(sesion_id)
    if not sesion.movimientos:
        return {"sesion_id": sesion.id, "vacio": True}
    return {"sesion_id": sesion.id, "vacio": False, **resumen_gastos(meses=meses, ctx=sesion)}


@app.post("/chat", dependencies=[Depends(exigir_demo_key)])  # gasta o cambia estado
def chat(peticion: PeticionChat) -> dict:
    sesion = ALMACEN.obtener(peticion.sesion_id, perfil_demo=config.ajustes().perfil_demo)
    try:
        resultado = servicio.conversar(sesion, peticion.mensaje, adjunto=_adjunto(peticion),
                                       preferencia=peticion.modelo)
    except Exception as error:
        raise HTTPException(estado_http(error), mensaje_error(error)) from error
    return {"sesion_id": sesion.id, **resultado}


@app.post("/chat/stream", dependencies=[Depends(exigir_demo_key)])  # gasta o cambia estado
async def chat_stream(peticion: PeticionChat) -> StreamingResponse:
    sesion = ALMACEN.obtener(peticion.sesion_id, perfil_demo=config.ajustes().perfil_demo)
    cola: queue.Queue = queue.Queue()
    terminado = object()

    def trabajar() -> None:
        try:
            servicio.conversar(sesion, peticion.mensaje, adjunto=_adjunto(peticion),
                               preferencia=peticion.modelo, al_evento=lambda t, d: cola.put((t, d)))
        except Exception as error:  # el error llega al navegador como un evento más
            cola.put(("error", {"mensaje": mensaje_error(error), "tipo": type(error).__name__}))
        finally:
            cola.put(terminado)

    threading.Thread(target=trabajar, daemon=True).start()

    async def generar():
        yield evento_sse("sesion", {"sesion_id": sesion.id})
        while True:
            elemento = await asyncio.to_thread(cola.get)
            if elemento is terminado:
                break
            tipo, datos = elemento
            yield evento_sse(tipo, datos)

    return StreamingResponse(generar(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
