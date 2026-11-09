"""
Plataforma de módulos. STUB de E1: firmas definitivas de docs/ARQUITECTURA.md §3.2.
Lo sustituye el hilo `modulos`; las firmas no cambian.
"""

from __future__ import annotations

from ..plataforma.tipos import BorradorModulo, InformePrueba, ControlPrueba, ModeloUsuario, Modulo, Momento, Propuesta


def proponer(momento: Momento, modelo: ModeloUsuario) -> list[Propuesta]:
    """Momento + modelo -> propuestas de los módulos que lo escuchan. Stub: ninguna."""
    return []


def crear_borrador(descripcion: str) -> BorradorModulo:
    """Claude redacta el YAML y se valida con el esquema. Stub: borrador de ejemplo."""
    return BorradorModulo(
        spec={
            "id": "borrador_ejemplo",
            "version": 1,
            "nombre": "Borrador de ejemplo",
            "estado": "borrador",
            "origen": "lenguaje_natural",
            "escucha": ["subida_recibo"],
        },
        interpretacion=["Stub de E1: sin interpretar."],
    )


def probar_en_seco(borrador: BorradorModulo, usuario_id: str) -> InformePrueba:
    """Sin efectos. Stub: informe vacío con un control en ok."""
    return InformePrueba(
        controles=[ControlPrueba(nombre="esquema_valido", ok=True)],
        resumen="0 avisos (stub)",
    )


def aprobar(modulo_id: str, aprobado_por: str) -> Modulo:
    """Exige informe aprobado y guarda el YAML en datos_usuario/_modulos/. Stub: módulo de ejemplo."""
    return Modulo(
        id=modulo_id, nombre=modulo_id, estado="activo", origen="lenguaje_natural",
        escucha=["subida_recibo"], aprobado_por=aprobado_por,
    )
