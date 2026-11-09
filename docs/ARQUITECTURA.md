# Arquitectura

Arquitectura de **Meisam** (nombre visible; en el código, paquetes y skills siguen los nombres internos, como `copiloto`). Cerrada en `/planificar` (9 nov, tarde) y actualizada la noche del 9 nov con los cambios de Pablo y la segunda revisión. Manda `docs/diseno/CONTRATO.md` (sus apartados finales mandan sobre todo lo anterior); el detalle de cada parte está en `docs/diseno/{motor,personalizacion,modulos,experiencia}.md`. Este archivo fija lo que comparten las zonas: paquetes, interfaces, API, herramientas, datos y pruebas.

## 1. Componentes y flujo
```
Navegador (Next.js): /app (cliente) · /app/llamada/[id] · /app/aprendido · /banco (consola) · /jurado · /kit (chat del kit)
   │ HTTP + SSE (frontend/lib/api.ts)                     │ (opcional) WebRTC/WebSocket con token de ElevenLabs
   ▼                                                      ▼
API FastAPI (backend/api: main.py + un router por zona)   Agente de voz ElevenLabs (herramientas de cliente → /voz/herramientas/*)
   │
   ▼
plataforma/orquestador  (candado por usuario; único que dispara escrituras en datos_usuario/)
   reloj simulado ─> movimientos del día (escenario)
   ├─ personalizacion.perfilar ─> PerfilUsuario   (al activar y cada 7 días simulados; pandas; antes de procesar)
   ├─ motor.procesar(…, perfil) ─> Momento[]      (normalizar → enriquecer → parametros.ajustar(perfil) → detectores
   │                                               → razonador con impacto_relativo y contexto_personal; sin Claude)
   ├─ modulos.proponer ─> Propuesta[]             (catálogo YAML + módulos aprobados; 2 o 3 acciones; sin Claude)
   ├─ personalizacion.ordenar_acciones ─> Propuesta  (solo reordena según lo que esa persona suele elegir)
   ├─ personalizacion.decidir ─> Decision         (reglas duras + Beta jerárquica v2 + utilidad relativa al perfil; motivos)
   ├─ acciones.preparar / ejecutar                (token de un solo uso, límites, banco simulado, auditoría, detalle_baja)
   ├─ motor.cerrar_prueba                         (tras cancelar_suscripcion con bloquear_cobros = true)
   └─ personalizacion.aprender / registrar_*      (ModeloUsuario: perfil, elecciones, hechos)
motor.conocimiento: info_en_cache (caché, camino caliente) · info_comercio (búsqueda web, fuera del camino caliente, opcional)
voz: sesion (modos `voz` y `texto_el` de ElevenLabs **obligatorios en el MVP**: llamada y chat con el mismo agente y herramientas de cliente) · `texto_kit` = agente del kit, solo plan B si ElevenLabs falla
Claude, siempre por backend/claude_client.py: Sonnet 5.5 (modo texto, crear módulos); Haiku 5.5 (búsqueda web y resumen_vida, opcionales)
```
**Un día simulado** (`avanzar_dia(usuario_id, hoy, ahora=None)`, `ahora` por defecto `hoy 20:30`):
1. Si toca (cada 7 días desde la activación): `perfil = perfilar(motor.enriquecer(historial ≤ hoy), hoy, modelo.perfil)`; se respetan `campos_fijados` y `campos_borrados`. Con menos de 28 días, `None`.
2. `motor.procesar(usuario_id, movimientos_del_dia, hoy, perfil if modelo.preferencias.usar_perfil else None)`.
3. Por cada momento: `modulos.proponer` → `ordenar_acciones` → `decidir` → `registrar_decision`.
4. `observar` (diaria) y guardar. Con `BUSQUEDA_WEB=on` (opcional), después: `info_comercio` para cada `motor.comercios_pendientes(usuario_id)` (máximo 20 al día).
5. Al confirmar `cancelar_suscripcion`: con `bloquear_cobros = true`, `motor.cerrar_prueba(…, "cancelada", hoy)`; con `false`, `cerrar_prueba(…, "baja_guiada", hoy)` y un `recordar` el día antes del cobro («¿Pudiste darte de baja de X?»). Si llega el cobro, el motor la cierra igualmente.

Ningún detector ve movimientos con `fecha > hoy`. Sin perfil, el motor se comporta exactamente como sin personalización (test de regresión).

