# Plan del proyecto

Lo mantienen el orquestador y `/estado`. `/planificar` cierra las tareas y `/esqueleto` las primeras.

## Estado
- 2026-11-09, mediodía: cambio de idea a **Copiloto**. El sistema de trabajo está listo: contrato en `docs/diseno/CONTRATO.md`, 16 subagentes, skills nuevas (`/planificar`, `/esqueleto`, `/escenario`, `/detector`, `/modulo`, `/medir` y `copiloto`) y borradores de diseño en `docs/diseno/`. Aún no hay código nuevo; los tests del kit siguen en verde. **Siguiente paso: `/planificar` y después `/esqueleto`.**
- 2026-11-09, 13:45 (`/estado`): **justo**. Sin código nuevo y quedan 2,5 días; el MVP tiene cinco bloques grandes. Faltan en git tres de los cuatro borradores de diseño (`motor.md`, `personalizacion.md` y `modulos.md`; solo están `CONTRATO.md` y `experiencia.md`): o se recuperan o `/planificar` los rehace. Entorno montado en el portátil (`.venv`; `pytest`: 83 en verde). Faltan el `.env` con las claves y el agente de ElevenLabs. Recorte propuesto si el 10 a mediodía vamos tarde: la creación de módulos en lenguaje natural se queda en borrador YAML con prueba en seco (sin flujo de aprobación) y el panel del jurado es una página que lee `evals/resultados/`. **Siguiente: P1 `/planificar` y después P2 `/esqueleto`; P3 (ElevenLabs) en paralelo, a mano.**

- 2026-11-09, ~17:30 (`/planificar`): **diseño cerrado**. Contrato con todas las decisiones (`docs/diseno/CONTRATO.md`), los cuatro diseños reescritos o pulidos, revisión de banca y revisión final aplicadas, `ARQUITECTURA.md` y tareas E1-E12, H*, O*. **Recorte por carga** (el plan pedía 19,5 h hoy y 34 h el 10): hoy solo E1-E8 (E8 mínimo: activar, avanzar, notificaciones, preparar y confirmar); E9, E10 y E12 pasan al 10 por la mañana; O1-O7 fuera; `/jurado` desde los JSON de `medir`; curva con una semilla en la demo. Prioridad intocable: la cena de principio a fin en modo texto. **Siguiente: `/esqueleto`, empezando por E1 (`backend/plataforma/tipos.py`).**

## Idea y MVP
- **Idea elegida**: Copiloto, una plataforma para bancos que convierte los movimientos de cada cliente en momentos, avisa solo cuando ahorra dinero o protege y lo resuelve en una llamada de voz. Aprende de cada usuario y admite módulos nuevos sin código.
- **Usuario**: el cliente del banco, dentro de la app de su banco. **Comprador**: bancos medianos y neobancos.
- **MVP** (imprescindible para ganar):
  1. Motor en línea con reloj simulado y cinco detectores: `gasto_compartido` (la estrella), `cargo_duplicado`, `renovacion_proxima`, `saldo_negativo_previsto` y `subida_recibo` (para el módulo que el banco crea en directo).
  2. Personalización que aprende del feedback, con la curva «semana 1 frente a semana 6» y sus motivos visibles.
  3. Módulos en YAML con acciones de la lista cerrada y confirmación por botón, y un módulo creado en directo desde lenguaje natural (prueba en seco y aprobación).
  4. Notificación → llamada de voz con ElevenLabs, aviso de IA y modo texto de respaldo.
  5. Panel del jurado: precisión de la detección, molestias evitadas y curva de aprendizaje.
- **Si sobra tiempo**: `posible_estafa` (fuera de la demo; propone «llama al banco»), `ingreso_extra` (primera nómina), «lo que he aprendido de ti» editable y saldos con cada amigo.
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
Las escribe el `arquitecto` en `/planificar` (9 nov, 16:00). Contrato de la API y archivos en `docs/ARQUITECTURA.md`. Columna **Hilo**: `—` = secuencial (bloquea a los demás); `H1`, `H2`, `H3` = sesiones en paralelo (`claude --worktree <zona>`, integrar en `main` al acabar cada tarea); `mano` = Pablo, fuera de Claude Code. **h** = horas de sesión (máximo 2).

