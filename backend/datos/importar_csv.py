"""
Importa extractos CSV de bancos españoles y los normaliza al formato del kit.

Soporta separador ; , tabulador o |, coma decimal ("1.234,56"), fechas dd/mm/aaaa,
columnas Cargo/Abono separadas, filas de cabecera previas y codificaciones utf-8 o latin-1.
Los conceptos se enmascaran (IBAN, tarjetas, DNI, emails, teléfonos) al importar.
"""

from __future__ import annotations

import csv
import io
import re
from datetime import date, datetime

from .categorias import CATEGORIAS, categorizar_por_reglas, normalizar

COLUMNAS = {
    "fecha": ["fecha", "fecha operacion", "f. operacion", "f.operacion", "fecha valor", "f. valor",
              "fecha contable", "date"],
    "concepto": ["concepto", "descripcion", "movimiento", "detalle", "concepto comun",
                 "observaciones", "description", "concept"],
    "importe": ["importe", "cantidad", "importe (eur)", "importe eur", "importe euros", "amount"],
    "cargo": ["cargo", "debe", "gasto", "cargos"],
    "abono": ["abono", "haber", "ingreso", "abonos"],
    "saldo": ["saldo", "saldo (eur)", "saldo eur", "disponible", "balance"],
    "categoria": ["categoria", "category"],
}
FORMATOS_FECHA = ["%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%y", "%d.%m.%Y", "%Y/%m/%d"]
_PREFIJOS = re.compile(
    r"^(COMPRA (EN )?(TARJ(ETA)?\.?|TARJ\.)( \d{4}X+\d{4})?|COMPRA ONLINE|PAGO (CON )?(TARJETA|MOVIL)|"
    r"RECIBO|ADEUDO|TRANSFERENCIA (EMITIDA|RECIBIDA|A FAVOR DE|DE)?|TRANSF\.?|BIZUM (ENVIADO|RECIBIDO)( A| DE)?)\s*",
)


def _decodificar(contenido: bytes | str) -> str:
    if isinstance(contenido, str):
        return contenido
    for codificacion in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return contenido.decode(codificacion)
        except UnicodeDecodeError:
            continue
    return contenido.decode("utf-8", errors="replace")


def _separador(texto: str) -> str:
    muestra = "\n".join(texto.splitlines()[:20])
    try:
        return csv.Sniffer().sniff(muestra, delimiters=";,\t|").delimiter
    except csv.Error:
        conteos = {s: muestra.count(s) for s in ";,\t|"}
        return max(conteos, key=conteos.get)


def numero(texto) -> float | None:
    """Convierte "1.234,56", "-45,20", "45,20-", "(45,20)" o "1,234.56" en float."""
    if texto is None:
        return None
    if isinstance(texto, (int, float)):
        return float(texto)
    limpio = str(texto).replace("\xa0", "").replace("€", "").replace("EUR", "").replace(" ", "").strip()
    if not limpio:
        return None
    negativo = limpio.startswith("-") or limpio.endswith("-") or (limpio.startswith("(") and limpio.endswith(")"))
    limpio = limpio.strip("-+()")
    if "," in limpio and "." in limpio:
        if limpio.rfind(",") > limpio.rfind("."):
            limpio = limpio.replace(".", "").replace(",", ".")
        else:
            limpio = limpio.replace(",", "")
    elif "," in limpio:
        limpio = limpio.replace(",", ".")
    elif limpio.count(".") >= 1 and len(limpio.rsplit(".", 1)[1]) == 3:
        limpio = limpio.replace(".", "")  # "1.234" en un extracto español son mil doscientos...
    try:
        valor = float(limpio)
    except ValueError:
        return None
    return -valor if negativo else valor


def fecha(texto) -> date | None:
    texto = str(texto or "").strip()
    for formato in FORMATOS_FECHA:
        try:
            return datetime.strptime(texto[:10], formato).date()
        except ValueError:
            continue
    return None


def extraer_comercio(concepto: str) -> str:
    """Nombre corto del comercio a partir del concepto del banco."""
    texto = normalizar(concepto)
    texto = _PREFIJOS.sub("", texto)
    texto = re.sub(r"\b\d{4}X+\d{4}\b|\b\d{2}/\d{2}(/\d{2,4})?\b|\*+", " ", texto)
    palabras = [p for p in texto.split() if not p.isdigit()]
    return " ".join(palabras[:3]) or normalizar(concepto)[:30]


def _mapear_columnas(cabecera: list[str]) -> dict[str, int]:
    normal = [normalizar(c).lower().strip() for c in cabecera]
    mapa = {}
    for campo, sinonimos in COLUMNAS.items():
        for indice, nombre in enumerate(normal):
            if nombre in sinonimos and campo not in mapa:
                mapa[campo] = indice
    return mapa


def importar_csv(contenido: bytes | str) -> tuple[list[dict], dict]:
    """Devuelve (movimientos, informe). Lanza ValueError si no reconoce las columnas."""
    from ..agente.guardarrailes import enmascarar

    texto = _decodificar(contenido)
    filas = list(csv.reader(io.StringIO(texto), delimiter=_separador(texto)))
    inicio, mapa = None, {}
    for indice, fila in enumerate(filas[:25]):
        mapa = _mapear_columnas(fila)
        if "fecha" in mapa and "concepto" in mapa and ("importe" in mapa or "cargo" in mapa):
            inicio = indice
            break
    if inicio is None:
        raise ValueError(
            "No encuentro las columnas de fecha, concepto e importe. "
            "Revisa que el CSV tenga una fila de cabecera (por ejemplo: Fecha;Concepto;Importe;Saldo)."
        )

    movimientos, descartadas, ocultados = [], 0, 0
    for fila in filas[inicio + 1:]:
        if not any(celda.strip() for celda in fila):
            continue
        try:
            dia = fecha(fila[mapa["fecha"]])
            concepto = fila[mapa["concepto"]].strip()
            if "importe" in mapa:
                importe = numero(fila[mapa["importe"]])
            else:
                cargo = numero(fila[mapa["cargo"]]) or 0.0
                abono = numero(fila[mapa["abono"]]) if "abono" in mapa else 0.0
                importe = (abono or 0.0) - abs(cargo)
        except IndexError:
            descartadas += 1
            continue
        if dia is None or importe is None:
            descartadas += 1
            continue
        concepto, n = enmascarar(concepto)
        ocultados += n
        categoria = None
        if "categoria" in mapa and len(fila) > mapa["categoria"]:
            categoria = normalizar(fila[mapa["categoria"]]).lower() or None
            if categoria not in CATEGORIAS:
                categoria = None
        movimiento = {
            "id": f"csv-{len(movimientos) + 1:05d}",
            "fecha": dia.isoformat(),
            "concepto": concepto,
            "comercio": extraer_comercio(concepto),
            "importe": round(importe, 2),
            "categoria": categoria or categorizar_por_reglas(concepto, importe),
        }
        if "saldo" in mapa and len(fila) > mapa["saldo"]:
            saldo = numero(fila[mapa["saldo"]])
            if saldo is not None:
                movimiento["saldo"] = round(saldo, 2)
        movimientos.append(movimiento)

    movimientos.sort(key=lambda m: m["fecha"])
    informe = {
        "filas_leidas": len(filas) - inicio - 1,
        "importadas": len(movimientos),
        "descartadas": descartadas,
        "datos_personales_ocultados": ocultados,
        "columnas": {campo: filas[inicio][i] for campo, i in mapa.items()},
        "sin_categoria": sum(1 for m in movimientos if not m["categoria"]),
    }
    return movimientos, informe
