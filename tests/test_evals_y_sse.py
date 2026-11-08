import json

from backend.api.sse import estado_http, evento_sse, mensaje_error
from backend.claude_client import SinClaveError
from evals.ejecutar import cargar_casos, contiene_cifra, evaluar, numeros_en


def test_casos_bien_formados():
    casos = cargar_casos()
    assert len(casos) >= 15
    for caso in casos:
        assert caso["pregunta"] and caso["id"]
        assert caso.get("perfil") in (None, "estudiante", "familia", "autonomo")


def test_numeros_en_espanol_e_ingles():
    assert numeros_en("Pagarás 304,22 € (TAE 6,17 %), total 10.951,88 €; en inglés 1234.56") == [
        304.22, 6.17, 10951.88, 1234.56]
    assert contiene_cifra("unos 43.234 €", 43233.75)
    assert not contiene_cifra("unos 40.000 €", 43233.75)


def test_evaluar_con_cliente_simulado():
    caso = next(c for c in cargar_casos() if c["id"] == "prestamo-cuota-tae")
    resultado = evaluar(caso, modelo=None, revisor=False, uso="evals")
    assert resultado["ok"] is False  # el cliente simulado no llama a herramientas
    tipos = {c["tipo"] for c in resultado["comprobaciones"]}
    assert {"herramienta", "cifra"} <= tipos


def test_formato_sse_y_errores():
    texto = evento_sse("texto", {"texto": "hola\nadiós"})
    assert texto.startswith("event: texto\ndata: ") and texto.endswith("\n\n")
    assert json.loads(texto.split("data: ", 1)[1]) == {"texto": "hola\nadiós"}
    assert "ANTHROPIC_API_KEY_PRODUCTO" in mensaje_error(SinClaveError("Falta ANTHROPIC_API_KEY_PRODUCTO"))
    assert estado_http(SinClaveError("x")) == 503
    assert "saldo" in mensaje_error(RuntimeError("Your credit balance is too low"))


def test_arnes_de_evals_en_un_proceso_nuevo():
    """El arnés completo funciona sin API (--simulado) en un proceso limpio."""
    import subprocess
    import sys
    from pathlib import Path

    raiz = Path(__file__).resolve().parent.parent
    salida = subprocess.run([sys.executable, "evals/ejecutar.py", "--simulado", "--paralelo", "2"],
                            cwd=raiz, capture_output=True, text=True, timeout=120)
    assert "Aprobados:" in salida.stdout, salida.stderr[-2000:]
