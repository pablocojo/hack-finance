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

- Hackathon: hoy es el 9 de noviembre a mediodía. MVP completo con evals en verde el 10 por la noche; congelación el 11 a las 14:00; **entrega completa el 11 a las 23:59** (presentación el 12). Un solo desarrollador que trabaja con Claude Code y subagentes, así que todo tiene que caber en día y medio de desarrollo.
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
| `cancelar_suscripcion` | `comercio`, `bloquear_cobros` | Baja guiada (enlace y pasos) y, si el cliente quiere, rechazo de los cobros con tarjeta de ese comercio. Sustituye a `preparar_baja` |
| `recordar` | `cuando`, `texto` | Recordatorio sin efectos en la cuenta |

**Módulos del MVP** (`backend/modulos/catalogo/*.yaml`): `gasto_compartido` (`gasto_compartido`, la estrella), `cobro_duplicado` (`cargo_duplicado`), `renovacion` (`renovacion_proxima`) y `fin_de_prueba` (`prueba_gratuita`); `colchon` (`saldo_negativo_previsto`) es opcional. El módulo que el banco crea en directo **solo usa tipos de momento que ya existen** y acciones de la lista.

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
- **`limites`**: `{importe_max?: Decimal, contrapartes?: list[str]}`. En `gasto_compartido`, `contrapartes: ["{item.contraparte}"]`.
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

## Cambios de Pablo (9 nov, noche). Mandan sobre todo lo anterior

**Nombre**: el producto se llama **Meisam** (sustituye a «Copiloto» en textos, app y pitch). Los nombres internos del código y de las skills no cambian. El banco ficticio sigue siendo Banco Aurora.

**1. Perfil de vida: la personalización también razona dentro del motor.** Ya no solo decide si interrumpir.
- Tipo nuevo `PerfilUsuario` dentro de `ModeloUsuario` (dueña: personalización). Lo **calcula el código** a partir del historial: `dia_cobro_nomina?`, `ingreso_mensual_tipico?`, `gasto_tipico_por_categoria`, `ticket_tipico`, `comercios_habituales`, `grupos` (amigos que dividen juntos y cómo), `umbral_relevante_eur` (qué es «mucho» para esta persona), `suscripciones_activas`, y `resumen_vida` (3-4 frases redactadas por Haiku a partir de esas cifras, sin inferir categorías sensibles del RGPD art. 9). Se ve, se edita y se borra en «Lo que he aprendido de ti».
- `personalizacion.perfilar(historial, hoy, perfil_anterior) -> PerfilUsuario` (pura). El orquestador lo llama al activar y una vez por semana simulada.
- `motor.procesar(usuario_id, nuevos, hoy, perfil: PerfilUsuario | None = None)`. Los detectores usan el perfil para **umbrales personales** (p. ej. duplicado relevante según `ticket_tipico`; candidatos de la cena según `grupos`), y el razonador añade a `Momento` dos campos: `impacto_relativo?` (p. ej. fracción del dinero que queda hasta la nómina, calculada por código) y `contexto_personal?` (frase por plantilla: «Te quedan 9 días hasta la nómina y son el 10 % de lo que te queda»). Sin perfil, el motor usa los umbrales por defecto (arranque en frío).

**2. Acciones con sentido para el contexto.** La lista sigue cerrada, pero cada módulo ofrece solo las 2 o 3 acciones que encajan con ese momento, y `personalizacion.ordenar_acciones(propuesta, modelo) -> Propuesta` las ordena según lo que esa persona suele elegir. El agente propone primero la de arriba.

**3. Cancelar suscripciones.** El banco no puede dar de baja un contrato con el comercio, pero sí guiar la baja y cortar los cobros de tarjeta.
- `preparar_baja` se sustituye por **`cancelar_suscripcion`** (`comercio`, `bloquear_cobros: bool`): prepara la **baja guiada** (enlace y pasos de ese servicio, de `InfoComercio`) y, si el cliente quiere, bloquea los cobros recurrentes de ese comercio en la tarjeta como red de seguridad (servicios de cancelación de pagos recurrentes de Visa y Mastercard). El texto deja claro que la baja la confirma el cliente en el servicio.
- Lista cerrada final: `pedir_bizum`, `cancelar_suscripcion`, `bloquear_comercio`, `reclamar_cargo`, `mover_dinero`, `recordar`.

**4. Pruebas gratuitas: tipo de momento nuevo `prueba_gratuita` (entra en el MVP).**
- Señal: al dar la tarjeta para una prueba, el comercio pide al banco emisor una **verificación de 0 €** (o 1 € que luego devuelve). `Movimiento` gana `tipo_operacion?: cargo | verificacion | devolucion`. Si la verificación es de un comercio de suscripciones y no hay serie de cobros suyos, empieza una prueba.
- Otra fuente: el cliente lo dice en la app o en la llamada («he empezado la prueba de X»), que crea el mismo momento con `fuente: usuario`.
- `datos`: `comercio`, `fecha_alta`, `dias_prueba`, `fecha_primer_cobro`, `dias_hasta`, `importe_previsto?`, `fuente` (`verificacion` | `usuario`), `fuente_duracion` (`catalogo` | `web` | `por_defecto`), `verificacion_id?`. Avisa 2-3 días antes del primer cobro.
- Módulo del catálogo `fin_de_prueba`: ofrece `cancelar_suscripcion` y `recordar`.
- **MVP de detectores**: `gasto_compartido`, `cargo_duplicado`, `renovacion_proxima`, `subida_recibo` y `prueba_gratuita`. **`saldo_negativo_previsto` sale del MVP** (queda en «si sobra», con el módulo `colchon` y `mover_dinero`). Módulos del catálogo del MVP: `gasto_compartido`, `cobro_duplicado`, `renovacion` y `fin_de_prueba`.

