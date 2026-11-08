"""
Sesiones en memoria: movimientos, perfil del usuario, historial del chat y coste.

Es suficiente para el hackathon: si el servidor se reinicia, se pierden las conversaciones
(el perfil se guarda en datos_usuario/perfiles/ si GUARDAR_PERFILES está activo).
"""

from __future__ import annotations

import json
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .. import config
from .sinteticos import PERFILES, descripcion_perfil, generar_movimientos

CARPETA_PERFILES = config.RAIZ / "datos_usuario" / "perfiles"
MAX_SESIONES = 200


@dataclass
class Sesion:
    id: str
    movimientos: list[dict] = field(default_factory=list)
    perfil: dict = field(default_factory=dict)
    mensajes: list[dict] = field(default_factory=list)
    origen_datos: str = "sin datos"
    coste_usd: float = 0.0
    creada: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    # cerrojo protege los datos (lo usan las herramientas, que corren en otros hilos);
    # turno impide que dos preguntas de la misma sesión se respondan a la vez.
    cerrojo: threading.RLock = field(default_factory=threading.RLock, repr=False, compare=False)
    turno: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)

    def resumen_datos(self) -> dict:
        if not self.movimientos:
            return {"movimientos": 0, "origen": self.origen_datos}
        fechas = [m["fecha"] for m in self.movimientos]
        return {
            "movimientos": len(self.movimientos),
            "desde": min(fechas),
            "hasta": max(fechas),
            "origen": self.origen_datos,
            "sin_categoria": sum(1 for m in self.movimientos if not m.get("categoria")),
        }


class Almacen:
    def __init__(self, carpeta_perfiles: Path | None = CARPETA_PERFILES):
        self._sesiones: dict[str, Sesion] = {}
        self._cerrojo = threading.Lock()
        self._carpeta = carpeta_perfiles

    def crear(self, perfil_demo: str | None = None) -> Sesion:
        sesion = Sesion(id=uuid.uuid4().hex[:12])
        if perfil_demo:
            self.cargar_ejemplo(sesion, perfil_demo)
        with self._cerrojo:
            if len(self._sesiones) >= MAX_SESIONES:
                self._sesiones.pop(next(iter(self._sesiones)))
            self._sesiones[sesion.id] = sesion
        return sesion

    def obtener(self, sesion_id: str | None, *, crear: bool = True, perfil_demo: str | None = None) -> Sesion:
        with self._cerrojo:
            sesion = self._sesiones.get(sesion_id or "")
        if sesion is not None:
            return sesion
        if not crear:
            raise KeyError(f"No existe la sesión {sesion_id}")
        sesion = self.crear(perfil_demo)
        if sesion_id:  # conserva el id que pide el cliente y recupera su perfil guardado
            with self._cerrojo:
                self._sesiones.pop(sesion.id, None)
                sesion.id = sesion_id
                self._sesiones[sesion_id] = sesion
            sesion.perfil.update(self._leer_perfil(sesion_id))
        return sesion

    def cargar_ejemplo(self, sesion: Sesion, perfil_demo: str, meses: int = 6) -> None:
        if perfil_demo not in PERFILES:
            raise ValueError(f"Perfil de ejemplo desconocido: {perfil_demo}. Opciones: {sorted(PERFILES)}")
        with sesion.cerrojo:
            sesion.movimientos = generar_movimientos(perfil_demo, meses=meses)
            sesion.origen_datos = f"datos sintéticos del perfil {perfil_demo}: {descripcion_perfil(perfil_demo)}"

    def cargar_movimientos(self, sesion: Sesion, movimientos: list[dict], origen: str) -> None:
        with sesion.cerrojo:
            sesion.movimientos = movimientos
            sesion.origen_datos = origen

    def guardar_perfil(self, sesion: Sesion) -> None:
        if not (self._carpeta and config.ajustes().guardar_perfiles):
            return
        try:
            self._carpeta.mkdir(parents=True, exist_ok=True)
            ruta = self._carpeta / f"{sesion.id}.json"
            ruta.write_text(json.dumps(sesion.perfil, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            pass

    def _leer_perfil(self, sesion_id: str) -> dict:
        if not self._carpeta or not sesion_id.replace("-", "").isalnum():
            return {}
        ruta = self._carpeta / f"{sesion_id}.json"
        try:
            return json.loads(ruta.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def borrar(self, sesion_id: str) -> None:
        with self._cerrojo:
            self._sesiones.pop(sesion_id, None)


ALMACEN = Almacen()
