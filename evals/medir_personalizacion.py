"""
Métricas de la personalización (personalizacion.md §8), sin Claude ni internet: curva de aprendizaje con
usuarios simulados de preferencias ocultas, 6 semanas × 4 usuarios × 10 semillas (0-9) y cinco políticas
(`reglas`, `fija`, `perfil`, `aprendida`, `personalizada`). Usa la política, el perfil y el aprendizaje
reales; solo la simulación (`backend/personalizacion/simulacion/`) es nueva.

Lo llama `evals/medir.py --parte personalizacion`: `medir(anterior, archivo_anterior) -> dict` (JSON
serializable) y `resumen(resultado) -> str`. También se puede ejecutar solo:

    python evals/medir_personalizacion.py [--semillas N]
"""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from backend.personalizacion import PARAMETROS  # noqa: E402
from backend.personalizacion.simulacion import protocolo as P  # noqa: E402
from backend.personalizacion.simulacion.perfiles import USUARIOS  # noqa: E402

N_SEMILLAS = 10
SEMANA_1, SEMANA_6 = 0, 5
MODULOS_NUEVOS = {t: f"modulo_nuevo_{i}" for i, t in enumerate(P.MODULO_DE)}


def _version_git() -> str | None:
    try:
        salida = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=RAIZ, capture_output=True,
                                text=True, timeout=5)
        return salida.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def _de(regs: list[dict], politica: str, usuario: str | None = None, semana: int | None = None) -> list[dict]:
    return [r for r in regs if r["politica"] == politica and (usuario is None or r["usuario"] == usuario)
            and (semana is None or r["semana"] == semana)]


def _redondea(x: float | None) -> float | None:
    return None if x is None else round(x, 3)


def _criterio(id_: str, texto: str, valor: float | None, minimo: float | None = None, maximo: float | None = None,
              mejor_si_sube: bool = True, extra: dict | None = None) -> dict:
    cumple = None if valor is None else (valor >= minimo if minimo is not None else valor <= maximo)
    return {"id": id_, "texto": texto, "valor": _redondea(valor), "minimo": minimo, "maximo": maximo,
            "cumple": cumple, "mejor_si_sube": mejor_si_sube, **(extra or {})}


