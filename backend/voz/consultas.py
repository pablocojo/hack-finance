"""
Herramientas de LECTURA de la llamada: `consultar_cuentas`, `buscar_movimientos` y `lo_que_sabes_de_mi`
(docs/diseno/experiencia.md, «Herramientas de la llamada»). Reglas:

- Solo lectura y siempre del usuario de la SESIÓN: ninguna función recibe un `usuario_id` del modelo.
- Nada se vuelca en el contexto: el agente pregunta lo que necesita, con un máximo de `MAX_RESULTADOS` filas.
- Las cifras salen ya calculadas del código (saldos, pendientes, totales): el agente no suma.
- Lo que devuelven es DATO, nunca instrucción: todo texto libre (comercios, conceptos, nombres, notas, motivos) va
  entre `<datos>…</datos>`, saneado y enmascarado. Nunca la nota de un Bizum, ni movimientos sensibles (RGPD), ni
  ingresos, gasto por categoría o `resumen_vida`.
- Los errores salen como `{"ok": false, "error": "…"}` en español, sin lanzar.
"""

from __future__ import annotations

import unicodedata
from datetime import date
from decimal import Decimal
from typing import Any

from .. import casos
from ..modulos.plantillas import sanear_dato
from ..personalizacion.memoria import textos_para_agente
from ..personalizacion.perfil import es_sensible
from ..plataforma import almacenamiento as alm
from ..plataforma import orquestador
from ..plataforma.privacidad import enmascarar_nombre, enmascarar_texto
from ..plataforma.tipos import ModeloUsuario

MAX_RESULTADOS = 10
LIMITE_PREDETERMINADO = 5
ESTADOS = ("abiertos", "cerrados", "todos")


def dato(texto: Any, maximo: int = 60) -> str | None:
    """Texto libre -> `<datos>…</datos>` saneado y enmascarado (IBAN, teléfonos, correos); `None` si queda vacío."""
    limpio = sanear_dato(enmascarar_texto(str(texto or "")), maximo)
    return f"<datos>{limpio}</datos>" if limpio else None


def _sin_vacios(**campos: Any) -> dict:
    return {k: v for k, v in campos.items() if v not in (None, "", [])}


def _normal(texto: Any) -> str:
    base = unicodedata.normalize("NFD", str(texto or "")).encode("ascii", "ignore").decode()
    return " ".join(base.lower().split())


# --- consultar_cuentas ----------------------------------------------------------------------------

def _coincide(clave: str, buscada: str) -> bool:
    """«Marcos», «Marcos R.» o «Marcos Ruiz» encajan con la clave `MARCOS R`; un nombre de pila solo, con cualquiera."""
    return clave == buscada or (" " not in buscada and clave.split()[:1] == [buscada])


def _caso_vista(c: dict) -> dict:
    cerrado = c["estado"] in casos.CERRADOS
    origen = c.get("movimiento_origen") or {}
    comercio = c.get("comercio") or origen.get("comercio")
    if comercio and es_sensible(comercio=comercio):
        comercio = None                      # RGPD: un comercio sensible no se detalla
    pregunta = c.get("pregunta") if (c.get("pregunta") or {}).get("estado") == "pendiente" else None
    return _sin_vacios(
        caso_id=c["id"], tipo=c.get("escenario") or "dudoso", estado=c["estado"], comercio=dato(comercio),
        fecha=origen.get("fecha") or c.get("creado"), importe_total=c.get("importe_total"),
        importe_pendiente="0.00" if cerrado else c["importe_pendiente"],
        personas=[_sin_vacios(nombre=dato(d["nombre"]), debe=d["cuota"], estado=d["estado"], via_saldado=d.get("via_saldado"),
                              motivo_saldado=dato(d.get("motivo_saldado"), 120), saldada=d.get("saldada"))
                  for d in c["deudores"]],
        pregunta_pendiente=_sin_vacios(texto=dato(pregunta["texto"], 200),
                                       personas=[dato(n) for n in pregunta.get("candidatos", [])]) if pregunta else None,
        acuerdos=[dato(a, 140) for a in (c.get("acuerdos") or [])[-3:]])


