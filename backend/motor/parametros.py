"""
Parámetros del motor con nombre (motor.md §2.3). Un dataclass por pieza, con sus valores por defecto,
y una única función de umbrales personales: `ajustar(params, perfil)`.

Sin perfil, `ajustar` devuelve el mismo objeto (arranque en frío idéntico; hay test de regresión).
Los ajustes con perfil (ticket_tipico, umbral_relevante_eur) están en `ajustar` (M9).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import ROUND_HALF_UP, Decimal
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
    # Deudas por casos (deudas-casos.md): lo que no encaja con una cuota exacta
    MAX_MULTIPLO: int = 3               # un Bizum de k x cuota (k <= 3) cuenta como k personas
    TOL_REDONDEO_EUR: Decimal = Decimal("1")  # redondeo: a <= 1 € de la cuota (en un múltiplo, 1 € por cuota)
    PARTE_MAX_PCT: Decimal = Decimal("0.6")   # un envío mayor que el 60 % del total no es la parte de nadie
    MIN_CONOCIDOS_DESIGUAL: int = 2     # cuotas desiguales: al menos 2 pagadores de repartos anteriores
    CUBIERTO_MAX_PCT: Decimal = Decimal("0.95")  # desiguales: si ya se ha recibido el 95 % del total, no falta nada
    CONFIANZA_DUDOSO: float = 0.60      # un caso dudoso nunca llega al 0,7 del módulo: lo resuelve la fase 2
    # Gasto fijo compartido (alquiler, hipoteca, comunidad): el pago puede ser una transferencia o un recibo de una serie
    CATEGORIAS_FIJO: tuple[str, ...] = ("vivienda",)
    CANALES_FIJO: tuple[str, ...] = ("tarjeta", "transferencia", "recibo")
    PERSONAS_MAX_FIJO: int = 6          # un alquiler se reparte entre pocos: un Bizum de 31 € no es 1/12 de 380 €
    MIN_OCURRENCIAS_RECURRENTE: int = 3  # con el de ahora: >= 3 ciclos seguidos del mismo comercio...
    DIAS_ENTRE_CICLOS: tuple[int, int] = (25, 37)   # ...a ≈ un mes uno de otro


@dataclass(frozen=True)
class PagoIndividual:
    """Señal de lugar y día (deudas-casos.md, «pago_individual»): un pago con tarjeta que pudo ser con otros."""
    IMPORTE_MIN: Decimal = Decimal("20")                # sin perfil; con perfil: clamp(umbral_relevante_eur, 20, 60)
    IMPORTE_MIN_TOPE: Decimal = Decimal("60")
    MULT_ENTRE_SEMANA: Decimal = Decimal("2")           # entre semana solo cuenta un pago de >= 2 x el umbral
    TIPOS_ELEGIBLES: tuple[str, ...] = ("restaurante", "bar", "ocio")   # nunca supermercado, gasolinera, servicios...
    DIAS_FINDE: tuple[int, ...] = (5, 6)                # sábado y domingo (`date.weekday`)
    DIAS_NOCHE: tuple[int, ...] = (4,)                  # viernes: plausible, solo señal débil
    CONFIANZA: float = 0.50                             # baja y fija: el razonador descarta < 0,5 y aquí no avisa nadie
    MAX_CARACTERES_BUSQUEDA: int = 30                   # la búsqueda web del tipo solo acepta nombres cortos
    # Lo aprendido (`compania`, curva de amigos A3): abre con `senal = "aprendida"` aunque las reglas fijas callen
    P_ACOMPANADO_MIN: float = 0.60                      # p(acompañado) del ámbito desde la que abre (>=)
    IMPORTE_MIN_APRENDIDA: Decimal = Decimal("10")      # mínimo propio, cualquier día; el perfil no lo sube
    CONFIANZA_APRENDIDA: float = 0.60                   # < 0,7 del módulo: el aviso lo decide la escalera, no el motor


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
class PruebaGratuita:
    IMPORTE_MAX_VERIF: Decimal = Decimal("1")         # una verificación es de 0 € o de <= 1 € que se devuelve
    VENTANA_DEVOLUCION_VERIF: int = 5                 # días para que llegue la devolución del 1 €
    DIAS_SIN_SERIE: int = 365                         # sin cargos > 1 € del comercio en este plazo (si no: cambio de tarjeta)
    DIAS_PRUEBA_POR_DEFECTO: int = 30                 # duración supuesta si ni el cliente ni el catálogo la dicen
    AVISO_DIAS_ANTES: int = 3                         # avisa cuando faltan 3 días o menos para el primer cobro...
    AVISO_DIAS_EXTRA_POR_DEFECTO: int = 2             # ...y 5 si la duración es una suposición
    DIAS_GRACIA_COBRO: int = 7                        # un cargo hasta 7 días después del primer cobro previsto cierra la prueba
    DIAS_FUSION_USUARIO: int = 3                      # verificación a +-3 días de lo que dijo el cliente: es la misma prueba
    DIAS_ALTA_MAX: int = 90                           # una verificación más vieja no se adopta
    MAX_CARACTERES_BUSQUEDA: int = 30                 # solo se busca en la web un nombre corto y sin dígitos
    CONFIANZA_BASE: float = 0.60
    CONFIANZA_VERIFICACION: float = 0.20              # verificación explícita (0 € o 1 € devuelto)
    CONFIANZA_DURACION_CONOCIDA: float = 0.10         # catálogo o web
    CONFIANZA_DURACION_SUPUESTA: float = -0.15        # por defecto
    CONFIANZA_USUARIO: float = 0.90
    CONFIANZA_SIN_CATALOGO_MAX: float = 0.55          # comercio sin ficha: solo la categoría por reglas
    CONFIANZA_MAX: float = 0.95


@dataclass(frozen=True)
class Razonador:
    CONFIANZA_MIN: float = 0.5


DEFECTO: dict[str, object] = {
    "series": Series(),
    "gasto_compartido": GastoCompartido(),
    "pago_individual": PagoIndividual(),
    "cargo_duplicado": CargoDuplicado(),
    "subida_recibo": SubidaRecibo(),
    "prueba_gratuita": PruebaGratuita(),
    "razonador": Razonador(),
}


def _acotar(valor: Decimal, minimo: Decimal, maximo: Decimal) -> Decimal:
    return min(max(valor, minimo), maximo)


def _campo(perfil: PerfilUsuario, nombre: str):
    """El valor del campo del perfil, o None si falta o el usuario lo borró (entonces no cambia nada)."""
    if nombre in perfil.campos_borrados:
        return None
    return getattr(perfil, nombre, None)


def _eur(valor: Decimal) -> Decimal:
    return valor.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def ajustar(params: Parametros, perfil: PerfilUsuario | None) -> Parametros:
    """Única función de umbrales personales (motor.md §2.3). Sin perfil, los mismos valores (el mismo objeto).
    Con perfil, solo cambia lo de la tabla; un campo que falte o esté borrado no cambia nada.

    - `GastoCompartido.IMPORTE_MIN_PAGO` = clamp(2 x `ticket_tipico`, 20, 60).
    - `PagoIndividual.IMPORTE_MIN` = clamp(`umbral_relevante_eur`, 20, 60): el perfil solo lo sube (ante la duda, silencio).
    - `CargoDuplicado.IMPORTE_MIN_TARJETA` = clamp(0,5 x `ticket_tipico`, 5, 30).
    - `SubidaRecibo.SUBIDA_MIN_ANUAL` = max(12, 0,10 x `umbral_relevante_eur`).
    - `PruebaGratuita`: nada numérico; `suscripciones_activas` se lee en `pruebas.py` (ignora `en_prueba`).
    - Los grupos (candidatos de la cena y su retraso p75) los lee el detector `gasto_compartido`.
    """
    if perfil is None:
        return params
    ticket, umbral = _campo(perfil, "ticket_tipico"), _campo(perfil, "umbral_relevante_eur")
    if isinstance(params, GastoCompartido) and ticket is not None:
        return replace(params, IMPORTE_MIN_PAGO=_eur(_acotar(2 * ticket, Decimal("20"), Decimal("60"))))
    if isinstance(params, PagoIndividual) and umbral is not None:
        return replace(params, IMPORTE_MIN=_eur(_acotar(umbral, params.IMPORTE_MIN, params.IMPORTE_MIN_TOPE)))
    if isinstance(params, CargoDuplicado) and ticket is not None:
        return replace(params, IMPORTE_MIN_TARJETA=_eur(_acotar(ticket / 2, Decimal("5"), Decimal("30"))))
    if isinstance(params, SubidaRecibo) and umbral is not None:
        return replace(params, SUBIDA_MIN_ANUAL=_eur(max(params.SUBIDA_MIN_ANUAL, umbral / 10)))
    return params


def ajustados(perfil: PerfilUsuario | None) -> dict[str, object]:
    """Todos los parámetros del motor ajustados al perfil (o los de defecto)."""
    return {nombre: ajustar(params, perfil) for nombre, params in DEFECTO.items()}
