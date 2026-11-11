"""
A5 (curva de amigos): «Lo que he aprendido» para amigos y sitios. Ver (`amigos_aprendido` en `GET /aprendido`), editar,
borrar una persona o un sitio, y que borrar el contacto borre lo aprendido de esa persona. Sin red ni crédito.
"""

from __future__ import annotations

from datetime import date
from urllib.parse import quote

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from backend.api.main import app  # noqa: E402
from backend.personalizacion import aprende_amigos as A  # noqa: E402
from backend.personalizacion import edicion  # noqa: E402
from backend.personalizacion.amigos import borrar_contacto  # noqa: E402
from backend.plataforma import almacenamiento as alm  # noqa: E402
from backend.plataforma.tipos import AprendizajeAmigos, Contacto, HechoAprendido, ModeloUsuario  # noqa: E402
from tests.test_aprende_amigos import JUEVES, PALABRAS_DE_JUICIO, aprender, devolucion, visita  # noqa: E402
from tests.test_orquestador import UID, Falsos  # noqa: E402

http = TestClient(app)

CONTACTOS = {"RODRIGO P": Contacto(contraparte="RODRIGO P", nombre="Rodrigo P."),
             "PILAR R": Contacto(contraparte="PILAR R", nombre="Pilar R.")}


def modelo_con_amigos() -> ModeloUsuario:
    apr = aprender(AprendizajeAmigos(), [
        devolucion("b1", "RODRIGO P", 2), devolucion("b2", "RODRIGO P", 3),
        devolucion("c1", "PILAR R", 0, "efectivo"), devolucion("c2", "PILAR R", 1, "efectivo"),
        *[visita(f"v{i}", True, personas=["PILAR R", "RODRIGO P"], forma="iguales") for i in range(3)],
        *[visita(f"s{i}", False, comercio="CAFETERIA UNI", fecha=JUEVES) for i in range(3)],
    ])
    hecho = HechoAprendido(id="h-rodrigo", texto="Rodrigo P. suele tardar un poco", origen="chat",
                           creado=date(2026, 11, 11), contraparte="RODRIGO P")
    return ModeloUsuario(usuario_id="u", aprendizaje=apr, contactos=dict(CONTACTOS), hechos_aprendidos=[hecho])


# --- Puro ---------------------------------------------------------------------------------------------------------

def test_ninguna_frase_generada_valora_a_nadie():
    modelos = [modelo_con_amigos()]
    for dias in range(0, 11):                                   # todos los plazos, canales y hábitos posibles
        for canal in ("bizum", "efectivo", "transferencia", "invitacion"):
            apr = aprender(AprendizajeAmigos(), [
                devolucion(f"a{dias}{canal}{i}", "ANA G", dias, canal, tras_pedir=bool(i % 2)) for i in range(4)])
            modelos.append(ModeloUsuario(usuario_id="u", aprendizaje=apr))
    editado = edicion.corregir_persona(modelo_con_amigos(), "Rodrigo P.", "retraso_dias", 5)
    modelos.append(edicion.corregir_persona(editado, "Pilar R.", "canal", "invitacion"))
    frases = [f for m in modelos for f in edicion.frases_aprendido_amigos(m)]
    assert len(frases) > 40
    for f in frases:
        assert not any(p in f["texto"].lower() for p in PALABRAS_DE_JUICIO), f["texto"]
        assert f["tipo"] in ("persona", "sitio") and f["clave"] and f["campo"].endswith(f["clave"])


def test_frases_por_persona_y_sitio_con_su_clave():
    por_clave = {f["clave"]: f for f in edicion.frases_aprendido_amigos(modelo_con_amigos())}
    assert por_clave["RODRIGO P"]["texto"].startswith("Rodrigo P. suele devolvértelo a los 2 o 3 días")
    assert por_clave["RODRIGO P"]["tipo"] == "persona" and por_clave["RODRIGO P"]["editable"]
    assert por_clave["comercio:LA TASCA"]["tipo"] == "sitio" and not por_clave["comercio:LA TASCA"]["editable"]
    assert "Pilar R." in por_clave["comercio:LA TASCA"]["texto"] or "Rodrigo P." in por_clave["comercio:LA TASCA"]["texto"]


def test_borrar_persona_cambia_la_siguiente_decision():
    m = modelo_con_amigos()
    assert A.retraso_persona(m.aprendizaje, "RODRIGO P") == (3, "persona")
    sin = edicion.olvidar_persona(m, "Rodrigo P.")               # por el nombre visible
    assert A.retraso_persona(sin.aprendizaje, "RODRIGO P")[1] != "persona"
    assert "RODRIGO P" not in sin.aprendizaje.personas and sin.hechos_aprendidos == []
    assert "RODRIGO P" in m.aprendizaje.personas                 # pura
    with pytest.raises(edicion.NoExiste):
        edicion.olvidar_persona(sin, "Nadie X.")


def test_borrar_sitio_y_editar_persona():
    m = modelo_con_amigos()
    sin = edicion.olvidar_sitio(m, "sitios:comercio:CAFETERIA UNI")
    assert "CAFETERIA UNI" not in sin.aprendizaje.por_comercio and "LA TASCA" in sin.aprendizaje.por_comercio
    with pytest.raises(edicion.NoExiste):
        edicion.olvidar_sitio(sin, "comercio:CAFETERIA UNI")
    m = edicion.corregir_persona(m, "RODRIGO P", "retraso_dias", 7)
    assert A.retraso_persona(m.aprendizaje, "RODRIGO P") == (7, "persona")
    for campo, valor in (("retraso_dias", 99), ("canal", "paypal"), ("puntuacion", 3)):
        with pytest.raises(ValueError):
            edicion.corregir_persona(m, "RODRIGO P", campo, valor)
    with pytest.raises(edicion.NoExiste):
        edicion.corregir_persona(m, "NADIE X", "retraso_dias", 2)


