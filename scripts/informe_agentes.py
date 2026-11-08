"""
Cifras reales de cómo hemos trabajado con Claude, para el pitch.

    python scripts/informe_agentes.py

Lee registro/agentes.jsonl (lo escribe el hook de subagentes) y el último resultado de evals.
"""

import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from registrar_agente import carpeta_registro  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent


def main() -> None:
    ruta = carpeta_registro() / "agentes.jsonl"
    eventos = []
    if ruta.exists():
        for linea in ruta.read_text(encoding="utf-8").splitlines():
            try:
                eventos.append(json.loads(linea))
            except ValueError:
                continue
    inicios = [e for e in eventos if e.get("evento") == "SubagentStart"]
    finales = {e.get("id"): e for e in eventos if e.get("evento") == "SubagentStop"}
    por_agente = Counter(e.get("agente") or "desconocido" for e in inicios)
    por_dia = Counter((e.get("hora") or "")[:10] for e in inicios)
    duraciones = []
    for inicio in inicios:
        fin = finales.get(inicio.get("id"))
        if fin:
            try:
                segundos = (datetime.fromisoformat(fin["hora"]) - datetime.fromisoformat(inicio["hora"])).seconds
                duraciones.append(segundos)
            except (KeyError, ValueError):
                continue

    print("## Cómo hemos trabajado con Claude (datos reales)\n")
    print(f"- Subagentes lanzados: {len(inicios)} en {len({e.get('sesion') for e in inicios})} sesiones")
    if duraciones:
        print(f"- Duración media de un subagente: {sum(duraciones) / len(duraciones) / 60:.1f} min")
    print("\n| Subagente | Veces |\n|---|---|")
    for agente, veces in por_agente.most_common():
        print(f"| {agente} | {veces} |")
    if por_dia:
        print("\n| Día | Subagentes |\n|---|---|")
        for dia, veces in sorted(por_dia.items()):
            print(f"| {dia} | {veces} |")

    resultados = sorted((RAIZ / "evals" / "resultados").glob("*.json"))
    if resultados:
        ultimo = json.loads(resultados[-1].read_text(encoding="utf-8"))
        print(f"\n- Evals: {ultimo['aprobados']}/{ultimo['total']} aprobados ({ultimo['fecha']}), "
              f"{len(resultados)} ejecuciones en total")
    if not inicios:
        print("\n(Aún no hay subagentes registrados: el hook escribe en registro/agentes.jsonl.)")


if __name__ == "__main__":
    main()
