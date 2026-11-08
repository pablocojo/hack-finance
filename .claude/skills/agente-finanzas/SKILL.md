---
name: agente-finanzas
description: Arquitectura del núcleo del agente del producto y cómo ampliarlo (registro de herramientas, sesión, eventos SSE, guardarraíles, modo demo, evals y tests). Cárgala antes de cambiar backend/agente, añadir herramientas, endpoints o fuentes de datos.
user-invocable: false
---

# Núcleo del agente del producto

## Flujo de una pregunta
1. La web llama a `POST /chat/stream` (`backend/api/main.py`); el panel y las evals llaman directamente a `servicio.conversar()`.
2. `servicio.conversar()` aplica el modo demo (`MODO_DEMO=grabar|reproducir`) y llama a `Agente.responder()`.
3. `Agente.responder()` (`backend/agente/nucleo.py`):
   - enmascara datos personales del mensaje (`guardarrailes.enmascarar`) y detecta inyecciones;
   - elige modelo (`elegir_modelo`: preferencia del usuario, o Opus para análisis y Sonnet para el resto);
   - monta el system (`prompts.system_prompt`, con fecha, resumen de datos y perfil) y las herramientas (`registro.disponibles()`);
   - bucle: llamada a Claude (streaming si hay `al_evento`) → si `tool_use`, ejecuta las herramientas en paralelo y devuelve `tool_result` → repite hasta `end_turn` o `MAX_VUELTAS`;
   - revisor de cumplimiento con Haiku (`REVISOR_CUMPLIMIENTO=1`), que puede corregir la respuesta;
   - guarda el historial en la sesión y emite `fin` con texto, modelo, vueltas, coste y trazas.

## Mapa de archivos
| Archivo | Qué hay |
|---|---|
| `backend/agente/registro.py` | `@herramienta`, esquema desde tipos y docstring, `ejecutar()` con errores devueltos a Claude |
| `backend/agente/nucleo.py` | `Agente`, `elegir_modelo`, `contenido_usuario` (adjuntos), `recortar_historial` |
| `backend/agente/prompts.py` | Prompt del sistema |
| `backend/agente/guardarrailes.py` | `enmascarar`, `parece_inyeccion`, `revisar_cumplimiento`, `AVISO_IA` |
| `backend/agente/servicio.py` | `conversar()` con el modo demo |
| `backend/agente/demo.py` | Grabación y reproducción de respuestas |
| `backend/herramientas/*.py` | Las herramientas (gastos, cálculos, mercados, perfil) |
| `backend/datos/` | `sinteticos.py`, `importar_csv.py`, `categorias.py`, `almacen.py` (sesiones en memoria) |
| `backend/claude_client.py` | Único acceso a Claude |
| `backend/config.py` | Variables de entorno (`ajustes()`, `clave_api()`) |

## Eventos SSE (`/chat/stream`)
`sesion {sesion_id}` → `aviso {texto}` → `texto {texto}` (varios) → `herramienta_inicio {id, nombre, entrada}` → `herramienta_fin {id, nombre, entrada, ms, error, resumen}` → `revision {aprobada, problemas, texto}` → `fin {texto, modelo, vueltas, coste_usd, coste_sesion_usd, herramientas, trazas, tokens}`. Si algo falla: `error {mensaje, tipo}`. Los tipos de TypeScript están en `frontend/lib/api.ts`: si cambias un evento, cambia los dos lados.

## Cómo ampliar
- **Herramienta**: skill `/herramienta`. El parámetro `ctx` es la `Sesion` (movimientos, perfil, `cerrojo` para modificar datos, `coste_usd`).
- **Herramienta condicionada** a una clave: `@herramienta(activa=lambda: bool(config.ajustes().mi_clave))`.
- **Endpoint**: en `backend/api/main.py`, con modelo de Pydantic para el cuerpo, errores con `HTTPException` y su test en `tests/test_api.py`.
- **Perfil sintético**: añade una entrada a `PERFILES` en `sinteticos.py` (fijos, variables, periódicos y anomalías).
- **Fuente externa**: `obtener_json()` con timeout, caché en disco y mensaje claro sin red (patrón de `mercados.py`).
- **Cambio de prompt**: en `prompts.py`, manteniendo estable el principio (caché) y pasando `/evals` después.

## Configuración (`.env`)
`MODELO_CHAT` (sonnet), `ESFUERZO_CHAT` (medium), `MAX_VUELTAS` (8), `MAX_TOKENS` (4000), `MAX_HISTORIAL` (40), `REVISOR_CUMPLIMIENTO` (1), `MODO_DEMO` (off), `BUSQUEDA_WEB` (0), `EJECUCION_CODIGO` (0), `PERFIL_DEMO` (familia), `NOMBRE_PRODUCTO`, `ORIGENES_CORS`, `ALPHA_VANTAGE_API_KEY`, `GUARDAR_PERFILES` (1).

## Tests sin crédito
```python
from backend.claude_falso import herramienta, respuesta, respuesta_json, texto

def test_algo(sesion_familia, falso):
    cliente = falso([respuesta(herramienta("resumen_gastos", {"meses": 3})), respuesta(texto("..."))])
    resultado = Agente(revisor=False).responder(sesion_familia, "¿En qué gasto más?")
    assert resultado.herramientas == ["resumen_gastos"]
    assert cliente.peticiones[0]["model"] == "claude-sonnet-5-5"
```
