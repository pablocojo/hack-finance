"""
Prueba real de la API con la clave del producto (cuesta menos de un céntimo).

    python scripts/probar_api.py            # una llamada mínima a Haiku
    python scripts/probar_api.py --agente   # una pregunta completa al agente con datos de ejemplo
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend import claude_client, config  # noqa: E402


def main() -> int:
    clave, origen = config.clave_api("producto")
    if not clave:
        print("Falta ANTHROPIC_API_KEY_PRODUCTO en .env")
        return 1
    print(f"Clave usada: {origen}")
    try:
        texto = claude_client.preguntar("Responde solo con la palabra: funciona", modelo="haiku", max_tokens=20)
    except Exception as error:  # noqa: BLE001
        print(f"Error: {type(error).__name__}: {error}")
        return 1
    print(f"Haiku responde: {texto!r} · coste: {claude_client.coste_acumulado():.6f} $")

    if "--agente" in sys.argv:
        from backend.agente.nucleo import Agente
        from backend.datos.almacen import Almacen

        sesion = Almacen(carpeta_perfiles=None).crear("familia")
        resultado = Agente().responder(sesion, "¿En qué categoría gasto más los últimos 3 meses?")
        print(f"\nAgente ({resultado.modelo}, {resultado.vueltas} vueltas, herramientas {resultado.herramientas}):")
        print(resultado.texto)
        print(f"\nCoste de la pregunta: {resultado.coste_usd:.4f} $")
    return 0


if __name__ == "__main__":
    sys.exit(main())
