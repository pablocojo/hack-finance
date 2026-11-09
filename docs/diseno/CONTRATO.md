# Contrato compartido del diseño

9 de noviembre de 2026. Lo escribe el orquestador antes de repartir el diseño. Los subagentes que diseñan cada parte lo respetan; si algo no encaja, lo proponen en una sección «Cambios propuestos al contrato» de su documento en vez de cambiarlo por su cuenta. `/planificar` resuelve esas propuestas y actualiza este archivo.

Cambios ya aceptados: confirmar una acción es un botón con un token de un solo uso (`preparar` → `TarjetaConfirmacion` → `ejecutar`), propuesto en `experiencia.md`. En `/planificar` (9 nov, tarde) se aceptan los siete cambios de `experiencia.md` y se fijan la lista de acciones, los módulos del MVP, la persistencia y el reparto de responsabilidades (sección «Decisiones de /planificar», al final).

## La idea

Nombre provisional: **Copiloto** (la marca la eligen los compañeros). Es una plataforma B2B para bancos que vive dentro de la app del banco. No hay que instalar nada ni registrarse: el cliente ve un aviso, lo activa y elige qué quiere que vigile.

1. Un **motor** lee los movimientos de cada cliente y los convierte en **momentos** con sentido: un cobro duplicado, una suscripción que se renueva, una cena pagada que tus amigos aún no te han devuelto, un recibo que sube, que te vas a quedar en negativo o una posible estafa.
2. Los **módulos** se enchufan al motor. Cada uno escucha unos tipos de momento y propone qué decir y qué hacer.
3. La **personalización** decide si merece la pena interrumpir a esa persona en concreto, y aprende de cómo responde.
4. Si interrumpe, llega una **notificación**. Al pulsarla se abre una **llamada de voz** con un agente que ya conoce el contexto y lo resuelve en el momento con acciones de una **lista cerrada**: bloquear los cobros de un comercio, pedir un Bizum, mover dinero o preparar la baja. Si no puedes hablar, por texto.
5. El **banco** puede crear módulos nuevos describiéndolos en lenguaje natural. Se prueban en seco con datos, pasan evals y alguien del banco los aprueba.

Lo valioso, por este orden: el motor de detección y razonamiento, que aprenda de cada usuario y que todo eso sirva para cualquier módulo nuevo sin escribir código específico.

Frase del pitch: «Los demás te enseñan tus finanzas. Nosotros te llamamos solo cuando hay algo que resolver, y lo resolvemos en la llamada».

## Por qué gana

- Rúbrica (sobre 100): innovación y viabilidad 30, uso de IA frontera con lenguaje **y audio** 15, experiencia de usuario y accesibilidad 15, implementación técnica y código 30, presentación 10.
- Casi todos los equipos harán chatbots reactivos o gestores con gráficos. Personetics vende a bancos consejos proactivos, pero avisa y no resuelve; Splitwise o Tricount exigen instalar otra app y apuntar cada gasto a mano.
- Estrella de la demo: **gastos compartidos**. Pagas 120 € en una cena, te llegan tres Bizums de 24 € y el sistema deduce que falta una persona, te avisa y en la llamada le pide el dinero.

## Flujo de principio a fin

```
movimiento nuevo ─> MOTOR: normalizar ─> enriquecer ─> detectores ─> razonador ─> Momentos
Momento ─> MÓDULOS que lo escuchan ─> Propuestas
Propuesta ─> PERSONALIZACIÓN (ModeloUsuario) ─> Decisión: notificar ya | resumen | silencio
notificar ─> app (notificación) ─> llamada de voz o texto ─> Acción (lista cerrada, con confirmación)
resultado y respuesta del usuario ─> Feedback ─> PERSONALIZACIÓN aprende
```

El proceso es **en línea y con reloj simulado**: el motor recibe los movimientos día a día y solo ve el pasado. Así la demo puede reproducir semanas en segundos y las evals miden cuándo se detecta cada cosa.

