"""
Hook de Claude Code (SubagentStart y SubagentStop): anota cada subagente en registro/agentes.jsonl.
Sirve para dar cifras reales en el pitch (python scripts/informe_agentes.py).

Escribe siempre en el repositorio principal, aunque la sesión esté en un worktree, para que
el registro de todas las sesiones paralelas quede junto. Nunca bloquea a Claude: si algo
falla, sale sin hacer nada.
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def carpeta_registro() -> Path:
    raiz = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parent.parent)
    try:
        comun = subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
            cwd=raiz, capture_output=True, text=True, timeout=5,
        ).stdout.strip()
        if comun:
            raiz = Path(comun).parent
    except (OSError, subprocess.SubprocessError):
        pass
    return raiz / "registro"


def main() -> None:
    try:
        datos = json.load(sys.stdin)
    except (ValueError, OSError):
        return
    entrada = {
        "hora": datetime.now().isoformat(timespec="seconds"),
        "evento": datos.get("hook_event_name"),
        "agente": datos.get("agent_type"),
        "id": datos.get("agent_id"),
        "sesion": datos.get("session_id"),
        "carpeta": Path(datos.get("cwd") or os.getcwd()).name,
    }
    mensaje = datos.get("last_assistant_message")
    if isinstance(mensaje, str):
        entrada["longitud_resultado"] = len(mensaje)
    try:
        carpeta = carpeta_registro()
        carpeta.mkdir(exist_ok=True)
        with (carpeta / "agentes.jsonl").open("a", encoding="utf-8") as archivo:
            archivo.write(json.dumps(entrada, ensure_ascii=False) + "\n")
    except OSError:
        pass


if __name__ == "__main__":
    main()
    sys.exit(0)
