"""
Diario de una vida con amigos (C9; `docs/diseno/curva-amigos.md` §6): qué preguntó o avisó Meisam, con su nivel y sus
motivos, qué contestó la persona, qué pasó con cada deuda y, al lado, la verdad oculta («en realidad: fue con Laura y
Marcos»). Sirve para el contraste de la semana 1 con la 8 en el pitch y para que el crítico juzgue.

    python scripts/diario_amigos.py --vida alvaro --semana 1
    python scripts/diario_amigos.py --vida alvaro --semana 8 --politica reglas --semilla 3
    python scripts/diario_amigos.py --vida alvaro --semana 1 --comparar        # reglas y personalizada lado a lado

Corre la simulación de esa vida y semilla sobre el sistema real (sin Claude ni internet) en un `DATOS_USUARIO_DIR`
temporal (`entorno_simulacion`): no toca `datos_usuario/`. Es una SIMULACIÓN: vidas inventadas.
"""

from __future__ import annotations

import argparse
import itertools
import sys
import textwrap
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from backend.personalizacion.simulacion.amigos import protocolo as P  # noqa: E402
from backend.personalizacion.simulacion.amigos.esquema import Vida, cargar_vidas  # noqa: E402
from backend.personalizacion.simulacion.amigos.generador import ACTIVACION, generar  # noqa: E402

DIAS = ("lun", "mar", "mié", "jue", "vie", "sáb", "dom")
MESES = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")
NIVELES = {0: "calla", 1: "pregunta en el resumen", 2: "resumen con sugerencia", 3: "aviso al móvil con sugerencia",
           4: "lo abre solo (rutina aceptada)"}
IGNORADA = {"no_contesta": "no contesta", "tarde": "tardaría más de 48 h: ya no cuenta", "tolerancia": "ya tuvo demasiados "
            "avisos esa semana", "harto": "ya está harta de preguntas de ese sitio", "duplicada": "ya hay otro caso del "
            "mismo pago", "cerrado": "el caso ya estaba cerrado"}
INUTIL = {"iba_solo": "iba solo", "nadie_debe": "nadie le debe", "ya_pagado": "ya estaba pagado", "duplicada": "duplicada"}
MODO = {"pide_bizum": "pedir el Bizum", "se_lo_dice_en_persona": "decírselo en persona", "lo_deja": "dejarlo"}
POLITICAS_DIARIO = ("reglas", "personalizada", "personalizada_sin_chat")


# --- Formato -----------------------------------------------------------------------------------

def euros(texto: str | None) -> str:
    if texto in (None, ""):
        return "?"
    return f"{Decimal(str(texto)):.2f}".replace(".", ",") + " €"


def fecha_corta(iso: str | None) -> str:
    if not iso:
        return "?"
    d = date.fromisoformat(iso)
    return f"{DIAS[d.weekday()]} {d.day} {MESES[d.month - 1]}"


def plural(n: int, uno: str, varios: str) -> str:
    return f"{n} {uno if n == 1 else varios}"


def lista(nombres: list[str]) -> str:
    if len(nombres) <= 1:
        return "".join(nombres)
    return ", ".join(nombres[:-1]) + " y " + nombres[-1]


class Contexto:
    """Nombres de pila de la vida y verdad oculta de cada pago (la verdad la conoce el simulador, nunca Meisam)."""

    def __init__(self, vida: Vida, verdad: dict, motivos: dict[str, str]):
        self.vida = vida
        self.verdad = verdad
        self.motivos = motivos

    def nombre(self, clave: str | None) -> str:
        if not clave:
            return "?"
        amigo = self.vida.amigos.get(clave)
        return amigo.nombre_pila if amigo else clave.title()

    def nombres(self, claves) -> str:
        return lista([self.nombre(c) for c in claves]) or "nadie"

    def pago(self, pago_id: str | None) -> str:
        v = self.verdad.get(pago_id or "")
        if v is None:
            return pago_id or "?"
        return f"{v.comercio or 'pago'} del {fecha_corta(v.fecha.isoformat())} ({euros(str(v.importe))})"

    def en_realidad(self, pago_id: str | None) -> str:
        """La verdad oculta de un pago, en una frase."""
        v = self.verdad.get(pago_id or "")
        if v is None:
            return "sin verdad conocida"
        if not v.acompanado:
            return "fue solo"
        if not v.cuotas:
            return "fue con gente, pero nadie le debe nada"
        partes = []
        for clave, cuota in v.cuotas.items():
            r = v.por_persona.get(clave)
            nota = []
            if r is not None and r.no_paga:
                nota.append("no pagará")
            elif r is not None and r.pagado_por:
                nota.append(f"lo paga {self.nombre(r.pagado_por)}")
            elif r is not None and r.dia_pagaria_solo:
                nota.append(f"pagaría solo el {fecha_corta(r.dia_pagaria_solo.isoformat())} por {r.canal}")
            partes.append(f"{self.nombre(clave)} {euros(str(cuota))}" + (f" [{', '.join(nota)}]" if nota else ""))
        return "fue con " + lista(partes)


