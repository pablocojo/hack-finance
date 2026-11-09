"""
Normalización de un movimiento (motor.md §2.1). Reglas puras, sin estado y sin Claude.

- `canal` y `tipo_operacion` se deducen del concepto si el banco no los trae.
- `comercio_normalizado`: mayúsculas sin tildes, sin prefijos, sufijos de tarjeta, dominios ni ciudad.
  Pasarelas (`PAYPAL *X` -> `X`) y descriptores de TPV de autónomos (`SUMUP *JUAN PEREZ`).
- `contraparte_normalizada` (Bizum y transferencias): `clave_contraparte`, que reutiliza la personalización.
- `categoria`: la del movimiento o las reglas del kit (más unas pocas del motor).

Los conceptos y las notas son datos: aquí solo se comparan con expresiones regulares.
"""

from __future__ import annotations

import re

from ..datos.categorias import categorizar_por_reglas, normalizar as normalizar_texto
from ..plataforma.tipos import Movimiento, MovimientoEnriquecido

# --- Canal y tipo de operación ---------------------------------------------------------------

_CANALES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bBIZUM\b"), "bizum"),
    (re.compile(r"\b(RECIBO|ADEUDO|DOMICILIACION)\b"), "recibo"),
    (re.compile(r"\b(COMPRA TARJETA|COMPRA ONLINE|PAGO TARJETA|VERIFICACION TARJETA|COMPRA TPV)\b"), "tarjeta"),
    (re.compile(r"\b(TRANSFERENCIA|TRASPASO|NOMINA)\b"), "transferencia"),
    (re.compile(r"\b(CAJERO|REINTEGRO|RETIRADA)\b"), "cajero"),
    (re.compile(r"\b(VERIFICACION|AUTORIZACION|PREAUTORIZ\w*|COMPRA)\b"), "tarjeta"),
]
_VERIFICACION = re.compile(r"VERIFICACION|AUTORIZACION|PREAUTORIZ")
_DEVOLUCION = re.compile(r"DEVOLUCION|ANULACION|ABONO|REEMBOLSO COMPRA")
IMPORTE_MAX_VERIFICACION = 1  # euros: una autorización de 1 € o menos es una verificación


def deducir_canal(concepto: str) -> str | None:
    texto = normalizar_texto(concepto)
    for patron, canal in _CANALES:
        if patron.search(texto):
            return canal
    return None


def deducir_tipo_operacion(concepto: str, importe) -> str:
    texto = normalizar_texto(concepto)
    if importe == 0 or (_VERIFICACION.search(texto) and abs(importe) <= IMPORTE_MAX_VERIFICACION):
        return "verificacion"
    if importe > 0 and _DEVOLUCION.search(texto):
        return "devolucion"
    return "cargo"


# --- Comercio --------------------------------------------------------------------------------

_PREFIJOS = re.compile(
    r"^(COMPRA TARJETA|COMPRA ONLINE|COMPRA TPV|COMPRA|PAGO TARJETA|PAGO|RECIBO|ADEUDO|CARGO|"
    r"VERIFICACION TARJETA|VERIFICACION|PREAUTORIZACION|AUTORIZACION|DEVOLUCION COMPRA|DEVOLUCION|"
    r"ANULACION|ABONO)\s+"
)
_SUFIJO_TARJETA = re.compile(r"(\s*\*\s*\d{3,}|\s+X{2,}\d+|\s+\d{4,})$")
_DOMINIO = re.compile(r"\.(COM|ES|NET|EU|ORG|CO\.UK)\b")
_CIUDADES = {
    "MADRID", "BARCELONA", "VALENCIA", "SEVILLA", "BILBAO", "MALAGA", "ZARAGOZA", "MURCIA", "PALMA",
    "ALICANTE", "CORDOBA", "VALLADOLID", "VIGO", "GIJON", "GRANADA", "SALAMANCA", "OVIEDO", "PAMPLONA",
    "SANTANDER", "TOLEDO", "CADIZ", "HUELVA", "BURGOS", "LEON", "LOGRONO", "VITORIA", "DONOSTIA",
}
_ALIAS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"^(AMZN MKTP|AMZN|AMAZON MKTPLACE|AMAZON MARKETPLACE|AMAZON EU)\b.*"), "AMAZON"),
]
_PASARELA = re.compile(r"^PAYPAL\s*\*\s*(.+)$")
_PASARELA_OPACA: list[tuple[re.Pattern, str]] = [
    (re.compile(r"^(APPLE\.COM|ITUNES|APPLE SERVICES)"), "APPLE"),
    (re.compile(r"^(GOOGLE\s*\*|GOOGLE PLAY|GOOGLE SERVICES)"), "GOOGLE"),
]
PASARELAS_OPACAS = frozenset(nombre for _, nombre in _PASARELA_OPACA)
_TPV_AUTONOMO = re.compile(r"^(SUMUP|ZETTLE|IZETTLE|SQ|IZ)\s*\*\s*(.+)$")
_PALABRAS = re.compile(r"^[A-Z]+( [A-Z]+){1,2}$")