def criterios(regs: list[dict], dup: dict, aislamiento: list[str], invariancia_modulos: bool) -> list[dict]:
    f = lambda pol, w, usuario=None: P.fila(_de(regs, pol, usuario, w))      # noqa: E731
    mol = lambda pol, w: f(pol, w)["molestias"]                               # noqa: E731
    p1_fija, p1_perfil = f("fija", SEMANA_1)["precision_ahora"], f("perfil", SEMANA_1)["precision_ahora"]
    p6_pers, p6_perfil = f("personalizada", SEMANA_6)["precision_ahora"], f("perfil", SEMANA_6)["precision_ahora"]
    evitadas = 1 - mol("personalizada", SEMANA_6) / mol("reglas", SEMANA_6) if mol("reglas", SEMANA_6) else None
    pers_todo = P.fila(_de(regs, "personalizada"))
    est_todo = P.fila(_de(regs, "personalizada", "estudiante"))
    pers = _de(regs, "personalizada")
    cons = [r for r in regs if r["politica"] != "reglas"]
    prot_silenciada = sum(1 for r in pers if r["proteccion"] and r["accion"] == "silenciar")
    tras_silencio = sum(1 for r in pers if r["tras_silencio"] and r["accion"] == "notificar_ahora")
    ms = sorted(r["ms"] for r in cons)
    con_motivo = sum(1 for r in cons if r["motivos"] >= 1) / len(cons)
    est, hol = dup["estudiante"]["perfil"]["accion"], dup["holgado"]["perfil"]["accion"]
    return [
        _criterio("p1_perfil", "Precisión de `notificar_ahora`, semana 1, con perfil (la `fija` sale en `extra`)",
                  p1_perfil, minimo=0.65, extra={"fija": _redondea(p1_fija)}),
        _criterio("p6_personalizada", "Precisión de `notificar_ahora` de `personalizada`, semana 6",
                  p6_pers, minimo=0.80, extra={"reglas": _redondea(f("reglas", SEMANA_6)["precision_ahora"])}),
        _criterio("aprender_suma", "`personalizada` frente a `perfil` en la semana 6 (puntos de precisión)",
                  None if p6_pers is None or p6_perfil is None else p6_pers - p6_perfil, minimo=0.15,
                  extra={"perfil": _redondea(p6_perfil)}),
        _criterio("molestias_evitadas", "Molestias evitadas en la semana 6 frente a `reglas`",
                  evitadas, minimo=0.65,
                  extra={"molestias_personalizada": mol("personalizada", SEMANA_6),
                         "molestias_reglas": mol("reglas", SEMANA_6)}),
        _criterio("primera_accion", "La primera acción ofrecida es la elegida, semana 6 de `personalizada`",
                  f("personalizada", SEMANA_6)["primera_accion"], minimo=0.70,
                  extra={"semana_1": _redondea(f("personalizada", SEMANA_1)["primera_accion"])}),
        _criterio("mismo_duplicado", "Mismo duplicado de 12,99 €: `estudiante` interrumpe y `holgado` no (con perfil)",
                  1.0 if (est == "notificar_ahora" and hol != "notificar_ahora") else 0.0, minimo=1.0,
                  extra={"estudiante": est, "holgado": hol}),
        _criterio("cobertura_total", "Útiles que llegan (ahora + resumen), `personalizada`, semana 6",
                  f("personalizada", SEMANA_6)["cobertura_total"], minimo=0.90),
        _criterio("cobertura_ahora", "Útiles que llegan ahora, `personalizada`, semana 6",
                  f("personalizada", SEMANA_6)["cobertura_ahora"], minimo=0.75),
        _criterio("arrepentimiento", "Arrepentimiento (€ útiles silenciados / € útiles), global y `estudiante`",
                  max(pers_todo["arrepentimiento"] or 0, est_todo["arrepentimiento"] or 0), maximo=0.05,
                  mejor_si_sube=False,
                  extra={"global": pers_todo["arrepentimiento"], "estudiante": est_todo["arrepentimiento"]}),
        _criterio("proteccion_silenciada", "Protección silenciada", prot_silenciada, maximo=0, mejor_si_sube=False),
        _criterio("avisos_tras_silencio", "Avisos tras un `no_avisar_*` que coincide", tras_silencio, maximo=0,
                  mejor_si_sube=False),
        _criterio("decisiones_con_motivo", "Decisiones con motivo", con_motivo, minimo=1.0),
        _criterio("ms_decidir", "Tiempo de `decidir` en el percentil 99 (ms)", ms[int(0.99 * len(ms))], maximo=5.0,
                  mejor_si_sube=False, extra={"maximo_ms": _redondea(ms[-1])}),
        _criterio("modulo_nuevo", "Un módulo nuevo (otros `modulo_id`) da exactamente las mismas decisiones",
                  1.0 if invariancia_modulos else 0.0, minimo=1.0),
        _criterio("politica_aislada", "La política no importa nada de `simulacion` (archivos que lo hacen)",
                  len(aislamiento), maximo=0, mejor_si_sube=False, extra={"archivos": aislamiento}),
    ]


def _invariancia_modulos() -> bool:
    """Misma vida con los módulos renombrados: las mismas decisiones y respuestas (se aprende por tipo)."""
    base = P.simular_todo((0,), ("personalizada",))
    nuevo = P.simular_todo((0,), ("personalizada",), modulos=MODULOS_NUEVOS)
    clave = lambda rs: [(r["id"], r["accion"], r["resultado"], r["primera"], r["elegida"]) for r in rs]   # noqa: E731
    return clave(base) == clave(nuevo)


def comparar(actual: dict, anterior: dict | None, archivo: str | None = None) -> dict | None:
    """Criterios y curva frente a la ejecución anterior. `empeora` lista lo que hay que mirar."""
    if not anterior or not anterior.get("criterios"):
        return None
    previos = {c["id"]: c for c in anterior["criterios"]}
    cambios, empeora, mejora = [], [], []
    for c in actual["criterios"]:
        if c["id"] == "ms_decidir":          # tiempo de reloj: varía de una ejecución a otra, no es una regresión
            continue
        a, b = (previos.get(c["id"]) or {}).get("valor"), c["valor"]
        if a is None or b is None or a == b:
            continue
        cambio = {"id": c["id"], "antes": a, "ahora": b}
        cambios.append(cambio)
        (mejora if (b > a) == c["mejor_si_sube"] else empeora).append(cambio)
    return {"contra": archivo, "generado_anterior": anterior.get("generado"), "commit_anterior": anterior.get("commit"),
            "cambios": cambios, "empeora": empeora, "mejora": mejora}


