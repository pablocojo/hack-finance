"""C7: la política y el sistema nunca importan el simulador (`docs/diseno/curva-amigos.md` §4.5).

Si el sistema supiera de la simulación, la curva sería una trampa: se comprueba con el código (AST) y con un proceso
limpio que importa el sistema y mira que `simulacion` no se cargó.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
BACKEND = RAIZ / "backend"
SIMULACION = BACKEND / "personalizacion" / "simulacion"
# Lo que no puede importar `simulacion`: `personalizacion/*.py` (sin subcarpetas), `motor/`, `casos/` y `plataforma/`.
ZONAS_ESTRICTAS = ("personalizacion", "motor", "casos", "plataforma")


def _importa_simulacion(ruta: Path) -> list[str]:
    arbol = ast.parse(ruta.read_text(encoding="utf-8"), filename=str(ruta))
    malos = []
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            malos += [a.name for a in nodo.names if "simulacion" in a.name.split(".")]
        elif isinstance(nodo, ast.ImportFrom):
            if "simulacion" in (nodo.module or "").split(".") or any(a.name == "simulacion" for a in nodo.names):
                malos.append(f"{'.' * nodo.level}{nodo.module or ''}")
    return malos


def _archivos(zona: str) -> list[Path]:
    base = BACKEND / zona
    if zona == "personalizacion":
        return sorted(base.glob("*.py"))
    return sorted(base.rglob("*.py"))


def test_la_politica_y_el_sistema_no_importan_el_simulador():
    ofensores = {}
    for zona in ZONAS_ESTRICTAS:
        archivos = _archivos(zona)
        assert archivos, f"no hay archivos en backend/{zona}: la comprobación no miraría nada"
        for ruta in archivos:
            if malos := _importa_simulacion(ruta):
                ofensores[str(ruta.relative_to(RAIZ))] = malos
    assert not ofensores, f"Estos archivos importan `simulacion` (la política no debe conocerla): {ofensores}"


def test_todo_el_backend_fuera_del_simulador_tampoco_lo_importa():
    ofensores = {}
    for ruta in sorted(BACKEND.rglob("*.py")):
        if SIMULACION in ruta.parents:
            continue
        if malos := _importa_simulacion(ruta):
            ofensores[str(ruta.relative_to(RAIZ))] = malos
    assert not ofensores, f"Importan `simulacion` fuera del simulador: {ofensores}"


def test_importar_el_sistema_no_carga_el_simulador():
    codigo = (
        "import sys\n"
        "import backend.personalizacion, backend.motor, backend.casos\n"
        "import backend.plataforma.orquestador, backend.plataforma.chat_casos\n"
        "malos = sorted(m for m in sys.modules if 'simulacion' in m.split('.'))\n"
        "print('CARGADOS', malos)\n"
        "raise SystemExit(1 if malos else 0)\n"
    )
    r = subprocess.run([sys.executable, "-c", codigo], cwd=RAIZ, capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, f"{r.stdout}\n{r.stderr[-500:]}"


def test_el_detector_de_importaciones_funciona(tmp_path):
    f = tmp_path / "a.py"
    for texto in ("from .simulacion import x", "from ..personalizacion.simulacion.amigos import y",
                  "import backend.personalizacion.simulacion", "from . import simulacion"):
        f.write_text(texto + "\n", encoding="utf-8")
        assert _importa_simulacion(f), texto
    f.write_text("from .perfil import simulacion_falsa\nimport simulaciones\n", encoding="utf-8")
    assert not _importa_simulacion(f)