## Tipos compartidos

Viven en `backend/plataforma/tipos.py` (modelos de pydantic, que ya viene con FastAPI). El dinero va en `Decimal`; las fechas, en ISO.

| Tipo | Campos |
|---|---|
| `Movimiento` | `id`, `fecha`, `concepto`, `comercio`, `importe` (negativo = cargo), `categoria`, `saldo?`, y nuevos opcionales: `canal` (`tarjeta`, `recibo`, `bizum`, `transferencia`, `cajero`), `contraparte` (persona o empresa en Bizum y transferencias), `nota` (el concepto que escribe quien envía un Bizum) |
| `MovimientoEnriquecido` | `Movimiento` + `comercio_normalizado`, `contraparte_normalizada`, `categoria` final, `serie_id?` (si pertenece a una serie recurrente), `etiquetas` |
| `Momento` | `id`, `tipo`, `usuario_id`, `fecha`, `movimientos` (ids que lo prueban), `datos` (campos propios del tipo), `confianza` (0-1), `impacto_eur?`, `explicacion` (una frase de por qué), `detector`, `version` |
| `Propuesta` | `id`, `modulo_id`, `momento_id`, `usuario_id`, `titulo`, `mensaje_notificacion`, `contexto_llamada` (lo que el agente de voz necesita saber), `acciones_ofrecidas` (lista de `{accion_id, parametros, requiere_confirmacion, limites}`; `limites` = importe máximo y contrapartes permitidas, que `preparar` valida en el servidor), `valor_estimado_eur`, `urgencia`, `tipo_momento`, `comercio?`, `contraparte?`, `confianza` (copiados del momento para que `decidir` sepa a qué se refiere) (`alta`, `media`, `baja`), `creada` |
| `Decision` | `propuesta_id`, `accion` (`notificar_ahora`, `resumen`, `silenciar`), `puntuacion`, `probabilidad_util`, `motivos` (frases legibles), `politica` (versión) |
| `Feedback` | `propuesta_id`, `usuario_id`, `resultado` (`resuelta`, `vista_sin_accion`, `rechazada`, `ignorada`, `no_avisar_tipo`, `no_avisar_comercio`, `no_avisar_contacto`, `falso_positivo`), `canal` (`voz`, `texto`, `app`), `fecha`, `nota?` |
| `TarjetaConfirmacion` | `accion_id`, `propuesta_id`, `titulo`, `parametros_legibles`, `simulada`, `token_confirmacion` (de un solo uso), `caduca`. La genera `preparar` sin efectos; la app la pinta como un botón |
| `ResultadoAccion` | `accion_id`, `ok`, `mensaje`, `datos`, `simulada` (siempre `true` en el hackathon), `deshacer?` |
| `ModeloUsuario` | Lo diseña la personalización. Mínimo: `usuario_id`, `modulos_activos`, `consentimientos`, `preferencias` (silencios, horario), líneas base, contactos, series recurrentes, estadísticas de respuesta y memoria en texto para el agente. Además: `hechos_aprendidos: list[{id, texto, origen, activo}]` (lo que se ve, edita y borra en «Lo que he aprendido de ti») y `amigos: list[{contraparte, saldo, propuesta_origen, estado}]` |

### Tipos de momento del MVP y sus `datos` mínimos