## 2. Paquetes y archivos clave
```
backend/
  plataforma/  tipos.py (pydantic del contrato) · reloj.py · almacenamiento.py (JSON atómico) · orquestador.py · privacidad.py (enmascarar)
  motor/       __init__.py (procesar, enriquecer, cargar_historial, exportar/importar_estado, reiniciar, registrar_prueba,
               cerrar_prueba, comercios_pendientes) · normalizar.py (incluye tipo_operacion y etiquetas pasarela/posible_persona)
               · enriquecer.py (series, serie_id) · parametros.py (DEFECTO y ajustar(params, perfil)) · razonador.py
               · estado.py (EstadoMotor: historial, series, pruebas, comercios_pendientes, claves_emitidas) · conocimiento.py
               · detectores/{__init__, gasto_compartido, cargo_duplicado, subida_recibo, prueba_gratuita}.py
               (opcionales: renovacion_proxima, saldo_negativo_previsto, posible_estafa)
  escenarios/  cargar.py · *.yaml (cena-lucia, prueba-streamflix-lucia, demo-lucia, trampas, fondo-*)
  personalizacion/ __init__.py · perfil.py (perfilar) · politica.py (beta-jerarquica-v2) · orden_acciones.py · aprendizaje.py
               · motivos.py · edicion.py (perfil y hechos) · amigos.py (opcional) · memoria.py (opcional)
               · simulacion/{perfiles, generador, protocolo}.py (vidas.py opcional)
  modulos/     __init__.py · esquema.py · campos_momento.py · condiciones.py · plantillas.py · registro.py · proponer.py
               · creacion.py · prueba_seco.py · catalogo/{cena_compartida, cobro_duplicado, fin_de_prueba}.yaml
               (opcionales: renovacion.yaml, colchon.yaml)
  acciones/    __init__.py (preparar, ejecutar, deshacer) · registro.py (las 6 AccionDef) · banco_sim.py · tokens.py
               · auditoria.py · enlaces.py (validación de url_baja y detalle_baja desde InfoComercio)
  voz/         __init__.py (sesion) · sesiones.py (token_sesion en memoria) · contexto.py (variables enmascaradas)
               · texto.py (modo texto_kit) · herramientas_llamada.py · elevenlabs.py (opcional: token o URL firmada, urllib)
  datos/       comercios_conocidos.json (nuevo, versionado: catálogo revisado a mano) · sinteticos.py (anomalias=False, verificaciones de 0 €)
  api/         main.py (kit + include_router) · rutas_copiloto.py · rutas_voz.py · rutas_banco.py · rutas_metricas.py · sse.py (kit)
evals/         ejecutar.py + casos.yaml (kit) · casos_llamada.yaml · medir.py (--parte) · medir_motor.py · medir_personalizacion.py
frontend/      app/{page (portada), kit, app, app/llamada/[propuestaId], app/aprendido, banco, jurado}
               components/{Activacion, Bandeja, RelojDemo, Llamada, Transcripcion, TarjetaAccion, DetalleBaja, PorQue, Aprendido,
               PerfilVida, TablaModulos, NuevoModulo, PruebaEnSeco, Precision, MolestiasEvitadas, CurvaAprendizaje, InsigniaIA}.tsx
               lib/api.ts (contrato en TypeScript; reutiliza leerJson y el lector SSE)
datos_usuario/ (fuera de git) <usuario_id>/{reloj, modelo, motor, momentos, propuestas, decisiones, feedback, banco, tokens}.json
               + auditoria.jsonl · _modulos/<id>.yaml (aprobados por el banco) · _cache/comercios_web.json (resultados de la web)
```
**E1 crea todos los `__init__.py` nuevos** con las firmas del §3; lo que aún no existe es un *stub* que devuelve un ejemplo válido (o la entrada sin cambios, como `ordenar_acciones` y `parametros.ajustar`) o lanza `NotImplementedError`. Así las zonas crecen sin tocar archivos ajenos y el orquestador y la API se escriben contra las firmas definitivas desde el primer día.

## 3. Contrato en código

### 3.1 Tipos de `backend/plataforma/tipos.py` (E1 los incluye todos)
Dinero `Decimal` (sale en JSON como cadena con 2 decimales), fechas ISO. Campos y semántica en `CONTRATO.md` y en los diseños; aquí la lista de comprobación de E1:

