"""
Medidas de la curva de amigos (C6; `docs/diseno/curva-amigos.md` §4.4): las vidas con amigos sobre el sistema real
(`backend/personalizacion/simulacion/amigos/`), 8 semanas, sin Claude ni internet.

    python evals/medir.py --parte amigos                                   # vidas de ajuste, semillas 0-9
    python evals/medir.py --parte amigos --semillas 0-1 --vidas alvaro,diego
    python evals/medir.py --parte amigos --semillas 100-119 --vidas todas  # curva final (con Nerea y Pilar, aparte)
    python evals/medir.py --parte amigos --politicas reglas,personalizada,personalizada_sin_chat --sin-sensibilidad

Escribe `evals/resultados/amigos-<fecha>.json` con `semillas`, `hash_vidas` (contenido de `vidas/*.yaml` + corpus del
chat), `supuestos`, `politicas`, las medidas por usuario y semana (media e IC 95 % sobre las semillas, globales y por
grado de rutina y de chat), los objetivos de §4.4 y, salvo con `--sin-sensibilidad`, lo mismo con las tasas de respuesta
a la mitad (`sensibilidad`, aparte).

Ajuste y evaluación van separados: las semillas 0-9 y las 8 vidas de ajuste sirven para ajustar; las 100-119 para la
curva final; Nerea y Pilar (solo evaluación) exigen semillas >= 100 y salen siempre por separado.

Cada (vida, semilla) va en un proceso (`protocolo.simular_en_paralelo`, cada uno con su `DATOS_USUARIO_DIR` temporal).
"""

from __future__ import annotations

import hashlib
import subprocess
import time
from datetime import datetime
from pathlib import Path

from backend.personalizacion.simulacion.amigos import medidas as M
from backend.personalizacion.simulacion.amigos import protocolo as P
from backend.personalizacion.simulacion.amigos.esquema import DIR_VIDAS, RAIZ, RUTA_CORPUS, Vida, cargar_vidas

POLITICAS_POR_DEFECTO = ("reglas", "personalizada")
SEMILLAS_POR_DEFECTO = tuple(range(10))
SEMILLA_EVALUACION = 100
FACTOR_SENSIBILIDAD = M.FACTOR_SENSIBILIDAD
# Medidas que se repiten, por política, en la sensibilidad.
CLAVES_RESUMEN = ("dinero_escapa", "dinero_escapa_eur", "preguntas", "preguntas_inutiles", "acierto_sugerencia",
                  "casos_cerrados_solos", "recordatorios_a_destiempo", "toques_por_100_eur", "dias_hasta_cobrar")


# --- Entradas ----------------------------------------------------------------------------------

def parse_semillas(texto: str) -> tuple[int, ...]:
    """`0-9`, `0,3,5-7` o `100-119` -> tupla ordenada sin repetidos."""
    salida: set[int] = set()
    try:
        for trozo in str(texto).split(","):
            trozo = trozo.strip()
            if "-" in trozo:
                a, b = (int(x) for x in trozo.split("-", 1))
                if b < a:
                    raise ValueError
                salida.update(range(a, b + 1))
            elif trozo:
                salida.add(int(trozo))
    except ValueError:
        raise ValueError(f"Semillas no válidas: {texto!r}. Usa un número, una lista o un rango (0-9, 0,3,5-7).") from None
    if not salida:
        raise ValueError("Indica al menos una semilla (por ejemplo 0-9).")
    return tuple(sorted(salida))


def elegir_vidas(texto: str | None, vidas: dict[str, Vida]) -> tuple[str, ...]:
    """`ajuste` (por defecto), `evaluacion`, `todas` o una lista de ids separados por comas."""
    texto = (texto or "ajuste").strip().lower()
    if texto in ("ajuste", "evaluacion", "todas"):
        return tuple(v for v, x in vidas.items() if texto == "todas" or x.uso == texto)
    ids = tuple(t.strip() for t in texto.split(",") if t.strip())
    desconocidas = [i for i in ids if i not in vidas]
    if desconocidas:
        raise ValueError(f"Vida desconocida: {', '.join(desconocidas)}. Hay: {', '.join(sorted(vidas))}.")
    return ids


