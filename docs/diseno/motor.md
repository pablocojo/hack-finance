# Diseño del motor de momentos

9 de noviembre de 2026, `/planificar`. Autor: `ingeniero-deteccion`. Respeta `CONTRATO.md` (manda su sección «Decisiones de /planificar»).

## 1. Resumen
- El motor convierte movimientos en `Momento`s **en línea**: `procesar(usuario_id, nuevos, hoy)` añade `nuevos` al historial y cada detector ve solo `fecha <= hoy`.
- Cuatro pasos: normalizar (comercio, contraparte, canal) → enriquecer (series recurrentes con `serie_id`, líneas base del historial) → detectores deterministas (pandas + `Decimal`) → razonador (deduplica, filtra, prioriza, explica).
- MVP: `gasto_compartido` (estrella), `cargo_duplicado`, `renovacion_proxima`, `saldo_negativo_previsto`. Después, si sobra tiempo: `subida_recibo` y `posible_estafa`.
- Sin Claude en el camino de detección: la `explicacion` sale de plantillas. Haiku queda tras un interruptor (notas de Bizum dudosas), apagado por defecto.
- Todo se mide con escenarios YAML etiquetados en `backend/escenarios/`, que alimentan tests, `/medir motor` y la demo.

## 2. Pipeline
**Estado por usuario** (`EstadoMotor`, en memoria): historial enriquecido, series, líneas base y `claves_emitidas`. El orquestador lo guarda en `datos_usuario/<id>/motor.json` con `exportar_estado`/`importar_estado` (ver §8). `procesar` lanza un error si algún movimiento de `nuevos` tiene `fecha > hoy`.

**2.1 Normalización** (`motor/normalizar.py`, reglas puras):
- `canal`: si falta, se deduce del concepto (`BIZUM` → bizum, `RECIBO`/`ADEUDO` → recibo, `COMPRA TARJETA`/`COMPRA ONLINE` → tarjeta, `TRANSFERENCIA` → transferencia, `CAJERO`/`REINTEGRO` → cajero).
- `comercio_normalizado`: `comercio` o, si falta, el concepto; `categorias.normalizar` (mayúsculas, sin tildes) y se quitan prefijos (`COMPRA TARJETA`, `RECIBO`, `COMPRA ONLINE`, `PAGO`), sufijos de tarjeta (`*1234`), dominios (`.COM`, `.ES`) y la ciudad final si está en una lista corta. Alias en un diccionario (`AMZN MKTP` → `AMAZON`).
- `contraparte_normalizada` (Bizum y transferencias): sin tildes, mayúsculas, sin `BIZUM DE/RECIBIDO/ENVIADO`; clave = nombre + inicial del primer apellido (`LAURA MARTINEZ G` → `LAURA M`).
- `categoria`: la del movimiento o `categorizar_por_reglas` del kit. La categorización con Haiku del kit no entra en el motor.

**2.2 Enriquecimiento** (`motor/enriquecer.py`), recalculado en cada `procesar` (cientos de filas, milisegundos):
- **Series**: adaptación de `detectar_recurrentes` del kit agrupando por `comercio_normalizado`, con `Decimal`, periodos de 1, 3, 6 y **12 meses** (anual: 2 cargos entre 330 y 400 días, o 1 cargo cuyo concepto lleva `ANUAL|ANNUAL|YEARLY|12 MESES`). `serie_id = "<COMERCIO>:<periodo>m"`, estable entre días. Guarda `importe_habitual` (mediana), `dia_habitual`, `variacion`, `veces`, `ultimo`, `fijo` (variación ≤ 5 %).
- **Etiquetas**: `reembolso_entrante` (Bizum recibido), `cargo_serie`, `comercio_nuevo` (primera vez en 180 días).
- **Líneas base del historial** (el motor no lee `ModeloUsuario`): `gasto_variable_diario` (mediana diaria de 60 días, sin series), `retraso_reembolso_p75` (días entre pago compartido y Bizum, de pagos anteriores) y `grupos` (contrapartes que aparecen juntas en reembolsos previos, con recuento).

**2.3 Detectores** (`motor/detectores/<tipo>.py`): `detectar(ctx) -> list[Momento]`, donde `ctx` tiene `hoy`, `historial` (≤ hoy), `nuevos`, `series`, `lineas_base` y `params` (dataclass con valores por defecto en `motor/parametros.py`, ajustados con las líneas base). Registro en `detectores/__init__.py`.