def test_borrar_el_contacto_borra_habito_grupos_y_hechos():
    m = borrar_contacto(modelo_con_amigos(), "RODRIGO P")
    assert "RODRIGO P" not in m.contactos and "RODRIGO P" not in m.aprendizaje.personas
    assert all("RODRIGO P" not in g.miembros for a in m.aprendizaje.por_comercio.values() for g in a.grupos)
    assert m.hechos_aprendidos == []
    assert "PILAR R" in m.aprendizaje.personas and "PILAR R" in m.contactos      # los demás no se tocan


# --- HTTP ---------------------------------------------------------------------------------------------------------

@pytest.fixture
def activo(monkeypatch):
    monkeypatch.delenv("DEMO_KEY", raising=False)
    Falsos().montar(monkeypatch)
    assert http.post("/demo/cargar", json={"escenario_id": "demo-test"}).status_code == 200
    r = http.post(f"/usuarios/{UID}/activar", json={"modulos_activos": ["gasto_compartido"],
                                                    "consentimientos": {"copiloto": True}})
    assert r.status_code == 200
    base = alm.cargar(UID, "modelo", ModeloUsuario)
    alm.guardar(UID, "modelo", base.model_copy(update={
        "aprendizaje": modelo_con_amigos().aprendizaje, "contactos": dict(CONTACTOS),
        "hechos_aprendidos": [*base.hechos_aprendidos, *modelo_con_amigos().hechos_aprendidos]}))


def _ruta(*partes: str) -> str:
    return "/".join([f"/usuarios/{UID}/aprendido", *[quote(p, safe="") for p in partes]])


def _claves(r) -> set[str]:
    return {f["clave"] for f in r.json()["amigos_aprendido"]}


def test_ver_lo_aprendido_de_amigos_y_sitios(activo):
    r = http.get(_ruta())
    assert r.status_code == 200
    assert {"RODRIGO P", "PILAR R", "comercio:LA TASCA", "comercio:CAFETERIA UNI"} <= _claves(r)
    assert {"hechos", "silencios", "amigos", "usar_perfil"} <= set(r.json())     # lo de siempre sigue ahí


def test_editar_una_persona(activo):
    r = http.patch(_ruta("amigos", "Rodrigo P."), json={"campo": "retraso_dias", "valor": 5})
    assert r.status_code == 200
    texto = next(f["texto"] for f in r.json()["amigos_aprendido"] if f["clave"] == "RODRIGO P")
    assert "5 días (me lo dijiste tú)" in texto
    assert A.retraso_persona(alm.cargar(UID, "modelo", ModeloUsuario).aprendizaje, "RODRIGO P") == (5, "persona")
    r = http.patch(_ruta("amigos", "PILAR R"), json={"campo": "canal", "valor": "transferencia"})
    assert r.status_code == 200
    assert http.patch(_ruta("amigos", "PILAR R"), json={"campo": "canal", "valor": "paypal"}).status_code == 400
    assert http.patch(_ruta("amigos", "PILAR R"), json={"campo": "puntuacion", "valor": 1}).status_code == 400
    assert http.patch(_ruta("amigos", "NADIE X"), json={"campo": "canal", "valor": "bizum"}).status_code == 404
    eventos = [e for e in alm.leer_auditoria(UID) if e["evento"] == "amigo_aprendido_editado"]
    assert len(eventos) == 2 and all("valor" not in e for e in eventos)         # se audita el campo, no el valor


def test_borrar_una_persona_y_un_sitio(activo):
    r = http.delete(_ruta("amigos", "RODRIGO P"))
    assert r.status_code == 200 and "RODRIGO P" not in _claves(r) and "PILAR R" in _claves(r)
    assert "RODRIGO P" not in alm.cargar(UID, "modelo", ModeloUsuario).aprendizaje.personas
    assert http.delete(_ruta("amigos", "Rodrigo P.")).status_code == 200          # sigue en la agenda: idempotente
    assert http.delete(_ruta("amigos", "NADIE X")).status_code == 404
    r = http.delete(_ruta("sitios", "comercio:CAFETERIA UNI"))
    assert r.status_code == 200 and "comercio:CAFETERIA UNI" not in _claves(r)
    assert http.delete(_ruta("sitios", "comercio:CAFETERIA UNI")).status_code == 404
    r = http.delete(_ruta("sitios", "tipo:restaurante|finde"))
    assert r.status_code == 200 and "tipo:restaurante|finde" not in _claves(r)


def test_borrar_el_contacto_o_el_amigo_borra_lo_aprendido(activo):
    r = http.delete(f"/usuarios/{UID}/contactos/{quote('Rodrigo P.', safe='')}")
    assert r.status_code == 200
    m = alm.cargar(UID, "modelo", ModeloUsuario)
    assert "RODRIGO P" not in m.contactos and "RODRIGO P" not in m.aprendizaje.personas
    assert all(h.contraparte != "RODRIGO P" for h in m.hechos_aprendidos)
    # Por la ruta de amigos: sin saldo pendiente, pero con algo aprendido, también lo borra.
    r = http.delete(f"/usuarios/{UID}/amigos/{quote('Pilar R.', safe='')}")
    assert r.status_code == 200
    m = alm.cargar(UID, "modelo", ModeloUsuario)
    assert "PILAR R" not in m.aprendizaje.personas
    assert all("PILAR R" not in g.miembros for a in m.aprendizaje.por_comercio.values() for g in a.grupos)
    assert http.delete(f"/usuarios/{UID}/amigos/{quote('Nadie X.', safe='')}").status_code == 404
