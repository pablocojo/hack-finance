"""
Usuarios simulados con **preferencias ocultas** (personalizacion.md §8). Datos inventados.

Cada `UsuarioSimulado` tiene dos mitades que no se mezclan:

- `perfil`: lo que sabría `perfilar` de su vida (escrito a mano, coherente con una vida real:
  umbral = 2 · compra típica). Es lo único que ve la política con perfil.
- `util`, `favorita`, `reacciona`: lo que de verdad le sirve y cómo responde. **La política no puede
  importar este módulo** (hay un test que lo comprueba): solo ve las respuestas (`Feedback`).

Los umbrales ocultos se parecen a los del perfil pero no coinciden, para que aprender siga haciendo falta.
Útil ⇔ lo que el usuario querría que le avisaran. La protección (`posible_estafa` y `prueba_gratuita`
real) es útil para todos; un falso positivo no es útil para nadie.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Callable

from ...plataforma.tipos import Grupo, PerfilUsuario

PROTECCION = frozenset({"posible_estafa", "prueba_gratuita"})
HOY = date(2026, 11, 9)

# Probabilidades de la respuesta simulada (como en v1, personalizacion.md §8).
P_ELIGE_FAVORITA = 0.8
P_MIRA_RESUMEN = 0.6
P_RESUELVE_UTIL = 0.9          # un aviso útil que interrumpe se resuelve con p = 0,9
P_RECHAZA = 0.6                # uno inútil se rechaza (si no, se ignora y llega 48 h después)
P_FALSO_POSITIVO = 0.7         # ante una detección errónea, la marca como tal
P_SILENCIO_CONTACTO = 0.7      # `social` pide no más avisos de «Hermano» a la primera molestia
AVISOS_ANTES_DE_FATIGA = 3     # `saturable`: desde el 4.º aviso de la semana, ignora

# Resultados que devuelve `reacciona` (todos de `ResultadoFeedback`).
Reaccion = tuple[str, bool]    # (resultado, hubo_fatiga)


@dataclass
class Estado:
    """Lo que el usuario recuerda mientras vive la simulación (no lo ve la política)."""
    avisos_semana: int = 0
    semana: int = -1
    molestias_tipo: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class UsuarioSimulado:
    nombre: str
    descripcion: str
    perfil: PerfilUsuario
    saldo_base: Decimal                              # ingreso mensual: el saldo cae hasta la nómina
    util: Callable[[str, Decimal, str | None], bool]          # (tipo, valor, contraparte) -> ¿útil?
    favorita: dict[str, str]                         # tipo de momento -> acción que elige
    fatiga: bool = False                             # ignora desde el 4.º aviso de la semana
    silencia_contacto: str | None = None             # pide no_avisar_contacto de este contacto
    silencia_tipo_a_la_2: bool = False               # a la 2.ª molestia de un tipo, no_avisar_tipo

    def es_util(self, tipo: str, valor: Decimal, contraparte: str | None, falsa: bool) -> bool:
        """Verdad oculta (sin fatiga): un falso positivo nunca es útil."""
        return (not falsa) and self.util(tipo, valor, contraparte)

    def reacciona(self, *, accion: str, tipo: str, util: bool, falsa: bool, contraparte: str | None,
                  semana: int, azar: tuple[float, ...], estado: Estado) -> Reaccion:
        """Cómo responde a un aviso que ha llegado (`notificar_ahora` o `resumen`).

        `azar` son números ya sorteados por el generador (los mismos para todas las políticas), de modo
        que dos políticas se comparan sobre las mismas propuestas y las mismas reacciones del usuario.
        Devuelve (resultado, fatiga). `fatiga` = era útil, pero llegó tarde en su semana y lo ignora.
        """
        u_resp, u_extra = azar[0], azar[1]
        if estado.semana != semana:
            estado.semana, estado.avisos_semana = semana, 0
        fatiga = False
        if accion == "notificar_ahora":
            estado.avisos_semana += 1
            if self.fatiga and estado.avisos_semana > AVISOS_ANTES_DE_FATIGA and util:
                util, fatiga = False, True
        if falsa:
            if accion == "notificar_ahora":
                return ("falso_positivo" if u_resp < P_FALSO_POSITIVO else "rechazada"), fatiga
            return "ignorada", fatiga
        if util:
            if accion == "notificar_ahora":
                return ("resuelta" if u_resp < P_RESUELVE_UTIL else "vista_sin_accion"), fatiga
            return ("resuelta" if u_resp < P_MIRA_RESUMEN else "ignorada"), fatiga
        # No le sirve: lo rechaza, lo silencia o lo ignora (y la fatiga se ignora siempre).
        if fatiga or accion != "notificar_ahora" or u_resp >= P_RECHAZA:
            return "ignorada", fatiga
        estado.molestias_tipo[tipo] = estado.molestias_tipo.get(tipo, 0) + 1
        if self.silencia_contacto and contraparte == self.silencia_contacto and u_extra < P_SILENCIO_CONTACTO:
            return "no_avisar_contacto", fatiga
        if self.silencia_tipo_a_la_2 and tipo not in PROTECCION and estado.molestias_tipo[tipo] >= 2:
            return "no_avisar_tipo", fatiga
        return "rechazada", fatiga


# --- Perfiles escritos a mano (lo que `perfilar` sacaría de su vida) -------------------------------

def _perfil(ingreso: str, dia_cobro: int, ticket: str, comercios: list[str], grupos: list[Grupo] | None = None,
            ) -> PerfilUsuario:
    t = Decimal(ticket)
    return PerfilUsuario(
        calculado=HOY, dias_historial=90, dia_cobro_nomina=dia_cobro, ingreso_mensual_tipico=Decimal(ingreso),
        ticket_tipico=t, umbral_relevante_eur=min(max(2 * t, Decimal("5")), Decimal("100")),
        comercios_habituales=comercios, grupos=grupos or [],
    )


def _estudiante_util(tipo: str, valor: Decimal, contraparte: str | None) -> bool:
    if tipo in PROTECCION:
        return True
    if tipo == "ingreso_extra":
        return False
    return valor >= Decimal("6")


def _holgado_util(tipo: str, valor: Decimal, contraparte: str | None) -> bool:
    return tipo in PROTECCION or valor >= Decimal("60")


def _social_util(tipo: str, valor: Decimal, contraparte: str | None) -> bool:
    if tipo in PROTECCION:
        return True
    if tipo == "gasto_compartido":
        return contraparte != "HERMANO"
    if tipo == "cargo_duplicado":
        return valor >= Decimal("10")
    return False                       # ignora renovaciones, subidas e ingresos extra


def _saturable_util(tipo: str, valor: Decimal, contraparte: str | None) -> bool:
    return tipo in PROTECCION or valor >= Decimal("15")


USUARIOS: dict[str, UsuarioSimulado] = {u.nombre: u for u in (
    UsuarioSimulado(
        nombre="estudiante",
        descripcion="650 €/mes el día 1, compra típica de 6 €: le importa casi todo lo que cueste 6 € o más.",
        perfil=_perfil("650", 1, "6", ["Mercadona", "Glovo", "Netflix"]),
        saldo_base=Decimal("650"),
        util=_estudiante_util,
        favorita={"cargo_duplicado": "bloquear_comercio", "renovacion_proxima": "cancelar_suscripcion",
                  "subida_recibo": "cancelar_suscripcion", "prueba_gratuita": "cancelar_suscripcion",
                  "gasto_compartido": "pedir_bizum", "posible_estafa": "bloquear_comercio",
                  "ingreso_extra": "recordar"},
    ),
    UsuarioSimulado(
        nombre="holgado",
        descripcion="4.800 €/mes el día 28, compra típica de 45 €: solo protección y valor de 60 € o más.",
        perfil=_perfil("4800", 28, "45", ["El Corte Ingles", "Iberia"]),
        saldo_base=Decimal("4800"),
        util=_holgado_util,
        favorita={"cargo_duplicado": "reclamar_cargo", "renovacion_proxima": "cancelar_suscripcion",
                  "subida_recibo": "reclamar_cargo", "prueba_gratuita": "cancelar_suscripcion",
                  "gasto_compartido": "recordar", "posible_estafa": "reclamar_cargo",
                  "ingreso_extra": "mover_dinero"},
        silencia_tipo_a_la_2=True,
    ),
    UsuarioSimulado(
        nombre="social",
        descripcion="1.850 €/mes, compra típica de 10 €, divide con 4: gastos compartidos sí (salvo Hermano), "
                    "duplicados de 10 € o más; ignora renovaciones y subidas.",
        perfil=_perfil("1850", 28, "9.80", ["Mercadona", "Glovo", "La Tasca"],
                       [Grupo(miembros=["LAURA M", "DANIEL P", "SARA L", "MARCOS R"], veces=3, retraso_p75_dias=2)]),
        saldo_base=Decimal("1850"),
        util=_social_util,
        favorita={"cargo_duplicado": "reclamar_cargo", "renovacion_proxima": "recordar",
                  "subida_recibo": "recordar", "prueba_gratuita": "recordar",
                  "gasto_compartido": "pedir_bizum", "posible_estafa": "bloquear_comercio",
                  "ingreso_extra": "recordar"},
        silencia_contacto="HERMANO",
    ),
    UsuarioSimulado(
        nombre="saturable",
        descripcion="2.400 €/mes, compra típica de 15 €: útil todo desde 15 €, pero desde el 4.º aviso de la "
                    "semana ignora (fatiga que el modelo no capta del todo).",
        perfil=_perfil("2400", 25, "15", ["Mercadona", "Zara"]),
        saldo_base=Decimal("2400"),
        util=_saturable_util,
        favorita={"cargo_duplicado": "recordar", "renovacion_proxima": "recordar",
                  "subida_recibo": "recordar", "prueba_gratuita": "recordar",
                  "gasto_compartido": "recordar", "posible_estafa": "bloquear_comercio",
                  "ingreso_extra": "mover_dinero"},
        fatiga=True,
    ),
)}
