"""
Lo que aprende Meisam de los gastos con amigos (curva-amigos.md §4.1; CONTRATO.md, «Curva de amigos»).

En una frase: «cuento, sitio a sitio y persona a persona, lo que me has contestado y lo que ha pasado con el dinero,
y lo voy olvidando poco a poco».

- **Dónde vas acompañado.** Beta-Bernoulli por comercio y por tipo de sitio y franja (`Acompanamiento`), con
  decaimiento exponencial (vida media `vida_media_dias`). Distingue tres cosas: ir solo, ir acompañado y que alguien
  te deba, e ir acompañado sin que nadie te deba (cada uno lo suyo, invitaste tú). Para preguntar solo cuenta
  p(alguien te debe): las dos últimas bajan igual hacia el silencio, pero se explican distinto.
- **Con quién y cómo repartís.** Hasta `max_grupos` `GrupoHabitual` por ámbito, con su forma de reparto.
- **Cuándo recordar a cada persona.** El p75 de sus devoluciones sin pedirlas (con >= 2); si no, el de su grupo;
  si no, el de siempre (2 días desde que se apunta el caso).
- **Cómo te paga.** El canal más frecuente («suele pagarte en efectivo»).

Reglas: funciones puras (devuelven copias; si no cambia nada, el mismo objeto), idempotentes por `EventoAmigos.id`,
sin nada por nombre de vida ni de comercio y sin importar el simulador. `modo = "reglas"`: ni aprende ni usa (lo de
antes del 11 nov); `modo = "fijo"`: usa lo que hay y no aprende (el oráculo). Las frases sobre personas son neutras y
de hechos, nunca juicios, y solo sirven para los recordatorios del propio usuario (no van a `memoria_para_agente`).

Todos los priors y umbrales están en `PARAMETROS` (también los de la escalera): se leen en cada llamada, así que el
bucle de ajuste (curva-amigos.md §4.6) puede cambiarlos sin tocar el código.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, get_args

from ..motor.normalizar import normalizar_comercio
from ..plataforma.privacidad import enmascarar_nombre
from ..plataforma.tipos import (
    Acompanamiento,
    AprendizajeAmigos,
    CanalDevolucion,
    Caso,
    Contacto,
    Deudor,
    EventoAmigos,
    FormaReparto,
    FrasePerfil,
    FuenteAprendizaje,
    Franja,
    GrupoHabitual,
    HabitoPersona,
    ModeloUsuario,
    PerfilUsuario,
)

CANALES = get_args(CanalDevolucion)

PARAMETROS: dict[str, Any] = {
    # --- Acompañamiento: Beta-Bernoulli por ámbito ---------------------------------------------------------------
    "prior_con": 1.0,                  # Beta(1, 1): sin datos, 50 % (las reglas fijas mandan hasta que hay evidencia)
    "prior_solo": 1.0,
    "vida_media_dias": 60,             # lo aprendido pesa la mitad a los 60 días: las rutinas cambian (exámenes, verano)
    "max_grupos": 5,                   # grupos habituales por ámbito
    "max_eventos_vistos": 500,         # ids recordados para la idempotencia
    "max_retrasos": 10,                # últimas devoluciones por persona
    # --- Cuándo recordar a cada persona ---------------------------------------------------------------------------
    "dias_general": 2,                 # lo de antes: 2 días desde que se apunta (casos.DIAS_ESPERA_PAGO_POR_OTRO)
    "min_obs_persona": 2,              # devoluciones propias para usar su p75
    "min_obs_grupo": 2,                # devoluciones del grupo para usar el p75 del grupo
    "margen_dias": 1,                  # se recuerda el día siguiente a su p75 (si para entonces no ha pagado)
    "dias_min_desde_hoy": 1,           # con lo aprendido, nunca el mismo día en que se apunta
    "dias_max_persona": 10,            # nadie espera más de 10 días a su primer recordatorio
    # --- Canal ------------------------------------------------------------------------------------------------------
    "min_obs_canal": 2,                # «suele pagarte en efectivo» con al menos 2 veces y más de la mitad
    # --- Motor y frases ----------------------------------------------------------------------------------------------
    "min_evidencia_motor": 1.5,        # pseudo-cuentas con decaimiento (~2 observaciones recientes) para el motor
    "min_evidencia_frase": 1.5,        # para enseñar una frase de un sitio
    # --- Escalera de la pregunta (escalera.py) -----------------------------------------------------------------------
    "min_evidencia_comercio": 1.0,     # con menos evidencia en el comercio se mira el tipo de sitio y la franja
    "p_solo_max": 0.25,                # nivel 0: casi siempre solo...
    "min_evidencia_silencio": 2.5,     # ...con ~3 observaciones recientes (tres «iba solo» semanales suman ~2,8)
    "p_preguntar": 0.6,                # sube a nivel 1 una señal débil si sueles ir acompañado...
    "min_evidencia_preguntar": 1.5,    # ...con ~2 observaciones recientes
    "p_media": 0.6,                    # nivel 2: resumen con sugerencia
    "min_evidencia_media": 1.5,
    "confianza_media": 0.4,            # p(acompañado) x peso del grupo
    "p_alta": 0.75,                    # nivel 3: notificación de un toque (3 de 3 recientes con Beta(1, 1): ~0,79)...
    "min_evidencia_alta": 2.5,
    "confianza_alta": 0.6,             # ...si la propuesta entera (personas) es probable e importe >= umbral
    "min_veces_grupo": 1.5,            # un grupo se sugiere si se ha visto ~2 veces (con decaimiento)
    "ignoradas_bajan": 2,              # cada 2 preguntas seguidas sin respuesta, un nivel menos
    "cuota_min": Decimal("0.50"),      # límites de un Bizum: fuera de ellos no se proponen cuotas
    "cuota_max": Decimal("1000"),
}

FRANJA_TEXTO = {"laborable": "entre semana", "viernes": "los viernes", "finde": "los fines de semana"}
TIPO_TEXTO = {"restaurante": "restaurantes", "bar": "bares", "ocio": "planes de ocio", "cafeteria": "cafeterías"}
FORMA_TEXTO = {"iguales": "a partes iguales", "por_consumo": "según lo que toma cada uno",
               "redondeo": "redondeando", "cada_uno_lo_suyo": "cada uno lo suyo"}
VIA_A_CANAL: dict[str, CanalDevolucion] = {"bizum": "bizum", "efectivo": "efectivo", "invitacion": "invitacion"}
ESCENARIOS_CON_DEUDA = ("pago_por_otro", "gasto_compartido")
CLAVE_SIN_DEUDA = "sin_deuda"          # Caso.hechos: lo pone la acción «nadie me debe» (A4)
TIPOS_SIN_AMBITO = ("", "desconocido")
CAMPOS_EDITABLES = ("retraso_dias", "canal")
_CENTIMO = Decimal("0.01")


# --- Claves y franjas ------------------------------------------------------------------------------------------

def franja_de(fecha: date) -> Franja:
    """Del día de la semana (el banco no da la hora): lunes-jueves `laborable`, viernes `viernes`, sábado y domingo
    `finde`."""
    dia = fecha.weekday()
    return "finde" if dia >= 5 else "viernes" if dia == 4 else "laborable"


def clave_comercio(texto: str | None) -> str | None:
    """El comercio como lo normaliza el motor («Telepizza Moncloa» -> «TELEPIZZA MONCLOA»); idempotente."""
    if not texto or not str(texto).strip():
        return None
    try:
        nombre = normalizar_comercio(str(texto), "")[0]
    except Exception:  # la normalización nunca rompe el aprendizaje
        nombre = None
    return (nombre or " ".join(str(texto).upper().split()))[:60] or None


def clave_tipo_franja(tipo: str | None, franja: str | None) -> str | None:
    if not tipo or tipo.strip().lower() in TIPOS_SIN_AMBITO or not franja:
        return None
    return f"{tipo.strip().lower()}|{franja}"


def vacio(apr: AprendizajeAmigos) -> bool:
    """Sin nada aprendido (ni sitios ni personas): se comporta como antes del 11 nov."""
    return not (apr.por_comercio or apr.por_tipo_franja or apr.personas)


def p75(valores: list[int]) -> int | None:
    """Percentil 75 por rango más cercano (entero, sin interpolar), como el motor y el perfil."""
    if not valores:
        return None
    ordenados = sorted(valores)
    return ordenados[max(0, -(-3 * len(ordenados) // 4) - 1)]


def _mediana_baja(valores: list[int]) -> int:
    ordenados = sorted(valores)
    return ordenados[(len(ordenados) - 1) // 2]


# --- Estimación de «fue acompañado» ---------------------------------------------------------------------------

#
# Tres resultados por ámbito, con los campos de `Acompanamiento`:
# - `solo`: fuiste solo;
# - `con_alguien`: fuiste acompañado (te deban o no);
# - de eso, «nadie te debía» (cada uno lo suyo, invitaste tú, lo pagó la empresa) es el peso `cada_uno_lo_suyo` de los
#   `repartos` de sus grupos; si no se sabe con quién, va a un grupo sin miembros que nunca se sugiere ni se recorta.
# Para preguntar solo cuenta p(alguien te debe) = (con deuda + prior) / (todo + priors): ir solo y «nadie me debe»
# bajan igual hacia el silencio, pero se aprenden y se explican por separado.

SIN_DEUDA: FormaReparto = "cada_uno_lo_suyo"


@dataclass(frozen=True)
class Estimacion:
    """Lo que sé de un ámbito: p(alguien te debe), p(acompañado), evidencia con decaimiento y observaciones reales."""
    p: float                    # p(alguien te debe algo): la que usa la escalera y el motor
    p_acompanado: float
    evidencia: float
    n: int
    ambito: str                 # "comercio:<X>" | "tipo:<tipo>|<franja>"
    es_comercio: bool
    solo: float                 # pseudo-cuentas, para explicar por qué se calla
    sin_deuda: float
    acomp: Acompanamiento


def sin_deuda_de(a: Acompanamiento) -> float:
    """Veces (con decaimiento) que fuiste acompañado y nadie te debía."""
    return min(sum(g.repartos.get(SIN_DEUDA, 0.0) for g in a.grupos), a.con_alguien)


def evidencia_de(a: Acompanamiento) -> float:
    return a.con_alguien + a.solo


def p_acompanado_de(a: Acompanamiento) -> float:
    P = PARAMETROS
    return (a.con_alguien + P["prior_con"]) / (evidencia_de(a) + P["prior_con"] + P["prior_solo"])


def p_de(a: Acompanamiento) -> float:
    """p(alguien te debe algo) en el ámbito: Beta(1, 1) con «solo» y «nadie me debe» como fracasos."""
    P = PARAMETROS
    return (a.con_alguien - sin_deuda_de(a) + P["prior_con"]) / (evidencia_de(a) + P["prior_con"] + P["prior_solo"])


def _estimacion(a: Acompanamiento, ambito: str, es_comercio: bool) -> Estimacion:
    return Estimacion(p_de(a), p_acompanado_de(a), evidencia_de(a), a.n, ambito, es_comercio, a.solo,
                      sin_deuda_de(a), a)


def estimar(apr: AprendizajeAmigos, comercio: str | None, tipo_comercio: str | None, fecha: date) -> Estimacion | None:
    """Mira primero el comercio; si sé poco de él, el tipo de sitio en esa franja («restaurantes los fines de semana»).
    None si no sé nada (entonces mandan las reglas de siempre)."""
    c = clave_comercio(comercio)
    a = apr.por_comercio.get(c) if c else None
    if a is not None and evidencia_de(a) >= PARAMETROS["min_evidencia_comercio"]:
        return _estimacion(a, f"comercio:{c}", True)
    t = clave_tipo_franja(tipo_comercio, franja_de(fecha))
    b = apr.por_tipo_franja.get(t) if t else None
    if b is not None and evidencia_de(b) > 0:
        return _estimacion(b, f"tipo:{t}", False)
    if a is not None and evidencia_de(a) > 0:
        return _estimacion(a, f"comercio:{c}", True)
    return None


def veces_con_deuda(g: GrupoHabitual) -> float:
    """Veces (con decaimiento) que fuiste con este grupo y alguien te debía."""
    return max(g.veces - g.repartos.get(SIN_DEUDA, 0.0), 0.0)


def grupo_con_deuda(a: Acompanamiento) -> GrupoHabitual | None:
    """El grupo (con miembros) con el que más veces te han debido dinero en el ámbito, si se ha visto ~2 veces."""
    candidatos = [g for g in a.grupos if g.miembros and veces_con_deuda(g) >= PARAMETROS["min_veces_grupo"]]
    if not candidatos:
        return None
    return min(candidatos, key=lambda g: (-veces_con_deuda(g), -(g.ultima or date.min).toordinal(), g.miembros))


def peso_grupo(a: Acompanamiento, g: GrupoHabitual) -> float:
    """Fracción de las veces con deuda del ámbito que fueron con ese grupo (0-1)."""
    total = max(a.con_alguien - sin_deuda_de(a), sum(veces_con_deuda(x) for x in a.grupos if x.miembros))
    return min(veces_con_deuda(g) / total, 1.0) if total > 0 else 0.0


def forma_con_deuda(g: GrupoHabitual) -> FormaReparto | None:
    """Cómo repartís con ese grupo cuando te deben (la forma de más peso, sin contar «cada uno lo suyo»)."""
    formas = [(v, k) for k, v in g.repartos.items() if k != SIN_DEUDA and v > 0]
    return max(formas)[1] if formas else None  # type: ignore[return-value]


def ambitos_de(apr: AprendizajeAmigos, comercio: str | None, tipo_comercio: str | None,
               fecha: date) -> list[Acompanamiento]:
    """Los ámbitos (comercio y tipo-franja) que existen para un pago, para leer `ignoradas` o los grupos."""
    c, t = clave_comercio(comercio), clave_tipo_franja(tipo_comercio, franja_de(fecha))
    return [x for x in (apr.por_comercio.get(c) if c else None, apr.por_tipo_franja.get(t) if t else None) if x]


# --- Aprender ----------------------------------------------------------------------------------------------------

def _copia(apr: AprendizajeAmigos) -> AprendizajeAmigos:
    """Copia con contenedores nuevos; las entradas se comparten hasta que se cambian (entonces se copian)."""
    return apr.model_copy(update={"por_comercio": dict(apr.por_comercio), "por_tipo_franja": dict(apr.por_tipo_franja),
                                  "personas": dict(apr.personas), "eventos_vistos": list(apr.eventos_vistos)})


def _factor(dias: int) -> float:
    return 0.5 ** (dias / PARAMETROS["vida_media_dias"])


def _decaer_ambito(a: Acompanamiento, f: float) -> Acompanamiento:
    grupos = [g.model_copy(update={"veces": g.veces * f, "repartos": {k: v * f for k, v in g.repartos.items()}})
              for g in a.grupos]
    return a.model_copy(update={"con_alguien": a.con_alguien * f, "solo": a.solo * f, "grupos": grupos})


def _decaer_en_copia(nuevo: AprendizajeAmigos, hoy: date) -> None:
    if nuevo.actualizado is None or hoy <= nuevo.actualizado:
        return
    f = _factor((hoy - nuevo.actualizado).days)
    nuevo.por_comercio = {k: _decaer_ambito(a, f) for k, a in nuevo.por_comercio.items()}
    nuevo.por_tipo_franja = {k: _decaer_ambito(a, f) for k, a in nuevo.por_tipo_franja.items()}
    nuevo.actualizado = hoy


def decaer(apr: AprendizajeAmigos, hoy: date) -> AprendizajeAmigos:
    """Olvida poco a poco: multiplica las pseudo-cuentas de cada sitio y grupo por 0,5^(días / vida media) desde
    `actualizado`. `n` (observaciones reales) no cambia. Solo en `modo = "aprende"`; si no hay nada que hacer, devuelve
    el mismo objeto. `aprender_evento` ya decae hasta la fecha de cada evento: llamarla a diario es opcional."""
    if apr.modo != "aprende" or apr.actualizado is None or hoy <= apr.actualizado:
        return apr
    nuevo = _copia(apr)
    _decaer_en_copia(nuevo, hoy)
    return nuevo


def _orden_grupo(g: GrupoHabitual) -> tuple:
    return (-g.veces, -(g.ultima or date.min).toordinal(), g.miembros)


def _recortar_grupos(a: Acompanamiento) -> None:
    """Deja `max_grupos` grupos con miembros (los de más peso) más el grupo sin miembros. Lo «sin deuda» de los que
    salen pasa al grupo sin miembros: así p(alguien te debe) no cambia al recortar."""
    con = sorted((g for g in a.grupos if g.miembros), key=_orden_grupo)
    anonimo = next((g for g in a.grupos if not g.miembros), None)
    sobran = con[PARAMETROS["max_grupos"]:]
    peso = sum(g.repartos.get(SIN_DEUDA, 0.0) for g in sobran)
    if peso > 0:
        if anonimo is None:
            anonimo = GrupoHabitual(miembros=[], veces=0.0)
        anonimo.veces += peso
        anonimo.repartos[SIN_DEUDA] = anonimo.repartos.get(SIN_DEUDA, 0.0) + peso
    a.grupos = con[:PARAMETROS["max_grupos"]] + ([anonimo] if anonimo is not None else [])


def _sumar_grupo(a: Acompanamiento, personas: list[str], forma: FormaReparto | None, fecha: date) -> None:
    """Suma una vez a un grupo exacto (miembros ordenados). Sin personas solo se apunta lo «sin deuda» (grupo sin
    miembros): una deuda con personas desconocidas no enseña nada de con quién."""
    miembros = sorted({p for p in personas if p})
    if not miembros and forma != SIN_DEUDA:
        return
    for g in a.grupos:
        if g.miembros == miembros:
            g.veces += 1.0
            g.ultima = max(g.ultima, fecha) if g.ultima else fecha
            if forma:
                g.repartos[forma] = g.repartos.get(forma, 0.0) + 1.0
            break
    else:
        a.grupos.append(GrupoHabitual(miembros=miembros, veces=1.0, ultima=fecha,
                                      repartos={forma: 1.0} if forma else {}))
    _recortar_grupos(a)


def _aprender_ambito(a: Acompanamiento, ev: EventoAmigos) -> Acompanamiento:
    a = a.model_copy(deep=True)
    if ev.fuente == "ignorada":
        a.ignoradas += 1
        return a
    a.n += 1
    a.ignoradas = 0
    a.ultima = max(a.ultima, ev.fecha) if a.ultima else ev.fecha
    if ev.acompanado:
        a.con_alguien += 1.0
        _sumar_grupo(a, ev.personas, ev.forma, ev.fecha)
    else:
        a.solo += 1.0
    if ev.sugerencia_aceptada is True:
        a.aceptadas_seguidas += 1
    elif ev.sugerencia_aceptada is False:
        a.aceptadas_seguidas = 0
    return a


def _aprender_persona(h: HabitoPersona, ev: EventoAmigos) -> HabitoPersona:
    P = PARAMETROS
    h = h.model_copy(deep=True)
    if ev.retraso_dias is not None and ev.canal != "invitacion":
        lista = h.retrasos_tras_pedir if ev.tras_pedir else h.retrasos_dias
        lista.append(int(ev.retraso_dias))
        del lista[:-P["max_retrasos"]]
    if ev.tras_pedir:
        h.paga_tras_pedir += 1
    else:
        h.paga_solo += 1
    if ev.canal and "canales" not in h.fijado_por_usuario:
        h.canales[ev.canal] = h.canales.get(ev.canal, 0) + 1
    if ev.redondeado:
        h.redondea += 1
    h.ultima = max(h.ultima, ev.fecha) if h.ultima else ev.fecha
    if "retraso_p75_dias" not in h.fijado_por_usuario:
        h.retraso_p75_dias = p75(h.retrasos_dias) if len(h.retrasos_dias) >= P["min_obs_persona"] else None
    return h


def aprender_evento(apr: AprendizajeAmigos, ev: EventoAmigos) -> AprendizajeAmigos:
    """Suma una observación. No hace nada (devuelve el mismo objeto) si `modo != "aprende"` o si el evento ya se vio.
    Antes de sumar, decae lo aprendido hasta la fecha del evento."""
    if apr.modo != "aprende" or ev.id in apr.eventos_vistos:
        return apr
    nuevo = _copia(apr)
    _decaer_en_copia(nuevo, ev.fecha)

    if ev.acompanado is not None or ev.fuente == "ignorada":
        c = clave_comercio(ev.comercio)
        franja = ev.franja or (franja_de(ev.fecha_pago) if ev.fecha_pago else None)
        t = clave_tipo_franja(ev.tipo_comercio, franja)
        if c:
            nuevo.por_comercio[c] = _aprender_ambito(nuevo.por_comercio.get(c) or Acompanamiento(), ev)
        if t:
            nuevo.por_tipo_franja[t] = _aprender_ambito(nuevo.por_tipo_franja.get(t) or Acompanamiento(), ev)

    if ev.contraparte and (ev.retraso_dias is not None or ev.canal is not None):
        previo = nuevo.personas.get(ev.contraparte) or HabitoPersona(contraparte=ev.contraparte)
        nuevo.personas[ev.contraparte] = _aprender_persona(previo, ev)

    nuevo.eventos_vistos.append(ev.id)
    del nuevo.eventos_vistos[:-PARAMETROS["max_eventos_vistos"]]
    nuevo.actualizado = max(nuevo.actualizado, ev.fecha) if nuevo.actualizado else ev.fecha
    return nuevo


def aprender_eventos(modelo: ModeloUsuario, eventos: list[EventoAmigos]) -> ModeloUsuario:
    """Pura: aplica los eventos en orden y devuelve una copia del modelo (o el mismo si no cambia nada)."""
    apr = modelo.aprendizaje
    for ev in eventos:
        apr = aprender_evento(apr, ev)
    return modelo if apr is modelo.aprendizaje else modelo.model_copy(update={"aprendizaje": apr})


# --- Construir eventos desde los casos ---------------------------------------------------------------------------

def _a_fecha(valor: Any) -> date | None:
    if isinstance(valor, date):
        return valor
    try:
        return date.fromisoformat(str(valor)[:10]) if valor else None
    except ValueError:
        return None


def _forma_de(deudores: list[Deudor]) -> FormaReparto | None:
    cuotas = [d.cuota for d in deudores if d.cuota is not None]
    if not cuotas:
        return None
    return "iguales" if max(cuotas) - min(cuotas) <= _CENTIMO else "por_consumo"


def _sugerencia_aceptada(caso_pregunta: Caso | None, deudores: list[Deudor]) -> bool | None:
    sug = caso_pregunta.sugerencia if caso_pregunta is not None else None
    if sug is None or not sug.personas:
        return None
    if {d.contraparte for d in deudores} != set(sug.personas):
        return False
    return all(abs(d.cuota - sug.cuotas[d.contraparte]) <= _CENTIMO for d in deudores if d.contraparte in sug.cuotas)


def evento_pago(caso: Caso, deudor: Deudor, hoy: date) -> EventoAmigos | None:
    """Una devolución de `deudor` en `caso` (Bizum, efectivo, invitación u otra vía), con su retraso: desde el pago si
    nadie se lo pidió y desde la solicitud si se le pidió. Mismo id venga del Bizum o del cierre (no cuenta dos veces)."""
    if deudor.estado != "saldada" or deudor.saldada is None:
        return None
    fecha_pago = _a_fecha(caso.hechos.get("fecha")) or caso.creado
    tras_pedir = deudor.pedida is not None and deudor.saldada >= deudor.pedida
    desde = deudor.pedida if tras_pedir else fecha_pago
    canal = VIA_A_CANAL.get(deudor.via_saldado or "") or ("bizum" if deudor.movimiento_pago else None)
    return EventoAmigos(id=f"pago:{caso.id}:{deudor.contraparte}", fuente="bizum" if canal == "bizum" else "cierre",
                        fecha=hoy, fecha_pago=fecha_pago, contraparte=deudor.contraparte,
                        retraso_dias=max((deudor.saldada - desde).days, 0), tras_pedir=tras_pedir, canal=canal)


def eventos_de_caso(antes: Caso | None, despues: Caso, fuente: FuenteAprendizaje, hoy: date,
                    tipo_comercio: str | None = None) -> list[EventoAmigos]:
    """Lo que enseña un cambio de un caso (respuesta, botón, chat, llamada, cierre o pregunta ignorada):
    - un `pago_individual` descartado («iba solo») -> fuiste solo; si el caso lleva `hechos["sin_deuda"]` (True o la
      lista de claves de con quién fue: «fui con gente pero nadie me debe») -> acompañado sin deuda;
    - un caso que pasa a (o nace como) `pago_por_otro` o `gasto_compartido` -> fuiste con esas personas, con la forma
      de reparto de sus cuotas y si aceptaste sin cambios la sugerencia con la que se preguntó;
    - cada persona que pasa a saldada -> su devolución (`evento_pago`);
    - `fuente = "ignorada"` -> la pregunta de ese pago se quedó sin respuesta.
    Una sola observación de compañía por caso (`acomp:<caso_id>`): la primera respuesta es la que cuenta."""
    hechos = {**(antes.hechos if antes else {}), **despues.hechos}
    fecha_pago = _a_fecha(hechos.get("fecha")) or despues.creado
    comun = {"fecha": hoy, "fecha_pago": fecha_pago, "comercio": clave_comercio(hechos.get("comercio")),
             "tipo_comercio": tipo_comercio or hechos.get("tipo_comercio"), "franja": franja_de(fecha_pago)}
    nivel = (antes.pregunta_nivel if antes is not None else None)
    if nivel is None:
        nivel = despues.pregunta_nivel
    eventos: list[EventoAmigos] = []

    if fuente == "ignorada":
        return [EventoAmigos(id=f"ign:{despues.id}", fuente="ignorada", nivel=nivel, **comun)]

    individual_antes = antes is not None and antes.escenario == "pago_individual" and antes.estado not in (
        "descartado", "saldado", "caducado")
    if individual_antes and despues.estado == "descartado" and despues.escenario in ("pago_individual", None):
        sin_deuda = despues.hechos.get(CLAVE_SIN_DEUDA)       # «fui con gente pero nadie me debe» (acción de A4)
        con_quien = sorted({str(p) for p in sin_deuda if p}) if isinstance(sin_deuda, list) else []
        eventos.append(EventoAmigos(id=f"acomp:{despues.id}", fuente=fuente, acompanado=bool(sin_deuda),
                                    personas=con_quien, forma=SIN_DEUDA if sin_deuda else None, nivel=nivel,
                                    sugerencia_aceptada=False if antes.sugerencia else None, **comun))
    elif (despues.escenario in ESCENARIOS_CON_DEUDA and despues.deudores
          and (antes is None or antes.escenario in ("pago_individual", None))):
        eventos.append(EventoAmigos(id=f"acomp:{despues.id}", fuente=fuente, acompanado=True, nivel=nivel,
                                    personas=sorted({d.contraparte for d in despues.deudores}),
                                    forma=_forma_de(despues.deudores),
                                    sugerencia_aceptada=_sugerencia_aceptada(antes or despues, despues.deudores),
                                    **comun))

    previos = {d.contraparte: d.estado for d in (antes.deudores if antes else [])}
    for d in despues.deudores:
        if d.estado == "saldada" and previos.get(d.contraparte) != "saldada":
            ev = evento_pago(despues, d, hoy)
            if ev is not None:
                eventos.append(ev)
    return eventos


def eventos_de_bizum(caso: Caso, deudor_antes: Deudor, deudor_despues: Deudor, hoy: date) -> list[EventoAmigos]:
    """Un Bizum (o transferencia) que salda a un deudor: su devolución. Nada si ya estaba saldado o no se salda."""
    if deudor_antes.estado == "saldada" or deudor_despues.estado != "saldada":
        return []
    ev = evento_pago(caso, deudor_despues, hoy)
    return [ev] if ev is not None else []


# --- Usar lo aprendido ---------------------------------------------------------------------------------------------

def _limitar(dias: int) -> int:
    return min(max(int(dias), 0), PARAMETROS["dias_max_persona"])


def retraso_persona(apr: AprendizajeAmigos, contraparte: str, grupo: list[str] | None = None,
                    perfil: PerfilUsuario | None = None) -> tuple[int, str]:
    """`(días desde el pago, fuente)`: lo que dijo el usuario o el p75 de la persona (con >= 2 devoluciones); si no,
    el p75 de las devoluciones de su grupo (las de este caso o los grupos del perfil); si no, `("general")` los 2
    días de siempre. Vacío o `modo = "reglas"` -> `(2, "general")`, como antes."""
    P = PARAMETROS
    if apr.modo == "reglas" or vacio(apr):
        return P["dias_general"], "general"
    h = apr.personas.get(contraparte)
    if h is not None and h.retraso_p75_dias is not None and (
            "retraso_p75_dias" in h.fijado_por_usuario or len(h.retrasos_dias) >= P["min_obs_persona"]):
        return _limitar(h.retraso_p75_dias), "persona"
    del_grupo = list(h.retrasos_dias) if h is not None else []
    for otro in grupo or []:
        if otro != contraparte and otro in apr.personas:
            del_grupo += apr.personas[otro].retrasos_dias
    if len(del_grupo) >= P["min_obs_grupo"]:
        return _limitar(p75(del_grupo) or 0), "grupo"
    if perfil is not None:
        for g in perfil.grupos:
            if contraparte in g.miembros and g.retraso_p75_dias is not None:
                return _limitar(g.retraso_p75_dias), "grupo"
    return P["dias_general"], "general"


def avisar_desde(apr: AprendizajeAmigos, contraparte: str, fecha_pago: date, hoy: date,
                 grupo: list[str] | None = None, perfil: PerfilUsuario | None = None) -> date:
    """Desde cuándo se le puede recordar a esta persona. Sin saber nada: `hoy + 2` (lo de antes). Sabiendo su retraso
    típico: el día siguiente a «pago + p75» (no se recuerda antes de que pague por su cuenta), nunca antes de mañana."""
    P = PARAMETROS
    dias, fuente = retraso_persona(apr, contraparte, grupo, perfil)
    if fuente == "general":
        return hoy + timedelta(days=P["dias_general"])
    return max(fecha_pago + timedelta(days=dias + P["margen_dias"]), hoy + timedelta(days=P["dias_min_desde_hoy"]))


def canal_probable(apr: AprendizajeAmigos, contraparte: str) -> CanalDevolucion | None:
    """El canal por el que suele devolverte el dinero (lo fijado por el usuario o >= 2 veces y más de la mitad).
    None si no se sabe, si hay empate o con `modo = "reglas"`."""
    if apr.modo == "reglas":
        return None
    h = apr.personas.get(contraparte)
    if h is None or not h.canales:
        return None
    orden = sorted(h.canales.items(), key=lambda kv: -kv[1])
    canal, veces = orden[0]
    if canal not in CANALES or (len(orden) > 1 and orden[1][1] == veces):
        return None
    if "canales" in h.fijado_por_usuario:
        return canal
    total = sum(h.canales.values())
    return canal if veces >= PARAMETROS["min_obs_canal"] and 2 * veces > total else None


def compania_para_motor(apr: AprendizajeAmigos) -> dict[str, float] | None:
    """`{"c:<COMERCIO>" | "t:<tipo>|<franja>": p}` de los ámbitos con evidencia suficiente, donde p es la de que
    alguien te deba (acompañado y con deuda: abrir un caso solo sirve entonces). None con `modo = "reglas"` o si no hay
    ninguno (el motor se comporta exactamente como antes)."""
    if apr.modo == "reglas":
        return None
    minimo = PARAMETROS["min_evidencia_motor"]
    salida = {f"c:{k}": round(p_de(a), 3) for k, a in apr.por_comercio.items() if evidencia_de(a) >= minimo}
    salida.update({f"t:{k}": round(p_de(a), 3) for k, a in apr.por_tipo_franja.items() if evidencia_de(a) >= minimo})
    return salida or None


# --- Lo que he aprendido de ti: ver, editar y borrar --------------------------------------------------------------

def nombre_persona(contraparte: str, contactos: dict[str, Contacto] | None = None) -> str:
    contacto = (contactos or {}).get(contraparte)
    return (contacto.nombre if contacto is not None and contacto.nombre else None) or enmascarar_nombre(contraparte)


def _nombre_sitio(comercio: str) -> str:
    return " ".join(p if (i and p in ("de", "del", "la", "el", "y")) else p.capitalize()
                    for i, p in enumerate(comercio.lower().split()))


def _texto_retraso(valores: list[int], p75_dias: int) -> str:
    """«a los 2 o 3 días», «el mismo día», «al día siguiente»... (mediana y p75 de sus devoluciones)."""
    med = _mediana_baja(valores)
    if p75_dias == 0:
        return "el mismo día"
    if med == p75_dias:
        return "al día siguiente" if med == 1 else f"a los {med} días"
    if med == 0 and p75_dias == 1:
        return "el mismo día o al siguiente"
    if p75_dias - med == 1:
        return f"a los {med} o {p75_dias} días"
    return f"entre {med} y {p75_dias} días después"


CANAL_TEXTO = {"efectivo": "suele pagarte en efectivo", "transferencia": "suele devolvértelo por transferencia",
               "invitacion": "suele compensarlo invitándote"}


def _partes_persona(h: HabitoPersona, apr: AprendizajeAmigos) -> tuple[list[str], bool]:
    """Hechos de una persona en frases cortas y neutras, y si se sabe su plazo («no te lo recuerdo antes»)."""
    P = PARAMETROS
    plazo = None
    if "retraso_p75_dias" in h.fijado_por_usuario and h.retraso_p75_dias is not None:
        plazo = f"en unos {h.retraso_p75_dias} días (me lo dijiste tú)"
    elif h.retraso_p75_dias is not None and len(h.retrasos_dias) >= P["min_obs_persona"]:
        plazo = _texto_retraso(h.retrasos_dias, h.retraso_p75_dias)
    canal = CANAL_TEXTO.get(canal_probable(apr, h.contraparte) or "")
    partes = []
    if canal:
        partes.append(f"{canal}, {plazo}" if plazo else canal)
    elif plazo:
        partes.append(f"suele devolvértelo {plazo}")
    if h.paga_tras_pedir >= P["min_obs_persona"] and h.paga_tras_pedir > h.paga_solo:
        partes.append("suele devolvértelo cuando se lo pides")
    if h.redondea >= P["min_obs_persona"]:
        partes.append("suele redondear lo que te devuelve")
    return partes, plazo is not None


def _unir(partes: list[str]) -> str:
    return partes[0] if len(partes) == 1 else ", ".join(partes[:-1]) + " y " + partes[-1]


def _frase_sitio(clave: str, a: Acompanamiento, donde: str, contactos: dict[str, Contacto] | None) -> FrasePerfil | None:
    P = PARAMETROS
    if evidencia_de(a) < P["min_evidencia_frase"] or a.n < 2:
        return None
    p = p_de(a)
    if p <= P["p_solo_max"]:
        texto = (f"{donde} cada uno suele pagar lo suyo: no te pregunto." if sin_deuda_de(a) > a.solo else
                 f"{donde} sueles ir solo: no te pregunto.")
    elif p >= P["p_media"]:
        texto = f"{donde} sueles pagar tú por más gente"
        g = grupo_con_deuda(a)
        if g is not None:
            texto += ", casi siempre con " + _unir([nombre_persona(m, contactos) for m in g.miembros])
            forma = forma_con_deuda(g)
            if forma:
                texto += f", y repartís {FORMA_TEXTO.get(forma, forma)}"
        texto += "."
        if a.rutina_aceptada:
            texto += " Abro el caso yo solo."
    else:
        return None
    return FrasePerfil(campo=f"sitios:{clave}", texto=texto, editable=False, borrable=True)


def frases_amigos(apr: AprendizajeAmigos, contactos: dict[str, Contacto] | None = None) -> list[FrasePerfil]:
    """«Lo que he aprendido de ti» sobre los gastos con amigos: una frase por persona («Rodrigo P. suele devolvértelo a
    los 2 o 3 días») y por sitio («En La Tasca sueles ir acompañado, casi siempre con Laura M. y Marcos R.»).
    Neutras y de hechos, nunca juicios. `campo` = `amigos:<contraparte>` o `sitios:<ámbito>` (para borrarlas).
    Con `modo = "reglas"` no hay nada que enseñar."""
    if apr.modo == "reglas":
        return []
    frases: list[FrasePerfil] = []
    for clave in sorted(apr.personas):
        h = apr.personas[clave]
        partes, con_plazo = _partes_persona(h, apr)
        if partes:
            texto = f"{nombre_persona(clave, contactos)} {_unir(partes)}."
            if con_plazo:
                texto += " No te lo recuerdo antes de ese plazo."
            frases.append(FrasePerfil(campo=f"amigos:{clave}", texto=texto, editable=True, borrable=True))
    for clave in sorted(apr.por_comercio):
        f = _frase_sitio(f"comercio:{clave}", apr.por_comercio[clave], f"En {_nombre_sitio(clave)}", contactos)
        if f:
            frases.append(f)
    for clave in sorted(apr.por_tipo_franja):
        tipo, _, franja = clave.partition("|")
        donde = f"{FRANJA_TEXTO.get(franja, franja).capitalize()}, en {TIPO_TEXTO.get(tipo, tipo)},"
        f = _frase_sitio(f"tipo:{clave}", apr.por_tipo_franja[clave], donde, contactos)
        if f:
            frases.append(f)
    return frases


def _sin_persona(a: Acompanamiento, contraparte: str) -> Acompanamiento:
    if not any(contraparte in g.miembros for g in a.grupos):
        return a
    fusion: dict[tuple[str, ...], GrupoHabitual] = {}
    for g in a.grupos:
        miembros = [m for m in g.miembros if m != contraparte]   # si se queda vacío, pasa al grupo sin miembros
        previo = fusion.get(tuple(miembros))
        if previo is None:
            fusion[tuple(miembros)] = g.model_copy(update={"miembros": miembros, "repartos": dict(g.repartos)})
        else:
            previo.veces += g.veces
            previo.ultima = max(d for d in (previo.ultima, g.ultima, date.min) if d)
            for k, v in g.repartos.items():
                previo.repartos[k] = previo.repartos.get(k, 0.0) + v
    nuevo = a.model_copy(update={"grupos": list(fusion.values())})
    _recortar_grupos(nuevo)
    return nuevo


def borrar_persona(apr: AprendizajeAmigos, contraparte: str) -> AprendizajeAmigos:
    """Olvida todo lo aprendido de una persona: su `HabitoPersona` y su presencia en los grupos habituales. Lo llama
    `DELETE /aprendido/amigos/{contraparte}` y borrar el contacto."""
    nuevo = _copia(apr)
    nuevo.personas.pop(contraparte, None)
    nuevo.por_comercio = {k: _sin_persona(a, contraparte) for k, a in nuevo.por_comercio.items()}
    nuevo.por_tipo_franja = {k: _sin_persona(a, contraparte) for k, a in nuevo.por_tipo_franja.items()}
    return nuevo


def borrar_sitio(apr: AprendizajeAmigos, clave: str) -> AprendizajeAmigos:
    """Olvida un ámbito: `comercio:<X>` o `tipo:<tipo>|<franja>` (también acepta `c:`/`t:` y `sitios:`). `KeyError`
    si no existe (la API lo convierte en 404)."""
    texto = clave.removeprefix("sitios:")
    tipo_ambito, _, valor = texto.partition(":")
    nuevo = _copia(apr)
    if tipo_ambito in ("comercio", "c") and (clave_comercio(valor) or valor) in nuevo.por_comercio:
        nuevo.por_comercio.pop(clave_comercio(valor) or valor)
    elif tipo_ambito in ("tipo", "t") and valor in nuevo.por_tipo_franja:
        nuevo.por_tipo_franja.pop(valor)
    else:
        raise KeyError(f"No he aprendido nada de {clave!r}.")
    return nuevo


def editar_persona(apr: AprendizajeAmigos, contraparte: str, campo: str, valor: Any) -> AprendizajeAmigos:
    """Corrige a mano lo aprendido de una persona; el código ya no lo pisa (`fijado_por_usuario`).
    - `retraso_dias`: entero de 0 a `dias_max_persona` («Rodrigo suele tardar 5 días»);
    - `canal`: `bizum | efectivo | transferencia | invitacion` («Pilar me paga en efectivo»).
    `ValueError` (en español) si el campo o el valor no valen."""
    if campo not in CAMPOS_EDITABLES:
        raise ValueError(f"Solo se puede cambiar: {', '.join(CAMPOS_EDITABLES)}.")
    nuevo = _copia(apr)
    h = (nuevo.personas.get(contraparte) or HabitoPersona(contraparte=contraparte)).model_copy(deep=True)
    if campo == "retraso_dias":
        if isinstance(valor, bool) or not isinstance(valor, int) or not 0 <= valor <= PARAMETROS["dias_max_persona"]:
            raise ValueError(f"Indica los días como un número entero de 0 a {PARAMETROS['dias_max_persona']}.")
        h.retraso_p75_dias = valor
        marca = "retraso_p75_dias"
    else:
        if valor not in CANALES:
            raise ValueError(f"El canal debe ser uno de: {', '.join(CANALES)}.")
        h.canales[valor] = max(h.canales.values(), default=0) + 1
        marca = "canales"
    if marca not in h.fijado_por_usuario:
        h.fijado_por_usuario.append(marca)
    nuevo.personas[contraparte] = h
    return nuevo
