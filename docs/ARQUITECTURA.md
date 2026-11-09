# Arquitectura

Arquitectura objetivo del Copiloto, cerrada en `/planificar` (9 nov, tarde). Manda `docs/diseno/CONTRATO.md` (tipos e interfaces); el detalle de cada parte está en `docs/diseno/{motor,personalizacion,modulos,experiencia}.md`. Este archivo fija lo que comparten las zonas: paquetes, API, herramientas, datos y pruebas.

## 1. Componentes y flujo
```
Navegador (Next.js): /app (cliente) · /app/llamada/[id] · /banco (consola) · /jurado · /kit (chat del kit)
   │ HTTP + SSE (frontend/lib/api.ts)                     │ WebRTC/WebSocket con token de ElevenLabs
   ▼                                                      ▼
API FastAPI (backend/api: main.py + un router por zona)   Agente de voz ElevenLabs (herramientas de cliente
   │                                                       → /voz/herramientas/*)
   ▼
plataforma/orquestador  (candado por usuario; único que dispara escrituras en datos_usuario/)
   reloj simulado ─> movimientos del día (escenario)
   ├─ motor.procesar ─> Momento[]           (normalizar → enriquecer → detectores → razonador; sin Claude)
   ├─ modulos.proponer ─> Propuesta[]       (catálogo YAML + módulos aprobados; sin Claude)
   ├─ personalizacion.decidir ─> Decision   (reglas duras + Beta jerárquica; motivos legibles)
   ├─ acciones.preparar / ejecutar          (token de un solo uso, límites, banco simulado, auditoría)
   └─ personalizacion.aprender / observar / registrar_*  (ModeloUsuario: hechos y amigos)
voz: sesion (modo voz | texto_el | texto_kit) · texto = agente del kit con contexto de la propuesta
Claude, siempre por backend/claude_client.py: Sonnet 5.5 (modo texto, crear módulos), Haiku 5.5 (memoria, opcional)
```
Un día simulado: `avanzar_dia` lee los movimientos de ese día → `motor.procesar` → por cada momento, `modulos.proponer` → `decidir` → `registrar_decision` (crea amigos) → `observar` (salda amigos, líneas base) → emite `ignorada` a las 48 h sin respuesta → guarda. Ningún detector ve movimientos con `fecha > hoy`.

## 2. Paquetes y archivos clave
```
backend/
  plataforma/  tipos.py (pydantic del contrato) · reloj.py · almacenamiento.py (JSON atómico) · orquestador.py · privacidad.py (enmascarar)
  motor/       __init__.py (procesar, cargar_historial, exportar/importar_estado, reiniciar) · normalizar.py · enriquecer.py
               parametros.py · razonador.py · estado.py · detectores/{__init__, gasto_compartido, cargo_duplicado,
               renovacion_proxima, saldo_negativo_previsto, subida_recibo}.py
  escenarios/  cargar.py · *.yaml (cena-lucia, trampas, fondo-*, demo-lucia)
  personalizacion/ __init__.py · politica.py · aprendizaje.py · motivos.py · amigos.py · lineas_base.py · edicion.py
               · memoria.py (opcional) · simulacion/{perfiles, generador, protocolo}.py
  modulos/     __init__.py · esquema.py · campos_momento.py · condiciones.py · plantillas.py · registro.py · proponer.py
               · creacion.py · prueba_seco.py · catalogo/{cena_compartida, cobro_duplicado, renovacion, colchon}.yaml
  acciones/    __init__.py (preparar, ejecutar, deshacer) · registro.py (las 6) · banco_sim.py · tokens.py · auditoria.py
  voz/         __init__.py (sesion) · elevenlabs.py (token/URL firmada, urllib) · sesiones.py (token_sesion en memoria)
               · contexto.py (variables enmascaradas) · texto.py (modo texto_kit) · herramientas_llamada.py
  api/         main.py (kit + include_router) · rutas_copiloto.py · rutas_voz.py · rutas_banco.py · rutas_metricas.py · sse.py (kit)
evals/         ejecutar.py + casos.yaml (kit) · casos_llamada.yaml · medir.py (--parte) · medir_motor.py · medir_personalizacion.py
frontend/      app/{page (portada), kit, app, app/llamada/[propuestaId], app/aprendido, app/amigos, banco, jurado}
               components/{Activacion, Bandeja, RelojDemo, Llamada, Transcripcion, TarjetaAccion, PorQue, Aprendido,
               SaldosAmigos, TablaModulos, NuevoModulo, PruebaEnSeco, Precision, MolestiasEvitadas, CurvaAprendizaje}.tsx
               lib/api.ts (contrato en TypeScript; reutiliza leerJson y el lector SSE)
datos_usuario/ (fuera de git) <usuario_id>/{reloj, modelo, motor, momentos, propuestas, decisiones, feedback, banco, tokens}.json
               + auditoria.jsonl · _modulos/<id>.yaml (aprobados por el banco)
```
Cada `__init__.py` nuevo exporta desde `/esqueleto` todas las funciones del contrato (las que faltan, como *stub* que devuelve un ejemplo válido o lanza `NotImplementedError`): así las zonas crecen sin tocar archivos ajenos.