### 9 nov: esqueleto (P2 = E1-E12)
Orden: E1 solo (16:15-17:45) → bloque 1 en paralelo (17:45-21:45) → bloque 2 en paralelo (21:45-23:45) → E11 y E12. Si a las 23:45 va tarde, E10 y E12 pasan al 10 a las 9:00 (la puerta no depende de ellas).

| Id | Tarea | Zona | Depende de | Criterio de aceptación | Cómo se verifica | Día | Hilo | h | Estado |
|---|---|---|---|---|---|---|---|---|---|
| P1 | Cerrar el diseño | todas | — | Contrato sin contradicciones; arquitectura y tareas escritas; el revisor no deja nada que bloquee | `/planificar` | 9 nov | — | — | hecho |
| P2 | Montar el esqueleto (agrupa E1-E12) | todas | P1 | La cena de Lucía recorre motor → módulo → decisión → propuesta → acción simulada y `/medir` da la línea base | `/esqueleto` | 9 nov | — | — | pendiente |
| E1 | Contrato en código: `plataforma/tipos.py` (todos los tipos del contrato, también `SesionVoz`, `BorradorModulo`, `InformePrueba`, `Modulo`, `HechoAprendido`, `Amigo`), `reloj.py`, `almacenamiento.py`, `privacidad.py`, `config.datos_usuario_dir` y `DATOS_USUARIO_DIR` en `conftest.py` | plataforma | P1 | `Decimal` sale como cadena; los ejemplos de `motor.md` §4 validan; escritura atómica | `pytest tests/test_tipos.py tests/test_almacenamiento.py`; commit antes de abrir hilos | 9 nov | — | 1,5 | pendiente |
| E2 | Motor base: `normalizar`, `estado`, `procesar`, `cargar_historial`, `exportar`/`importar_estado`, `reiniciar`, razonador (clave, filtro, plantilla), registro de detectores; `sinteticos(anomalias=False)` | motor | E1 | Rechaza `fecha > hoy`; reprocesar es idempotente; «Laura Martinez G» → `LAURA M` | `pytest tests/test_motor_base.py` | 9 nov | H1 | 2 | pendiente |
| E3 | `escenarios/cargar.py`, `cena-lucia.yaml` (con cenas previas y trampa de Bizums recibidos) y detector `gasto_compartido` con candidatos | motor | E2 | Momento el 9-11 con `personas_estimadas` 5, `faltan` 1, `importe_pendiente` "24.00" y candidato `MARCOS R`; trampa sin violar | `pytest tests/test_escenarios.py -k cena` | 9 nov | H1 | 2 | pendiente |
| E4 | Módulos: `esquema`, `campos_momento`, `condiciones` (minilenguaje completo), `plantillas`, `registro`, `proponer`, `catalogo/cena_compartida.yaml`; *stubs* de `crear_borrador`, `probar_en_seco` y `aprobar` que devuelven ejemplos válidos | modulos | E1 | La cena da una propuesta con `pedir_bizum` a Marcos limitada a 24 €; la gramática rechaza `__import__`, atributos y llamadas | `pytest tests/test_condiciones.py tests/test_modulos_catalogo.py` | 9 nov | H2 | 2 | pendiente |
| E5 | Acciones: las seis `AccionDef`, `banco_sim`, `tokens` (10 min, hash de parámetros, un solo uso, idempotencia), `auditoria.jsonl`, `preparar`/`ejecutar` | modulos | E1 | Fallan el token reutilizado, caducado, de otra propuesta, con parámetros alterados o sobre el límite; todo queda auditado y enmascarado | `pytest tests/test_acciones.py` | 9 nov | H2 | 2 | pendiente |
| E6 | Personalización v1: `nuevo_modelo`, `decidir` (reglas duras, Beta jerárquica, utilidad, motivos) y `aprender`, puras; *stubs* de `observar`, `registrar_decision`, `registrar_accion` y `memoria_para_agente` | personalizacion | E1 | Ejemplo §3.4 de `personalizacion.md` exacto; toda decisión con motivo; la protección nunca se silencia; < 5 ms | `pytest tests/test_personalizacion_politica.py` | 9 nov | H3 | 2 | pendiente |
| E7 | Orquestador: `cargar_escenario`, `activar`, `avanzar_dia`, `reproducir`, `registrar_feedback`, `preparar_accion`, `confirmar_accion` y consultas; candado por usuario | plataforma | E1 (E2-E6 con falsos si no han llegado) | Un día produce momento → propuesta → decisión y se guarda; `reproducir` emite los eventos en orden | `pytest tests/test_orquestador.py` | 9 nov | H3 | 2 | pendiente |
| E8 | API: `rutas_copiloto`, `rutas_voz` (contra *stubs* de voz), `rutas_banco`, `rutas_metricas`, incluidos en `main.py`; CORS con `PATCH` y `DELETE` | api | E5, E7 | Responden todos los endpoints de ARQUITECTURA §3; los del kit siguen igual | `pytest tests/test_api.py tests/test_api_copiloto.py` | 9 nov | H2 | 2 | pendiente |
| E9 | `/medir` línea base: `evals/medir.py --parte` y `medir_motor.py` (precisión, exhaustividad, retraso, trampas) | motor | E3 | Escribe `evals/resultados/motor-<fecha>.json`; `gasto_compartido` 1,0 / 1,0 en `cena-lucia` | `python evals/medir.py --parte motor` | 9 nov | H1 | 1 | pendiente |
| E10 | Frontend mínimo: chat del kit a `/kit`, portada `/`, `/app` con `Bandeja` y «Avanzar un día»; `api.ts` con todos los tipos y funciones de §3 | frontend | E1 | `/app` muestra la notificación de la cena contra el backend local | `npm run build` y la app a mano | 9 nov | H3 | 1,5 | pendiente |
| E11 | Unir: integrar ramas, test de principio a fin de `cena-lucia` por HTTP, `revisor` y puerta **esqueleto vivo** | plataforma | E2-E9 | `pytest -q` en verde; `/medir` da línea base; a mano: avanzar → notificación → preparar → confirmar | `pytest -q`, `/medir motor`, `revisor` | 9 nov | — | 1 | pendiente |
| E12 | Desplegar el esqueleto (Render + Vercel) | demo | E11 | `/salud` y `/app` responden en las URL públicas | Abrir las URL | 9 nov | — | 0,5 | pendiente |

