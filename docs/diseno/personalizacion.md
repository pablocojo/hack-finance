# Personalización: cuándo avisar y qué aprender de cada persona

9 de noviembre de 2026. Respeta `CONTRATO.md` (manda su apartado «Decisiones de /planificar»); los cambios que necesito van al final. Solo numpy, pandas y biblioteca estándar; Haiku 5.5 únicamente para extraer memoria de la llamada.

## 1. Resumen

- **Método**: Beta-Bernoulli jerárquica por *tipo de momento → tramo de importe → comercio o contacto*, con el valor en euros y la urgencia en una utilidad esperada. Se explica en una frase: «estimo la probabilidad de que este aviso te sirva a partir de cómo respondiste a avisos parecidos, y solo interrumpo si lo que te ahorra o te protege compensa la molestia».
- **Funciona igual para cualquier módulo**: aprende por `tipo_momento` y entidad, no por `modulo_id`; un módulo nuevo del banco hereda lo aprendido.
- **Reglas duras antes que estadística**: consentimiento, «solo si ahorra o protege», silencios explícitos y presupuesto diario. La protección nunca se silencia por aprendizaje.
- **Todo lo aprendido son frases** (`hechos_aprendidos`) que se ven, se apagan y se borran; borrar un hecho borra también la evidencia que lo genera.
- **Se demuestra** con 4 usuarios simulados de preferencias ocultas, 6 semanas y 10 semillas: precisión de avisos del ~50 % al ≥80 % y ≥65 % menos molestias que un sistema de reglas.

## 2. `ModeloUsuario` (para `backend/plataforma/tipos.py`)

```python
class Celda(BaseModel):            # una Beta: evidencia de utilidad para una clave
    utiles: float = 0.0            # suma de pesos positivos (a)
    molestias: float = 0.0         # suma de pesos negativos (b)
    n: int = 0
    ultima: date | None = None
class Silencio(BaseModel):
    ambito: Literal["tipo", "comercio", "contacto"]
    valor: str                     # "renovacion_proxima", "netflix", "marcos"
    desde: date
    origen: str                    # propuesta_id o "ajustes"
class Preferencias(BaseModel):
    silencios: list[Silencio] = []
    hora_inicio: int = 9           # franja en la que se puede interrumpir
    hora_fin: int = 22
    max_avisos_dia: int = 2        # la urgencia alta no cuenta
    euros_por_molestia: Decimal = Decimal("10")
class Contacto(BaseModel):         # sale de Bizums y transferencias
    contraparte: str
    veces: int
    importe_medio: Decimal
    primera: date
    ultima: date
    en_compartidos: int = 0
    dias_devolucion: list[int] = []   # días entre la petición y el pago
class Serie(BaseModel):
    serie_id: str
    comercio: str
    importe_habitual: Decimal      # mediana
    periodicidad_dias: int         # mediana de días entre cargos
    ultima: date
class Amigo(BaseModel):
    contraparte: str
    saldo: Decimal                 # > 0: te debe
    propuesta_origen: str
    concepto: str                  # "Cena en La Tasca"
    estado: Literal["detectado", "pedido", "saldado", "olvidado"]
    creado: date
    pedido: date | None = None
    saldado: date | None = None
class HechoAprendido(BaseModel):
    id: str
    texto: str                     # «Las renovaciones de menos de 10 € no suelen interesarte»
    origen: Literal["feedback", "preferencia", "amigos", "voz", "ajustes"]
    activo: bool = True
    clave: str | None = None       # celda o silencio que lo respalda; None si es de voz
    creado: date
class AvisoAbierto(BaseModel):     # para que aprender() sepa a qué claves afecta un Feedback
    propuesta_id: str
    claves: list[str]
    tipo_momento: str
    accion: Literal["notificar_ahora", "resumen", "silenciar"]
    fecha: datetime
class ModeloUsuario(BaseModel):
    usuario_id: str
    politica: str = "beta-jerarquica-v1"
    modulos_activos: list[str] = []
    consentimientos: dict[str, datetime] = {}   # "copiloto", "voz", "memoria"
    preferencias: Preferencias = Preferencias()
    estadisticas: dict[str, Celda] = {}         # claves en §3.1
    falsos_positivos: dict[str, int] = {}       # por tipo_momento
    avisos_abiertos: dict[str, AvisoAbierto] = {}
    ultimos_avisos: list[datetime] = []         # notificar_ahora de los últimos 7 días
    contactos: dict[str, Contacto] = {}
    series: dict[str, Serie] = {}
    lineas_base: dict[str, Decimal] = {}        # gasto semanal medio por categoría no sensible
    amigos: list[Amigo] = []
    hechos_aprendidos: list[HechoAprendido] = []
    actualizado: datetime | None = None
```

