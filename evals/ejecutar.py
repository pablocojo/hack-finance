"""
Lanza la batería de evals del agente y la compara con la ejecución anterior.

    python evals/ejecutar.py                       # todos los casos (clave ANTHROPIC_API_KEY_EVALS)
    python evals/ejecutar.py --casos divisa,plan-ahorro
    python evals/ejecutar.py --modelo opus --paralelo 2
    python evals/ejecutar.py --simulado            # sin API: comprueba que el arnés funciona

Guarda cada ejecución en evals/resultados/AAAAMMDD-HHMMSS.json.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import yaml  # noqa: E402

from backend import claude_client  # noqa: E402
from backend.agente import registro  # noqa: E402
from backend.agente.nucleo import Agente  # noqa: E402
from backend.datos.almacen import Almacen  # noqa: E402

CASOS = Path(__file__).resolve().parent / "casos.yaml"
RESULTADOS = Path(__file__).resolve().parent / "resultados"
_NUMERO = re.compile(r"-?\d[\d.,]*\d|-?\d")


def cargar_casos(ruta: Path = CASOS) -> list[dict]:
    casos = yaml.safe_load(ruta.read_text(encoding="utf-8")) or []
    ids = [c["id"] for c in casos]
    repetidos = {i for i in ids if ids.count(i) > 1}
    if repetidos:
        raise ValueError(f"Ids repetidos en casos.yaml: {sorted(repetidos)}")
    return casos


def numeros_en(texto: str) -> list[float]:
    """Extrae números en formato español (1.234,56) o inglés (1234.56) de un texto."""
    valores = []
    for crudo in _NUMERO.findall(texto or ""):
        limpio = crudo.rstrip(".,")
        if "," in limpio and "." in limpio:
            if limpio.rfind(",") > limpio.rfind("."):
                limpio = limpio.replace(".", "").replace(",", ".")
            else:
                limpio = limpio.replace(",", "")
        elif "," in limpio:
            limpio = limpio.replace(",", ".")  # en español la coma es el decimal
        elif re.fullmatch(r"-?\d{1,3}(\.\d{3})+", limpio):
            limpio = limpio.replace(".", "")  # 10.000 son diez mil
        try:
            valores.append(float(limpio))
        except ValueError:
            continue
    return valores


def contiene_cifra(texto: str, esperado: float) -> bool:
    tolerancia = max(0.011, abs(esperado) * 0.01)
    return any(abs(abs(v) - abs(esperado)) <= tolerancia for v in numeros_en(texto))


def leer_campo(datos, ruta: str):
    for parte in ruta.split("."):
        datos = datos[int(parte)] if isinstance(datos, list) else datos[parte]
    return float(datos)


def preparar_sesion(caso: dict):
    almacen = Almacen(carpeta_perfiles=None)
    sesion = almacen.crear(caso.get("perfil") or None)
    extra = caso.get("inyectar_movimiento")
    if extra:
        fecha = sesion.movimientos[-1]["fecha"] if sesion.movimientos else datetime.now().date().isoformat()
        sesion.movimientos.append({"id": "eval-00001", "fecha": fecha, "concepto": extra["concepto"],
                                   "comercio": "TIENDA ONLINE", "importe": float(extra["importe"]),
                                   "categoria": "compras"})
    return sesion


def evaluar(caso: dict, *, modelo: str | None, revisor: bool, uso: str) -> dict:
    sesion = preparar_sesion(caso)
    esperadas = []
    for cifra in caso.get("cifras", []):
        texto, es_error, _ = registro.ejecutar(cifra["herramienta"], cifra.get("argumentos", {}), ctx=sesion)
        if es_error:
            raise RuntimeError(f"El caso {caso['id']} calcula mal su cifra: {texto}")
        esperadas.append((cifra["campo"], leer_campo(json.loads(texto), cifra["campo"])))

    inicio = time.perf_counter()
    try:
        resultado = Agente(modelo=modelo, revisor=revisor, uso=uso).responder(sesion, caso["pregunta"]).a_dict()
        error = None
    except Exception as fallo:  # noqa: BLE001
        resultado, error = {"texto": "", "herramientas": [], "coste_usd": 0.0}, f"{type(fallo).__name__}: {fallo}"
    texto = resultado["texto"]
    comprobaciones = []
    if error:
        comprobaciones.append({"tipo": "sin_error", "ok": False, "detalle": error})
    for nombre in caso.get("herramientas", []):
        comprobaciones.append({"tipo": "herramienta", "ok": nombre in resultado["herramientas"], "detalle": nombre})
    for campo, valor in esperadas:
        comprobaciones.append({"tipo": "cifra", "ok": contiene_cifra(texto, valor), "detalle": f"{campo}={valor}"})
    for patron in caso.get("debe_contener", []):
        comprobaciones.append({"tipo": "debe_contener", "ok": bool(re.search(patron, texto, re.I)), "detalle": patron})
    for patron in caso.get("no_debe_contener", []):
        comprobaciones.append({"tipo": "no_debe_contener", "ok": not re.search(patron, texto, re.I),
                               "detalle": patron})
    revision = resultado.get("revision") or {}
    return {
        "id": caso["id"],
        "ok": all(c["ok"] for c in comprobaciones),
        "comprobaciones": comprobaciones,
        "herramientas_usadas": resultado["herramientas"],
        "revisor_corrigio": revision.get("aprobada") is False,
        "coste_usd": resultado.get("coste_usd", 0.0),
        "segundos": round(time.perf_counter() - inicio, 1),
        "respuesta": texto,
    }


def anterior() -> dict | None:
    archivos = sorted(RESULTADOS.glob("*.json"))
    if not archivos:
        return None
    return json.loads(archivos[-1].read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--casos", help="ids separados por comas")
    parser.add_argument("--modelo", help="haiku, sonnet, opus o un ID (por defecto, el enrutado normal)")
    parser.add_argument("--paralelo", type=int, default=3)
    parser.add_argument("--sin-revisor", action="store_true")
    parser.add_argument("--simulado", action="store_true", help="usa un cliente falso: no gasta crédito")
    parser.add_argument("--no-guardar", action="store_true")
    argumentos = parser.parse_args()

    casos = cargar_casos()
    if argumentos.casos:
        elegidos = set(argumentos.casos.split(","))
        casos = [c for c in casos if c["id"] in elegidos]
    if argumentos.simulado:
        from backend.claude_falso import ClienteFalso

        claude_client.usar_cliente(ClienteFalso(por_defecto="Respuesta simulada. Soy una IA; es orientativo."))
    revisor = not (argumentos.sin_revisor or argumentos.simulado)

    with ThreadPoolExecutor(max_workers=max(1, argumentos.paralelo)) as grupo:
        resultados = list(grupo.map(
            lambda c: evaluar(c, modelo=argumentos.modelo, revisor=revisor, uso="evals"), casos))

    aprobados = sum(r["ok"] for r in resultados)
    coste = sum(r["coste_usd"] for r in resultados)
    previo = anterior()
    print(f"\n{'caso':32} {'ok':4} {'$':>8}  fallos")
    for r in resultados:
        fallos = "; ".join(f"{c['tipo']}:{c['detalle']}" for c in r["comprobaciones"] if not c["ok"])
        print(f"{r['id'][:32]:32} {'sí' if r['ok'] else 'NO':4} {r['coste_usd']:8.4f}  {fallos[:110]}")
    print(f"\nAprobados: {aprobados}/{len(resultados)} · coste: {coste:.4f} $")
    if argumentos.simulado:
        print("Modo simulado: sin API, los fallos son normales y el coste es ficticio.")
    if previo:
        antes = {r["id"]: r["ok"] for r in previo["resultados"]}
        empeoran = [r["id"] for r in resultados if antes.get(r["id"]) is True and not r["ok"]]
        mejoran = [r["id"] for r in resultados if antes.get(r["id"]) is False and r["ok"]]
        print(f"Anterior ({previo['fecha']}): {previo['aprobados']}/{previo['total']}")
        if empeoran:
            print("EMPEORAN:", ", ".join(empeoran))
        if mejoran:
            print("Mejoran:", ", ".join(mejoran))

    if not (argumentos.no_guardar or argumentos.simulado):
        RESULTADOS.mkdir(exist_ok=True)
        salida = {"fecha": datetime.now().isoformat(timespec="seconds"), "modelo": argumentos.modelo or "auto",
                  "aprobados": aprobados, "total": len(resultados), "coste_usd": round(coste, 4),
                  "resultados": resultados}
        ruta = RESULTADOS / f"{datetime.now():%Y%m%d-%H%M%S}.json"
        ruta.write_text(json.dumps(salida, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"Guardado en {ruta.relative_to(RAIZ)}")
    return 0 if aprobados == len(resultados) else 1


if __name__ == "__main__":
    sys.exit(main())
