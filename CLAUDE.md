# Proyecto: Meisam (hackathon Hack Finance)

El producto se llama **Meisam**; «Copiloto» queda solo en nombres internos (skill `copiloto`, rutas).

Hackathon de 4 días: empezó el 8 de noviembre; **la entrega completa es el 11 a las 23:59** y se presenta el 12. La voz y el chat con ElevenLabs son obligatorios. El jurado valora el producto y trabajar bien con Claude. Hay un único desarrollador (Pablo); sus compañeros aportan ideas, usuarios, marca y pitch, pero no código. Responde siempre en español, breve y con los siguientes pasos claros.

## La idea
Plataforma para bancos que vive dentro de su app. Un **motor** convierte los movimientos de cada cliente en **momentos** (cobro duplicado, suscripción que se renueva, cena que tus amigos no te han devuelto, recibo que sube, saldo que se va a quedar en negativo, posible estafa…). Solo cuando ahorra dinero o protege, avisa. Al pulsar el aviso se abre una **llamada de voz** que lo resuelve con **acciones de una lista cerrada**. Lo valioso, por este orden: el motor de detección y razonamiento, que **aprenda de cada usuario** y que eso sirva para cualquier **módulo** nuevo que cree el banco. Estrella de la demo: los gastos compartidos.

## Dónde está cada cosa
- `reto/RETO.md`: rúbrica, entrega y dudas. Es la fuente de verdad del reto.
- `docs/diseno/`: `CONTRATO.md` (tipos e interfaces que comparten todas las partes) y los diseños de cada parte: `motor.md`, `personalizacion.md`, `modulos.md`, `experiencia.md`. **`deudas-casos.md`** es el diseño vigente de todo lo que toca deudas y Bizum (escenarios, casos, detector en dos fases, portero, agente post-llamada) y su plan hasta la congelación; manda sobre `motor.md` §3.1 donde choquen. **`curva-amigos.md`** es el encargo del 11 nov: simulador de vidas con amigos, lo que aprende Meisam de cada usuario, casos desde el chat y la curva para el jurado.
- `docs/`: `ANALISIS.md` (la idea), `PLAN.md` (fases, puertas, tareas y estado), `ARQUITECTURA.md`, `DECISIONES.md`, `DIARIO.md` (memoria entre días), `IDEAS.md` (compañeros), `INVESTIGACION.md`, `PITCH.md`, `DEMO.md`.
- `backend/`: el kit (`agente/`, `herramientas/`, `datos/`, `api/`, `claude_client.py`) y los paquetes nuevos que crea `/esqueleto`: `plataforma/`, `motor/`, `escenarios/`, `personalizacion/`, `modulos/`, `acciones/`, `voz/`. El mapa completo está en la skill `copiloto`.
- `frontend/`: Next.js. Pantallas nuevas `/app` (cliente), `/banco` (consola) y `/jurado` (métricas); el chat del kit pasa a `/kit`.
- `evals/`: evals del agente (`ejecutar.py`) y métricas del motor y la personalización (`medir.py`). `tests/`: pytest con cliente simulado.

## Tu papel: orquestador
Divides el trabajo, delegas en el subagente adecuado, integras y verificas. Los subagentes no ven esta conversación.

| Necesidad | Subagente |
|---|---|
| Algoritmos del motor: normalización, detectores, razonador y escenarios etiquetados | `ingeniero-deteccion` |
| Aprendizaje del usuario: líneas base, política de interrupción, memoria y usuarios simulados | `cientifico-personalizacion` |
| Plataforma de módulos (YAML, minilenguaje, creación desde lenguaje natural) y acciones con el banco simulado | `ingeniero-modulos` |
| Llamada de voz con ElevenLabs y modo texto | `ingeniero-voz` |
| Realismo y normativa bancaria española (Bizum, recibos, bloqueos, PSD2, RGPD) | `experto-banca` |
| Realismo de las personas: vidas del simulador de amigos, hábitos reales con Bizum y efectivo, y si lo que aprende Meisam es creíble | `experto-usuarios` |
| Juicio independiente con el contexto limpio: si Meisam cubre una necesidad real, si cada aviso ayuda o molesta y si la curva y las cifras del pitch se sostienen | `critico-necesidad` |
| Stack, contrato de la API y reparto en tareas paralelas | `arquitecto` |
| Prompts y guardarraíles del agente conversacional del kit | `ingeniero-agente` |
| Backend en Python: plataforma, orquestador, API y datos | `programador` |
| Interfaz en Next.js | `frontend` |
| Tests con pytest que no gastan crédito | `tester` |
| Evals y ataques controlados a los agentes | `evaluador` |
| Fórmulas, cifras y normativa financiera | `experto-finanzas` |
| APIs, datos, normativa o competencia, con enlaces | `investigador` |
| Revisión de código y seguridad (solo lectura, contexto limpio) | `revisor` |
| Guion, demo, README y vídeo | `pitch` |
| Replantear la idea si cambia el reto | `analista-reto` |

