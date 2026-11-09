"""
`/medir`: métricas del Copiloto sin gastar crédito (sin Claude ni internet).

    python evals/medir.py --parte motor            # detectores sobre los escenarios etiquetados
    python evals/medir.py --parte personalizacion  # curva de aprendizaje con usuarios simulados
    python evals/medir.py --parte todo             # las dos (por defecto)

Cada parte escribe `evals/resultados/<parte>-<AAAA-MM-DD>.json` (versionados: los lee `/jurado` por
`GET /metricas/{parte}`) y se compara con la ejecución anterior de esa parte.

Cada parte es un módulo de `evals/` con `medir(anterior: dict | None, archivo_anterior: str | None) -> dict`:
`medir_motor.py` (motor) y `medir_personalizacion.py` (lo crea la personalización en U3). Si este
último aún no existe, se escribe un JSON que lo dice (`estado: pendiente`) en vez de fallar.
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import re
import sys
from datetime import date, datetime
from pathlib import Path

DIR_EVALS = Path(__file__).resolve().parent
RAIZ = DIR_EVALS.parent
for _ruta in (str(RAIZ), str(DIR_EVALS)):
    if _ruta not in sys.path:
        sys.path.insert(0, _ruta)

# Sin internet ni Claude: la búsqueda web de comercios queda apagada pase lo que pase en el entorno.
os.environ["BUSQUEDA_WEB"] = "off"

RESULTADOS = DIR_EVALS / "resultados"
PARTES = ("motor", "personalizacion")
MODULOS = {"motor": "medir_motor", "personalizacion": "medir_personalizacion"}
# Si falta alguno de estos módulos, la parte aún no existe (no es un error del código).
PENDIENTE_SI_FALTA = {"personalizacion": ("medir_personalizacion", "backend.personalizacion.simulacion")}


def _patron(parte: str) -> re.Pattern:
    return re.compile(rf"^{re.escape(parte)}-(\d{{4}}-\d{{2}}-\d{{2}})\.json$")


def ultimo(parte: str, directorio: Path = RESULTADOS) -> Path | None:
    """El JSON más reciente de la parte (por la fecha del nombre)."""
    if not directorio.is_dir():
        return None
    patron = _patron(parte)
    rutas = sorted(r for r in directorio.iterdir() if patron.match(r.name))
    return rutas[-1] if rutas else None


def _pendiente(parte: str, error: ImportError) -> dict:
    return {
        "parte": parte,
        "estado": "pendiente",
        "generado": datetime.now().isoformat(timespec="seconds"),
        "motivo": (f"La simulación de {parte} aún no existe (falta el módulo {error.name!r}); "
                   "llega en U3 con evals/medir_personalizacion.py."),
    }


def medir_parte(parte: str, directorio: Path = RESULTADOS, fecha: date | None = None) -> tuple[Path, dict]:
    """Mide una parte, la compara con la anterior y guarda `<parte>-<fecha>.json`."""
    if parte not in PARTES:
        raise ValueError(f"Parte desconocida: {parte!r}. Elige entre {', '.join(PARTES)} o todo.")
    previa = ultimo(parte, directorio)
    anterior = json.loads(previa.read_text(encoding="utf-8")) if previa else None
    try:
        modulo = importlib.import_module(MODULOS[parte])
    except ImportError as error:
        faltan = PENDIENTE_SI_FALTA.get(parte, ())
        if not error.name or not any(error.name == m or error.name.startswith(m + ".") for m in faltan):
            raise
        resultado = _pendiente(parte, error)
    else:
        resultado = modulo.medir(anterior, previa.name if previa else None)
    directorio.mkdir(parents=True, exist_ok=True)
    ruta = directorio / f"{parte}-{(fecha or date.today()).isoformat()}.json"
    ruta.write_text(json.dumps(resultado, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    return ruta, resultado


def ejecutar(parte: str = "todo", directorio: Path = RESULTADOS, fecha: date | None = None) -> dict[str, Path]:
    partes = PARTES if parte == "todo" else (parte,)
    salida = {}
    for p in partes:
        ruta, resultado = medir_parte(p, directorio, fecha)
        salida[p] = ruta
        print(f"== {p}: {ruta.relative_to(RAIZ) if ruta.is_relative_to(RAIZ) else ruta}")
        modulo = sys.modules.get(MODULOS[p])
        if resultado.get("estado") == "pendiente":
            print(f"  pendiente: {resultado['motivo']}")
        elif modulo is not None and hasattr(modulo, "resumen"):
            print(modulo.resumen(resultado))
    return salida


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Métricas del Copiloto sin gastar crédito.")
    parser.add_argument("--parte", choices=(*PARTES, "todo"), default="todo")
    parser.add_argument("--salida", type=Path, default=RESULTADOS, help="directorio de resultados")
    args = parser.parse_args(argv)
    ejecutar(args.parte, args.salida)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
