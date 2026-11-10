"""
Casos de deuda (docs/diseno/deudas-casos.md): el objeto vivo detrás de un momento de `gasto_compartido`.

API pública (todo puro salvo `cargar` y `guardar`; solo el orquestador escribe en disco):

    crear_desde_momento(momento, hoy=None, ahora=None) -> Caso
    saldar_con_movimientos(caso, movimientos, hoy, ahora=None) -> Caso      (cierre.py)
    saldar_casos(casos, movimientos, hoy, ahora=None) -> list[Caso]
    posponer(caso, hoy, dias=2, origen="feedback", ahora=None) -> Caso
    descartar(caso, hoy, motivo, origen="feedback", ahora=None) -> Caso
    cerrar(caso, estado, hoy, motivo="", origen="codigo", ahora=None) -> Caso
    marcar_pedido(caso, contraparte, hoy, origen="usuario", ahora=None) -> Caso
    aplicar_feedback(caso, resultado, hoy, ahora=None) -> Caso
    listo_para_avisar(caso, hoy) -> bool;  agrupar_por_contacto(casos) -> list[list[Caso]]
    amigos_desde_casos(casos, hoy) -> list[Amigo];  sincronizar_amigos(modelo, casos, hoy) -> ModeloUsuario
    cargar(usuario_id) -> list[Caso];  guardar(usuario_id, casos) -> None
"""

from __future__ import annotations

from ..plataforma import almacenamiento as _alm
from ..plataforma.tipos import Caso
from .amigos import amigos_desde_casos, olvidar_contacto, purgar, sincronizar_amigos
from .ciclo import (
    ABIERTOS,
    CERRADOS,
    DIAS_COLA,
    DIAS_POSPONER,
    DIAS_VIDA,
    MOTIVO_DUDOSO,
    TOLERANCIA,
    agrupar_por_contacto,
    aplicar_feedback,
    caducar,
    cerrar,
    crear_desde_momento,
    de_propuesta,
    decision_dudosa,
    descartar,
    es_dudoso,
    importe_pendiente,
    listo_para_avisar,
    marcar_avisado,
    marcar_ignorado,
    marcar_pedido,
    pendientes,
    posponer,
    vincular_propuesta,
)
from .cierre import pagos_entrantes, saldar_casos, saldar_con_movimientos

NOMBRE_ARCHIVO = "casos"


def cargar(usuario_id: str) -> list[Caso]:
    """Lee `casos.json` del usuario (vacío si no existe)."""
    return _alm.cargar(usuario_id, NOMBRE_ARCHIVO, tipo=list[Caso], defecto=[])


def guardar(usuario_id: str, casos: list[Caso]) -> None:
    """Guarda `casos.json` (escritura atómica). Hay que llamarla dentro del candado del usuario."""
    _alm.guardar(usuario_id, NOMBRE_ARCHIVO, casos)
