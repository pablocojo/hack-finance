import pytest

from backend.agente import registro
from backend.herramientas import mercados


@pytest.fixture(autouse=True)
def cache_temporal(monkeypatch, tmp_path):
    monkeypatch.setattr(mercados, "CACHE_DIVISAS", tmp_path / "divisas.json")


def test_convertir_divisa_y_cache(monkeypatch):
    llamadas = []

    def falso_get(url, timeout=8.0):
        llamadas.append(url)
        return {"amount": 1.0, "base": "EUR", "date": "2026-11-06", "rates": {"USD": 1.1}}

    monkeypatch.setattr(mercados, "obtener_json", falso_get)
    r = mercados.convertir_divisa(250, "eur", "USD")
    assert r["importe_convertido"] == 275.0 and r["fecha_tipo"] == "2026-11-06"
    assert "from=EUR" in llamadas[0] and "to=USD" in llamadas[0]
    mercados.convertir_divisa(10, "EUR", "USD")
    assert len(llamadas) == 1  # la segunda sale de la caché


def test_sin_red_usa_respaldo(monkeypatch, tmp_path):
    def sin_red(url, timeout=8.0):
        raise OSError("sin conexión")

    respaldo = tmp_path / "respaldo.json"
    respaldo.write_text('{"base": "EUR", "date": "2026-11-06", "rates": {"USD": 1.2, "GBP": 0.8}}')
    monkeypatch.setattr(mercados, "obtener_json", sin_red)
    monkeypatch.setattr(mercados, "RESPALDO", respaldo)
    r = mercados.convertir_divisa(100, "USD", "GBP")
    assert r["importe_convertido"] == pytest.approx(66.67, abs=0.01)
    assert "respaldo" in r["fuente"]


def test_divisa_no_valida():
    with pytest.raises(ValueError):
        mercados.convertir_divisa(1, "EURO", "USD")


def test_precio_accion_solo_con_clave(monkeypatch):
    assert "precio_accion" not in [h.nombre for h in registro.disponibles()]
    monkeypatch.setenv("ALPHA_VANTAGE_API_KEY", "demo")
    assert "precio_accion" in [h.nombre for h in registro.disponibles()]

    monkeypatch.setattr(mercados, "obtener_json", lambda url, timeout=8.0: {
        "Global Quote": {"01. symbol": "IBM", "05. price": "250.10", "09. change": "1.2",
                         "10. change percent": "0.48%", "07. latest trading day": "2026-11-06"}})
    r = mercados.precio_accion("ibm")
    assert r["precio"] == 250.10 and "no es una recomendación" in r["aviso"]

    mercados._cotizaciones.clear()
    monkeypatch.setattr(mercados, "obtener_json", lambda url, timeout=8.0: {"Information": "limit"})
    with pytest.raises(ValueError, match="límite"):
        mercados.precio_accion("MSFT")