def comprobar_separacion(vidas: dict[str, Vida], ids: tuple[str, ...], semillas: tuple[int, ...]) -> None:
    """Nerea y Pilar son solo de evaluación: no se miran con las semillas de ajuste."""
    evaluacion = [i for i in ids if vidas[i].uso == "evaluacion"]
    if evaluacion and min(semillas) < SEMILLA_EVALUACION:
        raise ValueError(f"{', '.join(evaluacion)} son solo de evaluación: usa semillas >= {SEMILLA_EVALUACION} "
                         "(las 0-9 y las vidas de ajuste son para ajustar).")


def hash_vidas() -> dict:
    """Hash del contenido de `vidas/*.yaml` y del corpus del chat: prueba de que no se tocaron al ajustar."""
    por_archivo = {}
    total = hashlib.sha256()
    for ruta in [*sorted(DIR_VIDAS.glob("*.yaml")), RUTA_CORPUS]:
        if not ruta.exists():
            continue
        h = hashlib.sha256(ruta.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
        por_archivo[ruta.name] = h[:16]
        total.update(ruta.name.encode() + b"\0" + h.encode())
    return {"hash_vidas": total.hexdigest(), "archivos": por_archivo}


def _version_git() -> str | None:
    try:
        salida = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=RAIZ, capture_output=True, text=True,
                                timeout=5)
        return salida.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


# --- Ejecución ---------------------------------------------------------------------------------

def _correr(vidas: dict[str, Vida], ids: tuple[str, ...], semillas: tuple[int, ...], politicas: tuple[str, ...],
            factor: float, procesos: int | None) -> tuple[list[dict], dict]:
    # una tarea por política: generar la vida cuesta ~0,1 s y así los procesos quedan mejor repartidos
    tareas = [(v, s, (p,), factor) for v in ids for s in semillas for p in politicas]
    resultados = P.simular_en_paralelo(tareas, procesos)
    corridas, errores, saltado, vacios = [], {}, {}, {}
    for r in resultados:
        corridas.append({"vida": r.vida_id, "semilla": r.semilla, "politica": r.politica,
                         "medidas": M.medir_corrida(r.eventos, vidas[r.vida_id])})
        n_err = sum(1 for e in r.eventos if e["tipo"] == "error")
        errores[r.politica] = errores.get(r.politica, 0) + n_err
        for pieza, n in r.saltado.items():
            saltado.setdefault(r.politica, {})[pieza] = saltado.get(r.politica, {}).get(pieza, 0) + n
        v = vacios.setdefault(r.politica, [0, 0])
        v[0] += 1 if r.aprendizaje_final.get("vacio") else 0
        v[1] += 1
    estado = {"errores_del_sistema": errores, "piezas_saltadas": saltado,
              "aprendizaje_vacio": {p: f"{a}/{n} corridas" for p, (a, n) in vacios.items()}}
    return corridas, estado


def medir(anterior: dict | None = None, archivo_anterior: str | None = None, *,
          semillas: tuple[int, ...] = SEMILLAS_POR_DEFECTO, vidas: str | None = None,
          politicas: tuple[str, ...] = POLITICAS_POR_DEFECTO, procesos: int | None = None,
          sensibilidad: bool = True) -> dict:
    """Ejecuta la tanda y devuelve el JSON (la tarea `medir.py` lo guarda)."""
    todas = cargar_vidas()
    ids = elegir_vidas(vidas, todas)
    comprobar_separacion(todas, ids, semillas)
    for p in politicas:
        if p not in P.POLITICAS:
            raise ValueError(f"Política desconocida: {p!r}. Elige entre {', '.join(P.POLITICAS)}.")
    t0 = time.perf_counter()
    corridas, estado = _correr(todas, ids, semillas, politicas, 1.0, procesos)
    resultados = M.agregar(corridas, todas)
    duracion = time.perf_counter() - t0
    resultado = {
        "parte": "amigos", "estado": "ok", "simulacion": True,
        "generado": datetime.now().isoformat(timespec="seconds"), "version_git": _version_git(),
        "semillas": list(semillas),
        "fase": "ajuste" if max(semillas) < SEMILLA_EVALUACION else "evaluacion" if min(semillas) >= SEMILLA_EVALUACION
        else "mixta",
        "vidas": list(ids), "politicas": list(politicas), **hash_vidas(),
        "supuestos": M.SUPUESTOS, "procesos": procesos if procesos is not None else "auto",
        "duracion_s": round(duracion, 1), "corridas": len(corridas),
        "medidas": {n: {"tipo": m.tipo, "debe": m.debe, "descripcion": m.descripcion} for n, m in M.MEDIDAS.items()},
        "semanas_deuda": "las medidas de deuda se juzgan en la semana en que se cumplen los 21 días del cargo "
                         "(semanas 4-8; semana_cargo = semana - 3)",
        "comprobaciones": estado,
        "resultados": resultados,
        "objetivos": M.objetivos(resultados),
    }
    if sensibilidad:
        pols = tuple(p for p in politicas if p != "personalizada_sin_chat") or politicas
        t1 = time.perf_counter()
        corridas_s, estado_s = _correr(todas, ids, semillas, pols, FACTOR_SENSIBILIDAD, procesos)
        res_s = M.agregar(corridas_s, todas)
        resultado["sensibilidad"] = {
            "factor_respuesta": FACTOR_SENSIBILIDAD, "politicas": list(pols),
            "nota": "tasas con que el usuario contesta a Meisam (push y resumen) a la mitad; el resto igual",
            "duracion_s": round(time.perf_counter() - t1, 1), "comprobaciones": estado_s,
            "resultados": {p: {g: {k: v for k, v in bloque.get("global", {}).items() if k in CLAVES_RESUMEN}
                               for g, bloque in b.items() if g in ("ajuste", "evaluacion")} for p, b in res_s.items()},
            "objetivos": M.objetivos(res_s),
        }
    else:
        resultado["sensibilidad"] = {"estado": "no medida (se pidió --sin-sensibilidad)"}
    resultado["comparacion"] = _comparar(resultado, anterior, archivo_anterior)
    return resultado


