# Diseño del motor de momentos

9 de noviembre de 2026. Autor: `ingeniero-deteccion`. Respeta `CONTRATO.md`; manda su sección «Cambios de Pablo (9 nov, noche)» y, después, la «Revisión final».

## 1. Resumen
- El motor convierte movimientos en `Momento`s **en línea**: `procesar(usuario_id, nuevos, hoy, perfil=None)` añade `nuevos` al historial y cada detector ve solo `fecha <= hoy`.
- Cinco pasos: normalizar (comercio, contraparte, canal, `tipo_operacion`) → enriquecer (series con `serie_id`, líneas base propias) → ajustar parámetros con el `PerfilUsuario` → detectores deterministas (pandas + `Decimal`) → razonador (deduplica, filtra, prioriza, explica y pone el contexto personal).
- **MVP**: `gasto_compartido` (estrella), `cargo_duplicado`, `renovacion_proxima`, `subida_recibo` y `prueba_gratuita`. **Si sobra tiempo**: `saldo_negativo_previsto` y `posible_estafa`.
- Sin Claude en el camino de detección: `explicacion` y `contexto_personal` salen de plantillas. Claude solo entra en `conocimiento.py` (búsqueda web de comercios), fuera del camino caliente y tras `BUSQUEDA_WEB`.
- Todo se mide con escenarios YAML etiquetados en `backend/escenarios/`, que alimentan tests, `/medir motor` y la demo.

## 2. Pipeline
**Estado por usuario** (`EstadoMotor`, en memoria): historial enriquecido, series, líneas base, `pruebas` (abiertas y cerradas), `comercios_pendientes` y `claves_emitidas`. El orquestador lo guarda con `exportar_estado`/`importar_estado`. `procesar` lanza un error si algún movimiento de `nuevos` tiene `fecha > hoy`. El perfil **no** se guarda en el motor: es de la personalización y llega en cada llamada.

**2.1 Normalización** (`motor/normalizar.py`, reglas puras):
- `canal`: si falta, se deduce del concepto (`BIZUM` → bizum, `RECIBO`/`ADEUDO` → recibo, `COMPRA TARJETA`/`COMPRA ONLINE` → tarjeta, `TRANSFERENCIA` → transferencia, `CAJERO`/`REINTEGRO` → cajero).
- `tipo_operacion`: si falta, `importe == 0` o concepto `VERIFICACION|AUTORIZACION|PREAUTORIZ` con `|importe| <= 1 €` → `verificacion`; abono con `DEVOLUCION|ANULACION|ABONO` → `devolucion`; el resto → `cargo`. Las series, el duplicado y la subida solo miran `cargo`.
- `comercio_normalizado`: `comercio` o el concepto; `categorias.normalizar` (mayúsculas, sin tildes), sin prefijos (`COMPRA TARJETA`, `RECIBO`, `COMPRA ONLINE`, `PAGO`), sufijos de tarjeta (`*1234`), dominios (`.COM`, `.ES`) ni ciudad final. Alias en un diccionario (`AMZN MKTP` → `AMAZON`). **Pasarelas**: `PAYPAL *STREAMFLIX` → `STREAMFLIX` (etiqueta `pasarela`); si la pasarela oculta el nombre (`APPLE.COM/BILL`, `GOOGLE *SERVICES`), el comercio queda como la pasarela y no se busca. **`posible_persona`**: descriptores de TPV de autónomos (`SUMUP *`, `ZETTLE *`, `SQ *`) seguidos de dos o tres palabras que no son una marca del catálogo (`SUMUP *JUAN PEREZ`).
- `contraparte_normalizada` (Bizum y transferencias): clave = nombre + inicial del primer apellido (`LAURA MARTINEZ GARCIA` → `LAURA M`). Función pública `clave_contraparte`, que **la personalización reutiliza** para `perfil.grupos` (misma clave en los dos lados).
- `categoria`: la del movimiento o `categorizar_por_reglas` del kit.

**2.2 Enriquecimiento** (`motor/enriquecer.py`), recalculado en cada `procesar` (cientos de filas, milisegundos):
- **Series**: adaptación de `detectar_recurrentes` del kit por `comercio_normalizado`, con `Decimal` y periodos de 1, 3, 6 y 12 meses (anual: 2 cargos entre 330 y 400 días, o 1 con `ANUAL|ANNUAL|YEARLY|12 MESES`). `serie_id = "<COMERCIO>:<periodo>m"`. Guarda `importe_habitual` (mediana), `dia_habitual`, `variacion`, `veces`, `ultimo`, `fijo` (variación ≤ 5 %).
- **Etiquetas**: `reembolso_entrante`, `cargo_serie`, `comercio_nuevo` (primera vez en 180 días), `verificacion`.
- **Líneas base propias** (respaldo sin perfil): `retraso_reembolso_p75` y `grupos` (contrapartes que aparecen juntas en reembolsos previos).