**5. Búsqueda en internet (conocimiento de comercios).**
- `backend/motor/conocimiento.py`: `info_comercio(nombre) -> InfoComercio {nombre, tipo, es_suscripcion, dias_prueba?, precio_tras_prueba?, precio_persona? (K1 d, 11 nov), url_baja?, pasos_baja?, fuentes, consultado}`. Primero mira la caché versionada `backend/datos/comercios_conocidos.json` (precargada para la demo); si no está, usa la herramienta de búsqueda web de Claude a través de `claude_client.py`, con salida estructurada validada (URL `https`), y guarda el resultado.
- Solo se busca el **nombre del comercio**, nunca datos del cliente. Lo que llega de la web son datos, nunca instrucciones (`<datos>`). Las cifras que se usen (precio, días) se muestran con su fuente.
- Fuera del camino caliente: los detectores solo leen la caché; si un comercio no está, el orquestador lo pide (una vez) y el detector lo usa al día siguiente. Los tests no salen a internet (caché o cliente falso). Variable `BUSQUEDA_WEB=on|off`.

**6. Aviso de IA.** La IA **no lo dice en voz alta**. Solo una insignia «IA» discreta y visible en la pantalla de la llamada y en el modo texto. El primer mensaje del agente es fijo y neutro («Hola {{nombre}}, {{titulo_aviso}}»; el backend manda en `titulo_aviso` la frase entera: «me has abierto desde el aviso: <título>. ¿Lo vemos?» o, sin aviso, «¿qué quieres repasar de tus cuentas con amigos?»). El resto de reglas de cumplimiento se mantiene en lo mínimo.

### Cambios aceptados de los diseños tras los cambios de Pablo (9 nov, noche)

- **Motor**: funciones nuevas `enriquecer(movimientos) -> list[MovimientoEnriquecido]` (pura), `registrar_prueba(usuario_id, comercio, fecha_alta, dias?)` (cuando el cliente lo dice), `cerrar_prueba(usuario_id, comercio, motivo)` y `comercios_pendientes(usuario_id) -> list[str]` (los que el orquestador manda buscar en la web, como mucho 20 al día). `prueba_gratuita.fuente_duracion` admite `usuario | catalogo | web | por_defecto`. `InfoComercio` añade `origen` (`catalogo | web | desconocido`). Los umbrales personales se calculan en una sola función, `parametros.ajustar(params, perfil)`; sin perfil, el motor se comporta igual que sin personalización (test de regresión).
- **Quién cierra una prueba**: el orquestador llama a `motor.cerrar_prueba` cuando `ejecutar` de `cancelar_suscripcion` devuelve `ok`.
- **`Grupo`** (único formato, lo calcula `perfilar` y lo usa el motor): `{miembros: list[str] (clave_contraparte del motor, enmascarada), veces: int, retraso_p75_dias: int | None}` (percentil 75 de días entre pago y Bizum del grupo, con al menos 3 Bizums). Desaparece `Contacto.dias_devolucion`: no queda ningún dato por persona. `retraso_p75_dias` es interno del grupo y nunca se muestra.
- **Personalización**: `perfilar(historial: list[MovimientoEnriquecido], hoy, perfil_anterior)`; `ModeloUsuario` añade `perfil`, `elecciones` (para `ordenar_acciones`) y `usar_perfil`, y pierde `series` y `lineas_base` (son estado del motor). `Preferencias.euros_por_molestia?`. Política `beta-jerarquica-v2`. `ingreso_mensual_tipico` se muestra al cliente y se puede editar o borrar. La prueba gratuita urgente respeta la franja horaria (la demo es a las 20:30).
- **`Propuesta`** copia también `impacto_relativo?` y `contexto_personal?` del momento.
- **Orden en el orquestador**: `motor.procesar` → `modulos.proponer` → `personalizacion.ordenar_acciones` → `personalizacion.decidir` → guardar.
- **Módulos**: `TarjetaConfirmacion.detalle_baja? = {url_baja?, pasos, bloquea_cobros, canal, fuente}` (solo desde la caché de `InfoComercio`; URL `https` validada que el servidor nunca sigue; en la auditoría solo el host). Cada módulo ofrece 2 acciones y el validador rechaza más de 3. `fin_de_prueba` lleva urgencia alta. El minilenguaje puede leer `momento.impacto_relativo` y los campos numéricos y listas de `modelo.perfil` (no `resumen_vida` ni `grupos`); si falta el perfil, la comparación es falsa, así que las condiciones con perfil llevan un umbral fijo de respaldo con `o`. El bloqueo de cobros de `cancelar_suscripcion` y `bloquear_comercio` solo aplica a tarjeta, y la tarjeta de confirmación lo dice.
- **Demo de pruebas**: `prueba-streamflix-lucia` (verificación de 0 € el 14/10, 30 días, 9,99 €; aviso el 10/11, el día después de la cena). En la caché solo hay servicios ficticios con días y precios; de las marcas reales, solo el tipo.

