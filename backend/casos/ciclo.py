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

import unicodedata
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, get_args

from ..plataforma.privacidad import enmascarar_nombre, enmascarar_texto
from ..plataforma.reloj import ahora_por_defecto
from ..plataforma.tipos import (AvisoCaso, CambioCaso, Caso, Decision, DecisionPregunta, Deudor, EscenarioDeuda,
                                Hipotesis, Momento, OrigenCambio, Propuesta)

DIAS_POSPONER = 2            # «ahora no»: se vuelve a mirar pasados 2 días
DIAS_COLA = 7                # un caso que llegó a su fecha y no avisó deja de esperar a los 7 días
DIAS_SOLICITUD = 7           # una solicitud de Bizum caduca a los 7 días naturales
DIAS_VIDA = 90               # un caso (y su amigo) se borra o caduca a los 90 días
TOLERANCIA = Decimal("0.50")  # un Bizum salda la cuota con ±0,50 €

ABIERTOS = ("abierto", "dudoso", "pedido", "caducado")   # casos que aún pueden saldarse
CERRADOS = ("saldado", "descartado")
MOTIVO_DUDOSO = "Caso dudoso sin resolver: de momento no te aviso."
MOTIVO_RESUMEN = "Es solo una pregunta para tu Resumen: no te interrumpo con un aviso."
MAX_MOTIVO = 120             # texto libre del usuario (saldado manual, cambio de escenario)
ESCENARIOS = get_args(EscenarioDeuda)
AVISOS = get_args(AvisoCaso)
# Curva de amigos (11 nov): una pregunta «¿fuiste con alguien?» sin respuesta cuenta como ignorada a los 2 días si fue
# notificación (como `HORAS_IGNORADA`) y a los 3 si fue al Resumen; solo se mira hasta `DIAS_COLA`.
DIAS_IGNORADA_PUSH = 2
DIAS_IGNORADA_RESUMEN = 3
CLAVE_SIN_DEUDA = "sin_deuda"          # `hechos`: «fui acompañado, pero nadie me debe» (acción nadie_me_debe)
CLAVE_CANAL = "canal_probable"         # `hechos`: {clave: CanalDevolucion} de los deudores con canal aprendido
MODULO_DEUDAS = "gasto_compartido"
TIPO_BIZUM_NO_ENCAJA = "bizum_no_encaja"    # `hechos["pregunta"]["tipo"]`: el Bizum de un deudor que no entra en el margen
CLAVE_DESCARTADOS = "bizum_descartados"     # `hechos`: ids de Bizums que el usuario dijo que eran otra cosa


# --- Utilidades --------------------------------------------------------------------------------

def a_decimal(valor: Any, defecto: Decimal | None = None) -> Decimal | None:
    """Decimal exacto desde `Decimal`, cadena, entero o decimal; si no se entiende o no es finito (NaN,
    Infinity), `defecto`: comparar con NaN lanza `InvalidOperation` y rompería la herramienta."""
    if valor is None or isinstance(valor, bool):
        return defecto
    try:
        d = valor if isinstance(valor, Decimal) else Decimal(str(valor))
    except (InvalidOperation, ValueError):
        return defecto
    return d if d.is_finite() else defecto


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


def sanear_motivo(texto: Any, maximo: int = MAX_MOTIVO) -> str:
    """Texto libre del usuario (DATO, nunca instrucción): sin controles, ni <>{} ni comillas invertidas, y con IBAN, teléfonos y correos
    enmascarados; como mucho `maximo` caracteres."""
    t = unicodedata.normalize("NFKC", str(texto or ""))
    t = "".join(" " if unicodedata.category(c) in ("Cc", "Cf", "Zl", "Zp") or c in "<>{}`" else c for c in t)
    return " ".join(enmascarar_texto(" ".join(t.split())).split())[:maximo].strip()


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