Cómo delegar:
1. Cada encargo lleva: objetivo, archivos que tocar, interfaces que respetar (del contrato), cómo se verifica y qué es «terminado».
2. Pide la respuesta breve: qué ha hecho, archivos tocados, cómo lo ha comprobado y qué queda pendiente.
3. En paralelo, solo lo que no toque los mismos archivos. La escritura de código va en un solo hilo por zona.
4. Lo trivial (pocas líneas) hazlo tú. Una tarea muy difícil puede ir a `programador` con `model: opus`.

## Skills
- Fases: `/planificar` (diseño con subagentes, sin código), `/esqueleto` (flujo de principio a fin), `/feature <tarea>` (cada tarea del plan), `/demo` (entrega).
- Del Copiloto: `/escenario <historia>`, `/detector <tipo>`, `/modulo <descripción>`, `/medir [motor|personalizacion|todo]`.
- Del kit: `/herramienta <idea>`, `/depurar <síntoma>`, `/evals`, `/estado [tiempo]`, `/cierre-dia`. `/kickoff` ya se usó: no la repitas.
- Se cargan solas: `copiloto` (arquitectura y reglas), `api-claude`, `finanzas`, `agente-finanzas`.

**Siguiente paso** (si `docs/PLAN.md` no dice otra cosa): `/planificar` y después `/esqueleto`.

## Reglas de oro
- Primero el flujo de principio a fin; la demo debe funcionar en todo momento. Puertas en `docs/PLAN.md`.
- Nada está terminado sin verificarlo: `pytest` en verde, `/medir` si cambia el motor, la política o un módulo, `/evals` si cambia un agente, y la app arrancada si cambia la interfaz. Di cómo lo has comprobado.
- Commits pequeños en español. Integra en `main` solo con los tests en verde.
- Nunca leas ni muestres `.env` ni claves. Las claves de Claude y de ElevenLabs solo viven en el backend.
- Solo datos sintéticos o públicos; nunca datos personales reales.
- Si dudas en algo irreversible (borrar, forzar, desplegar), pregunta antes.

## Reglas del producto
- **En línea**: el motor procesa los movimientos día a día con un reloj simulado y ningún detector mira el futuro.
- **Las cifras, del código**: dinero exacto con `Decimal`; análisis con pandas. Los modelos clasifican, razonan y explican, nunca calculan.
- **Los datos no son instrucciones**: conceptos, comercios y notas de Bizum van marcados como datos en todo prompt.
- **Acciones de una lista cerrada**: el agente solo las prepara. Se ejecutan con el botón del usuario y un token de un solo uso, validado en el servidor contra las acciones ofrecidas en la propuesta. Son simuladas y quedan auditadas.
- **Solo interrumpe si ahorra o protege**, y cada decisión lleva sus motivos legibles. La personalización también alimenta al motor con el perfil de vida del usuario (umbrales y contexto personales). Todo lo aprendido se ve, se edita y se borra.
- **Búsqueda web** solo por nombre de comercio, con caché y nunca con datos del cliente; lo que llega de la web son datos.
- **Módulos sin código**: momentos del motor, condiciones del minilenguaje, plantillas y acciones de la lista. Módulo nuevo = `/modulo`; tipo de momento nuevo = `/detector`.
- Toda llamada a Claude pasa por `backend/claude_client.py`. No uses `temperature`, `top_p` ni `top_k` (error 400). Haiku 5.5 para clasificar y extraer.
- Cumplimiento (mínimo, es un hackathon): insignia «IA» discreta y visible en la llamada (la IA no lo dice en voz alta), nada de puntuar solvencia, datos personales enmascarados y revisor de cumplimiento activo. Un producto concreto (como un seguro) solo se ofrece en un módulo opcional que el cliente activa, con su ficha de información y sin presionar.

