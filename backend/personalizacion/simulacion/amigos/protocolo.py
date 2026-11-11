"""
Protocolo de la curva de amigos (C5; `docs/diseno/curva-amigos.md` §4.3-§4.5; CONTRATO.md, «Curva de amigos»).

Bucle de 8 semanas SOBRE EL SISTEMA REAL con el reloj simulado. Por cada (vida, semilla, política):

    orquestador.cargar_simulacion(uid, movimientos_base, activación - 1 día, contactos, modelo con `aprendizaje.modo`)
    orquestador.activar(uid, ["gasto_compartido"], {copiloto, memoria})
    cada día D de la activación (lunes 2026-10-05) al fin (domingo 2026-11-29):
        orquestador.avanzar_dia(uid, D)          -> el motor, los casos, el portero y la política deciden SOLOS
        el usuario simulado mira lo que hay (casos.cargar, orquestador.notificaciones) y reacciona según su verdad
        oculta y el azar común de `VidaGenerada.azar(clave)`; lo que hace va por las funciones del sistema:
            actualizar_caso_llamada (iba_solo, nadie_me_debe, con_personas, no_me_debe, marcar_saldado)
            registrar_feedback (en persona / lo deja / no recordar / «no me preguntes por este sitio»)
            preparar_accion + confirmar_accion (pedir Bizum confirmado, como el botón)
            chat_casos.apuntar_gasto_usuario y recordar_sobre_mi_usuario
        el amigo paga tras una solicitud según sus rasgos: orquestador.anadir_movimientos (siempre con fecha > hoy)

Sin mirar el futuro: el sistema solo recibe los movimientos día a día (`pendientes` del orquestador) y los Bizums
reactivos se añaden con fecha posterior a hoy (el orquestador rechaza el pasado). La verdad oculta solo la leen el
usuario simulado (que conoce su propia vida hasta hoy) y el registro, para que C6 pueda medir.

Políticas (la política nunca importa el simulador; solo lee `ModeloUsuario.aprendizaje.modo`):
    reglas                  modo `reglas`  (ni aprende ni usa; el chat crea casos igual)
    personalizada           modo `aprende`
    personalizada_sin_chat  modo `aprende`, sin mensajes de chat
Todas ven la misma suerte: cada reacción usa `VidaGenerada.azar(<clave del evento>)`.

Entorno: `entorno_simulacion()` pone `DATOS_USUARIO_DIR` en una carpeta temporal, `BUSQUEDA_WEB=off` y `DUDAS_IA=off`
y los restaura al salir. Nunca toca `datos_usuario/` ni `.env`.

Cuándo responde el usuario: lo ve el día D a las 20:30 (tras `avanzar_dia`); tarda `h` horas
(`meisam.retraso_respuesta_horas`) y actúa tras `avanzar_dia(D + h // 24)`. Con `h > 48` no contesta (ignorada).

======================================================================================================
REGISTRO (lo usa C6 para las 7 medidas de §4.4). `ResultadoSimulacion.eventos`: lista de dicts JSON, en orden.
Campos comunes: `tipo`, `dia` (ISO), `semana` (1-8; 9 = eventos finales), `vida`, `semilla`, `politica`.
Importes como cadenas con 2 decimales. Claves de persona como el alias de Bizum («RODRIGO P»).
------------------------------------------------------------------------------------------------------
Durante el bucle
  pago          (VERDAD) cargo con tarjeta del día. pago_id, comercio, importe, acompanado, forma, plan_id,
                gasto_solo_id, deudores {clave: cuota}, por_persona {clave: {dia_pagaria_solo, canal, no_paga,
                paga_solo, pagado_por, retraso_tras_pedir_dias}}
  caso          caso nuevo visto en el sistema. caso_id, pago_id, origen (motor|boton|chat|None), escenario,
                estado, aviso, pregunta_nivel, sugerencia {personas, cuotas}|None, deudores [claves]
  silencio      Meisam calla (pago_individual silencioso = nivel 0). caso_id, pago_id, nivel, habria_sido_util
  pregunta      Meisam pregunta por un pago (pago_individual en resumen o push). caso_id, pago_id, nivel (1-3),
                canal (push|resumen), sugerencia, sugerencia_correcta (bool|None), inutil
                (None|iba_solo|nadie_debe|ya_pagado|duplicada; de la verdad, hasta hoy)
  respuesta     el usuario contesta. caso_id, pago_id, nivel, accion (iba_solo|nadie_me_debe|con_personas), personas,
                importe, sugerencia_aceptada (bool|None), ruido (contestó contra su verdad), retraso_horas,
                inutil, ok, error, fuera_de_agenda [claves]
  ignorada      objeto (pregunta|aviso), caso_id|propuesta_id, pago_id, motivo
                (no_contesta|tarde|tolerancia|harto|duplicada|cerrado)
  aviso         el portero avisa de una deuda (decisión notificar_ahora = push, resumen = resumen). propuesta_id,
                casos [ids], pago_id, canal, personas [{clave, cuota, deudor_verdad, a_destiempo, ya_devuelto}]
                a_destiempo = hoy < dia_pagaria_solo (el amigo iba a pagar solo más tarde)
  accion_aviso  qué hace el usuario con el aviso. propuesta_id, pago_id, modo
                (pide_bizum|se_lo_dice_en_persona|lo_deja), retraso_horas
  solicitud     pedir_bizum confirmado. propuesta_id, caso_id, pago_id, contraparte, importe, ok, a_destiempo
  reclamo       se lo pide en persona. pago_id, contraparte, a_destiempo
  reaccion      el amigo pagará tras la solicitud. pago_id, contraparte, llega (fecha), canal, importe, cubre
  cobro         dinero devuelto ese día (banco o efectivo). pago_id, contraparte, importe, canal,
                origen (solo|pedido), cubre [claves cuya parte incluye]
  efectivo      el usuario marca «ya me lo dio». pago_id, contraparte, caso_id, declara (bool), ok
  correccion    el usuario quita a alguien de un caso. caso_id, pago_id, contraparte, motivo (no_es_deudor|no_recordar)
  feedback      registrar_feedback. propuesta_id, resultado
  silencia      el usuario pulsa «no me preguntes por este sitio». caso_id, pago_id, comercio, con_propuesta
  chat          mensaje del usuario. entrada_id, tipo_entrada, pago_id, herramienta, resultado,
                esperado_resultado, caso_id, extraccion (etiqueta|grabada), omitido (motivo|None), reintento
  cierre        un caso se cierra. caso_id, pago_id, estado, deudores [{clave, estado, via}]
  toque         cada gesto del usuario (esfuerzo). caso_id, pago_id, que (respuesta|solicitud|efectivo|
                correccion|feedback|chat|silencia)
  error         excepción inesperada del sistema (no de negocio). donde, error. Debe ser 0.
  saltado       pieza que aún no existe (una vez por pieza). pieza, motivo
Al final (semana 9)
  deuda         una por (pago, persona) con cuota en las semanas activas: pago_id, fecha_pago, contraparte, cuota,
                canal, no_paga, paga_solo, dia_pagaria_solo, devuelto_el, declarado, reclamado_el, en_caso_el,
                recordado_el, primer_recordatorio_a_destiempo, dias_hasta_cobrar, observable_21
                (fecha_pago + 21 <= fin: solo esas cuentan para «dinero que se escapa»)
  caso_final    caso_id, pago_id, origen, escenario, estado, aviso, pregunta_nivel, creado, deudores
                [{clave, cuota, estado, via, saldada}], toques, cerrado_solo (saldado por Bizum sin toques)
  fin           aprendizaje: modo, n_comercios, n_tipo_franja, n_personas, n_eventos, vacio (bool); duracion_s
======================================================================================================

Uso:
    python -m backend.personalizacion.simulacion.amigos.protocolo --vida alvaro --semilla 0
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import tempfile
import time
from collections import Counter, defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any, Callable, Iterator

from ....plataforma.tipos import ApuntarGastoEntrada, Feedback, ModeloUsuario
from .esquema import RAIZ, Corpus, Vida, cargar_vidas
from .generador import Reaccion, VerdadPago, VidaGenerada, generar

POLITICAS = ("reglas", "personalizada", "personalizada_sin_chat")
MODO = {"reglas": "reglas", "personalizada": "aprende", "personalizada_sin_chat": "aprende", "oraculo": "fijo"}
CON_CHAT = {"reglas": True, "personalizada": True, "personalizada_sin_chat": False, "oraculo": True}
MODULOS = ["gasto_compartido"]
CONSENTIMIENTOS = {"copiloto": True, "memoria": True}
HORAS_IGNORADA = 48
TOLERANCIA_IMPORTE = Decimal("0.50")
CENT = Decimal("0.01")
RUTA_EXTRACCION = RAIZ / "evals" / "datos" / "chat_amigos_extraccion.json"
FINALES = ("deuda", "caso_final", "fin")
SEMANA_FINAL = 9
CERRADOS = ("saldado", "descartado")


# --- Entorno -----------------------------------------------------------------------------------

@contextmanager
def entorno_simulacion(dir_datos: str | Path | None = None, en_memoria: bool = True) -> Iterator[Path]:
    """`DATOS_USUARIO_DIR` temporal (o `dir_datos`), sin web y sin IA de dudas; restaura el entorno al salir.
    Si crea la carpeta, la borra al terminar. Por defecto el almacén va en memoria (`ALMACEN_EN_MEMORIA`, ~3x más
    rápido); `en_memoria=False` lo deja en disco (la carpeta temporal)."""
    from ....plataforma import almacenamiento
    claves = ("DATOS_USUARIO_DIR", "BUSQUEDA_WEB", "DUDAS_IA", "ALMACEN_EN_MEMORIA")
    previo = {k: os.environ.get(k) for k in claves}
    propia = dir_datos is None
    carpeta = Path(tempfile.mkdtemp(prefix="sim-amigos-")) if propia else Path(dir_datos)
    carpeta.mkdir(parents=True, exist_ok=True)
    os.environ.update(DATOS_USUARIO_DIR=str(carpeta), BUSQUEDA_WEB="off", DUDAS_IA="off",
                      ALMACEN_EN_MEMORIA="on" if en_memoria else "off")
    try:
        yield carpeta
    finally:
        almacenamiento.vaciar_memoria()
        for k, v in previo.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        if propia:
            shutil.rmtree(carpeta, ignore_errors=True)


# --- Utilidades --------------------------------------------------------------------------------

def _eur(valor: Decimal | None) -> str | None:
    return None if valor is None else f"{Decimal(valor).quantize(CENT):.2f}"


def _iso(d: date | None) -> str | None:
    return d.isoformat() if d else None


def _elegir(dist: dict, u: float) -> Any:
    """Valor de una distribución discreta con un número ya sorteado (`u` en [0, 1))."""
    claves = sorted(dist, key=lambda k: (str(type(k)), k))
    total = sum(float(dist[k]) for k in claves)
    acumulado = 0.0
    for k in claves:
        acumulado += float(dist[k]) / total
        if u < acumulado:
            return k
    return claves[-1]


def _via(deudor) -> str | None:
    """Cómo se saldó: la del usuario o, si la cerró el código con un movimiento, `bizum` (o transferencia)."""
    if deudor.via_saldado:
        return deudor.via_saldado
    return "bizum" if deudor.estado == "saldada" and deudor.movimiento_pago else None


def _pago_de(caso) -> str | None:
    pid = caso.hechos.get("movimiento_origen") or caso.hechos.get("pago_id")
    return pid if isinstance(pid, str) else None


def _cargar_extraccion() -> dict[str, dict]:
    """Extracción grabada (C8), si existe: `clave -> entrada`. Si no, el bucle usa las etiquetas del corpus."""
    if not RUTA_EXTRACCION.exists():
        return {}
    try:
        datos = json.loads(RUTA_EXTRACCION.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    filas = datos.get("extracciones", datos) if isinstance(datos, dict) else datos
    return {f["clave"]: f["entrada"] for f in filas if isinstance(f, dict) and "clave" in f and "entrada" in f}


@dataclass
class ResultadoSimulacion:
    vida_id: str
    semilla: int
    politica: str
    usuario_id: str
    eventos: list[dict]
    saltado: dict[str, int]
    aprendizaje_final: dict
    duracion_s: float

    def de_tipo(self, tipo: str) -> list[dict]:
        return [e for e in self.eventos if e["tipo"] == tipo]

    def resumen(self) -> dict:
        """Recuento rápido (no sustituye a C6): eventos por tipo, preguntas inútiles, solicitudes y errores."""
        cuenta = Counter(e["tipo"] for e in self.eventos)
        preguntas = self.de_tipo("pregunta")
        return {"vida": self.vida_id, "semilla": self.semilla, "politica": self.politica,
                "eventos": dict(sorted(cuenta.items())),
                "preguntas_inutiles": sum(1 for p in preguntas if p["inutil"]),
                "errores": cuenta.get("error", 0), "saltado": dict(self.saltado),
                "aprendizaje_vacio": self.aprendizaje_final.get("vacio"), "duracion_s": round(self.duracion_s, 2)}


# --- El usuario simulado -----------------------------------------------------------------------

@dataclass
class _Simulacion:
    vida: Vida
    gen: VidaGenerada
    politica: str
    corte: date | None = None
    factor_respuesta: float = 1.0
    uid: str = ""
    eventos: list[dict] = field(default_factory=list)
    saltado: Counter = field(default_factory=Counter)
    hoy: date | None = None
    cola: dict[date, list[tuple]] = field(default_factory=lambda: defaultdict(list))
    casos_vistos: dict[str, str] = field(default_factory=dict)            # caso_id -> estado
    presentados: set[str] = field(default_factory=set)
    preguntas_por_pago: Counter = field(default_factory=Counter)
    avisos_por_pago: Counter = field(default_factory=Counter)
    push_semana: Counter = field(default_factory=Counter)
    inutiles_seguidas: int = 0
    harto_de: set[str] = field(default_factory=set)                        # comercios que ya no contesta
    toques_caso: Counter = field(default_factory=Counter)
    devuelto: dict[tuple[str, str], date] = field(default_factory=dict)    # (pago, persona) -> día que vuelve
    canal_devuelto: dict[tuple[str, str], str] = field(default_factory=dict)
    declarado: dict[tuple[str, str], bool] = field(default_factory=dict)   # efectivo: decidido y si lo marca
    reclamado: dict[tuple[str, str], date] = field(default_factory=dict)
    recordado: dict[tuple[str, str], tuple[date, bool]] = field(default_factory=dict)
    en_caso: dict[tuple[str, str], date] = field(default_factory=dict)
    programado: set[tuple[str, str]] = field(default_factory=set)
    efectivo_pendiente: list[tuple[date, str, str]] = field(default_factory=list)
    extraccion: dict[str, dict] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.uid = self.gen.usuario_id(self.politica)
        self.reacciones: dict[tuple[str, str], Reaccion] = {(r.pago_id, r.persona): r for r in self.gen.reacciones}
        self.cobros_por_dia: dict[date, list[tuple[str, str]]] = defaultdict(list)
        self.pagos_por_dia: dict[date, list[VerdadPago]] = defaultdict(list)
        for v in self.gen.verdad.values():
            if v.fecha >= self.gen.activacion:
                self.pagos_por_dia[v.fecha].append(v)
            for clave, vp in v.por_persona.items():
                pagador = v.por_persona.get(vp.pagado_por) if vp.pagado_por else vp
                if pagador and pagador.dia_pagaria_solo and not pagador.no_paga and pagador.dia_pagaria_solo <= self.gen.fin:
                    self.cobros_por_dia[pagador.dia_pagaria_solo].append((v.pago_id, clave))
        self.chat_por_dia: dict[date, list] = defaultdict(list)
        if CON_CHAT[self.politica]:
            for m in self.gen.chat:
                self.chat_por_dia[m.fecha].append(m)
        self.m = self.vida.meisam

    # --- registro ---------------------------------------------------------------------------

    def _semana(self, dia: date) -> int:
        return (dia - self.gen.activacion).days // 7 + 1

    def ev(self, tipo: str, dia: date | None = None, **campos: Any) -> dict:
        dia = dia or self.hoy
        e = {"tipo": tipo, "dia": _iso(dia), "semana": SEMANA_FINAL if tipo in FINALES else self._semana(dia),
             "vida": self.gen.vida_id, "semilla": self.gen.semilla, "politica": self.politica, **campos}
        self.eventos.append(e)
        return e

    def saltar(self, pieza: str, motivo: str) -> None:
        if not self.saltado[pieza]:
            self.ev("saltado", pieza=pieza, motivo=motivo)
        self.saltado[pieza] += 1

    def toque(self, que: str, caso_id: str | None = None, pago_id: str | None = None) -> None:
        if caso_id:
            self.toques_caso[caso_id] += 1
        self.ev("toque", caso_id=caso_id, pago_id=pago_id, que=que)

    def llamar(self, donde: str, funcion: Callable, *args, **kwargs) -> tuple[Any, str | None]:
        """Llama al sistema. Errores de negocio (ValueError y los del banco) -> `(None, mensaje)`; cualquier otro se
        registra como `error` (debe ser 0)."""
        from ....acciones import ErrorAccion
        from ....plataforma import orquestador as orq
        try:
            return funcion(*args, **kwargs), None
        except (ValueError, ErrorAccion, orq.Prohibido, orq.NoEncontrado) as error:
            return None, f"{type(error).__name__}: {str(error)[:160]}"
        except Exception as error:   # noqa: BLE001  (se registra y se sigue: el informe lo cuenta)
            self.ev("error", donde=donde, error=f"{type(error).__name__}: {str(error)[:200]}")
            return None, f"{type(error).__name__}"

    # --- verdad hasta hoy ---------------------------------------------------------------------

    def verdad(self, pago_id: str | None) -> VerdadPago | None:
        return self.gen.verdad.get(pago_id) if pago_id else None

    def ya_devuelto(self, pago_id: str, persona: str, dia: date) -> bool:
        d = self.devuelto.get((pago_id, persona))
        return d is not None and d <= dia

    def a_destiempo(self, v: VerdadPago | None, persona: str, dia: date) -> bool | None:
        vp = v.por_persona.get(persona) if v else None
        if vp is None:
            return None
        pagador = v.por_persona.get(vp.pagado_por, vp) if vp.pagado_por else vp
        return bool(pagador.dia_pagaria_solo and dia < pagador.dia_pagaria_solo and not pagador.no_paga)

    def inutil(self, v: VerdadPago | None, dia: date) -> str | None:
        if v is None or not v.acompanado:
            return "iba_solo"
        if not v.cuotas:
            return "nadie_debe"
        if all(self.ya_devuelto(v.pago_id, p, dia) for p in v.cuotas):
            return "ya_pagado"
        return None

    # --- el bucle -----------------------------------------------------------------------------

    def correr(self) -> None:
        from .... import casos as _casos
        from .... import personalizacion
        from ....plataforma import orquestador as orq

        modelo: ModeloUsuario = personalizacion.nuevo_modelo(self.uid)
        modelo.aprendizaje.modo = MODO[self.politica]   # type: ignore[assignment]
        base = self.gen.movimientos_base
        if self.corte is not None:
            base = [m for m in base if m.fecha <= self.corte]
        inicio = self.gen.activacion - timedelta(days=1)
        self.hoy = inicio
        orq.cargar_simulacion(self.uid, list(base), inicio, contactos=dict(self.gen.contactos), modelo=modelo)
        orq.activar(self.uid, MODULOS, CONSENTIMIENTOS)
        self.extraccion = _cargar_extraccion() if CON_CHAT[self.politica] else {}
        if CON_CHAT[self.politica] and not self.gen.chat:
            self.saltar("chat", "esta vida no tiene mensajes de chat en el corpus para esta semilla")

        fin = min(self.gen.fin, self.corte) if self.corte else self.gen.fin
        dia = self.gen.activacion
        while dia <= fin:
            self.hoy = dia
            decisiones, error = self.llamar("avanzar_dia", orq.avanzar_dia, self.uid, dia)
            if error:
                raise RuntimeError(f"avanzar_dia({dia}) falló: {error}")
            for v in self.pagos_por_dia.get(dia, []):
                self.ev("pago", pago_id=v.pago_id, comercio=v.comercio, importe=_eur(v.importe),
                        acompanado=v.acompanado, forma=v.forma, plan_id=v.plan_id, gasto_solo_id=v.gasto_solo_id,
                        deudores={k: _eur(c) for k, c in v.cuotas.items()},
                        por_persona={k: {"dia_pagaria_solo": _iso(p.dia_pagaria_solo), "canal": p.canal,
                                         "no_paga": p.no_paga, "paga_solo": p.paga_solo, "pagado_por": p.pagado_por,
                                         "retraso_tras_pedir_dias": p.retraso_tras_pedir_dias}
                                     for k, p in v.por_persona.items()})
            self._cobros_solos(dia)
            lista = _casos.cargar(self.uid)
            notifs = {}
            if decisiones or any(c.escenario == "pago_individual" and c.propuesta_id and c.id not in self.presentados
                                 for c in lista):
                notifs = {n["propuesta"]["id"]: n for n in orq.notificaciones(self.uid)}
            self._mirar_casos(lista)
            self._preguntas(lista, notifs, decisiones or [])
            self._avisos(lista, notifs, decisiones or [])
            self._efectivo(lista)
            for mensaje in self.chat_por_dia.get(dia, []):
                self._chat(mensaje)
            for accion in self.cola.pop(dia, []):
                self._ejecutar(accion)
            self._mirar_casos(_casos.cargar(self.uid))      # los casos que abre o cierra el usuario hoy
            dia += timedelta(days=1)
        self._finales(_casos.cargar(self.uid), orq)

    # --- casos: nuevos y cierres --------------------------------------------------------------

    def _mirar_casos(self, lista) -> None:
        for c in lista:
            pago = _pago_de(c)
            for d in c.deudores:
                if pago:
                    self.en_caso.setdefault((pago, d.contraparte), self.hoy)
            previo = self.casos_vistos.get(c.id)
            if previo is None:
                sug = c.sugerencia
                self.ev("caso", caso_id=c.id, pago_id=pago, origen=c.origen, escenario=c.escenario, estado=c.estado,
                        aviso=c.aviso, pregunta_nivel=c.pregunta_nivel,
                        sugerencia=({"personas": list(sug.personas), "cuotas": {k: _eur(v) for k, v in sug.cuotas.items()}}
                                    if sug else None),
                        deudores=[d.contraparte for d in c.deudores])
            if c.estado in CERRADOS and previo not in CERRADOS:
                self.ev("cierre", caso_id=c.id, pago_id=pago, estado=c.estado,
                        deudores=[{"clave": d.contraparte, "estado": d.estado, "via": _via(d)} for d in c.deudores])
            self.casos_vistos[c.id] = c.estado

    # --- dinero que vuelve solo ---------------------------------------------------------------

    def _cobros_solos(self, dia: date) -> None:
        for pago_id, persona in self.cobros_por_dia.get(dia, []):
            v = self.gen.verdad[pago_id]
            vp = v.por_persona[persona]
            pagador = v.por_persona.get(vp.pagado_por, vp) if vp.pagado_por else vp
            self._registrar_cobro(pago_id, persona, dia, pagador.canal, vp.importe_pago, "solo",
                                  [c for c, x in v.por_persona.items() if x.pagado_por == persona])

    def _registrar_cobro(self, pago_id: str, persona: str, dia: date, canal: str, importe: Decimal, origen: str,
                         cubre: list[str]) -> None:
        if (pago_id, persona) in self.devuelto:
            return
        self.devuelto[(pago_id, persona)] = dia
        self.canal_devuelto[(pago_id, persona)] = canal
        if importe > 0 or cubre:
            self.ev("cobro", dia=dia, pago_id=pago_id, contraparte=persona, importe=_eur(importe), canal=canal,
                    origen=origen, cubre=cubre)
        if canal == "efectivo":
            self.efectivo_pendiente.append((dia, pago_id, persona))

    # --- preguntas («¿fuiste con alguien?») ---------------------------------------------------

    def _canal_de(self, caso, notifs: dict, decisiones) -> str | None:
        """push | resumen | None (aún sin propuesta de un aviso `notificar`: se espera)."""
        pid = caso.propuesta_id
        if pid:
            n = notifs.get(pid)
            accion = n["decision"]["accion"] if n else next((d.accion for d in decisiones if d.propuesta_id == pid), None)
            return "push" if accion == "notificar_ahora" else "resumen"
        if caso.aviso == "notificar" and (self.hoy - (caso.avisar_desde or caso.creado)).days < 2:
            return None
        return "resumen"

    def _preguntas(self, lista, notifs: dict, decisiones) -> None:
        por_pago: dict[str, list] = defaultdict(list)
        for c in lista:
            if _pago_de(c):
                por_pago[_pago_de(c)].append(c)
        for c in lista:
            if c.escenario != "pago_individual" or c.estado != "abierto" or c.id in self.presentados:
                continue
            if (c.avisar_desde or c.creado) > self.hoy:
                continue
            pago = _pago_de(c)
            v = self.verdad(pago)
            if c.aviso == "silencioso":
                self.presentados.add(c.id)
                self.ev("silencio", caso_id=c.id, pago_id=pago, nivel=c.pregunta_nivel or 0,
                        habria_sido_util=self.inutil(v, self.hoy) is None)
                continue
            canal = self._canal_de(c, notifs, decisiones)
            if canal is None:
                continue
            self.presentados.add(c.id)
            nivel = c.pregunta_nivel if c.pregunta_nivel is not None else (3 if canal == "push" else 1)
            otros = [o for o in por_pago.get(pago, []) if o.id != c.id and o.escenario != "pago_individual"]
            inutil = "duplicada" if otros else self.inutil(v, self.hoy)
            sug = c.sugerencia if nivel in (2, 3) else None
            correcta = None
            if sug is not None and v is not None:
                correcta = set(sug.personas) == set(v.cuotas) and bool(v.cuotas)
            self.ev("pregunta", caso_id=c.id, pago_id=pago, nivel=nivel, canal=canal, inutil=inutil,
                    sugerencia=({"personas": list(sug.personas), "cuotas": {k: _eur(x) for k, x in sug.cuotas.items()}}
                                if sug else None), sugerencia_correcta=correcta)
            n = self.preguntas_por_pago[pago]
            self.preguntas_por_pago[pago] += 1
            u = self.gen.azar(f"pregunta:{pago}:{n}", 6)
            comercio = (c.hechos.get("comercio") or (v.comercio if v else "")) or ""
            motivo = None
            if otros:
                motivo = "duplicada"
            elif comercio in self.harto_de:
                motivo = "harto"
            elif canal == "push" and self._sobre_tolerancia():
                motivo = "tolerancia"
            elif u[0] >= self._prob_contesta(canal):
                motivo = "no_contesta"
            horas = int(_elegir(self.m.retraso_respuesta_horas, u[1]))
            if motivo is None and horas > HORAS_IGNORADA:
                motivo = "tarde"
            if motivo:
                self.ev("ignorada", objeto="pregunta", caso_id=c.id, pago_id=pago, motivo=motivo)
                continue
            self.cola[self.hoy + timedelta(days=horas // 24)].append(
                ("pregunta", c.id, nivel, inutil, u, horas, comercio))

    def _prob_contesta(self, canal: str) -> float:
        """Probabilidad de contestar a Meisam por ese canal, por `factor_respuesta` (sensibilidad: 0,5 = la mitad)."""
        base = self.m.contesta_notificacion if canal == "push" else self.m.contesta_resumen
        return min(1.0, base * self.factor_respuesta)

    def _sobre_tolerancia(self) -> bool:
        semana = self._semana(self.hoy)
        self.push_semana[semana] += 1
        return self.push_semana[semana] > self.m.tolerancia_avisos_semana

    def _contactos(self) -> set[str]:
        from ....plataforma import orquestador as orq
        lista, _ = self.llamar("contactos_usuario", orq.contactos_usuario, self.uid)
        return {c["contraparte"] for c in lista or []}

    def _responder_pregunta(self, caso_id: str, nivel: int, inutil: str | None, u: tuple, horas: int,
                            comercio: str) -> None:
        from .... import casos as _casos
        from ....plataforma import orquestador as orq

        caso = next((c for c in _casos.cargar(self.uid) if c.id == caso_id), None)
        pago = _pago_de(caso) if caso else None
        if caso is None or caso.estado != "abierto" or caso.escenario != "pago_individual":
            self.ev("ignorada", objeto="pregunta", caso_id=caso_id, pago_id=pago, motivo="cerrado")
            return
        v = self.verdad(pago)
        deudores = list(v.cuotas) if v and v.cuotas else []
        acierta = u[2] < self.m.acierta_respuesta
        if acierta:
            personas = deudores
        elif deudores:
            personas = []                                                  # ruido: «iba solo» cuando no
        else:
            amigos = sorted(self.gen.contactos)
            personas = [amigos[int(u[4] * len(amigos))]] if amigos else []  # ruido: nombra a alguien que no fue
        sug = caso.sugerencia if nivel in (2, 3) else None
        aceptada = None
        importe = None
        if personas and sug is not None and sug.personas:
            if set(sug.personas) == set(personas) and u[3] < self.m.acepta_sugerencia_correcta:
                aceptada = True
                cuotas = set(sug.cuotas.values())
                importe = next(iter(cuotas)) if len(cuotas) == 1 else None
            else:
                aceptada = False
        conocidos = self._contactos() | {d.contraparte for c in _casos.cargar(self.uid) for d in c.deudores}
        fuera = [p for p in personas if p not in conocidos]
        personas = [p for p in personas if p in conocidos]
        if personas and aceptada is not True and v is not None:
            importe = self._importe_con_personas(v, personas)
        if personas:
            r, error = self.llamar("con_personas", orq.actualizar_caso_llamada, self.uid, caso_id, "con_personas",
                                   persona=", ".join(personas), importe=None if importe is None else format(importe, "f"))
            accion = "con_personas"
        elif fuera:
            r, error = None, "todas las personas están fuera de la agenda"
            accion = "con_personas"
        elif acierta and v is not None and v.acompanado:
            # fue acompañado pero nadie le debe (cada uno lo suyo, invitó él…): no dice que fuera solo
            r, error = self.llamar("nadie_me_debe", orq.actualizar_caso_llamada, self.uid, caso_id, "nadie_me_debe")
            accion = "nadie_me_debe"
        else:
            r, error = self.llamar("iba_solo", orq.actualizar_caso_llamada, self.uid, caso_id, "iba_solo")
            accion = "iba_solo"
        self.ev("respuesta", caso_id=caso_id, pago_id=pago, nivel=nivel, accion=accion, personas=personas,
                importe=_eur(importe), sugerencia_aceptada=aceptada, ruido=not acierta, retraso_horas=horas,
                inutil=inutil, ok=error is None, error=error, fuera_de_agenda=fuera)
        self.toque("respuesta", caso_id, pago)
        if inutil:
            self.inutiles_seguidas += 1
        else:
            self.inutiles_seguidas = 0
        n = self.m.silencia_tras_inutiles
        if n and self.inutiles_seguidas >= n and comercio and comercio not in self.harto_de:
            self.harto_de.add(comercio)
            self.inutiles_seguidas = 0
            con_propuesta = bool(caso.propuesta_id)
            if con_propuesta:
                self._feedback(caso.propuesta_id, "no_avisar_comercio")
            self.ev("silencia", caso_id=caso_id, pago_id=pago, comercio=comercio, con_propuesta=con_propuesta)
            self.toque("silencia", caso_id, pago)

    def _importe_con_personas(self, v: VerdadPago, personas: list[str]) -> Decimal | None:
        """Lo que dice el usuario de cuota: None si el reparto a partes iguales del código ya encaja (±0,50 €);
        si no (por consumo, gente de fuera que no debe nada...), la cuota media de su verdad."""
        cuotas = [v.cuotas[p] for p in personas if p in v.cuotas]
        if not cuotas:
            return None
        media = (sum(cuotas, Decimal("0")) / len(cuotas)).quantize(CENT, rounding=ROUND_HALF_UP)
        defecto = (v.importe / (len(personas) + 1)).quantize(CENT, rounding=ROUND_HALF_UP)
        return None if abs(defecto - media) <= TOLERANCIA_IMPORTE else media

    # --- avisos de deudas ---------------------------------------------------------------------

    def _avisos(self, lista, notifs: dict, decisiones) -> None:
        por_propuesta: dict[str, list] = defaultdict(list)
        for c in lista:
            if c.propuesta_id:
                por_propuesta[c.propuesta_id].append(c)
        for d in decisiones:
            if d.accion not in ("notificar_ahora", "resumen"):
                continue
            ligados = [c for c in por_propuesta.get(d.propuesta_id, []) if c.escenario != "pago_individual"]
            if not ligados or any(c.escenario == "pago_individual" for c in por_propuesta.get(d.propuesta_id, [])):
                continue
            n = notifs.get(d.propuesta_id)
            if n is None:
                continue
            canal = "push" if d.accion == "notificar_ahora" else "resumen"
            pago = _pago_de(ligados[0])
            v = self.verdad(pago)
            personas = []
            for a in n["propuesta"]["acciones_ofrecidas"]:
                clave = a["parametros"].get("contraparte") if a["accion_id"] == "pedir_bizum" else None
                if not clave:
                    continue
                destiempo = self.a_destiempo(v, clave, self.hoy)
                for c in ligados:            # un aviso agrupado recuerda las deudas de esa persona en todos sus casos
                    if any(x.contraparte == clave for x in c.deudores) and _pago_de(c):
                        otro = _pago_de(c)
                        self.recordado.setdefault((otro, clave), (self.hoy, bool(self.a_destiempo(self.verdad(otro),
                                                                                                    clave, self.hoy))))
                personas.append({"clave": clave, "cuota": a["parametros"].get("importe"),
                                 "deudor_verdad": bool(v and clave in v.cuotas), "a_destiempo": destiempo,
                                 "ya_devuelto": self.ya_devuelto(pago, clave, self.hoy) if pago else None})
            self.ev("aviso", propuesta_id=d.propuesta_id, casos=[c.id for c in ligados], pago_id=pago, canal=canal,
                    personas=personas)
            k = self.avisos_por_pago[pago]
            self.avisos_por_pago[pago] += 1
            u = self.gen.azar(f"aviso:{pago}:{k}", 4)
            motivo = None
            if canal == "push" and self._sobre_tolerancia():
                motivo = "tolerancia"
            elif u[0] >= self._prob_contesta(canal):
                motivo = "no_contesta"
            horas = int(_elegir(self.m.retraso_respuesta_horas, u[1]))
            if motivo is None and horas > HORAS_IGNORADA:
                motivo = "tarde"
            if motivo:
                self.ev("ignorada", objeto="aviso", propuesta_id=d.propuesta_id, pago_id=pago, motivo=motivo)
                continue
            self.cola[self.hoy + timedelta(days=horas // 24)].append(("aviso", d.propuesta_id, u, horas))

    def _responder_aviso(self, propuesta_id: str, u: tuple, horas: int) -> None:
        from .... import casos as _casos
        from ....plataforma import orquestador as orq

        lista = _casos.cargar(self.uid)
        abiertos = [c for c in _casos.de_propuesta(lista, propuesta_id) if c.estado not in CERRADOS]
        if not abiertos:
            self.ev("ignorada", objeto="aviso", propuesta_id=propuesta_id, pago_id=None, motivo="cerrado")
            return
        n = {x["propuesta"]["id"]: x for x in orq.notificaciones(self.uid)}.get(propuesta_id)
        ofrecidas = {a["parametros"].get("contraparte"): a for a in (n["propuesta"]["acciones_ofrecidas"] if n else [])
                     if a["accion_id"] == "pedir_bizum"}
        modo = _elegir(self.m.si_no_pagan, u[2])
        pago0 = _pago_de(abiertos[0])
        self.ev("accion_aviso", propuesta_id=propuesta_id, pago_id=pago0, modo=modo, retraso_horas=horas)
        a_pedir: list[tuple[Any, str]] = []
        for caso in abiertos:
            pago = _pago_de(caso)
            v = self.verdad(pago)
            for d in _casos.pendientes(caso):
                clave = d.contraparte
                if v is None or clave not in v.cuotas:
                    self._corregir(caso, clave, "no_es_deudor")
                elif clave in self.m.no_recordar:
                    self._corregir(caso, clave, "no_recordar")
                elif self.ya_devuelto(pago, clave, self.hoy):
                    continue                    # ya le pagó: si fue en efectivo, lo decide `_efectivo`
                elif d.estado in ("detectada", "caducada", "rechazada", "olvidada"):
                    a_pedir.append((caso, clave))
        if not a_pedir:
            return
        if modo == "lo_deja":
            self._feedback(propuesta_id, "vista_sin_accion")
            return
        en_persona: list[tuple[Any, str]] = []
        if modo == "pide_bizum":
            pedidas: set[str] = set()
            for caso, clave in a_pedir:
                accion = ofrecidas.get(clave)
                if accion is None:
                    en_persona.append((caso, clave))
                elif clave in pedidas:       # una sola solicitud por persona y aviso: cubre sus otras deudas del grupo
                    pago = _pago_de(caso)
                    self.reclamado.setdefault((pago, clave), self.hoy)
                    self._reaccion(pago, clave)
                else:
                    pedidas.add(clave)
                    self._pedir_bizum(propuesta_id, caso, clave, accion)
        else:
            en_persona = a_pedir
        if en_persona:
            self._feedback(propuesta_id, "resuelta")
            for caso, clave in en_persona:
                pago = _pago_de(caso)
                self.reclamado.setdefault((pago, clave), self.hoy)
                self.ev("reclamo", pago_id=pago, contraparte=clave,
                        a_destiempo=self.a_destiempo(self.verdad(pago), clave, self.hoy))
                self._reaccion(pago, clave)

    def _pedir_bizum(self, propuesta_id: str, caso, clave: str, accion: dict) -> None:
        from ....plataforma import orquestador as orq
        pago = _pago_de(caso)
        tarjeta, error = self.llamar("preparar_accion", orq.preparar_accion, self.uid, propuesta_id, "pedir_bizum",
                                     dict(accion["parametros"]))
        ok = False
        if tarjeta is not None:
            resultado, error = self.llamar("confirmar_accion", orq.confirmar_accion, self.uid, tarjeta.token_confirmacion)
            ok = bool(resultado is not None and resultado.ok)
            if resultado is not None and not resultado.ok:
                error = resultado.mensaje if hasattr(resultado, "mensaje") else "no ok"
        self.ev("solicitud", propuesta_id=propuesta_id, caso_id=caso.id, pago_id=pago, contraparte=clave,
                importe=accion["parametros"].get("importe"), ok=ok, error=error,
                a_destiempo=self.a_destiempo(self.verdad(pago), clave, self.hoy))
        self.toque("solicitud", caso.id, pago)
        if ok:
            self.reclamado.setdefault((pago, clave), self.hoy)
            self._reaccion(pago, clave)

    def _reaccion(self, pago: str | None, clave: str) -> None:
        """El amigo paga tras la solicitud o el recordatorio en persona, con su `retraso_tras_pedir_dias`. Quien ya
        pagaba solo, no paga nunca o tiene la parte pagada por otro no cambia: su verdad ya está en la base."""
        from ....plataforma import orquestador as orq
        if not pago or (pago, clave) in self.programado or (pago, clave) in self.devuelto:
            return
        r = self.reacciones.get((pago, clave))
        if r is None:
            return
        self.programado.add((pago, clave))
        llega = self.hoy + timedelta(days=max(1, r.tras_pedir_dias))
        if llega > self.gen.fin or (self.corte and llega > self.corte):
            self.ev("reaccion", pago_id=pago, contraparte=clave, llega=_iso(llega), canal=r.canal,
                    importe=_eur(r.importe), cubre=list(r.cubre), fuera_de_ventana=True)
            return
        mov = r.movimiento(llega)
        if mov is not None:
            _, error = self.llamar("anadir_movimientos", orq.anadir_movimientos, self.uid, [mov])
            if error:
                self.ev("error", donde="anadir_movimientos", error=error)
        self.ev("reaccion", pago_id=pago, contraparte=clave, llega=_iso(llega), canal=r.canal, importe=_eur(r.importe),
                cubre=list(r.cubre), fuera_de_ventana=False)
        self.cola[llega].append(("cobro_pedido", pago, clave, r.canal, r.importe, list(r.cubre)))

    def _corregir(self, caso, clave: str, motivo: str) -> None:
        from ....plataforma import orquestador as orq
        pago = _pago_de(caso)
        if motivo == "no_recordar" and caso.propuesta_id and len(caso.deudores) == 1:
            self._feedback(caso.propuesta_id, "no_avisar_contacto")
        else:
            self.llamar("no_me_debe", orq.actualizar_caso_llamada, self.uid, caso.id, "no_me_debe", persona=clave)
        self.ev("correccion", caso_id=caso.id, pago_id=pago, contraparte=clave, motivo=motivo)
        self.toque("correccion", caso.id, pago)

    def _feedback(self, propuesta_id: str, resultado: str) -> None:
        from ....plataforma import orquestador as orq
        from ....plataforma.reloj import ahora_por_defecto
        fb = Feedback(propuesta_id=propuesta_id, usuario_id=self.uid, resultado=resultado, canal="app",
                      fecha=ahora_por_defecto(self.hoy))
        _, error = self.llamar("registrar_feedback", orq.registrar_feedback, fb)
        self.ev("feedback", propuesta_id=propuesta_id, resultado=resultado, ok=error is None, error=error)
        self.toque("feedback", None, None)

    # --- efectivo: «ya me lo dio» -------------------------------------------------------------

    def _efectivo(self, lista) -> None:
        from .... import casos as _casos
        from ....plataforma import orquestador as orq
        quedan = []
        for dia, pago, clave in self.efectivo_pendiente:
            if (pago, clave) in self.declarado:
                continue
            caso = next((c for c in lista if _pago_de(c) == pago and c.estado not in CERRADOS
                         and any(d.contraparte == clave and d.estado != "saldada" for d in c.deudores)), None)
            if caso is None:
                if any(_pago_de(c) == pago and c.estado in CERRADOS for c in lista):
                    continue
                quedan.append((dia, pago, clave))
                continue
            declara = self.gen.azar(f"efectivo:{pago}:{clave}", 1)[0] < self.m.declara_efectivo
            self.declarado[(pago, clave)] = declara
            ok = None
            if declara:
                _, error = self.llamar("marcar_saldado", orq.actualizar_caso_llamada, self.uid, caso.id,
                                       "marcar_saldado", persona=clave, via="efectivo")
                ok = error is None
                self.toque("efectivo", caso.id, pago)
            self.ev("efectivo", pago_id=pago, contraparte=clave, caso_id=caso.id, declara=declara, ok=ok)
        self.efectivo_pendiente = quedan

    # --- chat ---------------------------------------------------------------------------------

    def _chat(self, mensaje) -> None:
        from .... import casos as _casos
        from ....plataforma import chat_casos
        from ....plataforma import orquestador as orq

        esp = mensaje.esperado
        herramienta = esp.get("herramienta")
        entrada = self.extraccion.get(mensaje.clave)
        extraccion = "grabada" if entrada is not None else "etiqueta"
        if entrada is None:
            entrada = dict(esp.get("entrada") or {})
            self.saltado["extraccion_de_etiqueta"] += 1
        base = {"entrada_id": mensaje.entrada_id, "tipo_entrada": mensaje.tipo, "pago_id": mensaje.pago_id,
                "herramienta": herramienta, "esperado_resultado": esp.get("resultado"), "extraccion": extraccion}
        lista = _casos.cargar(self.uid)
        if herramienta == "apuntar_gasto":
            if mensaje.pago_id and any(_pago_de(c) == mensaje.pago_id and c.escenario != "pago_individual"
                                       and c.deudores for c in lista):
                self.ev("chat", **base, resultado=None, caso_id=None, omitido="ya_hay_caso", reintento=False)
                return
            try:
                ent = ApuntarGastoEntrada.model_validate(entrada)
            except ValueError as error:
                self.ev("chat", **base, resultado="entrada_invalida", caso_id=None, omitido=str(error)[:120],
                        reintento=False)
                return
            salida, error = self.llamar("apuntar_gasto", chat_casos.apuntar_gasto_usuario, self.uid, ent)
            reintento = False
            if salida is not None and salida.resultado == "varios_candidatos" and esp.get("cargo") in {
                    c.movimiento_id for c in salida.candidatos}:
                salida, error = self.llamar("apuntar_gasto", chat_casos.apuntar_gasto_usuario, self.uid,
                                            ent.model_copy(update={"movimiento_id": esp["cargo"]}))
                reintento = True
            elif salida is not None and salida.resultado == "persona_desconocida" and esp.get("resultado") in (
                    "creado", "convertido"):
                salida, error = self.llamar("apuntar_gasto", chat_casos.apuntar_gasto_usuario, self.uid,
                                            ent.model_copy(update={"confirmar_personas_nuevas": True}))
                reintento = True
            self.ev("chat", **base, resultado=salida.resultado if salida else "error", caso_id=salida.caso_id if salida else None,
                    omitido=None, reintento=reintento, error=error)
            self.toque("chat", salida.caso_id if salida else None, mensaje.pago_id)
        elif herramienta == "recordar_sobre_mi":
            from ....plataforma.tipos import HechoChatEntrada
            try:
                ent_h = HechoChatEntrada.model_validate({**entrada, "texto": entrada.get("texto") or mensaje.texto[:160]})
            except ValueError as error:
                self.ev("chat", **base, resultado="entrada_invalida", caso_id=None, omitido=str(error)[:120],
                        reintento=False)
                return
            r, error = self.llamar("recordar_sobre_mi", chat_casos.recordar_sobre_mi_usuario, self.uid, ent_h)
            reintento = False
            if r is not None and r.get("resultado") == "persona_desconocida" and esp.get("resultado") in (
                    None, "guardado", "repetido"):
                r, error = self.llamar("recordar_sobre_mi", chat_casos.recordar_sobre_mi_usuario, self.uid, ent_h,
                                       confirmar_personas_nuevas=True)
                reintento = True
            self.ev("chat", **base, resultado=r.get("resultado") if r else "error", caso_id=None, omitido=None,
                    reintento=reintento, error=error or (None if r is None or r.get("ok") else r.get("error")))
            self.toque("chat", None, mensaje.pago_id)
        elif herramienta == "actualizar_caso":
            persona = mensaje.persona or (entrada.get("persona") if isinstance(entrada.get("persona"), str) else None)
            caso = next((c for c in lista if _pago_de(c) == mensaje.pago_id and c.estado not in CERRADOS
                         and any(d.contraparte == persona and d.estado != "saldada" for d in c.deudores)), None)
            if caso is None:
                self.ev("chat", **base, resultado="sin_caso", caso_id=None, omitido=None, reintento=False)
            else:
                _, error = self.llamar("marcar_saldado", orq.actualizar_caso_llamada, self.uid, caso.id,
                                       "marcar_saldado", persona=persona, via=entrada.get("via") or "efectivo")
                self.declarado[(mensaje.pago_id, persona)] = True
                self.ev("chat", **base, resultado="saldado" if error is None else "error", caso_id=caso.id,
                        omitido=None, reintento=False, error=error)
            self.toque("chat", caso.id if caso else None, mensaje.pago_id)
        else:
            self.ev("chat", **base, resultado="ninguna", caso_id=None, omitido=None, reintento=False)

    # --- cola ---------------------------------------------------------------------------------

    def _ejecutar(self, accion: tuple) -> None:
        tipo = accion[0]
        if tipo == "pregunta":
            self._responder_pregunta(*accion[1:])
        elif tipo == "aviso":
            self._responder_aviso(*accion[1:])
        elif tipo == "cobro_pedido":
            _, pago, clave, canal, importe, cubre = accion
            self._registrar_cobro(pago, clave, self.hoy, canal, importe, "pedido", cubre)
            for otro in cubre:
                self._registrar_cobro(pago, otro, self.hoy, canal, Decimal("0"), "pedido", [])

    # --- final --------------------------------------------------------------------------------

    def _finales(self, lista, orq) -> None:
        fin = min(self.gen.fin, self.corte) if self.corte else self.gen.fin
        self.hoy = fin
        for v in sorted(self.gen.verdad.values(), key=lambda x: (x.fecha, x.pago_id)):
            if v.fecha < self.gen.activacion or v.fecha > fin or not v.cuotas:
                continue
            for clave, cuota in v.cuotas.items():
                vp = v.por_persona.get(clave)
                pagador = v.por_persona.get(vp.pagado_por, vp) if vp and vp.pagado_por else vp
                devuelto = self.devuelto.get((v.pago_id, clave))
                recordado = self.recordado.get((v.pago_id, clave))
                self.ev("deuda", pago_id=v.pago_id, fecha_pago=_iso(v.fecha), contraparte=clave, cuota=_eur(cuota),
                        canal=pagador.canal if pagador else None, no_paga=bool(pagador and pagador.no_paga),
                        paga_solo=bool(pagador and pagador.paga_solo),
                        dia_pagaria_solo=_iso(pagador.dia_pagaria_solo) if pagador else None,
                        devuelto_el=_iso(devuelto), canal_devuelto=self.canal_devuelto.get((v.pago_id, clave)),
                        declarado=self.declarado.get((v.pago_id, clave)),
                        reclamado_el=_iso(self.reclamado.get((v.pago_id, clave))),
                        en_caso_el=_iso(self.en_caso.get((v.pago_id, clave))),
                        recordado_el=_iso(recordado[0]) if recordado else None,
                        primer_recordatorio_a_destiempo=recordado[1] if recordado else None,
                        dias_hasta_cobrar=(devuelto - v.fecha).days if devuelto else None,
                        observable_21=v.fecha + timedelta(days=21) <= fin)
        for c in lista:
            vias = [_via(d) for d in c.deudores]
            self.ev("caso_final", caso_id=c.id, pago_id=_pago_de(c), origen=c.origen, escenario=c.escenario,
                    estado=c.estado, aviso=c.aviso, pregunta_nivel=c.pregunta_nivel, creado=_iso(c.creado),
                    deudores=[{"clave": d.contraparte, "cuota": _eur(d.cuota), "estado": d.estado,
                               "via": _via(d), "saldada": _iso(d.saldada)} for d in c.deudores],
                    toques=self.toques_caso[c.id],
                    cerrado_solo=bool(c.estado == "saldado" and c.deudores and all(x == "bizum" for x in vias)
                                      and self.toques_caso[c.id] == 0))
        modelo = orq._leer(self.uid, "modelo")
        apr = modelo.aprendizaje
        vacio = not (apr.por_comercio or apr.por_tipo_franja or apr.personas or apr.eventos_vistos)
        if vacio and MODO[self.politica] == "aprende":
            self.saltar("aprendizaje", "el orquestador aún no pasa eventos a aprende_amigos (A4): no ha aprendido nada")
        self.aprendizaje_final = {"modo": apr.modo, "n_comercios": len(apr.por_comercio),
                                  "n_tipo_franja": len(apr.por_tipo_franja), "n_personas": len(apr.personas),
                                  "n_eventos": len(apr.eventos_vistos), "vacio": vacio}
        self.ev("fin", **self.aprendizaje_final)


# --- Entrada -----------------------------------------------------------------------------------

def simular(vida: Vida, semilla: int, politica: str, *, corpus: Corpus | None = None,
            generada: VidaGenerada | None = None, corte: date | None = None,
            dir_datos: str | Path | None = None, factor_respuesta: float = 1.0) -> ResultadoSimulacion:
    """Una vida × una semilla × una política sobre el sistema real. `generada` evita regenerar (las 3 políticas
    comparten la misma). `corte`: solo para el test de «no mira el futuro» (quita la base posterior y para ahí).
    Sin `dir_datos`, usa una carpeta temporal propia (y la borra). `factor_respuesta` (1,0 = la vida tal cual) multiplica
    la probabilidad de que el usuario conteste a Meisam (sensibilidad de C6: las notificaciones de banca se abren un
    7-16 %, así que se prueba con 0,5); no cambia nada más."""
    if politica not in MODO or politica == "oraculo":
        raise ValueError(f"Política desconocida o aún sin hacer (oraculo es C10): {politica!r}")
    gen = generada or generar(vida, semilla, corpus)
    t0 = time.perf_counter()
    with entorno_simulacion(dir_datos, en_memoria=dir_datos is None):   # con `dir_datos`, a disco (se puede inspeccionar)
        sim = _Simulacion(vida=vida, gen=gen, politica=politica, corte=corte, factor_respuesta=factor_respuesta)
        sim.correr()
    duracion = time.perf_counter() - t0
    sim.eventos[-1]["duracion_s"] = round(duracion, 3)
    return ResultadoSimulacion(vida_id=vida.id, semilla=semilla, politica=politica, usuario_id=sim.uid,
                               eventos=sim.eventos, saltado=dict(sim.saltado),
                               aprendizaje_final=sim.aprendizaje_final, duracion_s=duracion)


def simular_politicas(vida: Vida, semilla: int, politicas: tuple[str, ...] = POLITICAS, *,
                      corpus: Corpus | None = None, dir_datos: str | Path | None = None,
                      factor_respuesta: float = 1.0) -> dict[str, ResultadoSimulacion]:
    """Las políticas pedidas sobre la MISMA vida generada (misma suerte). Cada una con su `usuario_id`."""
    gen = generar(vida, semilla, corpus)
    return {p: simular(vida, semilla, p, generada=gen, dir_datos=dir_datos, factor_respuesta=factor_respuesta)
            for p in politicas}


# --- En paralelo (C7) --------------------------------------------------------------------------

def _tarea(args: tuple[str, int, tuple[str, ...], float]) -> list[ResultadoSimulacion]:
    """Un proceso: una vida y una semilla con sus políticas (comparten la vida generada). Cada simulación usa su
    propia carpeta temporal (`entorno_simulacion`), así que los procesos no se pisan."""
    vida_id, semilla, politicas, factor = args
    vida = cargar_vidas()[vida_id]
    return list(simular_politicas(vida, semilla, politicas, factor_respuesta=factor).values())


def simular_en_paralelo(tareas: list[tuple[str, int, tuple[str, ...], float]], procesos: int | None = None,
                        al_terminar: Callable[[list[ResultadoSimulacion]], None] | None = None
                        ) -> list[ResultadoSimulacion]:
    """Ejecuta `tareas` = `(vida_id, semilla, políticas, factor_respuesta)` en procesos (`ProcessPoolExecutor`).
    Con `procesos <= 1` va en serie en este mismo proceso. El resultado sale ordenado por (vida, semilla, política
    en el orden pedido), igual que en serie, así que no depende de quién acabe antes."""
    if not tareas:
        return []
    procesos = procesos if procesos is not None else min(len(tareas), max(1, (os.cpu_count() or 2) - 1))
    hechos: dict[int, list[ResultadoSimulacion]] = {}
    if procesos <= 1 or len(tareas) == 1:
        for i, t in enumerate(tareas):
            hechos[i] = _tarea(t)
            if al_terminar:
                al_terminar(hechos[i])
    else:
        from concurrent.futures import ProcessPoolExecutor, as_completed
        with ProcessPoolExecutor(max_workers=procesos) as pool:
            futuros = {pool.submit(_tarea, t): i for i, t in enumerate(tareas)}
            for futuro in as_completed(futuros):
                hechos[futuros[futuro]] = futuro.result()
                if al_terminar:
                    al_terminar(hechos[futuros[futuro]])
    return [r for i in sorted(hechos) for r in hechos[i]]


def _main() -> None:
    parser = argparse.ArgumentParser(description="Simula una vida con amigos sobre el sistema real (C5).")
    parser.add_argument("--vida", default="alvaro")
    parser.add_argument("--semilla", type=int, default=0)
    parser.add_argument("--politicas", default=",".join(POLITICAS))
    parser.add_argument("--json", help="ruta donde guardar los eventos (opcional)")
    args = parser.parse_args()
    vidas = cargar_vidas()
    vida = vidas[args.vida]
    t0 = time.perf_counter()
    resultados = simular_politicas(vida, args.semilla, tuple(args.politicas.split(",")))
    for r in resultados.values():
        print(json.dumps(r.resumen(), ensure_ascii=False))
    print(f"total {time.perf_counter() - t0:.1f} s")
    if args.json:
        Path(args.json).write_text(json.dumps({p: r.eventos for p, r in resultados.items()}, ensure_ascii=False,
                                              indent=1), encoding="utf-8")


if __name__ == "__main__":
    _main()
