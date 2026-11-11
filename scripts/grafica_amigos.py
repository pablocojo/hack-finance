"""
Gráfica de la curva de amigos para la diapositiva del jurado (C9; `docs/diseno/curva-amigos.md` §6 y §4.5).

    python scripts/grafica_amigos.py                       # el amigos-*.json más reciente de evals/resultados/
    python scripts/grafica_amigos.py ruta/amigos-X.json    # uno concreto
    python scripts/grafica_amigos.py --salida otra.svg     # otra ruta de salida

Escribe `evals/resultados/curva-amigos.svg` (1920x1080, 16:9). Sin dependencias: el SVG se escribe a mano.
Dos paneles, dinero que se escapa y preguntas inútiles por semana, `reglas` frente a `personalizada` con su banda de
IC 95 %; debajo, el total de las 8 semanas de cada medida (la semana 8 sola es ruidosa) y, en pequeño, que es una
SIMULACIÓN, sus supuestos, el hash de las vidas y dónde no mejora. Las semanas sin dato (`None`) no se pintan como 0.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from xml.sax.saxutils import escape

RAIZ = Path(__file__).resolve().parent.parent
RESULTADOS = RAIZ / "evals" / "resultados"
SALIDA = RESULTADOS / "curva-amigos.svg"

ANCHO, ALTO = 1920, 1080
FUENTE = "Segoe UI, Helvetica, Arial, sans-serif"
# Okabe-Ito (aptos para daltonismo): bermellón para `reglas`, azul para `personalizada`. Además, trazo y marcador distintos.
COLOR = {"reglas": "#D55E00", "personalizada": "#0072B2"}
TINTA, SUAVE, EJE = "#1b1b1b", "#555555", "#bdbdbd"
SEMANAS = [str(s) for s in range(1, 9)]
POLITICAS = ("reglas", "personalizada")

# (medida, etiqueta, formato). Las 7 medidas de §4.4 para la fila de totales.
TOTALES = (
    ("dinero_escapa", "dinero que se escapa", "pct"),
    ("preguntas_inutiles", "preguntas inútiles", "num"),
    ("recordatorios_a_destiempo", "recordatorios a destiempo", "pct"),
    ("acierto_sugerencia", "acierto de la sugerencia", "pct"),
    ("casos_cerrados_solos", "casos cerrados solos", "pct"),
    ("toques_por_100_eur", "toques por 100 € cobrados", "num"),
    ("dias_hasta_cobrar", "días hasta cobrar", "num"),
)
SUPUESTOS_CORTOS = (
    "vidas inventadas, no son clientes",
    "tasas con que el usuario contesta a Meisam supuestas (probado también con la mitad)",
    "dinero que se escapa = lo prestado que a los 21 días ni volvió ni se reclamó (solo semanas 4-8)",
    "no cuenta quien pide que no se le recuerde; el efectivo devuelto es cobrado",
    "IC 95 % entre semillas",
    "el chat usa las etiquetas del corpus (sin extracción con IA)",
    "la IA de dudas está apagada en la simulación",
)
NBSP = chr(160)         # espacio que no parte línea: «21,1 %» no se separa de su %
UMBRAL_IGUAL = 0.02    # cambio relativo por debajo del cual se dice «igual»


# --- Formato -----------------------------------------------------------------------------------

def num(v: float, dec: int = 2) -> str:
    return f"{v:.{dec}f}".replace(".", ",")


def valor(v: float | None, formato: str) -> str:
    if v is None:
        return "sin dato"
    return f"{num(v * 100, 1)}{NBSP}%" if formato == "pct" else num(v, 2)


def nombre_vida(vida: str) -> str:
    return vida[:1].upper() + vida[1:]


def envolver(texto: str, tamano: float, ancho: float) -> list[str]:
    """Parte el texto en líneas que caben en `ancho` px (anchura media de letra ~0,5 del tamaño)."""
    maximo = max(10, int(ancho / (tamano * 0.5)))
    lineas, actual = [], ""
    for palabra in texto.split(" "):
        if actual and len(actual) + 1 + len(palabra) > maximo:
            lineas.append(actual)
            actual = palabra
        else:
            actual = f"{actual} {palabra}".strip()
    if actual:
        lineas.append(actual)
    return lineas


def texto(x: float, y: float, contenido: str, tamano: int, color: str = TINTA, peso: str = "normal",
          ancla: str = "start") -> str:
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{tamano}" font-weight="{peso}" fill="{color}" '
            f'text-anchor="{ancla}">{escape(contenido)}</text>')


# --- Datos -------------------------------------------------------------------------------------

def grupo(bloque: dict) -> dict | None:
    """El grupo con el que se compara: las vidas de ajuste o, si no hay, las de evaluación."""
    return bloque.get("ajuste") or bloque.get("evaluacion")


def serie(datos: dict, politica: str, medida: str) -> list[dict]:
    """Por semana 1-8: `{media, ic95}` (media `None` = sin dato)."""
    g = grupo(datos["resultados"][politica])
    if g is None:
        raise ValueError(f"El JSON no tiene vidas medidas para la política {politica!r}.")
    return [{"media": g["global"][medida][s]["media"], "ic95": g["global"][medida][s]["ic95"]} for s in SEMANAS]


def total(datos: dict, politica: str, medida: str, bloque: str | None = None) -> float | None:
    return total_ic(datos, politica, medida, bloque)[0]


def total_ic(datos: dict, politica: str, medida: str, bloque: str | None = None) -> tuple[float | None, list | None]:
    """Media e IC 95 % del total de las 8 semanas (`bloque`: `ajuste` o `evaluacion`; por defecto el principal)."""
    r = datos["resultados"][politica]
    g = (r.get(bloque) if bloque else grupo(r)) or {}
    celda = g["global"][medida]["total"]
    return celda["media"], celda.get("ic95")


def solapan(a: list | None, b: list | None) -> bool:
    return bool(a and b and a[0] <= b[1] and b[0] <= a[1])


def veredicto(base: float | None, nueva: float | None, debe: str, ic_base: list | None = None,
              ic_nueva: list | None = None) -> str:
    """mejora | igual | empeora. «igual» si el cambio es menor del 2 % o si los IC 95 % de las dos se solapan (no se
    puede distinguir del azar de las semillas: criterio prudente). El JSON no trae IC de la diferencia entre políticas,
    por eso se usa el solapamiento de los IC de las dos."""
    if base is None or nueva is None:
        return "sin comparar"
    if solapan(ic_base, ic_nueva):
        return "igual"
    if base == 0:
        return "igual" if nueva == 0 else ("empeora" if debe == "bajar" else "mejora")
    cambio = (nueva - base) / abs(base)
    if abs(cambio) < UMBRAL_IGUAL:
        return "igual"
    bueno = cambio < 0 if debe == "bajar" else cambio > 0
    return "mejora" if bueno else "empeora"


def conclusion(datos: dict) -> str:
    """Título con la conclusión en una frase, calculada del JSON: dice «igual» o «empeora» cuando es lo que hay."""
    partes = []
    for medida, etiqueta, formato, unidad, plural in (
            ("dinero_escapa", "el dinero que se escapa", "pct", "", False),
            ("preguntas_inutiles", "las preguntas inútiles", "num", " por vida", True)):
        (b, ib), (n, i_n) = total_ic(datos, "reglas", medida), total_ic(datos, "personalizada", medida)
        if b is None or n is None:
            partes.append(f"{etiqueta}: sin dato")
            continue
        v = veredicto(b, n, "bajar", ib, i_n)
        if v == "igual":
            detalle = f"{valor(b, formato)}{unidad}" if valor(b, formato) == valor(n, formato) else (
                f"{valor(b, formato)} a {valor(n, formato)}{unidad}, dentro del IC{NBSP}95{NBSP}%")
            partes.append(f"{etiqueta} {'no cambian' if plural else 'no cambia'} ({detalle})")
            continue
        cambio = f", {'-' if n < b else '+'}{abs(round((n - b) / b * 100)) if b else 0}{NBSP}%"
        palabra = ("bajan" if plural else "baja") if v == "mejora" else ("SUBEN" if plural else "SUBE")
        partes.append(f"{etiqueta} {palabra} ({valor(b, formato)} a {valor(n, formato)}{unidad}{cambio})")
    return "Con lo que aprende de cada usuario, " + " y ".join(partes)


def sin_mejora(datos: dict) -> list[str]:
    """Vidas en las que `personalizada` no mejora a `reglas` (total de 8 semanas): §4.5, enseñar dónde no mejora."""
    por = {p: datos["resultados"].get(p, {}).get("por_vida", {}) for p in POLITICAS}
    ajuste = set((grupo(datos["resultados"]["personalizada"]) or {}).get("vidas", [])) or set(por["reglas"])
    por = {p: {v: x for v, x in vs.items() if v in ajuste} for p, vs in por.items()}   # Nerea y Pilar van aparte
    frases = []
    for medida, etiqueta in (("dinero_escapa", "dinero que se escapa"), ("preguntas_inutiles", "preguntas inútiles")):
        vidas = []
        for vida in sorted(set(por["reglas"]) & set(por["personalizada"])):
            cb, cn = por["reglas"][vida][medida]["total"], por["personalizada"][vida][medida]["total"]
            b, n = cb["media"], cn["media"]
            if b is not None and n is not None and veredicto(b, n, "bajar", cb.get("ic95"), cn.get("ic95")) in (
                    "igual", "empeora"):
                vidas.append(nombre_vida(vida))
        if vidas:
            total_vidas = len(set(por["reglas"]) & set(por["personalizada"]))
            lista = f"todas las vidas ({total_vidas})" if len(vidas) == total_vidas else ", ".join(vidas)
            frases.append(f"{etiqueta}: {lista}")
    return frases


# --- Dibujo ------------------------------------------------------------------------------------

def tope(mayor: float) -> float:
    """Máximo «redondo» del eje por encima de `mayor` (el eje arranca en 0)."""
    mayor = max(mayor, 1e-9)
    candidatos = [paso * escala for paso in (1, 2, 3, 4, 5, 6, 8) for escala in (0.001, 0.01, 0.1, 1, 10, 100)]
    return min(c for c in candidatos if c >= mayor * 1.05)


def tramos(puntos: list[tuple[float, float, float | None, float | None] | None]) -> list[list[tuple]]:
    """Trozos de semanas seguidas con dato: la semana sin dato corta la línea, no baja a 0."""
    salida, actual = [], []
    for p in puntos:
        if p is None:
            if actual:
                salida.append(actual)
            actual = []
        else:
            actual.append(p)
    if actual:
        salida.append(actual)
    return salida


def panel(datos: dict, medida: str, titulo: str, formato: str, x: float, y: float, ancho: float, alto: float,
          idx: int) -> list[str]:
    margen_izq, margen_der = 95, 220
    x0, x1 = x + margen_izq, x + ancho - margen_der
    y0, y1 = y, y + alto
    series = {p: serie(datos, p, medida) for p in POLITICAS}
    todos = []
    for s in series.values():
        for p in s:
            if p["media"] is not None:
                todos.append(p["media"])
    medias_max = max(todos + [1e-9])
    altos = [p["ic95"][1] for s in series.values() for p in s if p["media"] is not None and p["ic95"]]
    ymax = tope(min(max(todos + altos + [1e-9]), medias_max * 2.2))

    def px(i: int) -> float:
        return x0 + 25 + i * (x1 - x0 - 50) / 7

    def py(v: float) -> float:
        return y1 - max(0.0, v) / ymax * (y1 - y0)

    sal = [f'<g id="panel-{idx}">', texto(x, y - 38, titulo, 34, TINTA, "bold")]
    sal.append(f'<clipPath id="recorte-{idx}"><rect x="{x0 - 5}" y="{y0 - 4}" width="{x1 - x0 + 10}" '
               f'height="{y1 - y0 + 8}"/></clipPath>')
    for k in range(3):                                   # solo 3 marcas: 0, mitad y tope (sin rejilla recargada)
        v = ymax * k / 2
        yy = py(v)
        sal.append(f'<line x1="{x0}" y1="{yy:.1f}" x2="{x1}" y2="{yy:.1f}" stroke="{EJE}" '
                   f'stroke-width="{2 if k == 0 else 1}"/>')
        etiqueta = f"{num(v * 100, 0)} %" if formato == "pct" else num(v, 2 if ymax < 5 else 0)
        sal.append(texto(x0 - 14, yy + 9, etiqueta, 26, SUAVE, ancla="end"))
    for i, s in enumerate(SEMANAS):
        sal.append(texto(px(i), y1 + 40, f"S{s}", 26, SUAVE, ancla="middle"))
    sal.append(texto((x0 + x1) / 2, y1 + 78, "semana", 22, SUAVE, ancla="middle"))
    # semanas sin dato: se dice, no se pinta un 0
    sin_dato = [i for i, p in enumerate(series["reglas"]) if p["media"] is None]
    if sin_dato and len(sin_dato) < 8:
        mitad = (px(sin_dato[0]) + px(sin_dato[-1])) / 2
        sal.append(texto(mitad, y1 - 52, "sin dato aún", 24, SUAVE, ancla="middle"))
        sal.append(texto(mitad, y1 - 24, "(el cargo no cumple 21 días)", 20, SUAVE, ancla="middle"))
    extremos = {}
    for pol in POLITICAS:                                 # primero reglas (debajo), luego personalizada
        color = COLOR[pol]
        puntos = [None if p["media"] is None else (px(i), py(p["media"]), p["ic95"], p["media"])
                  for i, p in enumerate(series[pol])]
        for tramo in tramos(puntos):
            if len(tramo) >= 2 and all(t[2] for t in tramo):
                sup = " ".join(f"{t[0]:.1f},{py(t[2][1]):.1f}" for t in tramo)
                inf = " ".join(f"{t[0]:.1f},{py(t[2][0]):.1f}" for t in reversed(tramo))
                sal.append(f'<polygon points="{sup} {inf}" fill="{color}" fill-opacity="0.16" '
                           f'clip-path="url(#recorte-{idx})"/>')
            else:
                for t in tramo:
                    if t[2]:
                        sal.append(f'<line x1="{t[0]:.1f}" y1="{py(t[2][1]):.1f}" x2="{t[0]:.1f}" y2="{py(t[2][0]):.1f}" '
                                   f'stroke="{color}" stroke-opacity="0.5" stroke-width="4" '
                                   f'clip-path="url(#recorte-{idx})"/>')
            trazo = "stroke-dasharray=\"14 8\" " if pol == "reglas" else ""
            ancho_l = 6 if pol == "reglas" else 5
            ruta = " ".join(f"{t[0]:.1f},{t[1]:.1f}" for t in tramo)
            if len(tramo) >= 2:
                sal.append(f'<polyline points="{ruta}" fill="none" stroke="{color}" stroke-width="{ancho_l}" {trazo}'
                           f'stroke-linejoin="round" stroke-linecap="round"/>')
            for t in tramo:
                if pol == "reglas":
                    sal.append(f'<rect x="{t[0] - 8:.1f}" y="{t[1] - 8:.1f}" width="16" height="16" fill="{color}"/>')
                else:
                    sal.append(f'<circle cx="{t[0]:.1f}" cy="{t[1]:.1f}" r="8" fill="{color}"/>')
        ultimo = next((p for p in reversed(puntos) if p is not None), None)
        if ultimo:
            extremos[pol] = (ultimo[0], ultimo[1], ultimo[3])
    # etiqueta directa al final de cada línea (sin leyenda); si chocan, se separan
    ys = {p: e[1] for p, e in extremos.items()}
    if len(ys) == 2 and abs(ys["reglas"] - ys["personalizada"]) < 84:
        centro = (ys["reglas"] + ys["personalizada"]) / 2
        arriba = "reglas" if ys["reglas"] <= ys["personalizada"] else "personalizada"
        abajo = "personalizada" if arriba == "reglas" else "reglas"
        ys[arriba], ys[abajo] = centro - 42, centro + 42
    for pol, (ex, _ey, v) in extremos.items():
        sal.append(texto(ex + 22, ys[pol] + 2, pol, 28, COLOR[pol], "bold"))
        sal.append(texto(ex + 22, ys[pol] + 30, f"total {valor(total(datos, pol, medida), formato)}", 26, COLOR[pol],
                         "bold"))
        sal.append(texto(ex + 22, ys[pol] + 54, f"S8: {valor(v, formato)}", 20, SUAVE))
    sal.append("</g>")
    return sal


def fila_totales(datos: dict, y: float) -> list[str]:
    """Tabla: una columna por medida y una fila por política (etiqueta de fila una sola vez, a la izquierda)."""
    sal = [texto(70, y, "Total de las 8 semanas (la semana 8 sola es ruidosa)", 28, TINTA, "bold")]
    medidas = datos.get("medidas", {})
    x_fila, ancho = 70, (ANCHO - 140 - 200) / len(TOTALES)
    for texto_fila, color, dy in (("reglas", COLOR["reglas"], 98), ("personalizada", COLOR["personalizada"], 138),
                                  ("frente a reglas", SUAVE, 174)):
        sal.append(texto(x_fila, y + dy, texto_fila, 24 if dy < 170 else 20, color, "bold" if dy < 170 else "normal"))
    for k, (medida, etiqueta, formato) in enumerate(TOTALES):
        x = 70 + 200 + k * ancho
        try:
            b, n = total(datos, "reglas", medida), total(datos, "personalizada", medida)
        except KeyError:
            continue
        v = veredicto(b, n, medidas.get(medida, {}).get("debe", "bajar"), total_ic(datos, "reglas", medida)[1],
                      total_ic(datos, "personalizada", medida)[1])
        sal.append(f'<line x1="{x:.1f}" y1="{y + 14}" x2="{x + ancho - 18:.1f}" y2="{y + 14}" stroke="{EJE}" '
                   f'stroke-width="1"/>')
        for i, linea in enumerate(envolver(etiqueta, 22, ancho - 18)[:2]):
            sal.append(texto(x, y + 38 + i * 24, linea, 22, SUAVE))
        sal.append(texto(x, y + 98, valor(b, formato), 28, COLOR["reglas"], "bold"))
        sal.append(texto(x, y + 138, valor(n, formato), 28, COLOR["personalizada"], "bold"))
        sal.append(texto(x, y + 174, v, 22, SUAVE))
    return sal


def fila_evaluacion(datos: dict, y: float) -> list[str]:
    """Las vidas solo de evaluación (Nerea y Pilar), aparte: nunca se ajustó con ellas, así que es la prueba más limpia."""
    bloques = [datos["resultados"][p].get("evaluacion") for p in POLITICAS]
    if not all(bloques):
        return []
    nombres = lista_nombres([nombre_vida(v) for v in bloques[1].get("vidas", [])])
    partes = []
    for medida, etiqueta, formato in (("preguntas_inutiles", "preguntas inútiles", "num"),
                                      ("dinero_escapa", "dinero que se escapa", "pct")):
        (b, ib), (n, i_n) = (total_ic(datos, p, medida, "evaluacion") for p in POLITICAS)
        v = veredicto(b, n, "bajar", ib, i_n)
        palabra = {"mejora": "mejora", "igual": "NO MEJORA (igual)", "empeora": "EMPEORA"}.get(v, "sin comparar")
        partes.append(f"{etiqueta} {valor(b, formato)} a {valor(n, formato)}: {palabra}")
    texto_fila = (f"Solo evaluación, vidas nuevas con las que no se ajustó nada ({nombres}, semillas 100 o más; total de "
                  f"las 8 semanas, reglas a personalizada): " + "; ".join(partes) + ".")
    sal = []
    for linea in envolver(texto_fila, 24, ANCHO - 140)[:2]:
        sal.append(texto(70, y, linea, 24, TINTA, "bold"))
        y += 28
    return sal


def lista_nombres(nombres: list[str]) -> str:
    if len(nombres) <= 1:
        return "".join(nombres)
    return ", ".join(nombres[:-1]) + " y " + nombres[-1]


def pie(datos: dict, y: float) -> list[str]:
    g = grupo(datos["resultados"]["personalizada"]) or {}
    vidas = len(g.get("vidas", datos.get("vidas", [])))
    semillas = len(datos.get("semillas", []))
    codigo = str(datos.get("hash_vidas", ""))[:8]
    frases = [f"Simulación: {vidas} vidas × {semillas} semillas · supuestos: " + "; ".join(SUPUESTOS_CORTOS)
              + f" · vidas {codigo}"]
    malas = sin_mejora(datos)
    cola = "Dónde no mejora (vidas de ajuste, total 8 semanas) · " + (" · ".join(malas) if malas else "en ninguna vida")
    sens = datos.get("sensibilidad", {}).get("resultados", {})
    try:
        gb, gn = (grupo(sens[p]) for p in POLITICAS)
        sb, sn = gb["dinero_escapa"]["total"]["media"], gn["dinero_escapa"]["total"]["media"]
        cola += (f" · Con la mitad de respuestas del usuario, el dinero que se escapa va de {valor(sb, 'pct')} (reglas) "
                 f"a {valor(sn, 'pct')} (personalizada).")
    except (KeyError, TypeError):
        pass
    frases.append(cola)
    sal = []
    for frase in frases:
        for linea in envolver(frase, 19, ANCHO - 140):
            sal.append(texto(70, y, linea, 19, SUAVE))
            y += 23
    return sal


def generar_svg(datos: dict) -> str:
    """El SVG completo (cadena) a partir del JSON de `evals/medir_amigos.py`."""
    if "resultados" not in datos or "reglas" not in datos["resultados"] or "personalizada" not in datos["resultados"]:
        raise ValueError("El JSON no es de la curva de amigos o le faltan las políticas `reglas` y `personalizada`. "
                         "Genera uno con: python evals/medir.py --parte amigos")
    partes = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{ANCHO}" height="{ALTO}" viewBox="0 0 {ANCHO} {ALTO}" '
              f'font-family="{FUENTE}" role="img" aria-labelledby="t d">',
              '<title id="t">Curva de amigos: reglas frente a personalizada</title>',
              '<desc id="d">Dinero que se escapa y preguntas inútiles por semana, con banda de IC 95 %. Simulación.</desc>',
              f'<rect width="{ANCHO}" height="{ALTO}" fill="#ffffff"/>']
    y = 70
    for linea in envolver(conclusion(datos), 42, ANCHO - 140)[:2]:
        partes.append(texto(70, y, linea, 42, TINTA, "bold"))
        y += 54
    ancho_panel = (ANCHO - 140 - 50) / 2
    partes += panel(datos, "dinero_escapa", "Dinero que se escapa (% de lo prestado)", "pct", 70, 235, ancho_panel, 290, 0)
    partes += panel(datos, "preguntas_inutiles", "Preguntas inútiles (por vida y semana)", "num",
                    70 + ancho_panel + 50, 235, ancho_panel, 290, 1)
    partes += fila_totales(datos, 645)
    partes += fila_evaluacion(datos, 855)
    partes += pie(datos, 925)
    partes.append("</svg>")
    return "\n".join(partes) + "\n"


def ultimo_json(directorio: Path = RESULTADOS) -> Path:
    candidatos = sorted(directorio.glob("amigos-*.json"))
    if not candidatos:
        raise ValueError(f"No hay ningún amigos-*.json en {directorio}. Genera uno con: "
                         "python evals/medir.py --parte amigos")
    return candidatos[-1]


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Gráfica de la curva de amigos (SVG sin dependencias).")
    parser.add_argument("json", nargs="?", type=Path, help="amigos-*.json (por defecto, el más reciente)")
    parser.add_argument("--salida", type=Path, default=SALIDA, help=f"SVG de salida (por defecto {SALIDA})")
    args = parser.parse_args(argv)
    try:
        ruta = args.json or ultimo_json()
        datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
        svg = generar_svg(datos)
    except (ValueError, OSError) as error:
        parser.error(str(error))
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    args.salida.write_text(svg, encoding="utf-8")
    print(f"{args.salida}  (de {ruta})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