| Tipo | Novedades de la noche del 9 nov |
|---|---|
| `Movimiento` | `tipo_operacion?: cargo \| verificacion \| devolucion` (además de `canal`, `contraparte`, `nota`) |
| `MovimientoEnriquecido` | `etiquetas` admite `pasarela` y `posible_persona` |
| `Momento` | `impacto_relativo?: Decimal`, `contexto_personal?: str` |
| `Propuesta` | copia `impacto_relativo?` y `contexto_personal?`; `acciones_ofrecidas` de 2 o 3 (`AccionOfrecida {accion_id, parametros, requiere_confirmacion, limites}`); `Limites {importe_max?, contrapartes?}` |
| `Decision`, `Feedback`, `ResultadoAccion` (`deshacer? {resultado_id, disponible_hasta}`) | sin cambios |
| `TarjetaConfirmacion` | `detalle_baja?: DetalleBaja {url_baja?, url_es_enlace: bool, pasos: list[str], bloquea_cobros, canal, fuente}` (`url_es_enlace` es falso si `origen: web`: se muestra como texto con «Compruébalo en la web oficial») |
| `InfoComercio` | nuevo: `nombre, tipo, es_suscripcion, dias_prueba?, precio_tras_prueba?, url_baja?, pasos_baja?, fuentes, consultado, origen: catalogo \| web \| desconocido` |
| `Grupo` | nuevo: `miembros: list[str]` (clave enmascarada), `veces: int`, `retraso_p75_dias: int \| None` (interno, nunca se muestra) |
| `Suscripcion` | nuevo: `comercio, serie_id?, importe, periodicidad_dias, proximo_cobro?, en_prueba` |
| `PerfilUsuario` | nuevo (`personalizacion.md` §2): `version, calculado, dias_historial, dia_cobro_nomina?, ingreso_mensual_tipico?, gasto_tipico_por_categoria, ticket_tipico, umbral_relevante_eur, comercios_habituales, grupos, suscripciones_activas, resumen_vida?, campos_fijados, campos_borrados` |
| `Preferencias` | `silencios`, horario, `max_avisos_dia`, `euros_por_molestia?`, `usar_perfil` |
| `ModeloUsuario` | `politica = "beta-jerarquica-v2"`, `perfil?`, `estadisticas: dict[str, Celda]`, `elecciones: dict[str, int]`, `avisos_abiertos`, `hechos_aprendidos`, `amigos`, `contactos`; **sin** `series` ni `lineas_base` (son estado del motor) |
| `Celda`, `Silencio`, `Contacto`, `AvisoAbierto`, `Amigo` (sin concepto), `HechoAprendido` (`origen` admite `perfil`; `clave?`) | según `personalizacion.md` §2 |
| `SesionVoz`, `BorradorModulo`, `InformePrueba`, `Modulo`, `Evento` (`tipo`, `datos`) | sin cambios |
| `datos` de `prueba_gratuita` | `comercio, fecha_alta, dias_prueba, fecha_primer_cobro, dias_hasta, importe_previsto?, fuente (verificacion \| usuario), fuente_duracion (usuario \| catalogo \| web \| por_defecto), verificacion_id?, fuentes_info` |

`AccionId = Literal["pedir_bizum", "cancelar_suscripcion", "bloquear_comercio", "reclamar_cargo", "mover_dinero", "recordar"]` (`preparar_baja` ya no existe). `TipoMomento` incluye `prueba_gratuita`.

