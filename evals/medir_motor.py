"""
Métricas del motor (motor.md §6), sin Claude ni internet: reproduce en línea cada escenario de
`backend/escenarios/` y lo compara con su verdad etiquetada.

- Escenarios etiquetados (todos menos `fondo-*`): precisión, exhaustividad, días de retraso y trampas
  violadas, por detector y por escenario.
- Escenarios `fondo-*` (perfiles sintéticos sin anomalías): ruido de fondo = momentos por usuario y mes.
- Todo dos veces: sin perfil (arranque en frío) y con perfil (`perfil: calcular` si el escenario no
  trae uno). Si `personalizacion.perfilar` aún no da perfil, la parte con perfil queda «no disponible».

Lo llama `evals/medir.py --parte motor`: `medir(anterior) -> dict` (JSON serializable).
"""

from __future__ import annotations

import dataclasses
import statistics
import subprocess
import time
from datetime import datetime
from pathlib import Path

from backend import motor, personalizacion
from backend.escenarios import cargar
from backend.motor.detectores import REGISTRO

RAIZ = Path(__file__).resolve().parent.parent
PREFIJO_FONDO = "fondo-"
DIAS_POR_MES = 30.44
RUIDO_MAX_MES = 1.0
NOMBRES_PERFIL = ("sin_perfil", "con_perfil")

# motor.md §6. `retraso_medio_max` en días (para las previsiones se mide el retraso sobre el día
# etiquetado como detectable, que ya incluye la antelación).
OBJETIVOS: dict[str, dict] = {
    "gasto_compartido": {"precision_min": 1.0, "exhaustividad_min": 1.0, "retraso_medio_max": 1, "trampas_max": 0},
    "cargo_duplicado": {"precision_min": 0.9, "exhaustividad_min": 1.0, "retraso_medio_max": 0, "trampas_max": 0},
    "renovacion_proxima": {"precision_min": 0.9, "exhaustividad_min": 0.9, "retraso_medio_max": 0, "trampas_max": 0},
    "subida_recibo": {"precision_min": 0.9, "exhaustividad_min": 0.9, "retraso_medio_max": 0, "trampas_max": 0},
    "prueba_gratuita": {"precision_min": 1.0, "exhaustividad_min": 1.0, "retraso_medio_max": 0, "trampas_max": 0},
    "saldo_negativo_previsto": {"precision_min": 0.8, "exhaustividad_min": 0.8, "retraso_medio_max": 0,
                                "trampas_max": 0},
}
# Métricas que se comparan con la ejecución anterior: (campo, mejor si sube).
COMPARABLES = (("precision", True), ("exhaustividad", True), ("retraso_medio", False), ("trampas_violadas", False))


# --- Reproducir y evaluar ------------------------------------------------------------------------

def _version_git() -> str | None:
    try:
        salida = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=RAIZ, capture_output=True,
                                text=True, timeout=5)
        return salida.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def _con_perfil(escenario: cargar.Escenario) -> cargar.Escenario:
    """Para la pasada con perfil: el del escenario o, si no trae, el calculado con `perfilar`."""
    return escenario if escenario.perfil else dataclasses.replace(escenario, perfil="calcular")


def perfil_disponible(escenario: cargar.Escenario) -> bool:
    """¿`perfilar` da un perfil sobre el historial completo del escenario? (Hoy es un stub: None)."""
    if isinstance(escenario.perfil, dict):
        return True
    try:
        perfil = personalizacion.perfilar(motor.enriquecer(escenario.movimientos), escenario.hasta, None)
    except NotImplementedError:
        return False
    return perfil is not None


