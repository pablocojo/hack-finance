"""
Registro de herramientas del agente.

Una herramienta es una función de Python con tipos y docstring:

    from backend.agente.registro import herramienta

    @herramienta
    def calcular_algo(importe: float, meses: int = 12, ctx=None) -> dict:
        \"\"\"Primera línea: qué hace y cuándo usarla (Claude la lee para decidir).

        Args:
            importe: Importe en euros.
            meses: Número de meses (1-360).
        \"\"\"

- El esquema JSON (input_schema) se genera solo a partir de los tipos y de la sección Args.
- El parámetro `ctx` no aparece en el esquema: recibe la sesión (movimientos, perfil...).
- El resultado (dict, lista o texto) se convierte a JSON para Claude.
- Si la función lanza una excepción, Claude recibe el error y puede corregir la llamada.
"""

from __future__ import annotations

import inspect
import json
import re
import time
import types
import typing
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Callable

LIMITE_RESULTADO = 20_000  # caracteres que se devuelven a Claude por herramienta

_TIPOS = {str: "string", int: "integer", float: "number", bool: "boolean"}
_CABECERA_ARGS = re.compile(r"^\s*(Args|Argumentos|Parámetros|Parametros)\s*:\s*$", re.I)
_FIN_ARGS = re.compile(r"^\s*(Returns|Devuelve|Raises|Ejemplo|Ejemplos|Notas?)\s*:\s*$", re.I)
_LINEA_ARG = re.compile(r"^\s*(\w+)\s*(\([^)]*\))?\s*:\s*(.*)$")


@dataclass
class Herramienta:
    nombre: str
    descripcion: str
    funcion: Callable[..., Any]
    esquema: dict
    usa_ctx: bool
    activa: Callable[[], bool] | None = None

    def definicion(self) -> dict:
        return {"name": self.nombre, "description": self.descripcion, "input_schema": self.esquema}

    def disponible(self) -> bool:
        return self.activa is None or bool(self.activa())


REGISTRO: dict[str, Herramienta] = {}


def _esquema_tipo(anotacion) -> dict:
    if anotacion is inspect.Parameter.empty or anotacion is Any:
        return {"type": "string"}
    origen = typing.get_origin(anotacion)
    argumentos = typing.get_args(anotacion)
    if origen in (typing.Union, types.UnionType):
        no_nulos = [a for a in argumentos if a is not type(None)]
        if len(no_nulos) == 1:
            return _esquema_tipo(no_nulos[0])
        return {"anyOf": [_esquema_tipo(a) for a in no_nulos]}
    if origen is typing.Literal:
        valores = list(argumentos)
        tipo = _TIPOS.get(type(valores[0]), "string") if valores else "string"
        return {"type": tipo, "enum": valores}
    if origen in (list, tuple, set) or anotacion in (list, tuple, set):
        item = argumentos[0] if argumentos else str
        return {"type": "array", "items": _esquema_tipo(item)}
    if origen is dict or anotacion is dict:
        return {"type": "object"}
    if anotacion in _TIPOS:
        return {"type": _TIPOS[anotacion]}
    if anotacion in (date, datetime):
        return {"type": "string", "description": "Fecha en formato AAAA-MM-DD."}
    return {"type": "string"}


def _leer_docstring(funcion) -> tuple[str, dict[str, str]]:
    doc = inspect.getdoc(funcion) or ""
    descripcion, parametros = [], {}
    actual = None
    en_args = False
    for linea in doc.splitlines():
        if _CABECERA_ARGS.match(linea):
            en_args = True
            continue
        if en_args and _FIN_ARGS.match(linea):
            en_args = False
            actual = None
            continue
        if en_args:
            sangria = len(linea) - len(linea.lstrip())
            coincidencia = _LINEA_ARG.match(linea)
            if coincidencia and sangria <= 4:
                actual = coincidencia.group(1)
                parametros[actual] = coincidencia.group(3).strip()
            elif actual and linea.strip():
                parametros[actual] += " " + linea.strip()
            continue
        descripcion.append(linea)
    texto = "\n".join(descripcion).strip()
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    return texto, parametros