**2.3 Parámetros personales** (`motor/parametros.py`): una dataclass por detector con valores por defecto y una sola función `ajustar(params, perfil) -> params`. **Sin perfil = valores por defecto** (arranque en frío, idéntico a hoy; hay test de regresión). Los campos del perfil que falten no cambian nada. El motor **no lee** `resumen_vida` (es texto de Haiku).

| Detector | Campo del perfil | Defecto | Con perfil (ejemplo Lucía: `ticket_tipico` 12 €, `umbral_relevante_eur` 40 €) |
|---|---|---|---|
| `gasto_compartido` | `ticket_tipico` | `IMPORTE_MIN_PAGO` = 30 € | `clamp(2 × ticket, 20, 60)` → 24 € |
| `gasto_compartido` | `grupos` | candidatos de los grupos propios, `MIN_COINCIDENCIAS` = 2 | grupo del perfil con más miembros entre los que ya pagaron (≥ 2, o ≥ 1 si el grupo tiene ≤ 4); candidatos = miembros − pagadores, por `veces`; +0,10 de confianza si `len(grupo) == personas_estimadas − 1` |
| `gasto_compartido` | `grupos[].retraso_p75_dias` | `DIAS_ESPERA = clamp(p75 propio + 1, 2, 5)`, 3 | el mismo cálculo con el p75 del grupo |
| `cargo_duplicado` | `ticket_tipico` | `IMPORTE_MIN_TARJETA` = 15 € | `clamp(0,5 × ticket, 5, 30)` → 6 € |
| `renovacion_proxima` | `umbral_relevante_eur` | antelación anual 15 días | 21 días si `importe >= umbral` |
| `renovacion_proxima` | `suscripciones_activas` | — | +0,10 de confianza si la serie está en la lista |
| `subida_recibo` | `umbral_relevante_eur` | `SUBIDA_MIN_ANUAL` = 12 € | `max(12, 0,10 × umbral)` |
| `cargo_duplicado` (demo) | `ticket_tipico` | 9,99 € < 15 € no avisa | Lucía: 9,99 € ≥ 6 € → avisa (va al resumen por decisión de la personalización) |
| `prueba_gratuita` | `suscripciones_activas` | solo series del historial | un comercio de la lista «ya se paga» y no puede estar en prueba; se **ignoran** las entradas con `en_prueba = true` |
| `saldo_negativo_previsto` (si sobra) | `dia_cobro_nomina`, `ingreso_mensual_tipico` | ingresos de las series | la nómina entra en la proyección en su día |

**2.4 Detectores** (`motor/detectores/<tipo>.py`): `detectar(ctx) -> list[Momento]`; `ctx` = `hoy`, `historial` (≤ hoy), `nuevos`, `series`, `lineas_base`, `perfil`, `params` (ya ajustados) y `conocimiento` (solo lectura de la caché). Registro en `detectores/__init__.py`.

**2.5 Razonador** (`motor/razonador.py`):
1. **Clave estable** por tipo → `Momento.id = "mom-<tipo>-<sha1(clave)[:10]>"`; si ya está en `claves_emitidas`, no se repite (idempotente).
2. **Filtro**: `confianza >= 0,5`.
3. **Solapes** (un movimiento en dos momentos): `posible_estafa` (si sobra) > `cargo_duplicado` > `saldo_negativo_previsto` (si sobra) > `gasto_compartido` > `prueba_gratuita` > `subida_recibo` > `renovacion_proxima`.
4. **Orden**: prioridad y luego `impacto_eur`.
5. **`explicacion`**: plantilla por tipo en formato español («Pagaste 120,00 € en La Tasca y te han devuelto 72,00 € de 3 personas; falta 1 (24,00 €)»). `subida_recibo` dice «ha subido», nunca «te han cobrado de más». Las notas de Bizum no salen del motor.
6. **`impacto_relativo` y `contexto_personal`** (solo con perfil y `impacto_eur`; código y plantillas, sin Claude). Se usa la primera regla que tenga datos:
   - a) `saldo_hoy` (último `saldo` ≤ hoy) > 0 y `dia_cobro_nomina`: `impacto_relativo = impacto_eur / saldo_hoy` → «Te quedan {d} días hasta la nómina y son el {pct} % de lo que te queda». Si ≥ 100 %: «Es más de lo que te queda hasta la nómina ({d} días)».
   - b) `ingreso_mensual_tipico`: `impacto_eur / ingreso` → «Es el {pct} % de lo que sueles ingresar al mes».
   - c) `umbral_relevante_eur`: `impacto_eur / umbral` → solo si ≥ 1: «Está por encima de lo que para ti es un gasto importante ({umbral} €)».
   - Extra para `prueba_gratuita` y `renovacion_proxima`: si el cobro cae en los 5 días antes de la nómina, se antepone «El cobro llega {n} días antes de tu nómina».
   - `impacto_relativo` es `Decimal` con 2 decimales; si `pct < 1 %`, no hay frase. Solo cifras: nada de categorías sensibles ni de valorar a terceros.
7. `version = "motor-0.2/<tipo>-<n>"` y `detector = "<tipo>"`.

