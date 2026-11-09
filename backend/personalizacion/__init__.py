"""
Personalización de Meisam (nombre interno: copiloto). Firmas de docs/ARQUITECTURA.md §3.2.

Hecho (E6): `nuevo_modelo`, `decidir` (política `beta-jerarquica-v2`, en politica.py), `aprender`
(aprendizaje.py) y `registrar_decision` (abre el aviso para poder aprender de la respuesta).
Todas puras: no guardan nada; guarda el orquestador.
Stubs para mañana: `perfilar` (None), `ordenar_acciones` (sin cambios), `observar`,
`registrar_accion` y la parte de amigos de `registrar_decision`.
"""

from __future__ import annotations

from datetime import date, datetime

from ..plataforma.tipos import (
    Decision,
    Feedback,
    ModeloUsuario,
    Movimiento,
    MovimientoEnriquecido,
    PerfilUsuario,
    Propuesta,
    ResultadoAccion,
)
from . import edicion  # noqa: F401
from .aprendizaje import abrir_aviso
from .aprendizaje import aprender as _aprender
from .memoria import memoria_para_agente as _memoria_para_agente
from .politica import PARAMETROS, VERSION  # noqa: F401
from .politica import decidir as _decidir

POLITICA = VERSION


def nuevo_modelo(usuario_id: str) -> ModeloUsuario:
    """Modelo vacío v2: sin módulos ni consentimientos (se rellenan al activar) y en frío."""
    return ModeloUsuario(usuario_id=usuario_id, politica=VERSION)


def perfilar(
    historial: list[MovimientoEnriquecido], hoy: date, perfil_anterior: PerfilUsuario | None
) -> PerfilUsuario | None:
    """Pura. Con menos de 28 días de historial devuelve None (sin perfil). Stub: None."""
    return None


def ordenar_acciones(propuesta: Propuesta, modelo: ModeloUsuario) -> Propuesta:
    """Pura; solo reordena las acciones. Stub: sin cambios."""
    return propuesta


def decidir(propuesta: Propuesta, modelo: ModeloUsuario, ahora: datetime) -> Decision:
    """Pura y < 5 ms: reglas duras, Beta jerárquica y U = q·B − (1 − q), con motivos legibles."""
    return _decidir(propuesta, modelo, ahora)


def aprender(feedback: Feedback, modelo: ModeloUsuario) -> ModeloUsuario:
    """Pura: no guarda. Suma la respuesta a las claves del aviso abierto y regenera los hechos."""
    return _aprender(feedback, modelo)


def registrar_decision(modelo: ModeloUsuario, propuesta: Propuesta, decision: Decision) -> ModeloUsuario:
    """Pura. Abre el aviso (si no es `silenciar`) y lo cuenta para el tope diario.
    Pendiente: crear amigos desde `candidatos`."""
    return abrir_aviso(modelo, propuesta, decision)


def registrar_accion(modelo: ModeloUsuario, propuesta: Propuesta, resultado: ResultadoAccion) -> ModeloUsuario:
    """Suma a `elecciones`. Stub: sin cambios."""
    return modelo


def observar(modelo: ModeloUsuario, movimientos: list[Movimiento], hoy: date) -> ModeloUsuario:
    """Contactos y amigos. Stub: sin cambios."""
    return modelo


def memoria_para_agente(modelo: ModeloUsuario) -> str:
    """Solo hechos operativos; nunca ingresos, importes por categoría ni resumen_vida."""
    return _memoria_para_agente(modelo)
