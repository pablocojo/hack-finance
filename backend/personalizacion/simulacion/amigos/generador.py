"""
Generador de vidas con amigos (curva de amigos, `ESQUEMA.md` §2). Datos sintéticos, semilla fija, puro.

`generar(vida, semilla) -> VidaGenerada`: todo el azar de la vida se sortea aquí, antes de simular y sin tocar
el sistema. Cada evento tiene su propio `random.Random` derivado de `f"{vida.id}:{semilla}:<evento>"`, así que
todas las políticas ven la misma suerte (muestreo común) y añadir un evento no cambia los demás.

Calendario del protocolo: historial previo de 4 semanas desde el lunes 2026-09-07 (Meisam inactivo),
activación el lunes 2026-10-05 y 8 semanas activas hasta el domingo 2026-11-29. La semana `s` empieza el
lunes `ACTIVACION + 7 * (s - 1)`: las semanas -3..0 son el historial y 1..8 las activas.

Qué hay en la salida:
- `movimientos_base`: lo que el banco ve y no depende de Meisam (ingresos, fondo, cargos de planes y de gastos
  en solitario, Bizums que envía el usuario cuando paga otro y cobros de amigos que pagan por su cuenta).
  Lo pagado en efectivo no genera nada.
- `reacciones`: lo que pasa solo si Meisam pide o recuerda (el amigo paga tras la solicitud).
- `verdad`: por cada cargo con tarjeta, qué pasó de verdad (acompañado, cuotas, forma, retraso y canal de cada uno).
- `chat`: mensajes del usuario rellenados desde el corpus con cargos que existen.

Dinero siempre con `Decimal`. El sistema nunca importa este módulo.
"""

from __future__ import annotations

import math
import random
import re
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Literal

from ....plataforma.tipos import Base, Contacto, Euros, Movimiento
from .esquema import (
    Corpus,
    EntradaChat,
    PlanEsporadico,
    PlanRecurrente,
    Vida,
    corpus_por_defecto,
)

INICIO_HISTORIAL = date(2026, 9, 7)
ACTIVACION = date(2026, 10, 5)
FIN = date(2026, 11, 29)
SEMANAS_HISTORIAL = (-3, -2, -1, 0)
SEMANAS_ACTIVAS = tuple(range(1, 9))
SEMANAS = SEMANAS_HISTORIAL + SEMANAS_ACTIVAS

CENT = Decimal("0.01")
DIAS = ("lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo")
NOMBRES_NUEVOS = ("Sergio", "Irene", "Javi", "Carmen", "Ivan", "Marta", "Dani", "Alba", "Hugo", "Noelia", "Raul",
                  "Elena")
TIPOS_DE_HECHO = ("hecho", "deuda_sin_cargo", "ruido")      # su probabilidad es `chat_hechos`; el resto, `usa_chat`

Forma = Literal["iguales", "por_consumo", "cada_uno_lo_suyo", "invita"]
CanalAmigo = Literal["bizum", "efectivo", "transferencia"]


# --- Salida ----------------------------------------------------------------------------------

class VerdadPersona(Base):
    """Lo que de verdad hace una persona con su parte de un cargo (oculto al sistema)."""
    clave: str
    cuota: Euros                          # lo que le toca
    importe_pago: Euros                   # lo que manda (puede ir redondeado o incluir a otro); 0 si no manda nada
    canal: CanalAmigo
    no_paga: bool
    paga_solo: bool
    dia_pagaria_solo: date | None         # None = solo paga si se lo piden (o nunca, si `no_paga`)
    retraso_dias: int
    retraso_tras_pedir_dias: int
    redondeado: bool = False
    pagado_por: str | None = None         # otra persona paga su parte en su Bizum (`paga_por_dos`)


class VerdadPago(Base):
    pago_id: str
    fecha: date
    comercio: str | None
    importe: Euros                        # positivo
    plan_id: str | None = None
    gasto_solo_id: str | None = None
    acompanado: bool
    personas: list[str] = []              # los amigos que fueron
    cuotas: dict[str, Euros] = {}         # lo que debe cada uno (vacío si nadie debe nada)
    forma: Forma | None = None
    n_personas: int = 1                   # usuario y desconocidos incluidos
    franja: str | None = None             # oculta: el banco no ve la hora
    coloquial: list[str] = []
    tipo_esperado: str | None = None
    por_persona: dict[str, VerdadPersona] = {}