La **memoria en texto para el agente** no se guarda: la calcula `memoria_para_agente(modelo)` a partir de los hechos activos y los amigos pendientes (≤ 600 caracteres, dentro de `<datos>…</datos>`). Así nunca se desincroniza de lo que el usuario ve.

## 3. Política de interrupción (`beta-jerarquica-v1`)

### 3.1 Probabilidad de que el aviso sirva

Claves de una propuesta, de lo general a lo concreto: `global` → `t:<tipo>` → `t:<tipo>|b:<tramo>` (tramos `<10`, `10-50`, `>=50` €) → `t:<tipo>|e:<comercio o contacto>`. Cada nivel encoge hacia el anterior con fuerza `k = 4`:

```
m_0 = (2 + a_0) / (4 + a_0 + b_0)                 # prior global Beta(2, 2)
m_l = (k·m_{l-1} + a_l) / (k + a_l + b_l)         # l = tipo, tramo, entidad (si existe celda)
p   = m_último                                     # probabilidad de utilidad aprendida
c   = confianza_del_momento · 0.8^falsos_positivos[tipo]
q   = p · c                                        # útil y además cierto
```

### 3.2 Utilidad esperada

```
B = min(5, valor_estimado_eur / euros_por_molestia + bonus_urgencia)   # alta 2 · media 0,5 · baja 0
U = q·B − (1 − q)·1                                                    # 1 = coste de una interrupción
```

Parámetros versionados en `politica.py`: `k=4`, prior `(2,2)`, `θ_ahora=0,5`, `θ_resumen=−0,3`, tope `B=5`, factor `0,8` por falso positivo.

### 3.3 Orden de la decisión (la primera regla que aplica, gana)

1. Módulo no activo o sin consentimiento → `silenciar`.
2. No ahorra ni protege (`valor_estimado_eur ≤ 0` y urgencia ≠ alta) → `silenciar`.
3. Silencio explícito que coincide con tipo, comercio o contacto → `silenciar` (si es `posible_estafa` con urgencia alta, `resumen`).
4. `U ≥ θ_ahora` → `notificar_ahora`, salvo que esté fuera de franja o ya se haya alcanzado `max_avisos_dia` (urgencia alta exenta): entonces `resumen`.
5. `θ_resumen ≤ U < θ_ahora` → `resumen`.
6. `U < θ_resumen` → `silenciar`, salvo **protección** (urgencia alta: mínimo `resumen`) o **exploración prudente** (la celda del tipo tiene `n < 3` y `U` con `p + desviación` llega a `θ_resumen`: `resumen`).

`decidir` es pura y tarda < 5 ms. `Decision.puntuacion = U`, `probabilidad_util = q`.

### 3.4 Ejemplo: la cena de Lucía

Propuesta `cena_compartida`: faltan 24 € de Marcos, urgencia media, confianza 0,92, 20:30, ningún aviso hoy. Historial: global 6 útiles y 4 molestias; gastos compartidos 2 de 2 resueltos; tramo 10-50 €, 1 de 1; Marcos, 1 de 1; 0 falsos positivos.

```
m_0 = (2+6)/(4+10)              = 0,571
m_t = (4·0,571+2)/(4+2)         = 0,714
m_b = (4·0,714+1)/(4+1)         = 0,771
m_e = (4·0,771+1)/(4+1)         = 0,817 = p
q   = 0,817 · 0,92              = 0,752
B   = 24/10 + 0,5               = 2,9
U   = 0,752·2,9 − 0,248         = 1,93 ≥ 0,5  → notificar_ahora (dentro de franja, 0/2 avisos hoy)
```