### 3.2 Interfaces Python (firmas definitivas)
```python
# backend/motor
def procesar(usuario_id: str, nuevos: list[Movimiento], hoy: date, perfil: PerfilUsuario | None = None) -> list[Momento]: ...
def enriquecer(movimientos: list[Movimiento]) -> list[MovimientoEnriquecido]: ...            # pura (la usa perfilar)
def cargar_historial(usuario_id: str, historial: list[Movimiento], hoy: date) -> None: ...
def exportar_estado(usuario_id: str) -> dict: ...; def importar_estado(usuario_id: str, estado: dict) -> None: ...
def reiniciar(usuario_id: str) -> None: ...
def registrar_prueba(usuario_id: str, comercio: str, fecha_alta: date, dias: int | None, hoy: date) -> None: ...
def cerrar_prueba(usuario_id: str, comercio: str, motivo: Literal["cancelada", "cobrada", "caducada", "baja_guiada"], hoy: date) -> None: ...
def comercios_pendientes(usuario_id: str) -> list[str]: ...
# backend/motor/parametros.py
def ajustar(params: Parametros, perfil: PerfilUsuario | None) -> Parametros: ...  # única función de umbrales personales
# backend/motor/conocimiento.py
def info_en_cache(nombre: str) -> InfoComercio | None: ...   # sin red: catálogo + _cache/comercios_web.json
def info_comercio(nombre: str) -> InfoComercio | None: ...   # caché y, con BUSQUEDA_WEB=on, búsqueda web (opcional)
def guardar(info: InfoComercio) -> None: ...                 # solo en datos_usuario/_cache/comercios_web.json

# backend/modulos
def proponer(momento: Momento, modelo: ModeloUsuario) -> list[Propuesta]: ...
def crear_borrador(descripcion: str) -> BorradorModulo: ...
def probar_en_seco(borrador: BorradorModulo, usuario_id: str) -> InformePrueba: ...
def aprobar(modulo_id: str, aprobado_por: str) -> Modulo: ...

# backend/personalizacion
def perfilar(historial: list[MovimientoEnriquecido], hoy: date, perfil_anterior: PerfilUsuario | None) -> PerfilUsuario | None: ...
def ordenar_acciones(propuesta: Propuesta, modelo: ModeloUsuario) -> Propuesta: ...   # pura; solo reordena
def decidir(propuesta: Propuesta, modelo: ModeloUsuario, ahora: datetime) -> Decision: ...
def aprender(feedback: Feedback, modelo: ModeloUsuario) -> ModeloUsuario: ...           # pura
def registrar_decision(modelo, propuesta, decision) -> ModeloUsuario: ...
def registrar_accion(modelo, propuesta, resultado: ResultadoAccion) -> ModeloUsuario: ...  # suma a elecciones
def observar(modelo, movimientos, hoy) -> ModeloUsuario: ...
def memoria_para_agente(modelo) -> str: ...   # solo hechos operativos; nunca ingresos, importes por categoría ni resumen_vida
def nuevo_modelo(usuario_id: str) -> ModeloUsuario: ...
# backend/personalizacion/edicion.py
def frases_perfil(perfil: PerfilUsuario | None) -> list[FrasePerfil]: ...     # {campo, texto, editable, borrable}
def editar_perfil(modelo, campo: str, valor) -> ModeloUsuario: ...            # va a campos_fijados
def borrar_campo_perfil(modelo, campo: str) -> ModeloUsuario: ...             # valor por defecto y campos_borrados
def borrar_perfil(modelo) -> ModeloUsuario: ...                               # perfil = None, usar_perfil = False

# backend/acciones
def preparar(accion_id: str, parametros: dict, propuesta_id: str, usuario_id: str) -> TarjetaConfirmacion: ...
def ejecutar(token_confirmacion: str, usuario_id: str) -> ResultadoAccion: ...
def deshacer(resultado_id: str, usuario_id: str) -> ResultadoAccion: ...      # opcional (O4)

# backend/plataforma/orquestador.py
def cargar_escenario(escenario_id: str) -> dict: ...
def activar(usuario_id: str, modulos_activos: list[str], consentimientos: dict) -> ModeloUsuario: ...  # cargar_historial + perfilar
def avanzar_dia(usuario_id: str, hoy: date, ahora: datetime | None = None) -> list[Decision]: ...
def reproducir(usuario_id: str, dias: int, pausar_en: str | None = None) -> Iterator[Evento]: ...
def registrar_feedback(feedback: Feedback) -> list[HechoAprendido]: ...
def preparar_accion(usuario_id, propuesta_id, accion_id, parametros) -> TarjetaConfirmacion: ...
def confirmar_accion(usuario_id: str, token_confirmacion: str) -> ResultadoAccion: ...  # registrar_accion y cierre de la prueba

# backend/voz
def sesion(propuesta_id: str, usuario_id: str, modo_preferido: str) -> SesionVoz: ...  # voz | texto_el | texto_kit | grabado
```

## 4. Contrato de la API
Lo comparten `backend/api/rutas_*.py` y `frontend/lib/api.ts`. Convenciones: JSON; dinero como **cadena** con 2 decimales (`"24.00"`, tipo `Euros = string` en `api.ts`; el frontend solo formatea); fechas ISO del reloj simulado. Errores `{"detail": "…"}`: 400 datos, 403 acción no ofrecida o fuera de límites, 404, 409 token ya usado o prueba en seco no superada, 410 token caducado, 501 *stub* aún sin hacer. Sin autenticación (usuarios sintéticos): `usuario_id` va en la ruta o el cuerpo; en la llamada solo cuenta el `token_sesion`. Cabecera `X-Demo-Key` en `/demo/cargar`, `/banco/modulos/*` y `/voz/*`. SSE con `evento_sse` del kit (`event: <tipo>` + `data: <json>`); todo flujo termina en `fin` o `error`. CORS: `GET, POST, PATCH, DELETE`.