| Tipo | `datos` mínimos |
|---|---|
| `cargo_duplicado` | `comercio`, `importe`, `fechas`, `ids`, `dias_entre`, `canal`, `fecha_limite_devolucion?` (solo recibos: cargo + 8 semanas) |
| `renovacion_proxima` | `comercio`, `importe`, `periodicidad`, `fecha_prevista`, `dias_hasta`, `veces_cobrado` |
| `subida_recibo` | `comercio`, `importe_actual`, `importe_habitual`, `subida_eur`, `subida_pct`, `serie_id` |
| `saldo_negativo_previsto` | `fecha_prevista`, `saldo_minimo`, `cargos_previstos` (lista), `importe_para_cubrir` |
| `posible_estafa` | `contraparte`, `importe`, `canal`, `senales` (lista), `contraparte_nueva`, `veces_lo_habitual` |
| `gasto_compartido` | `pago_id`, `comercio`, `importe_total`, `fecha`, `reembolsos` (lista de `{contraparte, importe, id}`), `personas_estimadas`, `faltan`, `importe_pendiente`, `candidatos` |
| `ingreso_extra` | `subtipo` (`primera_nomina`, `devolucion_hacienda`, `otro`), `importe`, `contraparte` |
| `viaje_detectado` | `comercio`, `importe`, `fecha_viaje?`, `destino?` (solo para el módulo secundario de seguro) |

El motor puede añadir campos; no puede quitar ni renombrar estos sin proponerlo.

## Interfaces entre partes

```python
# backend/motor
def procesar(usuario_id: str, nuevos: list[Movimiento], hoy: date) -> list[Momento]: ...
def cargar_historial(usuario_id: str, historial: list[Movimiento], hoy: date) -> None: ...  # al activar: aprende series sin avisar
def exportar_estado(usuario_id: str) -> dict: ...; def importar_estado(usuario_id: str, estado: dict) -> None: ...; def reiniciar(usuario_id: str) -> None: ...

# backend/modulos
def proponer(momento: Momento, modelo: ModeloUsuario) -> list[Propuesta]: ...

# backend/personalizacion
def decidir(propuesta: Propuesta, modelo: ModeloUsuario, ahora: datetime) -> Decision: ...
def aprender(feedback: Feedback, modelo: ModeloUsuario) -> ModeloUsuario: ...  # pura: no guarda; guarda el orquestador

# backend/acciones: el agente solo prepara; ejecuta el botón del usuario con el token
def preparar(accion_id: str, parametros: dict, propuesta_id: str) -> TarjetaConfirmacion: ...
def ejecutar(token_confirmacion: str) -> ResultadoAccion: ...  # valida token, propuesta y acción permitida

# backend/plataforma/orquestador.py: une todo
def avanzar_dia(usuario_id: str, hoy: date) -> list[Decision]: ...
def reproducir(usuario_id: str, dias: int) -> Iterator[Evento]: ...  # emite dia, momento, propuesta, decision (SSE)

# backend/modulos: ciclo de vida de un módulo creado por el banco
def crear_borrador(descripcion: str) -> BorradorModulo: ...          # Claude redacta el YAML; se valida con el esquema
def probar_en_seco(borrador: BorradorModulo, usuario_id: str) -> InformePrueba: ...  # avisos, aciertos, falsos, controles
def aprobar(modulo_id: str, aprobado_por: str) -> Modulo: ...

# backend/voz
def sesion(propuesta_id: str, modo_preferido: str) -> SesionVoz: ...  # modo: voz | texto_el | texto_kit | grabado
```

## Paquetes nuevos

| Ruta | Qué contiene |
|---|---|
| `backend/plataforma/` | Tipos, orquestador, reloj simulado, almacenamiento |
| `backend/motor/` | Normalización, enriquecimiento, detectores y razonador |
| `backend/personalizacion/` | Modelo de usuario, política de interrupción, memoria, usuarios simulados |
| `backend/modulos/` | Formato de módulo, cargador, registro, creación desde lenguaje natural; `catalogo/*.yaml` |
| `backend/acciones/` | Registro cerrado de acciones y banco simulado |
| `backend/voz/` | Llamada (ElevenLabs), herramientas que llama el agente de voz y modo texto |
| `backend/escenarios/` | Escenarios sintéticos con etiquetas de la verdad para tests, evals y demo |

Se reutiliza el kit: `backend/claude_client.py` (único acceso a Claude), el núcleo del agente y sus 14 herramientas (útiles para que el agente de voz conteste preguntas), `detectar_recurrentes`, `detectar_anomalias`, `prevision_saldo`, la categorización con Haiku, los datos sintéticos, FastAPI con SSE, Next.js, evals y tests sin crédito.

