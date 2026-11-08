from backend.agente.nucleo import Agente, elegir_modelo, recortar_historial
from backend.claude_falso import herramienta, pensamiento, respuesta, respuesta_json, texto


def test_bucle_con_herramientas_en_paralelo(sesion_familia, falso):
    cliente = falso([
        respuesta(pensamiento(), texto("Miro tus datos."),
                  herramienta("resumen_gastos", {"meses": 3}), herramienta("gastos_recurrentes", {})),
        respuesta(texto("Tu mayor gasto es la vivienda.")),
    ])
    eventos = []
    r = Agente(revisor=False).responder(sesion_familia, "¿En qué gasto más?",
                                        al_evento=lambda tipo, datos: eventos.append(tipo))
    assert r.texto.endswith("Tu mayor gasto es la vivienda.")
    assert r.vueltas == 2 and r.herramientas == ["resumen_gastos", "gastos_recurrentes"]
    assert r.coste_usd > 0 and r.tokens["entrada"] > 0
    tipos = [t for t in eventos if t != "texto"]
    assert tipos == ["herramienta_inicio", "herramienta_inicio", "herramienta_fin", "herramienta_fin", "fin"]

    segunda = cliente.peticiones[1]["messages"]
    assert [m["role"] for m in segunda] == ["user", "assistant", "user"]
    assert [b["type"] for b in segunda[1]["content"]] == ["thinking", "text", "tool_use", "tool_use"]
    assert all(b["type"] == "tool_result" for b in segunda[2]["content"])
    assert len(sesion_familia.mensajes) == 4  # se guarda para la siguiente pregunta


def test_peticion_usa_cache_esfuerzo_y_herramientas(sesion_familia, falso):
    cliente = falso([respuesta(texto("Hola."))])
    Agente(revisor=False).responder(sesion_familia, "Hola")
    peticion = cliente.peticiones[0]
    assert peticion["model"] == "claude-sonnet-5-5"
    assert peticion["extra_body"]["cache_control"] == {"type": "ephemeral"}
    assert peticion["extra_body"]["output_config"]["effort"] == "medium"
    assert "temperature" not in peticion  # la API 2026-10-21 la rechaza
    nombres = [t["name"] for t in peticion["tools"]]
    assert nombres == sorted(nombres) and "resumen_gastos" in nombres
    assert "Fecha de hoy" in peticion["system"]


def test_enmascara_antes_de_enviar(sesion_familia, falso):
    cliente = falso([respuesta(texto("Vale."))])
    r = Agente(revisor=False).responder(sesion_familia, "Mi IBAN es ES91 2100 0418 4502 0005 1332")
    assert "[IBAN]" in cliente.peticiones[0]["messages"][-1]["content"]
    assert r.avisos


def test_errores_de_herramientas_vuelven_a_claude(sesion_familia, falso):
    cliente = falso([
        respuesta(herramienta("no_existe"), herramienta("calcular_prestamo", {"importe": -5, "tin_anual": 5,
                                                                               "plazo_meses": 12})),
        respuesta(texto("Corrijo los datos.")),
    ])
    r = Agente(revisor=False).responder(sesion_familia, "prueba")
    resultados = cliente.peticiones[1]["messages"][-1]["content"]
    assert all(b["is_error"] for b in resultados)
    assert r.texto == "Corrijo los datos."


def test_limite_de_vueltas(sesion_familia, falso):
    falso([respuesta(herramienta("leer_perfil")) for _ in range(5)])
    r = Agente(max_vueltas=2, revisor=False).responder(sesion_familia, "bucle")
    assert r.vueltas == 2 and "límite de pasos" in r.texto
    assert sesion_familia.mensajes[-1]["role"] == "assistant"


def test_revisor_corrige_la_respuesta(sesion_familia, falso):
    falso([
        respuesta(texto("Compra acciones de ACME.")),
        respuesta_json({"aprobada": False, "problemas": ["Recomienda un valor concreto"],
                        "respuesta_corregida": "No recomiendo valores concretos; te explico cómo comparar."}),
    ])
    eventos = {}
    r = Agente(revisor=True).responder(sesion_familia, "¿Qué compro?",
                                       al_evento=lambda tipo, datos: eventos.setdefault(tipo, datos))
    assert r.texto.startswith("No recomiendo valores concretos")
    assert eventos["revision"]["aprobada"] is False


def test_si_el_revisor_falla_la_respuesta_sale_igual(sesion_familia, falso):
    falso([respuesta(texto("Respuesta normal.")), respuesta(texto("esto no es JSON"))])
    r = Agente(revisor=True).responder(sesion_familia, "Hola")
    assert r.texto == "Respuesta normal."
    assert any(t["tipo"] == "revision" and "error" in t for t in r.trazas)


def test_adjunto_pdf_va_en_el_mensaje_del_usuario(sesion_familia, falso):
    cliente = falso([respuesta(texto("Leído."))])
    Agente(revisor=False).responder(sesion_familia, "Lee esta factura",
                                    adjunto={"tipo": "application/pdf", "datos_base64": "JVBERi0x"})
    contenido = cliente.peticiones[0]["messages"][-1]["content"]
    assert contenido[0]["type"] == "document" and contenido[1]["text"] == "Lee esta factura"


def test_elegir_modelo():
    assert elegir_modelo("hola") == "sonnet"
    assert elegir_modelo("Analiza mis gastos a fondo") == "opus"
    assert elegir_modelo("hola", "rapido") == "haiku"
    assert elegir_modelo("hola", "claude-opus-5-5") == "claude-opus-5-5"


def test_recortar_historial_no_separa_herramientas():
    mensajes = []
    for i in range(10):
        mensajes += [
            {"role": "user", "content": f"pregunta {i}"},
            {"role": "assistant", "content": [{"type": "tool_use", "id": f"t{i}", "name": "x", "input": {}}]},
            {"role": "user", "content": [{"type": "tool_result", "tool_use_id": f"t{i}", "content": "{}"}]},
            {"role": "assistant", "content": [{"type": "text", "text": "ok"}]},
        ]
    recortado = recortar_historial(mensajes, 10)
    assert len(recortado) <= 10 and recortado[0]["content"].startswith("pregunta")
