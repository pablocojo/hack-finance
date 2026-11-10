"""
Ciclo de vida de un `Caso` de deuda (docs/diseno/deudas-casos.md, «Ciclo de vida de una deuda»).

Todo es puro: cada función devuelve un `Caso` nuevo y no guarda nada (guarda el orquestador, que es el
único que escribe en disco). Las cifras las pone el código con `Decimal`. Los conceptos y notas de Bizum
nunca entran en un caso: solo claves de contraparte, cuotas, fechas e ids de movimientos.

Estados del caso: abierto | dudoso | pedido | saldado | descartado | caducado.
Estados del deudor: detectada | pedida | saldada | rechazada | caducada | olvidada.
`hechos["avisado_el"]` (fecha ISO) lo pone el portero cuando el caso se notifica; sin él, el caso sigue
en la cola de avisos. «Ahora no» lo quita y mueve `avisar_desde`.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable

from ..plataforma.privacidad import enmascarar_nombre
from ..plataforma.reloj import ahora_por_defecto
from ..plataforma.tipos import CambioCaso, Caso, Decision, Deudor, Hipotesis, Momento, OrigenCambio, Propuesta

DIAS_POSPONER = 2            # «ahora no»: se vuelve a mirar pasados 2 días
DIAS_COLA = 7                # un caso que llegó a su fecha y no avisó deja de esperar a los 7 días
DIAS_SOLICITUD = 7           # una solicitud de Bizum caduca a los 7 días naturales
DIAS_VIDA = 90               # un caso (y su amigo) se borra o caduca a los 90 días
TOLERANCIA = Decimal("0.50")  # un Bizum salda la cuota con ±0,50 €

ABIERTOS = ("abierto", "dudoso", "pedido", "caducado")   # casos que aún pueden saldarse
CERRADOS = ("saldado", "descartado")
MOTIVO_DUDOSO = "Caso dudoso sin resolver: de momento no te aviso."


# --- Utilidades --------------------------------------------------------------------------------

def a_decimal(valor: Any, defecto: Decimal | None = None) -> Decimal | None:
    """Decimal exacto desde `Decimal`, cadena, entero o decimal; si no se entiende, `defecto`."""
    if isinstance(valor, Decimal):
        return valor
    if valor is None or isinstance(valor, bool):
        return defecto
    try:
        return Decimal(str(valor))
    except (InvalidOperation, ValueError):
        return defecto


def _a_fecha(valor: Any) -> date | None:
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    if isinstance(valor, str):
        try:
            return date.fromisoformat(valor[:10])
        except ValueError:
            return None
    return None


def eur_texto(valor: Decimal) -> str:
    return format(valor.quantize(Decimal("0.01")), "f")


def nombre_visible(clave: str) -> str:
    """«MARCOS R» -> «Marcos R.»."""
    return enmascarar_nombre(clave) or clave


def _clave(valor: Any) -> str | None:
    """Clave de contraparte de un candidato: cadena o `{contraparte, ...}`."""
    if isinstance(valor, dict):
        valor = valor.get("contraparte")
    return " ".join(valor.strip().upper().split()) if isinstance(valor, str) and valor.strip() else None


def _anotar(caso: Caso, origen: OrigenCambio, cambio: str, cuando: datetime) -> None:
    caso.historial.append(CambioCaso(cuando=cuando, origen=origen, cambio=cambio))


def _copia(caso: Caso) -> Caso:
    return caso.model_copy(deep=True)


def es_dudoso(caso: Caso) -> bool:
    return caso.estado == "dudoso"


def pendientes(caso: Caso) -> list[Deudor]:
    """Deudores que aún no han pagado (cualquier estado menos `saldada`)."""
    return [d for d in caso.deudores if d.estado != "saldada"]


def importe_pendiente(caso: Caso) -> Decimal:
    return sum((d.cuota for d in pendientes(caso)), Decimal("0"))


# --- Crear -------------------------------------------------------------------------------------

def _hipotesis(momento: Momento) -> list[Hipotesis]:
    """Hipótesis de `Momento.datos["hipotesis"]` (`[{candidatos, faltan, motivo}]`), leídas con tolerancia."""
    crudas = momento.datos.get("hipotesis")
    salida: list[Hipotesis] = []
    if not isinstance(crudas, list):
        return salida
    for h in crudas:
        if not isinstance(h, dict):
            continue
        lista = h.get("candidatos") if isinstance(h.get("candidatos"), list) else []
        claves = [c for c in (_clave(x) for x in lista) if c]
        salida.append(Hipotesis(escenario="gasto_compartido", confianza=momento.confianza,
                                deudores=claves, motivo=str(h.get("motivo") or "")[:200]))
    return salida


def crear_desde_momento(momento: Momento, hoy: date | None = None, ahora: datetime | None = None) -> Caso:
    """Abre el caso de un `Momento` de `gasto_compartido`. Los deudores son los candidatos del momento, con la
    cuota que calculó el motor; `avisar_desde` es `datos["avisar_desde"]` si el motor la da y, si no, la fecha
    del momento. Si `datos["dudoso"]` es verdadero, el caso nace `dudoso`, sin escenario y con sus hipótesis."""
    if momento.tipo != "gasto_compartido":
        raise ValueError(f"Solo los momentos de gasto_compartido abren un caso (este es {momento.tipo!r}).")
    datos = momento.datos
    hoy = hoy or momento.fecha
    cuando = ahora or ahora_por_defecto(hoy)
    dudoso = bool(datos.get("dudoso"))
    hipotesis = _hipotesis(momento)
    cuota = a_decimal(datos.get("cuota"))

    claves_deudor: list[tuple[str, Decimal | None]] = []
    candidatos = datos.get("candidatos") if isinstance(datos.get("candidatos"), list) else []
    for c in candidatos:
        clave = _clave(c)
        if clave:
            claves_deudor.append((clave, a_decimal(c.get("importe"), cuota) if isinstance(c, dict) else cuota))
    if not claves_deudor and dudoso:       # solo hipótesis: sus candidatos son los posibles deudores
        for h in hipotesis:
            claves_deudor += [(c, cuota) for c in h.deudores]
    vistos: set[str] = set()
    deudores = []
    for clave, importe in claves_deudor:
        if clave in vistos or importe is None:
            continue
        vistos.add(clave)
        deudores.append(Deudor(contraparte=clave, cuota=importe))

    hechos: dict[str, Any] = {"movimientos": list(momento.movimientos)}
    for clave_hecho in ("comercio", "pago_id"):
        if isinstance(datos.get(clave_hecho), str):
            hechos[clave_hecho] = datos[clave_hecho]
    fecha_pago = _a_fecha(datos.get("fecha"))
    if fecha_pago:
        hechos["fecha"] = fecha_pago.isoformat()
    for origen in ("importe_total", "importe_pendiente", "cuota"):
        valor = a_decimal(datos.get(origen))
        if valor is not None:
            hechos[origen] = eur_texto(valor)
    if isinstance(datos.get("faltan"), int):
        hechos["faltan"] = datos["faltan"]

    caso = Caso(id=f"caso-{momento.id}", usuario_id=momento.usuario_id,
                escenario=None if dudoso else "gasto_compartido",
                estado="dudoso" if dudoso else "abierto", momento_id=momento.id, creado=hoy,
                avisar_desde=_a_fecha(datos.get("avisar_desde")) or momento.fecha, hechos=hechos,
                hipotesis=hipotesis if dudoso else [], deudores=deudores)
    _anotar(caso, "codigo", "Caso dudoso: sin avisar hasta resolver el reparto." if dudoso else
            "Caso abierto: falta por devolver una parte del gasto.", cuando)
    return caso


# --- Cambios de estado -------------------------------------------------------------------------

def posponer(caso: Caso, hoy: date, dias: int = DIAS_POSPONER, origen: OrigenCambio = "feedback",
             ahora: datetime | None = None) -> Caso:
    """«Ahora no»: no se avisa hasta dentro de `dias`. Quita la marca de avisado para que vuelva a la cola."""
    if caso.estado in CERRADOS:
        return caso
    nuevo = _copia(caso)
    nuevo.avisar_desde = hoy + timedelta(days=max(dias, 1))
    nuevo.hechos.pop("avisado_el", None)
    _anotar(nuevo, origen, f"Pospuesto hasta el {nuevo.avisar_desde.isoformat()}.", ahora or ahora_por_defecto(hoy))
    return nuevo


def descartar(caso: Caso, hoy: date, motivo: str = "El usuario dice que no se lo deben.",
              origen: OrigenCambio = "feedback", ahora: datetime | None = None) -> Caso:
    """Cierra el caso sin cobrar: lo que no estaba saldado pasa a `olvidada`."""
    if caso.estado in CERRADOS:
        return caso
    nuevo = _copia(caso)
    for d in nuevo.deudores:
        if d.estado != "saldada":
            d.estado = "olvidada"
    nuevo.estado = "descartado"
    _anotar(nuevo, origen, f"Caso descartado: {motivo}", ahora or ahora_por_defecto(hoy))
    return nuevo


def cerrar(caso: Caso, estado: str, hoy: date, motivo: str = "", origen: OrigenCambio = "codigo",
           ahora: datetime | None = None) -> Caso:
    """Cierra el caso en `saldado`, `descartado` o `caducado`. `descartado` equivale a `descartar`."""
    if estado == "descartado":
        return descartar(caso, hoy, motivo or "cerrado sin cobrar.", origen, ahora)
    if estado not in ("saldado", "caducado"):
        raise ValueError(f"Un caso solo se cierra como saldado, descartado o caducado, no {estado!r}.")
    if caso.estado == estado or caso.estado in CERRADOS:
        return caso
    nuevo = _copia(caso)
    nuevo.estado = estado  # type: ignore[assignment]
    _anotar(nuevo, origen, f"Caso {estado}" + (f": {motivo}" if motivo else "."), ahora or ahora_por_defecto(hoy))
    return nuevo


def marcar_pedido(caso: Caso, contraparte: str, hoy: date, origen: OrigenCambio = "usuario",
                  ahora: datetime | None = None) -> Caso:
    """El usuario confirmó `pedir_bizum` a esa contraparte: el deudor pasa a `pedida` (una sola solicitud
    abierta por deudor y caso). Si no hay deudor con esa clave o ya pagó, no cambia nada."""
    clave = _clave(contraparte)
    if caso.estado in CERRADOS or not clave:
        return caso
    nuevo = _copia(caso)
    cambiado = False
    for d in nuevo.deudores:
        if d.contraparte == clave and d.estado in ("detectada", "caducada", "rechazada", "olvidada"):
            d.estado, d.pedida, d.solicitudes = "pedida", hoy, d.solicitudes + 1
            _anotar(nuevo, origen, f"{nombre_visible(clave)} pasa a pedida.", ahora or ahora_por_defecto(hoy))
            cambiado = True
    if not cambiado:
        return caso
    if nuevo.estado in ("abierto", "caducado"):
        nuevo.estado = "pedido"
    return nuevo


def marcar_avisado(caso: Caso, hoy: date, ahora: datetime | None = None, nota: str = "Aviso enviado.") -> Caso:
    nuevo = _copia(caso)
    nuevo.hechos["avisado_el"] = hoy.isoformat()
    _anotar(nuevo, "codigo", nota, ahora or ahora_por_defecto(hoy))
    return nuevo


def marcar_ignorado(caso: Caso, hoy: date, ahora: datetime | None = None) -> Caso:
    """El aviso pasó 48 h sin respuesta. Procede olvidar a quien aún no se había pedido nada (`detectada`):
    pasa a `olvidada` (no se vuelve a avisar ni se le pide solo). Si más tarde paga, el cierre lo salda igual."""
    if caso.estado in CERRADOS:
        return caso
    nuevo = _copia(caso)
    olvidados = [d for d in nuevo.deudores if d.estado == "detectada"]
    for d in olvidados:
        d.estado = "olvidada"
    if not olvidados:
        return caso
    _anotar(nuevo, "feedback", "Aviso sin respuesta en 48 h: se deja de insistir.", ahora or ahora_por_defecto(hoy))
    return nuevo


def vincular_propuesta(caso: Caso, propuesta_id: str, nota: str | None = None, ahora: datetime | None = None,
                       hoy: date | None = None) -> Caso:
    if caso.propuesta_id == propuesta_id:
        return caso
    nuevo = _copia(caso)
    nuevo.propuesta_id = propuesta_id
    if nota:
        _anotar(nuevo, "codigo", nota, ahora or ahora_por_defecto(hoy or caso.creado))
    return nuevo


def caducar(caso: Caso, hoy: date, ahora: datetime | None = None) -> Caso:
    """Solicitudes sin pago a los 7 días: el deudor pasa a `caducada`; si ya nadie está pendiente de pagar
    de forma activa, el caso pasa a `caducado` (todavía puede saldarse si paga tarde). Con 90 días, `caducado`."""
    if caso.estado in CERRADOS:
        return caso
    nuevo = _copia(caso)
    cuando = ahora or ahora_por_defecto(hoy)
    for d in nuevo.deudores:
        if d.estado == "pedida" and d.pedida and (hoy - d.pedida).days >= DIAS_SOLICITUD:
            d.estado = "caducada"
            _anotar(nuevo, "codigo", f"La solicitud a {nombre_visible(d.contraparte)} caducó.", cuando)
    if nuevo.estado == "pedido" and not any(d.estado == "pedida" for d in nuevo.deudores):
        nuevo.estado = "caducado"
        _anotar(nuevo, "codigo", "Caso caducado: nadie pagó la solicitud.", cuando)
    elif nuevo.estado in ("abierto", "dudoso") and (hoy - nuevo.creado).days >= DIAS_VIDA:
        nuevo.estado = "caducado"
        _anotar(nuevo, "codigo", "Caso caducado por antigüedad (90 días).", cuando)
    return nuevo if nuevo != caso else caso


def aplicar_resolucion(caso: Caso, resolucion: Any, hoy: date, ahora: datetime | None = None) -> Caso:
    """Aplica lo que decidió la fase 2 del detector (`motor.dudas.ResolucionDuda`, ya validada y con la política
    aplicada) a un caso `dudoso`. Deja rastro en `historial` con origen `ia_dudas` y el motivo. Nunca toca cifras:
    las cuotas son las del caso (o la cuota del código para un candidato que no era deudor).

    - `avisar`: el caso pasa a `abierto` con escenario y con los deudores reducidos a los candidatos (se quita a
      quien la IA ve cubierto, p. ej. el acompañante de quien pagó por dos). Quita `propuesta_id` para que el
      portero prepare una propuesta nueva solo con esos deudores.
    - `preguntar`: sigue dudoso y guarda la pregunta en `hechos["pregunta"]` (la hace la llamada, una sola vez).
    - `no_avisar`: sigue dudoso y en silencio; solo queda anotado.
    """
    if caso.estado != "dudoso":
        return caso
    cuando = ahora or ahora_por_defecto(hoy)
    nuevo = _copia(caso)
    nuevo.hechos["dudas_hash"] = resolucion.hash
    nuevo.hechos.pop("dudas_fallo", None)
    motivo = (resolucion.motivo or "").strip()
    if resolucion.decision == "avisar":
        cuota = a_decimal(nuevo.hechos.get("cuota"))
        previos = {d.contraparte: d for d in nuevo.deudores}
        elegidos: list[Deudor] = []
        for clave in resolucion.candidatos:
            if clave in previos:
                elegidos.append(previos[clave])
            elif cuota is not None:
                elegidos.append(Deudor(contraparte=clave, cuota=cuota))
        if not elegidos:
            return caso
        quitados = [nombre_visible(c) for c in previos if c not in resolucion.candidatos]
        nuevo.deudores = elegidos
        nuevo.escenario = resolucion.escenario
        nuevo.estado = "abierto"
        nuevo.propuesta_id = None
        nuevo.hechos["resuelto_por"] = "ia_dudas"
        nuevo.hechos["motivo_ia"] = motivo
        nuevo.hechos["confianza_ia"] = resolucion.confianza
        nuevo.hechos["faltan"] = len(elegidos)
        nuevo.hechos["importe_pendiente"] = eur_texto(sum((d.cuota for d in elegidos), Decimal("0")))
        quitado = f" Se quita a {', '.join(quitados)}." if quitados else ""
        _anotar(nuevo, "ia_dudas", f"Duda resuelta como {resolucion.escenario}: {motivo}{quitado}", cuando)
    elif resolucion.decision == "preguntar" and resolucion.pregunta:
        nuevo.hechos["pregunta"] = {"texto": resolucion.pregunta, "candidatos": list(resolucion.candidatos),
                                    "preguntada": hoy.isoformat(), "estado": "pendiente"}
        _anotar(nuevo, "ia_dudas", f"Duda pendiente de preguntar al usuario: {resolucion.pregunta}", cuando)
    else:
        _anotar(nuevo, "ia_dudas", f"Sigue dudoso y sin avisar: {motivo}" if motivo else "Sigue dudoso y sin avisar.",
                cuando)
    return nuevo


def aplicar_feedback(caso: Caso, resultado: str, hoy: date, ahora: datetime | None = None) -> Caso:
    """Respuesta al aviso -> caso. «No me lo debe» (`falso_positivo`, `no_avisar_contacto`) lo descarta;
    «ahora no» (`rechazada`) lo pospone; `ignorada` olvida a quien no se había pedido. El resto no lo toca."""
    if resultado in ("falso_positivo", "no_avisar_contacto"):
        return descartar(caso, hoy, "dice que no se lo deben.", "feedback", ahora)
    if resultado == "rechazada":
        return posponer(caso, hoy, origen="feedback", ahora=ahora)
    if resultado == "ignorada":
        return marcar_ignorado(caso, hoy, ahora)
    return caso


# --- Cola de avisos ----------------------------------------------------------------------------

def listo_para_avisar(caso: Caso, hoy: date) -> bool:
    """¿Entra hoy en el portero? Abierto, con su fecha cumplida, sin avisar aún y con menos de 7 días de espera.
    Un caso `dudoso` solo entra una vez (sin propuesta) para dejar su decisión silenciada y a la vista."""
    desde = caso.avisar_desde or caso.creado
    if desde > hoy:
        return False
    if caso.estado == "dudoso":
        return caso.propuesta_id is None
    if caso.estado != "abierto" or "avisado_el" in caso.hechos:
        return False
    return (hoy - desde).days <= DIAS_COLA


def agrupar_por_contacto(casos: Iterable[Caso]) -> list[list[Caso]]:
    """Agrupa los casos que comparten algún deudor pendiente (un solo aviso por contacto). El primero de cada
    grupo es el representante: el de mayor importe pendiente (y, a igualdad, el más antiguo)."""
    ordenados = sorted(casos, key=lambda c: (-importe_pendiente(c), c.creado, c.id))
    grupos: list[tuple[set[str], list[Caso]]] = []
    for caso in ordenados:
        claves = {d.contraparte for d in pendientes(caso)}
        destino = next((g for g in grupos if claves & g[0]), None) if claves else None
        if destino is None:
            grupos.append((set(claves), [caso]))
        else:
            destino[0].update(claves)
            destino[1].append(caso)
    return [g[1] for g in grupos]


def decision_dudosa(propuesta: Propuesta) -> Decision:
    """Un caso dudoso nunca avisa: se silencia con su motivo legible hasta que la fase 2 lo resuelva."""
    return Decision(propuesta_id=propuesta.id, accion="silenciar", puntuacion=0.0, probabilidad_util=0.0,
                    motivos=[MOTIVO_DUDOSO], politica="caso-dudoso")


def de_propuesta(casos: Iterable[Caso], propuesta_id: str) -> list[Caso]:
    return [c for c in casos if c.propuesta_id == propuesta_id]
