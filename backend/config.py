"""
Configuración del backend. Se lee de variables de entorno y del archivo .env de la raíz.

Claves de la API (nunca en el código ni en git):
- ANTHROPIC_API_KEY_PRODUCTO: la usa el agente de la app (clave 2 del hackathon).
- ANTHROPIC_API_KEY_EVALS: la usan las evals (clave 3). Si falta, se usa la del producto.
- ANTHROPIC_API_KEY: último recurso. Suele ser la de Claude Code (clave 1), así que
  /salud avisa si el producto acaba usándola.

python-dotenv no sobrescribe variables que ya existen en el entorno: por eso las claves
del producto y de las evals tienen nombres propios.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

try:
    from dotenv import load_dotenv

    load_dotenv(RAIZ / ".env", override=False)
except ImportError:  # python-dotenv es opcional
    pass

VERDADERO = {"1", "true", "si", "sí", "yes", "on"}


def _texto(nombre: str, defecto: str | None = None) -> str | None:
    valor = os.environ.get(nombre)
    if valor is None or not valor.strip():
        return defecto
    return valor.strip()


def _entero(nombre: str, defecto: int) -> int:
    try:
        return int(_texto(nombre, str(defecto)))
    except ValueError:
        return defecto


def _bool(nombre: str, defecto: bool) -> bool:
    valor = _texto(nombre)
    if valor is None:
        return defecto
    return valor.lower() in VERDADERO


@dataclass(frozen=True)
class Ajustes:
    nombre_producto: str
    modelo_chat: str
    esfuerzo_chat: str | None
    max_vueltas: int
    max_tokens: int
    max_historial: int
    revisor_cumplimiento: bool
    modo_demo: str
    busqueda_web: bool
    ejecucion_codigo: bool
    origenes_cors: tuple[str, ...]
    perfil_demo: str
    alpha_vantage_key: str | None
    frankfurter_url: str
    guardar_perfiles: bool


def ajustes() -> Ajustes:
    """Lee la configuración en cada llamada, así los tests pueden cambiar el entorno."""
    origenes = _texto("ORIGENES_CORS", "http://localhost:3000,http://127.0.0.1:3000")
    return Ajustes(
        nombre_producto=_texto("NOMBRE_PRODUCTO", "Finanzas IA"),
        modelo_chat=_texto("MODELO_CHAT", "sonnet"),
        esfuerzo_chat=_texto("ESFUERZO_CHAT", "medium"),
        max_vueltas=_entero("MAX_VUELTAS", 8),
        max_tokens=_entero("MAX_TOKENS", 4000),
        max_historial=_entero("MAX_HISTORIAL", 40),
        revisor_cumplimiento=_bool("REVISOR_CUMPLIMIENTO", True),
        modo_demo=(_texto("MODO_DEMO", "off") or "off").lower(),
        busqueda_web=_bool("BUSQUEDA_WEB", False),
        ejecucion_codigo=_bool("EJECUCION_CODIGO", False),
        origenes_cors=tuple(o.strip() for o in origenes.split(",") if o.strip()),
        perfil_demo=_texto("PERFIL_DEMO", "familia"),
        alpha_vantage_key=_texto("ALPHA_VANTAGE_API_KEY"),
        frankfurter_url=_texto("FRANKFURTER_URL", "https://api.frankfurter.dev/v1"),
        guardar_perfiles=_bool("GUARDAR_PERFILES", True),
    )


def clave_api(uso: str = "producto") -> tuple[str | None, str | None]:
    """Devuelve (clave, nombre de la variable de la que sale) para un uso: producto o evals."""
    if uso == "evals":
        orden = ["ANTHROPIC_API_KEY_EVALS", "ANTHROPIC_API_KEY_PRODUCTO", "ANTHROPIC_API_KEY"]
    else:
        orden = ["ANTHROPIC_API_KEY_PRODUCTO", "ANTHROPIC_API_KEY"]
    for nombre in orden:
        valor = _texto(nombre)
        if valor:
            return valor, nombre
    return None, None
