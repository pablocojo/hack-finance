"""
Plataforma de módulos (E4). `proponer` es real; `crear_borrador`, `probar_en_seco` y `aprobar` son
STUBS con el módulo de la demo `recibo_al_alza` (sin llamar a Claude todavía; D2 los completa).
Las firmas son las del contrato.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from ..plataforma.tipos import (
    AvisoPrueba, BorradorModulo, ControlPrueba, InformePrueba, ModeloUsuario, Modulo, Momento, Propuesta,
)
from . import esquema, proponer as _proponer, registro
from .esquema import ModuloSpec

RECIBO_AL_ALZA: dict = {
    "id": "recibo_al_alza",
    "version": 1,
    "nombre": "Recibo que sube",
    "descripcion": "Avisa cuando un recibo sube más de 8 euros y ofrece guiar la baja o recordarlo.",
    "estado": "borrador",
    "origen": "lenguaje_natural",
    "escucha": ["subida_recibo"],
    "cuando": "momento.datos.subida_eur > 8",
    "propuesta": {
        "titulo": "{datos.comercio|dato} ha subido",
        "mensaje_notificacion": "{datos.comercio|dato} ha subido de {datos.importe_habitual|eur} a {datos.importe_actual|eur}.",
        "contexto_llamada": "Subida de recibo de {datos.comercio|dato}: antes {datos.importe_habitual|eur}, ahora {datos.importe_actual|eur} ({datos.subida_pct|pct}).",
        "urgencia": "media",
        "valor_estimado_eur": "momento.datos.subida_eur",
    },
    "acciones": [
        {"accion_id": "cancelar_suscripcion", "parametros": {"comercio": "{datos.comercio}", "bloquear_cobros": False}},
        {"accion_id": "recordar", "parametros": {"cuando": "+7d", "texto": "Revisar la subida de {datos.comercio|dato}"}},
    ],
}

_BORRADORES: dict[str, BorradorModulo] = {}
_INFORMES: dict[str, InformePrueba] = {}


def proponer(momento: Momento, modelo: ModeloUsuario) -> list[Propuesta]:
    """Momento + modelo -> propuestas de los módulos activos que lo escuchan."""
    return _proponer.proponer(momento, modelo)


def crear_borrador(descripcion: str) -> BorradorModulo:
    """STUB: devuelve `recibo_al_alza` validado (D2: Claude Sonnet 5.5 con salida estructurada)."""
    spec = ModuloSpec.model_validate(RECIBO_AL_ALZA)
    borrador = BorradorModulo(
        spec=spec.model_dump(mode="json"),
        interpretacion=[
            "Escucha las subidas de recibo.",
            "Avisa si la subida es de más de 8 euros.",
            "Ofrece guiarte para darte de baja o recordártelo en una semana.",
        ],
        advertencias=esquema.advertencias(spec) + ["Borrador de ejemplo: aún no se interpreta tu descripción."],
    )
    _BORRADORES[spec.id] = borrador
    return borrador


def _momento_ejemplo(tipo: str, **datos) -> Momento:
    return Momento(id=f"ejemplo-{tipo}-{len(datos)}", tipo=tipo, usuario_id="prueba", fecha=date(2026, 11, 9),
                   datos=datos, confianza=0.9, impacto_eur=None, explicacion="Ejemplo de prueba", detector="ejemplo",
                   version="0")


def probar_en_seco(borrador: BorradorModulo, usuario_id: str) -> InformePrueba:
    """Sin efectos. STUB: controles reales sobre el esquema y las plantillas; escenario de ejemplo solo para
    `subida_recibo` (subida de 12 EUR que avisa y de 2 EUR que no)."""
    controles: list[ControlPrueba] = []
    try:
        spec = ModuloSpec.model_validate(borrador.spec)
        controles.append(ControlPrueba(nombre="esquema_valido", ok=True))
    except Exception as e:
        return InformePrueba(controles=[ControlPrueba(nombre="esquema_valido", ok=False, detalle=str(e)[:300])],
                             resumen="El esquema no es válido.")
    controles.append(ControlPrueba(nombre="acciones_2_o_3", ok=2 <= len(spec.acciones) <= 3,
                                   detalle=f"{len(spec.acciones)} acciones"))
    avisos: list[AvisoPrueba] = []
    aciertos = falsos = 0
    if "subida_recibo" in spec.escucha:
        casos = [(Decimal("12.00"), True), (Decimal("2.00"), False)]
        for subida, debe in casos:
            m = _momento_ejemplo("subida_recibo", comercio="Fibra Hogar", importe_habitual=Decimal("30.00"),
                                 importe_actual=Decimal("30.00") + subida, subida_eur=subida,
                                 subida_pct=(subida / Decimal("30.00") * 100).quantize(Decimal("0.1")), serie_id="s1")
            prop = _proponer.construir(spec, m, None)
            if prop is not None:
                etiqueta = "acierto" if debe else "falso_positivo"
                aciertos += debe
                falsos += not debe
                avisos.append(AvisoPrueba(fecha=m.fecha, momento_id=m.id, mensaje=prop.mensaje_notificacion, etiqueta=etiqueta))
        controles.append(ControlPrueba(nombre="plantillas_renderizan", ok=bool(avisos)))
    informe = InformePrueba(avisos=avisos, aciertos=aciertos, falsos_positivos=falsos,
                            omitidos=0, controles=controles,
                            resumen=f"{len(avisos)} aviso(s) en el escenario de prueba, {falsos} falso(s)")
    _INFORMES[spec.id] = informe
    return informe


def aprobar(modulo_id: str, aprobado_por: str) -> Modulo:
    """Exige un informe aprobado y guarda el YAML en `datos_usuario/_modulos/` con estado `activo`.
    STUB: solo conoce los borradores creados en este proceso (o `recibo_al_alza`)."""
    borrador = _BORRADORES.get(modulo_id)
    if borrador is None and modulo_id == "recibo_al_alza":
        borrador = crear_borrador("")
    if borrador is None:
        raise ValueError(f"No hay borrador con id {modulo_id!r}.")
    informe = _INFORMES.get(modulo_id) or probar_en_seco(borrador, "prueba")
    if not informe.aprobado:
        raise ValueError("La prueba en seco no está aprobada: no se puede activar el módulo.")
    spec = ModuloSpec.model_validate({**borrador.spec, "estado": "activo", "aprobado_por": aprobado_por,
                                      "aprobado_en": datetime.now().isoformat(timespec="seconds")})
    registro.guardar_aprobado(spec)
    return Modulo.model_validate(spec.model_dump(mode="json"))
