"""
Persistencia en JSON por usuario: `datos_usuario/<usuario_id>/<nombre>.json`.

- Escritura atómica: archivo temporal en la misma carpeta + `os.replace`.
- Candado por usuario (`candado`): el orquestador lo toma antes de leer-modificar-escribir.
- `auditoria.jsonl`: un registro por línea, con los datos personales enmascarados.
- Solo escribe el orquestador (y `conocimiento.guardar` en `_cache`). Los nombres que empiezan por
  `_` (`_cache`, `_modulos`) son carpetas del sistema, no usuarios.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, TypeAdapter

from .. import config
from .privacidad import enmascarar_datos

_ID_VALIDO = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_-]{0,63}$")
_NOMBRE_VALIDO = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]{0,63}$")
_candados: dict[str, threading.RLock] = {}
_candados_guarda = threading.Lock()


def raiz() -> Path:
    return config.ajustes().datos_usuario_dir


def carpeta_usuario(usuario_id: str, crear: bool = False) -> Path:
    if not isinstance(usuario_id, str) or not _ID_VALIDO.match(usuario_id):
        raise ValueError(
            f"usuario_id no válido: {usuario_id!r}. Usa letras, números, guiones y guiones bajos (máximo 64)."
        )
    carpeta = raiz() / usuario_id
    if crear:
        carpeta.mkdir(parents=True, exist_ok=True)
    return carpeta


def _ruta(usuario_id: str, nombre: str, extension: str, crear: bool) -> Path:
    if not _NOMBRE_VALIDO.match(nombre) or ".." in nombre:
        raise ValueError(f"Nombre de archivo no válido: {nombre!r}.")
    return carpeta_usuario(usuario_id, crear) / f"{nombre}.{extension}"


def candado(usuario_id: str) -> threading.RLock:
    """Candado reentrante por usuario: `with almacenamiento.candado(uid): ...`."""
    carpeta_usuario(usuario_id)  # valida el id
    with _candados_guarda:
        if usuario_id not in _candados:
            _candados[usuario_id] = threading.RLock()
        return _candados[usuario_id]


def _serializar(objeto: Any) -> str:
    if isinstance(objeto, BaseModel):
        return objeto.model_dump_json(indent=2)
    return TypeAdapter(Any).dump_json(objeto, indent=2).decode("utf-8")


def escribir_texto_atomico(ruta: Path, texto: str) -> None:
    """Escribe en un temporal de la misma carpeta y lo mueve con `os.replace`."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporal = tempfile.mkstemp(dir=ruta.parent, prefix=f".{ruta.name}.", suffix=".tmp")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as f:
            f.write(texto)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporal, ruta)
    except BaseException:
        try:
            os.unlink(temporal)
        except OSError:
            pass
        raise


def guardar(usuario_id: str, nombre: str, objeto: Any) -> Path:
    """Guarda un modelo pydantic, dict o lista como `<nombre>.json` (dinero como cadena)."""
    ruta = _ruta(usuario_id, nombre, "json", crear=True)
    escribir_texto_atomico(ruta, _serializar(objeto))
    return ruta


def cargar(usuario_id: str, nombre: str, tipo: Any = None, defecto: Any = None) -> Any:
    """Lee `<nombre>.json`. Con `tipo` (modelo o `list[Modelo]`) valida y devuelve objetos.
    Si no existe, devuelve `defecto`."""
    ruta = _ruta(usuario_id, nombre, "json", crear=False)
    if not ruta.exists():
        return defecto
    texto = ruta.read_text(encoding="utf-8")
    if tipo is None:
        return json.loads(texto)
    return TypeAdapter(tipo).validate_json(texto)


def existe(usuario_id: str, nombre: str) -> bool:
    return _ruta(usuario_id, nombre, "json", crear=False).exists()


def borrar_usuario(usuario_id: str) -> None:
    carpeta = carpeta_usuario(usuario_id)
    with candado(usuario_id):
        if carpeta.exists():
            shutil.rmtree(carpeta)


def anadir_auditoria(usuario_id: str, registro: dict[str, Any]) -> dict[str, Any]:
    """Añade una línea a `auditoria.jsonl` con las cadenas enmascaradas y la marca de tiempo."""
    limpio = enmascarar_datos(json.loads(_serializar(registro)))
    limpio.setdefault("ts", datetime.now().isoformat(timespec="seconds"))
    ruta = _ruta(usuario_id, "auditoria", "jsonl", crear=True)
    linea = json.dumps(limpio, ensure_ascii=False) + "\n"
    with candado(usuario_id):
        with open(ruta, "a", encoding="utf-8", newline="\n") as f:
            f.write(linea)
            f.flush()
            os.fsync(f.fileno())
    return limpio


def leer_auditoria(usuario_id: str) -> list[dict[str, Any]]:
    ruta = _ruta(usuario_id, "auditoria", "jsonl", crear=False)
    if not ruta.exists():
        return []
    registros = []
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        if linea.strip():
            registros.append(json.loads(linea))
    return registros