Contraste en frío (todo a cero): `p = 0,5`, `q = 0,46`, `U = 0,46·2,9 − 0,54 = 0,79` → también avisa. Un duplicado de 9,99 € en frío da `B = 1,5`, `U = 0,15` → `resumen`, como en el guion de la demo.

### 3.5 Motivos (`Decision.motivos`, máximo 3 frases)

Plantillas en `motivos.py`, en este orden:
1. **Regla dura**, si decidió una: «Me pediste no avisarte de Netflix», «Hoy ya te he avisado 2 veces; lo dejo en el resumen», «Son las 23:10; te lo dejo para mañana en el resumen», «Puede ser una estafa: siempre te lo enseño».
2. **Valor o protección**: «Te faltan 24 € de la cena en La Tasca».
3. **Lo aprendido**: el nivel cuya media más se aleja del anterior (si `n ≥ 1`): «Sueles resolver los avisos de gastos compartidos (2 de 2)», «Con Marcos ya resolviste uno antes», «Los últimos 3 avisos de renovaciones los dejaste pasar».
4. **Arranque en frío** (todas las celdas con `n = 0`): «Aún no sé si estos avisos te interesan; decido por lo que te puede ahorrar».

### 3.6 Qué hace cada `Feedback` (`aprender`)

`aprender` busca el `AvisoAbierto` de la propuesta y suma a **todas sus claves**:

| `resultado` | Efecto |
|---|---|
| `resuelta` | `utiles += 1` |
| `vista_sin_accion` | `utiles += 0,5`, `molestias += 0,5` |
| `rechazada` | `molestias += 1` |
| `ignorada` | `molestias += 1` si fue `notificar_ahora`; `+0,25` si fue `resumen`. La genera el orquestador a las 48 h sin respuesta |
| `no_avisar_tipo` / `_comercio` / `_contacto` | Crea `Silencio` y su hecho («No quieres avisos de Netflix»); además `molestias += 1` |
| `falso_positivo` | No toca la utilidad (el error es del motor): `falsos_positivos[tipo] += 1`, que baja `c` un 20 %. Cuenta en las métricas del banco |

Después regenera los **hechos derivados** (plantillas, deterministas): tipo o tramo con `n ≥ 3` y media ≤ 0,3 («Los avisos de menos de 10 € no suelen interesarte») o ≥ 0,75 («Los avisos de cobros duplicados te resultan útiles»). Apagar o borrar un hecho con `clave` reinicia esa celda o quita el silencio; si no, volvería a aparecer. Los hechos derivados no se editan (mentirían sobre la evidencia): se apagan o se borran. «Olvidar todo» deja solo `consentimientos` y `modulos_activos`.

## 4. Líneas base y memoria