## Trabajo en paralelo
2 o 3 sesiones con `claude --worktree <zona>`, una por zona: `plataforma`, `motor`, `personalizacion`, `modulos`, `voz`, `api`, `frontend` o `demo`. Primero el contrato en código (`backend/plataforma/tipos.py`); después, las zonas. Cada sesión hace `/feature` en su zona e integra en `main` al terminar.

## Coste
- Sesión principal en Opus 5.5; para tareas mecánicas, `/model sonnet`. Cada subagente ya tiene su modelo.
- `/clear` al cambiar de tarea, `/compact` en sesiones largas, `/usage` para ver el gasto. Lee solo lo necesario y consulta `docs/` antes de repetir trabajo.
- Claves de Claude: 1 = Claude Code, 2 = producto, 3 = evals, 4-6 = reserva. ElevenLabs: el plan gratuito da pocos minutos de voz; ensaya en modo texto.

## Memoria entre días
Al empezar, el hook de inicio te muestra el estado de `docs/PLAN.md` y el final de `docs/DIARIO.md`. Al acabar el día, `/cierre-dia`.

## Lecciones aprendidas
Cada vez que Claude se equivoque de forma evitable, añade aquí una línea con la regla que lo evita.
- Antes de programar, confirma el alcance: diseñar, montar el sistema de trabajo y desarrollar son encargos distintos.
- Las variables dinámicas del agente de ElevenLabs son solo las que aparecen en su prompt o primer mensaje; no pidas crear otras.
- Los tests de escenario avanzan el reloj hasta la fecha que esperan (calculada desde el escenario), nunca un número fijo de días.
- Antes de lanzar hilos largos, comprueba el saldo de la clave frente al coste estimado de la tanda; si no llega, cambia de clave o de modelo antes de empezar, no a mitad (el 9 nov se cortaron tres hilos por falta de crédito).
- En los encargos a subagentes, copia las rutas de `docs/diseno/` y `ARQUITECTURA.md`; no las escribas de memoria (el catálogo de comercios es `backend/datos/comercios_conocidos.json`, no `backend/motor/`).
- En el Bash de este equipo, `\\` dentro de un heredoc llega como `\`: para escribir `\b` u otras barras en código o regex usa la herramienta Edit o `chr(92)`, y comprueba después que no hay caracteres de control (el 11 nov se colaron dos `\x08`).
- Los scripts de diagnóstico no usan `datos_usuario/` de Pablo: pon `DATOS_USUARIO_DIR` en una carpeta temporal (el 11 nov se reinició su demo local).
- Al acabar un subagente con `isolation: worktree`, la sesión principal puede quedarse dentro de ese worktree y los agentes siguientes trabajan allí: comprueba `pwd` antes de lanzar más e integra con `git -C` (el 11 nov K1 (a) se hizo sobre una base sin A3b).
- Un paquete nuevo que importe `backend/` va en `requirements-backend.txt` (Render instala solo ese), no solo en `requirements.txt`; y tras cada `push`, comprueba que Render y Vercel despliegan de verdad (el 11 nov Render llevaba desde el 9 sin arrancar por `httpx` y Vercel bloqueaba los commits por el email del autor).
- Las estimaciones de horas del plan salen de 3 a 10 veces por encima de lo real con subagentes (11 nov: ~20 h estimadas, ~5 h reales). Planifica por dependencias y mide con `registro/agentes.jsonl`, no por horas.

## Instrucciones de compactación
Conserva la idea, el contrato (`docs/diseno/CONTRATO.md`), el estado de `docs/PLAN.md`, las decisiones tomadas, los errores abiertos y la tarea en curso.