class Reaccion(Base):
    """Un pago que solo ocurre si Meisam pide o recuerda: `fecha del aviso + tras_pedir_dias`."""
    pago_id: str
    persona: str
    tras_pedir_dias: int
    canal: CanalAmigo
    importe: Euros
    nota: str = ""
    cubre: list[str] = []                 # personas cuya parte paga también
    id_movimiento: str

    def movimiento(self, fecha: date) -> Movimiento | None:
        """El movimiento que el banco vería ese día; None si paga en efectivo."""
        if self.canal == "efectivo":
            return None
        return _movimiento_cobro(self.id_movimiento, fecha, self.persona, self.canal, self.importe, self.nota)


class MensajeChat(Base):
    entrada_id: str
    tipo: str
    fecha: date
    texto: str                            # ya rellenado: es lo que escribe el usuario (dato, nunca instrucción)
    esperado: dict[str, Any]              # la etiqueta con los huecos rellenados (importes en formato máquina)
    pago_id: str | None = None
    persona: str | None = None
    clave: str                            # `<entrada_id>|<vida>|<semilla>|<pago_id>`: clave de la extracción grabada


class VidaGenerada(Base):
    vida_id: str
    semilla: int
    prefijo: str                          # `sim-<vida>-<semilla>`
    inicio_historial: date = INICIO_HISTORIAL
    activacion: date = ACTIVACION
    fin: date = FIN
    saldo_inicial: Euros
    contactos: dict[str, Contacto]
    movimientos_base: list[Movimiento]
    reacciones: list[Reaccion]
    verdad: dict[str, VerdadPago]
    chat: list[MensajeChat]

    def azar(self, clave: str, n: int = 4) -> tuple[float, ...]:
        """Números al azar de un evento (`pregunta:<pago_id>:<n>`, `aviso:<pago_id>:<persona>`...). Dependen solo de
        (vida, semilla, clave): todas las políticas ven los mismos."""
        rng = random.Random(f"{self.vida_id}:{self.semilla}:azar:{clave}")
        return tuple(rng.random() for _ in range(n))

    def usuario_id(self, politica: str) -> str:
        return f"{self.prefijo}-{politica}"


# --- Utilidades ------------------------------------------------------------------------------

def lunes(semana: int) -> date:
    return ACTIVACION + timedelta(days=7 * (semana - 1))


def _elegir(rng: random.Random, dist: dict) -> Any:
    return rng.choices(list(dist), weights=list(dist.values()))[0]


def _dinero(rng: random.Random, rango) -> Decimal:
    return Decimal(rng.randint(int(rango.min * 100), int(rango.max * 100))) / 100


def _poisson(rng: random.Random, lam: float) -> int:
    limite, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= limite:
            return k
        k += 1


def _redondear_a(valor: Decimal, multiplo: Decimal) -> Decimal:
    veces = (valor / multiplo).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return max(multiplo, veces * multiplo).quantize(CENT)


def _movimiento_cobro(id_: str, fecha: date, persona: str, canal: str, importe: Decimal, nota: str) -> Movimiento:
    if canal == "transferencia":
        return Movimiento(id=id_, fecha=fecha, concepto="TRANSFERENCIA RECIBIDA", importe=importe, canal="transferencia",
                          contraparte=persona)
    return Movimiento(id=id_, fecha=fecha, concepto="BIZUM RECIBIDO", importe=importe, canal="bizum",
                      contraparte=persona, nota=nota or None)


def _concepto_cobro(canal: str) -> str:
    return "TRANSFERENCIA RECIBIDA" if canal == "transferencia" else "BIZUM RECIBIDO"


def _meses_en_rango():
    y, m = INICIO_HISTORIAL.year, INICIO_HISTORIAL.month
    while date(y, m, 1) <= FIN:
        yield y, m
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)