`impacto_eur`: duplicado = importe; renovación = próximo cargo; compartido = `importe_pendiente`; subida = `subida_eur × cargos al año`; prueba = `importe_previsto` (si no se conoce, `None`); saldo (si sobra) = `importe_para_cubrir`.

## 3. Detectores
En `datos` los importes van en **positivo** (`Decimal`, 2 decimales), las fechas en ISO y las listas `ids` ordenadas por fecha.

### 3.1 `gasto_compartido` (la estrella)
**Pagos**: cargo de tarjeta ≥ `IMPORTE_MIN_PAGO`, que no es de una serie y de categoría `restaurantes`, `ocio`, `supermercado`, `compras` o `transporte`.
**Reembolsos**: Bizums o transferencias **recibidos** en `[pago, pago + VENTANA_REEMBOLSO = 7 días]`; cada uno se asigna al pago anterior más cercano cuya cuota encaje.
**Cuota y personas**: `cuota` = mediana de los reembolsos a ≤ `TOL_CUOTA = 0,50 €` de la mediana (`MIN_REEMBOLSOS = 2`). `personas = round(total / cuota)`, válido si `|total − personas × cuota| ≤ max(1 €, 3 %)` y `3 <= personas <= 12`. `faltan = personas − 1 − reembolsos`; `importe_pendiente = faltan × cuota`.
**Cuándo**: primer `hoy` con `hoy − pago >= DIAS_ESPERA` y `hoy − último reembolso >= 1`, mientras `faltan >= 1` y `hoy − pago <= 7`. Lucía (cena el 6/11; Bizums el 6, 7 y 8; `retraso_p75 = 2` → `DIAS_ESPERA = 3`) → **9/11**, con perfil y sin él.
**Candidatos**: ver §2.3 (perfil o grupos propios); se guardan los `faltan × 2` mejores.
**`datos`**: `pago_id`, `comercio`, `importe_total`, `fecha`, `reembolsos [{contraparte, importe, id}]`, `personas_estimadas`, `faltan`, `importe_pendiente`, `candidatos [{contraparte, importe}]` (importe = cuota) y `cuota`. Clave: `pago_id`.
**Confianza**: 0,50 + 0,15 si el reparto cuadra a ±0,05 € por persona + 0,10 si hay ≥ 3 reembolsos + 0,10 si alguna nota tiene palabras de plan (`cena|comida|pizza|birra|cumple de|regalo para`, 🍕🍝🍻) + 0,10 si el candidato principal tiene ≥ 3 coincidencias (o encaja el grupo del perfil) − 0,15 si `personas > 8`. Máximo 0,95.
**No hace**: cuotas desiguales (no avisa); si el amigo paga después, lo salda la personalización (`amigos`).

### 3.2 `cargo_duplicado`
**Par**: cargo nuevo B y cargo anterior A del mismo comercio e **importe al céntimo**, `0 <= B − A <= 3 días`, sin abono igual entre los dos.
**Exclusiones**: verificaciones; tarjeta < `IMPORTE_MIN_TARJETA`; `transporte`; patrón habitual (el mismo par ya apareció en un periodo anterior: dos cuotas de gimnasio cada mes); ≥ 8 compras en 30 días en ese comercio si va con tarjeta y es < 50 €.
**Confianza**: 0,90 si A es de una serie y B cae en el mismo periodo; 0,85 si es recibo; tarjeta 0,70 el mismo día y 0,55 con 1-3 días. **Cuándo**: el día que entra B.
**`datos`**: `comercio`, `importe`, `fechas`, `ids`, `id_segundo`, `dias_entre`, `canal`, `fecha_limite_devolucion?` (recibo: B + 8 semanas), `serie_id?`. Clave: `ids`.

### 3.3 `renovacion_proxima`
**Series avisables**: de cargo, categoría `suscripciones`, `ocio`, `seguros` o `compras`, tarjeta o recibo, periodo de 3, 6 o 12 meses (`INCLUIR_MENSUALES = False`). **Fecha prevista**: `ultimo + periodo` en el `dia_habitual`. **Cuándo**: primer `hoy` con `0 < fecha_prevista − hoy <= ANTELACION` (7 días trimestral o semestral; anual según §2.3).
**`datos`**: `comercio`, `importe`, `periodicidad`, `fecha_prevista`, `dias_hasta`, `veces_cobrado`, `serie_id`. Clave: `serie_id + fecha_prevista`. **Confianza**: 0,60 + 0,10 por cargo más allá del segundo (máx. 0,90) − 0,10 si el día varía > 2; 0,50 si es anual de un cargo con marcador.

### 3.4 `subida_recibo`
Cargo nuevo de una serie con ≥ 3 cargos, `importe > habitual × 1,08` y `> habitual + 2 €` (series variables como luz o agua: 25 %), y `subida_eur × cargos al año >= SUBIDA_MIN_ANUAL`. **Cuándo**: el día del cargo. `datos` del contrato. Confianza 0,60 + 0,10 por cargo más allá del tercero (máx. 0,90). Clave: id del cargo.

