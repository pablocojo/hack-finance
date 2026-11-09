"""
Configuración común de los tests. Ningún test gasta crédito: el cliente de Claude es siempre
uno simulado (backend/claude_falso.py) con respuestas guionizadas.
"""

from __future__ import annotations

from datetime import date

import pytest

from backend import claude_client
from backend.claude_falso import ClienteFalso
from backend.datos.almacen import Almacen, Sesion
from backend.datos.sinteticos import generar_movimientos

HOY = date(2026, 11, 7)  # fecha fija para que los datos sintéticos no cambien entre ejecuciones


@pytest.fixture(autouse=True)
def entorno_seguro(monkeypatch, tmp_path):
    monkeypatch.setenv("GUARDAR_PERFILES", "0")
    monkeypatch.setenv("MODO_DEMO", "off")
    monkeypatch.setenv("REVISOR_CUMPLIMIENTO", "0")
    monkeypatch.setenv("BUSQUEDA_WEB", "off")
    monkeypatch.setenv("DATOS_USUARIO_DIR", str(tmp_path / "datos_usuario"))
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    monkeypatch.delenv("ELEVENLABS_AGENT_ID", raising=False)
    monkeypatch.delenv("ALPHA_VANTAGE_API_KEY", raising=False)
    claude_client.usar_cliente(ClienteFalso(por_defecto="(cliente simulado)"))
    yield
    claude_client.olvidar_clientes()


@pytest.fixture
def falso():
    """falso([respuesta(...), ...]) instala un cliente simulado con ese guion y lo devuelve."""

    def crear(guion=None, **opciones) -> ClienteFalso:
        cliente = ClienteFalso(guion, **opciones)
        claude_client.usar_cliente(cliente)
        return cliente

    return crear


@pytest.fixture
def sesion_familia() -> Sesion:
    sesion = Sesion(id="test-familia")
    sesion.movimientos = generar_movimientos("familia", meses=6, semilla=42, hasta=HOY)
    sesion.origen_datos = "datos sintéticos de test"
    return sesion


@pytest.fixture
def almacen() -> Almacen:
    return Almacen(carpeta_perfiles=None)