@dataclass
class _Mov:
    clave: str
    fecha: date
    concepto: str
    importe: Decimal
    canal: str
    orden: int = 1                         # 0 ingresos, 1 cargos, 2 cobros y reacciones (a igualdad de fecha)
    comercio: str | None = None
    categoria: str | None = None
    contraparte: str | None = None
    nota: str | None = None
    base: bool = True
    id: str = ""

    def movimiento(self) -> Movimiento:
        return Movimiento(id=self.id, fecha=self.fecha, concepto=self.concepto, comercio=self.comercio,
                          importe=self.importe, categoria=self.categoria, canal=self.canal,  # type: ignore[arg-type]
                          contraparte=self.contraparte, nota=self.nota)


@dataclass
class _Ctx:
    vida: Vida
    semilla: int
    movs: list[_Mov] = field(default_factory=list)
    pagos: list[tuple[_Mov, dict]] = field(default_factory=list)     # (cargo, datos de la verdad)
    reacciones: list[tuple[_Mov, dict]] = field(default_factory=list)
    cobros: list[tuple[str, date, _Mov]] = field(default_factory=list)   # (persona, día, cargo) cobrados solos

    def rng(self, evento: str) -> random.Random:
        return random.Random(f"{self.vida.id}:{self.semilla}:{evento}")

    def multiplicador(self, semana: int, id_: str, campo: str) -> float:
        m = 1.0
        for c in self.vida.cambios_rutina:
            if semana in c.semanas:
                m *= getattr(c, campo).get(id_, 1.0)
        return m


# --- Fondo, ingresos y gastos en solitario ---------------------------------------------------

def _ingresos_y_fondo(ctx: _Ctx) -> None:
    vida = ctx.vida
    for i, ing in enumerate(vida.visible.ingresos):
        for y, m in _meses_en_rango():
            fecha = date(y, m, ing.dia_mes)
            if not INICIO_HISTORIAL <= fecha <= FIN:
                continue
            rng = ctx.rng(f"ingreso:{i}:{fecha}")
            var = int(ing.variacion * 100)
            importe = ing.importe + Decimal(rng.randint(-var, var)) / 100
            ctx.movs.append(_Mov(f"ingreso:{i}:{fecha}", fecha, ing.concepto.upper(), importe.quantize(CENT), ing.canal,
                                 orden=0, categoria="ingresos", contraparte=ing.contraparte))
    for i, f in enumerate(vida.visible.fondo):
        concepto = f"COMPRA TARJETA {f.comercio}" if f.canal == "tarjeta" else f"RECIBO {f.comercio}"
        if f.dia_mes is not None:
            for y, m in _meses_en_rango():
                fecha = date(y, m, f.dia_mes)
                if INICIO_HISTORIAL <= fecha <= FIN:
                    rng = ctx.rng(f"fondo:{i}:{fecha}")
                    importe = f.importe if f.importe is not None else _dinero(rng, f.rango)
                    _anadir_fondo(ctx, f, i, fecha, 0, concepto, importe)
            continue
        for semana in SEMANAS:
            rng = ctx.rng(f"fondo:{i}:s{semana}")
            veces = _poisson(rng, f.veces_semana)
            dias = list(f.dias) if f.dias else list(range(7))
            elegidos = rng.sample(dias, veces) if veces <= len(dias) else [rng.choice(dias) for _ in range(veces)]
            for j, dia in enumerate(sorted(elegidos)):
                fecha = lunes(semana) + timedelta(days=dia)
                if fecha <= FIN:
                    importe = f.importe if f.importe is not None else _dinero(rng, f.rango)
                    _anadir_fondo(ctx, f, i, fecha, j, concepto, importe)


def _anadir_fondo(ctx: _Ctx, f, i: int, fecha: date, j: int, concepto: str, importe: Decimal) -> None:
    mov = _Mov(f"fondo:{i}:{fecha}:{j}", fecha, concepto, -importe, f.canal, comercio=f.comercio, categoria=f.categoria)
    ctx.movs.append(mov)
    if f.canal == "tarjeta":
        ctx.pagos.append((mov, {"plan_id": None, "gasto_solo_id": None, "acompanado": False, "importe": importe,
                                "coloquial": [], "tipo_esperado": None, "franja": None}))