### Segunda revisión (`revisor`, 9 nov, noche). Manda sobre todo lo anterior

**Escenario único de la demo: `demo-lucia`** (lo usan el guion, el test de principio a fin y `/medir`). Une la cena, la prueba de Streamflix y el duplicado de 9,99 € en el mismo historial. `cena-lucia` y `prueba-streamflix-lucia` siguen como escenarios unitarios.
- Reparto (clave literal de `clave_contraparte` → nombre visible): `LAURA M` (Laura Martínez García → «Laura M.»), `DANIEL P` (Daniel Pérez Ruiz → «Daniel P.»), `SARA L` (Sara López Gil → «Sara L.»), `MARCOS R` (Marcos Ruiz Sanz → «Marcos R.»). Es el único grupo de Lucía; en las cenas anteriores (al menos 3) pagan los cuatro, con Bizums a 0-2 días, así que `retraso_p75_dias = 2`.
- Cena: viernes 6/11 en «La Tasca», 120 €. Bizums de 24 €: Laura (6/11), Daniel (7/11), Sara (8/11). `DIAS_ESPERA = clamp(2 + 1, 2, 5) = 3` → el momento sale el **lunes 9/11**, con o sin perfil (hay test de las dos cosas). Candidato único: `MARCOS R`.
- Streamflix: verificación de 0 € el 14/10 (`luc-v1`), 30 días, 9,99 €; primer cobro el 13/11; aviso el **10/11**.
- Duplicado de 9,99 € con tarjeta a mediados de octubre: se detecta gracias al umbral personal de Lucía y va al **resumen** (urgencia `media`).

**Pruebas gratuitas**
- `fin_de_prueba.cuando` usa `dias_hasta <= 5` (el motor ya decide el momento: 3 días, o 5 con duración por defecto). Para la personalización, cualquier `prueba_gratuita` emitida cuenta como protección.
- Al ejecutar `cancelar_suscripcion`: si `bloquear_cobros = true`, el orquestador llama a `motor.cerrar_prueba`; si es `false`, la prueba queda en `baja_guiada` y el orquestador crea un `recordar` el día antes del cobro («¿Pudiste darte de baja de X?»). Si llega el cobro, el motor la cierra igualmente.
- El motor ignora las entradas de `suscripciones_activas` con `en_prueba = true` al decidir si un comercio «ya se paga» (test: recalcular el perfil a mitad del escenario de Streamflix no mata la prueba).
- `registrar_prueba(usuario_id, comercio, fecha_alta, dias?, hoy)` y `cerrar_prueba(usuario_id, comercio, motivo, hoy)` llevan `hoy`. Endpoint y botón «He empezado una prueba» son **opcionales**.
- **Realismo (para el pitch y la demo)**: la señal son las **autorizaciones** que recibe el banco emisor (también las de 0 €), no el extracto. No cubre todo: hay pruebas sin verificación y comercios que pasan por pasarelas (PayPal, Apple, Google) que ocultan el nombre. Por eso existe también la vía «el cliente lo dice». No se promete cobertura total.

**`cancelar_suscripcion`**: texto de la tarjeta: «La baja la confirmas tú en {comercio}. Si lo eliges, rechazaremos sus cobros con tarjeta (según lo que permita tu banco emisor; no vale para recibos domiciliados). Bloquear no cancela el contrato: el comercio podría reclamarte lo que debas». `bloquear_cobros` puede venir marcado en `fin_de_prueba` solo si la tarjeta lo explica así.

**Búsqueda web (seguridad)**
- Solo se buscan comercios de tarjeta con nombre de ≤ 30 caracteres, sin dígitos, que el normalizador no marque como posible persona (p. ej. `SUMUP *JUAN PEREZ`). Nunca contrapartes de Bizum o transferencias.
- Los resultados web se guardan en `datos_usuario/_cache/comercios_web.json` (fuera de git). `backend/datos/comercios_conocidos.json` (versionado) es solo el catálogo revisado a mano.
- `url_baja` con `origen: web` solo se acepta si su host coincide con el dominio oficial del comercio que aparece en las fuentes; se rechazan `xn--`, IP, credenciales y lo que no sea `https`. Con `origen: web` se muestra como texto con «Compruébalo en la web oficial», sin enlace directo. Con `origen: catalogo`, enlace normal.
- `pasos_baja`: como mucho 5 pasos de 200 caracteres, en texto plano dentro de la tarjeta (no pasan por plantillas). Se descartan los pasos con teléfonos, IBAN, correos, URL distintas de `url_baja` o verbos de pago («transfiere», «paga», «envía», «introduce tu tarjeta»).
- `InfoComercio` fallido: `origen: desconocido` (no se usa `tipo: desconocido`).

**Privacidad del perfil**
- `memoria_para_agente` envía al agente de voz solo hechos operativos (p. ej. «suele resolver los gastos compartidos pidiendo Bizum»). Nunca `ingreso_mensual_tipico`, importes por categoría ni `resumen_vida`.
- Lista negra de comercios sensibles (salud, citas, religión, política, sindicatos, apuestas) que no entran en `comercios_habituales` ni en `suscripciones_activas`, ni en `resumen_vida`.
- `perfilar` devuelve `None` con menos de 28 días de historial: «sin perfil» significa los umbrales por defecto del motor, no un perfil por defecto.