### 10 nov: MVP (tres hilos de 9:00 a ~22:30; X1 al final)
| Id | Tarea | Zona | Depende de | Criterio de aceptación | Cómo se verifica | Día | Hilo | h | Estado |
|---|---|---|---|---|---|---|---|---|---|
| P3 | Crear el agente en ElevenLabs y comprobar las variables dinámicas (`experiencia.md` §6.1 y §6.3) | voz | P1 | Llamada de prueba con el aviso de IA y una herramienta de cliente | Prueba manual de 2 minutos | 10 nov, mañana | mano | 2 | pendiente |
| M1 | `cargo_duplicado` y sus escenarios (2 positivos, 4 trampas de `motor.md` §4) | motor | E9 | Precisión ≥ 0,9, exhaustividad 1, retraso 0, 0 trampas | `pytest -k duplicado`; `/medir motor` | 10 nov | H1 | 1,5 | pendiente |
| M2 | Series completas (1, 3, 6 y 12 meses, `serie_id`) y `renovacion_proxima` con escenarios | motor | M1 | ≥ 0,9 / ≥ 0,9; antelación ≥ 7 días (anual ≥ 14); 0 trampas | `pytest -k renovacion`; `/medir motor` | 10 nov | H1 | 2 | pendiente |
| M3 | `saldo_negativo_previsto` con escenarios | motor | M2 | ≥ 0,8 / ≥ 0,8; antelación ≥ 3 días | `pytest -k saldo`; `/medir motor` | 10 nov | H1 | 1,5 | pendiente |
| M4 | `subida_recibo` y escenario `recibo-luz` (sube 12 €: avisa; sube 2 €: trampa) | motor | M2 | Detecta la de 12 € el día del cargo; 0 trampas | `pytest -k subida`; `/medir motor` | 10 nov | H1 | 1 | pendiente |
| D1 | Catálogo: `cobro_duplicado`, `renovacion` y `colchon` | modulos | E4, M1, M3 | Cada YAML da su propuesta esperada con acciones y `limites`; nada sin marcar como dato | `pytest tests/test_modulos_catalogo.py` | 10 nov | H1 | 1 | pendiente |
| M5 | Trampas restantes de la cena, `fondo-*`, test de no mirar el futuro y de rendimiento | motor | M3 | Objetivos de `motor.md` §5; ruido ≤ 1 por usuario y mes; 6 meses < 2 s | `pytest`; `/medir motor` | 10 nov | H1 | 1,5 | pendiente |
| M6 | Escenario de la demo `demo-lucia` (8 semanas: cena, duplicado de 9,99 €, renovación anual, recibo de luz) | motor | M4, D1 | Al reproducir: el duplicado va a «Resumen», la cena a «Ahora» y el recibo solo avisa con el módulo del banco | `pytest tests/test_demo_lucia.py` | 10 nov | H1 | 1 | pendiente |
| D3 | `probar_en_seco`, `aprobar`, estados del registro y métricas por módulo | modulos | M4, D1 | `recibo_al_alza` escrito a mano: «1 aviso, 0 falsos» y controles en verde; aprobado, recibe momentos al día siguiente | `pytest tests/test_prueba_seco.py` | 10 nov | H1 | 1,5 | pendiente |
| V1 | Modo texto (nivel 3): `voz/sesiones.py`, `contexto.py`, `texto.py`, `herramientas_llamada.py`, grupo `llamada` en el registro, `/voz/texto` y `/voz/herramientas/{preparar,feedback}` | voz | E8 | Saludo fijo con aviso de IA; con cliente falso prepara `pedir_bizum` y sale el evento `tarjeta`; el token nunca llega al modelo; `/kit` no ve las herramientas | `pytest tests/test_voz_texto.py` | 10 nov | H2 | 2 | pendiente |
| V2 | Sesión de ElevenLabs: `elevenlabs.py` (token y URL firmada), elección de modo y plan B por niveles | voz | V1 | Sin clave → `texto_kit`; con falso → token; ninguna respuesta de `/voz/*` contiene la clave | `pytest tests/test_voz_sesion.py` | 10 nov | H2 | 1,5 | pendiente |
| U1 | Amigos y líneas base: `registrar_decision`, `registrar_accion`, `observar` (salda), enganchados en el orquestador | personalizacion | E7 | Tras confirmar `pedir_bizum`, Marcos pasa a `pedido`; al entrar su Bizum, a `saldado` | `pytest tests/test_amigos.py` y test de principio a fin | 10 nov | H2 | 1,5 | pendiente |
| U2 | Hechos aprendidos y edición (apagar, editar, borrar, olvidar todo), silencios `no_avisar_*` e `ignorada` a las 48 h en el orquestador | personalizacion | U1 | Borrar un hecho cambia la siguiente decisión; 0 avisos tras un `no_avisar_*` | `pytest tests/test_personalizacion_aprender.py` | 10 nov | H2 | 1,5 | pendiente |
| U3 | Usuarios simulados y curva: `simulacion/`, `medir_personalizacion.py`, `test_curva.py` | personalizacion | U2 | Objetivos de `personalizacion.md` §5 (semilla 0 en el test, 10 semillas en `/medir`) | `/medir personalizacion` | 10 nov | H2 | 2 | pendiente |
| D2 | `crear_borrador` con Sonnet 5.5 (salida estructurada, un reintento, `no_soportado`) | modulos | E4 | Con cliente falso, la frase de la demo da `recibo_al_alza` válido; pedir un producto → `no_soportado`; una inyección en la descripción no cambia las reglas | `pytest tests/test_creacion.py` | 10 nov | H2 | 1,5 | pendiente |
| F1 | `/app`: `Activacion`, `RelojDemo` (SSE de `reproducir`), bandejas «Ahora» y «Resumen» y contador de silenciadas | frontend | E10 | El guion 0:00-0:45 funciona contra el backend | `npm run build` y la app a mano | 10 nov | H3 | 1,5 | pendiente |
| F2 | Llamada en texto: `/app/llamada/[propuestaId]`, `Llamada`, `Transcripcion`, `TarjetaAccion`, respuestas rápidas e insignia «IA» | frontend | F1, V1 | Cena → «Sí» → tarjeta → «Confirmar» → resultado simulado | `npm run build` y la app a mano | 10 nov | H3 | 2 | pendiente |
| F3 | «Por qué te aviso», «Lo que he aprendido» (ver, apagar, borrar, olvidar todo) y saldos con amigos | frontend | F2, U1, U2 | Se ven los motivos; borrar un hecho llama al `DELETE`; Marcos «pendiente: 24 €» | `npm run build` y la app a mano | 10 nov | H3 | 1,5 | pendiente |
| F4 | `/banco`: `TablaModulos`, `NuevoModulo` (SSE), `PruebaEnSeco` y aprobar | frontend | E8 (*stubs*), D2, D3 | La frase de la demo enseña los pasos y el informe y activa el módulo | `npm run build` y la app a mano | 10 nov | H3 | 2 | pendiente |
| F5 | `/jurado`: precisión por detector, molestias evitadas y curva de aprendizaje (SVG) | frontend | E9, U3 | Pinta `/metricas/*`; legible a 3 m | `npm run build` y la app a mano | 10 nov | H3 | 1,5 | pendiente |
| V3 | Evals de la llamada: `evals/casos_llamada.yaml` (aviso de IA, sin cifras inventadas, inyección en nota de Bizum, acción no ofrecida, no confirma por voz) y `ejecutar.py --conjunto llamada` | voz | V1 | Todos los casos en verde | `/evals llamada` (clave 3) | 10 nov, noche | H3 | 1,5 | pendiente |
| X1 | Cerrar el MVP: integrar, `pytest -q`, `/medir todo`, `/evals`, `revisor`, desplegar y puerta **MVP completo** | todas | H1-H3 | Todo en verde y la demo de 3 minutos en texto de principio a fin | Los cuatro comandos y el guion a mano | 10 nov, noche | — | 1 | pendiente |