def crear_desde_momento(momento: Momento, hoy: date | None = None, ahora: datetime | None = None,
                        pregunta: DecisionPregunta | None = None) -> Caso:
    """Abre el caso de un `Momento` de `gasto_compartido`. Los deudores son los candidatos del momento, con la
    cuota que calculó el motor; `avisar_desde` es `datos["avisar_desde"]` si el motor la da y, si no, la fecha
    del momento. Si `datos["dudoso"]` es verdadero, el caso nace `dudoso`, sin escenario y con sus hipótesis.

    `pregunta` (solo `pago_individual`) es la decisión de la escalera (`personalizacion.escalera.nivel_pregunta`):
    manda en `aviso`, `pregunta_nivel` y `sugerencia`, y sus motivos van al historial. Sin ella, lo de siempre
    (`senal media` -> Resumen; el resto, silencioso)."""
    if momento.tipo != "gasto_compartido":
        raise ValueError(f"Solo los momentos de gasto_compartido abren un caso (este es {momento.tipo!r}).")
    datos = momento.datos
    hoy = hoy or momento.fecha
    cuando = ahora or ahora_por_defecto(hoy)
    # `pago_individual` (motor): un pago propio que quizá no lo era. No es un caso dudoso para la IA: la duda la
    # resuelve el usuario («¿fuiste con alguien?»). Nace abierto, sin deudores, y nunca hace push.
    individual = datos.get("origen") == "pago_individual"
    dudoso = bool(datos.get("dudoso")) and not individual
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
    for clave_hecho in ("comercio", "pago_id", "tipo_comercio"):
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
    # K1 d: personas estimadas por el precio por persona del sitio («19,00 € en Cines Fotograma son unas 2 entradas»).
    # Las cifras son del código (motor); el motivo es una frase del código con el nombre del comercio (dato, saneado).
    if isinstance(datos.get("personas_estimadas"), int) and not isinstance(datos.get("personas_estimadas"), bool):
        hechos["personas_estimadas"] = datos["personas_estimadas"]
    precio_persona = a_decimal(datos.get("precio_persona"))
    if precio_persona is not None:
        hechos["precio_persona"] = eur_texto(precio_persona)
    motivo_personas = sanear_motivo(datos.get("motivo_personas"), MAX_MOTIVO) if datos.get("motivo_personas") else ""
    if motivo_personas:
        hechos["motivo_personas"] = motivo_personas

    origen_pago = datos.get("movimiento_origen") or datos.get("pago_id")
    if isinstance(origen_pago, str):
        hechos["movimiento_origen"] = origen_pago
    escenario = datos.get("escenario") if datos.get("escenario") in ESCENARIOS else "gasto_compartido"
    aviso = datos.get("aviso") if datos.get("aviso") in AVISOS else "notificar"
    nivel, sugerencia = None, None
    if individual:
        escenario = "pago_individual"
        aviso = "resumen" if datos.get("senal") == "media" else "silencioso"
        if pregunta is not None:
            aviso, nivel, sugerencia = pregunta.aviso, pregunta.nivel, pregunta.sugerencia
    caso = Caso(id=f"caso-{momento.id}", usuario_id=momento.usuario_id,
                escenario=None if dudoso else escenario, aviso=aviso,
                estado="dudoso" if dudoso else "abierto", momento_id=momento.id, creado=hoy,
                avisar_desde=_a_fecha(datos.get("avisar_desde")) or momento.fecha, hechos=hechos,
                hipotesis=hipotesis if dudoso else [], deudores=deudores, pregunta_nivel=nivel,
                sugerencia=sugerencia)
    _anotar(caso, "codigo", "Caso dudoso: sin avisar hasta resolver el reparto." if dudoso else
            ("Pago propio que quizá fue con alguien: " + ("se pregunta con una notificación de un toque."
                                                          if aviso == "notificar" else
                                                          "solo se pregunta en el Resumen.")) if individual else
            "Caso abierto: falta por devolver una parte del gasto.", cuando)
    if motivo_personas:
        _anotar(caso, "codigo", f"Personas estimadas por el precio del sitio: {motivo_personas}", cuando)
    if individual and pregunta is not None and pregunta.motivos:
        _anotar(caso, "codigo", f"Escalera de la pregunta, nivel {pregunta.nivel}: " + " ".join(pregunta.motivos), cuando)
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


