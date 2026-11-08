"""
Comprueba que el entorno está listo. Nunca muestra claves.

    python scripts/comprobar_entorno.py
"""

from __future__ import annotations

import importlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
errores, avisos = [], []


def bien(texto: str) -> None:
    print(f"  [ok] {texto}")


def mal(texto: str, arreglo: str) -> None:
    errores.append(texto)
    print(f"  [FALTA] {texto}\n         -> {arreglo}")


def ojo(texto: str) -> None:
    avisos.append(texto)
    print(f"  [aviso] {texto}")


def version(comando: list[str]) -> str | None:
    try:
        return subprocess.run(comando, capture_output=True, text=True, timeout=20).stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


print("Python")
if sys.version_info < (3, 10):
    mal(f"Python {sys.version.split()[0]}", "Instala Python 3.11 o superior (el SDK necesita 3.10+)")
else:
    bien(f"Python {sys.version.split()[0]}")

print("Paquetes")
for modulo, nombre in [("anthropic", "anthropic"), ("fastapi", "fastapi"), ("uvicorn", "uvicorn"),
                       ("pandas", "pandas"), ("dotenv", "python-dotenv"), ("yaml", "pyyaml"),
                       ("multipart", "python-multipart"), ("pytest", "pytest"), ("httpx", "httpx"),
                       ("streamlit", "streamlit")]:
    try:
        paquete = importlib.import_module(modulo)
        bien(f"{nombre} {getattr(paquete, '__version__', '')}".strip())
    except ImportError:
        mal(nombre, "pip install -r requirements.txt (con el entorno virtual activado)")
try:
    import anthropic

    if int(anthropic.__version__.split(".")[0]) < 2:
        ojo("anthropic < 2.0: actualiza con pip install -U anthropic (el kit usa la API 2026-10-21)")
except (ImportError, ValueError):
    pass

print("Claves (solo se comprueba que existen)")
from backend import config  # noqa: E402

if not (RAIZ / ".env").exists():
    mal(".env", "Copia .env.example como .env y pon las claves 2 y 3")
for uso, variable in [("producto", "ANTHROPIC_API_KEY_PRODUCTO"), ("evals", "ANTHROPIC_API_KEY_EVALS")]:
    clave, origen = config.clave_api(uso)
    if not clave:
        mal(variable, f"Añade {variable} a .env")
    elif origen != variable:
        ojo(f"{variable} no está: el {uso} usará {origen}")
    else:
        bien(variable)
if os.environ.get("ANTHROPIC_API_KEY"):
    bien("ANTHROPIC_API_KEY en el entorno (la usa Claude Code)")
    if os.environ.get("ANTHROPIC_API_KEY") == os.environ.get("ANTHROPIC_API_KEY_PRODUCTO"):
        ojo("Claude Code y el producto usan la misma clave: no podrás separar el gasto")
else:
    ojo("ANTHROPIC_API_KEY no está en el entorno: Claude Code pedirá iniciar sesión o la clave")

print("Herramientas")
for nombre, comando, arreglo in [
    ("git", ["git", "--version"], "Instala git"),
    ("node", ["node", "--version"], "Instala Node.js 20.9 o superior"),
    ("npm", ["npm", "--version"], "Viene con Node.js"),
    ("claude", ["claude", "--version"], "curl -fsSL https://claude.ai/install.sh | bash"),
]:
    if shutil.which(nombre) and (salida := version(comando)):
        bien(f"{nombre} {salida.splitlines()[0]}")
    else:
        mal(nombre, arreglo)
if not (RAIZ / "frontend" / "node_modules").exists():
    mal("frontend/node_modules", "cd frontend && npm install")
if not (RAIZ / "frontend" / ".env.local").exists():
    ojo("frontend/.env.local no existe: se usará http://localhost:8000 como backend")

print("Repositorio")
if (RAIZ / ".git").exists():
    bien("repositorio git")
    if version(["git", "-C", str(RAIZ), "ls-files", ".env"]):
        mal(".env está en git", "git rm --cached .env y rota las claves")
else:
    ojo("todavía no es un repositorio git: git init && git add . && git commit -m 'kit'")
reto = (RAIZ / "reto" / "RETO.md").read_text(encoding="utf-8")
if "PLANTILLA" in reto:
    ojo("reto/RETO.md es la plantilla (normal hasta el 8 nov a las 9:00)")
if not (RAIZ / "backend" / "datos" / "tipos_respaldo.json").exists():
    ojo("Faltan los tipos de cambio de respaldo: python scripts/actualizar_tipos_respaldo.py")

print()
if errores:
    print(f"Faltan {len(errores)} cosas. Arréglalas y vuelve a ejecutar este script.")
    sys.exit(1)
print(f"Todo listo{' (con ' + str(len(avisos)) + ' avisos)' if avisos else ''}.")
