"""
Personalización de Meisam (nombre interno: copiloto). Firmas de docs/ARQUITECTURA.md §3.2.

Hecho: `nuevo_modelo`, `decidir` (política `beta-jerarquica-v2`, en politica.py), `aprender`
(aprendizaje.py), `registrar_decision` (abre el aviso para poder aprender de la respuesta),
`perfilar` (perfil.py, U1) y `ordenar_acciones` + `registrar_accion` (orden_acciones.py, U1).
Todas puras: no guardan nada; guarda el orquestador.
Stubs: `observar` y la parte de amigos de `registrar_decision`.
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
from .orden_acciones import ordenar_acciones as _ordenar_acciones
from .orden_acciones import registrar_accion as _registrar_accion
from .perfil import perfilar as _perfilar
from .politica import PARAMETROS, VERSION  # noqa: F401
from .politica import decidir as _decidir

POLITICA = VERSION


def nuevo_modelo(usuario_id: str) -> ModeloUsuario:
    """Modelo vacío v2: sin módulos ni consentimientos (se rellenan al activar) y en frío."""
    return ModeloUsuario(usuario_id=usuario_id, politica=VERSION)


def perfilar(
    historial: list[MovimientoEnriquecido], hoy: date, perfil_anterior: PerfilUsuario | None
) -> PerfilUsuario | None:
    """Pura. Con menos de 28 días de historial devuelve None (sin perfil). Nunca mira el futuro y
    respeta `campos_fijados` y `campos_borrados` del perfil anterior."""
    return _perfilar(historial, hoy, perfil_anterior)


def ordenar_acciones(propuesta: Propuesta, modelo: ModeloUsuario) -> Propuesta:
    """Pura; solo reordena las acciones (primero la que sueles elegir en ese tipo de momento)."""
    return _ordenar_acciones(propuesta, modelo)


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
    """Pura. Si la acción salió bien, suma 1 a `elecciones` (por tipo de momento y en total)."""
    return _registrar_accion(modelo, propuesta, resultado)


def observar(modelo: ModeloUsuario, movimientos: list[Movimiento], hoy: date) -> ModeloUsuario:
    """Contactos y amigos. Stub: sin cambios."""
    return modelo


def memoria_para_agente(modelo: ModeloUsuario) -> str:
    """Solo hechos operativos; nunca ingresos, importes por categoría ni resumen_vida."""
    return _memoria_para_agente(modelo)