# --- Cada evento en una línea ------------------------------------------------------------------

def linea(e: dict, c: Contexto) -> str | None:
    t = e["tipo"]
    if t == "pago":
        return f"PAGO {e['comercio'] or '(sin comercio)'} {euros(e['importe'])}. En realidad: {c.en_realidad(e['pago_id'])}."
    if t == "caso":
        if e["escenario"] == "pago_individual":
            return None                                       # se cuenta en la pregunta o el silencio
        quien = c.nombres(e["deudores"])
        return f"Meisam abre un caso de deuda ({e['origen'] or 'motor'}): {quien} por {c.pago(e['pago_id'])}."
    if t == "silencio":
        motivos = c.motivos.get(e["caso_id"])
        extra = f" Motivos: {motivos.rstrip('.')}." if motivos else ""
        juicio = "habría sido útil preguntar (se pierde)" if e["habria_sido_util"] else "bien: no había nada que reclamar"
        return f"MEISAM CALLA (nivel {e['nivel']}) por {c.pago(e['pago_id'])}. En realidad: {juicio}.{extra}"
    if t == "pregunta":
        sug = e.get("sugerencia")
        txt = f"MEISAM PREGUNTA (nivel {e['nivel']}: {NIVELES.get(e['nivel'], '?')}; {e['canal']}) por {c.pago(e['pago_id'])}"
        txt += ": «¿Fuiste con alguien?»"
        if sug:
            ok = e.get("sugerencia_correcta")
            txt += (f" Sugiere: {c.nombres(sug['personas'])}"
                    + (" (acierta)" if ok else " (falla)" if ok is False else ""))
        motivos = c.motivos.get(e["caso_id"])
        if motivos:
            txt += f". Motivos: {motivos.rstrip('.')}"
        txt += f". En realidad: {c.en_realidad(e['pago_id'])}"
        if e["inutil"]:
            txt += f" (pregunta inútil: {INUTIL.get(e['inutil'], e['inutil'])})"
        return txt + "."
    if t == "respuesta":
        if e["accion"] == "con_personas":
            dicho = "«con " + (c.nombres(e["personas"]) if e["personas"] else "gente que Meisam no conoce") + "»"
            if e.get("sugerencia_aceptada") is True:
                dicho += ", aceptando la sugerencia"
            elif e.get("sugerencia_aceptada") is False:
                dicho += ", corrigiendo la sugerencia"
        else:
            dicho = {"iba_solo": "«iba solo»", "nadie_me_debe": "«nadie me debe nada»"}.get(e["accion"], e["accion"])
        txt = f"LA PERSONA CONTESTA a las {e['retraso_horas']} h: {dicho}"
        if e.get("ruido"):
            txt += " (se equivoca: no es lo que pasó)"
        if e.get("ok") is False:
            txt += f". El sistema no lo admitió: {e.get('error')}"
        return txt + "."
    if t == "ignorada":
        objeto = "la pregunta" if e["objeto"] == "pregunta" else "el aviso"
        return f"LA PERSONA IGNORA {objeto}: {IGNORADA.get(e['motivo'], e['motivo'])}."
    if t == "aviso":
        partes = []
        for p in e["personas"]:
            rasgos = []
            if not p["deudor_verdad"]:
                rasgos.append("en realidad no le debe nada")
            if p["a_destiempo"]:
                rasgos.append("a destiempo: iba a pagar solo")
            if p["ya_devuelto"]:
                rasgos.append("ya lo había devuelto")
            partes.append(f"{c.nombre(p['clave'])} {euros(p['cuota'])}" + (f" [{'; '.join(rasgos)}]" if rasgos else ""))
        motivos = " ".join(c.motivos.get(i, "") for i in e["casos"][:1]).strip()
        return (f"MEISAM AVISA ({'al móvil' if e['canal'] == 'push' else 'en el resumen'}) de la deuda de "
                f"{c.pago(e['pago_id'])}: {lista(partes) or '?'}." + (f" Motivos: {motivos.rstrip('.')}." if motivos else ""))
    if t == "accion_aviso":
        return f"LA PERSONA DECIDE a las {e['retraso_horas']} h: {MODO.get(e['modo'], e['modo'])}."
    if t == "solicitud":
        return (f"Pide Bizum a {c.nombre(e['contraparte'])} por {euros(e['importe'])}"
                + (" (a destiempo)" if e.get("a_destiempo") else "") + ("" if e["ok"] else f" (falló: {e.get('error')})") + ".")
    if t == "reclamo":
        return f"Se lo dice en persona a {c.nombre(e['contraparte'])}" + (" (a destiempo)" if e.get("a_destiempo") else "") + "."
    if t == "reaccion":
        cuando = "fuera de las 8 semanas" if e.get("fuera_de_ventana") else fecha_corta(e["llega"])
        return (f"(verdad) {c.nombre(e['contraparte'])} pagará {euros(e['importe'])} por {e['canal']}: {cuando}.")
    if t == "cobro":
        origen = "sin que se lo pidan" if e["origen"] == "solo" else "tras pedírselo"
        return f"COBRO: {c.nombre(e['contraparte'])} devuelve {euros(e['importe'])} por {e['canal']} ({origen}) de {c.pago(e['pago_id'])}."
    if t == "efectivo":
        if e["declara"]:
            return f"{c.nombre(e['contraparte'])} le dio el efectivo y la persona lo marca como cobrado."
        return f"{c.nombre(e['contraparte'])} le dio el efectivo y la persona NO lo marca: Meisam no lo sabe."
    if t == "correccion":
        motivo = "no es deudor" if e["motivo"] == "no_es_deudor" else "no quiere que se le recuerde"
        return f"La persona quita a {c.nombre(e['contraparte'])} del caso ({motivo})."
    if t == "feedback":
        return f"Feedback a Meisam: {e['resultado']}."
    if t == "silencia":
        return f"La persona pulsa «no me preguntes por este sitio»: {e['comercio']}."
    if t == "chat":
        return f"CHAT: {e['tipo_entrada']} -> {e['herramienta']}: {e.get('resultado') or e.get('omitido')}."
    if t == "cierre":
        quienes = ", ".join(f"{c.nombre(d['clave'])} {d['estado']}" + (f" por {d['via']}" if d.get("via") else "")
                            for d in e["deudores"])
        return f"Caso cerrado ({e['estado']}) de {c.pago(e['pago_id'])}" + (f": {quienes}" if quienes else "") + "."
    if t == "error":
        return f"ERROR DEL SISTEMA en {e['donde']}: {e['error']}"
    return None                                               # toque, saltado...