## 3. Contrato de la API
Convenciones: JSON; dinero `Decimal` serializado como **cadena** con 2 decimales (`"24.00"`, tipo `Euros = string` en `api.ts`; el frontend solo lo formatea); fechas ISO del reloj simulado. Errores `{"detail": "…"}`: 400 datos, 403 acción no ofrecida o fuera de límites, 404, 409 token ya usado o prueba en seco no superada, 410 token caducado. Sin autenticación (usuarios sintéticos): `usuario_id` va en la ruta o el cuerpo; en la llamada solo cuenta el `token_sesion`. SSE con `evento_sse` del kit (`event: <tipo>` + `data: <json>`); todo flujo termina en `fin` o `error`. CORS: `GET, POST, PATCH, DELETE`.

| Método y ruta | Cuerpo o consulta | Devuelve |
|---|---|---|
| `GET /escenarios` | — | `[{id, usuario_id, descripcion}]` |
| `POST /demo/cargar` | `{escenario_id}` | `{usuario_id, hoy, activacion}`; reinicia el usuario y pone el reloj en la activación |
| `POST /usuarios/{id}/activar` | `{modulos_activos: str[], consentimientos: {avisos, memoria}}` | `ModeloUsuario` (llama a `motor.cargar_historial`) |
| `GET /usuarios/{id}/estado` | — | `{hoy, activado, saldo, contadores: {momentos, ahora, resumen, silenciadas}}` |
| `POST /reloj/avanzar` | `{usuario_id, dias: 1-60}` | `{hoy, decisiones: Decision[]}` |
| `GET /reloj/reproducir` (SSE) | `?usuario_id&dias&ms_por_dia=1500` | eventos `dia`, `momento`, `propuesta`, `decision`, `fin`, `error` |
| `GET /usuarios/{id}/notificaciones` | `?bandeja=ahora\|resumen\|silenciadas` | `[{propuesta, decision, estado: nueva\|vista\|resuelta\|rechazada\|ignorada}]` |
| `GET /usuarios/{id}/propuestas/{pid}` | — | `{propuesta, decision, momento, movimientos}` (enmascarados) |
| `POST /feedback` | `{usuario_id, propuesta_id, resultado, canal, nota?}` | `{ok, hechos_nuevos: HechoAprendido[]}`; fecha del reloj |
| `POST /acciones/confirmar` | `{usuario_id, token_confirmacion}` | `ResultadoAccion` |
| `POST /acciones/deshacer` | `{usuario_id, resultado_id}` | `ResultadoAccion` (opcional O4) |
| `GET /usuarios/{id}/aprendido` | — | `HechoAprendido[]` |
| `PATCH /usuarios/{id}/aprendido/{hid}` · `DELETE …/{hid}` · `DELETE /usuarios/{id}/aprendido` | `{activo?, texto?}` | hecho · `{ok}` · `{ok}` (olvidar todo) |
| `GET /usuarios/{id}/amigos` | — | `Amigo[]` |
| `POST /voz/sesion` | `{propuesta_id, usuario_id, modo_preferido: voz\|texto_el\|texto_kit}` | `SesionVoz {modo, token?, signed_url?, variables, token_sesion, caduca}` |
| `POST /voz/texto` (SSE) | `{token_sesion, mensaje?}` (sin mensaje = saludo fijo con aviso de IA) | eventos del kit (`texto`, `herramienta_inicio`, `herramienta_fin`, `revision`, `fin`, `error`) + `tarjeta` |
| `POST /voz/herramientas/preparar` | `{token_sesion, accion_id, parametros}` | `{tarjeta: TarjetaConfirmacion}` o `{rechazo: str}` |
| `POST /voz/herramientas/feedback` | `{token_sesion, resultado}` | `{ok}` (colgar sin acción = `vista_sin_accion`) |
| `POST /voz/herramientas/consultar` | `{token_sesion, pregunta}` | `{respuesta}` (opcional O3) |
| `GET /banco/modulos` | — | `Modulo[]` con `metricas {avisos, resueltas, falsos, silenciados, valor_eur}` |
| `POST /banco/modulos/borrador` (SSE) | `{descripcion, usuario_id}` | eventos `paso {nombre, estado}`, `borrador` (`BorradorModulo`), `prueba` (`InformePrueba`), `fin`, `error` |
| `POST /banco/modulos/{id}/aprobar` | `{aprobado_por}` | `Modulo` activo desde el siguiente día simulado (409 si la prueba no pasa) |
| `GET /metricas/{deteccion\|molestias\|aprendizaje}` | — | último JSON de `evals/resultados/` + `generado` (404 si no hay) |