def medir(anterior: dict | None = None, archivo_anterior: str | None = None, semillas: int = N_SEMILLAS) -> dict:
    semillas_t = tuple(range(semillas))
    regs = P.simular_todo(semillas_t)
    dup = P.duplicado()
    por_politica = {}
    for pol in P.POLITICAS:
        rp = _de(regs, pol)
        por_politica[pol] = {
            "semanas": P.por_semana(rp), "total": P.fila(rp),
            "por_usuario": {u: {"semana_1": P.fila(_de(regs, pol, u, SEMANA_1)),
                                "semana_6": P.fila(_de(regs, pol, u, SEMANA_6))} for u in USUARIOS},
        }
    resultado = {
        "parte": "personalizacion",
        "generado": datetime.now().isoformat(timespec="seconds"),
        "commit": _version_git(),
        "politica": PARAMETROS["version"],
        "protocolo": {"semillas": list(semillas_t), "semanas": P.SEMANAS, "propuestas_por_semana": 10,
                      "usuarios": {n: u.descripcion for n, u in USUARIOS.items()},
                      "politicas": list(P.POLITICAS),
                      "nota": "Precisión y molestias se cuentan sobre `notificar_ahora`; el usuario ignora un aviso "
                              "útil si ya lleva 3 esa semana (`saturable`), y eso cuenta como molestia."},
        "curva": {pol: [{"semana": w + 1, "precision_ahora": s["precision_ahora"], "molestias": s["molestias"],
                         "ahora": s["ahora"], "primera_accion": s["primera_accion"]}
                        for w, s in enumerate(por_politica[pol]["semanas"])] for pol in P.POLITICAS},
        "por_politica": por_politica,
        "duplicado": dup,
        "criterios": criterios(regs, dup, P.verificar_aislamiento(), _invariancia_modulos()),
    }
    resultado["cumplen"] = sum(1 for c in resultado["criterios"] if c["cumple"])
    resultado["total_criterios"] = len(resultado["criterios"])
    resultado["comparacion"] = comparar(resultado, anterior, archivo_anterior)
    return resultado


def resumen(resultado: dict) -> str:
    """Tabla corta para la consola."""
    pr = lambda x: "  -  " if x is None else f"{x:5.2f}"     # noqa: E731
    p = resultado["protocolo"]
    lineas = [f"{len(p['semillas'])} semillas × {len(p['usuarios'])} usuarios × {p['semanas']} semanas "
              f"(política {resultado['politica']})",
              "Precisión de `notificar_ahora` por semana (media de usuarios y semillas):",
              "  política         " + "".join(f"  s{w + 1}  " for w in range(p["semanas"]))]
    for pol in p["politicas"]:
        lineas.append(f"  {pol:<15}  " + " ".join(pr(s["precision_ahora"]) for s in resultado["curva"][pol]))
    lineas.append("Molestias (avisos ahora que no servían) por semana:")
    for pol in p["politicas"]:
        lineas.append(f"  {pol:<15}  " + " ".join(f"{s['molestias']:5d}" for s in resultado["curva"][pol]))
    lineas.append("Mismo duplicado (Netflix 12,99 €), con perfil: " + ", ".join(
        f"{u} -> {d['perfil']['accion']}" for u, d in resultado["duplicado"].items()))
    lineas.append(f"Criterios: {resultado['cumplen']}/{resultado['total_criterios']}")
    for c in resultado["criterios"]:
        meta = f">= {c['minimo']}" if c["minimo"] is not None else f"<= {c['maximo']}"
        marca = {True: "OK  ", False: "FALLA", None: "  -  "}[c["cumple"]]
        lineas.append(f"  {marca} {c['id']:<22} {str(c['valor']):>7}  (objetivo {meta})  {c['texto']}")
    comp = resultado.get("comparacion")
    if comp is None:
        lineas.append("Sin ejecución anterior con la que comparar.")
    else:
        lineas.append(f"Frente a {comp['contra']}: {len(comp['empeora'])} empeoran, {len(comp['mejora'])} mejoran.")
        for c in comp["empeora"]:
            lineas.append(f"  EMPEORA {c['id']}: {c['antes']} -> {c['ahora']}")
        for c in comp["mejora"]:
            lineas.append(f"  mejora  {c['id']}: {c['antes']} -> {c['ahora']}")
    return "\n".join(lineas)


def main(argv: list[str] | None = None) -> int:
    import argparse

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Curva de aprendizaje con usuarios simulados.")
    parser.add_argument("--semillas", type=int, default=N_SEMILLAS)
    args = parser.parse_args(argv)
    print(resumen(medir(semillas=args.semillas)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
