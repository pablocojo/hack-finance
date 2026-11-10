"""`acciones/enlaces.py`: validación de `url_baja`, filtro de `pasos_baja` y `detalle_baja` (D1). Sin red."""

from __future__ import annotations

import socket
from pathlib import Path

import pytest

from backend.acciones import enlaces
from backend.plataforma.tipos import InfoComercio


@pytest.fixture(autouse=True)
def sin_internet(monkeypatch):
    def prohibido(*args, **kwargs):
        raise AssertionError("Un test ha intentado salir a internet.")

    monkeypatch.setattr(socket.socket, "connect", prohibido)
    monkeypatch.setattr(socket, "create_connection", prohibido)


OK = "https://streamflix.example/cuenta/baja"


@pytest.mark.parametrize("url", [
    "http://streamflix.example/baja",
    "javascript:alert(1)",
    "JAVASCRIPT:alert(1)",
    "data:text/html,<b>x</b>",
    "ftp://streamflix.example/baja",
    "//streamflix.example/baja",
    "https://192.168.1.10/baja",
    "https://[::1]/baja",
    "https://2130706433/baja",
    "https://127.1/baja",
    "https://0x7f.0.0.1/baja",
    "https://xn--strmflix-9wa.example/baja",
    "https://www.XN--80ak6aa92e.com/baja",
    "https://usuario:clave@streamflix.example/baja",
    "https://streamflix.example@malo.example/baja",
    "https://localhost/baja",
    "https://streamflix.example:8443/baja",
    "https://streamflíx.example/baja",
    "https://streamflix.example/baja con espacio",
    "https://streamflix.example/" + "a" * 200,
    "",
    None,
])
def test_url_mala_se_omite(url):
    assert enlaces.validar_url_baja(url, "catalogo") is None


def test_url_buena_del_catalogo_pasa_y_el_puerto_443_tambien():
    assert enlaces.validar_url_baja(OK, "catalogo") == OK
    assert enlaces.validar_url_baja("https://streamflix.example:443/baja", "catalogo")


def test_origen_desconocido_no_trae_enlace():
    assert enlaces.validar_url_baja(OK, "desconocido") is None


def test_con_origen_web_el_host_debe_estar_en_las_fuentes():
    f = ["https://www.streamflix.example/ayuda/cancelar"]
    assert enlaces.validar_url_baja(OK, "web", f) == OK
    assert enlaces.validar_url_baja("https://ayuda.streamflix.example/baja", "web", f)
    assert enlaces.validar_url_baja("https://streamflix-baja.example/baja", "web", f) is None
    assert enlaces.validar_url_baja("https://streamflix.example.malo.com/baja", "web", f) is None
    assert enlaces.validar_url_baja(OK, "web", []) is None
    assert enlaces.validar_url_baja(OK, "web", ["Catálogo de la demo"]) is None


BUENOS = [
    "Entra en tu cuenta de Streamflix.",
    "Abre el apartado Cuenta y después Membresía.",
    "Pulsa Cancelar suscripción y confirma.",
    "Guarda el aviso de confirmación que te envíen.",
]


def test_pasos_buenos_pasan_tal_cual():
    assert enlaces.filtrar_pasos(BUENOS, OK) == BUENOS


@pytest.mark.parametrize("paso", [
    "Llama al 912 345 678 para cancelar.",
    "Llama al +34 612345678.",
    "Ingresa en ES91 2100 0418 4502 0005 1332 el importe.",
    "Escribe a bajas@streamflix.example con tu nombre.",
    "Ve a https://otro.example/baja y pulsa Cancelar.",
    "Entra en www.streamflix-baja.com.",
    "Entra en streamflix-baja.com y cancela.",
    "Transfiere 1 € para verificar tu cuenta.",
    "Paga la penalización en la web.",
    "Envía un Bizum al comercio.",
    "Introduce tu tarjeta para confirmar la baja.",
    "Introduce los datos de tu tarjeta de crédito.",
    "x" * 201,
    "",
    "   ",
    42,
])
def test_pasos_peligrosos_se_descartan(paso):
    assert enlaces.filtrar_pasos([paso], OK) == []


def test_un_paso_puede_citar_la_url_de_baja_pero_no_otra():
    assert enlaces.filtrar_pasos([f"Entra en {OK} y pulsa Cancelar."], OK) == [f"Entra en {OK} y pulsa Cancelar."]
    assert enlaces.filtrar_pasos([f"Entra en {OK} y pulsa Cancelar."], None) == []


def test_maximo_cinco_pasos_y_texto_plano():
    seis = [f"Paso número {i} de la baja." for i in range(8)]
    assert len(enlaces.filtrar_pasos(seis)) == 5
    [p] = enlaces.filtrar_pasos(["Pulsa <b>Cancelar</b> {datos.x} \"ya\"\n ahora."])
    assert not any(c in p for c in "<>{}\"\n")


def info(**kw) -> InfoComercio:
    base = dict(nombre="STREAMFLIX", tipo="streaming", es_suscripcion=True, url_baja=OK, pasos_baja=BUENOS,
                fuentes=["Catálogo de la demo"], origen="catalogo")
    base.update(kw)
    return InfoComercio(**base)


def test_detalle_del_catalogo_trae_enlace_y_pasos():
    d = enlaces.detalle_desde_info(info(), "Streamflix", True)
    assert d.url_baja == OK and d.url_es_enlace and d.pasos == BUENOS
    assert d.bloquea_cobros and d.canal == "tarjeta" and d.fuente == "catalogo"


def test_detalle_web_va_como_texto_sin_enlace():
    web = info(origen="web", fuentes=["https://streamflix.example/ayuda"])
    d = enlaces.detalle_desde_info(web, "Streamflix", False)
    assert d.url_baja == OK and d.url_es_enlace is False and d.fuente == "web"
    assert enlaces.TEXTO_URL_WEB == "Compruébalo en la web oficial"


def test_detalle_web_con_host_ajeno_omite_la_url_y_conserva_los_pasos_buenos():
    web = info(origen="web", url_baja="https://otro.example/baja", fuentes=["https://streamflix.example/ayuda"])
    d = enlaces.detalle_desde_info(web, "Streamflix", False)
    assert d.url_baja is None and d.url_es_enlace is False and d.pasos == BUENOS


def test_comercio_desconocido_dice_que_busque_en_la_web_oficial():
    d = enlaces.detalle_desde_info(None, "Comercio <b>Raro</b>", False)
    assert d.url_baja is None and d.fuente == "desconocido"
    assert d.pasos == ["Busca la baja en la web oficial de Comercio bRaro/b."]


def test_detalle_baja_lee_el_catalogo_de_comercios_sin_red():
    d = enlaces.detalle_baja("Streamflix", True)
    assert d.url_baja == "https://streamflix.example/cuenta/baja" and d.url_es_enlace and len(d.pasos) == 4
    assert enlaces.host_para_auditoria(d) == "streamflix.example"


def test_enlaces_no_importa_ninguna_libreria_de_red():
    fuente = Path(enlaces.__file__).read_text(encoding="utf-8")
    for prohibido in ("requests", "httpx", "urllib.request", "http.client", "aiohttp", "socket", "urlopen"):
        assert prohibido not in fuente
