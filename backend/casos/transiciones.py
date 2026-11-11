"""
Escenarios, transiciones y saldado manual de un `Caso` (docs/diseno/deudas-casos.md, «Escenarios, transiciones y
cuentas con personas»). Todo es puro: devuelve casos nuevos y no guarda nada (guarda el orquestador).

- `saldar_manual`: el usuario dice que alguien le pagó fuera de Bizum (efectivo, invitación, otro). Nunca mueve dinero.
- `cambiar_escenario`: solo las transiciones de la tabla; cualquier otra lanza `ValueError` con lo que hay que hacer.
- `caso_de_movimiento`: «X me debe esto» sobre un cargo del usuario (`pago_por_otro` o `gasto_compartido`).
- `momento_sintetico`: el `Momento` que el portero emite cuando un caso del usuario llega a su fecha, para que el
  módulo `gasto_compartido` proponga `pedir_bizum` con el botón. El dinero solo se mueve con el botón y el token.
- `aplicar_recurrente`: cambio AUTOMÁTICO por código a `gasto_fijo_compartido` si el momento trae `recurrente`.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Iterable

from ..motor.normalizar import clave_contraparte
from ..plataforma.reloj import ahora_por_defecto
from ..plataforma.tipos import Caso, Deudor, EscenarioDeuda, Momento, Movimiento, OrigenCambio
from .amigos import _coincide
from .ciclo import (CERRADOS, _a_fecha, _anotar, _copia, a_decimal, descartar, eur_texto, nombre_visible,
                    pendientes, sanear_motivo)
from .cierre import saldar_con_movimientos

DIAS_ESPERA_PAGO_POR_OTRO = 2        # a los 2 días sin Bizum de esa persona, el portero pregunta
VIAS_MANUALES = ("efectivo", "invitacion", "otro")
MAX_DEUDORES = 30                    # un envío múltiple de Bizum llega a 30 personas
ESCENARIOS_CON_DEUDORES = ("pago_por_otro", "gasto_compartido", "gasto_fijo_compartido")
ESTADOS_PEDIBLES = ("detectada", "caducada", "rechazada")   # a quien se le puede pedir (no pedida ni olvidada)

# Qué escenario puede pasar a cuál (`descartado` no es un escenario: cierra el caso). Cualquier otra se rechaza.
TRANSICIONES: dict[str, tuple[str, ...]] = {
    "pago_individual": ("pago_por_otro", "gasto_compartido", "descartado"),
    "gasto_compartido": ("gasto_fijo_compartido", "pago_por_otro", "pago_individual"),
    "pago_por_otro": ("gasto_compartido",),
}
ETIQUETA = {"pago_individual": "pago individual", "pago_por_otro": "pago por otro", "gasto_compartido": "gasto compartido",
            "gasto_fijo_compartido": "gasto fijo compartido", "descartado": "descartado"}


def _etiqueta(escenario: str | None) -> str:
    return ETIQUETA.get(escenario or "", escenario or "sin escenario")


# --- Saldado manual -----------------------------------------------------------------------------

def saldar_manual(caso: Caso, contraparte: str | None, via: str, motivo: str | None, hoy: date,
                  ahora: datetime | None = None, origen: OrigenCambio = "usuario") -> Caso:
    """Marca como `saldada` a una persona (o, sin `contraparte`, a todas las que faltan) con su `via_saldado` y un
    `motivo_saldado` saneado (máx. 120 caracteres). Si pagan todos, el caso pasa a `saldado` y no insiste."""
    if via not in VIAS_MANUALES:
        raise ValueError(f"La vía de saldado debe ser una de: {', '.join(VIAS_MANUALES)}. Recibí {via!r}.")
    if caso.estado in CERRADOS:
        raise ValueError(f"Este caso ya está cerrado ({caso.estado}): no hay nada que saldar.")
    if contraparte is None:
        objetivo = pendientes(caso)
        if not objetivo:
            raise ValueError("Este caso no tiene a nadie por pagar.")
    else:
        objetivo = [d for d in caso.deudores if _coincide(d.contraparte, contraparte)]
        if not objetivo:
            raise ValueError("No hay nadie con ese nombre en este caso: elige a una de las personas del caso.")
        if all(d.estado == "saldada" for d in objetivo):
            raise ValueError(f"{nombre_visible(objetivo[0].contraparte)} ya está saldada en este caso.")
    nuevo = _copia(caso)
    cuando = ahora or ahora_por_defecto(hoy)
    nota = sanear_motivo(motivo) or None
    claves = {d.contraparte for d in objetivo}
    for d in nuevo.deudores:
        if d.contraparte in claves and d.estado != "saldada":
            d.estado, d.saldada, d.via_saldado, d.motivo_saldado = "saldada", hoy, via, nota
            _anotar(nuevo, origen, f"{nombre_visible(d.contraparte)} pasa a saldada ({via}); no se mueve dinero.", cuando)
    if all(d.estado == "saldada" for d in nuevo.deudores):
        nuevo.estado = "saldado"
        _anotar(nuevo, origen, "Caso saldado.", cuando)
    return nuevo


def descartar_persona(caso: Caso, contraparte: str, hoy: date, motivo: str | None = None,
                      origen: OrigenCambio = "usuario", ahora: datetime | None = None) -> Caso:
    """«Esta persona no me debe»: sale del caso (su saldo baja) y queda el rastro en `historial`. Si no queda nadie por
    cobrar, el caso se cierra: `saldado` si otros ya habían pagado y `descartado` si no. Nunca mueve dinero."""
    if caso.estado in CERRADOS:
        raise ValueError(f"Este caso ya está cerrado ({caso.estado}).")
    objetivo = [d for d in caso.deudores if _coincide(d.contraparte, contraparte)]
    if not objetivo:
        raise ValueError("No hay nadie con ese nombre en este caso: elige a una de las personas del caso.")
    if all(d.estado == "saldada" for d in objetivo):
        raise ValueError(f"{nombre_visible(objetivo[0].contraparte)} ya pagó en este caso: no se puede descartar.")
    nuevo = _copia(caso)
    cuando = ahora or ahora_por_defecto(hoy)
    nota = sanear_motivo(motivo)
    claves = {d.contraparte for d in objetivo if d.estado != "saldada"}
    nuevo.deudores = [d for d in nuevo.deudores if d.contraparte not in claves]
    for clave in sorted(claves):
        _anotar(nuevo, origen, f"{nombre_visible(clave)} no te debe: sale del caso" + (f" ({nota})." if nota else "."), cuando)
    _recalcular_hechos(nuevo)
    if not pendientes(nuevo):
        if nuevo.deudores:                      # los demás ya habían pagado
            nuevo.estado = "saldado"
            _anotar(nuevo, origen, "Caso saldado.", cuando)
            return nuevo
        return descartar(nuevo, hoy, nota or "ya no queda nadie por cobrar.", origen, cuando)
    if nuevo.estado == "pedido" and not any(d.estado == "pedida" for d in nuevo.deudores):
        nuevo.estado = "abierto"
    return nuevo


# --- Transiciones --------------------------------------------------------------------------------

def comprobar_transicion(caso: Caso, nuevo: str) -> None:
    """Lanza `ValueError` (en español, con qué hacer) si el caso no puede pasar a `nuevo`."""
    if caso.estado in CERRADOS:
        raise ValueError(f"Este caso ya está cerrado ({caso.estado}): no se puede cambiar su escenario.")
    actual = caso.escenario
    if actual is None:
        raise ValueError("Este caso aún es dudoso y no tiene escenario: primero hay que resolver la duda.")
    if nuevo == actual:
        raise ValueError(f"Este caso ya es de tipo {_etiqueta(actual)}.")
    permitidos = TRANSICIONES.get(actual, ())
    if nuevo not in permitidos:
        destinos = ", ".join(_etiqueta(p) for p in permitidos) or "ninguno"
        raise ValueError(f"No se puede pasar de {_etiqueta(actual)} a {_etiqueta(nuevo)}. "
                         f"Desde {_etiqueta(actual)} solo se puede ir a: {destinos}.")


def _fusionar(caso: Caso, nuevos: Iterable[Deudor]) -> list[Deudor]:
    """Los deudores del caso más los nuevos; quien ya estaba conserva su estado y su cuota."""
    actuales = {d.contraparte for d in caso.deudores}
    return [*caso.deudores, *(d for d in nuevos if d.contraparte not in actuales)]


def _recalcular_hechos(caso: Caso) -> None:
    pend = pendientes(caso)
    caso.hechos["faltan"] = len(pend)
    caso.hechos["importe_pendiente"] = eur_texto(sum((d.cuota for d in pend), Decimal("0")))
    cuotas = {d.cuota for d in pend}
    if len(cuotas) == 1:
        caso.hechos["cuota"] = eur_texto(next(iter(cuotas)))
    else:
        caso.hechos.pop("cuota", None)


def cambiar_escenario(caso: Caso, nuevo: str, motivo: str | None, origen: OrigenCambio, hoy: date,
                      ahora: datetime | None = None, deudores: Iterable[Deudor] | None = None) -> Caso:
    """Cambia el escenario con la tabla `TRANSICIONES` y deja rastro en `historial`. Ajusta `aviso`, `avisar_desde` y
    los deudores al nuevo escenario. `deudores` (opcional) suma personas al caso (solo `pago_individual` ->
    `pago_por_otro` | `gasto_compartido` y `pago_por_otro` -> `gasto_compartido` tienen sentido). `descartado` cierra
    el caso. Si cambia quién debe, se prepara una propuesta nueva (sin `propuesta_id` ni `momento_id` viejos)."""
    comprobar_transicion(caso, nuevo)
    nota = sanear_motivo(motivo)
    cuando = ahora or ahora_por_defecto(hoy)
    if nuevo == "descartado":
        return descartar(caso, hoy, nota or "no era un gasto compartido.", origen, cuando)

    anterior = caso.escenario
    resultado = _copia(caso)
    previos = {d.contraparte for d in resultado.deudores}
    resultado.deudores = _fusionar(resultado, deudores or [])

    if nuevo == "pago_individual":                       # «no era compartido»: nadie debe nada
        resultado.deudores = [d for d in resultado.deudores if d.estado == "saldada"]
        resultado.aviso = "silencioso"
        if resultado.estado == "pedido":
            resultado.estado = "abierto"
    else:
        pend = pendientes(resultado)
        if nuevo == "pago_por_otro" and len(pend) != 1:
            raise ValueError("Pago por otro es cuando te debe una sola persona: "
                             + ("indica quién te debe." if not pend else
                                f"aquí faltan {len(pend)}; déjalo como gasto compartido."))
        if not pend:
            raise ValueError(f"Para pasar a {_etiqueta(nuevo)} tiene que haber alguien a quien se le espera el dinero: "
                             "indica quién te debe.")
        resultado.aviso = "notificar"
        if anterior == "pago_individual":                # nace ahora: se da tiempo a pagar antes de preguntar
            resultado.avisar_desde = hoy + timedelta(days=DIAS_ESPERA_PAGO_POR_OTRO)

    if {d.contraparte for d in resultado.deudores} != previos:
        resultado.propuesta_id = None                    # la propuesta vieja listaba a otras personas
        resultado.momento_id = None
        resultado.hechos.pop("avisado_el", None)
        resultado.hechos.pop("pregunta", None)
    if nuevo != "pago_individual" or resultado.deudores:
        _recalcular_hechos(resultado)
    resultado.escenario = nuevo                          # type: ignore[assignment]
    _anotar(resultado, origen, f"Cambia de {_etiqueta(anterior)} a {_etiqueta(nuevo)}" + (f": {nota}" if nota else "."),
            cuando)
    return resultado


def _es_recurrente(valor: Any) -> bool:
    if isinstance(valor, str):
        return valor.strip().lower() not in ("", "false", "no", "0", "none")
    return bool(valor)


def aplicar_recurrente(caso: Caso, momento: Momento, hoy: date, ahora: datetime | None = None) -> Caso:
    """Un `gasto_compartido` que el motor marca como serie recurrente (`Momento.datos["recurrente"]`) pasa solo a
    `gasto_fijo_compartido`, con rastro de origen `codigo`. Sin la marca (o en un caso dudoso) no cambia nada."""
    if caso.escenario != "gasto_compartido" or caso.estado in CERRADOS or not _es_recurrente(momento.datos.get("recurrente")):
        return caso
    return cambiar_escenario(caso, "gasto_fijo_compartido", "se repite cada ciclo con las mismas personas.", "codigo",
                             hoy, ahora)


# --- «X me debe esto»: caso del usuario sobre un movimiento ---------------------------------------

def clave_persona(texto: Any) -> str | None:
    """Clave de contraparte de lo que escribe el usuario: «Marcos R.», «Marcos Ruiz Sanz» o «MARCOS R» -> `MARCOS R`."""
    return clave_contraparte(texto) if isinstance(texto, str) else None


def deudores_de_peticion(movimiento: Movimiento, pedidos: list[dict]) -> list[Deudor]:
    """`[{contraparte, importe}]` -> `Deudor`s. Cada importe debe ser > 0 y no pasar del pago; sin repetidos."""
    if movimiento.importe >= 0:
        raise ValueError("Solo puedes reclamar un cargo tuyo: ese movimiento es un ingreso.")
    if not pedidos:
        raise ValueError("Indica al menos una persona que te debe, con su importe.")
    if len(pedidos) > MAX_DEUDORES:
        raise ValueError(f"Como mucho {MAX_DEUDORES} personas por caso.")
    total = abs(movimiento.importe)
    salida: list[Deudor] = []
    vistos: set[str] = set()
    for p in pedidos:
        clave = clave_persona(p.get("contraparte") if isinstance(p, dict) else None)
        if clave is None:
            raise ValueError("Cada persona necesita un nombre.")
        if clave in vistos:
            raise ValueError(f"{nombre_visible(clave)} aparece dos veces: suma sus importes en uno.")
        importe = a_decimal(p.get("importe"))
        if importe is None or importe <= 0:
            raise ValueError(f"El importe de {nombre_visible(clave)} debe ser un número mayor que cero.")
        importe = importe.quantize(Decimal("0.01"))
        if importe > total:
            raise ValueError(f"{nombre_visible(clave)} no puede deberte más de lo que pagaste ({eur_texto(total)} €).")
        vistos.add(clave)
        salida.append(Deudor(contraparte=clave, cuota=importe))
    if sum((d.cuota for d in salida), Decimal("0")) > total:
        raise ValueError(f"Entre todos no pueden deberte más de lo que pagaste ({eur_texto(total)} €).")
    return salida


def escenario_por_defecto(deudores: list[Deudor], escenario: str | None) -> str:
    if escenario is None:
        return "pago_por_otro" if len(deudores) == 1 else "gasto_compartido"
    if escenario not in ("pago_por_otro", "gasto_compartido"):
        raise ValueError("Un caso nuevo solo puede ser pago_por_otro o gasto_compartido.")
    if escenario == "pago_por_otro" and len(deudores) != 1:
        raise ValueError("Pago por otro es cuando te debe una sola persona; con varias usa gasto_compartido.")
    return escenario


def buscar_de_movimiento(lista: Iterable[Caso], movimiento_id: str) -> Caso | None:
    """Caso aún abierto que nació de ese movimiento (`hechos.movimiento_origen` o `pago_id`)."""
    for c in lista:
        if c.estado not in CERRADOS and movimiento_id in (c.hechos.get("movimiento_origen"), c.hechos.get("pago_id")):
            return c
    return None


def abre_caso(lista: Iterable[Caso], momento: Momento) -> bool:
    """¿Abre caso este momento de `gasto_compartido`? No si ya hay un caso de ese momento. Un `pago_individual`
    («¿fuiste con alguien?») tampoco si el cargo ya tiene un caso, abierto o cerrado: p. ej. el que creó el usuario con
    el botón o el chat antes de que el motor lo viera (ya sabemos con quién fue) o uno que ya se cerró."""
    lista = list(lista)
    if any(c.momento_id == momento.id for c in lista):
        return False
    if momento.datos.get("origen") != "pago_individual":
        return True
    cargo = momento.datos.get("pago_id") or momento.datos.get("movimiento_origen")
    if not isinstance(cargo, str):
        return True
    return not any(cargo in (c.hechos.get("movimiento_origen"), c.hechos.get("pago_id")) for c in lista)


def caso_de_movimiento(usuario_id: str, movimiento: Movimiento, deudores: list[Deudor], escenario: str, hoy: date,
                       ahora: datetime | None = None) -> Caso:
    """Caso nuevo `pago_por_otro` o `gasto_compartido` sobre un cargo del usuario. Avisa (pregunta y propone
    `pedir_bizum` con botón) a los 2 días sin Bizum de esa persona."""
    cuando = ahora or ahora_por_defecto(hoy)
    comercio = sanear_motivo(movimiento.comercio or "", 40)
    hechos: dict[str, Any] = {"movimientos": [movimiento.id], "movimiento_origen": movimiento.id, "pago_id": movimiento.id,
                              "fecha": movimiento.fecha.isoformat(), "importe_total": eur_texto(abs(movimiento.importe)),
                              "origen": "usuario"}
    if comercio:
        hechos["comercio"] = comercio
    caso = Caso(id=f"caso-u-{movimiento.id}", usuario_id=usuario_id, escenario=escenario,  # type: ignore[arg-type]
                estado="abierto", creado=hoy, avisar_desde=hoy + timedelta(days=DIAS_ESPERA_PAGO_POR_OTRO),
                aviso="notificar", hechos=hechos, deudores=deudores)
    _recalcular_hechos(caso)
    quien = ", ".join(nombre_visible(d.contraparte) for d in deudores)
    _anotar(caso, "usuario", f"Caso creado por ti: {quien} te debe(n) parte de este gasto.", cuando)
    return caso


def conciliar_con_historial(caso: Caso, movimientos: list[Movimiento], hoy: date, ahora: datetime | None = None) -> Caso:
    """Si la persona ya había hecho Bizum después del pago (antes de crear el caso), se salda con ese movimiento."""
    return saldar_con_movimientos(caso, [m for m in movimientos if m.importe > 0], hoy, ahora)


# --- El Momento que el portero emite para un caso del usuario ---------------------------------------

def momento_sintetico(caso: Caso, hoy: date) -> Momento | None:
    """`Momento` de tipo `gasto_compartido` con los datos del caso (faltan, candidatos, cuota, importe_pendiente,
    importe_total, comercio y `origen` = escenario) para que el módulo `gasto_compartido` proponga `pedir_bizum`. Solo
    incluye a quien se le puede pedir (no a quien ya tiene una solicitud abierta ni a quien se olvidó). `None` si el
    escenario no tiene deudores o no queda nadie."""
    if caso.escenario not in ESCENARIOS_CON_DEUDORES:
        return None
    pedibles = [d for d in caso.deudores if d.estado in ESTADOS_PEDIBLES]
    if not pedibles:
        return None
    pendiente = sum((d.cuota for d in pedibles), Decimal("0"))
    cuotas = {d.cuota for d in pedibles}
    total = a_decimal(caso.hechos.get("importe_total"), pendiente)
    fecha = _a_fecha(caso.hechos.get("fecha")) or caso.creado
    datos: dict[str, Any] = {
        "comercio": sanear_motivo(caso.hechos.get("comercio") or "este gasto", 40) or "este gasto",
        "importe_total": total, "importe_pendiente": pendiente, "faltan": len(pedibles),
        "personas_estimadas": len(caso.deudores) + 1, "fecha": fecha.isoformat(), "origen": caso.escenario,
        "candidatos": [{"contraparte": d.contraparte, "importe": d.cuota} for d in pedibles]}
    if len(cuotas) == 1:
        datos["cuota"] = next(iter(cuotas))
    if isinstance(caso.hechos.get("movimiento_origen"), str):
        datos["pago_id"] = caso.hechos["movimiento_origen"]
    quien = ", ".join(nombre_visible(d.contraparte) for d in pedibles)
    return Momento(id=f"mom-{caso.id}", tipo="gasto_compartido", usuario_id=caso.usuario_id, fecha=hoy,
                   movimientos=[str(x) for x in caso.hechos.get("movimientos", [])], datos=datos, confianza=1.0,
                   impacto_eur=pendiente, explicacion=f"Dijiste que {quien} te debe {eur_texto(pendiente)} € y no ha pagado.",
                   detector="casos-usuario", version="1")