def _retrasos_por_tipo(escenario: cargar.Escenario, resultado: dict, con_perfil: bool) -> dict[str, list[int]]:
    """`evaluar` da los retrasos en el orden de las etiquetas acertadas; aquí se reparten por tipo."""
    etiquetas = [e for e in escenario.esperado if con_perfil or not e.get("solo_con_perfil")]
    omitidas = {id(e) for e in resultado["detalle_omitidos"]}
    acertadas = [e for e in etiquetas if id(e) not in omitidas]
    salida: dict[str, list[int]] = {}
    for etiqueta, retraso in zip(acertadas, resultado["retrasos"]):
        salida.setdefault(etiqueta["tipo"], []).append(retraso)
    return salida


def medir_escenario(escenario: cargar.Escenario, con_perfil: bool) -> dict:
    """Una pasada en línea del escenario y su comparación con la verdad."""
    esc = _con_perfil(escenario) if con_perfil else escenario
    inicio = time.perf_counter()
    momentos = cargar.reproducir(esc, con_perfil=con_perfil)
    ms = (time.perf_counter() - inicio) * 1000
    resultado = cargar.evaluar(esc, momentos, con_perfil)
    por_id = {m.id: m for m in momentos}
    dias = (esc.hasta - esc.activacion).days
    return {
        "escenario": esc.id,
        "con_perfil": con_perfil,
        "dias_procesados": dias,
        "ms": round(ms, 1),
        "momentos": len(momentos),
        "aciertos": resultado["aciertos"],
        "omitidos": resultado["omitidos"],
        "omitidos_detalle": [{"tipo": e["tipo"], "fecha_detectable": str(e["fecha_detectable"]),
                              "ids": list(e.get("ids", []))} for e in resultado["detalle_omitidos"]],
        "falsos_positivos": [{"id": i, "tipo": por_id[i].tipo, "fecha": por_id[i].fecha.isoformat(),
                              "movimientos": list(por_id[i].movimientos)} for i in resultado["falsos_positivos"]],
        "trampas_comprobadas": [{"tipo": t["tipo"], "motivo": t.get("motivo", "")} for t in esc.trampas],
        "trampas_violadas": resultado["trampas_violadas"],
        "retrasos": _retrasos_por_tipo(esc, resultado, con_perfil),
        "por_tipo": resultado["por_tipo"],
    }


# --- Agregar -------------------------------------------------------------------------------------

def _cociente(a: int, b: int) -> float | None:
    return round(a / b, 3) if b else None


def _cumple(tipo: str, fila: dict) -> bool | None:
    objetivo = OBJETIVOS.get(tipo)
    if not objetivo or (fila["precision"] is None and fila["exhaustividad"] is None):
        return None
    checks = [fila["trampas_violadas"] <= objetivo["trampas_max"]]
    if fila["precision"] is not None:
        checks.append(fila["precision"] >= objetivo["precision_min"])
    if fila["exhaustividad"] is not None:
        checks.append(fila["exhaustividad"] >= objetivo["exhaustividad_min"])
    if fila["retraso_medio"] is not None:
        checks.append(fila["retraso_medio"] <= objetivo["retraso_medio_max"])
    return all(checks)


def por_detector(filas: list[dict]) -> dict[str, dict]:
    """Suma los escenarios etiquetados por tipo de momento."""
    tipos = set(REGISTRO)
    for f in filas:
        tipos |= set(f["por_tipo"]) | set(f["retrasos"]) | {t["tipo"] for t in f["trampas_comprobadas"]}
    salida = {}
    for tipo in sorted(tipos):
        aciertos = sum(f["por_tipo"].get(tipo, {}).get("aciertos", 0) for f in filas)
        omitidos = sum(f["por_tipo"].get(tipo, {}).get("omitidos", 0) for f in filas)
        falsos = sum(f["por_tipo"].get(tipo, {}).get("falsos", 0) for f in filas)
        retrasos = [r for f in filas for r in f["retrasos"].get(tipo, [])]
        fila = {
            "implementado": tipo in REGISTRO,
            "version": REGISTRO[tipo].version if tipo in REGISTRO else None,
            "aciertos": aciertos,
            "omitidos": omitidos,
            "falsos_positivos": falsos,
            "precision": _cociente(aciertos, aciertos + falsos),
            "exhaustividad": _cociente(aciertos, aciertos + omitidos),
            "retraso_medio": round(statistics.fmean(retrasos), 2) if retrasos else None,
            "retraso_max": max(retrasos) if retrasos else None,
            "trampas_comprobadas": sum(1 for f in filas for t in f["trampas_comprobadas"] if t["tipo"] == tipo),
            "trampas_violadas": sum(1 for f in filas for t in f["trampas_violadas"] if t["tipo"] == tipo),
            "escenarios": sorted({f["escenario"] for f in filas if tipo in f["por_tipo"] or tipo in f["retrasos"]}),
        }
        fila["objetivo"] = OBJETIVOS.get(tipo)
        fila["cumple"] = _cumple(tipo, fila)
        salida[tipo] = fila
    return salida