def aplicar_respuesta(caso: Caso, respuesta: str, hoy: date, ahora: datetime | None = None,
                      origen: OrigenCambio = "llamada") -> Caso:
    """El usuario contesta la pregunta pendiente de un caso `dudoso` (`hechos["pregunta"]`, estado `pendiente`).
    `si`: los candidatos de la pregunta quedan fuera del reparto (p. ej. Daniel pagó también lo de Marcos) y el caso
    se abre con los demás; si no queda nadie, se descarta. `no`: se deja a todos y el caso se abre. Quita `propuesta_id`
    para que el portero prepare una propuesta nueva con los deudores definitivos. Rastro en `historial`. Nunca toca
    cuotas ni mueve dinero. `ValueError` (en español) si no hay pregunta pendiente o la respuesta no es sí o no."""
    pregunta = caso.hechos.get("pregunta")
    bizum = isinstance(pregunta, dict) and pregunta.get("tipo") == TIPO_BIZUM_NO_ENCAJA
    if not isinstance(pregunta, dict) or pregunta.get("estado") != "pendiente" or (caso.estado != "dudoso" and not bizum):
        raise ValueError("Este caso no tiene ninguna pregunta pendiente que responder.")
    texto = "".join(c for c in unicodedata.normalize("NFD", str(respuesta or "").strip().lower()) if unicodedata.category(c) != "Mn")
    if texto not in ("si", "no"):
        raise ValueError("La respuesta debe ser sí o no.")
    cuando = ahora or ahora_por_defecto(hoy)
    if bizum:
        return _responder_bizum(caso, pregunta, texto, hoy, cuando, origen)
    nuevo = _copia(caso)
    candidatos = {c for c in (_clave(x) for x in pregunta.get("candidatos", [])) if c}
    nuevo.hechos["pregunta"] = {**pregunta, "estado": "respondida", "respuesta": texto}
    quitados = [d for d in nuevo.deudores if d.contraparte in candidatos] if texto == "si" else []
    if quitados:
        nuevo.deudores = [d for d in nuevo.deudores if d.contraparte not in candidatos]
        quien = ", ".join(nombre_visible(d.contraparte) for d in quitados)
        if not nuevo.deudores:
            _anotar(nuevo, origen, f"Respondiste que sí: {quien} ya estaba cubierto y no queda nadie por cobrar.", cuando)
            return descartar(nuevo, hoy, "no queda nadie por cobrar.", origen, cuando)
        _anotar(nuevo, origen, f"Respondiste que sí: se quita a {quien} del reparto.", cuando)
    else:
        _anotar(nuevo, origen, "Respondiste que no: se deja a todos en el reparto." if texto == "no" else
                "Respondiste que sí: no hay a quién quitar del reparto.", cuando)
    nuevo.escenario = next((h.escenario for h in nuevo.hipotesis if h.escenario in ESCENARIOS), None) or "gasto_compartido"
    nuevo.estado = "abierto"
    nuevo.propuesta_id = None
    nuevo.hechos.pop("avisado_el", None)
    nuevo.hechos["resuelto_por"] = origen
    nuevo.hechos["faltan"] = len(pendientes(nuevo))
    nuevo.hechos["importe_pendiente"] = eur_texto(importe_pendiente(nuevo))
    return nuevo


