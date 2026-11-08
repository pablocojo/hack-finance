"""
Datos de mercado: tipos de cambio (Frankfurter, sin clave) y cotizaciones (Alpha Vantage, opcional).

- convertir_divisa usa caché en disco y, sin conexión, los tipos de respaldo de
  backend/datos/tipos_respaldo.json (actualízalos con scripts/actualizar_tipos_respaldo.py).
- precio_accion solo se activa si hay ALPHA_VANTAGE_API_KEY (25 consultas al día gratis).
"""

from __future__ import annotations

import json
import re
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

from .. import config
from ..agente.registro import herramienta

CARPETA_DATOS = Path(__file__).resolve().parent.parent / "datos"
CACHE_DIVISAS = CARPETA_DATOS / "cache" / "divisas.json"
RESPALDO = CARPETA_DATOS / "tipos_respaldo.json"
VIGENCIA_ULTIMOS = 6 * 3600  # segundos que vale un tipo "latest" en caché
VIGENCIA_COTIZACION = 15 * 60
_cerrojo = threading.Lock()
_cotizaciones: dict[str, tuple[float, dict]] = {}


def obtener_json(url: str, timeout: float = 8.0) -> dict:
    """GET que devuelve JSON. Los tests lo sustituyen con monkeypatch."""
    peticion = urllib.request.Request(url, headers={"User-Agent": "agente-finanzas-hackathon/1.0"})
    with urllib.request.urlopen(peticion, timeout=timeout) as respuesta:  # noqa: S310 (URL fija)
        return json.loads(respuesta.read().decode("utf-8"))


def _leer_cache() -> dict:
    try:
        return json.loads(CACHE_DIVISAS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _guardar_cache(cache: dict) -> None:
    try:
        CACHE_DIVISAS.parent.mkdir(parents=True, exist_ok=True)
        CACHE_DIVISAS.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def _tipo_respaldo(origen: str, destino: str) -> tuple[float, str] | None:
    try:
        respaldo = json.loads(RESPALDO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    tipos = {**respaldo.get("rates", {}), respaldo.get("base", "EUR"): 1.0}
    if origen not in tipos or destino not in tipos:
        return None
    return tipos[destino] / tipos[origen], respaldo.get("date", "fecha desconocida")


def _codigo(texto: str) -> str:
    codigo = (texto or "").strip().upper()
    if not re.fullmatch(r"[A-Z]{3}", codigo):
        raise ValueError(f"Código de divisa no válido: {texto!r}. Usa códigos ISO de 3 letras como EUR o USD.")
    return codigo


@herramienta
def convertir_divisa(importe: float, origen: str, destino: str, fecha: str | None = None) -> dict:
    """Convierte un importe entre divisas con los tipos de referencia de bancos centrales (BCE incluido).

    Úsala para pagos en el extranjero, viajes o comparar precios. Los tipos son de referencia y pueden
    diferir de los que aplica el banco o la tarjeta (que suelen añadir comisión).

    Args:
        importe: Importe en la divisa de origen.
        origen: Código ISO de la divisa de origen, por ejemplo EUR.
        destino: Código ISO de la divisa de destino, por ejemplo USD.
        fecha: Fecha AAAA-MM-DD para un tipo histórico. Si no se indica, el último disponible.
    """
    origen, destino = _codigo(origen), _codigo(destino)
    if origen == destino:
        return {"importe_origen": importe, "importe_convertido": round(importe, 2), "tipo": 1.0,
                "origen": origen, "destino": destino, "fuente": "misma divisa"}
    if fecha and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", fecha):
        raise ValueError("La fecha debe tener formato AAAA-MM-DD.")
    clave = f"{fecha or 'latest'}:{origen}:{destino}"
    with _cerrojo:
        cache = _leer_cache()
    guardado = cache.get(clave)
    vigente = guardado and (fecha or time.time() - guardado["guardado"] < VIGENCIA_ULTIMOS)
    fuente = "Frankfurter (tipos de referencia de bancos centrales)"
    if vigente:
        tipo, dia = guardado["tipo"], guardado["fecha"]
    else:
        base = config.ajustes().frankfurter_url.rstrip("/")
        parametros = urllib.parse.urlencode({"from": origen, "to": destino})
        try:
            datos = obtener_json(f"{base}/{fecha or 'latest'}?{parametros}")
            tipo, dia = float(datos["rates"][destino]), datos.get("date", fecha)
            with _cerrojo:
                cache = _leer_cache()
                cache[clave] = {"tipo": tipo, "fecha": dia, "guardado": time.time()}
                _guardar_cache(cache)
        except Exception as error:  # sin red o divisa no soportada
            if guardado:
                tipo, dia = guardado["tipo"], guardado["fecha"]
                fuente += " (caché, sin conexión)"
            else:
                respaldo = _tipo_respaldo(origen, destino)
                if respaldo is None:
                    raise ValueError(f"No puedo obtener el tipo {origen}/{destino} ahora mismo ({error}).") from error
                tipo, dia = respaldo
                fuente = "tipos de respaldo guardados (sin conexión): pueden estar desactualizados"
    return {
        "importe_origen": importe,
        "importe_convertido": round(importe * tipo, 2),
        "tipo": round(tipo, 6),
        "origen": origen,
        "destino": destino,
        "fecha_tipo": dia,
        "fuente": fuente,
    }


def _alpha_vantage_activa() -> bool:
    return bool(config.ajustes().alpha_vantage_key)


@herramienta(activa=_alpha_vantage_activa)
def precio_accion(simbolo: str) -> dict:
    """Consulta la última cotización de una acción o ETF (precio, variación y fecha), con posible retraso.

    Úsala solo cuando el usuario pregunte por un valor concreto. Es información, no una recomendación:
    no digas si conviene comprar o vender.

    Args:
        simbolo: Símbolo bursátil, por ejemplo IBM, AAPL o SAN.MC.
    """
    simbolo = (simbolo or "").strip().upper()
    if not re.fullmatch(r"[A-Z0-9.\-]{1,15}", simbolo):
        raise ValueError("Símbolo no válido.")
    with _cerrojo:
        guardado = _cotizaciones.get(simbolo)
    if guardado and time.time() - guardado[0] < VIGENCIA_COTIZACION:
        return guardado[1]
    parametros = urllib.parse.urlencode({"function": "GLOBAL_QUOTE", "symbol": simbolo,
                                         "apikey": config.ajustes().alpha_vantage_key})
    datos = obtener_json(f"https://www.alphavantage.co/query?{parametros}")
    if "Note" in datos or "Information" in datos:
        raise ValueError("Se ha alcanzado el límite gratuito de Alpha Vantage (25 consultas al día). "
                         "Prueba más tarde.")
    cotizacion = datos.get("Global Quote") or {}
    if not cotizacion.get("05. price"):
        raise ValueError(f"No encuentro cotización para {simbolo}.")
    resultado = {
        "simbolo": cotizacion.get("01. symbol", simbolo),
        "precio": float(cotizacion["05. price"]),
        "variacion": float(cotizacion.get("09. change") or 0),
        "variacion_pct": cotizacion.get("10. change percent"),
        "dia_cotizacion": cotizacion.get("07. latest trading day"),
        "fuente": "Alpha Vantage (puede tener retraso)",
        "aviso": "Dato informativo; no es una recomendación de inversión.",
    }
    with _cerrojo:
        _cotizaciones[simbolo] = (time.time(), resultado)
    return resultado
