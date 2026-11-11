"""
Cambios que el usuario pide durante la llamada con la herramienta `actualizar_caso` (docs/diseno/experiencia.md,
«Herramientas de la llamada»). Todo es puro: devuelve un `Caso` nuevo y no guarda nada (guarda el orquestador, dentro
del candado del usuario, con su auditoría). Cada acción reutiliza las reglas de `casos/` (transiciones, saldado
manual, personas del caso) y deja rastro en `Caso.historial` con origen `llamada`.

    iba_solo                       descarta un `pago_individual` («iba solo»)
    nadie_me_debe                  descarta un `pago_individual` en el que fue acompañado pero nadie le debe
                                   (cada uno lo suyo, invitó él, lo paga la empresa)
    con_personas                   convierte un `pago_individual` o `pago_por_otro` en `pago_por_otro` o
                                   `gasto_compartido` con personas de la agenda
    no_me_debe                     una persona sale del reparto (o, si solo hay una, se descarta el caso)
    marcar_saldado                 saldado manual (efectivo, invitación u otro): nunca mueve dinero
    posponer                       no avisar hasta dentro de 1 a 14 días
    responder_duda                 contesta sí o no a la pregunta pendiente de un caso dudoso
    proponer_cambio_de_escenario   NO cambia nada: deja `hechos["cambio_propuesto"]` y el agente post-llamada
                                   (`resumir.py`) lo confirma al colgar con una cita literal del usuario

Nunca recibe ni cambia cuotas ya fijadas, ni marca pagos de Bizum, ni mueve dinero. El único importe que admite es
el de `con_personas` (lo que debe cada persona nueva), entre 0,50 y 1.000 € y sin pasar de lo que pagó el usuario.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from ..acciones.registro import BIZUM_IMPORTE_MAX, BIZUM_IMPORTE_MIN
from ..plataforma.reloj import ahora_por_defecto
from ..plataforma.tipos import Caso, Movimiento
from . import ciclo, transiciones

ACCIONES = ("iba_solo", "nadie_me_debe", "con_personas", "no_me_debe", "marcar_saldado", "posponer", "responder_duda",
            "proponer_cambio_de_escenario")
ESCENARIOS_PROPUESTA = ("pago_individual", "pago_por_otro", "gasto_compartido", "gasto_fijo_compartido")
DIAS_MIN, DIAS_MAX = 1, 14
MAX_PERSONAS = 10


@dataclass
class Cambio:
    caso: Caso
    hecho: str          # frase corta para la pantalla y para el agente («Marcos R. fuera del reparto»)


def _eur(valor: Decimal) -> str:
    return ciclo.eur_texto(valor).replace(".", ",") + " €"


def _nombres(claves: list[str]) -> str:
    visibles = [ciclo.nombre_visible(c) for c in claves]
    return visibles[0] if len(visibles) == 1 else ", ".join(visibles[:-1]) + " y " + visibles[-1]


def _abierto(caso: Caso) -> None:
    if caso.estado in ciclo.CERRADOS:
        raise ValueError(f"Este caso ya está cerrado ({caso.estado}): no hay nada que cambiar.")


def _deudor(caso: Caso, persona: Any) -> str:
    """Clave de un deudor del caso a partir de lo que dijo el usuario; `ValueError` si no está o es ambiguo."""
    from .resumir import resolver_contraparte

    clave = resolver_contraparte(caso, persona)
    if clave is None:
        quienes = ", ".join(ciclo.nombre_visible(d.contraparte) for d in caso.deudores) or "nadie"
        raise ValueError(f"No hay nadie con ese nombre en este caso. Las personas del caso son: {quienes}.")
    return clave


def _persona_o_unica(caso: Caso, persona: Any) -> str | None:
    """Sin persona: `None` = todas las que faltan, solo si únicamente falta una; si hay varias, hay que decir quién."""
    if persona not in (None, ""):
        return _deudor(caso, persona)
    pendientes = ciclo.pendientes(caso)
    if len(pendientes) > 1:
        raise ValueError("Este caso tiene a varias personas: dime de quién hablas (por su nombre).")
    return pendientes[0].contraparte if pendientes else None


def _importe(valor: Any) -> Decimal | None:
    d = ciclo.a_decimal(valor)
    return None if d is None else d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def aplicar(caso: Caso, accion: str, hoy: date, ahora: datetime | None = None, *, persona: Any = None,
            personas: list[str] | None = None, importe: Any = None, via: Any = None, motivo: Any = None,
            dias: Any = None, escenario: Any = None, respuesta: Any = None,
            movimiento: Movimiento | None = None) -> Cambio:
    """Aplica una acción de la lista cerrada a `caso`. `personas` son las claves ya resueltas en la agenda (solo
    `con_personas`) y `movimiento` es el pago del caso (para comprobar los importes). Lanza `ValueError` con un
    mensaje en español, que el agente puede contar, si la acción no vale para este caso."""
    if accion not in ACCIONES:
        raise ValueError(f"Acción no permitida. Las válidas son: {', '.join(ACCIONES)}.")
    if importe not in (None, "") and accion != "con_personas":
        raise ValueError("Esta acción no cambia importes: los importes los calcula el código.")
    cuando = ahora or ahora_por_defecto(hoy)
    texto = ciclo.sanear_motivo(motivo)

    if accion == "iba_solo":
        _abierto(caso)
        if caso.escenario != "pago_individual":
            raise ValueError("Solo vale para un pago individual (una pregunta «¿fuiste con alguien?»). "
                             "Si ya no te deben nada, usa no_me_debe.")
        nuevo = transiciones.cambiar_escenario(caso, "descartado", "dijiste en la llamada que ibas solo.", "llamada",
                                               hoy, cuando)
        return Cambio(nuevo, "Pago marcado como tuyo: ibas solo")

    if accion == "nadie_me_debe":
        _abierto(caso)
        if caso.escenario != "pago_individual":
            raise ValueError("Solo vale para un pago individual (una pregunta «¿fuiste con alguien?»). "
                             "Si una persona concreta no te debe, usa no_me_debe.")
        nuevo = transiciones.cambiar_escenario(caso, "descartado", "fuiste acompañado, pero nadie te debe nada.",
                                               "llamada", hoy, cuando)
        if nuevo is not caso:      # para aprender: acompañado sin deuda (no es lo mismo que ir solo)
            nuevo = nuevo.model_copy(update={"hechos": {**nuevo.hechos, ciclo.CLAVE_SIN_DEUDA: True}})
        return Cambio(nuevo, "Pago marcado: fuiste acompañado, pero nadie te debe")

    if accion == "con_personas":
        return _con_personas(caso, hoy, cuando, personas or [], importe, texto, movimiento)

    if accion == "no_me_debe":
        _abierto(caso)
        clave = _persona_o_unica(caso, persona)
        if clave is None:
            nuevo = ciclo.descartar(caso, hoy, "dijiste en la llamada que no te deben.", "llamada", cuando)
            return Cambio(nuevo, "Caso descartado: no te deben nada")
        nuevo = transiciones.descartar_persona(caso, clave, hoy, "lo dijiste en la llamada.", "llamada", cuando)
        return Cambio(nuevo, f"{ciclo.nombre_visible(clave)} fuera del reparto")

    if accion == "marcar_saldado":
        _abierto(caso)
        if via not in transiciones.VIAS_MANUALES:
            raise ValueError(f"Indica cómo pagó: {', '.join(transiciones.VIAS_MANUALES)}.")
        clave = _persona_o_unica(caso, persona)
        nuevo = transiciones.saldar_manual(caso, clave, via, texto or None, hoy, cuando, origen="llamada")
        quien = ciclo.nombre_visible(clave) if clave else "Todo"
        return Cambio(nuevo, f"{quien} saldado ({via}); no se mueve dinero")

    if accion == "posponer":
        _abierto(caso)
        if isinstance(dias, bool) or not isinstance(dias, int) or not DIAS_MIN <= dias <= DIAS_MAX:
            raise ValueError(f"Indica cuántos días esperar, de {DIAS_MIN} a {DIAS_MAX}.")
        return Cambio(ciclo.posponer(caso, hoy, dias, origen="llamada", ahora=cuando),
                      f"Aviso pospuesto {dias} {'día' if dias == 1 else 'días'}")

    if accion == "responder_duda":
        nuevo = ciclo.aplicar_respuesta(caso, respuesta, hoy, cuando, origen="llamada")
        quitados = sorted({d.contraparte for d in caso.deudores} - {d.contraparte for d in nuevo.deudores})
        if nuevo.estado == "descartado":
            return Cambio(nuevo, "Caso descartado: no queda nadie por cobrar")
        if quitados:
            return Cambio(nuevo, f"{_nombres(quitados)} fuera del reparto")
        return Cambio(nuevo, "Reparto confirmado con todos")

    # proponer_cambio_de_escenario: solo deja la propuesta; el agente post-llamada decide al colgar.
    _abierto(caso)
    if escenario not in ESCENARIOS_PROPUESTA:
        raise ValueError(f"El tipo debe ser uno de: {', '.join(ESCENARIOS_PROPUESTA)}.")
    transiciones.cambiar_escenario(caso, escenario, None, "llamada", hoy, cuando)   # en seco: ¿es una transición válida?
    clave = _deudor(caso, persona) if persona not in (None, "") else None
    nuevo = ciclo._copia(caso)
    nuevo.hechos["cambio_propuesto"] = {"escenario": escenario, "motivo": texto, "persona": clave,
                                        "propuesto": hoy.isoformat()}
    ciclo._anotar(nuevo, "llamada", f"Propuesta de cambio a {transiciones.ETIQUETA[escenario]}: "
                  "se confirma al colgar si lo pediste.", cuando)
    return Cambio(nuevo, f"Anotado: cambio a {transiciones.ETIQUETA[escenario]}; lo confirmo al colgar")


def _con_personas(caso: Caso, hoy: date, cuando: datetime, personas: list[str], importe: Any, texto: str,
                  movimiento: Movimiento | None) -> Cambio:
    _abierto(caso)
    if caso.escenario not in ("pago_individual", "pago_por_otro"):
        raise ValueError("Solo vale para un pago individual o un pago por otro. Si ya es un gasto compartido, "
                         "no hace falta cambiar nada.")
    if not personas:
        raise ValueError("Indica con quién fuiste (personas de tu agenda).")
    if len(personas) > MAX_PERSONAS:
        raise ValueError(f"Como mucho {MAX_PERSONAS} personas a la vez.")
    if movimiento is None:
        raise ValueError("No encuentro el pago de ese caso en tus movimientos.")
    ya = {d.contraparte for d in caso.deudores}
    repetidas = [p for p in personas if p in ya]
    if repetidas:
        raise ValueError(f"{_nombres(repetidas)} ya está en este caso.")
    total = abs(movimiento.importe)
    if importe in (None, ""):
        por_persona = (total / (len(personas) + len(ya) + 1)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    else:
        por_persona = _importe(importe)
        if por_persona is None:
            raise ValueError("El importe debe ser un número.")
    if not BIZUM_IMPORTE_MIN <= por_persona <= BIZUM_IMPORTE_MAX:
        raise ValueError("Un Bizum admite importes de 0,50 € a 1.000 €.")
    nuevos = transiciones.deudores_de_peticion(
        movimiento, [{"contraparte": p, "importe": por_persona} for p in personas])
    if sum((d.cuota for d in caso.deudores), Decimal("0")) + sum((d.cuota for d in nuevos), Decimal("0")) > total:
        raise ValueError(f"Entre todos no pueden deberte más de lo que pagaste ({ciclo.eur_texto(total)} €).")
    destino = "pago_por_otro" if len(personas) + len(ciclo.pendientes(caso)) == 1 else "gasto_compartido"
    if destino == caso.escenario:
        raise ValueError("Con esas personas el caso seguiría siendo del mismo tipo: indica a alguien más.")
    nuevo = transiciones.cambiar_escenario(caso, destino, texto or "lo dijiste en la llamada.", "llamada", hoy, cuando,
                                           deudores=nuevos)
    return Cambio(nuevo, f"{_nombres(personas)} {'añadido' if len(personas) == 1 else 'añadidos'} al reparto "
                         f"({_eur(por_persona)} cada uno)")