### 3.5 `prueba_gratuita` (nuevo)
**Realismo**: la señal son las **autorizaciones** que recibe el banco emisor (también las de 0 €), no el extracto. No cubre las pruebas sin verificación ni los comercios ocultos tras una pasarela (Apple, Google); `PAYPAL *X` se normaliza cuando se puede. Por eso existe también la vía «el cliente lo dice». No se promete cobertura total.
**Alta por verificación**: un movimiento con `tipo_operacion = verificacion` e importe 0 €, o de ≤ `IMPORTE_MAX_VERIF = 1 €` que se devuelve (devolución del mismo comercio e importe en ≤ `VENTANA_DEVOLUCION_VERIF = 5 días`), cuyo comercio:
- es de suscripciones según `InfoComercio.es_suscripcion` de la caché. Si no está en la caché, se añade a `comercios_pendientes` y se reevalúa cada día (la búsqueda llega al día siguiente, con margen de sobra). Sin caché ni búsqueda: categoría `suscripciones` por reglas, con confianza máxima 0,55;
- **no tiene serie previa**: ningún `cargo` > 1 € suyo en `DIAS_SIN_SERIE = 365` y no está en `perfil.suscripciones_activas` con `en_prueba = false` (si no, es un cambio de tarjeta). Las entradas con `en_prueba = true` se ignoran: recalcular el perfil a mitad de la prueba no la mata (hay test);
- no tiene ya una prueba abierta o cerrada en esos 365 días.

**Duración**: `dias_prueba` de la caché (`fuente_duracion = catalogo` si viene precargada, `web` si la trajo la búsqueda) o `DIAS_PRUEBA_POR_DEFECTO = 30` (`por_defecto`). `fecha_primer_cobro = fecha_alta + dias_prueba`; `importe_previsto = precio_tras_prueba`.
**Alta por el cliente** (`fuente: usuario`): `registrar_prueba(usuario_id, comercio, fecha_alta, dias: int | None, hoy)` (exige `fecha_alta <= hoy`), llamado por el orquestador cuando el cliente lo dice en la app o en la llamada (la extracción del comercio no es del motor; el botón «He empezado una prueba» es opcional). Si hay una verificación del mismo comercio a ±3 días, se fusionan (`verificacion_id` se rellena). Duración: la que diga el cliente > caché > 30.
**Cuándo**: primer `hoy` con `0 < fecha_primer_cobro − hoy <= AVISO_DIAS_ANTES = 3`; con `por_defecto`, `AVISO_DIAS_ANTES + 2 = 5` (la duración es una suposición). Si el alta llega tarde, se avisa mientras quede ≥ 1 día.
**Cierre** (la prueba pasa a cerrada y no emite nada más):
- **Cobrada**: entra un `cargo` > 1 € del comercio entre el alta y `fecha_primer_cobro + 7`. Ese cargo empieza la serie; renovación y subida siguen su curso.
- **Cancelada**: `cerrar_prueba(usuario_id, comercio, motivo, hoy)`. La llama el orquestador al ejecutar `cancelar_suscripcion` con `bloquear_cobros = true` o cuando el cliente dice que ya la ha cancelado. Antes del aviso, no hay momento.
- **Baja guiada** (`cancelar_suscripcion` con `bloquear_cobros = false`): `cerrar_prueba(..., motivo="baja_guiada", hoy)` deja la prueba en `baja_guiada`, sin más momentos; el recordatorio del día antes lo crea el orquestador. Si después llega el cobro, pasa a cobrada.
- **Caducada**: `hoy > fecha_primer_cobro + 7` sin cargo.

**`datos`**: `comercio`, `fecha_alta`, `dias_prueba`, `fecha_primer_cobro`, `dias_hasta`, `importe_previsto?`, `fuente`, `fuente_duracion`, `verificacion_id?` y además `fuentes_info` (URLs de `InfoComercio`, para mostrar de dónde sale cada cifra). Clave: `comercio + fecha_alta`. Evidencias: verificación (y su devolución).
**Confianza**: 0,60 + 0,20 si la verificación es explícita (0 € o 1 € devuelto) + 0,10 si la duración es de `catalogo` o `web` − 0,15 si es `por_defecto`; `usuario`: 0,90. Máximo 0,95.

### 3.6 Si sobra tiempo
- **`saldo_negativo_previsto`** (fuera del MVP, se conserva el diseño): requiere `saldo`. Proyección de `HORIZONTE = 10 días` con las series y la mediana del gasto variable diario (y la nómina del perfil). Dispara si `saldo_minimo < 0` y hay un cargo de serie previsto antes del mínimo. `importe_para_cubrir = −saldo_minimo + 20 €`, redondeado hacia arriba a 10 €. Confianza 0,50 + 0,20 si el cargo es fijo + 0,10 si la serie tiene ≥ 4 cargos + 0,10 si el gasto variable explica < 30 % del hueco − 0,20 si `saldo_minimo > −20 €`. Clave: `serie_id + fecha`.
- **`posible_estafa`**: Bizum o transferencia **enviados**, o tarjeta en comercio nuevo, con ≥ 2 señales (contraparte nueva; `importe >= max(150 €, 5 × mediana)`; ≥ 2 cargos ≤ 2 € en 48 h; nota con `urgente|verifica|codigo|nuevo numero|hijo`). Los Bizums recibidos nunca son estafa. No sale en la demo.

