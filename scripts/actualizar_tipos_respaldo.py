"""
Descarga los últimos tipos de cambio de Frankfurter (base EUR) y los guarda como respaldo
sin conexión en backend/datos/tipos_respaldo.json. Ejecútalo la víspera de la demo.

    python scripts/actualizar_tipos_respaldo.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend import config  # noqa: E402
from backend.herramientas.mercados import RESPALDO, obtener_json  # noqa: E402


def main() -> int:
    url = f"{config.ajustes().frankfurter_url.rstrip('/')}/latest"
    try:
        datos = obtener_json(url)
    except Exception as error:  # noqa: BLE001
        print(f"No se ha podido descargar {url}: {error}")
        return 1
    datos["fuente"] = f"Frankfurter ({url}), tipos de referencia"
    RESPALDO.write_text(json.dumps(datos, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"Guardados {len(datos.get('rates', {}))} tipos del {datos.get('date')} en {RESPALDO}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
