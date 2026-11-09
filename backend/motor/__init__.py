"""
Motor de momentos (motor.md). Firmas definitivas de docs/ARQUITECTURA.md §3.2.

En línea: `procesar` añade `nuevos` al historial y cada detector ve solo `fecha <= hoy`.
normalizar -> enriquecer (series, líneas base) -> parámetros (perfil) -> detectores -> razonador.
"""

from __future__ import annotations

import threading
from datetime import date
from typing import Literal

from ..plataforma.tipos import Momento, Movimiento, MovimientoEnriquecido, PerfilUsuario
from . import conocimiento, parametros, razonador
from .detectores import REGISTRO
from .detectores.base import Contexto
from .enriquecer import enriquecer as _enriquecer
from .enriquecer import enriquecer_normalizados, lineas_base
from .estado import EstadoMotor
from .normalizar import normalizar_comercio

_ESTADOS: dict[str, EstadoMotor] = {}
_CANDADO = threading.RLock()


def _comprobar_pasado(movimientos: list[Movimiento], hoy: date) -> None:
    futuros = [m.id for m in movimientos if m.fecha > hoy]
    if futuros:
        raise ValueError(f"Movimientos con fecha posterior a hoy ({hoy.isoformat()}): {futuros[:5]}")


def _estado(usuario_id: str) -> EstadoMotor:
    if usuario_id not in _ESTADOS:
        _ESTADOS[usuario_id] = EstadoMotor(usuario_id=usuario_id)
    return _ESTADOS[usuario_id]


def procesar(
    usuario_id: str, nuevos: list[Movimiento], hoy: date, perfil: PerfilUsuario | None = None
) -> list[Momento]:
    """Detecta los momentos nuevos de `hoy`. Error si algún movimiento tiene fecha > hoy.
    Idempotente: reprocesar el mismo día no repite momentos ni duplica movimientos."""
    _comprobar_pasado(nuevos, hoy)
    with _CANDADO:
        estado = _estado(usuario_id)
        estado.agregar(nuevos)
        params = parametros.ajustados(perfil)
        historial, series = enriquecer_normalizados(estado.normalizados_hasta(hoy), params["series"])
        ids_nuevos = {m.id for m in nuevos}
        ctx = Contexto(
            hoy=hoy,
            historial=historial,
            nuevos=[m for m in historial if m.id in ids_nuevos],
            series=series,
            lineas_base=lineas_base(historial, hoy, params["gasto_compartido"]),
            perfil=perfil,
            params=params,
            conocimiento=conocimiento.info_en_cache,
            pruebas=tuple(dict(p) for p in estado.pruebas),
        )
        hallazgos = [h for detector in REGISTRO.values() for h in detector.detectar(ctx)]
        fechas = {m.id: m.fecha for m in historial}
        momentos = razonador.razonar(usuario_id, hallazgos, estado.claves_emitidas, hoy, fechas,
                                     params["razonador"], perfil)
        estado.ultimo_hoy = max(estado.ultimo_hoy or hoy, hoy)
        return momentos


def enriquecer(movimientos: list[Movimiento]) -> list[MovimientoEnriquecido]:
    """Pura: normaliza y enriquece (series, `serie_id`, etiquetas). La usa `perfilar`."""
    return _enriquecer(movimientos)


def cargar_historial(usuario_id: str, historial: list[Movimiento], hoy: date) -> None:
    """Al activar: guarda el historial (de él salen series y líneas base) sin emitir momentos."""
    _comprobar_pasado(historial, hoy)
    with _CANDADO:
        estado = _estado(usuario_id)
        estado.agregar(historial)
        estado.ultimo_hoy = max(estado.ultimo_hoy or hoy, hoy)


def exportar_estado(usuario_id: str) -> dict:
    """JSON puro (dinero y fechas como cadena). `{}` si el usuario no tiene estado."""
    with _CANDADO:
        estado = _ESTADOS.get(usuario_id)
        return estado.a_dict() if estado else {}


def importar_estado(usuario_id: str, estado: dict) -> None:
    """Sustituye el estado del usuario. Con `{}` lo deja vacío."""
    with _CANDADO:
        if not estado:
            _ESTADOS.pop(usuario_id, None)
        else:
            _ESTADOS[usuario_id] = EstadoMotor.desde_dict(usuario_id, estado)


def reiniciar(usuario_id: str) -> None:
    with _CANDADO:
        _ESTADOS.pop(usuario_id, None)


def _clave_comercio(comercio: str) -> str:
    return normalizar_comercio(comercio, comercio)[0] or comercio.strip().upper()


def registrar_prueba(usuario_id: str, comercio: str, fecha_alta: date, dias: int | None, hoy: date) -> None:
    """El cliente dice que ha empezado una prueba (fuente `usuario`). El aviso llega con M8."""
    if fecha_alta > hoy:
        raise ValueError("La fecha de alta de la prueba no puede ser posterior a hoy.")
    nombre = _clave_comercio(comercio)
    with _CANDADO:
        estado = _estado(usuario_id)
        abierta = next((p for p in estado.pruebas if p["comercio"] == nombre and p["estado"] == "abierta"), None)
        if abierta:
            abierta.update(dias=dias if dias is not None else abierta.get("dias"), fuente="usuario")
            return
        estado.pruebas.append({
            "comercio": nombre, "fecha_alta": fecha_alta.isoformat(), "dias": dias, "fuente": "usuario",
            "estado": "abierta", "registrada": hoy.isoformat(), "cerrada": None, "verificacion_id": None,
        })


def cerrar_prueba(
    usuario_id: str,
    comercio: str,
    motivo: Literal["cancelada", "cobrada", "caducada", "baja_guiada"],
    hoy: date,
) -> None:
    """Cierra la última prueba abierta (o en baja guiada) de ese comercio. Sin prueba, no hace nada."""
    nombre = _clave_comercio(comercio)
    with _CANDADO:
        estado = _estado(usuario_id)
        for prueba in reversed(estado.pruebas):
            if prueba["comercio"] == nombre and prueba["estado"] in ("abierta", "baja_guiada"):
                prueba.update(estado=motivo, cerrada=hoy.isoformat())
                return


def comercios_pendientes(usuario_id: str) -> list[str]:
    """Comercios que el orquestador debe buscar (los llenará `prueba_gratuita`, M7)."""
    with _CANDADO:
        estado = _ESTADOS.get(usuario_id)
        return list(estado.comercios_pendientes) if estado else []