## 4. Conocimiento de comercios (`backend/motor/conocimiento.py`)
- **Dos archivos**: `backend/datos/comercios_conocidos.json` (versionado) es solo el **catálogo revisado a mano** (`origen: catalogo`). Lo que trae la web va a `datos_usuario/_cache/comercios_web.json` (fuera de git, `origen: web`); lo escribe el orquestador, único que escribe en `datos_usuario/`, con `conocimiento.guardar(info)`.
- `info_en_cache(nombre) -> InfoComercio | None`: lee el catálogo y, si no está, la caché web (clave = `comercio_normalizado`). Es lo único que usan detectores y módulos (`cancelar_suscripcion` toma `url_baja` y `pasos_baja`).
- `info_comercio(nombre) -> InfoComercio`: caché y, si falta y `BUSQUEDA_WEB=on`, búsqueda web de Claude (Haiku 5.5, herramienta `web_search` con `max_uses = 3`) por `claude_client.py`. Con `off`, devuelve `None` y no sale a internet.
- **Fuera del camino caliente**: tras `procesar`, el orquestador lee `motor.comercios_pendientes(usuario_id)` y llama a `info_comercio` una vez por nombre (tope `MAX_BUSQUEDAS_DIA = 20`). Los fallos se guardan con `origen: desconocido` y no se repiten en 30 días.
- **Qué se busca**: solo comercios de **tarjeta** con nombre normalizado de ≤ 30 caracteres, sin dígitos y sin la marca `posible_persona` (§2.1). Nunca contrapartes de Bizum o transferencias, recibos, importes ni datos del cliente. Lo que no cumple no entra en `comercios_pendientes`.
- **Validación** (pydantic): `es_suscripcion: bool`, `dias_prueba: 0-90`, `precio_tras_prueba: Decimal 0-500`, `fuentes` solo `https`. `url_baja` web: `https`, sin `xn--`, sin IP, sin credenciales (`usuario@`) y con un host que coincide con el dominio oficial del comercio que aparece en las fuentes; si no, se descarta (la tarjeta la muestra como texto con «Compruébalo en la web oficial»). `pasos_baja`: ≤ 5 de ≤ 200 caracteres, texto plano; se descartan los que llevan teléfonos, IBAN, correos, URL distintas de `url_baja` o verbos de pago («transfiere», «paga», «envía», «introduce tu tarjeta»). Si lo esencial no valida, `origen: desconocido`. El prompt marca lo que llega de la web como `<datos>…</datos>`. Coste de cada búsqueda al registro de costes del cliente.
- **Precarga del catálogo**: ficticios de la demo con fuente «catálogo de la demo»: `STREAMFLIX` (streaming, 30 días, 9,99 €, URL y pasos de baja), `SONORA MUSIC` (música, 14 días, 10,99 €), `FITAPP PLUS` (deporte, 7 días, 4,99 €). Reales solo con `tipo` y `es_suscripcion` (Netflix, Spotify, Amazon Prime, Disney+, HBO Max, DAZN, Audible, YouTube Premium); sus días y precios solo si `investigador` los trae con enlace. Comercios que **no** son de suscripción para las trampas: `ZARA`, `REPSOL`, `NH HOTELES`, `MERCADONA`.
- **Tests sin internet**: catálogo de prueba, caché web en un directorio temporal y `claude_falso.py`. Tests: la consulta solo lleva el nombre; `SUMUP *JUAN PEREZ`, nombres con dígitos o de > 30 caracteres y contrapartes no se buscan; se rechazan `url_baja` `http`, `xn--`, IP, con credenciales o de otro dominio; los pasos con teléfono, IBAN o «transfiere» se descartan; un texto «ignora las instrucciones» no cambia el esquema; con `off` no hay llamadas.