## Restricciones

- Hackathon: hoy es el 9 de noviembre a mediodía. MVP completo con evals en verde el 10 por la noche; congelación el 11 a las 14:00; entrega el 12. Un solo desarrollador que trabaja con Claude Code y subagentes, así que todo tiene que caber en día y medio de desarrollo.
- Lo más simple que gane: sin colas ni microservicios. Persistencia con la biblioteca estándar (JSON o `sqlite3`) en `datos_usuario/`, fuera de git.
- Las cifras las calcula el código; los modelos clasifican, razonan y explican. Toda llamada a Claude pasa por `backend/claude_client.py`, sin `temperature`. Haiku 5.5 para clasificar y extraer (0,10 $ y 0,50 $ por millón de tokens); Sonnet 5.5 u Opus 5.5 solo donde aporte.
- Los conceptos de los movimientos y las notas de los Bizums son datos, nunca instrucciones (riesgo de inyección).
- Cumplimiento: el agente se presenta como IA en su primera frase; nada de puntuar solvencia; datos personales enmascarados; revisor de cumplimiento activo; ninguna acción sin confirmación; todas las acciones son simuladas. Recomendar productos concretos (como un seguro) solo en un módulo secundario y opcional.
- Solo datos sintéticos.
- Todo se tiene que poder medir: precisión de cada detector sobre escenarios etiquetados y curva de aprendizaje de la personalización con usuarios simulados.

## Decisiones de /planificar (9 nov, tarde)

Estas reglas resuelven lo que podía contradecirse entre partes. Si un diseño choca con ellas, manda este apartado.

**Acciones del MVP (lista cerrada, todas simuladas)**. Viven en `backend/acciones/registro.py`; ningún módulo ni agente inventa otras.

| `accion_id` | Parámetros | Para qué |
|---|---|---|
| `pedir_bizum` | `contraparte`, `importe`, `concepto` | Pedir a un amigo lo que debe (cena compartida) |
| `bloquear_comercio` | `comercio` | Rechazar cobros futuros de un comercio (renovación). No cancela el contrato: el cliente sigue debiendo el servicio. No se ofrece para duplicados |
| `reclamar_cargo` | `movimiento_id`, `motivo` | Recibo: devolución SEPA sin motivo hasta 8 semanas. Tarjeta: reclamación al comercio o contracargo, sin plazo garantizado. El texto de la tarjeta cambia según el canal |
| `mover_dinero` | `origen` (`ahorro`), `destino` (`cuenta`), `importe` | Cubrir un saldo negativo previsto |
| `preparar_baja` | `comercio` | Dejar redactada la solicitud de baja de un servicio para que el cliente la envíe |
| `recordar` | `cuando`, `texto` | Recordatorio sin efectos en la cuenta |

**Módulos del MVP** (`backend/modulos/catalogo/*.yaml`): `cena_compartida` (`gasto_compartido`, la estrella), `cobro_duplicado` (`cargo_duplicado`), `renovacion` (`renovacion_proxima`) y `colchon` (`saldo_negativo_previsto`). El módulo que el banco crea en directo **solo usa tipos de momento que ya existen** y acciones de la lista.

**Responsabilidades**
- El **motor** no sabe nada de usuarios más allá de su historial: detecta y explica. No decide si se avisa.
- Los **módulos** convierten un momento en propuestas y fijan `acciones_ofrecidas` con sus `limites`. No calculan cifras nuevas: usan las de `Momento.datos`.
- La **personalización** decide (`Decision` con `motivos`) y aprende de `Feedback`. Es la dueña de `ModeloUsuario`, incluidos `amigos` (se crean a partir del momento `gasto_compartido` notificado y se saldan cuando entra el Bizum) y `hechos_aprendidos`.
- Las **acciones** validan en el servidor: token de un solo uso, que la acción esté en `acciones_ofrecidas` de esa propuesta y que los parámetros respeten `limites`. Todo queda en un registro de auditoría.
- El **orquestador** une las piezas y es el único que escribe en almacenamiento.