**2.4 Razonador** (`motor/razonador.py`):
1. **Clave estable** por tipo (tabla de §3) → `Momento.id = "mom-<tipo>-<sha1(clave)[:10]>"`. Si la clave ya está en `claves_emitidas`, no se repite: reprocesar es idempotente.
2. **Filtro**: `confianza >= 0.5` (`CONFIANZA_MINIMA`).
3. **Solapes**: si un movimiento es evidencia de dos momentos, gana el de más prioridad: `posible_estafa` > `cargo_duplicado` > `saldo_negativo_previsto` > `gasto_compartido` > `subida_recibo` > `renovacion_proxima`.
4. **Orden**: prioridad y luego `impacto_eur`.
5. **`explicacion`**: plantilla por tipo con cifras en formato español («Pagaste 120,00 € en La Tagliatella y te han devuelto 72,00 € de 4 personas; falta 1 (24,00 €)»). Los conceptos y notas se copian como texto, nunca se interpretan.
6. `version = "motor-0.1/<tipo>-<n>"` y `detector = "<tipo>"`.

`impacto_eur`: duplicado = importe; renovación = importe del próximo cargo; saldo = `importe_para_cubrir`; compartido = `importe_pendiente`; estafa = importe; subida = (actual − habitual) × cargos al año.

## 3. Detectores del MVP
En `datos` los importes van en **positivo** (`Decimal`, 2 decimales) y las fechas en ISO.

### 3.1 `gasto_compartido` (la estrella)
**Pagos candidatos**: cargo de tarjeta ≥ `IMPORTE_MIN_PAGO = 30 €`, que no es de una serie y de categoría `restaurantes`, `ocio`, `supermercado`, `compras` o `transporte`.
**Reembolsos**: Bizums o transferencias **recibidos** con fecha en `[pago, pago + VENTANA_REEMBOLSO = 7 días]`. Cada Bizum se asigna a un solo pago: al anterior más cercano cuya cuota encaje.
**Cuota y personas**: `cuota` = mediana de los reembolsos que distan ≤ `TOL_CUOTA = 0,50 €` de la mediana (exige `MIN_REEMBOLSOS = 2` en ese grupo). `personas = round(total / cuota)`, válido si `|total − personas × cuota| ≤ max(1 €, 3 % del total)` y `3 <= personas <= 12`.
`faltan = personas − 1 − nº reembolsos`; `importe_pendiente = faltan × cuota`.
**Cuándo**: el primer `hoy` con `hoy − pago >= DIAS_ESPERA` y `hoy − último reembolso >= DIAS_SILENCIO = 1`, mientras `faltan >= 1` y `hoy − pago <= VENTANA_REEMBOLSO`. `DIAS_ESPERA = clamp(retraso_reembolso_p75 + 1, 2, 5)`, por defecto 3. Lucía (cena el viernes D; Bizums en D, D+1 y D+2) → momento en **D+3**.
**Candidatos** (quién falta): contrapartes de `grupos` que han coincidido con ≥ 1 de los que ya pagaron en ≥ `MIN_COINCIDENCIAS = 2` reembolsos anteriores y que no han pagado este. Se puntúan por coincidencias y se guardan los `faltan × 2` mejores. Marcos sale porque pagó las cenas anteriores con Laura, Dani y Sara.
**`datos`**: `pago_id`, `comercio`, `importe_total`, `fecha`, `reembolsos [{contraparte, importe, id}]`, `personas_estimadas`, `faltan`, `importe_pendiente`, `candidatos [{contraparte, coincidencias, retraso_medio_dias}]` y además `cuota`. Clave: `pago_id`.
**Confianza**: 0,50 + 0,15 si `|total − personas × cuota| ≤ 0,05 × personas` + 0,10 si hay ≥ 3 reembolsos + 0,10 si la nota de algún Bizum tiene palabras de comida o plan (`cena|comida|pizza|birra|cumple de|regalo para` y emojis 🍕🍝🍻) + 0,10 si el candidato principal tiene ≥ 3 coincidencias − 0,15 si `personas > 8`. Máximo 0,95.
**No hace**: si el amigo paga después, no hay momento nuevo; lo salda la personalización (`amigos`). Con cuotas desiguales no se estima (recorte).

