"""
Parámetros del motor con nombre (motor.md §2.3). Un dataclass por pieza, con sus valores por defecto,
y una única función de umbrales personales: `ajustar(params, perfil)`.

Sin perfil, `ajustar` devuelve el mismo objeto (arranque en frío idéntico; hay test de regresión).
La tabla de ajustes con perfil (ticket_tipico, umbral_relevante_eur...) llega en M9.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TypeVar

from ..plataforma.tipos import PerfilUsuario

Parametros = TypeVar("Parametros")


@dataclass(frozen=True)
class Series:
    PERIODOS_MESES: tuple[int, ...] = (1, 2, 3, 6, 12)   # 2: recibos bimestrales (agua)
    MIN_CARGOS_MENSUAL: int = 3
    MAX_CARGOS_POR_MES: float = 1.5                       # más: gasto variable, no recibo
    VARIACION_MAX: float = 0.25                           # desviación / media de los importes
    VARIACION_FIJO: float = 0.05
    DISPERSION_DIA_MAX: float = 3.0                       # desviación del día del mes (circular: 30 y 2 están cerca)
    MAX_HUECOS: int = 1                                   # recibos que pueden faltar (salto de 2 periodos)
    DIAS_TOLERANCIA_CARGO: int = 6                        # un cargo nuevo es de la serie si cae a ±6 días de su día
    MIN_CARGOS_TARJETA: int = 3                           # tarjeta (periodo < 6 meses): importe fijo y >= 3 cargos
    DIAS_ANUAL: tuple[int, int] = (330, 400)
    DIAS_COMERCIO_NUEVO: int = 180


@dataclass(frozen=True)
class GastoCompartido:
    IMPORTE_MIN_PAGO: Decimal = Decimal("30")
    CATEGORIAS_PAGO: tuple[str, ...] = ("restaurantes", "ocio", "supermercado", "compras", "transporte")
    VENTANA_REEMBOLSO: int = 7          # días tras el pago en los que cuenta un Bizum recibido
    TOL_CUOTA: Decimal = Decimal("0.50")  # todos los reembolsos a esta distancia de la mediana
    MIN_REEMBOLSOS: int = 2
    PERSONAS_MIN: int = 3
    PERSONAS_MAX: int = 12
    TOL_REPARTO_EUR: Decimal = Decimal("1")
    TOL_REPARTO_PCT: Decimal = Decimal("0.03")
    DIAS_ESPERA: int = 3                # sin línea base propia
    DIAS_ESPERA_MIN: int = 2
    DIAS_ESPERA_MAX: int = 5
    MIN_RETRASOS_P75: int = 3           # reembolsos previos necesarios para usar el p75 propio
    MIN_DIAS_DESDE_ULTIMO: int = 1      # no avisar el mismo día en que entra un Bizum
    MIN_COINCIDENCIAS: int = 2          # repartos previos con alguno de los que ya pagaron
    COINCIDENCIAS_FUERTES: int = 3
    CONFIANZA_BASE: float = 0.50
    CONFIANZA_MAX: float = 0.95


@dataclass(frozen=True)
class CargoDuplicado:
    IMPORTE_MIN_TARJETA: Decimal = Decimal("15")      # con perfil (M9): clamp(0,5 x ticket_tipico, 5, 30)
    IMPORTE_MIN_RECIBO: Decimal = Decimal("1")
    CANALES: tuple[str, ...] = ("tarjeta", "recibo")
    CATEGORIAS_EXCLUIDAS: tuple[str, ...] = ("transporte",)
    VENTANA_DIAS: int = 3                             # 0 <= B - A <= 3 días
    COMPRAS_FRECUENTES: int = 8                       # >= 8 compras en 30 días en el comercio...
    DIAS_FRECUENCIA: int = 30
    IMPORTE_FRECUENTE_MAX: Decimal = Decimal("50")    # ... con tarjeta y < 50 €: compra habitual (menú, café)
    SEMANAS_DEVOLUCION_RECIBO: int = 8                # SEPA básico: 8 semanas para devolver un recibo
    CONFIANZA_SERIE: float = 0.90
    CONFIANZA_RECIBO: float = 0.85
    CONFIANZA_TARJETA_MISMO_DIA: float = 0.70
    CONFIANZA_TARJETA_OTRO_DIA: float = 0.55


@dataclass(frozen=True)
class SubidaRecibo:
    SUBIDA_MIN_EUR: Decimal = Decimal("2")            # más de 2 € sobre lo habitual y sobre el último (o el máximo)
    PCT_MIN_FIJO: Decimal = Decimal("0.08")           # serie fija (variación <= 5 %): más del 8 %
    PCT_MIN_VARIABLE: Decimal = Decimal("0.25")       # serie variable (luz, agua): más del 25 %
    SUBIDA_MIN_ANUAL: Decimal = Decimal("12")         # subida x cargos al año; con perfil (M9): max(12, 0,10 x umbral)
    MIN_CARGOS_PREVIOS: int = 3
    MIN_CARGOS_PREVIOS_ANUAL: int = 2
    CONFIANZA_BASE: float = 0.60                      # + 0,10 por recibo previo más allá del tercero
    CONFIANZA_MAX: float = 0.90


@dataclass(frozen=True)
class Razonador:
    CONFIANZA_MIN: float = 0.5


DEFECTO: dict[str, object] = {
    "series": Series(),
    "gasto_compartido": GastoCompartido(),
    "cargo_duplicado": CargoDuplicado(),
    "subida_recibo": SubidaRecibo(),
    "razonador": Razonador(),
}


def ajustar(params: Parametros, perfil: PerfilUsuario | None) -> Parametros:
    """Única función de umbrales personales. Sin perfil, los mismos valores (el mismo objeto)."""
    if perfil is None:
        return params
    return params  # M9: tabla de motor.md §2.3 (ticket_tipico, umbral_relevante_eur, grupos...)


def ajustados(perfil: PerfilUsuario | None) -> dict[str, object]:
    """Todos los parámetros del motor ajustados al perfil (o los de defecto)."""
    return {nombre: ajustar(params, perfil) for nombre, params in DEFECTO.items()}