## 5. Escenarios etiquetados (`backend/escenarios/*.yaml`)
Fechas **absolutas**. `cargar.py` lee el YAML, genera los movimientos, reproduce el reloj y, si el escenario trae `perfil`, lo pasa a `procesar` (`perfil: calcular` = `perfilar` sobre el fondo; o un perfil escrito a mano). `eventos` simula lo que dice el cliente (`registrar_prueba`, `cerrar_prueba`).
**Escenario único de la demo: `demo-lucia`.** Lo usan el guion, el test de principio a fin y `/medir`. Une en el mismo historial la cena, la prueba de Streamflix y el duplicado de 9,99 €. `cena-lucia` y `prueba-streamflix-lucia` son sus versiones unitarias (los mismos movimientos, cada una con su parte).
```yaml
id: demo-lucia
usuario_id: lucia
fondo: {perfil: estudiante, meses: 4, semilla: 7, hasta: 2026-11-16, anomalias: false}
activacion: 2026-10-01          # antes: cargar_historial (sin emitir); después: procesar día a día
perfil: calcular                # perfilar al activar y cada semana; el test repite sin perfil
movimientos:
  # Grupo único de Lucía: LAURA M, DANIEL P, SARA L, MARCOS R. Al menos 3 cenas anteriores
  # (p. ej. 12/09, 03/10, 24/10) en las que pagan los cuatro con Bizums a 0-2 días → retraso_p75_dias = 2
  - {id: luc-v1, fecha: 2026-10-14, concepto: "VERIFICACION TARJETA STREAMFLIX", comercio: "STREAMFLIX", importe: 0.00, canal: tarjeta, tipo_operacion: verificacion}
  - {id: luc-d1, fecha: 2026-10-15, concepto: "COMPRA TARJETA LIBRERIA LUNA", comercio: "LIBRERIA LUNA", importe: -9.99, canal: tarjeta}
  - {id: luc-d2, fecha: 2026-10-15, concepto: "COMPRA TARJETA LIBRERIA LUNA", comercio: "LIBRERIA LUNA", importe: -9.99, canal: tarjeta}
  - {id: luc-c1, fecha: 2026-11-06, concepto: "COMPRA TARJETA LA TASCA MADRID", comercio: "LA TASCA", importe: -120.00, canal: tarjeta}
  - {id: luc-b1, fecha: 2026-11-06, concepto: "BIZUM RECIBIDO", contraparte: "Laura Martinez Garcia", nota: "cena", importe: 24.00, canal: bizum}
  - {id: luc-b2, fecha: 2026-11-07, concepto: "BIZUM RECIBIDO", contraparte: "Daniel Perez Ruiz", nota: "cena", importe: 24.00, canal: bizum}
  - {id: luc-b3, fecha: 2026-11-08, concepto: "BIZUM RECIBIDO", contraparte: "Sara Lopez Gil", nota: "cena", importe: 24.00, canal: bizum}
esperado:
  - {tipo: cargo_duplicado, fecha_detectable: 2026-10-15, ids: [luc-d1, luc-d2], tolerancia_dias: 0, solo_con_perfil: true}
  - {tipo: prueba_gratuita, fecha_detectable: 2026-11-10, ids: [luc-v1], tolerancia_dias: 0,
     datos: {fecha_primer_cobro: 2026-11-13, dias_hasta: 3, importe_previsto: "9.99", fuente_duracion: catalogo}}
  - {tipo: gasto_compartido, fecha_detectable: 2026-11-09, ids: [luc-c1], tolerancia_dias: 0,
     datos: {personas_estimadas: 5, faltan: 1, importe_pendiente: "24.00"}, candidatos: ["MARCOS R"]}
trampas:
  - {tipo: posible_estafa, ids: [luc-b1, luc-b2, luc-b3], motivo: "Bizums recibidos"}
  - {tipo: gasto_compartido, ids: [cenas anteriores], motivo: "pagaron los cuatro"}
```
Reparto (clave de `clave_contraparte` → nombre visible): `LAURA M` → «Laura M.», `DANIEL P` → «Daniel P.», `SARA L` → «Sara L.», `MARCOS R` (Marcos Ruiz Sanz) → «Marcos R.». La cena sale el **lunes 9/11 con y sin perfil** (`DIAS_ESPERA = clamp(2 + 1, 2, 5) = 3`; hay test de las dos cosas) con `MARCOS R` como candidato único. El duplicado del 15/10 solo sale **con** perfil (9,99 € ≥ 6 €; sin perfil, 9,99 € < 15 €) y la personalización lo manda al resumen (urgencia `media`). La prueba sale el **10/11**. Test extra: recalcular el perfil el 21/10 (con Streamflix en `suscripciones_activas` y `en_prueba = true`) no cambia el aviso del 10/11.
**Acierto**: un momento del mismo `tipo` que toca `ids` y sale entre `fecha_detectable` y `+ tolerancia_dias`. En las previsiones (renovación, prueba y saldo) se cruza además `datos.fecha_prevista` o `fecha_primer_cobro` (±1 día) con la etiqueta. **Trampa violada**: cualquier momento del tipo indicado que toque esos `ids`. `datos` se comparan como subconjunto.