**Persistencia**: un JSON por usuario en `datos_usuario/<usuario_id>/` (modelo, momentos, propuestas, decisiones, feedback, auditoría), fuera de git. Sin base de datos.

**Escenarios**: cada escenario es un archivo en `backend/escenarios/` con movimientos sintéticos y etiquetas de la verdad (`{tipo, fecha_detectable, ids}`), con trampas (casos que **no** deben avisar). Las mismas piezas alimentan tests, `/medir` y la demo.

**Usuarios de la demo**: `lucia` (la cena: paga 120 €, recibe tres Bizums de 24 €, falta Marcos) y usuarios simulados para la curva de aprendizaje.

**Modelos**: Haiku 5.5 para clasificar, normalizar comercios dudosos y redactar textos cortos; Sonnet 5.5 para la creación de módulos desde lenguaje natural y el agente de texto. Todos los detectores del MVP son deterministas (pandas y `Decimal`); Claude solo explica y redacta.

### Cambios aceptados de los borradores (9 nov, tarde)

- **Motor**: `cargar_historial`, `exportar_estado`/`importar_estado` y `reiniciar` (el orquestador sigue siendo el único que escribe). Los importes dentro de `datos` van **en positivo**. El `id` de cada movimiento es único y estable, y las listas `ids` van ordenadas por fecha. Campos añadidos: `cuota` en `gasto_compartido`, `serie_id`, `saldo_actual` e `ingresos_previstos` en `saldo_negativo_previsto`. `candidatos` es `list[{contraparte, importe}]`. En `saldo_negativo_previsto`, `impacto_eur` = `importe_para_cubrir`. Pagos con cuotas desiguales: fuera del MVP (no avisa). `backend/datos/sinteticos.py` gana `anomalias=False`.
- **`subida_recibo` entra en el MVP** (quinto detector): lo necesita el módulo `recibo_al_alza` que el banco crea en directo. Si no llega, el módulo en directo usa `cargo_duplicado`.
- **Módulos**: `limites = {importe_max?, contrapartes?}`; `ResultadoAccion.deshacer = {resultado_id, disponible_hasta}` y `acciones.deshacer(resultado_id)`; tipos `BorradorModulo`, `InformePrueba` y `Modulo` en `tipos.py`. Token de 10 minutos ligado al hash de los parámetros.
- **Personalización**: `Propuesta` lleva `tipo_momento`, `comercio?`, `contraparte?` y `confianza`; `aprender` es pura y devuelve el modelo; funciones `registrar_decision`, `observar`, `registrar_accion` y `memoria_para_agente`. `HechoAprendido = {id, clave, texto, origen, activo, creado}`; `Amigo` añade fechas, concepto y estado. `ignorada` la genera el orquestador a las 48 h sin respuesta. Se aprende por tipo de momento, no por módulo: un módulo nuevo hereda lo aprendido.
- **Voz**: tipo `SesionVoz = {modo, token?, signed_url?, variables, token_sesion, caduca}`; variables de entorno `ELEVENLABS_API_KEY`, `ELEVENLABS_AGENT_ID` y `MODO_DEMO`. No hay herramienta `terminar_llamada`: colgar sin acción es `vista_sin_accion`.
- **Hechos sobre terceros**: nada que valore a otra persona («Marcos tarda en pagar»). Como mucho un dato operativo para el recordatorio («los Bizums de este grupo suelen llegar en una semana»), pendiente de `experto-banca`.

### Revisión de `experto-banca` (9 nov, tarde)

