"""
Genera extractos CSV de ejemplo (formato de banco español) en datos_ejemplo/, uno por perfil.
Sirven para probar la subida de CSV en la web y en el panel.

    python scripts/generar_datos.py [--meses 6]
"""

import argparse
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from backend.datos.sinteticos import PERFILES, a_csv_banco, generar_movimientos  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--meses", type=int, default=6)
    meses = parser.parse_args().meses
    carpeta = RAIZ / "datos_ejemplo"
    carpeta.mkdir(exist_ok=True)
    for perfil in PERFILES:
        ruta = carpeta / f"extracto_{perfil}.csv"
        ruta.write_text(a_csv_banco(generar_movimientos(perfil, meses=meses)), encoding="utf-8")
        print(f"{ruta.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
