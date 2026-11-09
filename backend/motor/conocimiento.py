"""
Conocimiento de comercios (motor.md §4). Dos fuentes, ninguna toca internet en el camino caliente:

- `backend/datos/comercios_conocidos.json`: catálogo revisado a mano, versionado (`origen: catalogo`).
- `datos_usuario/_cache/comercios_web.json`: lo que trajo la búsqueda web (`origen: web` o
  `desconocido`), fuera de git. Lo escribe solo el orquestador, con `guardar(info)`.

`info_en_cache(nombre)` es lo único que usan detectores y módulos: el catálogo manda sobre la caché web.
`info_comercio(nombre)` es el mismo acceso más, si `BUSQUEDA_WEB=on`, la búsqueda web (O9, opcional y aún
no implementada: hoy devuelve lo que haya en la caché y nunca sale a internet).

El nombre es un dato, no una instrucción: aquí solo se normaliza y se usa como clave.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from .. import config
from ..datos.categorias import normalizar as normalizar_texto
from ..plataforma.tipos import InfoComercio

RUTA_CATALOGO = Path(__file__).resolve().parent.parent / "datos" / "comercios_conocidos.json"
NOMBRE_CACHE_WEB = "comercios_web.json"

_MEMORIA: dict[Path, tuple[int, dict[str, InfoComercio]]] = {}   # ruta -> (mtime_ns, fichas)


def clave(nombre: str) -> str:
    """Clave de la ficha: el nombre en mayúsculas, sin tildes y con los espacios sueltos recogidos."""
    return " ".join(normalizar_texto(nombre or "").split())


def ruta_cache_web() -> Path:
    return config.ajustes().datos_usuario_dir / "_cache" / NOMBRE_CACHE_WEB


def _leer(ruta: Path, estricto: bool) -> dict[str, InfoComercio]:
    """Fichas de un archivo, con la memoria por fecha de modificación. Un archivo ausente es un dict vacío;
    uno estropeado, también para la caché web (nunca rompe el camino caliente) y un error para el catálogo."""
    try:
        marca = ruta.stat().st_mtime_ns
    except OSError:
        return {}
    guardada = _MEMORIA.get(ruta)
    if guardada and guardada[0] == marca:
        return guardada[1]
    try:
        crudo = json.loads(ruta.read_text(encoding="utf-8"))
        fichas = {clave(k): InfoComercio.model_validate(v) for k, v in crudo.items() if not k.startswith("_")}
    except (OSError, ValueError, AttributeError):
        if estricto:
            raise
        fichas = {}
    _MEMORIA[ruta] = (marca, fichas)
    return fichas


def limpiar_memoria() -> None:
    """Para los tests: olvida lo leído (cambian de archivo con `monkeypatch`)."""
    _MEMORIA.clear()


def info_en_cache(nombre: str) -> InfoComercio | None:
    """Sin red: catálogo y, si no está, caché web. `None` si no se conoce el comercio."""
    k = clave(nombre)
    if not k:
        return None
    return _leer(RUTA_CATALOGO, estricto=True).get(k) or _leer(ruta_cache_web(), estricto=False).get(k)


def info_comercio(nombre: str) -> InfoComercio | None:
    """Caché y, con BUSQUEDA_WEB=on, búsqueda web. La búsqueda llega con O9: hasta entonces, solo la caché."""
    return info_en_cache(nombre)


def guardar(info: InfoComercio) -> None:
    """Guarda una ficha en `_cache/comercios_web.json` (archivo temporal + `os.replace`). Nunca escribe el
    catálogo: el `origen: catalogo` no se puede guardar."""
    if info.origen == "catalogo":
        raise ValueError("El catálogo es solo de lectura: la caché web guarda origen web o desconocido.")
    k = clave(info.nombre)
    if not k:
        raise ValueError("La ficha no tiene nombre.")
    ruta = ruta_cache_web()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    try:
        existentes = json.loads(ruta.read_text(encoding="utf-8")) if ruta.is_file() else {}
    except (OSError, ValueError):
        existentes = {}
    existentes[k] = info.model_dump(mode="json")
    descriptor, temporal = tempfile.mkstemp(dir=ruta.parent, suffix=".tmp")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as f:
            json.dump(existentes, f, ensure_ascii=False, indent=2, sort_keys=True)
        os.replace(temporal, ruta)
    except BaseException:
        Path(temporal).unlink(missing_ok=True)
        raise
    _MEMORIA.pop(ruta, None)