def ruido(filas: list[dict]) -> dict:
    """Momentos por usuario y mes en los escenarios `fondo-*` (todo lo que sale ahí es ruido)."""
    usuarios = []
    for f in filas:
        meses = f["dias_procesados"] / DIAS_POR_MES
        tipos: dict[str, int] = {}
        for falso in f["falsos_positivos"]:
            tipos[falso["tipo"]] = tipos.get(falso["tipo"], 0) + 1
        usuarios.append({"escenario": f["escenario"], "meses": round(meses, 2), "momentos": f["momentos"],
                         "por_mes": round(f["momentos"] / meses, 3) if meses else None, "por_tipo": tipos,
                         "ms": f["ms"], "momentos_detalle": f["falsos_positivos"]})
    valores = [u["por_mes"] for u in usuarios if u["por_mes"] is not None]
    medio = round(statistics.fmean(valores), 3) if valores else None
    maximo = max(valores) if valores else None
    return {"objetivo_max_por_mes": RUIDO_MAX_MES, "medio_por_usuario_mes": medio, "max_por_usuario_mes": maximo,
            "cumple": None if maximo is None else maximo <= RUIDO_MAX_MES, "usuarios": usuarios}


def _pasada(etiquetados: list[cargar.Escenario], fondos: list[cargar.Escenario], con_perfil: bool) -> dict:
    filas = [medir_escenario(e, con_perfil) for e in etiquetados]
    filas_fondo = [medir_escenario(e, con_perfil) for e in fondos]
    ms = [f["ms"] for f in filas + filas_fondo]
    return {
        "disponible": True,
        "por_detector": por_detector(filas),
        "por_escenario": filas,
        "ruido_fondo": ruido(filas_fondo),
        "trampas_violadas_total": sum(len(f["trampas_violadas"]) for f in filas + filas_fondo),
        "ms_max_por_escenario": max(ms) if ms else None,
    }


# --- Comparar con la ejecución anterior ----------------------------------------------------------

def comparar(actual: dict, anterior: dict | None, archivo: str | None = None) -> dict | None:
    """Diferencias por detector y en el ruido. `empeora` lista lo que hay que mirar."""
    if not anterior:
        return None
    cambios, empeora, mejora = [], [], []
    for pasada in NOMBRES_PERFIL:
        hoy, antes = actual.get(pasada) or {}, anterior.get(pasada) or {}
        if not hoy.get("disponible") or not antes.get("disponible"):
            continue
        for tipo, fila in hoy["por_detector"].items():
            previa = antes.get("por_detector", {}).get(tipo)
            if not previa:
                cambios.append({"pasada": pasada, "detector": tipo, "campo": "nuevo"})
                continue
            for campo, sube_es_mejor in COMPARABLES:
                a, b = previa.get(campo), fila.get(campo)
                if a == b or a is None or b is None:
                    continue
                cambio = {"pasada": pasada, "detector": tipo, "campo": campo, "antes": a, "ahora": b}
                cambios.append(cambio)
                (mejora if (b > a) == sube_es_mejor else empeora).append(cambio)
        a = antes.get("ruido_fondo", {}).get("max_por_usuario_mes")
        b = hoy["ruido_fondo"].get("max_por_usuario_mes")
        if a is not None and b is not None and a != b:
            cambio = {"pasada": pasada, "detector": "ruido_fondo", "campo": "max_por_usuario_mes", "antes": a, "ahora": b}
            cambios.append(cambio)
            (mejora if b < a else empeora).append(cambio)
    return {"contra": archivo, "generado_anterior": anterior.get("generado"), "commit_anterior": anterior.get("commit"),
            "cambios": cambios, "empeora": empeora, "mejora": mejora}