- **`observar(modelo, movimientos, hoy)`**, cada día simulado: actualiza `contactos` (Bizums y transferencias), `series` (por `serie_id`, mediana de importe y de días) y `lineas_base` (gasto semanal por categoría, media móvil exponencial con α = 0,3). **No se guardan** categorías sensibles (salud, farmacia, donaciones, partidos, sindicatos, religión) ni se deriva nada de ellas. Nada de esto puntúa solvencia ni se usa para decidir; sirve para «Lo que he aprendido» y para el contexto del agente.
- **Amigos**: `registrar_decision` crea un `Amigo` (`detectado`) por cada elemento de `gasto_compartido.datos.candidatos` (`{contraparte, importe}`) cuando la decisión no es `silenciar`; si no hay candidato identificado, no se crea y el agente pregunta en la llamada. `registrar_accion` pasa a `pedido` tras `pedir_bizum` correcto (y crea el amigo si faltaba). `observar` lo **salda** cuando entra un Bizum de esa contraparte posterior a la cena: si cubre el saldo, `saldado` y se apuntan los días en `Contacto.dias_devolucion`; si es parcial, resta. **Sin hechos sobre terceros** (revisión de `experto-banca`, AI Act anexo III 5(b) y RGPD 5.1.c): `dias_devolucion` es solo un parámetro interno para programar `recordar` y nunca se muestra ni se dice por persona. Del amigo se guarda el nombre enmascarado, `estado` y `saldo` (nunca teléfono, agenda ni concepto), se borra al saldarse o a los 90 días y aparece, borrable, en «Lo que he aprendido».
- **Memoria de la llamada** (`memoria.py`, requiere consentimiento `memoria`): al colgar, Haiku 5.5 con salida estructurada recibe la transcripción entre `<datos>` y devuelve `{hechos: [{texto ≤ 100, categoria: hecho|preferencia, sobre: contacto|comercio|tipo|general, sensible: bool}]}`. El código descarta los `sensible`, los que coinciden con la lista de términos sensibles, los que parecen órdenes («ignora», «a partir de ahora», «siempre haz», imperativos, URLs, IBAN) y los duplicados; guarda como mucho 3 por llamada y 20 en total, con `origen: voz`. Ante la duda, no se guarda. Estos sí se pueden editar.

## 5. Usuarios simulados y protocolo

Preferencias ocultas en `simulacion/perfiles.py`; la política no puede importarlo (un test lo comprueba). Utilidad oculta `u ∈ {0,1; 0,9}`; **útil ⇔ u ≥ 0,5**. Protección (`posible_estafa`, `saldo_negativo_previsto`) es útil para todos.

| Perfil | Preferencias ocultas |
|---|---|
| `ahorradora` | Útiles gastos compartidos y duplicados; renovaciones solo ≥ 10 €; subidas de recibo solo si el valor ≥ 20 €; `ingreso_extra` nunca |
| `ocupado` | Solo protección y valor ≥ 30 €. A la segunda molestia de un tipo responde `no_avisar_tipo` |
| `social` | Gastos compartidos sí, salvo con «Hermano» (la primera vez, `no_avisar_contacto`); ignora renovaciones y subidas |
| `saturable` | Útil todo lo que vale ≥ 15 €, pero a partir del 4.º aviso de la semana ignora los demás (fatiga que el modelo no captura del todo: lo enseñamos con honestidad) |

**Generador** (`simulacion/generador.py`, semillas 0-9): ~10 propuestas por semana con tipos, comercios (Netflix 12,99, Spotify 10,99, gimnasio 39…), contactos, importes y confianza en [0,7; 0,98]; un 10 % son falsas (el usuario marca `falso_positivo` con p = 0,7). No depende del motor, así se mide ya; `--escenarios` usa los del motor cuando existan.

**Respuesta simulada**: `notificar_ahora` → `resuelta` con p = u; si no, `rechazada` (50 %) o `ignorada`. `resumen` → lo mira con p = 0,6 y resuelve con p = 0,8·u; si no, `ignorada` (peso 0,25). `silenciar` → nada.

**Protocolo**: 6 semanas × 4 perfiles × 10 semillas, tres políticas: `reglas` (notifica todo lo que ahorra o protege), `fija` (mi política sin aprender) y `personalizada`. Salida en `evals/resultados/personalizacion.json`; `/jurado` solo la pinta.

**Lo que ve el jurado** (semana 1 frente a semana 6): precisión de avisos (% de `notificar_ahora` útiles), molestias por semana (avisos no útiles enviados) con `reglas` como referencia, y silenciados por motivo.

| Métrica de `/medir personalizacion` (media de perfiles y semillas) | Objetivo |
|---|---|
| Precisión de `notificar_ahora`, semana 1 → semana 6 | ≥ 0,50 → **≥ 0,80** (`reglas` ≈ 0,45 constante) |
| Molestias evitadas en la semana 6 frente a `reglas` | **≥ 65 %** |
| Cobertura de útiles en la semana 6 (ahora + resumen) | ≥ 0,90; solo en ahora, ≥ 0,75 |
| Arrepentimiento: € de avisos útiles silenciados / € útiles (semanas 1-6) | ≤ 5 % |
| Avisos de protección silenciados | 0 |
| Avisos después de un `no_avisar_*` que coincide | 0 |
| Decisiones con al menos un motivo / tiempo de `decidir` | 100 % / < 5 ms |
| `personalizada` frente a `fija` en la semana 6 | ≥ +20 puntos de precisión (prueba que mejora por aprender) |