def cuentas(usuario_id: str, persona: str | None = None, estado: str | None = None) -> dict:
    """Casos y saldo por persona. `estado`: abiertos (por defecto), cerrados o todos. Máximo 10 casos y 10 personas."""
    estado = (estado or "abiertos").strip().lower()
    if estado not in ESTADOS:
        return {"ok": False, "error": f"El estado debe ser uno de: {', '.join(ESTADOS)}."}
    buscada = None
    if persona not in (None, ""):
        buscada = casos.clave_persona(persona)
        if buscada is None:
            return {"ok": False, "error": "Dime el nombre de la persona."}
    try:
        lista = orquestador.casos_usuario(usuario_id)
        contactos = orquestador.contactos_usuario(usuario_id)
    except ValueError as error:
        return {"ok": False, "error": str(error)}

    def de_persona(c: dict) -> bool:
        return buscada is None or any(_coincide(d["contraparte"], buscada) for d in c["deudores"])

    abiertos = [c for c in lista if c["estado"] in casos.ABIERTOS]
    cerrados = [c for c in lista if c["estado"] in casos.CERRADOS]
    elegidos = {"abiertos": abiertos, "cerrados": cerrados, "todos": lista}[estado]
    elegidos = [c for c in elegidos if de_persona(c)]
    elegidos.sort(key=lambda c: (c["estado"] in casos.CERRADOS, -Decimal(c["importe_pendiente"]), c["creado"]))
    filas = [f for f in contactos if (_coincide(f["contraparte"], buscada) if buscada
                                      else Decimal(f["saldo_total"]) > 0 or f["casos_abiertos"] > 0)]
    total = sum((Decimal(f["saldo_total"]) for f in filas), Decimal("0")).quantize(Decimal("0.01"))
    if not elegidos and not filas:
        return {"ok": True, "personas": [], "casos": [],
                "aviso": "No hay nada con esa persona en tus cuentas." if buscada else "No hay cuentas con nadie ahora mismo."}
    return _sin_vacios(
        ok=True,
        pendiente_total=format(total, "f"),
        personas=[_sin_vacios(nombre=dato(f["nombre"]), relacion=f.get("relacion"), te_debe=f["saldo_total"],
                              casos_abiertos=f["casos_abiertos"]) for f in filas[:MAX_RESULTADOS]],
        casos=[_caso_vista(c) for c in elegidos[:MAX_RESULTADOS]],
        recortado=True if len(elegidos) > MAX_RESULTADOS or len(filas) > MAX_RESULTADOS else None,
        total_casos=len(elegidos) if len(elegidos) > MAX_RESULTADOS else None)


# --- buscar_movimientos ---------------------------------------------------------------------------

def _fecha(valor: Any, nombre: str) -> date | None:
    if valor in (None, ""):
        return None
    try:
        return date.fromisoformat(str(valor).strip()[:10])
    except ValueError:
        raise ValueError(f"`{nombre}` debe ser una fecha AAAA-MM-DD.") from None


def _euros(valor: Any, nombre: str) -> Decimal | None:
    if valor in (None, ""):
        return None
    d = casos.ciclo.a_decimal(valor)
    if d is None or d < 0:
        raise ValueError(f"`{nombre}` debe ser un importe en euros, positivo.")
    return d


def _entero(valor: Any) -> int:
    d = casos.ciclo.a_decimal(valor)
    if d is None or d != d.to_integral_value():
        raise ValueError("`limite` debe ser un número entero de 1 a 10.")
    return int(d)