def _comparar(actual: dict, anterior: dict | None, archivo: str | None) -> dict | None:
    if not anterior or anterior.get("parte") != "amigos" or "resultados" not in anterior:
        return None
    salida: dict = {"con": archivo, "mismas_vidas": anterior.get("hash_vidas") == actual["hash_vidas"],
                    "mismas_semillas": anterior.get("semillas") == actual["semillas"],
                    "mismas_vidas_medidas": anterior.get("vidas") == actual["vidas"], "politicas": {}}
    for pol, bloque in actual["resultados"].items():
        previo = anterior["resultados"].get(pol, {}).get("ajuste")
        ahora = bloque.get("ajuste")
        if not previo or not ahora:
            continue
        salida["politicas"][pol] = {
            m: {"antes": previo["global"][m]["total"]["media"], "ahora": ahora["global"][m]["total"]["media"]}
            for m in ("dinero_escapa", "preguntas_inutiles", "recordatorios_a_destiempo", "acierto_sugerencia")}
    return salida


# --- Resumen -----------------------------------------------------------------------------------

def _fmt(v, pct: bool = False) -> str:
    if v is None:
        return "  -  "
    return f"{v * 100:5.1f}%" if pct else f"{v:6.2f}"


def resumen(resultado: dict) -> str:
    lineas = [f"  SIMULACIÓN · fase {resultado['fase']} · semillas {resultado['semillas'][0]}-{resultado['semillas'][-1]} "
              f"({len(resultado['semillas'])}) · {len(resultado['vidas'])} vidas · {resultado['corridas']} corridas en "
              f"{resultado['duracion_s']} s · vidas {resultado['hash_vidas'][:10]}"]
    for tipo, errores in resultado["comprobaciones"]["errores_del_sistema"].items():
        if errores:
            lineas.append(f"  AVISO: {errores} errores del sistema con {tipo} (deben ser 0)")
    cifras = (("dinero_escapa", True), ("preguntas_inutiles", False), ("recordatorios_a_destiempo", True),
              ("acierto_sugerencia", True), ("casos_cerrados_solos", True), ("toques_por_100_eur", False),
              ("dias_hasta_cobrar", False))
    for semana in ("8", "total"):
        lineas.append(f"  {'semana 8' if semana == '8' else 'total 8 semanas'}:")
        for pol, bloque in resultado["resultados"].items():
            g = bloque.get("ajuste") or bloque.get("evaluacion")
            if not g:
                continue
            partes = [f"{m}={_fmt(g['global'][m][semana]['media'], pct).strip()}" for m, pct in cifras]
            lineas.append(f"    {pol:<24} " + "  ".join(partes))
    obj = resultado.get("objetivos")
    if obj and obj.get("semana_8"):
        s8 = obj["semana_8"]
        lineas.append("  objetivos semana 8 (nueva/base): " + "  ".join(
            f"{k}={s8[k]['razon']}" for k in ("dinero_escapa", "preguntas_inutiles", "recordatorios_a_destiempo")))
    return "\n".join(lineas)