| Método y ruta | Cuerpo o consulta | Devuelve | Tarea |
|---|---|---|---|
| `GET /escenarios` | — | `[{id, usuario_id, descripcion}]` | E8 |
| `POST /demo/cargar` | `{escenario_id}` (demo: `demo-lucia`) | `{usuario_id, hoy, activacion}`; reinicia el usuario y pone el reloj en la activación | E8 |
| `POST /usuarios/{id}/activar` | `{modulos_activos: str[], consentimientos: {avisos, memoria}}` | `ModeloUsuario` (llama a `cargar_historial` y `perfilar`) | E8 |
| `GET /usuarios/{id}/estado` | — | `{hoy, activado, saldo, contadores: {momentos, ahora, resumen, silenciadas}}` | E8 |
| `POST /reloj/avanzar` | `{usuario_id, dias: 1-60}` | `{hoy, decisiones: Decision[]}` | E8 |
| `GET /reloj/reproducir` (SSE) | `?usuario_id&dias&ms_por_dia=1500&pausar_en=` | eventos `dia`, `perfil`, `momento`, `propuesta`, `decision`, `fin`, `error` | U2 (la función, en E7) |
| `GET /usuarios/{id}/notificaciones` | `?bandeja=ahora\|resumen\|silenciadas` | `[{propuesta, decision, estado: nueva\|vista\|resuelta\|rechazada\|ignorada}]` | E8 |
| `GET /usuarios/{id}/propuestas/{pid}` | — | `{propuesta, decision, momento, movimientos}` (enmascarados) | E8 |
| `POST /feedback` | `{usuario_id, propuesta_id, resultado, canal, nota?}` | `{ok, hechos_nuevos: HechoAprendido[]}` | E8 |
| `POST /acciones/preparar` | `{usuario_id, propuesta_id, accion_id, parametros}` | `TarjetaConfirmacion` (con `detalle_baja` si es `cancelar_suscripcion`); el cliente puede volver a llamarla cambiando solo `bloquear_cobros` | E8 |
| `POST /acciones/confirmar` | `{usuario_id, token_confirmacion}` | `ResultadoAccion` | E8 |
| `POST /acciones/deshacer` | `{usuario_id, resultado_id}` | `ResultadoAccion` | opcional O4 |
| `GET /usuarios/{id}/perfil` | — | `{perfil: PerfilUsuario \| null, usar_perfil, frases: [{campo, texto, editable, borrable}]}` | U2 |
| `PATCH /usuarios/{id}/perfil` | `{campo, valor}` (`dia_cobro_nomina`, `umbral_relevante_eur`, quitar de `comercios_habituales`/`grupos`/`suscripciones_activas`) | igual que `GET` | U2 |
| `DELETE /usuarios/{id}/perfil/{campo}` · `DELETE /usuarios/{id}/perfil` | — | igual que `GET` (borrar todo: `perfil = null`, `usar_perfil = false`) | U2 |
| `GET /usuarios/{id}/aprendido` | — | `HechoAprendido[]` | U2 |
| `PATCH /usuarios/{id}/aprendido/{hid}` · `DELETE …/{hid}` · `DELETE /usuarios/{id}/aprendido` | `{activo?, texto?}` | hecho · `{ok}` · `{ok}` (olvidar todo: también el perfil) | U2 |
| `POST /usuarios/{id}/pruebas` | `{comercio, fecha_alta, dias?}` | `{ok}` (`registrar_prueba`; botón «He empezado una prueba») | opcional O8 |
| `GET /usuarios/{id}/amigos` | — | `Amigo[]` | opcional O7 |
| `POST /voz/sesion` | `{propuesta_id, usuario_id, modo_preferido: voz\|texto_el\|texto_kit}` | `SesionVoz` (sin clave de ElevenLabs → `texto_kit`) | V1 |
| `POST /voz/texto` (SSE) | `{token_sesion, mensaje?}` (sin mensaje = primer mensaje fijo y neutro: «Hola {nombre}, me has abierto desde el aviso: {titulo_aviso}. ¿Lo vemos?») | eventos del kit (`texto`, `herramienta_inicio`, `herramienta_fin`, `revision`, `fin`, `error`) + `tarjeta` | V1 |
| `POST /voz/herramientas/preparar` | `{token_sesion, accion_id, parametros}` | `{preparada, titulo}` al agente; la tarjeta con token va solo a la app | V1 |
| `POST /voz/herramientas/feedback` | `{token_sesion, resultado}` | `{ok}` (colgar sin acción = `vista_sin_accion`) | V1 |
| `POST /voz/herramientas/consultar` | `{token_sesion, pregunta}` | `{respuesta}` | opcional O3 |
| `GET /banco/modulos` | — | `Modulo[]` con `metricas {avisos, resueltas, falsos, silenciados, valor_eur}` | D2 |
| `POST /banco/modulos/borrador` (SSE) | `{descripcion, usuario_id}` | `paso {nombre, estado}`, `borrador` (`BorradorModulo`), `prueba` (`InformePrueba`), `fin`, `error` | D2 |
| `POST /banco/modulos/{id}/aprobar` | `{aprobado_por}` | `Modulo` activo desde el siguiente día simulado (aprobar = activar con un clic) | D2 |
| `GET /metricas/{deteccion\|molestias\|aprendizaje}` | — | último JSON de `evals/resultados/` + `generado` (404 si no hay) | E9 |

