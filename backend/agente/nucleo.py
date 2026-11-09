"""
Núcleo del agente: el bucle de herramientas sobre la Messages API.

    from backend.agente.nucleo import Agente
    from backend.datos.almacen import ALMACEN

    sesion = ALMACEN.crear(perfil_demo="familia")
    resultado = Agente().responder(sesion, "¿En qué gasto más?")
    print(resultado.texto, resultado.coste_usd)

Con al_evento(tipo, datos) la respuesta llega en streaming. Eventos, en orden:
    aviso               {"texto"}  datos personales ocultados antes de enviar el mensaje
    texto               {"texto"}  trozo de la respuesta
    herramienta_inicio  {"id", "nombre", "entrada"}
    herramienta_fin     {"id", "nombre", "entrada", "ms", "error", "resumen"}
    revision            {"aprobada", "problemas", "texto"}  texto = respuesta corregida o null
    fin                 {"texto", "modelo", "vueltas", "coste_usd", "coste_sesion_usd", "trazas", ...}
Los errores de la API se lanzan como excepciones (la API HTTP los convierte en un evento "error").
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from typing import Callable

from .. import claude_client, config
from ..datos.almacen import Sesion
from . import guardarrailes, prompts, registro

AlEvento = Callable[[str, dict], None]

PREFERENCIAS = {"rapido": "haiku", "normal": "sonnet", "profundo": "opus"}
PALABRAS_PROFUNDO = ("analiza", "análisis", "compara", "estrategia", "optimiza", "planifica",
                     "detallad", "escenario", "a fondo")
TIPOS_IMAGEN = {"image/jpeg", "image/png", "image/gif", "image/webp"}
MAX_TOKENS_OPUS = 8000  # Opus piensa siempre y max_tokens incluye ese razonamiento
LIMITE_VUELTAS = ("He llegado al límite de pasos para esta pregunta. "
                  "Prueba a dividirla en preguntas más pequeñas.")
_CONFIG = object()


@dataclass
class Resultado:
    texto: str
    modelo: str
    vueltas: int
    coste_usd: float
    coste_sesion_usd: float
    herramientas: list[str] = field(default_factory=list)
    trazas: list[dict] = field(default_factory=list)
    revision: dict | None = None
    avisos: list[str] = field(default_factory=list)
    tokens: dict = field(default_factory=dict)

    def a_dict(self) -> dict:
        return asdict(self)


def elegir_modelo(mensaje: str, preferencia: str | None = "auto", defecto: str = "sonnet") -> str:
    """Enrutado sencillo: preferencia explícita, o Opus para análisis largos y Sonnet para el resto."""
    if preferencia in PREFERENCIAS:
        return PREFERENCIAS[preferencia]
    if preferencia and preferencia != "auto":
        return preferencia  # alias (haiku/sonnet/opus) o ID completo
    texto = (mensaje or "").lower()
    if len(texto) > 600 or any(palabra in texto for palabra in PALABRAS_PROFUNDO):
        return "opus"
    return defecto


def herramientas_servidor(ajustes: config.Ajustes) -> list[dict]:
    """Herramientas que ejecuta Anthropic (se activan en .env; la búsqueda cuesta 10 $ / 1.000)."""
    extra = []
    if ajustes.busqueda_web:
        extra.append({"type": "web_search_20260209", "name": "web_search", "max_uses": 3})
    if ajustes.ejecucion_codigo:
        extra.append({"type": "code_execution_20250825", "name": "code_execution"})
    return extra


def contenido_usuario(texto: str, adjunto: dict | None) -> str | list:
    if not adjunto:
        return texto
    tipo = (adjunto.get("tipo") or "").lower()
    datos = adjunto.get("datos_base64") or ""
    if tipo in TIPOS_IMAGEN:
        bloque = {"type": "image", "source": {"type": "base64", "media_type": tipo, "data": datos}}
    elif tipo == "application/pdf":
        bloque = {"type": "document", "source": {"type": "base64", "media_type": tipo, "data": datos}}
    else:
        raise ValueError(f"Tipo de adjunto no admitido: {tipo}. Usa PNG, JPG, GIF, WEBP o PDF.")
    return [bloque, {"type": "text", "text": texto}]


def bloque_a_dict(bloque) -> dict:
    """Convierte un bloque de la respuesta en un dict reutilizable en el historial."""
    if isinstance(bloque, dict):
        return bloque
    tipo = getattr(bloque, "type", None)
    if tipo == "text":
        return {"type": "text", "text": bloque.text}
    if tipo == "tool_use":
        return {"type": "tool_use", "id": bloque.id, "name": bloque.name, "input": bloque.input}
    if tipo == "thinking":
        return {"type": "thinking", "thinking": bloque.thinking, "signature": bloque.signature}
    if tipo == "redacted_thinking":
        return {"type": "redacted_thinking", "data": bloque.data}
    if hasattr(bloque, "model_dump"):
        return bloque.model_dump(mode="json", exclude_none=True)
    return {k: v for k, v in vars(bloque).items() if v is not None}


def _solo_resultados(mensaje: dict) -> bool:
    contenido = mensaje.get("content")
    return isinstance(contenido, list) and bool(contenido) and all(
        isinstance(b, dict) and b.get("type") == "tool_result" for b in contenido
    )


def recortar_historial(mensajes: list[dict], maximo: int) -> list[dict]:
    """Deja como mucho `maximo` mensajes, cortando siempre al principio de una pregunta del usuario."""
    if len(mensajes) <= maximo:
        return mensajes
    for indice in range(len(mensajes) - maximo, len(mensajes)):
        mensaje = mensajes[indice]
        if mensaje["role"] == "user" and not _solo_resultados(mensaje):
            return mensajes[indice:]
    return []


def _anadir_texto(mensajes: list[dict], texto: str) -> None:
    if mensajes and mensajes[-1]["role"] == "assistant":
        mensajes[-1]["content"].append({"type": "text", "text": texto})
    else:
        mensajes.append({"role": "assistant", "content": [{"type": "text", "text": texto}]})


class Agente:
    def __init__(self, *, modelo: str | None = None, max_vueltas: int | None = None,
                 esfuerzo=_CONFIG, revisor: bool | None = None, herramientas: list[str] | None = None,
                 uso: str = "producto", sistema: str | None = None):
        self.sistema = sistema  # prompt del sistema propio (la llamada); None = el del kit
        ajustes = config.ajustes()
        self.modelo = modelo
        self.max_vueltas = max_vueltas or ajustes.max_vueltas
        self.esfuerzo = ajustes.esfuerzo_chat if esfuerzo is _CONFIG else esfuerzo
        self.revisor = ajustes.revisor_cumplimiento if revisor is None else revisor
        self.uso = uso
        self.definidas = registro.disponibles(herramientas)
        self.permitidas = {h.nombre for h in self.definidas}
        self.servidor = herramientas_servidor(ajustes)
        self.max_tokens = ajustes.max_tokens
        self.max_historial = ajustes.max_historial
        self.modelo_defecto = ajustes.modelo_chat

    def herramientas_api(self) -> list[dict]:
        return [h.definicion() for h in self.definidas] + self.servidor

    def responder(self, sesion: Sesion, mensaje: str, *, adjunto: dict | None = None,
                  preferencia: str | None = "auto", al_evento: AlEvento | None = None) -> Resultado:
        emitir = al_evento or (lambda tipo, datos: None)
        modelo = self.modelo or elegir_modelo(mensaje, preferencia, self.modelo_defecto)
        es_opus = claude_client.modelo_id(modelo) == claude_client.MODELOS["opus"]
        max_tokens = max(self.max_tokens, MAX_TOKENS_OPUS) if es_opus else self.max_tokens
        trazas: list[dict] = []
        avisos: list[str] = []

        limpio, ocultos = guardarrailes.enmascarar(mensaje)
        if ocultos:
            avisos.append(f"He ocultado {ocultos} dato(s) personal(es) antes de enviar tu mensaje a la IA.")
            emitir("aviso", {"texto": avisos[-1]})
        sospecha = guardarrailes.parece_inyeccion(limpio)
        if sospecha:
            trazas.append({"tipo": "posible_inyeccion", "fragmento": sospecha})

        with sesion.turno:
            mensajes = recortar_historial(list(sesion.mensajes), self.max_historial)
            mensajes.append({"role": "user", "content": contenido_usuario(limpio, adjunto)})
            system = self.sistema or prompts.system_prompt(resumen_datos=sesion.resumen_datos(), perfil=dict(sesion.perfil))
            herramientas = self.herramientas_api()
            textos: list[str] = []
            usadas: list[str] = []
            coste, vueltas, terminado = 0.0, 0, False
            totales = {"entrada": 0, "salida": 0, "cache_lectura": 0, "cache_escritura": 0}

            while vueltas < self.max_vueltas:
                vueltas += 1
                peticion = claude_client.preparar_peticion(
                    modelo=modelo, messages=mensajes, system=system, tools=herramientas,
                    max_tokens=max_tokens, esfuerzo=self.esfuerzo,
                )
                inicio = time.perf_counter()
                respuesta = self._llamar(peticion, al_evento, separar=bool(textos), emitir=emitir)
                importe = claude_client.coste(peticion["model"], getattr(respuesta, "usage", None))
                claude_client.registrar_coste(importe)
                coste += importe
                consumo = claude_client.tokens(getattr(respuesta, "usage", None))
                for clave in totales:
                    totales[clave] += consumo[clave]
                trazas.append({
                    "tipo": "llamada", "vuelta": vueltas, "modelo": peticion["model"],
                    "stop_reason": respuesta.stop_reason, "ms": int((time.perf_counter() - inicio) * 1000),
                    "tokens": consumo, "coste_usd": round(importe, 6),
                })
                bloques = [bloque_a_dict(b) for b in respuesta.content]
                mensajes.append({"role": "assistant", "content": bloques})
                textos.extend(b["text"] for b in bloques if b.get("type") == "text" and b.get("text", "").strip())

                if respuesta.stop_reason == "tool_use":
                    usos = [b for b in bloques if b.get("type") == "tool_use"]
                    usadas.extend(u["name"] for u in usos)
                    mensajes.append({"role": "user", "content": self._ejecutar(usos, sesion, emitir, trazas)})
                    continue
                if respuesta.stop_reason == "pause_turn":  # herramientas del servidor: seguir el turno
                    continue
                if respuesta.stop_reason == "max_tokens":
                    textos.append("(La respuesta se ha cortado por longitud.)")
                if respuesta.stop_reason == "refusal" and not textos:
                    textos.append("No puedo ayudarte con esa petición.")
                terminado = True
                break

            if not terminado:
                textos.append(LIMITE_VUELTAS)
                emitir("texto", {"texto": "\n\n" + LIMITE_VUELTAS})
                _anadir_texto(mensajes, LIMITE_VUELTAS)

            texto = "\n\n".join(textos).strip() or "No he podido generar una respuesta."
            revision = None
            if self.revisor:
                revision = self._revisar(limpio, texto, emitir, trazas)
                if revision:
                    coste += revision.get("coste_usd", 0.0)
                    if revision.get("texto_corregido"):
                        texto = revision["texto_corregido"]
            sesion.mensajes = mensajes
            sesion.coste_usd += coste
            coste_sesion = sesion.coste_usd

        resultado = Resultado(
            texto=texto, modelo=claude_client.modelo_id(modelo), vueltas=vueltas,
            coste_usd=round(coste, 6), coste_sesion_usd=round(coste_sesion, 6),
            herramientas=usadas, trazas=trazas, revision=revision, avisos=avisos, tokens=totales,
        )
        emitir("fin", resultado.a_dict())
        return resultado

    def _llamar(self, peticion: dict, al_evento: AlEvento | None, *, separar: bool, emitir: AlEvento):
        api = claude_client.cliente(self.uso).messages
        if al_evento is None:
            return api.create(**peticion)
        with api.stream(**peticion) as stream:
            primero = True
            for trozo in stream.text_stream:
                if primero and separar:
                    emitir("texto", {"texto": "\n\n"})
                primero = False
                emitir("texto", {"texto": trozo})
            return stream.get_final_message()

    def _ejecutar(self, usos: list[dict], sesion: Sesion, emitir: AlEvento, trazas: list[dict]) -> list[dict]:
        for uso in usos:
            emitir("herramienta_inicio", {"id": uso["id"], "nombre": uso["name"], "entrada": uso.get("input") or {}})

        def correr(uso):
            return registro.ejecutar(uso["name"], uso.get("input") or {}, ctx=sesion, permitidas=self.permitidas)

        if len(usos) == 1:
            salidas = [correr(usos[0])]
        else:  # herramientas independientes en paralelo; el orden del resultado se conserva
            with ThreadPoolExecutor(max_workers=min(4, len(usos))) as grupo:
                salidas = list(grupo.map(correr, usos))

        resultados = []
        for uso, (texto, es_error, ms) in zip(usos, salidas):
            traza = {"tipo": "herramienta", "id": uso["id"], "nombre": uso["name"],
                     "entrada": uso.get("input") or {}, "ms": ms, "error": es_error, "resumen": texto[:400]}
            trazas.append(traza)
            emitir("herramienta_fin", traza)
            bloque = {"type": "tool_result", "tool_use_id": uso["id"], "content": texto}
            if es_error:
                bloque["is_error"] = True
            resultados.append(bloque)
        return resultados

    def _revisar(self, pregunta: str, texto: str, emitir: AlEvento, trazas: list[dict]) -> dict | None:
        try:
            revision = guardarrailes.revisar_cumplimiento(pregunta, texto, uso=self.uso)
        except Exception as error:  # si el revisor falla, la respuesta sale igual y queda anotado
            trazas.append({"tipo": "revision", "error": f"{type(error).__name__}: {error}"})
            return None
        corregida = None
        if not revision.get("aprobada", True) and (revision.get("respuesta_corregida") or "").strip():
            corregida = revision["respuesta_corregida"].strip()
        revision["texto_corregido"] = corregida
        trazas.append({"tipo": "revision", "aprobada": revision.get("aprobada"),
                       "problemas": revision.get("problemas", []),
                       "coste_usd": round(revision.get("coste_usd", 0.0), 6)})
        emitir("revision", {"aprobada": revision.get("aprobada", True),
                            "problemas": revision.get("problemas", []), "texto": corregida})
        return revision