**Limpieza**: `preparar_baja` ya no existe (en todas las tablas, `cancelar_suscripcion`); `saldo_negativo_previsto`, `colchon` y `mover_dinero` en la demo son opcionales; el token caduca a los 10 minutos; `MODO_DEMO = off | grabar | reproducir`; `preparar_accion` admite `bloquear_cobros` (boolean); el nombre visible es Meisam (las claves internas pueden seguir diciendo `copiloto`).
- **Firmas finales del motor para pruebas y conocimiento**: `registrar_prueba(usuario_id, comercio, fecha_alta, dias: int | None, hoy)` y `cerrar_prueba(usuario_id, comercio, motivo, hoy)` (`motivo` admite `cancelada`, `cobrada`, `caducada` y `baja_guiada`). `conocimiento.info_en_cache(nombre)` y `conocimiento.guardar(info)`. `MovimientoEnriquecido.etiquetas` admite `pasarela` (p. ej. `PAYPAL *X`) y `posible_persona` (nunca se busca en la web).
- **Duplicado de la demo**: «LIBRERIA LUNA», 9,99 € dos veces el 15/10 (`luc-d1`, `luc-d2`). Solo se detecta con perfil (umbral personal de Lucía 6 € frente a 15 € por defecto) y va al resumen: así se ve que el perfil cambia lo que el motor considera relevante.

### Voz y chat con ElevenLabs: obligatorios (Pablo, 9 nov, noche)

El reto exige usar la voz y las herramientas de ElevenLabs por la API. La **llamada de voz** y el **chat** usan el mismo agente de ElevenLabs y las mismas herramientas de cliente (`preparar_accion`, `registrar_feedback`): el chat es el modo `textOnly` (nivel 2) y es el modo de texto principal. El agente del kit en `/voz/texto` (nivel 3) queda solo como plan B si ElevenLabs falla. No se recorta: si vamos tarde, cae antes la creación del módulo en directo.

### Integración del esqueleto (9 nov, noche)

- **Consentimiento principal**: clave `copiloto` en `ModeloUsuario.consentimientos`. La política acepta `avisos` como alias mientras el frontend se unifica; el frontend envía `copiloto`.
- **Tokens de confirmación**: los guarda y valida `backend/acciones/tokens.py` por usuario (SHA-256, un solo uso, 10 min). El `usuario_id` va en el cuerpo de `/acciones/confirmar` y un token de otro usuario falla.
- **Archivos del usuario que leen las acciones**: `propuestas.json` y `reloj.json` (`hoy`), que escribe el orquestador antes de llamar a `preparar`.
- **Nombre visible de las contrapartes**: el motor y los módulos usan la clave (`MARCOS R`); la app y la llamada muestran «Marcos R.» (pendiente en D1/F2).
- **Clave de demo**: `X-Demo-Key` (variable `DEMO_KEY`) protege todas las rutas que cambian estado o gastan; sin `DEMO_KEY` se permite (local). El frontend lee los SSE (`/reloj/reproducir`) con `fetch` y su lector del kit, no con `EventSource`, para poder enviar la cabecera.
- **Confirmar sin memoria**: `acciones.ejecutar` devuelve `propuesta_id` y `parametros` en `ResultadoAccion.datos`; el orquestador no guarda nada en memoria entre preparar y confirmar (sobrevive a un reinicio).
- **Reloj de las acciones**: el orquestador escribe `reloj.json` al cargar el escenario y en cada día procesado.

### Casos de deuda (Pablo, 10 nov; diseño en `docs/diseno/deudas-casos.md`)