**Eventos de `/reloj/reproducir`**: `dia {fecha, movimientos, saldo}`, `perfil {calculado, umbral_relevante_eur}` (cuando se recalcula), `momento` (`Momento`), `propuesta` (`Propuesta`), `decision` (`Decision`), `fin {hoy, contadores}`. Si el navegador corta, el servidor termina el día en curso y guarda. **Evento `tarjeta`** de `/voz/texto`: `TarjetaConfirmacion` (con token; solo para el botón). Del kit siguen igual `/salud`, `/datos/ejemplo`, `/movimientos`, `/movimientos/resumen`, `/chat` y `/chat/stream`.

**`api.ts`** (E10) declara todos los tipos del §3.1 que cruzan la API (`Movimiento`, `Momento`, `Propuesta`, `Decision`, `Feedback`, `TarjetaConfirmacion`, `DetalleBaja`, `ResultadoAccion`, `ModeloUsuario`, `PerfilUsuario`, `FrasePerfil`, `HechoAprendido`, `Amigo`, `SesionVoz`, `Modulo`, `BorradorModulo`, `InformePrueba`) y una función por endpoint de la tabla, también las de las tareas posteriores; el lector SSE del kit pasa a `leerSse(respuesta, alEvento)` y lo usan `preguntar`, `reproducir`, `hablarTexto` y `crearBorrador`. La insignia «IA» (`InsigniaIA`) está siempre visible en la llamada y en el modo texto; cada tarjeta lleva «Simulado».

**E8 (esqueleto)** crea los cuatro routers con **todas** las rutas de la tabla y los incluye en `main.py`; las que aún no tienen tarea hecha responden 501. Así el 10 nov nadie toca `main.py`.

## 5. Herramientas nuevas del agente (modo texto)
En `backend/voz/herramientas_llamada.py`, con el `@herramienta` del kit y el grupo `llamada`: `registro.disponibles()` sin nombres las excluye, así el chat de `/kit` no las ve. `ctx` es una `SesionLlamada` (la `Sesion` del kit con `usuario_id`, `propuesta_id`, movimientos hasta hoy enmascarados y `emitir(tipo, datos)`).
```python
def preparar_accion(accion_id: Literal["pedir_bizum", "cancelar_suscripcion", "bloquear_comercio", "reclamar_cargo",
                    "mover_dinero", "recordar"], contraparte: str | None = None, importe: float | None = None,
                    concepto: str | None = None, comercio: str | None = None, bloquear_cobros: bool | None = None,
                    movimiento_id: str | None = None, motivo: str | None = None, cuando: str | None = None,
                    texto: str | None = None, ctx=None) -> dict:
    """Prepara una de las acciones ofrecidas en esta llamada y muestra al usuario la tarjeta para confirmarla.
    No ejecuta nada: solo el botón «Confirmar» del usuario la ejecuta. Propón primero la primera acción ofrecida.
    En cancelar_suscripcion, la baja la confirma el usuario en el servicio; bloquear_cobros solo corta los cobros
    con tarjeta. Si la acción no está ofrecida o supera sus límites, devuelve el motivo para que se lo expliques.
    (Args: uno por parámetro de la acción.)"""
    # → {"preparada": True, "titulo"} | {"rechazada": motivo}. El token sale por ctx.emitir("tarjeta", …), nunca al modelo.

def registrar_feedback(resultado: Literal["rechazada", "falso_positivo", "no_avisar_tipo", "no_avisar_comercio",
                       "no_avisar_contacto"], ctx=None) -> dict:
    """Registra que el usuario rechaza el aviso, dice que era un error o no quiere más avisos así. Úsala antes de despedirte."""
```
`mover_dinero` usa siempre `origen=ahorro`, `destino=cuenta` (lo fija el servidor). El modo texto usa Sonnet 5.5 con esfuerzo bajo, el revisor de cumplimiento del kit y las herramientas de solo lectura del kit para contestar con cifras de código. El prompt es el de `experiencia.md` §6.1, con el contexto (incluido `contexto_personal` y `memoria_para_agente`) entre `<datos>`; el primer mensaje es fijo y neutro y lo emite el servidor. **El aviso de IA es solo visual** (insignia); si el cliente pregunta, el agente dice que es una IA. Las herramientas de ElevenLabs (opcional) llaman a `/voz/herramientas/*`, que usan las mismas funciones del orquestador.

