from backend.agente import demo, servicio
from backend.claude_falso import respuesta, texto


def test_grabar_y_reproducir(sesion_familia, falso, monkeypatch, tmp_path):
    monkeypatch.setattr(demo, "CARPETA", tmp_path)
    monkeypatch.setenv("MODO_DEMO", "grabar")
    falso([respuesta(texto("Respuesta grabada de verdad."))])
    original = servicio.conversar(sesion_familia, "¿Cuánto gasto al mes?")
    assert original["texto"] == "Respuesta grabada de verdad."
    assert demo.grabadas() == ["¿Cuánto gasto al mes?"]

    monkeypatch.setenv("MODO_DEMO", "reproducir")
    cliente = falso([])  # si llamase a la API, respondería otra cosa
    eventos = []
    reproducido = servicio.conversar(sesion_familia, "cuanto gasto al mes", al_evento=lambda t, d: eventos.append(t))
    assert reproducido["texto"] == "Respuesta grabada de verdad." and reproducido["reproducido"]
    assert reproducido["coste_usd"] == 0 and not cliente.peticiones
    assert eventos[-1] == "fin" and "texto" in eventos


def test_reproducir_sin_grabacion_ni_clave(sesion_familia, monkeypatch, tmp_path):
    monkeypatch.setattr(demo, "CARPETA", tmp_path)
    monkeypatch.setenv("MODO_DEMO", "reproducir")
    for nombre in ("ANTHROPIC_API_KEY_PRODUCTO", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(nombre, raising=False)
    resultado = servicio.conversar(sesion_familia, "pregunta nueva")
    assert resultado["texto"] == servicio.SIN_GRABACION


def test_clave_ignora_mayusculas_tildes_y_signos():
    assert demo.clave("¿Cuánto GASTO al mes?") == demo.clave("cuanto gasto al mes")
