# Arquitectura

Estado del kit antes del reto. El `arquitecto` la adapta en `/kickoff`.

## Visión general
Un agente conversacional con herramientas. Claude decide qué consultar o calcular, el código hace los números y la interfaz enseña la respuesta, los gráficos y cómo ha razonado.

```
Web (Next.js) ──SSE──> API (FastAPI) ──┐
Panel (Streamlit) ─────────────────────┼──> servicio.conversar() ──> Agente (núcleo) <──> API de Claude
Evals ─────────────────────────────────┘                                │
                                                     guardarraíles ─────┤ (enmascarado, revisor)
                                                     herramientas ──────┴──> datos (sintéticos, CSV, Frankfurter, Alpha Vantage)
```

## Componentes
| Componente | Ruta | Responsabilidad |
|---|---|---|
| Web | `frontend/` | Chat en streaming, panel de gastos, subida de CSV, adjuntos, traza y avisos |
| API | `backend/api/main.py` | Endpoints, SSE, CORS, límites de tamaño |
| Servicio | `backend/agente/servicio.py` | Modo demo (grabar o reproducir) y llamada al agente |
| Núcleo | `backend/agente/nucleo.py` | Bucle de herramientas, enrutado de modelos, streaming, límites, coste y trazas |
| Registro | `backend/agente/registro.py` | Esquema JSON desde funciones, ejecución con errores devueltos a Claude |
| Prompt | `backend/agente/prompts.py` | Reglas del agente, contexto de datos y perfil |
| Guardarraíles | `backend/agente/guardarrailes.py` | Datos personales, inyección y revisor de cumplimiento (Haiku) |
| Herramientas | `backend/herramientas/` | 14: gastos, cálculos, mercados y perfil |
| Datos | `backend/datos/` | Sintéticos (3 perfiles), importación de CSV, categorías, sesiones en memoria |
| Cliente de Claude | `backend/claude_client.py` | Único acceso a la API, precios y coste |
| Panel | `panel/app.py` | Pruebas rápidas del agente y de cada herramienta |
| Evals | `evals/` | Casos, ejecución y comparación con la anterior |

## Contrato de la API
| Método y ruta | Cuerpo o parámetros | Respuesta |
|---|---|---|
| `GET /salud` | — | Producto, avisos, modelo, modo demo, herramientas, perfiles, clave configurada |
| `POST /datos/ejemplo` | `{perfil, sesion_id?, meses?}` | `{sesion_id, movimientos, desde, hasta, origen, sin_categoria}` |
| `GET /movimientos` | `sesion_id, limite?, categoria?` | `{total, movimientos[]}` (los más recientes primero) |
| `POST /movimientos` | multipart `archivo` + `sesion_id?` | `{sesion_id, informe, movimientos, ...}` |
| `GET /movimientos/resumen` | `sesion_id, meses?` | Resultado de `resumen_gastos` + `vacio` |
| `POST /chat` | `{mensaje, sesion_id?, modelo?, adjunto?}` | Resultado completo del agente |
| `POST /chat/stream` | igual | SSE: `sesion`, `aviso`, `texto`, `herramienta_inicio`, `herramienta_fin`, `revision`, `fin`, `error` |

`modelo`: `auto`, `rapido` (Haiku), `normal` (Sonnet), `profundo` (Opus). `adjunto`: `{tipo, datos_base64}` con imagen o PDF.

## Herramientas del agente
`resumen_gastos`, `buscar_movimientos`, `detectar_anomalias`, `gastos_recurrentes`, `prevision_saldo`, `categorizar_movimientos`, `calcular_prestamo`, `interes_compuesto`, `plan_ahorro`, `regla_50_30_20`, `convertir_divisa`, `precio_accion` (solo con clave de Alpha Vantage), `guardar_preferencia`, `leer_perfil`.

## Datos
- Movimiento: `{id, fecha (AAAA-MM-DD), concepto, comercio, importe (negativo = cargo), categoria, saldo?}`.
- Perfiles sintéticos: `estudiante`, `familia`, `autonomo`, con un cargo duplicado, un gasto inusual y un comercio nuevo sembrados a propósito.
- Las sesiones viven en memoria; el perfil del usuario se guarda en `datos_usuario/perfiles/` (fuera de git).

## Despliegue
Backend en Render (`render.yaml`) o cualquier servicio con Docker (`Dockerfile`); frontend en Vercel (raíz `frontend/`). Ver `docs/DESPLIEGUE.md`.