Eventos de `/reloj/reproducir`: `dia {fecha, movimientos, saldo}`, `momento` (`Momento`), `propuesta` (`Propuesta`), `decision` (`Decision`), `fin {hoy, contadores}`. Si el navegador corta, el servidor termina el día en curso y guarda (cada día se guarda entero). Evento `tarjeta` de `/voz/texto`: `TarjetaConfirmacion` (con el token; solo para el botón). Del kit siguen igual `/salud`, `/datos/ejemplo`, `/movimientos`, `/movimientos/resumen`, `/chat` y `/chat/stream`.

`api.ts` declara los tipos del contrato (`Movimiento`, `Momento`, `Propuesta`, `Decision`, `Feedback`, `TarjetaConfirmacion`, `ResultadoAccion`, `ModeloUsuario`, `HechoAprendido`, `Amigo`, `SesionVoz`, `Modulo`, `BorradorModulo`, `InformePrueba`) y una función por endpoint; el lector SSE del kit pasa a `leerSse(respuesta, alEvento)` y lo usan `preguntar`, `reproducir`, `hablarTexto` y `crearBorrador`.

## 4. Herramientas nuevas del agente (modo texto)
En `backend/voz/herramientas_llamada.py`, con el `@herramienta` del kit y el grupo `llamada`: `registro.disponibles()` sin nombres las excluye, así el chat de `/kit` no las ve. `ctx` es una `SesionLlamada` (la `Sesion` del kit con `usuario_id`, `propuesta_id`, movimientos hasta hoy enmascarados y `emitir(tipo, datos)`).
```python
def preparar_accion(accion_id: Literal["pedir_bizum", "bloquear_comercio", "reclamar_cargo", "mover_dinero",
                    "preparar_baja", "recordar"], contraparte: str | None = None, importe: float | None = None,
                    concepto: str | None = None, comercio: str | None = None, movimiento_id: str | None = None,
                    motivo: str | None = None, cuando: str | None = None, texto: str | None = None, ctx=None) -> dict:
    """Prepara una de las acciones ofrecidas en esta llamada y muestra al usuario la tarjeta para confirmarla.
    No ejecuta nada: solo el botón «Confirmar» del usuario la ejecuta. Si la acción no está ofrecida o supera
    sus límites, devuelve el motivo del rechazo para que se lo expliques. (Args: uno por parámetro.)"""
    # → {"preparada": True, "titulo", "parametros_legibles"} | {"rechazada": motivo}. El token sale por ctx.emitir("tarjeta", …), nunca al modelo.

def registrar_feedback(resultado: Literal["rechazada", "falso_positivo", "no_avisar_tipo", "no_avisar_comercio",
                       "no_avisar_contacto"], ctx=None) -> dict:
    """Registra que el usuario rechaza el aviso, dice que era un error o no quiere más avisos así. Úsala antes de despedirte."""
```
`mover_dinero` usa siempre `origen=ahorro`, `destino=cuenta` (lo fija el servidor). El modo texto usa Sonnet 5.5 con esfuerzo bajo, el revisor de cumplimiento del kit y, además, las herramientas de solo lectura del kit para contestar con cifras de código. El prompt es el de `experiencia.md` §6.1, con el contexto entre `<datos>`; el primer mensaje es fijo y lo emite el servidor. Las herramientas de ElevenLabs (`preparar_accion`, `registrar_feedback`, `consultar`) llaman a `/voz/herramientas/*`, que usan las mismas funciones del orquestador.