def _responder_bizum(caso: Caso, pregunta: dict, texto: str, hoy: date, cuando: datetime, origen: OrigenCambio) -> Caso:
    """Respuesta a «Marcos te ha enviado 25 €: ¿es lo de La Tasca (24 €)?». `si`: ese Bizum salda a esa persona (la cuota
    sigue siendo la del código; no se mueve dinero). `no`: el deudor sigue como estaba y ese Bizum no se vuelve a
    preguntar. Un deudor que ya no está pendiente (saldado a mano, fuera del reparto) solo cierra la pregunta."""
    clave, mov = _clave(pregunta.get("contraparte")), str(pregunta.get("movimiento") or "")
    nuevo = _copia(caso)
    nuevo.hechos["pregunta"] = {**pregunta, "estado": "respondida", "respuesta": texto}
    deudor = next((d for d in nuevo.deudores if d.contraparte == clave and d.estado != "saldada"), None)
    nombre = nombre_visible(clave or "")
    if texto == "no":
        nuevo.hechos[CLAVE_DESCARTADOS] = [*nuevo.hechos.get(CLAVE_DESCARTADOS, []), mov]
        _anotar(nuevo, origen, f"Respondiste que el Bizum de {nombre} era otra cosa: su deuda sigue como estaba.", cuando)
        return nuevo
    if deudor is None:
        _anotar(nuevo, origen, f"Respondiste que sí, pero {nombre} ya no tenía nada pendiente.", cuando)
        return nuevo
    deudor.estado, deudor.saldada, deudor.movimiento_pago = "saldada", _a_fecha(pregunta.get("fecha")) or hoy, mov or None
    nuevo.hechos["movimientos"] = [*nuevo.hechos.get("movimientos", []), *([mov] if mov else [])]
    _anotar(nuevo, origen, f"Respondiste que sí: el Bizum de {nombre} salda su parte ({pregunta.get('importe')} €).", cuando)
    if all(d.estado == "saldada" for d in nuevo.deudores):
        nuevo.estado = "saldado"
        _anotar(nuevo, origen, "Caso saldado.", cuando)
    nuevo.hechos["faltan"] = len(pendientes(nuevo))
    nuevo.hechos["importe_pendiente"] = eur_texto(importe_pendiente(nuevo))
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

def fecha_aviso(caso: Caso) -> date:
    """Desde cuándo puede avisar el caso: su `avisar_desde` y, si algún deudor pendiente tiene el suyo
    (`Deudor.avisar_desde`, su retraso típico aprendido), el más tardío. Un solo aviso por caso: así nadie recibe un
    recordatorio antes de cuando suele pagar por su cuenta (quien paga antes ya no estará pendiente). Lo aprendido solo
    retrasa: nunca adelanta el plazo del caso ni un «ahora no»."""
    desde = caso.avisar_desde or caso.creado
    propias = [d.avisar_desde for d in pendientes(caso) if d.avisar_desde is not None]
    return max([desde, *propias])


def listo_para_avisar(caso: Caso, hoy: date) -> bool:
    """¿Entra hoy en el portero? Abierto, con su fecha cumplida (`fecha_aviso`, que respeta el plazo de cada persona),
    sin avisar aún y con menos de 7 días de espera. Un caso `dudoso` solo entra una vez (sin propuesta) para dejar su
    decisión silenciada y a la vista."""
    desde = fecha_aviso(caso)
    if desde > hoy or caso.aviso == "silencioso":   # silencioso: solo se ve en «Mis cuentas», nunca avisa
        return False
    pregunta = caso.hechos.get("pregunta")
    if isinstance(pregunta, dict) and pregunta.get("tipo") == TIPO_BIZUM_NO_ENCAJA and pregunta.get("estado") == "pendiente":
        return False                                # un Bizum sin aclarar: no se recuerda la deuda hasta que responda
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


def limitar_aviso(caso: Caso, decision: Decision) -> Decision:
    """`Caso.aviso` es el tope: un caso `resumen` nunca llega al usuario como aviso (push), solo a la bandeja Resumen."""
    if caso.aviso == "resumen" and decision.accion == "notificar_ahora":
        return decision.model_copy(update={"accion": "resumen", "motivos": [*decision.motivos, MOTIVO_RESUMEN]})
    return decision