# --- Entrada -------------------------------------------------------------------------------------

def cargar_escenarios() -> tuple[list[cargar.Escenario], list[cargar.Escenario]]:
    todos = [cargar.cargar(e["id"]) for e in cargar.listar()]
    etiquetados = [e for e in todos if not e.id.startswith(PREFIJO_FONDO)]
    fondos = [e for e in todos if e.id.startswith(PREFIJO_FONDO)]
    return etiquetados, fondos


def medir(anterior: dict | None = None, archivo_anterior: str | None = None) -> dict:
    etiquetados, fondos = cargar_escenarios()
    inicio = time.perf_counter()
    resultado: dict = {
        "parte": "motor",
        "generado": datetime.now().isoformat(timespec="seconds"),
        "commit": _version_git(),
        "detectores": {t: d.version for t, d in sorted(REGISTRO.items())},
        "escenarios": {"etiquetados": [e.id for e in etiquetados], "fondo": [e.id for e in fondos]},
        "sin_perfil": _pasada(etiquetados, fondos, con_perfil=False),
    }
    con_perfil = {e.id for e in etiquetados + fondos if perfil_disponible(e)}
    if con_perfil:
        resultado["con_perfil"] = _pasada([e for e in etiquetados if e.id in con_perfil],
                                          [e for e in fondos if e.id in con_perfil], con_perfil=True)
    else:
        resultado["con_perfil"] = {"disponible": False,
                                   "motivo": "personalizacion.perfilar aún no devuelve perfil (llega en U1); "
                                             "solo se mide sin perfil."}
    resultado["ms_total"] = round((time.perf_counter() - inicio) * 1000, 1)
    resultado["comparacion"] = comparar(resultado, anterior, archivo_anterior)
    return resultado


def resumen(resultado: dict) -> str:
    """Tabla corta para la consola."""
    lineas = []
    for pasada in NOMBRES_PERFIL:
        bloque = resultado.get(pasada) or {}
        if not bloque.get("disponible"):
            lineas.append(f"[{pasada}] no disponible: {bloque.get('motivo', '')}")
            continue
        lineas.append(f"[{pasada}] detector             prec  exh   retraso  trampas  cumple")
        for tipo, f in bloque["por_detector"].items():
            def fmt(v):
                return "  -  " if v is None else f"{v:5.2f}"
            lineas.append(f"  {tipo:<24} {fmt(f['precision'])} {fmt(f['exhaustividad'])} {fmt(f['retraso_medio'])}"
                          f"    {f['trampas_violadas']}/{f['trampas_comprobadas']}    {f['cumple']}")
        r = bloque["ruido_fondo"]
        lineas.append(f"  ruido de fondo: medio {r['medio_por_usuario_mes']} y máximo {r['max_por_usuario_mes']} "
                      f"momentos por usuario y mes (objetivo <= {r['objetivo_max_por_mes']})")
    comp = resultado.get("comparacion")
    if comp is None:
        lineas.append("Sin ejecución anterior con la que comparar.")
    else:
        lineas.append(f"Frente a {comp['contra']}: {len(comp['empeora'])} empeoran, {len(comp['mejora'])} mejoran.")
        for c in comp["empeora"]:
            lineas.append(f"  EMPEORA [{c['pasada']}] {c['detector']}.{c['campo']}: {c['antes']} -> {c['ahora']}")
    return "\n".join(lineas)
