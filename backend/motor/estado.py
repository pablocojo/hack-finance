"""
Estado del motor por usuario (motor.md §2): movimientos vistos, claves emitidas, pruebas y comercios
pendientes de buscar. Vive en memoria; el orquestador lo guarda con `exportar`/`importar` (JSON puro).
El perfil NO se guarda aquí: es de la personalización y llega en cada `procesar`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from ..plataforma.tipos import Movimiento, MovimientoEnriquecido
from .normalizar import normalizar

VERSION_ESTADO = "motor-estado-1"
ESTADOS_PRUEBA = ("abierta", "cancelada", "cobrada", "caducada", "baja_guiada")


@dataclass
class EstadoMotor:
    usuario_id: str
    movimientos: dict[str, Movimiento] = field(default_factory=dict)      # por orden de llegada
    claves_emitidas: dict[str, str] = field(default_factory=dict)         # "tipo|clave" -> momento_id
    pruebas: list[dict] = field(default_factory=list)
    comercios_pendientes: list[str] = field(default_factory=list)
    tipos_pendientes: list[str] = field(default_factory=list)             # comercios sin tipo (pago_individual)
    ultimo_hoy: date | None = None
    _normalizados: dict[str, MovimientoEnriquecido] = field(default_factory=dict, repr=False)
    _orden: dict[str, int] = field(default_factory=dict, repr=False)

    def agregar(self, movimientos: list[Movimiento]) -> None:
        """Añade los que no estaban (el id es único y estable: reprocesar no duplica)."""
        for m in movimientos:
            if m.id not in self.movimientos:
                self._orden[m.id] = len(self._orden)
                self.movimientos[m.id] = m

    def normalizados_hasta(self, hoy: date) -> list[MovimientoEnriquecido]:
        """Único punto de corte del motor: solo lo que tiene fecha <= hoy, por fecha y orden de llegada."""
        visibles = [m for m in self.movimientos.values() if m.fecha <= hoy]
        visibles.sort(key=lambda m: (m.fecha, self._orden[m.id]))
        salida = []
        for m in visibles:
            if m.id not in self._normalizados:
                self._normalizados[m.id] = normalizar(m)
            salida.append(self._normalizados[m.id])
        return salida

    def a_dict(self) -> dict:
        return {
            "version": VERSION_ESTADO,
            "usuario_id": self.usuario_id,
            "movimientos": [m.model_dump(mode="json") for m in self.movimientos.values()],
            "claves_emitidas": dict(self.claves_emitidas),
            "pruebas": [dict(p) for p in self.pruebas],
            "comercios_pendientes": list(self.comercios_pendientes),
            "tipos_pendientes": list(self.tipos_pendientes),
            "ultimo_hoy": self.ultimo_hoy.isoformat() if self.ultimo_hoy else None,
        }

    @classmethod
    def desde_dict(cls, usuario_id: str, datos: dict) -> "EstadoMotor":
        estado = cls(usuario_id=usuario_id)
        estado.agregar([Movimiento.model_validate(m) for m in datos.get("movimientos", [])])
        estado.claves_emitidas = dict(datos.get("claves_emitidas", {}))
        estado.pruebas = [dict(p) for p in datos.get("pruebas", [])]
        estado.comercios_pendientes = list(datos.get("comercios_pendientes", []))
        estado.tipos_pendientes = list(datos.get("tipos_pendientes", []))
        ultimo = datos.get("ultimo_hoy")
        estado.ultimo_hoy = date.fromisoformat(ultimo) if ultimo else None
        return estado