- Tipo nuevo `Caso` en `backend/plataforma/tipos.py` (con `Deudor`, `Hipotesis`, `Acuerdo`, `CambioCaso`). Se guarda por usuario en `casos.json` (`list[Caso]`, vía `almacenamiento`; lo registra `_tipo` del orquestador). «Escenario» = tipo de deuda (`EscenarioDeuda`); «caso» = el objeto real (la cena del viernes).
- `Momento` no cambia: sigue siendo «se abre un caso», así `/medir` y los tests actuales valen. El caso guarda `momento_id` y `propuesta_id`.
- **Estados**: `Caso.estado` = `abierto | dudoso | pedido | saldado | descartado | caducado`; `Deudor.estado` = `detectada | pedida | saldada | rechazada | caducada | olvidada`. Transiciones en el diagrama de `deudas-casos.md`.
- **Código frente a IA**: el código calcula cifras (`hechos`, `Deudor.cuota`) y solo asigna escenario cuando la señal es completamente clara; todo lo demás queda `dudoso` con sus `hipotesis` y lo resuelve la fase 2 (Haiku). La IA elige entre escenarios de la lista y candidatos; nunca cambia importes ni marca pagos. Sin IA o sin red, un caso dudoso **no avisa**.
- **`Amigo` no se estira**: el saldo con cada amigo (O7) se calcula a partir de los `Caso` abiertos y cerrados.
- **Privacidad**: `contraparte` enmascarada, sin conceptos ni notas de Bizum; `conversaciones` y `acuerdos` son resúmenes enmascarados, visibles y borrables en «Lo que he aprendido». El agente nunca valora a una persona.
- **Hecho en la tanda 1**: `GET /usuarios/{id}/amigos` devuelve `Amigo[]` calculado desde los casos (saldo positivo = te debe); `DELETE /usuarios/{id}/amigos/{contraparte}` (con demo key) olvida a un contacto. El código marca un caso como avisado con `Caso.hechos["avisado_el"]`. `POST /acciones/preparar` admite `editado: bool` (solo el botón del usuario; el agente de voz nunca lo envía) y llama a `acciones.preparar_editada`; el flag vive en el token, nunca en el cliente.
- **Fase 2 del detector (agente de dudas, 10 nov)**: `backend/motor/dudas.py` + `casos.ciclo.aplicar_resolucion`. Se activa con la variable de entorno `DUDAS_IA=on` (por defecto `off`; los tests no gastan crédito). Sin tipos nuevos: la pregunta vive en `Caso.hechos["pregunta"]` (`{texto, candidatos, preguntada, estado, propuesta_id}`), junto a `dudas_hash`, `dudas_fallo`, `resuelto_por`, `motivo_ia` y `confianza_ia`. La pregunta sale como una `Propuesta` de solo preguntar (`id = prop-duda-<caso>`, única acción `recordar`, `contexto_llamada` con la pregunta) que pasa por `decidir` y el tope de avisos; no se enlaza con `Caso.propuesta_id`. Diseño en `motor.md` §8 quater.
- **Agente post-llamada (tanda 2)**: `POST /voz/conversacion {token_sesion, mensajes: [{rol: meisam|usuario, texto}], canal}` (demo key; usuario y propuesta salen de la sesión del servidor, con 10 min de gracia tras caducar el TTL solo en esta ruta; `Llamada.tsx` la manda una vez al terminar, voz o chat, con `fetch` `keepalive`, y falla en silencio; en una conversación sin aviso solo se manda si el agente cambió algún caso). El backend (`casos/resumir.py`, `orquestador.registrar_conversacion`) enmascara la transcripción, la pasa a Haiku como dato y valida una lista cerrada: `posponer` (1-14 días), `nota` (a `Caso.acuerdos`), `silenciar_contacto` (misma vía que `no_avisar_contacto`), `corregir_deudores` (solo a `olvidada`) y `resumen` (a `Caso.conversaciones`). Nunca toca importes ni pagos; sin caso no hace nada; sin consentimiento `memoria` no guarda nota ni resumen. Rastro en `Caso.historial` con origen `llamada`. Para «Lo que he aprendido»: `GET /usuarios/{id}/casos` (id, estado, creado, deudores, conversaciones, acuerdos) y `DELETE /usuarios/{id}/casos/{caso_id}/conversaciones` (demo key).

### Escenarios, transiciones y personas (10 nov, noche)
Diseño completo, tabla de transiciones y API en `docs/diseno/deudas-casos.md` («Escenarios, transiciones y cuentas con personas»). Cambios de tipos: `EscenarioDeuda` = `pago_individual | pago_por_otro | gasto_compartido | gasto_fijo_compartido | viaje | prestamo_amigo | bizum_recibido_sin_pagar` (`gasto_compartido_puntual` pasa a `gasto_compartido`); `Deudor.via_saldado` y `Deudor.motivo_saldado`; `Caso.aviso` (`notificar | resumen | silencioso`); `Contacto` con `nombre`, `telefono` y `relacion`. El módulo de catálogo `cena_compartida` pasa a `gasto_compartido`.
- **Hecho en la tanda 3** (API en `rutas_copiloto.py`/`rutas_voz.py`): `GET /usuarios/{id}/casos` (con `escenario`, `aviso`, `movimiento_origen` como objeto `{id, comercio, importe, fecha}`, deudores con `pedida`, `saldada`, `via_saldado`, `motivo_saldado`, `historial`); `POST /usuarios/{id}/casos`; `POST …/casos/{id}/saldar`, `…/descartar` (con `contraparte?`) y `…/escenario`; `GET /usuarios/{id}/movimientos?limite=60`; `GET`/`PATCH`/`DELETE /usuarios/{id}/contactos[/{clave}]`. Claves nuevas de `Momento.datos` (motor): `origen` (`pago_individual`), `senal` (`media`|`debil`), `tipo_comercio`, `recurrente`. Un `pago_individual` nace como caso abierto sin deudores: `senal=media` → `aviso=resumen`; `debil` → `silencioso`. El agente post-llamada admite `cambiar_escenario` y `marcar_saldado` con una cita literal del usuario.
- **Herramientas de la llamada para consultar y cambiar casos (11 nov)**: `POST /voz/herramientas/{consultar_cuentas, buscar_movimientos, lo_que_sabes_de_mi, actualizar_caso, deshacer}` (demo key; `token_sesion` en el cuerpo; el usuario sale de la sesión y un campo `usuario_id` se rechaza con 422). Resultado `{ok, ...}` o `{ok: false, error}` en español; todo texto libre va entre `<datos>`. `actualizar_caso` `{caso_id, accion, persona?, importe?, via?, motivo?, dias?, escenario?, respuesta?}` con `accion` en `iba_solo | con_personas | no_me_debe | marcar_saldado | posponer | responder_duda | proponer_cambio_de_escenario` (`backend/casos/llamada.py`, `orquestador.actualizar_caso_llamada`; rastro `origen="llamada"` y auditoría `caso_llamada`); `deshacer` `{cambio_id}` restaura el caso si no ha cambiado después (`caso_deshecho`). `proponer_cambio_de_escenario` solo deja `Caso.hechos["cambio_propuesto"] = {escenario, motivo, persona, propuesto}`; el agente post-llamada lo confirma al colgar (con cita literal del usuario) y lo borra. Nuevo: `casos.aplicar_respuesta` (responde la pregunta pendiente de un caso dudoso), evento SSE `cambio {hecho, cambio_id}` en el nivel 3 y la herramienta del plan B `buscar_movimientos_llamada` (el chat del kit ya tiene `buscar_movimientos`). Detalle y textos del panel en `experiencia.md` §6.7.