### 3.2 `cargo_duplicado`
**Par**: un cargo nuevo B y un cargo anterior A del mismo `comercio_normalizado` y el **mismo importe al céntimo**, con `0 <= B − A <= VENTANA_DUP = 3 días` y sin un abono del mismo comercio e importe entre los dos.
**Exclusiones (trampas)**: tarjeta con importe < `IMPORTE_MIN_TARJETA = 15 €`; categoría `transporte`; **patrón habitual**: el mismo par (comercio, importe, ≥ 2 cargos en ≤ 3 días) ya apareció en un periodo anterior (dos cuotas del gimnasio cada mes para dos personas); comercio con ≥ `COMPRAS_FRECUENTES = 8` compras en 30 días si va con tarjeta y es < 50 €.
**Confianza**: 0,90 si A es de una serie y B cae en el mismo periodo; 0,85 si el canal es recibo; tarjeta: 0,70 el mismo día y 0,55 si hay 1-3 días entre ellos.
**Cuándo**: el día que entra B (retraso 0).
**`datos`**: `comercio`, `importe`, `fechas [A, B]`, `ids [A, B]`, `dias_entre` y además `serie_id?`. Clave: `ids` ordenados. Evidencias: `[A, B]`.

### 3.3 `renovacion_proxima`
**Series avisables**: de cargo, categoría `suscripciones`, `ocio`, `seguros` o `compras`, canal tarjeta o recibo, periodo en `PERIODOS_AVISABLES = {3, 6, 12}` meses. Las mensuales no avisan por defecto (`INCLUIR_MENSUALES = False`): avisar cada mes es ruido.
**Fecha prevista**: `ultimo + periodo` meses, en el `dia_habitual` (limitado al último día del mes, como `_toca` del kit).
**Cuándo**: el primer `hoy` con `0 < fecha_prevista − hoy <= ANTELACION[periodo]`: 7 días si es trimestral o semestral y 15 si es anual.
**`datos`**: `comercio`, `importe` (habitual), `periodicidad` (`trimestral|semestral|anual`), `fecha_prevista`, `dias_hasta`, `veces_cobrado` y además `serie_id`. Clave: `serie_id + fecha_prevista`. Evidencias: los cargos anteriores de la serie.
**Confianza**: 0,60 + 0,10 por cada cargo más allá del segundo (máximo 0,90) − 0,10 si la desviación del día es > 2; 0,50 si es anual de un solo cargo con marcador `ANUAL`.

### 3.4 `saldo_negativo_previsto`
**Requisito**: el último movimiento trae `saldo`. Si no, no se evalúa.
**Proyección** cada día, desde el saldo de hoy durante `HORIZONTE = 10 días`: cargos e ingresos de las series en su fecha prevista + `gasto_variable_diario` (mediana, no media: los picos no inflan) cada día.
**Dispara** si `saldo_minimo < UMBRAL_SALDO = 0 €` **y** hay al menos un cargo de serie previsto antes o el mismo día del mínimo. La deriva del gasto variable sola no avisa.
**`datos`**: `fecha_prevista` (día del mínimo), `saldo_minimo`, `cargos_previstos [{comercio, importe, fecha, serie_id}]`, `importe_para_cubrir` = `−saldo_minimo + COLCHON (20 €)` redondeado hacia arriba a 10 € y además `saldo_actual` e `ingresos_previstos`. Clave: `serie_id + fecha` del primer cargo previsto que deja el saldo en negativo. Si la previsión vuelve a ser positiva, la clave se libera.
**Confianza**: 0,50 + 0,20 si ese cargo es fijo + 0,10 si la serie tiene ≥ 4 cargos + 0,10 si el gasto variable explica < 30 % del hueco − 0,20 si `saldo_minimo > −20 €`.

### 3.5 Si sobra tiempo
- **`subida_recibo`**: un cargo nuevo de una serie con ≥ 3 cargos e `importe > habitual × (1 + 8 %)` y > habitual + 2 €. En las series variables (luz, agua) el umbral es 25 %. `datos` del contrato. Confianza 0,6-0,9 según `veces`. Clave: id del cargo.
- **`posible_estafa`**: Bizum o transferencia **enviados**, o tarjeta en un comercio nuevo, con ≥ 2 señales: contraparte o comercio nuevo; `importe >= max(150 €, 5 × mediana de esos pagos del usuario)`; ≥ 2 cargos de prueba ≤ 2 € en 48 h; nota con `urgente|verifica|codigo|nuevo numero|hijo`. Esta última es la única regla donde Haiku aportaría, con la nota marcada como dato y salida JSON `{sospechosa, motivo}`; apagado por defecto. `datos` del contrato y `veces_lo_habitual`. Los Bizums **recibidos** nunca son estafa.

