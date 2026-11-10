"""
Generador de propuestas sintéticas (personalizacion.md §8). Datos inventados, semilla fija.

Cada semana trae 10 propuestas de los tipos del MVP (`gasto_compartido`, `cargo_duplicado`,
`renovacion_proxima`, `subida_recibo`, `prueba_gratuita`) más `posible_estafa` e `ingreso_extra` como
control. Un 10 % son falsos positivos del motor (confianza algo más baja, como cabría esperar de un
detector calibrado a medias). `impacto_relativo` sale de un saldo simulado que cae hasta la nómina.

El flujo de propuestas depende solo de (semilla, usuario): todas las políticas ven las mismas propuestas
y los mismos números al azar de respuesta (muestreo común), así la comparación entre políticas no es ruido.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from ...plataforma.tipos import AccionOfrecida, Propuesta
from .perfiles import HOY, PROTECCION, UsuarioSimulado

LUNES = datetime(2026, 11, 2)                   # semana 1 = 2-8 de noviembre de 2026
PROPUESTAS_POR_SEMANA = 10
FALSOS = 0.10

# Composición de cada semana (10): la misma para todos; cambian valores, contactos, días y horas.
COMPOSICION = (("gasto_compartido", 2), ("cargo_duplicado", 2), ("renovacion_proxima", 2),
               ("subida_recibo", 1), ("prueba_gratuita", 1), ("posible_estafa", 1), ("ingreso_extra", 1))
VALORES = {
    "gasto_compartido": ("6", "12", "18", "24", "40", "60"),
    "cargo_duplicado": ("4", "9.99", "15", "24", "45", "80"),
    "renovacion_proxima": ("5", "9.99", "12.99", "25", "49"),
    "subida_recibo": ("1.5", "3", "5", "8", "12"),
    "prueba_gratuita": ("4.99", "9.99", "14.99"),
    "posible_estafa": ("30", "120", "300"),
    "ingreso_extra": ("30", "60", "150"),
}
COMERCIOS = {
    "cargo_duplicado": ("Libreria Luna", "Netflix", "Glovo", "Zara"),
    "renovacion_proxima": ("Spotify", "Netflix", "Gimnasio Fit", "Iberdrola"),
    "subida_recibo": ("Iberdrola", "Movistar", "Seguro Hogar"),
    "prueba_gratuita": ("Streamflix", "Musicly", "Fitnow"),
    "posible_estafa": ("Tienda Rapida", "Envios Express"),
    "gasto_compartido": ("La Tasca", "Bar Pepe", "Cine Ideal"),
    "ingreso_extra": (None,),
}
CONTACTOS = ("MARCOS R", "LAURA M", "DANIEL P", "SARA L", "HERMANO")

# Módulo que emite cada tipo de momento (nombres de ejemplo; el reparto lo cambia el test de módulo nuevo).
MODULO_DE = {
    "gasto_compartido": "cena_compartida", "cargo_duplicado": "cobro_duplicado",
    "renovacion_proxima": "renovacion", "prueba_gratuita": "fin_de_prueba", "subida_recibo": "recibo_al_alza",
    "posible_estafa": "estafa", "ingreso_extra": "ingreso",
}
# Acciones que ofrece cada módulo, en su orden de fábrica (la política puede reordenarlas, nunca añadir).
ACCIONES_OFRECIDAS = {
    "gasto_compartido": ("recordar", "pedir_bizum"),
    "cargo_duplicado": ("reclamar_cargo", "bloquear_comercio", "recordar"),
    "renovacion_proxima": ("recordar", "cancelar_suscripcion", "bloquear_comercio"),
    "subida_recibo": ("recordar", "cancelar_suscripcion", "reclamar_cargo"),
    "prueba_gratuita": ("recordar", "cancelar_suscripcion", "bloquear_comercio"),
    "posible_estafa": ("bloquear_comercio", "reclamar_cargo", "mover_dinero"),
    "ingreso_extra": ("mover_dinero", "recordar"),
}
URGENCIA = {"posible_estafa": "alta", "prueba_gratuita": "alta", "renovacion_proxima": "media",
            "cargo_duplicado": "media", "gasto_compartido": "media", "subida_recibo": "baja",
            "ingreso_extra": "baja"}


@dataclass(frozen=True)
class Sintetica:
    """Una propuesta con su verdad oculta (la política solo ve `propuesta`)."""
    propuesta: Propuesta
    semana: int            # 0-5
    util: bool             # verdad: ¿le sirve a este usuario? (sin fatiga)
    falsa: bool            # falso positivo del motor
    azar: tuple[float, ...]   # números al azar de su respuesta, comunes a todas las políticas


def saldo_simulado(usuario: UsuarioSimulado, dia: datetime) -> Decimal:
    """El saldo cae del ingreso (el día de cobro) hasta ~8 % justo antes de la siguiente nómina."""
    cobro = usuario.perfil.dia_cobro_nomina or 1
    desde = (dia.day - cobro) % 30
    fraccion = max(Decimal("0.08"), 1 - Decimal("0.92") * desde / 30)
    return usuario.saldo_base * fraccion


def impacto_relativo(usuario: UsuarioSimulado, valor: Decimal, dia: datetime) -> Decimal:
    return (valor / saldo_simulado(usuario, dia)).quantize(Decimal("0.001"))


def _propuesta(usuario: UsuarioSimulado, pid: str, tipo: str, valor: Decimal, comercio: str | None,
               contraparte: str | None, confianza: float, ahora: datetime,
               modulos: dict[str, str]) -> Propuesta:
    return Propuesta(
        id=pid, modulo_id=modulos[tipo], momento_id=f"m-{pid}", usuario_id=usuario.nombre,
        titulo=f"Sintética {tipo}", mensaje_notificacion=f"Sintética {tipo}", contexto_llamada="Sintética.",
        acciones_ofrecidas=[AccionOfrecida(accion_id=a) for a in ACCIONES_OFRECIDAS[tipo]],
        valor_estimado_eur=valor, urgencia=URGENCIA[tipo], tipo_momento=tipo, comercio=comercio,
        contraparte=contraparte, confianza=confianza, impacto_relativo=impacto_relativo(usuario, valor, ahora),
        creada=ahora,
    )


def generar(usuario: UsuarioSimulado, semilla: int, semanas: int = 6,
            modulos: dict[str, str] | None = None) -> list[Sintetica]:
    """Todas las propuestas del usuario en orden cronológico. Determinista en (usuario, semilla)."""
    modulos = modulos or MODULO_DE
    rng = random.Random(f"generador|{usuario.nombre}|{semilla}")
    salida: list[Sintetica] = []
    for semana in range(semanas):
        tipos = [t for t, n in COMPOSICION for _ in range(n)]
        rng.shuffle(tipos)
        items = []
        for i, tipo in enumerate(tipos):
            dia = rng.randrange(7)
            hora, minuto = rng.randrange(10, 21), rng.randrange(60)
            valor = Decimal(rng.choice(VALORES[tipo]))
            comercio = rng.choice(COMERCIOS[tipo])
            contraparte = rng.choice(CONTACTOS) if tipo == "gasto_compartido" else None
            falsa = rng.random() < FALSOS
            confianza = round(rng.uniform(0.60, 0.90) if falsa else rng.uniform(0.80, 0.98), 2)
            azar = tuple(rng.random() for _ in range(4))
            ahora = LUNES + timedelta(days=7 * semana + dia, hours=hora, minutes=minuto)
            items.append((ahora, i, tipo, valor, comercio, contraparte, falsa, confianza, azar))
        for ahora, i, tipo, valor, comercio, contraparte, falsa, confianza, azar in sorted(items, key=lambda x: x[:2]):
            propuesta = _propuesta(usuario, f"s{semilla}-{usuario.nombre[:3]}-{semana}-{i}", tipo, valor, comercio,
                                   contraparte, confianza, ahora, modulos)
            salida.append(Sintetica(propuesta, semana, usuario.es_util(tipo, valor, contraparte, falsa), falsa, azar))
    return salida


# --- El mismo duplicado para todos (tabla del jurado) ----------------------------------------------

AHORA_DUPLICADO = datetime(2026, 11, 27, 12, 0)    # a 4 días de la nómina del estudiante (día 1)


def mismo_duplicado(usuario: UsuarioSimulado, modulos: dict[str, str] | None = None) -> Propuesta:
    """Netflix cobrado dos veces (12,99 €, urgencia media, confianza 0,92) un 27 de noviembre."""
    return _propuesta(usuario, f"dup-{usuario.nombre}", "cargo_duplicado", Decimal("12.99"), "Netflix", None, 0.92,
                      AHORA_DUPLICADO, modulos or MODULO_DE)


__all__ = ["Sintetica", "generar", "mismo_duplicado", "saldo_simulado", "impacto_relativo", "PROTECCION", "HOY",
           "MODULO_DE", "ACCIONES_OFRECIDAS", "AHORA_DUPLICADO", "LUNES"]