**Búsqueda web (opcional O9)**: no es una herramienta del agente, sino `conocimiento.info_comercio`, que llama a Claude (Haiku 5.5) con la herramienta de servidor `web_search` (`max_uses = 3`) y salida estructurada validada. `claude_client.preguntar_json` no admite hoy `tools`: O9 le añade el parámetro (cambio pequeño del kit). La consulta es solo el nombre normalizado de un comercio de tarjeta (≤ 30 caracteres, sin dígitos, sin etiqueta `posible_persona`); lo que vuelve va entre `<datos>`.

## 6. Datos
- **Escenarios** (`backend/escenarios/*.yaml`, formato de `motor.md` §5): fondo de `datos/sinteticos.py` (`anomalias=False`, verificaciones de 0 €) más movimientos fijos, `perfil: calcular | <a mano>`, `eventos` (`registrar_prueba`, `cerrar_prueba`) y etiquetas `esperado`/`trampas`. Alimentan tests, `/medir`, la prueba en seco y la demo.
  - **`demo-lucia`** (escenario único de la demo, del test de principio a fin del MVP y de `/medir`): reparto `LAURA M`, `DANIEL P`, `SARA L`, `MARCOS R` (único grupo; ≥ 3 cenas previas donde pagan los cuatro); duplicado «LIBRERIA LUNA» 9,99 € × 2 el 15/10 (`luc-d1`, `luc-d2`; solo con perfil, va al resumen); verificación de 0 € de Streamflix el 14/10 (`luc-v1`); cena en «La Tasca» el 6/11, 120 €, Bizums de 24 € el 6, 7 y 8/11 → momento el **9/11** con y sin perfil; aviso de Streamflix el **10/11**; recibo de la luz con subida de 12 € para el módulo que crea el banco.
  - Unitarios: `cena-lucia` (el esqueleto), `prueba-streamflix-lucia`, los de `cargo_duplicado` y `subida_recibo`, trampas de prueba y `fondo-*` (ruido con y sin perfil).
- **Conocimiento de comercios**: `backend/datos/comercios_conocidos.json` (versionado, solo catálogo revisado a mano, `origen: catalogo`): `STREAMFLIX` (30 días, 9,99 €, URL y pasos de baja), `SONORA MUSIC`, `FITAPP PLUS` (ficticios); marcas reales solo con `tipo` y `es_suscripcion`; comercios que no son de suscripción (`ZARA`, `REPSOL`, `NH HOTELES`, `MERCADONA`). Resultados de la web (opcional): `datos_usuario/_cache/comercios_web.json`, fuera de git. Validación: `url_baja` solo `https` y, si viene de la web, con host igual al dominio oficial de las fuentes (sin `xn--`, IP ni credenciales; se muestra como texto); `pasos_baja` ≤ 5 de ≤ 200 caracteres, sin teléfonos, IBAN, correos, otras URL ni verbos de pago.
- **Perfil de vida**: lo calcula `perfilar` con pandas desde el historial enriquecido (90 días; `None` con < 28). Sin categorías sensibles (lista negra de comercios de salud, citas, religión, política, sindicatos y apuestas fuera de `comercios_habituales`, `suscripciones_activas` y `resumen_vida`). `resumen_vida` por plantilla en el MVP; por Haiku, opcional. El motor ignora las suscripciones con `en_prueba = true` al decidir si un comercio «ya se paga».
- **Usuarios simulados** (`personalizacion/simulacion/`): 4 perfiles (`estudiante`, `holgado`, `social`, `saturable`) con `PerfilUsuario` escrito a mano y preferencias ocultas que la política no importa (test); 4 políticas (`reglas`, `fija`, `perfil`, `personalizada`); 6 semanas con una semilla (10 semillas, opcional).
- **Estado por usuario**: JSON en `datos_usuario/` (§2), escrito con archivo temporal + `os.replace` por `plataforma/almacenamiento.py`, siempre dentro del candado del usuario. En Render el disco es efímero: la demo arranca con `POST /demo/cargar`.
- **Privacidad**: `privacidad.enmascarar` (patrones de `datos/importar_csv.py`: IBAN, teléfono, DNI, correo) en todo lo que sale hacia Claude, ElevenLabs o la auditoría; contrapartes como «nombre + inicial». Las notas de Bizum no salen del motor. Única fuente externa nueva: la búsqueda web de nombres de comercio (opcional, `BUSQUEDA_WEB`).