def _limpiar_prefijos(texto: str) -> str:
    anterior = None
    while anterior != texto:
        anterior = texto
        texto = _PREFIJOS.sub("", texto).strip()
    return texto


def _limpiar(texto: str) -> str:
    texto = _SUFIJO_TARJETA.sub("", _limpiar_prefijos(texto)).strip()
    texto = _DOMINIO.sub("", texto).strip()
    palabras = texto.split(" ")
    if len(palabras) > 1 and palabras[-1] in _CIUDADES:
        texto = " ".join(palabras[:-1])
    for patron, alias in _ALIAS:
        if patron.match(texto):
            return alias
    return texto.strip(" *-.,/")


def _es_marca_conocida(nombre: str) -> bool:
    try:
        from .conocimiento import info_en_cache

        return info_en_cache(nombre) is not None
    except Exception:  # el catálogo nunca rompe la normalización
        return False


def normalizar_comercio(comercio: str | None, concepto: str) -> tuple[str | None, list[str]]:
    """(`comercio_normalizado`, etiquetas `pasarela` / `posible_persona`)."""
    texto = re.sub(r"\s*\*\s*", " *", normalizar_texto(comercio or concepto or ""))   # «PAYPAL*X» -> «PAYPAL *X»
    sin_prefijo = _limpiar_prefijos(texto)
    for patron, nombre in _PASARELA_OPACA:
        if patron.match(sin_prefijo):
            return nombre, ["pasarela"]
    pasarela = _PASARELA.match(sin_prefijo)
    if pasarela:
        nombre = _limpiar(pasarela.group(1).strip())
        return (nombre or "PAYPAL"), ["pasarela"]
    tpv = _TPV_AUTONOMO.match(sin_prefijo)
    if tpv:
        resto = _SUFIJO_TARJETA.sub("", tpv.group(2)).strip()
        if _PALABRAS.match(resto) and not _es_marca_conocida(resto):
            return f"{tpv.group(1)} *{resto}", ["posible_persona"]
        return _limpiar(resto) or None, []
    nombre = _limpiar(sin_prefijo)
    return (nombre or None), []


# --- Contraparte -----------------------------------------------------------------------------

_PARTICULAS = {"DE", "DEL", "LA", "LAS", "LOS", "Y", "DA", "DO", "VAN", "VON", "I"}
_CONTRAPARTE_EN_CONCEPTO = re.compile(r"\b(?:BIZUM|TRANSFERENCIA)\s+(?:RECIBID[OA]|ENVIAD[OA]|EMITIDA)\s+(?:DE|A)\s+(.+)$")


def clave_contraparte(nombre: str | None) -> str | None:
    """Nombre + inicial del primer apellido: «Laura Martínez García» -> `LAURA M`. La usa también `perfilar`."""
    texto = re.sub(r"[^A-Z ]", " ", normalizar_texto(nombre or ""))
    palabras = [p for p in texto.split() if p]
    if not palabras:
        return None
    resto = [p for p in palabras[1:] if p not in _PARTICULAS]
    return f"{palabras[0]} {resto[0][0]}" if resto else palabras[0]


def _contraparte(m: Movimiento, canal: str | None) -> str | None:
    if canal not in ("bizum", "transferencia"):
        return None
    if m.contraparte:
        return clave_contraparte(m.contraparte)
    encontrada = _CONTRAPARTE_EN_CONCEPTO.search(normalizar_texto(m.concepto))
    return clave_contraparte(encontrada.group(1)) if encontrada else None


# --- Categoría -------------------------------------------------------------------------------

_REGLAS_MOTOR: list[tuple[re.Pattern, str]] = [
    (re.compile(r"TASCA|ASADOR|MESON|TRATTORIA|BRASERIA|MARISQUERIA|TAPAS|VINOTECA|TABERNA|PIZZERIA"), "restaurantes"),
]


def categoria(m: Movimiento, comercio: str | None) -> str | None:
    if m.categoria:
        return m.categoria
    texto = f"{m.concepto} {comercio or ''}"
    encontrada = categorizar_por_reglas(texto, float(m.importe))
    if encontrada:
        return encontrada
    normal = normalizar_texto(texto)
    for patron, nombre in _REGLAS_MOTOR:
        if patron.search(normal):
            return nombre
    return None


# --- Movimiento ------------------------------------------------------------------------------

def normalizar(m: Movimiento) -> MovimientoEnriquecido:
    """Pura: un `Movimiento` -> `MovimientoEnriquecido` sin series (las pone `enriquecer`)."""
    canal = m.canal or deducir_canal(m.concepto)
    tipo = m.tipo_operacion or deducir_tipo_operacion(m.concepto, m.importe)
    etiquetas: list[str] = []
    comercio = None
    if canal != "bizum":
        comercio, etiquetas = normalizar_comercio(m.comercio, m.concepto)
    if tipo == "verificacion":
        etiquetas.append("verificacion")
    datos = m.model_dump()
    datos.update(canal=canal, tipo_operacion=tipo, categoria=categoria(m, comercio))
    return MovimientoEnriquecido(
        **datos,
        comercio_normalizado=comercio,
        contraparte_normalizada=_contraparte(m, canal),
        etiquetas=etiquetas,
    )