def _gastos_solo(ctx: _Ctx) -> None:
    for g in ctx.vida.gastos_solo:
        for semana in SEMANAS:
            mult = ctx.multiplicador(semana, g.id, "gastos_solo")
            for dia in g.dias:
                rng = ctx.rng(f"solo:{g.id}:{semana}:{dia}")
                u, importe = rng.random(), _dinero(rng, g.importe)
                fecha = lunes(semana) + timedelta(days=dia)
                if fecha > FIN or u >= min(1.0, g.prob_dia * mult):
                    continue
                mov = _Mov(f"solo:{g.id}:{fecha}", fecha, f"COMPRA TARJETA {g.comercio}", -importe, "tarjeta",
                           comercio=g.comercio, categoria=g.categoria)
                ctx.movs.append(mov)
                ctx.pagos.append((mov, {"plan_id": None, "gasto_solo_id": g.id, "acompanado": False,
                                        "importe": importe, "coloquial": list(g.coloquial),
                                        "tipo_esperado": g.tipo_esperado, "franja": None}))


# --- Planes con amigos -----------------------------------------------------------------------

def _planes(ctx: _Ctx) -> None:
    for plan in ctx.vida.planes_recurrentes:
        for semana in SEMANAS:
            rng = ctx.rng(f"ocurre:{plan.id}:{semana}")
            u, i = rng.random(), rng.randrange(len(plan.dias))
            mult = ctx.multiplicador(semana, plan.id, "planes")
            if u < min(1.0, plan.prob_semanal * mult):
                _ocurrencia(ctx, plan, semana, plan.dias[i])
    for plan in ctx.vida.planes_esporadicos:
        for cuando in plan.cuando:
            _ocurrencia(ctx, plan, cuando.semana, cuando.dia)


def _ocurrencia(ctx: _Ctx, plan: PlanRecurrente | PlanEsporadico, semana: int, dia: int) -> None:
    vida = ctx.vida
    fecha = lunes(semana) + timedelta(days=dia)
    if fecha > FIN:
        return
    k = f"{plan.id}:{semana}:{dia}"
    rng = ctx.rng(f"plan:{k}")
    sitio = rng.choices(plan.sitios, weights=[s.peso for s in plan.sitios])[0]
    grupo = list(plan.grupo.fijos)
    for o in plan.grupo.opcionales:
        if rng.random() < o.prob and o.amigo not in grupo:
            grupo.append(o.amigo)
    desconocidos = rng.randint(plan.grupo.desconocidos.min, plan.grupo.desconocidos.max)
    n = 1 + len(grupo) + desconocidos
    quien = _elegir(rng, plan.paga)
    base = _dinero(rng, plan.importe_por_persona)

    def parte() -> Decimal:
        if plan.reparto != "por_consumo":
            return base
        factor = 1 + Decimal(str(round(rng.uniform(-plan.variacion_pct, plan.variacion_pct), 4)))
        return (base * factor).quantize(CENT, rounding=ROUND_HALF_UP)

    parte_usuario = parte()
    partes = {a: parte() for a in grupo}
    resto = sum((parte() for _ in range(desconocidos)), Decimal("0"))
    total = parte_usuario + sum(partes.values(), Decimal("0")) + resto

    if quien == "efectivo":
        return                                         # nada en el banco
    if quien in vida.amigos:                           # paga un amigo: el usuario le envía su parte
        if plan.reparto != "invita":
            envio = fecha + timedelta(days=rng.choice((0, 0, 1)))
            if envio <= FIN:
                ctx.movs.append(_Mov(f"envio:{k}", envio, "BIZUM ENVIADO", -parte_usuario, "bizum", orden=2,
                                     contraparte=quien, nota=(sitio.coloquial[0] if sitio.coloquial else None)))
        return

    paga_todo = quien == "usuario"
    importe = total if paga_todo else parte_usuario
    cargo = _Mov(f"plan:{k}", fecha, f"COMPRA TARJETA {sitio.comercio}", -importe, "tarjeta",
                 comercio=sitio.comercio, categoria=sitio.categoria)
    ctx.movs.append(cargo)
    datos: dict[str, Any] = {
        "plan_id": plan.id, "gasto_solo_id": None, "acompanado": True, "importe": importe, "personas": grupo,
        "n_personas": n, "franja": plan.franja, "coloquial": list(sitio.coloquial),
        "tipo_esperado": sitio.tipo_esperado, "cuotas": {}, "forma": "cada_uno_lo_suyo", "por_persona": {},
    }
    if paga_todo and plan.reparto == "invita":
        datos["forma"] = "invita"
    elif paga_todo:
        datos["forma"] = plan.reparto
        datos["cuotas"] = dict(partes)
        _amigos_pagan(ctx, cargo, datos, grupo, partes, k)
    ctx.pagos.append((cargo, datos))


