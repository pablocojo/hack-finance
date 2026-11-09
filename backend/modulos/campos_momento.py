"""Campos de `Momento.datos` por tipo (el `?` del contrato = opcional) y rutas permitidas del minilenguaje."""

from __future__ import annotations

# tipo -> {campo: opcional}
CAMPOS_DATOS: dict[str, dict[str, bool]] = {
    "cargo_duplicado": {
        "comercio": False, "importe": False, "fechas": False, "ids": False, "id_segundo": False,
        "dias_entre": False, "canal": False, "fecha_limite_devolucion": True,
    },
    "renovacion_proxima": {
        "comercio": False, "importe": False, "periodicidad": False, "fecha_prevista": False,
        "dias_hasta": False, "veces_cobrado": False,
    },
    "subida_recibo": {
        "comercio": False, "importe_actual": False, "importe_habitual": False, "subida_eur": False,
        "subida_pct": False, "serie_id": False,
    },
    "saldo_negativo_previsto": {
        "fecha_prevista": False, "saldo_minimo": False, "cargos_previstos": False,
        "importe_para_cubrir": False, "saldo_actual": True, "ingresos_previstos": True,
    },
    "posible_estafa": {
        "contraparte": False, "importe": False, "canal": False, "senales": False,
        "contraparte_nueva": False, "veces_lo_habitual": False,
    },
    "gasto_compartido": {
        "pago_id": False, "comercio": False, "importe_total": False, "fecha": False, "reembolsos": False,
        "personas_estimadas": False, "faltan": False, "importe_pendiente": False, "candidatos": False,
        "cuota": True,
    },
    "ingreso_extra": {"subtipo": False, "importe": False, "contraparte": False},
    "viaje_detectado": {
        "comercio": False, "importe": False, "fecha_viaje": True, "destino": True,
    },
    "prueba_gratuita": {
        "comercio": False, "fecha_alta": False, "dias_prueba": False, "fecha_primer_cobro": False,
        "dias_hasta": False, "importe_previsto": True, "fuente": False, "fuente_duracion": False,
        "verificacion_id": True,
    },
}

# Campos de cada elemento de las listas que admiten `repetir_por` / `item.<campo>`.
CAMPOS_ITEM: dict[str, dict[str, set[str]]] = {
    "gasto_compartido": {"candidatos": {"contraparte", "importe"}},
}

RUTAS_MOMENTO = ("tipo", "confianza", "impacto_eur", "impacto_relativo", "fecha")
RUTAS_MODELO = ("modulos_activos", "consentimientos", "preferencias", "amigos", "hechos_aprendidos")
RUTAS_PERFIL = (
    "umbral_relevante_eur", "ticket_tipico", "ingreso_mensual_tipico", "dia_cobro_nomina",
    "comercios_habituales", "suscripciones_activas",
)
# Fuera: perfil.resumen_vida, perfil.grupos, momento.contexto_personal, movimientos, concepto, nota.