- **Terceros**: el agente nunca valora a otra persona («el que suele retrasarse» queda prohibido). Los amigos guardan nombre enmascarado, `estado` y `saldo`; se borran al saldarse o a los 90 días; se ven y se borran en «Lo que he aprendido». El minilenguaje no accede a `modelo.contactos`.
- **`pedir_bizum`** es una solicitud que el otro acepta o rechaza; concepto neutro («Tu parte de X»); error controlado si el destinatario no tiene Bizum; `deshacer` solo «si el banco lo soporta».
- **SCA**: el botón con token es la confirmación de la demo. En producción, las acciones con efecto lanzan SCA (PSD2 art. 97, RTS 2018/389) con vínculo dinámico; en la demo se dice «aquí iría la huella». Copiloto vive dentro del banco: no necesita licencia AIS/PIS; un proveedor externo sería encargado del tratamiento (RGPD art. 28).
- **`posible_estafa`** no sale en la demo; si se programa, la propuesta dice «llama al banco», no «lo resolvemos».
- **`subida_recibo`**: el texto dice «ha subido», nunca «te han cobrado de más».
- **Primera frase**: la llamada la abre el cliente desde el aviso; cada tarjeta de acción lleva la insignia «Simulado».
- Las fuentes normativas se contrastan en EUR-Lex y bizum.es antes de ponerlas en el pitch.

### Revisión final (`revisor`, 9 nov, tarde). Manda sobre los documentos de diseño

- **Hora de las decisiones**: `avanzar_dia(usuario_id, hoy, ahora: datetime | None = None)`; si falta, `ahora = hoy 20:30`. `reproducir` acepta `pausar_en: tipo_momento | None` para que el reloj se pare en la notificación de la cena.
- **`limites`**: `{importe_max?: Decimal, contrapartes?: list[str]}`. En `cena_compartida`, `contrapartes: ["{item.contraparte}"]`.
- **`cargo_duplicado.datos`** añade `id_segundo` (las plantillas no admiten índices).
- **`recibo_al_alza`** lleva `valor_estimado_eur: momento.datos.subida_eur`; si un módulo no lo pone, se copia `Momento.impacto_eur`.
- **Notas de Bizum**: no salen del motor hacia módulos ni llamada (solo la contraparte normalizada). Marcador único de datos en todo prompt: `<datos>…</datos>`.
- **Token de confirmación**: nunca llega a ningún modelo (ni Claude ni el LLM de ElevenLabs). La herramienta de cliente `preparar_accion` devuelve al agente solo `{preparada, titulo}`; el token va solo al componente `TarjetaAccion`. Caduca a los **10 minutos**. `ejecutar` comprueba además que el `usuario_id` coincide con el del token. Hay test.
- **`MODO_DEMO`**: `off | grabar | reproducir`. Al reproducir se graba el texto y la llamada a `preparar_accion`, y `preparar` se ejecuta de verdad para emitir un token válido.
- **API desplegada**: cabecera `X-Demo-Key` en las rutas que reinician o gastan (`/demo/cargar`, `/banco/modulos/*`, `/voz/*`) y tope de peticiones a `/banco/modulos/borrador`. No es seguridad real (la clave va en el frontend); solo evita abusos durante la demo.
- **`Decimal` y JSON**: el dinero viaja como cadena. El evaluador del minilenguaje convierte con `Decimal(str(x))` los campos numéricos de `campos_momento.py`. Hay test de ida y vuelta por JSON.
- **Endpoints**: la fuente es `docs/ARQUITECTURA.md` §3 (`/usuarios/{id}/propuestas/{pid}`, `usuario_id` en el cuerpo, nivel 3 en `/voz/texto`). Las métricas se sirven desde los JSON de `evals/resultados/`, que se versionan (Render tiene disco efímero).
- **`Amigo`**: sin concepto (fechas, estado, saldo y contraparte enmascarada).
- **Nombres de la demo**: el restaurante es «La Tasca» en el escenario y en el guion; el campo es `candidatos` (no `candidato_principal`).
- **Excepción documentada**: el agente de voz de ElevenLabs usa su propio Claude, fuera de `claude_client.py` y del revisor de cumplimiento. Mitigación: primer mensaje fijo con el aviso de IA, herramientas de la lista cerrada, sin token y confirmación por botón.