**Dueños de archivos el 10 nov** (no se cruzan): **H1** `backend/motor/`, `backend/escenarios/`, `evals/medir_motor.py`, `backend/modulos/{catalogo/, prueba_seco.py, registro.py}`, `backend/api/rutas_banco.py`. **H2** `backend/voz/`, `backend/personalizacion/`, `backend/plataforma/orquestador.py`, `backend/agente/registro.py`, `backend/modulos/creacion.py`, `backend/api/{rutas_voz, rutas_copiloto}.py`, `evals/medir_personalizacion.py`. **H3** `frontend/`, `evals/casos_llamada.yaml`, `evals/ejecutar.py`. Cada hilo, con sus tests. Solo el orquestador toca `tipos.py`, `CONTRATO.md`, `ARQUITECTURA.md` y este archivo. El 9 nov: H1 motor, escenarios y `sinteticos.py`; H2 módulos, acciones y después la API; H3 personalización, orquestador y después el frontend.

### 11 y 12 nov: pulido, congelación (11, 14:00) y entrega
| Id | Tarea | Zona | Depende de | Criterio de aceptación | Cómo se verifica | Día | Hilo | h | Estado |
|---|---|---|---|---|---|---|---|---|---|
| F6 | Llamada de voz: `@elevenlabs/react` con versión fija, `startSession` con token y variables, herramientas de cliente y «Prefiero escribir» | frontend | P3, V2, F2 | Lista de `experiencia.md` §6.3 completa; la cena se resuelve por voz | A mano con auriculares (≤ 5 min de voz) | 11 nov, mañana | H3 | 2 | pendiente |
| Q1 | Medir la latencia y ajustar el prompt de voz; anotarlo en `experiencia.md` §6.6 | voz | F6 | Turno < ~2 s; `preparar` < 500 ms | Cronómetro y pestaña Red | 11 nov, mañana | mano | 0,5 | pendiente |
| Q2 | Pruebas con compañeros del guion completo y arreglos | demo | X1 | Fallos cerrados o aceptados por escrito | Sesiones de 10 minutos | 11 nov, mañana | H1 | 2 | pendiente |
| Q3 | `MODO_DEMO=grabar` del modo texto y del borrador del módulo; probar los cuatro niveles del plan B | demo | X1 | Sin clave de Claude, la demo funciona con `reproducir` | A mano quitando la clave | 11 nov, mañana | H2 | 1 | pendiente |
| Q4 | Vídeo de respaldo de la llamada completa | demo | F6 | Vídeo de ≤ 3 minutos guardado | Verlo entero | 11 nov, mañana | mano | 0,5 | pendiente |
| Q5 | Revisión final de seguridad y cumplimiento (claves, enmascarado, aviso de IA, sin productos) | todas | X1 | `revisor` sin bloqueantes | `revisor` y test de claves | 11 nov, 13:00 | H2 | 1 | pendiente |
| Z1 | README, `docs/DEMO.md` y guion (`pitch`) | demo | Q2 | Cualquiera arranca la demo con el README | Leerlo en limpio | 11 nov, tarde | — | 1,5 | pendiente |
| Z2 | Ensayo 1 cronometrado; solo se cambian textos | demo | Z1 | ≤ 3 minutos | Cronómetro | 11 nov, tarde | mano | 1 | pendiente |
| Z3 | Despliegue final y prueba desde otro equipo | demo | Q5 | URL públicas con `POST /demo/cargar` | A mano | 11 nov, tarde | — | 0,5 | pendiente |
| Z4 | Ensayo 2 con voz real y vídeo de la entrega | demo | Z2, Z3 | Vídeo final | Verlo | 12 nov | mano | 2 | pendiente |
| Z5 | Entrega según `reto/RETO.md` | demo | Z4 | Todo lo que pide la entrega | Lista del reto | 12 nov | — | 0,5 | pendiente |