def crear_herramienta(funcion, *, nombre: str | None = None, activa=None) -> Herramienta:
    firma = inspect.signature(funcion)
    try:
        tipos = typing.get_type_hints(funcion)
    except Exception:
        tipos = {}
    descripcion, docs = _leer_docstring(funcion)
    propiedades, requeridos = {}, []
    usa_ctx = False
    for parametro in firma.parameters.values():
        if parametro.name == "ctx":
            usa_ctx = True
            continue
        if parametro.kind in (parametro.VAR_POSITIONAL, parametro.VAR_KEYWORD):
            continue
        esquema = _esquema_tipo(tipos.get(parametro.name, parametro.annotation))
        if parametro.name in docs:
            esquema["description"] = docs[parametro.name]
        if parametro.default is inspect.Parameter.empty:
            requeridos.append(parametro.name)
        elif parametro.default is not None:
            esquema["default"] = parametro.default
        propiedades[parametro.name] = esquema
    esquema_entrada = {"type": "object", "properties": propiedades}
    if requeridos:
        esquema_entrada["required"] = requeridos
    if not descripcion:
        raise ValueError(f"La herramienta {funcion.__name__} necesita un docstring que explique qué hace.")
    return Herramienta(
        nombre=nombre or funcion.__name__,
        descripcion=descripcion,
        funcion=funcion,
        esquema=esquema_entrada,
        usa_ctx=usa_ctx,
        activa=activa,
    )


def herramienta(_funcion=None, *, nombre: str | None = None, activa=None):
    """Decorador que registra la función como herramienta del agente."""

    def decorar(funcion):
        definida = crear_herramienta(funcion, nombre=nombre, activa=activa)
        REGISTRO[definida.nombre] = definida
        return funcion

    return decorar(_funcion) if _funcion is not None else decorar


def disponibles(nombres: list[str] | None = None) -> list[Herramienta]:
    """Herramientas activas, en orden alfabético (un orden estable mantiene la caché)."""
    _cargar_modulos()
    elegidas = [h for h in REGISTRO.values() if h.disponible()]
    if nombres is not None:
        elegidas = [h for h in elegidas if h.nombre in nombres]
    return sorted(elegidas, key=lambda h: h.nombre)


def _cargar_modulos() -> None:
    # Importar el paquete registra todas las herramientas (ver backend/herramientas/__init__.py).
    import backend.herramientas  # noqa: F401


def _por_defecto(valor):
    if isinstance(valor, Decimal):
        return float(valor)
    if isinstance(valor, (date, datetime)):
        return valor.isoformat()
    if hasattr(valor, "item"):  # tipos de numpy
        return valor.item()
    if hasattr(valor, "isoformat"):  # pandas.Timestamp
        return valor.isoformat()
    return str(valor)


def a_json(valor) -> str:
    if isinstance(valor, str):
        texto = valor
    else:
        texto = json.dumps(valor, ensure_ascii=False, default=_por_defecto)
    if len(texto) > LIMITE_RESULTADO:
        texto = texto[:LIMITE_RESULTADO] + " …[resultado recortado: filtra más o pide menos datos]"
    return texto


def _coaccionar(entrada: dict, esquema: dict) -> dict:
    """Corrige tipos sencillos que a veces llegan como texto ("3" -> 3)."""
    salida = {}
    for clave, valor in (entrada or {}).items():
        tipo = esquema.get("properties", {}).get(clave, {}).get("type")
        if isinstance(valor, str):
            try:
                if tipo == "integer":
                    valor = int(float(valor.replace(",", ".")))
                elif tipo == "number":
                    valor = float(valor.replace(",", "."))
                elif tipo == "boolean":
                    valor = valor.strip().lower() in {"true", "1", "si", "sí", "yes"}
            except ValueError:
                pass
        salida[clave] = valor
    return salida


def ejecutar(nombre: str, entrada: dict | None, ctx=None, permitidas: set[str] | None = None):
    """Ejecuta una herramienta. Devuelve (texto para Claude, es_error, milisegundos)."""
    inicio = time.perf_counter()
    _cargar_modulos()
    definida = REGISTRO.get(nombre)
    if definida is None or (permitidas is not None and nombre not in permitidas):
        return f"Error: la herramienta '{nombre}' no existe o no está disponible.", True, 0
    conocidos = set(definida.esquema.get("properties", {}))
    argumentos = {k: v for k, v in _coaccionar(entrada or {}, definida.esquema).items() if k in conocidos}
    if definida.usa_ctx:
        argumentos["ctx"] = ctx
    try:
        resultado = definida.funcion(**argumentos)
        texto, es_error = a_json(resultado), False
    except Exception as error:  # el error vuelve a Claude para que corrija la llamada
        texto, es_error = f"Error en {nombre}: {type(error).__name__}: {error}", True
    return texto, es_error, int((time.perf_counter() - inicio) * 1000)