def estado_deuda(e: dict, c: Contexto) -> str:
    """Una deuda al final: qué pasó y cómo se juzga a los 21 días (como la medida «dinero que se escapa»)."""
    cierre = date.fromisoformat(e["fecha_pago"]) + timedelta(days=21)
    devuelto = date.fromisoformat(e["devuelto_el"]) if e.get("devuelto_el") else None
    reclamado = date.fromisoformat(e["reclamado_el"]) if e.get("reclamado_el") else None
    cabecera = f"{c.nombre(e['contraparte'])} debía {euros(e['cuota'])} de {c.pago(e['pago_id'])}: "
    hechos = []
    if e.get("recordado_el"):
        hechos.append(f"Meisam se lo recordó el {fecha_corta(e['recordado_el'])}"
                      + (" (a destiempo)" if e.get("primer_recordatorio_a_destiempo") else ""))
    if reclamado:
        hechos.append(f"la persona lo reclamó el {fecha_corta(e['reclamado_el'])}")
    if devuelto:
        sin = ", sin declarar: Meisam no lo sabe" if e.get("canal_devuelto") == "efectivo" and e.get("declarado") is not True else ""
        hechos.append(f"devuelto el {fecha_corta(e['devuelto_el'])} ({plural(e['dias_hasta_cobrar'], 'día', 'días')}, por "
                      f"{e.get('canal_devuelto')}{sin})")
    elif e.get("no_paga"):
        hechos.append("no pagará nunca")
    if not hechos:
        hechos.append("sin recordar ni cobrar")
    if not e.get("observable_21"):
        veredicto = "aún no se cumplen los 21 días"
    elif devuelto and devuelto <= cierre:
        veredicto = "a los 21 días: vuelve"
    elif reclamado and reclamado <= cierre:
        veredicto = "a los 21 días: reclamada, sin cobrar"
    else:
        veredicto = "a los 21 días: SE ESCAPA"
    return cabecera + "; ".join(hechos) + f" -> {veredicto}."


