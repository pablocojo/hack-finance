"""
Hook de Claude Code (SessionStart): imprime el contexto con el que empezar cada sesión.
Claude Code añade esta salida al contexto: así cada sesión (y cada día) arranca sabiendo
el estado del plan y lo último del diario, sin leer archivos enteros.
"""

import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
MAX_LINEAS = 25


def git(*argumentos: str) -> str:
    try:
        return subprocess.run(["git", *argumentos], cwd=RAIZ, capture_output=True, text=True,
                              timeout=5).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def seccion(ruta: Path, titulo: str) -> list[str]:
    """Líneas de la sección '## titulo' de un markdown (hasta la siguiente sección)."""
    try:
        lineas = ruta.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    dentro, resultado = False, []
    for linea in lineas:
        if linea.startswith("## "):
            if dentro:
                break
            dentro = linea[3:].strip().lower().startswith(titulo.lower())
            continue
        if dentro and linea.strip():
            resultado.append(linea)
    return resultado[:MAX_LINEAS]


def ultima_entrada(ruta: Path) -> list[str]:
    try:
        texto = ruta.read_text(encoding="utf-8")
    except OSError:
        return []
    entradas = re.split(r"\n(?=## \d{4}-\d{2}-\d{2})", texto)
    if len(entradas) < 2:
        return []
    return [linea for linea in entradas[-1].splitlines() if linea.strip()][:MAX_LINEAS]


def main() -> None:
    salida = ["=== Contexto del proyecto (hook de inicio) ===",
              f"Ahora: {datetime.now():%Y-%m-%d %H:%M}"]
    rama = git("branch", "--show-current")
    if rama:
        cambios = len([l for l in git("status", "--porcelain").splitlines() if l.strip()])
        salida.append(f"Rama: {rama} · archivos con cambios sin commit: {cambios}")
    reto = RAIZ / "reto" / "RETO.md"
    if reto.exists() and "PLANTILLA" in reto.read_text(encoding="utf-8"):
        salida.append("El reto aún no está en reto/RETO.md: pégalo y lanza /kickoff.")
    estado = seccion(RAIZ / "docs" / "PLAN.md", "Estado")
    if estado:
        salida += ["", "Estado (docs/PLAN.md):", *estado]
    diario = ultima_entrada(RAIZ / "docs" / "DIARIO.md")
    if diario:
        salida += ["", "Última entrada del diario (docs/DIARIO.md):", *diario]
    salida += ["", "Recuerda: /estado para priorizar, /feature para cada tarea y /cierre-dia al terminar."]
    print("\n".join(salida))


if __name__ == "__main__":
    try:
        main()
    finally:
        sys.exit(0)