def _amigos_pagan(ctx: _Ctx, cargo: _Mov, datos: dict, grupo: list[str], cuotas: dict[str, Decimal], k: str) -> None:
    """Sortea cómo devuelve cada amigo su parte y crea cobros (por su cuenta) y reacciones (si se lo piden)."""
    vida, fecha = ctx.vida, cargo.fecha
    historial = fecha < ACTIVACION
    sorteo: dict[str, dict[str, Any]] = {}
    for a in grupo:
        am, rng = vida.amigos[a], ctx.rng(f"pago:{k}:{a}")
        sorteo[a] = {
            "no_paga": rng.random() < am.no_paga, "solo": rng.random() < am.prob_paga_solo,
            "retraso": _elegir(rng, am.retraso_dias), "pedir": _elegir(rng, am.retraso_tras_pedir_dias),
            "canal": _elegir(rng, am.canal), "u_red": rng.random(), "nota": rng.choice(am.notas_bizum),
            "u_dos": rng.random(),
        }
    pagado_por: dict[str, str] = {}                  # quien tiene su parte pagada -> quien la paga
    for a in grupo:
        am, s = vida.amigos[a], sorteo[a]
        if not am.paga_por_dos or s["no_paga"] or a in pagado_por:
            continue
        con = am.paga_por_dos.con
        if con in grupo and con not in pagado_por and con not in pagado_por.values() and s["u_dos"] < am.paga_por_dos.prob:
            pagado_por[con] = a
    cubre: dict[str, list[str]] = {}
    for con, a in pagado_por.items():
        cubre.setdefault(a, []).append(con)

    for a in grupo:
        am, s = vida.amigos[a], sorteo[a]
        pagador = pagado_por.get(a, a)
        sp = sorteo[pagador]
        if a in pagado_por:                          # su parte la paga otro: hereda canal y tiempos de quien paga
            s = {**s, "no_paga": False, "solo": sp["solo"], "retraso": sp["retraso"], "pedir": sp["pedir"],
                 "canal": sp["canal"]}
        debido = cuotas[a] + sum((cuotas[c] for c in cubre.get(a, [])), Decimal("0"))
        paga = Decimal("0.00")
        redondeado = False
        if a not in pagado_por and not s["no_paga"]:
            paga = debido.quantize(CENT)
            if am.redondea and s["u_red"] < am.redondea.prob:
                redondeo = _redondear_a(debido, am.redondea.a)
                redondeado = redondeo != paga
                paga = redondeo
        dia_solo = fecha + timedelta(days=s["retraso"]) if s["solo"] and not s["no_paga"] else None
        datos["por_persona"][a] = VerdadPersona(
            clave=a, cuota=cuotas[a], importe_pago=paga, canal=s["canal"], no_paga=s["no_paga"],
            paga_solo=s["solo"], dia_pagaria_solo=dia_solo, retraso_dias=s["retraso"],
            retraso_tras_pedir_dias=s["pedir"], redondeado=redondeado, pagado_por=pagado_por.get(a))
        if a in pagado_por or s["no_paga"]:
            continue
        nota = s["nota"]
        if historial:                                # sin Meisam: si no pagaba solo, se lo pidieron en persona
            cuando = fecha + timedelta(days=s["retraso"] + (0 if s["solo"] else s["pedir"]))
            if s["canal"] != "efectivo" and cuando <= FIN:
                ctx.movs.append(_Mov(f"cobro:{k}:{a}", cuando, _concepto_cobro(s["canal"]), paga, s["canal"], orden=2,
                                     contraparte=a, nota=(nota or None) if s["canal"] == "bizum" else None))
        elif s["solo"]:
            cuando = dia_solo
            if s["canal"] != "efectivo" and cuando <= FIN:
                ctx.movs.append(_Mov(f"cobro:{k}:{a}", cuando, _concepto_cobro(s["canal"]), paga, s["canal"], orden=2,
                                     contraparte=a, nota=(nota or None) if s["canal"] == "bizum" else None))
            if cuando <= FIN:
                ctx.cobros.append((a, cuando, cargo))
        else:
            ctx.reacciones.append((_Mov(f"reac:{k}:{a}", fecha, "", paga, s["canal"], orden=2, contraparte=a,
                                        nota=nota or None, base=False),
                                   {"persona": a, "tras_pedir_dias": s["pedir"], "cubre": cubre.get(a, []),
                                    "pago": cargo}))


