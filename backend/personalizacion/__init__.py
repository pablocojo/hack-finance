"""
Personalización de Meisam (nombre interno: copiloto). Firmas de docs/ARQUITECTURA.md §3.2.

Hecho: `nuevo_modelo`, `decidir` (política `beta-jerarquica-v2`, en politica.py), `aprender`
(aprendizaje.py), `registrar_decision` (abre el aviso para poder aprender de la respuesta),
`perfilar` (perfil.py, U1) y `ordenar_acciones` + `registrar_accion` (orden_acciones.py, U1).
Todas puras: no guardan nada; guarda el orquestador.
`observar` (amigos.py, O7): contactos del día y saldo con cada amigo calculado desde los `Caso`.
Pendiente: crear amigos en `registrar_decision` (ya no hace falta: salen de los casos).
Curva de amigos (11 nov): `aprende_amigos` (lo que aprende de cada usuario y persona) y `escalera` (cómo preguntar).
"""

from __future__ import annotations

from datetime import date, datetime

from ..plataforma.tipos import (
    Caso,
    Decision,
    Feedback,
    ModeloUsuario,
    Movimiento,
    MovimientoEnriquecido,
    PerfilUsuario,
    Propuesta,
    ResultadoAccion,
)
from . import aprende_amigos, edicion, escalera  # noqa: F401  (curva de amigos: lo aprendido y la escalera)
from .amigos import observar as _observar
from .amigos import saldo_amigos as _saldo_amigos
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
    """Pura. Abre el aviso (si no es `silenciar`) y lo cuenta para el tope diario. Los amigos no se crean
    aquí: se calculan desde los casos (`observar`)."""
    return abrir_aviso(modelo, propuesta, decision)


def registrar_accion(modelo: ModeloUsuario, propuesta: Propuesta, resultado: ResultadoAccion) -> ModeloUsuario:
    """Pura. Si la acción salió bien, suma 1 a `elecciones` (por tipo de momento y en total)."""
    return _registrar_accion(modelo, propuesta, resultado)


def observar(modelo: ModeloUsuario, movimientos: list[Movimiento], hoy: date) -> ModeloUsuario:
    """Pura. Suma los Bizums y transferencias del día a `contactos` (solo claves, nunca conceptos)."""
    return _observar(modelo, movimientos, hoy)


def saldo_amigos(modelo: ModeloUsuario, casos: list[Caso], hoy: date) -> ModeloUsuario:
    """Pura. El saldo con cada amigo (`amigos`) se calcula desde los casos; `Amigo` no se estira."""
    return _saldo_amigos(modelo, casos, hoy)


def memoria_para_agente(modelo: ModeloUsuario) -> str:
    """Solo hechos operativos; nunca ingresos, importes por categoría ni resumen_vida."""
    return _memoria_para_agente(modelo)
