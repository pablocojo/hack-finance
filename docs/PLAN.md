# Plan del proyecto

Lo mantienen el orquestador y `/estado`. `/planificar` cierra las tareas y `/esqueleto` las primeras.

## Estado
- 2026-11-09, mediodía: cambio de idea a **Copiloto**. El sistema de trabajo está listo: contrato en `docs/diseno/CONTRATO.md`, 16 subagentes, skills nuevas (`/planificar`, `/esqueleto`, `/escenario`, `/detector`, `/modulo`, `/medir` y `copiloto`) y borradores de diseño en `docs/diseno/`. Aún no hay código nuevo; los tests del kit siguen en verde. **Siguiente paso: `/planificar` y después `/esqueleto`.**

## Idea y MVP
- **Idea elegida**: Copiloto, una plataforma para bancos que convierte los movimientos de cada cliente en momentos, avisa solo cuando ahorra dinero o protege y lo resuelve en una llamada de voz. Aprende de cada usuario y admite módulos nuevos sin código.
- **Usuario**: el cliente del banco, dentro de la app de su banco. **Comprador**: bancos medianos y neobancos.
- **MVP** (imprescindible para ganar):
  1. Motor en línea con reloj simulado y cuatro detectores: `gasto_compartido` (la estrella), `cargo_duplicado`, `renovacion_proxima` y `saldo_negativo_previsto`.
  2. Personalización que aprende del feedback, con la curva «semana 1 frente a semana 6» y sus motivos visibles.
  3. Módulos en YAML con acciones de la lista cerrada y confirmación por botón, y un módulo creado en directo desde lenguaje natural (prueba en seco y aprobación).
  4. Notificación → llamada de voz con ElevenLabs, aviso de IA y modo texto de respaldo.
  5. Panel del jurado: precisión de la detección, molestias evitadas y curva de aprendizaje.
- **Si sobra tiempo**: `posible_estafa`, `subida_recibo`, `ingreso_extra` (primera nómina), «lo que he aprendido de ti» editable y saldos con cada amigo.
- **Fuera del MVP (a propósito)**: el seguro de viaje (módulo secundario y opcional), datos bancarios reales, pagos reales y app móvil nativa.

## Hoja de ruta y puertas
| Fase | Cuándo | Qué | Puerta al final |
|---|---|---|---|
| Idea | 8 nov | Primera idea (municipios), descartada el 9 | Idea cerrada |
| Cambio de idea | 9 nov, mañana | Contrato, agentes, skills y borradores de diseño | **Sistema de trabajo listo** (hecho) |
| Diseño | 9 nov, tarde | `/planificar` | **Diseño cerrado**: contrato sin contradicciones, arquitectura y tareas aquí |
| Esqueleto | 9 nov, tarde y noche | `/esqueleto` | **Esqueleto vivo**: un escenario etiquetado recorre todo el flujo y `/medir` da la línea base |
| MVP | 10 nov | `/feature` en 2 o 3 sesiones a la vez | **MVP completo** (10 nov, noche): `pytest`, `/medir` y `/evals` en verde |
| Pulido | 11 nov, mañana | Pruebas con compañeros, voz real y grabación del modo demo | **Congelación** (11 nov, 14:00): solo arreglos |
| Demo y entrega | 11 nov por la tarde y 12 nov | `/demo`, vídeo y dos ensayos | **Entrega** (12 nov) |

## Tareas
| Id | Tarea | Zona | Depende de | Criterio de aceptación | Cómo se verifica | Día | Estado |
|---|---|---|---|---|---|---|---|
| P1 | Cerrar el diseño | todas | — | Contrato sin contradicciones; arquitectura y tareas escritas; el revisor no deja nada que bloquee | `/planificar` | 9 nov | pendiente |
| P2 | Montar el esqueleto | todas | P1 | Un escenario etiquetado recorre todo el flujo y `/medir` da la línea base | `/esqueleto`: `pytest`, `/medir` y el flujo a mano | 9 nov | pendiente |
| P3 | Crear el agente en ElevenLabs y comprobar las variables dinámicas | voz | P1 | Llamada de prueba con el aviso de IA y una herramienta de cliente | Prueba manual de 2 minutos | 10 nov, mañana | pendiente |

El resto de tareas las escribe el `arquitecto` en `/planificar`: como mucho 2 horas cada una, con zona, dependencias y verificación.

Zonas: `plataforma`, `motor`, `personalizacion`, `modulos`, `voz`, `api`, `frontend` y `demo`. Una sesión de Claude por zona en paralelo.

## Riesgos y planes B
| Riesgo | Señal | Plan B |
|---|---|---|
| Falsos positivos que parecen spam | Trampas en rojo en `/medir` | Subir umbrales, añadir trampas y dejar que la política silencie; enseñar «molestias evitadas» |
| La cena compartida falla con importes raros | Escenarios límite en rojo | Preguntar al usuario en vez de adivinar; demo con el escenario fijo |
| La personalización no se nota en la demo | Curva plana en `/medir personalizacion` | Usuario simulado con preferencias claras durante 6 semanas; curva precalculada como respaldo |
| La voz tarda o falla | Latencia por encima de 2 s o errores | Modelo más rápido o menos razonamiento; modo texto; modo demo grabado |
| Pocos créditos de ElevenLabs | Minutos gastados | Ensayar en texto; voz solo en dos ensayos y en la entrega |
| Inyección en notas de Bizum o conceptos | Evals de ataque en rojo | Marcar como datos, limpiar y confirmar con botón validado en el servidor |
| Demasiados módulos a medias | `/estado` dice «justo» | Cuatro módulos perfectos más uno en directo; congelar el resto |
| Cambios del contrato a mitad | Conflictos entre zonas | Cambios solo en `CONTRATO.md`, a través del orquestador; integrar pronto |
| La demo falla en directo (red o API) | — | Vídeo grabado y `MODO_DEMO=reproducir` con respuestas guardadas |
| Se agota el saldo de una clave | `/usage` o error de saldo | Cambiar de clave, bajar a Sonnet y abrir menos sesiones |
| Error 429 por límite de velocidad | Mensajes de rate limit | Bajar la concurrencia a 2 y esperar; el SDK reintenta solo |
| Se pierde el contexto entre días | Claude repite trabajo | `/cierre-dia` cada noche; el hook de inicio enseña el diario |
| El despliegue falla el último día | — | Desplegar el esqueleto el primer día y volver a desplegar cada día |
| Una clave queda expuesta | `revisor` o `security-guidance` lo detectan | Claves solo en el backend, `.env` fuera de git y rotar la clave |

## Claves de la API
| Clave | Uso | Dónde |
|---|---|---|
| 1 | Claude Code (desarrollo) | Variable de entorno `ANTHROPIC_API_KEY` del sistema |
| 2 | Producto (motor, módulos, agente y demo) | `.env`: `ANTHROPIC_API_KEY_PRODUCTO` y en el despliegue |
| 3 | Evals | `.env`: `ANTHROPIC_API_KEY_EVALS` |
| 4-6 | Reserva | Gestor de contraseñas; solo si se agota otra |
| ElevenLabs | Llamada de voz | `.env`: `ELEVENLABS_API_KEY` y `ELEVENLABS_AGENT_ID` (solo en el backend) |