def de_propuesta(casos: Iterable[Caso], propuesta_id: str) -> list[Caso]:
    return [c for c in casos if c.propuesta_id == propuesta_id]


# --- Curva de amigos (11 nov): plazos por persona, pregunta de nivel 3 e ignoradas ----------------

def fijar_plazos(caso: Caso, plazos: dict[str, date], canales: dict[str, str], hoy: date,
                 ahora: datetime | None = None) -> Caso:
    """Pura. `plazos` = `{clave: fecha}` desde la que se puede recordar a cada deudor (lo calcula el orquestador con
    `aprende_amigos.avisar_desde`); `canales` = `{clave: canal}` por el que suele pagar (`hechos["canal_probable"]`).
    Solo toca a deudores pendientes. Deja rastro legible. Sin nada que cambiar, devuelve el mismo caso."""
    pend = {d.contraparte for d in pendientes(caso)}
    plazos = {k: v for k, v in plazos.items() if k in pend}
    canales = {k: v for k, v in canales.items() if k in {d.contraparte for d in caso.deudores}}
    previos = caso.hechos.get(CLAVE_CANAL) if isinstance(caso.hechos.get(CLAVE_CANAL), dict) else {}
    cambia_plazo = any(d.avisar_desde != plazos[d.contraparte] for d in caso.deudores if d.contraparte in plazos)
    if not cambia_plazo and (not canales or {**previos, **canales} == previos):
        return caso
    nuevo = _copia(caso)
    cuando = ahora or ahora_por_defecto(hoy)
    for d in nuevo.deudores:
        if d.contraparte in plazos and d.avisar_desde != plazos[d.contraparte]:
            d.avisar_desde = plazos[d.contraparte]
            _anotar(nuevo, "codigo", f"{nombre_visible(d.contraparte)} suele devolverlo más tarde: no se lo recuerdo "
                                     f"antes del {d.avisar_desde.isoformat()}.", cuando)
    if canales:
        nuevo.hechos[CLAVE_CANAL] = {**previos, **canales}
    return nuevo


def _eur_corto(valor: Decimal) -> str:
    """16 -> «16 €»; 16.5 -> «16,50 €» (cifras del código)."""
    valor = valor.quantize(Decimal("0.01"))
    return f"{int(valor)} €" if valor == valor.to_integral_value() else eur_texto(valor).replace(".", ",") + " €"


def _nombre_comercio(texto: Any) -> str:
    """«LA TASCA» -> «La Tasca» (dato de un tercero, saneado)."""
    limpio = sanear_motivo(texto or "", 40)
    return " ".join(p if (i and p in ("de", "del", "la", "el", "y")) else p.capitalize()
                    for i, p in enumerate(limpio.lower().split())) or "este pago"


def _nombres_cortos(claves: list[str], nombres: dict[str, str] | None) -> list[str]:
    """El nombre de pila de la agenda («Laura»); si dos coinciden, el nombre enmascarado completo («Laura M.»)."""
    completos = [sanear_motivo((nombres or {}).get(c) or nombre_visible(c), 30) for c in claves]
    pila = [n.split()[0] if n.split() else n for n in completos]
    return [p if pila.count(p) == 1 else n for p, n in zip(pila, completos)]


def _lista(nombres: list[str]) -> str:
    return nombres[0] if len(nombres) == 1 else ", ".join(nombres[:-1]) + " y " + nombres[-1]