## 7. Qué se reutiliza y qué se queda igual
Igual: `claude_client.py` (salvo el parámetro `tools` de O9), núcleo del agente, las 14 herramientas, `/chat` y `/chat/stream`, `sse.py`, panel Streamlit, `evals/ejecutar.py` y `casos.yaml`, `Chat.tsx`, `Markdown.tsx`, `Traza.tsx`, `formato.ts`, Docker y `render.yaml`. Cambios pequeños en el kit: `sinteticos.py` (`anomalias`, verificaciones), `agente/registro.py` (grupo `llamada`), `config.py` (`datos_usuario_dir`, `busqueda_web`), `api/main.py` (routers y CORS, solo en E8), `evals/ejecutar.py` (`--conjunto llamada`) y la página actual del frontend, que pasa a `/kit`. Se adaptan sin llamarlas: `detectar_recurrentes`, `prevision_saldo`/`_toca` y `categorias.normalizar`/`categorizar_por_reglas`.

## 8. Variables de entorno (sin valores; nunca en git)
| Variable | Dónde | Para qué |
|---|---|---|
| `ANTHROPIC_API_KEY_PRODUCTO` · `ANTHROPIC_API_KEY_EVALS` · `ANTHROPIC_API_KEY` | backend | Claves 2 y 3; la última, solo como recurso |
| `ELEVENLABS_API_KEY` · `ELEVENLABS_AGENT_ID` | backend | Solo si hay voz real (opcional); jamás en `NEXT_PUBLIC_*` |
| `MODO_DEMO` (`off`, `grabar`, `reproducir`) | backend | Graba y reproduce el modo texto y el borrador de módulo |
| `BUSQUEDA_WEB` (`off` por defecto, `on`) | backend | Con `off` no sale a internet; la demo vive del catálogo precargado |
| `DATOS_USUARIO_DIR` | backend | Por defecto `datos_usuario/`; los tests usan `tmp_path` |
| `NOMBRE_PRODUCTO` (= `Meisam`), `MODELO_CHAT`, `ESFUERZO_CHAT`, `REVISOR_CUMPLIMIENTO`, `ORIGENES_CORS` | backend | Del kit (`ORIGENES_CORS` incluye el dominio de Vercel) |
| `NEXT_PUBLIC_API_URL` · `NEXT_PUBLIC_DEMO_KEY` | frontend | URL del backend y cabecera `X-Demo-Key` (no es seguridad real) |

## 9. Cómo se prueba sin crédito
- `pytest -q`: el fixture `entorno_seguro` borra las claves, pone `BUSQUEDA_WEB=off` y apunta `DATOS_USUARIO_DIR` a `tmp_path`; `falso` sustituye a Claude con `claude_client.usar_cliente`. Ningún test sale a internet (caché de prueba y cliente falso). ElevenLabs se simula parcheando `voz.elevenlabs._pedir`.
- Motor, perfil, módulos, política, orden de acciones y acciones son deterministas: tests por detector y por escenario; no mirar el futuro; **regresión sin perfil** (idéntico a no tener personalización); la cena sale el 9/11 **con y sin perfil**; recalcular el perfil a mitad de `prueba-streamflix-lucia` no mata la prueba; gramática del minilenguaje contra inyección; token reutilizado, caducado, de otro usuario, de otra propuesta o con parámetros alterados; `url_baja` maliciosa omitida y el servidor nunca la sigue; `ordenar_acciones` nunca añade ni quita.
- Principio a fin (MVP, `tests/test_demo_lucia.py`): `TestClient` con `demo-lucia`: `demo/cargar` → `activar` → avanzar → resumen con el duplicado → 9/11 «falta 1 Bizum de 24 €» → `voz/texto` con cliente falso → tarjeta `pedir_bizum` → `acciones/confirmar` → 10/11 Streamflix → `acciones/preparar` `cancelar_suscripcion` con `detalle_baja` → confirmar → prueba cerrada. En el esqueleto basta `cena-lucia`.
- Seguridad: ninguna respuesta de `/voz/*` contiene la clave de ElevenLabs y el frontend no la referencia; el token de confirmación nunca aparece en lo que recibe un modelo.
- `python evals/medir.py --parte motor|personalizacion|todo` no gasta: escribe `evals/resultados/{motor,personalizacion}-<fecha>.json` (versionados), que lee `/jurado`. `/evals` (clave 3) sí gasta: al cerrar el MVP y si cambia un prompt.
- Frontend: `npm run build`; maquetas en `frontend/public/demo/*.json` mientras falta el backend.

## 10. Despliegue y trabajo en paralelo
Backend en Render (Docker), frontend en Vercel (raíz `frontend/`); ver `docs/DESPLIEGUE.md`. Se despliega el esqueleto la mañana del 10 y después cada noche. Dueños de archivos por hilo y día en `docs/PLAN.md` («Tareas»): una zona, un hilo a la vez; `tipos.py`, `CONTRATO.md`, `ARQUITECTURA.md` y `PLAN.md` solo los cambia el orquestador.
