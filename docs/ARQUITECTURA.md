# Arquitectura

Estado: arquitectura objetivo del Copiloto (borrador del 9 de noviembre) sobre el kit, que sigue funcionando. `/planificar` la cierra con el `arquitecto`. Los tipos y las interfaces están en `docs/diseno/CONTRATO.md`, y el detalle de cada parte, en `docs/diseno/`.

## Visión general
```
Navegador: /app (cliente) · /banco (consola) · /jurado (métricas)
   │  HTTP y SSE                                   ▲ voz (WebRTC) con token de un solo uso
   ▼                                               │
API FastAPI ── plataforma/orquestador ── reloj simulado          ElevenLabs (agente de voz)
                 ├─ motor: normalizar → enriquecer → detectores → razonador ──> Momentos
                 ├─ modulos: catálogo YAML ──> Propuestas
                 ├─ personalizacion: ModeloUsuario ──> Decisiones (avisar, resumen o silencio)
                 └─ almacenamiento en datos_usuario/
API ── acciones: preparar → botón del usuario → ejecutar ── banco simulado
API ── voz: sesión de ElevenLabs y herramientas de cliente · modo texto con el agente del kit
Todo lo que llama a Claude ── backend/claude_client.py (Haiku 5.5 para clasificar y extraer)
```

## Componentes
| Componente | Ruta | Responsabilidad | Estado |
|---|---|---|---|
| Tipos y orquestador | `backend/plataforma/` | Modelos del contrato, `avanzar_dia`, `reproducir`, reloj simulado y almacenamiento | Nuevo |
| Motor | `backend/motor/` | Normalización, enriquecimiento, detectores en línea y razonador | Nuevo |
| Escenarios | `backend/escenarios/` | Historias sintéticas con la verdad etiquetada | Nuevo |
| Personalización | `backend/personalizacion/` | Modelo de usuario, política de interrupción, memoria y usuarios simulados | Nuevo |
| Módulos | `backend/modulos/` | Esquema YAML, minilenguaje, catálogo, borrador desde lenguaje natural y prueba en seco | Nuevo |
| Acciones | `backend/acciones/` | Registro cerrado (`preparar`, `ejecutar`) y banco simulado | Nuevo |
| Voz | `backend/voz/` | Sesión de ElevenLabs, herramientas de cliente y modo texto | Nuevo |
| Métricas | `evals/medir.py` | Precisión de los detectores y curva de aprendizaje | Nuevo |
| Web | `frontend/` | `/app`, `/banco` y `/jurado`; el chat del kit pasa a `/kit` | Se amplía |
| API | `backend/api/main.py` | Endpoints nuevos más los del kit | Se amplía |
| Agente conversacional | `backend/agente/` | Modo texto y preguntas durante la llamada | Del kit |
| Herramientas | `backend/herramientas/` | Las 14 del kit; el motor reutiliza recurrentes, anomalías, previsión y categorización | Del kit |
| Datos | `backend/datos/` | Sintéticos (3 perfiles), CSV, categorías y sesiones | Del kit, se amplía |
| Cliente de Claude | `backend/claude_client.py` | Único acceso a la API, precios y coste | Del kit |
| Evals y tests | `evals/`, `tests/` | Casos del agente y pytest con cliente simulado | Del kit, se amplía |

## Contrato de la API (borrador)
Lo propone `docs/diseno/experiencia.md` (sección 9) y lo cierra el `arquitecto`. Los endpoints del kit (`/salud`, `/datos/ejemplo`, `/movimientos`, `/chat`, `/chat/stream`) se mantienen.

| Método y ruta | Devuelve |
|---|---|
| `POST /usuarios/{id}/activar` | `ModeloUsuario` con consentimientos y módulos activos |
| `POST /reloj/avanzar` · `GET /reloj/reproducir` (SSE) | `Decision[]` · eventos `dia`, `momento`, `propuesta` y `decision` |
| `GET /usuarios/{id}/notificaciones` · `GET /propuestas/{id}` | Propuestas con su decisión · detalle con el momento y los motivos |
| `POST /voz/sesion` · `POST /voz/herramientas/{preparar,consultar,feedback}` | Modo (voz o texto), token o URL firmada y variables · tarjeta o respuesta |
| `POST /acciones/confirmar` · `POST /feedback` | `ResultadoAccion` · ok |
| `GET` y `PATCH /usuarios/{id}/aprendido` · `GET /usuarios/{id}/amigos` | Lo aprendido, editable · saldos con cada amigo |
| `GET /banco/modulos` · `POST /banco/modulos/borrador` (SSE) · `POST /banco/modulos/{id}/aprobar` | Módulos con métricas · pasos y prueba en seco · módulo activo |
| `GET /metricas/{deteccion,molestias,aprendizaje}` | Series para el panel del jurado |

## Datos
- `Movimiento` del kit (`id`, `fecha`, `concepto`, `comercio`, `importe`, `categoria`, `saldo`), más los campos opcionales `canal`, `contraparte` y `nota` para Bizums y transferencias.
- Escenarios en `backend/escenarios/` con la verdad etiquetada (formato en la skill `/escenario` y en `docs/diseno/motor.md`).
- Modelo de usuario, propuestas y auditoría de acciones en `datos_usuario/` (fuera de git).

## Despliegue
Backend en Render (`render.yaml`) o cualquier servicio con Docker (`Dockerfile`); frontend en Vercel (raíz `frontend/`). Ver `docs/DESPLIEGUE.md`. Variables nuevas del backend: `ELEVENLABS_API_KEY` y `ELEVENLABS_AGENT_ID`.
