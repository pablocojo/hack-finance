"""Persistencia por usuario: JSON exacto, escritura atómica, candado y auditoría."""

from __future__ import annotations

import os
import threading
from datetime import date
from decimal import Decimal

import pytest

from backend import config
from backend.plataforma import almacenamiento
from backend.plataforma.tipos import ModeloUsuario, Movimiento


def test_config_usa_directorio_temporal_y_sin_busqueda_web(tmp_path):
    ajustes = config.ajustes()
    assert ajustes.datos_usuario_dir == tmp_path / "datos_usuario"
    assert ajustes.busqueda_web is False and ajustes.modo_demo == "off"


def test_modo_demo_invalido_cuenta_como_off(monkeypatch):
    monkeypatch.setenv("MODO_DEMO", "grabar")
    assert config.ajustes().modo_demo == "grabar"
    monkeypatch.setenv("MODO_DEMO", "loquesea")
    assert config.ajustes().modo_demo == "off"


def test_guardar_y_cargar_modelo_exacto(tmp_path):
    modelo = ModeloUsuario(usuario_id="lucia", elecciones={"a:recordar": 1})
    ruta = almacenamiento.guardar("lucia", "modelo", modelo)
    assert ruta == tmp_path / "datos_usuario" / "lucia" / "modelo.json"
    assert almacenamiento.cargar("lucia", "modelo", ModeloUsuario) == modelo
    assert almacenamiento.cargar("lucia", "no_existe", defecto="vacío") == "vacío"


def test_dinero_se_guarda_como_cadena_y_vuelve_exacto():
    movs = [Movimiento(id="a", fecha=date(2026, 11, 6), concepto="x", importe=Decimal("-120.00")),
            Movimiento(id="b", fecha=date(2026, 11, 7), concepto="y", importe=Decimal("24.05"))]
    ruta = almacenamiento.guardar("lucia", "movimientos", movs)
    assert '"importe": "-120.00"' in ruta.read_text(encoding="utf-8")
    vuelta = almacenamiento.cargar("lucia", "movimientos", list[Movimiento])
    assert [m.importe for m in vuelta] == [Decimal("-120.00"), Decimal("24.05")]
    assert almacenamiento.cargar("lucia", "movimientos")[1]["importe"] == "24.05"


def test_escritura_atomica_sin_restos_y_sin_corromper_si_falla(monkeypatch):
    almacenamiento.guardar("lucia", "estado", {"v": 1})
    carpeta = almacenamiento.carpeta_usuario("lucia")

    def falla(origen, destino):
        raise OSError("disco lleno")

    with monkeypatch.context() as m:
        m.setattr(os, "replace", falla)
        with pytest.raises(OSError):
            almacenamiento.guardar("lucia", "estado", {"v": 2})
    assert almacenamiento.cargar("lucia", "estado") == {"v": 1}
    assert [p.name for p in carpeta.iterdir()] == ["estado.json"]  # sin temporales


def test_escritura_usa_os_replace(monkeypatch):
    llamadas = []
    real = os.replace
    monkeypatch.setattr(os, "replace", lambda a, b: (llamadas.append((a, b)), real(a, b))[1])
    almacenamiento.guardar("lucia", "x", {"a": 1})
    assert len(llamadas) == 1 and str(llamadas[0][1]).endswith("x.json")


def test_candado_por_usuario_serializa_y_es_reentrante():
    assert almacenamiento.candado("lucia") is almacenamiento.candado("lucia")
    assert almacenamiento.candado("lucia") is not almacenamiento.candado("pablo")
    almacenamiento.guardar("lucia", "contador", {"n": 0})

    def sumar():
        for _ in range(25):
            with almacenamiento.candado("lucia"):
                with almacenamiento.candado("lucia"):  # reentrante
                    n = almacenamiento.cargar("lucia", "contador")["n"]
                    almacenamiento.guardar("lucia", "contador", {"n": n + 1})

    hilos = [threading.Thread(target=sumar) for _ in range(4)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    assert almacenamiento.cargar("lucia", "contador")["n"] == 100


@pytest.mark.parametrize("malo", ["../fuera", "a/b", "", ".oculto", "a b", "x" * 80])
def test_usuario_id_no_valido_se_rechaza(malo):
    with pytest.raises(ValueError):
        almacenamiento.guardar(malo, "modelo", {})


def test_nombre_de_archivo_no_valido():
    with pytest.raises(ValueError):
        almacenamiento.guardar("lucia", "../modelo", {})


def test_auditoria_jsonl_enmascara_y_conserva_orden():
    almacenamiento.anadir_auditoria("lucia", {"evento": "preparar", "nota": "mail ana@example.com", "importe": Decimal("24")})
    almacenamiento.anadir_auditoria("lucia", {"evento": "ejecutar"})
    registros = almacenamiento.leer_auditoria("lucia")
    assert [r["evento"] for r in registros] == ["preparar", "ejecutar"]
    assert "ana@example.com" not in registros[0]["nota"] and registros[0]["importe"] == "24"
    assert "ts" in registros[0]
    assert almacenamiento.leer_auditoria("otro") == []


def test_carpetas_del_sistema_y_borrado():
    almacenamiento.guardar("_cache", "comercios_web", {"x": 1})
    almacenamiento.guardar("lucia", "modelo", {})
    almacenamiento.borrar_usuario("lucia")
    assert not almacenamiento.existe("lucia", "modelo")
    assert almacenamiento.existe("_cache", "comercios_web")
