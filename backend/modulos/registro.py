"""Carga de módulos: `catalogo/*.yaml` (del repositorio) y `datos_usuario/_modulos/*.yaml` (aprobados por el banco)."""

from __future__ import annotations

from pathlib import Path

import yaml

from ..plataforma import almacenamiento
from .esquema import ModuloSpec

CATALOGO = Path(__file__).parent / "catalogo"
_cache_catalogo: dict[str, ModuloSpec] | None = None


class ErrorModulo(ValueError):
    pass


def leer_yaml(texto: str) -> ModuloSpec:
    try:
        datos = yaml.safe_load(texto)  # safe_load: sin objetos ni etiquetas de Python
    except yaml.YAMLError as e:
        raise ErrorModulo(f"YAML no válido: {e}") from e
    if not isinstance(datos, dict):
        raise ErrorModulo("El módulo debe ser un objeto YAML.")
    return ModuloSpec.model_validate(datos)


def catalogo() -> dict[str, ModuloSpec]:
    global _cache_catalogo
    if _cache_catalogo is None:
        cargados: dict[str, ModuloSpec] = {}
        for f in sorted(CATALOGO.glob("*.yaml")):
            try:
                spec = leer_yaml(f.read_text(encoding="utf-8"))
            except Exception as e:
                raise ErrorModulo(f"Catálogo inválido en {f.name}: {e}") from e
            if spec.id in cargados:
                raise ErrorModulo(f"Módulo duplicado en el catálogo: {spec.id}")
            cargados[spec.id] = spec
        _cache_catalogo = cargados
    return dict(_cache_catalogo)


def carpeta_aprobados() -> Path:
    return almacenamiento.raiz() / "_modulos"


def aprobados() -> dict[str, ModuloSpec]:
    salida: dict[str, ModuloSpec] = {}
    for f in sorted(carpeta_aprobados().glob("*.yaml")):
        try:
            spec = leer_yaml(f.read_text(encoding="utf-8"))
        except Exception:
            continue  # un YAML estropeado no tumba al resto
        salida[spec.id] = spec
    return salida


def todos() -> dict[str, ModuloSpec]:
    return {**catalogo(), **aprobados()}


def obtener(modulo_id: str) -> ModuloSpec | None:
    return todos().get(modulo_id)


def guardar_aprobado(spec: ModuloSpec) -> Path:
    ruta = carpeta_aprobados() / f"{spec.id}.yaml"
    almacenamiento.escribir_texto_atomico(
        ruta, yaml.safe_dump(spec.model_dump(mode="json", exclude_none=True), allow_unicode=True, sort_keys=False))
    return ruta