## 5. Datos
- **Escenarios** (`backend/escenarios/*.yaml`, formato de `motor.md` §4): fondo de `datos/sinteticos.py` (gana `anomalias=False`) más movimientos fijos y etiquetas `esperado`/`trampas`. Alimentan tests, `/medir`, la prueba en seco y la demo (`demo-lucia`: 8 semanas con la cena, un cobro duplicado de 9,99 €, una renovación anual y un recibo de luz que sube 12 €).
- **Usuarios simulados** de la personalización: `personalizacion/simulacion/` (4 perfiles ocultos, 10 semillas); la política no los importa (test).
- **Estado por usuario**: JSON en `datos_usuario/` (§2), escrito con archivo temporal + `os.replace` por `plataforma/almacenamiento.py`, siempre dentro del candado del usuario que toma el orquestador. `acciones` escribe `banco`, `tokens` y `auditoria` a través de ese mismo módulo. En Render el disco es efímero: la demo arranca con `POST /demo/cargar`.
- **Privacidad**: `privacidad.enmascarar` (reutiliza los patrones de `datos/importar_csv.py`: IBAN, teléfono, DNI, correo) en todo lo que sale hacia Claude, ElevenLabs o la auditoría; contrapartes como «nombre + inicial». Sin fuentes externas nuevas.

## 6. Qué se reutiliza y qué se queda igual
Igual: `claude_client.py`, núcleo del agente, las 14 herramientas, `/chat` y `/chat/stream`, `sse.py`, panel Streamlit, `evals/ejecutar.py` y `casos.yaml`, `Chat.tsx`, `Markdown.tsx`, `Traza.tsx`, `formato.ts`, Docker y `render.yaml`. Cambios pequeños en el kit: `sinteticos.py` (`anomalias`), `agente/registro.py` (grupo `llamada`), `config.py` (`datos_usuario_dir`), `api/main.py` (routers y CORS), `evals/ejecutar.py` (`--conjunto llamada`) y la página actual del frontend, que pasa a `/kit`. Se adaptan sin llamarlas: `detectar_recurrentes`, `prevision_saldo`/`_toca` y `categorias.normalizar`/`categorizar_por_reglas`.

## 7. Variables de entorno (sin valores; nunca en git)
| Variable | Dónde | Para qué |
|---|---|---|
| `ANTHROPIC_API_KEY_PRODUCTO` · `ANTHROPIC_API_KEY_EVALS` · `ANTHROPIC_API_KEY` | backend | Claves 2 y 3; la última, solo como recurso |
| `ELEVENLABS_API_KEY` · `ELEVENLABS_AGENT_ID` | backend | Token o URL firmada de la llamada; jamás en `NEXT_PUBLIC_*` |
| `MODO_DEMO` (`off`, `grabar`, `reproducir`) | backend | También graba y reproduce el modo texto y el borrador de módulo |
| `DATOS_USUARIO_DIR` (nueva) | backend | Por defecto `datos_usuario/`; los tests usan `tmp_path` |
| `NOMBRE_PRODUCTO`, `MODELO_CHAT`, `ESFUERZO_CHAT`, `REVISOR_CUMPLIMIENTO`, `ORIGENES_CORS` | backend | Del kit (`ORIGENES_CORS` incluye el dominio de Vercel) |
| `NEXT_PUBLIC_API_URL` | frontend | URL del backend; la única variable del navegador |

## 8. Cómo se prueba sin crédito
- `pytest -q`: el fixture `entorno_seguro` borra las claves y apunta `DATOS_USUARIO_DIR` a `tmp_path`; `falso` sustituye a Claude con `claude_client.usar_cliente`. ElevenLabs se simula parcheando `voz.elevenlabs._pedir`.
- Motor, módulos, política y acciones son deterministas: tests unitarios por detector y por escenario, test de no mirar el futuro, gramática del minilenguaje contra inyección, token reutilizado, caducado, de otra propuesta o con parámetros alterados.
- Principio a fin: `TestClient` con `cena-lucia`: `demo/cargar` → `activar` → `reloj/avanzar` → notificación «falta 1 Bizum de 24 €» → `voz/herramientas/preparar` → `acciones/confirmar` → amigo `pedido` → feedback.
- Seguridad: ninguna respuesta de `/voz/*` contiene la clave de ElevenLabs y el frontend no la referencia (búsqueda en `frontend/`).
- `python evals/medir.py --parte motor|personalizacion|todo` no gasta: escribe `evals/resultados/{motor,personalizacion}-<fecha>.json`, que lee `/jurado`. `/evals` (clave 3) sí gasta: solo al cerrar el MVP y si cambia un prompt.
- Frontend: `npm run build`; maquetas en `frontend/public/demo/*.json` mientras falta el backend.

## 9. Despliegue y trabajo en paralelo
Backend en Render (Docker), frontend en Vercel (raíz `frontend/`); ver `docs/DESPLIEGUE.md`. Se despliega el esqueleto y luego cada noche. Dueños de archivos por hilo en `docs/PLAN.md` («Tareas»): una zona, un hilo a la vez; `tipos.py`, `CONTRATO.md` y este archivo solo los cambia el orquestador.
