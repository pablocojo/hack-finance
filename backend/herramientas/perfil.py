"""Memoria del perfil del usuario: objetivos, situación y preferencias que cuenta en la conversación."""

from __future__ import annotations

import re

from ..agente.guardarrailes import enmascarar
from ..agente.registro import herramienta
from ..datos.almacen import ALMACEN

PROHIBIDAS = ("iban", "tarjeta", "dni", "nie", "pasaporte", "contrasena", "contraseña", "password",
              "pin", "cvv", "clave", "numero_cuenta", "cuenta_bancaria", "salud", "religion", "politica")
MAX_CLAVES = 30


@herramienta
def guardar_preferencia(clave: str, valor: str, ctx=None) -> dict:
    """Guarda un dato estable del usuario para tenerlo en cuenta en el resto de la conversación.

    Úsala cuando cuente su objetivo de ahorro, su situación (estudiante, autónomo, familia), su moneda
    o cómo prefiere las respuestas. Nunca guardes datos bancarios, documentos de identidad ni datos de salud.

    Args:
        clave: Nombre corto en minúsculas, por ejemplo "objetivo_ahorro" o "situacion_laboral".
        valor: Valor en texto, por ejemplo "6.000 € para junio de 2027".
    """
    clave_limpia = re.sub(r"[^a-z0-9_]", "_", (clave or "").strip().lower())[:40].strip("_")
    if not clave_limpia:
        raise ValueError("La clave no puede estar vacía.")
    if any(p in clave_limpia for p in PROHIBIDAS):
        raise ValueError("Ese dato es sensible y no se guarda en el perfil.")
    valor_limpio, ocultos = enmascarar(str(valor)[:300])
    with ctx.cerrojo:
        if clave_limpia not in ctx.perfil and len(ctx.perfil) >= MAX_CLAVES:
            raise ValueError("El perfil está lleno; actualiza una clave existente.")
        ctx.perfil[clave_limpia] = valor_limpio
        perfil = dict(ctx.perfil)
    ALMACEN.guardar_perfil(ctx)
    return {"guardado": {clave_limpia: valor_limpio}, "datos_ocultados": ocultos, "perfil": perfil}


@herramienta
def leer_perfil(ctx=None) -> dict:
    """Devuelve lo que se sabe del usuario (objetivos, situación, preferencias) y qué datos hay cargados."""
    with ctx.cerrojo:
        return {"perfil": dict(ctx.perfil), "datos": ctx.resumen_datos()}