# --- Chat ------------------------------------------------------------------------------------

def _humano(valor: Decimal) -> str:
    return f"{valor:.0f}" if valor == valor.to_integral_value() else f"{valor:.2f}".replace(".", ",")


def _maquina(valor: Decimal) -> str:
    return f"{valor.quantize(CENT):.2f}"


def _aprox(valor: Decimal) -> Decimal:
    return max(Decimal("5"), (valor / 5).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * 5)


def _unir(nombres: list[str]) -> str:
    return nombres[0] if len(nombres) == 1 else ", ".join(nombres[:-1]) + " y " + nombres[-1] if nombres else ""


def _cuando(pago: VerdadPago, mensaje: date) -> str:
    delta = (mensaje - pago.fecha).days
    if delta <= 0:
        return "hoy"
    if delta == 1:
        return "anoche" if pago.franja in ("cena", "noche") else "ayer"
    if pago.fecha.weekday() >= 5:
        return "el finde"
    return f"el {DIAS[pago.fecha.weekday()]}"


_HUECO = re.compile(r"\{([a-z_]+)\}")


def _rellenar(texto: str, valores: dict[str, str]) -> str:
    return _HUECO.sub(lambda m: valores.get(m.group(1), m.group(0)), texto)


def _expandir(obj: Any, valores: dict[str, str], pilas: list[str], cuotas: dict[str, str] | None) -> Any:
    """Rellena los huecos de la etiqueta; `{personas}` en una lista se expande a un elemento por persona."""
    if isinstance(obj, str):
        return _rellenar(obj, valores)
    if isinstance(obj, list):
        salida: list[Any] = []
        for item in obj:
            if isinstance(item, dict) and any(v == "{personas}" for v in item.values()):
                for pila in pilas:
                    salida.append({k: (pila if v == "{personas}" else _expandir(v, valores, pilas, cuotas))
                                   for k, v in item.items()})
            else:
                salida.append(_expandir(item, valores, pilas, cuotas))
        return salida
    if isinstance(obj, dict):
        return {_rellenar(k, valores) if isinstance(k, str) else k: _expandir(v, valores, pilas, cuotas)
                for k, v in obj.items()}
    return obj