## 6. Archivos de `backend/personalizacion/`

| Archivo | Contenido |
|---|---|
| `__init__.py` | Exporta `decidir`, `aprender`, `observar`, `registrar_decision`, `registrar_accion`, `memoria_para_agente`, `nuevo_modelo` |
| `politica.py` | `PARAMETROS`, `VERSION`, claves, Beta jerárquica, utilidad y `decidir` (pura) |
| `aprendizaje.py` | `aprender`, pesos del feedback, silencios, hechos derivados |
| `motivos.py` | Plantillas de motivos y de hechos |
| `amigos.py` | Crear, pedir y saldar amigos |
| `lineas_base.py` | `observar`: contactos, series, gasto semanal (pandas) |
| `memoria.py` | Extracción con Haiku, filtros, `memoria_para_agente` |
| `edicion.py` | Apagar, editar, borrar hechos y olvidar todo |
| `simulacion/{perfiles,generador,protocolo}.py` | Usuarios ocultos, propuestas sintéticas y las 6 semanas |

Tests (sin crédito, `claude_falso`): `tests/test_personalizacion_politica.py` (ejemplo §3.4 exacto, reglas duras, motivos), `test_personalizacion_aprender.py`, `test_amigos.py`, `test_memoria.py` (sensibles e instrucciones descartados) y `test_curva.py` (semilla 0, objetivos de §5 con margen).

## 7. Riesgos y recortes

- **Simulación circular** («habéis hecho el test para aprobar»): perfiles aislados, perfil `saturable` que el modelo no explica bien, tres políticas y 10 semillas. Lo decimos en el pitch.
- **Doble conteo** en la cadena jerárquica (la misma respuesta suma en todos los niveles): sobreconfianza leve; la frena `k = 4`.
- **Pocas señales** (~10 avisos por semana): si la curva sale plana, se sube a 15 y se baja `k` a 2.
- **Hechos sobre terceros**: descartados por `experto-banca` (BLOQUEA). Solo parámetro interno, ver amigos.
- **Sin olvido temporal** (las preferencias no caducan): futura versión con decaimiento semanal.
- **Recortes, en orden**: (1) memoria de la llamada por Haiku (quedan los hechos derivados); (2) nivel de tramo de importe; (3) `lineas_base` por categoría; (4) factor de falsos positivos (queda solo como métrica). No se recorta: reglas duras, motivos, hechos editables, amigos y la curva.

## 8. Cambios propuestos al contrato

1. **`Propuesta`**: añadir `tipo_momento`, `comercio?`, `contraparte?` y `confianza`, copiados del `Momento` por el módulo (sin calcular nada). Sin ellos `decidir(propuesta, …)` no sabe qué aprender ni por qué entidad.
2. **`aprender(feedback, modelo) -> ModeloUsuario`**: recibe y devuelve el modelo (puro), porque el orquestador es el único que escribe. Funciones nuevas que llama el orquestador: `registrar_decision(modelo, propuesta, decision, momento)`, `observar(modelo, movimientos, hoy)`, `registrar_accion(modelo, propuesta, accion_id, parametros, resultado)`; y `memoria_para_agente(modelo) -> str` para `voz`.
3. **`HechoAprendido`**: añadir `clave?` y `creado`. **`Amigo`**: añadir `concepto`, `creado`, `pedido?`, `saldado?`; `estado ∈ {detectado, pedido, saldado, olvidado}`.
4. **`Feedback` `ignorada`**: la emite el orquestador a las 48 h simuladas sin respuesta.
5. Apoyo la propuesta de `modulos.md` de `candidatos: list[{contraparte, importe}]`: de ahí salen los amigos.