def texto_pregunta(caso: Caso, nombres: dict[str, str] | None = None) -> str:
    """La pregunta de un toque del nivel 3: «48 € en La Tasca: ¿con Laura y Marcos, 16 € cada uno?». Cifras del
    caso y de la sugerencia (código); sin sugerencia con cuotas, la pregunta genérica."""
    total = a_decimal(caso.hechos.get("importe_total"))
    sitio = _nombre_comercio(caso.hechos.get("comercio"))
    cabeza = f"{_eur_corto(total)} en {sitio}" if total is not None else f"Tu pago en {sitio}"
    sug = caso.sugerencia
    if sug is None or not sug.personas:
        n = caso.hechos.get("personas_estimadas")       # K1 d: por el precio por persona del sitio
        pista = f" (unas {n} personas)" if isinstance(n, int) and not isinstance(n, bool) and n >= 2 else ""
        return f"{cabeza}: ¿fuiste con alguien?{pista}"
    quienes = _lista(_nombres_cortos(list(sug.personas), nombres))
    cuotas = {sug.cuotas[p] for p in sug.personas if p in sug.cuotas}
    if len(cuotas) == 1 and len(sug.cuotas) == len(sug.personas):
        return f"{cabeza}: ¿con {quienes}, {_eur_corto(next(iter(cuotas)))} cada uno?"
    return f"{cabeza}: ¿con {quienes}?"


def propuesta_pregunta(caso: Caso, ahora: datetime, nombres: dict[str, str] | None = None) -> Propuesta:
    """Nivel 3 de la escalera: propuesta de SOLO PREGUNTAR (como `prop-duda-*`: la única acción es `recordar`, no mueve
    dinero). Pasa por `decidir` y el tope de avisos como cualquier otra; si el usuario dice que sí, la llamada o la app
    convierten el caso con `con_personas` (las cuotas, del código). El comercio va marcado como dato."""
    from ..modulos.plantillas import CABECERA_DATOS

    texto = texto_pregunta(caso, nombres)
    sug = caso.sugerencia
    en_juego = sum((v for v in (sug.cuotas.values() if sug else [])), Decimal("0")) or None
    sitio = _nombre_comercio(caso.hechos.get("comercio"))
    return Propuesta(
        id=f"prop-preg-{caso.id}", modulo_id=MODULO_DEUDAS, momento_id=caso.momento_id or caso.id,
        usuario_id=caso.usuario_id, titulo="¿Fuiste con alguien?", mensaje_notificacion=texto,
        contexto_llamada=(f"{CABECERA_DATOS} Meisam cree que el usuario pagó por más gente en <datos>{sitio}</datos>. "
                          "Haz solo esta pregunta y no propongas pedir dinero hasta que responda: "
                          f"<datos>{texto}</datos> Si dice que sí, apunta a esas personas con con_personas; si iba "
                          "solo, iba_solo; si fue con gente pero nadie le debe, nadie_me_debe."),
        acciones_ofrecidas=[{"accion_id": "recordar",
                             "parametros": {"cuando": "+1d", "texto": "Mirar con quién fui a este pago"}}],
        valor_estimado_eur=en_juego, urgencia="media", tipo_momento="gasto_compartido",
        comercio=caso.hechos.get("comercio") if isinstance(caso.hechos.get("comercio"), str) else None,
        contraparte=sug.personas[0] if sug and sug.personas else None,
        confianza=max(min(sug.confianza if sug else 0.0, 1.0), 0.0), creada=ahora)


def pregunta_sin_respuesta(caso: Caso, hoy: date) -> bool:
    """¿La pregunta «¿fuiste con alguien?» de este `pago_individual` lleva sin respuesta lo bastante para contar como
    ignorada? 2 días si fue notificación y 3 si fue al Resumen, y solo dentro de `DIAS_COLA` (el evento es idempotente
    por caso: `ign:<caso_id>`). Silencioso o cerrado: no se preguntó."""
    if caso.escenario != "pago_individual" or caso.estado != "abierto" or caso.aviso == "silencioso":
        return False
    edad = (hoy - (caso.avisar_desde or caso.creado)).days
    minimo = DIAS_IGNORADA_PUSH if caso.aviso == "notificar" else DIAS_IGNORADA_RESUMEN
    return minimo <= edad <= DIAS_COLA