# --- El diario de una política -----------------------------------------------------------------

def secciones(eventos: list[dict], semana: int, ctx: Contexto) -> list[tuple[str, list[str]]]:
    """[(título, líneas)]: un bloque por día con movimiento, luego las deudas de la semana y el resumen."""
    dias: dict[str, list[str]] = {}
    for e in eventos:
        if e["semana"] != semana:
            continue
        texto = linea(e, ctx)
        if texto:
            dias.setdefault(e["dia"], []).append(texto)
    salida = [(fecha_corta(d), ls) for d, ls in sorted(dias.items())]
    inicio = ACTIVACION + timedelta(days=7 * (semana - 1))
    fin = inicio + timedelta(days=6)
    deudas = [e for e in eventos if e["tipo"] == "deuda" and inicio <= date.fromisoformat(e["fecha_pago"]) <= fin]
    salida.append(("Qué pasó con cada deuda de esta semana (al final de las 8 semanas)",
                   [estado_deuda(e, ctx) for e in deudas] or ["Ninguna deuda de esta semana."]))
    sem = [e for e in eventos if e["semana"] == semana]
    preguntas = [e for e in sem if e["tipo"] == "pregunta"]
    salida.append(("Resumen de la semana", [
        f"Meisam preguntó {plural(len(preguntas), 'vez', 'veces')} ({sum(1 for p in preguntas if p['inutil'])} "
        f"inútiles), calló {plural(sum(1 for e in sem if e['tipo'] == 'silencio'), 'vez', 'veces')} y avisó "
        f"{plural(sum(1 for e in sem if e['tipo'] == 'aviso'), 'vez', 'veces')}.",
        f"La persona hizo {sum(1 for e in sem if e['tipo'] == 'toque')} gestos y se cobraron "
        f"{euros(str(sum((Decimal(e['importe']) for e in sem if e['tipo'] == 'cobro'), Decimal('0'))))}.",
    ]))
    return salida


def motivos_de_casos(uid: str) -> dict[str, str]:
    """Motivos legibles de la escalera por caso (los anota el sistema en el historial del caso)."""
    from backend import casos
    salida: dict[str, str] = {}
    for caso in casos.cargar(uid):
        for cambio in caso.historial:
            if cambio.cambio.startswith("Escalera de la pregunta"):
                salida[caso.id] = cambio.cambio.split(":", 1)[1].strip() if ":" in cambio.cambio else cambio.cambio
    return salida


def correr(vida: Vida, semilla: int, politicas: tuple[str, ...]) -> dict[str, tuple[list[dict], dict[str, str]]]:
    """Simula las políticas sobre la MISMA vida y suerte, en un `DATOS_USUARIO_DIR` temporal en disco (para poder leer
    después los motivos de cada caso). Devuelve `{política: (eventos, motivos por caso)}`."""
    with P.entorno_simulacion(en_memoria=False) as carpeta:
        resultados = P.simular_politicas(vida, semilla, politicas, dir_datos=carpeta)
        salida = {}
        for pol, r in resultados.items():
            salida[pol] = (r.eventos, motivos_de_casos(r.usuario_id))
    return salida


