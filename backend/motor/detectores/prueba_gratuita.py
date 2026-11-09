"""
`prueba_gratuita` (motor.md §3.5): una prueba gratuita está a punto de empezar a cobrarse.

Las altas (por verificación o porque el cliente lo dijo) y los cierres (cobrada, caducada, cancelada) los
pone `pruebas.sincronizar` / `cerrar_prueba` en el estado del motor; aquí solo se decide **cuándo avisar**:
el primer `hoy` con `0 < fecha_primer_cobro - hoy <= AVISO_DIAS_ANTES` (3 días; 5 si la duración es una
suposición `por_defecto`). Si el alta llega tarde, se avisa mientras quede >= 1 día. Solo ve el pasado.
"""

from __future__ import annotations

from .. import pruebas
from ..parametros import PruebaGratuita
from . import registrar
from .base import Contexto, Hallazgo


@registrar("prueba_gratuita", version=1)
def detectar(ctx: Contexto) -> list[Hallazgo]:
    p: PruebaGratuita = ctx.params["prueba_gratuita"]
    hallazgos = []
    for prueba in ctx.pruebas:
        if prueba["estado"] != "abierta":
            continue
        comercio = prueba["comercio"]
        info = ctx.conocimiento(comercio)
        ficha = pruebas.ficha_util(info)
        if ficha is not None and not ficha.es_suscripcion:
            continue
        dias_prueba, fuente_duracion = pruebas.duracion(prueba, info, p)
        primer_cobro = pruebas.fecha_primer_cobro(prueba, info, p)
        dias_hasta = (primer_cobro - ctx.hoy).days
        antes = p.AVISO_DIAS_ANTES + (p.AVISO_DIAS_EXTRA_POR_DEFECTO if fuente_duracion == "por_defecto" else 0)
        if not 0 < dias_hasta <= antes:
            continue
        importe = pruebas.importe_previsto(info)
        datos = {
            "comercio": comercio,
            "fecha_alta": prueba["fecha_alta"],
            "dias_prueba": dias_prueba,
            "fecha_primer_cobro": primer_cobro.isoformat(),
            "dias_hasta": dias_hasta,
            "fuente": prueba["fuente"],
            "fuente_duracion": fuente_duracion,
            "fuentes_info": list(ficha.fuentes) if ficha is not None else [],
        }
        if importe is not None:
            datos["importe_previsto"] = importe
        if prueba.get("verificacion_id"):
            datos["verificacion_id"] = prueba["verificacion_id"]
        hallazgos.append(Hallazgo(
            tipo="prueba_gratuita",
            clave=f"{comercio}|{prueba['fecha_alta']}",
            movimientos=list(prueba.get("evidencias") or []),
            confianza=pruebas.confianza(prueba, info, fuente_duracion, p),
            datos=datos,
            impacto_eur=importe,
        ))
    return hallazgos