def movimientos(usuario_id: str, texto: str | None = None, desde: str | None = None, hasta: str | None = None,
                importe_min: Any = None, importe_max: Any = None, limite: Any = None) -> dict:
    """Movimientos hasta «hoy», de más reciente a más antiguo, sin la nota de Bizum, como mucho 10. `texto` busca en el
    concepto, el comercio, la contraparte y la categoría; los importes filtran por valor absoluto."""
    try:
        d1, d2 = _fecha(desde, "desde"), _fecha(hasta, "hasta")
        minimo, maximo = _euros(importe_min, "importe_min"), _euros(importe_max, "importe_max")
        if d1 and d2 and d1 > d2:
            raise ValueError("`desde` no puede ser posterior a `hasta`.")
        if minimo is not None and maximo is not None and minimo > maximo:
            raise ValueError("`importe_min` no puede ser mayor que `importe_max`.")
        n = LIMITE_PREDETERMINADO if limite in (None, "") else _entero(limite)
    except ValueError as error:
        return {"ok": False, "error": str(error)}
    n = max(1, min(n, MAX_RESULTADOS))
    buscado = _normal(texto)
    try:
        lista = orquestador.movimientos_usuario(usuario_id, 500)
    except ValueError as error:
        return {"ok": False, "error": str(error)}
    encontrados, sensibles = [], 0
    for m in lista:
        fecha, importe = date.fromisoformat(m["fecha"]), abs(Decimal(m["importe"]))
        if (d1 and fecha < d1) or (d2 and fecha > d2) or (minimo is not None and importe < minimo) \
                or (maximo is not None and importe > maximo):
            continue
        if buscado and buscado not in _normal(" ".join(str(m.get(k) or "") for k in ("concepto", "comercio", "contraparte", "categoria"))):
            continue
        if es_sensible(m.get("categoria"), m.get("comercio"), m.get("concepto")):
            sensibles += 1                   # RGPD: un movimiento sensible no se detalla
            continue
        encontrados.append(m)
    return _sin_vacios(
        ok=True, encontrados=len(encontrados), devueltos=min(len(encontrados), n),
        movimientos=[_sin_vacios(id=m["id"], fecha=m["fecha"], concepto=dato(m["concepto"], 80), comercio=dato(m.get("comercio")),
                                 importe=m["importe"], categoria=m.get("categoria"), canal=m.get("canal"),
                                 contraparte=dato(m.get("contraparte"))) for m in encontrados[:n]],
        omitidos_por_sensibles=sensibles or None,
        aviso="Hay más resultados: acota con fechas, texto o importes." if len(encontrados) > n else None)


# --- lo_que_sabes_de_mi ---------------------------------------------------------------------------

def aprendido(usuario_id: str) -> dict:
    """Lo aprendido, como «Lo que he aprendido» y `memoria_para_agente`: hechos operativos activos, personas silenciadas,
    relaciones que declaró el usuario, notas de llamadas y horario de avisos. Sin ingresos, importes por categoría ni
    `resumen_vida`."""
    try:
        modelo = alm.cargar(usuario_id, "modelo", tipo=ModeloUsuario)
        lista = orquestador.casos_usuario(usuario_id)
        contactos = orquestador.contactos_usuario(usuario_id)
    except ValueError as error:
        return {"ok": False, "error": str(error)}
    if modelo is None:
        return {"ok": False, "error": "Todavía no he aprendido nada de ti."}
    notas = [dato(t, 140) for c in lista for t in [*(c.get("acuerdos") or []), *(c.get("conversaciones") or [])]]
    p = modelo.preferencias
    resultado = _sin_vacios(
        ok=True,
        lo_aprendido=[dato(t, 140) for t in textos_para_agente(modelo)],
        no_avisar=[_sin_vacios(tipo=s.ambito, valor=dato(enmascarar_nombre(s.valor) if s.ambito == "contacto" else s.valor),
                               desde=s.desde.isoformat()) for s in p.silencios][:MAX_RESULTADOS],
        relaciones=[{"nombre": dato(f["nombre"]), "relacion": f["relacion"]} for f in contactos if f.get("relacion")][:MAX_RESULTADOS],
        notas_de_llamadas=[n for n in notas if n][-MAX_RESULTADOS:],
        avisos={"entre_las": f"{p.hora_inicio}:00 y las {p.hora_fin}:00", "maximo_por_dia": p.max_avisos_dia},
        nota="Todo esto se ve, se edita y se borra en «Lo que he aprendido».")
    if not any(resultado.get(k) for k in ("lo_aprendido", "no_avisar", "relaciones", "notas_de_llamadas")):
        resultado["aviso"] = "Todavía no he aprendido nada concreto de ti."
    return resultado