# --- Salida ------------------------------------------------------------------------------------

def envolver(texto: str, ancho: int) -> list[str]:
    return textwrap.wrap(texto, ancho, subsequent_indent="    ", break_long_words=False) or [""]


def pintar_una(titulo: str, secs: list[tuple[str, list[str]]], ancho: int) -> str:
    salida = [titulo, "=" * min(len(titulo), ancho)]
    for cabecera, lineas in secs:
        salida += ["", cabecera, "-" * min(len(cabecera), ancho)]
        for ln in lineas:
            salida += ["  " + x for x in envolver(ln, ancho - 2)]
    return "\n".join(salida)


def pintar_lado_a_lado(titulo: str, izq: tuple[str, list], der: tuple[str, list], ancho: int) -> str:
    """Dos columnas alineadas por sección (día) para ver cómo cambia lo que hace Meisam (`=`: igual en las dos)."""
    col = max(40, (ancho - 3) // 2)
    nombre_i, secs_i = izq
    nombre_d, secs_d = der
    dic_i, dic_d = dict(secs_i), dict(secs_d)
    orden = [t for t, _ in secs_i] + [t for t, _ in secs_d if t not in dic_i]
    salida = [titulo, "=" * min(len(titulo), ancho), "", f"{nombre_i.upper():<{col}} | {nombre_d.upper()}",
              "-" * col + "-+-" + "-" * col]
    for cabecera in orden:
        salida += ["", cabecera, "-" * min(len(cabecera), ancho)]

        def columna(lineas: list[str]) -> list[str]:
            return [x for ln in lineas for x in envolver("• " + ln, col)] or ["(nada)"]
        a, b = columna(dic_i.get(cabecera, [])), columna(dic_d.get(cabecera, []))
        for x, y in itertools.zip_longest(a, b, fillvalue=""):
            salida.append(f"{x:<{col}} {'=' if x == y and x.strip() else '|'} {y}")
    return "\n".join(salida)


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Diario de una vida con amigos: qué hace Meisam y qué es verdad.")
    parser.add_argument("--vida", default="alvaro", help="id de la vida (por defecto alvaro)")
    parser.add_argument("--semana", type=int, default=1, help="semana de 1 a 8 (por defecto 1)")
    parser.add_argument("--politica", default="personalizada", choices=POLITICAS_DIARIO)
    parser.add_argument("--semilla", type=int, default=0)
    parser.add_argument("--comparar", action="store_true", help="reglas y personalizada lado a lado")
    parser.add_argument("--ancho", type=int, default=None, help="columnas de la salida (110; 170 con --comparar)")
    args = parser.parse_args(argv)
    if not 1 <= args.semana <= 8:
        parser.error("La semana debe ir de 1 a 8.")
    vidas = cargar_vidas()
    if args.vida not in vidas:
        parser.error(f"Vida desconocida: {args.vida}. Hay: {', '.join(sorted(vidas))}.")
    vida = vidas[args.vida]
    politicas = ("reglas", "personalizada") if args.comparar else (args.politica,)
    try:
        corridas = correr(vida, args.semilla, politicas)
    except ValueError as error:
        parser.error(str(error))
    verdad = generar(vida, args.semilla).verdad
    secs = {}
    for pol, (eventos, motivos) in corridas.items():
        secs[pol] = secciones(eventos, args.semana, Contexto(vida, verdad, motivos))
    titulo = (f"SIMULACIÓN · diario de {vida.nombre_visible} ({vida.id}) · semana {args.semana} · semilla {args.semilla}"
              f" · vida inventada, no son datos de clientes")
    if args.comparar:
        print(pintar_lado_a_lado(titulo, ("reglas", secs["reglas"]), ("personalizada", secs["personalizada"]),
                                 args.ancho or 170))
    else:
        print(pintar_una(f"{titulo} · política {args.politica}", secs[args.politica], args.ancho or 110))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
