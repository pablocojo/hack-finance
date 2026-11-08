# Plan del proyecto

Lo mantienen el orquestador y `/estado`. El `arquitecto` rellena las tareas en `/kickoff`.

## Estado
- 2026-11-07: kit v2 preparado. Falta el reto (llega el 8 nov a las 9:00).

## Idea y MVP
- Idea elegida: _(pendiente de /kickoff)_
- Usuario: _(pendiente)_
- MVP (imprescindible para ganar):
  1. _(pendiente)_
- Fuera del MVP (a propósito):
  - _(pendiente)_

## Hoja de ruta y puertas
| Fase | Cuándo | Qué | Puerta al final |
|---|---|---|---|
| Idea | 8 nov, 9:00-13:00 | Tema, ideas de los compañeros, /kickoff | **Idea cerrada** (13:00): MVP escrito aquí |
| Esqueleto | 8 nov, tarde | Flujo completo y primer despliegue | **Esqueleto vivo** (noche): pregunta → respuesta, desplegado |
| MVP | 9 y 10 nov | /feature en 2 o 3 sesiones a la vez | **MVP completo** (10 nov, noche): evals en verde |
| Pulido | 11 nov, mañana | Pruebas con compañeros y arreglos | **Congelación** (11 nov, 14:00): solo arreglos |
| Demo y entrega | 11 nov tarde y 12 nov | /demo, vídeo y dos ensayos | **Entrega** (12 nov) |

## Tareas
| Id | Tarea | Zona | Depende de | Criterio de aceptación | Cómo se verifica | Día | Estado |
|---|---|---|---|---|---|---|---|
| T0 | Ejemplo: adaptar el prompt al reto | agente | — | El agente se presenta con el nombre del producto | `/evals` caso aviso-ia | 8 nov | pendiente |

Zonas: `agente` (prompts, herramientas), `backend` (API, datos), `frontend`, `demo`. Una sesión de Claude por zona en paralelo.

## Riesgos y planes B
| Riesgo | Señal | Plan B |
|---|---|---|
| La demo falla en directo (red o API) | — | Vídeo grabado y `MODO_DEMO=reproducir` con respuestas guardadas |
| Alcance demasiado grande | `/estado` dice "justo" o "no llegamos" | Recortar lo que no sea imprescindible y congelar el 11 nov a las 14:00 |
| El tema no encaja con la arquitectura base | El análisis pide otro tipo de producto | El arquitecto adapta el diseño; el núcleo sirve con herramientas nuevas (`/herramienta`) |
| Las reglas prohíben llegar con código hecho | Lo dicen las bases | Usar solo `.claude/` y `CLAUDE.md` y regenerar el código desde cero |
| El agente inventa cifras o da consejos de inversión | Evals en rojo | Reforzar el prompt, obligar a usar herramientas y activar el revisor |
| Una API de datos falla o limita | Errores de red o límite de Alpha Vantage | Caché y tipos de respaldo sin conexión |
| Se agota el saldo de una clave | `/usage` o error de saldo | Cambiar de clave, bajar a Sonnet y abrir menos sesiones |
| Error 429 por límite de velocidad | Mensajes de rate limit | Bajar la concurrencia a 2 y esperar; el SDK reintenta solo |
| Conflictos entre sesiones paralelas | Conflictos al integrar | Una sesión por zona, integrar pronto y pedir a Claude que resuelva el conflicto |
| Se pierde el contexto entre días | Claude repite trabajo | `/cierre-dia` cada noche; el hook de inicio enseña el diario |
| El despliegue falla el último día | — | Desplegar el esqueleto el primer día y volver a desplegar cada día |
| La clave queda expuesta | `revisor` o `security-guidance` lo detectan | Clave solo en el backend, `.env` fuera de git y rotar la clave |

## Claves de la API
| Clave | Uso | Dónde |
|---|---|---|
| 1 | Claude Code (desarrollo) | Variable de entorno `ANTHROPIC_API_KEY` del sistema |
| 2 | Producto (agente de la app y demo) | `.env`: `ANTHROPIC_API_KEY_PRODUCTO` y en el despliegue |
| 3 | Evals | `.env`: `ANTHROPIC_API_KEY_EVALS` |
| 4-6 | Reserva | Gestor de contraseñas; solo si se agota otra |
