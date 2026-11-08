import pytest

from backend.herramientas.perfil import guardar_preferencia, leer_perfil


def test_guardar_y_leer(sesion_familia):
    r = guardar_preferencia("Objetivo ahorro", "6.000 € para junio", ctx=sesion_familia)
    assert r["guardado"] == {"objetivo_ahorro": "6.000 € para junio"}
    assert leer_perfil(ctx=sesion_familia)["perfil"]["objetivo_ahorro"] == "6.000 € para junio"


def test_no_guarda_datos_sensibles(sesion_familia):
    with pytest.raises(ValueError):
        guardar_preferencia("iban", "ES91...", ctx=sesion_familia)
    r = guardar_preferencia("nota", "mi email es ana@correo.es", ctx=sesion_familia)
    assert r["guardado"]["nota"] == "mi email es [EMAIL]"