### Curva de amigos: lo que aprende Meisam y el chat que crea casos (11 nov; encargo `docs/diseno/curva-amigos.md`). Manda sobre todo lo anterior donde choque

Manda el encargo. Esquema de las vidas ocultas y del corpus: `backend/personalizacion/simulacion/amigos/ESQUEMA.md`. Tareas e hilos: `docs/PLAN.md`, «11 nov: curva de amigos (C, A, B)».

**Regla de compatibilidad.** Todo campo nuevo es opcional y con valor por defecto: los modelos guardados y los tests de antes cargan igual. Con `ModeloUsuario.aprendizaje` vacío (o `modo = "reglas"`) el sistema se comporta **exactamente** como antes del 11 nov: misma escalera (`senal media` → resumen, `debil` → silencio, nunca push), mismo `avisar_desde` (2 días) y el motor recibe `compania=None`.

**Tipos nuevos** (`backend/plataforma/tipos.py`):

| Tipo | Campos |
|---|---|
| `Franja` | `laborable \| viernes \| finde` (del día de la semana: el banco no da la hora) |
| `FormaReparto` | `iguales \| por_consumo \| redondeo \| cada_uno_lo_suyo` |
| `CanalDevolucion` | `bizum \| efectivo \| transferencia \| invitacion` |
| `FuenteAprendizaje` | `respuesta \| boton \| chat \| bizum \| cierre \| ignorada \| llamada` |
| `ModoAprendizaje` | `aprende` (por defecto) `\| fijo` (usa, no aprende: el `oraculo`) `\| reglas` (ni aprende ni usa: lo de antes) |
| `GrupoHabitual` | `miembros` (claves), `veces` (float, con decaimiento), `ultima`, `repartos` (`FormaReparto` → peso) |
| `Acompanamiento` | `con_alguien`, `solo` (pseudo-cuentas Beta con decaimiento), `n`, `ultima`, `ignoradas`, `aceptadas_seguidas`, `rutina_aceptada` (nivel 4), `grupos` (≤ 5) |
| `HabitoPersona` | `contraparte`, `retrasos_dias` (últimas 10), `retrasos_tras_pedir` (últimas 10), `retraso_p75_dias` (solo con ≥ 2), `paga_solo`, `paga_tras_pedir`, `canales` (`CanalDevolucion` → veces), `redondea`, `ultima`, `fijado_por_usuario` |
| `AprendizajeAmigos` | `version` (`amigos-v1`), `modo`, `por_comercio` (comercio normalizado → `Acompanamiento`), `por_tipo_franja` (`"<tipo>\|<franja>"` → `Acompanamiento`), `personas` (clave → `HabitoPersona`), `eventos_vistos` (idempotencia, ≤ 500), `actualizado` |
| `SugerenciaReparto` | `personas`, `forma`, `cuotas` (clave → Euros, del código; vacío en el nivel 2), `confianza`, `ambito` |
| `DecisionPregunta` | `nivel` (0-4), `aviso` (`AvisoCaso`: 0 y 4 → `silencioso`, 1 y 2 → `resumen`, 3 → `notificar`), `sugerencia?`, `p_acompanado`, `n`, `motivos` |
| `EventoAmigos` | `id` (idempotente), `fuente`, `fecha`, `fecha_pago?`, `comercio?`, `tipo_comercio?`, `franja?`, `acompanado?`, `personas`, `forma?`, `nivel?`, `sugerencia_aceptada?`, `contraparte?`, `retraso_dias?`, `tras_pedir`, `canal?`, `redondeado` |
| `PersonaGasto` | `nombre` (dato, 1-40), `importe?` |
| `ApuntarGastoEntrada` | `pista` (dato, 1-60), `fecha_aprox?`, `importe_total?`, `personas` (≤ 10), `incluye_usuario` (true), `efectivo` (false), `movimiento_id?`, `confirmar_personas_nuevas` (false) |
| `CargoCandidato` | `movimiento_id`, `fecha`, `comercio` (visible), `importe` (positivo) |
| `CuotaPersona` | `contraparte`, `nombre` (enmascarado), `cuota` |
| `ApuntarGastoSalida` | `ok`, `resultado` (`ResultadoApuntar`), `mensaje`, `caso_id?`, `candidatos` (≤ 5), `deudores`, `personas_sin_resolver`, `cambio_id?` |
| `ResultadoApuntar` | `creado \| convertido \| varios_candidatos \| sin_cargo \| persona_desconocida \| persona_ambigua \| importe_invalido \| sin_personas \| no_soportado` |
| `HechoChatEntrada` | `tipo` (`TipoHechoChat`: `va_solo \| grupo_habitual \| paga_en_efectivo \| no_recordar \| plan_recurrente`), `persona?`, `personas`, `pista?`, `dia_semana?` (0-6), `texto` (dato, ≤ 160) |

