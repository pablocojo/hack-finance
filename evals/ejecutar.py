"""
Lanza la batería de evals del agente y la compara con la ejecución anterior.

    python evals/ejecutar.py                       # todos los casos (clave ANTHROPIC_API_KEY_EVALS)
    python evals/ejecutar.py --casos divisa,plan-ahorro
    python evals/ejecutar.py --modelo opus --paralelo 2
    python evals/ejecutar.py --simulado            # sin API: comprueba que el arnés funciona
    python evals/ejecutar.py --conjunto llamada    # la llamada de Meisam (modo texto): evals/casos_llamada.yaml

Guarda cada ejecución en evals/resultados/AAAAMMDD-HHMMSS.json (kit) o llamada-AAAAMMDD-HHMMSS.json.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import sys
import tempfile
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
CASOS_LLAMADA = Path(__file__).resolve().parent / "casos_llamada.yaml"
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


# ---------------------------------------------------------------------------------------------
# Conjunto «llamada»: el agente de la llamada de Meisam en modo texto (nivel 3, backend/voz/texto.py)
# ---------------------------------------------------------------------------------------------

@contextlib.contextmanager
def almacen_temporal():
    """Datos de usuario en una carpeta temporal, sin demo ni búsqueda web; el entorno se restaura al salir."""
    cambios = {"MODO_DEMO": "off", "BUSQUEDA_WEB": "off", "GUARDAR_PERFILES": "0"}
    previos = {k: os.environ.get(k) for k in [*cambios, "DATOS_USUARIO_DIR"]}
    with tempfile.TemporaryDirectory(prefix="evals-llamada-") as carpeta:
        os.environ.update(cambios, DATOS_USUARIO_DIR=carpeta)
        try:
            yield Path(carpeta)
        finally:
            for k, v in previos.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v


def cargar_conjunto_llamada(ruta: Path = CASOS_LLAMADA) -> tuple[dict, list[dict]]:
    datos = yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}
    casos, escenarios = datos.get("casos", []), datos.get("escenarios", {})
    ids = [c["id"] for c in casos]
    repetidos = {i for i in ids if ids.count(i) > 1}
    if repetidos:
        raise ValueError(f"Ids repetidos en {ruta.name}: {sorted(repetidos)}")
    desconocidos = {c["escenario"] for c in casos if c["escenario"] not in escenarios}
    if desconocidos:
        raise ValueError(f"Escenarios desconocidos en {ruta.name}: {sorted(desconocidos)}")
    return escenarios, casos


def preparar_llamada(caso: dict, escenario: dict):
    """Guarda la propuesta del escenario para un usuario propio del caso y abre la sesión como POST /voz/sesion."""
    from datetime import date

    from backend import casos, personalizacion
    from backend.plataforma import almacenamiento as alm
    from backend.plataforma.tipos import Propuesta
    from backend.voz import contexto, sesiones

    usuario = f"lucia-{caso['id']}"[:64]
    propuesta = Propuesta.model_validate({
        "id": "prop-1", "modulo_id": escenario.get("modulo_id", "gasto_compartido"), "momento_id": "m1",
        "usuario_id": usuario, "titulo": escenario["titulo"], "mensaje_notificacion": escenario["titulo"],
        "contexto_llamada": caso.get("contexto_llamada") or escenario["contexto_llamada"],
        "tipo_momento": escenario.get("tipo_momento", "gasto_compartido"), "confianza": 0.9,
        "acciones_ofrecidas": escenario["acciones_ofrecidas"], "creada": datetime(2026, 11, 9, 20, 30)})
    hoy = date(2026, 11, 9).isoformat()
    alm.guardar(usuario, "estado", {"hoy": hoy, "activado": True, "activacion": hoy, "ultimo_perfil": None})
    alm.guardar(usuario, "reloj", {"hoy": hoy})
    modelo = personalizacion.nuevo_modelo(usuario)
    alm.guardar(usuario, "modelo", modelo)
    alm.guardar(usuario, "propuestas", [propuesta])
    for nombre in ("momentos", "decisiones", "movimientos", "notificaciones"):
        alm.guardar(usuario, nombre, [])
    sembrar_datos(usuario, modelo, escenario.get("datos") or {})
    variables = contexto.variables(propuesta, modelo, usuario, casos.cargar(usuario))
    return sesiones.crear(usuario, propuesta.id, "texto_kit", variables)


def sembrar_datos(usuario: str, modelo, datos: dict) -> None:
    """Datos sintéticos opcionales de un escenario para las herramientas de consulta y cambio: `movimientos`, `casos`,
    `contactos` (la agenda) y `casos_ajenos` (casos de OTRO usuario, que `actualizar_caso` no debe poder tocar)."""
    if not datos:
        return
    from backend import casos
    from backend.plataforma import almacenamiento as alm
    from backend.plataforma.tipos import Caso, Contacto, Movimiento

    alm.guardar(usuario, "movimientos", [Movimiento.model_validate(m) for m in datos.get("movimientos", [])])
    casos.guardar(usuario, [Caso.model_validate({"usuario_id": usuario, **c}) for c in datos.get("casos", [])])
    modelo.contactos = {c["contraparte"]: Contacto.model_validate(c) for c in datos.get("contactos", [])}
    alm.guardar(usuario, "modelo", modelo)
    ajeno = f"{usuario}-ajeno"[:64]
    casos.guardar(ajeno, [Caso.model_validate({"usuario_id": ajeno, **c}) for c in datos.get("casos_ajenos", [])])


def estado_de_casos(usuario: str) -> dict[str, dict]:
    """Lo que comprueba `casos_finales`: por caso, `estado`, `escenario`, `deudor:<CLAVE>` y `cambio_propuesto` (bool)."""
    from backend import casos

    return {c.id: {"estado": c.estado, "escenario": c.escenario, "cambio_propuesto": "cambio_propuesto" in c.hechos,
                   **{f"deudor:{d.contraparte}": d.estado for d in c.deudores}} for c in casos.cargar(usuario)}


def cifras_inventadas(texto: str, fuentes: list[str], extra: list[float] = ()) -> list[float]:
    """Cifras del texto que no salen de las fuentes (se ignoran 0, 1 y 2: «un minuto», «dos frases»)."""
    permitidas = [abs(v) for fuente in fuentes for v in numeros_en(fuente)] + [abs(float(e)) for e in extra]
    fuera = []
    for valor in numeros_en(texto):
        v = abs(valor)
        if v in (0, 1, 2):
            continue
        if not any(abs(v - p) <= max(0.011, p * 0.01) for p in permitidas):
            fuera.append(valor)
    return fuera


def evaluar_llamada(caso: dict, escenarios: dict, *, modelo: str | None, revisor: bool, uso: str) -> dict:
    from backend.agente import servicio
    from backend.agente.nucleo import Agente
    from backend.voz import contexto, texto as modo_texto

    inicio = time.perf_counter()
    turnos = caso.get("turnos") or [caso["pregunta"]]
    textos, usadas, trazas, coste, corregidos = [], [], [], 0.0, []
    tarjetas, error, registro = [], None, None
    try:
        registro = preparar_llamada(caso, escenarios[caso["escenario"]])
        modo_texto.saludo(registro)  # primer mensaje fijo, sin llamar a Claude (como en producción)
        agente = Agente(modelo=modelo or "sonnet", herramientas=modo_texto.HERRAMIENTAS, uso=uso, revisor=revisor,
                        sistema=contexto.sistema_texto(registro.variables))
        for mensaje in turnos:
            r = servicio.conversar(registro.kit, mensaje, agente=agente)
            textos.append(r["texto"])
            usadas += r["herramientas"]
            trazas += r.get("trazas", [])
            coste += r.get("coste_usd", 0.0)
            corregidos.append((r.get("revision") or {}).get("aprobada") is False)
        tarjetas = list(registro.kit.tarjetas)
    except Exception as fallo:  # noqa: BLE001
        error = f"{type(fallo).__name__}: {fallo}"
    texto = "\n---\n".join(textos)
    herramientas = [t for t in trazas if t.get("tipo") == "herramienta"]
    entradas = [json.dumps(t.get("entrada", {}), ensure_ascii=False) for t in herramientas]

    comprobaciones = []
    if error:
        comprobaciones.append({"tipo": "sin_error", "ok": False, "detalle": error})
    for nombre in caso.get("herramientas", []):
        comprobaciones.append({"tipo": "herramienta", "ok": nombre in usadas, "detalle": nombre})
    for nombre in caso.get("herramientas_prohibidas", []):
        comprobaciones.append({"tipo": "herramienta_prohibida", "ok": nombre not in usadas, "detalle": nombre})
    for patron in caso.get("entrada_prohibida", []):
        comprobaciones.append({"tipo": "entrada_prohibida",
                               "ok": not any(re.search(patron, e, re.I) for e in entradas), "detalle": patron})
    if "tarjetas_min" in caso:
        comprobaciones.append({"tipo": "tarjetas_min", "ok": len(tarjetas) >= caso["tarjetas_min"],
                               "detalle": f"{len(tarjetas)} tarjetas, mínimo {caso['tarjetas_min']}"})
    if "tarjetas_max" in caso:
        comprobaciones.append({"tipo": "tarjetas_max", "ok": len(tarjetas) <= caso["tarjetas_max"],
                               "detalle": f"{len(tarjetas)} tarjetas, máximo {caso['tarjetas_max']}"})
    for patron in caso.get("debe_contener", []):
        comprobaciones.append({"tipo": "debe_contener", "ok": bool(re.search(patron, texto, re.I)), "detalle": patron})
    for patron in caso.get("no_debe_contener", []):
        comprobaciones.append({"tipo": "no_debe_contener", "ok": not re.search(patron, texto, re.I),
                               "detalle": patron})
    if registro is not None:      # estado final de los casos del usuario (p. ej. que una inyección no cambió nada)
        reales = estado_de_casos(registro.usuario_id)
        for caso_id, esperado in (caso.get("casos_finales") or {}).items():
            real = reales.get(caso_id, {})
            comprobaciones.append({"tipo": "caso_final", "ok": bool(real) and all(real.get(k) == v for k, v in esperado.items()),
                                   "detalle": f"{caso_id}: {real or 'no existe'} (esperado {esperado})"})
    if caso.get("sin_cifras_inventadas") and registro is not None:
        v = registro.variables
        fuera = cifras_inventadas(texto, [v["titulo_aviso"], v["contexto_llamada"], v["acciones_ofrecidas"], *turnos],
                                  caso.get("cifras_extra", []))
        comprobaciones.append({"tipo": "sin_cifras_inventadas", "ok": not fuera,
                               "detalle": f"fuera del contexto: {fuera}"})
    return {
        "id": caso["id"],
        "ok": all(c["ok"] for c in comprobaciones),
        "comprobaciones": comprobaciones,
        "herramientas_usadas": usadas,
        "preparar_accion": [t.get("entrada", {}) for t in herramientas if t["nombre"] == "preparar_accion"],
        "tarjetas": len(tarjetas),
        "revisor_corrigio": any(corregidos),
        "coste_usd": round(coste, 6),
        "segundos": round(time.perf_counter() - inicio, 1),
        "respuesta": texto,
    }


def anterior(conjunto: str = "kit") -> dict | None:
    """Última ejecución del mismo conjunto (las del kit empiezan por un dígito; no se mezclan con motor-*.json)."""
    archivos = sorted(RESULTADOS.glob("llamada-*.json" if conjunto == "llamada" else "[0-9]*.json"))
    if not archivos:
        return None
    return json.loads(archivos[-1].read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--conjunto", choices=["kit", "llamada"], default="kit",
                        help="kit (casos.yaml, por defecto) o llamada (casos_llamada.yaml: el agente de la llamada)")
    parser.add_argument("--casos", help="ids separados por comas")
    parser.add_argument("--modelo", help="haiku, sonnet, opus o un ID (por defecto, el enrutado normal)")
    parser.add_argument("--paralelo", type=int, default=3)
    parser.add_argument("--sin-revisor", action="store_true")
    parser.add_argument("--simulado", action="store_true", help="usa un cliente falso: no gasta crédito")
    parser.add_argument("--no-guardar", action="store_true")
    argumentos = parser.parse_args()

    llamada = argumentos.conjunto == "llamada"
    escenarios, casos = cargar_conjunto_llamada() if llamada else ({}, cargar_casos())
    if argumentos.casos:
        elegidos = set(argumentos.casos.split(","))
        casos = [c for c in casos if c["id"] in elegidos]
    if argumentos.simulado:
        from backend.claude_falso import ClienteFalso

        claude_client.usar_cliente(ClienteFalso(por_defecto="Respuesta simulada. Soy una IA; es orientativo."))
    revisor = not (argumentos.sin_revisor or argumentos.simulado)

    if llamada:
        def lanzar(c):
            return evaluar_llamada(c, escenarios, modelo=argumentos.modelo, revisor=revisor, uso="evals")
    else:
        def lanzar(c):
            return evaluar(c, modelo=argumentos.modelo, revisor=revisor, uso="evals")
    with contextlib.ExitStack() as pila:
        if llamada:
            pila.enter_context(almacen_temporal())
        with ThreadPoolExecutor(max_workers=max(1, argumentos.paralelo)) as grupo:
            resultados = list(grupo.map(lanzar, casos))

    aprobados = sum(r["ok"] for r in resultados)
    coste = sum(r["coste_usd"] for r in resultados)
    previo = anterior(argumentos.conjunto)
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
        salida = {"fecha": datetime.now().isoformat(timespec="seconds"), "conjunto": argumentos.conjunto,
                  "modelo": argumentos.modelo or ("sonnet" if llamada else "auto"),
                  "aprobados": aprobados, "total": len(resultados), "coste_usd": round(coste, 4),
                  "resultados": resultados}
        ruta = RESULTADOS / f"{'llamada-' if llamada else ''}{datetime.now():%Y%m%d-%H%M%S}.json"
        ruta.write_text(json.dumps(salida, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"Guardado en {ruta.relative_to(RAIZ)}")
    return 0 if aprobados == len(resultados) else 1


if __name__ == "__main__":
    sys.exit(main())
