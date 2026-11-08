---
name: api-claude
description: Uso correcto de la API de Claude dentro del producto (modelos y precios, caché, esfuerzo, salidas estructuradas, herramientas, streaming, visión y PDF, herramientas del servidor y errores). Cárgala al escribir o cambiar código que llama a Claude.
user-invocable: false
---

# API de Claude en el producto

Comprobado el 7 de noviembre de 2026. SDK de Python `anthropic` 2.x (versión de la API 2026-10-21).

## Modelos (USD por millón de tokens, entrada / salida)
| Alias | ID | Precio | Uso en el producto |
|---|---|---|---|
| `haiku` | `claude-haiku-5-5` | 0,10 / 0,50 | Clasificar, revisar cumplimiento, extraer |
| `sonnet` | `claude-sonnet-5-5` | 2 / 10 | Conversación normal (por defecto) |
| `opus` | `claude-opus-5-5` | 4 / 20 | Análisis largos o complejos; piensa siempre y `max_tokens` incluye ese razonamiento |
Leer de la caché cuesta el 5 % de la entrada en Opus y Sonnet; escribir en la caché de 5 minutos, 1,25 veces. La búsqueda web del servidor cuesta 10 $ por cada 1.000 búsquedas.

## Siempre a través de `backend/claude_client.py`
- `preguntar(prompt, system=..., modelo="haiku", esfuerzo=None)` → texto.
- `preguntar_json(prompt, esquema, modelo="haiku")` → dict que cumple el JSON Schema (salida estructurada). `preguntar_json_con_coste` devuelve también el coste.
- `preparar_peticion(...)` construye los argumentos de `messages.create` y `messages.stream`; `coste(modelo, usage)` estima el gasto.
- Claves: `cliente("producto")` usa `ANTHROPIC_API_KEY_PRODUCTO`; `cliente("evals")`, `ANTHROPIC_API_KEY_EVALS`.
- Tests: `usar_cliente(ClienteFalso([...]))` de `backend/claude_falso.py`.

## Reglas que evitan errores
- `temperature`, `top_p` y `top_k` ya no existen: devuelven 400. Tampoco hay prefill de la respuesta.
- Los PDF (`document`) van siempre en mensajes del usuario; en mensajes del asistente dan 400.
- La respuesta puede empezar con bloques `thinking`: lee el texto filtrando `type == "text"` (`texto_de`). En el bucle de herramientas, devuelve los bloques del asistente tal cual (incluido `thinking` con su firma).
- La API no tiene estado: cada llamada lleva el historial completo, system incluido.
- Bucle de herramientas: mientras `stop_reason == "tool_use"`, ejecutar, responder con bloques `tool_result` (mismo `tool_use_id`, `is_error: true` si falló) en un mensaje `user`, y volver a llamar. `pause_turn` (herramientas del servidor): volver a llamar con el mismo historial.
- Varias herramientas en la misma respuesta son independientes: se ejecutan en paralelo y se devuelven todas juntas.

## Coste y latencia
- Caché automática: `cache_control: {"type": "ephemeral"}` en la raíz (lo pone `preparar_peticion`). Solo se cachea a partir de 512 tokens. Mantén estables el principio del system y el orden de las herramientas.
- Esfuerzo: `output_config.effort` = `low` | `medium` | `high` | `xhigh` | `max`. Por defecto, `medium` en Opus y Haiku y `high` en Sonnet. En el chat usamos `medium`; para clasificar, `low`.
- Salida estructurada: `output_config.format = {"type": "json_schema", "schema": ...}` con `additionalProperties: false` en cada objeto (lo añade `cerrar_objetos`).
- Ambas opciones viajan en `extra_body` para que funcionen con cualquier versión 2.x del SDK.

## Visión y documentos
- Imagen: `{"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": ...}}` (png, jpeg, gif, webp).
- PDF: `{"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": ...}}`.
- Pon el adjunto antes del texto de la pregunta (`contenido_usuario` en `nucleo.py`).

## Herramientas del servidor (opcionales, en `.env`)
- `BUSQUEDA_WEB=1`: `{"type": "web_search_20260209", "name": "web_search", "max_uses": 3}`.
- `EJECUCION_CODIGO=1`: `{"type": "code_execution_20250825", "name": "code_execution"}`. Si la API la rechaza, desactívala.

## Errores
| Excepción | Qué hacer |
|---|---|
| `RateLimitError` (429) | El SDK reintenta (configurado con 3 reintentos). Baja la concurrencia |
| `APIConnectionError`, `APITimeoutError` | Red. Mensaje claro y plan B (modo demo) |
| `AuthenticationError` | Clave mal puesta |
| `BadRequestError` (400) | Revisa parámetros; "credit balance" = saldo agotado |
| `InternalServerError` / saturación | Reintentar más tarde |
`backend/api/sse.py` traduce todas estas excepciones a mensajes en español.

## Límites de la organización
Los límites de uso se aplican por organización, no por clave. Las 6 claves del hackathon pueden compartirlos: no lances más de 3-4 sesiones intensivas a la vez.