**Campos nuevos en tipos que ya existían** (todos opcionales): `ModeloUsuario.aprendizaje: AprendizajeAmigos` (vacío por defecto) · `Caso.origen` (`motor \| boton \| chat`) · `Caso.pregunta_nivel` (0-4) · `Caso.sugerencia: SugerenciaReparto` · `Deudor.avisar_desde` (por persona; None = el del caso) · `HechoAprendido.origen` admite `chat` · `HechoAprendido.tipo` (`TipoHechoChat`) · `HechoAprendido.contraparte` (se borra con el contacto) · `HechoAprendido.datos`. Claves nuevas de `Caso.hechos`: `canal_probable` (`CanalDevolucion` más frecuente del deudor; la app ofrece primero «Ya me lo dio» si es `efectivo`). Clave nueva de `Momento.datos` en `pago_individual`: `senal = "aprendida"` (el motor lo abrió por lo aprendido, no por las reglas fijas).

**Salvaguardas de los hechos por persona** (decisión de Pablo, ver `DECISIONES.md`): frases neutras y de hechos («suele devolvértelo a los 2 o 3 días»), nunca juicios; solo para los recordatorios del propio usuario (no van a `memoria_para_agente` del banco ni a otros módulos, ni a `Propuesta.contexto_llamada` como valoración); se ven, se editan y se borran; `borrar_contacto` borra su `HabitoPersona` y sus hechos (`HechoAprendido.contraparte`).

#### Interfaces entre hilos (firmas; todas puras salvo las del orquestador)

```python
# backend/personalizacion/aprende_amigos.py (H2). Puras: devuelven copias, no guardan.
def franja_de(fecha: date) -> Franja: ...
def eventos_de_caso(antes: Caso | None, despues: Caso, fuente: FuenteAprendizaje, hoy: date,
                    tipo_comercio: str | None = None) -> list[EventoAmigos]: ...   # respuesta, botón, chat, cierre
def eventos_de_bizum(caso: Caso, deudor_antes: Deudor, deudor_despues: Deudor, hoy: date) -> list[EventoAmigos]: ...
def aprender_evento(apr: AprendizajeAmigos, ev: EventoAmigos) -> AprendizajeAmigos: ...  # no-op si modo != "aprende" o ev.id visto
def aprender_eventos(modelo: ModeloUsuario, eventos: list[EventoAmigos]) -> ModeloUsuario: ...
def decaer(apr: AprendizajeAmigos, hoy: date) -> AprendizajeAmigos: ...
def retraso_persona(apr: AprendizajeAmigos, contraparte: str, grupo: list[str] | None = None,
                    perfil: PerfilUsuario | None = None) -> tuple[int, str]: ...   # (días, "persona" | "grupo" | "general")
def avisar_desde(apr: AprendizajeAmigos, contraparte: str, fecha_pago: date, hoy: date,
                 grupo: list[str] | None = None, perfil: PerfilUsuario | None = None) -> date: ...  # nunca antes de hoy
def canal_probable(apr: AprendizajeAmigos, contraparte: str) -> CanalDevolucion | None: ...
def compania_para_motor(apr: AprendizajeAmigos) -> dict[str, float] | None: ...  # None si modo == "reglas" o vacío
def frases_amigos(apr: AprendizajeAmigos, contactos: dict[str, Contacto]) -> list[FrasePerfil]: ...
def borrar_persona(apr: AprendizajeAmigos, contraparte: str) -> AprendizajeAmigos: ...
def editar_persona(apr: AprendizajeAmigos, contraparte: str, campo: str, valor: Any) -> AprendizajeAmigos: ...

# backend/personalizacion/escalera.py (H2). Pura y rápida (< 1 ms).
def sugerir(apr: AprendizajeAmigos, comercio: str | None, tipo_comercio: str | None, fecha: date,
            importe: Decimal) -> SugerenciaReparto | None: ...   # cuotas con Decimal, usuario incluido
def nivel_pregunta(apr: AprendizajeAmigos, *, comercio: str | None, tipo_comercio: str | None, fecha: date,
                   importe: Decimal, senal: str | None, umbral: Decimal) -> DecisionPregunta: ...

# backend/motor (H2, ingeniero-deteccion). Solo añade un argumento opcional; con None, idéntico.
def procesar(usuario_id, nuevos, hoy, perfil=None, compania: dict[str, float] | None = None) -> list[Momento]: ...
#   compania: "c:<COMERCIO>" o "t:<tipo>|<franja>" -> p(acompañado), solo ámbitos con n suficiente.
#   `pago_individual` abre con `senal="aprendida"` donde p es alta (aunque sea entre semana o por debajo de IMPORTE_MIN,
#   con un mínimo propio en `PagoIndividual`). Nunca lee el modelo del usuario ni importa `personalizacion`.

# backend/casos/apuntar.py (H3). Puro.
def buscar_cargos(historial: list[Movimiento], entrada: ApuntarGastoEntrada, hoy: date) -> list[CargoCandidato]: ...
def cuotas_de(movimiento: Movimiento, entrada: ApuntarGastoEntrada, claves: list[str]) -> dict[str, Decimal]: ...  # ValueError si inválidas

# backend/plataforma/chat_casos.py (H3). Con candado y auditoría; lo llaman la herramienta y el simulador.
def apuntar_gasto_usuario(usuario_id: str, entrada: ApuntarGastoEntrada) -> ApuntarGastoSalida: ...
def recordar_sobre_mi_usuario(usuario_id: str, entrada: HechoChatEntrada) -> dict: ...   # {ok, hecho} | {ok: False, error}

# backend/plataforma/orquestador.py (H2, tarea A0: ganchos que necesitan H1 y H3; se integra en main lo primero)
def crear_caso_usuario(usuario_id, movimiento_id, deudores, escenario=None, origen: OrigenCaso = "boton") -> dict: ...
def cargar_simulacion(usuario_id: str, movimientos: list[Movimiento], activacion: date,
                      contactos: dict[str, Contacto] | None = None, modelo: ModeloUsuario | None = None) -> dict: ...
#   como `cargar_escenario`, pero desde memoria (comparten el cuerpo; no se duplica). `modelo` fija p. ej. `aprendizaje.modo`.
def anadir_movimientos(usuario_id: str, movimientos: list[Movimiento]) -> int: ...
#   añade a `pendientes` movimientos con fecha > hoy (rechaza el pasado: nadie mira el futuro ni reescribe el pasado).
```