| Detector | Positivos | Trampas (no deben avisar) |
|---|---|---|
| Todos | `demo-lucia` (cena, prueba y duplicado) | las de `demo-lucia` |
| `gasto_compartido` | `cena-lucia` (unitario); `cena-redondeo` (87,40 €, 3 × 17,50 €); `dos-cenas-solapadas`; `cena-pequena-perfil` (28 €, 2 × 7 €: solo sale **con** perfil) | `cena-todos-pagan`; `cumple-sin-pago`; `bizum-suelto`; `alquiler-compartido` |
| `cargo_duplicado` | `gimnasio-doble` (recibo 39,90 € × 2); `tpv-doble` (Zara 59,95 € × 2); `libreria-doble-perfil` (9,90 € × 2: solo con perfil) | `dos-cafes`; `cuotas-gimnasio`; `compra-devolucion-compra`; `metro-recargas` |
| `renovacion_proxima` | `prime-anual` (49,90 €, aviso 15 días antes; 21 con perfil si supera el umbral); `seguro-semestral` | `alquiler-mensual`; `netflix-mensual`; `ikea-una-vez` |
| `subida_recibo` | `luz-sube` (45 → 61 €); `seguro-hogar-sube` (anual +18 %) | `luz-invierno` (+12 % en serie variable); `subida-centimos` (+1,50 €) |
| `prueba_gratuita` | `prueba-streamflix-lucia` (unitario); `prueba-1eur-sonora` (1 € y devolución, 14 días); `prueba-dicha-usuario` (sin verificación, por defecto 30, aviso 5 días antes); `prueba-sin-cache` (comercio nuevo, la búsqueda falsa lo resuelve al día siguiente); `prueba-paypal` (`PAYPAL *SONORA MUSIC`) | `sumup-persona` (0 € de `SUMUP *JUAN PEREZ`: ni se busca ni avisa); `prueba-baja-guiada` (`cerrar_prueba` con `baja_guiada`: sin más momentos); `verificacion-tienda` (0 € de Zara al guardar la tarjeta); `ya-la-pago` (0 € de Streamflix con serie mensual de 9,99 €: cambio de tarjeta); `prueba-cancelada` (verificación + `cerrar_prueba` el día 10); `gasolinera-1eur` (Repsol 1 € y devolución); `cobro-antes` (el cargo llega antes del aviso: se cierra sin momento) |
| `saldo_negativo_previsto` (si sobra) | `seguro-coche-sin-saldo` | `nomina-antes`; `saldo-bajo-sin-recibos` |

Además, `fondo-*`: los tres perfiles del kit con `anomalias: false` y 6 meses, para medir el **ruido de fondo**. Cada escenario se mide **sin perfil y con perfil**.

## 6. Métricas objetivo (`/medir motor`)
| Detector | Precisión | Exhaustividad | Retraso o antelación | Trampas |
|---|---|---|---|---|
| `gasto_compartido` | 1,0 | 1,0 | retraso medio ≤ 1 día | 0 |
| `cargo_duplicado` | ≥ 0,9 | 1,0 | retraso 0 | 0 |
| `renovacion_proxima` | ≥ 0,9 | ≥ 0,9 | antelación ≥ 7 días (anual ≥ 14) | 0 |
| `subida_recibo` | ≥ 0,9 | ≥ 0,9 | retraso 0 | 0 |
| `prueba_gratuita` | 1,0 | 1,0 | antelación 2-3 días (4-5 si `por_defecto`) | 0 |
| `saldo_negativo_previsto` (si sobra) | ≥ 0,8 | ≥ 0,8 | antelación ≥ 3 días | 0 |

Además: ruido de fondo ≤ 1 momento por usuario y mes, **con y sin perfil**; exhaustividad con perfil ≥ sin perfil (los escenarios `*-perfil` lo demuestran) y sin perfil idéntica a `motor-0.1`; 6 meses día a día en < 2 s por usuario; test de no mirar el futuro (añadir movimientos posteriores a `hoy` no cambia nada emitido hasta `hoy`); cero llamadas a internet en tests. `medir.py` guarda `evals/resultados/motor-<fecha>.json`, que lee el panel del jurado.

## 7. Archivos
**Reutiliza**: `herramientas/_analisis.py: detectar_recurrentes` (se adapta en `enriquecer.py`), `herramientas/gastos.py: prevision_saldo` y `_toca` (para el saldo, si sobra), `datos/categorias.py`, `datos/sinteticos.py` (gana `anomalias=False` y verificaciones de 0 €), `claude_client.py` y `claude_falso.py`.
**Nuevo**: `backend/motor/{__init__,normalizar,enriquecer,parametros,razonador,estado,conocimiento}.py`; `backend/motor/detectores/{__init__,gasto_compartido,cargo_duplicado,renovacion_proxima,subida_recibo,prueba_gratuita}.py` (y `saldo_negativo_previsto.py` si sobra); `backend/datos/comercios_conocidos.json` (catálogo; la caché web vive en `datos_usuario/_cache/comercios_web.json`); `backend/escenarios/{cargar.py,*.yaml}`; `evals/medir.py` (parte motor); `tests/test_motor_*.py`, `tests/test_conocimiento.py`, `tests/test_escenarios.py`.
**Orden** (~7,5 h): tipos y normalización (1 h) → series y estado (1 h) → `gasto_compartido` + `cena-lucia` + trampas (1,5 h) → `demo-lucia` completo (0,5 h) → `cargo_duplicado` (0,5 h) → `renovacion_proxima` y `subida_recibo` (1 h) → `conocimiento.py` con caché (0,5 h) → `prueba_gratuita` (1 h) → perfil (`ajustar` y contexto) (0,5 h) → `medir.py` (0,5 h).