## 4. Escenarios etiquetados (`backend/escenarios/*.yaml`)
Fechas **absolutas** para que sea determinista. `cargar.py` lee el YAML, genera los movimientos y reproduce el reloj; lo usan los tests, `evals/medir.py` y la demo.
```yaml
id: cena-lucia
usuario_id: lucia
descripcion: Paga 120 € en una cena; tres de cuatro amigos le devuelven 24 €; falta Marcos
fondo: {perfil: estudiante, meses: 4, semilla: 7, hasta: 2026-11-16, anomalias: false}
activacion: 2026-10-01          # antes: cargar_historial (sin emitir); después: procesar día a día
fin: 2026-11-16
movimientos:
  - {id: luc-c1, fecha: 2026-11-06, concepto: "COMPRA TARJETA LA TAGLIATELLA MADRID", comercio: "LA TAGLIATELLA", importe: -120.00, canal: tarjeta}
  - {id: luc-b1, fecha: 2026-11-06, concepto: "BIZUM RECIBIDO", contraparte: "Laura Martinez G", nota: "cena", importe: 24.00, canal: bizum}
  # ... luc-b2 (Dani, 07/11) y luc-b3 (Sara, 08/11); cenas anteriores donde también paga Marcos
esperado:
  - {tipo: gasto_compartido, fecha_detectable: 2026-11-09, ids: [luc-c1], tolerancia_dias: 1,
     datos: {personas_estimadas: 5, faltan: 1, importe_pendiente: "24.00", candidato_principal: "MARCOS R"}}
trampas:
  - {tipo: posible_estafa, ids: [luc-b1, luc-b2, luc-b3], motivo: "Bizums recibidos"}
```
**Acierto**: un momento predicho del mismo `tipo` cuyos `movimientos` se cruzan con `ids` y que sale entre `fecha_detectable` y `fecha_detectable + tolerancia_dias`. En las previsiones (renovación y saldo), `ids` es el cargo **futuro** que lo materializa y se cruza por `datos.fecha_prevista` (±2 días) con la fecha de ese cargo. **Trampa violada**: cualquier momento del `tipo` indicado que toque esos `ids`. `datos` se comparan como subconjunto.

| Detector | Positivos (deben salir) | Trampas (no deben avisar) |
|---|---|---|
| `gasto_compartido` | `cena-lucia` (demo); `cena-redondeo` (87,40 €, 3 × 17,50 €, falta 1); `dos-cenas-solapadas` (cuotas de 20 € y 31 € en la misma semana) | `cena-todos-pagan` (100 €, 4 × 20 €); `cumple-sin-pago` (5 Bizums de 10 € «cumple 🎉» sin pago previo); `bizum-suelto` (Mercadona 120 € y un solo Bizum de 24 €); `alquiler-compartido` (serie mensual con Bizums de compañeros) |
| `cargo_duplicado` | `gimnasio-doble` (recibo de 39,90 € dos veces el día 5); `tpv-doble` (Zara 59,95 € dos veces en 1 día) | `dos-cafes` (2 × 1,80 € el mismo día); `cuotas-gimnasio` (dos cuotas iguales cada mes, desde el primer mes); `compra-devolucion-compra` (cargo, abono y cargo de 49,99 €); `metro-recargas` (2 × 10 €) |
| `renovacion_proxima` | `prime-anual` (49,90 €, 14 meses de historial, aviso 15 días antes); `seguro-semestral` | `alquiler-mensual`; `netflix-mensual` (mensual, no avisable); `ikea-una-vez` (una compra hace un año sin marcador) |
| `saldo_negativo_previsto` | `seguro-coche-sin-saldo` (saldo de 210 €, recibo de 380 € el día 10 y nómina el 28) | `nomina-antes` (la nómina llega el día anterior al recibo); `saldo-bajo-sin-recibos` (40 € sin cargos fijos en el horizonte) |

Además, `fondo-*`: los tres perfiles del kit con `anomalias: false` y 6 meses, para medir el **ruido de fondo** (momentos por usuario y mes que no están etiquetados).

## 5. Métricas objetivo (`/medir motor`)
| Detector | Precisión | Exhaustividad | Retraso o antelación | Trampas |
|---|---|---|---|---|
| `gasto_compartido` | 1,0 | 1,0 | retraso medio ≤ 1 día sobre `fecha_detectable` | 0 |
| `cargo_duplicado` | ≥ 0,9 | 1,0 | retraso 0 días | 0 |
| `renovacion_proxima` | ≥ 0,9 | ≥ 0,9 | antelación ≥ 7 días (anual ≥ 14) | 0 |
| `saldo_negativo_previsto` | ≥ 0,8 | ≥ 0,8 | antelación ≥ 3 días antes del negativo | 0 |
Además: ruido de fondo ≤ 1 momento por usuario y mes; reproducir 6 meses día a día en < 2 s por usuario (< 20 ms por día); test de no mirar el futuro: añadir movimientos posteriores a `hoy` no cambia ningún momento emitido hasta `hoy`. `medir.py` guarda JSON en `evals/resultados/motor-<fecha>.json`, que lee el panel del jurado.

