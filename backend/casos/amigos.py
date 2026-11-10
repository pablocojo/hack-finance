"""
O7, saldo con cada amigo: se CALCULA a partir de los `Caso` (no se estira `Amigo`).

- Un `Amigo` por contraparte, con la contraparte enmascarada («Marcos R.») y sin conceptos.
- `saldo` = suma de las cuotas que esa persona aún no ha pagado en casos vivos. Un caso `dudoso` no cuenta
  (es una hipótesis, no una deuda) y un caso con más de 90 días tampoco.
- Estado: `pedido` si hay una solicitud abierta; `olvidado` si todas sus deudas quedaron olvidadas (aviso sin
  respuesta); `detectado` en otro caso. Al saldarse desaparece de la lista (los casos cerrados no cuentan).
- Todo se ve y se borra en «Lo que he aprendido»: `olvidar_contacto` quita a la persona de los casos.
- El agente nunca valora a una persona: aquí solo hay saldos y estados.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from ..plataforma.privacidad import enmascarar_nombre
from ..plataforma.tipos import Amigo, Caso, ModeloUsuario
from .ciclo import ABIERTOS, DIAS_VIDA, _clave, pendientes


def _vivo(caso: Caso, hoy: date) -> bool:
    return caso.estado in ABIERTOS and caso.estado != "dudoso" and (hoy - caso.creado).days < DIAS_VIDA


def amigos_desde_casos(casos: list[Caso], hoy: date) -> list[Amigo]:
    """`list[Amigo]` ordenada por saldo (mayor primero) y nombre. Pura."""
    por_clave: dict[str, list[tuple[Caso, object]]] = {}
    for caso in casos:
        if not _vivo(caso, hoy):
            continue
        for d in pendientes(caso):
            por_clave.setdefault(d.contraparte, []).append((caso, d))
    salida: list[Amigo] = []
    for clave, pares in por_clave.items():
        deudas = [d for _, d in pares]
        casos_de = [c for c, _ in pares]
        primero = min(casos_de, key=lambda c: (c.creado, c.id))
        pedidas = [d.pedida for d in deudas if d.estado == "pedida" and d.pedida]
        if any(d.estado == "pedida" for d in deudas):
            estado = "pedido"
        elif all(d.estado == "olvidada" for d in deudas):
            estado = "olvidado"
        else:
            estado = "detectado"
        salida.append(Amigo(contraparte=enmascarar_nombre(clave) or clave,
                            saldo=sum((d.cuota for d in deudas), Decimal("0")),
                            propuesta_origen=primero.propuesta_id or primero.id, estado=estado,
                            creado=primero.creado, pedido=min(pedidas) if pedidas else None))
    return sorted(salida, key=lambda a: (-a.saldo, a.contraparte))


def sincronizar_amigos(modelo: ModeloUsuario, casos: list[Caso], hoy: date) -> ModeloUsuario:
    """Devuelve el modelo con `amigos` recalculados desde los casos."""
    amigos = amigos_desde_casos(casos, hoy)
    if amigos == modelo.amigos:
        return modelo
    return modelo.model_copy(update={"amigos": amigos})


def _coincide(clave: str, contraparte: str) -> bool:
    objetivo = _clave(contraparte)
    if objetivo is None:
        return False
    return clave == objetivo or enmascarar_nombre(clave).upper() == " ".join(contraparte.strip().upper().split())


def olvidar_contacto(casos: list[Caso], contraparte: str) -> tuple[list[Caso], bool]:
    """Quita a esa persona (clave «MARCOS R» o nombre enmascarado «Marcos R.») de todos los casos. Un caso que se
    queda sin deudores desaparece. Devuelve `(casos, hubo_cambios)`."""
    nuevos: list[Caso] = []
    cambio = False
    for caso in casos:
        quedan = [d for d in caso.deudores if not _coincide(d.contraparte, contraparte)]
        if len(quedan) == len(caso.deudores):
            nuevos.append(caso)
            continue
        cambio = True
        if quedan:
            nuevos.append(caso.model_copy(update={"deudores": quedan}, deep=True))
    return nuevos, cambio


def purgar(casos: list[Caso], hoy: date) -> list[Caso]:
    """Los casos cerrados (saldado, descartado, caducado) con más de 90 días se borran."""
    limite = hoy - timedelta(days=DIAS_VIDA)
    return [c for c in casos if not (c.estado in ("saldado", "descartado", "caducado") and c.creado <= limite)]