def _chat(ctx: _Ctx, corpus: Corpus | None, verdad: dict[str, VerdadPago]) -> list[MensajeChat]:
    vida, semilla = ctx.vida, ctx.semilla
    entradas = corpus.de_vida(vida.id) if corpus else []
    if not entradas or not vida.amigos:
        return []
    pila = {c: a.nombre_pila for c, a in vida.amigos.items()}
    prob = {t: (vida.meisam.chat_hechos if t in TIPOS_DE_HECHO else vida.meisam.usa_chat) for t in
            {e.tipo for e in entradas}}
    mensajes: list[MensajeChat] = []

    def emitir(rng: random.Random, e: EntradaChat, disparo: date, pago: VerdadPago | None, persona: str | None,
               plan=None) -> None:
        fecha = disparo + timedelta(days=_elegir(rng, e.retraso_dias))
        if fecha > FIN or fecha < ACTIVACION:
            return
        if pago is not None:
            deudores = list(pago.cuotas)
            persona = persona or deudores[0]
            cuota = pago.cuotas.get(persona, next(iter(pago.cuotas.values())))
            coloquial = rng.choice(pago.coloquial) if pago.coloquial else (pago.comercio or "")
            total = pago.importe
            humanos = {"coloquial": coloquial, "comercio": pago.comercio or "", "cuando": _cuando(pago, fecha),
                       "fecha": pago.fecha.isoformat(), "total": _humano(total), "total_aprox": f"unos {_humano(_aprox(total))}",
                       "cuota": _humano(cuota), "n": str(pago.n_personas),
                       "dia_semana": f"los {DIAS[pago.fecha.weekday()]}", "pago_id": pago.pago_id}
            maquina = {**humanos, "total": _maquina(total), "total_aprox": _maquina(_aprox(total)),
                       "cuota": _maquina(cuota)}
            pago_id = pago.pago_id
            cuotas_m = {c: _maquina(v) for c, v in pago.cuotas.items()}
        else:                                           # `semana`: contexto de la vida, sin pago
            deudores = list(plan.grupo.fijos) if plan else list(vida.amigos)[:2]
            persona = persona or rng.choice(list(vida.amigos))
            sitio = rng.choice(plan.sitios) if plan else None
            dias = getattr(plan, "dias", None) or [c.dia for c in getattr(plan, "cuando", [])] or [5]
            humanos = {"coloquial": rng.choice(sitio.coloquial) if sitio and sitio.coloquial else (sitio.comercio if sitio else ""),
                       "comercio": sitio.comercio if sitio else "", "n": str(1 + len(deudores)),
                       "dia_semana": f"los {DIAS[dias[0]]}"}
            maquina = dict(humanos)
            pago_id, cuotas_m = None, None
        nuevos = [n for n in NOMBRES_NUEVOS if n.lower() not in {p.lower() for p in pila.values()}]
        nuevo = rng.choice(nuevos)
        humanos |= {"personas": _unir([pila[c] for c in deudores]), "persona": pila[persona], "nuevo": nuevo}
        maquina |= {"personas": humanos["personas"], "persona": pila[persona], "nuevo": nuevo}
        esperado = _expandir(deepcopy(e.esperado.model_dump()), maquina, [pila[c] for c in deudores], cuotas_m)
        if pago is not None:
            esperado["cargo"] = pago_id if e.esperado.cargo else None
            if e.esperado.deudores == "iguales":
                esperado["deudores"] = dict(cuotas_m)
        mensajes.append(MensajeChat(
            entrada_id=e.id, tipo=e.tipo, fecha=fecha, texto=_rellenar(e.plantilla, humanos), esperado=esperado,
            pago_id=pago_id, persona=persona if e.disparador.startswith("cobro:") else None,
            clave=f"{e.id}|{vida.id}|{semilla}|{pago_id or ''}"))

    for pago in sorted(verdad.values(), key=lambda p: (p.fecha, p.pago_id)):
        if pago.plan_id is None or not pago.cuotas or pago.fecha < ACTIVACION:
            continue
        candidatas = [e for e in entradas if e.disparador in (f"plan:{pago.plan_id}", "compartido")]
        if candidatas:
            rng = ctx.rng(f"chat:{pago.pago_id}")
            e, u = candidatas[rng.randrange(len(candidatas))], rng.random()
            if u < prob[e.tipo]:
                emitir(rng, e, pago.fecha, pago, None)
    for persona, dia, cargo in sorted(ctx.cobros, key=lambda c: (c[1], c[0], c[2].id)):
        candidatas = [e for e in entradas if e.disparador == f"cobro:{persona}"]
        if candidatas and cargo.id in verdad and cargo.fecha >= ACTIVACION:
            rng = ctx.rng(f"chat:cobro:{cargo.id}:{persona}")
            e, u = candidatas[rng.randrange(len(candidatas))], rng.random()
            if u < prob[e.tipo]:
                emitir(rng, e, dia, verdad[cargo.id], persona)
    semana_e = [e for e in entradas if e.disparador == "semana"]
    if semana_e:
        for semana in SEMANAS_ACTIVAS:
            rng = ctx.rng(f"chat:semana:{semana}")
            e, u, dia = semana_e[rng.randrange(len(semana_e))], rng.random(), rng.randrange(7)
            plan = rng.choice(ctx.vida.planes) if ctx.vida.planes else None
            if u < prob[e.tipo]:
                emitir(rng, e, lunes(semana) + timedelta(days=dia), None, None, plan)
    mensajes.sort(key=lambda m: (m.fecha, m.entrada_id, m.pago_id or ""))
    return mensajes


