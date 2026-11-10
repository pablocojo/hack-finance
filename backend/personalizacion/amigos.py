"""
`observar` (O7): contactos y saldo con cada amigo. Puro: no guarda nada (guarda el orquestador).

- `observar(modelo, movimientos, hoy)` (firma fija del contrato): por cada Bizum o transferencia del día suma
  una vez a `contactos` (clave de contraparte `MARCOS R`). Nunca guarda conceptos ni notas.
- `saldo_amigos(modelo, casos, hoy)`: el saldo con cada amigo se CALCULA a partir de los `Caso`
  (`backend/casos/amigos.py`); `Amigo` no se estira ni se guarda aparte. Lo llama el orquestador tras `observar`.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, get_args

from ..motor.normalizar import clave_contraparte, normalizar
from ..plataforma.privacidad import enmascarar_nombre, enmascarar_texto
from ..plataforma.tipos import Caso, Contacto, ModeloUsuario, Movimiento, Relacion

RELACIONES = get_args(Relacion)


def observar(modelo: ModeloUsuario, movimientos: list[Movimiento], hoy: date) -> ModeloUsuario:
    nuevo = modelo
    for m in movimientos:
        e = normalizar(m)
        if e.canal not in ("bizum", "transferencia") or not e.contraparte_normalizada or e.fecha > hoy:
            continue
        if nuevo is modelo:
            nuevo = modelo.model_copy(deep=True)
        previo = nuevo.contactos.get(e.contraparte_normalizada)
        if previo is None:
            previo = Contacto(contraparte=e.contraparte_normalizada, nombre=enmascarar_nombre(e.contraparte_normalizada))
        # conserva lo que ya sabemos de la persona (nombre, teléfono y la relación que declaró el usuario)
        nuevo.contactos[e.contraparte_normalizada] = previo.model_copy(update={
            "veces": previo.veces + 1, "ultima": max(e.fecha, previo.ultima) if previo.ultima else e.fecha})
    return nuevo


def saldo_amigos(modelo: ModeloUsuario, casos: list[Caso], hoy: date) -> ModeloUsuario:
    from ..casos import sincronizar_amigos
    return sincronizar_amigos(modelo, casos, hoy)


# --- Personas en relación (agenda, saldo y relación declarada) ------------------------------------

def contacto_de_agenda(crudo: Any) -> Contacto | None:
    """Un contacto de la agenda inventada de un escenario (`Contacto` o dict con `contraparte`/`nombre`). El nombre y
    el teléfono salen enmascarados y la relación solo vale si es una de la lista; si no se entiende, `None`."""
    if isinstance(crudo, Contacto):
        crudo = crudo.model_dump()
    if not isinstance(crudo, dict):
        return None
    clave = clave_contraparte(crudo.get("contraparte") or crudo.get("nombre"))
    if not clave:
        return None
    relacion = crudo.get("relacion")
    telefono = crudo.get("telefono")
    return Contacto(contraparte=clave, nombre=enmascarar_nombre(crudo.get("nombre") or clave),
                    telefono=enmascarar_texto(str(telefono)) if telefono else None,
                    relacion=relacion if relacion in RELACIONES else None)


def agenda_de_escenario(crudos: Any) -> dict[str, Contacto]:
    """`Escenario.contactos` (lista de contactos o dict clave -> contacto) -> `ModeloUsuario.contactos`."""
    if isinstance(crudos, dict):
        crudos = [{"contraparte": k, **v} if isinstance(v, dict) else v for k, v in crudos.items()]
    salida: dict[str, Contacto] = {}
    for crudo in crudos if isinstance(crudos, list) else []:
        contacto = contacto_de_agenda(crudo)
        if contacto is not None:
            salida[contacto.contraparte] = contacto
    return salida


def buscar_contacto(modelo: ModeloUsuario, texto: str) -> str | None:
    """Clave del contacto por su clave o su nombre enmascarado («MARCOS R», «Marcos R.», «Marcos Ruiz Sanz»)."""
    clave = clave_contraparte(texto)
    if clave is None:
        return None
    if clave in modelo.contactos:
        return clave
    for k, c in modelo.contactos.items():
        if c.nombre and clave_contraparte(c.nombre) == clave:
            return k
    return None


def anotar_contacto(modelo: ModeloUsuario, clave: str, dia: date) -> ModeloUsuario:
    """Un caso nuevo con esa persona: crea el contacto si no estaba y suma una vez (`veces`, `ultima`)."""
    previo = modelo.contactos.get(clave) or Contacto(contraparte=clave, nombre=enmascarar_nombre(clave))
    nuevo = modelo.model_copy(deep=True)
    nuevo.contactos[clave] = previo.model_copy(update={
        "veces": previo.veces + 1, "ultima": max(dia, previo.ultima) if previo.ultima else dia})
    return nuevo


def editar_relacion(modelo: ModeloUsuario, clave: str, relacion: str | None) -> ModeloUsuario:
    """La relación la declara el usuario (nunca se infiere); `None` la borra. Si la persona solo estaba en un caso,
    se crea su contacto. Lanza `ValueError` si la relación no es de la lista."""
    if relacion is not None and relacion not in RELACIONES:
        raise ValueError(f"La relación debe ser una de: {', '.join(RELACIONES)}.")
    previo = modelo.contactos.get(clave) or Contacto(contraparte=clave, nombre=enmascarar_nombre(clave))
    nuevo = modelo.model_copy(deep=True)
    nuevo.contactos[clave] = previo.model_copy(update={"relacion": relacion})
    return nuevo


def borrar_contacto(modelo: ModeloUsuario, clave: str) -> ModeloUsuario:
    nuevo = modelo.model_copy(deep=True)
    nuevo.contactos.pop(clave, None)
    return nuevo


def contactos_con_saldo(modelo: ModeloUsuario, casos: list[Caso], hoy: date) -> list[dict]:
    """La agenda más quienes aparecen en casos, con `saldo_total` (lo que aún te debe, calculado desde los casos
    vivos) y `casos_abiertos`. Sin conceptos y sin valorar a nadie."""
    from ..casos.amigos import _vivo
    from ..casos.ciclo import pendientes

    saldo: dict[str, Decimal] = {}
    abiertos: dict[str, set[str]] = {}
    for caso in casos:
        if not _vivo(caso, hoy):
            continue
        for d in pendientes(caso):
            saldo[d.contraparte] = saldo.get(d.contraparte, Decimal("0")) + d.cuota
            abiertos.setdefault(d.contraparte, set()).add(caso.id)
    filas = []
    for clave in {*modelo.contactos, *saldo}:
        c = modelo.contactos.get(clave) or Contacto(contraparte=clave)
        filas.append({"contraparte": clave, "nombre": c.nombre or enmascarar_nombre(clave), "telefono": c.telefono,
                      "relacion": c.relacion, "saldo_total": format(saldo.get(clave, Decimal("0")).quantize(Decimal("0.01")), "f"),
                      "casos_abiertos": len(abiertos.get(clave, ())), "veces": c.veces,
                      "ultima": c.ultima.isoformat() if c.ultima else None})
    return sorted(filas, key=lambda f: (-Decimal(f["saldo_total"]), f["nombre"]))