### Opcionales (solo si un hilo acaba antes el 10 nov; nada después de la congelación)
| Id | Tarea | Zona | Hilo | h |
|---|---|---|---|---|
| O1 | Memoria de la llamada con Haiku 5.5 (`memoria.py`, filtros de sensibles e instrucciones) | personalizacion | H2 | 1,5 |
| O2 | `posible_estafa` con escenarios y trampas | motor | H1 | 1,5 |
| O3 | Herramienta `consultar` de la llamada (`/voz/herramientas/consultar`) | voz | H2 | 1 |
| O4 | Deshacer una acción (`/acciones/deshacer` y botón en la tarjeta) | modulos + frontend | H2 → H3 | 1 |
| O5 | Editar el texto de un hecho aprendido | frontend | H3 | 0,5 |
| O6 | Pausar módulos y registrar quién aprueba en la consola | modulos + frontend | H1 → H3 | 1 |
| O7 | Varios amigos con saldo acumulado en `/app/amigos` | frontend | H3 | 0,5 |

**Recortes si el 10 nov a las 17:00 vamos tarde** (en este orden; `experiencia.md` §10, `modulos.md` §9 y `personalizacion.md` §7): (1) aprobar = activar con un clic, sin estados; (2) prueba en seco precalculada con animación; (3) `subida_recibo` fuera y el módulo en directo sobre `cobro_duplicado`; (4) `/jurado` con imágenes de `evals/resultados/`; (5) F6: voz solo en vídeo y demo en texto. No se recorta: aviso de IA, confirmación por botón, la cena de Lucía y el cierre con métricas.

**Cuentas**: 9 nov, 19,5 h de sesión en ~8,5 h de reloj (16:15-~01:00, tres hilos); 10 nov, 34 h (H1 11, H2 10, H3 10, P3 2 a mano y X1 1) en ~13,5 h de reloj; 11 nov, 7 h de pulido antes de las 14:00 y 3 h por la tarde; 12 nov, 2,5 h. Holgura: solo los opcionales (7 h) y la mañana del 11.

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