# --- Entrada ---------------------------------------------------------------------------------

def generar(vida: Vida, semilla: int, corpus: Corpus | None = None) -> VidaGenerada:
    """Genera la vida de `vida` para `semilla`. Puro y determinista.

    `corpus`: el del chat; con None se usa `evals/datos/chat_amigos.yaml` si existe (si no, sin chat). Para
    desactivar el chat explícitamente, pasa `Corpus(version=1, entradas=[])`.
    """
    if corpus is None:
        corpus = corpus_por_defecto()
    ctx = _Ctx(vida=vida, semilla=semilla)
    _ingresos_y_fondo(ctx)
    _gastos_solo(ctx)
    _planes(ctx)

    # ids estables: orden por (fecha, tipo, clave) y número correlativo; los reactivos también se numeran
    todos = [*ctx.movs, *(m for m, _ in ctx.reacciones)]
    prefijo = f"sim-{vida.id}-{semilla}"
    for n, mov in enumerate(sorted(todos, key=lambda m: (m.fecha, m.orden, m.clave)), start=1):
        mov.id = f"{prefijo}-{n}"

    verdad: dict[str, VerdadPago] = {}
    for cargo, d in ctx.pagos:
        if cargo.fecha > FIN:
            continue
        verdad[cargo.id] = VerdadPago(
            pago_id=cargo.id, fecha=cargo.fecha, comercio=cargo.comercio, importe=d["importe"], plan_id=d["plan_id"],
            gasto_solo_id=d["gasto_solo_id"], acompanado=d["acompanado"], personas=d.get("personas", []),
            cuotas=d.get("cuotas", {}), forma=d.get("forma") if d["acompanado"] else None,
            n_personas=d.get("n_personas", 1), franja=d["franja"], coloquial=d["coloquial"],
            tipo_esperado=d["tipo_esperado"], por_persona=d.get("por_persona", {}))
    reacciones = sorted(
        (Reaccion(pago_id=d["pago"].id, persona=d["persona"], tras_pedir_dias=d["tras_pedir_dias"], canal=m.canal,
                  importe=m.importe, nota=m.nota or "", cubre=d["cubre"], id_movimiento=m.id)
         for m, d in ctx.reacciones),
        key=lambda r: (r.pago_id, r.persona))
    base = sorted((m.movimiento() for m in ctx.movs if m.fecha <= FIN), key=lambda m: int(m.id.rsplit("-", 1)[1]))
    contactos = {}
    for clave, a in vida.amigos.items():
        if a.en_agenda:
            tel = random.Random(f"{vida.id}:{semilla}:telefono:{clave}").randint(100, 999)
            contactos[clave] = Contacto(contraparte=clave, nombre=a.nombre, telefono=f"+34 6** *** {tel}",
                                        relacion=a.relacion)
    return VidaGenerada(
        vida_id=vida.id, semilla=semilla, prefijo=prefijo, saldo_inicial=vida.visible.saldo_inicial,
        contactos=contactos, movimientos_base=base, reacciones=reacciones, verdad=verdad,
        chat=_chat(ctx, corpus, verdad))