## 6. Qué se reutiliza y qué es nuevo
| Reutiliza (kit) | Uso |
|---|---|
| `backend/herramientas/_analisis.py: detectar_recurrentes` | Base de las series; se adapta en `enriquecer.py` (más periodos, `Decimal`, `serie_id`) sin romper la herramienta |
| `backend/herramientas/gastos.py: detectar_anomalias` | Idea del duplicado (3 días) y de la mediana/MAD para `posible_estafa`; no se llama directamente (no es en línea: usa `max(fecha)`) |
| `backend/herramientas/gastos.py: prevision_saldo`, `_toca` | Lógica de la proyección; se reescribe con `hoy` explícito y mediana |
| `backend/datos/categorias.py` | `normalizar`, `categorizar_por_reglas` |
| `backend/datos/sinteticos.py` | Fondo de los escenarios. **Cambio pequeño**: parámetro `anomalias=True` para poder apagarlas |

Nuevo: `backend/motor/{__init__,normalizar,enriquecer,parametros,razonador,estado}.py`, `backend/motor/detectores/{__init__,gasto_compartido,cargo_duplicado,renovacion_proxima,saldo_negativo_previsto}.py`, `backend/escenarios/{cargar.py,*.yaml}`, `evals/medir.py` (parte motor), `tests/test_motor_*.py` y `tests/test_escenarios.py`.

**Orden de trabajo** (~6 h): tipos y normalización (1 h) → series y estado (1 h) → `gasto_compartido` + `cena-lucia` + trampas (1,5 h) → `cargo_duplicado` (0,5 h) → `renovacion_proxima` (0,5 h) → `saldo_negativo_previsto` (1 h) → `medir.py` (0,5 h).

## 7. Riesgos y recortes
- **Ruido en el fondo del kit** (sus anomalías y compras repetidas): `anomalias: false` y el filtro de patrón habitual. Si aun así hay ruido, se suben `IMPORTE_MIN_TARJETA` y `CONFIANZA_MINIMA`.
- **Cuotas desiguales y pagos a medias** (alguien paga dos partes): fuera del MVP; se documenta como límite. Si un Bizum vale 2 × cuota, se cuenta como 2 personas (cambio de 10 líneas, opcional).
- **Nombres de contraparte inconsistentes** (`Marcos R.` / `MARCOS RUIZ`): la clave nombre + inicial lo resuelve en los datos sintéticos; en datos reales haría falta Haiku (recorte).
- **Saldo sin campo `saldo`**: el detector no corre; los escenarios lo traen siempre.
- **Recortes, por orden**: `posible_estafa` → `subida_recibo` → anual de un solo cargo → candidatos con retraso medio. El primero que **no** se recorta es `gasto_compartido` con `cena-lucia`.
- **Mirar el futuro por error**: un solo punto de corte (`ctx.historial` filtrado en `procesar`) y un test de propiedad que lo vigila.

## 8. Cambios propuestos al contrato
1. **Funciones nuevas en `backend/motor`** (no cambian `procesar`):
   `cargar_historial(usuario_id, movimientos, hoy) -> None`: carga el historial de la activación **sin emitir momentos**. Sin ella, al activar con 6 meses saldrían decenas de avisos viejos, y las trampas de patrón habitual necesitan historia previa.
   `exportar_estado(usuario_id) -> dict` / `importar_estado(usuario_id, dict) -> None`: el orquestador sigue siendo el único que escribe en disco (`datos_usuario/<id>/motor.json`).
   `reiniciar(usuario_id) -> None`: para repetir la demo.
2. **Convención de `datos`**: importes en positivo (valor absoluto, `Decimal` con 2 decimales). Los módulos y la voz no tienen que interpretar el signo.
3. **Campos añadidos** (permitidos por el contrato; se avisa para los módulos): `gasto_compartido.cuota`, `gasto_compartido.candidatos` como lista de `{contraparte, coincidencias, retraso_medio_dias}`, `cargo_duplicado.serie_id`, `renovacion_proxima.serie_id`, `saldo_negativo_previsto.saldo_actual` e `ingresos_previstos`.
4. **`Movimiento.id` único y estable** entre días, porque es la base de las claves del razonador y de las etiquetas.