## 8. Riesgos y recortes
- **Ruido del fondo**: `anomalias: false` y patrón habitual. Bajar umbrales con el perfil puede subir el ruido: se mide con perfil y, si pasa de 1 al mes, se suben los suelos de `clamp`.
- **Perfil desfasado** (se recalcula una vez por semana): solo ajusta umbrales; nunca crea un momento sin evidencias en movimientos.
- **Duración de la prueba equivocada** (web o por defecto): si el cobro llega antes, se pierde el aviso; por eso `por_defecto` avisa 5 días antes y la cifra se muestra con su fuente.
- **Cobertura de las pruebas**: la señal son las autorizaciones del emisor, que el extracto no siempre muestra; en la demo las trae el sintético. No hay señal sin verificación ni tras pasarelas opacas: lo cubre la vía «el cliente lo dice» y no se promete cobertura total.
- **Búsqueda web**: inyección y URLs falsas (validación y `<datos>`), coste (tope diario, caché) y caída de red (`BUSQUEDA_WEB=off`; la demo vive de la caché).
- **Cuotas desiguales** y **nombres inconsistentes** (`Marcos R.` / `MARCOS RUIZ`): fuera del MVP.
- **Recortes, por orden**: `posible_estafa` → `saldo_negativo_previsto` → búsqueda web real (queda la caché) → anual de un solo cargo → `subida_recibo`. Lo que **no** se recorta: `demo-lucia` (cena, prueba y duplicado).
- **Mirar el futuro por error**: un solo punto de corte (`ctx.historial` en `procesar`) y un test de propiedad.

## 8 bis. Implementado en E2-E3 (9 nov, noche): lo que concreta o cambia este diseño
- **Detectores** devuelven `Hallazgo {tipo, clave, movimientos, confianza, datos, impacto_eur}` (`detectores/base.py`); el razonador pone `id`, `fecha`, `explicacion` y `version`. Registro con `@registrar("<tipo>", version=n)` en `detectores/__init__.py`.
- **Id**: `mom-<tipo>-<sha1("<tipo>|<clave>")[:10]>` (sin `usuario_id`: los escenarios se reproducen en un usuario aislado y dan los mismos ids). `claves_emitidas = {"tipo|clave": momento_id}`.
- **Solapes**: el perdedor queda en `claves_emitidas` como `solapado:<id>` para que no reaparezca al día siguiente.
- **Series**: periodos 1, **2** (agua bimestral), 3, 6 y 12 meses. Con tarjeta y periodo < 6 meses: importe fijo (≤ 5 %) y ≥ 3 cargos (dos cenas en el mismo restaurante no son una serie).
- **Reembolso**: Bizum o transferencia recibidos de una contraparte (no nóminas ni devoluciones). Se asigna al pago más reciente de la ventana donde **ese reembolso solo** ya encaja (3-12 personas y total a `max(1 €, 3 %)`). Si alguno se aleja más de `TOL_CUOTA` de la mediana, no avisa.
- **Líneas base** (`enriquecer.lineas_base`): solo repartos **cerrados** (`hoy − pago > VENTANA_REEMBOLSO`); p75 por rango más cercano con ≥ 3 retrasos (si no, `DIAS_ESPERA = 3`). Candidatos sin perfil: quienes devolvieron junto a **alguno** de los que ya han pagado, con ≥ 2 coincidencias, ordenados por coincidencias.
- **`cargar_historial`** solo guarda (no ejecuta detectores). Escenarios: lo que tiene `fecha <= activacion` entra por `cargar_historial` y se procesa desde el día siguiente, igual que el orquestador.
- **`escenarios/cargar.py`**: `listar()`, `leer(id)`, `cargar(id) -> Escenario`, `desde_dict(d)`, `perfil_para(esc, hoy, historial)`, `reproducir(esc, con_perfil=None, al_terminar=None)` (usuario aislado; no toca el estado real) y `evaluar(esc, momentos, con_perfil)` → `{aciertos, omitidos, falsos_positivos, trampas_violadas, retrasos, por_tipo}`.
- **Pendiente**: `ajustar` con perfil, `impacto_relativo` y `contexto_personal` (M9); `comercios_pendientes` lo llena `prueba_gratuita` (M7).

## 9. Cambios que pido al contrato
1. **`comercios_pendientes(usuario_id) -> list[str]`** en el motor (lo lee el orquestador para pedir búsquedas). `cerrar_prueba` admite `motivo: cancelada | baja_guiada | descartada`.
2. **`prueba_gratuita.fuente_duracion`** admite además `usuario` (cuando el cliente dice cuántos días).
3. **`InfoComercio.origen`**: `catalogo | web | desconocido`; `conocimiento.info_en_cache(nombre)` (sin red) y `conocimiento.guardar(info)` (lo llama el orquestador).
4. **`PerfilUsuario.grupos`**: `list[{miembros: list[clave_contraparte], veces, retraso_p75_dias?}]`, con la clave de `motor.normalizar.clave_contraparte`.
5. Campos añadidos (permitidos): `gasto_compartido.cuota`, `cargo_duplicado.serie_id`, `renovacion_proxima.serie_id`, `prueba_gratuita.fuentes_info`; etiquetas `pasarela` y `posible_persona` en `MovimientoEnriquecido`.