**Qué llama el simulador** (`backend/personalizacion/simulacion/amigos/`, H1), siempre las funciones del sistema real, sin duplicarlas: `orquestador.cargar_simulacion` → `orquestador.activar` → cada día `orquestador.anadir_movimientos` (Bizums reactivos de los amigos) y `orquestador.avanzar_dia`; para leer, `orquestador.notificaciones`, `orquestador.casos_usuario` y `casos.cargar`; las reacciones del usuario con `orquestador.actualizar_caso_llamada` (`iba_solo`, `con_personas`, `marcar_saldado`, `no_me_debe`, `responder_duda`), `orquestador.registrar_feedback` (ignoradas, «no me avises»), `orquestador.preparar_accion` + `orquestador.confirmar_accion` (pedir Bizum confirmado, como el botón) y `chat_casos.apuntar_gasto_usuario` / `recordar_sobre_mi_usuario` (el chat). Todo con `DATOS_USUARIO_DIR` temporal, `BUSQUEDA_WEB=off` y `DUDAS_IA=off`. Si una ejecución completa no baja de 2 minutos, primero procesos en paralelo (cada uno con su `DATOS_USUARIO_DIR`); después, `almacenamiento` en memoria (tarea C7).

**Cómo elige el simulador la política sin que la política lo importe.** La política solo lee `ModeloUsuario.aprendizaje.modo`, que el simulador fija al crear el modelo con `cargar_simulacion(..., modelo=...)`:

| Política de la simulación | `aprendizaje.modo` | Chat | Estado inicial |
|---|---|---|---|
| `reglas` | `reglas` | sí (el chat crea casos igual; no aprende de ellos) | vacío |
| `personalizada` | `aprende` | sí | vacío (valores por defecto) |
| `personalizada_sin_chat` | `aprende` | el simulador no envía mensajes de chat | vacío |
| `oraculo` (opcional) | `fijo` | sí | el simulador rellena `AprendizajeAmigos` desde la verdad oculta |

El sistema nunca sabe qué política es: no hay parámetros por nombre de vida ni de comercio. Un test (como `verificar_aislamiento` de U3) comprueba que ningún archivo de `backend/personalizacion/*.py`, `backend/motor/`, `backend/casos/` ni `backend/plataforma/` importa `simulacion`.

**API nueva** (demo key en las que cambian estado):
- `POST /voz/herramientas/apuntar_gasto` `{token_sesion, ...ApuntarGastoEntrada}` → `ApuntarGastoSalida` (todo texto libre del resultado entre `<datos>`; `usuario_id` en el cuerpo → 422). Rastro `origen="chat"` y auditoría `caso_chat`. «Deshacer» con el `POST /voz/herramientas/deshacer` de siempre.
- `POST /voz/herramientas/recordar_sobre_mi` `{token_sesion, ...HechoChatEntrada}` → `{ok, hecho}`.
- `GET /usuarios/{id}/aprendido` añade `amigos_aprendido: [{campo, texto, editable, borrable, tipo: "persona"|"sitio", clave}]` (frases por persona y por sitio; `amigos` sigue siendo los saldos pendientes); `PATCH /usuarios/{id}/aprendido/amigos/{contraparte}` con `{campo: "retraso_dias"|"canal", valor}`; `DELETE /usuarios/{id}/aprendido/amigos/{contraparte}` borra lo aprendido de esa persona; `DELETE /usuarios/{id}/aprendido/sitios/{clave}` borra un ámbito de `Acompanamiento`.
- El cliente de ElevenLabs registra `apuntar_gasto` y `recordar_sobre_mi` como herramientas de cliente (textos del panel en `experiencia.md` §6.7, los deja H3).
