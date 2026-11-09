"""Banco simulado: estado en `datos_usuario/<usuario>/banco.json` (vía almacenamiento). Todo es simulado."""

from __future__ import annotations

from datetime import date

from ..plataforma import almacenamiento


def estado_inicial() -> dict:
    return {
        "cuentas": {"corriente": "1500.00", "ahorro": "3000.00"},
        "bloqueos": [], "solicitudes_bizum": [], "reclamaciones": [], "bajas": [], "recordatorios": [],
        "sin_bizum": [], "recibos_domiciliados": [], "canal_movimientos": {},
        "ejecuciones": {},   # clave idempotente (propuesta|accion|hash) -> resultado
        "resultados": {},    # resultado_id -> {accion_id, params, efecto, deshecho}
    }


def cargar(usuario_id: str) -> dict:
    est = almacenamiento.cargar(usuario_id, "banco", defecto=None) or {}
    base = estado_inicial()
    base.update(est)
    return base


def guardar(usuario_id: str, estado: dict) -> None:
    almacenamiento.guardar(usuario_id, "banco", estado)


def fecha_simulada(usuario_id: str) -> date:
    """Fecha del reloj simulado del usuario (`reloj.json`); si no hay, la del sistema."""
    try:
        r = almacenamiento.cargar(usuario_id, "reloj", defecto=None)
        if isinstance(r, dict) and r.get("hoy"):
            return date.fromisoformat(str(r["hoy"])[:10])
        if isinstance(r, str):
            return date.fromisoformat(r[:10])
    except (ValueError, TypeError):
        pass
    return date.today()
