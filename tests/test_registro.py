from typing import Literal

import pytest

from backend.agente import registro
from backend.agente.registro import a_json, crear_herramienta, ejecutar


def ejemplo(importe: float, meses: int = 12, modo: Literal["a", "b"] = "a", etiquetas: list[str] | None = None,
            ctx=None) -> dict:
    """Calcula algo de ejemplo.

    Úsala en los tests.

    Args:
        importe: Importe en euros.
        meses: Número de meses,
            con una línea de continuación.
        modo: Modo de cálculo.
        etiquetas: Lista de etiquetas.
    """
    return {"importe": importe, "meses": meses, "ctx": ctx is not None}


def test_esquema_desde_tipos_y_docstring():
    herramienta = crear_herramienta(ejemplo)
    esquema = herramienta.esquema
    assert herramienta.descripcion.startswith("Calcula algo de ejemplo.")
    assert "Args" not in herramienta.descripcion
    assert esquema["required"] == ["importe"]
    assert esquema["properties"]["importe"]["type"] == "number"
    assert esquema["properties"]["meses"] == {
        "type": "integer", "description": "Número de meses, con una línea de continuación.", "default": 12}
    assert esquema["properties"]["modo"]["enum"] == ["a", "b"]
    assert esquema["properties"]["etiquetas"]["type"] == "array"
    assert "ctx" not in esquema["properties"] and herramienta.usa_ctx


def test_sin_docstring_falla():
    def sin_doc(x: int):
        return x

    with pytest.raises(ValueError):
        crear_herramienta(sin_doc)


def test_todas_las_herramientas_tienen_esquema_valido():
    disponibles = registro.disponibles()
    nombres = [h.nombre for h in disponibles]
    assert nombres == sorted(nombres)  # orden estable para la caché
    assert "precio_accion" not in nombres  # sin clave de Alpha Vantage no se ofrece
    for h in disponibles:
        definicion = h.definicion()
        assert definicion["input_schema"]["type"] == "object"
        assert len(definicion["description"]) > 20
        for propiedad in definicion["input_schema"]["properties"].values():
            assert "description" in propiedad, f"{h.nombre}: falta la descripción de un argumento"


def test_ejecutar_coacciona_tipos_ignora_extras_y_captura_errores(sesion_familia):
    texto, es_error, _ = ejecutar("calcular_prestamo",
                                  {"importe": "10000", "tin_anual": "6", "plazo_meses": "36", "inventado": 1})
    assert not es_error and '"cuota_mensual": 304.22' in texto
    texto, es_error, _ = ejecutar("calcular_prestamo", {"importe": -1, "tin_anual": 5, "plazo_meses": 12})
    assert es_error and "ValueError" in texto
    texto, es_error, _ = ejecutar("no_existe", {})
    assert es_error
    texto, es_error, _ = ejecutar("resumen_gastos", {"meses": 2}, ctx=sesion_familia,
                                  permitidas={"calcular_prestamo"})
    assert es_error  # no permitida para este agente


def test_a_json_recorta_resultados_enormes():
    texto = a_json({"x": "a" * 50_000})
    assert len(texto) < 21_000 and "recortado" in texto
