"""
Esquema del módulo (modulos.md §2). Todo con `extra="forbid"`: un campo desconocido invalida el módulo.
`validar_modulo` hace las comprobaciones que el esquema solo no puede (rutas, plantillas, acciones).
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..plataforma.tipos import AccionId, EstadoModulo, TipoMomento, Urgencia
from . import campos_momento as cm
from . import condiciones, plantillas

MAX_ACCIONES = 3
MAX_REPETIR = 6
LISTA_NEGRA = re.compile(
    r"\b(seguros?|pr[eé]stamos?|hipotecas?|inversi[oó]n|inversiones|fondos? de inversi[oó]n|criptomonedas?|"
    r"tarjeta de cr[eé]dito|cr[eé]dito|broker)\b", re.IGNORECASE)
URL = re.compile(r"(https?://|www\.|\b\w+\.(com|es|net|org|io)\b)", re.IGNORECASE)
PERSONALES = re.compile(r"\b[A-Z]{2}\d{2}[ ]?\d{4}|\b\d{8}[A-Z]\b|\b[6-9]\d{8}\b|\d{9,}")


class _E(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AlternativaSpec(_E):
    falta: str
    titulo: str | None = None
    mensaje_notificacion: str | None = None
    contexto_llamada: str | None = None


class PropuestaSpec(_E):
    titulo: str = Field(min_length=1, max_length=120)
    mensaje_notificacion: str = Field(min_length=1, max_length=300)
    contexto_llamada: str = Field(min_length=1, max_length=900)
    urgencia: Urgencia = "media"
    valor_estimado_eur: str | None = None
    alternativa: AlternativaSpec | None = None


class LimitesSpec(_E):
    importe_max: str | int | float | None = None
    contrapartes: list[str] | None = None


class AccionSpec(_E):
    accion_id: AccionId
    parametros: dict[str, Any] = Field(default_factory=dict)
    repetir_por: str | None = None
    limites: LimitesSpec = Field(default_factory=LimitesSpec)


class ModuloSpec(_E):
    id: str
    version: int = Field(ge=1)
    nombre: str = Field(min_length=1, max_length=80)
    descripcion: str = ""
    estado: EstadoModulo = "borrador"
    origen: Literal["catalogo", "lenguaje_natural"] = "catalogo"
    escucha: list[TipoMomento] = Field(min_length=1, max_length=3)
    cuando: str | None = None
    propuesta: PropuestaSpec
    acciones: list[AccionSpec] = Field(min_length=1)
    opcional: bool = False
    ficha_informacion: str | None = None
    aprobado_por: str | None = None
    aprobado_en: datetime | None = None

    @field_validator("id")
    @classmethod
    def _id(cls, v: str) -> str:
        if not re.fullmatch(r"[a-z][a-z0-9_]{2,40}", v):
            raise ValueError("`id`: minúsculas, números y _, de 3 a 41 caracteres, empezando por letra.")
        return v

    @field_validator("acciones")
    @classmethod
    def _max_acciones(cls, v: list) -> list:
        if len(v) > MAX_ACCIONES:
            raise ValueError(f"Un módulo ofrece como mucho {MAX_ACCIONES} acciones (tiene {len(v)}); elige las que encajan.")
        return v

    @model_validator(mode="after")
    def _completo(self) -> "ModuloSpec":
        for e in validar_modulo(self):
            raise ValueError(e)
        return self


def _textos(spec: ModuloSpec) -> list[str]:
    p = spec.propuesta
    t = [p.titulo, p.mensaje_notificacion, p.contexto_llamada, spec.nombre, spec.descripcion]
    if p.alternativa:
        t += [x for x in (p.alternativa.titulo, p.alternativa.mensaje_notificacion, p.alternativa.contexto_llamada) if x]
    return t


def validar_modulo(spec: ModuloSpec) -> list[str]:
    """Lista de errores (vacía = válido). No lanza."""
    from ..acciones.registro import REGISTRO  # import tardío: evita el ciclo modulos <-> acciones

    errores: list[str] = []
    tipos = list(spec.escucha)
    p = spec.propuesta

    def campo_ok(ruta: str) -> bool:
        partes = ruta.split(".")
        return (len(partes) == 2 and partes[0] == "datos"
                and all(partes[1] in cm.CAMPOS_DATOS.get(t, {}) for t in tipos))

    # condición y valor estimado
    for nombre, expr in (("cuando", spec.cuando), ("valor_estimado_eur", p.valor_estimado_eur)):
        if expr is None:
            continue
        try:
            arbol = condiciones.compilar(expr)
        except condiciones.ErrorCondicion as e:
            errores.append(f"`{nombre}`: {e}")
            continue
        for ruta in condiciones.rutas_usadas(arbol):
            if ruta.startswith("momento.datos."):
                campo = ruta.split(".")[2]
                if not all(campo in cm.CAMPOS_DATOS.get(t, {}) for t in tipos):
                    errores.append(f"`{nombre}`: el campo {campo!r} no existe en {', '.join(tipos)}.")

    # alternativa
    cubiertos: frozenset[str] = frozenset()
    if p.alternativa:
        if not campo_ok(p.alternativa.falta) or not all(
                cm.CAMPOS_DATOS[t].get(p.alternativa.falta.split(".")[1]) for t in tipos):
            errores.append("`alternativa.falta` debe ser un campo opcional (`datos.<campo>`) de los tipos escuchados.")
        else:
            cubiertos = frozenset({p.alternativa.falta})
    # plantillas principales: el campo opcional cubierto por `alternativa` solo vale si las plantillas
    # alternativas redefinen ese texto
    alt = p.alternativa
    principales = {"titulo": p.titulo, "mensaje_notificacion": p.mensaje_notificacion, "contexto_llamada": p.contexto_llamada}
    for nombre, texto in principales.items():
        try:
            ok = cubiertos if (alt and getattr(alt, nombre)) else frozenset()
            plantillas.validar(texto, tipos, opcionales_ok=ok)
        except plantillas.ErrorPlantilla as e:
            errores.append(f"`propuesta.{nombre}`: {e}")
    if alt:
        for nombre in ("titulo", "mensaje_notificacion", "contexto_llamada"):
            texto = getattr(alt, nombre)
            if texto:
                try:
                    plantillas.validar(texto, tipos)
                except plantillas.ErrorPlantilla as e:
                    errores.append(f"`alternativa.{nombre}`: {e}")

    # acciones
    for i, a in enumerate(spec.acciones):
        pref = f"`acciones[{i}]` ({a.accion_id})"
        defn = REGISTRO.get(a.accion_id)
        if defn is None:
            errores.append(f"{pref}: acción fuera de la lista cerrada.")
            continue
        con_item = a.repetir_por is not None
        if con_item:
            if not campo_ok(a.repetir_por) or not all(
                    a.repetir_por.split(".")[1] in cm.CAMPOS_ITEM.get(t, {}) for t in tipos):
                errores.append(f"{pref}: `repetir_por` {a.repetir_por!r} no es una lista repetible de los tipos escuchados.")
                con_item = False
        esperados = set(defn.modelo.model_fields)
        if set(a.parametros) != esperados:
            errores.append(f"{pref}: los parámetros deben ser exactamente {sorted(esperados)}; hay {sorted(a.parametros)}.")
        valores = list(a.parametros.values()) + [a.limites.importe_max] + list(a.limites.contrapartes or [])
        for v in valores:
            if isinstance(v, str) and "{" in v:
                try:
                    plantillas.validar(v, tipos, con_item=con_item or a.repetir_por is not None)
                    if "item." in v and a.repetir_por:
                        campos_item = set.intersection(*(cm.CAMPOS_ITEM.get(t, {}).get(a.repetir_por.split(".")[1], set()) for t in tipos))
                        for r, _ in plantillas.referencias(v):
                            if r.startswith("item.") and r[5:] not in campos_item:
                                errores.append(f"{pref}: {r} no existe en los elementos de {a.repetir_por}.")
                except plantillas.ErrorPlantilla as e:
                    errores.append(f"{pref}: {e}")
        if "importe_max" in defn.limites and a.limites.importe_max is None and a.accion_id in ("pedir_bizum", "mover_dinero"):
            errores.append(f"{pref}: lleva `limites.importe_max`.")
        if a.accion_id == "pedir_bizum" and not a.limites.contrapartes:
            errores.append(f"{pref}: lleva `limites.contrapartes`.")
        if a.limites.importe_max is not None and "importe_max" not in defn.limites:
            errores.append(f"{pref}: no admite `importe_max`.")
        if a.limites.contrapartes is not None and "contrapartes" not in defn.limites:
            errores.append(f"{pref}: no admite `contrapartes`.")

    # contenido
    textos = _textos(spec) + [v for a in spec.acciones for v in a.parametros.values() if isinstance(v, str)]
    for t in textos:
        if URL.search(t):
            errores.append(f"Ningún texto lleva URL: {t[:40]!r}.")
        if PERSONALES.search(t):
            errores.append(f"Ningún texto lleva datos personales (IBAN, teléfono, DNI): {t[:40]!r}.")
        if LISTA_NEGRA.search(t) and not spec.ficha_informacion:
            errores.append(f"Un producto concreto solo se ofrece con `ficha_informacion`: {t[:40]!r}.")
    return errores


def advertencias(spec: ModuloSpec) -> list[str]:
    avisos = []
    if len(spec.acciones) < 2:
        avisos.append("Se recomiendan 2 o 3 acciones que encajen con el momento.")
    return avisos
